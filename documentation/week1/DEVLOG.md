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

- [X] **Set up Azure Logic App for email monitoring**
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
- ✅ **Logic App successfully monitors email and triggers API**
- ✅ **End-to-end test: Email → Logic App → API → Blob Storage → Service Bus → Agent (local)** ⭐


**Technical Decisions:**
- 

**Challenges & Solutions:**
- *Document any issues you encounter here*
- 

**Learnings:**
- *Key insights from today's work*
- 

**Next Steps:**
- [ ] 

**Time Invested:**  hours



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