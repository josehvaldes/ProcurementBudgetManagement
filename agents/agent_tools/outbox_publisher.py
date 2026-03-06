


import asyncio
import signal
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from invoice_lifecycle_api.application.interfaces.service_interfaces import CompareOperator, JoinOperator
from shared.config.settings import settings
from shared.utils.constants import AgentNames, SubscriptionNames
from shared.utils.logging_config import get_logger, setup_logging
from invoice_lifecycle_api.infrastructure.messaging.servicebus_messaging_service import ServiceBusMessagingService
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService

setup_logging(
    log_level=settings.log_level,
    log_file=settings.log_file,
    log_to_console=settings.log_to_console
)
logger = get_logger(__name__)

scheduler = AsyncIOScheduler()
shutdown_event = asyncio.Event()

class OutboxPublisher:
    
    MAX_BATCH_SIZE = settings.outbox_max_batch_size  # Max number of messages to publish in one batch

    def __init__(self):

        self.service_bus_client: Optional[ServiceBusMessagingService] = None
        self.outbox_table: Optional[TableStorageService] = None
        self._initialize_resources()
    
    def _initialize_resources(self):
        """Initialize resources like Service Bus client and Table Storage service."""
        try:
            logger.info("Initializing resources for OutboxPublisher",
                        extra={
                            "service_bus_host_name": settings.service_bus_host_name,
                            "table_storage_account_url": settings.table_storage_account_url,
                            "out_box_queue_table_name": settings.out_box_queue_table_name
                        })
            self.service_bus_client = ServiceBusMessagingService(
                host_name=settings.service_bus_host_name
            )
            logger.info("Service Bus client initialized successfully")

            self.outbox_table = TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.out_box_queue_table_name
            )
            logger.debug("Outbox Table Storage service initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing resources: {str(e)}", exc_info=True)
            raise

    async def publish_outbox_messages(self):
        """Check the outbox table for messages and publish them to Service Bus."""
        try:
            agent_names = [
                AgentNames.INTAKE_AGENT,
                AgentNames.VALIDATION_AGENT,
                AgentNames.BUDGET_AGENT,
                AgentNames.APPROVAL_AGENT,
                AgentNames.PAYMENT_AGENT,
            ]

            logger.info("Checking outbox for messages to publish")
            for agent_name in agent_names:
                filters =  [("PartitionKey", agent_name, CompareOperator.EQUAL.value)]
                logger.info(f"Querying outbox for agent '{agent_name}'",
                             extra={
                                 "filters": filters
                             })
                entities = await self.outbox_table.query_entities_with_filters(
                    filters=filters,
                    max_size=self.MAX_BATCH_SIZE
                )
                if entities and len(entities) > 0:
                    logger.info(f"Found {len(entities)} messages for agent '{agent_name}' to publish",
                                extra={"message_count": len(entities)})
                    for entity in entities:
                        body = {
                            "invoice_id": entity.get("invoice_id"),
                            "department_id": entity.get("department_id"),
                            "state": entity.get("state"),
                            "correlation_id": entity.get("correlation_id"),
                            "event_type": entity.get("event_type"),
                        }
                        message_payload = {
                            "subject": entity.get("subject"),
                            "body": body,
                            "correlation_id": entity.get("correlation_id"),
                        }
                        try:
                            row_key = entity.get("compound_key")
                            await self.service_bus_client.publish_message(
                                topic=settings.service_bus_topic_name,
                                message_data=message_payload
                            )
                            logger.info(f"Published message to Service Bus for agent '{agent_name}'",
                                         extra={"message_id": message_payload.get("RowKey")})
                            partition_key = entity.get("agent_name")
                            
                            # Delete the message from the outbox after successful publish
                            await self.outbox_table.delete_entity(
                                partition_key=partition_key,
                                row_key=row_key
                            )
                        except Exception as e:
                            logger.error(f"Error publishing message for agent '{agent_name}': {str(e)}",
                                         exc_info=True,
                                         extra={"message_id": row_key})
                else:
                    logger.debug(f"No messages found in outbox for agent: '{agent_name}'")

            logger.debug("Outbox check completed successfully")
        except Exception as e:
            logger.error(f"Error publishing outbox messages: {str(e)}", exc_info=True)

    async def close(self):
        """Close any open resources."""
        errors = []
        try:
            logger.info("Closing resources for OutboxPublisher")
            if self.service_bus_client:
                await self.service_bus_client.close()
                logger.debug("Service Bus client closed successfully")
            # If there are other resources to close, do it here
        except Exception as e:
            logger.error(f"Error closing resources: {str(e)}", exc_info=True)
            errors.append(f"Error closing resources: {str(e)}")

        try:
            if self.outbox_table:
                await self.outbox_table.close()
                logger.debug("Outbox Table Storage service closed successfully")
        except Exception as e:
            logger.error(f"Error closing Outbox Table Storage service: {str(e)}", exc_info=True)
            errors.append(f"Error closing Outbox Table Storage service: {str(e)}")

        if errors:
            logger.warning(
                f"Resource cleanup completed with {len(errors)} errors",
                extra={"cleanup_errors": errors}
            )
        else:
            logger.info("All resources released successfully")

    async def __aenter__(self) -> "OutboxPublisher":
        """Enter async context manager."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager and close resources."""
        await self.close()

def setup_signal_handlers() -> None:
    """
    Configure signal handlers for graceful shutdown.
    
    Registers handlers for:
    - SIGINT (Ctrl+C)
    - SIGTERM (kill command)
    - SIGBREAK (Ctrl+Break on Windows)
    When a signal is received, sets the shutdown_event to trigger
    graceful agent termination.
    """
    logger.info(
        "Setting up signal handlers for graceful shutdown",
    )
    
    def handle_shutdown_signal(sig: int, frame) -> None:
        """Handle shutdown signals by setting shutdown event."""
        try:
            sig_name = signal.Signals(sig).name
            logger.info(
                f"Received {sig_name} signal, initiating graceful shutdown",
                extra={
                    "signal": sig_name
                }
            )
            shutdown_event.set()
            scheduler.shutdown(wait=True)
            logger.info("Scheduler shutdown initiated successfully")
        except Exception as e:
            logger.error(
                f"Error handling shutdown signal: {str(e)}",
                exc_info=True
            )
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown_signal)   # Ctrl+C
    signal.signal(signal.SIGTERM, handle_shutdown_signal)  # kill command
    
    # Windows-specific: Ctrl+Break
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, handle_shutdown_signal)
    
    logger.debug("Signal handlers registered successfully")

async def check_outbox(publisher: OutboxPublisher):
    try:
        await publisher.publish_outbox_messages()
    except Exception as e:
        logger.error(f"Error in check_outbox: {str(e)}", exc_info=True)

async def main():
    logger.info("Starting Outbox Publisher Agent")
    setup_signal_handlers()
    interval_time = settings.outbox_poll_interval_seconds
    async with OutboxPublisher() as publisher:
        logger.info("Signal handlers set up successfully.")
        scheduler.add_job(check_outbox, 'interval', 
                          seconds=interval_time, 
                          kwargs={"publisher": publisher}
                          )
        scheduler.start()
        while not shutdown_event.is_set():
            print("sleeping...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
