"""FastAPI application — Web UI management panel.

Routes:
- /              → Vue SPA (frontend/index.html)
- /frontend/*    → Static frontend files
- /api/*         → REST API endpoints
- /site/*        → Generated static site (legacy)
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from openlearning.web.api import api_router

# Frontend directory
FRONTEND_DIR = Path(__file__).parent / "frontend"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="OpenLearning Web UI",
        description="AI 驱动的个人学习信息系统 — 管理面板",
        version="0.1.0",
    )

    # Mount API router
    app.include_router(api_router, prefix="/api")

    # Serve frontend static files
    if FRONTEND_DIR.exists():
        app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

    # Serve generated site (legacy)
    output_dir = Path("output")
    if output_dir.exists():
        app.mount("/site", StaticFiles(directory=str(output_dir), html=True), name="site")

    # SPA index.html
    index_path = FRONTEND_DIR / "index.html"

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the Vue SPA entry point."""
        if index_path.exists():
            return HTMLResponse(index_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok", "version": "0.1.0"}

    # SPA fallback: all non-API, non-frontend routes → index.html
    # This enables Vue Router's history mode
    @app.middleware("http")
    async def spa_fallback(request: Request, call_next):
        response = await call_next(request)
        # Only fallback for GET requests that return 404
        if (
            response.status_code == 404
            and request.method == "GET"
            and not request.url.path.startswith("/api")
            and not request.url.path.startswith("/frontend")
            and not request.url.path.startswith("/site")
            and index_path.exists()
        ):
            return HTMLResponse(index_path.read_text(encoding="utf-8"))
        return response

    return app
