"""
Vendor domain model.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import json
from typing import Optional, List, Dict, Any
from enum import Enum
from shared.utils.convert import convert_to_table_entity

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
    status: Optional[str] = None  # active, expired, terminated

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VendorContract':
        """Populate VendorContract fields from a dictionary."""
        return cls(**data)

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
    address: Optional[str] = None
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
    created_date: datetime = field(default_factory= lambda: datetime.now(timezone.utc))
    updated_date: datetime = field(default_factory= lambda: datetime.now(timezone.utc))
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
        self.last_invoice_date = datetime.now(timezone.utc)
        self.updated_date = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Convert Vendor dataclass to dictionary."""
        result = asdict(self)
        result = convert_to_table_entity(result)
        return result
    

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Vendor':
        """Populate Vendor fields from a dictionary."""
        vendor = Vendor(**data)

        bank_account_data = data.get('bank_account', None)
        if bank_account_data:
            bank_data = json.loads(bank_account_data) if isinstance(bank_account_data, str) else bank_account_data
            vendor.bank_account = BankAccount(**bank_data)

        contracts_data = data.get('contracts', "")
        if contracts_data:
            contracts_list = json.loads(contracts_data) if isinstance(contracts_data, str) else contracts_data
            vendor.contracts = [VendorContract(**contract) for contract in contracts_list]

        return vendor
