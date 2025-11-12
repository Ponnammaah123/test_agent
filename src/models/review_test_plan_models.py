from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class ReviewTestPlanRequest(BaseModel):
    """Request model for reviewing and enhancing test plan"""
    test_plan: Dict[str, Any] = Field(..., description="Original test plan to review and enhance")
    jira_ticket: Dict[str, Any] = Field(..., description="Jira ticket details for context")
    max_iterations: int = Field(default=2, description="Maximum enhancement iterations")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "test_plan": {
                    "jira_ticket": "TP-1",
                    "strategy": "Comprehensive testing approach",
                    "test_approach": "Risk-based testing",
                    "testable_components": ["API", "UI", "Database"],
                    "test_scenarios": [
                        {
                            "id": "TS-001",
                            "title": "User login validation",
                            "given": "User has valid credentials",
                            "when": "User submits login form",
                            "then": "System authenticates user",
                            "priority": "High",
                            "test_type": "E2E"
                        }
                    ],
                    "traceability_matrix": {
                        "AC-001": ["TS-001", "TS-002"]
                    },
                    "coverage_targets": {
                        "functional_coverage": "95%",
                        "code_coverage": "80%"
                    },
                    "confidence_score": 85.5
                },
                "jira_ticket": {
                    "key": "TP-1",
                    "summary": "Add user profile page",
                    "description": "Users should be able to view and edit their profile",
                    "acceptance_criteria": [
                        "Display user information",
                        "Include an edit profile button", 
                        "Enable save changes functionality"
                    ],
                    "components": ["UI", "Backend"],
                    "priority": "High"
                },
                "max_iterations": 2
            }
        }
    }

class ReviewTestPlanResponse(BaseModel):
    """Response model for review test plan operation"""
    status: str = Field(..., description="Operation status: success/error")
    message: str = Field(..., description="Result message")
    enhanced_test_plan: Optional[Dict[str, Any]] = Field(default=None, description="Enhanced test plan")
    quality_issues_found: List[str] = Field(default=[], description="Quality issues identified")
    scenarios_added: int = Field(default=0, description="Number of scenarios added during enhancement")
    original_scenario_count: int = Field(default=0, description="Original number of scenarios")
    final_scenario_count: int = Field(default=0, description="Final number of scenarios after enhancement")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "success",
                "message": "Test plan reviewed and enhanced successfully",
                "enhanced_test_plan": {
                    "jira_ticket": "TP-1",
                    "strategy": "Enhanced comprehensive testing approach",
                    "test_scenarios": [
                        {
                            "id": "TS-001",
                            "title": "User login validation",
                            "given": "User has valid credentials",
                            "when": "User submits login form", 
                            "then": "System authenticates user",
                            "priority": "High",
                            "test_type": "E2E"
                        }
                    ],
                    "confidence_score": 92.0
                },
                "quality_issues_found": [
                    "Insufficient scenarios: 5 (minimum 20 required)",
                    "Missing accessibility scenarios"
                ],
                "scenarios_added": 15,
                "original_scenario_count": 5,
                "final_scenario_count": 20
            }
        }
    }