import io
import zipfile
from datetime import timedelta

import pytest
from django.utils import timezone

from portal.maintenance import purge
from portal.models import Document
from portal.storage import get_storage

from .conftest import body, login, pdf_bytes, process, xlsx_bytes, Api


def _zip():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("index.htm", "<html/>")
    return b.getvalue()


TOOL_CASES = [
    ("html-converter", ("converted.htm", b"<html><body>x</body></html>"), ("source.docx", None)),
    ("sec-form-dashboard", ("report.txt", b"check results"), ("filing.htm", b"<html>src</html>")),
    ("redline-to-gofiler-html", ("redline.html", b"<html><body>x</body></html>"), ("source.htm", b"<html>src</html>")),
    ("ppt-pdf-converter", ("deck.zip", None), ("deck.pdf", pdf_bytes())),
]


@pytest.mark.parametrize("slug,out,orig", TOOL_CASES)
def test_all_four_process_endpoints_store_list_and_download(u1, slug, out, orig):
    out = (out[0], out[1] if out[1] is not None else _zip())
    r = process(u1, slug, out, orig)
    assert r.status_code == 200, r.content
    d = r.json()["document"]
    assert d["status"] == "completed" and d["tool"] == slug and d["output_filename"] == out[0]
    assert d["output_size"] == len(out[1]) and d["original_filename"] == orig[0]
    listed = u1.get("/api/documents").json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == d["id"]
    assert body(u1.get(f"/api/documents/{d['id']}/download")) == out[1]
    assert u1.get(f"/api/documents/{d['id']}/download?kind=original").status_code == 200


def test_users_only_see_their_own_documents(u1, u2):
    d1 = process(u1).json()["document"]
    d2 = process(u2, out=("b.xml", b"<b/>")).json()["document"]
    assert [x["id"] for x in u1.get("/api/documents").json()["items"]] == [d1["id"]]
    assert [x["id"] for x in u2.get("/api/documents").json()["items"]] == [d2["id"]]


def test_idor_other_users_document_cannot_be_read_viewed_downloaded_or_deleted(u1, u2):
    victim = process(u1).json()["document"]["id"]
    for method, url in [("get", f"/api/documents/{victim}"), ("get", f"/api/documents/{victim}/view"),
                        ("get", f"/api/documents/{victim}/download"), ("get", f"/api/documents/{victim}/download?kind=original"),
                        ("delete", f"/api/documents/{victim}")]:
        r = getattr(u2, method)(url)
        assert r.status_code == 404, (method, url, r.status_code)
    assert u1.get(f"/api/documents/{victim}").status_code == 200  # untouched
    nonexistent = u2.get("/api/documents/" + "0" * 32)
    assert nonexistent.status_code == 404 and nonexistent.json() == u2.get(f"/api/documents/{victim}").json()  # no existence leak


def test_client_cannot_pick_the_owner(u1, u2):
    uid2 = u2.get("/api/auth/me").json()["user"]["id"]
    r = u1.post_files("/api/process/html-converter", {"output": ("a.xml", b"<a/>")}, data={"owner_id": uid2, "user_id": uid2})
    assert r.status_code == 200
    assert u2.get("/api/documents").json()["total"] == 0
    assert u1.get("/api/documents").json()["total"] == 1


def test_listing_params_cannot_widen_scope(u1, u2):
    process(u2)
    uid2 = u2.get("/api/auth/me").json()["user"]["id"]
    assert u1.get(f"/api/documents?owner_id={uid2}&user={uid2}").json()["total"] == 0


def test_unauthenticated_access_is_rejected(anon):
    for url in ["/api/documents", "/api/auth/me", "/api/admin/users", "/api/tools/html-converter/frame"]:
        assert anon.get(url).status_code == 401
    assert anon.post_files("/api/process/html-converter", {"output": ("a.xml", b"<a/>")}).status_code == 401


def test_delete_is_soft_then_hidden_and_purged_by_retention(u1, settings):
    d = process(u1).json()["document"]
    key = Document.objects.get(id=d["id"]).output_key
    assert u1.delete(f"/api/documents/{d['id']}").status_code == 200
    assert u1.get(f"/api/documents/{d['id']}").status_code == 404
    assert u1.get("/api/documents").json()["total"] == 0
    assert get_storage().exists(key)  # still within retention
    Document.objects.filter(id=d["id"]).update(deleted_at=timezone.now() - timedelta(days=settings.DELETED_FILE_RETENTION_DAYS + 1))
    assert purge()["files_purged"] >= 1
    assert not get_storage().exists(key)


