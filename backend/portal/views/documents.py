import threading
import zipfile
from datetime import datetime, timedelta, timezone as dt_tz
from urllib.parse import quote

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.utils import timezone

from ..api import ApiError, api_login_required, error, methods
from ..models import Document
from ..services import audit, doc_out
from ..preview import decode_text, zip_preview
from ..storage import get_storage
from ..tools import TOOLS
from ..validation import MEDIA


_preview_slots = None


def _preview_slot() -> threading.BoundedSemaphore:
    """Previews of ZIP packages and text files are built in memory (up to tens of MB each). Capping how many run at once
    per worker keeps a burst of previews from exhausting the instance's RAM (512 MB on Render starter)."""
    global _preview_slots
    if _preview_slots is None:
        _preview_slots = threading.BoundedSemaphore(max(1, settings.PREVIEW_CONCURRENCY))
    return _preview_slots


def parse_date(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=dt_tz.utc)
    except ValueError:
        raise ApiError(422, "Dates must be YYYY-MM-DD.")


def page_params(request, default_size=10, max_size=100):
    try:
        page = int(request.GET.get("page", 1))
        size = int(request.GET.get("page_size", default_size))
    except ValueError:
        raise ApiError(422, "Invalid request.")
    if page < 1 or page > 100000 or size < 1 or size > max_size:
        raise ApiError(422, "Invalid request.")
    return page, size


def apply_filters(qs, g):
    q = (g.get("q") or "").strip()[:100]
    if q:  # icontains escapes LIKE wildcards; the ORM parameterises the query
        qs = qs.filter(Q(document_name__icontains=q) | Q(original_filename__icontains=q) | Q(output_filename__icontains=q))
    if g.get("tool"):
        qs = qs.filter(tool=g["tool"])
    if g.get("status"):
        qs = qs.filter(status=g["status"])
    if g.get("date_from"):
        qs = qs.filter(created_at__gte=parse_date(g["date_from"]))
    if g.get("date_to"):
        qs = qs.filter(created_at__lt=parse_date(g["date_to"]) + timedelta(days=1))
    return qs


def paginate(request, qs, include_owner=False):
    allowed = request.api_user.allowed_tool_slugs()
    page, size = page_params(request)
    total = qs.count()
    rows = qs.order_by("-created_at", "id")[(page - 1) * size: page * size]
    return {"items": [doc_out(d, include_owner=include_owner) for d in rows], "total": total, "page": page, "page_size": size,
            "tools": {k: t.label for k, t in TOOLS.items() if k in allowed}}


def get_accessible(user, doc_id: str) -> Document:
    """THE ownership check used by every get/view/download/delete. Non-owners get an identical 404 (no existence leak);
    only ADMIN and MD may open other users' documents (deleting them is ADMIN-only, see document_detail)."""
    doc = Document.objects.select_related("owner").filter(id=doc_id, deleted_at__isnull=True).first()
    if doc is None or (doc.owner_id != user.id and not user.can_view_all_documents):
        raise ApiError(404, "Document not found.")
    if not user.can_view_all_documents and doc.tool not in user.allowed_tool_slugs():  # tool access was revoked: its documents are locked too
        raise ApiError(403, "You do not have access to this tool. Please contact your administrator.")
    return doc


@methods("GET")
@api_login_required
def list_documents(request):
    user = request.api_user
    # the owner filter comes from the session identity, never from request parameters
    qs = Document.objects.filter(owner=user, deleted_at__isnull=True)
    if not user.can_view_all_documents:  # only documents of tools this user may use
        qs = qs.filter(tool__in=user.allowed_tool_slugs())
    qs = apply_filters(qs, request.GET)
    return JsonResponse(paginate(request, qs))


