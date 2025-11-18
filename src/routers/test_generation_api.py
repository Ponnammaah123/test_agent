from fastapi import APIRouter, HTTPException, status, Body
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from src.config.settings import Config
from src.agents.test_generation_agent import TestGenerationAgent
from src.models.test_plan_models import TestPlan
from src.models.github_models import CodebaseAnalysis
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

class GenerateTestsRequest(BaseModel):
    """Request model for test generation"""
    jira_ticket_key: str = Field(..., description="Jira ticket key (e.g., PROJ-123)")
    test_plan: Dict[str, Any] = Field(..., description="The approved test plan")
    codebase_analysis: Dict[str, Any] = Field(..., description="Codebase analysis data")
    test_repo_url: Optional[str] = Field(None, description="Optional override for test repo URL")
    scope_analysis: Optional[Dict[str, Any]] = Field(None, description="Optional scope analysis data")

@router.post(
    "/generate/tests",
    summary="Generate E2E Tests",
    description="Generate Playwright test code based on Test Plan and Codebase Analysis",
    response_model=Dict[str, Any]
)
async def generate_tests(
    request: GenerateTestsRequest = Body(..., description="Test generation parameters")
):
    """
    Generate E2E tests using the Test Generation Agent
    """
    logger.info(f"Received test generation request for {request.jira_ticket_key}")

    try:
        # 1. Initialize Configuration
        config = Config()
        config.validate()
        
        # 2. Initialize Agent
        agent = TestGenerationAgent(config)

        # 3. Convert Dictionary inputs to Domain Models
        # Convert Test Plan
        try:
            # Handle potential mismatch in fields if necessary, usually dataclasses accept **dict
            test_plan_obj = TestPlan(**request.test_plan)
        except Exception as e:
            logger.error(f"Failed to parse Test Plan: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid Test Plan format: {e}")

        # Convert Codebase Analysis
        # Note: CodebaseAnalysis might contain nested objects (RepositoryConfig) that need handling
        # For now, we assume the dict structure matches the dataclass fields
        try:
            # Filter out fields that might not match the constructor if necessary, 
            # or reconstruct nested objects. 
            # Assuming standard structure matches src.models.github_models.CodebaseAnalysis
            codebase_analysis_obj = CodebaseAnalysis(**request.codebase_analysis)
        except Exception as e:
            logger.error(f"Failed to parse Codebase Analysis: {e}")
            # Fallback: Try to construct with minimal required fields if strict parsing fails
            # or raise error.
            raise HTTPException(status_code=400, detail=f"Invalid Codebase Analysis format: {e}")

        # 4. Determine Test Repo URL
        target_repo_url = request.test_repo_url or config.test_repo.repo_url

        # 5. Execute Generation
        result = await agent.generate_tests(
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

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Test generation failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )
