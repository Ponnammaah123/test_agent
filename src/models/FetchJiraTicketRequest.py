import re
from pydantic import BaseModel, Field, field_validator, model_validator
from src.utils.logger import get_logger

Logger = get_logger(__name__)

class FetchJiraTicketRequest(BaseModel):
    """
    Input schema for Jira ticket fetching with comprehensive validation
    
    Validation Rules:
    - jira_ticket_id: MANDATORY, must match Jira ticket format (e.g., PROJ-123)
    - include_comments: OPTIONAL, defaults to False
    - latest_comment_count: OPTIONAL, defaults to 5, must be between 1-100
    - include_attachments: OPTIONAL, defaults to False
    """
    
    jira_ticket_id: str = Field(..., description="Jira ticket key (e.g., TP-123, PROJ-456)", min_length=1, max_length=50)
    include_comments: bool = Field(False, description="Include ticket comments")
    latest_comment_count: int = Field(5, description="Number of most recent comments to fetch (1-100)",
        ge=1,  # Greater than or equal to 1
        le=100  # Less than or equal to 100
    )
    include_attachments: bool = Field(False, description="Include ticket attachments")
    
    @field_validator('jira_ticket_id')
    @classmethod
    def validate_jira_ticket_id(cls, v: str) -> str:
        """
        Validate Jira ticket ID format
        
        Requirements:
        - Not empty
        - Must contain alphanumeric characters and hyphens
        - Typically in format: PROJECT-123
        - Examples: PROJ-123, TP-456, ABC-1
        
        Args:
            v: Jira ticket ID to validate
            
        Returns:
            Validated ticket ID (stripped)
            
        Raises:
            ValueError: If ticket ID is invalid
        """
        # Strip whitespace
        v = v.strip()
        
        # Check if empty after stripping
        if not v:
            raise ValueError("jira_ticket_id cannot be empty or whitespace only")
        
        # Check format: should be alphanumeric + hyphen, like PROJ-123
        # Pattern: One or more letters/numbers, hyphen, one or more digits
        pattern = r'^[A-Z0-9]+-\d+$'
        if not re.match(pattern, v, re.IGNORECASE):
            raise ValueError(
                f"Invalid Jira ticket ID format: {v}. "
                f"Expected format: PROJECT-123 (letters/numbers, hyphen, digits)"
            )
        
        # Convert to uppercase (Jira ticket keys are typically uppercase)
        return v.upper()
    
    @field_validator('latest_comment_count')
    @classmethod
    def validate_comment_count(cls, v: int) -> int:
        """
        Validate latest_comment_count
        
        Requirements:
        - Must be a positive integer (> 0)
        - Must not exceed reasonable maximum (100)
        
        Args:
            v: Comment count to validate
            
        Returns:
            Validated count
            
        Raises:
            ValueError: If count is invalid
        """
        if v <= 0:
            raise ValueError("latest_comment_count must be greater than 0")
        
        if v > 100:
            raise ValueError(
                f"latest_comment_count must not exceed 100 (requested: {v}). "
                f"Use smaller values to reduce API load."
            )
        
        return v
    
    @field_validator('include_comments')
    @classmethod
    def validate_include_comments(cls, v: bool) -> bool:
        """Validate include_comments is a boolean"""
        if not isinstance(v, bool):
            raise ValueError("include_comments must be a boolean (true/false)")
        return v
    
    @field_validator('include_attachments')
    @classmethod
    def validate_include_attachments(cls, v: bool) -> bool:
        """Validate include_attachments is a boolean"""
        if not isinstance(v, bool):
            raise ValueError("include_attachments must be a boolean (true/false)")
        return v
    
    @model_validator(mode='after')
    def validate_request(self) -> 'FetchJiraTicketRequest':
        """
        Validate the entire request after all field validators
        
        Cross-field validation:
        - If include_comments is False, latest_comment_count can be anything (ignored)
        - If include_comments is True, latest_comment_count should be > 0
        
        Returns:
            Validated request
            
        Raises:
            ValueError: If cross-field validation fails
        """
        # If comments not requested, validate comment count doesn't matter
        if not self.include_comments and self.latest_comment_count != 5:
            Logger.warning(
                f"include_comments is False but latest_comment_count={self.latest_comment_count} "
                f"provided. latest_comment_count will be ignored."
            )
        
        return self
    
    def to_dict_for_logging(self) -> dict:
        """Convert request to dictionary for logging (masks sensitive data)"""
        return {
            'jira_ticket_id': self.jira_ticket_id,
            'include_comments': self.include_comments,
            'latest_comment_count': self.latest_comment_count,
            'include_attachments': self.include_attachments
        }


