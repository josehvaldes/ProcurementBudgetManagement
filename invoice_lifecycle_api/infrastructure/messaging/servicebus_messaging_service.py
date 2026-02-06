import asyncio
import json
from typing import Optional
from azure.servicebus import ServiceBusMessage, ServiceBusSender
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus.exceptions import ServiceBusError

from shared.config.settings import settings
from shared.utils.exceptions import MessagePublishException, MessagingException, ServiceBusConnectionException
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from invoice_lifecycle_api.infrastructure.messaging.subscription_receiver_wrapper import SubscriptionReceiverWrapper
from invoice_lifecycle_api.application.interfaces.service_interfaces import MessagingServiceInterface

logger = get_logger(__name__)


class ServiceBusMessagingService(MessagingServiceInterface):
    """
    Azure Service Bus messaging service for publish/subscribe operations.
    
    This service manages:
    - Publishing messages to Service Bus topics
    - Creating subscription receivers for message consumption
    - Managing Service Bus client lifecycle
    
    Attributes:
        topic_name (str): Default Service Bus topic name
        service_bus_host_name (str): Fully qualified Service Bus namespace
        servicebus_client (ServiceBusClient): Azure Service Bus client
        subscribers (list): List of active subscription receivers
    """
    
    def __init__(self, host_name: Optional[str] = None, topic_name: Optional[str] = None):
        """
        Initialize Service Bus messaging service.
        
        Args:
            host_name: Fully qualified Service Bus namespace (e.g., 'namespace.servicebus.windows.net')
                      If None, uses settings.service_bus_host_name
            topic_name: Default topic name for publishing messages
                       If None, uses settings.service_bus_topic_name
                       
        Raises:
            ServiceBusConnectionException: If Service Bus client initialization fails
        """
        self.subscribers = []    
        self.topic_name = topic_name or settings.service_bus_topic_name
        self.service_bus_host_name = host_name or settings.service_bus_host_name
        
        logger.info(
            "Initializing Service Bus messaging service",
            extra={
                "service_bus_namespace": self.service_bus_host_name,
                "default_topic": self.topic_name
            }
        )
        
        try:
            credential_manager = get_credential_manager()
            self.servicebus_client = ServiceBusClient(
                fully_qualified_namespace=self.service_bus_host_name,
                credential=credential_manager.get_credential()
            )
            
            logger.info(
                "Service Bus client initialized successfully",
                extra={"service_bus_namespace": self.service_bus_host_name}
            )
            
        except Exception as e:
            logger.error(
                "Failed to initialize Service Bus client",
                extra={
                    "service_bus_namespace": self.service_bus_host_name,
                    "error_type": "ServiceBusConnectionFailed",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise ServiceBusConnectionException(
                f"Failed to initialize Service Bus client: {str(e)}"
            ) from e

    async def publish_message(self, topic: str, message_data: dict) -> None:
        """
        Publish a message to the specified Service Bus topic.
        
        Args:
            topic: Topic name to publish to
            message_data: Message payload containing:
                - subject (str): Message subject/event type
                - body (dict): Message body data
                - correlation_id (str): Correlation ID for distributed tracing
                
        Raises:
            MessagePublishException: If message publishing fails
            ValueError: If required message_data fields are missing
            
        Example:
            message_data = {
                "subject": "InvoiceCreated",
                "body": {"invoice_id": "INV-123", "amount": 100.0},
                "correlation_id": "INV-123"
            }
            await service.publish_message("invoice-lifecycle", message_data)
        """
        # Validate required fields
        required_fields = ["subject", "body", "correlation_id"]
        missing_fields = [field for field in required_fields if field not in message_data]
        
        if missing_fields:
            error_msg = f"Missing required fields in message_data: {', '.join(missing_fields)}"
            logger.error(
                "Message validation failed",
                extra={
                    "topic": topic,
                    "missing_fields": missing_fields,
                    "error_type": "MessageValidationFailed"
                }
            )
            raise ValueError(error_msg)
        
        correlation_id = message_data["correlation_id"]
        subject = message_data["subject"]
        
        logger.info(
            "Publishing message to Service Bus topic",
            extra={
                "topic": topic,
                "subject": subject,
                "correlation_id": correlation_id
            }
        )
        
        sender: Optional[ServiceBusSender] = None
        
        try:
            sender = self.servicebus_client.get_topic_sender(topic)
            
            message = ServiceBusMessage(
                content_type='application/json',
                subject=subject,                
                body=json.dumps(message_data["body"]),
                correlation_id=correlation_id
            )
            
            await sender.send_messages(message)
            
            logger.info(
                "Message published successfully",
                extra={
                    "topic": topic,
                    "subject": subject,
                    "correlation_id": correlation_id,
                }
            )
            
        except ServiceBusError as e:
            logger.error(
                "Service Bus error during message publish",
                extra={
                    "topic": topic,
                    "subject": subject,
                    "correlation_id": correlation_id,
                    "error_type": "ServiceBusPublishFailed",
                    "error_code": getattr(e, 'error_code', 'UNKNOWN'),
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise MessagePublishException(
                f"Failed to publish message to topic '{topic}': {str(e)}"
            ) from e
            
        except Exception as e:
            logger.error(
                "Unexpected error during message publish",
                extra={
                    "topic": topic,
                    "subject": subject,
                    "correlation_id": correlation_id,
                    "error_type": "UnexpectedPublishError",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise MessagePublishException(
                f"Unexpected error publishing message: {str(e)}"
            ) from e
            
        finally:
            if sender:
                await sender.close()
                logger.debug(
                    "Topic sender closed",
                    extra={
                        "topic": topic,
                        "correlation_id": correlation_id
                    }
                )

    def get_subscription_receiver(
        self, 
        subscription: str, 
        shutdown_event: asyncio.Event
    ) -> SubscriptionReceiverWrapper:
        """
        Create and register a subscription receiver for message consumption.
        
        Args:
            subscription: Subscription name to receive messages from
            shutdown_event: Asyncio event to signal graceful shutdown
            
        Returns:
            SubscriptionReceiverWrapper configured for the subscription
            
        Note:
            The receiver is automatically tracked and will be closed during service shutdown.
            
        Example:
            shutdown_event = asyncio.Event()
            receiver = service.get_subscription_receiver("budget-agent-sub", shutdown_event)
            async for message in receiver:
                # Process message
                await receiver.complete_message(message)
        """
        logger.info(
            "Creating subscription receiver",
            extra={
                "topic": self.topic_name,
                "subscription": subscription
            }
        )
        
        try:
            subscription_receiver = SubscriptionReceiverWrapper(
                self.servicebus_client,
                self.topic_name, 
                subscription, 
                shutdown_event
            )
            
            self.subscribers.append(subscription_receiver)
            
            logger.info(
                "Subscription receiver created successfully",
                extra={
                    "topic": self.topic_name,
                    "subscription": subscription,
                    "total_subscribers": len(self.subscribers)
                }
            )
            
            return subscription_receiver
            
        except Exception as e:
            logger.error(
                "Failed to create subscription receiver",
                extra={
                    "topic": self.topic_name,
                    "subscription": subscription,
                    "error_type": "ReceiverCreationFailed",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise MessagingException(
                f"Failed to create subscription receiver for '{subscription}': {str(e)}"
            ) from e

    async def close(self) -> None:
        """
        Close Service Bus client and all active subscription receivers.
        
        This method performs graceful shutdown:
        1. Closes all subscription receivers
        2. Closes the Service Bus client connection
        
        Should be called during application shutdown to release resources.
        
        Example:
            try:
                # Use messaging service
                await service.publish_message(...)
            finally:
                await service.close()
        """
        logger.info(
            "Closing Service Bus messaging service",
            extra={
                "total_subscribers": len(self.subscribers),
                "service_bus_namespace": self.service_bus_host_name
            }
        )
        
        # Close all subscription receivers
        if self.subscribers:
            close_errors = []
            
            for idx, subscriber in enumerate(self.subscribers):
                try:
                    await subscriber.close()
                    logger.debug(
                        f"Subscriber {idx + 1} closed successfully",
                        extra={"subscriber_index": idx}
                    )
                except Exception as e:
                    close_errors.append(f"Subscriber {idx}: {str(e)}")
                    logger.warning(
                        f"Error closing subscriber {idx + 1}",
                        extra={
                            "subscriber_index": idx,
                            "error_details": str(e)
                        }
                    )
            
            if close_errors:
                logger.warning(
                    f"Some subscribers failed to close gracefully",
                    extra={
                        "failed_count": len(close_errors),
                        "total_subscribers": len(self.subscribers),
                        "errors": close_errors
                    }
                )
            
            logger.info(
                f"All {len(self.subscribers)} subscribers closed",
                extra={"total_subscribers": len(self.subscribers)}
            )
        
        # Close Service Bus client
        if self.servicebus_client:
            try:
                await self.servicebus_client.close()
                logger.info(
                    "Service Bus client closed successfully",
                    extra={"service_bus_namespace": self.service_bus_host_name}
                )
            except Exception as e:
                logger.error(
                    "Error closing Service Bus client",
                    extra={
                        "service_bus_namespace": self.service_bus_host_name,
                        "error_type": "ServiceBusCloseFailed",
                        "error_details": str(e)
                    },
                    exc_info=True
                )
                # Don't re-raise - we're shutting down anyway