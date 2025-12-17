"""
Approval Agent - Manages invoice approval workflow.
"""

from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent
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
    
    def __init__(self):
        super().__init__(
            agent_name="ApprovalAgent",
            subscription_name=SubscriptionNames.APPROVAL_AGENT
        )
    
    def process_invoice(self, invoice_id: str, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process invoice approval decision.
        
        Args:
            invoice_id: Invoice ID
            message_data: Message payload
            
        Returns:
            Result data for next state
        """
        self.logger.info(f"Processing approval for invoice {invoice_id}")
        
        # Get invoice from storage
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
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
    agent.initialize()
    agent.run()
