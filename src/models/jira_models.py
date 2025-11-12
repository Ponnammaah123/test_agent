# ==============================================
# Jira data models
# ==============================================

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class JiraTicket:
    """Jira ticket data model"""
    key: str
    summary: str
    description: str
    story_type: str
    acceptance_criteria: List[str]
    components: List[str]
    linked_issues: List[str]
    assignee: str
    status: str
    priority: str = "Medium"
    reporter: str = ""
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    labels: List[str] = field(default_factory=list)

    # Hierarchical relationships
    parent_key: Optional[str] = None  # Parent story/epic for subtasks
    epic_key: Optional[str] = None  # Epic link
    epic_name: Optional[str] = None  # Epic name for grouping
    subtasks: List[str] = field(default_factory=list)  # List of subtask keys
    is_subtask: bool = False  # Whether this is a subtask
    
    def has_acceptance_criteria(self) -> bool:
        """Check if ticket has acceptance criteria"""
        return len(self.acceptance_criteria) > 0

    def get_hierarchy_path(self) -> str:
        """
        Get the full hierarchical path for this ticket

        Returns:
            Path string like "EPIC-123/STORY-456/SUBTASK-789" or just "STORY-456"
        """
        path_parts = []

        if self.epic_key:
            path_parts.append(self.epic_key)

        if self.parent_key and self.parent_key != self.epic_key:
            path_parts.append(self.parent_key)

        path_parts.append(self.key)

        return "/".join(path_parts)

    def get_test_file_prefix(self) -> str:
        """
        Generate a test file prefix based on ticket hierarchy

        Returns:
            String like "epic-123/story-456" or "story-456" for file organization
        """
        parts = []

        # Use epic name if available (more readable than key)
        if self.epic_name:
            epic_slug = self.epic_name.lower().replace(' ', '-').replace('_', '-')
            parts.append(epic_slug[:30])  # Limit length
        elif self.epic_key:
            parts.append(self.epic_key.lower())

        # If this is a subtask, include parent
        if self.is_subtask and self.parent_key:
            parts.append(self.parent_key.lower())

        return "/".join(parts) if parts else ""

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'key': self.key,
            'summary': self.summary,
            'description': self.description,
            'story_type': self.story_type,
            'acceptance_criteria': self.acceptance_criteria,
            'components': self.components,
            'linked_issues': self.linked_issues,
            'assignee': self.assignee,
            'status': self.status,
            'priority': self.priority,
            'parent_key': self.parent_key,
            'epic_key': self.epic_key,
            'epic_name': self.epic_name,
            'subtasks': self.subtasks,
            'is_subtask': self.is_subtask
        }