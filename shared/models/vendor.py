"""
Vendor domain model.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum


class VendorSize(str, Enum):
    """Vendor size classification."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


@dataclass
class VendorContract:
    """Vendor contract information."""
    contract_id: str
    contract_start_date: datetime
    contract_end_date: datetime
    contract_value: Decimal
    terms: Optional[str] = None


@dataclass
class VendorAddress:
    """Vendor address information."""
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: str = "USA"


@dataclass
class BankAccount:
    """Bank account information (should be encrypted in storage)."""
    bank_name: Optional[str] = None
    account_number: Optional[str] = None  # Encrypted
    routing_number: Optional[str] = None
    account_type: Optional[str] = None  # checking, savings


@dataclass
class Vendor:
    """
    Vendor domain model aligned with Azure Table Storage schema.
    PartitionKey: "VENDOR" (all vendors in single partition)
    RowKey: vendor_id (UUID)
    """
    
    # ========== IDENTIFICATION ==========
    vendor_id: str  # RowKey - UUID
    name: str  # Legal name
    display_name: Optional[str] = None  # Friendly name
    tax_id: Optional[str] = None  # EIN / Tax ID
    vendor_number: Optional[str] = None  # Internal vendor code
    
    # ========== CONTACT INFORMATION ==========
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[VendorAddress] = None
    website: Optional[str] = None
    
    # ========== APPROVAL & STATUS ==========
    approved: bool = False
    approved_by: Optional[str] = None
    approved_date: Optional[datetime] = None
    active: bool = True
    suspended: bool = False
    suspension_reason: Optional[str] = None
    
    # ========== PAYMENT TERMS ==========
    payment_terms: str = "NET-30"  # net-30, net-60, etc.
    payment_method: Optional[str] = None  # Preferred payment method
    bank_account: Optional[BankAccount] = None  # Encrypted in storage
    currency: str = "USD"
    
    # ========== SPENDING CONTROLS ==========
    spend_limit: Optional[Decimal] = None  # Max per-invoice limit
    monthly_spend_limit: Optional[Decimal] = None  # Monthly cap
    ytd_spend: Decimal = Decimal("0.00")  # Year-to-date spending
    last_invoice_date: Optional[datetime] = None
    total_invoices: int = 0
    
    # ========== CONTRACTS & AGREEMENTS ==========
    contracts: List[VendorContract] = field(default_factory=list)
    contract_start_date: Optional[datetime] = None
    contract_end_date: Optional[datetime] = None
    contract_value: Optional[Decimal] = None
    auto_approve: bool = False  # Auto-approve invoices from vendor
    auto_approve_limit: Optional[Decimal] = None  # Max for auto-approval
    
    # ========== CATEGORIES & TAGS ==========
    categories: List[str] = field(default_factory=list)  # What vendor provides
    tags: List[str] = field(default_factory=list)
    industry: Optional[str] = None
    size: Optional[VendorSize] = None
    
    # ========== PERFORMANCE METRICS ==========
    on_time_delivery_rate: Optional[float] = None  # % of on-time deliveries
    quality_rating: Optional[float] = None  # 1-5 rating
    last_review_date: Optional[datetime] = None
    notes: Optional[str] = None
    
    # ========== METADATA ==========
    created_date: datetime = field(default_factory=datetime.utcnow)
    updated_date: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    
    def can_auto_approve(self, amount: Decimal) -> bool:
        """Check if invoice can be auto-approved for this vendor."""
        if not self.auto_approve or not self.approved or not self.active:
            return False
        if self.auto_approve_limit and amount > self.auto_approve_limit:
            return False
        return True
    
    def is_within_spend_limit(self, amount: Decimal) -> bool:
        """Check if amount is within vendor spend limits."""
        if self.spend_limit and amount > self.spend_limit:
            return False
        return True
    
    def update_spending(self, amount: Decimal) -> None:
        """Update vendor spending metrics."""
        self.ytd_spend += amount
        self.total_invoices += 1
        self.last_invoice_date = datetime.utcnow()
        self.updated_date = datetime.utcnow()
