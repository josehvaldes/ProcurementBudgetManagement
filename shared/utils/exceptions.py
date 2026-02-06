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


class MessagingException(Exception):
    """Base exception for messaging operations."""
    pass


class MessagePublishException(MessagingException):
    """Exception raised when message publishing fails."""
    pass


class ServiceBusConnectionException(MessagingException):
    """Exception raised when Service Bus connection fails."""
    pass


class TableStorageException(Exception):
    """Base exception for table storage operations."""
    pass


class EntityUpsertException(TableStorageException):
    """Exception raised when entity upsert operation fails."""
    pass


class EntityQueryException(TableStorageException):
    """Exception raised when entity query operation fails."""
    pass


class EntityDeleteException(TableStorageException):
    """Exception raised when entity delete operation fails."""
    pass

class EntityNotFoundException(TableStorageException):
    """Exception raised when an entity is not found in table storage."""
    pass

