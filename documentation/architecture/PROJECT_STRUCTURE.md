# Procurement & Budget Management System - Project Structure

**Generated**: December 16, 2025  
**Version**: 0.1.0  
**Architecture**: Event-Driven Choreography with Azure Services

---

## 📁 Root Directory

```
ProcurementBudgetManagement/
├── .env.example                    # Environment variables template
├── .gitignore                      # Git ignore rules
├── docker-compose.yml              # Local development orchestration
├── LICENSE                         # Project license
├── README.md                       # Project overview and setup
├── requirements.txt                # Python dependencies (140 packages)
├── agents/                         # Invoice processing agents
├── documentation/                  # Project documentation
├── invoice-lifecycle-api/          # FastAPI REST API
├── invoice-lifecycle-azure/        # Azure IaC templates
├── invoice-lifecycle-ui/           # React TypeScript UI
├── scripts/                        # Utility scripts
└── shared/                         # Shared modules and utilities
```

---

## 🤖 Agents Directory (`/agents`)

Independent agents that process invoices through event-driven choreography.

```
agents/
├── __init__.py                     # Empty - Agents package marker
├── base_agent.py                   # Abstract base class for all agents
├── Dockerfile                      # Docker container for agents
├── run_agents.py                   # Script to start all agents
│
├── intake_agent/                   # Document extraction agent
│   ├── __init__.py                 # Package marker (minimal)
│   ├── agent.py                    # IntakeAgent implementation
│   └── tools/                      # Agent-specific tools
│
├── validation_agent/               # Business rules validation agent
│   ├── __init__.py                 # Package marker (minimal)
│   ├── agent.py                    # ValidationAgent implementation
│   └── tools/                      # Agent-specific tools
│
├── budget_agent/                   # Budget tracking agent
│   ├── __init__.py                 # Package marker (minimal)
│   ├── agent.py                    # BudgetAgent implementation
│   └── tools/                      # Agent-specific tools
│
├── approval_agent/                 # Approval workflow agent
│   ├── __init__.py                 # Package marker (minimal)
│   ├── agent.py                    # ApprovalAgent implementation
│   └── tools/                      # Agent-specific tools
│
├── payment_agent/                  # Payment scheduling agent
│   ├── __init__.py                 # Package marker (minimal)
│   ├── agent.py                    # PaymentAgent implementation
│   └── tools/                      # Agent-specific tools
│
└── analytics_agent/                # Spending analytics agent (parallel)
    ├── __init__.py                 # Package marker (minimal)
    ├── agent.py                    # AnalyticsAgent implementation
    └── tools/                      # Agent-specific tools
```

### Agent Responsibilities

| Agent | Purpose | Subscribes To | Publishes |
|-------|---------|---------------|-----------|
| **IntakeAgent** | Extract data from invoice documents using Azure Document Intelligence | `invoice.created` | `invoice.extracted` |
| **ValidationAgent** | Validate against business rules, vendor list, and policies | `invoice.extracted` | `invoice.validated` |
| **BudgetAgent** | Check budget availability and track allocations | `invoice.validated` | `invoice.budget_checked` |
| **ApprovalAgent** | Auto-approve or route for manual approval | `invoice.budget_checked` | `invoice.approved` |
| **PaymentAgent** | Schedule payments based on terms | `invoice.approved` | `invoice.payment_scheduled` |
| **AnalyticsAgent** | Analyze spending patterns (runs in parallel) | `invoice.*` (all events) | None |

---

## 📦 Shared Module (`/shared`)

Reusable components shared across all agents and the API.

