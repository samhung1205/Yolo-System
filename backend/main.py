"""
FastAPI application entry point.

Phase 1: Auth + Users (admin) + Upload + Health check
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import agents, auth, chat, detections, health, models, static_files, users, upload

app = FastAPI(
    title="YOLO System API",
    description="Backend API for YOLO detection system — desktop + web dual-track architecture",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

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


@app.on_event("startup")
async def startup_event():
    print(f"[YOLO API] env={settings.APP_ENV}")
    print(f"[YOLO API] docs → http://localhost:{settings.APP_PORT}/docs")
    if settings.SECRET_KEY == "change-me-in-production":
        message = (
            "[YOLO API] WARNING: SECRET_KEY is still the built-in default. "
            "JWT tokens are forgeable — set SECRET_KEY in backend/.env before any real deployment."
        )
        if settings.APP_ENV.lower() in ("production", "prod"):
            raise RuntimeError(message)
        print(message)
