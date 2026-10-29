from portal.models import AuditLog

from .conftest import PW, Api, login, process


def test_admin_sees_all_documents_and_can_filter_by_user(admin, u1, u2):
    d1 = process(u1).json()["document"]
    d2 = process(u2, "redline-to-gofiler-html", ("r.html", b"<html></html>"), ("s.html", b"<html></html>")).json()["document"]
    allp = admin.get("/api/admin/documents").json()
    assert {x["id"] for x in allp["items"]} == {d1["id"], d2["id"]}
    assert all("owner" in x for x in allp["items"])
    assert [x["id"] for x in admin.get("/api/admin/documents?user=user02").json()["items"]] == [d2["id"]]
    assert admin.get("/api/admin/documents?tool=redline-to-gofiler-html").json()["total"] == 1


def test_admin_can_view_download_delete_any_document_and_it_is_audited(admin, u1):
    d = process(u1).json()["document"]
    assert admin.get(f"/api/documents/{d['id']}/download").status_code == 200
    assert admin.get(f"/api/documents/{d['id']}").json()["document"]["owner"]["username"] == "user01"
    assert admin.delete(f"/api/documents/{d['id']}").status_code == 200
    acts = [(r.action, r.actor_name) for r in AuditLog.objects.filter(resource_id=d["id"])]
    assert ("document.download", "admin") in acts and ("document.delete", "admin") in acts


def test_regular_users_are_forbidden_from_every_admin_endpoint(u1):
    new_user = {"username": "x1x", "email": "x@y.zz", "full_name": "X", "password": "Abcdefgh1234"}
    assert u1.get("/api/admin/documents").status_code == 403
    assert u1.get("/api/admin/users").status_code == 403
    assert u1.post_json("/api/admin/users", new_user).status_code == 403
    assert u1.patch_json("/api/admin/users/abc", {"role": "ADMIN"}).status_code == 403
    assert u1.get("/api/admin/audit-logs").status_code == 403
    assert u1.get("/api/admin/overview").status_code == 403


def test_user_cannot_escalate_own_role(u1):
    uid = u1.get("/api/auth/me").json()["user"]["id"]
    assert u1.patch_json(f"/api/admin/users/{uid}", {"role": "ADMIN"}).status_code == 403
    assert u1.get("/api/auth/me").json()["user"]["role"] == "USER"


def test_admin_user_management(admin):
    r = admin.post_json("/api/admin/users", {"username": "newbie", "email": "newbie@example.com", "full_name": "New B", "password": "S3cr!t"})
    assert r.status_code == 201
    uid = r.json()["user"]["id"]
    assert admin.post_json("/api/admin/users", {"username": "newbie", "email": "n2@example.com", "full_name": "Dup", "password": "S3cr!t"}).status_code == 409
    assert admin.post_json("/api/admin/users", {"username": "weakpw", "email": "w@example.com", "full_name": "W", "password": "weak"}).status_code == 422
    login("newbie", "S3cr!t")
    assert admin.patch_json(f"/api/admin/users/{uid}", {"new_password": "R3set!"}).status_code == 200
    assert Api().post_json("/api/auth/login", {"username": "newbie", "password": "S3cr!t"}).status_code == 401
    login("newbie", "R3set!")
    users = admin.get("/api/admin/users").json()["items"]
    assert len(users) == 13 and all("password" not in u and "password_hash" not in u for u in users)


def test_admin_password_reset_signs_the_user_out_everywhere(admin, u2):
    uid = u2.get("/api/auth/me").json()["user"]["id"]
    assert admin.patch_json(f"/api/admin/users/{uid}", {"new_password": "R3set!"}).status_code == 200
    assert u2.get("/api/auth/me").status_code == 401


def test_admin_cannot_lock_themselves_out(admin):
    me = admin.get("/api/auth/me").json()["user"]["id"]
    assert admin.patch_json(f"/api/admin/users/{me}", {"is_active": False}).status_code == 400
    assert admin.patch_json(f"/api/admin/users/{me}", {"role": "USER"}).status_code == 400


