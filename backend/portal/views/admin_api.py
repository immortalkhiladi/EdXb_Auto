import re
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.utils import timezone

from ..api import EMAIL_RE, ApiError, admin_required, all_documents_required, error, methods, read_json
from ..models import AuditLog, Document, User, UserToolAccess
from ..security import password_error
from ..services import audit, doc_out, iso, user_out
from ..storage import get_storage
from ..tools import TOOLS
from .documents import apply_filters, page_params, paginate, parse_date

SHOWN_AUDIT_ACTIONS = ("auth.login", "auth.logout")
USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]{3,64}$")


@methods("GET")
@all_documents_required
def admin_documents(request):
    g = request.GET
    qs = Document.objects.select_related("owner")
    if g.get("include_deleted") not in ("1", "true"):
        qs = qs.filter(deleted_at__isnull=True)
    if g.get("user"):
        qs = qs.filter(Q(owner__id=g["user"]) | Q(owner__username=g["user"].lower()))
    return JsonResponse(paginate(request, apply_filters(qs, g), include_owner=True))


@methods("GET", "POST")
@admin_required
def admin_users(request):
    admin = request.api_user
    if request.method == "GET":
        users = User.objects.prefetch_related("tool_access").annotate(document_count=Count("documents", filter=Q(documents__deleted_at__isnull=True))).order_by("role", "username")
        return JsonResponse({"items": [{**user_out(u), "document_count": u.document_count} for u in users]})

    b = read_json(request)
    username, email = str(b.get("username", "")).lower(), str(b.get("email", "")).lower()
    full_name, password, role = str(b.get("full_name", "")).strip(), str(b.get("password", "")), str(b.get("role", "USER"))
    if not USERNAME_RE.match(username) or not EMAIL_RE.match(email) or len(email) > 255 or not (1 <= len(full_name) <= 150) \
            or role not in ("ADMIN", "MD", "USER"):
        return error("Invalid request.", 422)
    problem = password_error(password)
    if problem:
        return error(problem, 422)
    if User.objects.filter(Q(username=username) | Q(email=email)).exists():
        return error("A user with that User ID or email already exists.", 409)
    tools = b.get("tools")  # optional list of tool slugs for a USER; omitted = all four
    if tools is not None and (not isinstance(tools, list) or any(t not in TOOLS for t in tools)):
        return error("Unknown tool in the tool list.", 422)
    u = User.objects.create_user(username, email, full_name, password, role, tools=sorted(set(tools)) if tools is not None else None)
    audit(request, "admin.user.create", actor=admin, resource_type="user", resource_id=u.id, detail=f"{u.username} ({u.role})")
    return JsonResponse({"user": user_out(u)}, status=201)


@methods("PATCH", "DELETE")
@admin_required
def admin_user_patch(request, user_id):
    admin = request.api_user
    u = User.objects.filter(id=user_id).first()
    if not u:
        return error("User not found.", 404)
    if request.method == "DELETE":
        return _delete_user(request, admin, u)
    b = read_json(request)
    changes, revoke = [], False

    new_role = b.get("role")
    new_active = b.get("is_active")
    if new_role is not None and new_role not in ("ADMIN", "MD", "USER"):
        return error("Invalid request.", 422)
    if new_active is not None and not isinstance(new_active, bool):
        return error("Invalid request.", 422)
    if u.id == admin.id and (new_active is False or (new_role and new_role != "ADMIN")):
        return error("You cannot deactivate or demote your own account.", 400)

    email = b.get("email")
    if email is not None:
        email = str(email).lower()
        if not EMAIL_RE.match(email) or len(email) > 255:
            return error("Invalid request.", 422)
        if email != u.email:
            if User.objects.filter(email=email).exclude(id=u.id).exists():
                return error("That email is already in use.", 409)
            u.email = email
            changes.append("email")
    if b.get("full_name"):
        name = str(b["full_name"]).strip()
        if len(name) > 150:
            return error("Invalid request.", 422)
        u.full_name = name
        changes.append("name")
    if new_role and new_role != u.role:
        u.role = new_role
        changes.append(f"role={new_role}")
        if new_role == "USER" and not u.tool_access.exists():  # demoted ADMIN/MD keeps using the tools (admin can then narrow them)
            UserToolAccess.objects.bulk_create([UserToolAccess(user=u, tool=t) for t in TOOLS])
        revoke = True
    if new_active is not None and new_active != u.is_active:
        u.is_active = new_active
        changes.append("activated" if new_active else "deactivated")
        revoke = revoke or not new_active
    if b.get("unlock"):
        u.locked_until, u.failed_attempts = None, 0
        changes.append("unlocked")
    if b.get("reset_mfa"):
        u.mfa_enabled, u.totp_secret_enc, u.last_totp_step = False, None, None
        changes.append("mfa reset")
        revoke = True
    if b.get("new_password"):
        pw = str(b["new_password"])
        problem = password_error(pw)
        if problem:
            return error(problem, 422)
        u.set_password(pw)
        changes.append("password reset")
        revoke = True
    if revoke:
        u.session_epoch += 1  # signs the user out everywhere

    # never leave the system without an active administrator
    if not (u.role == "ADMIN" and u.is_active) and not User.objects.filter(role="ADMIN", is_active=True).exclude(id=u.id).exists():
        return error("At least one active administrator is required.", 400)

    u.save()
    audit(request, "admin.user.update", actor=admin, resource_type="user", resource_id=u.id,
          detail=f"{u.username}: {', '.join(changes) or 'no change'}")
    return JsonResponse({"user": user_out(u)})


def _delete_user(request, admin, u):
    """Permanently deletes a user. Their tool-access rows cascade; their documents (PROTECT) are removed explicitly and
    their stored files are deleted after the transaction commits. Audit rows keep a plain-text actor reference, so they stay."""
    if u.id == admin.id:
        return error("You cannot delete your own account.", 400)
    with transaction.atomic():
        # lock active admins so two concurrent deletes cannot remove the last one
        active_admins = list(User.objects.select_for_update().filter(role="ADMIN", is_active=True).values_list("id", flat=True))
        if u.role == "ADMIN" and u.is_active and not [i for i in active_admins if i != u.id]:
            return error("The last active administrator cannot be deleted.", 400)
        docs = list(Document.objects.filter(owner=u).values_list("original_key", "output_key"))
        Document.objects.filter(owner=u).delete()
        username, role, uid = u.username, u.role, u.id
        u.delete()
    storage = get_storage()
    for keys in docs:
        for k in keys:
            if k:
                try:
                    storage.delete(k)
                except Exception:
                    pass  # an orphaned file is harmless and never blocks the deletion
    audit(request, "admin.user.delete", actor=admin, resource_type="user", resource_id=uid,
          detail=f"{username} ({role}); {len(docs)} document(s) removed")
    return JsonResponse({"status": "ok", "message": f"User {username} deleted."})


@methods("GET")
@admin_required
def audit_logs(request):
    """Audit Log page: ONLY successful sign-in / sign-out events (who, which event, when). Everything else is still
    recorded in the table for security investigations but is never listed here."""
    g = request.GET
    qs = AuditLog.objects.filter(action__in=SHOWN_AUDIT_ACTIONS, outcome="success", actor_name__isnull=False)
    if g.get("actor"):
        qs = qs.filter(actor_name__icontains=g["actor"])
    if g.get("action"):
        qs = qs.filter(action__startswith=g["action"])
    if g.get("outcome") and g["outcome"] != "success":
        qs = qs.none()
    if g.get("date_from"):
        qs = qs.filter(created_at__gte=parse_date(g["date_from"]))
    if g.get("date_to"):
        qs = qs.filter(created_at__lt=parse_date(g["date_to"]) + timedelta(days=1))
    page, size = page_params(request, default_size=25, max_size=200)
    total = qs.count()
    rows = qs.order_by("-id")[(page - 1) * size: page * size]
    return JsonResponse({
        "items": [{"id": r.id, "created_at": iso(r.created_at), "actor": r.actor_name, "action": r.action,
                   "resource_type": None, "resource_id": None, "outcome": r.outcome,
                   "ip": r.ip, "detail": None} for r in rows],
        "total": total, "page": page, "page_size": size})


