"""
Product service interface for dependency injection.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Generator
from datetime import datetime

from shared.models.invoice import Invoice

class TableServiceInterface(ABC):
    """Abstract base class for product service implementations."""
    @abstractmethod
    async def save_invoice(self, invoice_data: Invoice) -> str:
        """Save invoice data to the repository."""
        pass

    @abstractmethod
    async def get_invoice(self, invoice_id: str) -> Invoice | None:
        """Retrieve invoice by ID."""
        pass

    @abstractmethod
    async def delete_invoice(self, invoice_id: str) -> None:
        """Delete invoice by ID."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any resources held by the service."""
        pass
    

class StorageServiceInterface(ABC):
    """Abstract base class for storage service implementations."""
    
    @abstractmethod
    async def upload_file_as_bytes(self, blob_bytes: bytes, blob_name: str) -> str:
        """Upload file bytes to storage and return the file URL."""
        pass


    @abstractmethod
    async def upload_file(self, file_path: str, blob_name: str) -> str:
        """Upload file to storage and return the file URL."""
        pass

    @abstractmethod
    async def download_file(self, blob_name: str) -> bytes | None:
        """Download file from storage."""
        pass

    @abstractmethod
    async def delete_file(self, blob_name: str) -> None:
        """Delete file from storage."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any resources held by the service."""
        pass
    



class MessagingServiceInterface(ABC):
    """Abstract base class for messaging service implementations."""
    
    @abstractmethod
    async def send_message(self, topic: str, message_data: Dict) -> None:
        """Send a message to the specified topic."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any resources held by the service."""
        pass
    
