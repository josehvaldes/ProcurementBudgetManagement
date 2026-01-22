"""
Budget Agent - Tracks and validates budget allocations.
"""

import asyncio
from typing import Dict, Any, Optional
from langsmith import traceable

from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.config.settings import settings
from agents.base_agent import BaseAgent
from shared.models.invoice import InvoiceState
from shared.utils.constants import InvoiceSubjects, SubscriptionNames

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

        compound_key = f"{department_id}:{project_id}:{category}"
        budget_year = message_data.get("budget_year", "FY2024")

        self.logger.info(f"Extracting data from invoice: [{invoice_id}], department_id {department_id}, project_id {project_id}, category {category}")
        # Get invoice from storage
        invoice = await self.get_invoice(department_id, invoice_id)

        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        budget_filters = [
            ("PartitionKey", budget_year),
            ("RowKey", f"{compound_key}"),
        ]
        budget = await self.budget_table_client.query_entities(
            filters_query=budget_filters
        )
        
        # TODO: Implement budget checking logic
        # - Get budget allocation for department/project
        # - Calculate available budget
        # - Check if invoice amount fits within budget
        # - Update budget spent/committed amounts
        
        budget_available = True
        budget_warnings = []
        
        # Update invoice state
        invoice["state"] = "BUDGET_CHECKED"
        invoice["budget_available"] = budget_available
        invoice["budget_warnings"] = budget_warnings
        
        self.update_invoice(invoice)
        
        return {
            "invoice_id": invoice_id,
            "department_id": department_id,
            "event_type": "BudgetAgentGenerated",
            "state": InvoiceState.BUDGET_CHECKED.value,
            "budget_available": budget_available,
            "budget_warnings": budget_warnings,
        }
    
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

