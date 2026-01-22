import argparse
import asyncio
from datetime import datetime, timezone

import json
import traceback
import uuid

from shared.config.settings import settings
from shared.utils.logging_config import get_logger, setup_logging
from shared.models.invoice import DocumentType, Invoice, InvoiceSource
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from invoice_lifecycle_api.infrastructure.repositories.invoice_storage_service import InvoiceStorageService
from invoice_lifecycle_api.application.interfaces.service_interfaces import JoinOperator, StorageServiceInterface, TableServiceInterface

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)

class InvoiceRepositoryTests:
    def setup_method(self):
        self.invoice_repository: TableServiceInterface = TableStorageService(
            storage_account_url=settings.table_storage_account_url,
            table_name=settings.invoices_table_name,
            standalone=True
        )
        self.blob_repository: StorageServiceInterface = InvoiceStorageService()


    async def test_upsert_entity(self):
        invoice = Invoice(
            invoice_id=uuid.uuid4().hex[:12],
            department_id=f"dept_{uuid.uuid4().hex[:6]}",
            invoice_number=f"INV-{uuid.uuid4().hex[:6]}",
            source=InvoiceSource.API,
            document_type=DocumentType.INVOICE,
            source_email=f"test@test.com",
            priority="high",
            file_name="invoice.pdf",
            file_type="application/pdf",
            created_date=datetime.now(timezone.utc),
            raw_file_url="https://examplestorage.blob.core.windows.net/invoices/invoice.pdf",
            raw_file_blob_name="invoices/invoice.pdf",
            file_size=204800,
            file_uploaded_at=datetime.now(timezone.utc),
            has_po=False
            )
        entity_dict = invoice.to_dict()
        id = await self.invoice_repository.upsert_entity(entity_dict, invoice.department_id, invoice.invoice_id)
        print(f"Saved invoice : {entity_dict}")
        assert id is not None
    
    async def test_upload_file_as_bytes(self):
        file_path_low_q = "./scripts/poc/sample_documents/receipts/VALDES_251216_image.jpg"
        with open(file_path_low_q, "rb") as f:
            file_content = f.read()
        
        today = datetime.now()
        blob_name = f"{today.year}/{today.month}/{today.day}/VALDES_251216_image.jpg"
        print(f"Uploading blob with name: {blob_name}, {len(file_content)} bytes")
        print(f"Azure Blob Storage Account URL: {settings.blob_storage_account_url}")
        blob_url = await self.blob_repository.upload_file_as_bytes(file_content, blob_name)
        print(f"Uploaded blob URL: {blob_url}")
        assert blob_url is not None
        assert blob_name in blob_url

    async def test_download_file(self):
        blob_name = f"2025/12/22/invoice_3c4a78652c62.jpg"
        container_name = settings.blob_container_name
        print(f"Downloading blob with name: {blob_name}")
        downloaded_content = await self.blob_repository.download_file(container_name, blob_name)
        print(f"Downloaded blob content length: {len(downloaded_content)} bytes")

        assert downloaded_content is not None
        assert len(downloaded_content) > 0
        with open("./scripts/poc/sample_documents/receipts/received_invoice_3c4a78652c62.jpg", "wb") as f:
            f.write(downloaded_content)

    async def test_delete_file(self):
        container_name = settings.blob_container_name
        blob_name = f"2025/12/22/invoice_3c4a78652c62.jpg"
        print(f"Deleting blob with name: {blob_name}")
        await self.blob_repository.delete_file(container_name, blob_name)
        print(f"Deleted blob: {blob_name}")


    async def test_get_entity(self):
        try:
            partition_key = "dept_8d6014"
            row_key = "d7224a169011"
            print(f"Retrieving entity with Partition Key: {partition_key}, Row Key: {row_key}")
            entity = await self.invoice_repository.get_entity(partition_key, row_key)
            invoice: Invoice = Invoice.from_dict(entity) if entity else None
            if invoice:
                print(f"Retrieved entity: {invoice}")
            else:
                print("Entity not found.")
        except Exception as e:
            print(f"Error retrieving entity: {e}")
            traceback.print_exc()

    async def save_to_file_entity(self):
        try:
            file_path = "./scripts/poc/sample_documents/invoice_entity.json"
            partition_key = "kitchen-01"
            row_key = "96686795c22a"
            logger.info(f"Saving entity to file: {partition_key}, Row Key: {row_key}")
            entity = await self.invoice_repository.get_entity(partition_key, row_key)
            with open(file_path, "w") as f:
                f.write(json.dumps(entity, indent=4, default=str))
            logger.info(f"Entity saved to file: {file_path}")

        except Exception as e:
            logger.error(f"Error saving entity to file: {e}")
            traceback.print_exc()

    async def close_repositories(self):
        
        tasks = []

        tasks.append(self.invoice_repository.close())
        tasks.append(self.blob_repository.close())

        results = await asyncio.gather(*tasks)
        logger.info("Closed all repository services and credential manager.")

    async def teardown_method(self):
        await self.close_repositories()


async def main():
    """Main async entry point for running tests."""
    test_instance = InvoiceRepositoryTests()
    test_instance.setup_method()

    parser = argparse.ArgumentParser(description="Azure Storage Repository Service Tests")
    parser.add_argument("action", type=str, help="Action to perform: upsert, upload, download, delete, get_entity, save",
                       choices=["upsert", "upload", "download", "delete", "get_entity", "save"])
    args = parser.parse_args()
    
    logger.info(f"Running test for action: {args.action}")
    
    # Map actions to test methods
    test_map = {
        "upsert": test_instance.test_upsert_entity,
        "upload": test_instance.test_upload_file_as_bytes,
        "download": test_instance.test_download_file,
        "delete": test_instance.test_delete_file,
        "get_entity": test_instance.test_get_entity,
        "save": test_instance.save_to_file_entity,
    }
    
    tasks = []
    # Run the selected test
    test_method = test_map.get(args.action)
    if test_method:
        tasks.append(test_method())

    await asyncio.gather(*tasks)

    await test_instance.close_repositories()

if __name__ == "__main__":
    asyncio.run(main())