@methods("GET")
@admin_required
def overview(request):
    since = timezone.now() - timedelta(hours=24)
    live = Document.objects.filter(deleted_at__isnull=True)
    by_status = dict(live.values_list("status").annotate(n=Count("id")))
    by_tool = dict(live.values_list("tool").annotate(n=Count("id")))
    storage_bytes = live.filter(purged_at__isnull=True).aggregate(s=Sum("output_size") + Sum("original_size"))["s"] or 0
    failed = Document.objects.select_related("owner").filter(status="failed").order_by("-created_at")[:10]
    try:
        users_count = User.objects.aggregate(total=Count("id"), active=Count("id", filter=Q(is_active=True)))
        db_ok = True
    except Exception:
        users_count, db_ok = {"total": 0, "active": 0}, False
    return JsonResponse({
        "users": users_count,
        "documents": {"total": sum(by_status.values()), "by_status": by_status,
                      "by_tool": {TOOLS[k].label if k in TOOLS else k: v for k, v in by_tool.items()}},
        "storage_bytes": int(storage_bytes),
        "failed_logins_24h": AuditLog.objects.filter(action="auth.login", created_at__gte=since).exclude(outcome="success").count(),
        "recent_failed_jobs": [doc_out(d, include_owner=True) for d in failed],
        "health": {"database": "ok" if db_ok else "error", "storage": "ok" if get_storage().healthy() else "error"},
    })


def _tool_row(u) -> dict:
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role, "is_active": u.is_active,
            "all_access": u.role != "USER", "tools": sorted(u.allowed_tool_slugs())}


@methods("GET", "PUT")
@admin_required
def admin_tool_access(request):
    """ADMIN only. GET: every user with the tools they may use. PUT {"changes": [{"user_id", "tools": [slug, ...]}]}:
    replaces those users' tool lists (all-or-nothing). Only USER accounts are configurable: ADMIN and MD always have all tools."""
    admin = request.api_user
    if request.method == "GET":
        users = User.objects.prefetch_related("tool_access").order_by("role", "username")
        return JsonResponse({"tools": [{"slug": t.slug, "label": t.label} for t in TOOLS.values()], "users": [_tool_row(u) for u in users]})

    changes = read_json(request).get("changes")
    if not isinstance(changes, list) or not changes or len(changes) > 1000:
        return error("No changes to save.", 422)
    wanted = {}
    for c in changes:
        uid, tools = (c.get("user_id"), c.get("tools")) if isinstance(c, dict) else (None, None)
        if not isinstance(uid, str) or not isinstance(tools, list) or any(not isinstance(t, str) for t in tools):
            return error("Invalid request.", 422)
        unknown = [t for t in tools if t not in TOOLS]
        if unknown:
            return error("Unknown tool: " + ", ".join(unknown[:3]) + ".", 422)
        wanted[uid] = set(tools)
    users = {u.id: u for u in User.objects.prefetch_related("tool_access").filter(id__in=wanted)}
    if len(users) != len(wanted):
        return error("One or more users were not found.", 404)
    for u in users.values():
        if u.role != "USER":
            return error(f"{u.username} is {u.role}: ADMIN and MD accounts always have access to all tools.", 422)

    updated = []
    with transaction.atomic():
        for uid, new in wanted.items():
            u = users[uid]
            old = {a.tool for a in u.tool_access.all()}
            if old == new:
                continue
            UserToolAccess.objects.filter(user=u).exclude(tool__in=new).delete()
            UserToolAccess.objects.bulk_create([UserToolAccess(user=u, tool=t) for t in sorted(new - old)])
            updated.append(u.username)
            audit(request, "admin.user.tools", actor=admin, resource_type="user", resource_id=u.id,
                  detail=f"{u.username}: granted [{', '.join(sorted(new - old))}] revoked [{', '.join(sorted(old - new))}]")
    return JsonResponse({"status": "ok", "updated": len(updated), "message": f"Tool access saved for {len(updated)} user(s)." if updated else "No changes to save."})
