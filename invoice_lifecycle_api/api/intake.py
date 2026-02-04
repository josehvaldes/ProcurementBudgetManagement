"""
Invoice Intake API endpoints for uploading and processing invoices.

This module provides RESTful API endpoints for uploading invoice files
along with metadata, triggering the invoice processing workflow.
"""
import traceback
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from invoice_lifecycle_api.domain.uploaded_file_dto import UploadedFileDTO
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.application.services.event_choreographer import EventChoreographer
from invoice_lifecycle_api.application.interfaces.di_container import get_event_choreographer_service
from shared.models.invoice import Invoice, InvoiceSource

logger = get_logger(__name__)

router = APIRouter(
    responses={
        500: {"description": "Internal server error"}
    }
)


# ==================== Request/Response Models ====================

class UploadRequestModel(BaseModel):
    """
    Model representing the metadata for an uploaded invoice.
    
    This model captures the essential information needed to process
    an uploaded invoice file and route it through the appropriate workflow.
    """
    department_id: str = Field(
        ...,
        description="Department identifier for budget allocation and routing",
        example="IT",
        min_length=2,
        max_length=50
    )
    source_email: Optional[EmailStr] = Field(
        None,
        description="Email address of the invoice sender (if applicable)",
        example="vendor@supplier.com"
    )
    priority: Optional[str] = Field(
        "normal",
        description="Processing priority: low, normal, or high",
        example="normal"
    )
    document_type: Optional[str] = Field(
        "invoice",
        description="Type of document: invoice or receipt",
        example="invoice"
    )
    user_comments: Optional[str] = Field(
        None,
        description="Additional comments or notes about the invoice",
        example="Urgent payment required for Q4 software licenses",
        max_length=2000
    )

    @field_validator('priority')
    def validate_priority(cls, v):
        """Validate priority is one of the allowed values."""
        if v is None:
            return "normal"
        allowed_priorities = ['low', 'normal', 'high']
        if v.lower() not in allowed_priorities:
            raise ValueError(f"Priority must be one of: {', '.join(allowed_priorities)}")
        return v.lower()

    @field_validator('document_type')
    def validate_document_type(cls, v):
        """Validate document type is one of the allowed values."""
        if v is None:
            return "invoice"
        allowed_types = ['invoice', 'receipt']
        if v.lower() not in allowed_types:
            raise ValueError(f"Document type must be one of: {', '.join(allowed_types)}")
        return v.lower()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "department_id": "IT",
                "source_email": "billing@techsupply.com",
                "priority": "high",
                "document_type": "invoice",
                "user_comments": "Annual software licensing - requires CFO approval"
            }
        }
    )


class InvoiceUploadResponse(BaseModel):
    """Response model for successful invoice upload."""
    message: str = Field(..., description="Success message")
    invoice_id: str = Field(..., description="Unique identifier for the uploaded invoice")
    status: str = Field(..., description="Processing status")
    department_id: str = Field(..., description="Department identifier")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Invoice uploaded and processing initiated",
                "invoice_id": "a1b2c3d4e5f6",
                "status": "accepted",
                "department_id": "IT"
            }
        }
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Invalid file format",
                "detail": "Only PDF, JPEG, and PNG files are accepted"
            }
        }
    )


# ==================== Helper Functions ====================

def upload_metadata_form(
    department_id: str = Form(
        ...,
        description="Department identifier",
        example="IT"
    ),
    source_email: Optional[str] = Form(
        None,
        description="Email address of the invoice sender",
        example="vendor@supplier.com"
    ),
    user_comments: Optional[str] = Form(
        None,
        description="Additional comments or notes",
        example="Urgent payment required"
    ),
    priority: str = Form(
        "normal",
        description="Processing priority: low, normal, or high",
        example="normal"
    ),
    document_type: str = Form(
        "invoice",
        description="Document type: invoice or receipt",
        example="invoice"
    ),    
) -> UploadRequestModel:
    """
    Parse form data into UploadRequestModel.
    
    This function converts multipart form data into a structured
    Pydantic model for validation and processing.
    """
    return UploadRequestModel(
        department_id=department_id,
        source_email=source_email,
        priority=priority,
        document_type=document_type,
        user_comments=user_comments
    )


# ==================== API Endpoints ====================

