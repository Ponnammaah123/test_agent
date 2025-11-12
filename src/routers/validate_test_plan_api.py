from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Body, Header
from typing import Dict
import json
from src.services.validate_test_plan_service import validate_existing_test_plan
from src.models.validate_test_plan_models import ValidateTestPlanRequest

router = APIRouter()

# def extract_token(authorization: str = Header(...)) -> str:
#     if not authorization.startswith("Bearer "):
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header")
#     return authorization.split(" ")[1]

@router.post("/validate/test-plan"
             #, dependencies=[Depends(authenticate_user)]
             )
async def validate_test_plan(
    request_data: ValidateTestPlanRequest = Body(...)
    # ,
    # token: str = Depends(extract_token)
):
    try:
        input_params = request_data.model_dump()
        
        result = await validate_existing_test_plan(
            input_params=input_params
            # ,
            # token=token
        )
        
        if result.get("status") == "error":
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Validation error occurred")
            )
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))