import pytest
import pytest_asyncio

from shared.config.settings import settings
from agents.budget_agent.tools.budget_analytics_agent import BudgetAnalyticsAgent, get_historical_spending_data, get_invoices_by_vendor
from shared.utils.logging_config import get_logger, setup_logging

setup_logging(log_level=settings.log_level,
                log_file=settings.log_file,
                log_to_console=settings.log_to_console)

logger = get_logger(__name__)

@pytest.mark.asyncio(scope="class")
class TestBudgetAnalyticsAgent:

    @pytest_asyncio.fixture
    async def tool(self):
        agent = BudgetAnalyticsAgent()
        yield agent

    @pytest.fixture
    async def invoice(self):
        return {
            "invoice_id": "INV-1001",
            "amount": 1500.00,
            "department_id": "FIN",
            "category": "Consulting",
            "project_id": "PROJ-001",
            "vendor_name": "LINKSER S.A"
        }
    
    @pytest.fixture
    async def budget(self):
        return {
            "year": 2024,
            "total_budget": 50000.00,
            "spent_to_date": 20000.00
        }

    @pytest.mark.asyncio
    async def test_impact_analysis(self, tool: BudgetAnalyticsAgent, invoice: dict, budget: dict):
        logger.info("Testing BudgetAnalyticsAgent ainvoke method...")

        result = await tool.impact_analysis(invoice=invoice,budget=budget)

        logger.info(f"Budget Analytics Agent Result: {result}")
        assert result is not None

    @pytest.mark.asyncio
    async def test_trend_analysis(self, tool: BudgetAnalyticsAgent, invoice: dict, budget: dict):
        logger.info("Testing BudgetAnalyticsAgent trend_analysis method...")
        historical_spending = await get_historical_spending_data(
            department_id="FIN",
            category="Consulting",
            project_id="PROJ-002",
            budget_year=2024,
            months=12
        )

        vendor_invoices = await get_invoices_by_vendor(
            vendor_name="LINKSER S.A",
            months=12
        )

        result = await tool.trend_analysis(
            invoice=invoice,
            budget=budget,
            historical_spending=historical_spending,
            vendor_invoices=vendor_invoices
        )
        logger.info(f"Budget Trend Analysis Agent Result: {result}")
        assert result is not None

    @pytest.mark.asyncio
    async def test_anomaly_detection(self, tool: BudgetAnalyticsAgent, invoice: dict, budget:dict):
        logger.info("Testing BudgetAnalyticsAgent anomaly_detection method...")
    
        historical_spending = await get_historical_spending_data(
            department_id="FIN",
            category="Consulting",
            project_id="PROJ-003",
            budget_year=2024,
            months=12
        )

        vendor_invoices = await get_invoices_by_vendor(
            vendor_name="LINKSER S.A",
            months=12
        )

        result = await tool.anomaly_detection(
            invoice=invoice,
            budget=budget,
            historical_spending=historical_spending,
            vendor_invoices=vendor_invoices
        )
        logger.info(f"Budget Anomaly Detection Agent Result: {result}")
        assert result is not None

    @pytest.mark.asyncio
    async def test_contextual_analysis(self, tool: BudgetAnalyticsAgent, invoice: dict):
        logger.info("Testing BudgetAnalyticsAgent contextual_analysis method...")

        # Sample context data
        context = {
            "invoice": invoice,
            "budget_impact": {
                "impact": "Moderate",
                "reasoning": "The invoice amount is within budget but higher than average monthly spending."
            },
            "trend_analysis": {
                "trend": "Increasing",
                "reasoning": "The vendor's invoices have been steadily increasing over the past year."
            },
            "anomaly_detection": {
                "anomaly": "None detected",
                "reasoning": "The invoice aligns with historical spending patterns."
            }
        }

        result = await tool.contextual_analysis(context=context)
        logger.info(f"Budget Contextual Analysis Agent Result: {result}")
        assert result is not None
