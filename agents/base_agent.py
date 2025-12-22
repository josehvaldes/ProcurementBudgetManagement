"""
Base agent class for invoice processing agents.
"""

import logging
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from azure.servicebus import ServiceBusMessage

from shared.infrastructure import ServiceBusClient, TableStorageClient
from shared.config import get_settings
from shared.utils import setup_logger


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
    ):
        """
        Initialize the base agent.
        
        Args:
            agent_name: Name of the agent (for logging)
            subscription_name: Service Bus subscription name
        """
        self.agent_name = agent_name
        self.subscription_name = subscription_name
        self.settings = get_settings()
        self.logger = setup_logger(agent_name, level=self.settings.log_level)
        
        # Initialize clients
        self.service_bus_client: Optional[ServiceBusClient] = None
        self.table_storage_client: Optional[TableStorageClient] = None
    
    def initialize(self) -> None:
        """Initialize agent resources."""
        self.logger.info(f"Initializing {self.agent_name}...")
        
        # Initialize Table Storage client
        self.table_storage_client = TableStorageClient(
            self.settings.storage_connection_string
        )
        
        self.logger.info(f"{self.agent_name} initialized successfully")
    
    def run(self) -> None:
        """
        Main agent run loop.
        Continuously polls for messages and processes them.
        """
        self.logger.info(f"Starting {self.agent_name}...")
        
        try:
            with ServiceBusClient(
                self.settings.service_bus_host_name,
                self.settings.service_bus_topic_name
            ) as sb_client:
                self.service_bus_client = sb_client
                
                with sb_client.get_subscription_receiver(self.subscription_name) as receiver:
                    self.logger.info(f"{self.agent_name} listening for messages...")
                    
                    for message in receiver:
                        try:
                            self._process_message(message)
                            receiver.complete_message(message)
                            
                        except Exception as e:
                            self.logger.error(f"Error processing message: {e}", exc_info=True)
                            # Dead-letter the message
                            receiver.dead_letter_message(
                                message,
                                reason="ProcessingError",
                                error_description=str(e)
                            )
        
        except KeyboardInterrupt:
            self.logger.info(f"{self.agent_name} stopped by user")
        except Exception as e:
            self.logger.error(f"Fatal error in {self.agent_name}: {e}", exc_info=True)
            raise
    
    def _process_message(self, message: ServiceBusMessage) -> None:
        """
        Process a Service Bus message.
        
        Args:
            message: Service Bus message
        """
        try:
            # Parse message body
            body = json.loads(str(message))
            invoice_id = body.get("invoice_id")
            
            self.logger.info(
                f"Processing message: subject={message.subject}, "
                f"invoice_id={invoice_id}"
            )
            
            # Call agent-specific processing logic
            result = self.process_invoice(invoice_id, body)
            
            # Publish next state message if processing succeeded
            if result:
                self._publish_next_state(invoice_id, result)
            
            self.logger.info(f"Successfully processed invoice {invoice_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to process message: {e}", exc_info=True)
            raise
    
    @abstractmethod
    def process_invoice(self, invoice_id: str, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
    
    def _publish_next_state(self, invoice_id: str, data: Dict[str, Any]) -> None:
        """
        Publish message for next state transition.
        
        Args:
            invoice_id: Invoice ID
            data: Message payload
        """
        next_subject = self.get_next_subject()
        
        if next_subject:
            self.service_bus_client.publish_message(
                invoice_id=invoice_id,
                subject=next_subject,
                data=data
            )
            self.logger.info(f"Published {next_subject} for invoice {invoice_id}")
    
    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """
        Get invoice from Table Storage.
        
        Args:
            invoice_id: Invoice ID
            
        Returns:
            Invoice entity or None
        """
        return self.table_storage_client.get_entity(
            table_name=self.settings.invoices_table_name,
            partition_key="invoice",
            row_key=invoice_id
        )
    
    def update_invoice(self, invoice: Dict[str, Any]) -> None:
        """
        Update invoice in Table Storage.
        
        Args:
            invoice: Invoice entity to update
        """
        self.table_storage_client.update_entity(
            table_name=self.settings.invoices_table_name,
            entity=invoice,
            mode="merge"
        )
