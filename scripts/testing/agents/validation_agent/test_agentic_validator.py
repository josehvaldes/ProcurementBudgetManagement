import asyncio
import json

import pytest

from agents.validation_agent.tools.agentic_validator import AgenticValidator
from shared.models.agentic import AgenticResponse
from shared.models.invoice import Invoice
from shared.models.vendor import Vendor


class TestAgenticValidator:
    
    #@pytest.fixture
    def invoice(self):
        """Load invoice test data."""
        invoice_path = "./scripts/poc/sample_documents/invoice_entity.json"
        with open(invoice_path, "r") as f:
            invoice_data = json.load(f)
            return invoice_data
        
    #@pytest.fixture
    def vendor(self):
        """Load vendor test data."""
        vendor_path = "./scripts/poc/sample_documents/vendor_entity.json"
        with open(vendor_path, "r") as f:
            vendor_data = json.load(f)
            return vendor_data
    
    #@pytest.fixture
    def validator(self):
        """Create a mock AI validation tool."""
        validator = AgenticValidator()
        return validator

    #@pytest.mark.asyncio
    async def test_valid_invoice(self, validator, invoice, vendor):
        # Add assertions to validate the invoice and vendor data
        print("Testing invalid invoice...")
        response: AgenticResponse = await validator.ainvoke({
            "invoice": invoice,
            "vendor": vendor
        })

        print(f"is_valid: {response.passed}")
        if len(response.errors) > 0 or len(response.recommended_actions) > 0:
            print(f"Errors: {response.errors}")
            print(f"Recommended Actions: {response.recommended_actions}")

        assert response.passed == True
        assert len(response.errors) == 0



async def main():
    test_instance = TestAgenticValidator()
    tasks = []
    tasks.append(test_instance.test_valid_invoice(
        test_instance.validator(),
        test_instance.invoice(),
        test_instance.vendor()
    ))
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    #pytest.main(["-v", __file__])
    # run manually
    test_instance = TestAgenticValidator()
    asyncio.run(main())
