"""
Application settings and configuration.
"""

import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import find_dotenv
# Find .env file automatically
ENV_FILE = find_dotenv(usecwd=True) or ".env"

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "Procurement & Budget Management"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    
    # Azure Service Bus
    service_bus_connection_string: str = ""
    service_bus_topic_name: str = "invoice-events"
    
    # Azure Storage (Tables)
    storage_connection_string: str = ""
    invoices_table_name: str = "invoices"
    vendors_table_name: str = "vendors"
    budgets_table_name: str = "budgets"
    
    # Azure Document Intelligence
    document_intelligence_endpoint: str = ""
        
    # Azure Blob Storage (for document storage)
    blob_storage_connection_string: str = ""
    blob_container_name: str = "invoice-documents"
    
    # LangChain / LLM
    openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_deployment_name: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # LangSmith
    langsmith_api_key: Optional[str] = None
    langsmith_project: Optional[str] = None
    langsmith_tracing_enabled: bool = False
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    
    # Agent Configuration
    agent_poll_interval_seconds: int = 5
    agent_max_concurrent_messages: int = 10
    
    # Business Rules
    auto_approve_threshold: float = 1000.00  # Auto-approve invoices under this amount
    require_po_match: bool = True
    require_budget_check: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Returns:
        Settings instance
    """
    return Settings()
