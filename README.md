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

**Azure Storage Account (Tables)**
- Invoice data and metadata
- Vendor information
- Budget allocations
- Audit trails
- Cost-effective for high-volume transactions

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
│  • Validate payload                                     │
│  • Store raw invoice in Azure Tables                    │
│  • Set state = CREATED                                  │
│  • Publish message to Service Bus Topic                 │
│  • Return 202 Accepted                                  │
└─────────────────────────────────────────────────────────┘
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
│              │                                      │
│     ┌────────────┼────────────┬──────────┬─────────  │
│     ↓            ↓            ↓          ↓         ↓  │
│  ┌──────┐    ┌──────┐    ┌──────┐   ┌──────┐  ┌────┤│
│  │ Sub: │    │ Sub: │    │ Sub: │   │ Sub: │  │Sub:││
│  │intake│    │valid │    │budget│   │approv│  │etc ││
│  │      │    │      │    │      │   │      │  │    ││
│  │SQL:  │    │SQL:  │    │SQL:  │   │SQL:  │  │SQL:││
│  │subj= │    │subj= │    │subj= │   │subj= │  │all ││
│  │created    │extrac│    │valid │   │budget│  │    ││
│  └──────┘    └──────┘    └──────┘   └──────┘  └────┘│
└─────────────────────────────────────────────────────────┘
     ↓            ↓            ↓          ↓         ↓
┌─────────┐  ┌─────────┐  ┌─────────┐ ┌─────────┐ ┌────────┐
│ INTAKE  │  │VALIDATN │  │ BUDGET  │ │APPROVAL │ │ANALYTICS│
│ AGENT   │  │ AGENT   │  │ AGENT   │ │ AGENT   │ │ AGENT  │
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
│  • Extract data using Document Intelligence             │
│  • Identify vendor                                      │
│  • Update state → EXTRACTED                             │
│  • Publish message: subject='invoice.extracted'         │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│              VALIDATION AGENT                           │
│  Subscription: validation-agent-subscription            │
│  Filter: subject = 'invoice.extracted'                  │
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
