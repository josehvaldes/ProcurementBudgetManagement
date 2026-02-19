from typing import Any

import json
from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel, Field

from shared.config.settings import settings
from agents.approval_agent.tools.prompts import ApprovalAgentPrompts
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from shared.utils.exceptions import FileLoadException
from shared.utils.logging_config import get_logger, setup_logging

setup_logging(log_level=settings.log_level,
                log_file=settings.log_file,
                log_to_console=settings.log_to_console)

logger = get_logger(__name__)

class ApprovalAnalyticsOutcome(BaseModel):
    risk_level: str = Field(..., description="Risk level of the invoice (e.g., low, medium, high)")
    risk_factors: list[str] = Field(..., description="List of identified risk factors")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Overall risk score between 0 and 1")
    reasoning: str = Field(..., description="Brief explanation of the risk assessment")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of the analysis between 0 and 1")
    suggested_approver: str = Field(..., description="AI-suggested approver for the invoice")

class ApprovalAnalyticsAgent:
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
    
    async def invoke(self, input: dict) -> ApprovalAnalyticsOutcome:
        invoice:dict = input.get("invoice", None)
        budget:dict = input.get("budget", None)
        vendor:dict = input.get("vendor", None)
        
        try:

            errors = []
            if invoice is None:
                errors.append("Invoice information is required for approval analytics.")
            if budget is None:
                errors.append("Budget information is required for approval analytics.")
            if vendor is None:
                errors.append("Vendor information is required for approval analytics.")

            if errors:
                logger.error(f"Approval analytics invocation failed: {errors}")
                raise ValueError(" ; ".join(errors))

            # load approval policy from yaml file
            approval_policy = None
            try:
                with open("agents/approval_agent/tools/approval_policy.yaml", "r") as f:
                    approval_policy = f.read()
            except Exception as e:
                logger.error(f"Failed to load approval policy: {e}")
                errors.append("Unable to load approval policy for analytics.")
                raise FileLoadException("Failed to load approval policy")

            messages = ApprovalAgentPrompts.build_approval_decision_prompt(
                invoice=invoice,
                budget=budget,
                vendor=vendor,
                approval_policy=approval_policy
            )

            # Call the LLM with the constructed messages
            response = await self.llm(messages)
            if not response or not response.content:
                logger.error("No response from LLM for approval analytics.")
                raise ValueError("No response from LLM for approval analytics.")

            # Process the LLM response and extract relevant information
            outcome = json.loads(response.content)
            return ApprovalAnalyticsOutcome(**outcome)

        except Exception as e:
            logger.error(f"Approval analytics invocation failed: {e}")
            raise