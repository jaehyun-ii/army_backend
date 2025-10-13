"""
FastAPI main application.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.core.config import settings
from app.api.v1.router import api_router
from app.core.logging import setup_logging, get_logger
from app.core.cache import cache_manager

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="""## 🚀 Adversarial Vision Platform API

    A comprehensive platform for adversarial AI research and testing.

    ### Features
    - 📊 **Dataset Management**: Upload and manage 2D/3D datasets
    - 🤖 **Model Repository**: Store and version AI models
    - ⚔️ **Adversarial Attacks**: Generate patches and noise attacks
    - 📈 **Evaluation**: Benchmark model robustness
    - 🔄 **Real-time Processing**: Stream processing capabilities
    - 🔌 **Plugin System**: Extensible attack methods

    ### Authentication
    Most endpoints require Bearer token authentication.
    """,
    version="1.0.0",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
    openapi_tags=[
        {"name": "2D Datasets", "description": "Manage 2D image datasets"},
        {"name": "3D Datasets", "description": "Manage 3D datasets"},
        {"name": "Models", "description": "Model repository operations"},
        {"name": "Adversarial Attacks", "description": "Generate adversarial examples"},
        {"name": "Evaluation", "description": "Model evaluation and benchmarking"},
        {"name": "Real-time", "description": "Real-time capture and processing"},
        {"name": "System", "description": "System metrics and health"},
    ]
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint.

    Returns:
        Health status including app name, version, and environment.
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


@app.on_event("startup")
async def startup_event():
    """Application startup tasks."""
    logger.info(f"Starting {settings.APP_NAME}...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"API docs available at: http://localhost:8000{settings.API_PREFIX}/docs")

    # Initialize cache
    await cache_manager.initialize()
    logger.info(f"Cache initialized: {settings.CACHE_TYPE}")

    # Load attack plugins
    from app.plugins import attack_plugin_registry
    plugin_count = attack_plugin_registry.discover_plugins()
    logger.info(f"Loaded {plugin_count} attack plugin(s)")

    # List loaded plugins
    plugins = attack_plugin_registry.list_plugins()
    if plugins:
        logger.info("Available attack plugins:")
        for plugin in plugins:
            logger.info(f"  - {plugin['name']} v{plugin['version']} ({plugin['category']})")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks."""
    logger.info(f"Shutting down {settings.APP_NAME}...")

    # Close cache connection
    await cache_manager.close()
    logger.info("Cache connection closed")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
