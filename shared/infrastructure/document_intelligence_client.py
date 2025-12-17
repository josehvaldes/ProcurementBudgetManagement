"""
Azure Document Intelligence client wrapper for OCR and document extraction.
"""

import logging
from typing import Optional, Dict, Any, List
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)


class DocumentIntelligenceClient:
    """
    Wrapper for Azure Document Intelligence (Form Recognizer) operations.
    Handles invoice and receipt extraction.
    """
    
    def __init__(self, endpoint: str, api_key: str):
        """
        Initialize Document Intelligence client.
        
        Args:
            endpoint: Azure Document Intelligence endpoint
            api_key: API key for authentication
        """
        self.endpoint = endpoint
        self.client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )
    
    def analyze_invoice(self, document_url: str) -> Dict[str, Any]:
        """
        Analyze an invoice document using the prebuilt invoice model.
        
        Args:
            document_url: URL to the invoice document (PDF, JPG, PNG)
            
        Returns:
            Extracted invoice data
        """
        try:
            logger.info(f"Analyzing invoice from URL: {document_url}")
            poller = self.client.begin_analyze_document_from_url(
                "prebuilt-invoice",
                document_url
            )
            result = poller.result()
            
            # Extract invoice data
            invoice_data = self._extract_invoice_data(result)
            logger.info("Invoice analysis completed successfully")
            return invoice_data
            
        except Exception as e:
            logger.error(f"Failed to analyze invoice: {e}")
            raise
    
    def analyze_receipt(self, document_url: str) -> Dict[str, Any]:
        """
        Analyze a receipt document using the prebuilt receipt model.
        
        Args:
            document_url: URL to the receipt document (JPG, PNG)
            
        Returns:
            Extracted receipt data
        """
        try:
            logger.info(f"Analyzing receipt from URL: {document_url}")
            poller = self.client.begin_analyze_document_from_url(
                "prebuilt-receipt",
                document_url
            )
            result = poller.result()
            
            # Extract receipt data
            receipt_data = self._extract_receipt_data(result)
            logger.info("Receipt analysis completed successfully")
            return receipt_data
            
        except Exception as e:
            logger.error(f"Failed to analyze receipt: {e}")
            raise
    
    def _extract_invoice_data(self, result) -> Dict[str, Any]:
        """Extract structured data from invoice analysis result."""
        invoice_data = {
            "vendor_name": None,
            "vendor_address": None,
            "customer_name": None,
            "invoice_id": None,
            "invoice_date": None,
            "due_date": None,
            "invoice_total": None,
            "amount_due": None,
            "subtotal": None,
            "total_tax": None,
            "line_items": [],
            "confidence_scores": {},
        }
        
        for document in result.documents:
            fields = document.fields
            
            # Extract vendor information
            if "VendorName" in fields and fields["VendorName"].value:
                invoice_data["vendor_name"] = fields["VendorName"].value
                invoice_data["confidence_scores"]["vendor_name"] = fields["VendorName"].confidence
            
            if "VendorAddress" in fields and fields["VendorAddress"].value:
                invoice_data["vendor_address"] = fields["VendorAddress"].value
            
            # Extract invoice details
            if "InvoiceId" in fields and fields["InvoiceId"].value:
                invoice_data["invoice_id"] = fields["InvoiceId"].value
            
            if "InvoiceDate" in fields and fields["InvoiceDate"].value:
                invoice_data["invoice_date"] = fields["InvoiceDate"].value.isoformat()
            
            if "DueDate" in fields and fields["DueDate"].value:
                invoice_data["due_date"] = fields["DueDate"].value.isoformat()
            
            # Extract amounts
            if "InvoiceTotal" in fields and fields["InvoiceTotal"].value:
                invoice_data["invoice_total"] = float(fields["InvoiceTotal"].value.amount)
            
            if "AmountDue" in fields and fields["AmountDue"].value:
                invoice_data["amount_due"] = float(fields["AmountDue"].value.amount)
            
            if "SubTotal" in fields and fields["SubTotal"].value:
                invoice_data["subtotal"] = float(fields["SubTotal"].value.amount)
            
            if "TotalTax" in fields and fields["TotalTax"].value:
                invoice_data["total_tax"] = float(fields["TotalTax"].value.amount)
            
            # Extract line items
            if "Items" in fields and fields["Items"].value:
                for item in fields["Items"].value:
                    line_item = {}
                    item_fields = item.value
                    
                    if "Description" in item_fields:
                        line_item["description"] = item_fields["Description"].value
                    if "Quantity" in item_fields:
                        line_item["quantity"] = item_fields["Quantity"].value
                    if "UnitPrice" in item_fields:
                        line_item["unit_price"] = float(item_fields["UnitPrice"].value.amount)
                    if "Amount" in item_fields:
                        line_item["amount"] = float(item_fields["Amount"].value.amount)
                    
                    invoice_data["line_items"].append(line_item)
        
        return invoice_data
    
    def _extract_receipt_data(self, result) -> Dict[str, Any]:
        """Extract structured data from receipt analysis result."""
        receipt_data = {
            "merchant_name": None,
            "merchant_address": None,
            "merchant_phone": None,
            "transaction_date": None,
            "transaction_time": None,
            "total": None,
            "subtotal": None,
            "tax": None,
            "tip": None,
            "items": [],
        }
        
        for document in result.documents:
            fields = document.fields
            
            if "MerchantName" in fields and fields["MerchantName"].value:
                receipt_data["merchant_name"] = fields["MerchantName"].value
            
            if "MerchantAddress" in fields and fields["MerchantAddress"].value:
                receipt_data["merchant_address"] = fields["MerchantAddress"].value
            
            if "TransactionDate" in fields and fields["TransactionDate"].value:
                receipt_data["transaction_date"] = fields["TransactionDate"].value.isoformat()
            
            if "Total" in fields and fields["Total"].value:
                receipt_data["total"] = float(fields["Total"].value.amount)
            
            if "Subtotal" in fields and fields["Subtotal"].value:
                receipt_data["subtotal"] = float(fields["Subtotal"].value.amount)
            
            if "TotalTax" in fields and fields["TotalTax"].value:
                receipt_data["tax"] = float(fields["TotalTax"].value.amount)
            
            # Extract items
            if "Items" in fields and fields["Items"].value:
                for item in fields["Items"].value:
                    item_data = {}
                    item_fields = item.value
                    
                    if "Description" in item_fields:
                        item_data["description"] = item_fields["Description"].value
                    if "TotalPrice" in item_fields:
                        item_data["total_price"] = float(item_fields["TotalPrice"].value.amount)
                    
                    receipt_data["items"].append(item_data)
        
        return receipt_data
