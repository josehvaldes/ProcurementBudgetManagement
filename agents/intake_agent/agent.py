"""
Intake Agent - Extracts data from invoice documents using Azure Document Intelligence.

This agent is responsible for:
- Processing newly uploaded invoices
- Extracting structured data using Azure Document Intelligence
- Detecting and extracting QR codes
- Transitioning invoices to EXTRACTED state
- Publishing extraction completion events
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from agents.base_agent import BaseAgent
from agents.intake_agent.tools.invoice_analyzer_tool import InvoiceAnalyzerTool
from agents.intake_agent.tools.qr_extractor import get_qr_info_from_bytes
from shared.models.invoice import Invoice, InvoiceState
from shared.utils.constants import InvoiceSubjects, SubscriptionNames
from invoice_lifecycle_api.infrastructure.repositories.invoice_storage_service import InvoiceStorageService 
from shared.config.settings import settings
from shared.utils.exceptions import (
    InvoiceNotFoundException,
    DocumentExtractionException,
    StorageException,
    InvalidInvoiceStateException
)

from langsmith import traceable


class IntakeAgent(BaseAgent):
    """
    Intake Agent for invoice document processing.
    
    This agent orchestrates the document intelligence extraction workflow,
    handling both invoices and receipts with QR code detection capabilities.
    
    Attributes:
        agent_name (str): Agent identifier
        blob_storage_client (InvoiceStorageService): Azure Blob Storage client
        invoice_analyzer_tool (InvoiceAnalyzerTool): Document Intelligence wrapper
    """

    def __init__(self, shutdown_event: Optional[asyncio.Event] = None):
        """
        Initialize the Intake Agent.
        
        Args:
            shutdown_event: Event to signal graceful shutdown
        """
        super().__init__(
            agent_name="IntakeAgent",
            subscription_name=SubscriptionNames.INTAKE_AGENT,
            shutdown_event=shutdown_event or asyncio.Event()
        )

        self.blob_storage_client: Optional[InvoiceStorageService] = None
        self.invoice_analyzer_tool: Optional[InvoiceAnalyzerTool] = None
        
        try:
            self.blob_storage_client = InvoiceStorageService()
            self.invoice_analyzer_tool = InvoiceAnalyzerTool()
            self.logger.info(
                "IntakeAgent initialized successfully",
                extra={
                    "agent_name": self.agent_name,
                    "subscription": SubscriptionNames.INTAKE_AGENT
                }
            )
        except Exception as e:
            self.logger.error(
                f"Failed to initialize IntakeAgent: {str(e)}",
                exc_info=True,
                extra={"error_type": type(e).__name__}
            )
            raise

    async def release_resources(self) -> None:
        """
        Release resources held by the agent.
        
        Performs cleanup of Azure service clients and connections.
        Should be called during graceful shutdown.
        """
        self.logger.info(
            f"Releasing resources for {self.agent_name}",
            extra={"agent_name": self.agent_name}
        )
        
        cleanup_errors = []
        
        # Close blob storage client
        if self.blob_storage_client:
            try:
                await self.blob_storage_client.close()
                self.logger.debug("Blob storage client closed successfully")
            except Exception as e:
                error_msg = f"Error closing blob storage client: {str(e)}"
                self.logger.warning(error_msg, exc_info=True)
                cleanup_errors.append(error_msg)
        
        # Close invoice analyzer tool
        if self.invoice_analyzer_tool:
            try:
                await self.invoice_analyzer_tool.close()
                self.logger.debug("Invoice analyzer tool closed successfully")
            except Exception as e:
                error_msg = f"Error closing invoice analyzer tool: {str(e)}"
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
        name="intake_agent.process_invoice",
        tags=["intake", "agent", "document_extraction"],
        metadata={"version": "1.0", "agent": "IntakeAgent"}
    )
    async def process_invoice(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an invoice by extracting structured data from the document.
        
        This method orchestrates the complete extraction workflow:
        1. Retrieve invoice metadata from Table Storage
        2. Download document from Blob Storage
        3. Extract data using Azure Document Intelligence
        4. Detect and extract QR codes
        5. Update invoice state to EXTRACTED
        
        Args:
            message_data: Message payload containing:
                - invoice_id (str): Unique invoice identifier
                - department_id (str): Department identifier
                - timestamp (str, optional): Message timestamp
                
        Returns:
            Dict containing:
                - invoice_id (str): Invoice identifier
                - department_id (str): Department identifier
                - event_type (str): Event type for next stage
                - state (str): New invoice state
                - extracted_at (str): Extraction timestamp
                
        Raises:
            InvoiceNotFoundException: If invoice not found in storage
            DocumentExtractionException: If document extraction fails
            StorageException: If storage operations fail
            InvalidInvoiceStateException: If invoice is in invalid state
        """
        # Extract and validate message data
        invoice_id = message_data.get("invoice_id")
        department_id = message_data.get("department_id")
        correlation_id = message_data.get("correlation_id", invoice_id)
        
        if not invoice_id or not department_id:
            raise ValueError("invoice_id and department_id are required in message_data")
        
        self.logger.info(
            f"Starting invoice extraction workflow",
            extra={
                "invoice_id": invoice_id,
                "department_id": department_id,
                "correlation_id": correlation_id,
                "agent": self.agent_name
            }
        )
        
        try:
            # Step 1: Retrieve invoice metadata
            invoice_data = await self._retrieve_invoice_metadata(
                department_id=department_id,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            # Step 2: Download document from blob storage
            document_bytes = await self._download_invoice_document(
                blob_name=invoice_data["raw_file_blob_name"],
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            # Step 3: Extract structured data
            extracted_data = await self._extract_invoice_data(
                document_bytes=document_bytes,
                document_type=invoice_data["document_type"],
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            # Step 4: Extract QR codes (if present)
            qr_codes = await self._extract_qr_codes(
                document_bytes=document_bytes,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            # Step 5: Update invoice with extracted data
            updated_invoice = await self._update_invoice_with_extraction(
                invoice_data=invoice_data,
                extracted_data=extracted_data,
                qr_codes=qr_codes,
                invoice_id=invoice_id,
                correlation_id=correlation_id
            )
            
            self.logger.info(
                f"Invoice extraction completed successfully",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "state": InvoiceState.EXTRACTED.value,
                    "has_qr_codes": len(qr_codes) > 0,
                    "qr_code_count": len(qr_codes)
                }
            )
            
            return {
                "invoice_id": invoice_id,
                "department_id": department_id,
                "event_type": "IntakeAgentCompleted",
                "state": InvoiceState.EXTRACTED.value,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
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
            
        except DocumentExtractionException as e:
            self.logger.error(
                f"Document extraction failed for invoice: {invoice_id}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "error_type": "ExtractionFailed",
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
                f"Unexpected error processing invoice: {invoice_id}",
                extra={
                    "invoice_id": invoice_id,
                    "department_id": department_id,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise DocumentExtractionException(
                f"Failed to process invoice {invoice_id}: {str(e)}"
            ) from e

    async def _retrieve_invoice_metadata(
        self,
        department_id: str,
        invoice_id: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Retrieve invoice metadata from Table Storage.
        
        Args:
            department_id: Department identifier
            invoice_id: Invoice identifier
            correlation_id: Correlation ID for tracing
            
        Returns:
            Invoice metadata dictionary
            
        Raises:
            InvoiceNotFoundException: If invoice not found
            StorageException: If retrieval fails
        """
        self.logger.debug(
            "Retrieving invoice metadata",
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
            
            self.logger.debug(
                "Invoice metadata retrieved successfully",
                extra={
                    "invoice_id": invoice_id,
                    "document_type": invoice_data.get("document_type"),
                    "correlation_id": correlation_id
                }
            )
            
            return invoice_data
            
        except InvoiceNotFoundException:
            raise
        except Exception as e:
            raise StorageException(
                f"Failed to retrieve invoice metadata: {str(e)}"
            ) from e

    async def _download_invoice_document(
        self,
        blob_name: str,
        invoice_id: str,
        correlation_id: str
    ) -> bytes:
        """
        Download invoice document from Blob Storage.
        
        Args:
            blob_name: Blob storage path
            invoice_id: Invoice identifier for logging
            correlation_id: Correlation ID for tracing
            
        Returns:
            Document bytes
            
        Raises:
            StorageException: If download fails or document not found
        """
        self.logger.debug(
            "Downloading invoice document",
            extra={
                "invoice_id": invoice_id,
                "blob_name": blob_name,
                "correlation_id": correlation_id
            }
        )
        
        try:
            document_bytes = await self.blob_storage_client.download_file(
                container_name=settings.blob_container_name,
                blob_name=blob_name
            )
            
            if not document_bytes:
                raise StorageException(
                    f"Document not found in blob storage: {blob_name}"
                )
            
            self.logger.debug(
                "Invoice document downloaded successfully",
                extra={
                    "invoice_id": invoice_id,
                    "blob_name": blob_name,
                    "document_size_bytes": len(document_bytes),
                    "correlation_id": correlation_id
                }
            )
            
            return document_bytes
            
        except StorageException:
            raise
        except Exception as e:
            raise StorageException(
                f"Failed to download document from blob storage: {str(e)}"
            ) from e

    async def _extract_invoice_data(
        self,
        document_bytes: bytes,
        document_type: str,
        invoice_id: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Extract structured data from invoice document.
        
        Args:
            document_bytes: Document content
            document_type: Type of document (invoice or receipt)
            invoice_id: Invoice identifier for logging
            correlation_id: Correlation ID for tracing
            
        Returns:
            Extracted invoice data
            
        Raises:
            DocumentExtractionException: If extraction fails
        """
        self.logger.info(
            f"Extracting data from {document_type}",
            extra={
                "invoice_id": invoice_id,
                "document_type": document_type,
                "document_size_bytes": len(document_bytes),
                "correlation_id": correlation_id
            }
        )
        
        try:
            if document_type.lower() == "invoice":
                extracted_data = await self.invoice_analyzer_tool.analyze_invoice_request(
                    document_bytes
                )
            elif document_type.lower() == "receipt":
                extracted_data = await self.invoice_analyzer_tool.analyze_receipt_request(
                    document_bytes
                )
            else:
                raise DocumentExtractionException(
                    f"Unsupported document type: {document_type}"
                )
            
            self.logger.info(
                "Document extraction completed",
                extra={
                    "invoice_id": invoice_id,
                    "document_type": document_type,
                    "fields_extracted": len(extracted_data),
                    "correlation_id": correlation_id
                }
            )
            
            return extracted_data
            
        except Exception as e:
            raise DocumentExtractionException(
                f"Failed to extract data from {document_type}: {str(e)}"
            ) from e

    async def _extract_qr_codes(
        self,
        document_bytes: bytes,
        invoice_id: str,
        correlation_id: str
    ) -> list:
        """
        Extract QR codes from invoice document.
        
        Args:
            document_bytes: Document content
            invoice_id: Invoice identifier for logging
            correlation_id: Correlation ID for tracing
            
        Returns:
            List of QR code data strings (empty if none found)
        """
        self.logger.debug(
            "Scanning for QR codes",
            extra={
                "invoice_id": invoice_id,
                "correlation_id": correlation_id
            }
        )
        
        try:
            qr_info_list = await get_qr_info_from_bytes(document_bytes)
            
            if qr_info_list:
                qr_codes = [qr_info.data for qr_info in qr_info_list]
                self.logger.info(
                    f"Found {len(qr_codes)} QR code(s)",
                    extra={
                        "invoice_id": invoice_id,
                        "qr_code_count": len(qr_codes),
                        "correlation_id": correlation_id
                        # Don't log actual QR data - may contain sensitive info
                    }
                )
                return qr_codes
            else:
                self.logger.debug(
                    "No QR codes found in document",
                    extra={
                        "invoice_id": invoice_id,
                        "correlation_id": correlation_id
                    }
                )
                return []
                
        except Exception as e:
            # QR code extraction is non-critical, log warning but don't fail
            self.logger.warning(
                f"QR code extraction failed (non-critical): {str(e)}",
                extra={
                    "invoice_id": invoice_id,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__
                }
            )
            return []

    async def _update_invoice_with_extraction(
        self,
        invoice_data: Dict[str, Any],
        extracted_data: Dict[str, Any],
        qr_codes: list,
        invoice_id: str,
        correlation_id: str
    ) -> Invoice:
        """
        Update invoice with extracted data and change state.
        
        Args:
            invoice_data: Original invoice metadata
            extracted_data: Data extracted from document
            qr_codes: List of QR code data
            invoice_id: Invoice identifier
            correlation_id: Correlation ID for tracing
            
        Returns:
            Updated Invoice object
            
        Raises:
            StorageException: If update fails
        """
        self.logger.debug(
            "Updating invoice with extracted data",
            extra={
                "invoice_id": invoice_id,
                "correlation_id": correlation_id
            }
        )
        
        try:
            # Merge extracted data into invoice
            invoice_data.update(extracted_data)
            
            # Add QR codes if found
            if qr_codes:
                invoice_data["qr_codes_data"] = qr_codes
            
            # Convert to Invoice object and update state
            invoice_obj = Invoice.from_dict(invoice_data)
            invoice_obj.state = InvoiceState.EXTRACTED
            
            # Persist to storage
            update_successful = await self.update_invoice(invoice_obj.to_dict())
            
            if not update_successful:
                raise StorageException(
                    f"Failed to update invoice in storage: {invoice_id}"
                )
            
            self.logger.info(
                "Invoice updated successfully",
                extra={
                    "invoice_id": invoice_id,
                    "new_state": InvoiceState.EXTRACTED.value,
                    "correlation_id": correlation_id
                }
            )
            
            return invoice_obj
            
        except Exception as e:
            raise StorageException(
                f"Failed to update invoice with extracted data: {str(e)}"
            ) from e

    def get_next_subject(self) -> str:
        """
        Get the message subject for the next processing stage.
        
        Returns:
            Subject name for invoice.extracted messages
        """
        return InvoiceSubjects.EXTRACTED.value


if __name__ == "__main__":
    agent = IntakeAgent()
    agent.setup_signal_handlers()
    asyncio.run(agent.run())