```
shared/
├── __init__.py                     # Empty - Shared package marker
│
├── config/                         # Configuration management
│   ├── __init__.py                 # Empty
│   └── settings.py                 # Pydantic settings with env validation
│
├── infrastructure/                 # Azure service clients
│   ├── __init__.py                 # Empty
│   ├── document_intelligence_client.py  # Azure Document Intelligence wrapper
│   ├── email_client.py             # Email notification client
│   ├── logical_app_client.py       # Azure Logic Apps integration
│   ├── service_bus_client.py       # Azure Service Bus pub/sub wrapper
│   └── table_storage_client.py     # Azure Table Storage CRUD wrapper
│
├── models/                         # Domain models
│   ├── __init__.py                 # Empty
│   ├── invoice.py                  # Invoice, InvoiceState, Priority, LineItem
│   ├── vendor.py                   # Vendor, VendorContract, BankAccount
│   └── budget.py                   # Budget, BudgetAdjustment, BudgetAlert
│
├── observability/                  # Monitoring and observability
│   ├── __init__.py                 # Empty
│   ├── health_checks.py            # Health check endpoints
│   ├── langsmith_config.py         # LangSmith tracing configuration
│   └── metrics.py                  # Application metrics
│
└── utils/                          # Utilities and constants
    ├── __init__.py                 # Empty
    ├── constants.py                # Message subjects, table names, subscriptions
    ├── extraction_helpers.py       # Data extraction utilities
    ├── logger.py                   # Logging configuration
    ├── message_builder.py          # Message construction helpers
    └── qr_scanner.py               # QR code scanning utilities
```

### Shared Components Detail

#### Domain Models (155+ fields, 7 enums, 10 business methods)
- **Invoice**: State machine, line items, totals, validation
- **Vendor**: Contracts, addresses, bank accounts, spending limits
- **Budget**: Allocations, adjustments, alerts, metrics

#### Infrastructure Clients
- **ServiceBusClient**: Publish/subscribe with context manager
- **DocumentIntelligenceClient**: OCR and invoice extraction
- **TableStorageClient**: Azure Table Storage operations
- **EmailClient**: Email notification service
- **LogicalAppClient**: Azure Logic Apps integration

#### Observability
- **HealthChecks**: Service health monitoring
- **LangSmithConfig**: LangSmith tracing and debugging
- **Metrics**: Application performance metrics

#### Configuration
- **Settings**: 30+ environment variables with Pydantic validation
- **Constants**: Message subjects, subscription names, table names

#### Utilities
- **Logger**: Centralized logging configuration
- **ExtractionHelpers**: Data extraction utilities
- **MessageBuilder**: Message construction helpers
- **QRScanner**: QR code scanning for invoices

---

## 🌐 Invoice Lifecycle API (`/invoice-lifecycle-api`)

FastAPI REST API for invoice submission and management (DDD architecture).

```
invoice-lifecycle-api/
├── Dockerfile                      # API container configuration
├── requirements.txt                # API-specific dependencies
│
├── invoice_lifecycle_api/          # Main API package
│   ├── __init__.py                 # Empty
│   ├── main.py                     # FastAPI application entry point
│   │
│   ├── api/                        # HTTP layer (controllers/routes)
│   │   ├── __init__.py             # Empty
│   │   └── routes/                 # API endpoints
│   │       ├── invoices.py         # Invoice CRUD endpoints (TODO)
│   │       ├── vendors.py          # Vendor management (TODO)
│   │       ├── budgets.py          # Budget queries (TODO)
│   │       └── analytics.py        # Analytics endpoints (TODO)
│   │
│   ├── application/                # Application layer (use cases)
│   │   ├── __init__.py             # Empty
│   │   └── services/               # Business logic services
│   │       ├── invoice_service.py  # Invoice use cases (TODO)
│   │       ├── vendor_service.py   # Vendor use cases (TODO)
│   │       └── budget_service.py   # Budget use cases (TODO)
│   │
│   ├── domain/                     # Domain layer (business logic)
│   │   ├── __init__.py             # Empty
│   │   ├── entities/               # Domain entities (TODO)
│   │   ├── value_objects/          # Value objects (TODO)
│   │   └── repositories/           # Repository interfaces (TODO)
│   │
│   ├── infrastructure/             # Infrastructure layer
│   │   ├── __init__.py             # Empty
│   │   ├── repositories/           # Repository implementations
│   │   │   ├── invoice_repository.py    # (TODO)
│   │   │   ├── vendor_repository.py     # (TODO)
│   │   │   └── budget_repository.py     # (TODO)
│   │   └── messaging/              # Message publishing
│   │       └── event_publisher.py  # Service Bus publisher (TODO)
│   │
│   └── utils/                      # API utilities
│       ├── __init__.py             # Empty
│       ├── dependencies.py         # FastAPI dependencies (TODO)
│       └── validators.py           # Request validators (TODO)
│
└── tests/                          # API tests
    ├── unit_tests/                 # Unit tests
    │   └── __init__.py             # Empty
    └── integration_tests/          # Integration tests
        └── __init__.py             # Empty
```

