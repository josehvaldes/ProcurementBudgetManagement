

from openai import BaseModel



class Metadata(BaseModel):
    """Metadata common to all agents"""
    id:str = ""
    input_token:int
    output_token:int
    total_token:int


class ValidatorAgenticResponse(BaseModel):
    """Standardized response model for agentic interactions."""
    response: str
    metadata: Metadata
    passed: bool
    recommended_actions: list[str] = []