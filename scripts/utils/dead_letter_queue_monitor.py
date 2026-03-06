


import argparse
import asyncio
import json
import signal
import traceback
from typing import Optional
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.config.settings import settings
from shared.utils.constants import SubscriptionNames
from shared.utils.logging_config import get_logger, setup_logging
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager

from azure.servicebus import ServiceBusReceivedMessage, ServiceBusSubQueue
from invoice_lifecycle_api.application.interfaces.service_interfaces import TableServiceInterface
from invoice_lifecycle_api.infrastructure.messaging.servicebus_messaging_service import ServiceBusMessagingService
from invoice_lifecycle_api.infrastructure.messaging.subscription_receiver_wrapper import SubscriptionReceiverWrapper

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)


class DeadLetterQueueMonitor:
    def __init__(self, 
                 service_bus_client:ServiceBusMessagingService, 
                 dead_letter_table: TableServiceInterface,
                 shutdown_event: Optional[asyncio.Event] = None
                 ):
        self.service_bus_client = service_bus_client
        self.dead_letter_table = dead_letter_table
        self.shutdown_event = shutdown_event

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def handle_signal(sig, frame):
            sig_name = signal.Signals(sig).name
            logger.info(f"Received {sig_name}, initiating shutdown...")
            if self.shutdown_event:
                self.shutdown_event.set()
                logger.info(f"Shutdown event set to {self.shutdown_event.is_set()}.")
            else:
                logger.warning("No shutdown event provided, cannot signal receivers to stop.")
            logger.info("Cleanup tasks completed. Exiting now.")

        # Handle Ctrl+C (SIGINT) and kill command (SIGTERM)
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        # On Windows, also handle SIGBREAK (Ctrl+Break)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, handle_signal)

    def shutdown(self):
        pass


    async def monitor_dead_queue(self, queue_name, max_message_count=10):
        messages = []

        try:
            receiver: SubscriptionReceiverWrapper
            async with self.service_bus_client.get_subscription_dead_letter_receiver(
                subscription=queue_name,
                shutdown_event=self.shutdown_event,
                peek_mode=True
            ) as receiver:
                logger.info(f"Started monitoring dead letter queue for subscription '{queue_name}'...")
                received_messages = await receiver.receive_messages(
                    max_message_count=max_message_count,
                    max_wait_time=30
                )
                logger.info(f"Received messages from dead letter queue of subscription '{queue_name}': {len(received_messages)}")
                for msg in received_messages:
                    msg: ServiceBusReceivedMessage = msg
                    data = {
                        "message_id": msg.message_id,
                        "body": json.loads(str(msg)),
                        "enqueued_time": msg.enqueued_time_utc.isoformat() if msg.enqueued_time_utc else None,
                        "dead_letter_reason": msg.dead_letter_reason,
                        "dead_letter_error_description": msg.dead_letter_error_description,
                        "subject": msg.subject,
                        "sequence_number": msg.sequence_number,
                        "delivery_count": msg.delivery_count,
                        "content_type": msg.content_type,
                        "enqueued_sequence_number": msg.enqueued_sequence_number,
                    }
                    messages.append(data)

            return messages
        except Exception as e:
            logger.error(f" * Error monitoring dead letter queue: {e}")
            raise


    async def transfer_dead_letter_messages(self, source_queue_name):
        """Transfer messages from the dead letter queue of source_queue_name to Azure table."""

        try:

            receiver: SubscriptionReceiverWrapper
            async with self.service_bus_client.get_subscription_dead_letter_receiver(
                subscription=source_queue_name,
                shutdown_event=self.shutdown_event,
                peek_mode=False
            ) as receiver:
                logger.info(f"Started transferring messages from dead letter queue of subscription '{source_queue_name}' to Azure table...")
                async for message in receiver:

                    if self.shutdown_event and self.shutdown_event.is_set():
                        logger.info("Shutdown event set, stopping transfer of messages from dead letter queue.")
                        break

                    msg: ServiceBusReceivedMessage = message
                    body = json.loads(str(msg))
                    department_id = body.get("department_id", None)
                    invoice_id = body.get("invoice_id", None)
                    logger.info(f"Processing message for invoice_id: {invoice_id}, department_id: {department_id}")
                    if not invoice_id or not department_id:
                        logger.warning(f"Message is missing required properties. invoice_id: {invoice_id}, department_id: {department_id}. Skipping message.")
                        await receiver.complete_message(msg)
                        continue

                    message_data = {
                        "message_id": msg.message_id,
                        "body": json.dumps(body),
                        "enqueued_time": msg.enqueued_time_utc.isoformat() if msg.enqueued_time_utc else None,
                        "dead_letter_reason": msg.dead_letter_reason,
                        "dead_letter_error_description": msg.dead_letter_error_description,
                        "subject": msg.subject,
                        "sequence_number": msg.sequence_number,
                        "delivery_count": msg.delivery_count,
                        "content_type": msg.content_type,
                        "enqueued_sequence_number": msg.enqueued_sequence_number,
                    }
                    partition_key = department_id
                    # Use invoice_id and message_id to ensure uniqueness in the dead letter table and to easily identify the source of the message
                    row_key = f"{invoice_id}:{msg.message_id}" 
                    if self.dead_letter_table:
                        await self.dead_letter_table.upsert_entity(message_data, 
                                                                partition_key=partition_key, 
                                                                row_key=row_key
                        )
                    # Complete the message in the dead letter queue
                    await receiver.complete_message(msg)
        except asyncio.CancelledError:
            logger.info("processing cancelled")
        except StopAsyncIteration:
            logger.warning("No more messages available, exiting message loop")
        except Exception as e:
            logger.error(f" * Error transferring messages from dead letter queue: {e}")
            raise

