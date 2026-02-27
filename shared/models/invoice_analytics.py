

from dataclasses import dataclass
from datetime import datetime


@dataclass
class InvoiceAnalytics:
    # --- Keys ---
    invoice_id: str
    department_id: str

    # --- Invoice core ---
    invoice_state: str
    invoice_document_type: str
    invoice_amount: float
    invoice_currency: str
    invoice_category: str          # Software, Hardware, etc - critical for spend breakdown
    invoice_source: str            # email, api, upload
    invoice_priority: str          # normal, high, urgent
    invoice_budget_year: str            # fiscal year of the budget this invoice is charged to

    invoice_errors: list[str]     # any errors encountered during processing - important for error analysis
    invoice_warnings: list[str]   # any warnings during processing - useful for process improvement
    invoice_ai_suggested_approver: str  # if AI suggests an approver, capture it for analysis of AI impact

    # --- Timeline (for pipeline performance reports) ---
    invoice_created_at: datetime
    invoice_updated_at: datetime
    invoice_extracted_at: datetime     # when EXTRACTED state was reached
    invoice_validated_at: datetime     # when VALIDATED
    invoice_validated_state: bool     # validated successfully or not - important for error rate analysis

    invoice_budget_checked_at: datetime
    invoice_approved_at: datetime      # when APPROVED
    invoice_payment_scheduled_at: datetime
    invoice_paid_at: datetime
    processing_minutes: float          # total CREATED→PAID duration, computed at close



    # --- Approval info ---
    approval_type: str             # "auto" or "manual" - key metric
    approved_by: str               # who approved if manual

    # --- Vendor info ---
    vendor_id: str
    vendor_name: str
    vendor_active: bool
    vendor_categories: list[str]
    vendor_industry: str

    # --- Budget info ---
    budget_id: str
    budget_fiscal_year: str
    budget_category: str
    budget_project_id: str
    budget_status: str
    budget_rotation: str
    budget_allocated_amount: float     # snapshot at time of invoice - useful for % calculations
    budget_consumed_at_time: float     # how much was consumed when this invoice was processed