"""
Azure Service Bus client wrapper for invoice events.
"""

import json
import logging
from typing import Optional, Dict, Any
from azure.servicebus import ServiceBusClient as AzureServiceBusClient, ServiceBusMessage
from azure.servicebus import ServiceBusReceiver

logger = logging.getLogger(__name__)


class ServiceBusClient:
    """
    Wrapper for Azure Service Bus operations.
    Handles publishing and subscribing to invoice events.
    """
    
    def __init__(self, connection_string: str, topic_name: str = "invoice-events"):
        """
        Initialize Service Bus client.
        
        Args:
            connection_string: Azure Service Bus connection string
            topic_name: Name of the topic for invoice events
        """
        self.connection_string = connection_string
        self.topic_name = topic_name
        self._client: Optional[AzureServiceBusClient] = None
    
    def __enter__(self):
        """Context manager entry."""
        self._client = AzureServiceBusClient.from_connection_string(
            self.connection_string
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._client:
            self._client.close()
    
    def publish_message(
        self,
        invoice_id: str,
        subject: str,
        data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Publish a message to the Service Bus topic.
        
        Args:
            invoice_id: Invoice ID
            subject: Message subject (e.g., "invoice.created")
            data: Message payload
            correlation_id: Optional correlation ID for tracking
        """
        if not self._client:
            raise RuntimeError("Service Bus client not initialized. Use context manager.")
        
        try:
            with self._client.get_topic_sender(self.topic_name) as sender:
                message = ServiceBusMessage(
                    body=json.dumps(data),
                    subject=subject,
                    content_type="application/json",
                    correlation_id=correlation_id or invoice_id,
                    message_id=f"{invoice_id}-{subject}",
                )
                sender.send_messages(message)
                logger.info(f"Published message: {subject} for invoice {invoice_id}")
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            raise
    
    def get_subscription_receiver(
        self,
        subscription_name: str,
        max_wait_time: int = 60
    ) -> ServiceBusReceiver:
        """
        Get a receiver for a specific subscription.
        
        Args:
            subscription_name: Name of the subscription
            max_wait_time: Maximum wait time for messages in seconds
            
        Returns:
            ServiceBusReceiver instance
        """
        if not self._client:
            raise RuntimeError("Service Bus client not initialized. Use context manager.")
        
        return self._client.get_subscription_receiver(
            topic_name=self.topic_name,
            subscription_name=subscription_name,
            max_wait_time=max_wait_time
        )
