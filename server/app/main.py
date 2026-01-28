"""
ScrapeCrawlAI - FastAPI Application Entry Point

BFS-based web crawler and scraper with multi-worker architecture.
Supports single-URL crawling and multi-Knowledge Base crawling.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router as api_router
from .api.kb_routes import router as kb_router
from .config import config


app = FastAPI(
    title=config.APP_NAME,
    description=config.APP_DESCRIPTION,
    version=config.APP_VERSION,
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(config.cors.ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(api_router)
app.include_router(kb_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": config.APP_NAME,
        "version": config.APP_VERSION,
    }
