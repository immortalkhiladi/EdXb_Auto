"""Admin-controlled tool access: ADMIN picks which of the four tools each USER may use; the backend enforces it on every
tool operation (open, process/upload, list, view/download/delete of the tool's documents)."""
import pytest

from portal.models import AuditLog, Document, User, UserToolAccess
from portal.tools import TOOLS

from .conftest import Api, login, process

ALL = list(TOOLS)
T1, T2, T3, T4 = ALL  # Redline to GoFiler HTML, GoFiler HTML Converter, PPT and PDF Converter, SEC Form Type Dashboard
NOFILE = (None, None)


def set_tools(admin, username, tools):
    uid = User.objects.get(username=username).id
    return admin.put_json("/api/admin/tool-access", {"changes": [{"user_id": uid, "tools": tools}]})


def slugs_of(username):
    return set(UserToolAccess.objects.filter(user__username=username).values_list("tool", flat=True))


def can_open(api, slug):
    return api.get(f"/api/tools/{slug}/frame").status_code


def can_process(api, slug):
    return process(api, slug, orig=NOFILE).status_code


# ------------------------------------------------------------------ the four tools exist
def test_there_are_exactly_the_four_tools():
    assert [TOOLS[s].label for s in ALL] == ["Redline to GoFiler HTML", "GoFiler HTML Converter", "PPT and PDF Converter", "SEC Form Type Dashboard"]


# ------------------------------------------------------------------ admin screen API
def test_admin_lists_all_users_with_their_tools(admin):
    r = admin.get("/api/admin/tool-access").json()
    assert [t["slug"] for t in r["tools"]] == ALL
    rows = {u["username"]: u for u in r["users"]}
    assert len(rows) == 12 and rows["user01"]["tools"] == sorted(ALL)  # new users start with all four
    assert rows["admin"]["all_access"] and rows["md01"]["all_access"] and not rows["user01"]["all_access"]
    assert rows["admin"]["tools"] == sorted(ALL) and rows["md01"]["tools"] == sorted(ALL)


def test_only_admin_can_manage_tool_access(anon, md, u1):
    uid = User.objects.get(username="user02").id
    body = {"changes": [{"user_id": uid, "tools": [T1]}]}
    assert anon.get("/api/admin/tool-access").status_code == 401
    for who in (md, u1):  # MD gets no permission-management capability
        assert who.get("/api/admin/tool-access").status_code == 403
        assert who.put_json("/api/admin/tool-access", body).status_code == 403
    assert slugs_of("user02") == set(ALL)


def test_example_user01_gets_only_the_first_two_tools(admin, u1):
    assert set_tools(admin, "user01", [T1, T2]).status_code == 200
    assert slugs_of("user01") == {T1, T2}
    assert [can_open(u1, s) for s in ALL] == [200, 200, 403, 403]
    assert [can_process(u1, s) for s in ALL] == [200, 200, 403, 403]
    assert Document.objects.filter(owner__username="user01").count() == 2  # nothing was stored for the refused tools
    assert u1.get("/api/auth/me").json()["user"]["tools"] == sorted([T1, T2])
    assert [t["slug"] for t in u1.get("/api/tools").json()["items"]] == [T1, T2]


def test_assign_and_revoke_take_effect_immediately_without_relogin(admin, u1):
    assert can_open(u1, T3) == 200
    set_tools(admin, "user01", [T1, T2, T4])           # revoke T3 while user01 is signed in
    assert can_open(u1, T3) == 403 and can_process(u1, T3) == 403
    assert can_open(u1, T4) == 200
    set_tools(admin, "user01", [T1, T2, T3, T4])        # grant it back
    assert can_open(u1, T3) == 200 and can_process(u1, T3) == 200
    set_tools(admin, "user01", [])                      # revoke everything
    assert [can_open(u1, s) for s in ALL] == [403] * 4
    assert u1.get("/api/tools").json()["items"] == []


