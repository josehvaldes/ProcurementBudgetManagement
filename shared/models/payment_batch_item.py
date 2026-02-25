


from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum

from shared.utils.convert import convert_to_table_entity


class PaymentState(str, Enum):
    SCHEDULED = "Scheduled"
    PROCESSED = "Processed"
    FAILED = "Failed"

@dataclass
class PaymentBatchItem:
    invoice_id: str
    department_id: str
    payment_date: datetime
    amount: float
    currency: str
    vendor_id: str
    vendor_name: str
    payment_method: str
    state: PaymentState
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        """Convert Invoice dataclass to dictionary."""
        result = asdict(self)
        result = convert_to_table_entity(result)
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'PaymentBatchItem':
        """Create Invoice from dictionary, converting TablesEntityDatetime to datetime"""
        converted_data = {}
        for key, value in data.items():
            # Convert TablesEntityDatetime to Python datetime
            if hasattr(value, '__class__') and 'TablesEntityDatetime' in value.__class__.__name__:
                converted_data[key] = datetime.fromisoformat(value.isoformat())
            else:
                converted_data[key] = value
        
        return cls(**converted_data)

