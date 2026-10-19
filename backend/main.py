"""
FastAPI application entry point.

Phase 1: Auth + Users (admin) + Upload + Health check
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.startup_checks import run_startup_checks
from app.db.session import SessionLocal
from app.api.routes import (
    agents,
    auth,
    chat,
    detections,
    health,
    models,
    reports,
    static_files,
    upload,
    users,
    yolo_models,
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    print(f"[YOLO API] env={settings.APP_ENV}")
    if not settings.is_production:
        print(f"[YOLO API] docs → http://localhost:{settings.APP_PORT}/docs")
    # Raises in production while a problem remains; warns otherwise.
    for problem in run_startup_checks(settings, SessionLocal):
        print(f"[YOLO API] WARNING: {problem} — fix this before any real deployment.")
    yield


# Interactive API docs expose every route and schema; keep them off in production.
_docs_enabled = not settings.is_production
app = FastAPI(
    title="YOLO System API",
    description="Backend API for YOLO detection system — desktop + web dual-track architecture",
    version="0.1.0",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (avatars, detection results, etc.)
os.makedirs("static/avatars", exist_ok=True)
os.makedirs("static/results", exist_ok=True)
os.makedirs("static/detections/originals", exist_ok=True)
os.makedirs("static/detections/results", exist_ok=True)
os.makedirs("static/detections/videos/originals", exist_ok=True)
os.makedirs("static/detections/videos/results", exist_ok=True)
os.makedirs("static/detections/previews", exist_ok=True)

# Routers
app.include_router(static_files.router)
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(detections.router, prefix="/api/detections", tags=["Detections"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(agents.router, prefix="/api/agent", tags=["Agent"])
app.include_router(models.router, prefix="/api/models", tags=["Models"])
app.include_router(yolo_models.router, prefix="/api/yolo-models", tags=["YOLO Models"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])

