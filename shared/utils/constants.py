"""
Constants and enumerations for the invoice lifecycle.
"""

from enum import Enum


class InvoiceSubjects:
    """Service Bus message subjects for invoice state changes."""
    CREATED = "invoice.created"
    EXTRACTED = "invoice.extracted"
    VALIDATED = "invoice.validated"
    BUDGET_CHECKED = "invoice.budget_checked"
    APPROVED = "invoice.approved"
    PAYMENT_SCHEDULED = "invoice.payment_scheduled"
    PAID = "invoice.paid"
    FAILED = "invoice.failed"
    MANUAL_REVIEW = "invoice.manual_review"


class TABLE_NAMES:
    """Azure Table Storage table names."""
    INVOICES = "invoices"
    VENDORS = "vendors"
    BUDGETS = "budgets"
    AUDIT_TRAIL = "audittrail"


# Valid state transitions for invoice state machine
VALID_STATE_TRANSITIONS = {
    "CREATED": ["EXTRACTED", "FAILED"],
    "EXTRACTED": ["VALIDATED", "FAILED"],
    "VALIDATED": ["BUDGET_CHECKED", "FAILED"],
    "BUDGET_CHECKED": ["APPROVED", "MANUAL_REVIEW", "FAILED"],
    "APPROVED": ["PAYMENT_SCHEDULED", "FAILED"],
    "PAYMENT_SCHEDULED": ["PAID", "FAILED"],
    "MANUAL_REVIEW": ["CREATED", "EXTRACTED", "VALIDATED", "BUDGET_CHECKED", "APPROVED", "FAILED"],
    "FAILED": ["CREATED"],
    "PAID": [],
}


# Subscription names for each agent
class SubscriptionNames:
    """Azure Service Bus subscription names."""
    INTAKE_AGENT = "intake-agent-subscription"
    VALIDATION_AGENT = "validation-agent-subscription"
    BUDGET_AGENT = "budget-agent-subscription"
    APPROVAL_AGENT = "approval-agent-subscription"
    PAYMENT_AGENT = "payment-agent-subscription"
    ANALYTICS_AGENT = "analytics-agent-subscription"


# Agent message filters (SQL filter expressions)
class AgentFilters:
    """SQL filters for agent subscriptions."""
    INTAKE = f"subject = '{InvoiceSubjects.CREATED}'"
    VALIDATION = f"subject = '{InvoiceSubjects.EXTRACTED}'"
    BUDGET = f"subject = '{InvoiceSubjects.VALIDATED}'"
    APPROVAL = f"subject = '{InvoiceSubjects.BUDGET_CHECKED}'"
    PAYMENT = f"subject = '{InvoiceSubjects.APPROVED}'"
    ANALYTICS = "1=1"  # Receives all messages
