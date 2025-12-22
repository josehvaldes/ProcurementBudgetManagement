import json
import os
import traceback
import uuid
from azure.data.tables.aio import TableClient

from shared.config.settings import settings
from shared.utils.logging_config import get_logger
from shared.models.invoice import Invoice
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from invoice_lifecycle_api.application.interfaces.service_interfaces import TableServiceInterface


logger = get_logger(__name__)

class TableStorageService(TableServiceInterface):
    
    def __init__(self):
        self.table_name = settings.invoices_table_name
        self.account_url = settings.azure_storage_account_url
        credential_manager = get_credential_manager()
        self.table_client = TableClient(
            endpoint=self.account_url,
            table_name=self.table_name,
            credential=credential_manager.get_credential()
        )


    async def save_invoice(self, invoice_data: Invoice) -> str:
        """Save invoice data to the Azure Table Storage."""
        logger.info("Saving invoice to Azure Table Storage...")
        try:
            entity = invoice_data.to_dict()
            entity["PartitionKey"] = invoice_data.department_id
            entity["RowKey"] = invoice_data.invoice_id or uuid.uuid4().hex[:12]

            _ = await self.table_client.upsert_entity(entity=entity)
            logger.info(f"Invoice saved successfully. Invoice ID: {entity.get('invoice_id')}")
            return entity.get("invoice_id", "")
        except Exception as e:
            logger.error(f"Error saving invoice to Table Storage: {e}")
            traceback.print_exc()
            return ""

    async def get_invoice(self, invoice_id: str, department_id: str) -> Invoice | None:
        """Retrieve invoice data from Azure Table Storage by invoice ID."""
        pass
    
    async def delete_invoice(self, invoice_id: str, department_id: str) -> None:
        """Delete invoice data from Azure Table Storage by invoice ID."""
        pass

    async def close(self) -> None:
        """Close the Table Storage client."""
        if self.table_client:
            await self.table_client.close()
            logger.info("Table Storage client closed.")