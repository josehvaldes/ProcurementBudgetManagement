
import json
import operator
import traceback
from typing import Annotated, Optional, TypedDict
from langsmith import traceable
from langchain.tools import tool
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agents.budget_agent.tools.prompts import BudgetAgentsPrompts
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager

from shared.config.settings import settings
from shared.utils.constants import CompoundKeyStructure
from shared.utils.logging_config import get_logger

logger = get_logger(__name__)

class BudgetAnalyticsState(TypedDict):
    messages: Annotated[list, operator.add]
    invoice: dict = {}
    category: str = ""
    department_id: str = ""
    budget_year: str = ""


class BudgetAnalyticsOutcome:
    analytics: dict = {}

@tool
async def get_historical_spending_data(department_id: str, category: str, project_id:str, budget_year:int, months: int = 12):
    """
    Fetch historical spending data from Table Storage based on department, category, project, and budget year.
    Inputs:
        department_id: Department Identifier
        category: Budget Category
        project_id: Project Identifier
        budget_year: Budget Year (e.g., 2024)
        months: Number of months of historical data to retrieve
    Returns a list of historical spending records.
    """

    lower = CompoundKeyStructure.LOWER_BOUND.value
    budget_table: TableStorageService
    async with TableStorageService(
        storage_account_url=settings.table_storage_account_url,
        table_name=settings.budget_analytics_table_name
    ) as budget_table:
        
        completed = False
        historical_spending = []
        row_key = f"{department_id}{lower}{category}{lower}{project_id}"
        logger.info(f"Fetching historical spending data for Department: {department_id}, Category: {category}, Project: {project_id}, Budget Year: {budget_year}, Months: {months}")
        while not completed and len(historical_spending) < months:

            partition_key = f"FY{budget_year}"
            logger.info(f"Querying budget table with Partition Key: {partition_key}, Row Key: {row_key}")
            data = await budget_table.query_compound_key(
                partition_key=partition_key,
                row_key=row_key
            )
            # get data from awaited data
            if data:
                historical_spending.extend([{
                    "month": item.get("month"),
                    "year": item.get("year"),
                    "avg_invoice_amount": item.get("avg_invoice_amount", 0),
                    "total_spent": item.get("total_spent", 0),
                } for item in data]
                )
                logger.info(f"Fetched historical spending data: {len(data)} records for Partition Key: {partition_key}, Row Key: {row_key}")
                if len(historical_spending) < months:
                    # fetch more data if available
                    budget_year = budget_year - 1
                    completed = False
            else:
                logger.warning(f"No data found for Partition Key: {partition_key}, Row Key: {row_key}")
                completed = True

        # Process data to get historical and current year spending
        return historical_spending


async def calculate_budget_utilization_tool(department_id:str, category:str, budget_year:str) -> dict:
    """
    Calculate budget utilization based on invoice information.
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
        self.agent = self._get_agent()
        
    async def _get_agent(self):
        agent = create_agent (
                model=self.llm,
                tools=[get_historiacal_spending_data],
                system_prompt=BudgetAgentsPrompts.BUDGET_RISK_ASSESSMENT_SYSTEM_PROMPT,
                state_schema=BudgetAnalyticsState,
        
        )
        return agent

    async def ainvoke(self, input:dict) -> BudgetAnalyticsOutcome:
        errors = []
        invoice:dict = input.get("invoice", None)
        if invoice is None:
            errors.append("Invoice information is required for budget analytics.")
        
        if len(errors) > 0:
            return False, errors, []

        department_id = invoice.get("department_id", "Not set")
        category = invoice.get("category", "Not set")
        budget_year = input.get("budget_year", "FY2024")

        result = await self.agent.ainvoke({
            "messages": [HumanMessage(content=f"invoice: {invoice} \n\n department_id: {department_id} \n\n category: {category} \n\n budget_year: {budget_year}")]
        })

        response = "__No AI Message__"
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

        return BudgetAnalyticsOutcome()