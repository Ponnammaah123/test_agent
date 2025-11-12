from fastapi import APIRouter, HTTPException, status, Body
from pydantic import BaseModel
from typing import Dict, Any, Optional

from src.config.settings import Config
from src.agents.test_generation_agent import TestGenerationAgent
from src.models.test_plan_models import TestPlan
from src.models.github_models import CodebaseAnalysis
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

class GenerateTestsRequest(BaseModel):
    """Request model for test generation"""
    jira_ticket_key: str
    test_plan: Dict[str, Any]
    codebase_analysis: Dict[str, Any]
    test_repo_url: Optional[str] = None
    scope_analysis: Optional[Dict[str, Any]] = None

@router.post(
    "/generate/tests",
    summary="Generate E2E Tests",
    description="Generate Playwright test code based on Test Plan and Codebase Analysis"
)
async def generate_tests(
    request: GenerateTestsRequest = Body(..., description="Test generation parameters")
):
    """
    Generate E2E tests
    """
    logger.info(f"Received test generation request for {request.jira_ticket_key}")

    try:
        # 1. Initialize Config & Agent
        config = Config()
        config.validate()
        
        # Note: TestGenerationAgent requires BaseAgent and other utils to be present
        agent = TestGenerationAgent(config)

        # 2. Convert Dictionary inputs to Models
        # Assuming TestPlan and CodebaseAnalysis are Pydantic models or DataClasses
        # If they are DataClasses, we might need specific logic. 
        # Based on your files, TestPlan is a dataclass, CodebaseAnalysis is a dataclass.
        
        test_plan_obj = TestPlan(**request.test_plan)
        
        # CodebaseAnalysis has nested objects like RepositoryConfig
        # You might need a helper to fully hydrate this if it's complex, 
        # but simple kwargs usually work for standard dataclasses
        codebase_analysis_obj = CodebaseAnalysis(**request.codebase_analysis)

        target_repo_url = request.test_repo_url or config.test_repo.repo_url

        # 3. Execute Generation
        result = agent.generate_tests(
            jira_ticket_key=request.jira_ticket_key,
            test_plan=test_plan_obj,
            codebase_analysis=codebase_analysis_obj,
            test_repo_url=target_repo_url,
            scope_analysis=request.scope_analysis
        )

        return {
            "status": "success",
            "message": f"Generated {len(result.get('test_files', {}))} test files",
            "data": result
        }

    except Exception as e:
        error_msg = f"Test generation failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )