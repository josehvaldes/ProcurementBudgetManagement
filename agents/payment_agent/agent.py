"""
Payment Agent - Schedules and manages invoice payments.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from agents.base_agent import BaseAgent
from shared.utils.constants import InvoiceSubjects, SubscriptionNames


class PaymentAgent(BaseAgent):
    """
    Payment Agent manages payment scheduling and processing.
    
    Responsibilities:
    - Schedule payment based on terms (NET-30, NET-60, etc.)
    - Generate payment batches
    - Send remittance information to vendors
    - Update invoice state to PAYMENT_SCHEDULED
    - Publish invoice.payment_scheduled message
    """
    
    def __init__(self):
        super().__init__(
            agent_name="PaymentAgent",
            subscription_name=SubscriptionNames.PAYMENT_AGENT
        )
    
    def process_invoice(self, invoice_id: str, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Schedule payment for approved invoice.
        
        Args:
            invoice_id: Invoice ID
            message_data: Message payload
            
        Returns:
            Result data for next state
        """
        self.logger.info(f"Scheduling payment for invoice {invoice_id}")
        
        # Get invoice from storage
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        # TODO: Implement payment scheduling logic
        # - Get vendor payment terms
        # - Calculate payment due date
        # - Add to payment batch
        # - Generate remittance advice
        
        # Simple implementation: NET-30 from invoice date
        payment_terms = invoice.get("payment_terms", "NET-30")
        days = int(payment_terms.replace("NET-", ""))
        
        invoice_date = invoice.get("invoice_date")
        if invoice_date:
            payment_date = datetime.fromisoformat(invoice_date) + timedelta(days=days)
        else:
            payment_date = datetime.utcnow() + timedelta(days=days)
        
        # Update invoice state
        invoice["state"] = "PAYMENT_SCHEDULED"
        invoice["payment_scheduled_date"] = payment_date.isoformat()
        invoice["payment_terms"] = payment_terms
        
        self.update_invoice(invoice)
        
        return {
            "invoice_id": invoice_id,
            "state": "PAYMENT_SCHEDULED",
            "payment_date": payment_date.isoformat(),
        }
    
    def get_next_subject(self) -> str:
        """Return the next message subject."""
        return InvoiceSubjects.PAYMENT_SCHEDULED


if __name__ == "__main__":
    agent = PaymentAgent()
    agent.initialize()
    agent.run()
