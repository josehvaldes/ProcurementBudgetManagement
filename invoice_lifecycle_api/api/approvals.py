"""
Approvals API - Manages invoice approval and rejection workflows.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from invoice_lifecycle_api.application.interfaces.di_container import get_approval_service
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

DEFAULT_USER_NAME: str = "system"


class ApprovalRequest(BaseModel):
    """Request model for invoice approval or rejection."""

    
    approver_name: Optional[str] = Field(
        None, description="Name of the approver"
    )
    rejection_reason: Optional[str] = Field(
        None,
        description="Reason for rejection, required if rejecting an invoice",
    )

    @field_validator("approver_name")
    def validate_approver_name(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Approver name cannot be empty")
        return value
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "approver_name": "John Doe",
                "rejection_reason": "Insufficient funds"
            }
        }
    )


@router.get("/pending/{department_id}")
async def get_pending_approvals(
    department_id: str,
    approval_service: ApprovalService = Depends(get_approval_service),
) -> List[dict]:
    """Get a list of pending approvals for a department."""

    logger.info(
        "Retrieving pending approvals",
        extra={"department_id": department_id},
    )

    try:
        pending_approvals = await approval_service.get_pending_approvals(department_id)

        logger.info(
            "Pending approvals retrieved successfully",
            extra={
                "department_id": department_id,
                "result_count": len(pending_approvals),
            },
        )
        return pending_approvals

    except Exception as e:
        logger.error(
            "Failed to retrieve pending approvals",
            extra={
                "department_id": department_id,
                "error_type": "InvoiceRetrievalError",
                "error_details": str(e),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pending approvals",
        )

    except Exception as e:
        logger.error(
            "Unexpected error retrieving pending approvals",
            extra={
                "department_id": department_id,
                "error_type": "UnexpectedError",
                "error_details": str(e),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/approve/{department_id}/{invoice_id}")
async def approve_invoice(
    department_id: str,
    invoice_id: str,
    request: ApprovalRequest,
    approval_service: ApprovalService = Depends(get_approval_service),
) -> dict:
    """Approve an invoice by department and invoice ID."""

    approver_name = request.approver_name or DEFAULT_USER_NAME

    logger.info(
        "Processing invoice approval request",
        extra={
            "department_id": department_id,
            "invoice_id": invoice_id,
            "approver_name": approver_name,
        },
    )

    try:
        result = await approval_service.approve_invoice(
            department_id, invoice_id, approver_name
        )

        logger.info(
            "Invoice approved successfully",
            extra={
                "department_id": department_id,
                "invoice_id": invoice_id,
                "approver_name": approver_name,
            },
        )
        return result

    except InvoiceNotFoundException as e:
        logger.warning(
            "Invoice not found for approval",
            extra={
                "department_id": department_id,
                "invoice_id": invoice_id,
                "error_type": "InvoiceNotFound",
                "error_details": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found in department {department_id}",
        )

    except InvalidInvoiceStateException as e:
        logger.warning(
            "Invoice is not in a valid state for approval",
            extra={
                "department_id": department_id,
                "invoice_id": invoice_id,
                "error_type": "InvalidInvoiceState",
                "error_details": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    except Exception as e:
        logger.error(
            "Service error during invoice approval",
            extra={
                "department_id": department_id,
                "invoice_id": invoice_id,
                "approver_name": approver_name,
                "error_type": "ServiceError",
                "error_details": str(e),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve invoice",
        )

    except Exception as e:
        logger.error(
            "Unexpected error during invoice approval",
            extra={
                "department_id": department_id,
                "invoice_id": invoice_id,
                "approver_name": approver_name,
                "error_type": "UnexpectedError",
                "error_details": str(e),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/reject/{department_id}/{invoice_id}")
async def reject_invoice(
    department_id: str,
    invoice_id: str,
    request: ApprovalRequest,
    approval_service: ApprovalService = Depends(get_approval_service),
) -> dict:
    """Reject an invoice by department and invoice ID."""

    approver_name = request.approver_name or DEFAULT_USER_NAME

    logger.info(
        "Processing invoice rejection request",
        extra={
            "department_id": department_id,
            "invoice_id": invoice_id,
            "approver_name": approver_name,
            "has_rejection_reason": request.rejection_reason is not None,
        },
    )

    try:
        result = await approval_service.reject_invoice(
            department_id,
            invoice_id,
            approver_name,
            reason=request.rejection_reason,
        )

        logger.info(
            "Invoice rejected successfully",
            extra={
                "department_id": department_id,
                "invoice_id": invoice_id,
                "approver_name": approver_name,
            },
        )
        return result

    except InvoiceNotFoundException as e:
        logger.warning(
            "Invoice not found for rejection",
            extra={
                "department_id": department_id,
                "invoice_id": invoice_id,
                "error_type": "InvoiceNotFound",
                "error_details": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found in department {department_id}",
        )

    except InvalidInvoiceStateException as e:
        logger.warning(
            "Invoice is not in a valid state for rejection",
            extra={
                "department_id": department_id,
                "invoice_id": invoice_id,
                "error_type": "InvalidInvoiceState",
                "error_details": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Unexpected error during invoice rejection",
            extra={
                "department_id": department_id,
                "invoice_id": invoice_id,
                "approver_name": approver_name,
                "error_type": "UnexpectedError",
                "error_details": str(e),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject invoice",
        )

    except Exception as e:
        logger.error(
            "Unexpected error during invoice rejection",
            extra={
                "department_id": department_id,
                "invoice_id": invoice_id,
                "approver_name": approver_name,
                "error_type": "UnexpectedError",
                "error_details": str(e),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
