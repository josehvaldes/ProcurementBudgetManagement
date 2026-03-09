"""
Budget Agent - Validates budget availability and tracks allocations.

This agent is responsible for:
- Classifying invoices into appropriate budget categories
- Checking budget availability and remaining funds
- Analyzing budget impact and anomalies
- Sending alerts for high-risk or over-budget scenarios
- Transitioning invoices to BUDGET_CHECKED state
- Publishing budget check completion events
"""

import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from langsmith import traceable
from shared.config.settings import settings
from agents.base_agent import BaseAgent
from agents.budget_agent.tools.alert_notification_system import AlertNotificationSystem
from agents.budget_agent.tools.budget_analytics_agent import BudgetAnalyticsAgent, BudgetAnalyticsOutcome
from agents.budget_agent.tools.budget_classification_agent import BudgetClassificationAgent
from shared.models.budget import Budget
from shared.models.invoice import InvoiceInternalMessage, InvoiceState
from shared.utils.constants import AgentNames, CompoundKeyStructure, InvoiceSubjects, SubscriptionNames
from shared.utils.exceptions import (
    InvoiceNotFoundException,
    BudgetException,
    InvoiceProcessingException,
    StorageException
)


class BudgetAgent(BaseAgent):
    """
    Budget Tracking Agent manages budget allocations and availability.
    
    This agent orchestrates the budget validation workflow:
    1. Classify invoice into budget category (AI-powered)
    2. Retrieve applicable budget allocation
    3. Analyze budget impact and availability
    4. Detect spending anomalies
    5. Send alerts for high-risk scenarios
    6. Update invoice state to BUDGET_CHECKED
    
    Attributes:
        agent_name (str): Agent identifier
        budget_classification_agent (BudgetClassificationAgent): AI classifier
        budget_analytics_agent (BudgetAnalyticsAgent): Analytics and anomaly detection
        alert_notification_system (AlertNotificationSystem): Alert sender
    """
    
    def __init__(self, shutdown_event: Optional[asyncio.Event] = None):
        """
        Initialize the Budget Agent.
        
        Args:
            shutdown_event: Event to signal graceful shutdown
        """
        super().__init__(
            agent_name=AgentNames.BUDGET_AGENT,
            subscription_name=[SubscriptionNames.BUDGET_AGENT, SubscriptionNames.BUDGET_COMPENSATION],
            shutdown_event=shutdown_event or asyncio.Event()
        )

        self.budget_classification_agent: Optional[BudgetClassificationAgent] = None
        self.budget_analytics_agent: Optional[BudgetAnalyticsAgent] = None
        self.alert_notification_system: Optional[AlertNotificationSystem] = None

        try:

            # Initialize AI-powered tools
            self.budget_classification_agent = BudgetClassificationAgent()
            self.budget_analytics_agent = BudgetAnalyticsAgent()
            self.alert_notification_system = AlertNotificationSystem()

            self.logger.info(
                "BudgetAgent initialized successfully",
                extra={
                    "agent_name": self.agent_name,
                    "subscription": SubscriptionNames.BUDGET_AGENT,
                }
            )
        except Exception as e:
            self.logger.error(
                f"Failed to initialize BudgetAgent: {str(e)}",
                exc_info=True,
                extra={"error_type": type(e).__name__}
            )
            raise

    async def release_resources(self) -> None:
        """
        Release resources held by the agent.
        
        Performs cleanup of Azure service clients and AI agents.
        Should be called during graceful shutdown.
        """
        self.logger.info(
            f"Releasing resources for {self.agent_name}",
            extra={"agent_name": self.agent_name}
        )
        
        cleanup_errors = []
        
        # Close budget table client
        # Close AI agents (if they have resources)
        for agent_name, agent in [
            ("budget_classification_agent", self.budget_classification_agent),
            ("budget_analytics_agent", self.budget_analytics_agent),
        ]:
            if agent:
                try:
                    if hasattr(agent, 'close'):
                        await agent.close()
                    self.logger.debug(f"{agent_name} closed successfully")
                except Exception as e:
                    error_msg = f"Error closing {agent_name}: {str(e)}"
                    self.logger.warning(error_msg, exc_info=True)
                    cleanup_errors.append(error_msg)
        
        if cleanup_errors:
            self.logger.warning(
                f"Resource cleanup completed with {len(cleanup_errors)} errors",
                extra={"cleanup_errors": cleanup_errors}
            )
        else:
            self.logger.info("All resources released successfully")

    @traceable(
        name="budget_agent.process_invoice",
        tags=["budget", "agent", "allocation"],
        metadata={"version": "1.0", "agent": "BudgetAgent"}
    )
    async def process_invoice(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        subject = message_data.get("subject")
        if subject == InvoiceSubjects.VALIDATED:
            return await self._process_invoice_validated(message_data)
        if subject == InvoiceSubjects.PAYMENT_FAILED:
            return await self._process_budget_compensation(message_data)
    
    async def _process_budget_compensation(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        invoice_id = message_data.get("invoice_id")
        department_id = message_data.get("department_id")
        correlation_id = message_data.get("correlation_id", invoice_id)
        
        if not invoice_id or not department_id:
            raise ValueError("invoice_id and department_id are required in message_data")

        self.logger.info(
            "Processing budget compensation",
            extra={
                "invoice_id": invoice_id,
                "department_id": department_id,
                "correlation_id": correlation_id,
                "agent": self.agent_name
            }
        )
        try:
            invoice_data = await self._retrieve_invoice(
                department_id=department_id,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )

            budget_data = await self.retrieve_budget_metadata(
                invoice_data=invoice_data,
                correlation_id=correlation_id
            )
            amount = invoice_data.get("amount", 0)

            await self._compensate_budget(
                invoice_data=invoice_data,
                budget_data=budget_data,
                amount=amount,
                correlation_id=correlation_id
            )

        except Exception as e:
            self.logger.error(
                f"Error processing budget compensation for invoice {invoice_id}: {str(e)}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                },
                exc_info=True
            )
            raise BudgetException(
                f"Failed to process budget compensation for invoice {invoice_id}: {str(e)}"
            ) from e

        # compensation agent doesn't publish next state as payment failure is a terminal state for the invoice.
        return None
    
    async def _compensate_budget(self, invoice_data: Dict[str, Any], budget_data: Dict[str, Any], amount: float, correlation_id: str) -> None:
        
        self.logger.info(
                "Budget compensation completed successfully",
                extra={
                    "invoice_id": invoice_data.get("invoice_id"),
                    "compensated_amount": amount,
                    "correlation_id": correlation_id
                }
            )
        
        try:            
            # Build compensation details
            budget: Budget = Budget.from_dict(budget_data)
            reserved = budget.reserved_amount
            if reserved >= amount:
                budget.reserved_amount = reserved - amount
                # recalculate budget metrics after compensation
                budget.calculate_metrics()

            else:
                raise BudgetException(
                    f"Insufficient reserved budget  "
                    f"Reserved: {reserved}, Required: {amount}"
                )

            message = (f"Budget compensated for payment failure of invoice {invoice_data.get('invoice_id')}. "
                                     f"Original reserved amount: {reserved}, "
                                     f"New reserved amount: {budget.reserved_amount}, "
                                     f"New consumed amount: {budget.consumed_amount}")

            # Send alert
            approver_email = budget.approver_email or settings.default_finance_approver_email
            await self.alert_notification_system.send_alert(
                    approver_email=approver_email,
                    subject="alert_subject_budget_compensation",
                    message=message
                )
            alert_summary = f"Budget compensation alert sent to {approver_email} for invoice {invoice_data.get('invoice_id')}"
            budget.alerts_sent.append(alert_summary)
            self.budget_table.upsert_entity(budget.to_dict())
        except BudgetException as e:
            self.logger.error(
                f"Budget exception occurred: {str(e)}",
                extra={
                    "invoice_id": invoice_data.get("invoice_id"),
                    "budget": budget_data.get("budget_id"),
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                },
                exc_info=True
            )
            raise
        except Exception as e:
            raise BudgetException(
                f"Failed to compensate budget: {str(e)}"
            ) from e

    async def _process_invoice_validated(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check budget availability and allocate invoice to budget.
        
        This method orchestrates the complete budget validation workflow:
        1. Retrieve invoice from Table Storage
        2. Classify invoice into budget category (AI)
        3. Retrieve applicable budget allocation
        4. Analyze budget impact and availability
        5. Detect spending anomalies
        6. Send alerts if necessary
        7. Update invoice state to BUDGET_CHECKED
        
        Budget Check Flow:
        - Budget Available → BUDGET_CHECKED (proceed to approval)
        - Budget Exceeded → BUDGET_CHECKED with HIGH_IMPACT flag (alert sent)
        - No Budget Found → Error (invoice marked for manual review)
        
        Args:
            message_data: Message payload containing:
                - invoice_id (str): Unique invoice identifier
                - department_id (str): Department identifier
                - category (str, optional): Invoice category (may be reclassified)
                - project_id (str, optional): Project identifier (default: "GEN-0")
                - budget_year (str, optional): Fiscal year (default: "FY2024")
                - correlation_id (str, optional): Correlation ID for tracing
                
        Returns:
            Dict containing:
                - invoice_id (str): Invoice identifier
                - department_id (str): Department identifier
                - state (str): New invoice state (BUDGET_CHECKED)
                - event_type (str): Event type for next stage
                - budget_checked_at (str): Check timestamp
                - correlation_id (str): Correlation ID
                
        Raises:
            InvoiceNotFoundException: If invoice not found in storage
            BudgetException: If budget validation fails
            StorageException: If storage operations fail
        """
        # Extract and validate message data
        invoice_id = message_data.get("invoice_id")
        department_id = message_data.get("department_id")
        correlation_id = message_data.get("correlation_id", invoice_id)
        
        if not invoice_id or not department_id:
            raise ValueError("invoice_id and department_id are required in message_data")
        
        self.logger.info(
            "Starting budget validation workflow",
            extra={
                "invoice_id": invoice_id,
                "department_id": department_id,
                "correlation_id": correlation_id,
                "agent": self.agent_name
            }
        )
        
        try:
            # Step 1: Retrieve invoice
            invoice_data = await self._retrieve_invoice(
                department_id=department_id,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )

            budget_year = invoice_data.get("budget_year", None)
            category = invoice_data.get("category", None)
            project_id = invoice_data.get("project_id", None)

            # Step 2: Classify invoice into budget category
            classification = await self._classify_invoice_category(
                invoice_data=invoice_data,
                original_category=category,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            # Step 3: Retrieve budget allocation
            budget = await self._retrieve_budget_allocation(
                department_id=classification.get("department"),
                project_id=project_id,
                category=classification.get("category"),
                budget_year=budget_year,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            # Step 4: Analyze budget impact
            analytics_result = await self._analyze_budget_impact(
                invoice_data=invoice_data,
                budget=budget,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            # Step 5: Update invoice with analysis results
            await self._update_invoice_with_budget_analysis(
                invoice_data=invoice_data,
                analytics_result=analytics_result,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            # Step 6: Evaluate and send alerts if necessary
            await self._evaluate_and_send_alerts(
                analytics_result=analytics_result,
                invoice_data=invoice_data,
                budget=budget,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            self.logger.info(
                "Budget validation completed successfully",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "state": InvoiceState.BUDGET_CHECKED.value,
                    "budget_impact": analytics_result.outcomes.get("budget_impact", {}).get("budget_impact"),
                    "confidence_score": analytics_result.confidence_score
                }
            )
            
            return {
                "invoice_id": invoice_id,
                "department_id": department_id,
                "state": InvoiceState.BUDGET_CHECKED.value,
                "event_type": "BudgetAgentCompleted",
                "budget_checked_at": datetime.now(timezone.utc).isoformat(),
                "correlation_id": correlation_id
            }
            
        except InvoiceNotFoundException:
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
            
        except BudgetException as e:
            self.logger.error(
                f"Budget validation failed for invoice: {invoice_id}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "error_type": "BudgetValidationFailed",
                    "error_details": str(e)
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
                f"Unexpected error processing budget check: {invoice_id}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise BudgetException(
                f"Failed to process budget check for invoice {invoice_id}: {str(e)}"
            ) from e

    async def _retrieve_invoice(
        self,
        department_id: str,
        invoice_id: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Retrieve invoice from Table Storage.
        
        Args:
            department_id: Department identifier
            invoice_id: Invoice identifier
            correlation_id: Correlation ID for tracing
            
        Returns:
            Invoice data dictionary
            
        Raises:
            InvoiceNotFoundException: If invoice not found
            StorageException: If retrieval fails
        """
        self.logger.debug(
            "Retrieving invoice for budget validation",
            extra={
                "invoice_id": invoice_id,
                "department_id": department_id,
                "correlation_id": correlation_id
            }
        )
        
        try:
            invoice_data = await self.get_invoice(department_id, invoice_id)
            
            if not invoice_data:
                raise InvoiceNotFoundException(
                    f"Invoice not found: {invoice_id} in department: {department_id}"
                )
            
            self.logger.debug(
                "Invoice retrieved successfully",
                extra={
                    "invoice_id": invoice_id,
                    "vendor_name": invoice_data.get("vendor_name", "unknown"),
                    "amount": invoice_data.get("amount", 0),
                    "correlation_id": correlation_id
                }
            )
            
            return invoice_data
            
        except InvoiceNotFoundException:
            raise
        except Exception as e:
            raise StorageException(
                f"Failed to retrieve invoice for budget check: {str(e)}"
            ) from e

    async def _classify_invoice_category(
        self,
        invoice_data: Dict[str, Any],
        original_category: Optional[str],
        invoice_id: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Classify invoice into appropriate budget category using AI.
        
        Args:
            invoice_data: Invoice data
            original_category: Original category (may be reclassified)
            invoice_id: Invoice identifier for logging
            correlation_id: Correlation ID for tracing
            
        Returns:
            Classification result with department and category
            
        Raises:
            BudgetException: If classification fails
        """
        self.logger.info(
            "Classifying invoice into budget category",
            extra={
                "invoice_id": invoice_id,
                "original_category": original_category,
                "correlation_id": correlation_id
            }
        )
        
        try:
            classification = await self.budget_classification_agent.ainvoke({
                "invoice": invoice_data
            })
            
            if not classification:
                raise BudgetException(
                    "Budget classification agent returned no result"
                )
            
            classified_category = classification.get("category")
            classified_department = classification.get("department")
            
            self.logger.info(
                "Invoice classified successfully",
                extra={
                    "invoice_id": invoice_id,
                    "classified_category": classified_category,
                    "classified_department": classified_department,
                    "original_category": original_category,
                    "category_changed": classified_category != original_category,
                    "correlation_id": correlation_id
                }
            )
            
            # If category changed, update invoice and add warning
            if classified_category and classified_category != original_category:
                invoice_data["category"] = classified_category
                
                warning_message = InvoiceInternalMessage(
                    agent="BudgetClassificationAgent",
                    message=f"Invoice category updated from '{original_category}' to '{classified_category}' based on AI classification.",
                    code="BUDGET_CATEGORY_RECLASSIFIED",
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                
                if "warnings" not in invoice_data:
                    invoice_data["warnings"] = []
                invoice_data["warnings"].append(warning_message.__dict__)
                
                self.logger.warning(
                    "Invoice category reclassified",
                    extra={
                        "invoice_id": invoice_id,
                        "from_category": original_category,
                        "to_category": classified_category,
                        "correlation_id": correlation_id
                    }
                )
            
            return classification
            
        except Exception as e:
            error_message = InvoiceInternalMessage(
                agent="BudgetClassificationAgent",
                message=f"Failed to classify invoice for budget allocation: {str(e)}",
                code="BUDGET_CLASSIFICATION_FAILED",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
            if "errors" not in invoice_data:
                invoice_data["errors"] = []
            invoice_data["errors"].append(error_message.__dict__)
            
            raise BudgetException(
                f"Failed to classify invoice category: {str(e)}"
            ) from e

    async def _retrieve_budget_allocation(
        self,
        department_id: str,
        project_id: str,
        category: str,
        budget_year: str,
        invoice_id: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Retrieve budget allocation from storage.
        
        Args:
            department_id: Department identifier
            project_id: Project identifier
            category: Budget category
            budget_year: Fiscal year
            invoice_id: Invoice identifier for logging
            correlation_id: Correlation ID for tracing
            
        Returns:
            Budget allocation data
            
        Raises:
            BudgetException: If budget not found
            StorageException: If retrieval fails
        """
        self.logger.debug(
            "Retrieving budget allocation",
            extra={
                "invoice_id": invoice_id,
                "department_id": department_id,
                "project_id": project_id,
                "category": category,
                "budget_year": budget_year,
                "correlation_id": correlation_id
            }
        )
        
        try:
            # Build compound key for budget lookup
            lower_bound = CompoundKeyStructure.LOWER_BOUND.value
            compound_key = f"{department_id}{lower_bound}{project_id}{lower_bound}{category}"
            
            budget_filters = [
                ("PartitionKey", budget_year),
                ("RowKey", compound_key),
            ]
            # use budget_table from BaseAgent which is initialized with the correct table name
            budgets = await self.budget_table.query_entities(
                filters_query=budget_filters
            )
            
            if not budgets or len(budgets) == 0:
                error_msg = (
                    f"No budget allocation found for department '{department_id}', "
                    f"project '{project_id}', category '{category}' in {budget_year}"
                )
                
                self.logger.error(
                    error_msg,
                    extra={
                        "invoice_id": invoice_id,
                        "department_id": department_id,
                        "project_id": project_id,
                        "category": category,
                        "budget_year": budget_year,
                        "correlation_id": correlation_id
                    }
                )
                
                raise BudgetException(error_msg)
            
            budget = budgets[0]
            
            self.logger.info(
                "Budget allocation retrieved successfully",
                extra={
                    "invoice_id": invoice_id,
                    "budget_id": budget.get("budget_id"),
                    "allocated_amount": budget.get("allocated_budget"),
                    "remaining_amount": budget.get("remaining_amount"),
                    "correlation_id": correlation_id
                }
            )
            
            return budget
            
        except BudgetException:
            raise
        except Exception as e:
            raise StorageException(
                f"Failed to retrieve budget allocation: {str(e)}"
            ) from e

    async def _analyze_budget_impact(
        self,
        invoice_data: Dict[str, Any],
        budget: Dict[str, Any],
        invoice_id: str,
        correlation_id: str
    ) -> BudgetAnalyticsOutcome:
        """
        Analyze budget impact and detect anomalies.
        
        Args:
            invoice_data: Invoice data
            budget: Budget allocation data
            invoice_id: Invoice identifier for logging
            correlation_id: Correlation ID for tracing
            
        Returns:
            Budget analytics result with impact assessment and anomalies
            
        Raises:
            BudgetException: If analysis fails
        """
        self.logger.info(
            "Analyzing budget impact and anomalies",
            extra={
                "invoice_id": invoice_id,
                "invoice_amount": invoice_data.get("amount"),
                "budget_remaining": budget.get("remaining_amount"),
                "correlation_id": correlation_id
            }
        )
        
        try:
            analytics_result: BudgetAnalyticsOutcome = await self.budget_analytics_agent.ainvoke({
                "invoice": invoice_data,
                "budget": budget
            })
            
            if not analytics_result:
                raise BudgetException(
                    "Budget analytics agent returned no result"
                )
            
            budget_impact = analytics_result.outcomes.get("budget_impact", {})
            anomaly_detection = analytics_result.outcomes.get("anomaly_detection", {})
            
            self.logger.info(
                "Budget analysis completed",
                extra={
                    "invoice_id": invoice_id,
                    "budget_impact_level": budget_impact.get("budget_impact"),
                    "risk_level": anomaly_detection.get("risk_level"),
                    "confidence_score": analytics_result.confidence_score,
                    "correlation_id": correlation_id
                }
            )
            
            return analytics_result
            
        except Exception as e:
            raise BudgetException(
                f"Failed to analyze budget impact: {str(e)}"
            ) from e

    async def _update_invoice_with_budget_analysis(
        self,
        invoice_data: Dict[str, Any],
        analytics_result: BudgetAnalyticsOutcome,
        invoice_id: str,
        correlation_id: str
    ) -> None:
        """
        Update invoice with budget analysis results.
        
        Args:
            invoice_data: Invoice data to update
            analytics_result: Budget analytics result
            invoice_id: Invoice identifier for logging
            correlation_id: Correlation ID for tracing
            
        Raises:
            StorageException: If update fails
        """
        self.logger.debug(
            "Updating invoice with budget analysis",
            extra={
                "invoice_id": invoice_id,
                "correlation_id": correlation_id
            }
        )
        
        try:
            # Update invoice state
            invoice_data["state"] = InvoiceState.BUDGET_CHECKED.value
            
            # Store budget analysis results
            invoice_data["budget_analysis"] = json.dumps({
                "explanation": analytics_result.explanation,
                "confidence_score": analytics_result.confidence_score,
                "outcomes": analytics_result.outcomes,
                "analyzed_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Persist to storage
            await self.complete_processing(
                invoice=invoice_data,
                new_state=InvoiceState.BUDGET_CHECKED.value,
                event_type=SubscriptionNames.BUDGET_AGENT,
                correlation_id=correlation_id
                )            
            
            self.logger.info(
                "Invoice updated with budget analysis",
                extra={
                    "invoice_id": invoice_id,
                    "new_state": InvoiceState.BUDGET_CHECKED.value,
                    "correlation_id": correlation_id
                }
            )
        except Exception as e:
            raise InvoiceProcessingException(
                f"Failed to update invoice with budget analysis: {str(e)}"
            ) from e

    async def _evaluate_and_send_alerts(
        self,
        analytics_result: BudgetAnalyticsOutcome,
        invoice_data: Dict[str, Any],
        budget: Dict[str, Any],
        invoice_id: str,
        correlation_id: str
    ) -> None:
        """
        Evaluate budget analysis and send alerts if necessary.
        
        Alerts are sent when:
        - Budget impact is High (over budget or significantly impacts remaining funds)
        - Anomaly risk level is High (unusual spending pattern detected)
        
        Args:
            analytics_result: Budget analytics result
            invoice_data: Invoice data
            budget: Budget allocation data
            invoice_id: Invoice identifier for logging
            correlation_id: Correlation ID for tracing
        """
        budget_impact = analytics_result.outcomes.get("budget_impact", {})
        anomaly_detection = analytics_result.outcomes.get("anomaly_detection", {})
        
        budget_impact_level = budget_impact.get("budget_impact")
        risk_level = anomaly_detection.get("risk_level")
        
        alert_conditions = [
            budget_impact_level == "High",
            risk_level == "High"
        ]
        
        if any(alert_conditions):
            self.logger.warning(
                "High-risk budget scenario detected - sending alert",
                extra={
                    "invoice_id": invoice_id,
                    "budget_impact": budget_impact_level,
                    "risk_level": risk_level,
                    "invoice_amount": invoice_data.get("amount"),
                    "budget_remaining": budget.get("remaining_amount"),
                    "correlation_id": correlation_id
                }
            )
            
            try:
                # Prepare alert details
                alert_subject = (
                    f"Budget Alert: High-Risk Invoice {invoice_data.get('invoice_number', 'N/A')} "
                    f"from {invoice_data.get('vendor_name', 'Unknown Vendor')}"
                )
                
                alert_message = "\n".join([
                    f"Invoice ID: {invoice_id}",
                    f"Amount: ${invoice_data.get('amount', 0):.2f}",
                    f"Budget Impact: {budget_impact_level}",
                    f"Risk Level: {risk_level}",
                    "",
                    "Analysis:",
                    *analytics_result.explanation
                ])
                
                # Send alert
                approver_email = budget.get("approver_email", settings.default_finance_approver_email)
                
                await self.alert_notification_system.send_alert(
                    approver_email=approver_email,
                    subject=alert_subject,
                    message=alert_message
                )
                
                self.logger.info(
                    "Budget alert sent successfully",
                    extra={
                        "invoice_id": invoice_id,
                        "approver_email": approver_email,
                        "alert_type": "high_risk_budget",
                        "correlation_id": correlation_id
                    }
                )
                
            except Exception as e:
                # Alert failure is non-critical - log warning but don't fail
                self.logger.warning(
                    f"Failed to send budget alert (non-critical): {str(e)}",
                    extra={
                        "invoice_id": invoice_id,
                        "error_type": type(e).__name__,
                        "correlation_id": correlation_id
                    },
                    exc_info=True
                )
        else:
            self.logger.debug(
                "No alerts required - budget impact within acceptable range",
                extra={
                    "invoice_id": invoice_id,
                    "budget_impact": budget_impact_level,
                    "risk_level": risk_level,
                    "correlation_id": correlation_id
                }
            )

    def get_next_subject(self) -> str:
        """
        Get the message subject for the next processing stage.
        
        Returns:
            Subject name for invoice.budget_checked messages
        """
        return InvoiceSubjects.BUDGET_CHECKED


if __name__ == "__main__":
    agent = BudgetAgent()
    agent.setup_signal_handlers()
    asyncio.run(agent.run())

