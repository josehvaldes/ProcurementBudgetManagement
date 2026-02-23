"""
Invoice domain model and state machine.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from decimal import Decimal
from shared.utils.convert import convert_to_table_entity

class InvoiceState(str, Enum):
    """Invoice state machine states."""
    CREATED = "CREATED"
    EXTRACTED = "EXTRACTED"
    VALIDATED = "VALIDATED"
    BUDGET_CHECKED = "BUDGET_CHECKED"
    APPROVED = "APPROVED"
    PAYMENT_SCHEDULED = "PAYMENT_SCHEDULED"
    PAID = "PAID"
    FAILED = "FAILED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    REJECTED = "REJECTED"

class ReviewStatus(str, Enum):
    """Invoice review status."""
    NOT_REVIEWED = "NOT_REVIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class Priority(str, Enum):
    """Invoice priority levels."""
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class InvoiceSource(str, Enum):
    """Invoice source types."""
    EMAIL = "email"
    API = "api"
    UPLOAD = "upload"
    MANUAL = "manual"

#class for invouice type: Invoice or receipt
class DocumentType(str, Enum):
    """Document type."""
    INVOICE = "invoice"
    RECEIPT = "receipt"

class InvoiceInternalMessage:
    agent: str
    message: str
    code: Optional[str] = None
    timestamp: str= None
    def __init__(self, agent: str, message: str, code: Optional[str] = None, timestamp: Optional[str] = None):
        self.agent = agent
        self.message = message
        self.code = code
        self.timestamp = timestamp if timestamp else datetime.now(timezone.utc).isoformat()

@dataclass
class Invoice:
    """Invoice domain model aligned with Azure Table Storage schema."""
    
    # ========== IDENTIFIERS ==========
    invoice_id: str  # RowKey in Azure Tables
    department_id: str  # PartitionKey in Azure Tables
    invoice_number: Optional[str] = None
    vendor_id: Optional[str] = None
    vendor_name: Optional[str] = None
    document_type: DocumentType = DocumentType.INVOICE

    # ========== AMOUNTS ==========
    amount: Optional[Decimal] = None  # Total invoice amount
    currency: str = "USD"
    tax_amount: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None
    shipping_amount: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    
    # ========== DATES ==========
    issued_date: Optional[datetime] = None  # When vendor issued invoice
    due_date: Optional[datetime] = None
    created_date: datetime = field(default_factory= lambda: datetime.now(timezone.utc))
    updated_date: datetime = field(default_factory= lambda: datetime.now(timezone.utc))

    # ========== STATE & WORKFLOW ==========
    state: InvoiceState = InvoiceState.CREATED
    previous_state: Optional[InvoiceState] = None
    state_changed_at: datetime = field(default_factory= lambda: datetime.now(timezone.utc))
    state_changed_by: Optional[str] = None  # Agent or user who changed state
    
    # ========== DOCUMENT & EXTRACTION ==========
    description: Optional[str] = None
    raw_file_url: Optional[str] = None  # Azure Blob Storage URL
    raw_file_blob_name: Optional[str] = None  # Blob name for original file
    file_name: Optional[str] = None
    file_type: Optional[str] = None  # pdf, jpg, png
    file_size: Optional[int] = None  # in bytes
    file_uploaded_at: Optional[datetime] = None
    extracted_data: Optional[Dict[str, Any]] = None  # Parsed OCR data
    extraction_confidence: Optional[float] = None  # 0-1
    qr_codes_data: Optional[list[str]] = None
    
    # ========== User Input & User Details ==========
    user_comments: Optional[str] = None

    # ========== PURCHASE ORDER MATCHING ==========
    has_po: Optional[bool]  = False
    po_number: Optional[str] = None
    po_matched: Optional[bool]  = False
    po_match_confidence: Optional[float] = None
    
    # ========== BUDGET TRACKING ==========
    project_id: Optional[str] = None
    cost_center: Optional[str] = None
    category: Optional[str] = None  # Spending category
    budget_year: Optional[str] = None  # FY2024, FY2025
    budget_allocated: bool = False
    budget_analysis: Optional[str] = None  # Explanation of budget impact

    # ========== VALIDATION & APPROVAL ==========
    validation_passed: bool = False
    approval_required: bool = False
    ai_suggested_approver: Optional[str] = None
    review_status: Optional[ReviewStatus] = ReviewStatus.NOT_REVIEWED
    reviewed_by: Optional[str] = None
    reviewed_date: Optional[datetime] = None    
    rejection_reason: Optional[str] = None

    # ========== Errors ==========
    errors: List[InvoiceInternalMessage] = field(default_factory=list)
    warnings: List[InvoiceInternalMessage] = field(default_factory=list)

    # ========== METADATA & TRACKING ==========
    source: InvoiceSource = InvoiceSource.UPLOAD
    source_email: Optional[str] = None
    source_subject: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Priority = Priority.NORMAL
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    

    def can_transition_to(self, new_state: InvoiceState) -> bool:
        """Check if transition to new state is valid."""
        valid_transitions = {
            InvoiceState.CREATED: [InvoiceState.EXTRACTED, InvoiceState.FAILED],
            InvoiceState.EXTRACTED: [InvoiceState.VALIDATED, InvoiceState.FAILED],
            InvoiceState.VALIDATED: [InvoiceState.BUDGET_CHECKED, InvoiceState.FAILED],
            InvoiceState.BUDGET_CHECKED: [InvoiceState.APPROVED, InvoiceState.MANUAL_REVIEW, InvoiceState.FAILED],
            InvoiceState.APPROVED: [InvoiceState.PAYMENT_SCHEDULED, InvoiceState.FAILED],
            InvoiceState.PAYMENT_SCHEDULED: [InvoiceState.PAID, InvoiceState.FAILED],
            InvoiceState.MANUAL_REVIEW: list(InvoiceState),  # Can go to any state after review
            InvoiceState.FAILED: [InvoiceState.CREATED],  # Can retry
            InvoiceState.PAID: [],  # Terminal state
        }
        return new_state in valid_transitions.get(self.state, [])
    
    def transition_to(self, new_state: InvoiceState) -> None:
        """Transition to a new state if valid."""
        if not self.can_transition_to(new_state):
            raise ValueError(
                f"Invalid state transition from {self.state} to {new_state}"
            )
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)

   
    def to_dict(self) -> dict:
        """Convert Invoice dataclass to dictionary."""
        result = asdict(self)
        result = convert_to_table_entity(result)
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'Invoice':
        """Create Invoice from dictionary, converting TablesEntityDatetime to datetime"""
        converted_data = {}
        for key, value in data.items():
            # Convert TablesEntityDatetime to Python datetime
            if hasattr(value, '__class__') and 'TablesEntityDatetime' in value.__class__.__name__:
                converted_data[key] = datetime.fromisoformat(value.isoformat())
            else:
                converted_data[key] = value
        
        return cls(**converted_data)

