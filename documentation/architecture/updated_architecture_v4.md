# Procurement & Budget Management Automation

## Overview

A company's procurement/purchasing department makes regular purchases (office supplies, equipment, services). Finance needs to:

- Process invoices from vendors
- Validate against procurement policies (spending limits, approved vendors)
- Track spending across departments/projects
- Monitor budget utilization vs. allocation
- Identify spending patterns and cost-saving opportunities

## Architecture Pattern

### Event-Driven Choreography Pattern

This project uses a **choreography pattern** where agents independently react to state changes without central orchestration. Each agent:

- Subscribes to specific invoice state messages via Azure Service Bus
- Processes invoices when their trigger state is detected
- Updates the invoice state, triggering the next agent
- Operates independently with no knowledge of other agents

### Key Benefits

- **High decoupling** - agents are independent services
- **Easy scalability** - each agent can scale independently
- **Fault isolation** - one agent failure doesn't cascade
- **Simple extension** - new agents can be added by subscribing to messages
- **Local development** - agents can run on local machines while connected to cloud Service Bus

## Technology Stack

### Core Infrastructure

**Azure Service Bus (Topic/Subscription Pattern)**
- Single Topic: "invoice-events" for all state change messages
- Each agent has its own Subscription with SQL filters
- Messages have subject property (invoice.created, invoice.extracted, etc.)
- Built-in durability, retry logic, and dead-letter queues
- Pull-based model: agents fetch messages at their own pace
- Supports local development without deployment

**Azure Blob Storage** ⭐
- **Primary file storage for invoice documents** (PDFs, images, receipts)
- Hierarchical organization: `{year}/{month}/{department}/{invoice_id}.{ext}`
- SAS token generation for secure, time-limited file access
- Lifecycle policies for automatic cost optimization (Cool/Archive tiers)
- No file size limitations (up to 190.7 TB per blob)
- Cost-effective: ~$0.018 per GB/month

**Azure Storage Account (Tables)**
- Invoice **metadata** and state information (not raw files) ⭐
- Vendor information
- Budget allocations
- Audit trails
- Cost-effective for high-volume transactions
- Fast queries on structured data

**Python Multiprocessing**
- Each agent runs in its own process
- Managed by a single container for development/MVP
- Can be scaled to separate containers for production
- Isolated memory space per agent

### AI/ML Stack

**LangChain**
- Agent development (ReAct, conversational agents)
- LLM integrations (Azure OpenAI, Anthropic Claude)
- Tool/function calling for external system integration
- Prompt templates and chain composition
- Memory and context management

**LangSmith**
- Agent execution tracing
- Performance monitoring
- Debugging and troubleshooting
- Cost tracking per agent
- Production monitoring and alerts

### OCR and Image Processing

**Azure Document Intelligence**
- Analysis of PDF invoices (prebuilt Invoice model)
- Analysis of photo receipts: JPG, PNG formats (prebuilt Receipt model)
- Scanning POS receipts (printed and handwritten)
- Extracts key fields: vendor, date, amount, line items, tax, etc.
- Handles various document qualities and formats

**pyzbar for QR Scanning**
- Scan QR codes from receipts
- Extract URL to validate receipts against vendor systems
- Pre-processing step before or after Document Intelligence extraction

### Email Integration

**Azure Logic Apps**
- Monitors Outlook.com / Office 365 inbox
- Triggers on new email arrival with attachments
- Filters emails based on subject, sender, attachment type
- Extracts invoice attachments (PDF, JPG, PNG)
- Calls unified API endpoint with invoice data

**Microsoft Graph API**
- Provides email access via OAuth 2.0
- Enables programmatic inbox monitoring
- Supports Outlook.com and Office 365 accounts
- Managed Identity authentication for security

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│              INPUT CONNECTORS                           │
│  • Email Listener (Azure Logic Apps + Graph API)       │
│    - Monitors Outlook.com inbox                         │
│    - Extracts attachments (PDF, JPG, PNG)              │
│    - Calls unified API endpoint                         │
│  • Web Form (manual upload interface)                   │
│  • Direct API (external system integration)             │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│              UNIFIED API ENDPOINT                       │
│  • Authenticate request                                 │
│  • Validate payload and file                            │
│  • Upload file to Azure Blob Storage ⭐                 │
│  • Store metadata in Azure Tables ⭐                    │
│  • Set state = CREATED                                  │
│  • Publish message to Service Bus Topic                 │
│  • Return 202 Accepted with invoice_id                  │
└─────────────────────────────────────────────────────────┘
           ↓                              ↓
    ┌──────────────┐              ┌──────────────┐
    │ BLOB STORAGE │              │ TABLE STORAGE│
    │              │              │              │
    │ invoices/    │              │ invoices     │
    │ ├─2024/      │              │ ├─metadata   │
    │ │ ├─12/      │              │ ├─state      │
    │ │   ├─IT/    │              │ └─blob_ref ⭐│
    │ │   └─HR/    │              │              │
    │ └─2025/      │              │ vendors      │
    │              │              │ budgets      │
    └──────────────┘              └──────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│         AZURE SERVICE BUS NAMESPACE                     │
