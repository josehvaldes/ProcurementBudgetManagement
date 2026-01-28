import asyncio
import json
from shared.config.settings import settings
from shared.models.invoice import Invoice
from shared.utils.logging_config import get_logger, setup_logging
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)



async def download_invoices():

    async with TableStorageService(
        storage_account_url=settings.table_storage_account_url,
        table_name=settings.invoices_table_name,
        standalone=True
    ) as table_service:
        print("Downloading invoices...")
        entity = await table_service.get_entity(
            partition_key="HR",
            row_key="ddff341ba6b7"
        )
        
        if entity is None:
            print("No entity found.")
            return
        obj = Invoice.from_dict(entity)
        print("formatted:")
        print( json.dumps(obj.to_dict(), indent=4, default=str) )

async def seed_invoices(invoices_data: list[dict]):
    """Seed invoice data into the invoices table storage."""
    tasks = []
    logger.info(f"Starting to seed {len(invoices_data)} invoice records into Table Storage.")
    async with TableStorageService(storage_account_url=settings.table_storage_account_url,
                                   table_name=settings.invoices_table_name,
                                   standalone=True) as invoices_table_client:

        for record in invoices_data:
            partition_key = record["department_id"]
            row_key = record["invoice_id"]
            logger.info(f"Queuing invoice record: {row_key} with Partition Key: {partition_key}")
            # Convert dict to Invoice model and back to ensure proper formatting
            invoice = Invoice.from_dict(record)
            entity = invoice.to_dict()
            task = invoices_table_client.upsert_entity(
                entity=entity, 
                partition_key=partition_key, 
                row_key=row_key
            )
            tasks.append(task)
        
        # Wait for all operations and get results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log detailed results
        success_count = 0
        for record, result in zip(invoices_data, results):
            row_key = record["invoice_id"]
            if isinstance(result, Exception):
                logger.error(f"Failed to seed invoice record ({row_key}): {result}")
            else:
                success_count += 1
                logger.debug(f"Successfully seeded invoice record ({row_key})")
        
        logger.info(f"Seeding complete: {success_count}/{len(invoices_data)} successful")
    
    return success_count == len(invoices_data)

async def main():
    """Main function to load invoice data from JSON and seed into Table Storage."""
    filename = "scripts/data-source/invoices_data.json"
    logger.info(f"Loading invoice data from {filename}")
    with open(filename, 'r') as f:
        invoices_data = json.load(f)
    
    success = await seed_invoices(invoices_data)
    if success:
        logger.info("All invoice data seeded successfully.")
    else:
        logger.warning("Some invoice data failed to seed.")


if __name__ == "__main__":
    asyncio.run(main())
    # asyncio.run(download_invoices())