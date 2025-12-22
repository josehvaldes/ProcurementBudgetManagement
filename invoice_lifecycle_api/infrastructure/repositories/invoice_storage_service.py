
import io
from azure.storage.blob.aio import BlobServiceClient
from shared.config.settings import settings
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from invoice_lifecycle_api.application.interfaces.service_interfaces import StorageServiceInterface

logger = get_logger(__name__)

class InvoiceStorageService(StorageServiceInterface):

    def __init__(self):
        self.account_url = settings.blob_storage_account_url
        self.container_name = settings.blob_container_name
        credential_manager = get_credential_manager()        
        self.blob_service_client = BlobServiceClient(
            account_url=self.account_url,
            credential=credential_manager.get_credential()
        )

        self.container_client = self.blob_service_client.get_container_client(container=self.container_name)

    async def upload_file_as_bytes(self, blob_bytes: bytes, blob_name: str) -> str:
        """Upload file bytes to storage and return the file URL."""
        
        metadata = {"uploaded_by": "InvoiceLifecycleAPI"}
        logger.info(f" - Uploading blob to container: {self.container_name}, blob name: {blob_name}")

        blob_url = f"{self.account_url}/{self.container_name}/{blob_name}"

        _ = await self.container_client.upload_blob(name=blob_name, data=blob_bytes, overwrite=True,
                                                         metadata=metadata)
        return blob_url

    async def upload_file(self, file_path: str, blob_name: str) -> str:
        """Upload file to storage and return the file URL."""
        pass

    async def download_file(self, blob_name: str) -> bytes:
        """Download file from storage"""
        blob_client = self.blob_service_client.get_blob_client(container=settings.blob_container_name, blob=blob_name)
        stream = io.BytesIO()
        data = await blob_client.download_blob()
        _ = await data.readinto(stream)
        return stream.getvalue()

    async def delete_file(self, blob_name: str) -> None:
        """Delete file from storage."""
        blob_client = self.blob_service_client.get_blob_client(container=settings.blob_container_name, blob=blob_name)
        await blob_client.delete_blob()

    async def close(self) -> None:
        """Close the Blob Storage client."""
        if self.container_client:
            await self.container_client.close()
            logger.info("Blob Container client closed.")

        if self.blob_service_client:
            await self.blob_service_client.close()
            logger.info("Blob Storage client closed.")
