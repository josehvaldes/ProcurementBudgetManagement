from shared.config.settings import settings
from shared.models.invoice import Invoice
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.application.interfaces.service_interfaces import TableServiceInterface

logger = get_logger(__name__)

class InMemoryTableRepositoryService(TableServiceInterface):
    def __init__(self):
        self._invoices = {}

    def save_entity(self, invoice: Invoice) -> str:
        self._invoices[invoice.invoice_id] = invoice
        return invoice.invoice_id

    def get_entity(self, invoice_id: str) -> Invoice | None:
        return self._invoices.get(invoice_id)

    def delete_entity(self, invoice_id: str) -> None:
        self._invoices.pop(invoice_id, None)
