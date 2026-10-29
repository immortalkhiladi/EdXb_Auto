"""LOCAL DEVELOPMENT settings (plain HTTP on localhost). Never used in production."""
from .base import *  # noqa: F401,F403
from .base import BASE_DIR, DATA_DIR, env, env_list, os  # noqa: F401

DEBUG = env("DJANGO_DEBUG", "true").lower() in ("1", "true", "yes")

if not SECRET_KEY:  # noqa: F405
    # a persistent random key generated on first run so local sessions/MFA survive restarts
    import secrets
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _key = DATA_DIR / ".dev_secret_key"
    if not _key.exists():
        _key.write_text(secrets.token_urlsafe(64))
        try:
            _key.chmod(0o600)
        except OSError:
            pass
    SECRET_KEY = _key.read_text().strip()

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://127.0.0.1:8000"])
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", ["http://localhost:3000", "http://127.0.0.1:3000"])
