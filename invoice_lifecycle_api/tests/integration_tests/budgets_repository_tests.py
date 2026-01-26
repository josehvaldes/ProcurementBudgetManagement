import argparse
import asyncio
from datetime import datetime, timezone

import json
import traceback
import uuid

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


class BudgetsRepositoryTests:
    def setup_method(self):
        self.budget_repository: TableServiceInterface = TableStorageService(
            storage_account_url=settings.table_storage_account_url,
            table_name=settings.budgets_table_name, standalone=True
        )

    async def teardown_method(self):
        await self.budget_repository.close()

    async def test_query_single_entity(self):
        try:
            logger.info("Testing single entity query for IT-1 department, PROJ-2026, Software category in FY2026")
            row_key = "IT:PROJ-2026:Software"
            filters = [("PartitionKey", "FY2026"), ("RowKey", row_key)]
            entities = await self.budget_repository.query_entities(filters, join_operator=JoinOperator.AND)
            for entity in entities:
                budget: Budget = Budget.from_dict(entity)
                logger.info(f" - {budget}")
            assert len(entities) == 1
        except Exception as e:
            logger.error(f"Error querying entities: {e}")
            traceback.print_exc()

    async def test_query_lt_gt_filter_unique(self):
        try:
            logger.info("Testing lt/gt filters to query budgets for Advertising category in FY2026")
            compound_key = f"IT{CompoundKeyStructure.LOWER_BOUND.value}PROJ01-2026{CompoundKeyStructure.LOWER_BOUND.value}Software"
            entities = await self.budget_repository.query_compound_key("FY2026", compound_key)
            for entity in entities:
                budget: Budget = Budget.from_dict(entity)
                logger.info(f" - {budget}")
            assert len(entities) == 1
        except Exception as e:
            logger.error(f"Error querying entities with lt/gt filters: {e}")
            traceback.print_exc()

    async def test_query_lt_gt_filter_no_category(self):
        try:
            logger.info("Testing lt/gt filters to query budgets for Software and Training category in FY2026")
            compound_key = f"FIN{CompoundKeyStructure.LOWER_BOUND.value}PROJ03-2025"
            entities = await self.budget_repository.query_compound_key("FY2025", compound_key)  # exclude category
            for entity in entities:
                budget: Budget = Budget.from_dict(entity)
                logger.info(f" - {budget}")
            assert len(entities) >= 1
        except Exception as e:
            logger.error(f"Error querying entities with lt/gt filters: {e}")
            traceback.print_exc()

async def main():
    test_suite = BudgetsRepositoryTests()
    test_suite.setup_method()
    try:
        
        parser = argparse.ArgumentParser(description="Azure Storage Repository Service Tests")
        parser.add_argument("action", type=str, help="Action to perform: query",
                        choices=["query", "lt_gt_filter", "lt_gt_filter_no_cat"])
        args = parser.parse_args()
        
        logger.info(f"Running test for action: {args.action}")
        
        # Map actions to test methods
        test_map = {
            "query": test_suite.test_query_single_entity,
            "lt_gt_filter": test_suite.test_query_lt_gt_filter_unique,
            "lt_gt_filter_no_cat": test_suite.test_query_lt_gt_filter_no_category,
        }
        tasks = []
        # Run the selected test
        test_method = test_map.get(args.action)
        if test_method:
           tasks.append(test_method())
        await asyncio.gather(*tasks)

    finally:
        await test_suite.teardown_method()

if __name__ == "__main__":
    asyncio.run(main())

