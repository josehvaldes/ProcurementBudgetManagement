


import asyncio
from datetime import datetime, timedelta, timezone
import json
import pytest
import pytest_asyncio

from shared.config.settings import settings
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from agents.payment_agent.agent import PaymentAgent
from shared.models.payment_batch_item import PaymentBatchItem, PaymentState
from shared.utils.logging_config import get_logger, setup_logging

setup_logging(log_level=settings.log_level,
                log_file=settings.log_file,
                log_to_console=settings.log_to_console)

logger = get_logger(__name__)


class TestPaymentAgent:

    @pytest_asyncio.fixture
    async def tool(self):
        agent = PaymentAgent(
                shutdown_event=asyncio.Event(),
                start_scheduler=False  # Don't start the scheduler for testing
        )
        yield agent

    @pytest_asyncio.fixture
    async def payment_tool(self):
        payment_batch_table_client = TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.payment_items_table_name
            )
        yield payment_batch_table_client

    @pytest_asyncio.fixture
    async def invoice(self):
        invoice_data_path = "scripts/data-source/invoices_data.json"
        logger.info(f"Loading invoice data from {invoice_data_path}")
        with open(invoice_data_path, "r") as f:
            invoices_data = json.load(f)
        return invoices_data[0]

    @pytest_asyncio.fixture
    async def budget(self):
        budget_data_path = "scripts/data-source/budgets_data.json"
        logger.info(f"Loading budget data from {budget_data_path}")
        with open(budget_data_path, "r") as f:
            budget_data = json.load(f)
        return budget_data[0]

    @pytest_asyncio.fixture
    async def vendor(self):
        vendor_data_path = "scripts/data-source/vendors_data.json"
        logger.info(f"Loading vendor data from {vendor_data_path}")
        with open(vendor_data_path, "r") as f:
            vendor_data = json.load(f)
        return vendor_data[0]

    @pytest.mark.asyncio
    async def test_process_payment(self, 
                                   tool: PaymentAgent,
                                   payment_tool: TableStorageService,
                                   invoice: dict,
                                   vendor: dict):
        """
        Integration Test payment processing for a scheduled invoice.
        """
        one_hour_before = datetime.now(timezone.utc) - timedelta(hours=1)
        payment_item = PaymentBatchItem(
            invoice_id=invoice["invoice_id"],
            department_id=invoice["department_id"],
            payment_date=one_hour_before,
            amount=invoice["amount"],
            currency=invoice["currency"],
            vendor_id=invoice["vendor_id"],
            vendor_name=invoice["vendor_name"],
            payment_method=vendor["payment_method"],
            state=PaymentState.SCHEDULED.value,
            created_at=one_hour_before,
            updated_at=one_hour_before
        )
        logger.info(f"Upserting payment item for invoice {payment_item.invoice_id} into table storage...")
        logger.debug(f"Payment item data: {payment_item.to_dict()}")

        await payment_tool.upsert_entity(payment_item.to_dict(), 
                                            partition_key=payment_item.department_id, 
                                            row_key=payment_item.invoice_id)

        logger.info(f"Inserted payment item for invoice {payment_item.invoice_id}, waiting for processing...")
        await asyncio.sleep(3)
        await tool.payment_task()
        logger.info(f"Payment task executed, checking payment item state...")
        await asyncio.sleep(3)
        entity = await payment_tool.get_entity(
            partition_key=payment_item.department_id, 
            row_key=payment_item.invoice_id
        )
        assert entity is not None
        assert entity["state"] == PaymentState.PROCESSED.value

        await payment_tool.delete_entity(
            partition_key=payment_item.department_id, 
            row_key=payment_item.invoice_id
        )