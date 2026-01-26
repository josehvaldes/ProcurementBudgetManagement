import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, mock_open, patch

from agents.budget_agent.tools.budget_analytics_agent import get_historical_spending_data
from shared.config.settings import settings
from shared.utils.logging_config import get_logger, setup_logging

setup_logging(log_level=settings.log_level,
                log_file=settings.log_file,
                log_to_console=settings.log_to_console)

logger = get_logger(__name__)


class TestBudgetAnalyticsAgent:

    @pytest.mark.asyncio
    async def test_get_historical_spending_data(self):
        
        logger.info("Testing get_historical_spending_data tool...")
        data = await get_historical_spending_data.ainvoke({
            "department_id": "FINANCE",
            "category": "Consulting",
            "project_id": "PROJ-001",
            "budget_year": 2024,
            "months": 12
        })
        logger.info(f"Historical Spending Data: {data}")
        assert data is not None
        assert len(data) > 0