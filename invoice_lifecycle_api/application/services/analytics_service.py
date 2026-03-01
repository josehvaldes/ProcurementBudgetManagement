from datetime import datetime, timezone

from shared.models.invoice import InvoiceState, ReviewStatus
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.application.interfaces.service_interfaces import CompareOperator, JoinOperator, TableServiceInterface
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import EntityQueryException

logger = get_logger(__name__)


class AnalyticsService:

    def __init__(self, analytics_table: TableServiceInterface):
        self.analytics_table = analytics_table

    async def _process_spending_data(self, raw_data: list[dict]) -> list[dict]:
        # Placeholder for data processing logic - this could include aggregations, calculations, etc.
        # For now, we will return the raw data as-is.
        return raw_data
    
    async def get_spending_summary(self, department_id: str = None, fiscal_year: str = None) -> list[dict]:
        try:
            errors = []
            if not department_id:
                errors.append("Department ID must be provided if fiscal year is specified.")
            if not fiscal_year:
                errors.append("Fiscal year must be provided if department ID is specified.")

            if errors:
                logger.error("Validation errors found", extra={"errors": errors})
                raise ValueError("Validation errors found")

            filters = [
                ("PartitionKey", fiscal_year, CompareOperator.EQUAL.value),
                ("department_id", department_id, CompareOperator.EQUAL.value)
            ]

            spending_summary = await self.analytics_table.query_entities_with_filters(filters=filters, join_operator=JoinOperator.AND)
            return await self._process_spending_data(spending_summary)
        except EntityQueryException as e:
            logger.error("Error querying spending summary", extra={"error": str(e)})
            raise
    
    async def _process_pipeline_performance_data(self, raw_data: list[dict]) -> list[dict]:
        # Placeholder for data processing logic - this could include aggregations, calculations, etc.
        # For now, we will return the raw data as-is.
        return raw_data
    
    async def get_pipeline_performance(self, fiscal_year: str = None) -> list[dict]:
        try:
            filters = []
            if fiscal_year:
                filters.append(("PartitionKey", fiscal_year, CompareOperator.EQUAL.value))
            performance_data = await self.analytics_table.query_entities_with_filters(filters=filters, join_operator=JoinOperator.AND)
            return await self._process_pipeline_performance_data(performance_data)
        except EntityQueryException as e:
            logger.error("Error querying pipeline performance", extra={"error": str(e)})
            raise

    async def _process_vendor_summary_data(self, raw_data: list[dict]) -> list[dict]:
        # Placeholder for data processing logic - this could include aggregations, calculations, etc.
        # For now, we will return the raw data as-is.
        return raw_data

    async def get_vendor_summary(self, fiscal_year: str = None) -> list[dict]:
        try:
            filters = []
            if fiscal_year:
                filters.append(("PartitionKey", fiscal_year, CompareOperator.EQUAL.value))
            vendor_summary = await self.analytics_table.query_entities_with_filters(filters=filters, join_operator=JoinOperator.AND)
            return await self._process_vendor_summary_data(vendor_summary)
        except EntityQueryException as e:
            logger.error("Error querying vendor summary", extra={"error": str(e)})
            raise