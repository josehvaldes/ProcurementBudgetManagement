"""
Health check endpoint.
"""
import base64
import traceback
import uuid
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from fastapi.responses import JSONResponse

from fastapi import UploadFile, File, Form
import shutil
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
    
def upload_metadata_form(
    department_id: str = Form(...),
    source_email: str | None = Form(None),
    priority: str = Form("normal"),
) -> UploadRequestModel:
    return UploadRequestModel(
        department_id=department_id,
        source_email=source_email,
        priority=priority
    )

@router.post("/upload-invoice")
async def intake(model:UploadRequestModel = Depends(upload_metadata_form),
                 file: UploadFile = File(...), 
                 event_choreographer: EventChoreographer = Depends(get_event_choreographer_service)):
    """Endpoint to upload an invoice file along with metadata."""

    try:
        logger.info(f"upload-invoice endpoint called for department {model.department_id}")
        
        file_content = await file.read()
        uploadedFile = UploadedFileDTO(file.filename, file.content_type, file_content)
        
        invoice: Invoice = Invoice(
            invoice_id="",
            source=InvoiceSource.API,
            department_id=model.department_id,            
            source_email=model.source_email,
            priority=model.priority,
            line_items=[],
            has_po=False
        )

        invoice_id = await event_choreographer.handle_intake_event(invoice, uploadedFile)

        logger.info(f"Created invoice model: {invoice_id}, file: {invoice.file_name}, size: {invoice.file_size} bytes")
        
        if invoice_id and invoice_id != "":
            return JSONResponse(content=f"File uploaded successfully with ID: {invoice_id}", status_code=200)
        else:
            return JSONResponse(content=f"Failed to save invoice Id {invoice_id}", status_code=500)

    except Exception as e:
        logger.error(f"Error creating uploads directory: {e}")
        traceback.print_exc()
        return JSONResponse(content="Internal server error", status_code=500)
