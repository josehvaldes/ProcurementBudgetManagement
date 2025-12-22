import asyncio
import json
from azure.servicebus import ServiceBusMessage, ServiceBusSender
from azure.servicebus.aio import ServiceBusClient

from shared.config.settings import settings
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.application.interfaces.service_interfaces import MessagingServiceInterface
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager

logger = get_logger(__name__)

class ServiceBusMessagingService(MessagingServiceInterface):

    def __init__(self):
        
        self.topic_name = settings.service_bus_topic_name
        self.servicebus_connection_string = settings.service_bus_host_name
        credential_manager = get_credential_manager()
        self.servicebus_client = ServiceBusClient(
            fully_qualified_namespace=settings.service_bus_host_name,
            credential=credential_manager.get_credential()
        )

    async def send_message(self, topic: str, message_data: dict) -> None:
        """Send a message to the specified topic."""
        logger.info(f"Sending message to topic: {topic} with data: {message_data}")
        async with self.servicebus_client:
            sender: ServiceBusSender = self.servicebus_client.get_topic_sender(topic)
            message = ServiceBusMessage(
                subject=message_data["subject"],
                content_type=message_data["content_type"],
                body=json.dumps(message_data["body"]),
                message_id=message_data["messageId"]
            )
            await sender.send_messages(message)
            logger.info("Message sent successfully.")
    
    async def close(self) -> None:
        """Close the Service Bus client."""
        if self.servicebus_client:
            await self.servicebus_client.close()
            logger.info("Service Bus client closed.")