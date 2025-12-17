"""
Intake Agent - Extracts data from invoice documents using Azure Document Intelligence.
"""

from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent
from shared.utils.constants import InvoiceSubjects, SubscriptionNames


class IntakeAgent(BaseAgent):
    """
    Intake Agent processes newly created invoices.
    
    Responsibilities:
    - Extract data from invoice documents using Azure Document Intelligence
    - Update invoice state to EXTRACTED
    - Publish invoice.extracted message
    """
    
    def __init__(self):
        super().__init__(
            agent_name="IntakeAgent",
            subscription_name=SubscriptionNames.INTAKE_AGENT
        )
    
    def process_invoice(self, invoice_id: str, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process invoice by extracting data from document.
        
        Args:
            invoice_id: Invoice ID
            message_data: Message payload
            
        Returns:
            Result data for next state
        """
        self.logger.info(f"Extracting data from invoice {invoice_id}")
        
        # Get invoice from storage
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        # TODO: Extract data using Document Intelligence
        # document_url = invoice.get("document_url")
        # extracted_data = self.extract_invoice_data(document_url)
        
        # Update invoice with extracted data
        invoice["state"] = "EXTRACTED"
        # invoice.update(extracted_data)
        
        self.update_invoice(invoice)
        
        return {
            "invoice_id": invoice_id,
            "state": "EXTRACTED",
            "extracted_at": message_data.get("timestamp"),
        }
    
    def get_next_subject(self) -> str:
        """Return the next message subject."""
        return InvoiceSubjects.EXTRACTED


if __name__ == "__main__":
    agent = IntakeAgent()
    agent.initialize()
    agent.run()
