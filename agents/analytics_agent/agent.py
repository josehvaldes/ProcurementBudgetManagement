"""
Analytics Agent - Analyzes spending patterns and generates insights.
"""

from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent
from shared.utils.constants import SubscriptionNames


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
    
    def __init__(self):
        super().__init__(
            agent_name="AnalyticsAgent",
            subscription_name=SubscriptionNames.ANALYTICS_AGENT
        )
    
    def process_invoice(self, invoice_id: str, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze invoice for spending patterns and insights.
        
        Args:
            invoice_id: Invoice ID
            message_data: Message payload
            
        Returns:
            None (analytics agent doesn't trigger next state)
        """
        self.logger.info(f"Analyzing invoice {invoice_id}")
        
        # Get invoice from storage
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            self.logger.warning(f"Invoice {invoice_id} not found")
            return None
        
        # TODO: Implement analytics logic
        # - Track spending by department
        # - Compare to historical data
        # - Identify anomalies
        # - Generate insights
        # - Update analytics tables/metrics
        
        state = invoice.get("state")
        self.logger.info(f"Invoice {invoice_id} in state {state} - analytics recorded")
        
        # Analytics agent doesn't publish next state
        return None
    
    def get_next_subject(self) -> str:
        """Analytics agent doesn't publish next state."""
        return None


if __name__ == "__main__":
    agent = AnalyticsAgent()
    agent.initialize()
    agent.run()
