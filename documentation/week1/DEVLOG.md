# Procurement & Budget Management Automation - 7-Week Roadmap

## Project Overview
Building an AI-powered multi-agent system using **event-driven choreography** to automate invoice processing, procurement validation, budget tracking, and spending analytics.

**Tech Stack:** Azure Service Bus, Azure Blob Storage ⭐, Azure Table Storage, Python Multiprocessing, LangChain, LangSmith

---

## Week 1: Foundation, Infrastructure & Document Intelligence POC
**Goal:** Establish Azure infrastructure, core data models, Service Bus messaging, Blob Storage ⭐, and validate OCR capabilities

### Key Deliverables
- Azure resources provisioned (Service Bus, Blob Storage ⭐, Table Storage, OpenAI, Document Intelligence)
- **Service Bus Topic and Subscriptions configured with SQL filters** ⭐
- **Blob Storage container created with lifecycle policies** ⭐
- **Document Intelligence POC completed with findings documented** ⭐
- Database schema implemented in Azure Tables (with blob references) ⭐
- Basic API endpoint for invoice intake with file upload to Blob Storage ⭐
- Service Bus pub/sub infrastructure working **locally**
- LangSmith integration configured
- Development environment setup (local Python or Docker)

### Tasks

**Days 1-2: Azure Infrastructure Setup**
- [X] Set up Azure subscription and resource group
- **Create Azure Service Bus namespace (Standard tier)** ⭐
  - [X] Create Topic: "invoice-events"
  - [X] Configure topic settings (TTL, duplicate detection, max size)
- **Create Service Bus Subscriptions for each agent** ⭐
  - [X] intake-agent-subscription (filter: subject = 'invoice.created')
  - [X] validation-agent-subscription (filter: subject = 'invoice.extracted')
  - [X] budget-agent-subscription (filter: subject = 'invoice.validated')
  - [X] approval-agent-subscription (filter: subject = 'invoice.budget_checked')
  - [X] payment-agent-subscription (filter: subject = 'invoice.approved')
  - [X] analytics-agent-subscription (no filter - receives all)
- **Get Service Bus connection string for local development** ⭐
- **Create Azure Storage Account** ⭐
  - [X] Create Blob Storage container: "invoices"
  - [X] Configure container for private access (no anonymous)
  - [X] Set up lifecycle management policy (Hot → Cool → Archive)
  - [X] Get connection string for local development
- **Create Azure Tables** (Invoices, Vendors, Budgets)
  - [X] Implement schemas with blob reference fields ⭐
  - [X] Update Invoice schema: remove raw_data, add blob fields ⭐
- [X] Provision Azure Document Intelligence resource (Free tier for testing)
- [X] Provision Azure OpenAI Service
- [X] Set up version control and project structure

**Days 3-4: Document Intelligence POC** ⭐
- Test Azure Document Intelligence prebuilt Invoice model
  - [X] Test with sample PDF invoices (various formats)
  - Test with multi-page invoices
  - [X] Evaluate extraction accuracy for key fields
- Test Azure Document Intelligence prebuilt Receipt model
  - [X] Test with JPG/PNG photo receipts
  - [X] Test with POS receipts (printed)
  - [ ] Test with POS receipts (handwritten) *pending
  - [X] Test with various image qualities (lighting, angles, crumpled)
- Test QR code extraction with pyzbar
  - [X] Install and test pyzbar library
  - [X] Extract QR codes from sample receipts
  - [X] Validate URLs extracted from QR codes
- Document findings:
  - [X] Which fields are reliably extracted
    * the prebuilt models recover all the needed fiels. the level of confidence is higher than 0.91
    * ReceiptNumber isn ot part of the receipt model. It has to be added as custom "query_fields" with extra costs
  - [X] Accuracy rates for different document types
    * Average precision of 0.95
  - [X] Decision: Use prebuilt models or train custom model
    * prebuilt models is enough for Version 1
  - [X] Create field mapping documentation
  - [] Edge cases and limitations *pending
- Create extraction helper functions for Intake Agent
  - [X] Wrapper function for Invoice model
  - [X] Wrapper function for Receipt model
  - [X] QR code extraction function
  - [X] Error handling for failed extractions

**Days 5-7: API, Blob Storage, and Service Bus Integration** ⭐
- **Build InvoiceStorageService helper class** ⭐
  - [X] upload_invoice_file() method
  - [X] download_invoice_file() method
  - [X] delete_invoice_file() method
  - [X] Test all methods with sample files
- Build basic FastAPI application structure
- **Create invoice intake API endpoint with Blob Storage** ⭐
  - [X] Accept multipart/form-data for file uploads
  - [X] Upload file to Blob Storage (hierarchical naming)
  - [X] Store metadata in Table Storage with blob reference
  - [X] Support PDF, JPG, PNG formats
  - [X] Return 202 Accepted with invoice_id
