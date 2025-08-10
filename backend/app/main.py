"""FastAPI main application module."""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import config
from .errors import (
    APIError,
    api_error_handler,
    general_exception_handler,
    http_exception_handler,
)
from .logging_config import setup_logging

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Financial Planning API",
    description="Local-first investment planner and portfolio analytics",
    version="0.1.0",
)

# Add exception handlers
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("Financial Planning API starting up")
    logger.info(f"Configuration loaded - DB: {config.database.path}")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Financial Planning API shutting down")


@app.get("/")
async def root() -> dict[str, str]:
    """Health check endpoint."""
    return {"message": "Financial Planning API is running"}


@app.get("/api/health")
async def health() -> dict[str, str]:
    """API health check endpoint."""
    return {"status": "healthy"}
