"""
Budget API endpoints for managing departmental budgets.

This module provides RESTful API endpoints for creating, retrieving, and 
analyzing budget records across departments and fiscal years.
"""
from datetime import datetime
import traceback
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, validator

from shared.config.settings import settings
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.application.interfaces.service_interfaces import TableServiceInterface
from invoice_lifecycle_api.application.services.budget_service import BudgetService
from shared.models.budget import Budget
from invoice_lifecycle_api.application.interfaces.di_container import get_budget_service

logger = get_logger(__name__)

router = APIRouter(
    responses={
        404: {"description": "Budget not found"},
        500: {"description": "Internal server error"}
    }
)

DEFAULT_USER_NAME: str = "system"


# ==================== Request/Response Models ====================

class BudgetRequestModel(BaseModel):
    """
    Model representing a budget creation request.
    
    This model defines the required and optional fields for creating
    a new budget allocation for a department and fiscal year.
    """
    department_id: str = Field(
        ...,
        description="Unique identifier for the department (e.g., IT, HR, FIN)",
        example="IT",
        min_length=2,
        max_length=50
    )
    fiscal_year: int = Field(
        ...,
        description="Fiscal year for the budget (e.g., 2025)",
        example=2025,
        ge=2020,
        le=2100
    )
    allocated_budget: float = Field(
        ...,
        description="Total budget amount allocated for the period",
        example=50000.00,
        gt=0
    )
    rotation: str = Field(
        default="yearly",
        description="Budget rotation period: yearly, quarterly, or monthly",
        example="yearly"
    )
    period_start: Optional[str] = Field(
        None,
        description="Budget period start date in ISO format (YYYY-MM-DD)",
        example="2025-01-01"
    )
    period_end: Optional[str] = Field(
        None,
        description="Budget period end date in ISO format (YYYY-MM-DD)",
        example="2025-12-31"
    )
    notes: Optional[str] = Field(
        None,
        description="Additional notes or comments about the budget",
        example="Annual IT infrastructure budget",
        max_length=1000
    )

    @field_validator('rotation')
    def validate_rotation(cls, v):
        """Validate rotation period is one of the allowed values."""
        allowed_rotations = ['yearly', 'quarterly', 'monthly']
        if v.lower() not in allowed_rotations:
            raise ValueError(f"Rotation must be one of: {', '.join(allowed_rotations)}")
        return v.lower()

    @field_validator('period_start', 'period_end')
    def validate_date_format(cls, v):
        """Validate date is in correct ISO format."""
        if v:
            try:
                datetime.fromisoformat(v)
            except ValueError:
                raise ValueError("Date must be in ISO format (YYYY-MM-DD)")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "department_id": "IT",
                "fiscal_year": 2025,
                "allocated_budget": 50000.00,
                "rotation": "yearly",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
                "notes": "Annual IT infrastructure and software licensing budget"
            }
        }
    )


class BudgetResponseModel(BaseModel):
    """
    Model representing a budget response.
    
    This model is returned when retrieving budget information.
    """
    budget_id: str = Field(..., description="Unique identifier for the budget record")
    department_id: str = Field(..., description="Department identifier")
    fiscal_year: int = Field(..., description="Fiscal year")
    allocated_budget: float = Field(..., description="Total allocated budget")
    remaining_amount: float = Field(..., description="Remaining unspent budget")
    available_amount: float = Field(..., description="Available budget for allocation")
    spent_amount: Optional[float] = Field(None, description="Amount already spent")
    rotation: str = Field(..., description="Budget rotation period")
    period_start: Optional[datetime] = Field(None, description="Period start date")
    period_end: Optional[datetime] = Field(None, description="Period end date")
    notes: Optional[str] = Field(None, description="Additional notes")
    created_by: str = Field(..., description="User who created the budget")
    created_date: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_date: Optional[datetime] = Field(None, description="Last update timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "budget_id": "BUD-2025-001",
                "department_id": "IT",
                "fiscal_year": 2025,
                "allocated_budget": 50000.00,
                "remaining_amount": 25000.00,
                "available_amount": 25000.00,
                "spent_amount": 25000.00,
                "rotation": "yearly",
                "period_start": "2025-01-01T00:00:00Z",
                "period_end": "2025-12-31T23:59:59Z",
                "notes": "Annual IT infrastructure budget",
                "created_by": "admin@company.com",
                "created_date": "2024-12-01T10:00:00Z",
                "updated_date": "2025-01-15T14:30:00Z"
            }
        }
    )


