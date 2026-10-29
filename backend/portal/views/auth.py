import hmac
import logging
import time
from datetime import timedelta

import pyotp
from django.conf import settings
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import F, Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from ..api import EMAIL_RE, ApiError, api_login_required, error, methods, read_json
from ..models import User
from ..security import decrypt_secret, encrypt_secret, limiter, password_error
from ..services import audit, client_ip, user_out

log = logging.getLogger("portal")
GENERIC_LOGIN_ERROR = "Invalid credentials, or the account is temporarily locked."
BACKEND = "django.contrib.auth.backends.ModelBackend"
_dummy = None


def _dummy_hash() -> str:
    global _dummy
    if _dummy is None:
        _dummy = make_password("not-a-real-password-used-for-timing")
    return _dummy


def _verify(user, password: str) -> bool:
    """Always performs one Argon2 verification (dummy hash for unknown users) to equalise timing."""
    if user is None:
        check_password(password, _dummy_hash())
        return False

    def upgrade(raw):  # re-hash with the current (tuned) Argon2 parameters after a successful check
        user.set_password(raw)
        User.objects.filter(pk=user.pk).update(password=user.password)

    return bool(check_password(password, user.password, setter=upgrade))


def _register_failure(user: User):
    # atomic increment: concurrent wrong passwords for the same account can no longer overwrite each other's count
    User.objects.filter(pk=user.pk).update(failed_attempts=F("failed_attempts") + 1)
    user.refresh_from_db(fields=["failed_attempts", "locked_until"])
    if user.failed_attempts >= settings.MAX_FAILED_LOGINS:
        user.locked_until = timezone.now() + timedelta(minutes=settings.LOCKOUT_MINUTES)
        user.failed_attempts = 0
        user.save(update_fields=["failed_attempts", "locked_until"])


def _is_locked(user: User) -> bool:
    return bool(user.locked_until and user.locked_until > timezone.now())


def _start_session(request, user: User):
    login(request, user, backend=BACKEND)  # rotates the session key (no fixation) and the CSRF token
    request.session["epoch"] = user.session_epoch
    request.session["login_ts"] = time.time()


@methods("GET")
def csrf(request):
    """The SPA reads the token from the response body (works for split hosting where cookies are not readable)."""
    return JsonResponse({"csrfToken": get_token(request)})


@methods("POST")
def login_view(request):
    body = read_json(request)
    username, password = str(body.get("username", "")).strip(), str(body.get("password", ""))
    if not username or not password or len(password) > 256:
        return error("Invalid request.", 422)
    ip = client_ip(request)
    ident = username.lower()
    # per IP + account (brute force on one account) and a much higher per-IP ceiling (spraying many accounts).
    # A single per-IP limit blocked whole offices that sign in from one shared public IP.
    window = settings.LOGIN_RATE_WINDOW_SECONDS
    if not limiter.hit(f"login:{ip}:{ident[:64]}", settings.LOGIN_RATE_LIMIT, window) or \
            not limiter.hit(f"login-ip:{ip}", settings.LOGIN_IP_RATE_LIMIT, window):
        audit(request, "auth.login", "denied", actor_name=username[:64], detail="rate limited")
        return error("Too many attempts. Please wait and try again.", 429)

    user = User.objects.filter(Q(username=ident) | Q(email=ident)).first()
    ok = _verify(user, password)
    if not user or not ok or not user.is_active or _is_locked(user):
        if user and not ok and user.is_active and not _is_locked(user):
            _register_failure(user)
        audit(request, "auth.login", "failure", actor_name=ident[:64], detail="invalid credentials or locked/inactive")
        return error(GENERIC_LOGIN_ERROR, 401)

    if user.failed_attempts:  # no write on the common path
        user.failed_attempts = 0
        user.save(update_fields=["failed_attempts"])

    needs_mfa = user.mfa_enabled
    needs_setup = (not user.mfa_enabled) and user.is_admin and settings.ADMIN_MFA_REQUIRED
    if needs_mfa or needs_setup:
        request.session.flush()  # new, anonymous session that only carries the pending-MFA marker
        request.session["pending_mfa"] = {"uid": user.id, "at": time.time()}
        audit(request, "auth.login.password_ok", "success", actor=user, detail="mfa pending")
        return JsonResponse({"status": "mfa_required" if needs_mfa else "mfa_setup_required"})

    _start_session(request, user)
    audit(request, "auth.login", "success", actor=user)
    return JsonResponse({"status": "ok", "user": user_out(user)})


