import json
import pytest
import pytest_asyncio
from shared.config.settings import settings
from agents.approval_agent.tools.approval_analytics_agent import ApprovalAnalyticsAgent


from shared.utils.logging_config import get_logger, setup_logging

setup_logging(log_level=settings.log_level,
                log_file=settings.log_file,
                log_to_console=settings.log_to_console)

logger = get_logger(__name__)

class TestApprovalAnalyticsAgent:

    @pytest_asyncio.fixture
    async def tool(self):
        agent = ApprovalAnalyticsAgent()
        yield agent

    @pytest_asyncio.fixture
    async def invoice(self):
        invoice_data_path = "scripts/data-source/invoices_data.json"
        logger.info(f"Loading invoice data from {invoice_data_path}")

        with open(invoice_data_path, "r") as f:
            invoices_data = json.load(f)

        return invoices_data[0]  # Use the first invoice for testing

    @pytest_asyncio.fixture
    async def budget(self):
        budget_data_path = "scripts/data-source/budgets_data.json"
        logger.info(f"Loading budget data from {budget_data_path}")
        with open(budget_data_path, "r") as f:
            budget_data = json.load(f)

        return budget_data[0]  # Use the first budget record for testing
    
    @pytest_asyncio.fixture
    async def vendor(self):
        vendor_data_path = "scripts/data-source/vendors_data.json"
        logger.info(f"Loading vendor data from {vendor_data_path}")
        with open(vendor_data_path, "r") as f:
            vendor_data = json.load(f)

        return vendor_data[0]  # Use the first vendor record for testing
    
    @pytest.mark.asyncio
    async def test_invoke(self, tool: ApprovalAnalyticsAgent, invoice: dict, budget: dict, vendor: dict):
        input_data = {
            "invoice": invoice,
            "budget": budget,
            "vendor": vendor
        }
        result = await tool.invoke(input_data)
        logger.info(f"Approval Analytics Agent Result: {result}")
        assert result is not None