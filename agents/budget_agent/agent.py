"""
Budget Agent - Tracks and validates budget allocations.
"""

from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent
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
    
    def __init__(self):
        super().__init__(
            agent_name="BudgetAgent",
            subscription_name=SubscriptionNames.BUDGET_AGENT
        )
    
    def process_invoice(self, invoice_id: str, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check budget availability for invoice.
        
        Args:
            invoice_id: Invoice ID
            message_data: Message payload
            
        Returns:
            Result data for next state
        """
        self.logger.info(f"Checking budget for invoice {invoice_id}")
        
        # Get invoice from storage
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
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
            "state": "BUDGET_CHECKED",
            "budget_available": budget_available,
            "budget_warnings": budget_warnings,
        }
    
    def get_next_subject(self) -> str:
        """Return the next message subject."""
        return InvoiceSubjects.BUDGET_CHECKED


if __name__ == "__main__":
    agent = BudgetAgent()
    agent.initialize()
    agent.run()
