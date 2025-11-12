from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class FetchJiraTicketResponse(BaseModel):
    """Output schema for Jira ticket response"""
    jira_id: str = Field(..., description="Jira ticket ID")
    jira_summary: str = Field(..., description="Ticket summary/title")
    jira_status: str = Field(..., description="Ticket status")
    jira_description: Optional[str] = Field(None, description="Ticket description")
    jira_assignee: Optional[str] = Field(None, description="Assigned user")
    comments: Optional[List[str]] = Field(default_factory=list, description="Ticket comments")
    attachments: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="List of attachment details with all information"
    )


class AttachmentDetail(BaseModel):
    """Model for individual attachment details"""
    id: str = Field(..., description="Attachment ID")
    filename: str = Field(..., description="Attachment filename")
    content: str = Field(..., description="Attachment download URL")
    size: int = Field(..., description="Attachment size in bytes")
    created: str = Field(..., description="Attachment creation timestamp")
    mimeType: Optional[str] = Field(None, description="MIME type of attachment")
