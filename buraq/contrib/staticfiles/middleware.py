from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from buraq.conf import settings


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Add cache headers to static file responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.url.path.startswith(settings.STATIC_URL):
            if settings.DEBUG:
                response.headers["Cache-Control"] = "no-cache"
            else:
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
