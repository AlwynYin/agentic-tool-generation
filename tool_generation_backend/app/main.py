"""
FastAPI application entry point for agent-browser backend.
Chemistry computation tool generation platform.
"""

from contextlib import asynccontextmanager
import logging
import subprocess
from typing import Dict, Any
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_database
from app.api.health import router as health_router
from app.api.tasks import router as tasks_router
from app.api.jobs import router as jobs_router
from app.api.repositories import router as repositories_router
from app.api.extract import router as extract_router
from app.websocket.manager import WebSocketManager
from app.middleware.logging import setup_logging_middleware
from app.utils.llm_backend import authenticate_llm
from app.dependencies import get_repository_service, set_websocket_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    # Startup
    settings = get_settings()
    logging.debug("In debug mode")
    logging.info("🚀 Starting agent-browser backend...")
    logging.info(f"📊 Environment: {settings.environment}")
    logging.info(f"🌐 Port: {settings.port}")

    # Initialize database connection
    await init_database(settings.mongodb_url, settings.mongodb_db_name)
    logging.info("✅ Database connection established")

    # Authenticate LLM backend
    logging.info(f"🤖 LLM Backend: {settings.llm_backend.upper()}")
    llm_auth_success = authenticate_llm()
    if not llm_auth_success:
        logging.warning(f"⚠️ {settings.llm_backend.upper()} authentication failed - tool generation may not work")
    else:
        logging.info(f"✅ {settings.llm_backend.upper()} authenticated successfully")

    # Initialize WebSocket manager
    websocket_manager = WebSocketManager()
    app.state.websocket_manager = websocket_manager
    set_websocket_manager(websocket_manager)  # Make available for dependency injection
    logging.info("🔌 WebSocket manager initialized")

    # Check repository status and warn about missing navigation guides (singleton)
    repo_service = get_repository_service()
    repo_service.load_package_config()
    missing_guides = repo_service.check_missing_guides()

    if missing_guides:
        logging.warning(f"⚠️  {len(missing_guides)} packages missing navigation guides: {', '.join(missing_guides)}")
        logging.info(f"💡 Use POST /api/v1/repositories/register-all to register missing packages")
    else:
        logging.info("✅ All configured packages have navigation guides")

    # Log overall repository status
    status = repo_service.get_repository_status()
    repos_downloaded = sum(1 for s in status if s.repo_exists)
    guides_present = sum(1 for s in status if s.has_navigation_guide)
    logging.info(f"📦 Repository status: {repos_downloaded}/{len(status)} repos downloaded, {guides_present}/{len(status)} guides present")
    yield

    # Shutdown
    logging.info("🛑 Shutting down agent-browser backend...")
    if hasattr(app.state, 'simpletooling'):
        await app.state.simpletooling.close()
        logging.info("🔧 SimpleTooling client closed")


# Create FastAPI application
app = FastAPI(
    title="Agent Browser Backend",
    description="Chemistry computation tool generation platform",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Setup CORS middleware
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup logging middleware
setup_logging_middleware(app, settings)

# Include API routers
app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(tasks_router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(jobs_router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(repositories_router, prefix="/api/v1/repositories", tags=["repositories"])
app.include_router(extract_router, prefix="/api/v1", tags=["extract"])


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time session updates."""
    websocket_manager = app.state.websocket_manager
    await websocket_manager.connect(websocket, session_id)


# Serve frontend static files (must be after API routes)
# Check if frontend build directory exists
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    logging.info(f"📦 Serving frontend from {frontend_dist}")

    # Mount static files for assets (js, css, etc)
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    # Catch-all route for SPA - must be last
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve frontend for all non-API routes (SPA routing)."""
        from fastapi.responses import FileResponse

        # Check if file exists in dist
        file_path = frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        # Otherwise serve index.html (SPA routing)
        return FileResponse(frontend_dist / "index.html")
else:
    logging.warning("⚠️  Frontend build directory not found - API only mode")

    @app.get("/")
    async def root() -> Dict[str, Any]:
        """Root endpoint with basic service information."""
        return {
            "service": "agent-browser-backend",
            "version": "2.0.0",
            "status": "running",
            "docs": "/docs",
            "websocket": "/ws/{session_id}",
        }


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower()
    )