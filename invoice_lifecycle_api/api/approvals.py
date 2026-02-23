"""
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from invoice_lifecycle_api.application.interfaces.di_container import get_approval_service
from invoice_lifecycle_api.application.services.approval_service import ApprovalService
from shared.utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    responses={
        500: {"description": "Internal server error"}
    }
)

DEFAULT_USER_NAME: str = "system"


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )
    approver_name: Optional[str] = Field(None, description="Name of the approver")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection, required if rejecting an invoice")

    @field_validator("approver_name")
    def validate_approver_name(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Approver name cannot be empty")
        return value

@router.get("/pending/{department_id}")
async def get_pending_approvals(
    department_id: str,
    approval_service: ApprovalService = Depends(get_approval_service)
) -> List[dict]:
    """
    Get a list of pending approvals.
    """
    
    try:
        logger.info(f"Retrieving pending approvals for department {department_id}")
        pending_approvals = await approval_service.get_pending_approvals(department_id)
        logger.info(f"Retrieved {len(pending_approvals)} pending approvals")
        return pending_approvals    
    except Exception as e:
        logger.error(f"Error retrieving pending approvals: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving pending approvals")


@router.post("/approve/{department_id}/{invoice_id}")
async def approve_invoice(department_id: str,
                           invoice_id: str,
                           request: ApprovalRequest,
                           approval_service: ApprovalService = Depends(get_approval_service)
                           ) -> dict:
    """
    Approve an invoice by approval ID.
    """
    approver_name = request.approver_name or DEFAULT_USER_NAME
    logger.info(f"Approving invoice with approval ID {invoice_id} by approver {approver_name}")
    return await approval_service.approve_invoice(department_id, invoice_id, approver_name)

@router.post("/reject/{department_id}/{invoice_id}")
async def reject_invoice(department_id: str,
                         invoice_id: str,
                         request: ApprovalRequest,
                         approval_service: ApprovalService = Depends(get_approval_service)
                         ) -> dict:
    """
    Reject an invoice by approval ID.
    """
    approver_name = request.approver_name or DEFAULT_USER_NAME
    logger.info(f"Rejecting invoice with approval ID {invoice_id} by approver {approver_name}")
    return await approval_service.reject_invoice(department_id, invoice_id, approver_name, reason=request.rejection_reason)
