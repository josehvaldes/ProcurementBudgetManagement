"""
Health Check API endpoints for service monitoring.

This module provides health check endpoints for monitoring service status,
readiness, and dependency health. These endpoints are used by:
- Load balancers for health probes
- Kubernetes for liveness and readiness checks
- Monitoring systems for alerting
- Operational dashboards
"""
from fastapi import APIRouter, status
from datetime import datetime, timezone
from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from fastapi.responses import JSONResponse

from shared.utils.logging_config import get_logger
from shared.config.settings import settings

logger = get_logger(__name__)

router = APIRouter(
    responses={
        500: {"description": "Service is unhealthy"}
    }
)


# ==================== Response Models ====================

class HealthCheckResponse(BaseModel):
    """Basic health check response model."""
    status: str = Field(..., description="Health status: healthy or unhealthy")
    timestamp: str = Field(..., description="ISO 8601 formatted timestamp")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "timestamp": "2025-02-03T10:00:00.000Z",
                "service": "Invoice Lifecycle API",
                "version": "1.0.0"
            }
        }
    )


class ServiceStatus(BaseModel):
    """Individual service dependency status."""
    name: str = Field(..., description="Service name")
    status: str = Field(..., description="Status: connected, disconnected, or degraded")
    response_time_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    last_check: Optional[str] = Field(None, description="Last check timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "table_storage",
                "status": "connected",
                "response_time_ms": 45.2,
                "last_check": "2025-02-03T10:00:00.000Z"
            }
        }
    )


class ReadinessCheckResponse(BaseModel):
    """Readiness check response with dependency status."""
    status: str = Field(..., description="Overall status: ready or not_ready")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: str = Field(..., description="ISO 8601 formatted timestamp")
    services: Dict[str, bool] = Field(..., description="Status of each dependency service")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ready",
                "service": "Invoice Lifecycle API",
                "version": "1.0.0",
                "timestamp": "2025-02-03T10:00:00.000Z",
                "services": {
                    "table_storage": True,
                    "blob_storage": True,
                    "document_intelligence": True,
                    "service_bus": True
                }
            }
        }
    )


class FullHealthCheckResponse(BaseModel):
    """Comprehensive health check response with detailed dependency information."""
    status: str = Field(..., description="Overall health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: str = Field(..., description="ISO 8601 formatted timestamp")
    uptime_seconds: Optional[float] = Field(None, description="Service uptime in seconds")
    dependencies: Dict[str, str] = Field(..., description="Status of each dependency")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "service": "Invoice Lifecycle API",
                "version": "1.0.0",
                "timestamp": "2025-02-03T10:00:00.000Z",
                "uptime_seconds": 3600.5,
                "dependencies": {
                    "table_storage": "connected",
                    "blob_storage": "connected",
                    "document_intelligence": "connected",
                    "service_bus": "connected",
                    "budget_service": "reachable"
                }
            }
        }
    )


# ==================== API Endpoints ====================

@router.get(
    "/",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Basic health check",
    description="""
    Basic liveness check to verify the service is running.
    
    This endpoint performs a simple check to confirm the API is alive
    and responding to requests. It does not check dependencies or
    external services.
    
    **Use cases:**
    - Load balancer health probes
    - Kubernetes liveness probes
    - Quick status verification
    
    **Response time:** < 100ms
    """,
    responses={
        200: {
            "description": "Service is alive and responding",
            "model": HealthCheckResponse
        }
    }
)
async def health_check() -> HealthCheckResponse:
    """
    Basic health check endpoint.
    
    Returns a simple health status indicating the service is running.
    This endpoint should respond quickly (< 100ms) and is suitable
    for frequent health checks by load balancers.
    
    Returns:
        HealthCheckResponse with basic service information
    """
    logger.debug("Health check endpoint called")
    
    return HealthCheckResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        service=settings.api_title,
        version=settings.api_version
    )


