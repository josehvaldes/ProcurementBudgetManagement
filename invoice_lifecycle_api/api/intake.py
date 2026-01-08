"""
Health check endpoint.
"""
import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from fastapi import UploadFile, File, Form
from pydantic import BaseModel, EmailStr

from invoice_lifecycle_api.domain.uploaded_file_dto import UploadedFileDTO
from shared.utils.logging_config import get_logger
from shared.config.settings import settings
from invoice_lifecycle_api.application.services.event_choreographer import EventChoreographer
from invoice_lifecycle_api.application.interfaces.di_container import get_event_choreographer_service
from shared.models.invoice import Invoice, InvoiceSource

logger = get_logger(__name__)

router = APIRouter()

class UploadRequestModel(BaseModel):
    department_id: str 
    source_email: EmailStr | None
    priority: str | None
    document_type: str | None # e.g., "invoice" or "receipt"
    user_comments: str | None
    
def upload_metadata_form(
    department_id: str = Form(...),
    source_email: str | None = Form(None),
    user_comments: str | None = Form(None),
    priority: str = Form("normal"),
    document_type: str = Form("invoice"),    
) -> UploadRequestModel:
    return UploadRequestModel(
        department_id=department_id,
        source_email=source_email,
        priority=priority,
        document_type=document_type,
        user_comments=user_comments
    )

@router.post("/upload-invoice")
async def intake(model:UploadRequestModel = Depends(upload_metadata_form),
                 file: UploadFile = File(...), 
                 event_choreographer: EventChoreographer = Depends(get_event_choreographer_service)):
    """Endpoint to upload an invoice file along with metadata."""

    try:
        logger.info(f"upload-invoice endpoint called for department {model.department_id}, {model.user_comments}")
        
        file_content = await file.read()
        uploadedFile = UploadedFileDTO(file.filename, file.content_type, file_content)
        
        invoice: Invoice = Invoice(
            invoice_id="",
            source=InvoiceSource.API,
            department_id=model.department_id,            
            source_email=model.source_email,
            priority=model.priority,
            document_type=model.document_type,
            has_po=False,
            user_comments=model.user_comments
        )

        invoice_id = await event_choreographer.handle_intake_event(invoice, uploadedFile)

        logger.info(f"Created invoice model: {invoice_id}, file: {invoice.file_name}, size: {invoice.file_size} bytes")
        
        if invoice_id and invoice_id != "":
            # return a 202 Accepted response with the invoice ID
            return JSONResponse(content=f"File uploaded successfully with ID: {invoice_id}", status_code=202)
        else:
            return JSONResponse(content=f"Failed to save invoice Id {invoice_id}", status_code=500)

    except Exception as e:
        logger.error(f"Error creating uploads directory: {e}")
        traceback.print_exc()
        return JSONResponse(content="Internal server error", status_code=500)
