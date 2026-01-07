
import json
from typing import Optional
from langsmith import traceable
from langchain.tools import tool
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agents.validation_agent.tools.prompts import ValidationAgentPrompts
from shared.models.invoice import Invoice
from shared.models.vendor import Vendor
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager

from shared.config.settings import settings

class ValidationAgentState:
    vendor: Vendor
    invoice: Invoice
    k_limit: int = 5

class AgentDecisionOutcome:
    validation_passed: bool
    state:str
    vendor_matched: bool
    validation_flags: Optional[list[str]]
    confidence_score: Optional[float]
    reasoning: Optional[str]
    recommended_actions: Optional[list[str]]

@tool
@traceable(name="search_vendors_by_name", tags=["ai", "vendor"])
async def search_vendors_by_name(vendor_name: str) -> list[dict]:
    """Search for vendors by name in the vendor table."""

    vendor_table_client: TableStorageService
    with TableStorageService(storage_account_url=settings.table_storage_account_url,
                                 table_name=settings.vendors_table_name) as vendor_table_client:    
        filters_query = [("name", vendor_name)]
        vendor_entities = await vendor_table_client.query_entities(filters_query=filters_query)
        
        return vendor_entities

@tool
@traceable(name="get_invoices_by_vendor", tags=["ai", "invoice"])
async def get_invoices_by_vendor(state: ValidationAgentState) -> list[dict]:
    """Retrieve invoices by vendor name and invoice number."""
    
    invoice_table_client: TableStorageService
    with TableStorageService(storage_account_url=settings.table_storage_account_url,
                                 table_name=settings.invoices_table_name) as invoice_table_client:
        invoice_number = state.invoice.invoice_number
        vendor_name = state.vendor.name

        filters_query = [("invoice_number", invoice_number), ("vendor_name", vendor_name)]
        invoice_entities = await invoice_table_client.query_entities(filters_query=filters_query)

        # order by created_date descending
        sorted_invoices = sorted(invoice_entities, key=lambda x: x.get("created_date", 0), reverse=True)
        return sorted_invoices[:state.k_limit]


class AgenticValidator:
    def __init__(self):
        credential_manager = get_credential_manager()
        token_provider = credential_manager.get_openai_token_provider()
        self.model_deployment = settings.azure_openai_deployment_name
        self.llm = AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
                deployment_name=self.model_deployment,
                azure_ad_token_provider=token_provider,
                temperature=0
        )
        self.agent = None
        
    async def _get_agent(self):
        agent = create_agent (
                model=self.llm,
                tools=[get_invoices_by_vendor,
                          #search_vendors_by_name
                       ],
                system_prompt= ValidationAgentPrompts.SYSTEM_PROMPT,
                state_schema=ValidationAgentState,

            )
        return agent

    async def ainvoke(self, input:dict) -> tuple[bool, list[str], list[str]]:
        """
        Validate invoice with vendor information using AI model.
        Append any errors or warnings to the provided lists.
        input: {"vendor": dict, "invoice": dict}

        """
        errors = []

        vendor:dict = input.get("vendor", None)
        if vendor is None:
            errors.append("Vendor information is required for validation with vendor.")

        invoice:dict = input.get("invoice", None)
        if invoice is None:
            errors.append("Invoice information is required for validation with vendor.")

        if len(errors) > 0:
            return False, errors, []
        
        try:
            
            if self.agent is None:
                self.agent = await self._get_agent()

            result = await self.agent.ainvoke({
                "messages": [HumanMessage(content=f"vendor: {json.dumps(vendor)} \n\n invoice: {json.dumps(invoice)}")]
            })

            messages = result["messages"]
            response = messages[-1].content

            sum_input_tokens = 0
            sum_output_tokens = 0
            sum_total_tokens = 0

            for msg in messages:
                if isinstance(msg, ToolMessage):
                    # Handle tool messages
                    pass
                if isinstance(msg, AIMessage):
                    metadata = msg.usage_metadata
                    if metadata:
                        sum_input_tokens += metadata.get("input_tokens") or 0
                        sum_output_tokens += metadata.get("output_tokens") or 0
                        sum_total_tokens += metadata.get("total_tokens") or 0

            response_dict = json.loads(response)
            response_obj = AgentDecisionOutcome(**response_dict)

            
            passed = response_obj.validation_passed and response_obj.vendor_matched
            recommended_actions = response_obj.recommended_actions or []

            return not passed, errors, recommended_actions
        
        except Exception as e:
                errors.append(f"Error during AI validation: {e}")
                return False, errors, []

    def validate_without_vendor(self, invoice_data: Invoice) -> tuple[bool, list[str], list[str]]:
        """
        Validate invoice without vendor information using AI model.
        Append any errors or warnings to the provided lists.
        """
        # Implement AI validation logic here
        ai_response = self.ai_model_client.validate(invoice_data, without_vendor=True)

        errors = []
        warnings = []

        for issue in ai_response.issues:
            if issue.severity == "error":
                errors.append(issue.message)
            elif issue.severity == "warning":
                warnings.append(issue.message)

        return not errors, errors, warnings