import pytest
import pytest_asyncio
from unittest.mock import AsyncMock


import json

from invoice_lifecycle_api.application.services.event_choreographer import EventChoreographer
from invoice_lifecycle_api.domain.uploaded_file_dto import UploadedFileDTO
from invoice_lifecycle_api.infrastructure.repositories.invoice_storage_service import InvoiceStorageService
from shared.config.settings import settings
from shared.utils.logging_config import get_logger, setup_logging
from shared.models.invoice import Invoice, InvoiceState
from invoice_lifecycle_api.application.interfaces.service_interfaces import MessagingServiceInterface, TableServiceInterface

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)


@pytest.mark.asyncio(scope="class")
class TestEventChoreographer:
    
    @pytest_asyncio.fixture
    async def mock_invoice_storage(self):
        """Create a mock invoice repository."""
        mock_repo = AsyncMock(spec=InvoiceStorageService)
        return mock_repo
    
    @pytest_asyncio.fixture
    async def mock_table_repository(self):
        """Create a TableServiceInterface instance with mocked dependencies."""
        mock_repo = AsyncMock(spec=TableServiceInterface)
        return mock_repo
    
    @pytest_asyncio.fixture
    async def mock_messaging_service(self):
        """Create a mock messaging service."""
        mock_service = AsyncMock(spec=MessagingServiceInterface)
        return mock_service
    

    
    @pytest_asyncio.fixture
    async def sample_invoice(self):
        """Create a sample invoice for testing."""
        invoice_path = "./scripts/data-source/invoices_data.json"
        with open(invoice_path, "r") as f:
            invoice_data = json.load(f)

        return Invoice.from_dict(invoice_data[0])
    
    @pytest_asyncio.fixture
    async def event_choreographer(self, mock_invoice_storage, mock_table_repository,  mock_messaging_service):
        """Create EventChoreographer with mocked dependencies."""
        from invoice_lifecycle_api.application.services.event_choreographer import EventChoreographer
        choreographer = EventChoreographer(
            invoice_storage=mock_invoice_storage,
            table_repository=mock_table_repository,
            messaging_service=mock_messaging_service
        )
        yield choreographer

    @pytest.mark.asyncio
    async def test_handle_intake_event(self, event_choreographer: EventChoreographer, sample_invoice: Invoice):
        """Test handling an intake event."""
        uploaded_file = UploadedFileDTO(
            file_name=sample_invoice.file_name,
            content_type=sample_invoice.file_type,
            file_content=b"Sample file content for testing."
            )
        
        blob_url = f"https://examplestorage.blob.core.windows.net/invoices/{sample_invoice.file_name}"
        event_choreographer.invoice_storage.upload_file_as_bytes.return_value = blob_url

        invoice_id = await event_choreographer.handle_intake_event(
            invoice=sample_invoice,
            uploaded_file=uploaded_file
        )

        data = {
            "subject": "invoice.created",
            "correlation_id": invoice_id,
            "body": {
                "invoice_id": invoice_id,
                "event_type": "APIInvoiceGenerated",
                "department_id": sample_invoice.department_id,
            }
        }

        assert invoice_id is not None
        assert sample_invoice.state == InvoiceState.CREATED
        assert sample_invoice.raw_file_url == blob_url

        event_choreographer.table_repository.upsert_entity.assert_called_once()
        event_choreographer.invoice_storage.upload_file_as_bytes.assert_called_once()
        event_choreographer.messaging_service.publish_message.assert_called_once_with(settings.service_bus_topic_name, data)