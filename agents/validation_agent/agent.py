"""
Validation Agent - Validates invoices against business rules and policies.
"""

from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent
from shared.utils.constants import InvoiceSubjects, SubscriptionNames


class ValidationAgent(BaseAgent):
    """
    Validation Agent validates extracted invoice data.
    
    Responsibilities:
    - Verify against approved vendor list
    - Check spending authority limits
    - Validate pricing (compare to catalog)
    - Flag duplicate invoices
    - Check contract compliance
    - Update invoice state to VALIDATED
    - Publish invoice.validated message
    """
    
    def __init__(self):
        super().__init__(
            agent_name="ValidationAgent",
            subscription_name=SubscriptionNames.VALIDATION_AGENT
        )
    
    def process_invoice(self, invoice_id: str, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate invoice against business rules.
        
        Args:
            invoice_id: Invoice ID
            message_data: Message payload
            
        Returns:
            Result data for next state
        """
        self.logger.info(f"Validating invoice {invoice_id}")
        
        # Get invoice from storage
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        # TODO: Implement validation logic
        # - Check vendor approval status
        # - Validate amounts
        # - Check for duplicates
        # - Verify contract compliance
        
        validation_errors = []
        validation_warnings = []
        
        # Update invoice state
        invoice["state"] = "VALIDATED"
        invoice["validation_errors"] = validation_errors
        invoice["validation_warnings"] = validation_warnings
        
        self.update_invoice(invoice)
        
        return {
            "invoice_id": invoice_id,
            "state": "VALIDATED",
            "validation_errors": validation_errors,
            "validation_warnings": validation_warnings,
        }
    
    def get_next_subject(self) -> str:
        """Return the next message subject."""
        return InvoiceSubjects.VALIDATED


if __name__ == "__main__":
    agent = ValidationAgent()
    agent.initialize()
    agent.run()
