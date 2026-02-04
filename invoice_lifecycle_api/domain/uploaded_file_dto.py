
from pydantic import BaseModel
class UploadedFileDTO(BaseModel):
    """
    Data Transfer Object representing an uploaded file.
    """
    file_name: str
    content_type: str
    file_content: bytes