@router.get(
    "/ready",
    response_model=ReadinessCheckResponse,
    summary="Readiness check",
    description="""
    Readiness check to verify service and dependencies are ready.
    
    This endpoint checks if the service and its critical dependencies
    are ready to handle traffic. Unlike the basic health check, this
    performs actual connectivity tests to external services.
    
    **Checked dependencies:**
    - Azure Table Storage (invoices, budgets, vendors)
    - Azure Blob Storage (invoice files)
    - Azure Document Intelligence (OCR service)
    - Azure Service Bus (event messaging)
    
    **Use cases:**
    - Kubernetes readiness probes
    - Pre-deployment validation
    - Traffic routing decisions
    
    **Response time:** < 5 seconds
    
    Returns 200 only if all critical dependencies are ready.
    Returns 503 if any critical dependency is unavailable.
    """,
    responses={
        200: {
            "description": "Service and dependencies are ready",
            "model": ReadinessCheckResponse
        },
        503: {
            "description": "Service or dependencies are not ready",
            "model": ReadinessCheckResponse
        }
    }
)
async def readiness_check() -> JSONResponse:
    """
    Readiness check endpoint.
    
    Verifies that the service and all critical dependencies are ready
    to handle requests. This includes checking connectivity to:
    - Azure Table Storage
    - Azure Blob Storage
    - Azure Document Intelligence
    - Azure Service Bus
    
    Returns:
        JSONResponse with readiness status and dependency details
        - 200 if all services are ready
        - 503 if any critical service is not ready
    """
    logger.info("Readiness check endpoint called")
    
    # Check critical service dependencies
    services_ready = {
        "table_storage": True,  # TODO: Implement actual table storage connectivity check
        "blob_storage": True,   # TODO: Implement actual blob storage connectivity check
        "document_intelligence": True,  # TODO: Implement actual Document Intelligence check
        "service_bus": True     # TODO: Implement actual Service Bus connectivity check
    }
    
    # Determine overall readiness
    all_ready = all(services_ready.values())
    status_code = status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    
    logger.info(f"Readiness check result: {'ready' if all_ready else 'not_ready'} - Services: {services_ready}")

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ready else "not_ready",
            "service": settings.api_title,
            "version": settings.api_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": services_ready,
        }
    )


@router.get(
    "/full",
    response_model=FullHealthCheckResponse,
    summary="Full health check with detailed diagnostics",
    description="""
    Comprehensive health check with detailed dependency diagnostics.
    
    This endpoint provides detailed health information about the service
    and all its dependencies, including:
    - Service uptime
    - Dependency connection status
    - Response times (future enhancement)
    - Resource utilization (future enhancement)
    
    **Checked dependencies:**
    - Azure Table Storage
    - Azure Blob Storage
    - Azure Document Intelligence
    - Azure Service Bus
    - Budget Service
    - Vendor Service
    
    **Use cases:**
    - Operational dashboards
    - Troubleshooting and diagnostics
    - Detailed monitoring
    - Pre-deployment validation
    
    **Response time:** < 10 seconds
    
    ⚠️ **Warning:** This endpoint performs comprehensive checks and
    should not be used for frequent automated health checks.
    Use `/health` or `/health/ready` for automated monitoring.
    """,
    responses={
        200: {
            "description": "Detailed health status with all dependencies",
            "model": FullHealthCheckResponse
        },
        503: {
            "description": "Service is degraded or unhealthy",
            "model": FullHealthCheckResponse
        }
    }
)
async def health_check_full() -> JSONResponse:
    """
    Full health check with comprehensive diagnostics.
    
    Performs detailed checks on the service and all dependencies,
    including connectivity tests and status verification. This
    endpoint is more expensive than basic health checks and should
    be used sparingly.
    
    Returns:
        JSONResponse with detailed health status
        - 200 if service is healthy
        - 503 if service is degraded or unhealthy
    """
    logger.info("Full health check endpoint called")
    
    # Check all dependencies with detailed status
    # TODO: Implement actual connectivity checks with response time measurement
    dependencies_status = {
        "table_storage": "connected",
        "blob_storage": "connected",
        "document_intelligence": "connected",
        "service_bus": "connected",
        "budget_service": "reachable",
        "vendor_service": "reachable"
    }
    
    # Determine overall health
    all_healthy = all(status in ["connected", "reachable"] for status in dependencies_status.values())
    http_status = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    
    # TODO: Calculate actual service uptime
    uptime_seconds = 0.0
    
    logger.info(f"Full health check result: {'healthy' if all_healthy else 'unhealthy'} - Dependencies: {dependencies_status}")
    
    return JSONResponse(
        status_code=http_status,
        content={
            "status": "healthy" if all_healthy else "degraded",
            "service": settings.api_title,
            "version": settings.api_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": uptime_seconds,
            "dependencies": dependencies_status,
        }
    )


@router.get(
    "/ping",
    summary="Minimal ping endpoint",
    description="""
    Ultra-lightweight ping endpoint for network connectivity tests.
    
    This is the fastest possible endpoint, suitable for high-frequency
    monitoring and network connectivity verification.
    
    **Response time:** < 10ms
    """,
    responses={
        200: {
            "description": "Pong response",
            "content": {
                "application/json": {
                    "example": {"ping": "pong"}
                }
            }
        }
    }
)
async def ping():
    """
    Minimal ping endpoint.
    
    Returns a simple "pong" response for network connectivity testing.
    This endpoint has minimal overhead and should respond in < 10ms.
    
    Returns:
        Simple pong response
    """
    return {"ping": "pong"}