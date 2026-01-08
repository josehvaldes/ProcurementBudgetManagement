

from enum import Enum
import json
from invoice_lifecycle_api.application.interfaces.service_interfaces import TableServiceInterface
from shared.models.invoice import Invoice
from shared.models.vendor import Vendor, VendorContract
from shared.utils.logging_config import get_logger
logger = get_logger(__name__)

class ValidationResult(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    MANUAL_REVIEW = "manual_review"

class ValidationResponse:
    def __init__(self, result: ValidationResult, messages: list[str], matched_vendor: Vendor = None):
        self.result = result
        self.messages = messages
        self.matched_vendor = matched_vendor

class DeterministicValidator:
    """Deterministic Validator for invoice data validation."""

    def __init__(self, vendor_table: TableServiceInterface, invoice_table: TableServiceInterface):
        self.vendor_table = vendor_table
        self.invoice_table = invoice_table

    async def validate_invoice(self, invoice_data: Invoice) -> ValidationResponse:
        """Validate the invoice data against deterministic rules."""
        # 1. validate vendor_name
        vendor_name = invoice_data.vendor_name
        if vendor_name is None or vendor_name.strip() == "":
            return ValidationResponse(ValidationResult.INVALID, ["Vendor name is missing in the invoice data"])

        # 2. Validate duplicity vendor_name invoice_number
        if await self.has_duplicate(invoice_data):
            return ValidationResponse(ValidationResult.INVALID, [f"Duplicate invoice found for invoice number {invoice_data.invoice_number} and vendor {vendor_name}"])

        # 3. Check for required fields
        required_fields = ["amount", "vendor_name", "invoice_number", "issued_date"]
        missing_fields = []
        for field in required_fields:
            value = getattr(invoice_data, field, None)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                missing_fields.append(field)

        if missing_fields:
            return ValidationResponse(ValidationResult.INVALID, [f"Missing required field: {field}" for field in missing_fields])

        # 4. Validate amounts
        amount = invoice_data.amount
        if amount is None or amount < 0:
            return ValidationResponse(ValidationResult.INVALID, ["Invoice amount must be a positive number"])

        # 5. validate vendor approval status and contracts
        vendors_list = await self.vendor_table.query_entities(
            filters_query=[("name", vendor_name)]
        )

        if vendors_list and len(vendors_list) >= 0:
            vendor = vendors_list[0]
            if not vendor["active"]:
                return ValidationResponse(ValidationResult.INVALID, [f"Vendor {vendor_name} is not active"])
            
            # Validate vendor contracts
            if vendor["contracts"] and len(vendor["contracts"]) > 0:
                contracts_dicts = json.loads(vendor["contracts"]) if isinstance(vendor["contracts"], str) else {}
                contracts = [VendorContract.from_dict(c) for c in contracts_dicts]
                messages = []
                is_contract_valid = self.validate_contracts(contracts, invoice_data, messages=messages)
                logger.info(f"Contract validation for vendor {vendor_name} returned: {is_contract_valid}, errors: {messages}")
                if not is_contract_valid:
                    return ValidationResponse(ValidationResult.INVALID, messages)
            else:
                pass

            if vendor["auto_approve"]:
                auto_approve_limit = vendor.get("auto_approve_limit", None)
                if auto_approve_limit is not None and amount > auto_approve_limit:
                    return ValidationResponse(ValidationResult.INVALID, [f"Invoice amount {amount} exceeds auto-approve limit for vendor {vendor_name}"])

            # check spend limit
            spend_limit = vendor.get("spend_limit", None)
            if spend_limit is not None and amount > spend_limit:
                return ValidationResponse(ValidationResult.INVALID, [f"Invoice amount {amount} exceeds spend limit for vendor {vendor_name}"])

            return ValidationResponse(ValidationResult.VALID, [], Vendor.from_dict(vendor))
        else:
            # Vendor not found.
            return ValidationResponse(ValidationResult.MANUAL_REVIEW, [f"Vendor not found in the system. Vendor Name: {vendor_name}"])

    async def has_duplicate(self, invoice: Invoice) -> bool:
        """Check if the invoice is a duplicate."""
        # Placeholder logic for duplicate check
        invoice_number = invoice.invoice_number
        vendor_name = invoice.vendor_name
        department_id = invoice.department_id
        
        logger.info(f"Checking for duplicate invoice: {invoice_number} from vendor {vendor_name} (ID: {invoice_number})")

        entities = await self.invoice_table.query_entities(
            filters_query=[
                ("invoice_number", invoice_number),
                ("vendor_name", vendor_name),
                ("department_id", department_id) # to scope duplicates within the same department
            ]
        )

        if entities and len(entities) > 1:
            #validate dates to avoid false positives
            for entity in entities:
                existing_invoice = Invoice.from_dict(entity)

                #time_difference = abs((existing_invoice.created_date - invoice.created_date).total_seconds())
                # use time_difference threshold if needed later
                if existing_invoice.created_date != invoice.created_date:
                    logger.warning(f"Duplicate invoice found: {invoice_number} from vendor {vendor_name}")
                    return True

        # No duplicate found
        logger.info(f"No duplicate invoice found: {invoice_number} from vendor {vendor_name}")
        return False

    def validate_contracts(self, contracts: list[VendorContract], invoice_data: Invoice, messages: list[str]) -> bool:
        """Validate invoice against vendor contracts."""
        if not contracts or len(contracts) == 0:
            messages.append(f"No contracts found for vendor {invoice_data.vendor_name}; skipping contract compliance check")
            return True

        # Placeholder logic for contract compliance check
        # In a real implementation, this would involve checking the invoice details against contract terms
        compliant = True  # Assume compliance for placeholder
        active_contracts = [contract for contract in contracts if contract.status == "active"]
        
        if not active_contracts:
            messages.append(f"No active contracts for vendor {invoice_data.vendor_name}; skipping contract compliance check")
            return True

        for contract in active_contracts:
            if contract.contract_value and invoice_data.amount > contract.contract_value:
                messages.append(f"Invoice {invoice_data.invoice_number} exceeds contract value for vendor {invoice_data.vendor_name}")
                compliant = False
            
            if contract.contract_start_date and invoice_data.issued_date < contract.contract_start_date:
                messages.append(f"Invoice {invoice_data.invoice_number} issued before contract start date for vendor {invoice_data.vendor_name}")
                compliant = False
            if contract.contract_end_date and invoice_data.issued_date > contract.contract_end_date:
                messages.append(f"Invoice {invoice_data.invoice_number} issued after contract end date for vendor {invoice_data.vendor_name}")
                compliant = False

        if not compliant:
            messages.append(f"Invoice {invoice_data.invoice_number} does not comply with vendor contracts")
            return False
        
        logger.info(f"Invoice {invoice_data.invoice_number} complies with all vendor contracts for vendor {invoice_data.vendor_name}")
        return True