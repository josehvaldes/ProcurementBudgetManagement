import asyncio
from datetime import datetime, timedelta, timezone
import json
import traceback
from invoice_lifecycle_api.infrastructure.repositories.invoice_storage_service import InvoiceStorageService
from shared.config.settings import settings
from shared.utils.logging_config import get_logger, setup_logging
from azure.servicebus.aio.management import ServiceBusAdministrationClient
from azure.servicebus.management import SubscriptionRuntimeProperties
from azure.identity.aio import DefaultAzureCredential
from shared.models.invoice import InvoiceState
from invoice_lifecycle_api.application.interfaces.service_interfaces import CompareOperator, JoinOperator
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )

logger = get_logger(__name__)

class MonitorStats:
    
    def __init__(self):
        self.subscriptions = []
        self.invoices = []

    async def log_messaging_stats(self):
        
        async with DefaultAzureCredential() as credential:
            async with ServiceBusAdministrationClient(
                credential=credential,
                fully_qualified_namespace=settings.service_bus_host_name
            ) as admin_client:

                subscriptions = admin_client.list_subscriptions(settings.service_bus_topic_name)
                async for subscription in subscriptions:
                    runtime_info: SubscriptionRuntimeProperties = await admin_client.get_subscription_runtime_properties(
                        topic_name=settings.service_bus_topic_name,
                        subscription_name=subscription.name
                    )
                    
                    self.subscriptions.append({
                        "subscription_name": subscription.name,
                        "status": subscription.status,
                        "message_count": runtime_info.total_message_count,
                        "active": runtime_info.active_message_count,
                        "dead_letter": runtime_info.dead_letter_message_count,
                    })
                    

    async def log_storage_stats(self):
        pass

    async def log_table_stats(self):
        table_client: TableStorageService
        async with TableStorageService(
            storage_account_url=settings.table_storage_account_url,
            table_name=settings.invoices_table_name, 
            standalone=True
        ) as table_client:
            
            invoice_storage_service: InvoiceStorageService
            async with InvoiceStorageService(
                standalone=True
            ) as invoice_storage_service:

                # Pass datetime object directly, not a string
                days_ago = datetime.now(timezone.utc) - timedelta(days=5)
                date_filter = [("created_date", days_ago)]
                
                logger.info(f"Filtering for invoices created after: {days_ago}")
                entities_found = {
                    "in_created": 0,
                    "in_extracted": 0,
                    "in_manual_review": 0,
                    "in_validated": 0,
                }
                invalid_blobs = []

                try:
                    entities = await table_client.query_entities(
                        filters_query=date_filter,
                        join_operator=JoinOperator.AND,
                        compare_operator=CompareOperator.GREATER_THAN
                    )
                    for entity in entities:
                        logger.info(f"Entity found: {entity['invoice_id']}, {entity['invoice_number']}, State: {entity.get('state', 'N/A')}, Created: {entity.get('created_date', 'N/A')}")
                        state = entity.get("state", None)
                        if state == InvoiceState.CREATED.value:
                            entities_found["in_created"] += 1
                        elif state == InvoiceState.EXTRACTED.value:
                            entities_found["in_extracted"] += 1
                        elif state == InvoiceState.MANUAL_REVIEW.value:
                            entities_found["in_manual_review"] += 1
                        elif state == InvoiceState.VALIDATED.value:
                            entities_found["in_validated"] += 1

                        raw_blob_name = entity.get("raw_blob_name", None)
                        logger.info(f" - Raw Blob Name: {raw_blob_name}")
                        if raw_blob_name is None or raw_blob_name.strip() == "":
                            invalid_blobs.append({
                                "invoice_id": entity['invoice_id'],
                                "invoice_number": entity['invoice_number'],
                                "created_date": entity['created_date']
                            })
                        else:
                            blob = await invoice_storage_service.file_exists(
                                container_name=settings.blob_container_name,
                                blob_name=raw_blob_name)

                            if not blob:
                                invalid_blobs.append({
                                    "invoice_id": entity['invoice_id'],
                                    "invoice_number": entity['invoice_number'],
                                    "created_date": entity['created_date']
                                })

                    self.invoices = {
                        "total_invoices_last_5_days": len(entities),
                        **entities_found,
                        "invoices_with_invalid_blobs": invalid_blobs
                    }
                except Exception as e:
                    logger.error(f"Error querying table storage: {e}")
                    traceback.print_exc()
                
    def get_stats(self) -> dict:
        return {
            "subscriptions": self.subscriptions,
            "invoices": self.invoices
        }

    async def __aenter__(self) -> "TableStorageService":
       """Enter the runtime context related to this object."""
       return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
       """Exit the runtime context related to this object."""
       pass

async def run():
    monitor: MonitorStats
    async with MonitorStats() as monitor:
        logger.info("Starting to gather monitoring stats...")
        tasks = []
        tasks.append(monitor.log_messaging_stats())
        tasks.append(monitor.log_storage_stats())
        tasks.append(monitor.log_table_stats())
        await asyncio.gather(*tasks)
        stats = monitor.get_stats()
        print(json.dumps(stats, indent=4))


if __name__ == "__main__":
    asyncio.run(run())