---

## ☁️ Azure Infrastructure (`/invoice-lifecycle-azure`)

Infrastructure as Code (IaC) for Azure resource provisioning.

```
invoice-lifecycle-azure/
├── bicep/                          # Azure Bicep templates
│   ├── main.bicep                  # Main deployment template (TODO)
│   ├── service-bus.bicep           # Service Bus topic + subscriptions (TODO)
│   ├── storage.bicep               # Storage account + tables + blob (TODO)
│   ├── document-intelligence.bicep # Document Intelligence resource (TODO)
│   └── app-service.bicep           # App Service for API hosting (TODO)
│
├── service_bus/                    # Service Bus specific configurations
│   └── (Azure Service Bus configs) # (TODO)
│
└── terraform/                      # Terraform templates (alternative)
    ├── main.tf                     # Main configuration (TODO)
    ├── variables.tf                # Input variables (TODO)
    ├── outputs.tf                  # Output values (TODO)
    └── modules/                    # Reusable modules (TODO)
```

### Planned Azure Resources

| Resource | Purpose | Configuration |
|----------|---------|---------------|
| **Service Bus** | Event-driven messaging | 1 topic, 6 subscriptions (filters) |
| **Storage Account** | Data persistence | 4 tables (invoices, vendors, POs, budgets) |
| **Blob Storage** | Invoice document storage | Container with SAS tokens |
| **Document Intelligence** | OCR and extraction | Invoice/receipt model |
| **App Service** | API hosting | Linux, Python 3.11+ |
| **Key Vault** | Secrets management | Connection strings, API keys |

---

## 🎨 Invoice Lifecycle UI (`/invoice-lifecycle-ui`)

React + TypeScript frontend with Mantine UI 8.3.10 (Vite build).

```
invoice-lifecycle-ui/
├── Dockerfile                      # UI container configuration
├── package.json                    # Node.js dependencies
├── vite.config.ts                  # Vite build configuration
├── tsconfig.json                   # TypeScript main configuration
├── tsconfig.app.json               # TypeScript app configuration
├── tsconfig.node.json              # TypeScript node configuration
├── index.html                      # HTML entry point
├── eslint.config.js                # ESLint configuration
├── README.md                       # UI setup instructions
│
├── public/                         # Static assets
│   └── vite.svg                    # Vite logo
│
└── src/                            # Source code
    ├── main.tsx                    # Application entry point
    ├── App.tsx                     # Root component
    ├── App.css                     # Application styles
    ├── index.css                   # Global styles
    │
    ├── assets/                     # Images and icons
    │   └── react.svg               # React logo
    │
    ├── theme/                      # Mantine UI 8.3.10 theme
    │   └── theme.tsx               # Theme configuration
    │
    ├── components/                 # Reusable components (TODO)
    │   ├── InvoiceUpload/          # Invoice upload widget
    │   ├── InvoiceList/            # Invoice listing table
    │   ├── InvoiceDetails/         # Invoice detail view
    │   └── Dashboard/              # Analytics dashboard
    │
    ├── pages/                      # Page components (TODO)
    │   ├── Home.tsx                # Landing page
    │   ├── Invoices.tsx            # Invoice management
    │   ├── Vendors.tsx             # Vendor management
    │   ├── Budgets.tsx             # Budget tracking
    │   └── Analytics.tsx           # Spending analytics
    │
    ├── services/                   # API client services (TODO)
    │   ├── api.ts                  # Axios configuration
    │   ├── invoiceService.ts       # Invoice API calls
    │   ├── vendorService.ts        # Vendor API calls
    │   └── budgetService.ts        # Budget API calls
    │
    └── types/                      # TypeScript types (TODO)
        ├── invoice.ts              # Invoice types
        ├── vendor.ts               # Vendor types
        └── budget.ts               # Budget types
```

