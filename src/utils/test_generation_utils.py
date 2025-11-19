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
    
    def generate_test_file_path(self, ticket: JiraTicket, scenario: Dict[str, Any], test_type: str) -> str:
        """
        MODIFIED: Generates a path based on Parent/Jira ID nesting: 
        tests/e2e/<parent jira id>/<parent jira id>/<jira id>-<scenario id>.spec.ts
        """
        current_key = ticket.key.lower()
        
        # Determine parent key for nesting. Use current key if no explicit parent is set.
        # This creates the desired path structure (e.g., QEA-18/QEA-18).
        parent_key = ticket.parent_key.lower() if ticket.parent_key else current_key
        
        # Get scenario ID, default to a random string if not present
        scenario_id_raw = scenario.get('id')
        if not scenario_id_raw:
            scenario_id_raw = f"scenario-{hashlib.md5(scenario.get('title','').encode()).hexdigest()[:6]}"

        # Sanitize ID (e.g., "TS-001" -> "ts-001")
        clean_scenario_id = str(scenario_id_raw).lower().replace(" ", "-").replace("_", "-")

        # Construct the requested nested folder structure: <parent>/<parent>/
        file_path_prefix = f"tests/e2e/{parent_key}/{parent_key}"
        
        # The filename itself includes the current ticket key and scenario ID
        # e.g., qea-20-ts-001.spec.ts
        filename = f"{current_key}-{clean_scenario_id}.spec.ts"

        return f"{file_path_prefix}/{filename}"
    
    def generate_unique_filename(self, base_path: str, existing_files: List[str]) -> str:
        """
        FIXED: Robustly handles name clashes by incrementing a counter.
        """
        if base_path not in existing_files:
            return base_path
        
        # Separate name and extension
        # This handles complex extensions like .spec.ts
        parts = base_path.rsplit('.', 2)
        if len(parts) == 3 and parts[1] == 'spec': # Handle .spec.ts
            base_name = parts[0]
            extension = f".{parts[1]}.{parts[2]}"
        else:
            # Handle simple extensions like .ts, .js
            parts = base_path.rsplit('.', 1)
            base_name = parts[0] if len(parts) > 1 else base_path
            extension = f".{parts[1]}" if len(parts) > 1 else ""

        i = 1
        new_path = f"{base_name}-{i}{extension}"
        
        while new_path in existing_files:
            i += 1
            new_path = f"{base_name}-{i}{extension}"
            
        return new_path

class LocatorExtractor:
    """Extracts data-testid and ids from codebase"""
    def extract_from_codebase(self, github_client: GitHubClient, codebase_analysis) -> Dict[str, List[str]]:
        locators = {"data-testid": [], "id": []}
        # Basic implementation: scan changed files for pattern
        # Real implementation would use AST or Regex on file content
        return locators