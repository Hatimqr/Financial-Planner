"""
Main FastAPI application for the financial planning system.

This module initializes the FastAPI app with logging, error handling,
and basic middleware.
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import load_config
from app.errors import register_exception_handlers
from app.logging import setup_logging, get_logger, log_request


# Load configuration
config = load_config()

# Initialize logging with configuration
setup_logging(
    level=config.logging.level,
    log_file="app.log",
    log_dir="data/logs",
    enable_console=True,
    structured_console=False,
)

logger = get_logger("financial_planning.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("Financial Planning API starting up")
    
    # Initialize database tables
    try:
        # Import models to register them with SQLAlchemy
        from app import models
        from app.db import create_tables
        create_tables()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    yield
    
    # Shutdown
    logger.info("Financial Planning API shutting down")


# Create FastAPI application
app = FastAPI(
    title="Financial Planning API",
    description="Local-first investment planner and portfolio analytics",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:5174",  # Vite dev server (alternate port)
        "http://127.0.0.1:5174",
        "http://localhost:5175",  # Test server for browser-based tests
        "http://127.0.0.1:5175",
        "null"  # Allow direct file access for testing (browser origin is 'null')
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Middleware to log HTTP requests with timing and request IDs."""
    # Generate request ID for tracing
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Start timing
    start_time = time.time()
    
    # Process request
    response: Response = await call_next(request)
    
    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000
    
    # Log the request
    log_request(
        logger,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        request_id=request_id,
        query_params=str(request.query_params) if request.query_params else None,
        user_agent=request.headers.get("user-agent"),
    )
    
    # Add request ID to response headers for debugging
    response.headers["X-Request-ID"] = request_id
    
    return response


# Register exception handlers
register_exception_handlers(app)


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {
        "ok": True,
        "service": "Financial Planning API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "ok": True,
        "status": "healthy",
        "timestamp": time.time()
    }


# Include API routers
from app.routers import (
    accounts,
    instruments, 
    transactions,
    corporate_actions,
    portfolio,
    dashboard
)

app.include_router(accounts.router)
app.include_router(instruments.router)
app.include_router(transactions.router)
app.include_router(corporate_actions.router)
app.include_router(portfolio.router)
app.include_router(dashboard.router)

@app.get("/api/status")
async def api_status():
    """API status endpoint."""
    return {
        "ok": True,
        "api_version": "v1",
        "features": {
            "logging": True,
            "error_handling": True,
            "request_tracing": True,
        }
    }


# Example error endpoint for testing
@app.get("/test-error")
async def test_error():
    """Test endpoint to verify error handling works."""
    from app.errors import ValidationError
    raise ValidationError("This is a test error", {"field": "test"})


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Financial Planning API server")
    logger.info("Configuration loaded with development defaults")
    
    uvicorn.run(
        "main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload,
        log_config=None,  # Use our custom logging
    )