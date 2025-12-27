"""
Intake Agent - Extracts data from invoice documents using Azure Document Intelligence.
"""

import asyncio
import signal
from typing import Dict, Any
from agents.base_agent import BaseAgent
from agents.intake_agent.tools.invoice_analyzer_tool import InvoiceAnalyzerTool
from agents.intake_agent.tools.qr_extractor import get_qr_info_from_bytes
from shared.utils.constants import InvoiceSubjects, SubscriptionNames
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from invoice_lifecycle_api.infrastructure.repositories.invoice_storage_service import InvoiceStorageService 
from shared.config.settings import settings
from shared.utils.convert import convert_to_table_entity

from langsmith import traceable

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

        self.blob_storage_client = InvoiceStorageService()
        self.invoice_analyzer_tool = InvoiceAnalyzerTool()

    def setup_signal_handlers(self):
        """setup signal handlers."""
        print("Setting up signal handlers...")
        def handle_signal(sig, frame):
            sig_name = signal.Signals(sig).name
            self.logger.info(f"\n🛑 Received {sig_name}, initiating shutdown...")
            self.shutdown_event.set() 

        # Handle Ctrl+C (SIGINT) and kill command (SIGTERM)
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        # On Windows, also handle SIGBREAK (Ctrl+Break)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, handle_signal)

    async def release_resources(self) -> None:
        """Release any resources held by the agent."""
        self.logger.info(f"Releasing resources for {self.agent_name}...")
        if self.blob_storage_client:
            await self.blob_storage_client.close()
        if self.invoice_analyzer_tool:
            await self.invoice_analyzer_tool.close()

        get_credential_manager().close()

    @traceable(name="intake_agent.process_invoice", tags=["intake", "agent"], metadata={"version": "1.0"})
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
        department_id = message_data["department_id"]

        self.logger.info(f"   * Extracting data from invoice: [{invoice_id}], department_id {department_id}")
        # Get invoice from storage
        invoice = await self.get_invoice(department_id, invoice_id)

        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        # TODO: Extract data using Document Intelligence
        raw_file_url = invoice["raw_file_url"]
        document_type = invoice["document_type"]
        self.logger.info(f"   * Extracting data from document URL: {raw_file_url}")

        document_bytes = await self.blob_storage_client.download_file(
            container_name=settings.blob_container_name,
            blob_name=invoice["raw_file_blob_name"]
        )

        if not document_bytes:
            raise ValueError(f"Document {invoice['raw_file_blob_name']} not found")
        
        self.logger.info(f"   * Downloaded document bytes: {len(document_bytes)} bytes")
        if document_type.lower() == "invoice":
            invoice_extracted = await self.invoice_analyzer_tool.analyze_invoice_request(document_bytes)
        elif document_type.lower() == "receipt":
            invoice_extracted = await self.invoice_analyzer_tool.analyze_receipt_request(document_bytes)

        self.logger.info(f"   * Extracted invoice data: {invoice_extracted}")
        invoice.update(invoice_extracted)

        self.logger.info(f"   * Updated invoice with extracted data: {invoice}")
        qr_info_list = await get_qr_info_from_bytes(document_bytes)
        if qr_info_list:
            self.logger.info(f"   * Found QR code info: {qr_info_list}")
            invoice["qr_codes_data"] = [ qr_info.data for qr_info in qr_info_list ]

        # Update invoice with extracted data
        invoice["state"] = "EXTRACTED"
        # invoice.update(extracted_data)
        invoice = convert_to_table_entity(invoice)
        updated = await self.update_invoice(invoice)
        if not updated:
            raise ValueError(f"Failed to update invoice {invoice_id}")

        return {
            "invoice_id": invoice_id,
            "department_id": department_id,
            "event_type": "IntakeAgentGenerated",
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
