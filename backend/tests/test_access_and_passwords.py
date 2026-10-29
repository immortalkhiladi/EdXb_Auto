"""Role-based access (ADMIN / MD / USER), the 4-6 character password policy and the forgot/reset-password flow."""
import re
from unittest import mock

import pytest
from django.core import mail

from portal.models import AuditLog, Document, User
from portal.security import password_error, password_problems

from .conftest import PW, Api, login, process


# ------------------------------------------------------------------ password policy (unit)
@pytest.mark.parametrize("pw", ["Ab1@", "A1!x", "Zz9#yy", "P4$$wd", "a1B_", "Q9~zzz"])
def test_valid_passwords_are_accepted(pw):
    assert password_problems(pw) == []
    assert password_error(pw) is None


@pytest.mark.parametrize("pw,expected", [
    ("A1@", "4 to 6 characters long (yours has 3)"),       # too short
    ("", "yours has 0"),
    ("Abcd1@x", "4 to 6 characters long (yours has 7)"),   # too long
    ("ab1@", "missing an uppercase letter"),
    ("Abc@", "missing a number"),
    ("Abc1", "missing a special character"),
    ("abcd", "an uppercase letter (A-Z), a number (0-9), a special character"),  # everything missing
    ("Ab1 ", "missing a special character"),                # a space is not a special character
    ("ab1é", "missing an uppercase letter"),                # non-ASCII letters do not count as special
])
def test_invalid_passwords_get_a_precise_message(pw, expected):
    msg = password_error(pw)
    assert msg is not None and expected in msg


def test_length_and_missing_class_are_both_reported():
    assert len(password_problems("abcdefgh")) == 2


# ------------------------------------------------------------------ password policy (every place a password is set)
def test_change_password_enforces_policy_with_clear_errors(u1):
    for bad, needle in [("Ab1", "4 to 6"), ("Abcdefg1@", "4 to 6"), ("ab1@", "uppercase"), ("Abc@", "number"), ("Abc1", "special")]:
        r = u1.post_json("/api/auth/change-password", {"current_password": PW, "new_password": bad})
        assert r.status_code == 422 and needle in r.json()["detail"], (bad, r.content)
    assert User.objects.get(username="user01").check_password(PW)  # nothing was silently accepted
    assert u1.post_json("/api/auth/change-password", {"current_password": PW, "new_password": "Gd7#"}).status_code == 200


def test_admin_create_and_reset_enforce_policy(admin):
    base = {"username": "pol1", "email": "pol1@example.com", "full_name": "P"}
    for bad in ["Ab1", "Abcdefg1@", "ab1@", "Abc@", "Abc1"]:
        assert admin.post_json("/api/admin/users", {**base, "password": bad}).status_code == 422
    assert not User.objects.filter(username="pol1").exists()
    r = admin.post_json("/api/admin/users", {**base, "password": "Gd7#"})
    assert r.status_code == 201
    uid = r.json()["user"]["id"]
    assert admin.patch_json(f"/api/admin/users/{uid}", {"new_password": "weak"}).status_code == 422
    assert admin.patch_json(f"/api/admin/users/{uid}", {"new_password": "Nw5$k"}).status_code == 200
    login("pol1", "Nw5$k")


# ------------------------------------------------------------------ roles
def test_three_roles_exist_and_users_can_be_created_with_md_role(admin):
    r = admin.post_json("/api/admin/users", {"username": "mdnew", "email": "mdnew@example.com", "full_name": "M", "password": "Gd7#", "role": "MD"})
    assert r.status_code == 201 and r.json()["user"]["role"] == "MD"
    assert admin.post_json("/api/admin/users", {"username": "bad", "email": "bad@example.com", "full_name": "B", "password": "Gd7#", "role": "BOSS"}).status_code == 422
    assert login("md01").get("/api/auth/me").json()["user"]["role"] == "MD"


def test_fifty_plus_users_each_have_their_own_login():
    from django.contrib.auth.hashers import make_password
    h = make_password("Gd7#")
    User.objects.bulk_create([User(username=f"bulk{i:02d}", email=f"bulk{i:02d}@example.com", full_name=f"B{i}", role="USER", password=h) for i in range(55)])
    assert User.objects.count() >= 55 + 12
    a, b = login("bulk01", "Gd7#"), login("bulk54", "Gd7#")
    assert a.get("/api/auth/me").json()["user"]["username"] == "bulk01"
    assert b.get("/api/auth/me").json()["user"]["username"] == "bulk54"


