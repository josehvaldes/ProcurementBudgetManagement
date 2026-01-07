"""
Budget domain model.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum


class BudgetRotation(str, Enum):
    """Budget rotation periods."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class BudgetStatus(str, Enum):
    """Budget status."""
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"

@dataclass
class Budget:
    """
    Budget tracking and management.
    Aligned with Azure Table Storage schema.
    RowKey: department_id-category (e.g., "IT-Software")
    PartitionKey: fiscal_year (e.g., "FY2024")
    """
    
    # ========== IDENTIFICATION ==========
    budget_id: str  # UUID
    fiscal_year: str  # PartitionKey - e.g., "FY2024"
    department_id: str  # Part of RowKey
    department_name: str
    category: str  # Part of RowKey - e.g., "Software", "Hardware"
    
    # ========== BUDGET AMOUNTS ==========
    allocated_amount: Decimal  # Original budget allocation (max_limit)
    consumed_amount: Decimal = Decimal("0.00")  # Amount spent so far
    remaining_amount: Decimal = Decimal("0.00")  # allocated - consumed
    reserved_amount: Decimal = Decimal("0.00")  # Amount in pending invoices
    available_amount: Decimal = Decimal("0.00")  # remaining - reserved
    
    # ========== BUDGET PERIOD ==========
    rotation: BudgetRotation = BudgetRotation.YEARLY
    period_start: datetime = field(default_factory=datetime.now(timezone.utc))
    period_end: datetime = field(default_factory=datetime.now(timezone.utc))
    current_period: Optional[str] = None  # e.g., "Q4-2024", "Dec-2024"
    
    # ========== SPENDING METRICS ==========
    consumption_rate: float = 0.0  # % of budget consumed (0-100)
    burn_rate: Decimal = Decimal("0.00")  # Average spend per period
    projected_total: Optional[Decimal] = None  # Forecast total spend
    projected_overrun: Optional[Decimal] = None  # Projected over-budget amount
    days_remaining: int = 0  # Days left in period
    
    # ========== THRESHOLDS & ALERTS ==========
    warning_threshold: float = 75.0  # % to trigger warning
    critical_threshold: float = 90.0  # % to trigger critical alert
    warning_triggered: bool = False
    critical_triggered: bool = False
    over_budget: bool = False
    alerts_sent: List[str] = field(default_factory=list)
    
    # ========== APPROVAL WORKFLOW ==========
    approval_required_over: Optional[Decimal] = None  # Amount requiring approval
    auto_approve_under: Optional[Decimal] = None  # Amount auto-approved
    approver: Optional[str] = None  # Budget owner/approver
    approver_email: Optional[str] = None
    
    # ========== ROLLOVER & CARRYOVER ==========
    allow_rollover: bool = False  # Can unused budget carry over
    rollover_amount: Optional[Decimal] = None  # Amount rolled from previous period
    rollover_from: Optional[str] = None  # Previous period reference
    
    # ========== TRACKING ==========
    invoice_count: int = 0  # Number of invoices against budget
    last_invoice_date: Optional[datetime] = None  # Most recent invoice
    last_update_by: Optional[str] = None  # Last agent/user update
    
    # ========== METADATA ==========
    created_date: datetime = field(default_factory=datetime.now(timezone.utc))
    updated_date: datetime = field(default_factory=datetime.now(timezone.utc))
    created_by: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    status: BudgetStatus = BudgetStatus.ACTIVE
    
    def calculate_metrics(self) -> None:
        """Calculate budget metrics."""
        # Calculate amounts
        self.remaining_amount = self.allocated_amount - self.consumed_amount
        self.available_amount = self.remaining_amount - self.reserved_amount
        
        # Calculate consumption rate
        if self.allocated_amount > 0:
            self.consumption_rate = float(
                (self.consumed_amount / self.allocated_amount) * 100
            )
        
        # Check if over budget
        self.over_budget = self.available_amount < 0
        
        # Check thresholds
        if self.consumption_rate >= self.critical_threshold:
            self.critical_triggered = True
        elif self.consumption_rate >= self.warning_threshold:
            self.warning_triggered = True
    
   
    def is_over_budget(self) -> bool:
        """Check if budget is exceeded."""
        return self.over_budget
    
    @property
    def utilization_percentage(self) -> float:
        """Get budget utilization percentage."""
        return self.consumption_rate


# Keep BudgetAllocation for backward compatibility
@dataclass
class BudgetAllocation(Budget):
    """Alias for Budget for backward compatibility."""
    pass
