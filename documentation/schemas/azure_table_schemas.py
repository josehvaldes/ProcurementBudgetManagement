"""
Azure Storage Tables Schema Definitions
Procurement & Budget Management Automation

This module defines the table schemas for Azure Storage Tables.
Each schema includes partition key strategy, row key format, and all entity properties.
"""

from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class InvoiceState(str, Enum):
    """Invoice processing states"""
    CREATED = "CREATED"
    EXTRACTED = "EXTRACTED"
    VALIDATED = "VALIDATED"
    BUDGET_CHECKED = "BUDGET_CHECKED"
    APPROVED = "APPROVED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    PAYMENT_SCHEDULED = "PAYMENT_SCHEDULED"
    PAID = "PAID"
    FAILED = "FAILED"


class BudgetRotation(str, Enum):
    """Budget rotation periods"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


# ============================================================================
# TABLE: invoices
# ============================================================================

"""
Table Name: invoices
Purpose: Store all invoice records and processing state

Partition Key Strategy: department_id
- Enables efficient queries by department
- Supports budget tracking per department
- Natural data distribution

Row Key: invoice_id (UUID)
- Unique identifier for each invoice
- Enables direct lookups

Query Patterns:
1. Get all invoices for a department: PartitionKey = department_id
2. Get specific invoice: PartitionKey + RowKey
3. Get invoices by state: Filter on state property
4. Get invoices by date range: Filter on created_date
"""

INVOICES_SCHEMA = {
    # ========== REQUIRED AZURE TABLE PROPERTIES ==========
    "PartitionKey": "department_id",  # str - Department ID (e.g., "IT", "HR", "FINANCE")
    "RowKey": "invoice_id",            # str - UUID v4
    "Timestamp": "datetime",           # datetime - Auto-managed by Azure
    "etag": "str",                     # str - Auto-managed by Azure
    
    # ========== CORE INVOICE PROPERTIES ==========
    "invoice_number": "str",           # Vendor's invoice number
    "vendor_id": "Optional[str]",      # Foreign key to vendors table
    "vendor_name": "Optional[str]",    # Denormalized for quick access
    "amount": "float",                 # Total invoice amount
    "currency": "str",                 # ISO currency code (USD, EUR, etc.)
    "description": "str",              # Invoice description/purpose
    
    # ========== DATES ==========
    "issued_date": "datetime",         # Date vendor issued invoice
    "due_date": "Optional[datetime]",  # Payment due date
    "created_date": "datetime",        # Date record created in system
    "updated_date": "datetime",        # Last update timestamp
    
    # ========== STATE & WORKFLOW ==========
    "state": "str",                    # Current state (InvoiceState enum)
    "previous_state": "Optional[str]", # Previous state for audit trail
    "state_changed_at": "datetime",    # When state last changed
    "state_changed_by": "Optional[str]", # Agent or user who changed state
    
    # ========== EXTRACTED DATA (from Document Intelligence) ==========
    "raw_file_url": "Optional[str]",   # Azure Blob Storage URL for original file
    "raw_file_blob_name": "Optional[str]", # Blob name for original file
    "file_type": "Optional[str]",      # File extension (pdf, jpg, png)
    "file_size": "Optional[int]",      # in bytes
    "file_uploaded_at": "Optional[datetime]", # When file was uploaded
    "extracted_data": "Optional[str]", # JSON - Parsed fields from OCR
    "extraction_confidence": "Optional[float]", # OCR confidence score (0-1)
    "qr_code_data": "Optional[str]",   # QR code data if present
    
    # ========== PURCHASE ORDER MATCHING ==========
    "has_po": "bool",                  # Whether invoice has a matched PO
    "po_number": "Optional[str]",      # Matched PO reference
    "po_matched": "bool",              # Whether PO match was found
    "po_match_confidence": "Optional[float]", # Confidence of PO match
    
    # ========== BUDGET TRACKING ==========
    "department_id": "str",            # Department code
    "project_id": "Optional[str]",     # Project code (if applicable)
    "category": "Optional[str]",       # Spending category (Software, Hardware, etc.)
    "budget_year": "Optional[str]",    # Fiscal year (FY2024)
    "budget_allocated": "bool",        # Whether budget was allocated
    
    # ========== VALIDATION & APPROVAL ==========
    "validation_passed": "bool",       # Overall validation result
    "approval_required": "bool",       # Whether manual approval needed
    "approved_by": "Optional[str]",    # User who approved (if manual)
    "approved_date": "Optional[datetime]", # Approval timestamp
    "rejection_reason": "Optional[str]", # Why invoice was rejected
    
    # ========== METADATA & TRACKING ==========
    "source": "str",                   # How invoice entered (email, api, upload)
    "source_email": "Optional[str]",   # Email address if from email
    "source_subject": "Optional[str]", # Email subject if from email
    "assigned_to": "Optional[str]",    # User assigned for manual review
    "priority": "str",                 # normal, high, urgent
    "tags": "Optional[str]",           # JSON array - Custom tags
    "notes": "Optional[str]",          # Free-form notes
    
    # ========== LINE ITEMS ==========
    "tax_amount": "Optional[float]",   # Total tax
    "subtotal": "Optional[float]",     # Amount before tax
    "shipping_amount": "Optional[float]", # Shipping/handling
    "discount_amount": "Optional[float]", # Any discounts applied
}

# Example invoice entity
INVOICE_EXAMPLE = {
    "PartitionKey": "IT",
    "RowKey": "550e8400-e29b-41d4-a716-446655440000",
    "invoice_number": "INV-2024-001234",
    "vendor_id": "vendor-123",
    "vendor_name": "Tech Supplies Inc.",
    "amount": 1250.00,
    "currency": "USD",
    "description": "Monthly software licenses",
    "issued_date": "2024-12-01T00:00:00Z",
    "due_date": "2024-12-31T00:00:00Z",
    "created_date": "2024-12-15T10:30:00Z",
    "updated_date": "2024-12-15T10:35:00Z",
    "state": "VALIDATED",
    "previous_state": "EXTRACTED",
    "state_changed_at": "2024-12-15T10:35:00Z",
    "state_changed_by": "validation_agent",
    "extracted_data": '{"vendor": "Tech Supplies Inc.", "total": 1250.00, "items": [...]}',
    "po_number": "PO-2024-5678",
    "po_matched": True,
    "department_id": "IT",
    "category": "Software",
    "budget_year": "FY2024",
    "validation_passed": True,
    "source": "email",
    "priority": "normal"
}


# ============================================================================
# TABLE: vendors
# ============================================================================

"""
Table Name: vendors
Purpose: Store approved vendor information and payment terms

