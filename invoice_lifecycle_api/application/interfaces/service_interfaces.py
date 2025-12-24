"""
Product service interface for dependency injection.
"""
from abc import ABC, abstractmethod
import asyncio
from invoice_lifecycle_api.infrastructure.messaging.subscription_receiver_wrapper import SubscriptionReceiverWrapper

class TableServiceInterface(ABC):
    """Abstract base class for product service implementations."""

    @abstractmethod
    async def upsert_entity(self, entity, partition_key: str, row_key: str) -> str:
        """Upsert an entity in the table storage."""
        pass

    @abstractmethod
    async def get_entity(self, partition_key: str, row_key: str) -> dict | None:
        """Retrieve entity by ID."""
        pass

    @abstractmethod
    async def delete_entity(self, partition_key: str, row_key: str) -> None:
        """Delete entity by ID."""
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
    async def publish_message(self, topic: str, message_data: dict) -> None:
        """Send a message to the specified topic."""
        pass
    
    @abstractmethod
    def get_subscription_receiver(self, subscription: str, shutdown_event: asyncio.Event) -> SubscriptionReceiverWrapper:
        """Get a receiver for the specified subscription."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any resources held by the service."""
        pass
