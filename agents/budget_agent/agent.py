"""
Budget Agent - Tracks and validates budget allocations.
"""

import asyncio
import json
from typing import Dict, Any
from langsmith import traceable

from agents.budget_agent.tools.alert_notification_system import AlertNotificationSystem
from agents.budget_agent.tools.budget_analytics_agent import BudgetAnalyticsAgent, BudgetAnalyticsOutcome
from agents.budget_agent.tools.budget_classification_agent import BudgetClassificationAgent
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.config.settings import settings
from agents.base_agent import BaseAgent
from shared.models.invoice import InvoiceInternalMessage, InvoiceState
from shared.utils.constants import CompoundKeyStructure, InvoiceSubjects, SubscriptionNames

class BudgetAgent(BaseAgent):
    """
    Budget Tracking Agent manages budget allocations.
    
    Responsibilities:
    - Allocate invoice to department/project budget
    - Check remaining budget availability
    - Calculate % budget consumed
    - Flag over-budget scenarios
    - Update invoice state to BUDGET_CHECKED
    - Publish invoice.budget_checked message
    """
    
    def __init__(self, shutdown_event: asyncio.Event = asyncio.Event()):
        super().__init__(
            agent_name="BudgetAgent",
            subscription_name=SubscriptionNames.BUDGET_AGENT,
            shutdown_event=shutdown_event
        )

        self.budget_table_client = TableStorageService(
            storage_account_url=settings.table_storage_account_url,
            table_name=settings.budgets_table_name
        )

        self.budget_classification_agent = BudgetClassificationAgent()
        self.budget_analytics_agent = BudgetAnalyticsAgent()
        self.alert_notification_system = AlertNotificationSystem()

    @traceable(name="budget_agent.process_invoice", tags=["budget", "agent"], metadata={"version": "1.0"})
    async def process_invoice(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check budget availability for invoice.
        
        Args:
            invoice_id: Invoice ID
            message_data: Message payload
            
        Returns:
            Result data for next state
        """
        invoice_id = message_data["invoice_id"]
        department_id = message_data["department_id"]
        category = message_data["category"]
        project_id = message_data.get("project_id", "GEN-0")
        budget_year = message_data.get("budget_year", "FY2024")

        self.logger.info(f"Extracting data from invoice: [{invoice_id}], department_id {department_id}, project_id {project_id}, category {category}")

        # Get invoice from storage
        invoice = await self.get_invoice(department_id, invoice_id)

        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        classification = await self.budget_classification_agent.ainvoke({
            "invoice": invoice
        })
        if not classification:
            invoice.get("errors", []).append(InvoiceInternalMessage(
                agent="Budget Classification Agent",
                message="Failed to classify invoice for budget allocation.",
                code="BUDGET_CLASSIFICATION_FAILED"
            ))
            self.logger.warning("Classification not found from budget classification agent.")
            raise ValueError("Classification not found from budget classification agent.")
        
        self.logger.info(f"Budget classification result: {classification}")

        if classification.get("category", None) != category:
            invoice.update({
                "category": classification.get("category", None),
            })
            invoice.get("warnings", []).append(InvoiceInternalMessage(
                agent="Budget Classification Agent",
                message=f"Invoice category '{category}' updated to '{classification.get('category', None)}' based on budget classification.",
                code="BUDGET_CATEGORY_UPDATED"
            ))
            self.logger.info("Budget classification does not match existing data.")

        lower_bound = CompoundKeyStructure.LOWER_BOUND.value
        compound_key = f"{classification.get('department', None)}{lower_bound}{project_id}{lower_bound}{classification.get('category', None)}"

        budget_filters = [
            ("PartitionKey", budget_year),
            ("RowKey", f"{compound_key}"),
        ]
        budgets = await self.budget_table_client.query_entities(
            filters_query=budget_filters
        )
        budget = budgets[0] if budgets and len(budgets) > 0 else None

        if not budget or len(budget) == 0:
            invoice.get("errors", []).append(InvoiceInternalMessage(
                agent="Budget Agent",
                message=f"No budget allocation found for {classification.get('department', None)}, project {project_id}, category {classification.get('category', None)} for {budget_year}.",
                code="BUDGET_ALLOCATION_NOT_FOUND"
            ))
            self.logger.error(f"No budget allocation found for {classification.get('department', None)}, project {project_id}, category {classification.get('category', None)} for {budget_year}")
            raise ValueError(f"No budget allocation found for {classification.get('department', None)}, project {project_id}, category {classification.get('category', None)} for {budget_year}")

        response: BudgetAnalyticsOutcome = await self.budget_analytics_agent.ainvoke({
            "invoice": invoice,
            "budget": budget
        })

        self.logger.info(f"Budget analytics result: {response}")
        invoice["state"] = "BUDGET_CHECKED"
        invoice["budget_analysis"] = json.dumps({
            "explanation": response.explanation,
            "confidence_score": response.confidence_score
        })

        self.alert_evaluation(response, invoice, budget)

        await self.update_invoice(invoice)

        # TODO
        # improve error handling and reporting from budget analytics agent
        
        return {
            "invoice_id": invoice_id,
            "department_id": department_id,
            "state": InvoiceState.BUDGET_CHECKED.value,
            "event_type": "BudgetAgentGenerated",
        }

    def alert_evaluation(self, analysis: BudgetAnalyticsOutcome, invoice: dict, budget: dict) -> bool:
        """Determine if an alert should be sent based on analysis."""

        budget_impact = analysis.outcomes.get("budget_impact", {})
        anomaly_detection = analysis.outcomes.get("anomaly_detection", {})

        alert_conditions = [
            budget_impact.get("budget_impact") == "High",
            anomaly_detection.get("risk_level") == "High"
        ]

        if any(alert_conditions):
            self.alert_notification_system.send_alert(
                approver_email=budget.get("approver_email", "finance-approver@company"), # change later
                subject=f"Budget Alert for Invoice {invoice.get('invoice_number', '')} from {invoice.get('vendor_name', '')}",
                message="\n".join(analysis.explanation)
            )


    def get_next_subject(self) -> str:
        """Return the next message subject."""
        return InvoiceSubjects.BUDGET_CHECKED.value


    async def release_resources(self):
        """Release any resources held by the agent."""
        self.logger.info(f"Releasing resources for {self.agent_name}...")
        if self.budget_table_client:
            await self.budget_table_client.close()


if __name__ == "__main__":
    agent = BudgetAgent()
    agent.setup_signal_handlers()
    asyncio.run(agent.run())

