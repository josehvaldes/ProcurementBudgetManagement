import argparse
import asyncio
from datetime import datetime, timezone
import base64
import traceback
import uuid

from shared.config.settings import settings
from shared.utils.logging_config import get_logger, setup_logging
from shared.models.invoice import Invoice, InvoiceSource
from invoice_lifecycle_api.application.interfaces.service_interfaces import MessagingServiceInterface, StorageServiceInterface, TableServiceInterface
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from invoice_lifecycle_api.infrastructure.repositories.invoice_storage_service import InvoiceStorageService
from invoice_lifecycle_api.infrastructure.messaging.servicebus_messaging_service import ServiceBusMessagingService

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)

class RepositoryServiceTests:
    def setup_method(self):
        self.repository: TableServiceInterface = TableStorageService()
        self.blob_repository: StorageServiceInterface = InvoiceStorageService()
        self.messaging_service: MessagingServiceInterface = ServiceBusMessagingService()

    async def test_save_invoice(self):
        invoice = Invoice(
            invoice_id=uuid.uuid4().hex[:12],
            department_id=f"dept_{uuid.uuid4().hex[:6]}",
            source=InvoiceSource.API,
            source_email=f"test@test.com",
            priority="high",
            file_name="invoice.pdf",
            file_type="application/pdf",
            created_date=datetime.now(timezone.utc),
            raw_file_url="https://examplestorage.blob.core.windows.net/invoices/invoice.pdf",
            raw_file_blob_name="invoices/invoice.pdf",
            file_size=204800,
            file_uploaded_at=datetime.now(timezone.utc),
            line_items=[],
            has_po=False
            )
        id = await self.repository.save_invoice(invoice)
        print(f"Saved invoice ID: {id}")
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
        print(f"Downloading blob with name: {blob_name}")
        downloaded_content = await self.blob_repository.download_file(blob_name)
        print(f"Downloaded blob content length: {len(downloaded_content)} bytes")

        assert downloaded_content is not None
        assert len(downloaded_content) > 0
        with open("./scripts/poc/sample_documents/receipts/received_invoice_3c4a78652c62.jpg", "wb") as f:
            f.write(downloaded_content)

    async def test_delete_file(self):
        blob_name = f"2025/12/22/invoice_3c4a78652c62.jpg"
        print(f"Deleting blob with name: {blob_name}")
        await self.blob_repository.delete_file(blob_name)
        print(f"Deleted blob: {blob_name}")

    async def test_send_message(self):
        try:
            message_data = {
                "subject": "invoice.created",
                "content_type": "application/json",
                "messageId": uuid.uuid4().hex[:12],
                "body": {
                    "event_type": "APIInvoiceUploaded",                    
                    "department_id": "dept_test",
                }
            }
            print(f"Sending test message to topic 'invoice-events'")
            await self.messaging_service.send_message(settings.service_bus_topic_name, message_data)
            print(f"Sent test message with ID: {message_data['messageId']}")

        except Exception as e:
            print(f"Error sending test message: {e}")
            print(f"Message data: {message_data}")
            traceback.print_exc()

async def main():
    """Main async entry point for running tests."""
    test_instance = RepositoryServiceTests()
    test_instance.setup_method()

    parser = argparse.ArgumentParser(description="Azure Storage Repository Service Tests")
    parser.add_argument("action", type=str, help="Action to perform: Table or Blob", 
                       choices=["table", "upload", "download", "delete", "send_message"])
    args = parser.parse_args()
    
    logger.info(f"Running test for action: {args.action}")
    
    # Map actions to test methods
    test_map = {
        "table": test_instance.test_save_invoice,
        "upload": test_instance.test_upload_file_as_bytes,
        "download": test_instance.test_download_file,
        "delete": test_instance.test_delete_file,
        "send_message": test_instance.test_send_message,
    }
    
    # Run the selected test
    test_method = test_map.get(args.action)
    if test_method:
        await test_method()
        
if __name__ == "__main__":
    asyncio.run(main())

