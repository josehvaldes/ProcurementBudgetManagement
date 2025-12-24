"""
Intake Agent - Extracts data from invoice documents using Azure Document Intelligence.
"""

import asyncio
import signal
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

    def __init__(self, shutdown_event: asyncio.Event = asyncio.Event()):
        super().__init__(
            agent_name="IntakeAgent",
            subscription_name=SubscriptionNames.INTAKE_AGENT,
            shutdown_event=shutdown_event
        )
    
    def setup_signal_handlers(self):
        """setup signal handlers.""" 
        print("Setting up signal handlers...")
        def handle_signal(sig, frame):
            sig_name = signal.Signals(sig).name
            print(f"\n🛑 Received {sig_name}, initiating shutdown...")
            self.shutdown_event.set() 
            print(f"\n Shutdown event set to {self.shutdown_event.is_set()}. ")
            print("Cleanup tasks completed. Exiting now.")

        # Handle Ctrl+C (SIGINT) and kill command (SIGTERM)
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        # On Windows, also handle SIGBREAK (Ctrl+Break)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, handle_signal)

    async def process_invoice(self, invoice_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process invoice by extracting data from document.
        
        Args:
            invoice_id: Invoice ID
            message_data: Message payload
            
        Returns:
            Result data for next state
        """
        self.logger.info(f"Extracting data from invoice {invoice_id}")
        invoice_id = message_data["invoice_id"]
        event_type = message_data["event_type"]
        department_id = message_data["department_id"]

        self.logger.info(f"   * Extracting data from invoice: [{invoice_id}], event_type {event_type}, department_id {department_id}")
        # Get invoice from storage
        invoice = await self.get_invoice(department_id, invoice_id)

        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        # TODO: Extract data using Document Intelligence
        raw_file_url = invoice["raw_file_url"]
        self.logger.info(f"   * Extracting data from document URL: {raw_file_url}")

        # TODO: Implement document download and data extraction
        # document_url = await self.download_document(raw_file_url)
        # extracted_data = self.extract_invoice_data(document_url)

        # Update invoice with extracted data
        invoice["state"] = "EXTRACTED"
        # invoice.update(extracted_data)

        await self.update_invoice(invoice)

        return {
            "invoice_id": invoice_id,
            "department_id": department_id,
            "event_type": event_type,
            "state": "EXTRACTED",
            "extracted_at": message_data.get("timestamp"),
        }
    
    def get_next_subject(self) -> str:
        """Return the next message subject."""
        return InvoiceSubjects.EXTRACTED

if __name__ == "__main__":
    agent = IntakeAgent()
    agent.setup_signal_handlers()
    asyncio.run(agent.run())
