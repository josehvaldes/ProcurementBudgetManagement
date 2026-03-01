
import json
from typing import TypedDict
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import AIMessage

from agents.budget_agent.tools.prompts import BudgetAgentsPrompts
from invoice_lifecycle_api.application.interfaces.service_interfaces import CompareOperator
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager

from shared.config.settings import settings
from shared.models.invoice import InvoiceState
from shared.utils.constants import CompoundKeyStructure
from shared.utils.logging_config import get_logger

logger = get_logger(__name__)

class BudgetAnalyticsOutcome(TypedDict):
    explanation: str
    confidence_score: float
    outcomes: dict

    def __init__(self, explanation: str, confidence_score: float, outcomes: dict):
        self.explanation = explanation
        self.confidence_score = confidence_score
        self.outcomes = outcomes

async def get_invoices_by_vendor(vendor_name: str, months: int = 12) -> list:
    """
    Fetch invoices by vendor from Table Storage.
    Inputs:
        vendor_name: Vendor Name
        months: Number of months of historical data to retrieve
    Returns a list of invoices.
    """
    invoice_table: TableStorageService
    async with TableStorageService(
        storage_account_url=settings.table_storage_account_url,
        table_name=settings.invoices_table_name
    ) as invoice_table:
        
        invoices = []
        logger.info(f"Fetching invoices for Vendor Name: {vendor_name}, Months: {months}")
        filters = [("vendor_name", vendor_name, CompareOperator.EQUAL.value), 
                   ("state", InvoiceState.FAILED.value, CompareOperator.NOT_EQUAL.value)]
        data = await invoice_table.query_entities_with_filters(
            filters=filters
        )
        # get data from awaited data
        if data:
            #order by invoice date descending
            data = sorted(data, key=lambda x: x.get("invoice_date", ""), reverse=True)
            #limit to months
            invoices.extend(data[:months])
            logger.info(f"Fetched {len(data)} invoices for Vendor Name: {vendor_name}")
        else:
            logger.warning(f"No invoices found for Vendor Name: {vendor_name}")

        return invoices

async def get_historical_spending_data(department_id: str, category: str, project_id:str, budget_year:int, months: int = 12) -> list:
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


class BudgetAnalyticsAgent:

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

    async def impact_analysis(self, invoice: dict, budget: dict) -> dict:
        messages = BudgetAgentsPrompts.budget_impact_analytics_prompt(
            invoice=invoice, 
            budget=budget
        )

        logger.info("Invoke Impact Analysis")
        impact_result: AIMessage = await self.llm.ainvoke(messages)

        logger.info(f"Impact Analysis Result: {impact_result.content}")
        if not impact_result or not impact_result.content:
            raise ValueError("No response from LLM for budget analytics.")

        return json.loads(impact_result.content)


    async def trend_analysis(self, invoice: dict, budget: dict, historical_spending: list[dict], vendor_invoices: list[dict]) -> dict:
        messages = BudgetAgentsPrompts.budget_trend_analytics_prompt(
            invoice=invoice,
            budget=budget,
            historical_spending=historical_spending,
            vendor_invoices=vendor_invoices
        )
        trend_result: AIMessage = await self.llm.ainvoke(messages)

        if not trend_result or not trend_result.content:
            raise ValueError("No response from LLM for budget trend analytics.")
        
        return json.loads(trend_result.content)

    async def anomaly_detection(self, invoice: dict, budget: dict, historical_spending: list[dict], vendor_invoices: list[dict]) -> dict:
        messages = BudgetAgentsPrompts.anomaly_detection_prompt(
            invoice=invoice,
            budget=budget,
            historical_spending=historical_spending,
            vendor_invoices=vendor_invoices
        )
        anomaly_result: AIMessage = await self.llm.ainvoke(messages)

        if not anomaly_result or not anomaly_result.content:
            raise ValueError("No response from LLM for budget anomaly detection.")
        
        return json.loads(anomaly_result.content)

    async def contextual_analysis(self, context: dict) -> dict:
        context_messages = BudgetAgentsPrompts.contextual_budget_analytics_prompt(
            context=context
        )
        context_result: AIMessage = await self.llm.ainvoke(context_messages)

        if not context_result or not context_result.content:
            raise ValueError("No response from LLM for contextual budget analytics.")

        return json.loads(context_result.content)

    async def ainvoke(self, input:dict) -> BudgetAnalyticsOutcome:
        errors = []
        invoice:dict = input.get("invoice", None)
        if invoice is None:
            errors.append("Invoice information is required for budget analytics.")
        
        budget:dict = input.get("budget", None)
        if budget is None:
            errors.append("Budget information is required for budget analytics.")

        if len(errors) > 0:
            return False, errors, []

        department_id = invoice.get("department_id", "")
        category = invoice.get("category", "")
        project_id = invoice.get("project_id", "")
        budget_year = budget.get("year", "")
        vendor_name=invoice.get("vendor_name", "")
        
        historical_spending = get_historical_spending_data(
            department_id=department_id,
            category=category,
            project_id=project_id,
            budget_year=budget_year,
            months=12 # last 12 months
        )

        vendor_invoices = get_invoices_by_vendor(
            vendor_name=vendor_name,
            months=12 # last 12 months
        )

        impact_result_content = await self.impact_analysis(
            invoice=invoice,
            budget=budget
        )

        trend_result_content = await self.trend_analysis(
            invoice=invoice,
            budget=budget,
            historical_spending=historical_spending,
            vendor_invoices=vendor_invoices
        )

        anomaly_result_content = await self.anomaly_detection(
            invoice=invoice,
            budget=budget,
            historical_spending=historical_spending,
            vendor_invoices=vendor_invoices
        )

        context = {
            "invoice": invoice,
            "budget_impact": impact_result_content,
            "trend_analysis": trend_result_content,
            "anomaly_detection": anomaly_result_content
        }

        logger.info(f"Context for final analytics: {context}")
        context_result_content = await self.contextual_analysis(
            context=context
        )

        logger.info(context_result_content)
        return BudgetAnalyticsOutcome(
            explanation=context_result_content.get("explanation", ""),
            confidence_score=context_result_content.get("confidence", 0.0),
            outcomes = {
                "budget_impact": impact_result_content,
                "trend_analysis": trend_result_content,
                "anomaly_detection": anomaly_result_content
            }
        )