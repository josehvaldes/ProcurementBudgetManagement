"""
Validation Agent - Validates invoices against business rules and policies.

This agent is responsible for:
- Performing deterministic validations (vendor matching, duplicate detection)
- Executing AI-powered validations (pricing, compliance checks)
- Managing invoice state transitions (VALIDATED, FAILED, MANUAL_REVIEW)
- Publishing validation completion events
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from langsmith import traceable
from agents.base_agent import BaseAgent
from agents.validation_agent.tools.agentic_validator import AgenticValidator
from agents.validation_agent.tools.deterministic_validator import DeterministicValidator, ValidationResult
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from shared.models.invoice import Invoice, InvoiceState
from shared.utils.constants import InvoiceSubjects, SubscriptionNames
from shared.config.settings import settings
from shared.utils.exceptions import (
    InvoiceNotFoundException,
    ValidationException,
    StorageException
)


class ValidationAgent(BaseAgent):
    """
    Validation Agent validates extracted invoice data.
    
    This agent performs multi-stage validation:
    1. Deterministic validations (vendor matching, duplicates, spending limits)
    2. AI-powered validations (pricing analysis, compliance checks)
    3. State management (VALIDATED, FAILED, MANUAL_REVIEW)
    
    Attributes:
        agent_name (str): Agent identifier
        vendor_table_client (TableStorageService): Vendor repository
        deterministic_validation_tool (DeterministicValidator): Rule-based validator
        ai_validator (AgenticValidator): AI-powered validator
    """
    
    def __init__(self, shutdown_event: Optional[asyncio.Event] = None):
        """
        Initialize the Validation Agent.
        
        Args:
            shutdown_event: Event to signal graceful shutdown
        """
        super().__init__(
            agent_name="ValidationAgent",
            subscription_name=SubscriptionNames.VALIDATION_AGENT,
            shutdown_event=shutdown_event or asyncio.Event()
        )

        self.vendor_table_client: Optional[TableStorageService] = None
        self.deterministic_validation_tool: Optional[DeterministicValidator] = None
        self.ai_validator: Optional[AgenticValidator] = None

        try:
            # Initialize vendor repository
            self.vendor_table_client = TableStorageService(
                storage_account_url=settings.table_storage_account_url,
                table_name=settings.vendors_table_name
            )

            # Initialize validation tools
            self.deterministic_validation_tool = DeterministicValidator(
                vendor_table=self.vendor_table_client,
                invoice_table=self.invoice_table_client
            )

            self.ai_validator = AgenticValidator()

            self.logger.info(
                "ValidationAgent initialized successfully",
                extra={
                    "agent_name": self.agent_name,
                    "subscription": SubscriptionNames.VALIDATION_AGENT,
                    "vendor_table": settings.vendors_table_name
                }
            )
        except Exception as e:
            self.logger.error(
                f"Failed to initialize ValidationAgent: {str(e)}",
                exc_info=True,
                extra={"error_type": type(e).__name__}
            )
            raise

    async def release_resources(self) -> None:
        """
        Release resources held by the agent.
        
        Performs cleanup of Azure service clients and validation tools.
        Should be called during graceful shutdown.
        """
        self.logger.info(
            f"Releasing resources for {self.agent_name}",
            extra={"agent_name": self.agent_name}
        )
        
        cleanup_errors = []
        
        # Close vendor table client
        if self.vendor_table_client:
            try:
                await self.vendor_table_client.close()
                self.logger.debug("Vendor table client closed successfully")
            except Exception as e:
                error_msg = f"Error closing vendor table client: {str(e)}"
                self.logger.warning(error_msg, exc_info=True)
                cleanup_errors.append(error_msg)
        
        # Close AI validator (if it has resources)
        if self.ai_validator:
            try:
                if hasattr(self.ai_validator, 'close'):
                    await self.ai_validator.close()
                self.logger.debug("AI validator closed successfully")
            except Exception as e:
                error_msg = f"Error closing AI validator: {str(e)}"
                self.logger.warning(error_msg, exc_info=True)
                cleanup_errors.append(error_msg)
        
        if cleanup_errors:
            self.logger.warning(
                f"Resource cleanup completed with {len(cleanup_errors)} errors",
                extra={"cleanup_errors": cleanup_errors}
            )
        else:
            self.logger.info("All resources released successfully")

    @traceable(
        name="validation_agent.process_invoice",
        tags=["validation", "agent", "compliance"],
        metadata={"version": "1.0", "agent": "ValidationAgent"}
    )
    async def process_invoice(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate an invoice using deterministic and AI-powered rules.
        
        This method orchestrates the complete validation workflow:
        1. Retrieve invoice from Table Storage
        2. Execute deterministic validations (vendor, duplicates, limits)
        3. If passed, execute AI validations (pricing, compliance)
        4. Update invoice state based on validation results
        5. Record warnings and errors
        
        Validation Flow:
        - VALID (deterministic) → AI validation → VALIDATED or FAILED
        - MANUAL_REVIEW (deterministic) → MANUAL_REVIEW state
        - FAILED (deterministic) → FAILED state
        
        Args:
            message_data: Message payload containing:
                - invoice_id (str): Unique invoice identifier
                - department_id (str): Department identifier
                - correlation_id (str, optional): Correlation ID for tracing
                
        Returns:
            Dict containing:
                - invoice_id (str): Invoice identifier
                - department_id (str): Department identifier
                - state (str): New invoice state
                - event_type (str): Event type for next stage
                - validated_at (str): Validation timestamp
                - validation_passed (bool): Overall validation result
                
        Raises:
            InvoiceNotFoundException: If invoice not found in storage
            ValidationException: If validation process fails
            StorageException: If storage operations fail
        """
        # Extract and validate message data
        invoice_id = message_data.get("invoice_id")
        department_id = message_data.get("department_id")
        correlation_id = message_data.get("correlation_id", invoice_id)
        
        if not invoice_id or not department_id:
            raise ValueError("invoice_id and department_id are required in message_data")
        
        self.logger.info(
            f"Starting invoice validation workflow",
            extra={
                "invoice_id": invoice_id,
                "department_id": department_id,
                "correlation_id": correlation_id,
                "agent": self.agent_name
            }
        )
        
        try:
            # Step 1: Retrieve invoice
            invoice_obj = await self._retrieve_and_validate_invoice(
                department_id=department_id,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            # Step 2: Execute deterministic validations
            deterministic_result = await self._execute_deterministic_validation(
                invoice_obj=invoice_obj,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            # Step 3: Process validation results and update state
            final_state = await self._process_validation_results(
                invoice_obj=invoice_obj,
                deterministic_result=deterministic_result,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            # Step 4: Persist updated invoice
            await self._persist_invoice_state(
                invoice_obj=invoice_obj,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            self.logger.info(
                f"Invoice validation completed",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "final_state": final_state.value,
                    "validation_passed": invoice_obj.validation_passed,
                    "warnings_count": len(invoice_obj.warnings),
                    "errors_count": len(invoice_obj.errors)
                }
            )
            
            return {
                "invoice_id": invoice_id,
                "department_id": department_id,
                "state": invoice_obj.state.value,
                "event_type": "ValidationAgentCompleted",
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "validation_passed": invoice_obj.validation_passed,
                "correlation_id": correlation_id
            }
            
        except InvoiceNotFoundException as e:
            self.logger.error(
                f"Invoice not found: {invoice_id}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "error_type": "InvoiceNotFound"
                },
                exc_info=True
            )
            raise
            
        except ValidationException as e:
            self.logger.error(
                f"Validation failed for invoice: {invoice_id}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "error_type": "ValidationFailed",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise
            
        except StorageException as e:
            self.logger.error(
                f"Storage operation failed for invoice: {invoice_id}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "error_type": "StorageFailure",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise
            
        except Exception as e:
            self.logger.error(
                f"Unexpected error validating invoice: {invoice_id}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise ValidationException(
                f"Failed to validate invoice {invoice_id}: {str(e)}"
            ) from e

    async def _retrieve_and_validate_invoice(
        self,
        department_id: str,
        invoice_id: str,
        correlation_id: str
    ) -> Invoice:
        """
        Retrieve and validate invoice from storage.
        
        Args:
            department_id: Department identifier
            invoice_id: Invoice identifier
            correlation_id: Correlation ID for tracing
            
        Returns:
            Invoice object
            
        Raises:
            InvoiceNotFoundException: If invoice not found
            StorageException: If retrieval fails
        """
        self.logger.debug(
            "Retrieving invoice for validation",
            extra={
                "invoice_id": invoice_id,
                "department_id": department_id,
                "correlation_id": correlation_id
            }
        )
        
        try:
            invoice_data = await self.get_invoice(department_id, invoice_id)
            
            if not invoice_data:
                raise InvoiceNotFoundException(
                    f"Invoice not found: {invoice_id} in department: {department_id}"
                )
            
            invoice_obj = Invoice.from_dict(invoice_data)
            
            self.logger.debug(
                "Invoice retrieved successfully",
                extra={
                    "invoice_id": invoice_id,
                    "current_state": invoice_obj.state.value if invoice_obj.state else "unknown",
                    "vendor_name": invoice_obj.vendor_name or "unknown",
                    "amount": invoice_obj.amount or 0,
                    "correlation_id": correlation_id
                }
            )
            
            return invoice_obj
            
        except InvoiceNotFoundException:
            raise
        except Exception as e:
            raise StorageException(
                f"Failed to retrieve invoice for validation: {str(e)}"
            ) from e

    async def _execute_deterministic_validation(
        self,
        invoice_obj: Invoice,
        invoice_id: str,
        correlation_id: str
    ) -> Any:
        """
        Execute deterministic validation rules.
        
        Deterministic validations include:
        - Vendor matching against approved vendor list
        - Duplicate invoice detection
        - Spending authority limits
        - Required field validation
        
        Args:
            invoice_obj: Invoice to validate
            invoice_id: Invoice identifier for logging
            correlation_id: Correlation ID for tracing
            
        Returns:
            DeterministicValidationResult object
            
        Raises:
            ValidationException: If deterministic validation fails
        """
        self.logger.info(
            "Executing deterministic validations",
            extra={
                "invoice_id": invoice_id,
                "vendor_name": invoice_obj.vendor_name or "unknown",
                "invoice_number": invoice_obj.invoice_number or "unknown",
                "correlation_id": correlation_id
            }
        )
        
        try:
            deterministic_result = await self.deterministic_validation_tool.validate_invoice(
                invoice_obj
            )
            
            self.logger.info(
                f"Deterministic validation completed: {deterministic_result.result.value}",
                extra={
                    "invoice_id": invoice_id,
                    "validation_result": deterministic_result.result.value,
                    "vendor_matched": deterministic_result.matched_vendor is not None,
                    "messages_count": len(deterministic_result.messages),
                    "correlation_id": correlation_id
                }
            )
            
            return deterministic_result
            
        except Exception as e:
            raise ValidationException(
                f"Deterministic validation failed: {str(e)}"
            ) from e

    async def _execute_ai_validation(
        self,
        invoice_obj: Invoice,
        vendor_data: Dict[str, Any],
        invoice_id: str,
        correlation_id: str
    ) -> Any:
        """
        Execute AI-powered validation checks.
        
        AI validations include:
        - Pricing reasonableness analysis
        - Contract compliance verification
        - Invoice format validation
        - Anomaly detection
        
        Args:
            invoice_obj: Invoice to validate
            vendor_data: Matched vendor information
            invoice_id: Invoice identifier for logging
            correlation_id: Correlation ID for tracing
            
        Returns:
            AI validation response
            
        Raises:
            ValidationException: If AI validation fails
        """
        self.logger.info(
            "Executing AI-powered validations",
            extra={
                "invoice_id": invoice_id,
                "vendor_name": invoice_obj.vendor_name,
                "amount": invoice_obj.amount,
                "correlation_id": correlation_id
            }
        )
        
        try:
            ai_response = await self.ai_validator.ainvoke({
                "invoice": invoice_obj.to_dict(),
                "vendor": vendor_data
            })
            
            self.logger.info(
                f"AI validation completed: {'PASSED' if ai_response.passed else 'FAILED'}",
                extra={
                    "invoice_id": invoice_id,
                    "ai_validation_passed": ai_response.passed,
                    "warnings_count": len(ai_response.warnings),
                    "errors_count": len(ai_response.errors),
                    "correlation_id": correlation_id
                }
            )
            
            return ai_response
            
        except Exception as e:
            raise ValidationException(
                f"AI validation failed: {str(e)}"
            ) from e

    async def _process_validation_results(
        self,
        invoice_obj: Invoice,
        deterministic_result: Any,
        invoice_id: str,
        correlation_id: str
    ) -> InvoiceState:
        """
        Process validation results and update invoice state.
        
        Validation State Machine:
        1. VALID (deterministic) → Execute AI validation
           - AI PASSED → VALIDATED
           - AI FAILED → FAILED
        2. MANUAL_REVIEW (deterministic) → MANUAL_REVIEW
        3. FAILED (deterministic) → FAILED
        
        Args:
            invoice_obj: Invoice being validated (modified in-place)
            deterministic_result: Result from deterministic validation
            invoice_id: Invoice identifier for logging
            correlation_id: Correlation ID for tracing
            
        Returns:
            Final invoice state
            
        Raises:
            ValidationException: If result processing fails
        """
        try:
            if deterministic_result.result == ValidationResult.VALID:
                self.logger.info(
                    "Invoice passed deterministic validation, executing AI validation",
                    extra={
                        "invoice_id": invoice_id,
                        "correlation_id": correlation_id
                    }
                )
                
                # Execute AI validation with vendor context
                vendor_data = deterministic_result.matched_vendor.to_dict() if deterministic_result.matched_vendor else {}
                ai_response = await self._execute_ai_validation(
                    invoice_obj=invoice_obj,
                    vendor_data=vendor_data,
                    invoice_id=invoice_id,
                    correlation_id=correlation_id
                )
                
                # Update state based on AI validation
                if ai_response.passed:
                    self.logger.info(
                        f"Invoice {invoice_id} passed all validations",
                        extra={
                            "invoice_id": invoice_id,
                            "correlation_id": correlation_id
                        }
                    )
                    invoice_obj.state = InvoiceState.VALIDATED
                    invoice_obj.validation_passed = True
                else:
                    self.logger.warning(
                        f"Invoice {invoice_id} failed AI validation",
                        extra={
                            "invoice_id": invoice_id,
                            "ai_errors": ai_response.errors,
                            "correlation_id": correlation_id
                        }
                    )
                    invoice_obj.state = InvoiceState.FAILED
                    invoice_obj.validation_passed = False
                
                # Record AI validation messages
                invoice_obj.warnings.extend(
                    self._build_internal_messages("AI_Validation", ai_response.warnings)
                )
                invoice_obj.errors.extend(
                    self._build_internal_messages("AI_Validation", ai_response.errors)
                )
                
            elif deterministic_result.result == ValidationResult.MANUAL_REVIEW:
                self.logger.info(
                    f"Invoice {invoice_id} requires manual review",
                    extra={
                        "invoice_id": invoice_id,
                        "review_reasons": deterministic_result.messages,
                        "correlation_id": correlation_id
                    }
                )
                invoice_obj.state = InvoiceState.MANUAL_REVIEW
                invoice_obj.validation_passed = False
                invoice_obj.errors.extend(
                    self._build_internal_messages("Deterministic_Validation", deterministic_result.messages)
                )
                
            else:  # ValidationResult.FAILED
                self.logger.warning(
                    f"Invoice {invoice_id} failed deterministic validation",
                    extra={
                        "invoice_id": invoice_id,
                        "failure_reasons": deterministic_result.messages,
                        "correlation_id": correlation_id
                    }
                )
                invoice_obj.state = InvoiceState.FAILED
                invoice_obj.validation_passed = False
                invoice_obj.errors.extend(
                    self._build_internal_messages("Deterministic_Validation", deterministic_result.messages)
                )
            
            return invoice_obj.state
            
        except ValidationException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Failed to process validation results: {str(e)}"
            ) from e

    async def _persist_invoice_state(
        self,
        invoice_obj: Invoice,
        invoice_id: str,
        correlation_id: str
    ) -> None:
        """
        Persist updated invoice state to storage.
        
        Args:
            invoice_obj: Invoice with updated state
            invoice_id: Invoice identifier for logging
            correlation_id: Correlation ID for tracing
            
        Raises:
            StorageException: If persistence fails
        """
        self.logger.debug(
            "Persisting invoice validation results",
            extra={
                "invoice_id": invoice_id,
                "new_state": invoice_obj.state.value,
                "validation_passed": invoice_obj.validation_passed,
                "correlation_id": correlation_id
            }
        )
        
        try:
            update_successful = await self.update_invoice(invoice_obj.to_dict())
            
            if not update_successful:
                raise StorageException(
                    f"Failed to update invoice in storage: {invoice_id}"
                )
            
            self.logger.info(
                "Invoice state persisted successfully",
                extra={
                    "invoice_id": invoice_id,
                    "state": invoice_obj.state.value,
                    "correlation_id": correlation_id
                }
            )
            
        except Exception as e:
            raise StorageException(
                f"Failed to persist invoice state: {str(e)}"
            ) from e

    def _build_internal_messages(self, source: str, messages: list) -> list:
        """
        Build standardized internal messages for warnings/errors.
        
        Args:
            source: Source of the messages (e.g., "AI_Validation", "Deterministic_Validation")
            messages: List of message strings
            
        Returns:
            List of formatted message dictionaries
        """
        return [
            {
                "source": source,
                "message": msg,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            for msg in messages
        ]
    
    def get_next_subject(self) -> str:
        """
        Get the message subject for the next processing stage.
        
        Returns:
            Subject name for invoice.validated messages
        """
        return InvoiceSubjects.VALIDATED.value


if __name__ == "__main__":
    agent = ValidationAgent()
    agent.setup_signal_handlers()
    asyncio.run(agent.run())

