

from invoice_lifecycle_api.application.interfaces.service_interfaces import TableServiceInterface
from shared.models.invoice import Invoice
from shared.models.vendor import Vendor, VendorContract
from shared.utils.logging_config import get_logger
logger = get_logger(__name__)

class DeterministicValidator:
    """Deterministic Validator for invoice data validation."""

    async def validate(self, invoice_data: Invoice, vendor: Vendor) -> tuple[bool, list[str], list[str]]:
        """Perform deterministic validations on the invoice data."""

        errors = []
        warnings = []
        if not invoice_data:
            return False, ["Invoice data is empty"], []

        # Check for required fields
        required_fields = ["amount", "vendor_name", "invoice_number", "issued_date"]
        for field in required_fields:
            if not getattr(invoice_data, field, None):
                errors.append(f"Missing required field: {field}")

        # Check vendor approval status
        if not vendor.approved:
            errors.append(f"Vendor not approved: {vendor.name}")
        else:
            is_contract_valid = self.validate_contracts(vendor.contracts, invoice_data, errors, warnings)
            if not is_contract_valid:
                logger.warning(f"Invoice {invoice_data.invoice_number} failed contract compliance check for vendor {vendor.name}")

        # Validate amounts
        amount = invoice_data.amount
        if amount is None or amount < 0:
            errors.append("Invoice amount must be a positive number")

        return not errors, errors, warnings

    def validate_contracts(self, contracts: list[VendorContract], invoice_data: Invoice, errors: list[str], warnings: list[str]) -> bool:
        """Validate invoice against vendor contracts."""
        if not contracts or len(contracts) == 0:
            warnings.append(f"No contracts found for vendor {invoice_data.vendor_name}; skipping contract compliance check")
            return True

        # Placeholder logic for contract compliance check
        # In a real implementation, this would involve checking the invoice details against contract terms
        compliant = True  # Assume compliance for placeholder
        active_contracts = [contract for contract in contracts if contract.status == "active"]
        
        if not active_contracts:
            warnings.append(f"No active contracts for vendor {invoice_data.vendor_name}; skipping contract compliance check")
            return True

        for contract in active_contracts:
            if contract.contract_value and invoice_data.amount > contract.contract_value:
                warnings.append(f"Invoice {invoice_data.invoice_number} exceeds contract value for vendor {invoice_data.vendor_name}")
                compliant = False
            
            if contract.contract_start_date and invoice_data.issued_date < contract.contract_start_date:
                warnings.append(f"Invoice {invoice_data.invoice_number} issued before contract start date for vendor {invoice_data.vendor_name}")
                compliant = False
            if contract.contract_end_date and invoice_data.issued_date > contract.contract_end_date:
                warnings.append(f"Invoice {invoice_data.invoice_number} issued after contract end date for vendor {invoice_data.vendor_name}")
                compliant = False
            

        if not compliant:
            errors.append(f"Invoice {invoice_data.invoice_number} does not comply with vendor contracts")
            return False