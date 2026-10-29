"""Argon2id password hasher tuned for small instances (Render starter: 0.5 CPU / 512 MB).

Django's default Argon2 parameters (memory_cost=100 MiB, parallelism=8) cost ~100 MB of RAM and ~0.5 s of CPU per
hash on 0.5 CPU, so a burst of concurrent sign-ins pushed the workers past 512 MB and the kernel killed them (load test:
70 users -> OOM kill, dropped connections, failed logins). These defaults follow the OWASP Password Storage Cheat Sheet
minimum for Argon2id (m=19 MiB, t=2, p=1): ~19 MB and ~70 ms per hash. Every value can be raised with environment
variables. The algorithm name is unchanged ("argon2"), so existing hashes still verify; they are re-hashed with the
current parameters at the user's next successful sign-in.

A semaphore plus instance-wide file locks also cap how many hashes run at the same time, so memory use stays bounded no
matter how many requests arrive at once (extra sign-ins wait a few milliseconds instead of competing for the CPU)."""
import contextlib
import os
import tempfile
import threading
import time

from django.conf import settings
from django.contrib.auth.hashers import Argon2PasswordHasher

try:
    import fcntl
except ImportError:  # Windows (local development): per-process limit only
    fcntl = None

_slots = None
_slots_lock = threading.Lock()


def _semaphore() -> threading.BoundedSemaphore:
    global _slots
    if _slots is None:
        with _slots_lock:
            if _slots is None:
                _slots = threading.BoundedSemaphore(max(1, getattr(settings, "PASSWORD_HASH_CONCURRENCY", 1)))
    return _slots


@contextlib.contextmanager
def _hash_slot():
    """At most PASSWORD_HASH_CONCURRENCY hashes at a time in this process AND across all gunicorn workers on the instance
    (file locks), so N workers cannot multiply the memory peak. Hashes saved with Django's old defaults still need
    ~100 MB each to verify until each user's next sign-in re-hashes them."""
    with _semaphore():
        if fcntl is None:
            yield
            return
        n = max(1, getattr(settings, "PASSWORD_HASH_CONCURRENCY", 1))
        base = os.path.join(getattr(settings, "PASSWORD_HASH_LOCK_DIR", "") or tempfile.gettempdir(), "ff-pwhash")
        fds = []
        try:
            for i in range(n):
                fds.append(os.open(f"{base}.{i}.lock", os.O_RDWR | os.O_CREAT, 0o600))
        except OSError:  # lock files cannot be created: fall back to the per-process limit
            for fd in fds:
                os.close(fd)
            yield
            return
        held = None
        try:
            while held is None:
                for fd in fds:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        held = fd
                        break
                    except BlockingIOError:
                        continue
                if held is None:
                    time.sleep(0.005)
            yield
        finally:
            if held is not None:
                fcntl.flock(held, fcntl.LOCK_UN)
            for fd in fds:
                os.close(fd)


class TunedArgon2PasswordHasher(Argon2PasswordHasher):
    @property
    def time_cost(self):
        return getattr(settings, "ARGON2_TIME_COST", 2)

    @property
    def memory_cost(self):
        return getattr(settings, "ARGON2_MEMORY_COST_KIB", 19456)

    @property
    def parallelism(self):
        return getattr(settings, "ARGON2_PARALLELISM", 1)

    def encode(self, password, salt):
        with _hash_slot():
            return super().encode(password, salt)

    def verify(self, password, encoded):
        with _hash_slot():
            return super().verify(password, encoded)
