"""PRODUCTION settings (Render). Refuses to start when mis-configured."""
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import ADMIN_MFA_REQUIRED, DATABASES, SECRET_KEY, STORAGE_BACKEND, env, env_bool, env_list

DEBUG = False
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"  # never print reset links into production logs


def _require(cond, msg):
    if not cond:
        raise ImproperlyConfigured(msg)


_require(len(SECRET_KEY) >= 50, "DJANGO_SECRET_KEY must be set (50+ random characters) in production.")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
_require(ALLOWED_HOSTS, "DJANGO_ALLOWED_HOSTS must list the API host name(s), e.g. api.example.com.")
if env("RENDER_EXTERNAL_HOSTNAME"):  # Render injects the service's public host name
    ALLOWED_HOSTS.append(env("RENDER_EXTERNAL_HOSTNAME"))
try:  # platform health probes may reach the container by its internal IP: allow it so they are not rejected
    import socket
    ALLOWED_HOSTS.append(socket.gethostbyname(socket.gethostname()))
except OSError:
    pass
_require(ADMIN_MFA_REQUIRED, "ADMIN_MFA_REQUIRED must be true in production.")

# Render's container disk is erased on every deploy/restart: uploads must go to the mounted persistent disk.
_require(not env("RENDER") or STORAGE_BACKEND == "database" or env("STORAGE_LOCAL_DIR"),
         "STORAGE_LOCAL_DIR must point at the Render persistent disk (e.g. /var/data/storage) so uploaded files survive restarts.")

_db = DATABASES["default"]
if _db["ENGINE"].endswith("postgresql"):
    for key in ("NAME", "USER", "PASSWORD", "HOST"):
        _require(_db.get(key), f"DB_{key} must be set (Render environment variable).")
    _require(_db["HOST"] not in ("localhost", "127.0.0.1", "::1"),
             "DB_HOST must be the PostgreSQL server host name (Render: the database's internal host), not localhost.")
    _db.setdefault("OPTIONS", {}).setdefault("sslmode", "require")

# ---- HTTPS and secure cookies ----
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # Render terminates TLS
TRUST_PROXY_HEADERS = True
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_REDIRECT_EXEMPT = [r"^api/health$"]  # platform health probes arrive over http
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 63072000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "no-referrer"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Reviewed and intentionally silenced:
#  W002: X-Frame-Options is set by portal.middleware.SecurityHeadersMiddleware (SAMEORIGIN, or CSP frame-ancestors
#        for split hosting) because the tool/preview frames must be embeddable by the UI.
#  W021: HSTS preload is a deliberate, hard-to-undo decision (browser preload list) - not enabled automatically.
SILENCED_SYSTEM_CHECKS = ["security.W002", "security.W021"]