class BudgetCreatedResponse(BaseModel):
    """Response model for successful budget creation."""
    message: str = Field(..., description="Success message")
    budget_id: str = Field(..., description="ID of the created budget")
    department_id: str = Field(..., description="Department ID")
    fiscal_year: int = Field(..., description="Fiscal year")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Budget created successfully",
                "budget_id": "BUD-2025-001",
                "department_id": "IT",
                "fiscal_year": 2025
            }
        }
    )


class ConsumptionReportResponse(BaseModel):
    """Response model for budget consumption reports."""
    department_id: str = Field(..., description="Department identifier")
    fiscal_year: str = Field(..., description="Fiscal year")
    total_allocated: float = Field(..., description="Total budget allocated")
    total_spent: float = Field(..., description="Total amount spent")
    total_remaining: float = Field(..., description="Total remaining budget")
    utilization_percentage: float = Field(..., description="Budget utilization percentage")
    budgets: List[dict] = Field(..., description="Detailed breakdown by budget")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "department_id": "IT",
                "fiscal_year": "2025",
                "total_allocated": 100000.00,
                "total_spent": 45000.00,
                "total_remaining": 55000.00,
                "utilization_percentage": 45.0,
                "budgets": [
                    {
                        "budget_id": "BUD-2025-001",
                        "category": "Software",
                        "allocated": 50000.00,
                        "spent": 25000.00,
                        "remaining": 25000.00
                    },
                    {
                        "budget_id": "BUD-2025-002",
                        "category": "Hardware",
                        "allocated": 50000.00,
                        "spent": 20000.00,
                        "remaining": 30000.00
                    }
                ]
            }
        }
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Internal server error",
                "detail": "Failed to process budget creation request"
            }
        }
    )

# ==================== API Endpoints ====================

