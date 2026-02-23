"""
Payment Agent - Schedules and manages invoice payments.
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from langsmith import traceable
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
    
    def __init__(self, shutdown_event: asyncio.Event = asyncio.Event()):
        super().__init__( 
            agent_name="PaymentAgent",
            subscription_name=SubscriptionNames.PAYMENT_AGENT,
            shutdown_event=shutdown_event
        )
    
    async def release_resources(self) -> None:
        """Release any resources held by the agent."""
        cleanup_errors = []

    @traceable(name="payment_agent.process_invoice", tags=["payment", "agent"], metadata={"version": "1.0"})
    async def process_invoice(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Schedule payment for approved invoice.
        
        Args:
            invoice_id: Invoice ID
            message_data: Message payload
            
        Returns:
            Result data for next state
        """
        invoice_id = message_data["invoice_id"]
        department_id = message_data["department_id"]
        correlation_id = message_data.get("correlation_id", invoice_id)
        
        self.logger.info(
            f"Starting payment scheduling for invoice",
            extra={
                "invoice_id": invoice_id,
                "department_id": department_id,
                "correlation_id": correlation_id,
                "agent": self.agent_name
            }
        )
        
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
    agent.setup_signal_handlers()
    asyncio.run(agent.run())
