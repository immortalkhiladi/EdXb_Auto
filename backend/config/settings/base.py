"""Settings shared by every environment. Secrets/config come from ENVIRONMENT VARIABLES:
 - local development: variables in backend/.env (never committed)
 - Render: the service's environment variables (secrets marked `sync: false` / generated in render.yaml)
Nothing secret is hardcoded in this repository."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
load_dotenv(BASE_DIR / ".env")  # no-op when the file does not exist (Render)


def env(name, default=""):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    v = os.environ.get(name)
    return default if v is None or v == "" else v.strip().lower() in ("1", "true", "yes", "on")


def env_int(name, default):
    v = os.environ.get(name)
    return int(v) if v not in (None, "") else default


def env_list(name, default=None):
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return list(default or [])
    v = v.strip()
    if v.startswith("["):
        import json
        return json.loads(v)
    return [p.strip() for p in v.split(",") if p.strip()]


DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")  # also encrypts MFA secrets at rest
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "corsheaders",
    "portal",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "portal.middleware.RequestLimitMiddleware",
    "portal.middleware.SecurityHeadersMiddleware",
    "portal.middleware.ApiErrorMiddleware",
    "portal.middleware.PurgeSchedulerMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES: list = []  # no server-side templates: the UI is the React app
APPEND_SLASH = False
USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "portal.User"
# Argon2id with memory/CPU costs sized for a 512 MB instance (see portal/hashers.py). Existing hashes keep verifying.
PASSWORD_HASHERS = ["portal.hashers.TunedArgon2PasswordHasher"]
ARGON2_TIME_COST = env_int("ARGON2_TIME_COST", 2)
ARGON2_MEMORY_COST_KIB = env_int("ARGON2_MEMORY_COST_KIB", 19456)  # 19 MiB (OWASP minimum for Argon2id)
ARGON2_PARALLELISM = env_int("ARGON2_PARALLELISM", 1)
PASSWORD_HASH_CONCURRENCY = env_int("PASSWORD_HASH_CONCURRENCY", 1)  # simultaneous hashes per worker (1: legacy 100 MB hashes stay bounded too)

# ---- sessions: server-side, HttpOnly, SameSite=Strict, sliding idle timeout + absolute lifetime ----
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = env("SESSION_COOKIE_NAME", "ff_session")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_IDLE_MINUTES = env_int("SESSION_IDLE_MINUTES", 30)
SESSION_COOKIE_AGE = SESSION_IDLE_MINUTES * 60
SESSION_SAVE_EVERY_REQUEST = False  # the idle timeout is slid by portal.api.current_user (at most once a minute) instead of a DB write per request
SESSION_ABSOLUTE_HOURS = env_int("SESSION_ABSOLUTE_HOURS", 8)
MFA_PENDING_MINUTES = env_int("MFA_PENDING_MINUTES", 5)

# ---- CSRF (token kept in the server-side session, delivered via GET /api/auth/csrf) ----
CSRF_USE_SESSIONS = True
CSRF_FAILURE_VIEW = "portal.views.common.csrf_failure"
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")  # e.g. https://app.example.com (split hosting)

# ---- split hosting (only needed when the React app is served from a different origin than the API) ----
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")  # e.g. https://app.example.com
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = ["content-type", "x-csrftoken"]
FRAME_ANCESTORS = env_list("FRAME_ANCESTORS")  # origins allowed to embed tool/preview frames

# ---- application ----
ADMIN_MFA_REQUIRED = env_bool("ADMIN_MFA_REQUIRED", False)
MAX_FAILED_LOGINS = env_int("MAX_FAILED_LOGINS", 5)
LOCKOUT_MINUTES = env_int("LOCKOUT_MINUTES", 15)
LOGIN_RATE_LIMIT = env_int("LOGIN_RATE_LIMIT", 20)  # attempts per (client IP + account) per window
# attempts per client IP per window, all accounts together. Kept well above the user count because a whole office
# usually signs in from ONE public (NAT) IP: the old single per-IP limit of 20 rejected the 21st colleague with 429.
LOGIN_IP_RATE_LIMIT = env_int("LOGIN_IP_RATE_LIMIT", 300)
LOGIN_RATE_WINDOW_SECONDS = env_int("LOGIN_RATE_WINDOW_SECONDS", 600)
UPLOAD_RATE_LIMIT = env_int("UPLOAD_RATE_LIMIT", 60)
MAX_UPLOAD_MB = env_int("MAX_UPLOAD_MB", 50)
MAX_ZIP_UNCOMPRESSED_MB = env_int("MAX_ZIP_UNCOMPRESSED_MB", 500)
MAX_ZIP_ENTRIES = env_int("MAX_ZIP_ENTRIES", 5000)
DELETED_FILE_RETENTION_DAYS = env_int("DELETED_FILE_RETENTION_DAYS", 30)
AUDIT_RETENTION_DAYS = env_int("AUDIT_RETENTION_DAYS", 30)  # audit rows older than this are deleted automatically
AUDIT_CLEANUP_INTERVAL_HOURS = env_int("AUDIT_CLEANUP_INTERVAL_HOURS", 6)
RUN_PURGE_SCHEDULER = env_bool("RUN_PURGE_SCHEDULER", True)
TRUST_PROXY_HEADERS = env_bool("TRUST_PROXY_HEADERS", False)  # client IP from X-Forwarded-For (Render: true)
# 0 = use the first (left-most) X-Forwarded-For entry (previous behaviour; a client can pre-fill that entry).
# N > 0 = use the N-th entry from the right, i.e. the address written by your N-th trusted proxy (not spoofable).
PROXY_HOPS = env_int("PROXY_HOPS", 0)
PREVIEW_CONCURRENCY = env_int("PREVIEW_CONCURRENCY", 2)  # in-memory document previews per worker process
# ---- forgot / reset password (signed, expiring, single-use link sent by email) ----
PASSWORD_RESET_TIMEOUT = env_int("PASSWORD_RESET_MINUTES", 30) * 60  # link lifetime
PASSWORD_RESET_RATE_LIMIT = env_int("PASSWORD_RESET_RATE_LIMIT", 5)  # requests per IP per LOGIN_RATE_WINDOW_SECONDS
# True: the form says when no account matches the email (clear message, but lets people probe which emails exist).
# False: always answers "if the account exists, an email was sent".
PASSWORD_RESET_REVEAL_ACCOUNT = env_bool("PASSWORD_RESET_REVEAL_ACCOUNT", True)
FRONTEND_URL = env("FRONTEND_URL").rstrip("/")  # base URL of the web app used in the email link; empty = the request's own host
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "EDGAR Agents LLC <no-reply@localhost>")
# no SMTP server configured (local development): the reset email is printed to the server console instead
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST else "django.core.mail.backends.console.EmailBackend"

SEED_USER_COUNT = env_int("SEED_USER_COUNT", 0)  # 0 = admin only (dashboard starts empty)
SEED_ADMIN_USERNAME = env("SEED_ADMIN_USERNAME", "admin")
SEED_PASSWORD = env("SEED_PASSWORD")  # optional; empty = random passwords

DATA_DIR = Path(env("DATA_DIR", str(BASE_DIR / "data")))
# Uploaded files live in a private directory. On Render this MUST be on a persistent disk (render.yaml mounts one at
# /var/data and sets STORAGE_LOCAL_DIR=/var/data/storage); the container's own filesystem is wiped on every deploy/restart.
# "database" (default): files are stored inside PostgreSQL and survive any restart/redeploy. "local": files on disk only.
STORAGE_BACKEND = env("STORAGE_BACKEND", "database").lower()
STORAGE_LOCAL_DIR = Path(env("STORAGE_LOCAL_DIR", str(DATA_DIR / "storage")))

# ---- uploads (files above 2.5 MB spill to temp files, never held fully in memory by Django) ----
FILE_UPLOAD_PERMISSIONS = 0o600
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # non-file form data / JSON bodies
DATA_UPLOAD_MAX_NUMBER_FILES = 5

# ---- React build served by Django when present (single-origin mode) ----
def _frontend_dist() -> Path:
    # single-origin mode: the built React app is served by Django. Looked up in: $FRONTEND_DIST, frontend/dist
    # (what deploy/render/build.sh produces), backend/dist.
    for cand in (env("FRONTEND_DIST"), BASE_DIR.parent / "frontend" / "dist", BASE_DIR / "dist"):
        if cand and (Path(cand) / "index.html").is_file():
            return Path(cand)
    return BASE_DIR.parent / "frontend" / "dist"


FRONTEND_DIST = _frontend_dist()
if (FRONTEND_DIST / "index.html").is_file():
    WHITENOISE_ROOT = FRONTEND_DIST
    WHITENOISE_INDEX_FILE = True
# Vite emits content-hashed file names under /assets/: cache them for a year (the default is 60 seconds).
WHITENOISE_IMMUTABLE_FILE_TEST = lambda path, url: url.startswith("/assets/")  # noqa: E731
STATIC_URL = "/_static/"  # unused: the UI is served from FRONTEND_DIST via WhiteNoise


def database_from_env():
    """DB_ENGINE=postgres (default) or sqlite. Credentials ONLY from the environment."""
    if env("DB_ENGINE", "postgres").lower() == "sqlite":
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": str(DATA_DIR / "db.sqlite3")}
    cfg = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
    if env("DB_SSLMODE"):
        cfg["OPTIONS"] = {"sslmode": env("DB_SSLMODE")}
    return cfg


DATABASES = {"default": database_from_env()}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"std": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "std"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    # never log request bodies / passwords: only our own audit trail and errors
    "loggers": {"django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False}},
}
