

from datetime import datetime, timezone
import uuid
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.application.interfaces.service_interfaces import CompareOperator, JoinOperator, TableServiceInterface
from shared.models.budget import Budget, BudgetStatus
from shared.utils.constants import CompoundKeyStructure

logger = get_logger(__name__)

class BudgetService:
    def __init__(self, budget_repository: TableServiceInterface):
        self.budget_repository = budget_repository

    async def create_budget(self, budget: Budget) -> None:
        """Create a new budget record in the repository."""

        budget.budget_id = uuid.uuid4().hex[:12]
        budget.compound_key = f"{budget.department_id}:{budget.project_id}:{budget.category}"
        budget.status = BudgetStatus.FROZEN
        budget.created_date = datetime.now(timezone.utc)
        budget.updated_date = datetime.now(timezone.utc)

        await self.budget_repository.upsert_entity(budget.to_dict(),
                                                   partition_key=budget.fiscal_year,
                                                   row_key=budget.compound_key)

    async def get_budget_by_id(self, department_id:str, budget_id: str) -> Budget | None:
        """Get a budget record by its ID."""
        partition_key = department_id
        filters = [("PartitionKey", partition_key, CompareOperator.EQUAL),
                   ("budget_id", budget_id, CompareOperator.EQUAL)]
        budgets = await self.budget_repository.query_entities_with_filters(
            filters=filters,
            join_operator=JoinOperator.AND
        )
        if budgets and len(budgets) > 0:
            return Budget.from_dict(budgets[0]) if budgets else None
        
        return None

    async def get_budget(self, department_id: str, project_id:str, category:str) -> Budget | None:
        """Get a budget record from the repository."""
        compound_key = f"{department_id}:{project_id}:{category}"
        result = await self.budget_repository.get_entity(
            partition_key=department_id, 
            row_key=compound_key
        )
        return Budget.from_dict(result) if result else None

    async def search_budgets(self, department_id: str, category: str) -> list[Budget]:
        """Search budgets by fiscal year."""
        partition_key = department_id
        row_key_filter = f"{department_id}{CompoundKeyStructure.LOWER_BOUND.value}{category}"
        result = await self.budget_repository.query_compound_key(
            partition_key=partition_key,
            row_key_filter=row_key_filter
        )
        return [Budget.from_dict(item) for item in result] if result else []

    async def generate_consumption_report(self, department_id: str, fiscal_year: str) -> dict:
        """Generate a budget consumption report."""
        report = {}
        budgets = await self.search_budgets(department_id, category="")
        #classify by category
        categorized_budgets = {}
        for budget in budgets:
            if budget.status == BudgetStatus.ACTIVE and budget.fiscal_year == fiscal_year:
                categorized_budgets.setdefault(budget.category, []).append(budget)

        for category, category_budgets in categorized_budgets.items():
            # Generate report for each category
            report[category] = {
                "total_budget": sum(budget.allocated_amount for budget in category_budgets),
                "used_budget": sum(budget.consumed_amount for budget in category_budgets),
                "remaining_budget": sum(budget.remaining_amount for budget in category_budgets),
            }

        # Generate report logic here
        report["overall"] = {
            "department_id": department_id,
            "fiscal_year": fiscal_year,
            "total_budget": sum(budget.allocated_amount for budget in budgets),
            "used_budget": sum(budget.consumed_amount for budget in budgets),
            "remaining_budget": sum(budget.remaining_amount for budget in budgets),
        }
        return report