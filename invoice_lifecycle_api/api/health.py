"""
Health check endpoint.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from fastapi.responses import JSONResponse

from shared.utils.logging_config import get_logger
from shared.config.settings import settings

logger = get_logger(__name__)

router = APIRouter()

@router.get("/")
async def health_check_():
    """Basic health check - is service alive?"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": settings.api_title,
        "version": settings.api_version
    }

# Readiness: Check if dependencies are ready
@router.get("/ready")
async def readiness_check():
    """Readiness check - """
    services_ready = {
        "embedding_service": False,
        "vector_service": False,
        "llm_service": False,
        "cache_service": False
    }
    
    status_code = 200
    all_ready = True

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ready else "not_ready",
            "service": settings.api_title,
            "version": settings.api_version,
            "timestamp": datetime.now().isoformat(),
            "services": services_ready,
        }
    )
@router.get("/full")
async def health_check_full():
    """Full health check - service and dependencies status."""
    # Here you would normally check the status of your dependencies
    dependencies_status = {
        "database": "connected",
        "message_queue": "connected",
        "external_api": "reachable"
    }
    
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": settings.api_title,
            "version": settings.api_version,
            "timestamp": datetime.now().isoformat(),
            "dependencies": dependencies_status,
        }
        )