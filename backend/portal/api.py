"""Small helpers shared by the JSON API views."""
import json
import re
import time
from functools import wraps

from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse


SESSION_TOUCH_SECONDS = 60
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def error(detail: str, status: int) -> JsonResponse:
    return JsonResponse({"detail": detail}, status=status)


def read_json(request) -> dict:
    try:
        data = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        raise ApiError(422, "Invalid request.")
    if not isinstance(data, dict):
        raise ApiError(422, "Invalid request.")
    return data


def methods(*allowed):
    def deco(view):
        @wraps(view)
        def wrapper(request, *a, **kw):
            if request.method not in allowed:
                return error("Method not allowed.", 405)
            return view(request, *a, **kw)
        return wrapper
    return deco


def current_user(request):
    """The signed-in user, or None. Enforces revocation (session_epoch) and the absolute session lifetime."""
    user = request.user
    if not user.is_authenticated:
        return None
    s = request.session
    if s.get("epoch") != user.session_epoch or time.time() - s.get("login_ts", 0) > settings.SESSION_ABSOLUTE_HOURS * 3600:
        logout(request)
        return None
    now = int(time.time())
    if now - s.get("touched", 0) >= SESSION_TOUCH_SECONDS:  # slides the idle timeout at most once a minute
        s["touched"] = now
    return user


def api_login_required(view):
    @wraps(view)
    def wrapper(request, *a, **kw):
        user = current_user(request)
        if user is None:
            return error("Not authenticated.", 401)
        request.api_user = user
        return view(request, *a, **kw)
    return wrapper


def all_documents_required(view):
    """ADMIN or MD (read access to every user's documents)."""
    @wraps(view)
    @api_login_required
    def wrapper(request, *a, **kw):
        if not request.api_user.can_view_all_documents:
            return error("Administrator or MD access required.", 403)
        return view(request, *a, **kw)
    return wrapper


def admin_required(view):
    @wraps(view)
    @api_login_required
    def wrapper(request, *a, **kw):
        if not request.api_user.is_admin:
            return error("Administrator access required.", 403)
        return view(request, *a, **kw)
    return wrapper
