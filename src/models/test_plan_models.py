# ==============================================
# Test plan data models
# ==============================================

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from src.models.github_models import RepositoryConfig
import re

@dataclass
class TestScenario:
    """Individual test scenario"""
    id: str
    title: str
    given: str
    when: str
    then: str
    priority: str  # High, Medium, Low
    test_type: str  # API, E2E
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'given': self.given,
            'when': self.when,
            'then': self.then,
            'priority': self.priority,
            'test_type': self.test_type
        }

@dataclass
class TestPlan:
    """Generated test plan"""
    # Required fields from your payload
    jira_ticket: str
    test_scenarios: List[Dict]

    # Optional fields (made optional to fix the error)
    strategy: str = ""
    test_approach: str = "BDD"
    testable_components: List[str] = field(default_factory=list)
    traceability_matrix: Dict[str, List[str]] = field(default_factory=dict)
    coverage_targets: Dict[str, str] = field(default_factory=dict)
    
    # Updated confidence_score to handle string input like "40%"
    confidence_score: Any = 0.0
    
    environment_config: Optional[RepositoryConfig] = None
    generated_at: Optional[str] = None
    quality_issues: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Clean up confidence_score after initialization"""
        if isinstance(self.confidence_score, str):
            # Remove '%' and other non-numeric characters, then convert to float
            match = re.search(r'[\d\.]+', self.confidence_score)
            if match:
                self.confidence_score = float(match.group(0))
            else:
                self.confidence_score = 0.0
        elif not isinstance(self.confidence_score, (float, int)):
            # Handle other invalid types
            self.confidence_score = 0.0
    
    def get_scenario_count(self) -> int:
        """Get total number of test scenarios"""
        return len(self.test_scenarios)
    
    def get_high_priority_scenarios(self) -> List[Dict]:
        """Get high priority scenarios"""
        return [s for s in self.test_scenarios if s.get('priority') == 'High']
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'jira_ticket': self.jira_ticket,
            'strategy': self.strategy,
            'test_approach': self.test_approach,
            'testable_components': self.testable_components,
            'test_scenarios': self.test_scenarios,
            'traceability_matrix': self.traceability_matrix,
            'coverage_targets': self.coverage_targets,
            'confidence_score': self.confidence_score
        }