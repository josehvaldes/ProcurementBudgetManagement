"""Event Choreographer Service."""
from datetime import datetime, timezone
import traceback
import uuid
from invoice_lifecycle_api.domain.uploaded_file_dto import UploadedFileDTO
from shared.utils.logging_config import get_logger
from shared.config.settings import settings
from invoice_lifecycle_api.application.interfaces.service_interfaces import MessagingServiceInterface, TableServiceInterface
from invoice_lifecycle_api.infrastructure.repositories.invoice_storage_service import InvoiceStorageService
from shared.models.invoice import Invoice, InvoiceState

logger = get_logger(__name__)

class EventChoreographer:

    def __init__(self, 
                 table_repository:TableServiceInterface,
                 invoice_storage:InvoiceStorageService,
                 messaging_service:MessagingServiceInterface):
        self.table_repository = table_repository
        self.invoice_storage = invoice_storage
        self.messaging_service = messaging_service

    async def handle_intake_event(self, invoice: Invoice, uploaded_file: UploadedFileDTO) -> str:
        """Handle the intake event: upload file, save metadata, send notification."""
        today = datetime.now(timezone.utc)
        invoice_id = uuid.uuid4().hex[:12]

        blob_name = f"{today.year}/{today.month}/{today.day}/{invoice.department_id}/{invoice_id}_{uploaded_file.file_name}"
        logger.info(f"Uploading blob with name: {blob_name}, {len(uploaded_file.file_content)} bytes")
        
        try:
            #step 1 - upload file to blob storage
            blob_url = await self.invoice_storage.upload_file_as_bytes(uploaded_file.file_content, blob_name)
            
            invoice.invoice_id = invoice_id
            invoice.file_name = uploaded_file.file_name
            invoice.file_type = uploaded_file.content_type
            invoice.file_size = len(uploaded_file.file_content)
            invoice.file_uploaded_at = today
            invoice.created_date = today
            invoice.raw_file_blob_name = blob_name
            invoice.raw_file_url = blob_url
            invoice.state = InvoiceState.CREATED

            logger.info(f"Invoice ID: {invoice_id} Uploaded to blob URL: {blob_url}")

            #step 2 - save invoice metadata to table storage
            entity = invoice.to_dict()
            id = await self.table_repository.upsert_entity(entity, invoice.department_id, invoice.invoice_id)
            logger.info(f"Invoice saved with ID: {id}")

            #step 3 - send notification to ServiceBus topic
            data = {
                "subject": "invoice.created",
                "body": {
                    "invoice_id": invoice.invoice_id,
                    "event_type": "APIInvoiceGenerated",
                    "department_id": invoice.department_id,
                }
            }
            logger.info(f"Sending message to Service Bus Topic: {settings.service_bus_topic_name} with Invoice ID: {invoice_id}")
            await self.messaging_service.publish_message(settings.service_bus_topic_name, data)

            return invoice_id
        except Exception as e:
            logger.error(f"Error processing intake event: {e}")
            traceback.print_exc()
            return ""

