"""
Approval Agent - Manages invoice approval workflow.
"""

import asyncio
from typing import Dict, Any

from langsmith import traceable
from shared.config.settings import settings
from agents.base_agent import BaseAgent
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.utils.constants import InvoiceSubjects, SubscriptionNames

class ApprovalAgent(BaseAgent):
    """
    Approval Agent manages the invoice approval process.
    
    Responsibilities:
    - Auto-approve invoices within policy thresholds
    - Route to department manager for approval if needed
    - Escalate over-budget invoices
    - Update invoice state to APPROVED or MANUAL_REVIEW
    - Publish appropriate message
    """
    
    def __init__(self, shutdown_event: asyncio.Event = asyncio.Event()):
        super().__init__(
            agent_name="ApprovalAgent",
            subscription_name=SubscriptionNames.APPROVAL_AGENT,
            shutdown_event=shutdown_event
        )
        self.vendor_table_client = TableStorageService(
            storage_account_url=settings.table_storage_account_url,
            table_name=settings.vendors_table_name
        )


    async def release_resources(self) -> None:
        """Release any resources held by the agent."""
        pass

    @traceable(name="approval_agent.process_invoice", tags=["approval", "agent"], metadata={"version": "1.0"})
    async def process_invoice(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process invoice approval decision.
        Args:
            message_data: Message payload
            
        Returns:
            Result data for next state
        """
        invoice_id = message_data["invoice_id"]
        department_id = message_data["department_id"]
        self.logger.info(f"Processing approval for invoice {invoice_id}")
        
        # Get invoice from storage
        invoice = await self.get_invoice(department_id, invoice_id)

        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        vendor_id = invoice.get("vendor_id")
        if vendor_id is not None:
            vendor = await self.vendor_table_client.get_entity(
                partition_key="VENDOR", # partiotion key is fixed for vendors
                row_key=vendor_id
            )
            if not vendor:
                raise ValueError(f"Vendor {vendor_id} not found for invoice {invoice_id}")

            self.logger.info(f"Vendor {vendor.get('name')} found for invoice {invoice_id}")

        else:
            raise ValueError(f"Vendor ID missing for invoice {invoice_id}")

        # TODO: Implement approval logic
        # - Check if invoice meets auto-approval criteria
        # - Route for manual approval if needed
        # - Handle over-budget escalations
        
        total_amount = float(invoice.get("total_amount", 0))
        auto_approve_threshold = self.settings.auto_approve_threshold
        
        if total_amount <= auto_approve_threshold:
            # Auto-approve
            invoice["state"] = "APPROVED"
            invoice["approval_method"] = "auto"
            next_state = "APPROVED"
        else:
            # Requires manual approval
            invoice["state"] = "MANUAL_REVIEW"
            invoice["approval_method"] = "manual"
            next_state = "MANUAL_REVIEW"
        
        self.update_invoice(invoice)
        
        return {
            "invoice_id": invoice_id,
            "state": next_state,
            "approval_method": invoice["approval_method"],
        }
    
    def get_next_subject(self) -> str:
        """Return the next message subject."""
        return InvoiceSubjects.APPROVED


if __name__ == "__main__":
    agent = ApprovalAgent()
    agent.setup_signal_handlers()
    asyncio.run(agent.run())
