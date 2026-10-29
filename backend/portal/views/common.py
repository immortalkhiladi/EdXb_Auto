import json
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.http import FileResponse, JsonResponse


def csrf_failure(request, reason=""):
    return JsonResponse({"detail": "CSRF verification failed."}, status=403)


def health(request):
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)


LINKEDIN_FILE = Path(__file__).resolve().parent.parent / "linkedin_updates.json"


def linkedin_updates(request):
    """Public list of company updates shown on the login page. LinkedIn's API does not allow fetching company posts
    without partner approval, so the team maintains backend/portal/linkedin_updates.json by hand (title, date, text, link)."""
    data = json.loads(LINKEDIN_FILE.read_text(encoding="utf-8"))
    items = [{k: str(i.get(k, "")) for k in ("title", "date", "text", "link")} for i in data.get("items", [])]
    resp = JsonResponse({"profile": data.get("profile", ""), "items": items})
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


def api_not_found(request):
    return JsonResponse({"detail": "Not found."}, status=404)


def spa(request):
    """Single-page app fallback (client-side routes such as /documents, /admin)."""
    index = settings.FRONTEND_DIST / "index.html"
    if index.is_file():
        resp = FileResponse(open(index, "rb"), content_type="text/html; charset=utf-8")
        resp.headers["Cache-Control"] = "no-store"
        return resp
    return JsonResponse({"detail": "Frontend not built. Run `npm run build` in the project root, or use `npm run dev`."})
