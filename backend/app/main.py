
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.logger import get_logger
from app.core.config import settings
from app.core.rate_limit import limiter

from app.database.connection import engine
from app.database.base import Base

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app = FastAPI(title=settings.PROJECT_NAME)
logger = get_logger("main")

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

# CORS configuration
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    os.getenv("FRONTEND_URL", ""),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin for origin in allowed_origins if origin
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception,
):
    logger.error(
        f"Unhandled error on {request.url.path}: {str(exc)}",
        exc_info=True,
    )

    origin = request.headers.get("origin", "")
    headers = {}

    if origin in allowed_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"

    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers=headers,
    )


# Health endpoints
@app.get("/")
def root():
    return {"message": "DataPilot AI backend is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Import routers
from app.api import (  # noqa: E402
    auth,
    workspace,
    upload,
    etl,
    relationship,
    knowledge_base,
    query,
    dashboard,
    reports,
    settings as settings_router,
    ai,
    ml,
)

# Register routers
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


# Register models before initializing the missing table
from app.models.user import User  # noqa: E402
from app.models.workspace import Workspace  # noqa: E402
from app.models.query_history import QueryHistory  # noqa: E402


@app.on_event("startup")
def initialize_query_history_table():
    """Create query_history if it does not exist."""
    try:
        QueryHistory.__table__.create(
            bind=engine,
            checkfirst=True,
        )
        logger.info("query_history table verified.")
    except Exception:
        logger.exception(
            "Failed to initialize query_history table."
        )
        raise
