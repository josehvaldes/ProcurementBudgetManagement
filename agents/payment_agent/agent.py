"""
Payment Agent - Schedules and manages invoice payments.
"""
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from langsmith import traceable
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from agents.payment_agent.tools.alert_notification_tool import AlertNotificationTool
from invoice_lifecycle_api.application.interfaces.service_interfaces import CompareOperator
from shared.config.settings import settings
from agents.base_agent import BaseAgent
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.models.invoice import InvoiceState
from shared.models.payment_batch_item import PaymentBatchItem, PaymentState
from shared.utils.constants import InvoiceSubjects, SubscriptionNames
from shared.utils.exceptions import InvoiceProcessingException, PaymentProcessingException, StorageException

scheduler: AsyncIOScheduler = AsyncIOScheduler()

async def payment_task(agent: "PaymentAgent") -> None:
    """Background job to process payments."""
    now = datetime.now(timezone.utc)
    agent.logger.info(f"Starting payment job at: {now.isoformat()}")

    try:
        # Get all invoices in APPROVED state
        now = datetime.now(timezone.utc)
        filters = [("state", PaymentState.SCHEDULED.value, CompareOperator.EQUAL.value),
                    ("payment_date", now, CompareOperator.LESS_THAN_OR_EQUAL.value)]
        scheduled_invoices = await agent.payment_batch_table_client.query_entities_with_filters(
            filters=filters
        )

        agent.logger.info(f"Found {len(scheduled_invoices)} scheduled payments to process")

        for item in scheduled_invoices:
            agent.logger.info(
                f"Processing payment for invoice {item['invoice_id']}",
                extra={"invoice_id": item["invoice_id"]}
            )
            await agent._process_payment(item)
            agent.logger.info(
                f"Payment processed for invoice {item['invoice_id']}",
                extra={"invoice_id": item["invoice_id"]}
            )
    except Exception as e:
        agent.logger.error("Error in payment job", extra={"error": str(e)})
        
