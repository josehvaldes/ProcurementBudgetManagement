## DEVLOG
# Procurement & Budget Management Automation

## Project Overview
Building an AI-powered multi-agent system using **event-driven choreography** to automate invoice processing, procurement validation, budget tracking, and spending analytics.

**Tech Stack:** Azure Service Bus, Azure Storage Tables, Python Multiprocessing, LangChain, LangSmith



## Week 1: Foundation, Infrastructure & Document Intelligence POC
**Goal:** Establish Azure infrastructure, core data models, Service Bus messaging, and validate OCR capabilities

### Key Deliverables
- Azure resources provisioned (Service Bus, Storage Tables, OpenAI, Document Intelligence)
- **Service Bus Topic and Subscriptions configured with SQL filters** ⭐
- **Document Intelligence POC completed with findings documented** ⭐
- Database schema implemented in Azure Tables
- Basic API endpoint for invoice intake
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
- [X] Create Azure Storage Account and Tables (Invoices, Vendors, Budgets)
- [X] Implement table schemas with proper partition/row keys
- [X] Provision Azure Document Intelligence resource (Free tier for testing)
- [X] Provision Azure OpenAI Service
- [X] Set up version control and project structure

**Days 3-4: Document Intelligence POC** ⭐
- ** Test Azure Document Intelligence prebuilt Invoice model
  - [X] Test with sample PDF invoices (various formats)
  - [X] Test with multi-page invoices
  - [X] Evaluate extraction accuracy for key fields
- *** Test Azure Document Intelligence prebuilt Receipt model
  - [X] Test with JPG/PNG photo receipts
  - [X] Test with POS receipts (printed)
  - [X] Test with various image qualities (lighting, angles, crumpled)
  - [ ] Test with POS receipts (handwritten) *pending
- ** Test QR code extraction with pyzbar
  - [X] Install and test pyzbar library
  - [X] Extract QR codes from sample receipts
  - [X] Validate URLs extracted from QR codes
- ** Document findings:
  - [X] Which fields are reliably extracted
    * the prebuilt models recover all the needed fiels. the level of confidence is higher than 0.91
    * ReceiptNumber isn ot part of the receipt model. It has to be added as custom "query_fields" with extra costs
  - [X] Accuracy rates for different document types
    *Average precision of 0.95
  - [X] Decision: Use prebuilt models or train custom model
    * prebuilt models is enough for Version 1
  - [X] Create field mapping documentation
 
  **TODO  
  - Edge cases and limitations

- ** Create extraction helper functions for Intake Agent
  - [X] Wrapper function for Invoice model
  - [X] Wrapper function for Receipt model
  - [X] QR code extraction function
  - [X] Error handling for failed extractions

**Days 5-7: API and Service Bus Integration**
- Build basic FastAPI application structure
- Create invoice intake API endpoint (handles file uploads)
  - Support multipart/form-data for file uploads
  - Accept metadata (source, sender, subject, date)
  - Return 202 Accepted with invoice_id
- **Implement Service Bus message publishing in API** ⭐
  - Install azure-servicebus SDK
  - Configure ServiceBusClient with connection string
  - Publish test message to "invoice-events" topic
- **Create first agent listener (Intake Agent)** ⭐
  - Implement Service Bus subscription receiver
  - Pull messages from intake-agent-subscription
  - Test message filtering (only invoice.created)
  - Implement complete_message() after processing
- Set up LangChain with Azure OpenAI connection
- Configure LangSmith for agent tracing
- Integrate Document Intelligence extraction into intake flow
- **Test end-to-end locally**: API → Service Bus → Intake Agent ⭐
- Create local development environment setup documentation
- **Set up Azure Logic App for email monitoring**
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
- ✅ Invoice can be submitted via API (with file upload)
- ✅ Invoice stored in Azure Tables with CREATED state
- ✅ Message published to Service Bus successfully
- ✅ Intake Agent receives message from subscription (running locally!)
- ✅ LangSmith traces visible in dashboard
- ✅ **Document Intelligence successfully extracts data from 90%+ test invoices**
- ✅ **QR codes successfully decoded from receipt images**
- ✅ **Extraction helper functions created and tested**
- ✅ **Logic App successfully monitors email and triggers API**
- ✅ **End-to-end test: Email → Logic App → API → Service Bus → Agent (local)**

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
AZURE_OPENAI_ENDPOINT=https://...
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://...
LANGSMITH_API_KEY=lsv2_...

# Test commands
python api/main.py                    # Should start API
python agents/intake_agent.py         # Should connect and wait for messages
curl -X POST http://localhost:8000/invoices  # Should publish message
# Agent should receive and process message!
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
```

---