def test_search_filter_and_pagination(u1):
    for i in range(12):
        process(u1, out=(f"report_{i:02d}.xml", b"<a/>"))
    process(u1, "redline-to-gofiler-html", ("special.html", b"<html></html>"), ("src.html", b"<html></html>"))
    assert u1.get("/api/documents?page_size=5").json()["total"] == 13
    assert len(u1.get("/api/documents?page=3&page_size=5").json()["items"]) == 3
    assert u1.get("/api/documents?q=special").json()["total"] == 1
    assert u1.get("/api/documents?q=%25").json()["total"] == 0  # LIKE wildcard is escaped, not injected
    assert u1.get("/api/documents?tool=redline-to-gofiler-html").json()["total"] == 1
    assert u1.get("/api/documents?status=failed").json()["total"] == 0
    assert u1.get("/api/documents?date_from=2999-01-01").json()["total"] == 0
    assert u1.get("/api/documents?q=' OR 1=1 --").json()["total"] == 0  # parameterised
    assert u1.get("/api/documents?page=abc").status_code == 422


def test_view_serves_sandboxed_preview_and_refuses_binary(u1):
    d = process(u1, "redline-to-gofiler-html", ("x.html", b"<html><script>alert(1)</script></html>"), ("s.html", b"<html></html>")).json()["document"]
    r = u1.get(f"/api/documents/{d['id']}/view")
    csp = r.headers["Content-Security-Policy"]
    assert r.status_code == 200 and "sandbox" in csp and "script-src" not in csp
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    x = process(u1).json()["document"]
    assert u1.get(f"/api/documents/{x['id']}/view?kind=original").status_code == 415  # xlsx not previewable


# ---------------- upload validation ----------------
def test_content_is_inspected_not_just_extension(u1):
    assert process(u1, out=("evil.xml", b"MZ\x90\x00 binary")).status_code == 422
    assert process(u1, "ppt-pdf-converter", ("o.zip", _zip()), ("fake.pdf", b"not a pdf")).status_code == 422
    assert process(u1, orig=("fake.xlsx", b"PK\x03\x04junk")).status_code == 422
    assert process(u1, out=("a.exe", b"MZ")).status_code == 422
    assert process(u1, out=("a.xml", b"")).status_code == 422
    assert process(u1, orig=("macro.docx", xlsx_bytes())).status_code == 422  # .docx name, but Excel package inside


def test_failed_jobs_are_recorded_for_review(u1, admin):
    process(u1, out=("evil.xml", b"\x00\x01\x02"))
    failed = admin.get("/api/admin/documents?status=failed").json()
    assert failed["total"] == 1 and failed["items"][0]["error_summary"]
    assert u1.get("/api/documents?status=failed").json()["total"] == 1


def test_oversize_upload_rejected(u1):
    assert process(u1, out=("big.xml", b"<a>" + b"x" * (3 * 1024 * 1024))).status_code == 422   # over MAX_UPLOAD_MB
    assert process(u1, out=("huge.xml", b"<a>" + b"x" * (6 * 1024 * 1024))).status_code == 413   # rejected before reading


def test_zip_bomb_and_zip_slip_rejected(u1):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("../../etc/evil.txt", "x")
    assert process(u1, "ppt-pdf-converter", ("o.zip", b.getvalue()), ("d.pdf", pdf_bytes())).status_code == 422
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("big.txt", b"0" * (5 * 1024 * 1024))
    assert process(u1, "ppt-pdf-converter", ("o.zip", b.getvalue()), ("d.pdf", pdf_bytes())).status_code == 422


def test_path_traversal_filename_is_neutralised(u1, settings):
    r = process(u1, out=("../../../etc/passwd.xml", b"<a/>"))
    assert r.status_code == 200
    d = r.json()["document"]
    assert "/" not in d["output_filename"] and ".." not in d["output_filename"]
    key = Document.objects.get(id=d["id"]).output_key
    assert key.startswith("outputs/") and "passwd" not in key  # storage key is random, never user-derived
    assert str(settings.STORAGE_LOCAL_DIR) not in str(d)  # no server paths leak to the client


def test_storage_keys_never_exposed_and_ids_are_random(u1):
    d = process(u1).json()["document"]
    assert len(d["id"]) == 32 and "output_key" not in d and "original_key" not in d


# ---- eye icon: preview shows the stored output exactly ----
def _package(**files) -> bytes:
    import io, zipfile
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n, d in files.items():
            z.writestr(n.replace("__", "/"), d)
    return b.getvalue()


