from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import Dict, Any

from src.models.review_test_plan_models import ReviewTestPlanRequest, ReviewTestPlanResponse
from src.services.review_test_plan_service import review_and_enhance_test_plan
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.post(
    "/review/test-plan",
    response_model=ReviewTestPlanResponse,
    summary="Review and enhance test plan",
    description="Review test plan quality and enhance it using AI to address identified issues"
    #, dependencies=[Depends(authenticate_user)]
)
async def review_test_plan(
    request: ReviewTestPlanRequest = Body(..., description="Test plan review request")
) -> ReviewTestPlanResponse:
    """
    Review and enhance test plan quality
    
    This endpoint:
    1. Validates test plan quality against standards
    2. Identifies gaps and issues using AI analysis
    3. Generates additional scenarios to address issues
    4. Returns enhanced test plan with quality improvements
    
    Args:
        request: ReviewTestPlanRequest with test_plan, jira_ticket, and max_iterations
        
    Returns:
        ReviewTestPlanResponse with enhancement results
    """
    logger.info(f"Received test plan review request for {request.jira_ticket.get('key', 'unknown')}")
    
    try:
        # Convert request to dictionary for service processing
        request_data = {
            "test_plan": request.test_plan,
            "jira_ticket": request.jira_ticket,
            "max_iterations": request.max_iterations
        }
        
        # Call the service
        result = await review_and_enhance_test_plan(request_data)
        
        # Convert back to response model
        response = ReviewTestPlanResponse(**result)
        
        if response.status == "error":
            logger.error(f"Test plan review failed: {response.message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=response.message
            )
        
        logger.info(f"Test plan review completed successfully: {response.scenarios_added} scenarios added")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Internal server error: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "review_test_plan"}