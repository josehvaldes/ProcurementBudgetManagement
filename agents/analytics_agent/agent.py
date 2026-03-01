"""
Analytics Agent - Analyzes spending patterns and generates insights.
"""

import asyncio
from datetime import datetime
import json
from typing import Dict, Any, Optional

from langsmith import traceable
from shared.config.settings import settings
from agents.base_agent import BaseAgent
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.utils.constants import CompoundKeyStructure, InvoiceSubjects, SubscriptionNames
from shared.utils.exceptions import BudgetNotFoundException, EntityNotFoundException, InvoiceNotFoundException, StorageException, VendorNotFoundException


class AnalyticsAgent(BaseAgent):
    """
    Analytics Agent analyzes spending and generates insights.
    
    Responsibilities:
    - Compare spending vs. last month/year
    - Identify spending trends
    - Flag anomalies (sudden spikes)
    - Generate cost-saving insights
    - Forecast budget burn rate
    
    Note: This agent runs in parallel and doesn't block the main workflow.
    It subscribes to ALL invoice events for comprehensive analysis.
    """
    
    def __init__(self, shutdown_event: Optional[asyncio.Event] = None):
        super().__init__(
            agent_name="AnalyticsAgent",
            subscription_name=SubscriptionNames.ANALYTICS_AGENT,
            shutdown_event=shutdown_event or asyncio.Event()
        )

        self.invoice_analytics_table:Optional[TableStorageService] = None
        self.payment_table:Optional[TableStorageService] = None

        try:

            self.invoice_analytics_table = TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.invoice_analytics_table_name
            )

            self.payment_table = TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.payment_items_table_name
            )

            self.logger.info("Successfully initialized ApprovalAgent",
                    extra={
                        "agent": self.agent_name,
                        "vendor_table": settings.vendors_table_name,
                        "budget_table": settings.budgets_table_name,
                        "invoice_analytics_table": settings.invoice_analytics_table_name,
                        "payment_table": settings.payment_items_table_name
                    })
                

        except Exception as e:
            self.logger.error(
                "Failed to initialize ApprovalAgent",
                extra={
                    "agent": self.agent_name,
                    "error_type": type(e).__name__,
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise
    
    async def release_resources(self) -> None:
        """Release any resources held by the agent."""
        cleanup_errors = []

        if self.invoice_analytics_table:
            try:
                await self.invoice_analytics_table.close()
                self.logger.info("Closed invoice analytics table connection")
            except Exception as e:
                error_msg = f"Error closing invoice analytics table: {e}"
                cleanup_errors.append(error_msg)
                self.logger.error(error_msg, exc_info=True)

        if self.payment_table:
            try:
                await self.payment_table.close()
                self.logger.info("Closed payment table connection")
            except Exception as e:
                error_msg = f"Error closing payment table: {e}"
                cleanup_errors.append(error_msg)
                self.logger.error(error_msg, exc_info=True)
        
        if cleanup_errors:
            self.logger.warning(
                f"Resource cleanup completed with {len(cleanup_errors)} errors",
                extra={"cleanup_errors": cleanup_errors}
            )
        else:
            self.logger.info("All resources released successfully")

    @traceable(
        name="analytics_agent.process_invoice",
        tags=["analytics", "agent", "document_extraction"],
        metadata={"version": "1.0", "agent": "AnalyticsAgent"}
    )
    async def process_invoice(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze invoice for spending patterns and insights.
        
        Args:
            invoice_id: Invoice ID
            message_data: Message payload
            
        Returns:
            None (analytics agent doesn't trigger next state)
        """
        # Extract and validate message data
        invoice_id = message_data.get("invoice_id")
        department_id = message_data.get("department_id")
        
        correlation_id = message_data.get("correlation_id", invoice_id)
        subject = message_data.get("subject", None)
        

        if not invoice_id or not department_id or not subject:
            raise ValueError("invoice_id, department_id, and subject are required in message_data")

        self.logger.info(
            f"Starting invoice analytics",
            extra={
                "invoice_id": invoice_id,
                "department_id": department_id,
                "correlation_id": correlation_id,
                "subject": subject,
                "agent": self.agent_name
            }
        )
        try:
            # Get invoice from storage
            invoice_data = await self.get_invoice(department_id, invoice_id)
            now = datetime.now()
            issued_date: datetime = invoice_data.get("issued_date", now)
            issue_year: int = issued_date.year if isinstance(issued_date, datetime) else now.year
            partition_key = "FY" + str(issue_year)

            if not invoice_data:
                raise InvoiceNotFoundException(
                    f"Invoice not found: {invoice_id} in department: {department_id}"
                )

            try:
                self.logger.info(
                    f"Retrieved invoice data for analytics",
                    extra={
                        "invoice_id": invoice_id,
                        "department_id": department_id,
                        "correlation_id": correlation_id,
                        "agent": self.agent_name
                    }
                )
                
                analytics_data = await self.invoice_analytics_table.get_entity(
                    partition_key=partition_key,
                    row_key=invoice_id
                )
            except EntityNotFoundException as e:
                self.logger.warning(f"Analytics data not found for invoice {invoice_id}, will create new entry")
                analytics_data = None

            analytics_data = analytics_data or {
                "fiscal_year": partition_key,
                "invoice_id": invoice_id,
                "department_id": department_id,
            }

            analytics_data["invoice_state"] = invoice_data.get("state", "unknown")
            analytics_data["invoice_updated_at"] = invoice_data.get("updated_date", None)
            analytics_data["invoice_errors"] = json.dumps(invoice_data.get("errors", []))
            analytics_data["invoice_warnings"] = json.dumps(invoice_data.get("warnings", []))

            state = invoice_data.get("state")
            self.logger.info(f"Invoice {invoice_id} in state {state} - analytics recorded")

            if subject == InvoiceSubjects.CREATED:
                await self._handle_created_event( invoice_data, analytics_data)
            elif subject == InvoiceSubjects.EXTRACTED:
                await self._handle_extracted_event( invoice_data, analytics_data)
            elif subject == InvoiceSubjects.APPROVED:
                    await self._handle_approved_event( invoice_data, analytics_data)
            elif subject == InvoiceSubjects.PAID:
                await self._handle_paid_event( invoice_data, analytics_data)
            elif subject == InvoiceSubjects.MANUAL_REVIEW:
                await self._handle_manual_review_event( invoice_data, analytics_data)
            elif subject == InvoiceSubjects.FAILED:
                await self._handle_failed_event( invoice_data, analytics_data)
            elif subject == InvoiceSubjects.PAYMENT_SCHEDULED:
                await self._handle_payment_scheduled_event( invoice_data, analytics_data)
            elif subject == InvoiceSubjects.BUDGET_CHECKED:
                try:
                    budget_data = await self.retrieve_budget_metadata(invoice_data, correlation_id)
                    await self._handle_budget_checked_event( invoice_data, budget_data, analytics_data)
                except BudgetNotFoundException as e:
                    self.logger.warning(f"Failed to retrieve budget metadata for invoice {invoice_id}", exc_info=True)
                    budget_data = None
            elif subject == InvoiceSubjects.VALIDATED:
                try:
                    vendor_id = invoice_data.get("vendor_id", None)
                    if not vendor_id:
                        vendor_data = await self.retrieve_vendor_metadata(vendor_id, correlation_id)
                        await self._handle_validated_event( invoice_data, vendor_data, analytics_data)
                except VendorNotFoundException as e:
                    self.logger.warning(f"Failed to retrieve vendor metadata for invoice {invoice_id}", exc_info=True)
                    vendor_data = None
            
            self.logger.info(f"Completed analytics processing for invoice {invoice_id} in state {state}")
            # Analytics agent doesn't publish next state
            return None
        except Exception as e:
            self.logger.error(f"Error processing invoice {invoice_id}: {e}", exc_info=True, stack_info=True)
            raise

    async def _handle_created_event(self,
                              invoice_data: dict, 
                              analytics_data: dict) -> None:
        """Handle analytics for CREATED state."""
        analytics_data["invoice_amount"] = invoice_data.get("amount", 0.0)
        analytics_data["invoice_document_type"] = invoice_data.get("document_type", "unknown")
        analytics_data["invoice_priority"] = invoice_data.get("priority", "normal")
        analytics_data["invoice_source"] = invoice_data.get("source", "unknown")
        analytics_data["invoice_category"] = invoice_data.get("category", "uncategorized")
        analytics_data["invoice_created_at"] = invoice_data.get("created_date", None)
        analytics_data["invoice_budget_year"] = invoice_data.get("budget_year", None)

        await self.invoice_analytics_table.upsert_entity(analytics_data,
                                                         partition_key=analytics_data["fiscal_year"],
                                                         row_key=analytics_data["invoice_id"])

    async def _handle_extracted_event(self, invoice_data: dict, analytics_data: dict) -> None:
        """Handle analytics for EXTRACTED state."""
        analytics_data["invoice_extracted_at"] = invoice_data.get("extracted_date", None)
        await self.invoice_analytics_table.upsert_entity(analytics_data,
                                                         partition_key=analytics_data["fiscal_year"],
                                                         row_key=analytics_data["invoice_id"])

    async def _handle_validated_event(self, invoice_data: dict, vendor_data: dict, analytics_data: dict) -> None:
        """Handle analytics for VALIDATED state."""

        analytics_data["vendor_name"] = invoice_data.get("vendor_name", "unknown")
        analytics_data["invoice_validated_at"] = invoice_data.get("validated_date", None)        
        analytics_data["invoice_validated_state"] = invoice_data.get("validation_passed", False)

        if vendor_data:
            analytics_data["vendor_id"] = vendor_data.get("vendor_id", "unknown")            
            analytics_data["vendor_active"] = vendor_data.get("active", False)
            analytics_data["vendor_categories"] = json.dumps(vendor_data.get("categories", []))
            analytics_data["vendor_industry"] = vendor_data.get("industry", "unknown")

        await self.invoice_analytics_table.upsert_entity(analytics_data,
                                                         partition_key=analytics_data["fiscal_year"],
                                                         row_key=analytics_data["invoice_id"])


    async def _handle_budget_checked_event(self, invoice_data: dict, budget_data: dict, analytics_data: dict) -> None:
        """Handle analytics for BUDGET_CHECKED state."""
        analytics_data["budget_analysis"] = invoice_data.get("budget_analysis", None)
        analytics_data["invoice_budget_checked_at"] = invoice_data.get("updated_date", None)

        analytics_data["budget_id"] = budget_data.get("budget_id", None) if budget_data else None
        analytics_data["budget_name"] = budget_data.get("name", None)  if budget_data else None
        analytics_data["budget_status"] = budget_data.get("status", None) if budget_data else None
        analytics_data["budget_rotation"] = budget_data.get("rotation", None) if budget_data else None
        analytics_data["budget_allocated_amount"] = budget_data.get("allocated_amount", None) if budget_data else None
        analytics_data["budget_consumed_at_time"] = budget_data.get("consumed_amount", None) if budget_data else None
        analytics_data["budget_category"] = budget_data.get("category", None) if budget_data else None

        await self.invoice_analytics_table.upsert_entity(analytics_data,
                                                         partition_key=analytics_data["fiscal_year"],
                                                         row_key=analytics_data["invoice_id"])

    async def _handle_approved_event(self, invoice_data: dict, analytics_data: dict) -> None:
        """Handle analytics for APPROVED state."""
        analytics_data["due_date"] = invoice_data.get("due_date", None)
        analytics_data["invoice_approved_at"] = invoice_data.get("approved_date", None)
        analytics_data["reviewed_by"] = invoice_data.get("reviewed_by", None)
        analytics_data["reviewed_date"] = invoice_data.get("reviewed_date", None)
        analytics_data["review_status"] = invoice_data.get("review_status", None)

        await self.invoice_analytics_table.upsert_entity(analytics_data,
                                                         partition_key=analytics_data["fiscal_year"],
                                                         row_key=analytics_data["invoice_id"])

    async def _handle_payment_scheduled_event(self, invoice_data: dict, analytics_data: dict) -> None:
        """Handle analytics for PAYMENT_SCHEDULED state."""
        analytics_data["invoice_ai_suggested_approver"] = invoice_data.get("ai_suggested_approver", None)
        await self.invoice_analytics_table.upsert_entity(analytics_data,
                                                         partition_key=analytics_data["fiscal_year"],
                                                         row_key=analytics_data["invoice_id"])

    async def _handle_paid_event(self, invoice_data: dict, analytics_data: dict) -> None:
        """Handle analytics for PAID state."""
        analytics_data["invoice_paid"] = invoice_data.get("updated_date", None)
        await self.invoice_analytics_table.upsert_entity(analytics_data,
                                                         partition_key=analytics_data["fiscal_year"],
                                                         row_key=analytics_data["invoice_id"])

    async def _handle_failed_event(self, invoice_data: dict, analytics_data: dict) -> None:
        """Handle analytics for FAILED state."""
        analytics_data["invoice_budget_year"] = invoice_data.get("budget_year", None)

        await self.invoice_analytics_table.upsert_entity(analytics_data,
                                                         partition_key=analytics_data["fiscal_year"],
                                                         row_key=analytics_data["invoice_id"])

    async def _handle_manual_review_event(self, invoice_data: dict, analytics_data: dict) -> None:
        """Handle analytics for MANUAL_REVIEW state."""
        pass

    def get_next_subject(self) -> str:
        """Analytics agent doesn't publish next state."""
        return None


if __name__ == "__main__":
    agent = AnalyticsAgent()
    agent.setup_signal_handlers()
    asyncio.run(agent.run())
