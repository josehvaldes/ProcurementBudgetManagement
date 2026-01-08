import json
from unittest.mock import AsyncMock, Mock, patch
import uuid

import pytest
from shared.config.settings import settings
from shared.models.vendor import Vendor
from shared.utils.logging_config import get_logger, setup_logging
from shared.models.invoice import Invoice
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from agents.validation_agent.tools.deterministic_validator import DeterministicValidator, ValidationResponse, ValidationResult

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)


class TestValidationAgent:
    """Test suite for ValidationAgent using pytest."""
    
    @pytest.fixture
    def invoice(self):
        """Load invoice test data."""
        invoice_path = "./scripts/poc/sample_documents/invoice_entity.json"
        with open(invoice_path, "r") as f:
            invoice_data = json.load(f)
            return Invoice.from_dict(invoice_data)

    @pytest.fixture
    def vendor(self):
        """Load vendor test data."""
        vendor_path = "./scripts/poc/sample_documents/vendor_entity.json"
        with open(vendor_path, "r") as f:
            vendor_data = json.load(f)
            return Vendor.from_dict(vendor_data)

    @pytest.fixture
    def mock_vendor_table(self):
        """Create a mock vendor table storage service."""
        mock = AsyncMock(spec=TableStorageService)
        mock.close = AsyncMock()
        return mock

    @pytest.fixture
    def mock_invoice_table(self):
        """Create a mock invoice table storage service."""
        mock = AsyncMock(spec=TableStorageService)
        mock.close = AsyncMock()
        return mock

    @pytest.fixture
    def validator(self, mock_vendor_table, mock_invoice_table):
        """Create DeterministicValidator with mocked dependencies."""
        return DeterministicValidator(
            vendor_table=mock_vendor_table,
            invoice_table=mock_invoice_table
        )

    @pytest.mark.asyncio
    async def test_validate_invoice_valid(self, validator, invoice, vendor):
        """Test validation of a valid invoice with matching vendor."""
        # Arrange
        invoice.vendor_name = vendor.name  # Ensure vendor name matches
        validator.vendor_table.query_entities = AsyncMock(return_value=[vendor.to_dict()])
        validator.invoice_table.query_entities = AsyncMock(return_value=[])

        # Act
        response: ValidationResponse = await validator.validate_invoice(invoice)

        # Assert
        logger.info(f"Validation Result: {response.result}")
        logger.info(f"Messages: {response.messages}")
        assert response.result == ValidationResult.VALID
        assert len(response.messages) == 0
        assert response.matched_vendor is not None
        assert response.matched_vendor.vendor_id == vendor.vendor_id

    @pytest.mark.asyncio
    async def test_false_duplicate_invoice(self, validator, invoice, vendor):
        """Test that invoices with different IDs are not flagged as duplicates."""
        validator.vendor_table.query_entities = AsyncMock(return_value=[vendor.to_dict()])
        
        # Create a different invoice with different ID
        existing_invoice_dict = invoice.to_dict()
        existing_invoice_dict['invoice_id'] = str(uuid.uuid4())
        validator.invoice_table.query_entities = AsyncMock(return_value=[existing_invoice_dict])

        # Act
        is_duplicate = await validator.has_duplicate(invoice)
        
        # Assert
        assert is_duplicate == False

    @pytest.mark.asyncio
    async def test_duplicate_invoice_detection(self, validator, invoice, vendor):
        """Test that true duplicate invoices are detected."""
        # Arrange
        invoice.vendor_name = vendor.name
        validator.vendor_table.query_entities = AsyncMock(return_value=[vendor.to_dict()])
        invoice_1 = invoice.to_dict()
        
        # set the create_date to be different to simulate different entries
        invoice_2 = invoice.to_dict()
        invoice_2['created_date'] = "2026-01-06 22:50:30.097315+00:00"

        # Same invoice ID should be flagged as duplicate
        validator.invoice_table.query_entities = AsyncMock(return_value=[invoice_1, invoice_2])

        # Act
        is_duplicate = await validator.has_duplicate(invoice)
        
        # Assert
        assert is_duplicate == True

    @pytest.mark.asyncio
    async def test_missing_vendor_name(self, validator, invoice, vendor):
        """Test validation fails when vendor name is missing."""
        # Arrange
        validator.vendor_table.query_entities = AsyncMock(return_value=[vendor.to_dict()])
        validator.invoice_table.query_entities = AsyncMock(return_value=[])
        
        invoice.vendor_name = ""  # Simulate missing vendor name
        
        # Act
        response: ValidationResponse = await validator.validate_invoice(invoice)

        # Assert
        assert response.result == ValidationResult.INVALID
        assert any("Vendor name is missing" in msg for msg in response.messages)
        assert response.matched_vendor is None

    @pytest.mark.asyncio
    async def test_vendor_not_found(self, validator, invoice):
        """Test validation fails when vendor doesn't exist."""
        # Arrange
        invoice.vendor_name = "NonExistent Vendor Inc."
        validator.vendor_table.query_entities = AsyncMock(return_value=[])
        validator.invoice_table.query_entities = AsyncMock(return_value=[])
        
        # Act
        response: ValidationResponse = await validator.validate_invoice(invoice)

        # Assert
        assert response.result == ValidationResult.MANUAL_REVIEW
        assert any("Vendor not found" in msg or "not approved" in msg for msg in response.messages)
        assert response.matched_vendor is None

    @pytest.mark.asyncio
    async def test_inactive_vendor(self, validator, invoice, vendor):
        """Test validation fails when vendor is inactive."""
        # Arrange
        vendor.active = False
        invoice.vendor_name = vendor.name
        validator.vendor_table.query_entities = AsyncMock(return_value=[vendor.to_dict()])
        validator.invoice_table.query_entities = AsyncMock(return_value=[])
        
        # Act
        response: ValidationResponse = await validator.validate_invoice(invoice)

        # Assert
        assert response.result == ValidationResult.INVALID
        assert any("not active" in msg.lower() for msg in response.messages)


# For running tests directly with python (not recommended, use pytest instead)
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])