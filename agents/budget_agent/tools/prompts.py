
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage


class BudgetAgentsPrompts:
    BUDGET_CLASSIFICATION_SYSTEM_PROMPT = """
You are a Budget Classification Agent for invoice processing. Your job is to classify invoices into the correct department and spending category based on the invoice details.

**Your Task:**
Analyze the invoice and determine:
1. **Department**: Which department should be charged (IT, HR, FIN, MKT, OPS)
2. **Category**: What type of expense (Software, Hardware, Consulting, Travel, Marketing, Supplies, Training)

**Input Information:**
- Invoice description
- Vendor name
- Amount

**Classification Guidelines:**
- Software licenses/subscriptions → IT/Software
- Hardware equipment → IT/Hardware or OPERATIONS/Equipment
- Professional services → Department requesting service/Services
- Office supplies → OPERATIONS/Supplies
- Travel expenses → Department traveling/Travel
- Employee benefits → HR/Benefits
- Consulting fees → Department using consultant/Services

**Output Format:**
{
    "department": 'department_id',
    "category": 'category',
    "confidence": 'confidence_score_between_0_and_1',
    "reasoning": "Brief explanation of classification"
}

**Important:** Only classify based on invoice content. Do not check budget availability - that's handled by the Budget Agent.
"""
    @staticmethod
    def build_budget_classification_prompt(context: dict, category: str, department: str) -> str:
        """Generate a prompt for classifying an invoice."""

        user_message = f"""
Classify this invoice:

**Invoice Details:**
{context}

**Current Classification (if any):**
- Department: {department}
- Category: {category}
Provide your classification in string with JSON format.
"""
        return [
            SystemMessage(content=BudgetAgentsPrompts.BUDGET_CLASSIFICATION_SYSTEM_PROMPT),
            HumanMessage(content=user_message)
        ]
    

    BUDGET_RISK_ASSESSMENT_SYSTEM_PROMPT = """
You are a Budget Risk Assessment Agent for invoice processing. Your job is to assess the risk level associated with processing an invoice based on its details.

**Output Format:**
{
    
    "projected_total": 105000.00,
    "projected_overrun": 5000.00,
    "confidence_interval": [100000, 110000],
    "expected_exhaustion_date": "2024-11-15"    
}
"""
    @staticmethod
    def build_budget_risk_assessment_prompt(context: dict, department_id: str, category: str, budget_year: str) -> str:
        """Generate a prompt for assessing budget risk for an invoice."""

        user_message = f"""
Assess the budget risk for the following invoice:

**Invoice Details:**
{context}
**Department ID:** {department_id}
**Category:** {category}
**Budget Year:** {budget_year}

Provide your risk assessment in string with JSON format.
"""
        return [
            SystemMessage(content=BudgetAgentsPrompts.BUDGET_RISK_ASSESSMENT_SYSTEM_PROMPT),
            HumanMessage(content=user_message)
        ]