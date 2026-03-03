from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from invoice_lifecycle_api.application.interfaces.di_container import get_analytics_service
from invoice_lifecycle_api.application.services.analytics_service import AnalyticsService
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


async def _handle_analytics_request(
    operation_name: str,
    handler,
    log_context: dict,
) -> list[dict]:
    """
    Centralised wrapper for analytics endpoint logic.

    Handles logging, invocation, and exception translation so that
    every endpoint behaves consistently.
    """
    logger.info(
        "Analytics request started: %s",
        operation_name,
        extra=log_context,
    )

    try:
        result = await handler()
        logger.info(
            "Analytics request completed: %s – returned %d record(s)",
            operation_name,
            len(result) if result else 0,
            extra=log_context,
        )
        return result

    except HTTPException:
        # Re-raise any HTTPException already raised by the service layer
        raise

    except ValueError as exc:
        logger.warning(
            "Bad request for %s: %s",
            operation_name,
            exc,
            extra={**log_context, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    except Exception as exc:
        logger.exception(
            "Unhandled error during %s",
            operation_name,
            extra={**log_context, "error": str(exc), "error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing {operation_name}",
        )


@router.get("/spending-summary")
async def get_spending_summary(
    department_id: Optional[str] = Query(None, description="Filter by department ID"),
    fiscal_year: Optional[str] = Query(None, description="Filter by fiscal year (e.g. FY2025)"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> list[dict]:
    """Get a summary of spending by department."""
    return await _handle_analytics_request(
        operation_name="spending-summary",
        handler=lambda: analytics_service.get_spending_summary(
            department_id=department_id,
            fiscal_year=fiscal_year,
        ),
        log_context={"department_id": department_id, "fiscal_year": fiscal_year},
    )


@router.get("/pipeline-performance")
async def get_pipeline_performance(
    fiscal_year: Optional[str] = Query(None, description="Filter by fiscal year (e.g. FY2025)"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> list[dict]:
    """Get performance metrics for the invoice approval pipeline."""
    return await _handle_analytics_request(
        operation_name="pipeline-performance",
        handler=lambda: analytics_service.get_pipeline_performance(
            fiscal_year=fiscal_year,
        ),
        log_context={"fiscal_year": fiscal_year},
    )


@router.get("/vendor-summary")
async def get_vendor_summary(
    fiscal_year: Optional[str] = Query(None, description="Filter by fiscal year (e.g. FY2025)"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> list[dict]:
    """Get a summary of spending by vendor."""
    return await _handle_analytics_request(
        operation_name="vendor-summary",
        handler=lambda: analytics_service.get_vendor_summary(
            fiscal_year=fiscal_year,
        ),
        log_context={"fiscal_year": fiscal_year},
    )