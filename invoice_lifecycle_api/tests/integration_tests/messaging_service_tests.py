import argparse
import asyncio
import json
import signal

import traceback
import uuid

from invoice_lifecycle_api.infrastructure.messaging.subscription_receiver_wrapper import SubscriptionReceiverWrapper
from shared.config.settings import settings
from shared.utils.constants import SubscriptionNames
from shared.utils.logging_config import get_logger, setup_logging
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from invoice_lifecycle_api.application.interfaces.service_interfaces import MessagingServiceInterface
from invoice_lifecycle_api.infrastructure.messaging.servicebus_messaging_service import ServiceBusMessagingService

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)


class MessagingServiceTests:

    def __init__(self):
        self.messaging_service: MessagingServiceInterface = None
        self.receivers: list[SubscriptionReceiverWrapper] = []
        self.shutdown_event: asyncio.Event = asyncio.Event()

    def setup(self):
        """Setup signal handlers.""" 
        def handle_signal(sig, frame):
            sig_name = signal.Signals(sig).name
            print(f"\n🛑 Received {sig_name}, initiating shutdown...")
            self.shutdown_event.set()
            print(f"\n Shutdown event set to {self.shutdown_event.is_set()}. {len(self.receivers)} receivers to close.")
            print("Cleanup tasks completed. Exiting now.")

        # Handle Ctrl+C (SIGINT) and kill command (SIGTERM)
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        # On Windows, also handle SIGBREAK (Ctrl+Break)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, handle_signal)


    def setup_method(self):
        self.messaging_service: MessagingServiceInterface = ServiceBusMessagingService(
            host_name=settings.service_bus_host_name,
            topic_name=settings.service_bus_topic_name
        )

        
    async def test_send_message(self):
        try:
            invoice_data = {
                "invoice_id": "d7224a169011",
                "event_type": "APIInvoiceUploaded",                    
                "department_id": "dept_8d6014",
            }
            message_data = {
                "subject": "invoice.created",
                "body": {
                    "event_type": invoice_data["event_type"],
                    "department_id": invoice_data["department_id"],
                    "invoice_id": invoice_data["invoice_id"],
                }
            }
            print(f"Sending test message to topic 'invoice-events'")
            await self.messaging_service.publish_message(settings.service_bus_topic_name, message_data)
            print(f"Sent test message with ID: {invoice_data['invoice_id']}")

        except Exception as e:
            print(f"Error sending test message: {e}")
            print(f"Message data: {message_data}")
            traceback.print_exc()

    async def test_single_receive_message(self):
        try:
            subscription_name = SubscriptionNames.INTAKE_AGENT
            print(f"Getting subscription receiver for topic 'invoice-events' and subscription '{subscription_name}'")
            
            receiver: SubscriptionReceiverWrapper
            async with self.messaging_service.get_subscription_receiver(
                subscription=subscription_name,
                shutdown_event=self.shutdown_event
            ) as receiver:
                self.receivers.append(receiver)
                print("Receiving messages...")
                received_messages = await receiver.receive_messages(max_message_count=5, max_wait_time=10)
                for msg in received_messages:
                    print("Received subject:", msg.subject)
                    body = json.loads(str(msg))
                    print(f"Received message: {body}")
                    await receiver.complete_message(msg)
                if not received_messages:
                    print("No messages received.")
        except Exception as e:
            print(f"Error receiving messages: {e}")
            traceback.print_exc()

    async def test_iterative_receive_messages(self):
        try:
            subscription_name = SubscriptionNames.INTAKE_AGENT
            print(f"Getting subscription receiver for topic 'invoice-events' and subscription '{subscription_name}'")
            receiver: SubscriptionReceiverWrapper
            async with self.messaging_service.get_subscription_receiver(
                subscription=subscription_name,
                shutdown_event=self.shutdown_event
            ) as receiver:
                counter = 1
                self.receivers.append(receiver)
                print("Iteratively receiving messages...")
                async for msg in receiver:
                    
                    if self.shutdown_event.is_set():
                        print("Shutdown signal received, stopping message receiving...")
                        break

                    print(f"  {counter} Received message: {msg}")
                    await receiver.complete_message(msg)
                    counter += 1

            print(f"Total messages received: {counter}")
        except StopAsyncIteration:
            print("No more messages to receive, exiting iteration.")
        except Exception as e:
            print(f"Error during iterative message receiving: {e}")
            traceback.print_exc()


    async def close_repositories(self):
        await self.messaging_service.close()
        credential_manager = get_credential_manager()
        await credential_manager.close()

async def main():
    test_instance = MessagingServiceTests()
    test_instance.setup()
    test_instance.setup_method()
    
    parser = argparse.ArgumentParser(description="Azure Storage Messaging Service Tests")
    parser.add_argument("action", type=str, help="Action to perform: send, receive, iterative",
                       choices=["send", "receive", "iterative"])
    args = parser.parse_args()
    
    logger.info(f"Running test for action: {args.action}")
    
    # Map actions to test methods
    test_map = {
        "send": test_instance.test_send_message,
        "receive": test_instance.test_single_receive_message,
        "iterative": test_instance.test_iterative_receive_messages,
    }

    # Run the selected test
    test_method = test_map.get(args.action)
    if test_method:
        await test_method()

    await test_instance.close_repositories()
    
    print("All tests completed.")

if __name__ == "__main__":
    asyncio.run(main())