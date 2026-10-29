import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone

from .tools import TOOLS


def new_id() -> str:
    """Non-guessable identifier (122 random bits)."""
    return uuid.uuid4().hex


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, email, full_name, password, role="USER", tools=None):
        user = self.model(username=username.lower(), email=email.lower(), full_name=full_name, role=role)
        user.set_password(password)  # Argon2id
        user.save(using=self._db)
        if role == "USER":  # ADMIN / MD always have every tool; a USER gets the tools the admin picks (default: all four)
            UserToolAccess.objects.bulk_create([UserToolAccess(user=user, tool=t) for t in (TOOLS if tools is None else tools)])
        return user


class User(AbstractBaseUser):
    ROLES = [("ADMIN", "ADMIN"), ("MD", "MD"), ("USER", "USER")]
    id = models.CharField(max_length=32, primary_key=True, default=new_id, editable=False)
    username = models.CharField(max_length=64, unique=True)
    email = models.CharField(max_length=255, unique=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=16, choices=ROLES, default="USER")
    is_active = models.BooleanField(default=True)
    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    totp_secret_enc = models.TextField(null=True, blank=True)
    last_totp_step = models.BigIntegerField(null=True, blank=True)
    session_epoch = models.IntegerField(default=0)  # bump = every existing session of this user is revoked
    created_at = models.DateTimeField(default=timezone.now)

    objects = UserManager()
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "full_name"]

    class Meta:
        indexes = [models.Index(fields=["role"])]

    @property
    def is_admin(self) -> bool:
        return self.role == "ADMIN"

    @property
    def can_view_all_documents(self) -> bool:
        """ADMIN and MD may open every user's documents; USER only their own."""
        return self.role in ("ADMIN", "MD")

    def allowed_tool_slugs(self) -> set:
        """Tools this account may use. ADMIN and MD: all four. USER: only what the admin assigned (read from the database on
        every call, so a revoked tool stops working immediately)."""
        if self.role in ("ADMIN", "MD"):
            return set(TOOLS)
        # A user object lives for one request, so memoising here keeps "read from the database on every request" while
        # avoiding repeated identical queries within that request (list view, filters, access checks...).
        cached = self.__dict__.get("_tool_slugs")
        if cached is None:
            cached = {a.tool for a in self.tool_access.all()} & set(TOOLS)  # uses prefetch_related("tool_access") when present
            self.__dict__["_tool_slugs"] = cached
        return set(cached)

    def can_use_tool(self, slug: str) -> bool:
        return slug in self.allowed_tool_slugs()


class UserToolAccess(models.Model):
    """One row = this USER may use this tool (slug from tools.TOOLS). Managed by ADMIN under Admin Console > Tool Access."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tool_access")
    tool = models.CharField(max_length=40)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "tool"], name="uniq_user_tool")]


class Document(models.Model):
    id = models.CharField(max_length=32, primary_key=True, default=new_id, editable=False)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="documents")
    tool = models.CharField(max_length=40, db_index=True)  # slug, e.g. ppt-pdf-converter
    document_name = models.CharField(max_length=200)
    original_filename = models.CharField(max_length=200, null=True, blank=True)
    output_filename = models.CharField(max_length=200, null=True, blank=True)
    original_key = models.CharField(max_length=120, null=True, blank=True)  # private storage key, never sent to clients
    output_key = models.CharField(max_length=120, null=True, blank=True)
    file_type = models.CharField(max_length=16, null=True, blank=True)
    original_size = models.BigIntegerField(default=0)
    output_size = models.BigIntegerField(default=0)
    status = models.CharField(max_length=16, default="processing", db_index=True)  # processing | completed | failed
    error_summary = models.CharField(max_length=300, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["owner", "created_at"])]


class AuditLog(models.Model):
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    actor_id = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    actor_name = models.CharField(max_length=64, null=True, blank=True)
    action = models.CharField(max_length=64, db_index=True)
    resource_type = models.CharField(max_length=32, null=True, blank=True)
    resource_id = models.CharField(max_length=64, null=True, blank=True)
    outcome = models.CharField(max_length=16, db_index=True)  # success | failure | denied
    ip = models.CharField(max_length=64, null=True, blank=True)
    detail = models.CharField(max_length=500, null=True, blank=True)


class StoredFile(models.Model):
    """One uploaded/generated file kept INSIDE the database (PostgreSQL), split into fixed-size chunk rows so a 50 MB file
    never has to sit in one row or fully in memory. Addressed only by the random storage key held in Document.*_key."""
    key = models.CharField(max_length=120, primary_key=True)
    size = models.BigIntegerField(default=0)
    chunk_size = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)


class StoredFileChunk(models.Model):
    file = models.ForeignKey(StoredFile, on_delete=models.CASCADE, related_name="chunks", db_column="file_key")
    seq = models.IntegerField()
    data = models.BinaryField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["file", "seq"], name="uniq_file_chunk")]
