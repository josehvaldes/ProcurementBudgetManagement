"""
Base agent class for invoice processing agents.
"""
import asyncio
import signal
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from azure.servicebus import ServiceBusReceivedMessage, ServiceBusMessage
from invoice_lifecycle_api.infrastructure.messaging.servicebus_messaging_service import ServiceBusMessagingService
from invoice_lifecycle_api.infrastructure.messaging.subscription_receiver_wrapper import SubscriptionReceiverWrapper
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.utils.logging_config import get_logger, setup_logging
from shared.config.settings import settings

setup_logging(log_level=settings.log_level,
                log_file=settings.log_file,
                log_to_console=settings.log_to_console)

class BaseAgent(ABC):
    """
    Abstract base class for all invoice processing agents.
    
    Provides common functionality for:
    - Service Bus message handling
    - Table Storage operations
    - Logging
    - Error handling
    """
    
    def __init__(
        self,
        agent_name: str,
        subscription_name: str,
        shutdown_event: asyncio.Event = None
    ):
        """
        Initialize the base agent.
        
        Args:
            agent_name: Name of the agent (for logging)
            subscription_name: Service Bus subscription name
        """
        self.logger = get_logger(agent_name)

        self.shutdown_event = shutdown_event or asyncio.Event()
        self.agent_name = agent_name
        self.subscription_name = subscription_name
        self.topic_name = settings.service_bus_topic_name

        # Initialize clients
        self.service_bus_client: ServiceBusMessagingService = None
        self.table_storage_client: TableStorageService = None

        self.initialize_clients()

    
    def initialize_clients(self) -> None:
        """Initialize agent resources."""
        self.logger.info(f"Initializing {self.agent_name}...")
        
        self.logger.info(f"storage_account_url: {settings.table_storage_account_url} | table_name: {settings.invoices_table_name}") 
        # Initialize Table Storage client
        self.table_storage_client = TableStorageService(
            storage_account_url=settings.table_storage_account_url,
            table_name=settings.invoices_table_name
        )
        # Initialize Service Bus client
        self.service_bus_client = ServiceBusMessagingService(
            host_name=settings.service_bus_host_name,
            topic_name=settings.service_bus_topic_name
        )
        self.logger.info(f"{self.agent_name} initialized successfully")
    
    async def close(self) -> None:
        """Close agent resources."""
        self.logger.info(f"Closing {self.agent_name} clients...")
        if self.table_storage_client:
            await self.table_storage_client.close()
        if self.service_bus_client:
            await self.service_bus_client.close()
        self.logger.info(f"{self.agent_name} clients closed successfully")

    async def run(self) -> None:
        """
        Main agent run loop.
        Continuously polls for messages and processes them.
        """
        self.logger.info(f"Starting {self.agent_name}...")
        try:
            async with self.service_bus_client.get_subscription_receiver(
                subscription=self.subscription_name,
                shutdown_event=self.shutdown_event
            ) as receiver:
                self.logger.info(f"{self.agent_name} listening for messages...")
                async for message in receiver:

                    if self.shutdown_event.is_set():
                        self.logger.info(f"Shutdown event set, stopping {self.agent_name}...")
                        break

                    try:
                        completed = await self._process_message(message)
                        if completed:
                            await receiver.complete_message(message)
                        else:
                            # this should not happen, but just in case
                            self.logger.warning(f"Message processing not completed, abandoning message: [{message}]")   
                            await receiver.dead_letter_message(message
                                , reason="ProcessingIncomplete"
                                , description="Message processing did not complete successfully."
                            )

                    except Exception as e:
                        self.logger.error(f"Error processing message: {e}", exc_info=True)
                        self.logger.error(f"Sending to dead-letter Message data: [{message}]")

                        # Dead-letter the message
                        await receiver.dead_letter_message(
                            message,
                            reason="ProcessingError",
                            description=str(e)
                        )
            self.logger.info(f"{self.agent_name} shut down gracefully")
        except asyncio.CancelledError:
            self.logger.info(f"{self.agent_name} cancelled")
        except Exception as e:
            self.logger.error(f"Fatal error in {self.agent_name}: {e}", exc_info=True)
            raise
        finally:
            await self.close()
            self.logger.info(f"{self.agent_name} stopped")

    async def _process_message(self, message: ServiceBusReceivedMessage) -> bool:
        """
        Process a Service Bus message.
        
        Args:
            message: Service Bus message
        """
        try:
            # Parse message body
            body = json.loads(str(message))
            invoice_id = body.get("invoice_id")
            event_type = body.get("event_type")
            department_id = body.get("department_id")
            
            self.logger.info(
                f"Processing message: subject={message.subject}, "
                f"invoice_id={invoice_id}"
            )
            
            # Call agent-specific processing logic
            result = await self.process_invoice(invoice_id, body)

            # Publish next state message if processing succeeded

            if result:
                await self._publish_next_state(invoice_id, result)

            self.logger.info(f"Successfully processed invoice {invoice_id}")
            return True
        except Exception as e:
            self.logger.error(f"..Failed to process message: {e}", exc_info=True)
            raise
    
    @abstractmethod
    async def process_invoice(self, invoice_id: str, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process an invoice. Must be implemented by subclasses.
        
        Args:
            invoice_id: Invoice ID
            message_data: Message payload
            
        Returns:
            Result data to publish, or None if no next message should be published
        """
        pass
    
    @abstractmethod
    def get_next_subject(self) -> str:
        """
        Get the subject for the next message to publish.
        Must be implemented by subclasses.
        
        Returns:
            Message subject string
        """
        pass
    
    async def _publish_next_state(self, invoice_id: str, data: Dict[str, Any]) -> None:
        """
        Publish message for next state transition.
        
        Args:
            invoice_id: Invoice ID
            data: Message payload
        """
        next_subject = self.get_next_subject()
        
        if next_subject:
            message_data = {
                "subject": next_subject,
                "body": data
            }
            await self.service_bus_client.publish_message(self.topic_name, message_data)
            self.logger.info(f"Published {next_subject} for invoice {invoice_id}")

    async def get_invoice(self, department_id: str, invoice_id: str) -> Optional[Dict[str, Any]]:
        """
        Get invoice from Table Storage.
        
        Args:
            invoice_id: Invoice ID
            
        Returns:
            Invoice entity or None
        """
        return await self.table_storage_client.get_entity(
            partition_key=department_id,
            row_key=invoice_id
        )
    
    async def update_invoice(self, invoice: Dict[str, Any]) -> None:
        """
        Update invoice in Table Storage.
        
        Args:
            invoice: Invoice entity to update
        """
        await self.table_storage_client.upsert_entity(
            entity=invoice,
            partition_key=invoice["department_id"],
            row_key=invoice["invoice_id"]
        )