Partition Key: "VENDOR" (single partition)
- All vendors in one partition for simple lookups
- Small enough dataset (hundreds, not millions)
- Efficient for "get all vendors" queries

Row Key: vendor_id (UUID)
- Unique identifier for vendor

Query Patterns:
1. Get all vendors: PartitionKey = "VENDOR"
2. Get specific vendor: PartitionKey + RowKey
3. Get approved vendors: Filter on approved = true
"""

VENDORS_SCHEMA = {
    # ========== REQUIRED AZURE TABLE PROPERTIES ==========
    "PartitionKey": "str",             # Always "VENDOR"
    "RowKey": "vendor_id",             # str - UUID v4
    "Timestamp": "datetime",
    "etag": "str",
    
    # ========== VENDOR INFORMATION ==========
    "name": "str",                     # Vendor legal name
    "display_name": "Optional[str]",   # Friendly display name
    "tax_id": "Optional[str]",         # Tax ID / EIN
    "vendor_number": "Optional[str]",  # Internal vendor code
    
    # ========== CONTACT INFORMATION ==========
    "contact_name": "Optional[str]",   # Primary contact person
    "contact_email": "Optional[str]",  # Primary email
    "contact_phone": "Optional[str]",  # Primary phone
    "address": "Optional[str]",        # JSON - Full address object
    "website": "Optional[str]",        # Vendor website
    
    # ========== APPROVAL & STATUS ==========
    "approved": "bool",                # Whether vendor is approved
    "approved_by": "Optional[str]",    # Who approved vendor
    "approved_date": "Optional[datetime]", # When approved
    "active": "bool",                  # Whether vendor is active
    "suspended": "bool",               # Whether vendor is suspended
    "suspension_reason": "Optional[str]", # Why vendor suspended
    
    # ========== PAYMENT TERMS ==========
    "payment_terms": "str",            # net-30, net-60, etc.
    "payment_method": "Optional[str]", # Preferred payment method
    "bank_account": "Optional[str]",   # JSON - Bank details (encrypted)
    "currency": "str",                 # Default currency
    
    # ========== SPENDING CONTROLS ==========
    "spend_limit": "Optional[float]",  # Maximum per-invoice limit
    "monthly_spend_limit": "Optional[float]", # Monthly cap
    "ytd_spend": "float",              # Year-to-date spending
    "last_invoice_date": "Optional[datetime]", # Most recent invoice
    "total_invoices": "int",           # Count of invoices
    
    # ========== CONTRACTS & AGREEMENTS ==========
    "contracts": "Optional[str]",      # JSON array - Contract references
    "contract_start_date": "Optional[datetime]",
    "contract_end_date": "Optional[datetime]",
    "contract_value": "Optional[float]",
    "auto_approve": "bool",            # Auto-approve invoices from vendor
    "auto_approve_limit": "Optional[float]", # Max amount for auto-approval
    
    # ========== CATEGORIES & TAGS ==========
    "categories": "Optional[str]",     # JSON array - What vendor provides
    "tags": "Optional[str]",           # JSON array - Custom tags
    "industry": "Optional[str]",       # Vendor industry
    "size": "Optional[str]",           # small, medium, large
    
    # ========== PERFORMANCE METRICS ==========
    "on_time_delivery_rate": "Optional[float]", # % of on-time deliveries
    "quality_rating": "Optional[float]", # 1-5 rating
    "last_review_date": "Optional[datetime]",
    "notes": "Optional[str]",          # Internal notes
    
    # ========== METADATA ==========
    "created_date": "datetime",
    "updated_date": "datetime",
    "created_by": "Optional[str]",
    "updated_by": "Optional[str]",
}

# Example vendor entity
VENDOR_EXAMPLE = {
    "PartitionKey": "VENDOR",
    "RowKey": "vendor-123",
    "name": "Tech Supplies Inc.",
    "display_name": "Tech Supplies",
    "tax_id": "12-3456789",
    "contact_email": "billing@techsupplies.com",
    "contact_phone": "+1-555-0123",
    "address": '{"street": "123 Tech Lane", "city": "San Francisco", "state": "CA", "zip": "94105"}',
    "approved": True,
    "approved_by": "john.doe@company.com",
    "approved_date": "2024-01-15T00:00:00Z",
    "active": True,
    "suspended": False,
    "payment_terms": "net-30",
    "currency": "USD",
    "spend_limit": 10000.00,
    "monthly_spend_limit": 50000.00,
    "ytd_spend": 125000.00,
    "auto_approve": True,
    "auto_approve_limit": 5000.00,
    "categories": '["Software", "Hardware", "Licenses"]',
    "created_date": "2024-01-15T00:00:00Z",
    "updated_date": "2024-12-15T00:00:00Z"
}

# ============================================================================
# TABLE: budgets
# ============================================================================

"""
Table Name: budgets
Purpose: Track budget allocations and consumption by department and category

