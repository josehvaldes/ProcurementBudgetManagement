import pytest

from shared.config.settings import settings
from agents.budget_agent.tools.budget_analytics_agent import get_historical_spending_data, get_invoices_by_vendor
from shared.utils.logging_config import get_logger, setup_logging

setup_logging(log_level=settings.log_level,
                log_file=settings.log_file,
                log_to_console=settings.log_to_console)

logger = get_logger(__name__)

class TestBudgetAnalyticsTools:

    @pytest.mark.asyncio
    async def test_get_historical_spending_data(self):
        
        logger.info("Testing get_historical_spending_data tool...")
        data = await get_historical_spending_data(
            department_id = "FIN",
            category = "Consulting",
            project_id = "PROJ-001",
            budget_year = 2024,
            months = 12
        )
        logger.info(f"Historical Spending Data: {data}")
        assert data is not None
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_get_invoices_by_vendor(self):
        
        logger.info("Testing get_invoices_by_vendor tool...")

        data = await get_invoices_by_vendor(
            vendor_name = "Adventure Logistics",
            months = 12
        )
        logger.info(f"Invoices by Vendor Data: {data}")
        assert data is not None
        assert len(data) > 0
