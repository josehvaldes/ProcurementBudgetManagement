"""Custom exceptions for the procurement budget management system."""


class ProcurementException(Exception):
    """Base exception for all procurement-related errors."""
    pass


class InvoiceNotFoundException(ProcurementException):
    """Raised when an invoice cannot be found in storage."""
    pass


class DocumentExtractionException(ProcurementException):
    """Raised when document extraction fails."""
    pass


class StorageException(ProcurementException):
    """Raised when storage operations fail."""
    pass


class InvalidInvoiceStateException(ProcurementException):
    """Raised when an invoice is in an invalid state for the requested operation."""
    pass


class BudgetException(ProcurementException):
    """Raised when budget operations fail."""
    pass


class ValidationException(ProcurementException):
    """Raised when validation fails."""
    pass