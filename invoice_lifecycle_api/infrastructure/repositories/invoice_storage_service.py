
import io
from azure.storage.blob.aio import BlobServiceClient
from azure.core.exceptions import ServiceResponseError
import pybreaker
import random
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from shared.config.settings import settings
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from invoice_lifecycle_api.application.interfaces.service_interfaces import StorageServiceInterface

logger = get_logger(__name__)

class InvoiceStorageBreakerListener(pybreaker.CircuitBreakerListener):
    """Listener to log circuit breaker state changes."""

    def state_change(self, cb, old_state, new_state):
        logger.warning(
            f"Circuit breaker '{cb.name}' state changed: {old_state.name} → {new_state.name}"
        )

    def failure(self, cb, exc):
        logger.warning(f"Circuit breaker '{cb.name}' recorded failure: {exc}")

    def success(self, cb):
        logger.info(f"Circuit breaker '{cb.name}' recorded success")

download_circuit_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    listener=InvoiceStorageBreakerListener(),
    exclude=[FileNotFoundError,  # Exclude FileNotFoundError from tripping the circuit breaker
             ValueError,
             TypeError] 
)

command_circuit_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    listener=InvoiceStorageBreakerListener(),
    exclude=[FileNotFoundError,
             ValueError,
             TypeError]
)

class InvoiceStorageService(StorageServiceInterface):

    def __init__(self, standalone: bool = False):
        self.standalone = standalone
        self.account_url = settings.blob_storage_account_url
        self.container_name = settings.blob_container_name
        self.credential_manager = get_credential_manager()        
        self.blob_service_client = BlobServiceClient(
            account_url=self.account_url,
            credential=self.credential_manager.get_credential()
        )

        self.container_client = self.blob_service_client.get_container_client(container=self.container_name)

    @download_circuit_breaker
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

    @retry(
            stop=stop_after_attempt(3), 
            wait=wait_fixed(2), 
            retry=retry_if_exception_type((ServiceResponseError))
        )
    @download_circuit_breaker
    async def download_file(self,  container_name:str, blob_name: str) -> bytes:
        """Download file from storage"""
        blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        stream = io.BytesIO()
        data = await blob_client.download_blob()
        _ = await data.readinto(stream)
        return stream.getvalue()

    @command_circuit_breaker
    async def file_exists(self, container_name: str, blob_name: str) -> bool:
        """Check if file exists in storage."""
        blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        return await blob_client.exists()

    @command_circuit_breaker
    async def delete_file(self, container_name: str, blob_name: str) -> None:
        """Delete file from storage."""
        blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        await blob_client.delete_blob()

    async def close(self) -> None:
        """Close the Blob Storage client."""
        if self.container_client:
            await self.container_client.close()
            logger.info("Blob Container client closed.")

        if self.blob_service_client:
            await self.blob_service_client.close()
            logger.info("Blob Storage client closed.")
        
        if self.standalone:
            await self.credential_manager.close()
            logger.info("Credential manager closed.")

    async def __aenter__(self):
        """Enter async context manager."""
        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        try: 
            await self.close()
        except Exception as e:
            logger.error(f"Error closing Blob Storage client: {e}")