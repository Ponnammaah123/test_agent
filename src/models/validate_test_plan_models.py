from typing import Dict, Any, Union, List
from pydantic import BaseModel, Field
from datetime import datetime

class AttachmentModel(BaseModel):
    id: str = Field(..., description="Attachment ID")
    filename: str = Field(..., description="Attachment filename")
    content: str = Field(..., description="Attachment content URL")
    size: int = Field(..., description="Attachment size in bytes")
    created: str = Field(..., description="Attachment creation timestamp")
    mimeType: str = Field(..., description="Attachment MIME type")

class ValidateTestPlanRequest(BaseModel):
    attachments: List[AttachmentModel] = Field(default=[], description="List of attachments from Jira")
    
    class Config:
        extra = "allow"