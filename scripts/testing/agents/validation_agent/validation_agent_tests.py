import argparse
import asyncio
from datetime import datetime, timezone

import json
import traceback
import uuid
from shared.config.settings import settings
from shared.models.vendor import Vendor
from shared.utils.logging_config import get_logger, setup_logging
from shared.models.invoice import DocumentType, Invoice, InvoiceSource
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from agents.validation_agent.tools.deterministic_validator import DeterministicValidator, ValidationResult

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)


class ValidationAgentTests:
    
    def setup_method(self):
        
        vendor_table=TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.vendors_table_name
            )
        
        invoice_table=TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.invoices_table_name
            )
        
        self.validator = DeterministicValidator(
            vendor_table=vendor_table,
            invoice_table=invoice_table            
        )

        invoice_path = "./scripts/poc/sample_documents/invoice_entity.json"
        with open(invoice_path, "r") as f:
            invoice_data = f.read()
            invoice_dict = json.loads(invoice_data)
            self.invoice = Invoice(**invoice_dict)

        vendor_path = "./scripts/poc/sample_documents/vendor_entity.json"
        with open(vendor_path, "r") as f:
            vendor_data = f.read()
            vendor_dict = json.loads(vendor_data)
            self.vendor = Vendor(**vendor_dict)

    async def teardown_method(self):
        await self.validator.vendor_table.close()
        await self.validator.invoice_table.close()
        await get_credential_manager().close()

    async def test_validate_invoice(self):

        self.invoice.vendor_name = self.vendor.name  # Ensure vendor name matches

        result, messages, matched_vendor = await self.validator.validate_invoice(self.invoice)
        print(f"Validation Result: {result}")
        print(f"Messages: {messages}")
        assert result == ValidationResult.VALID
        assert len(messages) == 0
        assert matched_vendor is not None
    
    async def test_false_duplicate_invoice(self):

        is_duplicate = await self.validator.has_duplicate(self.invoice)

        assert is_duplicate == False

    async def test_missing_vendor_name(self):

        invoice = self.invoice
        invoice.vendor_name = ""  # Simulate missing vendor name
        result, messages, matched_vendor = await self.validator.validate_invoice(invoice)
        assert result == ValidationResult.INVALID
        assert "Vendor name is missing in the invoice data" in messages

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Validation Agent Tests")
    args = parser.parse_args()

    test_suite = ValidationAgentTests()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        test_suite.setup_method()
        loop.run_until_complete(test_suite.test_validate_invoice())
        #loop.run_until_complete(test_suite.test_false_duplicate_invoice())
        #loop.run_until_complete(test_suite.test_missing_vendor_name())
        
    except Exception as e:
        logger.error(f"An error occurred during tests: {e}")
        traceback.print_exc()
    finally:
        loop.run_until_complete(test_suite.teardown_method())
        loop.close()