│                                                         │
│   ┌─────────────────────────────────────────────┐     │
│   │  Topic: "invoice-events"                    │     │
│   │                                             │     │
│   │  Messages by Subject:                       │     │
│   │  • invoice.created                          │     │
│   │  • invoice.extracted                        │     │
│   │  • invoice.validated                        │     │
│   │  • invoice.budget_checked                   │     │
│   │  • invoice.approved                         │     │
│   │  • invoice.payment_scheduled                │     │
│   │  • invoice.paid                             │     │
│   │  • invoice.failed                           │     │
│   └──────────┬──────────────────────────────────┘     │
│              │                                          │
│     ┌────────────┼────────────┬──────────┬─────────    │
│     ↓            ↓            ↓          ↓         ↓   │
│  ┌──────┐    ┌──────┐    ┌──────┐   ┌──────┐  ┌─────┐│
│  │ Sub: │    │ Sub: │    │ Sub: │   │ Sub: │  │Sub: ││
│  │intake│    │valid │    │budget│   │approv│  │etc  ││
│  │      │    │      │    │      │   │      │  │     ││
│  │SQL:  │    │SQL:  │    │SQL:  │   │SQL:  │  │SQL: ││
│  │subj= │    │subj= │    │subj= │   │subj= │  │all  ││
│  │created    │extrac│    │valid │   │budget│  │     ││
│  └──────┘    └──────┘    └──────┘   └──────┘  └─────┘│
└─────────────────────────────────────────────────────────┘
     ↓            ↓            ↓          ↓         ↓
