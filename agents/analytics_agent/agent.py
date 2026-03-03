"""
Analytics Agent - Analyzes spending patterns and generates insights.
"""

import asyncio
from datetime import datetime
import json
from typing import Any, Callable, Coroutine, Dict, Optional

from langsmith import traceable
from shared.config.settings import settings
from agents.base_agent import BaseAgent
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.utils.constants import InvoiceSubjects, SubscriptionNames
from shared.utils.exceptions import (
    BudgetNotFoundException,
    EntityNotFoundException,
    InvoiceNotFoundException,
    VendorNotFoundException,
)


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
            shutdown_event=shutdown_event or asyncio.Event(),
        )

        self.invoice_analytics_table: Optional[TableStorageService] = None
        self.payment_table: Optional[TableStorageService] = None

        try:
            self.invoice_analytics_table = TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.invoice_analytics_table_name,
            )

            self.payment_table = TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.payment_items_table_name,
            )

            self.logger.info(
                "Successfully initialized AnalyticsAgent",
                extra={
                    "agent": self.agent_name,
                    "invoice_analytics_table": settings.invoice_analytics_table_name,
                    "payment_table": settings.payment_items_table_name,
                },
            )

        except Exception as e:
            self.logger.error(
                "Failed to initialize AnalyticsAgent",
                extra={
                    "agent": self.agent_name,
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
                exc_info=True,
            )
            raise

    # ------------------------------------------------------------------ #
    #  Resource cleanup
    # ------------------------------------------------------------------ #

    async def release_resources(self) -> None:
        """Release any resources held by the agent."""
        resources: list[tuple[str, Optional[TableStorageService]]] = [
            ("invoice_analytics_table", self.invoice_analytics_table),
            ("payment_table", self.payment_table),
        ]
        cleanup_errors: list[str] = []

        for name, resource in resources:
            if resource is None:
                continue
            try:
                await resource.close()
                self.logger.info(
                    "Closed table connection",
                    extra={"agent": self.agent_name, "resource": name},
                )
            except Exception as e:
                cleanup_errors.append(f"{name}: {e}")
                self.logger.error(
                    "Error closing table connection",
                    extra={
                        "agent": self.agent_name,
                        "resource": name,
                        "error_type": type(e).__name__,
                        "error_details": str(e),
                    },
                    exc_info=True,
                )

        if cleanup_errors:
            self.logger.warning(
                "Resource cleanup completed with errors",
                extra={
                    "agent": self.agent_name,
                    "error_count": len(cleanup_errors),
                    "cleanup_errors": cleanup_errors,
                },
            )
        else:
            self.logger.info(
                "All resources released successfully",
                extra={"agent": self.agent_name},
            )

    # ------------------------------------------------------------------ #
    #  Main processing entry-point
    # ------------------------------------------------------------------ #

    @traceable(
        name="analytics_agent.process_invoice",
        tags=["analytics", "agent", "document_extraction"],
        metadata={"version": "1.0", "agent": "AnalyticsAgent"},
    )
    async def process_invoice(self, message_data: Dict[str, Any]) -> None:
        """
        Analyze invoice for spending patterns and insights.

        Args:
            message_data: Message payload containing invoice_id,
                          department_id, subject, and correlation_id.

        Returns:
            None – the analytics agent never triggers a next state.
        """
        invoice_id = message_data.get("invoice_id")
        department_id = message_data.get("department_id")
        correlation_id = message_data.get("correlation_id", invoice_id)
        subject = message_data.get("subject")

        if not invoice_id or not department_id or not subject:
            raise ValueError(
                "invoice_id, department_id, and subject are required in message_data"
            )

        log_ctx: Dict[str, Any] = {
            "agent": self.agent_name,
            "invoice_id": invoice_id,
            "department_id": department_id,
            "correlation_id": correlation_id,
            "subject": subject,
        }

        self.logger.info("Starting invoice analytics", extra=log_ctx)

        try:
            invoice_data = await self.get_invoice(
                department_id, invoice_id
            )
            partition_key = self._resolve_partition_key(invoice_data)

            analytics_data = await self._fetch_or_init_analytics(
                partition_key, invoice_id, department_id, log_ctx
            )

            # Stamp common fields on every event
            state = invoice_data.get("state", "unknown")
            analytics_data["invoice_state"] = state
            analytics_data["invoice_updated_at"] = invoice_data.get("updated_date")
            analytics_data["invoice_errors"] = json.dumps(
                invoice_data.get("errors", [])
            )
            analytics_data["invoice_warnings"] = json.dumps(
                invoice_data.get("warnings", [])
            )

            self.logger.info(
                "Invoice state recorded for analytics",
                extra={**log_ctx, "state": state},
            )

            await self._dispatch_event(
                subject, invoice_data, analytics_data, correlation_id, log_ctx
            )

            self.logger.info(
                "Completed analytics processing",
                extra={**log_ctx, "state": state},
            )
            # Analytics agent doesn't publish next state – it just updates the analytics record
            return None

        except (ValueError, InvoiceNotFoundException):
            raise

        except Exception as exc:
            self.logger.error(
                "Unhandled error during analytics processing",
                extra={
                    **log_ctx,
                    "error_type": type(exc).__name__,
                    "error_details": str(exc),
                },
                exc_info=True,
            )
            raise

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_partition_key(invoice_data: Dict[str, Any]) -> str:
        """Derive the fiscal-year partition key from the invoice."""
        now = datetime.now()
        issued_date = invoice_data.get("issued_date", now)
        issue_year = (
            issued_date.year if isinstance(issued_date, datetime) else now.year
        )
        return f"FY{issue_year}"

    async def _fetch_or_init_analytics(
        self,
        partition_key: str,
        invoice_id: str,
        department_id: str,
        log_ctx: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Load existing analytics row or bootstrap a new one."""
        try:
            analytics_data = await self.invoice_analytics_table.get_entity(
                partition_key=partition_key,
                row_key=invoice_id,
            )
            self.logger.debug(
                "Loaded existing analytics record",
                extra={**log_ctx, "partition_key": partition_key},
            )
            return analytics_data
        except EntityNotFoundException:
            self.logger.info(
                "Analytics record not found – creating new entry",
                extra={**log_ctx, "partition_key": partition_key},
            )
            return {
                "fiscal_year": partition_key,
                "invoice_id": invoice_id,
                "department_id": department_id,
            }

    async def _dispatch_event(
        self,
        subject: str,
        invoice_data: Dict[str, Any],
        analytics_data: Dict[str, Any],
        correlation_id: str,
        log_ctx: Dict[str, Any],
    ) -> None:
        """Route the event to the appropriate handler."""

        # Simple handlers (invoice_data + analytics_data only)
        simple_handlers: Dict[
            str, Callable[[dict, dict], Coroutine[Any, Any, None]]
        ] = {
            InvoiceSubjects.CREATED: self._handle_created_event,
            InvoiceSubjects.EXTRACTED: self._handle_extracted_event,
            InvoiceSubjects.APPROVED: self._handle_approved_event,
            InvoiceSubjects.PAID: self._handle_paid_event,
            InvoiceSubjects.MANUAL_REVIEW: self._handle_manual_review_event,
            InvoiceSubjects.FAILED: self._handle_failed_event,
            InvoiceSubjects.PAYMENT_SCHEDULED: self._handle_payment_scheduled_event,
        }

        handler = simple_handlers.get(subject)
        if handler is not None:
            await handler(invoice_data, analytics_data)
            return

        # Handlers that need additional metadata lookups
        if subject == InvoiceSubjects.BUDGET_CHECKED:
            await self._dispatch_budget_checked(
                invoice_data, analytics_data, correlation_id, log_ctx
            )
        elif subject == InvoiceSubjects.VALIDATED:
            await self._dispatch_validated(
                invoice_data, analytics_data, correlation_id, log_ctx
            )
        else:
            self.logger.warning(
                "Received unrecognised event subject – skipping",
                extra={**log_ctx, "subject": subject},
            )

    async def _dispatch_budget_checked(
        self,
        invoice_data: Dict[str, Any],
        analytics_data: Dict[str, Any],
        correlation_id: str,
        log_ctx: Dict[str, Any],
    ) -> None:
        try:
            budget_data = await self.retrieve_budget_metadata(
                invoice_data, correlation_id
            )
            await self._handle_budget_checked_event(
                invoice_data, budget_data, analytics_data
            )
        except BudgetNotFoundException:
            self.logger.warning(
                "Budget metadata not found – recording analytics without budget data",
                extra=log_ctx,
                exc_info=True,
            )
            await self._handle_budget_checked_event(
                invoice_data, None, analytics_data
            )

    async def _dispatch_validated(
        self,
        invoice_data: Dict[str, Any],
        analytics_data: Dict[str, Any],
        correlation_id: str,
        log_ctx: Dict[str, Any],
    ) -> None:
        vendor_id = invoice_data.get("vendor_id")
        if not vendor_id:
            self.logger.warning(
                "No vendor_id on invoice – recording analytics without vendor data",
                extra=log_ctx,
            )
            await self._handle_validated_event(invoice_data, None, analytics_data)
            return

        try:
            vendor_data = await self.retrieve_vendor_metadata(
                vendor_id, correlation_id
            )
            await self._handle_validated_event(
                invoice_data, vendor_data, analytics_data
            )
        except VendorNotFoundException:
            self.logger.warning(
                "Vendor metadata not found – recording analytics without vendor data",
                extra={**log_ctx, "vendor_id": vendor_id},
                exc_info=True,
            )
            await self._handle_validated_event(invoice_data, None, analytics_data)

    # ------------------------------------------------------------------ #
    #  Persistence helper
    # ------------------------------------------------------------------ #

    async def _persist_analytics(self, analytics_data: Dict[str, Any]) -> None:
        """Upsert the analytics row into Table Storage."""
        await self.invoice_analytics_table.upsert_entity(
            analytics_data,
            partition_key=analytics_data["fiscal_year"],
            row_key=analytics_data["invoice_id"],
        )

    # ------------------------------------------------------------------ #
    #  Per-event handlers
    # ------------------------------------------------------------------ #

    async def _handle_created_event(
        self, invoice_data: dict, analytics_data: dict
    ) -> None:
        """Handle analytics for CREATED state."""
        analytics_data["invoice_amount"] = invoice_data.get("amount", 0.0)
        analytics_data["invoice_document_type"] = invoice_data.get(
            "document_type", "unknown"
        )
        analytics_data["invoice_priority"] = invoice_data.get("priority", "normal")
        analytics_data["invoice_source"] = invoice_data.get("source", "unknown")
        analytics_data["invoice_category"] = invoice_data.get(
            "category", "uncategorized"
        )
        analytics_data["invoice_created_at"] = invoice_data.get("created_date")
        analytics_data["invoice_budget_year"] = invoice_data.get("budget_year")
        await self._persist_analytics(analytics_data)

    async def _handle_extracted_event(
        self, invoice_data: dict, analytics_data: dict
    ) -> None:
        """Handle analytics for EXTRACTED state."""
        analytics_data["invoice_extracted_at"] = invoice_data.get("extracted_date")
        await self._persist_analytics(analytics_data)

    async def _handle_validated_event(
        self,
        invoice_data: dict,
        vendor_data: Optional[dict],
        analytics_data: dict,
    ) -> None:
        """Handle analytics for VALIDATED state."""
        analytics_data["vendor_name"] = invoice_data.get("vendor_name", "unknown")
        analytics_data["invoice_validated_at"] = invoice_data.get("validated_date")
        analytics_data["invoice_validated_state"] = invoice_data.get(
            "validation_passed", False
        )

        if vendor_data:
            analytics_data["vendor_id"] = vendor_data.get("vendor_id", "unknown")
            analytics_data["vendor_active"] = vendor_data.get("active", False)
            analytics_data["vendor_categories"] = json.dumps(
                vendor_data.get("categories", [])
            )
            analytics_data["vendor_industry"] = vendor_data.get("industry", "unknown")

        await self._persist_analytics(analytics_data)

    async def _handle_budget_checked_event(
        self,
        invoice_data: dict,
        budget_data: Optional[dict],
        analytics_data: dict,
    ) -> None:
        """Handle analytics for BUDGET_CHECKED state."""
        analytics_data["budget_analysis"] = invoice_data.get("budget_analysis")
        analytics_data["invoice_budget_checked_at"] = invoice_data.get("updated_date")

        if budget_data:
            analytics_data["budget_id"] = budget_data.get("budget_id")
            analytics_data["budget_name"] = budget_data.get("name")
            analytics_data["budget_status"] = budget_data.get("status")
            analytics_data["budget_rotation"] = budget_data.get("rotation")
            analytics_data["budget_allocated_amount"] = budget_data.get(
                "allocated_amount"
            )
            analytics_data["budget_consumed_at_time"] = budget_data.get(
                "consumed_amount"
            )
            analytics_data["budget_category"] = budget_data.get("category")

        await self._persist_analytics(analytics_data)

    async def _handle_approved_event(
        self, invoice_data: dict, analytics_data: dict
    ) -> None:
        """Handle analytics for APPROVED state."""
        analytics_data["due_date"] = invoice_data.get("due_date")
        analytics_data["invoice_approved_at"] = invoice_data.get("approved_date")
        analytics_data["reviewed_by"] = invoice_data.get("reviewed_by")
        analytics_data["reviewed_date"] = invoice_data.get("reviewed_date")
        analytics_data["review_status"] = invoice_data.get("review_status")
        await self._persist_analytics(analytics_data)

    async def _handle_payment_scheduled_event(
        self, invoice_data: dict, analytics_data: dict
    ) -> None:
        """Handle analytics for PAYMENT_SCHEDULED state."""
        analytics_data["invoice_ai_suggested_approver"] = invoice_data.get(
            "ai_suggested_approver"
        )
        await self._persist_analytics(analytics_data)

    async def _handle_paid_event(
        self, invoice_data: dict, analytics_data: dict
    ) -> None:
        """Handle analytics for PAID state."""
        analytics_data["invoice_paid"] = invoice_data.get("updated_date")
        await self._persist_analytics(analytics_data)

    async def _handle_failed_event(
        self, invoice_data: dict, analytics_data: dict
    ) -> None:
        """Handle analytics for FAILED state."""
        analytics_data["invoice_budget_year"] = invoice_data.get("budget_year")
        await self._persist_analytics(analytics_data)

    async def _handle_manual_review_event(
        self, invoice_data: dict, analytics_data: dict
    ) -> None:
        """Handle analytics for MANUAL_REVIEW state."""
        analytics_data["invoice_manual_review_at"] = invoice_data.get("updated_date")
        await self._persist_analytics(analytics_data)

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #

    def get_next_subject(self) -> str:
        """Analytics agent doesn't publish next state."""
        return None


if __name__ == "__main__":
    agent = AnalyticsAgent()
    agent.setup_signal_handlers()
    asyncio.run(agent.run())