---

## 📜 Scripts Directory (`/scripts`)

Utility scripts for development, testing, and deployment.

```
scripts/
├── data-source/                    # Data generation and seeding
│   ├── seed_invoices.py            # Generate sample invoices (TODO)
│   ├── seed_vendors.py             # Generate sample vendors (TODO)
│   └── seed_budgets.py             # Generate sample budgets (TODO)
│
├── deployment/                     # Deployment automation
│   ├── deploy_azure.sh             # Deploy Azure resources (TODO)
│   ├── deploy_agents.sh            # Deploy agent containers (TODO)
│   └── deploy_api.sh               # Deploy API container (TODO)
│
├── dev/                            # Development utilities
│   ├── __init__.py                 # Package marker
│   ├── monitor_queues.py           # Service Bus queue monitoring
│   └── test_flows.py               # Test workflow execution
│
├── poc/                            # Proof of concept scripts
│   ├── test_document_intelligence.py  # Document Intelligence testing
│   └── sample_documents/           # Sample invoice documents
│
├── testing/                        # Testing utilities
│   ├── test_end_to_end.py          # E2E workflow test (TODO)
│   ├── test_agents.py              # Agent integration test (TODO)
│   └── load_test.py                # Performance testing (TODO)
│
└── utils/                          # General utilities
    ├── setup_azure.py              # Azure resource setup (TODO)
    ├── cleanup_azure.py            # Azure resource cleanup (TODO)
    └── backup_data.py              # Data backup script (TODO)
```

---

## 📚 Documentation (`/documentation`)

Project documentation, architecture diagrams, and guides.

```
documentation/
├── AGENT_REFACTORING.md            # Agent package refactoring guide
├── DOMAIN_MODELS_UPDATE.md         # Domain model update log
├── REQUIREMENTS_UPDATE.md          # Dependencies update log
├── STEP_1_COMPLETE.md              # Step 1 completion summary
│
├── week1/                          # Week 1 documentation
│   └── PROJECT_STRUCTURE.md        # This file - detailed folder structure
│
├── architecture/                   # Architecture documentation
│   ├── PROJECT_STRUCTURE.md        # Legacy structure doc (may be outdated)
│   └── diagrams/                   # Architecture diagrams
│       ├── system-overview.png     # (TODO)
│       ├── event-flow.png          # (TODO)
│       └── data-model.png          # (TODO)
│
├── api/                            # API documentation
│   ├── openapi.yaml                # OpenAPI specification (TODO)
│   ├── endpoints.md                # Endpoint documentation (TODO)
│   └── authentication.md           # Auth guide (TODO)
│
├── agents/                         # Agent documentation
│   ├── intake-agent.md             # IntakeAgent guide (TODO)
│   ├── validation-agent.md         # ValidationAgent guide (TODO)
│   ├── budget-agent.md             # BudgetAgent guide (TODO)
│   ├── approval-agent.md           # ApprovalAgent guide (TODO)
│   ├── payment-agent.md            # PaymentAgent guide (TODO)
│   └── analytics-agent.md          # AnalyticsAgent guide (TODO)
│
├── deployment/                     # Deployment guides
│   ├── azure-setup.md              # Azure resource setup (TODO)
│   ├── local-development.md        # Local dev setup (TODO)
│   └── ci-cd.md                    # CI/CD pipeline (TODO)
│
└── schemas/                        # Data schemas
    └── azure_table_schemas.py      # Azure Table Storage schemas
```

---

## 🔧 Configuration Files

### Root Configuration

