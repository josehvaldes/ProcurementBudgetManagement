
from invoice_lifecycle_api.application.interfaces.service_interfaces import StorageServiceInterface


class InMemoryInvoiceStorageService(StorageServiceInterface):
    """In-memory implementation of invoice storage service."""
    def __init__(self):
        self._invoices = {}

    async def upload_file_as_bytes(self, blob_bytes: bytes, blob_name: str) -> str:
        """Upload file bytes to storage and return the file URL."""
        pass

    async def upload_file(self, file_path: str, blob_name: str) -> str:
        """Upload file to storage and return the file URL."""
        pass

    async def download_file(self, container_name: str, blob_name: str, download_path: str) -> None:
        """Download file from storage to the specified path."""
        pass

    async def delete_file(self, container_name: str, blob_name: str) -> None:
        """Delete file from storage."""
        pass
