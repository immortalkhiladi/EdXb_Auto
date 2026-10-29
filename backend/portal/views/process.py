"""POST /api/process/<tool-slug>: records a tool run for the signed-in user.
The generated output (and, when known, the source file) are validated by CONTENT, stored privately and attached to
the caller's account. The owner is ALWAYS the authenticated user, never a client-supplied value."""
from django.conf import settings
from django.http import JsonResponse

from ..api import api_login_required, error, methods
from ..models import Document
from ..security import limiter
from ..services import audit, doc_out, ensure_tool_access
from ..storage import get_storage, new_key
from ..tools import TOOLS
from ..validation import ValidationError, check_upload, safe_filename


def make_view(slug: str):
    tool = TOOLS[slug]

    @methods("POST")
    @api_login_required
    def view(request):
        user = request.api_user
        ensure_tool_access(request, user, slug)  # 403 before anything is read or stored
        if not limiter.hit(f"upload:{user.id}", settings.UPLOAD_RATE_LIMIT, 60):
            return error("Too many uploads. Please slow down.", 429)
        output, original = request.FILES.get("output"), request.FILES.get("original")
        if output is None:
            return error("Invalid request.", 422)

        out_name = safe_filename(output.name)
        doc_name = request.POST.get("document_name")
        has_original = original is not None and bool(original.name)
        fields = dict(
            owner=user, tool=slug,
            document_name=(safe_filename(doc_name) if doc_name else out_name)[:200],
            output_filename=out_name,
            original_filename=safe_filename(original.name) if has_original else None,
        )
        stored = []
        try:
            # validate both files in place (no whole-file reads/copies), then stream each one to storage once
            out_chk = check_upload(output, out_name, set(tool.output_exts))
            orig_chk = check_upload(original, original.name, set(tool.input_exts)) if has_original else None

            storage = get_storage()
            fields["output_key"] = new_key("outputs")
            stored.append(fields["output_key"])
            written = storage.put_file(fields["output_key"], output)
            if written != out_chk.size:
                raise IOError("stored size mismatch")
            fields.update(output_filename=out_chk.filename, file_type=out_chk.ext.lstrip("."), output_size=written)
            if orig_chk:
                fields["original_key"] = new_key("originals")
                stored.append(fields["original_key"])
                written = storage.put_file(fields["original_key"], original)
                if written != orig_chk.size:
                    raise IOError("stored size mismatch")
                fields.update(original_filename=orig_chk.filename, original_size=written)
            # files are safely stored: ONE insert records the finished document (was insert + update)
            doc = Document.objects.create(status="completed", **fields)
        except ValidationError as e:
            for k in stored:
                get_storage().delete(k)
            doc = Document.objects.create(status="failed", error_summary=str(e)[:300], **{k: v for k, v in fields.items() if k not in ("output_key", "original_key")})
            audit(request, "document.process", "failure", actor=user, resource_type="document", resource_id=doc.id, detail=f"{slug}: {e}")
            return error(str(e), 422)
        except Exception:
            for k in stored:
                get_storage().delete(k)
            doc = Document.objects.create(status="failed", error_summary="Internal error while storing the file.", **{k: v for k, v in fields.items() if k not in ("output_key", "original_key")})
            audit(request, "document.process", "failure", actor=user, resource_type="document", resource_id=doc.id, detail=f"{slug}: internal error")
            return error("The file could not be processed.", 500)

        audit(request, "document.process", "success", actor=user, resource_type="document", resource_id=doc.id, detail=f"{slug}: {doc.output_filename}")
        return JsonResponse({"document": doc_out(doc)})

    view.__name__ = "process_" + slug.replace("-", "_")
    return view
