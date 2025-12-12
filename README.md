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

- Subscribes to specific invoice state events
- Processes invoices when their trigger state is detected
- Updates the invoice state, triggering the next agent
- Operates independently with no knowledge of other agents

### Key Benefits

- **High decoupling** - agents are independent services
- **Easy scalability** - each agent can scale independently
- **Fault isolation** - one agent failure doesn't cascade
- **Simple extension** - new agents can be added by subscribing to events

## Technology Stack

### Core Infrastructure

**Azure Event Grid**
- Publishes state change events (invoice.created, invoice.extracted, etc.)
- Agents subscribe to relevant event types
- Handles event delivery, retries, and dead-lettering
- Built-in durability and at-least-once delivery

**Azure Storage Account (Tables)**
- Invoice data and metadata
- Vendor information
- Purchase orders
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

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│              INPUT CONNECTORS                           │
│  • Email Listener (monitors inbox)                      │
│  • Web Form (manual upload interface)                   │
│  • Direct API (external system integration)             │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│              UNIFIED API ENDPOINT                       │
│  • Authenticate request                                 │
│  • Validate payload                                     │
│  • Store raw invoice in Azure Tables                    │
│  • Set state = CREATED                                  │
│  • Publish "invoice.created" to Azure Event Grid        │
│  • Return 202 Accepted                                  │
└─────────────────────────────────────────────────────────┘
                       ↓
              [Azure Event Grid]
                       ↓
        ┌──────────────┴──────────────┐
        ↓                             ↓
┌──────────────────┐          ┌──────────────────┐
│  INTAKE AGENT    │          │  Other Agents    │
│  Subscribes to:  │          │  (listening but  │
│  invoice.created │          │   not reacting)  │
└────────┬─────────┘          └──────────────────┘
         ↓
    Processes invoice
    Extracts data
    Updates state → EXTRACTED
    Publishes "invoice.extracted"
         ↓
┌─────────────────────────────────────────────────────────┐
│              VALIDATION AGENT                           │
│  Subscribes to: invoice.extracted                       │
│  • Verify against approved vendor list                  │
│  • Check spending authority limits                      │
│  • Validate pricing (compare to catalog)                │
│  • Flag duplicate invoices                              │
│  • Check contract compliance                            │
│  Updates state → VALIDATED                              │
│  Publishes "invoice.validated"                          │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│              BUDGET TRACKING AGENT                      │
│  Subscribes to: invoice.validated                       │
│  • Allocate to department/project budget                │
│  • Check remaining budget availability                  │
│  • Calculate % budget consumed                          │
│  • Flag over-budget scenarios                           │
│  Updates state → BUDGET_CHECKED                         │
│  Publishes "invoice.budget_checked"                     │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│              APPROVAL AGENT                             │
│  Subscribes to: invoice.budget_checked                  │
│  • Auto-approve if within policy                        │
│  • Route to dept manager if needed                      │
│  • Escalate if over budget                              │
│  Updates state → APPROVED                               │
│  Publishes "invoice.approved"                           │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│              PAYMENT AGENT                              │
│  Subscribes to: invoice.approved                        │
│  • Schedule payment (net-30, net-60)                    │
│  • Generate payment batch                               │
│  • Send remittance to vendor                            │
│  Updates state → PAYMENT_SCHEDULED                      │
│  Publishes "invoice.payment_scheduled"                  │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│              ANALYTICS AGENT                            │
│  Subscribes to: invoice.* (all events)                  │
│  • Compare spending vs. last month/year                 │
│  • Identify spending trends                             │
│  • Flag anomalies (sudden spikes)                       │
│  • Generate cost-saving insights                        │
│  • Forecast budget burn rate                            │
│  (Runs in parallel, doesn't block main flow)            │
└─────────────────────────────────────────────────────────┘
```