┌─────────┐  ┌─────────┐  ┌─────────┐ ┌─────────┐ ┌────────┐
│ INTAKE  │  │VALIDATN │  │ BUDGET  │ │APPROVAL │ │ANALYTICS│
│ AGENT   │  │ AGENT   │  │ AGENT   │ │ AGENT   │ │ AGENT  │
│         │  │         │  │         │ │         │ │        │
│Downloads│  │(queries │  │(queries │ │(queries │ │(queries│
│file from│  │ tables) │  │ tables) │ │ tables) │ │ all)   │
│blob ⭐  │  │         │  │         │ │         │ │        │
│         │  │         │  │         │ │         │ │        │
│(local   │  │(local   │  │(local   │ │(local   │ │(local  │
│ or      │  │ or      │  │ or      │ │ or      │ │ or     │
│ cloud)  │  │ cloud)  │  │ cloud)  │ │ cloud)  │ │ cloud) │
└─────────┘  └─────────┘  └─────────┘ └─────────┘ └────────┘
```

### Detailed Agent Flow

```
┌─────────────────────────────────────────────────────────┐
│              INTAKE AGENT                               │
│  Subscription: intake-agent-subscription                │
│  Filter: subject = 'invoice.created'                    │
│  • Pull messages from subscription                      │
│  • Get invoice metadata from Table Storage ⭐           │
│  • Download file from Blob Storage using blob_name ⭐   │
│  • Extract data using Document Intelligence             │
│  • Identify vendor                                      │
│  • Update metadata in Table Storage → EXTRACTED         │
│  • Publish message: subject='invoice.extracted'         │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│              VALIDATION AGENT                           │
│  Subscription: validation-agent-subscription            │
│  Filter: subject = 'invoice.extracted'                  │
│  • Query invoice metadata from Table Storage ⭐         │
│  • Verify against approved vendor list                  │
│  • Check spending authority limits                      │
│  • Validate pricing (compare to catalog)                │
│  • Flag duplicate invoices                              │
│  • Check contract compliance                            │
│  • Update state → VALIDATED                             │
│  • Publish message: subject='invoice.validated'         │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│              BUDGET TRACKING AGENT                      │
│  Subscription: budget-agent-subscription                │
│  Filter: subject = 'invoice.validated'                  │
│  • Allocate to department/project budget                │
│  • Check remaining budget availability                  │
│  • Calculate % budget consumed                          │
│  • Flag over-budget scenarios                           │
│  • Update state → BUDGET_CHECKED                        │
│  • Publish message: subject='invoice.budget_checked'    │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│              APPROVAL AGENT                             │
│  Subscription: approval-agent-subscription              │
│  Filter: subject = 'invoice.budget_checked'             │
│  • Auto-approve if within policy                        │
│  • Route to dept manager if needed                      │
│  • Escalate if over budget                              │
│  • Update state → APPROVED                              │
│  • Publish message: subject='invoice.approved'          │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│              PAYMENT AGENT                              │
│  Subscription: payment-agent-subscription               │
│  Filter: subject = 'invoice.approved'                   │
│  • Schedule payment (net-30, net-60)                    │
│  • Generate payment batch                               │
│  • Send remittance to vendor                            │
│  • Update state → PAYMENT_SCHEDULED                     │
│  • Publish message: subject='invoice.payment_scheduled' │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│              ANALYTICS AGENT                            │
│  Subscription: analytics-agent-subscription             │
│  Filter: (no filter - receives ALL messages)            │
│  • Compare spending vs. last month/year                 │
│  • Identify spending trends                             │
│  • Flag anomalies (sudden spikes)                       │
│  • Generate cost-saving insights                        │
│  • Forecast budget burn rate                            │
│  (Runs in parallel, doesn't block main flow)            │
└─────────────────────────────────────────────────────────┘
```

## Data Storage Strategy ⭐

### Why Blob Storage + Table Storage?

**Problem:** Azure Table Storage has a 1 MB entity size limit, but invoice files are typically 100KB-5MB+

**Solution:** Separation of concerns
- **Blob Storage:** Large binary files (PDFs, images, receipts)
- **Table Storage:** Structured metadata, state, relationships

**Benefits:**
- No size limitations on invoice files
- Faster table queries (smaller entities)
- Cost optimization (blob lifecycle policies)
- Better security (SAS tokens for file access)
- Scalable architecture

### Blob Storage Structure

**Container:** `invoices`

**Naming Convention:** `{year}/{month}/{department}/{invoice_id}.{extension}`

```
invoices/
├── 2024/
│   ├── 12/
│   │   ├── IT/
│   │   │   ├── 550e8400-e29b-41d4-a716-446655440000.pdf
│   │   │   ├── 660e8401-e29b-41d4-a716-446655440001.jpg
│   │   │   └── 770e8402-e29b-41d4-a716-446655440002.png
│   │   ├── HR/
│   │   │   └── 880e8403-e29b-41d4-a716-446655440003.pdf
│   │   └── FINANCE/
│   │       └── 990e8404-e29b-41d4-a716-446655440004.pdf
│   └── 11/
│       └── IT/
│           └── aa0e8405-e29b-41d4-a716-446655440005.pdf
└── 2025/
    └── 01/
        └── IT/
            └── bb0e8406-e29b-41d4-a716-446655440006.pdf
```

**Benefits:**
- Logical organization by time and department
- Easy cleanup (delete old years)
- Efficient queries by time period
- Clear audit trail

### Table Storage: Invoice Metadata

**Key Change:** Store blob reference instead of raw file data

```python
{
    "PartitionKey": "IT",
    "RowKey": "550e8400-e29b-41d4-a716-446655440000",
    
    # Blob Storage references (NEW) ⭐
    "raw_file_url": "https://storage.blob.core.windows.net/invoices/2024/12/IT/550e8400.pdf",
    "raw_file_blob_name": "2024/12/IT/550e8400-e29b-41d4-a716-446655440000.pdf",
    "file_type": "pdf",
    "file_size_bytes": 245678,
    "file_upload_date": "2024-12-15T10:30:00Z",
    
    # Metadata (unchanged)
    "invoice_number": "INV-2024-001234",
    "vendor_name": "Tech Supplies Inc.",
    "amount": 1250.00,
    "state": "CREATED",
    "extracted_data": "{...}",  # Small JSON, stored in table
    # ... other metadata fields
}
```

## Invoice State Machine

```
CREATED → EXTRACTED → VALIDATED → BUDGET_CHECKED → APPROVED → PAYMENT_SCHEDULED → PAID

                                    ↓ (at any stage)
                                  FAILED / MANUAL_REVIEW
```

### Valid State Transitions

- CREATED → EXTRACTED, FAILED
- EXTRACTED → VALIDATED, FAILED
- VALIDATED → BUDGET_CHECKED, FAILED
- BUDGET_CHECKED → APPROVED, MANUAL_REVIEW, FAILED
- APPROVED → PAYMENT_SCHEDULED, FAILED
- PAYMENT_SCHEDULED → PAID, FAILED
- MANUAL_REVIEW → (any previous state after human intervention)

## Data Model (Azure Tables)

### Invoices Table
**PartitionKey:** department_id  
**RowKey:** InvoiceID (UUID)

Fields:
- **raw_file_url:** string - Full URL to blob in storage ⭐
- **raw_file_blob_name:** string - Blob path for management operations ⭐
- **file_type:** string - File extension (pdf, jpg, png) ⭐
- **file_size_bytes:** int - Original file size ⭐
- **file_upload_date:** datetime - When file was uploaded ⭐
- vendor_id: string
- vendor_name: string
- total_amount: decimal
- currency: string
- state: string (enum)
- created_at: datetime
- updated_at: datetime
- extracted_data: json (parsed fields - small JSON, stored in table)
- flags: array (warnings, exceptions)
- assigned_to: string (for manual review)
- department_id: string
- project_id: string
- has_po: bool (for future use - not validated)
- po_number: Optional[str] (for future use - not validated)
- po_matched: bool (for future use - not validated)
- po_match_confidence: Optional[float] (for future use - not validated)

### Vendors Table
**PartitionKey:** "VENDOR"  
**RowKey:** VendorID (UUID)

Fields:
- name: string
- approved: boolean
- contact_info: json
- payment_terms: string (net-30, net-60)
- contracts: array
- tax_id: string
- address: string
- spend_limit: decimal

### Budgets Table
**PartitionKey:** FiscalYear (e.g., "FY2024")  
**RowKey:** Department:Project;Category (e.g., "IT:PROJ-01:Software")

Fields:
- department_id: string
- project_id: string
- category: string
- allocated_amount: decimal
- consumed_amount: decimal
- remaining_amount: decimal
- period_start: date
- period_end: date
- last_updated: datetime

### AuditLog Table
**PartitionKey:** InvoiceID  
**RowKey:** Timestamp-AgentName

Fields:
- agent_name: string
- action: string
- old_state: string
- new_state: string
- details: json
- timestamp: datetime

## Agent Implementation

### Storage Service Helper Class ⭐

```python
class InvoiceStorageService:
    """
    Manages invoice file storage in Azure Blob Storage.
    Handles uploads, downloads, SAS URL generation, and file lifecycle.
    """
    
    def __init__(self):
        """Initialize Blob Service Client with connection string from environment"""
        pass
    
    def upload_invoice_file(
        self, 
        invoice_id: str, 
        department_id: str, 
        file_content: bytes, 
        file_extension: str
    ) -> dict:
        """
        Upload invoice file to Blob Storage with hierarchical naming.
        
        Args:
            invoice_id: Unique invoice identifier (UUID)
            department_id: Department code (IT, HR, FINANCE)
            file_content: Binary file content
            file_extension: File extension (pdf, jpg, png)
            
        Returns:
            dict: {
                "blob_url": str - Full URL to blob,
                "blob_name": str - Blob path (year/month/dept/id.ext),
                "file_size": int - Size in bytes
            }
        """
        pass
    
    def download_invoice_file(self, blob_name: str) -> bytes:
        """
        Download invoice file from Blob Storage.
        
        Args:
            blob_name: Blob path (from raw_file_blob_name in table)
            
        Returns:
            bytes: File content
        """
        pass
    
    def get_sas_url(self, blob_name: str, expiry_hours: int = 1) -> str:
        """
        Generate temporary SAS URL for secure file access.
        Used for providing download links to users/systems.
        
        Args:
            blob_name: Blob path
            expiry_hours: Hours until URL expires (default 1)
            
        Returns:
            str: Full URL with SAS token
        """
        pass
    
    def delete_invoice_file(self, blob_name: str) -> None:
        """
        Delete invoice file from Blob Storage.
        Used for cleanup or compliance deletions.
        
        Args:
            blob_name: Blob path to delete
        """
        pass
```

### Updated API Endpoint ⭐

```python
@app.post("/api/invoices")
async def create_invoice(
    file: UploadFile = File(...),
    department_id: str = Form(...),
    source: str = Form("api")
):
    """
    Create new invoice with file upload.
    
    Process:
    1. Upload file to Blob Storage
    2. Store metadata in Table Storage with blob reference
    3. Publish message to Service Bus
    4. Return 202 Accepted
    
    Args:
        file: Uploaded invoice file (PDF, JPG, PNG)
        department_id: Department code
        source: Invoice source (api, email, web)
        
    Returns:
        {"invoice_id": str, "status": "CREATED"}
    """
    pass
```

### Updated Intake Agent ⭐

```python
@traceable(run_type="chain", name="intake_agent_process")
def process_invoice(invoice_id: str, department_id: str):
    """
    Process invoice with Document Intelligence.
    
    Process:
    1. Get invoice metadata from Table Storage
    2. Download file from Blob Storage using blob_name
    3. Send to Document Intelligence for extraction
    4. Update metadata in Table Storage with extracted data
    5. Publish message to next agent
    
    Args:
        invoice_id: Invoice UUID
        department_id: Department code (for table partition key)
    """
    pass
```

## Blob Storage Lifecycle Management ⭐

### Cost Optimization Strategy

Azure Blob Storage lifecycle policies automatically move files between storage tiers based on age:

**Storage Tiers:**
- **Hot:** $0.018/GB/month - Active invoices (0-90 days)
- **Cool:** $0.01/GB/month - Recent history (91-365 days)
- **Archive:** $0.002/GB/month - Compliance storage (366+ days)

**Lifecycle Policy:**
```json
{
  "rules": [
    {
      "name": "OptimizeInvoiceStorage",
      "type": "Lifecycle",
      "definition": {
        "filters": {
          "blobTypes": ["blockBlob"],
          "prefixMatch": ["invoices/"]
        },
        "actions": {
          "baseBlob": {
            "tierToCool": {
              "daysAfterModificationGreaterThan": 90
            },
            "tierToArchive": {
              "daysAfterModificationGreaterThan": 365
            },
            "delete": {
              "daysAfterModificationGreaterThan": 2555
            }
          }
        }
      }
    }
  ]
}
```

**Actions:**
- Day 0-90: Hot tier (active processing)
- Day 91-365: Cool tier (recent history queries)
- Day 366-2555: Archive tier (7-year compliance retention)
- Day 2555+: Delete (adjust per compliance requirements)

**Savings Example:**
- 10,000 invoices/year × 500KB average = 5GB/year
- Year 1: $1.08/year (Hot)
- Years 2-7: $0.60/year (Cool) + $0.12/year (Archive)
- **Total 7-year cost: ~$4.50** vs. **$7.50 all-hot**
- **40% cost reduction** with lifecycle policies

## Security Considerations

### Blob Storage Security ⭐

- **SAS Tokens:** Time-limited access URLs (1-24 hours)
- **Access Levels:** Private container (no anonymous access)
- **Encryption at Rest:** Automatic (AES-256)
- **Encryption in Transit:** HTTPS required
- **Audit Logging:** All blob operations logged to Azure Monitor
- **RBAC:** Role-based access control for management operations
- **Immutable Storage:** Optional for compliance (WORM - Write Once Read Many)

### API and Tables Security

- API authentication via Azure AD
- Service Bus uses Managed Identity or connection strings (Key Vault)
- Storage account access via connection strings (Key Vault)
- LLM API keys stored in Azure Key Vault
- Audit logging for all state changes
- Row-level security on sensitive invoice data
- Message encryption in transit and at rest

## Performance Targets

- Invoice intake: < 5 seconds (including blob upload)
- Full pipeline (CREATED → APPROVED): < 2 minutes for auto-approved
- Message delivery latency: < 1 second
- Agent processing time: < 30 seconds per invoice
- Blob upload: < 2 seconds for files up to 5MB
- Blob download: < 1 second for typical invoices
- System throughput: 1000+ invoices/hour
- 99.9% uptime SLA

## Monitoring & Observability

### LangSmith Dashboard

- Agent execution traces
- Token usage per agent
- Latency metrics
- Error rates
- Cost tracking

### Azure Monitor

- Service Bus metrics (message delivery rate, active messages, dead letters)
- Storage account metrics (read/write operations)
- **Blob Storage metrics** ⭐
  - Upload/download success rates
  - Latency percentiles (p50, p95, p99)
  - Storage consumption by tier
  - Cost per tier
- Container metrics (CPU, memory usage)

### Service Bus Metrics

- Messages per subscription
- Message processing time
- Dead letter queue depth
- Active message count

### Custom Metrics

- Invoice processing time (end-to-end)
- Agent-specific processing time
- State transition rates
- Exception/flag rates
- Budget utilization alerts
- **File storage metrics** ⭐
  - Average file size
  - Storage growth rate
  - Lifecycle transitions

### Alerting

- Failed invoice processing (dead letter queue depth)
- Budget overruns
- Agent failures (no heartbeat)
- Unusual spending patterns
- Payment deadline misses
- **Blob storage alerts** ⭐
  - Upload failures
  - High storage costs
  - Unusual file sizes

## Error Handling Strategy

### Service Bus Built-in Features

- Maximum delivery count: 10 attempts
- Message lock duration: 5 minutes
- Dead letter queue: automatic routing after max retries
- Duplicate detection: optional based on MessageId

### Blob Storage Error Handling ⭐

```python
try:
    storage_service.upload_invoice_file(...)
except BlobStorageError as e:
    # Log error
    # Mark invoice as FAILED
    # Store error details in invoice entity
    # Publish failure message
    pass
```

**Common Scenarios:**
- Network timeout → Retry upload
- Storage quota exceeded → Alert operations team
- Corrupted file → Mark as failed, notify user
- Permission denied → Check SAS token/credentials

### Agent Error Handling

```python
try:
    process_invoice(invoice_id)
    receiver.complete_message(message)  # Success
except ValidationError as e:
    # Temporary error - retry
    receiver.abandon_message(message)
except FatalError as e:
    # Permanent error - send to dead letter
    receiver.dead_letter_message(message, reason="FatalError")
    # Update invoice state to FAILED
    invoice['state'] = 'FAILED'
    table_client.update_entity("invoices", invoice)
```

## Deployment Architecture

### Development/MVP (Weeks 1-4) - Local + Cloud Hybrid

```
┌─────────────────────────────────────────────────────────┐
│         LOCAL DEVELOPMENT MACHINE                       │
│                                                         │
│  Terminal 1: API Server (FastAPI)                      │
│    └─> uvicorn api.main:app --reload                   │
│                                                         │
│  Terminal 2: run_agents.py                             │
│    ├─> Process 1: Intake Agent                         │
│    ├─> Process 2: Validation Agent                     │
│    ├─> Process 3: Budget Agent                         │
│    ├─> Process 4: Approval Agent                       │
│    ├─> Process 5: Payment Agent                        │
│    └─> Process 6: Analytics Agent                      │
│                                                         │
│  All processes connect to Azure via SDK                │
└─────────────────────────────────────────────────────────┘
         ↓              ↓              ↓              ↓
    Service Bus    Blob Storage   Table Storage   OpenAI
    (cloud)        (cloud)        (cloud)         (cloud)
```

### Production (Weeks 5-7+) - Separate Containers

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ API Container│  │Intake Agent  │  │Validation    │
│              │  │  Container   │  │  Container   │
└──────────────┘  └──────────────┘  └──────────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│Budget Agent  │  │Approval Agent│  │Payment Agent │
│  Container   │  │  Container   │  │  Container   │
└──────────────┘  └──────────────┘  └──────────────┘

┌──────────────┐
│Analytics     │
│  Container   │
└──────────────┘

All deployed to Azure Container Instances or Kubernetes
```

## Service Bus Configuration

### Topic Configuration
```bash
az servicebus topic create \
  --name invoice-events \
  --namespace-name procurement-sb \
  --max-size 5120 \
  --default-message-time-to-live P14D \
  --enable-duplicate-detection true \
  --duplicate-detection-history-time-window PT10M
```

### Subscription Configuration (Example: Intake Agent)
```bash
az servicebus topic subscription create \
  --name intake-agent-subscription \
  --topic-name invoice-events \
  --namespace-name procurement-sb \
  --max-delivery-count 10 \
  --lock-duration PT5M \
  --enable-dead-lettering-on-message-expiration true

az servicebus topic subscription rule create \
  --name InvoiceCreatedFilter \
  --topic-name invoice-events \
  --subscription-name intake-agent-subscription \
  --namespace-name procurement