import pytest
import pytest_asyncio

import json

from shared.config.settings import settings
from shared.models.vendor import Vendor
from shared.utils.logging_config import get_logger, setup_logging
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from invoice_lifecycle_api.application.interfaces.service_interfaces import CompareOperator, JoinOperator, TableServiceInterface

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)

@pytest.mark.asyncio(scope="class")
class TestVendorRepository:
    
    @pytest_asyncio.fixture
    async def tool(self):
        vendor_repository: TableServiceInterface = TableStorageService(
            storage_account_url=settings.table_storage_account_url,
            table_name=settings.vendors_table_name,
            standalone=True
        )
        yield vendor_repository
        await vendor_repository.close()
    
    @pytest.mark.asyncio
    async def test_query_entities_OR_size_2(self, tool: TableServiceInterface):
        filters = [("name", "Contoso Supplies"), ("name", "Adventure Logistics")]
        entities = await tool.query_entities(filters, join_operator=JoinOperator.OR)
        for entity in entities:
            vendor: Vendor = Vendor.from_dict(entity)
            logger.info(f" - {vendor}")
        assert len(entities) == 2


    @pytest.mark.asyncio
    async def save_to_file_entity(self, tool: TableServiceInterface):
        # vendor
        vendor_file_path = "./scripts/poc/sample_documents/vendor_entity.json"
        vendor_partition_key = "VENDOR"
        vendor_row_key = "4eda3a25a6b9"
        logger.info(f"Saving vendor entity to file: {vendor_partition_key}, Row Key: {vendor_row_key}")
        vendor_entity = await tool.get_entity(vendor_partition_key, vendor_row_key)
        with open(vendor_file_path, "w") as f:
            f.write(json.dumps(vendor_entity, indent=4, default=str))
        logger.info(f"Vendor entity saved to file: {vendor_file_path}")

    
    @pytest.mark.asyncio
    async def test_query_entities_AND_size_1(self, tool: TableServiceInterface):
        filters = [("contact_name", "Carol Martinez"), ("name", "Adventure Logistics")]
        entities = await tool.query_entities(filters, join_operator=JoinOperator.AND)
        for entity in entities:
            vendor: Vendor = Vendor.from_dict(entity)
            logger.info(f" - {vendor}")
        assert len(entities) == 1

    @pytest.mark.asyncio
    async def test_query_entities(self, tool):
        table: TableServiceInterface = tool
        filters = [("name", "LINKSER S.A")]
        entities = await table.query_entities(filters)
        for entity in entities:
            vendor: Vendor = Vendor.from_dict(entity)
            logger.info(f" - {vendor}")
        assert len(entities) == 1
        
    @pytest.mark.asyncio
    async def test_query_entities_with_filter(self, tool):
        table: TableServiceInterface = tool
        filters = [("name", "LINKSER S.A", CompareOperator.EQUAL.value),
                    ("suspended", True, CompareOperator.NOT_EQUAL.value)]
        entities = await table.query_entities_with_filters(filters)
        for entity in entities:
            vendor: Vendor = Vendor.from_dict(entity)
            logger.info(f" - {vendor}")
        assert len(entities) == 1
    