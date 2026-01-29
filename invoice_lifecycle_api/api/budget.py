"""
Budget API endpoints.
"""
from datetime import datetime
import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from fastapi import UploadFile, File, Form
from pydantic import BaseModel, EmailStr

from shared.config.settings import settings
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.application.interfaces.service_interfaces import TableServiceInterface
from invoice_lifecycle_api.application.services.budget_service import BudgetService
from invoice_lifecycle_api.domain.uploaded_file_dto import UploadedFileDTO
from shared.models.budget import Budget
from invoice_lifecycle_api.application.services.event_choreographer import EventChoreographer
from invoice_lifecycle_api.application.interfaces.di_container import get_budget_service, get_budget_repository_service, get_event_choreographer_service
from shared.models.invoice import Invoice, InvoiceSource

logger = get_logger(__name__)

router = APIRouter()
DEFAULT_USER_NAME: str = "system"

class BudgetRequestModel(BaseModel):
    department_id: str 
    fiscal_year: int
    allocated_budget: float
    rotation: str = "yearly"  # e.g., "yearly", "quarterly", monthly
    period_start: str | None
    period_end: str | None
    notes: str | None

@router.post("/")
async def create_budget(budget: BudgetRequestModel,
                        budget_service: BudgetService = Depends(get_budget_service)
                        ):
    """Endpoint to create a new budget record."""
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

        await budget_service.create_budget(budget_item)
        logger.info(f"Budget Data: {budget.model_dump_json()}")
        
        return JSONResponse(status_code=201, content={"message": "Budget created successfully", "budget": budget.dict()})
    
    except Exception as e:
        logger.error(f"Error in create_budget endpoint: {str(e)}")
        logger.debug(traceback.format_exc())
        return JSONResponse(status_code=500, content={"message": "Internal server error"})

@router.get("/{department_id}/{project_id}/{category}")
async def get_budget(department_id: str,
                     project_id: str,
                     category: str,
                     budget_service: BudgetService = Depends(get_budget_service)
                     ) -> Budget | None:
    """Get a budget record from the repository."""
    try:
        logger.info(f"Retrieved budget for department {department_id}, project {project_id}, category {category}")
        budget = await budget_service.get_budget(department_id, project_id, category)
        logger.info(f"{budget}")
        return budget
    except Exception as e:
        logger.error(f"Error in get_budget endpoint: {str(e)}")
        logger.debug(traceback.format_exc())
        return None
    
@router.get("/{department_id}/{category}")
async def get_budget(department_id: str,
                     category: str,
                     budget_service: BudgetService = Depends(get_budget_service)
                     ) -> list[Budget] | None:
    """Search budgets by department and category."""
    try:
        logger.info(f"Retrieved budgets for department {department_id}, category {category}")
        budgets = await budget_service.search_budgets(department_id, category)
        logger.info(f"{budgets}")
        return budgets
    except Exception as e:
        logger.error(f"Error in get_budget endpoint: {str(e)}")
        logger.debug(traceback.format_exc())
        return None

@router.get("/consumption/{department_id}/{fiscal_year}")
async def get_consumption_report(department_id: str, fiscal_year: str,
                                 budget_service: BudgetService = Depends(get_budget_service)
                                 ) -> dict:
    """Generate a budget consumption report."""
    try:
        report = await budget_service.generate_consumption_report(department_id, fiscal_year)
        return report
    except Exception as e:
        logger.error(f"Error in get_consumption_report endpoint: {str(e)}")
        logger.debug(traceback.format_exc())
        return JSONResponse(status_code=500, content={"message": "Internal server error"})