def print_messages_data(messages:list):
    logger.info(f"Total messages in dead letter queue: {len(messages)}")
    for msg in messages:
        line = f" Message ID: {msg['message_id']}, Subject: {msg['subject']}, Enqueued Time: {msg['enqueued_time']}, Dead Letter Reason: {msg['dead_letter_reason']}"
        logger.info(line)
        body = msg.get("body", None)
        if body:
            logger.info(f"   Message body: {body}")


async def main():
    # Initialize the ServiceBusMessagingService and TableServiceInterface here
    parser = argparse.ArgumentParser(description="Azure Dead Letter Queue Monitor")
    parser.add_argument("queue_name", type=str, help="Name of the queue to monitor",
                    choices=[SubscriptionNames.INTAKE_AGENT, SubscriptionNames.APPROVAL_AGENT, 
                                SubscriptionNames.BUDGET_AGENT, SubscriptionNames.PAYMENT_AGENT, 
                                SubscriptionNames.VALIDATION_AGENT])
    parser.add_argument("--action", type=str, help="Action to perform: monitor or transfer",
                        choices=["monitor", "transfer"], default="monitor")
    parser.add_argument("--max_msg", type=int, help="Maximum number of messages to retrieve from the dead letter queue", default=10)

    args = parser.parse_args()
    queue_name = args.queue_name
    logger.info(f"Running test for action: {args.action}")
    max_message_count = int(args.max_msg)  if args.action == "monitor" else 0
    logger.info(f"Starting dead letter queue monitor with action: {args.action} for queue: {args.queue_name} and max_messages: {max_message_count}")
    shutdown_event = asyncio.Event()

    try:
        service_bus_client: ServiceBusMessagingService
        async with ServiceBusMessagingService(
            host_name=settings.service_bus_host_name,
            topic_name=settings.service_bus_topic_name,
            auto_close=True
        ) as service_bus_client:

            async with TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.dead_letter_table_name,
                standalone=True
            ) as table_service_client:

                monitor = DeadLetterQueueMonitor(service_bus_client, table_service_client, shutdown_event)

                if args.action == "monitor":
                    messages = await monitor.monitor_dead_queue(queue_name, max_message_count=max_message_count)
                    print_messages_data(messages)
                elif args.action == "transfer":
                    logger.info(f"Transferring messages from dead letter queue of subscription '{queue_name}' to Azure table...")
                    logger.info(f"Ignoring max_messages parameter for transfer action, will transfer all messages in the dead letter queue.")
                    await monitor.transfer_dead_letter_messages(queue_name)

    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error monitoring dead letter queue: {e}")


if __name__ == "__main__":
    asyncio.run(main())