@router.post(
    "/upload-invoice",
    response_model=InvoiceUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload an invoice file with metadata",
    description="""
    Upload an invoice or receipt file along with associated metadata.
    
    This endpoint accepts multipart/form-data containing:
    - Invoice file (PDF, JPEG, PNG)
    - Department identifier
    - Optional metadata (priority, source email, comments)
    
    The uploaded file is processed asynchronously through the invoice
    processing workflow, which includes:
    1. File storage in Azure Blob Storage
    2. OCR/Document Intelligence extraction
    3. Budget validation
    4. Workflow state management
    
    Supported file formats:
    - PDF (application/pdf)
    - JPEG (image/jpeg)
    - PNG (image/png)
    
    Maximum file size: 10MB
    """,
    responses={
        202: {
            "description": "Invoice accepted for processing",
            "model": InvoiceUploadResponse
        },
        400: {
            "description": "Invalid request data or unsupported file format",
            "model": ErrorResponse
        },
        413: {
            "description": "File too large (max 10MB)",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
async def upload_invoice(
    model: UploadRequestModel = Depends(upload_metadata_form),
    file: UploadFile = File(
        ...,
        description="Invoice file (PDF, JPEG, or PNG format, max 10MB)",
        example="invoice_2025_001.pdf"
    ), 
    event_choreographer: EventChoreographer = Depends(get_event_choreographer_service)
) -> InvoiceUploadResponse:
    """
    Upload and process an invoice file.
    
    This endpoint handles the complete invoice intake process:
    1. Validates file format and metadata
    2. Stores file in Azure Blob Storage
    3. Creates invoice record in Table Storage
    4. Triggers asynchronous processing workflow
    
    The invoice processing workflow includes:
    - Document Intelligence OCR extraction
    - Vendor and PO matching
    - Budget validation and allocation
    - Approval routing based on business rules
    
    Args:
        model: Invoice metadata from form data
        file: Uploaded invoice file
        event_choreographer: Service orchestrating the processing workflow
        
    Returns:
        InvoiceUploadResponse with invoice ID and processing status
        
    Raises:
        HTTPException: 400 if file format is invalid
        HTTPException: 413 if file is too large
        HTTPException: 500 if processing fails
    """
    try:
        # Validate file type
        allowed_content_types = [
            "application/pdf",
            "image/jpeg",
            "image/jpg",
            "image/png"
        ]
        
        if file.content_type not in allowed_content_types:
            logger.warning(f"Invalid file type uploaded: {file.content_type}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: {file.content_type}. Allowed formats: PDF, JPEG, PNG"
            )
        
        logger.info(
            f"upload-invoice endpoint called - Department: {model.department_id}, "
            f"File: {file.filename}, Type: {file.content_type}, Priority: {model.priority}"
        )
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file size (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        if file_size > max_size:
            logger.warning(f"File too large: {file_size} bytes (max: {max_size})")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds maximum allowed size (10MB)"
            )
        
        # Create DTO for file handling
        uploaded_file = UploadedFileDTO(
            file_name=file.filename,
            content_type=file.content_type,
            file_content=file_content
        )
        
        # Create invoice model
        invoice: Invoice = Invoice(
            invoice_id="",  # Will be generated by the service
            source=InvoiceSource.API,
            department_id=model.department_id,            
            source_email=model.source_email,
            priority=model.priority,
            document_type=model.document_type,
            has_po=False,
            user_comments=model.user_comments
        )

        # Trigger processing workflow
        invoice_id = await event_choreographer.handle_intake_event(invoice, uploaded_file)

        if not invoice_id or invoice_id == "":
            logger.error("Invoice ID generation failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create invoice record"
            )

        logger.info(
            f"Invoice uploaded successfully - ID: {invoice_id}, "
            f"File: {file.filename}, Size: {file_size} bytes"
        )
        
        return InvoiceUploadResponse(
            message="Invoice uploaded and processing initiated",
            invoice_id=invoice_id,
            status="accepted",
            department_id=model.department_id
        )

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    
    except ValueError as e:
        # Handle validation errors from the model
        logger.error(f"Validation error in upload_invoice: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Error in upload_invoice endpoint: {str(e)}")
        logger.debug(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the invoice upload"
        )

