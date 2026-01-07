"""
Validation Agent - Validates invoices against business rules and policies.
"""

import asyncio
import signal
from typing import Dict, Any, Optional

from langsmith import traceable
from agents.base_agent import BaseAgent
from agents.validation_agent.tools.agentic_validator import AgenticValidator
from agents.validation_agent.tools.deterministic_validator import DeterministicValidator
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

        self.deterministic_validation_tool = DeterministicValidator()

        self.ai_validation_tool = AgenticValidator(
            ai_model_client=None  # Placeholder for actual AI model client
        )

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
        Validate invoice against business rules.
            Deterministc validations:
                - Check invoice data completeness
                - Check for duplicate invoices

                if vendor in vendor list:
                - Check vendor approval status
                - Check approved vendor list
                - Check spending authority limits
                - Check contract compliance
                - AI Model Review
                
                If not in vendor list:
                - Flag for vendor review
                - AI Model Review

            AI Validations:
                - Check for anomalies in invoice data
                - Validate against historical invoice data
                - Predict potential issues using ML models

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
        
        if not invoice_obj:
            raise ValueError(f"Failed to parse invoice data for {invoice_id}")
        
        validation_errors = []
        validation_warnings = []
        
        vendor_name = invoice_obj.vendor_name
        if vendor_name is None or vendor_name.strip() == "":
            # new vendor or missing vendor_id
            self.logger.warning(f"Invoice {invoice_id} has no vendor_name; flagging for review")
            invoice_obj.state = InvoiceState.FAILED
        else:
            self.logger.info(f"Invoice {invoice_id} has vendor_name {vendor_name}; performing validations")
            # Perform duplicate check
            is_duplicate = self.has_duplicate(invoice)
            if is_duplicate:
                self.logger.warning(f"Invoice {invoice_id} is a duplicate; flagging for review")
                invoice_obj.state = InvoiceState.FAILED
                validation_errors = ["Duplicate invoice detected"]
            else:
                # - Check vendor approval status
                # - Validate amounts
                # - Verify contract compliance
                
                vendors_list = await self.vendor_table_client.query_entities(
                    filters_query=[("vendor_name", vendor_name)]
                )
                if vendors_list is None or len(vendors_list) == 0:
                    self.logger.info(f"Invoice {invoice_id} vendor not found; flagging for review")
                    invoice_obj.state = InvoiceState.MANUAL_REVIEW
                    validation_warnings.append(f"Vendor not found: {vendor_name}")
                    #do AI validation for unknown vendor
                    self.ai_validation_tool.validate_without_vendor(invoice_obj, validation_errors, validation_warnings)

                else:
                    # found vendor; perform deterministic validations. Use first match
                    vendor = Vendor.from_dict(vendors_list[0])
                    is_valid, errors, warnings = self.deterministic_validation_tool.validate(invoice_obj, vendor)
                    if not is_valid:
                        self.logger.warning(f"Invoice {invoice_id} failed deterministic validation")
                        invoice_obj.state = InvoiceState.FAILED
                        validation_errors.extend(errors)
                        validation_warnings.extend(warnings)

                    else:
                        # all deterministic validations passed
                        self.logger.info(f"Invoice {invoice_id} passed deterministic validation")
                        # Check AI validations
                        is_valid, errors, warnings = self.ai_validation_tool.validate_invoice(invoice_obj, vendor)
                        if not is_valid:
                            self.logger.warning(f"Invoice {invoice_id} failed AI validation")
                            invoice_obj.state = InvoiceState.FAILED
                            validation_errors.extend(errors)
                            validation_warnings.extend(warnings)
                        else:
                            self.logger.info(f"Invoice {invoice_id} passed AI validation")
                            invoice_obj.state = InvoiceState.VALIDATED

        
        invoice_obj.validation_flags = validation_warnings if validation_warnings else []
        invoice_obj.validation_errors = validation_errors if validation_errors else []
        invoice_obj.validation_passed = invoice_obj.state == InvoiceState.VALIDATED

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

    def has_duplicate(self, invoice: Invoice) -> bool:
        """Check if the invoice is a duplicate."""
        # Placeholder logic for duplicate check
        invoice_number = invoice.invoice_number
        vendor_name = invoice.vendor_name
        self.logger.info(f"Checking for duplicate invoice: {invoice_number} from vendor {vendor_name} (ID: {invoice_number})")

        entities = self.invoice_table_client.query_entities(
            filters_query=[
                ("invoice_number", invoice_number),
                ("vendor_name", vendor_name)
            ]
        )

        if entities and len(entities) > 0:
            self.logger.warning(f"Duplicate invoice found: {invoice_number} from vendor {vendor_name}")
            return True

        # No duplicate found
        return False

if __name__ == "__main__":
    agent = ValidationAgent()
    agent.initialize()
    agent.run()
