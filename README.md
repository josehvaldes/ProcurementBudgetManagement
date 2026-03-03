# Procurement & Budget Management Automation

An event-driven, AI-powered system for automating invoice processing, procurement validation, budget tracking, and payment scheduling. Built with Python, LangChain, and Azure cloud services using a choreography architecture pattern.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Agents](#agents)
- [API Endpoints](#api-endpoints)
- [Invoice Lifecycle](#invoice-lifecycle)
- [Development](#development)
- [Deployment](#deployment)
- [Monitoring & Observability](#monitoring--observability)
- [License](#license)

---

## Overview

A company's procurement/purchasing department makes regular purchases (office supplies, equipment, services). This system automates the finance workflow to:

- **Process invoices** from vendors (PDF, JPG, PNG) via email, web form, or API
- **Extract data** using Azure Document Intelligence (OCR)
- **Validate** against procurement policies (spending limits, approved vendors)
- **Track spending** across departments and projects
- **Monitor budget** utilization vs. allocation
- **Approve and schedule payments** based on configurable rules
- **Identify spending patterns** and cost-saving opportunities

---

## Architecture

### Event-Driven Choreography Pattern

This project uses a **choreography pattern** where agents independently react to invoice state changes without central orchestration:

```
Input Connectors (Email / Web / API)
          ↓
    Unified API Endpoint
     ↙         ↘
Blob Storage   Table Storage
          ↓
   Azure Service Bus
   Topic: "invoice-events"
     ↓    ↓    ↓    ↓    ↓
  Intake  →  Validation  →  Budget  →  Approval   →   Payment
                                         ↓              ↓
                                  Manual Review      Analytics
                                                 (parallel, all events)
```  

Each agent:
- Subscribes to specific invoice state messages via **Azure Service Bus**
- Processes invoices when their trigger state is detected
- Updates the invoice state, triggering the next agent
- Operates independently with no knowledge of other agents

For the full architecture details, see [documentation/architecture/updated_architecture_v4.md](documentation/architecture/updated_architecture_v4.md).

---

## Technology Stack

| Component | Technology |
|---|---|
| **Language** | Python 3.13 |
| **API Framework** | FastAPI |
| **Message Broker** | Azure Service Bus (Topic/Subscription) |
| **File Storage** | Azure Blob Storage |
| **Metadata Store** | Azure Table Storage |
| **OCR / Extraction** | Azure Document Intelligence |
| **AI / LLM** | LangChain + Azure OpenAI |
| **Observability** | LangSmith |
| **Email Integration** | Azure Logic Apps + Microsoft Graph API |
| **Containerization** | Docker |

---

## Project Structure

```
ProcurementBudgetManagement/
├── agents/                        # Agent implementations
│   ├── base_agent.py              # Base agent class with Service Bus integration
│   ├── run_agents.py              # Multiprocessing agent runner
│   ├── analytics_agent/           # Spending analytics & trend detection
│   ├── approval_agent/            # Invoice approval routing
│   ├── budget_agent/              # Budget tracking & allocation
│   ├── intake_agent/              # OCR extraction via Document Intelligence
│   ├── payment_agent/             # Payment scheduling
│   └── validation_agent/          # Policy & vendor validation
├── invoice_lifecycle_api/         # FastAPI application (unified API endpoint)
├── invoice-lifecycle-azure/       # Azure infrastructure & deployment configs
├── invoice-lifecycle-ui/          # Web UI for manual uploads & dashboard
├── shared/                        # Shared utilities and storage services
├── docker/                        # Docker configurations
├── documentation/                 # Architecture docs & design decisions
├── scripts/                       # Setup and utility scripts
├── logs/                          # Application logs
├── dev_server.py                  # Local development server
├── requirements.txt               # Production dependencies
├── requirements-dev.txt           # Development dependencies
├── .env.example                   # Environment variable template
└── README.md
```

---

## Getting Started

### Prerequisites

- **Python 3.13+**
- **Azure Subscription** with the following resources provisioned:
  - Azure Service Bus Namespace (with topic `invoice-events`)
  - Azure Storage Account (Blob containers + Table Storage)
  - Azure Document Intelligence
  - Azure OpenAI (or other LLM provider)
- **Docker** (optional, for containerized deployment)

### Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd ProcurementBudgetManagement
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate    # Linux/macOS
   venv\Scripts\activate       # Windows
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # For development/testing
   ```

4. **Configure environment variables:**

   ```bash
   cp .env.example .env
   # Edit .env with your Azure credentials and configuration
   ```

---

## Configuration

Copy [`.env.example`](.env.example) to `.env` and populate the required values:

```env
# Azure Service Bus
AZURE_SERVICE_BUS_CONNECTION_STRING=Endpoint=sb://<namespace>.servicebus.windows.net/;...
SERVICE_BUS_TOPIC_NAME=invoice-events

# Azure Storage (Blob + Tables)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
BLOB_CONTAINER_NAME=invoices

# Azure Document Intelligence
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://<resource>.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=<key>

# Azure OpenAI / LLM
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_DEPLOYMENT_NAME=<deployment>

# LangSmith (Observability)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<key>
LANGCHAIN_PROJECT=procurement-budget-mgmt
```

Agent-specific configuration is available in [`agents/.env.example`](agents/.env.example).

---

## Running the Application

### Local Development (Hybrid Mode)

In this mode, the API and agents run locally while connecting to Azure cloud services.

**Terminal 1 — Start the API server:**

```bash
python dev_server.py
```

Or directly with uvicorn:

```bash
uvicorn invoice_lifecycle_api.main:app --reload
```

**Terminal 2 — Start all agents:**

```bash
python agents/run_agents.py
```

This uses Python multiprocessing to start each agent in its own process:

| Process | Agent | Listens For |
|---|---|---|
| 1 | Intake Agent | `invoice.created` |
| 2 | Validation Agent | `invoice.extracted` |
| 3 | Budget Agent | `invoice.validated` |
| 4 | Approval Agent | `invoice.budget_checked` |
| 5 | Payment Agent | `invoice.approved` |
| 6 | Analytics Agent | All messages |

### Docker

```bash
docker build -f agents/Dockerfile -t procurement-agents .
docker run --env-file .env procurement-agents
```

See the [`docker/`](docker/) directory for additional Docker configurations.

---

## Agents

All agents extend [`BaseAgent`](agents/base_agent.py), which provides:

- Azure Service Bus subscription management
- Message receiving and acknowledgment
- State transition publishing
- Error handling with dead-letter support
- LangSmith tracing integration

### Agent Pipeline

| Agent | Trigger State | Output State | Description |
|---|---|---|---|
| **Intake Agent** | `CREATED` | `EXTRACTED` | Downloads file from Blob Storage, runs OCR via Document Intelligence, extracts invoice fields |
| **Validation Agent** | `EXTRACTED` | `VALIDATED` | Checks approved vendor list, spending authority, pricing, duplicates, contract compliance |
| **Budget Agent** | `VALIDATED` | `BUDGET_CHECKED` | Allocates to department/project budget, checks availability, flags over-budget |
| **Approval Agent** | `BUDGET_CHECKED` | `APPROVED` | Auto-approves within policy, routes to manager or escalates if needed |
| **Payment Agent** | `APPROVED` | `PAYMENT_SCHEDULED` | Schedules payment (net-30/60), generates payment batch, sends remittance |
| **Analytics Agent** | All states | — | Tracks spending trends, detects anomalies, generates cost-saving insights (non-blocking) |

---

## API Endpoints

### Create Invoice

```http
POST /api/invoices
Content-Type: multipart/form-data

file: <invoice file (PDF, JPG, PNG)>
department_id: <department code (IT, HR, FINANCE)>
source: <api | email | web>
```

**Response:** `202 Accepted`

```json
{
  "invoice_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "CREATED"
}
```

**Process:**
1. Uploads file to Azure Blob Storage (`invoices/{year}/{month}/{department}/{id}.{ext}`)
2. Stores metadata in Azure Table Storage with blob reference
3. Publishes `invoice.created` message to Service Bus
4. Returns immediately with invoice ID

---

## Invoice Lifecycle

### State Machine

```
CREATED → EXTRACTED → VALIDATED → BUDGET_CHECKED → APPROVED → PAYMENT_SCHEDULED → PAID

                              ↓ (at any stage)
                         FAILED / MANUAL_REVIEW
```

### Data Storage Strategy

| Store | Purpose | Content |
|---|---|---|
| **Blob Storage** | File storage | Invoice PDFs, images, receipts (up to 190.7 TB per blob) |
| **Table Storage** | Metadata | Invoice state, vendor info, budgets, audit trails, blob references |

**Why separate?** Azure Table Storage has a 1 MB entity size limit, but invoice files are typically 100KB–5MB+. Separation enables faster queries, lifecycle cost optimization, and better security via SAS tokens.

### Blob Storage Lifecycle

| Age | Tier | Cost/GB/month |
|---|---|---|
| 0–90 days | Hot | $0.018 |
| 91–365 days | Cool | $0.010 |
| 366–2,555 days | Archive | $0.002 |
| 2,555+ days | Deleted | — |

---

## Development

### Running Tests

```bash
pytest
```

### Linting

```bash
ruff check .
```

### Project Dependencies

- **Production:** [`requirements.txt`](requirements.txt)
- **Development:** [`requirements-dev.txt`](requirements-dev.txt)

---

## Deployment

### Development / MVP

Local machine running API + agents, connected to Azure cloud resources (Service Bus, Blob Storage, Table Storage, OpenAI).

### Production

Each agent deployed as a separate container to **Azure Container Instances** or **Azure Kubernetes Service**:

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
```

See [`invoice-lifecycle-azure/`](invoice-lifecycle-azure/) for Azure deployment configurations.

---

## Monitoring & Observability

| Tool | Metrics |
|---|---|
| **LangSmith** | Agent execution traces, token usage, latency, error rates, cost tracking |
| **Azure Monitor** | Service Bus delivery rates, storage operations, blob upload/download latency, container CPU/memory |
| **Custom Metrics** | End-to-end processing time, state transition rates, budget utilization, file storage growth |

### Alerting

- Failed invoice processing (dead-letter queue depth)
- Budget overruns
- Agent failures (no heartbeat)
- Unusual spending patterns
- Blob storage upload failures

---

## Performance Targets

| Metric | Target |
|---|---|
| Invoice intake (including blob upload) | < 5 seconds |
| Full pipeline (CREATED → APPROVED) | < 2 minutes |
| Message delivery latency | < 1 second |
| Agent processing time | < 30 seconds/invoice |
| System throughput | 1,000+ invoices/hour |
| Uptime SLA | 99.9% |

---

## License

See [LICENSE](LICENSE) for details.