@methods("GET", "DELETE")
@api_login_required
def document_detail(request, document_id):
    user = request.api_user
    doc = get_accessible(user, document_id)
    if request.method == "GET":
        return JsonResponse({"document": doc_out(doc, include_owner=user.can_view_all_documents)})
    if doc.owner_id != user.id and not user.is_admin:  # MD can view everything but only ADMIN may delete someone else's file
        audit(request, "document.delete", "denied", actor=user, resource_type="document", resource_id=doc.id, detail="MD tried to delete another user's document")
        return error("Only administrators can delete other users' documents.", 403)
    purge = request.GET.get("purge") in ("1", "true") and user.is_admin
    doc.deleted_at = timezone.now()  # soft delete; files are removed by the retention job
    if purge:
        storage = get_storage()
        for k in (doc.output_key, doc.original_key):
            if k:
                storage.delete(k)
        doc.purged_at = timezone.now()
    doc.save()
    audit(request, "document.delete", "success", actor=user, resource_type="document", resource_id=doc.id,
          detail=("purged" if purge else "soft delete") + (" (admin, other user's)" if doc.owner_id != user.id else ""))
    return JsonResponse({"status": "deleted"})


def _disposition(kind: str, filename: str) -> str:
    ascii_name = filename.encode("ascii", "ignore").decode().replace('"', "") or "download"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _serve(request, document_id, disposition):
    user = request.api_user
    kind = request.GET.get("kind", "output")
    if kind not in ("output", "original"):
        return error("Invalid request.", 422)
    doc = get_accessible(user, document_id)
    key, name = (doc.original_key, doc.original_filename) if kind == "original" else (doc.output_key, doc.output_filename)
    if not key or doc.purged_at:
        return error("File not available.", 404)
    ext = "." + name.rsplit(".", 1)[-1].lower() if name and "." in name else ""
    media, previewable = MEDIA.get(ext, ("application/octet-stream", False))
    if disposition == "inline" and not previewable:
        return error("This file type cannot be previewed. Please download it instead.", 415)
    storage = get_storage()
    if not storage.exists(key):
        return error("File not available.", 404)

    audit(request, "document.view" if disposition == "inline" else "document.download", "success", actor=user,
          resource_type="document", resource_id=doc.id,
          detail=(f"{user.role} access to document of another user ({kind})" if doc.owner_id != user.id else kind))

    size = doc.original_size if kind == "original" else doc.output_size
    body = None
    in_memory = disposition == "inline" and (ext == ".zip" or media.startswith("text/"))
    if in_memory and not _preview_slot().acquire(timeout=30):
        return error("The server is busy. Please try the preview again in a moment.", 503)
    try:
        if disposition == "inline" and ext == ".zip":  # package output: show the HTML inside with its images (stored file untouched)
            try:
                with storage.open(key) as fh:  # zipfile reads only the entries it needs, not the whole archive
                    body = zip_preview(fh)
            except zipfile.BadZipFile:
                body = None
            if body is None:
                return error("This package has no page that can be previewed. Please download it instead.", 415)
            media, size = "text/html; charset=utf-8", len(body)
        elif disposition == "inline" and media.startswith("text/"):  # label the real encoding so the text shows exactly as stored
            raw = b"".join(storage.stream(key))
            media, size = f"{media}; charset={decode_text(raw)[1]}", len(raw)
            body = raw
    finally:
        if in_memory:
            _preview_slot().release()

    resp = HttpResponse(body, content_type=media) if body is not None else StreamingHttpResponse(storage.stream(key), content_type=media)
    resp.headers["Content-Disposition"] = _disposition(disposition, name or "download")
    resp.headers["Cache-Control"] = "private, no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    fa = " ".join(["'self'", *settings.FRAME_ANCESTORS])
    # Previewed content can never run scripts or load anything else, even if the file is hostile HTML.
    # (PDFs are not sandboxed because browsers refuse to render their viewer inside a sandbox.)
    resp.headers["Content-Security-Policy"] = (
        f"frame-ancestors {fa}" if media.startswith("application/pdf")
        else f"sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors {fa}")
    if size and body is None:
        resp.headers["Content-Length"] = str(size)
    return resp


@methods("GET")
@api_login_required
def view_document(request, document_id):
    return _serve(request, document_id, "inline")


@methods("GET")
@api_login_required
def download_document(request, document_id):
    return _serve(request, document_id, "attachment")
