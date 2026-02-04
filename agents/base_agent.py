"""
Base agent class for invoice processing agents.
"""
import asyncio
import signal
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
import time
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from azure.servicebus import ServiceBusReceivedMessage
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from invoice_lifecycle_api.infrastructure.messaging.servicebus_messaging_service import ServiceBusMessagingService
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.models.invoice import InvoiceInternalMessage, InvoiceState
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
        self.invoice_table_client: TableStorageService = None
        self.initialize_clients()

    
    def initialize_clients(self) -> None:
        """Initialize agent resources."""
        self.logger.info(f"Initializing {self.agent_name}...")
        
        self.logger.info(f"storage_account_url: {settings.table_storage_account_url} | table_name: {settings.invoices_table_name}") 
        # Initialize Table Storage client
        self.invoice_table_client = TableStorageService(
            storage_account_url=settings.table_storage_account_url,
            table_name=settings.invoices_table_name
        )
        # Initialize Service Bus client
        self.service_bus_client = ServiceBusMessagingService(
            host_name=settings.service_bus_host_name,
            topic_name=settings.service_bus_topic_name
        )

        self.logger.info(f"{self.agent_name} initialized successfully")
    
    def setup_signal_handlers(self):
        """setup signal handlers."""
        print("Setting up signal handlers...")
        def handle_signal(sig, frame):
            sig_name = signal.Signals(sig).name
            self.logger.info(f"\n🛑 Received {sig_name}, initiating shutdown...")
            self.shutdown_event.set() 

        # Handle Ctrl+C (SIGINT) and kill command (SIGTERM)
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        # On Windows, also handle SIGBREAK (Ctrl+Break)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, handle_signal)

    async def close(self) -> None:
        """Close agent resources."""
        self.logger.info(f"Closing {self.agent_name} clients...")
        if self.invoice_table_client:
            await self.invoice_table_client.close()
        if self.service_bus_client:
            await self.service_bus_client.close()
        
        await self.release_resources()
        
        await get_credential_manager().close()
        
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
                    
                    run = get_current_run_tree()
                    start_time = time.time()
                    try:
                        completed = await self._process_message(message)
                        if completed:
                            await receiver.complete_message(message)
                        else:
                            self.logger.warning(f"Message processing not completed, abandoning message: [{message}]")   
                            await receiver.dead_letter_message(message
                                , reason="ProcessingIncomplete"
                                , description="Message processing did not complete successfully."
                            )

                    except Exception as e:
                        self.logger.error(f"Sending to dead-letter Message data. Error processing message: {e}", exc_info=True)

                        # Dead-letter the message
                        await receiver.dead_letter_message(
                            message,
                            reason="ProcessingError",
                            description=str(e)
                        )
                    total_time = time.time() - start_time
                    if run:
                        run.add_metadata({
                            "total_latency_ms": total_time * 1000,
                            "intent": self.agent_name,
                        })
                    else:
                        self.logger.warning("No active LangSmith run found to add metadata.")

        except asyncio.CancelledError:
            self.logger.info(f"{self.agent_name} cancelled")
        except StopAsyncIteration:
            self.logger.warning("No more messages to receive, exiting iteration.")
        except Exception as e:
            self.logger.error(f"Fatal error in {self.agent_name}: {e}", exc_info=True)
            raise
        finally:
            await self.close()
            self.logger.info(f"{self.agent_name} stopped")

    @traceable(name="base_agent.process_message", tags=["base", "agent"], metadata={"version": "1.0"})
    async def _process_message(self, message: ServiceBusReceivedMessage) -> bool:
        """
        Process a Service Bus message.
        
        Args:
            message: Service Bus message
        """
        try:
            # Parse message body
            body = json.loads(str(message))
            invoice_id = body["invoice_id"]
            department_id = body["department_id"]

            if not invoice_id or not department_id or invoice_id.strip() == "" or department_id.strip() == "":
                raise ValueError("Message missing required fields: invoice_id or department_id")

            self.logger.info(
                f"Processing message: subject={message.subject}, "
                f"invoice_id={invoice_id}, department_id={department_id}"
            )

            # Call agent-specific processing logic
            result = await self.process_invoice(body)

            # Publish next state message if processing succeeded

            if result is not None and result["state"] == InvoiceState.VALIDATED.value:
                await self._publish_next_state(invoice_id, result)
                self.logger.info(f"Successfully processed invoice {invoice_id}")
                return True
            elif result is not None and result["state"] == InvoiceState.MANUAL_REVIEW.value:
                self.logger.info(f"Processed invoice {invoice_id} requiring manual review")
                return False
            else:
                self.logger.warning(f"Processing of invoice {invoice_id} did not complete successfully; no next state published.")
                return False
            
        except Exception as e:
            self.logger.error(f"Failed to process message: {e}", exc_info=True)
            raise
    
    @abstractmethod
    async def process_invoice(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process an invoice. Must be implemented by subclasses.
        
        Args:
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

    @abstractmethod
    async def release_resources(self) -> None:
        """
        Release any resources held by the agent.
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
        return await self.invoice_table_client.get_entity(
            partition_key=department_id,
            row_key=invoice_id
        )
    
    async def update_invoice(self, invoice: Dict[str, Any]) -> bool:
        """
        Update invoice in Table Storage.
        
        Args:
            invoice: Invoice entity to update
        """
        key = await self.invoice_table_client.upsert_entity(
            entity=invoice,
            partition_key=invoice["department_id"],
            row_key=invoice["invoice_id"]
        )
        return key == invoice["invoice_id"]

    def _build_internal_messages(self, code:str, messages: list[str]) -> list[InvoiceInternalMessage]:
        """
        Build internal messages log for invoice.
        Args:
            messages: List of message dicts with 'agent', 'message', 'code', 'timestamp'
        """
        internal_list =  [InvoiceInternalMessage(
            agent=self.agent_name,
            message=msg,
            code=code
        ) for msg in messages]
        
        return internal_list