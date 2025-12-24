import traceback
import uuid
from azure.data.tables.aio import TableClient

from shared.config.settings import settings
from shared.utils.logging_config import get_logger
from shared.models.invoice import Invoice
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from invoice_lifecycle_api.application.interfaces.service_interfaces import TableServiceInterface


logger = get_logger(__name__)

AZURE_TABLE_METADATA_FIELDS = {'PartitionKey', 'RowKey', 'Timestamp', 'etag', 'odata.etag', 'odata.metadata'}

class TableStorageService(TableServiceInterface):
    
    def __init__(self, storage_account_url: str = None, table_name: str = None):
        
        self.account_url = storage_account_url or settings.table_storage_account_url
        self.table_name = table_name or settings.invoices_table_name

        credential_manager = get_credential_manager()
        self.table_client = TableClient(
            endpoint=self.account_url,
            table_name=self.table_name,
            credential=credential_manager.get_credential()
        )

    async def upsert_entity(self, entity: dict, partition_key: str, row_key: str) -> str:
        """Save an entity to the Azure Table Storage."""
        logger.info("Saving entity to Azure Table Storage...")
        try:
            entity["PartitionKey"] = partition_key
            entity["RowKey"] = row_key

            _ = await self.table_client.upsert_entity(entity=entity)
            logger.info(f"Entity saved successfully. Row Key: {row_key}")
            return row_key
        except Exception as e:
            logger.error(f"Error saving entity to Table Storage: {e}")
            return ""

    async def get_entity(self, partition_key: str, row_key: str) -> dict | None:
        """Retrieve entity data from Azure Table Storage by entity ID."""

        try:
            entity = await self.table_client.get_entity(partition_key=partition_key, row_key=row_key)
            logger.info(f"Entity retrieved successfully. Row Key: {row_key}")
            return self._strip_metadata(dict(entity))
        except Exception as e:
            logger.error(f"Error retrieving entity from Table Storage: {e}")
            return None

    async def delete_entity(self, partition_key: str, row_key: str) -> None:
        """Delete entity data from Azure Table Storage by entity ID."""
        try:
            await self.table_client.delete_entity(partition_key=partition_key, row_key=row_key)
            logger.info(f"Entity deleted successfully. Row Key: {row_key}")
        except Exception as e:
            logger.error(f"Error deleting entity from Table Storage: {e}")

    async def close(self) -> None:
        """Close the Table Storage client."""
        if self.table_client:
            await self.table_client.close()
            logger.info("Table Storage client closed.")

    def _strip_metadata(self, entity: dict) -> dict:
        """Remove Azure Table Storage metadata fields."""
        return {k: v for k, v in entity.items() if k not in AZURE_TABLE_METADATA_FIELDS}
   