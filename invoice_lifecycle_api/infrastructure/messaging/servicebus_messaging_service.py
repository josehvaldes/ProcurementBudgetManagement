import asyncio
import json
from azure.servicebus import ServiceBusMessage, ServiceBusSender
from azure.servicebus.aio import ServiceBusClient


from shared.config.settings import settings
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from invoice_lifecycle_api.infrastructure.messaging.subscription_receiver_wrapper import SubscriptionReceiverWrapper
from invoice_lifecycle_api.application.interfaces.service_interfaces import MessagingServiceInterface

logger = get_logger(__name__)

class ServiceBusMessagingService(MessagingServiceInterface):
    
    def __init__(self, host_name: str = None, topic_name: str = None):
    
        self.subscribers = []    
        self.topic_name = topic_name or settings.service_bus_topic_name
        self.service_bus_host_name = host_name or settings.service_bus_host_name
        credential_manager = get_credential_manager()

        self.servicebus_client = ServiceBusClient(
            fully_qualified_namespace=self.service_bus_host_name,
            credential=credential_manager.get_credential()
        )

    async def publish_message(self, topic: str, message_data: dict) -> None:
        """Send a message to the specified topic."""
        logger.info(f"Sending message to topic: {topic} with data: {message_data}")
        sender: ServiceBusSender = self.servicebus_client.get_topic_sender(topic)
        message = ServiceBusMessage(
            content_type='application/json',
            subject=message_data["subject"],                
            body=json.dumps(message_data["body"]),                
        )
        await sender.send_messages(message)
        logger.info("Message sent successfully.")

    def get_subscription_receiver(self, subscription: str, shutdown_event: asyncio.Event) -> SubscriptionReceiverWrapper:
        """Get a receiver for the specified topic and subscription."""
        subscription_receiver = SubscriptionReceiverWrapper(self.servicebus_client,
                                                            self.topic_name, subscription, shutdown_event)

        self.subscribers.append(subscription_receiver)
        return subscription_receiver

    async def close(self) -> None:
        """Close the Service Bus client."""
        if self.servicebus_client:
            await self.servicebus_client.close()
            logger.info("Service Bus client closed.")

        if self.subscribers:
            for subscriber in self.subscribers:
                await subscriber.close()
            logger.info(f"All {len(self.subscribers)} subscribers closed.")