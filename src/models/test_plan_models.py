# ==============================================
# Test plan data models
# ==============================================

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from src.models.github_models import RepositoryConfig

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
    jira_ticket: str
    strategy: str
    test_approach: str
    testable_components: List[str]
    test_scenarios: List[Dict]
    traceability_matrix: Dict[str, List[str]]
    coverage_targets: Dict[str, str]
    confidence_score: float
    environment_config: Optional[RepositoryConfig] = None
    generated_at: Optional[str] = None
    quality_issues: List[str] = field(default_factory=list)
    
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