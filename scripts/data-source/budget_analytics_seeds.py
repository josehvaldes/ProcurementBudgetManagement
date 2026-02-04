import asyncio
import json
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.config.settings import settings
from shared.utils.logging_config import get_logger, setup_logging

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)
async def seed_budget_analytics(analytics_data: list[dict]):
    """Seed budget analytics data into the budget_analytics table storage."""
    tasks = []
    logger.info(f"Starting to seed {len(analytics_data)} budget analytics records into Table Storage.")
    async with TableStorageService(storage_account_url=settings.table_storage_account_url,
                                   table_name=settings.budget_analytics_table_name,
                                   standalone=True) as budget_analytics_table_client:

        for record in analytics_data:  # Limit to first 2 records for testing
            partition_key = record["PartitionKey"]
            row_key = record["RowKey"]

            logger.info(f"Queuing budget analytics record: {row_key} with Partition Key: {partition_key}")
            entity = record
            task = budget_analytics_table_client.upsert_entity(
                entity=entity, 
                partition_key=partition_key, 
                row_key=row_key
            )
            tasks.append(task)
        
        # Wait for all operations and get results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log detailed results
        success_count = 0
        for record, result in zip(analytics_data, results):
            row_key = record["RowKey"]
            if isinstance(result, Exception):
                logger.error(f"Failed to seed budget analytics record ({row_key}): {result}")
            else:
                success_count += 1
                logger.debug(f"Successfully seeded budget analytics record ({row_key})")
        
        logger.info(f"Seeding complete: {success_count}/{len(analytics_data)} successful")
    
    return success_count == len(analytics_data)


async def main():
    """Main function to load budget analytics data from JSON and seed into Table Storage."""
    filename = "scripts/data-source/budget_analytics_data.json"
    logger.info(f"Loading budget analytics data from {filename}")
    with open(filename, 'r') as f:
        analytics_data = json.load(f)
    
    success = await seed_budget_analytics(analytics_data)
    if success:
        logger.info("All budget analytics data seeded successfully.")
    else:
        logger.warning("Some budget analytics data failed to seed.")


if __name__ == "__main__":
    asyncio.run(main())