

from dataclasses import dataclass, asdict
from datetime import datetime
from shared.utils.convert import convert_to_table_entity

@dataclass
class OutboxMessage:
    agent_name: str
    compound_key: str  # Unique identifier for the message (could be a combination of event type and timestamp)
    invoice_id: str
    department_id: str
    state: str
    event_type: str
    subject: str
    correlation_id: str

    def to_dict(self) -> dict:
        """Convert OutboxMessage dataclass to dictionary."""
        result = asdict(self)
        result = convert_to_table_entity(result)
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> 'OutboxMessage':
        """Create OutboxMessage from dictionary, converting TablesEntityDatetime to datetime"""
        converted_data = {}
        for key, value in data.items():
            # Convert TablesEntityDatetime to Python datetime
            if hasattr(value, '__class__') and 'TablesEntityDatetime' in value.__class__.__name__:
                converted_data[key] = datetime.fromisoformat(value.isoformat())
            else:
                converted_data[key] = value
        
        return cls(**converted_data)