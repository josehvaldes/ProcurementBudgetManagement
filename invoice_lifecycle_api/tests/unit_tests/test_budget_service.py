import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, Mock, mock_open, patch, MagicMock

import argparse
import asyncio
from datetime import datetime, timezone

import json
import traceback
import uuid

from shared.config.settings import settings
from shared.utils.logging_config import get_logger, setup_logging
from shared.models.invoice import Invoice
from shared.models.budget import Budget
from invoice_lifecycle_api.application.services.budget_service import BudgetService
from invoice_lifecycle_api.application.interfaces.service_interfaces import TableServiceInterface

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)

@pytest.mark.asyncio(scope="class")
class TestBudgetService:
    
    @pytest_asyncio.fixture
    async def mock_budget_repository(self):
        """Create a mock budget repository."""
        mock_repo = AsyncMock(spec=TableServiceInterface)
        return mock_repo
    
    @pytest_asyncio.fixture
    async def budget_service(self, mock_budget_repository):
        """Create a BudgetService instance with mocked dependencies."""
        service = BudgetService(budget_repository=mock_budget_repository)
        return service
    
    @pytest_asyncio.fixture
    async def sample_budget(self):
        """Create a sample budget for testing."""
        budgets_path = "./scripts/data-source/budgets_data.json"
        with open(budgets_path, "r") as f:
            budget_data = json.load(f)

        return budget_data[0]  # Return the first budget record


    @pytest.mark.asyncio
    async def test_get_budget_by_id_success(self, budget_service: BudgetService, mock_budget_repository, sample_budget):
        """Test successfully retrieving a budget by ID."""
        budget_id = "7d818f2b"
        department_id = "IT"
        mock_budget_repository.query_entities_with_filters.return_value = [sample_budget]

        result = await budget_service.get_budget_by_id(department_id, budget_id)
        
        assert result is not None
        assert result.budget_id == budget_id
        mock_budget_repository.query_entities_with_filters.assert_called_once()
        logger.info(f"✓ test_get_budget_by_id_success passed")
    
    @pytest.mark.asyncio
    async def test_get_budget_by_id_not_found(self, budget_service, mock_budget_repository):
        """Test retrieving a non-existent budget."""
        budget_id = "NONEXISTENT"
        department_id = "IT"
        mock_budget_repository.query_entities_with_filters.return_value = []

        result = await budget_service.get_budget_by_id(department_id, budget_id)

        assert result is None
        mock_budget_repository.query_entities_with_filters.assert_called_once()
        logger.info(f"✓ test_get_budget_by_id_not_found passed")
    
    @pytest.mark.asyncio
    async def test_get_budget_with_compound_key(self, budget_service: BudgetService, mock_budget_repository, sample_budget):
        """Test successfully retrieving a budget by compound key."""
        department_id = sample_budget["department_id"]
        project_id = sample_budget["project_id"]
        category = sample_budget["category"]

        mock_budget_repository.get_entity.return_value = sample_budget

        result = await budget_service.get_budget(department_id, project_id, category)
        
        assert result is not None
        assert result.department_id == department_id
        assert result.project_id == project_id
        assert result.category == category
        mock_budget_repository.get_entity.assert_called_once()
        logger.info(f"✓ test_get_budget_with_compound_key passed")


    @pytest.mark.asyncio
    async def test_create_budget(self, budget_service: BudgetService, mock_budget_repository, sample_budget):
        """Test creating a new budget."""
        mock_budget_repository.upsert_entity.return_value = None
        budget = Budget.from_dict(sample_budget)
        await budget_service.create_budget(budget)

        mock_budget_repository.upsert_entity.assert_called_once()
        logger.info(f"✓ test_create_budget passed")
        print(mock_budget_repository.upsert_entity.call_args[0][0])
        assert mock_budget_repository.upsert_entity.call_args[0][0].get("status") == "frozen"
        assert mock_budget_repository.upsert_entity.call_args[0][0].get("budget_id") is not None
        assert mock_budget_repository.upsert_entity.call_args[0][0].get("compound_key") == f"{budget.department_id}:{budget.project_id}:{budget.category}"

    @pytest.mark.asyncio
    async def test_search_budgets(self, budget_service: BudgetService, mock_budget_repository:TableServiceInterface, sample_budget):
        """Test searching budgets by department and category."""
        department_id = sample_budget["department_id"]
        category = sample_budget["category"]

        mock_budget_repository.query_compound_key.return_value = [sample_budget]

        results = await budget_service.search_budgets(department_id, category)

        assert len(results) == 1
        assert results[0].department_id == department_id
        assert results[0].category == category
        mock_budget_repository.query_compound_key.assert_called_once()
        logger.info(f"✓ test_search_budgets passed")


    @pytest.mark.asyncio
    async def test_generate_consumption_report(self, budget_service: BudgetService, 
                                               mock_budget_repository:TableServiceInterface):
        
        """Test generating a budget consumption report."""
        department_id = "IT"
        fiscal_year = "FY2026"

        budgets_path = "./scripts/data-source/budgets_data.json"
        with open(budgets_path, "r") as f:
            budget_data = json.load(f)


        mock_budget_repository.query_compound_key.return_value = [
            item for item in budget_data if item["department_id"] == department_id and item["fiscal_year"] == fiscal_year
        ]

        report = await budget_service.generate_consumption_report(department_id, fiscal_year)

        logger.info(f"Consumption Report: {report}")
        
        assert report is not None
        mock_budget_repository.query_compound_key.assert_called_once()
        logger.info(f"✓ test_generate_consumption_report passed")