- **Implement Service Bus message publishing in API** ⭐
  - [X] Install azure-servicebus SDK
  - [X] Configure ServiceBusClient with connection string
  - [X] Publish test message to "invoice-events" topic
- **Create first agent listener (Intake Agent)** ⭐
  - [X] Implement Service Bus subscription receiver
  - [X] Pull messages from intake-agent-subscription
  - [X] Get invoice metadata from Table Storage
  - [X] Test message filtering (only invoice.created)
  - [X] Download file from Blob Storage  
  - [X] Implement complete_message() after processing
- [-] Set up LangChain with Azure OpenAI connection
     Postpone for later agents
- [X] Configure LangSmith for agent tracing
- [X] Integrate Document Intelligence extraction into intake flow
- [X] **Test end-to-end locally**: API → Blob Storage → Table Storage → Service Bus → Intake Agent ⭐
- [X] Create local development environment setup documentation

#Postpone until the end deployment phase.
- [-] **Set up Azure Logic App for email monitoring**
  - Create Logic App resource
  - Configure Outlook.com / Office 365 connector
  - Set up email trigger (when new email arrives)
  - Add filters (has attachments, specific formats)
  - Configure HTTP action to call API endpoint
  - Test with sample emails
  - Add error handling and retry logic

### Success Criteria
- ✅ Service Bus namespace created and accessible locally
- ✅ All subscriptions configured with correct SQL filters
- ✅ **Blob Storage container created with lifecycle policy** ⭐
- ✅ **InvoiceStorageService class implemented and tested** ⭐
- ✅ Invoice can be submitted via API (with file upload)
- ✅ **Invoice file uploaded to Blob Storage successfully** ⭐
- ✅ **Invoice metadata stored in Table with blob reference** ⭐
- ✅ Message published to Service Bus successfully
- ✅ Intake Agent receives message from subscription (running locally!)
- ✅ **Intake Agent downloads file from Blob Storage** ⭐
- ✅ LangSmith traces visible in dashboard
- ✅ **Document Intelligence successfully extracts data from 90%+ test invoices**
- ✅ **QR codes successfully decoded from receipt images**
- ✅ **Extraction helper functions created and tested**

#Postpone until the end deployment phase.
- ✅ **Logic App successfully monitors email and triggers API**
- ✅ **End-to-end test: Email → Logic App → API → Blob Storage → Service Bus → Agent (local)** ⭐


**Technical Decisions:**
- Defer the logic apps configuration and email monitoring. since the paid subscription of  Microsoft 365 will not be used fully for this project.
- Use Azure service bus as a event driven frameworks instead of Azure Event Grid.
- Azure Document intelligence will be handle through wrappers 
- Agents will run independently, or through an Agent Orchestrator script or both.
- Product Orders will be reduced to an optional input in the invoice model.
- Invoices and receipt will be handle in the same Invoice object model, and will be differentiated by a "document_type" with 2 possible values "invoice", "receipt"

**Challenges & Solutions:**
- Review the logic app implementation and technical/licensing limitation inside the current azure environment.


**Learnings:**
- Logic apps licensing requiremets 
- how to implement signals in python for clean exits
- Azure service bus wrappers and interators
- Python __aexit__ and __aenter__ functions in "async with" clauses

**Next Steps:**
- [-] Week 2 plan 

**Time Invested:** 50 hours



### Local Development Setup Checklist
```bash
# Required environment variables
SERVICEBUS_CONNECTION_STRING=Endpoint=sb://...
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpoints...
AZURE_STORAGE_ACCOUNT_KEY=...  # For SAS token generation ⭐
AZURE_OPENAI_ENDPOINT=https://...
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://...
LANGSMITH_API_KEY=lsv2_...

# Test commands
python api/main.py                    # Should start API
python agents/intake_agent.py         # Should connect and wait for messages
curl -X POST http://localhost:8000/invoices \
  -F "file=@invoice.pdf" \
  -F "department_id=IT"               # Should upload to blob + publish message
# Agent should receive message, download from blob, and process!
```

### POC Test Coverage Checklist
```
Invoice Types:
☐ Standard business invoices (PDF)
☐ Utility bills
☐ Multi-page invoices

Receipt Types:
☐ Printed POS receipts (photos)
☐ Handwritten receipts
☐ Hotel receipts
☐ Restaurant receipts

Quality Variations:
☐ High-quality scans
☐ Phone camera photos (various angles)
☐ Low-light images
☐ Crumpled/damaged receipts

Special Cases:
☐ Receipts with QR codes
☐ Multi-currency invoices
☐ Different languages (if applicable)
☐ Handwritten notes on receipts

Blob Storage Tests: ⭐
☐ Upload PDF files (various sizes)
☐ Upload JPG/PNG images
☐ Download uploaded files
☐ Generate SAS URLs
☐ Verify hierarchical naming
☐ Test error handling (large files, network errors)
```

---

