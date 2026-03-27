import time

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, OperationalError
from django.http import JsonResponse


class SimpleRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _request_limit(request):
        if request.path == "/api/chat/":
            return 20
        if request.path == "/support/":
            return 10
        return 60

    def __call__(self, request):
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return self.get_response(request)

        if request.method == "POST" and not request.path.startswith("/admin/"):
            ip_address = request.META.get("REMOTE_ADDR", "anonymous")
            limit = self._request_limit(request)
            window_seconds = getattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
            bucket = int(time.time() // window_seconds)
            key = f"rate-limit:{ip_address}:{request.path}:{bucket}"

            current_count = 1
            if cache.add(key, 1, timeout=window_seconds + 5):
                current_count = 1
            else:
                try:
                    current_count = int(cache.incr(key))
                except Exception:
                    # Fallback for non-atomic cache backends.
                    current_count = int(cache.get(key, 1)) + 1
                    cache.set(key, current_count, timeout=window_seconds + 5)

            if current_count > limit:
                retry_after = max(1, window_seconds - int(time.time() % window_seconds))
                response = JsonResponse(
                    {
                        "error": "rate_limited",
                        "message": "Too many requests. Please slow down and try again shortly.",
                    },
                    status=429,
                )
                response["Retry-After"] = str(retry_after)
                return response

        return self.get_response(request)


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.path.startswith("/static/") or request.path.startswith("/favicon"):
            return response
        if request.path.startswith("/healthz"):
            return response

        log_read_requests = getattr(settings, "AUDIT_LOG_READ_REQUESTS", False)
        if not log_read_requests and request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return response

        actor = ""
        if hasattr(request, "user") and request.user.is_authenticated:
            actor = request.user.get_username()

        try:
            from .models import AuditLog

            AuditLog.objects.create(
                event_type="request",
                path=request.path,
                method=request.method,
                status_code=response.status_code,
                actor=actor,
                ip_address=request.META.get("REMOTE_ADDR"),
                details={
                    "query_params": dict(request.GET),
                    "user_agent": request.META.get("HTTP_USER_AGENT", "")[:240],
                },
            )
        except (DatabaseError, OperationalError):
            pass

        return response
