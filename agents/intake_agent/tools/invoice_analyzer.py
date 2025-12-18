from decimal import Decimal
from azure.identity.aio import DefaultAzureCredential
from shared.infrastructure.document_intelligence_client import DocumentIntelligenceWrapper


from shared.config.settings import get_settings
from shared.models.invoice import Invoice
settings = get_settings()

endpoint = settings.document_intelligence_endpoint


async def analyze_invoice_request(document_data:bytes, locale:str= "en-US") -> Invoice:

    document_intelligence_wrapper = DocumentIntelligenceWrapper(endpoint=endpoint)
    async with document_intelligence_wrapper:
        print("Analyzing invoice document...")
        
        invoices = await document_intelligence_wrapper.analyze_invoice(
            document_data=document_data,
            locale=locale
        )
        print(f"Invoice analysis complete. {len(invoices)} document(s) found.")
        #get first invoice only for now.
        invoice_source = invoices[0] if len(invoices) > 0 else {}

        invoice = Invoice()
        # Map extracted fields to Invoice dataclass
        invoice.vendor_name = invoice_source.get("VendorName", {}).get("value", "")
        invoice.invoice_id = invoice_source.get("InvoiceId", {}).get("value", "")
        invoice.issued_date = invoice_source.get("InvoiceDate", {}).get("value", None)
        invoice.due_date = invoice_source.get("DueDate", {}).get("value", None)
        invoice.amount = Decimal(invoice_source.get("InvoiceTotal", {}).get("value", 0.0)) 
        invoice.subtotal = Decimal(invoice_source.get("SubTotal", {}).get("value", 0.0))
        invoice.tax_amount = Decimal(invoice_source.get("TotalTax", {}).get("value", 0.0))
        
    return invoice

async def analyze_invoice_request_file(file_path:str, locale:str= "en-US")->Invoice:
    """
    Analyze a local invoice document using the prebuilt invoice model.
    Args:
        file_path: Path to the local invoice document file (PDF, JPG, PNG)
        locale: Locale for analysis (default: "en-US") or use "es-ES"
    """
    # Read a local file as bytes
    print("Analyzing a local invoice document...")
    with open(file_path, "rb") as f:
        document_data = f.read()
    return await analyze_invoice_request(document_data, locale)