## Week 2: Intake & Validation Agents
**Goal:** Build the first two agents in the pipeline with full LangChain integration and Blob Storage access ⭐, all running locally

### Key Deliverables
- Intake Agent (extracts invoice data from Blob Storage ⭐, identifies vendors) **running locally**
- Validation Agent (verifies vendors, checks policies) **running locally**
- Both agents pulling from their Service Bus subscriptions
- Message-driven communication between agents working
- Vendor management functionality
- Audit trail implementation

### Tasks
- **Complete Intake Agent implementation with Blob Storage** ⭐
  - ✅ Get invoice metadata from Table Storage
  - ✅ Download file from Blob Storage using blob_name
  - ✅ Integrate Document Intelligence extraction functions from Week 1
  - ✅ Create tools for vendor identification logic
  - ✅ Implement state transition to EXTRACTED
  - ✅ Publish message with subject='invoice.extracted'
  - ✅ Add comprehensive error handling (blob download failures)
- Set up Validation Agent Service Bus subscription
  - ✅ Create receiver for validation-agent-subscription
  - ✅ Implement message pulling loop
- Build vendor database and management
  - ✅ Seed Vendors table with test data
  - ✅ Create vendor lookup functions
- ✅ Implement Validation Agent with LangChain
  - ✅ Create tools for vendor verification
  - ✅ Build spending limit checks
  - ✅ Implement pricing validation
  - ✅ Add duplicate invoice detection
  - ✅ Publish message with subject='invoice.validated' or 'invoice.failed'
- ✅ Implement audit trail in AuditLog table
  - ✅ Log every state transition
  - ✅ Include agent name, timestamp, old/new state
- **Test locally: API → Blob Storage → Intake Agent → Validation Agent** ⭐
  - ✅ All running on local machine
  - ✅ Connected to Azure Service Bus and Blob Storage in cloud
- ✅ Add comprehensive logging for debugging
- ✅ Create helper script to monitor Service Bus queues and Blob Storage

### Success Criteria
- ✅ Invoice flows from CREATED → EXTRACTED → VALIDATED
- ✅ **Intake Agent successfully downloads files from Blob Storage** ⭐
- ✅ **Files of various sizes (100KB-5MB) processed correctly** ⭐
- ✅ Agents process messages independently (no coupling)
- ✅ Invalid invoices properly flagged and sent to FAILED state
- ✅ All actions traced in LangSmith
- ✅ Dead letter queue properly handles failures
- ✅ Both agents run locally without deployment
- ✅ Audit trail captures all state changes
- ✅ **Blob Storage error handling works correctly** ⭐

### Testing Scenarios
```python
# Test 1: Valid invoice flow
upload_invoice() → Blob Storage → CREATED → EXTRACTED → VALIDATED

# Test 2: Large file (5MB PDF)
upload_large_invoice() → Blob Storage → CREATED → EXTRACTED → VALIDATED

# Test 3: Invalid vendor
upload_invoice(unapproved_vendor) → CREATED → EXTRACTED → FAILED

# Test 4: Blob download failure
simulate_blob_error() → CREATED → FAILED (with retry)

# Test 5: Agent failure recovery
kill_agent_mid_processing() → message_abandoned → retry_succeeds
```

---

## Week 3: Budget Tracking System
**Goal:** Implement budget management, allocation logic, and tracking agent

### Key Deliverables
- Budget data model and allocation structure
- Budget Tracking Agent with real-time calculation **running locally**
- Budget consumption monitoring and forecasting
- Over-budget detection and alerting
- Budget management API endpoints

### Tasks
- ✅ Design budget allocation hierarchy (departments, projects, categories)
- ✅ Implement Budgets table with fiscal year partitioning
- ✅ Seed Budgets table with test data
- ✅ Set up Budget Agent Service Bus subscription
  - Create receiver for budget-agent-subscription
  - Implement message pulling loop
- Build Budget Tracking Agent with LangChain
  - Create tools for budget lookup
  - Implement budget allocation logic
  - Build consumption tracking
  - Add forecasting logic (linear regression)
  - Implement over-budget detection
  - Publish message with subject='invoice.budget_checked'
- Create API endpoints for budget management (CRUD)
  - GET /budgets/{department}/{category}
  - GET /budgets/{department}/{project}/{category}
  - POST /budgets (create new budget allocation)
  - PUT /budgets/{id} (update allocation)
  - GET /budgets/consumption (real-time consumption report)
- Implement budget vs. actual comparison logic
- Build alerting system for budget thresholds
  - Email notifications for over-budget
  - Slack/Teams webhooks (optional)
- Create budget dashboard queries
- Test budget allocation and tracking flows locally

### Success Criteria
- ✅ Invoices properly allocated to budgets
- ✅ Real-time budget consumption calculated accurately
- ✅ Over-budget scenarios flagged correctly
- ✅ Budget forecasting generates insights
- ✅ API endpoints return correct budget data
- ✅ Budget Agent runs locally and processes messages

---
