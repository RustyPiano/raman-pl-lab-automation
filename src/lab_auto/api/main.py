"""FastAPI main application entry point."""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from lab_auto.api.models import HealthResponse
from lab_auto.api.routers import configs, devices, workflow
from lab_auto.api.task_queue import task_queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting FastAPI application")
    task_queue.start()
    logger.info("Task queue worker started")

    yield

    # Shutdown
    logger.info("Shutting down FastAPI application")
    await task_queue.stop()
    logger.info("Task queue worker stopped")


# Create FastAPI app
app = FastAPI(
    title="Raman/PL Lab Automation API",
    description="REST API and WebSocket interface for autonomous Raman/PL measurement platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration for Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite default
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(devices.router)
app.include_router(configs.router)
app.include_router(workflow.router)

# Static file serving (for production frontend)
dist_path = Path(__file__).parent.parent.parent.parent / "dist"
if dist_path.exists():
    app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="static")
    logger.info(f"Mounted static files from {dist_path}")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/health", response_model=HealthResponse)
async def api_health_check():
    """API health check endpoint."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "lab_auto.api.main:app",
        host="127.0.0.1",
        port=8008,
        reload=True,
        log_level="info",
    )
