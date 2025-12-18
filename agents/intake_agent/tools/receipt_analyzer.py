
from shared.infrastructure.document_intelligence_wrapper import DocumentIntelligenceWrapper

from shared.config.settings import get_settings
from shared.models.invoice import Invoice
settings = get_settings()

endpoint = settings.document_intelligence_endpoint


async def analyze_receipt_request(document_data:bytes, locale:str= "en-US")-> Invoice:
    document_intelligence_wrapper = DocumentIntelligenceWrapper(endpoint=endpoint)
    async with document_intelligence_wrapper:
        print("Analyzing receipt document...")
        #additional fields different from the default prebuilt receipt model. It may incur additional costs.
        query_fields_list = ["ReceiptNumber"]
        receipts = await document_intelligence_wrapper.analyze_receipt(
            document_data=document_data,
            locale=locale,
            additional_fields=query_fields_list
        )
        print(f"Receipt analysis complete. {len(receipts)} document(s) found.")
        #get first receipt only for now.
        receipt = receipts[0] if len(receipts) > 0 else {}
        invoice = Invoice()
        # Map extracted fields to Invoice dataclass
        invoice.vendor_name = receipt.get("MerchantName", {}).get("value", "")
        invoice.invoice_id = receipt.get("ReceiptNumber", {}).get("value", "")
        invoice.issued_date = receipt.get("TransactionDate", {}).get("value", None)
        invoice.amount = receipt.get("Total", {}).get("value", 0.0)

    return invoice

async def analyze_receipt_request_file(image_path:str, locale:str= "en-US")-> Invoice:
    with open(image_path, "rb") as f:
        document_data = f.read()
    return await analyze_receipt_request(document_data, locale)