"""
Application entrypoint. Wires together routers, middleware, and
startup behavior for the Financial Workflow Automation Platform.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, users, requests, approvals, audit, notifications

settings = get_settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workflow")

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Enterprise workflow management system that automates financial "
        "approval processes with multi-level approvals, RBAC, audit logging, "
        "and notifications."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(requests.router)
app.include_router(approvals.router)
app.include_router(audit.router)
app.include_router(notifications.router)


@app.on_event("startup")
def on_startup():
    # In production, use Alembic migrations instead of create_all.
    # This is kept for quick local/dev bootstrapping.
    if settings.ENV == "development":
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables ensured (development mode).")


@app.get("/", tags=["Health"])
def root():
    return {"service": settings.APP_NAME, "status": "ok"}


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}
