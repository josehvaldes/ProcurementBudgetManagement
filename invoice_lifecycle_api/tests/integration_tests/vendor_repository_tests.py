import argparse
import asyncio
from datetime import datetime, timezone

import json
import traceback
import uuid

from shared.config.settings import settings
from shared.models.vendor import Vendor
from shared.utils.logging_config import get_logger, setup_logging
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from invoice_lifecycle_api.application.interfaces.service_interfaces import JoinOperator, TableServiceInterface

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)

class VendorRepositoryTests:
    def setup_method(self):
        self.vendor_repository: TableServiceInterface = TableStorageService(
            storage_account_url=settings.table_storage_account_url,
            table_name=settings.vendors_table_name,
            standalone=True
        )

    async def teardown_method(self):
        await self.vendor_repository.close()

    async def test_query_entities_OR_size_2(self):
        try:
            filters = [("name", "Contoso Supplies"), ("name", "Adventure Logistics")]
            entities = await self.vendor_repository.query_entities(filters, join_operator=JoinOperator.OR)
            for entity in entities:
                vendor: Vendor = Vendor.from_dict(entity)
                logger.info(f" - {vendor}")
            assert len(entities) == 2
        except Exception as e:
            logger.error(f"Error querying entities: {e}")
            traceback.print_exc()

    async def save_to_file_entity(self):
        try:
                        # vendor
            vendor_file_path = "./scripts/poc/sample_documents/vendor_entity.json"
            vendor_partition_key = "VENDOR"
            vendor_row_key = "4eda3a25a6b9"
            logger.info(f"Saving vendor entity to file: {vendor_partition_key}, Row Key: {vendor_row_key}")
            vendor_entity = await self.vendor_repository.get_entity(vendor_partition_key, vendor_row_key)
            with open(vendor_file_path, "w") as f:
                f.write(json.dumps(vendor_entity, indent=4, default=str))
            logger.info(f"Vendor entity saved to file: {vendor_file_path}")
        except Exception as e:
            logger.error(f"Error saving vendor entity to file: {e}")
            traceback.print_exc()

    async def test_query_entities_AND_size_1(self):
        try:
            filters = [("contact_name", "Carol Martinez"), ("name", "Adventure Logistics")]
            entities = await self.vendor_repository.query_entities(filters, join_operator=JoinOperator.AND)
            for entity in entities:
                vendor: Vendor = Vendor.from_dict(entity)
                logger.info(f" - {vendor}")
            assert len(entities) == 1
        except Exception as e:
            logger.error(f"Error querying entities: {e}")
            traceback.print_exc()

    async def test_query_entities(self):
        try:
            filters = [("name", "Contoso Supplies")]
            entities = await self.vendor_repository.query_entities(filters)
            for entity in entities:
                vendor: Vendor = Vendor.from_dict(entity)
                logger.info(f" - {vendor}")
            assert len(entities) == 1
        except Exception as e:
            logger.error(f"Error querying entities: {e}")
            traceback.print_exc()




async def main():
    """Main async entry point for running tests."""
    test_instance = VendorRepositoryTests()
    test_instance.setup_method()

    parser = argparse.ArgumentParser(description="Azure Storage Repository Service Tests")
    parser.add_argument("action", type=str, help="Action to perform: query, query_and_1, query_or_2, save",
                       choices=["query", "query_and_1", "query_or_2", "save"])
    args = parser.parse_args()
    
    logger.info(f"Running test for action: {args.action}")
    
    # Map actions to test methods
    test_map = {
        "query": test_instance.test_query_entities,
        "query_and_1": test_instance.test_query_entities_AND_size_1,
        "query_or_2": test_instance.test_query_entities_OR_size_2,
        "save": test_instance.save_to_file_entity,
    }
    
    tasks = []
    # Run the selected test
    test_method = test_map.get(args.action)
    if test_method:
        tasks.append(test_method())

    await asyncio.gather(*tasks)

    await test_instance.teardown_method()

if __name__ == "__main__":
    asyncio.run(main())

