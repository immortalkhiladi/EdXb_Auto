import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.management import call_command

from portal.models import User
from portal.tools import TOOLS

from .conftest import PW, Api, process

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


def _prod_env(**over):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "DB_", "ADMIN_MFA", "SECURE_"))}
    env.update(DJANGO_SETTINGS_MODULE="config.settings.production", DJANGO_SECRET_KEY="Zr7-Qm2xVb9LpT4sWc8YdN3hKe6JfA1uGo5RiXy0BtMnCzE2vSqHw", DJANGO_ALLOWED_HOSTS="api.example.com",
               ADMIN_MFA_REQUIRED="true", DB_NAME="n", DB_USER="u", DB_PASSWORD="p", DB_HOST="dpg-abc-a")
    env.update(over)
    return {k: v for k, v in env.items() if v is not None}


def _load_settings(**over):
    code = "from django.conf import settings as s; print(s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, s.SECURE_SSL_REDIRECT, s.SECURE_HSTS_SECONDS, s.DEBUG, s.DATABASES['default']['OPTIONS']['sslmode'])"
    return subprocess.run([sys.executable, "-c", code], env=_prod_env(**over), cwd=BACKEND, capture_output=True, text=True)


def test_security_headers_health_and_generic_404(anon):
    r = anon.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["Referrer-Policy"] == "no-referrer"
    assert r.headers["Cache-Control"] == "no-store"
    nf = anon.get("/api/does-not-exist")
    assert nf.status_code == 404 and nf.json() == {"detail": "Not found."}


def test_unhandled_errors_do_not_leak_details(anon, monkeypatch):
    import portal.views.common as common
    monkeypatch.setattr(common, "connection", None)  # makes health raise
    r = anon.get("/api/health")
    assert r.status_code == 503 and r.json() == {"status": "unavailable"}


def test_tool_pages_only_for_authenticated_users_and_carry_sandbox_csp(u1, anon):
    for slug in TOOLS:
        assert anon.get(f"/api/tools/{slug}/frame").status_code == 401
        r = u1.get(f"/api/tools/{slug}/frame")
        assert r.status_code == 200 and b"ff-tool" in r.content          # bridge injected
        assert b"F12" in r.content and b"contextmenu" in r.content        # shortcut/right-click deterrents injected
        csp = r.headers["Content-Security-Policy"]
        assert csp.startswith("sandbox allow-scripts allow-same-origin") and "frame-src 'self' blob: data:" in csp
    assert u1.get("/api/tools/unknown/frame").status_code == 404


def test_tool_html_not_reachable_as_static_files(anon):
    for p in ["/tools/Redline_to_GoFiler_HTML_v2.html", "/backend/tools/Redline_to_GoFiler_HTML_v2.html", "/Redline_to_GoFiler_HTML_v2.html"]:
        assert b"<script" not in anon.get(p).content


def test_linkedin_updates_are_public_and_well_formed(anon):
    r = anon.get("/api/linkedin-updates")
    assert r.status_code == 200 and r.json()["profile"].startswith("https://www.linkedin.com/")
    assert all({"title", "date", "text", "link"} <= set(i) for i in r.json()["items"])


def test_csrf_endpoint_returns_token(anon):
    assert len(anon.get("/api/auth/csrf").json()["csrfToken"]) >= 32