def test_md_can_view_and_download_all_documents(md, u1, u2):
    d1 = process(u1).json()["document"]
    d2 = process(u2).json()["document"]
    allp = md.get("/api/admin/documents").json()
    assert {x["id"] for x in allp["items"]} == {d1["id"], d2["id"]} and all("owner" in x for x in allp["items"])
    assert md.get(f"/api/documents/{d1['id']}/download").status_code == 200
    assert md.get(f"/api/documents/{d1['id']}").json()["document"]["owner"]["username"] == "user01"
    assert any(r.action == "document.download" and r.actor_name == "md01" for r in AuditLog.objects.filter(resource_id=d1["id"]))


def test_md_cannot_delete_other_users_documents_but_can_delete_own(md, u1):
    d = process(u1).json()["document"]
    r = md.delete(f"/api/documents/{d['id']}")
    assert r.status_code == 403
    assert Document.objects.get(id=d["id"]).deleted_at is None
    assert AuditLog.objects.filter(action="document.delete", outcome="denied", actor_name="md01").exists()
    own = process(md).json()["document"]
    assert md.delete(f"/api/documents/{own['id']}").status_code == 200


def test_md_cannot_use_admin_only_endpoints(md, u1):
    uid = User.objects.get(username="user01").id
    assert md.get("/api/admin/users").status_code == 403
    assert md.get("/api/admin/audit-logs").status_code == 403
    assert md.get("/api/admin/overview").status_code == 403
    assert md.post_json("/api/admin/users", {"username": "zzz", "email": "z@z.zz", "full_name": "Z", "password": "Gd7#"}).status_code == 403
    assert md.patch_json(f"/api/admin/users/{uid}", {"role": "ADMIN"}).status_code == 403
    assert md.patch_json(f"/api/admin/users/{User.objects.get(username='md01').id}", {"role": "ADMIN"}).status_code == 403


def test_regular_user_sees_only_own_documents_and_no_all_documents_api(u1, u2):
    d1 = process(u1).json()["document"]
    d2 = process(u2).json()["document"]
    assert [x["id"] for x in u1.get("/api/documents").json()["items"]] == [d1["id"]]
    assert u1.get(f"/api/documents/{d2['id']}").status_code == 404
    assert u1.get(f"/api/documents/{d2['id']}/download").status_code == 404
    assert u1.get(f"/api/documents/{d2['id']}/view").status_code == 404
    assert u1.delete(f"/api/documents/{d2['id']}").status_code == 404
    assert u1.get("/api/admin/documents").status_code == 403
    assert u1.get("/api/documents?owner=user02").json()["total"] == 1  # an "owner" parameter changes nothing


def test_everything_requires_a_session(anon, u1):
    d = process(u1).json()["document"]
    for url in ["/api/documents", f"/api/documents/{d['id']}", f"/api/documents/{d['id']}/download", "/api/admin/documents",
                "/api/admin/users", "/api/admin/audit-logs", "/api/tools", "/api/auth/me"]:
        assert anon.get(url).status_code == 401, url


# ------------------------------------------------------------------ forgot / reset password
def _request_reset(api, email="user03@example.com"):
    return api.post_json("/api/auth/forgot-password", {"email": email})


def _link_parts():
    body = mail.outbox[-1].body
    m = re.search(r"/reset-password\?uid=([^&\s]+)&token=([^\s]+)", body)
    assert m, body
    return m.group(1), m.group(2)


def test_forgot_password_sends_a_link_and_never_the_password(anon):
    r = _request_reset(anon)
    assert r.status_code == 200 and "reset link has been sent" in r.json()["message"]
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["user03@example.com"]
    assert PW not in mail.outbox[0].body and "argon2" not in mail.outbox[0].body
    _link_parts()


def test_forgot_password_error_messages(anon, settings):
    assert _request_reset(anon, "not-an-email").status_code == 422
    assert "valid email" in _request_reset(anon, "not-an-email").json()["detail"]
    assert _request_reset(anon, "").status_code == 422
    r = _request_reset(anon, "nobody@example.com")
    assert r.status_code == 404 and "No active account" in r.json()["detail"]
    User.objects.filter(username="user04").update(is_active=False)
    assert _request_reset(anon, "user04@example.com").status_code == 404
    assert mail.outbox == []
    settings.PASSWORD_RESET_REVEAL_ACCOUNT = False  # generic mode: no account probing
    assert _request_reset(anon, "nobody@example.com").status_code == 200 and mail.outbox == []


def test_forgot_password_reports_delivery_failure(anon):
    with mock.patch("portal.views.auth.send_mail", side_effect=OSError("smtp down")):
        r = _request_reset(anon)
    assert r.status_code == 503 and "could not send" in r.json()["detail"]
    assert AuditLog.objects.filter(action="auth.password_reset.request", outcome="failure", detail="email delivery failed").exists()


