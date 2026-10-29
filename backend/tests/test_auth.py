import time

import pyotp
import pytest
from django.test import Client

from portal.models import AuditLog, User
from portal.security import decrypt_secret

from .conftest import PW, Api, login


@pytest.mark.parametrize("username", ["admin"] + [f"user{i:02d}" for i in range(1, 11)])
def test_all_eleven_accounts_authenticate_separately(username):
    a = login(username)
    me = a.get("/api/auth/me").json()["user"]
    assert me["username"] == username
    assert me["role"] == ("ADMIN" if username == "admin" else "USER")


def test_wrong_password_and_unknown_user_get_same_generic_error(anon):
    a = anon.post_json("/api/auth/login", {"username": "user01", "password": "bad"})
    b = anon.post_json("/api/auth/login", {"username": "nobody", "password": "bad"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_lockout_after_repeated_failures_then_correct_password_rejected(anon, settings):
    for _ in range(settings.MAX_FAILED_LOGINS):
        assert anon.post_json("/api/auth/login", {"username": "user03", "password": "nope"}).status_code == 401
    assert anon.post_json("/api/auth/login", {"username": "user03", "password": PW}).status_code == 401  # locked


def test_login_rate_limit(settings, anon):
    settings.LOGIN_RATE_LIMIT = 3
    codes = [anon.post_json("/api/auth/login", {"username": "x", "password": "y"}).status_code for _ in range(5)]
    assert codes[-1] == 429


def test_logout_destroys_server_side_session(settings):
    a = login("user01")
    cookie = a.c.cookies[settings.SESSION_COOKIE_NAME].value
    assert a.post_json("/api/auth/logout").status_code == 200
    replay = Client()
    replay.cookies[settings.SESSION_COOKIE_NAME] = cookie
    assert replay.get("/api/auth/me").status_code == 401


def test_deactivated_user_is_logged_out_and_cannot_login(admin):
    c = login("user04")
    uid = c.get("/api/auth/me").json()["user"]["id"]
    assert admin.patch_json(f"/api/admin/users/{uid}", {"is_active": False}).status_code == 200
    assert c.get("/api/auth/me").status_code == 401
    assert Api().post_json("/api/auth/login", {"username": "user04", "password": PW}).status_code == 401


def test_session_cookie_flags(anon, settings):
    r = anon.post_json("/api/auth/login", {"username": "user01", "password": PW})
    morsel = r.cookies[settings.SESSION_COOKIE_NAME]
    assert morsel["httponly"] is True and morsel["samesite"] == "Strict"


def test_passwords_are_argon2id_hashed():
    u = User.objects.get(username="user01")
    assert u.password.startswith("argon2$argon2id$") and PW not in u.password


def test_csrf_token_required_for_state_changing_requests():
    c = Client(enforce_csrf_checks=True)
    r = c.post("/api/auth/login", '{"username":"user01","password":"x"}', content_type="application/json")
    assert r.status_code == 403 and r.json()["detail"] == "CSRF verification failed."


def test_foreign_origin_rejected(anon):
    r = anon.post_json("/api/auth/login", {"username": "user01", "password": PW}, HTTP_ORIGIN="https://evil.example")
    assert r.status_code == 403


def test_change_password_policy_and_revokes_other_sessions():
    a, b = login("user05"), login("user05")
    assert a.post_json("/api/auth/change-password", {"current_password": PW, "new_password": "short"}).status_code == 422
    assert a.post_json("/api/auth/change-password", {"current_password": "wrong", "new_password": "An0t!r"}).status_code == 400
    assert a.post_json("/api/auth/change-password", {"current_password": PW, "new_password": "An0t!r"}).status_code == 200
    assert a.get("/api/auth/me").status_code == 200
    assert b.get("/api/auth/me").status_code == 401  # other session revoked
    login("user05", "An0t!r")


def test_session_absolute_lifetime_enforced(settings):
    a = login("user06")
    settings.SESSION_ABSOLUTE_HOURS = 0
    time.sleep(0.01)
    assert a.get("/api/auth/me").status_code == 401


def test_admin_mfa_enrolment_and_login(settings):
    settings.ADMIN_MFA_REQUIRED = True
    a = Api()
    assert a.post_json("/api/auth/login", {"username": "admin", "password": PW}).json()["status"] == "mfa_setup_required"
    assert a.get("/api/admin/users").status_code == 401  # pending session is not enough
    secret = a.post_json("/api/auth/mfa/setup").json()["secret"]
    assert a.post_json("/api/auth/mfa/verify", {"code": "000000"}).status_code == 401
    code = pyotp.TOTP(secret).now()
    assert a.post_json("/api/auth/mfa/verify", {"code": code}).status_code == 200
    assert a.get("/api/admin/users").status_code == 200
    u = User.objects.get(username="admin")
    assert secret not in u.totp_secret_enc and decrypt_secret(u.totp_secret_enc) == secret  # encrypted at rest

    a2 = Api()
    assert a2.post_json("/api/auth/login", {"username": "admin", "password": PW}).json()["status"] == "mfa_required"
    assert a2.post_json("/api/auth/mfa/verify", {"code": code}).status_code == 401  # replay of a used code
    nxt = pyotp.TOTP(secret).at(int(time.time()) + 30)
    assert a2.post_json("/api/auth/mfa/verify", {"code": nxt}).status_code == 200
    from portal.models import AuditLog
    assert AuditLog.objects.filter(action="auth.login", outcome="success", actor_name="admin").count() == 2  # MFA sign-ins are login events too
    listed = a2.get("/api/admin/audit-logs").json()["items"]
    assert [i["action"] for i in listed] == ["auth.login", "auth.login"] and "totp" not in str(listed).lower()


def test_auth_events_are_audited(anon):
    anon.post_json("/api/auth/login", {"username": "user06", "password": "bad"})
    login("user06")
    rows = list(AuditLog.objects.filter(action="auth.login"))
    assert {r.outcome for r in rows} == {"failure", "success"}
    assert all("bad" not in (r.detail or "") for r in rows)  # no secrets in logs
