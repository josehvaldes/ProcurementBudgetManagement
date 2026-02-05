
import json
from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel, Field, field_validator

from shared.config.settings import settings
from agents.budget_agent.tools.prompts import BudgetAgentsPrompts
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager

from shared.utils.logging_config import get_logger, setup_logging

setup_logging(log_level=settings.log_level,
                log_file=settings.log_file,
                log_to_console=settings.log_to_console)

logger = get_logger(__name__)

class BudgetClassificationOutcome(BaseModel):
    """Result of budget classification by LLM."""
    department: str = Field(..., description="Classified department ID")
    category: str = Field(..., description="Budget category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    reasoning: str = Field(..., description="Brief explanation of classification")
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError('Confidence must be between 0 and 1')
        return v


class BudgetClassificationAgent:

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


    async def ainvoke(self, input:dict) -> BudgetClassificationOutcome:
        errors = []
        invoice:dict = input.get("invoice", None)
        if invoice is None:
            errors.append("Invoice information is required for validation with vendor.")

        if len(errors) > 0:
            raise ValueError(" ; ".join(errors))

        messages = BudgetAgentsPrompts.build_budget_classification_prompt(
            context=invoice,
            category=invoice.get("category", "Not set"),
            department=invoice.get("department_id", "Not set")
        )
        logger.info("Invoking LLM for budget classification...")
        result = await self.llm.ainvoke(messages)
        if not result or not result.content:
            raise ValueError("No response from LLM for budget classification.")
        logger.info(result.content)
        json_result = json.loads(result.content)
        return BudgetClassificationOutcome(**json_result)