"""Regression tests for the fixes made after load testing (70+ concurrent users)."""
import threading

import pytest
from django.contrib.auth.hashers import Argon2PasswordHasher, check_password, get_hasher
from django.db import connection
from django.test import RequestFactory

from portal.models import User
from portal.services import client_ip

from .conftest import PW, Api, login


def test_office_behind_one_ip_can_all_sign_in(settings):
    """Many colleagues share one public IP: the per-account limit must not block the rest of the office."""
    settings.LOGIN_RATE_LIMIT = 3
    settings.LOGIN_IP_RATE_LIMIT = 1000
    for i in range(1, 11):  # 10 different accounts from the same IP, more than LOGIN_RATE_LIMIT
        login(f"user{i:02d}")


def test_brute_force_on_one_account_is_still_rate_limited(settings, anon):
    settings.LOGIN_RATE_LIMIT = 3
    codes = [anon.post_json("/api/auth/login", {"username": "user02", "password": "Wr0ng!"}).status_code for _ in range(5)]
    assert codes[-1] == 429
    login("user03")  # other accounts from the same IP are unaffected


def test_password_spraying_hits_the_per_ip_ceiling(settings, anon):
    settings.LOGIN_IP_RATE_LIMIT = 4
    codes = [anon.post_json("/api/auth/login", {"username": f"user{i:02d}", "password": "Wr0ng!"}).status_code for i in range(1, 7)]
    assert codes[-1] == 429


def test_hasher_uses_bounded_argon2id_parameters():
    h = get_hasher()
    assert h.algorithm == "argon2"
    encoded = User.objects.get(username="user01").password
    assert encoded.startswith("argon2$argon2id$")
    p = h.params()
    assert p.memory_cost <= 65536 and p.parallelism <= 4  # bounded RAM per hash on a 512 MB instance


def test_legacy_default_argon2_hash_still_verifies_and_is_upgraded():
    legacy = Argon2PasswordHasher().encode(PW, Argon2PasswordHasher().salt())  # Django default parameters (m=102400)
    assert "m=102400" in legacy
    User.objects.filter(username="user05").update(password=legacy)
    login("user05")  # still works
    upgraded = User.objects.get(username="user05").password
    assert "m=102400" not in upgraded and check_password(PW, upgraded)
    login("user05")  # and keeps working after the re-hash


def test_lockout_still_triggers(settings):
    a = Api()
    for _ in range(settings.MAX_FAILED_LOGINS):
        assert a.post_json("/api/auth/login", {"username": "user06", "password": "Wr0ng!"}).status_code == 401
    assert a.post_json("/api/auth/login", {"username": "user06", "password": PW}).status_code == 401  # locked


@pytest.mark.django_db(transaction=True)
def test_failed_attempt_counter_is_atomic_under_concurrency(settings):
    if connection.vendor == "sqlite":
        pytest.skip("concurrent writes need PostgreSQL (TEST_DB_ENGINE=postgres)")
    settings.MAX_FAILED_LOGINS = 1000
    from portal.views.auth import _register_failure
    u = User.objects.create(username="race", email="race@example.com", full_name="Race", password="x")

    def fail():
        _register_failure(User.objects.get(pk=u.pk))
        connection.close()

    threads = [threading.Thread(target=fail) for _ in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert User.objects.get(pk=u.pk).failed_attempts == 20


def test_client_ip_proxy_hops(settings):
    rf = RequestFactory()
    req = rf.get("/", HTTP_X_FORWARDED_FOR="6.6.6.6, 1.2.3.4", REMOTE_ADDR="10.0.0.1")
    settings.TRUST_PROXY_HEADERS = False
    assert client_ip(req) == "10.0.0.1"
    settings.TRUST_PROXY_HEADERS = True
    settings.PROXY_HOPS = 0
    assert client_ip(req) == "6.6.6.6"  # legacy: left-most entry
    settings.PROXY_HOPS = 1
    assert client_ip(req) == "1.2.3.4"  # the address added by the trusted proxy, cannot be forged by the client
