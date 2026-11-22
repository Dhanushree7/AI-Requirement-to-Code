import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

# Ensure project root and backend dir are in sys.path regardless of execution directory
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.core.database import Base, engine
from backend.app.routers import (
    projects, upload, requirements, artifacts, codegen, graph, rag, llm_health, provider_settings, auth
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("req-to-code")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully.")
    yield
    logger.info("Application shutting down...")

app = FastAPI(
    title=f"{settings.APP_NAME} - {settings.APP_SUBTITLE}",
    description="An Intelligent Framework for Automated Software Requirement Analysis and Code Generation using LLMs",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Mount API routers
app.include_router(projects.router, prefix=settings.API_V1_STR)
app.include_router(upload.router, prefix=settings.API_V1_STR)
app.include_router(requirements.router, prefix=settings.API_V1_STR)
app.include_router(artifacts.router, prefix=settings.API_V1_STR)
app.include_router(codegen.router, prefix=settings.API_V1_STR)
app.include_router(graph.router, prefix=settings.API_V1_STR)
app.include_router(rag.router, prefix=settings.API_V1_STR)
app.include_router(llm_health.router, prefix=settings.API_V1_STR)
app.include_router(provider_settings.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(auth.router)
app.include_router(auth.direct_auth_router, prefix=settings.API_V1_STR)
app.include_router(auth.direct_auth_router)

@app.get("/health", tags=["system"])
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "subtitle": settings.APP_SUBTITLE,
        "llm_provider": settings.LLM_PROVIDER,
        "environment": settings.ENVIRONMENT
    }

@app.get("/", tags=["system"])
def root():
    return {
        "message": "Welcome to Req-to-Code API: Intelligent Software Requirement Analysis and Code Generation",
        "docs": "/docs",
        "health": "/health"
    }