class PaymentAgent(BaseAgent):
    """
    Payment Agent manages payment scheduling and processing.
    
    Responsibilities:
    - Schedule payment based on terms (NET-30, NET-60, etc.)
    - Generate payment batches
    - Send remittance information to vendors
    - Update invoice state to PAYMENT_SCHEDULED
    - Publish invoice.payment_scheduled message
    """
    
    def __init__(self, shutdown_event: asyncio.Event = asyncio.Event(), start_scheduler: bool = True):
        super().__init__( 
            agent_name="PaymentAgent",
            subscription_name=SubscriptionNames.PAYMENT_AGENT,
            shutdown_event=shutdown_event
        )
        self.vendor_table_client:Optional[TableStorageService] = None
        self.payment_batch_table_client:Optional[TableStorageService] = None
        self.alert_notification_tool: Optional[AlertNotificationTool] = None
        

        try:
            self.vendor_table_client = TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.vendors_table_name
            )
            self.payment_batch_table_client = TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.payment_items_table_name
            )
            self.alert_notification_tool = AlertNotificationTool()
        except Exception as e:
            self.logger.error("Error initializing Vendor Table Storage client", extra={"error": str(e)})
            raise
        
        if start_scheduler:
            scheduler.add_job(payment_task, 'interval', 
                            seconds=settings.payment_interval_seconds,
                            kwargs={"agent": self})
            scheduler.start()
    
    async def release_resources(self) -> None:
        """Release any resources held by the agent."""
        cleanup_errors = []
        if self.vendor_table_client:
            try:
                await self.vendor_table_client.close()
                self.logger.info("Vendor table client closed successfully", extra={"agent": self.agent_name})
            except Exception as e:
                error_msg = f"Failed to close vendor table client: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                cleanup_errors.append(error_msg)

        if self.payment_batch_table_client:
            try:
                await self.payment_batch_table_client.close()
                self.logger.info("Payment batch table client closed successfully", extra={"agent": self.agent_name})
            except Exception as e:
                error_msg = f"Failed to close payment batch table client: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                cleanup_errors.append(error_msg)
        try:
            scheduler.shutdown(wait=True)
            self.logger.info("Scheduler shutdown initiated successfully", extra={"agent": self.agent_name})
        except Exception as e:
            error_msg = f"Failed to shutdown scheduler: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            cleanup_errors.append(error_msg)

        if cleanup_errors:
            self.logger.warning(
                f"Resource cleanup completed with {len(cleanup_errors)} errors",
                extra={"cleanup_errors": cleanup_errors}
            )
        else:
            self.logger.info("All resources released successfully")




    async def _get_invoices_by_state(self, state: str) -> list:
        """Helper method to get invoices by state."""
        
        try:
            # cross-partition query to get all invoices in the specified state
            filters = [("state", InvoiceState.PENDING_APPROVAL.value, CompareOperator.EQUAL.value)]

            invoices = self.invoice_table.query_entities_with_filters(
                filters=filters
            )

            return invoices
        except Exception as e:
            self.logger.error("Error querying invoices by state", extra={"state": state, "error": str(e)})
            return []

    async def _process_payment(self, payment_item: Dict[str, Any]) -> None:
        """Helper method to process payment for an invoice."""
        try:
            payment_item["state"] = PaymentState.PROCESSED.value
            await self.payment_batch_table_client.upsert_entity(payment_item,
                                                                partition_key=payment_item["department_id"],
                                                                row_key=payment_item["invoice_id"])
            await self.alert_notification_tool.send_payment_notification(
                payment_item=payment_item
            )
            self.logger.info(f"Payment processed for invoice {payment_item['invoice_id']}")
        except Exception as e:
            self.logger.error(f"Error processing payment for invoice {payment_item['invoice_id']}", extra={"error": str(e)})

    @traceable(name="payment_agent.process_invoice", tags=["payment", "agent"], metadata={"version": "1.0"})
    async def process_invoice(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Schedule payment for approved invoice.
        
        Args:
            invoice_id: Invoice ID
            message_data: Message payload
            
        Returns:
            Result data for next state
        """
        invoice_id = message_data["invoice_id"]
        department_id = message_data["department_id"]
        correlation_id = message_data.get("correlation_id", invoice_id)
        
        self.logger.info(
            "Starting payment scheduling for invoice",
            extra={
                "invoice_id": invoice_id,
                "department_id": department_id,
                "correlation_id": correlation_id,
                "agent": self.agent_name
            }
        )
        
        try:
            # Get invoice from storage
            invoice_data = await self.get_invoice(department_id, invoice_id)
            vendor_data = await self.retrieve_vendor_metadata(invoice_data["vendor_id"], correlation_id)
            
            await self._process_invoice_payment(invoice_data, vendor_data, correlation_id)
            
            self.logger.info(
                "Completed payment scheduling for invoice",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "agent": self.agent_name
                }
            )

            return {
                "invoice_id": invoice_id,
                "department_id": department_id,
                "event_type": "PaymentAgentComplete",
                "state": InvoiceState.PAYMENT_SCHEDULED.value,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "correlation_id": correlation_id
            }
        except Exception as e:
            self.logger.error(
                "Error in payment scheduling for invoice",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "agent": self.agent_name,
                    "error": str(e)
                }
            )
            raise

    async def _process_invoice_payment(self, invoice: dict, vendor: dict, correlation_id: str) -> None:
        """Helper method to process invoice payment scheduling."""

        try:
            payment_date = invoice.get("due_date")
            self.logger.info(
                f"Scheduling payment for invoice {invoice['invoice_id']}",
                extra={"invoice_id": invoice["invoice_id"], "payment_date": payment_date}
            )

            # Add any additional logic for payment scheduling here (e.g. add to batch, generate remittance advice, etc.)
            payment_batch = PaymentBatchItem(
                invoice_id=invoice["invoice_id"],
                department_id=invoice["department_id"],
                payment_date=payment_date,
                amount=invoice["amount"],
                currency=invoice["currency"],
                vendor_id=invoice["vendor_id"],
                vendor_name=vendor.get("name", ""),
                payment_method=vendor.get("payment_method", ""),
                status=PaymentState.SCHEDULED.value,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat()
            )

            self.payment_batch_table_client.upsert_entity(payment_batch.to_dict())

            # Update invoice state
            invoice["state"] = InvoiceState.PAYMENT_SCHEDULED.value        

            await self.complete_processing(
                invoice=invoice,
                new_state=InvoiceState.PAYMENT_SCHEDULED.value,
                event_type=SubscriptionNames.PAYMENT_AGENT.value,
                correlation_id=correlation_id
                )
        except Exception as e:
            self.logger.error(
                f"Error processing payment for invoice {invoice['invoice_id']}",
                extra={"invoice_id": invoice["invoice_id"], "error": str(e)}
            )
            raise PaymentProcessingException(f"Failed to process payment for invoice {invoice['invoice_id']}") from e

    def get_next_subject(self) -> str:
        """Return the next message subject."""
        return InvoiceSubjects.PAYMENT_SCHEDULED

if __name__ == "__main__":
    agent = PaymentAgent()
    agent.setup_signal_handlers()
    asyncio.run(agent.run())
