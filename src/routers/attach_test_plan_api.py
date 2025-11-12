from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import Dict, Any

from src.auth.authentication import authenticate_user
from src.models.attach_test_plan_models import AttachTestPlanRequest, AttachTestPlanResponse
from src.services.attach_test_plan_service import attach_test_plan_to_jira
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.post(
    "/attach/test-plan",
    response_model=AttachTestPlanResponse,
    summary="Attach test plan to Jira ticket",
    description="Generate test plan documents (PDF/Excel) and attach them to the specified Jira ticket"
    #, dependencies=[Depends(authenticate_user)]
)
async def attach_test_plan(
    request: AttachTestPlanRequest = Body(..., description="Test plan attachment request")
) -> AttachTestPlanResponse:
    """
    Attach generated test plan to Jira ticket
    
    This endpoint:
    1. Generates PDF and Excel test plan documents
    2. Attaches them to the specified Jira ticket
    3. Adds a summary comment with test plan details
    4. Adds a tracking label to the ticket
    
    Args:
        request: AttachTestPlanRequest with jira_ticket_key and test_plan data
        
    Returns:
        AttachTestPlanResponse with operation results
    """
    logger.info(f"Received test plan attachment request for {request.jira_ticket_key}")
    
    try:
        # Convert request to dictionary for service processing
        request_data = {
            "jira_ticket_key": request.jira_ticket_key,
            "test_plan": request.test_plan
        }
        
        # Call the service
        result = await attach_test_plan_to_jira(request_data)
        
        # Convert back to response model
        response = AttachTestPlanResponse(**result)
        
        if response.status == "error":
            logger.error(f"Test plan attachment failed: {response.message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=response.message
            )
        
        logger.info(f"Test plan attachment completed successfully for {request.jira_ticket_key}")
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
    return {"status": "healthy", "service": "attach_test_plan"}