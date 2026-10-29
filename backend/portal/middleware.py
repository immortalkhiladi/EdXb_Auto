import logging
import threading
import time

from django.conf import settings
from django.http import JsonResponse

from .api import ApiError

log = logging.getLogger("portal")

APP_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
           "font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob:; connect-src 'self'; "
           "frame-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'self'; form-action 'self'")


class RequestLimitMiddleware:
    """Rejects oversized requests before the body is read."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cl = request.META.get("CONTENT_LENGTH")
        limit = settings.MAX_UPLOAD_MB * 1024 * 1024 * 2 + 1024 * 1024  # output + original + overhead
        if cl and cl.isdigit() and int(cl) > limit:
            return JsonResponse({"detail": "Request too large."}, status=413)
        return self.get_response(request)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "no-referrer")
        if not settings.FRAME_ANCESTORS:  # with split hosting framing is governed by CSP frame-ancestors instead
            h.setdefault("X-Frame-Options", "SAMEORIGIN")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if request.path.startswith("/api/"):
            h.setdefault("Cache-Control", "no-store")
        else:
            h.setdefault("Content-Security-Policy", APP_CSP)
        return response


class ApiErrorMiddleware:
    """Generic JSON errors for /api: no stack traces or internal paths reach the client; details go to the log."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, ApiError):
            return JsonResponse({"detail": exception.detail}, status=exception.status)
        if request.path.startswith("/api/"):
            log.exception("unhandled error on %s %s", request.method, request.path)
            return JsonResponse({"detail": "An unexpected error occurred."}, status=500)
        return None


_scheduler_started = False


class PurgeSchedulerMiddleware:
    """Starts a daily retention-purge thread once per worker process (idempotent job, safe with several workers)."""

    def __init__(self, get_response):
        global _scheduler_started
        self.get_response = get_response
        if settings.RUN_PURGE_SCHEDULER and not _scheduler_started:
            _scheduler_started = True
            threading.Thread(target=self._loop, name="retention-purge", daemon=True).start()

    @staticmethod
    def _loop():
        from django.db import connection
        from .maintenance import purge, purge_audit_logs
        time.sleep(60)
        last_full = 0.0
        while True:
            try:
                if time.time() - last_full >= 24 * 3600:  # files + sessions + audit: once a day
                    log.info("retention purge: %s", purge())
                    last_full = time.time()
                else:  # audit rows: every AUDIT_CLEANUP_INTERVAL_HOURS (default 6)
                    log.info("audit cleanup: %s rows deleted", purge_audit_logs())
            except Exception:
                log.exception("retention purge failed")
            finally:
                connection.close()
            time.sleep(max(1, settings.AUDIT_CLEANUP_INTERVAL_HOURS) * 3600)

    def __call__(self, request):
        return self.get_response(request)