def test_permissions_persist_across_logout_and_login(admin, u1):
    set_tools(admin, "user01", [T1, T2])
    u1.post_json("/api/auth/logout")
    again = login("user01")
    assert [can_open(again, s) for s in ALL] == [200, 200, 403, 403]
    assert again.get("/api/auth/me").json()["user"]["tools"] == sorted([T1, T2])
    assert slugs_of("user01") == {T1, T2}  # stored in the database, so a server restart changes nothing


def test_one_users_permissions_do_not_affect_another(admin, u1, u2):
    set_tools(admin, "user01", [T1])
    assert can_open(u1, T2) == 403 and can_open(u2, T2) == 200
    assert slugs_of("user02") == set(ALL)


def test_restricted_tools_are_blocked_for_direct_urls_and_unknown_tools(anon, admin, u1):
    set_tools(admin, "user01", [T1])
    assert u1.get(f"/api/tools/{T2}/frame").status_code == 403
    assert u1.get("/api/tools/not-a-tool/frame").status_code == 404
    assert anon.get(f"/api/tools/{T1}/frame").status_code == 401
    assert process(anon, T1, orig=NOFILE).status_code == 401
    assert "do not have access" in u1.get(f"/api/tools/{T2}/frame").json()["detail"]


def test_denied_attempts_are_audited(admin, u1):
    set_tools(admin, "user01", [T1])
    can_process(u1, T3)
    assert AuditLog.objects.filter(action="tool.access", outcome="denied", actor_name="user01", resource_id=T3).exists()
    assert AuditLog.objects.filter(action="admin.user.tools", actor_name="admin", detail__contains="revoked").exists()


# ------------------------------------------------------------------ documents of a tool
def test_documents_of_a_revoked_tool_are_locked_and_come_back_when_granted(admin, u1):
    d1 = process(u1, T1, orig=NOFILE).json()["document"]
    d2 = process(u1, T2, orig=NOFILE).json()["document"]
    set_tools(admin, "user01", [T1])
    assert [x["id"] for x in u1.get("/api/documents").json()["items"]] == [d1["id"]]
    assert list(u1.get("/api/documents").json()["tools"]) == [T1]
    for url in (f"/api/documents/{d2['id']}", f"/api/documents/{d2['id']}/download", f"/api/documents/{d2['id']}/view"):
        assert u1.get(url).status_code == 403, url
    assert u1.delete(f"/api/documents/{d2['id']}").status_code == 403
    assert u1.get(f"/api/documents/{d1['id']}/download").status_code == 200
    set_tools(admin, "user01", [T1, T2])
    assert u1.get(f"/api/documents/{d2['id']}/download").status_code == 200


def test_other_users_still_cannot_reach_documents(admin, u1, u2):
    d = process(u1, T1, orig=NOFILE).json()["document"]
    assert u2.get(f"/api/documents/{d['id']}").status_code == 404
    assert u2.get(f"/api/documents/{d['id']}/download").status_code == 404


# ------------------------------------------------------------------ roles
def test_admin_and_md_keep_all_four_tools_and_md_document_rules_are_unchanged(admin, md, u1):
    set_tools(admin, "user01", [])
    for who in (admin, md):
        assert [can_open(who, s) for s in ALL] == [200] * 4
        assert [can_process(who, s) for s in ALL] == [200] * 4
        assert sorted(t["slug"] for t in who.get("/api/tools").json()["items"]) == sorted(ALL)
    d = Document.objects.filter(owner__username="md01").first()
    assert md.get(f"/api/documents/{d.id}/download").status_code == 200
    # MD still sees every user's documents, even for tools that user lost; still cannot delete them
    process_doc = Document.objects.create(owner=User.objects.get(username="user01"), tool=T3, document_name="x", status="completed")
    assert process_doc.id in [x["id"] for x in md.get("/api/admin/documents").json()["items"]]
    assert md.delete(f"/api/documents/{process_doc.id}").status_code == 403
    assert md.get(f"/api/documents/{process_doc.id}").status_code == 200


def test_admin_and_md_accounts_cannot_be_given_a_tool_list(admin):
    for name in ("admin", "md01"):
        r = set_tools(admin, name, [T1])
        assert r.status_code == 422 and "always have access to all tools" in r.json()["detail"]
    assert not UserToolAccess.objects.filter(user__username__in=["admin", "md01"]).exists()


