import argparse
import json
import asyncio
from datetime import datetime, timezone
import uuid

from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from shared.config.settings import settings
from shared.models.vendor import Vendor
from shared.utils.logging_config import get_logger, setup_logging

from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)

json_filename = "scripts/data-source/vendors.json"

vendor_table_client = TableStorageService(storage_account_url=settings.table_storage_account_url,
                                           table_name=settings.vendors_table_name)

async def seed_vendors(vendor_table_client, vendors: list[Vendor]):
    """Seed vendors into the vendor table storage."""
    tasks = []
    vendor_ids = []
    
    for vendor in vendors:
        partition_key = "VENDOR"
        row_key = uuid.uuid4().hex[:12]
        vendor_ids.append((vendor.vendor_id, row_key))
        logger.info(f"Queuing vendor: {vendor.vendor_id} with Row Key: {row_key}")
        
        entity = vendor.to_dict()
        task = vendor_table_client.upsert_entity(
            entity=entity, 
            partition_key=partition_key, 
            row_key=row_key
        )
        tasks.append(task)
    
    # Wait for all operations and get results
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Log detailed results
    success_count = 0
    for (vendor_id, row_key), result in zip(vendor_ids, results):
        if isinstance(result, Exception):
            logger.error(f"Failed to seed vendor {vendor_id} ({row_key}): {result}")
        else:
            success_count += 1
            logger.debug(f"Successfully seeded vendor {vendor_id} ({row_key})")
    
    logger.info(f"Seeding complete: {success_count}/{len(vendors)} successful")
    return success_count == len(vendors)


async def close_clients():
    """Close any open clients."""
    if vendor_table_client:
        await vendor_table_client.close()

    await get_credential_manager().close()


async def main():
   
    with open(json_filename, "r") as f:
        vendors_data = json.load(f)
        vendors = [Vendor.from_dict(item) for item in vendors_data]
        completed = await seed_vendors(vendor_table_client, vendors)
        if completed:
            logger.info("Vendor seeding completed successfully.")
        
        else:
            logger.error("Vendor seeding failed.")

        await close_clients()

if __name__ == "__main__":
    asyncio.run(main())