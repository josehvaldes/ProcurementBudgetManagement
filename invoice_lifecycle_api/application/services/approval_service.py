from datetime import datetime, timezone
from typing import Optional
import uuid

from shared.models.invoice import InvoiceState, ReviewStatus
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.application.interfaces.service_interfaces import CompareOperator, JoinOperator, TableServiceInterface
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import EntityQueryException
from shared.models.budget import Budget, BudgetStatus
from shared.utils.constants import CompoundKeyStructure

logger = get_logger(__name__)




class ApprovalService:

    def __init__(self, 
                 invoice_repository: TableServiceInterface,
                 budget_repository: TableServiceInterface = None
                 ):
        self.repository = invoice_repository
        self.budget_repository = budget_repository
        logger.info("ApprovalService initialized with repository", 
                    extra={"repository_type": type(invoice_repository).__name__}
                    )

    async def get_pending_approvals(self, department_id: str) -> list[dict]:
        try:
            
            partition_key = department_id
            filters = [
                ( "partitionkey", partition_key, CompareOperator.EQUAL.value ),
                ( "state", InvoiceState.PENDING_APPROVAL.value, CompareOperator.EQUAL.value )
            ]
            pending_approvals = await self.repository.query_entities_with_filters(filters = filters, join_operator=JoinOperator.AND)
            return pending_approvals
        except EntityQueryException as e:
            logger.error("Error querying pending approvals", extra={"error": str(e)})
            raise

    async def approve_invoice(self, department_id: str, invoice_id: str, approver_name: str) -> dict:
        try:
            invoice_entity = await self.repository.get_entity(partition_key=department_id, row_key=invoice_id)
            invoice_entity["state"] = InvoiceState.APPROVED.value
            invoice_entity["reviewed_date"] = datetime.now(timezone.utc).isoformat()
            invoice_entity["reviewed_by"] = approver_name
            invoice_entity["review_status"] = ReviewStatus.APPROVED.value
            await self.repository.upsert_entity(invoice_entity)
            return invoice_entity
        except EntityQueryException as e:
            logger.error("Error approving invoice", extra={"error": str(e), "invoice_id": invoice_id})
            raise

    async def reject_invoice(self, department_id: str, invoice_id: str, approver_name: str, rejection_reason: str) -> dict:
        try:
            invoice_entity = await self.repository.get_entity(partition_key=department_id, row_key=invoice_id)
            invoice_entity["state"] = InvoiceState.REJECTED.value
            invoice_entity["reviewed_date"] = datetime.now(timezone.utc).isoformat()
            invoice_entity["reviewed_by"] = approver_name
            invoice_entity["review_status"] = ReviewStatus.REJECTED.value
            invoice_entity["rejection_reason"] = rejection_reason
            await self.repository.upsert_entity(invoice_entity)
            return invoice_entity
        except EntityQueryException as e:
            logger.error("Error rejecting invoice", extra={"error": str(e), "invoice_id": invoice_id})
            raise