# ------------------------------------------------------------------ validation
def test_validation_and_all_or_nothing(admin):
    u2 = User.objects.get(username="user02").id
    u3 = User.objects.get(username="user03").id
    assert admin.put_json("/api/admin/tool-access", {}).status_code == 422
    assert admin.put_json("/api/admin/tool-access", {"changes": []}).status_code == 422
    assert admin.put_json("/api/admin/tool-access", {"changes": "x"}).status_code == 422
    assert admin.put_json("/api/admin/tool-access", {"changes": [{"user_id": u2, "tools": "all"}]}).status_code == 422
    r = admin.put_json("/api/admin/tool-access", {"changes": [{"user_id": u2, "tools": ["hack-tool"]}]})
    assert r.status_code == 422 and "Unknown tool" in r.json()["detail"]
    assert admin.put_json("/api/admin/tool-access", {"changes": [{"user_id": "nope", "tools": [T1]}]}).status_code == 404
    # one bad entry -> nothing is saved for anybody
    r = admin.put_json("/api/admin/tool-access", {"changes": [{"user_id": u2, "tools": [T1]}, {"user_id": u3, "tools": ["bad"]}]})
    assert r.status_code == 422 and slugs_of("user02") == set(ALL)
    # duplicates are harmless; unchanged users are skipped
    r = admin.put_json("/api/admin/tool-access", {"changes": [{"user_id": u2, "tools": [T1, T1]}, {"user_id": u3, "tools": ALL}]})
    assert r.status_code == 200 and r.json()["updated"] == 1 and slugs_of("user02") == {T1}


def test_put_requires_csrf(admin):
    import json
    r = admin.c.put("/api/admin/tool-access", json.dumps({"changes": []}), content_type="application/json")
    assert r.status_code == 403


# ------------------------------------------------------------------ user lifecycle
def test_new_users_get_all_tools_by_default_or_the_admins_choice(admin):
    base = {"email": "t1@example.com", "full_name": "T", "password": "Gd7#"}
    assert admin.post_json("/api/admin/users", {**base, "username": "tnew1"}).json()["user"]["tools"] == sorted(ALL)
    r = admin.post_json("/api/admin/users", {**base, "username": "tnew2", "email": "t2@example.com", "tools": [T4]})
    assert r.status_code == 201 and r.json()["user"]["tools"] == [T4]
    assert admin.post_json("/api/admin/users", {**base, "username": "tnew3", "email": "t3@example.com", "tools": ["bad"]}).status_code == 422
    assert not User.objects.filter(username="tnew3").exists()
    assert admin.post_json("/api/admin/users", {**base, "username": "tnew4", "email": "t4@example.com", "role": "MD"}).json()["user"]["tools"] == sorted(ALL)
    assert not UserToolAccess.objects.filter(user__username="tnew4").exists()  # MD: implicit, nothing stored


def test_demoting_an_md_to_user_does_not_leave_them_without_tools(admin):
    uid = User.objects.get(username="md01").id
    assert admin.patch_json(f"/api/admin/users/{uid}", {"role": "USER"}).json()["user"]["tools"] == sorted(ALL)


def test_users_list_includes_tools(admin):
    rows = {u["username"]: u for u in admin.get("/api/admin/users").json()["items"]}
    assert rows["user05"]["tools"] == sorted(ALL)


# ------------------------------------------------------------------ migration keeps today's behaviour for existing accounts
@pytest.mark.django_db(transaction=True)
def test_migration_gives_existing_users_all_tools_and_leaves_admin_md_implicit():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    ex = MigrationExecutor(connection)
    ex.migrate([("portal", "0002_user_role_md")])                      # schema before tool access existed
    UserToolAccess.objects.none()
    ex = MigrationExecutor(connection)
    ex.loader.build_graph()
    ex.migrate([("portal", "0003_user_tool_access")])
    assert UserToolAccess.objects.filter(user__role="USER").count() == 10 * 4
    assert not UserToolAccess.objects.filter(user__role__in=["ADMIN", "MD"]).exists()
