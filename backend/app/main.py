from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from app.config import ALLOWED_ORIGINS, CF_ORIGIN_SECRET
from app.limiter import limiter
from starlette.middleware.base import BaseHTTPMiddleware
from app.routes.upload import router as upload_router
from app.routes.analyze import router as analyze_router
from app.routes.chat import router as chat_router
from app.routes.testimonials import router as testimonials_router
from app.routes.meals import router as meals_router
from app.routes.facescan import router as facescan_router

app = FastAPI()
app.state.limiter = limiter


# Narrow, explicit carve-out: a public S3-hosted demo build of the maitribot UI needs to
# reach this backend directly while CloudFront is account-wide blocked (see
# documents/MIGRATION_OUTSTANDING_TASKS.md). The demo build cannot embed CF_ORIGIN_SECRET
# -- that secret would be extractable from public JS, defeating its purpose -- so instead
# this one Origin is explicitly allowed to skip the check. Remove once CloudFront is
# restored and the real domain-based access path is back.
DEMO_ORIGIN_EXEMPT = "http://maitribot-demo-ui.s3-website.ap-south-1.amazonaws.com"


class OriginVerifyMiddleware(BaseHTTPMiddleware):
    """Block direct ALB access — only allow requests through CloudFront (plus the
    explicit DEMO_ORIGIN_EXEMPT carve-out above)."""
    async def dispatch(self, request: Request, call_next):
        # Skip check if no secret configured (local dev), for health checks, or for the
        # public demo origin (see DEMO_ORIGIN_EXEMPT comment).
        if (not CF_ORIGIN_SECRET or request.url.path == "/health"
                or request.headers.get("origin") == DEMO_ORIGIN_EXEMPT):
            return await call_next(request)
        if request.headers.get("X-Origin-Verify") != CF_ORIGIN_SECRET:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        return await call_next(request)


app.add_middleware(OriginVerifyMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
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
