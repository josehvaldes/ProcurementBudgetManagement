import asyncio
import json
import uuid
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.config.settings import settings
from shared.models.budget import Budget
from shared.utils.logging_config import get_logger, setup_logging

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)


async def seed_budgets(budgets: list[Budget]):
    """Seed budgets into the budget table storage."""
    tasks = []
    budget_ids = []
    logger.info(f"Starting to seed {len(budgets)} budgets into Table Storage.")
    async with TableStorageService(storage_account_url=settings.table_storage_account_url,
                                   table_name=settings.budgets_table_name,
                                   standalone=True) as budget_table_client:

        for budget in budgets:
            partition_key = budget.fiscal_year
            # RowKey
            # {department_id}:{project_id}:{category}
            # IT:PROJ-3001:Software
            row_key = f"{budget.department_id}:{budget.project_id}:{budget.category}"

            budget.budget_id = uuid.uuid4().hex[:8]
            budget.compound_key = row_key
            budget_ids.append((budget.budget_id, row_key))
            logger.info(f"Queuing budget: {budget.compound_key} with Partition Key: {partition_key}")
            print(f"{budget.budget_id} - {partition_key} - {row_key}")
            entity = budget.to_dict()
            task = budget_table_client.upsert_entity(
                entity=entity, 
                partition_key=partition_key, 
                row_key=row_key
            )
            tasks.append(task)
        
        # Wait for all operations and get results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log detailed results
        success_count = 0
        for (budget_id, row_key), result in zip(budget_ids, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to seed budget {budget_id} ({row_key}): {result}")
            else:
                success_count += 1
                logger.debug(f"Successfully seeded budget {budget_id} ({row_key})")
        
        logger.info(f"Seeding complete: {success_count}/{len(budgets)} successful")
    
    return success_count == len(budgets)

async def main():
    json_filename = "scripts/data-source/budgets.json"
    with open(json_filename, "r") as f:
        budgets_data = json.load(f)
        budgets = [Budget.from_dict(item) for item in budgets_data]
        await seed_budgets(budgets)

if __name__ == "__main__":
    asyncio.run(main())