import logging
from datetime import datetime, timezone

from django.conf import settings

from .models import AuditLog
from .tools import TOOLS

log = logging.getLogger("portal.audit")


def client_ip(request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            parts = [p.strip() for p in xff.split(",") if p.strip()] or [""]
            hops = settings.PROXY_HOPS
            # PROXY_HOPS=N: the entry appended by the N-th trusted proxy (counted from the right) cannot be forged
            first = parts[-hops] if 0 < hops <= len(parts) else parts[0]
            if first.count(":") == 1:  # some proxies append the client port to IPv4 addresses (1.2.3.4:5678)
                first = first.split(":")[0]
            return first[:64]
    return (request.META.get("REMOTE_ADDR") or "unknown")[:64]


def audit(request, action, outcome="success", actor=None, resource_type=None, resource_id=None, detail=None, actor_name=None):
    """Records who did what. Never pass passwords, tokens or file contents in `detail`.
    Writes in autocommit mode so failures/denials persist even when the request itself fails."""
    try:
        AuditLog.objects.create(
            actor_id=actor.id if actor else None,
            actor_name=(actor.username if actor else actor_name),
            action=action, outcome=outcome, resource_type=resource_type, resource_id=resource_id,
            ip=client_ip(request) if request is not None else None,
            detail=((detail or "")[:500] or None),
        )
    except Exception:
        log.exception("failed to write audit log for %s", action)


def iso(dt: datetime | None):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def doc_out(d, include_owner: bool = False) -> dict:
    tool = TOOLS.get(d.tool)
    out = {
        "id": d.id, "document_name": d.document_name, "tool": d.tool,
        "tool_label": tool.label if tool else d.tool,
        "original_filename": d.original_filename, "output_filename": d.output_filename,
        "file_type": d.file_type, "original_size": d.original_size, "output_size": d.output_size,
        "status": d.status, "error_summary": d.error_summary, "created_at": iso(d.created_at),
        "has_original": bool(d.original_key) and not d.purged_at,
        "has_output": bool(d.output_key) and not d.purged_at,
        "deleted": d.deleted_at is not None,
    }
    if include_owner:
        o = d.owner
        out["owner"] = {"id": o.id, "username": o.username, "full_name": o.full_name}
    return out


def ensure_tool_access(request, user, slug: str):
    """Backend gate for every tool operation (open, process/upload). 403 + audit entry when the account may not use the tool."""
    from .api import ApiError
    if not user.can_use_tool(slug):
        audit(request, "tool.access", "denied", actor=user, resource_type="tool", resource_id=slug, detail=f"{user.role} has no access to {slug}")
        raise ApiError(403, "You do not have access to this tool. Please contact your administrator.")


def user_out(u) -> dict:
    locked = bool(u.locked_until and u.locked_until > datetime.now(timezone.utc))
    return {
        "id": u.id, "username": u.username, "email": u.email, "full_name": u.full_name, "name": u.full_name,
        "role": u.role, "is_active": u.is_active, "mfa_enabled": u.mfa_enabled,
        "created_at": iso(u.created_at), "last_login_at": iso(u.last_login), "locked": locked,
        "tools": sorted(u.allowed_tool_slugs()),
    }
