import argparse
import asyncio
from azure.identity.aio import DefaultAzureCredential
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentAnalysisFeature
import os
from shared.config.settings import get_settings
settings = get_settings()

endpoint = settings.document_intelligence_endpoint

async def analyze_receipt_request(image_path:str, locale:str= "en-US"):
    """
    Analyze a local receipt document using the prebuilt receipt model.
    Args:
        image_path: Path to the local receipt image file (JPG, PNG)
        locale: Locale for analysis (default: "en-US") or use "es-ES"
    Returns:
    """
    with open(image_path, "rb") as f:
        document_data = f.read()

    analyze_request = AnalyzeDocumentRequest(bytes_source=document_data)

    document_intelligence_client  = DocumentIntelligenceClient(
        endpoint=endpoint, credential=DefaultAzureCredential()
    )

    #additional fields to search. It may incur additional cost.
    #query_fields_list = ["ReceiptNumber"]
    
    async with document_intelligence_client:
        print("Analyzing receipt document...")
        poller = await document_intelligence_client.begin_analyze_document(
            model_id="prebuilt-receipt", 
            body=analyze_request,
            locale=locale, 
            # features=[DocumentAnalysisFeature.QUERY_FIELDS],
            # query_fields=query_fields_list
        )
        print("Waiting for receipt analysis to complete...")
        receipts = await poller.result()
        print(f"Receipt analysis complete. {len(receipts.documents)} document(s) found.")
        for idx, receipt in enumerate(receipts.documents):
            print("--------Recognizing receipt #{}--------".format(idx + 1))
            merchant_name = receipt.fields.get("MerchantName")
            if merchant_name:
                print(
                    "1. Merchant Name: {} has confidence: {}".format(
                        merchant_name.value_string, merchant_name.confidence
                    )
                )
            receipType = receipt.fields.get("ReceiptType")
            if receipType:
                print(
                    "2. Receipt Type: {} has confidence: {}".format(
                        receipType.value_string, receipType.confidence
                    )
                )
            transaction_date = receipt.fields.get("TransactionDate")
            if transaction_date:
                print(
                    "3. Transaction Date: {} has confidence: {}".format(
                        transaction_date.value_date, transaction_date.confidence
                    )
                )
            total = receipt.fields.get("Total")
            if total:
                print(
                    "4. Total: {} has confidence: {}".format(
                        total.value_currency.amount, total.confidence
                    )
                )
            receiptNumber = receipt.fields.get("ReceiptNumber")
            if receiptNumber:
                print(
                    "5. Receipt Number: {} has confidence: {}".format(
                        receiptNumber.value_string, receiptNumber.confidence
                    )
                )
    return "completed"

async def analyze_invoice_request(file_path:str, locale:str= "en-US"):
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

    analyze_request = AnalyzeDocumentRequest(bytes_source=document_data)

    document_intelligence_client  = DocumentIntelligenceClient(
        endpoint=endpoint, credential=DefaultAzureCredential()
    )

    async with document_intelligence_client:
        print("Analyzing invoice document...")
        poller = await document_intelligence_client.begin_analyze_document(
            model_id="prebuilt-invoice", 
            body=analyze_request,
            locale=locale #"es-ES" "en-US"
        )
        print("Waiting for invoice analysis to complete...")
        invoices = await poller.result()
        print(f"Invoice analysis complete. {len(invoices.documents)} document(s) found.")
        for idx, invoice in enumerate(invoices.documents):
            print("--------Recognizing invoice #{}--------".format(idx + 1))
        vendor_name = invoice.fields.get("VendorName")
        if vendor_name:
            print(
                "1. Vendor Name: {} has confidence: {}".format(
                    vendor_name.value_string, vendor_name.confidence
                )
            )
        invoice_id = invoice.fields.get("InvoiceId")
        if invoice_id:
            print(
                "2. Invoice Id: {} has confidence: {}".format(
                    invoice_id.value_string, invoice_id.confidence
                )
            )
        invoice_date = invoice.fields.get("InvoiceDate")
        if invoice_date:
            print(
                "3. Invoice Date: {} has confidence: {}".format(
                    invoice_date.value_date, invoice_date.confidence
                )
            )
        due_date = invoice.fields.get("DueDate")
        if due_date:
            print(
                "4. Due Date: {} has confidence: {}".format(
                    due_date.value_date, due_date.confidence
                )
            )
        invoice_total = invoice.fields.get("InvoiceTotal")
        if invoice_total:
            print(
                "5. Invoice Total: {} has confidence: {}".format(
                    invoice_total.value_currency.amount, invoice_total.confidence
                )
            )
        purchase_order = invoice.fields.get("PurchaseOrder")
        if purchase_order:
            print(
                "6. Purchase Order: {} has confidence: {}".format(
                    purchase_order.value_string, purchase_order.confidence
                )
            )
    return "completed"


async def run_invoce_tests():
    file_path_pdf = "./scripts/poc/sample_documents/invoices/invoice_software_services.pdf"
    response = await analyze_invoice_request(file_path_pdf, locale="en-US")     # Executes first, waits
    print(response)

    file_path_low_q = "./scripts/poc/sample_documents/invoices/invoice_low_quality_image.jpg"
    response = await analyze_invoice_request(file_path_low_q, locale="es-ES")   # Then executes second
    print(response)

async def run_receipt_tests():
    #print("Analyzing a standard receipt document...")
    #image_path ="./scripts/poc/sample_documents/receipts/VALDES_251216_image.jpg"
    #asyncio.run(analyze_receipt_request(image_path))

    #print("\nAnalyzing a low-quality receipt document...")
    #image_path_low_q = "./scripts/poc/sample_documents/receipts/20251216_152628_low_q.jpg"
    #asyncio.run(analyze_receipt_request(image_path_low_q))

    # print("\nAnalyzing a blurry receipt document...")
    # image_path_blurry = "./scripts/poc/sample_documents/receipts/20251217_213140_blurry.jpg"
    # response = await analyze_receipt_request(image_path_blurry, locale="es-ES")
    # print(response)

    print("\nAnalyzing a moved-angle receipt document...")
    image_path_moved = "./scripts/poc/sample_documents/receipts/20251217_213133_moved_angle.jpg"
    response = await analyze_receipt_request(image_path_moved, locale="es-ES")
    print(response)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Document Intelligence Client Test")
    parser.add_argument("action", type=str, help="Action to perform: invoice or receipt", choices=["invoice", "receipt"])
    args = parser.parse_args()
    if args.action == "invoice":
        asyncio.run(run_invoce_tests())
    elif args.action == "receipt":
        asyncio.run(run_receipt_tests())