def test_zip_package_preview_embeds_images_and_leaves_stored_file_untouched(u1, admin, u2):
    from .conftest import body
    png = b"\x89PNG\r\n\x1a\nfakeimage"
    pkg = _package(**{"deck.htm": '<html><body><table><tr><td>Q1</td></tr></table><img src="image001.png" width="10"></body></html>', "image001.png": png})
    d = process(u1, slug="ppt-pdf-converter", out=("deck_edgar.zip", pkg), orig=(None, None)).json()["document"]
    r = u1.get(f"/api/documents/{d['id']}/view")
    assert r.status_code == 200 and r["Content-Type"].startswith("text/html")
    page = body(r).decode()
    assert "<td>Q1</td>" in page and "data:image/png;base64," in page and 'src="image001.png"' not in page
    assert "sandbox" in r["Content-Security-Policy"]
    assert body(u1.get(f"/api/documents/{d['id']}/download")) == pkg  # the download is the original bytes
    assert admin.get(f"/api/documents/{d['id']}/view").status_code == 200  # admin may view
    assert u2.get(f"/api/documents/{d['id']}/view").status_code == 404  # other users may not


def test_zip_with_several_exhibits_and_text_charset(u1):
    from .conftest import body
    pkg = _package(**{"ex1.htm": "<html><body><p>ONE</p></body></html>", "ex2.htm": "<html><body><p>TWO</p></body></html>"})
    d = process(u1, slug="html-converter", out=("x_EDGAR.zip", pkg)).json()["document"]
    page = body(u1.get(f"/api/documents/{d['id']}/view")).decode()
    assert "ONE" in page and "TWO" in page
    x = process(u1, out=("t.xml", "<?xml version='1.0'?><a>caf\u00e9</a>".encode("utf-8"))).json()["document"]
    r = u1.get(f"/api/documents/{x['id']}/view")
    assert "charset=utf-8" in r["Content-Type"] and body(r).decode("utf-8").endswith("caf\u00e9</a>")
    z = process(u1, slug="html-converter", out=("n.zip", _package(**{"a.txt": "hi"}))).json()["document"]
    assert u1.get(f"/api/documents/{z['id']}/view").status_code == 415  # nothing to preview: download instead


def test_files_are_stored_in_the_database_and_survive_loss_of_local_disk(u1, settings):
    """Regression: previews failed after a day or two because files lived only on the (ephemeral) local disk."""
    import shutil
    from portal.models import StoredFile, StoredFileChunk
    from portal.storage import reset_storage
    data = b"<html><body>hello " + b"x" * (2 * 1024 * 1024 + 17) + b"</body></html>"
    settings.MAX_UPLOAD_MB = 5
    d = process(u1, "redline-to-gofiler-html", ("big.html", data), ("src.html", b"<html>src</html>")).json()["document"]
    doc = Document.objects.get(id=d["id"])
    assert StoredFile.objects.filter(key=doc.output_key).exists()
    assert StoredFileChunk.objects.filter(file_id=doc.output_key).count() == 3
    shutil.rmtree(settings.STORAGE_LOCAL_DIR, ignore_errors=True)  # simulate a wiped container disk / redeploy
    reset_storage()
    r = u1.get(f"/api/documents/{d['id']}/view")
    assert r.status_code == 200
    assert b"".join(r.streaming_content if r.streaming else [r.content]) .count(b"x") >= 2 * 1024 * 1024
    assert u1.get(f"/api/documents/{d['id']}/view?kind=original").status_code == 200
    assert b"".join(u1.get(f"/api/documents/{d['id']}/download").streaming_content) == data


def test_legacy_local_files_still_served_and_migrated(u1, settings):
    from portal.storage import LocalStorage, get_storage
    from django.core.management import call_command
    from portal.models import StoredFile
    d = process(u1).json()["document"]
    doc = Document.objects.get(id=d["id"])
    raw = b"".join(get_storage().stream(doc.output_key))
    key = "outputs/2026/01/legacykey"
    LocalStorage(settings.STORAGE_LOCAL_DIR).put(key, raw)
    Document.objects.filter(id=doc.id).update(output_key=key)
    assert u1.get(f"/api/documents/{doc.id}/view").status_code == 200  # served from the old disk
    call_command("migrate_files_to_db")
    assert StoredFile.objects.filter(key=key).exists()


def test_check_files_command_reports_missing(u1):
    from io import StringIO
    from django.core.management import call_command
    d = process(u1).json()["document"]
    out = StringIO(); call_command("check_files", stdout=out)
    assert "missing=0" in out.getvalue()
    from portal.models import StoredFile
    StoredFile.objects.all().delete()
    out = StringIO(); call_command("check_files", stdout=out)
    assert "MISSING" in out.getvalue()
