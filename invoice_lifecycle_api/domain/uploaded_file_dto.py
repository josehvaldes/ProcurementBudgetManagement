
class UploadedFileDTO:
    def __init__(self, file_name: str, content_type: str, file_content: bytes):
        self.file_name = file_name
        self.content_type = content_type
        self.file_content = file_content
