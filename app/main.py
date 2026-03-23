from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from app.core.config import get_settings
from app.core.database import init_db
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.audit_logger import AuditLoggerMiddleware

# Import routers
from app.routers import auth, units, threats, drones, comms, analytics, cyber, sensors

settings = get_settings()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting AEGIS C4ISR Platform...")

    # Initialize database tables
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down AEGIS C4ISR Platform...")


# Create FastAPI application
app = FastAPI(
    title="AEGIS C4ISR Unified Command Platform",
    description="Military-grade Command, Control, Communications, Computers, Intelligence, Surveillance & Reconnaissance platform",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(AuditLoggerMiddleware)
# app.add_middleware(AuthMiddleware)  # Uncomment for production

# Include routers
app.include_router(auth.router)
app.include_router(units.router)
app.include_router(threats.router)
app.include_router(drones.router)
app.include_router(comms.router)
app.include_router(analytics.router)
app.include_router(cyber.router)
app.include_router(sensors.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "AEGIS C4ISR Unified Command Platform",
        "version": "1.0.0",
        "status": "OPERATIONAL",
        "classification": "TOP SECRET//NOFORN"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": structlog.processors.TimeStamper()(None, None, None)
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
