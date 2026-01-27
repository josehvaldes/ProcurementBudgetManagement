##
departments = ["IT", "HR", "FIN", "OPS"]
categories = ["Software", "Hardware", "Consulting", "Travel", "Supplies"]
projects = ["PROJ-001", "PROJ-002", "None"]  # None = no project
    

```python
budget_analytics table:

"PartitionKey": str
"RowKey": str
"department_id": str
"project_id": str
"category": str
"Year": str # YYYY
"month": str # MM
"total_spent": float 
"invoice_count": int 
"avg_invoice_amount": float
"std_dev": float
"unique_vendors": int
"largest_invoice": float
"smallest_invoice": float
```

```json sample
Sample:
{
    "PartitionKey": "FY2024",
    "RowKey": "IT:Software:2021:01:PROJ-01",
    "department_id": "IT",
    "project_id": "PROJ-01",
    "category": "Software",    
    "year": "2024",
    "month": "01",
    "total_spent": 12500.00,
    "invoice_count": 45,
    "avg_invoice_amount": 277.78,
    "std_dev": 125.50,
    "unique_vendors": 8,
    "largest_invoice": 1250.00,
    "smallest_invoice": 45.00
}

```