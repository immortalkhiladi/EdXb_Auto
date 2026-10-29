"""Password policy, MFA-secret encryption, rate limiting."""
import base64
import hashlib
import re
import secrets
import threading
import time
from collections import defaultdict, deque

from cryptography.fernet import Fernet
from django.conf import settings


PASSWORD_MIN, PASSWORD_MAX = 4, 6
_SPECIALS = r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""


def password_problems(password: str) -> list[str]:
    """Policy for every place a password is created or reset (4-6 characters, 1+ uppercase, 1+ digit, 1+ special).
    Returns one clear sentence per problem; an empty list means the password is acceptable."""
    problems = []
    n = len(password)
    if n < PASSWORD_MIN or n > PASSWORD_MAX:
        problems.append(f"Password must be {PASSWORD_MIN} to {PASSWORD_MAX} characters long (yours has {n}).")
    missing = []
    if not re.search(r"[A-Z]", password):
        missing.append("an uppercase letter (A-Z)")
    if not re.search(r"[0-9]", password):
        missing.append("a number (0-9)")
    if not any(c in _SPECIALS for c in password):
        missing.append("a special character (for example @, #, $ or !)")
    if missing:
        problems.append("Password must include at least one of each: missing " + ", ".join(missing) + ".")
    return problems


def password_error(password: str) -> str | None:
    """Single message for API responses, or None when the password is valid."""
    problems = password_problems(password)
    return " ".join(problems) if problems else None


def generate_password(length: int = PASSWORD_MAX) -> str:
    """Random password that satisfies the policy (used only by the seed_users development helper)."""
    rnd = secrets.SystemRandom()
    upper, lower, digits = "ABCDEFGHJKLMNPQRSTUVWXYZ", "abcdefghijkmnopqrstuvwxyz", "23456789"
    special = "@#$!%*?"
    chars = [rnd.choice(upper), rnd.choice(digits), rnd.choice(special)]
    chars += [rnd.choice(upper + lower + digits + special) for _ in range(length - len(chars))]
    rnd.shuffle(chars)
    return "".join(chars)


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


class RateLimiter:
    """Sliding window, in memory => per process. Use Front Door/WAF or a shared store when scaling out."""

    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window: int) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self):
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
