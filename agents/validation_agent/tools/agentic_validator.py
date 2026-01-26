
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

class ValidationAgentState(TypedDict):
    messages: Annotated[list, operator.add]
    vendor: dict = {}
    invoice: dict = {}
    k_limit: int = 5

class AgentDecisionOutcome:
    validation_passed: bool = False
    state:str = ""
    vendor_matched: bool = False
    confidence_score: Optional[float] = None
    reasoning: Optional[str] = None
    recommended_actions: Optional[list[str]] = None


@tool
@traceable(name="get_invoices_by_vendor", tags=["ai", "invoice"])
async def get_invoices_by_vendor(state: ValidationAgentState) -> list[dict]:
    """
    Fetch invoices from Table Storage based on vendor information.
    Returns a list of invoice entities matching the vendor name and invoice number.
    """
    print("Fetching invoices by vendor...")
    invoice_number = state.invoice["invoice_number"]
    vendor_name = state.vendor["name"]
    print(f"Fetching invoices for vendor: {vendor_name}, invoice number: {invoice_number}")

    invoice_table_client: TableStorageService
    with TableStorageService(storage_account_url=settings.table_storage_account_url,
                                 table_name=settings.invoices_table_name) as invoice_table_client:
        filters_query = [("invoice_number", invoice_number), ("vendor_name", vendor_name)]
        invoice_entities = await invoice_table_client.query_entities(filters_query=filters_query, 
                                                                     join_operator=JoinOperator.OR)

        # order by created_date descending
        sorted_invoices = sorted(invoice_entities, key=lambda x: x.get("created_date", 0), reverse=True)
        print(f"Found {len(sorted_invoices)} invoices for vendor: {vendor_name}, invoice number: {invoice_number}")
        return sorted_invoices[:state.k_limit]

class AgenticValidator:
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
                tools=[get_invoices_by_vendor],
                system_prompt=ValidationAgentPrompts.SYSTEM_PROMPT,
                state_schema=ValidationAgentState,

            )
        return agent

    async def ainvoke(self, input:dict) -> ValidatorAgenticResponse:
        """
        Validate invoice with vendor information using AI model.
        Append any errors or warnings to the provided lists.
        input: {"vendor": dict, "invoice": dict}

        """
        errors = []
        print("Starting AI validation with vendor information...")

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

            print("Invoking agent for validation...")
            result = await self.agent.ainvoke({
                "messages": [HumanMessage(content=f"vendor: {vendor} \n\n invoice: {invoice}")]
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
            print(f"Response Dict: {response_dict}")

            agentic_response = ValidatorAgenticResponse(
                passed=response_dict["validation_passed"] and response_dict["vendor_matched"],
                response=response,
                recommended_actions=response_dict.get("recommended_actions", []),
                metadata=Metadata(
                    id="",
                    input_token=sum_input_tokens,
                    output_token=sum_output_tokens,
                    total_token=sum_total_tokens
                )
            )

            return agentic_response
        
        except Exception as e:
                errors.append(f"Error during AI validation: {e}")   
                traceback.print_exc()             
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