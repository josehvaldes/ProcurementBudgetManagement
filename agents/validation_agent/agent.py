"""
Validation Agent - Validates invoices against business rules and policies.
"""

import asyncio
import signal
from typing import Dict, Any, Optional

from langsmith import traceable
from agents.base_agent import BaseAgent
from agents.validation_agent.tools.agentic_validator import AgenticValidator
from agents.validation_agent.tools.deterministic_validator import DeterministicValidator, ValidationResult
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.models.invoice import Invoice, InvoiceState
from shared.models.vendor import Vendor
from shared.utils.constants import InvoiceSubjects, SubscriptionNames
from shared.config.settings import settings


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
    
    def __init__(self, shutdown_event: asyncio.Event = asyncio.Event()):
        super().__init__(
            agent_name="ValidationAgent",
            subscription_name=SubscriptionNames.VALIDATION_AGENT,
            shutdown_event=shutdown_event
        )

        self.vendor_table_client = TableStorageService(
            storage_account_url=settings.table_storage_account_url,
            table_name=settings.vendors_table_name
        )

        self.deterministic_validation_tool = DeterministicValidator(
            vendor_table=self.vendor_table_client,
            invoice_table=self.invoice_table_client
        )

        self.ai_validation_tool = AgenticValidator()

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

        if self.vendor_table_client:
            await self.vendor_table_client.close()

    @traceable(name="validation_agent.process_invoice", tags=["validation", "agent"], metadata={"version": "1.0"})
    async def process_invoice(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Args:
            message_data: Message payload
        Returns:
            Result data for next state
        """
        invoice_id = message_data["invoice_id"]
        department_id = message_data["department_id"]
        self.logger.info(f"Validating invoice {invoice_id}")
        
        # Get invoice from storage
        invoice = await self.get_invoice(department_id, invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        invoice_obj = Invoice.from_dict(invoice)
        
        # Validate deterministically

        deterministic_response = await self.deterministic_validation_tool.validate_invoice(invoice_obj)

        # all deterministic validations passed
        self.logger.info(f"Invoice {invoice_id} passed deterministic validation")

        if deterministic_response.result == ValidationResult.VALID:
            # Fetch vendor details if available
            vendor = deterministic_response.matched_vendor
            # Check AI validations with vendor info
            ai_response = await self.ai_validation_tool.ainvoke({
                "invoice": invoice_obj.to_dict(),
                "vendor": vendor.to_dict()
            })
        
            if not ai_response.passed:
                self.logger.warning(f"Invoice {invoice_id} failed AI validation")
                invoice_obj.state = InvoiceState.FAILED
            else:
                self.logger.info(f"Invoice {invoice_id} passed AI validation")
                invoice_obj.state = InvoiceState.VALIDATED
            
            invoice_obj.validation_flags = ai_response.recommended_actions
            invoice_obj.validation_errors = ai_response.errors
            invoice_obj.validation_passed = invoice_obj.state == InvoiceState.VALIDATED
        
        elif deterministic_response.result == ValidationResult.MANUAL_REVIEW:
            self.logger.info(f"Invoice {invoice_id} requires manual review")
            invoice_obj.state = InvoiceState.MANUAL_REVIEW
            invoice_obj.validation_flags = []
            invoice_obj.validation_errors = deterministic_response.messages
            invoice_obj.validation_passed = False
        
        else:
            self.logger.warning(f"Invoice {invoice_id} failed deterministic validation")
            invoice_obj.state = InvoiceState.FAILED
            invoice_obj.validation_flags = []
            invoice_obj.validation_errors = deterministic_response.messages
            invoice_obj.validation_passed = False

        # Update invoice state
        await self.update_invoice(invoice_obj.to_dict())
        
        return {
            "invoice_id": invoice_id,
            "department_id": department_id,
            "state": invoice_obj.state.value,
            "event_type": "ValidationAgentGenerated",            
        }
    
    def get_next_subject(self) -> str:
        """Return the next message subject."""
        return InvoiceSubjects.VALIDATED


if __name__ == "__main__":
    agent = ValidationAgent()
    agent.setup_signal_handlers()
    asyncio.run(agent.run())