| File | Purpose | Status |
|------|---------|--------|
| `.env.example` | Environment variables template | ✅ Complete |
| `.gitignore` | Git ignore patterns | ✅ Complete |
| `docker-compose.yml` | Local development services | ✅ Complete |
| `requirements.txt` | Python dependencies (140 packages) | ✅ Complete |
| `LICENSE` | Project license | ✅ Complete |
| `README.md` | Project overview | ✅ Complete |

### Python Dependencies (requirements.txt)

**Total Packages**: 140  
**Organized Sections**: 15

1. Core Python Utilities
2. Azure SDK - Core
3. Azure SDK - Storage
4. Azure SDK - AI Services
5. Azure SDK - Other Services
6. Authentication & Security
7. Web Framework - FastAPI
8. HTTP Clients
9. Data Validation & Serialization
10. LangChain - Core
11. LangChain - Integrations
12. LangGraph
13. LangSmith & Observability
14. OpenAI
15. Machine Learning & AI

**Key Dependencies**:
- `fastapi==0.122.0` - REST API framework
- `azure-data-tables==12.7.0` - Table Storage
- `azure-storage-blob==12.27.1` - Blob Storage
- `azure-ai-agents==1.1.0` - AI agents
- `langchain==1.1.0` - LLM orchestration
- `langgraph==1.0.3` - Agent workflows
- `openai==2.8.1` - OpenAI integration
- `pydantic==2.12.4` - Data validation

---

## 📊 Project Statistics

### Code Organization

```
Total Directories: 50+
Total Files: 70+
Python Modules: 40+
Configuration Files: 12+
Documentation Files: 12+
Tools Directories: 6 (one per agent)
```

### Implementation Status

| Component | Status | Progress |
|-----------|--------|----------|
| **Project Structure** | ✅ Complete | 100% |
| **Domain Models** | ✅ Complete | 100% |
| **Infrastructure Clients** | ✅ Complete | 100% |
| **Agent Framework** | ✅ Complete | 100% |
| **Configuration** | ✅ Complete | 100% |
| **Agent Logic** | 🔄 In Progress | 20% |
| **API Endpoints** | ⏳ Pending | 0% |
| **Azure IaC** | ⏳ Pending | 0% |
| **UI Components** | ⏳ Pending | 0% |
| **Tests** | ⏳ Pending | 0% |
| **Documentation** | 🔄 In Progress | 40% |

### Lines of Code

```
Domain Models:      ~1,200 lines
Infrastructure:     ~1,000 lines (added email, logic apps, observability)
Agents:             ~600 lines
Configuration:      ~200 lines
Utilities:          ~300 lines (extraction, messaging, QR scanning)
Observability:      ~200 lines (health checks, metrics, tracing)
Scripts (dev/poc):  ~150 lines
Total:              ~3,650 lines
```

---

## 📝 Notes

### Design Principles

1. **Event-Driven Choreography**: Agents are independent, communicate via Service Bus
2. **Domain-Driven Design**: Clear separation of domain, application, and infrastructure
3. **Infrastructure as Code**: Azure resources defined in Bicep/Terraform
4. **Containerized**: All services run in Docker containers
5. **Type Safety**: Python type hints, TypeScript for UI
6. **Scalability**: Agents can scale independently

### Technology Stack

**Backend**:
- Python 3.11+
- FastAPI (REST API)
- Azure SDK (Storage, Service Bus, Document Intelligence)
- LangChain/LangGraph (AI orchestration)
- Pydantic (validation)

**Frontend**:
- React 18+
- TypeScript
- Mantine UI 8.3.10
- Vite (build tool)
- Axios (HTTP client)

**Infrastructure**:
- Azure Service Bus (messaging)
- Azure Table Storage (data)
- Azure Blob Storage (documents)
- Azure Document Intelligence (OCR)
- Azure App Service (hosting)

**DevOps**:
- Docker (containerization)
- Docker Compose (local dev)
- Bicep/Terraform (IaC)
- GitHub Actions (CI/CD - planned)

---

**Last Updated**: December 16, 2025  
**Maintained By**: Development Team  
**License**: See LICENSE file
