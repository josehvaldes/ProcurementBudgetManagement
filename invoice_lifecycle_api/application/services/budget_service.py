from datetime import datetime, timezone
from typing import Optional
import uuid

from shared.utils.exceptions import BudgetCreationException, BudgetRetrievalException, BudgetValidationException
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.application.interfaces.service_interfaces import CompareOperator, JoinOperator, TableServiceInterface
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import EntityQueryException
from shared.models.budget import Budget, BudgetStatus
from shared.utils.constants import CompoundKeyStructure

logger = get_logger(__name__)



class BudgetService:
    """
    Service for managing budget operations.
    
    This service handles:
    - Creating budget records
    - Retrieving budgets by ID or composite key
    - Searching budgets by department and category
    - Generating budget consumption reports
    
    Attributes:
        budget_repository (TableServiceInterface): Repository for budget persistence
    """
    
    def __init__(self, budget_repository: TableServiceInterface):
        """
        Initialize budget service.
        
        Args:
            budget_repository: Table storage repository for budget entities
        """
        self.budget_repository = budget_repository
        
        logger.info(
            "Budget service initialized",
            extra={"repository_type": type(budget_repository).__name__}
        )

    async def create_budget(self, budget: Budget) -> str:
        """
        Create a new budget record in the repository.
        
        Args:
            budget: Budget entity to create
            
        Returns:
            budget_id: The generated budget ID
            
        Raises:
            BudgetValidationException: If required budget fields are missing or invalid
            BudgetCreationException: If budget creation fails
            
        Example:
            budget = Budget(
                department_id="DEPT-001",
                project_id="PROJ-123",
                category="OFFICE_SUPPLIES",
                fiscal_year="FY2024",
                allocated_amount=50000.0
            )
            budget_id = await service.create_budget(budget)
        """
        # Validate required fields
        validation_errors = []
        
        if not budget.department_id:
            validation_errors.append("department_id is required")
        if not budget.project_id:
            validation_errors.append("project_id is required")
        if not budget.category:
            validation_errors.append("category is required")
        if not budget.fiscal_year:
            validation_errors.append("fiscal_year is required")
        if budget.allocated_amount is None or budget.allocated_amount < 0:
            validation_errors.append("allocated_amount must be a positive number")
            
        if validation_errors:
            error_msg = f"Budget validation failed: {'; '.join(validation_errors)}"
            logger.error(
                "Budget validation failed",
                extra={
                    "department_id": budget.department_id,
                    "validation_errors": validation_errors,
                    "error_type": "BudgetValidationFailed"
                }
            )
            raise BudgetValidationException(error_msg)

        # Generate budget ID and compound key
        budget.budget_id = uuid.uuid4().hex[:12]
        budget.compound_key = f"{budget.department_id}:{budget.project_id}:{budget.category}"
        budget.status = BudgetStatus.FROZEN
        budget.created_date = datetime.now(timezone.utc)
        budget.updated_date = datetime.now(timezone.utc)

        logger.info(
            "Creating budget",
            extra={
                "budget_id": budget.budget_id,
                "department_id": budget.department_id,
                "project_id": budget.project_id,
                "category": budget.category,
                "fiscal_year": budget.fiscal_year,
                "allocated_amount": budget.allocated_amount
            }
        )

        try:
            await self.budget_repository.upsert_entity(
                budget.to_dict(),
                partition_key=budget.fiscal_year,
                row_key=budget.compound_key
            )
            
            logger.info(
                "Budget created successfully",
                extra={
                    "budget_id": budget.budget_id,
                    "department_id": budget.department_id,
                    "fiscal_year": budget.fiscal_year,
                    "compound_key": budget.compound_key
                }
            )
            
            return budget.budget_id
            
        except Exception as e:
            logger.error(
                "Failed to create budget",
                extra={
                    "budget_id": budget.budget_id,
                    "department_id": budget.department_id,
                    "fiscal_year": budget.fiscal_year,
                    "error_type": "BudgetCreationFailed",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise BudgetCreationException(
                f"Failed to create budget for department {budget.department_id}: {str(e)}"
            ) from e

    async def get_budget_by_id(self, department_id: str, budget_id: str) -> Optional[Budget]:
        """
        Get a budget record by its ID.
        
        Args:
            department_id: Department identifier
            budget_id: Budget identifier
            
        Returns:
            Budget entity if found, None otherwise
            
        Raises:
            BudgetRetrievalException: If budget retrieval fails
        """

        logger.info(
            "Retrieving budget by ID",
            extra={
                "department_id": department_id,
                "budget_id": budget_id
            }
        )

        try:
            filters = [
                ("PartitionKey", department_id, CompareOperator.EQUAL.value),
                ("budget_id", budget_id, CompareOperator.EQUAL.value)
            ]
            
            budgets = await self.budget_repository.query_entities_with_filters(
                filters=filters,
                join_operator=JoinOperator.AND
            )
            
            if budgets and len(budgets) > 0:
                logger.info(
                    "Budget found by ID",
                    extra={
                        "department_id": department_id,
                        "budget_id": budget_id,
                        "fiscal_year": budgets[0].get("fiscal_year"),
                        "category": budgets[0].get("category")
                    }
                )
                return Budget.from_dict(budgets[0])
            
            logger.info(
                "Budget not found by ID",
                extra={
                    "department_id": department_id,
                    "budget_id": budget_id
                }
            )
            return None
            
        except EntityQueryException as e:
            logger.error(
                "Failed to retrieve budget by ID",
                extra={
                    "department_id": department_id,
                    "budget_id": budget_id,
                    "error_type": "BudgetRetrievalFailed",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise BudgetRetrievalException(
                f"Failed to retrieve budget {budget_id} for department {department_id}: {str(e)}"
            ) from e
            
        except Exception as e:
            logger.error(
                "Unexpected error retrieving budget by ID",
                extra={
                    "department_id": department_id,
                    "budget_id": budget_id,
                    "error_type": "UnexpectedRetrievalError",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise BudgetRetrievalException(
                f"Unexpected error retrieving budget {budget_id}: {str(e)}"
            ) from e

    async def get_budget(
        self, 
        department_id: str, 
        project_id: str, 
        category: str
    ) -> Optional[Budget]:
        """
        Get a budget record by composite key.
        
        Args:
            department_id: Department identifier
            project_id: Project identifier
            category: Budget category
            
        Returns:
            Budget entity if found, None otherwise
        Raises:
            BudgetRetrievalException: If budget retrieval fails
        """

        compound_key = f"{department_id}:{project_id}:{category}"
        
        logger.info(
            "Retrieving budget by composite key",
            extra={
                "department_id": department_id,
                "project_id": project_id,
                "category": category,
                "compound_key": compound_key
            }
        )

        try:
            result = await self.budget_repository.get_entity(
                partition_key=department_id,
                row_key=compound_key
            )
            
            if result:
                logger.info(
                    "Budget found by composite key",
                    extra={
                        "department_id": department_id,
                        "project_id": project_id,
                        "category": category,
                        "budget_id": result.get("budget_id")
                    }
                )
                return Budget.from_dict(result)
            
            logger.info(
                "Budget not found by composite key",
                extra={
                    "department_id": department_id,
                    "project_id": project_id,
                    "category": category
                }
            )
            return None
            
        except Exception as e:
            logger.error(
                "Failed to retrieve budget by composite key",
                extra={
                    "department_id": department_id,
                    "project_id": project_id,
                    "category": category,
                    "compound_key": compound_key,
                    "error_type": "BudgetRetrievalFailed",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise BudgetRetrievalException(
                f"Failed to retrieve budget for {compound_key}: {str(e)}"
            ) from e

    async def search_budgets(self, department_id: str, category: str = "") -> list[Budget]:
        """
        Search budgets by department and optional category.
        
        Args:
            department_id: Department identifier
            category: Budget category filter (empty string for all categories)
            
        Returns:
            List of Budget entities (empty list if none found)
            
        Raises:
            BudgetRetrievalException: If budget search fails
        """

        partition_key = department_id
        row_key_filter = f"{department_id}{CompoundKeyStructure.LOWER_BOUND.value}{category}"
        
        logger.info(
            "Searching budgets",
            extra={
                "department_id": department_id,
                "category_filter": category or "all",
                "row_key_filter": row_key_filter
            }
        )

        try:
            result = await self.budget_repository.query_compound_key(
                partition_key=partition_key,
                row_key=row_key_filter
            )
            
            budgets = [Budget.from_dict(item) for item in result] if result else []
            
            logger.info(
                f"Budget search completed: {len(budgets)} budgets found",
                extra={
                    "department_id": department_id,
                    "category_filter": category or "all",
                    "result_count": len(budgets)
                }
            )
            
            return budgets
            
        except EntityQueryException as e:
            logger.error(
                "Failed to search budgets",
                extra={
                    "department_id": department_id,
                    "category_filter": category or "all",
                    "error_type": "BudgetSearchFailed",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise BudgetRetrievalException(
                f"Failed to search budgets for department {department_id}: {str(e)}"
            ) from e
            
        except Exception as e:
            logger.error(
                "Unexpected error searching budgets",
                extra={
                    "department_id": department_id,
                    "category_filter": category or "all",
                    "error_type": "UnexpectedSearchError",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise BudgetRetrievalException(
                f"Unexpected error searching budgets for department {department_id}: {str(e)}"
            ) from e

    async def generate_consumption_report(self, department_id: str, fiscal_year: str) -> dict:
        """
        Generate a budget consumption report for a department and fiscal year.
        
        Args:
            department_id: Department identifier
            fiscal_year: Fiscal year for the report
            
        Returns:
            Dictionary containing consumption report with:
                - Category-level breakdown (total, used, remaining budgets)
                - Overall department summary
                
        Raises:
            BudgetRetrievalException: If report generation fails
            
        Example:
            report = await service.generate_consumption_report("DEPT-001", "FY2024")
            # {
            #     "OFFICE_SUPPLIES": {
            #         "total_budget": 50000.0,
            #         "used_budget": 25000.0,
            #         "remaining_budget": 25000.0
            #     },
            #     "overall": {
            #         "department_id": "DEPT-001",
            #         "fiscal_year": "FY2024",
            #         "total_budget": 200000.0,
            #         "used_budget": 75000.0,
            #         "remaining_budget": 125000.0
            #     }
            # }
        """

        logger.info(
            "Generating budget consumption report",
            extra={
                "department_id": department_id,
                "fiscal_year": fiscal_year
            }
        )

        try:
            # Retrieve all budgets for the department
            budgets = await self.search_budgets(department_id, category="")
            
            # Filter active budgets for the specified fiscal year
            active_budgets = [
                budget for budget in budgets
                if budget.status == BudgetStatus.ACTIVE and budget.fiscal_year == fiscal_year
            ]
            
            logger.info(
                f"Processing {len(active_budgets)} active budgets for report",
                extra={
                    "department_id": department_id,
                    "fiscal_year": fiscal_year,
                    "total_budgets": len(budgets),
                    "active_budgets": len(active_budgets)
                }
            )
            
            # Categorize budgets by category
            categorized_budgets = {}
            for budget in active_budgets:
                categorized_budgets.setdefault(budget.category, []).append(budget)

            # Generate category-level reports
            report = {}
            for category, category_budgets in categorized_budgets.items():
                report[category] = {
                    "total_budget": sum(budget.allocated_amount for budget in category_budgets),
                    "used_budget": sum(budget.consumed_amount for budget in category_budgets),
                    "remaining_budget": sum(budget.remaining_amount for budget in category_budgets),
                }

            # Generate overall summary
            report["overall"] = {
                "department_id": department_id,
                "fiscal_year": fiscal_year,
                "total_budget": sum(budget.allocated_amount for budget in active_budgets),
                "used_budget": sum(budget.consumed_amount for budget in active_budgets),
                "remaining_budget": sum(budget.remaining_amount for budget in active_budgets),
            }
            
            logger.info(
                "Budget consumption report generated successfully",
                extra={
                    "department_id": department_id,
                    "fiscal_year": fiscal_year,
                    "categories_count": len(categorized_budgets),
                    "total_budget": report["overall"]["total_budget"],
                    "used_budget": report["overall"]["used_budget"],
                    "remaining_budget": report["overall"]["remaining_budget"]
                }
            )
            
            return report
            
        except (BudgetValidationException, BudgetRetrievalException):
            # Re-raise budget-specific exceptions
            raise
            
        except Exception as e:
            logger.error(
                "Failed to generate budget consumption report",
                extra={
                    "department_id": department_id,
                    "fiscal_year": fiscal_year,
                    "error_type": "ReportGenerationFailed",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise BudgetRetrievalException(
                f"Failed to generate consumption report for department {department_id}, fiscal year {fiscal_year}: {str(e)}"
            ) from e