def test_forgot_password_is_rate_limited(anon, settings):
    for _ in range(3):
        assert _request_reset(anon).status_code == 200
    assert _request_reset(anon).status_code == 429  # per-account limit (inbox flooding)
    settings.PASSWORD_RESET_RATE_LIMIT = 2
    from portal.security import limiter
    limiter.reset()
    codes = [_request_reset(anon, f"user0{i}@example.com").status_code for i in range(5, 9)]
    assert codes[:2] == [200, 200] and codes[2] == 429  # per-IP limit


def test_full_reset_flow(anon):
    old_hash = User.objects.get(username="user03").password
    _request_reset(anon)
    uid, token = _link_parts()
    # weak passwords are rejected with a clear message and do not use up the link
    r = anon.post_json("/api/auth/reset-password", {"uid": uid, "token": token, "new_password": "abc"})
    assert r.status_code == 422 and "4 to 6" in r.json()["detail"] and "uppercase" in r.json()["detail"]
    assert User.objects.get(username="user03").password == old_hash
    r = anon.post_json("/api/auth/reset-password", {"uid": uid, "token": token, "new_password": "Nw5$k"})
    assert r.status_code == 200 and "has been reset" in r.json()["message"]
    u = User.objects.get(username="user03")
    assert u.password != old_hash and u.password.startswith("argon2$argon2id$") and "Nw5$k" not in u.password  # hashed, not plain text
    login("user03", "Nw5$k")
    assert Api().post_json("/api/auth/login", {"username": "user03", "password": PW}).status_code == 401  # old password gone
    # the link works exactly once
    r = anon.post_json("/api/auth/reset-password", {"uid": uid, "token": token, "new_password": "Zz9#q"})
    assert r.status_code == 400 and "invalid or has expired" in r.json()["detail"]


def test_reset_signs_out_existing_sessions_and_unlocks_the_account(anon):
    sess = login("user03")
    User.objects.filter(username="user03").update(failed_attempts=3)
    _request_reset(anon)
    uid, token = _link_parts()
    assert anon.post_json("/api/auth/reset-password", {"uid": uid, "token": token, "new_password": "Nw5$k"}).status_code == 200
    assert sess.get("/api/auth/me").status_code == 401
    assert User.objects.get(username="user03").failed_attempts == 0


@pytest.mark.parametrize("mutate", [
    lambda uid, tok: (uid, tok[:-2] + ("aa" if tok[-2:] != "aa" else "bb")),  # tampered token
    lambda uid, tok: (uid, ""),                                               # missing token
    lambda uid, tok: ("!!!", tok),                                            # garbage uid
    lambda uid, tok: ("", tok),
])
def test_invalid_reset_links_are_rejected(anon, mutate):
    _request_reset(anon)
    uid, token = mutate(*_link_parts())
    r = anon.post_json("/api/auth/reset-password", {"uid": uid, "token": token, "new_password": "Nw5$k"})
    assert r.status_code == 400 and "invalid or has expired" in r.json()["detail"]
    assert User.objects.get(username="user03").check_password(PW)


def test_expired_link_and_other_users_link_are_rejected(anon, settings):
    _request_reset(anon)
    uid, token = _link_parts()
    other_uid = _request_reset(anon, "user05@example.com") and _link_parts()[0]
    assert anon.post_json("/api/auth/reset-password", {"uid": other_uid, "token": token, "new_password": "Nw5$k"}).status_code == 400  # token is bound to its user
    settings.PASSWORD_RESET_TIMEOUT = -1
    assert anon.post_json("/api/auth/reset-password", {"uid": uid, "token": token, "new_password": "Nw5$k"}).status_code == 400


def test_deactivated_account_cannot_complete_a_reset(anon):
    _request_reset(anon)
    uid, token = _link_parts()
    User.objects.filter(username="user03").update(is_active=False)
    assert anon.post_json("/api/auth/reset-password", {"uid": uid, "token": token, "new_password": "Nw5$k"}).status_code == 400


def test_reset_is_audited_without_secrets(anon):
    _request_reset(anon)
    uid, token = _link_parts()
    anon.post_json("/api/auth/reset-password", {"uid": uid, "token": token, "new_password": "Nw5$k"})
    rows = AuditLog.objects.filter(action__startswith="auth.password_reset")
    assert {r.action for r in rows} == {"auth.password_reset.request", "auth.password_reset.complete"}
    assert all(token not in (r.detail or "") and "Nw5$k" not in (r.detail or "") for r in rows)


# ------------------------------------------------------------------ DevTools deterrent reaches every tool page
@pytest.mark.parametrize("slug", ["redline-to-gofiler-html", "html-converter", "ppt-pdf-converter", "sec-form-dashboard"])
def test_every_tool_page_carries_the_shortcut_and_right_click_deterrent(u1, slug):
    html = u1.get(f"/api/tools/{slug}/frame").content.decode()
    assert 'e.key === "F12"' in html and '"contextmenu"' in html and 'k === "I"' in html
    assert "sourceMappingURL" not in html