def _pending_user(request) -> User:
    p = request.session.get("pending_mfa")
    if not p or time.time() - p.get("at", 0) > settings.MFA_PENDING_MINUTES * 60:
        raise ApiError(401, "Not authenticated.")
    user = User.objects.filter(id=p["uid"], is_active=True).first()
    if not user:
        raise ApiError(401, "Not authenticated.")
    return user


@methods("POST")
def mfa_setup(request):
    user = _pending_user(request)
    if user.mfa_enabled:
        return error("MFA is already enabled.", 400)
    secret = pyotp.random_base32()
    user.totp_secret_enc = encrypt_secret(secret)
    user.save(update_fields=["totp_secret_enc"])
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.username, issuer_name="EDGAR Agents LLC")
    return JsonResponse({"secret": secret, "otpauth_uri": uri})


@methods("POST")
def mfa_verify(request):
    code = str(read_json(request).get("code", "")).strip()
    ip = client_ip(request)
    pending_uid = (request.session.get("pending_mfa") or {}).get("uid", "")
    if not limiter.hit(f"mfa:{ip}:{pending_uid}", settings.LOGIN_RATE_LIMIT, settings.LOGIN_RATE_WINDOW_SECONDS) or \
            not limiter.hit(f"mfa-ip:{ip}", settings.LOGIN_IP_RATE_LIMIT, settings.LOGIN_RATE_WINDOW_SECONDS):
        return error("Too many attempts. Please wait and try again.", 429)
    user = _pending_user(request)
    if not user.totp_secret_enc or _is_locked(user):
        return error("Not authenticated.", 401)
    totp = pyotp.TOTP(decrypt_secret(user.totp_secret_enc))
    now_step = int(time.time() // 30)
    matched = None
    for step in (now_step - 1, now_step, now_step + 1):
        if hmac.compare_digest(totp.at(step * 30), code):
            matched = step
    if matched is None or (user.last_totp_step is not None and matched <= user.last_totp_step):
        _register_failure(user)
        audit(request, "auth.mfa", "failure", actor=user)
        return error("Invalid or expired code.", 401)

    user.last_totp_step = matched  # a code can only be used once
    user.mfa_enabled = True
    user.save(update_fields=["last_totp_step", "mfa_enabled"])
    request.session.pop("pending_mfa", None)
    _start_session(request, user)
    audit(request, "auth.mfa", "success", actor=user)
    audit(request, "auth.login", "success", actor=user)  # the sign-in is complete only now
    return JsonResponse({"status": "ok", "user": user_out(user)})


@methods("GET")
@api_login_required
def me(request):
    return JsonResponse({"user": user_out(request.api_user)})


@methods("POST")
def logout_view(request):
    actor = request.user if request.user.is_authenticated else None
    logout(request)  # deletes the server-side session
    audit(request, "auth.logout", "success", actor=actor)
    return JsonResponse({"status": "ok"})


@methods("POST")
@api_login_required
def change_password(request):
    user = request.api_user
    body = read_json(request)
    current, new = str(body.get("current_password", "")), str(body.get("new_password", ""))
    if not check_password(current, user.password):
        audit(request, "auth.password_change", "failure", actor=user, detail="wrong current password")
        return error("Current password is incorrect.", 400)
    problem = password_error(new)
    if problem:
        return error(problem, 422)
    user.set_password(new)
    user.session_epoch += 1  # revokes every other session of this user
    user.save(update_fields=["password", "session_epoch"])
    request.session["epoch"] = user.session_epoch  # keep THIS session ...
    update_session_auth_hash(request, user)         # ... Django ties sessions to the password hash
    audit(request, "auth.password_change", "success", actor=user)
    return JsonResponse({"status": "ok"})


# ---------------------------------------------------------------- forgot / reset password
# No passwords are ever sent or stored in clear text: the user gets a signed link whose token is bound to their
# current password hash and last login, expires after PASSWORD_RESET_MINUTES and stops working once used.
RESET_LINK_ERROR = "This password reset link is invalid or has expired. Please request a new one."


@methods("POST")
def forgot_password(request):
    email = str(read_json(request).get("email", "")).strip().lower()
    ip = client_ip(request)
    if not limiter.hit(f"forgot:{ip}", settings.PASSWORD_RESET_RATE_LIMIT, settings.LOGIN_RATE_WINDOW_SECONDS):
        audit(request, "auth.password_reset.request", "denied", detail="rate limited")
        return error("Too many reset requests. Please wait a few minutes and try again.", 429)
    if not email or len(email) > 255 or not EMAIL_RE.match(email):
        return error("Please enter a valid email address.", 422)

    sent = JsonResponse({"status": "ok", "message": "A password reset link has been sent to your email address. It is valid for "
                         f"{settings.PASSWORD_RESET_TIMEOUT // 60} minutes."})
    user = User.objects.filter(email=email, is_active=True).first()
    if user is None:
        audit(request, "auth.password_reset.request", "failure", detail="no active account for that email")
        if settings.PASSWORD_RESET_REVEAL_ACCOUNT:
            return error("No active account was found for that email address.", 404)
        return sent
    if not limiter.hit(f"forgot-user:{user.id}", 3, 3600):  # stops someone flooding one person's inbox
        audit(request, "auth.password_reset.request", "denied", actor=user, detail="per-user rate limit")
        return error("A reset link was already requested recently. Please check your email or try again later.", 429)

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    base = settings.FRONTEND_URL or request.build_absolute_uri("/").rstrip("/")
    link = f"{base}/reset-password?uid={uid}&token={token}"
    try:
        send_mail(
            "Reset your EDGAR Agents LLC password",
            f"Hello {user.full_name},\n\nWe received a request to reset the password for your EDGAR Agents LLC account "
            f"(User ID: {user.username}).\n\nChoose a new password here (valid for {settings.PASSWORD_RESET_TIMEOUT // 60} minutes, "
            f"one use only):\n{link}\n\nIf you did not ask for this, ignore this email - your password has not changed.\n",
            settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False,
        )
    except Exception:
        log.exception("password reset email could not be sent")
        audit(request, "auth.password_reset.request", "failure", actor=user, detail="email delivery failed")
        return error("We could not send the reset email right now. Please try again later or contact your administrator.", 503)
    audit(request, "auth.password_reset.request", "success", actor=user)
    return sent


@methods("POST")
def reset_password(request):
    body = read_json(request)
    uid, token, new = str(body.get("uid", "")), str(body.get("token", "")), str(body.get("new_password", ""))
    if not limiter.hit(f"reset:{client_ip(request)}", settings.PASSWORD_RESET_RATE_LIMIT * 4, settings.LOGIN_RATE_WINDOW_SECONDS):
        return error("Too many attempts. Please wait and try again.", 429)
    try:
        user = User.objects.filter(pk=force_str(urlsafe_base64_decode(uid)), is_active=True).first()
    except (ValueError, TypeError, OverflowError, UnicodeDecodeError):
        user = None
    if user is None or not token or not default_token_generator.check_token(user, token):
        audit(request, "auth.password_reset.complete", "failure", actor=user, detail="invalid or expired link")
        return error(RESET_LINK_ERROR, 400)
    problem = password_error(new)  # checked after the link so a weak password does not use up the link
    if problem:
        return error(problem, 422)
    user.set_password(new)  # Argon2id; this also invalidates the link that was just used
    user.failed_attempts, user.locked_until = 0, None
    user.session_epoch += 1  # signs the user out everywhere
    user.save(update_fields=["password", "failed_attempts", "locked_until", "session_epoch"])
    audit(request, "auth.password_reset.complete", "success", actor=user)
    return JsonResponse({"status": "ok", "message": "Your password has been reset. You can now sign in with the new password."})
