
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.logger import get_logger
from app.core.config import settings
from app.database.connection import engine
from app.database.base import Base
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limit import limiter

app = FastAPI(title=settings.PROJECT_NAME)
logger = get_logger("main")

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

# Read allowed frontend origins from Render environment variables.
allowed_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "FRONTEND_URL",
        "https://data-pilot-kappa.vercel.app",
    ).split(",")
    if origin.strip()
]

# Include known production and preview origins.
for origin in [
    "https://data-pilot-kappa.vercel.app",
]:
    if origin not in allowed_origins:
        allowed_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://data-pilot-kappa.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception,
):
    logger.error(
        f"Unhandled error on {request.url.path}: {str(exc)}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

@app.get("/")
def root():
    return {"message": "DataPilot AI backend is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Keep your existing router imports and registrations below.
from app.api import (
    auth, workspace, upload, etl, relationship,
    knowledge_base, query, dashboard, reports,
    settings as settings_router, ai, ml,
)

app.include_router(auth.router)
app.include_router(workspace.router)
app.include_router(upload.router)
app.include_router(etl.router)
app.include_router(relationship.router)
app.include_router(knowledge_base.router)
app.include_router(query.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(settings_router.router)
app.include_router(ai.router)
app.include_router(ml.router)
