
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
from shared.models.constants import DEPARTMENT_CATEGORIES, DEPARTMENT_IDS
from shared.models.invoice import Invoice
from shared.models.vendor import Vendor
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager

from shared.config.settings import settings

class BudgetClassificationState(TypedDict):
    messages: Annotated[list, operator.add]
    invoice: dict = {}
    budget_year: str
    categories: list[str]
    departments: list[str]

class BudgetClassificationOutcome:
    vendor: dict = {}

@tool
@traceable(name="budget_classification_agent", tags=["ai", "budget"])
async def budget_classification_tool(state: BudgetClassificationState) -> dict:
    """
    Classify invoice into budget categories based on invoice data.
    """
    pass

class BudgetClassificationAgent:
    state: BudgetClassificationState
    outcome: BudgetClassificationOutcome


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
        self.agent = self._get_agent()

    async def _get_agent(self):
        agent = create_agent (
                model=self.llm,
                tools=[budget_classification_tool],
                #system_prompt=ValidationAgentPrompts.SYSTEM_PROMPT,
                state_schema=BudgetClassificationState,

            )
        return agent

    async def ainvoke(self, input:dict) -> BudgetClassificationOutcome:
        errors = []
        invoice:dict = input.get("invoice", None)
        if invoice is None:
            errors.append("Invoice information is required for validation with vendor.")

        if len(errors) > 0:
            return False, errors, []

        departments = [dept for dept in DEPARTMENT_IDS]
        categories = [category for category in DEPARTMENT_CATEGORIES]

        if self.agent is None:
            self.agent = await self._get_agent()

        print("Invoking agent for validation...")
        result = await self.agent.ainvoke({
            "messages": [HumanMessage(content=f"invoice: {invoice} \n\n departments: {departments} \n\n categories: {categories}")]
        })

        messages = result["messages"]
        response = messages[-1].content
        sum_input_tokens = 0
        sum_output_tokens = 0
        sum_total_tokens = 0

        for msg in messages:
            if isinstance(msg, AIMessage):
                metadata = msg.usage_metadata
                if metadata:
                    sum_input_tokens += metadata.get("input_tokens") or 0
                    sum_output_tokens += metadata.get("output_tokens") or 0
                    sum_total_tokens += metadata.get("total_tokens") or 0

        response_dict = json.loads(response)
        print(f"Response Dict: {response_dict}")
        return BudgetClassificationOutcome(
            vendor=response_dict.get("vendor", {}),
            invoice=response_dict.get("invoice", {})
        )