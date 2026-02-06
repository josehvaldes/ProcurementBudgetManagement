"""
Base Agent - Abstract foundation for all invoice processing agents.

This module provides the core infrastructure for agent-based invoice processing:
- Service Bus message consumption and publishing
- Table Storage operations for invoice persistence
- Graceful shutdown handling
- Structured logging and observability
- Error handling and retry logic
- LangSmith tracing integration

All concrete agents (IntakeAgent, ValidationAgent, BudgetAgent, etc.) inherit
from this base class and implement the abstract methods for their specific
processing logic.
"""

import asyncio
import signal
import time
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from azure.servicebus import ServiceBusReceivedMessage
from azure.core.exceptions import AzureError

from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from invoice_lifecycle_api.infrastructure.messaging.servicebus_messaging_service import ServiceBusMessagingService
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.models.invoice import InvoiceInternalMessage, InvoiceState
from shared.utils.logging_config import get_logger, setup_logging
from shared.config.settings import settings
from shared.utils.exceptions import (
    InvoiceNotFoundException,
    StorageException,
    MessagingException
)

# Configure logging
setup_logging(
    log_level=settings.log_level,
    log_file=settings.log_file,
    log_to_console=settings.log_to_console
)


class BaseAgent(ABC):
    """
    Abstract base class for all invoice processing agents.
    
    This class provides the foundational infrastructure for agent-based processing:
    
    **Message Processing:**
    - Service Bus topic subscription and message consumption
    - Automatic message completion, abandonment, and dead-lettering
    - Retry logic for transient failures
    
    **Data Operations:**
    - Invoice retrieval and updates via Table Storage
    - State transition management
    - Internal message logging
    
    **Observability:**
    - Structured logging with correlation IDs
    - LangSmith distributed tracing
    - Performance metrics and latency tracking
    
    **Lifecycle Management:**
    - Graceful shutdown signal handling (SIGINT, SIGTERM, SIGBREAK)
    - Resource cleanup and connection pooling
    - Error recovery and dead-letter queue management
    
    Concrete agents must implement:
    - process_invoice(): Core business logic for invoice processing
    - get_next_subject(): Define next message subject for state transitions
    - release_resources(): Clean up agent-specific resources
    """
    
    def __init__(
        self,
        agent_name: str,
        subscription_name: str,
        shutdown_event: Optional[asyncio.Event] = None
    ):
        """
        Initialize the base agent with core dependencies.
        
        Args:
            agent_name: Agent identifier for logging and tracing (e.g., "IntakeAgent")
            subscription_name: Service Bus subscription name for this agent
            shutdown_event: Optional event for coordinated shutdown across agents
        """
        self.logger = get_logger(agent_name)
        
        self.agent_name = agent_name
        self.subscription_name = subscription_name
        self.topic_name = settings.service_bus_topic_name
        self.shutdown_event = shutdown_event or asyncio.Event()
        
        # Azure service clients (initialized in initialize_clients)
        self.service_bus_client: Optional[ServiceBusMessagingService] = None
        self.invoice_table_client: Optional[TableStorageService] = None
        
        # Initialize infrastructure
        self._initialize_clients()
        
        self.logger.info(
            f"{self.agent_name} instance created",
            extra={
                "agent_name": agent_name,
                "subscription": subscription_name,
                "topic": self.topic_name
            }
        )
    
    def _initialize_clients(self) -> None:
        """
        Initialize Azure service clients for the agent.
        
        Creates connections to:
        - Azure Table Storage (for invoice persistence)
        - Azure Service Bus (for message-driven processing)
        
        Raises:
            AzureError: If client initialization fails
        """
        self.logger.info(
            f"Initializing Azure clients for {self.agent_name}",
            extra={
                "storage_account": settings.table_storage_account_url,
                "table_name": settings.invoices_table_name,
                "service_bus_host": settings.service_bus_host_name,
                "topic": settings.service_bus_topic_name
            }
        )
        
        try:
            # Initialize Table Storage client for invoice persistence
            self.invoice_table_client = TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.invoices_table_name
            )
            self.logger.debug("Table Storage client initialized successfully")
            
            # Initialize Service Bus client for message processing
            self.service_bus_client = ServiceBusMessagingService(
                host_name=settings.service_bus_host_name,
                topic_name=settings.service_bus_topic_name
            )
            self.logger.debug("Service Bus client initialized successfully")
            
            self.logger.info(
                f"{self.agent_name} Azure clients initialized successfully",
                extra={"agent_name": self.agent_name}
            )
            
        except AzureError as e:
            self.logger.error(
                f"Failed to initialize Azure clients: {str(e)}",
                exc_info=True,
                extra={
                    "agent_name": self.agent_name,
                    "error_type": type(e).__name__
                }
            )
            raise
        except Exception as e:
            self.logger.error(
                f"Unexpected error initializing clients: {str(e)}",
                exc_info=True,
                extra={
                    "agent_name": self.agent_name,
                    "error_type": type(e).__name__
                }
            )
            raise
    
    def setup_signal_handlers(self) -> None:
        """
        Configure signal handlers for graceful shutdown.
        
        Registers handlers for:
        - SIGINT (Ctrl+C)
        - SIGTERM (kill command)
        - SIGBREAK (Ctrl+Break on Windows)
        
        When a signal is received, sets the shutdown_event to trigger
        graceful agent termination.
        """
        self.logger.info(
            "Setting up signal handlers for graceful shutdown",
            extra={"agent_name": self.agent_name}
        )
        
        def handle_shutdown_signal(sig: int, frame) -> None:
            """Handle shutdown signals by setting shutdown event."""
            try:
                sig_name = signal.Signals(sig).name
                self.logger.info(
                    f"Received {sig_name} signal, initiating graceful shutdown",
                    extra={
                        "agent_name": self.agent_name,
                        "signal": sig_name
                    }
                )
                self.shutdown_event.set()
            except Exception as e:
                self.logger.error(
                    f"Error handling shutdown signal: {str(e)}",
                    exc_info=True
                )
        
        # Register signal handlers
        signal.signal(signal.SIGINT, handle_shutdown_signal)   # Ctrl+C
        signal.signal(signal.SIGTERM, handle_shutdown_signal)  # kill command
        
        # Windows-specific: Ctrl+Break
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, handle_shutdown_signal)
        
        self.logger.debug("Signal handlers registered successfully")
    
    async def run(self) -> None:
        """
        Main agent run loop - continuously processes messages until shutdown.
        
        This method:
        1. Establishes Service Bus subscription receiver
        2. Continuously receives and processes messages
        3. Handles message completion, abandonment, and dead-lettering
        4. Monitors shutdown event for graceful termination
        5. Performs cleanup on exit
        
        The loop runs indefinitely until:
        - Shutdown signal is received (SIGINT, SIGTERM)
        - Fatal error occurs
        - Cancellation is requested
        
        Raises:
            Exception: On fatal errors that prevent agent operation
        """
        self.logger.info(
            f"Starting {self.agent_name} run loop",
            extra={
                "agent_name": self.agent_name,
                "subscription": self.subscription_name,
                "topic": self.topic_name
            }
        )
        
        try:
            async with self.service_bus_client.get_subscription_receiver(
                subscription=self.subscription_name,
                shutdown_event=self.shutdown_event
            ) as receiver:
                
                self.logger.info(
                    f"{self.agent_name} listening for messages",
                    extra={
                        "agent_name": self.agent_name,
                        "subscription": self.subscription_name
                    }
                )
                
                async for message in receiver:
                    # Check for shutdown request
                    if self.shutdown_event.is_set():
                        self.logger.info(
                            f"Shutdown event detected, stopping message processing",
                            extra={"agent_name": self.agent_name}
                        )
                        break
                    
                    # Process message with timing and tracing
                    await self._process_message_with_metrics(message, receiver)
                    
        except asyncio.CancelledError:
            self.logger.info(
                f"{self.agent_name} processing cancelled",
                extra={"agent_name": self.agent_name}
            )
        except StopAsyncIteration:
            self.logger.warning(
                "No more messages available, exiting message loop",
                extra={"agent_name": self.agent_name}
            )
        except Exception as e:
            self.logger.error(
                f"Fatal error in {self.agent_name} run loop: {str(e)}",
                exc_info=True,
                extra={
                    "agent_name": self.agent_name,
                    "error_type": type(e).__name__
                }
            )
            raise
        finally:
            await self._shutdown()

    async def _process_message_with_metrics(
        self,
        message: ServiceBusReceivedMessage,
        receiver
    ) -> None:
        """
        Process a message with performance metrics and error handling.
        
        Args:
            message: Service Bus message to process
            receiver: Service Bus receiver for message completion/abandonment
        """
        run = get_current_run_tree()
        start_time = time.time()
        message_id = message.message_id
        
        try:
            # Process the message
            processing_result = await self._process_message(message)
            
            # Handle message based on processing result
            if processing_result.success:
                await receiver.complete_message(message)
                self.logger.info(
                    f"Message completed successfully",
                    extra={
                        "agent_name": self.agent_name,
                        "message_id": message_id,
                        "invoice_id": processing_result.invoice_id,
                        "processing_time_ms": (time.time() - start_time) * 1000
                    }
                )
            else:
                # Send to dead-letter queue with reason
                await receiver.dead_letter_message(
                    message,
                    reason=processing_result.failure_reason or "ProcessingIncomplete",
                    error_description=processing_result.failure_description or "Message processing did not complete successfully"
                )
                self.logger.warning(
                    f"Message dead-lettered: {processing_result.failure_reason}",
                    extra={
                        "agent_name": self.agent_name,
                        "message_id": message_id,
                        "invoice_id": processing_result.invoice_id,
                        "reason": processing_result.failure_reason
                    }
                )
                
        except Exception as e:
            # Fatal error - send to dead-letter queue
            self.logger.error(
                f"Fatal error processing message: {str(e)}",
                exc_info=True,
                extra={
                    "agent_name": self.agent_name,
                    "message_id": message_id,
                    "error_type": type(e).__name__
                }
            )
            
            await receiver.dead_letter_message(
                message,
                reason="ProcessingError",
                error_description=str(e)
            )
        finally:
            # Add metrics to LangSmith trace
            processing_time_ms = (time.time() - start_time) * 1000
            if run:
                run.add_metadata({
                    "total_latency_ms": processing_time_ms,
                    "agent": self.agent_name,
                    "message_id": message_id
                })
            
            self.logger.debug(
                f"Message processing completed",
                extra={
                    "agent_name": self.agent_name,
                    "message_id": message_id,
                    "processing_time_ms": processing_time_ms
                }
            )

    @traceable(
        name="base_agent.process_message",
        tags=["base", "agent", "message_processing"],
        metadata={"version": "1.0"}
    )
    async def _process_message(
        self,
        message: ServiceBusReceivedMessage
    ) -> 'MessageProcessingResult':
        """
        Process a Service Bus message and manage state transitions.
        
        This method:
        1. Parses and validates the message payload
        2. Delegates to agent-specific processing logic
        3. Publishes next-state messages if applicable
        4. Returns processing result for message completion/abandonment
        
        Args:
            message: Service Bus message containing invoice processing request
            
        Returns:
            MessageProcessingResult indicating success/failure and next steps
        """
        invoice_id = None
        department_id = None
        correlation_id = None
        
        try:
            # Parse message payload
            body = json.loads(str(message))
            invoice_id = body.get("invoice_id")
            department_id = body.get("department_id")
            correlation_id = message.correlation_id if message.correlation_id else invoice_id
            
            
            # Validate required fields
            if not invoice_id or not department_id:
                raise ValueError(
                    "Message missing required fields: invoice_id and department_id are mandatory"
                )
            
            if not invoice_id.strip() or not department_id.strip():
                raise ValueError(
                    "Message contains empty required fields: invoice_id and department_id cannot be empty"
                )
            
            self.logger.info(
                f"Processing message for invoice",
                extra={
                    "agent_name": self.agent_name,
                    "message_subject": message.subject,
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id
                }
            )
            
            # Delegate to agent-specific processing
            processing_result = await self.process_invoice(body)
            
            # Handle processing result
            if processing_result is None:
                self.logger.warning(
                    f"Agent returned None - no state transition will occur",
                    extra={
                        "agent_name": self.agent_name,
                        "invoice_id": invoice_id,
                        "correlation_id": correlation_id
                    }
                )
                return MessageProcessingResult(
                    success=False,
                    invoice_id=invoice_id,
                    failure_reason="NoProcessingResult",
                    failure_description="Agent processing returned None"
                )
            
            # Check invoice state from processing result
            invoice_state = processing_result.get("state")
            
            # Handle state-specific logic
            if invoice_state == InvoiceState.EXTRACTED.value or \
               invoice_state == InvoiceState.VALIDATED.value or \
               invoice_state == InvoiceState.BUDGET_CHECKED.value:
                
                # Successful states - publish next state message
                await self._publish_next_state(invoice_id, processing_result)
                self.logger.info(
                    f"Invoice successfully processed to state {invoice_state}",
                    extra={
                        "agent_name": self.agent_name,
                        "invoice_id": invoice_id,
                        "state": invoice_state,
                        "correlation_id": correlation_id
                    }
                )
                return MessageProcessingResult(
                    success=True,
                    invoice_id=invoice_id,
                    state=invoice_state
                )
                
            elif invoice_state == InvoiceState.MANUAL_REVIEW.value:
                # Requires manual review - no automatic next step
                self.logger.info(
                    f"Invoice requires manual review - no automatic progression",
                    extra={
                        "agent_name": self.agent_name,
                        "invoice_id": invoice_id,
                        "state": invoice_state,
                        "correlation_id": correlation_id
                    }
                )
                return MessageProcessingResult(
                    success=True,
                    invoice_id=invoice_id,
                    state=invoice_state,
                    requires_manual_review=True
                )
                
            elif invoice_state == InvoiceState.FAILED.value:
                # Processing failed - mark as unsuccessful
                self.logger.warning(
                    f"Invoice processing failed",
                    extra={
                        "agent_name": self.agent_name,
                        "invoice_id": invoice_id,
                        "state": invoice_state,
                        "correlation_id": correlation_id
                    }
                )
                return MessageProcessingResult(
                    success=False,
                    invoice_id=invoice_id,
                    state=invoice_state,
                    failure_reason="ProcessingFailed",
                    failure_description="Invoice validation or processing failed"
                )
                
            else:
                # Publish next state for other states (EXTRACTED, BUDGET_CHECKED, etc.)
                await self._publish_next_state(invoice_id, processing_result)
                self.logger.info(
                    f"Invoice processed successfully",
                    extra={
                        "agent_name": self.agent_name,
                        "invoice_id": invoice_id,
                        "state": invoice_state,
                        "correlation_id": correlation_id
                    }
                )
                return MessageProcessingResult(
                    success=True,
                    invoice_id=invoice_id,
                    state=invoice_state
                )
            
        except ValueError as e:
            # Validation error - message format issue
            self.logger.error(
                f"Message validation error: {str(e)}",
                extra={
                    "agent_name": self.agent_name,
                    "invoice_id": invoice_id,
                    "error_type": "ValidationError"
                },
                exc_info=True
            )
            return MessageProcessingResult(
                success=False,
                invoice_id=invoice_id,
                failure_reason="ValidationError",
                failure_description=str(e)
            )
            
        except json.JSONDecodeError as e:
            # Invalid JSON in message
            self.logger.error(
                f"Invalid JSON in message: {str(e)}",
                extra={
                    "agent_name": self.agent_name,
                    "error_type": "JSONDecodeError"
                },
                exc_info=True
            )
            return MessageProcessingResult(
                success=False,
                invoice_id=invoice_id,
                failure_reason="InvalidJSON",
                failure_description=f"Message contains invalid JSON: {str(e)}"
            )
            
        except Exception as e:
            # Unexpected error
            self.logger.error(
                f"Unexpected error processing message: {str(e)}",
                exc_info=True,
                extra={
                    "agent_name": self.agent_name,
                    "invoice_id": invoice_id,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__
                }
            )
            return MessageProcessingResult(
                success=False,
                invoice_id=invoice_id,
                failure_reason=type(e).__name__,
                failure_description=str(e)
            )
    
    async def _publish_next_state(
        self,
        invoice_id: str,
        processing_result: Dict[str, Any]
    ) -> None:
        """
        Publish message for next processing stage.
        
        Args:
            invoice_id: Invoice identifier
            processing_result: Result from invoice processing containing state info
            
        Raises:
            MessagingException: If message publishing fails
        """
        next_subject = self.get_next_subject()
        correlation_id = processing_result.get("correlation_id", invoice_id)
        
        if not next_subject:
            self.logger.debug(
                "No next subject defined - skipping message publication",
                extra={
                    "agent_name": self.agent_name,
                    "invoice_id": invoice_id,
                    "correlation_id": correlation_id
                }
            )
            return
        
        try:
            message_payload = {
                "subject": next_subject,
                "body": processing_result
            }
            
            await self.service_bus_client.publish_message(
                self.topic_name,
                message_payload
            )
            
            self.logger.info(
                f"Published next-state message",
                extra={
                    "agent_name": self.agent_name,
                    "invoice_id": invoice_id,
                    "next_subject": next_subject,
                    "correlation_id": correlation_id
                }
            )
            
        except Exception as e:
            error_msg = f"Failed to publish next-state message: {str(e)}"
            self.logger.error(
                error_msg,
                exc_info=True,
                extra={
                    "agent_name": self.agent_name,
                    "invoice_id": invoice_id,
                    "next_subject": next_subject,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__
                }
            )
            raise MessagingException(error_msg) from e
    
    async def get_invoice(
        self,
        department_id: str,
        invoice_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve invoice from Table Storage.
        
        Args:
            department_id: Partition key (department identifier)
            invoice_id: Row key (invoice identifier)
            
        Returns:
            Invoice entity dictionary or None if not found
            
        Raises:
            StorageException: If retrieval fails (other than not found)
        """
        try:
            invoice_entity = await self.invoice_table_client.get_entity(
                partition_key=department_id,
                row_key=invoice_id
            )
            
            if invoice_entity:
                self.logger.debug(
                    f"Invoice retrieved from storage",
                    extra={
                        "agent_name": self.agent_name,
                        "invoice_id": invoice_id,
                        "department_id": department_id
                    }
                )
            
            return invoice_entity
            
        except Exception as e:
            error_msg = f"Failed to retrieve invoice from storage: {str(e)}"
            self.logger.error(
                error_msg,
                exc_info=True,
                extra={
                    "agent_name": self.agent_name,
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "error_type": type(e).__name__
                }
            )
            raise StorageException(error_msg) from e
    
    async def update_invoice(
        self,
        invoice: Dict[str, Any]
    ) -> bool:
        """
        Update invoice in Table Storage.
        
        Args:
            invoice: Invoice entity to upsert (must contain department_id and invoice_id)
            
        Returns:
            True if update successful, False otherwise
            
        Raises:
            StorageException: If update fails
            ValueError: If required keys are missing
        """
        invoice_id = invoice.get("invoice_id")
        department_id = invoice.get("department_id")
        
        if not invoice_id or not department_id:
            raise ValueError(
                "Invoice must contain 'invoice_id' and 'department_id' fields"
            )
        
        try:
            returned_key = await self.invoice_table_client.upsert_entity(
                entity=invoice,
                partition_key=department_id,
                row_key=invoice_id
            )
            
            success = returned_key == invoice_id
            
            if success:
                self.logger.debug(
                    f"Invoice updated in storage",
                    extra={
                        "agent_name": self.agent_name,
                        "invoice_id": invoice_id,
                        "department_id": department_id
                    }
                )
            else:
                self.logger.warning(
                    f"Invoice update returned unexpected key",
                    extra={
                        "agent_name": self.agent_name,
                        "invoice_id": invoice_id,
                        "returned_key": returned_key
                    }
                )
            
            return success
            
        except Exception as e:
            error_msg = f"Failed to update invoice in storage: {str(e)}"
            self.logger.error(
                error_msg,
                exc_info=True,
                extra={
                    "agent_name": self.agent_name,
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "error_type": type(e).__name__
                }
            )
            raise StorageException(error_msg) from e
    
    def _build_internal_messages(
        self,
        code: str,
        messages: list[str]
    ) -> list[InvoiceInternalMessage]:
        """
        Build standardized internal messages for invoice logging.
        
        Args:
            code: Message code (e.g., "VALIDATION_FAILED", "BUDGET_EXCEEDED")
            messages: List of message strings
            
        Returns:
            List of InvoiceInternalMessage objects with timestamps
        """
        return [
            InvoiceInternalMessage(
                agent=self.agent_name,
                message=msg,
                code=code,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            for msg in messages
        ]
    
    async def _shutdown(self) -> None:
        """
        Perform graceful shutdown and resource cleanup.
        
        This method:
        1. Closes Azure service clients
        2. Releases agent-specific resources
        3. Closes credential manager
        4. Logs shutdown completion
        """
        self.logger.info(
            f"Initiating graceful shutdown for {self.agent_name}",
            extra={"agent_name": self.agent_name}
        )
        
        cleanup_errors = []
        
        # Close Table Storage client
        if self.invoice_table_client:
            try:
                await self.invoice_table_client.close()
                self.logger.debug("Invoice table client closed successfully")
            except Exception as e:
                error_msg = f"Error closing invoice table client: {str(e)}"
                self.logger.warning(error_msg, exc_info=True)
                cleanup_errors.append(error_msg)
        
        # Close Service Bus client
        if self.service_bus_client:
            try:
                await self.service_bus_client.close()
                self.logger.debug("Service Bus client closed successfully")
            except Exception as e:
                error_msg = f"Error closing Service Bus client: {str(e)}"
                self.logger.warning(error_msg, exc_info=True)
                cleanup_errors.append(error_msg)
        
        # Release agent-specific resources
        try:
            await self.release_resources()
            self.logger.debug("Agent-specific resources released")
        except Exception as e:
            error_msg = f"Error releasing agent resources: {str(e)}"
            self.logger.warning(error_msg, exc_info=True)
            cleanup_errors.append(error_msg)
        
        # Close credential manager
        try:
            await get_credential_manager().close()
            self.logger.debug("Credential manager closed successfully")
        except Exception as e:
            error_msg = f"Error closing credential manager: {str(e)}"
            self.logger.warning(error_msg, exc_info=True)
            cleanup_errors.append(error_msg)
        
        # Log shutdown summary
        if cleanup_errors:
            self.logger.warning(
                f"{self.agent_name} shutdown completed with {len(cleanup_errors)} errors",
                extra={
                    "agent_name": self.agent_name,
                    "cleanup_errors": cleanup_errors
                }
            )
        else:
            self.logger.info(
                f"{self.agent_name} shutdown completed successfully",
                extra={"agent_name": self.agent_name}
            )
    
    # ==================== Abstract Methods ====================
    
    @abstractmethod
    async def process_invoice(
        self,
        message_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Process an invoice with agent-specific logic.
        
        This method must be implemented by concrete agent subclasses
        to define their specific processing behavior (extraction,
        validation, budget checking, etc.).
        
        Args:
            message_data: Message payload containing invoice_id, department_id,
                         and any other relevant data for processing
            
        Returns:
            Processing result dictionary containing:
                - invoice_id (str): Invoice identifier
                - department_id (str): Department identifier
                - state (str): New invoice state
                - event_type (str): Type of event that occurred
                - correlation_id (str): Correlation ID for tracing
                - Any agent-specific data
            
            Returns None if processing cannot proceed or no state
            transition should occur.
            
        Raises:
            Exception: On processing failures (will be caught and logged by base class)
        """
        pass
    
    @abstractmethod
    def get_next_subject(self) -> str:
        """
        Get the Service Bus message subject for the next processing stage.
        
        This defines the workflow routing by specifying which agent
        should receive the invoice next.
        
        Returns:
            Message subject string (e.g., "invoice.extracted", "invoice.validated")
            Returns empty string if no next stage exists (terminal state)
        """
        pass
    
    @abstractmethod
    async def release_resources(self) -> None:
        """
        Release agent-specific resources during shutdown.
        
        Concrete agents should override this method to clean up
        any resources they've acquired (AI models, additional
        storage clients, HTTP sessions, etc.).
        
        The base class will call this during graceful shutdown.
        """
        pass


# ==================== Helper Classes ====================

class MessageProcessingResult:
    """
    Result of message processing for completion/abandonment decisions.
    
    Attributes:
        success (bool): Whether processing completed successfully
        invoice_id (str): Invoice identifier
        state (str): Invoice state after processing
        requires_manual_review (bool): Whether manual review is required
        failure_reason (str): Reason code for failure
        failure_description (str): Detailed failure description
    """
    
    def __init__(
        self,
        success: bool,
        invoice_id: Optional[str] = None,
        state: Optional[str] = None,
        requires_manual_review: bool = False,
        failure_reason: Optional[str] = None,
        failure_description: Optional[str] = None
    ):
        self.success = success
        self.invoice_id = invoice_id
        self.state = state
        self.requires_manual_review = requires_manual_review
        self.failure_reason = failure_reason
        self.failure_description = failure_description