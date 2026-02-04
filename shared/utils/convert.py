from datetime import datetime
from enum import Enum
import json


def convert_to_table_entity(data: dict) -> dict:
    """Convert complex types to Azure Table Storage compatible types."""
    entity = {}
    for key, value in data.items():
        if value is None:
            entity[key] = None
        elif isinstance(value, Enum):
            entity[key] = value.value
        elif isinstance(value, (list, dict)):
            entity[key] = json.dumps(value, default=str)
        elif isinstance(value, datetime):
            entity[key] = value
        elif isinstance(value, (str, int, float, bool, bytes)):
            entity[key] = value
        else:
            entity[key] = str(value)
    return entity