
### Field Mapping: DocumentAnalyzer prebuilt Invoice Model -> Invoice Model

```
invoice.vendor_name = "VendorName"
invoice.invoice_id = "InvoiceId
invoice.issued_date = "InvoiceDate" 
invoice.due_date = "DueDate" 
invoice.amount = "InvoiceTotal"
invoice.subtotal = "SubTotal"
invoice.tax_amount = "TotalTax"
```


### Field Mapping: DocumentAnalyzer prebuilt Receipt Model -> Invoice Model

```
invoice.vendor_name = "MerchantName"
invoice.invoice_id = "ReceiptNumber"
invoice.issued_date = "TransactionDate"
invoice.amount = "Total"
```


## Field Mapping: pyzbar.decode ->  QRInfo
data = obj.data.decode('utf-8')
QRInfo(data=data)