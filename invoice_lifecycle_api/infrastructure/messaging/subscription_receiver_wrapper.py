import asyncio
from typing import AsyncIterator
from azure.servicebus.aio import ServiceBusClient, ServiceBusReceiver
from azure.servicebus import ServiceBusReceivedMessage
from shared.config.settings import settings
from shared.utils.logging_config import get_logger
logger = get_logger(__name__)

class SubscriptionReceiverWrapper:
    def __init__(self, servicebus_client: ServiceBusClient, topic: str, subscription: str, shutdown_event: asyncio.Event):
        self.servicebus_client = servicebus_client
        self.topic = topic
        self.subscription = subscription
        self.receiver: ServiceBusReceiver | None = None
        self.shutdown_event = shutdown_event

    async def __aenter__(self):
        self.receiver = self.servicebus_client.get_subscription_receiver(
            topic_name=self.topic, 
            subscription_name=self.subscription
        )
        await self.receiver.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.receiver:
            try:
                await self.receiver.__aexit__(exc_type, exc_val, exc_tb)
                logger.info(f"Exited context for subscription receiver of topic '{self.topic}' and subscription '{self.subscription}'.")
                # Shutdown the receiver
                await self.close()
            except Exception as e:
                logger.warning(f"Error closing receiver: {e}")

    def __aiter__(self):
        """Return self as the async iterator."""
        return self

    async def __anext__(self) -> ServiceBusReceivedMessage:
        """Get the next message from the subscription."""
        if not self.receiver:
            raise StopAsyncIteration
        
        try:
            while self.shutdown_event.is_set() is False:
                # Receive one message at a time
                messages = await self.receiver.receive_messages(
                    max_message_count=1,
                    max_wait_time=5
                )
                
                if messages:
                    return messages[0]
                else:
                    # No messages available, keep iterating
                    print(f"No messages available, keep iterating. Shutdown_event: {self.shutdown_event.is_set()}")
                    await asyncio.sleep(0.1)  # Wait before retrying
                    
            # If we exit the loop, stop iteration
            raise StopAsyncIteration
        except StopAsyncIteration:
            logger.warning("No more messages to receive, stopping iteration.")
            raise
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            raise StopAsyncIteration

    async def receive_messages(self, max_message_count: int = 1, max_wait_time: int = 5):
        """Receive multiple messages from the subscription."""
        if not self.receiver:
            raise RuntimeError("Receiver not initialized. Use async with context manager.")
        
        messages = await self.receiver.receive_messages(
            max_message_count=max_message_count,
            max_wait_time=max_wait_time
        )
        return messages

    async def complete_message(self, message: ServiceBusReceivedMessage) -> None:
        """Complete (acknowledge) the received message."""
        if not self.receiver:
            raise RuntimeError("Receiver not initialized. Use async with context manager.")

        logger.info(f"Completing message: {message}")
        await self.receiver.complete_message(message)
    
    async def abandon_message(self, message: ServiceBusReceivedMessage) -> None:
        """Abandon the received message."""
        if not self.receiver:
            raise RuntimeError("Receiver not initialized. Use async with context manager.")

        await self.receiver.abandon_message(message)

    async def dead_letter_message(self, message: ServiceBusReceivedMessage, reason: str = "", description: str = "") -> None:
        """Dead-letter the received message."""
        if not self.receiver:
            raise RuntimeError("Receiver not initialized. Use async with context manager.")

        await self.receiver.dead_letter_message(
            message,
            reason=reason,
            error_description=description
        )        

    async def close(self) -> None:
        """Close the subscription receiver."""
        if self.receiver:
            try:
                await self.receiver.close()
                logger.info(f"Subscription receiver for topic '{self.topic}' and subscription '{self.subscription}' closed.")
            except Exception as e:
                logger.warning(f"Error closing subscription receiver: {e}")