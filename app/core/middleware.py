"""Cabeceras de seguridad, límite de tasa y request-id (OWASP Secure Headers). Origen: V5.

V6: fuentes autoalojadas (sin Google Fonts) y límite más estricto para el login."""
import time
import uuid
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "font-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        h = response.headers
        h["X-Request-ID"] = request_id
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "no-referrer"
        h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        h["Cross-Origin-Opener-Policy"] = "same-origin"
        h["Cross-Origin-Resource-Policy"] = "same-origin"
        # Swagger usa CDN e inline: CSP estricta solo fuera de /docs
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            h["Content-Security-Policy"] = CSP
        if request.url.path.startswith("/api/"):
            h["Cache-Control"] = "no-store"  # datos personales nunca en caché
        if get_settings().is_production:
            h["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Ventana deslizante en memoria por IP (Disponibilidad). En producción multi-instancia: Redis."""

    def __init__(self, app):
        super().__init__(app)
        self.hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            limit = get_settings().rate_limit_per_minute
            ip = request.client.host if request.client else "unknown"
            if request.url.path.endswith("/auth/token"):
                limit, ip = max(5, limit // 6), f"login:{ip}"  # fuerza bruta: ventana propia y más estricta
            now = time.monotonic()
            q = self.hits[ip]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= limit:
                return JSONResponse(
                    {"detail": "Demasiadas solicitudes"}, status_code=429, headers={"Retry-After": "60"}
                )
            q.append(now)
        return await call_next(request)
