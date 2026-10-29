"""Automated tests: temp SQLite (or PostgreSQL when TEST_DB_ENGINE=postgres with DB_* set), fast limits."""
import os
import tempfile

from .base import *  # noqa: F401,F403
from .base import env, env_list

_TMP = tempfile.mkdtemp(prefix="ff-tests-")
DEBUG = False
SECRET_KEY = "test-only-secret-key-" + "x" * 60
ALLOWED_HOSTS = ["testserver", "localhost"]
DATA_DIR = _TMP
STORAGE_BACKEND = env("TEST_STORAGE_BACKEND", "database")
STORAGE_LOCAL_DIR = os.path.join(_TMP, "storage")
from pathlib import Path  # noqa: E402
DATA_DIR = Path(_TMP)
STORAGE_LOCAL_DIR = Path(_TMP) / "storage"
FRONTEND_DIST = Path(_TMP) / "nodist"
WHITENOISE_ROOT = None
if env("TEST_DB_ENGINE", "sqlite") == "postgres":
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": env("DB_NAME", "postgres"),
                             "USER": env("DB_USER", "postgres"), "PASSWORD": env("DB_PASSWORD"), "HOST": env("DB_HOST"),
                             "PORT": env("DB_PORT", "5432")}}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.path.join(_TMP, "t.sqlite3")}}
LOGIN_RATE_LIMIT = 1000
LOGIN_IP_RATE_LIMIT = 1000
UPLOAD_RATE_LIMIT = 1000
MAX_UPLOAD_MB = 2
RUN_PURGE_SCHEDULER = False
SESSION_COOKIE_SECURE = False
CSRF_TRUSTED_ORIGINS = ["http://localhost:3000"]
CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]
ADMIN_MFA_REQUIRED = False
PASSWORD_RESET_RATE_LIMIT = 1000
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