@router.post(
    "/",
    response_model=BudgetCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new budget",
    description="Create a new budget allocation for a specific department and fiscal year.",
    responses={
        201: {
            "description": "Budget created successfully",
            "model": BudgetCreatedResponse
        },
        400: {
            "description": "Invalid request data",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
async def create_budget(
    budget: BudgetRequestModel,
    budget_service: BudgetService = Depends(get_budget_service)
) -> BudgetCreatedResponse:
    """
    Create a new budget record.
    
    This endpoint creates a new budget allocation for a department and fiscal year.
    The budget will be initialized with the allocated amount, and remaining/available
    amounts will be set to the full allocation.
    
    Args:
        budget: Budget creation request containing department, fiscal year, and allocation details
        budget_service: Injected budget service dependency
        
    Returns:
        BudgetCreatedResponse: Confirmation of budget creation with budget ID
        
    Raises:
        HTTPException: 400 if request data is invalid
        HTTPException: 500 if budget creation fails
    """
    try:
        logger.info(f"create_budget endpoint called for department {budget.department_id}, year {budget.fiscal_year}")

        budget_item: Budget = Budget(
            budget_id="",
            department_id=budget.department_id,
            fiscal_year=budget.fiscal_year,
            allocated_budget=budget.allocated_budget,
            remaining_amount=budget.allocated_budget,
            available_amount=budget.allocated_budget,
            rotation=budget.rotation,
            period_start=datetime.fromisoformat(budget.period_start) if budget.period_start else None,
            period_end=datetime.fromisoformat(budget.period_end) if budget.period_end else None,
            notes=budget.notes,
            created_by=DEFAULT_USER_NAME,
        )

        created_budget = await budget_service.create_budget(budget_item)
        logger.info(f"Budget created successfully: {created_budget.budget_id}")
        
        return BudgetCreatedResponse(
            message="Budget created successfully",
            budget_id=created_budget.budget_id,
            department_id=created_budget.department_id,
            fiscal_year=created_budget.fiscal_year
        )
    
    except ValueError as e:
        logger.error(f"Validation error in create_budget: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error in create_budget endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create budget"
        )


@router.get(
    "/{department_id}/{project_id}/{category}",
    response_model=Optional[BudgetResponseModel],
    summary="Get budget by department, project, and category",
    description="Retrieve a specific budget record based on department, project, and category.",
    responses={
        200: {
            "description": "Budget found and returned",
            "model": BudgetResponseModel
        },
        404: {
            "description": "Budget not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
async def get_budget(
    department_id: str,
    project_id: str,
    category: str,
    budget_service: BudgetService = Depends(get_budget_service)
) -> Optional[Budget]:
    """
    Retrieve a specific budget record.
    
    This endpoint fetches a budget based on department, project, and category filters.
    Returns None if no matching budget is found.
    
    Args:
        department_id: Unique identifier for the department
        project_id: Unique identifier for the project
        category: Budget category (e.g., Software, Hardware, Consulting)
        budget_service: Injected budget service dependency
        
    Returns:
        Budget object if found, None otherwise
        
    Raises:
        HTTPException: 500 if retrieval fails
    """
    try:
        logger.info(f"Retrieved budget for department {department_id}, project {project_id}, category {category}")
        budget = await budget_service.get_budget(department_id, project_id, category)
        
        if budget is None:
            logger.warning(f"Budget not found for {department_id}/{project_id}/{category}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Budget not found for department {department_id}, project {project_id}, category {category}"
            )
        
        logger.info(f"Budget retrieved: {budget.budget_id}")
        return budget
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in get_budget endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve budget"
        )


@router.get(
    "/{department_id}/{category}",
    response_model=List[BudgetResponseModel],
    summary="Search budgets by department and category",
    description="Retrieve all budgets matching the specified department and category.",
    responses={
        200: {
            "description": "List of budgets matching criteria",
            "model": List[BudgetResponseModel]
        },
        404: {
            "description": "No budgets found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
async def get_budgets_by_category(
    department_id: str,
    category: str,
    budget_service: BudgetService = Depends(get_budget_service)
) -> List[Budget]:
    """
    Search budgets by department and category.
    
    This endpoint returns all budget records that match the specified department
    and category criteria. Useful for getting an overview of all budgets in a
    specific category across fiscal years or projects.
    
    Args:
        department_id: Unique identifier for the department
        category: Budget category to filter by
        budget_service: Injected budget service dependency
        
    Returns:
        List of Budget objects matching the criteria
        
    Raises:
        HTTPException: 404 if no budgets found
        HTTPException: 500 if search fails
    """
    try:
        logger.info(f"Searching budgets for department {department_id}, category {category}")
        budgets = await budget_service.search_budgets(department_id, category)
        
        if not budgets or len(budgets) == 0:
            logger.warning(f"No budgets found for {department_id}/{category}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No budgets found for department {department_id} and category {category}"
            )
        
        logger.info(f"Found {len(budgets)} budgets")
        return budgets
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in get_budgets_by_category endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search budgets"
        )


@router.get(
    "/consumption/{department_id}/{fiscal_year}",
    response_model=ConsumptionReportResponse,
    summary="Generate budget consumption report",
    description="Generate a comprehensive consumption report for a department's budgets in a fiscal year.",
    responses={
        200: {
            "description": "Consumption report generated successfully",
            "model": ConsumptionReportResponse
        },
        404: {
            "description": "No budgets found for the specified criteria",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
async def get_consumption_report(
    department_id: str,
    fiscal_year: str,
    budget_service: BudgetService = Depends(get_budget_service)
) -> dict:
    """
    Generate a budget consumption report.
    
    This endpoint generates a comprehensive report showing budget allocation,
    spending, and utilization across all budget categories for a department
    in a specific fiscal year.
    
    The report includes:
    - Total allocated budget
    - Total spent amount
    - Total remaining budget
    - Utilization percentage
    - Breakdown by individual budgets
    
    Args:
        department_id: Unique identifier for the department
        fiscal_year: Fiscal year for the report
        budget_service: Injected budget service dependency
        
    Returns:
        Dictionary containing comprehensive consumption report data
        
    Raises:
        HTTPException: 404 if no budgets found
        HTTPException: 500 if report generation fails
    """
    try:
        logger.info(f"Generating consumption report for {department_id}, FY {fiscal_year}")
        report = await budget_service.generate_consumption_report(department_id, fiscal_year)
        
        if not report or report.get("total_allocated", 0) == 0:
            logger.warning(f"No budget data found for {department_id} in {fiscal_year}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No budget data found for department {department_id} in fiscal year {fiscal_year}"
            )
        
        logger.info(f"Consumption report generated: {report.get('utilization_percentage', 0)}% utilized")
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in get_consumption_report endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate consumption report"
        )