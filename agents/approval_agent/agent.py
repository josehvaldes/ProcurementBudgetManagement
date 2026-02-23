"""
Approval Agent - Manages invoice approval workflow.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from langsmith import traceable
from agents.approval_agent.tools.approval_analytics_agent import ApprovalAnalyticsAgent, ApprovalAnalyticsOutcome
from agents.approval_agent.tools.approval_notification_system import ApprovalNotificationSystem
from agents.approval_agent.tools.approval_status import ApprovalDecision, ApprovalStatus
from shared.config.settings import settings
from agents.base_agent import BaseAgent
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.models.budget import BudgetStatus
from shared.models.invoice import InvoiceState, ReviewStatus
from shared.utils.constants import CompoundKeyStructure, InvoiceSubjects, SubscriptionNames
from shared.utils.exceptions import BudgetNotFoundException, DocumentExtractionException, InvoiceApprovalException, InvoiceNotFoundException, StorageException, VendorNotFoundException

class ApprovalAgent(BaseAgent):
    """
    Approval Agent manages the invoice approval process.
    
    Responsibilities:
    - Auto-approve invoices within policy thresholds
    - Route to department manager for approval if needed
    - Escalate over-budget invoices
    - Update invoice state to APPROVED or MANUAL_REVIEW
    - Publish appropriate message
    """
    
    def __init__(self, shutdown_event: asyncio.Event = asyncio.Event()):
        super().__init__(
            agent_name="ApprovalAgent",
            subscription_name=SubscriptionNames.APPROVAL_AGENT,
            shutdown_event=shutdown_event
        )

        self.vendor_table_client:Optional[TableStorageService] = None
        self.budget_table_client:Optional[TableStorageService] = None
        self.alert_notification_system: Optional[ApprovalNotificationSystem] = None
        try:
            self.vendor_table_client = TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.vendors_table_name
            )
            self.budget_table_client = TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.budgets_table_name
            )
            self.alert_notification_system = ApprovalNotificationSystem()
            self.logger.info("Successfully initialized ApprovalAgent",
                             extra={
                                 "agent": self.agent_name,
                                 "vendor_table": settings.vendors_table_name,
                                 "budget_table": settings.budgets_table_name
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
        if self.vendor_table_client:
            try:
                await self.vendor_table_client.close()
                self.logger.info("Vendor table client closed successfully", extra={"agent": self.agent_name})
            except Exception as e:
                error_msg = f"Failed to close vendor table client: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                cleanup_errors.append(error_msg)

        if self.budget_table_client:
            try:
                await self.budget_table_client.close()
                self.logger.info("Budget table client closed successfully", extra={"agent": self.agent_name})
            except Exception as e:
                error_msg = f"Failed to close budget table client: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                cleanup_errors.append(error_msg)

        if cleanup_errors:
            self.logger.warning(
                f"Resource cleanup completed with {len(cleanup_errors)} errors",
                extra={"cleanup_errors": cleanup_errors}
            )
        else:
            self.logger.info("All resources released successfully")

    @traceable(name="approval_agent.process_invoice", tags=["approval", "agent"], metadata={"version": "1.0"})
    async def process_invoice(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process invoice approval decision.
        Args:
            message_data: Message payload
            
        Returns:
            Result data for next state
        """
        invoice_id = message_data["invoice_id"]
        department_id = message_data["department_id"]
        correlation_id = message_data.get("correlation_id", invoice_id)

        self.logger.info(
            f"Starting invoice extraction workflow",
            extra={
                "invoice_id": invoice_id,
                "department_id": department_id,
                "correlation_id": correlation_id,
                "agent": self.agent_name
            }
        )
        
        try:
            # Get invoice from storage

            invoice_data = await self._retrieve_invoice_metadata(department_id, invoice_id, correlation_id)

            if not invoice_data:
                raise InvoiceNotFoundException(
                        f"Invoice not found: {invoice_id} in department: {department_id}"
                    )
            
            vendor_id = invoice_data.get("vendor_id", None)

            vendor_data = await self._retrieve_vendor_metadata(vendor_id, correlation_id)

            budget_data = await self._retrieve_budget_metadata(invoice_data, correlation_id)
            
            deterministic_decision = await self._deterministic_approval_decision(invoice_data,
                                                                                 vendor_data,
                                                                                 budget_data,
                                                                                 correlation_id)
            tasks = []
            if deterministic_decision.status == ApprovalStatus.REJECTED:
                task = self._reject_invoice(invoice_data, InvoiceState.FAILED, deterministic_decision.reason)
                tasks.append(task)
            elif deterministic_decision.status == ApprovalStatus.MANUAL_APPROVAL_REQUIRED:
                task = self._handle_manual_review(invoice_data, vendor_data, budget_data, correlation_id, deterministic_decision.reason)
                tasks.append(task)
            elif deterministic_decision.status == ApprovalStatus.AUTO_APPROVED:
                task = self._handle_auto_approved(invoice_data, vendor_data, budget_data, correlation_id)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            return {
                "invoice_id": invoice_id,
                "department_id": department_id,
                "event_type": "ApprovalAgentCompleted",
                "approval_method": invoice_data["approval_method"],
                "correlation_id": correlation_id,
            }
        
        except InvoiceNotFoundException as e:
            self.logger.error(
                f"Invoice not found: {invoice_id}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "error_type": "InvoiceNotFound"
                },
                exc_info=True
            )
            raise
        except VendorNotFoundException as e:
            self.logger.error(
                f"Vendor not found for invoice: {invoice_id}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "vendor_id": invoice_data.get("vendor_id", None),
                    "error_type": "VendorNotFound"
                },
                exc_info=True
            )
            raise
        except BudgetNotFoundException as e:
            self.logger.error(
                f"Budget not found for invoice: {invoice_id}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "error_type": "BudgetNotFound"
                },
                exc_info=True
            )
            raise
        except StorageException as e:
            self.logger.error(
                f"Storage operation failed for invoice: {invoice_id}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "error_type": "StorageFailure",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise
        except Exception as e:
            self.logger.error(
                f"Unexpected error processing invoice: {invoice_id}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise InvoiceApprovalException(
                f"Failed to process invoice {invoice_id}: {str(e)}"
            ) from e

    def get_next_subject(self) -> str:
        """Return the next message subject."""
        return InvoiceSubjects.APPROVED

    async def _handle_manual_review(self, 
                                    invoice_data: Dict[str, Any], 
                                    vendor_data: Dict[str, Any],
                                    budget_data: Dict[str, Any],
                                    correlation_id: str, 
                                    reason: str) -> None:
        """Update invoice state to MANUAL_REVIEW with reason."""
        try:
            invoice_data["state"] = InvoiceState.PENDING_APPROVAL.value
            invoice_data["rejection_reason"] = reason
            
            invoice_id = invoice_data.get("invoice_id")
            vendor_id = invoice_data.get("vendor_id")

            decision: ApprovalDecision = await self._ai_approval_reasoning(invoice_data, vendor_data, budget_data, correlation_id)
            if decision.status == ApprovalStatus.AI_WARNING or decision.status == ApprovalStatus.AI_ALERT:
                invoice_data["warnings"] = invoice_data.get("warnings", []) + [decision.reason]
                invoice_data["ai_suggested_approver"] = decision.suggested_approver
                
                self.logger.warning(
                    "AI model returned warning for invoice approval decision. Approving invoice but flagging for review.",
                    extra={
                        "invoice_id": invoice_id,
                        "vendor_id": vendor_id,
                        "amount": invoice_data.get("amount"),
                        "reason": decision.reason,
                        "correlation_id": correlation_id
                    }
                )

            await self.update_invoice(invoice_data)
            self.logger.info(
                "Invoice required manual review",
                extra={
                    "invoice_id": invoice_data.get("invoice_id"),
                    "correlation_id": correlation_id,
                    "reason": reason
                }
            )
        except Exception as e:
            raise InvoiceApprovalException(
                f"Failed to reject invoice {invoice_data.get('invoice_id')}: {str(e)}"
            ) from e

    async def _handle_auto_approved(self, 
                                    invoice_data: Dict[str, Any], 
                                    vendor_data: Dict[str, Any],
                                    budget_data: Dict[str, Any],
                                    correlation_id: str) -> str:
        
        try:
            invoice_id = invoice_data.get("invoice_id")
            vendor_id = invoice_data.get("vendor_id")

            decision: ApprovalDecision = await self._ai_approval_reasoning(invoice_data, vendor_data, budget_data, correlation_id)
            if decision.status == ApprovalStatus.AI_WARNING:
                invoice_data["warnings"] = invoice_data.get("warnings", []) + [decision.reason]
                self.logger.warning(
                    "AI model returned warning for invoice approval decision. Approving invoice but flagging for review.",
                    extra={
                        "invoice_id": invoice_id,
                        "vendor_id": vendor_id,
                        "amount": invoice_data.get("amount"),
                        "reason": decision.reason,
                        "correlation_id": correlation_id
                    }
                )
                await self._approve_invoice(invoice_data, decision, approval_method="ai_warning")
            elif decision.status == ApprovalStatus.AI_ALERT:
                invoice_data["errors"] = invoice_data.get("errors", []) + [decision.reason]
                invoice_data["state"] = InvoiceState.MANUAL_REVIEW.value
                invoice_data["rejection_reason"] = f"AI High Alert: {decision.reason}" 
                await self.update_invoice(invoice_data)
                self.logger.error(
                    "AI model returned alert for invoice approval decision",
                    extra={
                        "invoice_id": invoice_id,
                        "vendor_id": vendor_id,
                        "amount": invoice_data.get("amount"),
                        "reason": decision.reason,
                        "correlation_id": correlation_id
                    }
                )
            elif decision.status == ApprovalStatus.AI_PASSED:
                await self._approve_invoice(invoice_data, 
                                             vendor_data, budget_data,
                                             decision, approval_method="ai_passed")
                self.logger.info(
                    "Invoice approved by AI decision",
                    extra={
                        "invoice_id": invoice_id,
                        "vendor_id": vendor_id,
                        "amount": invoice_data.get("amount"),
                        "correlation_id": correlation_id
                    }
                )

            return "AI approval decision: " + decision.status
        
        except Exception as e:
            raise InvoiceApprovalException(
                f"Failed to handle auto-approved invoice {invoice_data.get('invoice_id')}: {str(e)}"
            ) from e

    async def _ai_approval_reasoning(self, 
                                    invoice_data: Dict[str, Any], 
                                    vendor_data: Dict[str, Any], 
                                    budget_data: Dict[str, Any], 
                                    correlation_id: str) -> ApprovalDecision:
        """Use AI to determine if invoice should be approved."""
        # Placeholder for AI decision logic

        try:
            self.logger.info(
                "Invoking AI approval reasoning",
                extra={
                    "invoice_id": invoice_data.get("invoice_id"),
                    "vendor_id": vendor_data.get("vendor_id"),
                    "budget_id": budget_data.get("budget_id"),
                    "correlation_id": correlation_id
                }
            )

            agent: ApprovalAnalyticsAgent = ApprovalAnalyticsAgent()
            input = {
                "invoice": invoice_data,
                "vendor": vendor_data,
                "budget": budget_data
            }

            response: ApprovalAnalyticsOutcome = await agent.invoke(input)

            risk_level = response.risk_level
            if risk_level == "HIGH":
                return ApprovalDecision(
                    status=ApprovalStatus.AI_ALERT,
                    reason=f"High risk level detected by AI: {response.reasoning} (score: {response.risk_score}, confidence: {response.confidence})",
                    suggested_approver=response.suggested_approver
                )
            elif risk_level == "WARNING":
                return ApprovalDecision(
                    status=ApprovalStatus.AI_WARNING,
                    reason=f"Warning risk level detected by AI: {response.reasoning} (score: {response.risk_score}, confidence: {response.confidence})",
                    suggested_approver=response.suggested_approver
                )
            elif risk_level == "NONE":
                return ApprovalDecision(
                    status=ApprovalStatus.AI_PASSED,
                    reason=f"No significant risk detected by AI: {response.reasoning} (score: {response.risk_score}, confidence: {response.confidence})",
                    suggested_approver=response.suggested_approver
                )
        except Exception as e:
            self.logger.error(
                "AI approval reasoning failed, defaulting to auto-approval",
                extra={
                    "invoice_id": invoice_data.get("invoice_id"),
                    "vendor_id": invoice_data.get("vendor_id"),
                    "amount": invoice_data.get("amount"),
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "error_details": str(e)
                },
                exc_info=True
            )
            return ApprovalDecision(
                status=ApprovalStatus.AI_PASSED,
                reason=f"AI approval reasoning failed with error: {str(e)}. Defaulting to auto-approval."
            )


    async def _reject_invoice(self, invoice_data: Dict[str, Any], state: InvoiceState, reason: str) -> None:
        """Update invoice state to FAILED and save to storage."""
        try:
            invoice_data["state"] = state.value
            invoice_data["rejection_reason"] = reason
            invoice_data["review_status"] = ReviewStatus.REJECTED
            invoice_data["review_date"] = datetime.now(timezone.utc).isoformat()
            invoice_data["reviewed_by"] = "system"


            await self.update_invoice(invoice_data)
            self.logger.info(
                "Invoice Failed/Rejected",
                extra={
                    "invoice_id": invoice_data.get("invoice_id"),
                    "correlation_id": invoice_data.get("correlation_id"),
                    "reason": reason
                }
            )
        except Exception as e:
            raise InvoiceApprovalException(
                f"Failed to reject invoice {invoice_data.get('invoice_id')}: {str(e)}"
            ) from e

    async def _approve_invoice(self, 
                               invoice_data: Dict[str, Any],
                               vendor_data: Dict[str, Any],
                               budget_data: Dict[str, Any],
                               decision: ApprovalDecision,
                               approval_method: str = "auto"
                               ) -> None:
        """Update invoice state to APPROVED and save to storage."""
        try:

            invoice_data["state"] = InvoiceState.APPROVED.value
            invoice_data["reviewed_by"] = approval_method
            invoice_data["reviewed_date"] = datetime.now(timezone.utc).isoformat()
            invoice_data["review_status"] = ReviewStatus.APPROVED

            await self.update_invoice(invoice_data)

            if self.alert_notification_system:
                await self.alert_notification_system.send_alert(
                    invoice=invoice_data,
                    vendor=vendor_data,
                    budget=budget_data,
                    decision=decision
                )

            self.logger.info(
                "Invoice approved successfully",
                extra={
                    "invoice_id": invoice_data.get("invoice_id"),
                    "correlation_id": invoice_data.get("correlation_id")
                }
            )
        except Exception as e:
            raise InvoiceApprovalException(
                f"Failed to approve invoice {invoice_data.get('invoice_id')}: {str(e)}"
            ) from e

    async def _retrieve_invoice_metadata(self, 
                                         department_id: str, 
                                         invoice_id: str,
                                         correlation_id: str) -> Dict[str, Any]:
        """Retrieve invoice metadata from storage."""
        try:
            invoice_data = await self.get_invoice(department_id, invoice_id)

            if not invoice_data:
                raise InvoiceNotFoundException(
                    f"Invoice not found: {invoice_id} in department: {department_id}"
                )
            
            self.logger.debug(
                "Invoice metadata retrieved successfully",
                extra={
                    "invoice_id": invoice_id,
                    "document_type": invoice_data.get("document_type"),
                    "correlation_id": correlation_id
                }
            )

            return invoice_data
        except InvoiceNotFoundException:
            raise
        except Exception as e:
            raise StorageException(
                f"Failed to retrieve invoice metadata: {str(e)}"
            ) from e

    async def _retrieve_vendor_metadata(self, vendor_id: str, correlation_id: str) -> Dict[str, Any]:
        """Retrieve vendor metadata from storage."""
        try:
            vendor = await self.vendor_table_client.get_entity(
                partition_key="VENDOR", # partition key is fixed for vendors
                row_key=vendor_id
            )
            if not vendor:
                raise VendorNotFoundException(f"Vendor {vendor_id} not found")

            self.logger.debug(
                "Vendor metadata retrieved successfully",
                extra={
                    "vendor_id": vendor_id,
                    "correlation_id": correlation_id
                }
            )

            return vendor
        except VendorNotFoundException:
            raise
        except Exception as e:
            raise StorageException(
                f"Failed to retrieve vendor metadata: {str(e)}"
            ) from e
        
    async def _retrieve_budget_metadata(self, invoice_data: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
        """Retrieve budget metadata from storage."""        
        # Placeholder for budget retrieval logic
        # This would typically involve querying the budget table based on department_id, project_id, and category
        department_id = invoice_data.get("department_id")
        project_id = invoice_data.get("project_id")
        category = invoice_data.get("category")
        fiscal_year = invoice_data.get("fiscal_year")
        lower = CompoundKeyStructure.LOWER_BOUND.value
        compound_key = f"{department_id}{lower}{project_id}{lower}{category}"
        
        try:
            budget = self.budget_table_client.get_entity(
                partition_key=fiscal_year, # Partition key is fiscal year
                row_key=compound_key
            )
            if not budget:
                raise BudgetNotFoundException(f"Budget not found for department: {department_id}, project: {project_id}, category: {category}, fiscal_year: {fiscal_year}")

            self.logger.debug(
                "Budget metadata retrieved successfully",
                extra={
                    "department_id": department_id,
                    "project_id": project_id,
                    "category": category,
                    "fiscal_year": fiscal_year,
                    "correlation_id": correlation_id
                }
            )
            return budget
        
        except BudgetNotFoundException:
            raise
        except Exception as e:
            raise StorageException(f"Failed to retrieve budget metadata: {str(e)}") from e

    async def _deterministic_approval_decision(self, 
                                               invoice_data: Dict[str, Any], 
                                               vendor_data: Dict[str, Any],
                                               budget_data: Dict[str, Any],
                                               correlation_id: str
                                               ) -> ApprovalDecision:
        """Determine if invoice meets auto-approval criteria."""
        # Placeholder for actual approval logic
        amount = invoice_data.get("amount", 0)
        vendor_active = vendor_data.get("active", False)
        vendor_approved = vendor_data.get("approved", False)
        vendor_auto_approve = vendor_data.get("auto_approve", False)
        vendor_auto_approve_limit = vendor_data.get("auto_approve_limit", 0)

        budget_status = budget_data.get("status", None)
        budget_approval_required_over = budget_data.get("approval_required_over", 0.0)
        budget_auto_approve_under = budget_data.get("auto_approve_under", 0.0)
        approval_decision:ApprovalDecision

        if vendor_active and vendor_approved and vendor_auto_approve:
            if budget_status != BudgetStatus.ACTIVE:
                approval_decision = ApprovalDecision(
                    status=ApprovalStatus.REJECTED,
                    reason=f"Budget status is {budget_status}, not active"
                )
            elif vendor_auto_approve_limit and amount > vendor_auto_approve_limit:
                approval_decision = ApprovalDecision(
                    status=ApprovalStatus.MANUAL_APPROVAL_REQUIRED,
                    reason=f"Amount exceeds vendor auto-approval limit of {vendor_auto_approve_limit}"
                )
            elif budget_approval_required_over and amount > budget_approval_required_over:
                approval_decision = ApprovalDecision(
                    status=ApprovalStatus.MANUAL_APPROVAL_REQUIRED,
                    reason=f"Amount exceeds budget approval required limit of {budget_approval_required_over}"
                )

            elif budget_auto_approve_under and amount < budget_auto_approve_under:
                approval_decision = ApprovalDecision(
                    status=ApprovalStatus.AUTO_APPROVED,
                    reason=f"Amount is below budget auto-approval threshold of {budget_auto_approve_under}"
                )
            else:
                approval_decision = ApprovalDecision(
                    status=ApprovalStatus.REJECTED,
                    reason="Amount does not meet auto-approval criteria based on vendor and budget thresholds"
                )
        else:
            approval_decision = ApprovalDecision(
                status=ApprovalStatus.REJECTED,
                reason="Vendor does not meet auto-approval criteria (active, approved, auto_approve)"
            )

        if approval_decision.status == ApprovalStatus.AUTO_APPROVED:
            self.logger.info(
                "Invoice meets auto-approval criteria",
                extra={
                    "invoice_id": invoice_data.get("invoice_id"),
                    "amount": amount,
                    "vendor_id": invoice_data.get("vendor_id"),
                    "budget_status": budget_status,
                    "correlation_id": correlation_id
                }
            )            

        return approval_decision

if __name__ == "__main__":
    agent = ApprovalAgent()
    agent.setup_signal_handlers()
    asyncio.run(agent.run())