def test_cors_allows_only_configured_origins_with_credentials(anon):
    ok = anon.options("/api/auth/login", HTTP_ORIGIN="http://localhost:3000", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
                      HTTP_ACCESS_CONTROL_REQUEST_HEADERS="x-csrftoken,content-type")
    assert ok.status_code == 200 and ok.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert ok.headers["Access-Control-Allow-Credentials"] == "true"
    bad = anon.options("/api/auth/login", HTTP_ORIGIN="https://evil.example", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
    assert "Access-Control-Allow-Origin" not in bad.headers


def test_frame_ancestors_setting_controls_who_may_embed_tool_and_preview_frames(settings, u1):
    r = u1.get("/api/tools/html-converter/frame")
    assert "frame-ancestors 'self'" in r.headers["Content-Security-Policy"] and r.headers["X-Frame-Options"] == "SAMEORIGIN"
    settings.FRAME_ANCESTORS = ["https://app.example.com"]
    r = u1.get("/api/tools/html-converter/frame")
    assert "frame-ancestors 'self' https://app.example.com" in r.headers["Content-Security-Policy"]
    assert "X-Frame-Options" not in r.headers
    d = process(u1, "redline-to-gofiler-html", ("x.html", b"<html></html>"), ("s.html", b"<html></html>")).json()["document"]
    assert "https://app.example.com" in u1.get(f"/api/documents/{d['id']}/view").headers["Content-Security-Policy"]


def test_production_settings_refuse_insecure_configuration():
    assert _load_settings().returncode == 0
    assert "DJANGO_SECRET_KEY" in _load_settings(DJANGO_SECRET_KEY="short").stderr
    assert "DJANGO_ALLOWED_HOSTS" in _load_settings(DJANGO_ALLOWED_HOSTS=None).stderr
    assert "ADMIN_MFA_REQUIRED" in _load_settings(ADMIN_MFA_REQUIRED="false").stderr
    assert "not localhost" in _load_settings(DB_HOST="localhost").stderr
    assert "DB_PASSWORD" in _load_settings(DB_PASSWORD="").stderr


def test_production_enables_https_secure_cookies_and_ssl_to_database():
    r = _load_settings()
    assert r.stdout.split() == ["True", "True", "True", "63072000", "False", "require"], r.stderr


def test_django_deploy_check_has_no_warnings():
    r = subprocess.run([sys.executable, "manage.py", "check", "--deploy"], env=_prod_env(), cwd=BACKEND, capture_output=True, text=True)
    assert r.returncode == 0 and "no issues" in r.stdout, r.stdout + r.stderr


def test_no_missing_migrations():
    call_command("makemigrations", "--check", "--dry-run")


def test_list_environment_values_accept_comma_separated_and_json(monkeypatch):
    from config.settings.base import env_list
    monkeypatch.setenv("X_LIST", "https://a.example.com, https://b.example.com")
    assert env_list("X_LIST") == ["https://a.example.com", "https://b.example.com"]
    monkeypatch.setenv("X_LIST", '["https://a.example.com"]')
    assert env_list("X_LIST") == ["https://a.example.com"]
    monkeypatch.setenv("X_LIST", "")
    assert env_list("X_LIST", ["d"]) == ["d"]


def test_create_admin_and_seed_commands(monkeypatch, settings, tmp_path):
    monkeypatch.setenv("FF_NEW_PASSWORD", "S3cr!t")
    call_command("create_admin", "--username", "Boss", "--email", "b@x.zz", "--name", "Boss")
    u = User.objects.get(username="boss")
    assert u.role == "ADMIN" and u.check_password("S3cr!t")
    with pytest.raises(Exception):
        call_command("create_admin", "--username", "boss", "--email", "other@x.zz", "--name", "B")
    User.objects.all().delete()
    settings.DATA_DIR = tmp_path
    settings.SEED_USER_COUNT = 10
    call_command("seed_users")
    assert User.objects.count() == 12 and User.objects.filter(role="ADMIN").count() == 1 and User.objects.filter(role="MD").count() == 1
    assert User.objects.get(username="admin").check_password("Admin@123")
    assert all(User.objects.get(username=f"user{i:02d}").check_password("User@123") for i in range(1, 11))
    from portal.models import UserToolAccess
    assert set(UserToolAccess.objects.filter(user__username="user01").values_list("tool", flat=True)) == {"redline-to-gofiler-html", "html-converter"}
    assert UserToolAccess.objects.filter(user__username="user02").count() == 4


def test_frontend_bundle_has_no_secrets_or_sourcemaps(settings):
    dist = ROOT / "dist"
    if not dist.is_dir():
        pytest.skip("frontend not built")
    assert not list(dist.rglob("*.map")), "production source maps must be disabled"
    blob = "".join(p.read_text(errors="ignore") for p in dist.rglob("*.js"))
    for needle in [settings.SECRET_KEY, "initial_credentials", "BEGIN PRIVATE KEY", "AccountKey=", "MyApp@123", "Default Testing Password"]:
        assert needle not in blob


def test_no_hardcoded_credentials_in_source():
    bad = []
    for p in list((BACKEND / "config").rglob("*.py")) + list((BACKEND / "portal").rglob("*.py")):
        t = p.read_text()
        if "MyApp@123" in t or "myapp_user" in t:
            bad.append(str(p))
    assert not bad, f"database credentials must not be hardcoded: {bad}"


def test_seed_users_reset_fixes_existing_database_and_is_refused_in_production(settings, tmp_path):
    settings.SEED_USER_COUNT = 10  # default is now 0 (admin only); --reset must cover user08
    # the fixture already created users, so a plain run does nothing ...
    call_command("seed_users")
    assert not User.objects.get(username="user08").check_password("User@123")
    # ... --reset sets the default passwords, unlocks and signs the accounts out
    User.objects.filter(username="user08").update(failed_attempts=4)
    call_command("seed_users", "--reset")
    u = User.objects.get(username="user08")
    assert u.check_password("User@123") and u.failed_attempts == 0
    assert Api().post_json("/api/auth/login", {"username": "admin", "password": "Admin@123"}).status_code == 200
    assert Api().post_json("/api/auth/login", {"username": "user08", "password": "User@123"}).status_code == 200
    settings.SESSION_COOKIE_SECURE = True  # what production settings do
    with pytest.raises(Exception, match="refused"):
        call_command("seed_users", "--reset")
