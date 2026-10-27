"""FastAPI edge: assembles the app, its middleware, error handlers and the ``/api`` routers."""

import hmac

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from app.config import ALLOWED_ORIGINS, CF_ORIGIN_SECRET, ORIGIN_VERIFY_EXEMPT_ORIGINS
from app.limiter import limiter
from app.regions import RegionNotConfigured
from starlette.middleware.base import BaseHTTPMiddleware
from app.routes.upload import router as upload_router
from app.routes.analyze import router as analyze_router
from app.routes.chat import router as chat_router
from app.routes.testimonials import router as testimonials_router
from app.routes.meals import router as meals_router
from app.routes.facescan import router as facescan_router

app = FastAPI()
app.state.limiter = limiter


class OriginVerifyMiddleware(BaseHTTPMiddleware):
    """Block direct ALB access — only allow requests through CloudFront.

    CloudFront adds ``X-Origin-Verify: <CF_ORIGIN_SECRET>``; the browser never knows the
    secret. ``ORIGIN_VERIFY_EXEMPT_ORIGINS`` (empty by default) is the temporary carve-out
    for the S3 demo build while CloudFront is blocked; see its comment in app.config.
    """
    async def dispatch(self, request: Request, call_next):
        # Skip check if no secret configured (local dev), for health checks, or for an
        # explicitly exempted origin.
        if (not CF_ORIGIN_SECRET or request.url.path == "/health"
                or request.headers.get("origin") in ORIGIN_VERIFY_EXEMPT_ORIGINS):
            return await call_next(request)
        supplied = request.headers.get("X-Origin-Verify", "")
        if not hmac.compare_digest(supplied.encode(), CF_ORIGIN_SECRET.encode()):
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        return await call_next(request)


app.add_middleware(OriginVerifyMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )


@app.exception_handler(RegionNotConfigured)
async def region_not_configured_handler(request: Request, exc: RegionNotConfigured):
    """A data region without a bucket or runtime is unavailable, never rerouted."""
    return JSONResponse(
        status_code=503,
        content={"detail": "This service is not available in your region yet."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


app.include_router(upload_router, prefix="/api")
app.include_router(analyze_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(testimonials_router, prefix="/api")
app.include_router(meals_router, prefix="/api")
app.include_router(facescan_router, prefix="/api")
