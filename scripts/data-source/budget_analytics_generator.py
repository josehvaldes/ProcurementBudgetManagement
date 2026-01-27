import json
import random
from datetime import datetime

# Define constants
departments = ["IT", "HR", "FIN", "OPS", "MKT"]
categories = ["Software", "Hardware", "Consulting", "Travel", "Supplies"]
projects = ["PROJ-001", "PROJ-002", "None"]
years = [2024, 2025]
months = [f"{i:02d}" for i in range(1, 13)]

def generate_budget_analytics_data():
    """Generate budget analytics entities for 2024 and 2025"""
    entities = []
    
    for year in years:
        for month in months:
            # Generate combinations to ensure at least 40 entities per month
            for dept in departments:
                for category in categories:
                    for project in projects:
                        # Generate realistic financial data

                        # ramdomly skip some combinations to add variability
                        if random.random() < 0.3:
                            continue

                        # Add seasonality (Q4 spending spike)
                        seasonal_factor = 1.3 if month in [10, 11, 12] else 1.0
                        # Add growth trend (5% YoY)
                        growth_factor = 1.0 + (0.05 * (year - 2024))

                        # Random variation (±20%)
                        variation = random.uniform(0.8, 1.2)

                        invoice_count = random.randint(10, 100)
                        avg_invoice = round(random.uniform(50, 5000), 2)
                        
                        total_spent = round(avg_invoice * invoice_count, 2) * seasonal_factor * growth_factor * variation
                        total_spent = round(total_spent, 2)

                        std_dev = round(avg_invoice * random.uniform(0.1, 0.5), 2)
                        unique_vendors = random.randint(3, 15)
                        largest_invoice = round(avg_invoice * random.uniform(1.5, 4.0), 2)
                        smallest_invoice = round(avg_invoice * random.uniform(0.1, 0.5), 2)
                        
                        entity = {
                            "PartitionKey": f"FY{year}",
                            "RowKey": f"{dept}:{category}:{project}:{year}:{month}",
                            "department_id": dept,
                            "project_id": project,
                            "category": category,
                            "year": year,
                            "month": month,
                            "total_spent": total_spent,
                            "invoice_count": invoice_count,
                            "avg_invoice_amount": avg_invoice,
                            "std_dev": std_dev,
                            "unique_vendors": unique_vendors,
                            "largest_invoice": largest_invoice,
                            "smallest_invoice": smallest_invoice
                        }
                        entities.append(entity)
    
    return entities

def save_entities_to_file(entities, filename="scripts\\data-source\\budget_analytics_data.json"):
    """Save entities to JSON file"""
    with open(filename, 'w') as f:
        json.dump(entities, f, indent=2)
    
    # Also create a summary file with counts
    summary = {
        "total_entities": len(entities),
        "entities_per_month": len(entities) // 24,  # 24 months total
        "years_covered": ["2024", "2025"],
        "departments": departments,
        "categories": categories,
        "projects": projects
    }

    with open("scripts\\data-source\\budget_analytics_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Generated {len(entities)} entities")
    print(f"Entities per month: {len(entities) // 24}")
    print(f"Saved to {filename}")

if __name__ == "__main__":
    print("Generating budget analytics data...")
    entities = generate_budget_analytics_data()
    save_entities_to_file(entities)
    
    # Print first few entities as sample
    print("\nSample entities:")
    for entity in entities[:3]:
        print(json.dumps(entity, indent=2))