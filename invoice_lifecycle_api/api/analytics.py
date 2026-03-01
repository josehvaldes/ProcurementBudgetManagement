from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from invoice_lifecycle_api.application.interfaces.di_container import get_analytics_service, get_approval_service
from invoice_lifecycle_api.application.services.analytics_service import AnalyticsService
from invoice_lifecycle_api.application.services.approval_service import ApprovalService
from shared.utils.exceptions import (
    InvoiceNotFoundException,
    InvalidInvoiceStateException
)
from shared.utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    responses={
        400: {"description": "Bad request"},
        404: {"description": "Resource not found"},
        409: {"description": "Conflict - invalid state transition"},
        500: {"description": "Internal server error"},
    }
)

@router.get("/spending-summary")
async def get_spending_summary(
    department_id: str = None,
    fiscal_year: str = None,
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> list[dict]:
    """Get a summary of spending by department."""
    logger.info("Received request for spending summary", 
                extra={"department_id": department_id, "fiscal_year": fiscal_year})
    try:
        summary = await analytics_service.get_spending_summary(department_id=department_id, fiscal_year=fiscal_year)
        return summary
    except Exception as e:
        logger.error("Error getting spending summary", extra={"error": str(e), "department_id": department_id, "fiscal_year": fiscal_year})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error getting spending summary")
    

@router.get("/pipeline-performance")
async def get_pipeline_performance(
    fiscal_year: str = None,
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> list[dict]:
    """Get performance metrics for the invoice approval pipeline."""
    logger.info("Received request for pipeline performance",
                extra={"fiscal_year": fiscal_year})
    try:
        performance = await analytics_service.get_pipeline_performance(fiscal_year=fiscal_year)
        return performance
    except Exception as e:
        logger.error("Error getting pipeline performance", extra={"error": str(e), "fiscal_year": fiscal_year})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error getting pipeline performance")
    
@router.get("/vendor-summary")
async def get_vendor_summary(
    fiscal_year: str = None,
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> list[dict]:
    """Get a summary of spending by vendor."""
    logger.info("Received request for vendor summary",
                extra={"fiscal_year": fiscal_year})
    try:
        summary = await analytics_service.get_vendor_summary(fiscal_year=fiscal_year)
        return summary
    except Exception as e:
        logger.error("Error getting vendor summary", extra={"error": str(e), "fiscal_year": fiscal_year})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error getting vendor summary")