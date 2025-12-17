import argparse
import os
import asyncio
from azure.servicebus import ServiceBusMessage, ServiceBusSender
from azure.servicebus.aio import ServiceBusClient
from azure.identity.aio import DefaultAzureCredential

FULLY_QUALIFIED_NAMESPACE = os.environ["SERVICE_BUS_CONNECTION_STRING"]
TOPIC_NAME = os.environ["SERVICE_BUS_TOPIC_NAME"]
SUBSCRIPTION_NAME = "intake-agent-subscription" #os.environ["SERVICEBUS_SUBSCRIPTION_NAME"]
credential = DefaultAzureCredential()

async def send_single_message(sender:ServiceBusSender):

    message = ServiceBusMessage(
        subject="invoice.created",
        body="{'data':'sample data'}",
        content_type="application/json",
        correlation_id="12345",
        message_id="msg-001"
        )
    try:

        print("Sending a single message...")
        await sender.send_messages(message)
        print("Single message sent.")
    except Exception as e:
        print(f"Error occurred while sending single message: {e}")


async def main_send():
    servicebus_client = ServiceBusClient(FULLY_QUALIFIED_NAMESPACE, credential, logging_enable=True)

    async with servicebus_client:
        sender = servicebus_client.get_topic_sender(topic_name=TOPIC_NAME)
        async with sender:
            await send_single_message(sender)
            # await send_a_list_of_messages(sender)
            # await send_batch_message(sender)

    print("Send message is done.")



    print("\nDemonstrating concurrent sending with shared client and locks...")
    #await send_concurrent_with_shared_client_and_lock()

async def main_receive():
    
    servicebus_client = ServiceBusClient(FULLY_QUALIFIED_NAMESPACE, credential)

    async with servicebus_client:
        receiver = servicebus_client.get_subscription_receiver(
            topic_name=TOPIC_NAME, subscription_name=SUBSCRIPTION_NAME
        )
        async with receiver:
            print("Receiving messages from subscription...")
            received_msgs = await receiver.receive_messages(max_message_count=10, max_wait_time=5)
            for msg in received_msgs:
                print(f"  Message: {str(msg)}")
                await receiver.complete_message(msg)
            print("Message receiving is done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Service Bus Client Test Scenarios")
    parser.add_argument("action", type=str, help="Action to perform: send or receive", choices=["send", "receive"])
    args = parser.parse_args()
    if args.action == "send":
        print("Send action selected.")
        asyncio.run(main_send())
    elif args.action == "receive":
        print("Receive action selected")
        asyncio.run(main_receive())
    
