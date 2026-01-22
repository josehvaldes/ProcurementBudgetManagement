from typing import Final

DEPARTMENT_CATEGORIES: Final[tuple[str, ...]] = (
    "Software", # e.g., SaaS subscriptions
    "Hardware", # e.g., Computers, Servers
    "Consulting", # e.g., External consultants
    "Travel", # e.g., Business trips
    "Marketing", # e.g., Advertising, Promotions
    "Supplies", # e.g., Office supplies
    "Training" # e.g., Employee training programs
)

DEPARTMENT_IDS: Final[tuple[str, ...]] = (
    "IT", # Information Technology
    "HR", # Human Resources
    "FIN", # Financial Department
    "MKT", # Marketing Department
)