Partition Key: fiscal_year (e.g., "FY2024")
- Groups budgets by fiscal year
- Enables year-over-year comparisons
- Simplifies fiscal year rollover

Row Key: department_id + category (e.g., "IT-Software")
- Composite key for department + spending category
- Unique within fiscal year

Query Patterns:
1. Get all budgets for a year: PartitionKey = fiscal_year
2. Get specific budget: PartitionKey + RowKey
3. Get department budgets: PartitionKey + Filter on department_id
"""

BUDGETS_SCHEMA = {
    # ========== REQUIRED AZURE TABLE PROPERTIES ==========
    "PartitionKey": "fiscal_year",     # str - e.g., "FY2024", "FY2025"
    "RowKey": "str",                   # department_id-category (e.g., "IT-Software")
    "Timestamp": "datetime",
    "etag": "str",
    
    # ========== BUDGET IDENTIFICATION ==========
    "budget_id": "str",                # UUID - Alternative unique ID
    "department_id": "str",            # Department code
    "department_name": "str",          # Denormalized department name
    "category": "str",                 # Spending category
    "fiscal_year": "str",              # e.g., "FY2024"
    
    # ========== BUDGET AMOUNTS ==========
    "allocated_amount": "float",       # Original budget allocation (max_limit)
    "consumed_amount": "float",        # Amount spent so far
    "remaining_amount": "float",       # allocated - consumed
    "reserved_amount": "float",        # Amount in pending invoices
    "available_amount": "float",       # remaining - reserved
    
    # ========== BUDGET PERIOD ==========
    "rotation": "str",                 # monthly, quarterly, yearly
    "period_start": "datetime",        # Budget period start
    "period_end": "datetime",          # Budget period end
    "current_period": "str",           # e.g., "Q4-2024", "Dec-2024"
    
    # ========== SPENDING METRICS ==========
    "consumption_rate": "float",       # % of budget consumed (0-100)
    "burn_rate": "float",             # Average spend per period
    "projected_total": "Optional[float]", # Forecast total spend
    "projected_overrun": "Optional[float]", # Projected over-budget amount
    "days_remaining": "int",           # Days left in period
    
    # ========== THRESHOLDS & ALERTS ==========
    "warning_threshold": "float",      # % to trigger warning (e.g., 75%)
    "critical_threshold": "float",     # % to trigger critical alert (e.g., 90%)
    "warning_triggered": "bool",       # Whether warning sent
    "critical_triggered": "bool",      # Whether critical alert sent
    "over_budget": "bool",             # Whether budget exceeded
    "alerts_sent": "Optional[str]",    # JSON array - Alert history
    
    # ========== APPROVAL WORKFLOW ==========
    "approval_required_over": "Optional[float]", # Amount requiring approval
    "auto_approve_under": "Optional[float]",     # Amount auto-approved
    "approver": "Optional[str]",       # Budget owner/approver
    "approver_email": "Optional[str]",
    
    # ========== ROLLOVER & CARRYOVER ==========
    "allow_rollover": "bool",          # Can unused budget carry over
    "rollover_amount": "Optional[float]", # Amount rolled from previous period
    "rollover_from": "Optional[str]",  # Previous period reference
    
    # ========== TRACKING ==========
    "invoice_count": "int",            # Number of invoices against budget
    "last_invoice_date": "Optional[datetime]", # Most recent invoice
    "last_update_by": "Optional[str]", # Last agent/user update
    
    # ========== METADATA ==========
    "created_date": "datetime",
    "updated_date": "datetime",
    "created_by": "Optional[str]",
    "notes": "Optional[str]",
    "tags": "Optional[str]",           # JSON array
    "status": "str",                   # active, frozen, closed
}

# Example budget entity
BUDGET_EXAMPLE = {
    "PartitionKey": "FY2024",
    "RowKey": "IT-Software",
    "budget_id": "770e8400-e29b-41d4-a716-446655440002",
    "department_id": "IT",
    "department_name": "Information Technology",
    "category": "Software",
    "fiscal_year": "FY2024",
    "allocated_amount": 100000.00,     # max_limit
    "consumed_amount": 67500.00,
    "remaining_amount": 32500.00,
    "reserved_amount": 5000.00,
    "available_amount": 27500.00,
    "rotation": "yearly",
    "period_start": "2024-01-01T00:00:00Z",
    "period_end": "2024-12-31T23:59:59Z",
    "current_period": "FY2024",
    "adjustment_total": 0.00,
    "original_allocation": 100000.00,
    "consumption_rate": 67.5,          # 67.5% consumed
    "burn_rate": 6115.00,             # Monthly average
    "warning_threshold": 75.0,
    "critical_threshold": 90.0,
    "warning_triggered": False,
    "critical_triggered": False,
    "over_budget": False,
    "allow_rollover": False,
    "invoice_count": 54,
    "created_date": "2024-01-01T00:00:00Z",
    "updated_date": "2024-12-15T10:00:00Z",
    "status": "active"
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_invoice_partition_key(department_id: str) -> str:
    """Create partition key for invoice"""
    return department_id


def create_invoice_row_key() -> str:
    """Create row key (UUID) for invoice"""
    import uuid
    return str(uuid.uuid4())


def create_vendor_partition_key() -> str:
    """Create partition key for vendor (always 'VENDOR')"""
    return "VENDOR"


def create_vendor_row_key() -> str:
    """Create row key (UUID) for vendor"""
    import uuid
    return f"vendor-{uuid.uuid4()}"


def create_po_partition_key(department_id: str) -> str:
    """Create partition key for PO"""
    return department_id


def create_po_row_key(year: int, sequence: int) -> str:
    """Create row key for PO"""
    return f"PO-{year}-{sequence:04d}"


def create_budget_partition_key(fiscal_year: str) -> str:
    """Create partition key for budget"""
    return fiscal_year


def create_budget_row_key(department_id: str, category: str) -> str:
    """Create row key for budget"""
    return f"{department_id}-{category}"


# ============================================================================
# SCHEMA VALIDATION
# ============================================================================

def validate_invoice(entity: dict) -> bool:
    """Validate invoice entity has required fields"""
    required = ["PartitionKey", "RowKey", "amount", "department_id", "state", "created_date"]
    return all(field in entity for field in required)


def validate_vendor(entity: dict) -> bool:
    """Validate vendor entity has required fields"""
    required = ["PartitionKey", "RowKey", "name", "approved", "active"]
    return all(field in entity for field in required)


def validate_po(entity: dict) -> bool:
    """Validate PO entity has required fields"""
    required = ["PartitionKey", "RowKey", "vendor_id", "total", "status"]
    return all(field in entity for field in required)


def validate_budget(entity: dict) -> bool:
    """Validate budget entity has required fields"""
    required = ["PartitionKey", "RowKey", "department_id", "allocated_amount", "consumed_amount"]
    return all(field in entity for field in required)


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    print("Azure Storage Tables - Schema Definitions")
    print("=" * 60)
    
    print("\nINVOICES TABLE")
    print(f"Partition Key: {INVOICES_SCHEMA['PartitionKey']}")
    print(f"Row Key: {INVOICES_SCHEMA['RowKey']}")
    print(f"Total Fields: {len(INVOICES_SCHEMA)}")
    
    print("\nVENDORS TABLE")
    print(f"Partition Key: {VENDORS_SCHEMA['PartitionKey']}")
    print(f"Row Key: {VENDORS_SCHEMA['RowKey']}")
    print(f"Total Fields: {len(VENDORS_SCHEMA)}")
    
    print("\nBUDGETS TABLE")
    print(f"Partition Key: {BUDGETS_SCHEMA['PartitionKey']}")
    print(f"Row Key: {BUDGETS_SCHEMA['RowKey']}")
    print(f"Total Fields: {len(BUDGETS_SCHEMA)}")
