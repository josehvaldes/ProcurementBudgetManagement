import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, mock_open, patch
from agents.intake_agent.tools.invoice_analyzer_tool import InvoiceAnalyzerTool

class TestInvoiceAnalyzerTool:
    """Unit tests for InvoiceAnalyzerTool with mocked external dependencies."""

    @pytest.fixture
    def mock_wrapper(self):
        """Create a mock DocumentIntelligenceWrapper."""
        return Mock()

    @pytest.fixture
    def tool(self, mock_wrapper):
        """Create InvoiceAnalyzerTool instance with mocked wrapper."""
        with patch('agents.intake_agent.tools.invoice_analyzer_tool.DocumentIntelligenceWrapper', return_value=mock_wrapper):
            with patch('agents.intake_agent.tools.invoice_analyzer_tool.settings') as mock_settings:
                mock_settings.document_intelligence_endpoint = "https://fake-endpoint.com"
                return InvoiceAnalyzerTool()

    @pytest.mark.asyncio
    async def test_analyze_invoice_request_success_with_all_fields(self, tool):
        """Test successful invoice analysis with all fields populated."""
        mock_invoice_data = {
            "VendorName": {"value": "Acme Corp"},
            "InvoiceId": {"value": "INV-2024-001"},
            "InvoiceDate": {"value": "2024-01-15"},
            "DueDate": {"value": "2024-02-15"},
            "InvoiceTotal": {"value": 2500.75},
            "SubTotal": {"value": 2250.00},
            "TotalTax": {"value": 250.75}
        }
        tool.document_intelligence_wrapper.analyze_invoice = AsyncMock(return_value=[mock_invoice_data])
        
        result = await tool.analyze_invoice_request(b"fake_pdf_data", "en-US")
        
        assert result["vendor_name"] == "Acme Corp"
        assert result["invoice_id"] == "INV-2024-001"
        assert result["issued_date"] == "2024-01-15"
        assert result["due_date"] == "2024-02-15"
        assert result["amount"] == Decimal("2500.75")
        assert result["subtotal"] == Decimal("2250.00")
        assert result["tax_amount"] == Decimal("250.75")
        tool.document_intelligence_wrapper.analyze_invoice.assert_called_once_with(
            document_data=b"fake_pdf_data",
            locale="en-US"
        )

    @pytest.mark.asyncio
    async def test_analyze_invoice_request_empty_response(self, tool):
        """Test invoice analysis when API returns empty list."""
        tool.document_intelligence_wrapper.analyze_invoice = AsyncMock(return_value=[])
        
        result = await tool.analyze_invoice_request(b"fake_data")
        
        assert result["vendor_name"] == ""
        assert result["invoice_id"] == ""
        assert result["issued_date"] is None
        assert result["due_date"] is None
        assert result["amount"] == Decimal("0.0")
        assert result["subtotal"] == Decimal("0.0")
        assert result["tax_amount"] == Decimal("0.0")

    @pytest.mark.asyncio
    async def test_analyze_invoice_request_missing_fields(self, tool):
        """Test invoice analysis with missing optional fields."""
        mock_invoice_data = {
            "VendorName": {"value": "Test Vendor"}
        }
        tool.document_intelligence_wrapper.analyze_invoice = AsyncMock(return_value=[mock_invoice_data])
        
        result = await tool.analyze_invoice_request(b"fake_data")
        
        assert result["vendor_name"] == "Test Vendor"
        assert result["invoice_id"] == ""
        assert result["amount"] == Decimal("0.0")

    @pytest.mark.asyncio
    async def test_analyze_invoice_request_with_spanish_locale(self, tool):
        """Test invoice analysis with non-default locale."""
        mock_invoice_data = {"VendorName": {"value": "Empresa Test"}}
        tool.document_intelligence_wrapper.analyze_invoice = AsyncMock(return_value=[mock_invoice_data])
        
        await tool.analyze_invoice_request(b"fake_data", locale="es-ES")
        
        tool.document_intelligence_wrapper.analyze_invoice.assert_called_once_with(
            document_data=b"fake_data",
            locale="es-ES"
        )

    @pytest.mark.asyncio
    async def test_analyze_invoice_request_exception_handling(self, tool):
        """Test that exceptions from wrapper are propagated."""
        tool.document_intelligence_wrapper.analyze_invoice = AsyncMock(
            side_effect=Exception("Document Intelligence API Error")
        )
        
        with pytest.raises(Exception, match="Document Intelligence API Error"):
            await tool.analyze_invoice_request(b"fake_data")

    @pytest.mark.asyncio
    async def test_analyze_invoice_request_file_reads_and_processes(self, tool):
        """Test file-based invoice analysis reads file correctly."""
        mock_file_content = b"fake_pdf_binary_content"
        mock_result = {"invoice_id": "INV-001"}
        
        tool.analyze_invoice_request = AsyncMock(return_value=mock_result)
        
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            result = await tool.analyze_invoice_request_file("/fake/invoice.pdf", "en-US")
        
        tool.analyze_invoice_request.assert_called_once_with(mock_file_content, "en-US")
        assert result == mock_result

    @pytest.mark.asyncio
    async def test_analyze_receipt_request_success(self, tool):
        """Test successful receipt analysis with all fields."""
        mock_receipt_data = {
            "MerchantName": {"value": "Coffee Shop"},
            "ReceiptNumber": {"value": "REC-12345"},
            "TransactionDate": {"value": "2024-01-20"},
            "Total": {"value": 15.99}
        }
        tool.document_intelligence_wrapper.analyze_receipt = AsyncMock(return_value=[mock_receipt_data])
        
        result = await tool.analyze_receipt_request(b"fake_receipt_image", "en-US")
        
        assert result["vendor_name"] == "Coffee Shop"
        assert result["invoice_number"] == "REC-12345"
        assert result["issued_date"] == "2024-01-20"
        assert result["amount"] == 15.99
        tool.document_intelligence_wrapper.analyze_receipt.assert_called_once_with(
            document_data=b"fake_receipt_image",
            locale="en-US",
            additional_fields=["ReceiptNumber"]
        )

    @pytest.mark.asyncio
    async def test_analyze_receipt_request_empty_response(self, tool):
        """Test receipt analysis with empty response."""
        tool.document_intelligence_wrapper.analyze_receipt = AsyncMock(return_value=[])
        
        result = await tool.analyze_receipt_request(b"fake_data")
        
        assert result["vendor_name"] == ""
        assert result["invoice_number"] == ""
        assert result["issued_date"] is None
        assert result["amount"] == 0.0

    @pytest.mark.asyncio
    async def test_analyze_receipt_request_missing_fields(self, tool):
        """Test receipt analysis with missing fields."""
        mock_receipt_data = {"MerchantName": {"value": "Store"}}
        tool.document_intelligence_wrapper.analyze_receipt = AsyncMock(return_value=[mock_receipt_data])
        
        result = await tool.analyze_receipt_request(b"fake_data")
        
        assert result["vendor_name"] == "Store"
        assert result["invoice_number"] == ""
        assert result["amount"] == 0.0

    @pytest.mark.asyncio
    async def test_analyze_receipt_request_exception_handling(self, tool):
        """Test receipt analysis exception propagation."""
        tool.document_intelligence_wrapper.analyze_receipt = AsyncMock(
            side_effect=Exception("Receipt API Error")
        )
        
        with pytest.raises(Exception, match="Receipt API Error"):
            await tool.analyze_receipt_request(b"fake_data")

    @pytest.mark.asyncio
    async def test_analyze_receipt_request_file_reads_correctly(self, tool):
        """Test file-based receipt analysis."""
        mock_file_content = b"fake_image_binary"
        mock_result = {"invoice_number": "REC-999"}
        
        tool.analyze_receipt_request = AsyncMock(return_value=mock_result)
        
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            result = await tool.analyze_receipt_request_file("/fake/receipt.jpg", "es-ES")
        
        tool.analyze_receipt_request.assert_called_once_with(mock_file_content, "es-ES")
        assert result == mock_result

    @pytest.mark.asyncio
    async def test_close_releases_resources(self, tool):
        """Test that close method releases wrapper resources."""
        tool.document_intelligence_wrapper.close = AsyncMock()
        
        await tool.close()
        
        tool.document_intelligence_wrapper.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_none_wrapper(self):
        """Test close when wrapper is None."""
        with patch('agents.intake_agent.tools.invoice_analyzer_tool.DocumentIntelligenceWrapper'):
            with patch('agents.intake_agent.tools.invoice_analyzer_tool.settings') as mock_settings:
                mock_settings.document_intelligence_endpoint = "https://fake.com"
                tool = InvoiceAnalyzerTool()
                tool.document_intelligence_wrapper = None
                
                await tool.close()  # Should not raise exception