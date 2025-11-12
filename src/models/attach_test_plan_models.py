from typing import Dict, Any, List
from pydantic import BaseModel, Field

class AttachTestPlanRequest(BaseModel):
    """Request model for attaching test plan to Jira"""
    jira_ticket_key: str = Field(..., description="Jira ticket key (e.g., PROJ-102)")
    test_plan: Dict[str, Any] = Field(..., description="Structured test plan data")
    
    class Config:
        schema_extra = {
            "example": {
                "jira_ticket_key": "PROJ-102",
                "test_plan": {
                    "jira_ticket": "PROJ-102",
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
                }
            }
        }

class AttachTestPlanResponse(BaseModel):
    """Response model for attach test plan operation"""
    status: str = Field(..., description="Operation status: success/error")
    message: str = Field(..., description="Result message")
    attached_files: List[str] = Field(default=[], description="List of attached file names")
    jira_comment_id: str = Field(default="", description="Jira comment ID if created")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "message": "Test plan documents attached successfully to PROJ-102",
                "attached_files": [
                    "TestPlan_PROJ-102_20231201_120000.pdf",
                    "TestPlan_PROJ-102_20231201_120000.xlsx"
                ],
                "jira_comment_id": "12345"
            }
        }