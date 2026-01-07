from decimal import Decimal

from langsmith import traceable
from shared.config.settings import settings
from shared.utils.logging_config import get_logger

from shared.infrastructure.document_intelligence_wrapper import DocumentIntelligenceWrapper

logger = get_logger(__name__)

class InvoiceAnalyzerTool:

    def __init__(self):
        self.endpoint = settings.document_intelligence_endpoint
        self.document_intelligence_wrapper = DocumentIntelligenceWrapper(endpoint=self.endpoint)

    @traceable(name="invoice_analyzer_tool.analyze_invoice_request", tags=["tool", "invoice_analyzer"], metadata={"version": "1.0"})
    async def analyze_invoice_request(self, document_data:bytes, locale:str= "en-US") -> dict:
        """Tool for analyzing invoices."""

        try:

            logger.info("Analyzing invoice document...")
            query_fields_list = ["Description"]
            invoices = await self.document_intelligence_wrapper.analyze_invoice(
                document_data=document_data,
                locale=locale,
                query_fields=query_fields_list
            )
            logger.info(f"Invoice analysis complete. {len(invoices)} document(s) found.")
            #get first invoice only for now.
            invoice_source = invoices[0] if len(invoices) > 0 else {}

            invoice = {}
            # Map extracted fields to Invoice dataclass
            invoice["vendor_name"] = invoice_source.get("VendorName", {}).get("value", "")
            invoice["invoice_number"] = invoice_source.get("InvoiceId", {}).get("value", "")
            invoice["issued_date"] = invoice_source.get("InvoiceDate", {}).get("value", None)
            invoice["due_date"] = invoice_source.get("DueDate", {}).get("value", None)
            invoice["amount"] = Decimal(invoice_source.get("InvoiceTotal", {}).get("value", 0.0)) 
            invoice["subtotal"] = Decimal(invoice_source.get("SubTotal", {}).get("value", 0.0))
            invoice["tax_amount"] = Decimal(invoice_source.get("TotalTax", {}).get("value", 0.0))
            invoice["description"] = invoice_source.get("Description", {}).get("value", "")

            return invoice
        
        except Exception as e:
            logger.error(f"Error analyzing invoice: {e}")
            raise e

    async def analyze_invoice_request_file(self, file_path:str, locale:str= "en-US")->dict:
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
        return await self.analyze_invoice_request(document_data, locale)

    @traceable(name="invoice_analyzer_tool.analyze_receipt_request", tags=["tool", "invoice_analyzer"], metadata={"version": "1.0"})
    async def analyze_receipt_request(self, document_data:bytes, locale:str= "en-US")-> dict:

        try:
            logger.info("Analyzing receipt document...")
            #additional fields different from the default prebuilt receipt model. It may incur additional costs.
            query_fields_list = ["ReceiptNumber", "Description"]
            receipts = await self.document_intelligence_wrapper.analyze_receipt(
                document_data=document_data,
                locale=locale,
                additional_fields=query_fields_list
            )
            logger.info(f"Receipt analysis complete. {len(receipts)} document(s) found.")
            #get first receipt only for now.
            receipt = receipts[0] if len(receipts) > 0 else {}
            invoice = {}
            # Map extracted fields to Invoice dataclass
            invoice["vendor_name"] = receipt.get("MerchantName", {}).get("value", "")
            invoice["invoice_number"] = receipt.get("ReceiptNumber", {}).get("value", "")
            invoice["issued_date"] = receipt.get("TransactionDate", {}).get("value", None)
            invoice["amount"] = receipt.get("Total", {}).get("value", 0.0)
            invoice["description"] = receipt.get("Description", {}).get("value", "")

            return invoice
        except Exception as e:
            logger.error(f"Error analyzing receipt: {e}")
            raise e

    async def analyze_receipt_request_file(self, image_path:str, locale:str= "en-US")-> dict:
        with open(image_path, "rb") as f:
            document_data = f.read()
        return await self.analyze_receipt_request(document_data, locale)
    

    async def close(self) -> None:
        """Release any resources held by the tool."""
        logger.info("Releasing resources for InvoiceAnalyzerTool...")
        if self.document_intelligence_wrapper:
            await self.document_intelligence_wrapper.close()