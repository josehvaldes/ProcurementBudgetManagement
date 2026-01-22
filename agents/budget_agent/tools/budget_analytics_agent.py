
import json
import operator
import traceback
from typing import Annotated, Optional, TypedDict
from langsmith import traceable
from langchain.tools import tool
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agents.validation_agent.tools.prompts import ValidationAgentPrompts
from invoice_lifecycle_api.application.interfaces.service_interfaces import JoinOperator
from shared.models.agentic import Metadata, ValidatorAgenticResponse
from shared.models.invoice import Invoice
from shared.models.vendor import Vendor
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager

from shared.config.settings import settings

class BudgetAnalyticsState(TypedDict):
    messages: Annotated[list, operator.add]
    invoice: dict = {}
    budget_year: str = ""


class BudgetAnalyticsOutcome:
    analytics: dict = {}


@tool
@traceable(name="budget_analytics_agent", tags=["ai", "budget"])
async def budget_analytics_tool(state: BudgetAnalyticsState) -> dict:
    """
    Retrieve budget analytics data based on invoice information.
    """
    pass


class BudgetAnalyticsAgent:
    state: BudgetAnalyticsState
    outcome: BudgetAnalyticsOutcome


    def __init__(self):
        self.credential_manager = get_credential_manager()
        token_provider = self.credential_manager.get_openai_token_provider()
        self.model_deployment = settings.azure_openai_deployment_name
        self.llm = AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
                deployment_name=self.model_deployment,
                azure_ad_token_provider=token_provider,
                temperature=0.1
        )
        self.agent = None
        
    async def _get_agent(self):
        agent = create_agent (
                model=self.llm,
                tools=[budget_analytics_tool],
                #system_prompt=ValidationAgentPrompts.SYSTEM_PROMPT,
                state_schema=BudgetAnalyticsState,
        
        )
        return agent

    async def ainvoke(self, input:dict) -> ValidatorAgenticResponse:
        errors = []
        invoice:dict = input.get("invoice", None)
        if invoice is None:
            errors.append("Invoice information is required for budget analytics.")
        
        if len(errors) > 0:
            return False, errors, []