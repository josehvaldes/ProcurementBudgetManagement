"""
Azure Document Intelligence client wrapper for OCR and document extraction.
"""

import logging
from typing import Optional, Dict, Any, List
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.identity.aio import DefaultAzureCredential
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentAnalysisFeature, AnalyzeResult

logger = logging.getLogger(__name__)


class DocumentIntelligenceWrapper:
    """
    Wrapper for Azure Document Intelligence (Form Recognizer) operations.
    Handles invoice and receipt extraction.
    """
    
    def __init__(self, endpoint: str):
        """
        Initialize Document Intelligence client.
        
        Args:
            endpoint: Azure Document Intelligence endpoint
        """
        self.endpoint = endpoint
        self.client:DocumentIntelligenceClient = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential()
        )

    async def analyze_invoice(self, document_data: bytes, locale: str = "en-US", additional_fields:list[str] = [] ) -> list[Dict[str, Any]]:
        """
        Analyze an invoice document using the prebuilt invoice model.
        Args:
            document_data: Invoice document bytes
            locale: Locale for analysis (default: "en-US")
            additional_fields: List of additional fields to extract
        Returns:
            Extracted invoice data
        """
        try:
            analyze_request = AnalyzeDocumentRequest(bytes_source=document_data)
            
            if additional_fields and len(additional_fields) > 0:
                logger.info(f"Analyzing invoice with additional fields: {additional_fields}")
                poller = await self.client.begin_analyze_document(
                    model_id="prebuilt-invoice", 
                    body=analyze_request,
                    locale=locale, 
                    features=[DocumentAnalysisFeature.QUERY_FIELDS],
                    query_fields=additional_fields
                )
            else:
                poller = await self.client.begin_analyze_document(
                    model_id="prebuilt-invoice", 
                    body=analyze_request,
                    locale=locale
                )

            result = poller.result()
            return self._extract_invoice_data(result, additional_fields)
        except Exception as e:
            logger.error(f"Failed to analyze invoice from bytes: {e}")
            raise
    
    def _extract_invoice_data(self, result:AnalyzeResult, additional_fields: list[str]) -> list[dict[str, Any]]:
        """Extract structured data from invoice analysis result."""
        # Define default fields to extract
        fields = [
            "VendorName",
            "VendorAddress",
            "InvoiceId",
            "InvoiceDate",
            "DueDate",
            "InvoiceTotal", #float
            "SubTotal",
            "TotalTax",
        ]

        fields.extend(additional_fields)

        document_list = []
        for idx, document in enumerate(result.documents):
            logger.info(f"Extracting data from invoice document #{idx + 1}")
            document_data = {}
            fields = document.fields
            for field_name in additional_fields:
                if field_name in fields:
                    prop = fields.get(field_name)
                    document_data[field_name] = {
                        "value": prop.value_object,
                        "confidence": prop.confidence
                    }
            
            vendor_name = fields.get("VendorName")
            if vendor_name:
                document_data["VendorName"] = {
                    "value": vendor_name.value_string,
                    "confidence": vendor_name.confidence
                }
            
            vendor_address = fields.get("VendorAddress")
            if vendor_address:
                document_data["VendorAddress"] = {
                    "value": vendor_address.value_string,
                    "confidence": vendor_address.confidence
                }

            # Extract invoice details
            invoice_id = fields.get("InvoiceId")
            if invoice_id:
                document_data["InvoiceId"] = {
                    "value": invoice_id.value_string,
                    "confidence": invoice_id.confidence
                }

            invoice_date = fields.get("InvoiceDate")
            if invoice_date:
                document_data["InvoiceDate"] = {
                    "value": invoice_date.value_date,
                    "confidence": invoice_date.confidence
                }

            due_date = fields.get("DueDate")
            if due_date:
                document_data["DueDate"] = {
                    "value": due_date.value_date,
                    "confidence": due_date.confidence
                }

            # Extract amounts
            invoice_total = fields.get("InvoiceTotal")
            if invoice_total:
                document_data["InvoiceTotal"] = {
                    "value": invoice_total.value_currency.amount,
                    "confidence": invoice_total.confidence
                }
                
            sub_total = fields.get("SubTotal")
            if sub_total:
                document_data["SubTotal"] = {
                    "value": sub_total.value_currency.amount,
                    "confidence": sub_total.confidence
                }

            total_tax = fields.get("TotalTax")
            if total_tax:
                document_data["TotalTax"] = {
                    "value": total_tax.value_currency.amount,
                    "confidence": total_tax.confidence
                }
            document_list.append(document_data)
        
        return document_list


    async def analyze_receipt(self, document_data: bytes, locale: str = "en-US", additional_fields:list[str] = [] ) -> list[Dict[str, Any]]:
        """
        Analyze a receipt document using the prebuilt receipt model.
        Args:
            document_data: Receipt document bytes
            locale: Locale for analysis (default: "en-US")
            additional_fields: List of additional fields to extract            
        Returns:
            Extracted receipt data
        """

        try:
            analyze_request = AnalyzeDocumentRequest(bytes_source=document_data)
            
            if additional_fields and len(additional_fields) > 0:
                logger.info(f"Analyzing receipt with additional fields: {additional_fields}")
                poller = await self.client.begin_analyze_document(
                    model_id="prebuilt-receipt", 
                    body=analyze_request,
                    locale=locale, 
                    features=[DocumentAnalysisFeature.QUERY_FIELDS],
                    query_fields=additional_fields
                )
            else:
                poller = await self.client.begin_analyze_document(
                    model_id="prebuilt-receipt", 
                    body=analyze_request,
                    locale=locale, 
                )
            result = poller.result()
            
            # Extract receipt data
            receipt_data = self._extract_receipt_data(result, additional_fields)
            logger.info("Receipt analysis completed successfully")
            return receipt_data
            
        except Exception as e:
            logger.error(f"Failed to analyze receipt: {e}")
            raise


    def _extract_receipt_data(self, result, additional_fields: list[str]) -> list[Dict[str, Any]]:
        """Extract structured data from receipt analysis result."""
        
        field_names = [
            "MerchantName",
            "ReceiptType",
            "TransactionDate",
            "Total",
            "ReceiptNumber",
        ]

        field_names.extend(additional_fields)

        document_list = []
        for idx, document in enumerate(result.documents):
            logger.info(f"Extracting data from receipt document #{idx + 1}")
            document_data = {}
            fields = document.fields
            for field_name in additional_fields:
                if field_name in fields:
                    prop = fields.get(field_name)
                    document_data[field_name] = {
                        "value": prop.value_object,
                        "confidence": prop.confidence
                    }
            
            merchant_name = fields.get("MerchantName")
            if merchant_name:
                document_data["MerchantName"] = {
                    "value": merchant_name.value_string,
                    "confidence": merchant_name.confidence
                }
            
            receipType = fields.get("ReceiptType")
            if receipType:
                document_data["ReceiptType"] = {
                    "value": receipType.value_string,
                    "confidence": receipType.confidence
                }
            
            transaction_date = fields.get("TransactionDate")
            if transaction_date:
                document_data["TransactionDate"] = {
                    "value": transaction_date.value_date,
                    "confidence": transaction_date.confidence
                }
            
            total = fields.get("Total")
            if total:
                document_data["Total"] = {
                    "value": total.value_currency.amount,
                    "confidence": total.confidence
                }
            
            receiptNumber = fields.get("ReceiptNumber")
            if receiptNumber:
                document_data["ReceiptNumber"] = {
                    "value": receiptNumber.value_string,
                    "confidence": receiptNumber.confidence
                }
            document_list.append(document_data)

        return document_list
