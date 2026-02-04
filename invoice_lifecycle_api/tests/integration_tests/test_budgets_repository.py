import pytest
import pytest_asyncio

from shared.config.settings import settings
from shared.models.budget import Budget
from shared.utils.constants import CompoundKeyStructure
from shared.utils.logging_config import get_logger, setup_logging
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from invoice_lifecycle_api.application.interfaces.service_interfaces import JoinOperator, TableServiceInterface

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)

@pytest.mark.asyncio(scope="class")
class TestBudgetsRepository:

    @pytest_asyncio.fixture
    async def tool(self):
        self.budget_repository: TableServiceInterface = TableStorageService(
            storage_account_url=settings.table_storage_account_url,
            table_name=settings.budgets_table_name, standalone=True
        )
        yield self.budget_repository
        await self.budget_repository.close()

    @pytest.mark.asyncio
    async def test_query_single_entity(self, tool: TableServiceInterface):
        logger.info("Testing single entity query for IT-1 department, PROJ-2026, Software category in FY2026")
        row_key = "IT:PROJ-2026:Software"
        filters = [("PartitionKey", "FY2026"), ("RowKey", row_key)]
        entities = await tool.query_entities(filters, join_operator=JoinOperator.AND)
        for entity in entities:
            budget: Budget = Budget.from_dict(entity)
            logger.info(f" - {budget}")
        assert len(entities) == 1

    @pytest.mark.asyncio
    async def test_query_lt_gt_filter_unique(self, tool: TableServiceInterface):
        logger.info("Testing lt/gt filters to query budgets for Advertising category in FY2026")
        compound_key = f"IT{CompoundKeyStructure.LOWER_BOUND.value}PROJ01-2026{CompoundKeyStructure.LOWER_BOUND.value}Software"
        entities = await tool.query_compound_key("FY2026", compound_key)
        for entity in entities:
            budget: Budget = Budget.from_dict(entity)
            logger.info(f" - {budget}")
        assert len(entities) == 1

    @pytest.mark.asyncio
    async def test_query_lt_gt_filter_no_category(self, tool: TableServiceInterface):
        logger.info("Testing lt/gt filters to query budgets for Software and Training category in FY2026")
        compound_key = f"FIN{CompoundKeyStructure.LOWER_BOUND.value}PROJ03-2025"
        entities = await tool.query_compound_key("FY2025", compound_key)  # exclude category
        for entity in entities:
            budget: Budget = Budget.from_dict(entity)
            logger.info(f" - {budget}")
        assert len(entities) >= 1
