import pytest

from agents.budget_agent.tools.budget_classification_agent import BudgetClassificationAgent
from shared.config.settings import settings
from shared.utils.logging_config import get_logger, setup_logging

setup_logging(log_level=settings.log_level,
                log_file=settings.log_file,
                log_to_console=settings.log_to_console)

logger = get_logger(__name__)

class TestBudgetClassificationAgent:
    
    @pytest.fixture
    def tool(self):
        """Create a BudgetClassificationAgent instance."""
        agent = BudgetClassificationAgent()
        return agent


    @pytest.mark.asyncio
    async def test_budget_classification(self, tool):
        agent: BudgetClassificationAgent = tool
        input_data = {
            "invoice": {
                "description": "Purchase of software licenses",
                "vendor": "Software Co.",
                "amount": 1000,
                "department_id": "IT",
                "category": "Software"
            }
        }
        logger.info("Testing budget classification agent...")
        
        result = await agent.ainvoke(input_data)
        logger.info(f"Classification Result: {result}")
        assert result is not None
        assert result.department == "IT"
        assert result.category == "Software"
        assert result.confidence > 0.8

    @pytest.mark.asyncio
    async def test_failed_budget_classification(self, tool):
        agent: BudgetClassificationAgent = tool
        input_data = {
            "invoice": {
                "invoice_id": "INV-2024-003",
                "department_id": "FIN",
                "vendor_name": "Unknown Vendor",
                "amount": "5000.00",
                "state": "FAILED",
                "rejection_reason": "Vendor validation failed"
            }
        }
        logger.info("Testing failed budget classification agent...")
        result = await agent.ainvoke(input_data)
        logger.info(f"Classification Result: {result}")
        assert result is not None
        #assert result.get('errors', None) is not None
