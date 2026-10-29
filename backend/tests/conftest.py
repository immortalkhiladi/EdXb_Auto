import io
import json
import zipfile

import pytest
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from portal.models import User
from portal.security import limiter
from portal.storage import reset_storage

PW = "Str0ng-Passw0rd!"
_hash = None


def pw_hash() -> str:
    global _hash
    if _hash is None:
        _hash = make_password(PW)  # Argon2 is deliberately slow: hash once, reuse
    return _hash


class Api:
    """Test client that behaves like the SPA: CSRF enforcement ON, token fetched from /api/auth/csrf."""

    def __init__(self):
        self.c = Client(enforce_csrf_checks=True)

    def csrf(self):
        return self.c.get("/api/auth/csrf").json()["csrfToken"]

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post_json(self, url, body=None, **extra):
        return self.c.post(url, json.dumps(body or {}), content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf(), **extra)

    def patch_json(self, url, body=None, **extra):
        return self.c.patch(url, json.dumps(body or {}), content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf(), **extra)

    def put_json(self, url, body=None, **extra):
        return self.c.put(url, json.dumps(body or {}), content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf(), **extra)

    def delete(self, url, **extra):
        return self.c.delete(url, HTTP_X_CSRFTOKEN=self.csrf(), **extra)

    def post_files(self, url, files, data=None, **extra):
        payload = {**(data or {}), **{k: SimpleUploadedFile(v[0], v[1]) for k, v in files.items()}}
        return self.c.post(url, payload, HTTP_X_CSRFTOKEN=self.csrf(), **extra)

    def options(self, url, **extra):
        return self.c.options(url, **extra)


def body(resp) -> bytes:
    return b"".join(resp.streaming_content) if getattr(resp, "streaming", False) else resp.content


@pytest.fixture(autouse=True)
def fresh(db):
    limiter.reset()
    reset_storage()
    users = [User(username="admin", email="admin@example.com", full_name="Admin", role="ADMIN", password=pw_hash())]
    users += [User(username="md01", email="md01@example.com", full_name="MD 01", role="MD", password=pw_hash())]
    users += [User(username=f"user{i:02d}", email=f"user{i:02d}@example.com", full_name=f"User {i:02d}", role="USER", password=pw_hash())
              for i in range(1, 11)]
    User.objects.bulk_create(users)
    from portal.models import UserToolAccess
    from portal.tools import TOOLS
    UserToolAccess.objects.bulk_create([UserToolAccess(user=u, tool=t) for u in users if u.role == "USER" for t in TOOLS])  # all four, like a new user


def login(username: str, password: str = PW) -> Api:
    a = Api()
    r = a.post_json("/api/auth/login", {"username": username, "password": password})
    assert r.status_code == 200, r.content
    assert r.json()["status"] == "ok"
    return a


@pytest.fixture
def anon():
    return Api()


@pytest.fixture
def admin():
    return login("admin")


@pytest.fixture
def md():
    return login("md01")


@pytest.fixture
def u1():
    return login("user01")


@pytest.fixture
def u2():
    return login("user02")


def xlsx_bytes() -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
    return b.getvalue()


def docx_bytes() -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<document/>")
    return b.getvalue()


def pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def process(api, slug="html-converter", out=("result.xml", b"<?xml version='1.0'?><a/>"), orig=("source.docx", None), data=None):
    files = {"output": out}
    if orig and orig[0]:
        files["original"] = (orig[0], orig[1] if orig[1] is not None else docx_bytes())
    return api.post_files(f"/api/process/{slug}", files, data=data)
