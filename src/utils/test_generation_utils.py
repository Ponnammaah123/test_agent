import hashlib
from typing import Dict, Any, List, Optional
from src.utils.logger import get_logger
from src.clients.github_client import GitHubClient
from src.models.jira_models import JiraTicket

logger = get_logger(__name__)

class CacheManager:
    """Simple in-memory cache for test generation"""
    _store = {}
    
    def get(self, key: str) -> Any:
        return self._store.get(key)
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        self._store[key] = value

class ScopeDetector:
    """Detects scope of testing required based on Jira Ticket"""
    def detect(self, ticket: JiraTicket) -> Dict[str, Any]:
        scope = {
            "ticket_type": ticket.story_type.lower(),
            "complexity": "medium",
            "test_types_required": ["e2e"]
        }
        if "bug" in ticket.story_type.lower():
            scope["ticket_type"] = "bug"
            scope["test_types_required"].append("regression")
        return scope

class TestRepoAnalyzer:
    """Analyzes existing test repository"""
    def __init__(self, client):
        self.client = client
        
    def analyze_existing_tests(self, ticket_key: str) -> Dict[str, Any]:
        files = self.client.list_test_files()
        existing = [f for f in files if ticket_key.lower() in f.lower()]
        return {
            "existing_test_files": existing,
            "has_existing_tests": len(existing) > 0,
            "update_strategy": "update" if existing else "create"
        }

    def suggest_update_strategy(self, existing_files, ticket_key, scope) -> Dict[str, str]:
        return {"action": "create" if not existing_files else "update", "recommendations": []}

class TestFileNamingStrategy:
    """Handles naming conventions for test files"""
    def generate_test_file_path(self, ticket: JiraTicket, category: str, test_type: str) -> str:
        # e.g. tests/e2e/story-123/functional.spec.ts
        clean_key = ticket.key.lower()
        return f"tests/e2e/{clean_key}/{category.lower()}.spec.ts"
    
    def generate_unique_filename(self, base_path: str, existing_files: List[str], extension: str = ".spec.ts") -> str:
        if base_path not in existing_files:
            return base_path
        # Simple increment logic could be added here
        return base_path.replace(extension, f"-new{extension}")

class LocatorExtractor:
    """Extracts data-testid and ids from codebase"""
    def extract_from_codebase(self, github_client: GitHubClient, codebase_analysis) -> Dict[str, List[str]]:
        locators = {"data-testid": [], "id": []}
        # Basic implementation: scan changed files for pattern
        # Real implementation would use AST or Regex on file content
        return locators