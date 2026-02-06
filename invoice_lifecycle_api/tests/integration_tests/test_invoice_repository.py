import pytest
import pytest_asyncio

from datetime import datetime, timezone

import json
import uuid

from shared.config.settings import settings
from shared.utils.exceptions import EntityNotFoundException
from shared.utils.logging_config import get_logger, setup_logging
from shared.models.invoice import DocumentType, Invoice, InvoiceSource
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from invoice_lifecycle_api.infrastructure.repositories.invoice_storage_service import InvoiceStorageService
from invoice_lifecycle_api.application.interfaces.service_interfaces import StorageServiceInterface, TableServiceInterface

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)

@pytest.mark.asyncio(scope="class")
class TestInvoiceRepository:

    @pytest_asyncio.fixture
    async def invoice_repository(self):
        invoice_repository: TableServiceInterface = TableStorageService(
            storage_account_url=settings.table_storage_account_url,
            table_name=settings.invoices_table_name,
            standalone=True
        )
        yield invoice_repository
        await invoice_repository.close()

    @pytest_asyncio.fixture
    async def blob_repository(self):
        blob_repository: StorageServiceInterface = InvoiceStorageService()
        yield blob_repository
        await blob_repository.close()

    @pytest.mark.asyncio
    async def test_upsert_entity(self, invoice_repository: TableServiceInterface):
        invoice = Invoice(
            invoice_id=uuid.uuid4().hex[:12],
            department_id="FIN",
            invoice_number=f"INV-{uuid.uuid4().hex[:6]}",
            source=InvoiceSource.API,
            document_type=DocumentType.INVOICE,
            source_email="test@test.com",
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
        id = await invoice_repository.upsert_entity(entity_dict, invoice.department_id, invoice.invoice_id)
        print(f"Saved invoice : {entity_dict}")
        assert id is not None

    @pytest.mark.asyncio
    async def test_upload_file_as_bytes(self, blob_repository: StorageServiceInterface):
        file_path_low_q = "./scripts/poc/sample_documents/receipts/VALDES_251216_image.jpg"
        with open(file_path_low_q, "rb") as f:
            file_content = f.read()
        
        today = datetime.now()
        blob_name = f"{today.year}/{today.month}/{today.day}/VALDES_251216_image.jpg"
        print(f"Uploading blob with name: {blob_name}, {len(file_content)} bytes")
        print(f"Azure Blob Storage Account URL: {settings.blob_storage_account_url}")
        blob_url = await blob_repository.upload_file_as_bytes(file_content, blob_name)
        print(f"Uploaded blob URL: {blob_url}")
        assert blob_url is not None
        assert blob_name in blob_url

    @pytest.mark.asyncio
    async def test_download_file(self, blob_repository: StorageServiceInterface):
        blob_name = "2025/12/26/FIN-01/584708294422_20251216_152553.jpg"
        container_name = settings.blob_container_name
        print(f"Downloading blob with name: {blob_name}")
        downloaded_content = await blob_repository.download_file(container_name, blob_name)
        print(f"Downloaded blob content length: {len(downloaded_content)} bytes")

        assert downloaded_content is not None
        assert len(downloaded_content) > 0

    @pytest.mark.asyncio
    async def test_delete_file(self, blob_repository: StorageServiceInterface):
        container_name = settings.blob_container_name
        blob_name = "2025/12/26/FIN-01/584708294422_20251216_152553.jpg"
        print(f"Deleting blob with name: {blob_name}")
        await blob_repository.delete_file(container_name, blob_name)
        print(f"Deleted blob: {blob_name}")
        assert True  # If no exception, consider it successful

    @pytest.mark.asyncio
    async def test_get_entity(self, invoice_repository: TableServiceInterface):
        partition_key = "FIN"
        row_key = "865ce3705266"
        print(f"Retrieving entity with Partition Key: {partition_key}, Row Key: {row_key}")
        entity = await invoice_repository.get_entity(partition_key, row_key)
        invoice: Invoice = Invoice.from_dict(entity) if entity else None
        if invoice:
            print(f"Retrieved entity: {invoice}")
        else:
            print("Entity not found.")
        assert invoice is not None
    
    @pytest.mark.asyncio
    async def test_not_found_entity(self, invoice_repository: TableServiceInterface):
        partition_key = "NON_EXISTENT_PARTITION"
        row_key = "NON_EXISTENT_ROW"
        print(f"Attempting to retrieve non-existent entity with Partition Key: {partition_key}, Row Key: {row_key}")
        try:
            entity = await invoice_repository.get_entity(partition_key, row_key)
            print(f"Retrieved entity: {entity}")
            assert False, "Expected an exception for non-existent entity, but got a result."
        except EntityNotFoundException as e:
            print(f"Expected exception for non-existent entity: {e}")
            assert True

    @pytest.mark.asyncio
    async def test_save_to_file_entity(self, invoice_repository: TableServiceInterface):
        file_path = "./scripts/poc/sample_documents/invoice_entity.json"
        partition_key = "FIN"
        row_key = "8d9e0f1g2h3i"
        logger.info(f"Saving entity to file: {partition_key}, Row Key: {row_key}")
        entity = await invoice_repository.get_entity(partition_key, row_key)
        with open(file_path, "w") as f:
            f.write(json.dumps(entity, indent=4, default=str))
        logger.info(f"Entity saved to file: {file_path}")
        assert True