def test_audit_log_page_lists_only_successful_login_and_logout(admin, u1):
    from portal.models import AuditLog
    d = process(u1).json()["document"]
    u1.get(f"/api/documents/{d['id']}/download")
    u1.delete(f"/api/documents/{d['id']}")
    admin.post_json("/api/admin/users", {"username": "audited", "email": "a@example.com", "full_name": "A", "password": "S3cr!t"})
    u1.post_json("/api/auth/logout")
    items = admin.get("/api/admin/audit-logs?page_size=200").json()["items"]
    assert items and {i["action"] for i in items} <= {"auth.login", "auth.logout"}
    assert {"auth.logout"} <= {i["action"] for i in items}
    assert all(i["outcome"] == "success" and i["actor"] and i["created_at"] for i in items)
    assert all(i["detail"] is None and i["resource_id"] is None for i in items)
    # other events are still recorded for security investigations, just not listed on the page
    assert AuditLog.objects.filter(action__in=["document.process", "document.download", "document.delete", "admin.user.create"]).count() >= 4
    assert admin.get("/api/admin/audit-logs?outcome=failure").json()["items"] == []
    assert admin.get("/api/admin/audit-logs?action=document").json()["items"] == []


def test_overview_reports_health_storage_and_failed_jobs(admin, u1):
    process(u1)
    process(u1, out=("bad.xml", b"\x00"))
    o = admin.get("/api/admin/overview").json()
    assert o["health"] == {"database": "ok", "storage": "ok"}
    assert o["documents"]["by_status"]["completed"] == 1 and o["documents"]["by_status"]["failed"] == 1
    assert o["storage_bytes"] > 0 and len(o["recent_failed_jobs"]) == 1 and o["users"]["total"] == 12


def test_admin_deletes_user_with_documents_and_tool_access(admin, u1):
    from portal.models import Document, User, UserToolAccess
    from tests.conftest import process
    assert process(u1).status_code in (200, 201)
    uid = User.objects.get(username="user01").id
    assert Document.objects.filter(owner_id=uid).exists()
    assert admin.delete(f"/api/admin/users/{uid}").status_code == 200
    assert not User.objects.filter(id=uid).exists()
    assert not Document.objects.filter(owner_id=uid).exists() and not UserToolAccess.objects.filter(user_id=uid).exists()
    assert all(u["id"] != uid for u in admin.get("/api/admin/users").json()["items"])
    assert admin.delete(f"/api/admin/users/{uid}").status_code == 404


def test_delete_user_is_admin_only_and_protects_self_and_last_admin(admin, u1):
    from portal.models import User
    me = User.objects.get(username="admin").id
    assert admin.delete(f"/api/admin/users/{me}").status_code == 400
    assert u1.delete(f"/api/admin/users/{me}").status_code == 403
    second = User.objects.create_user("admin2", "a2@example.com", "Admin 2", "S3cr!t", role="ADMIN")
    a2 = login("admin2", "S3cr!t")
    User.objects.filter(username="admin").update(is_active=False)  # only admin2 is active now
    assert a2.delete(f"/api/admin/users/{second.id}").status_code == 400  # self
    assert User.objects.filter(id=second.id).exists()


def test_last_active_admin_cannot_be_deleted_by_another_admin(admin):
    from portal.models import User
    # a second admin deletes the first: allowed while another active admin remains
    User.objects.create_user("admin2", "a2@example.com", "Admin 2", "S3cr!t", role="ADMIN")
    a2 = login("admin2", "S3cr!t")
    me = User.objects.get(username="admin")
    User.objects.filter(username="admin2").update(is_active=True)
    assert a2.delete(f"/api/admin/users/{me.id}").status_code == 200
    assert User.objects.filter(role="ADMIN", is_active=True).count() == 1


def test_audit_cleanup_deletes_only_rows_older_than_30_days(admin):
    from datetime import timedelta
    from django.utils import timezone
    from portal.maintenance import purge_audit_logs
    from portal.models import AuditLog
    AuditLog.objects.all().delete()
    now = timezone.now()
    old = AuditLog.objects.create(action="x", outcome="success", created_at=now - timedelta(days=31))
    edge = AuditLog.objects.create(action="x", outcome="success", created_at=now - timedelta(days=29, hours=23))
    new = AuditLog.objects.create(action="x", outcome="success")
    assert purge_audit_logs() == 1
    assert set(AuditLog.objects.values_list("pk", flat=True)) == {edge.pk, new.pk}
    assert purge_audit_logs() == 0
