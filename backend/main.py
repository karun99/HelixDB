"""HelixDB FastAPI application entry point.

Wires the relational schema (see database.relational.SCHEMA), the API routers
and the built frontend into a single runnable service.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import auth, events, import_api, ocr_api, reports, research, settings, users
from .config.settings import settings as runtime_settings
from .database.relational import DB_PATH, init_db

BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"

app = FastAPI(title=runtime_settings.app_name, version=runtime_settings.version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in runtime_settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed_users()


def seed_users() -> None:
    """Create the default demo accounts on first run (mock auth mode)."""
    from .services.authentication import get_user_by_staff_id, create_user

    demo_users = [
        ("admin", "College Admin", "college", "Administrator", "Administration"),
        ("rcadmin", "Research Admin", "rc_admin", "Research Administrator", "Research Cell"),
        ("fac100", "Demo Faculty", "faculty", "Assistant Professor", "Computer Science"),
        ("stu100", "Demo Student", "student", "Student", "Computer Science"),
    ]
    for staff_id, name, role, designation, department in demo_users:
        if not get_user_by_staff_id(staff_id):
            create_user(staff_id, name, role=role, designation=designation, department=department)


for router in (auth.router, users.router, research.router, events.router,
               reports.router, import_api.router, ocr_api.router, settings.router):
    app.include_router(router)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app": runtime_settings.app_name,
        "version": runtime_settings.version,
        "db": str(DB_PATH),
    }


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        file = FRONTEND_DIST / full_path
        if full_path and file.is_file():
            return FileResponse(file)
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"detail": "Frontend not built"}, status_code=404)
else:
    @app.get("/")
    def root() -> dict[str, Any]:
        return {
            "app": runtime_settings.app_name,
            "message": "API is running. Build the frontend (frontend/) or open /docs for the API.",
            "docs": "/docs",
        }
