"""Serves the four workflow UIs ONLY to authenticated users, inside a locked-down sandbox.
The HTML lives outside any public/static directory so it cannot be fetched by URL without a session."""
import gzip
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, JsonResponse

from ..api import ApiError, api_login_required, methods
from ..services import ensure_tool_access
from ..tools import TOOLS

TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
BRIDGE = (Path(__file__).resolve().parent.parent / "tool_bridge.js").read_text(encoding="utf-8")
THEME = "<style>" + (Path(__file__).resolve().parent.parent / "tool_theme.css").read_text(encoding="utf-8") + "</style>"


def tool_csp() -> str:
    fa = " ".join(["'self'", *settings.FRAME_ANCESTORS])
    # allow-same-origin: the tools use localStorage (prefs), nested preview iframes, print and blob downloads, all of
    # which fail in an opaque-origin sandbox. The pages are first-party code served only to signed-in users.
    return (
        "sandbox allow-scripts allow-same-origin allow-downloads allow-modals allow-popups allow-forms; "
        "default-src 'none'; "
        "script-src 'unsafe-inline' 'unsafe-eval' blob: https://cdnjs.cloudflare.com; "
        "style-src 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src https://fonts.gstatic.com data:; img-src data: blob:; worker-src blob:; frame-src 'self' blob: data:; "
        f"connect-src blob: data:; frame-ancestors {fa}"
    )


_PAGES: dict = {}


def _tool_page(slug: str, html_file: str):
    """(html bytes, gzipped bytes) for a tool page. Static content (no per-user data), rebuilt only when the file changes."""
    path = TOOLS_DIR / html_file
    mtime = path.stat().st_mtime
    hit = _PAGES.get(slug)
    if hit and hit[0] == mtime:
        return hit[1], hit[2]
    html = path.read_text(encoding="utf-8")
    script = "<script>" + BRIDGE.replace("__TOOL_SLUG__", slug) + "</script>"
    i = html.lower().find("<head")
    j = html.find(">", i) if i != -1 else -1
    html = (html[: j + 1] + script + html[j + 1:]) if j != -1 else script + html
    html = html.replace("<html", f'<html data-tool="{slug}"', 1)  # hook for tool_theme.css
    k = html.rfind("</body>")  # brand theme last, so its :root variables override the tool's own
    html = (html[:k] + THEME + html[k:]) if k != -1 else html + THEME
    body = html.encode("utf-8")
    _PAGES[slug] = (mtime, body, gzip.compress(body, 6))
    return body, _PAGES[slug][2]


@methods("GET")
@api_login_required
def list_tools(request):
    allowed = request.api_user.allowed_tool_slugs()
    return JsonResponse({"items": [{"slug": t.slug, "label": t.label} for t in TOOLS.values() if t.slug in allowed]})


@methods("GET")
@api_login_required
def tool_frame(request, slug):
    tool = TOOLS.get(slug)
    if tool is None:
        raise ApiError(404, "Unknown tool.")
    ensure_tool_access(request, request.api_user, slug)
    body, gz = _tool_page(slug, tool.html_file)
    gzip_ok = "gzip" in request.META.get("HTTP_ACCEPT_ENCODING", "")
    resp = HttpResponse(gz if gzip_ok else body, content_type="text/html; charset=utf-8")
    if gzip_ok:
        resp.headers["Content-Encoding"] = "gzip"
    resp.headers["Vary"] = "Accept-Encoding"
    resp.headers["Content-Security-Policy"] = tool_csp()
    resp.headers["Cache-Control"] = "private, no-store"
    return resp
