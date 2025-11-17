from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import existing routers
from src.routers.jira_ticket_fetcher_api import router as jira_fetcher_router
from src.utils.validation_exception_handler import format_validation_errors
from src.routers.validate_test_plan_api import router as validate_test_plan_router
from src.routers.attach_test_plan_api import router as attach_test_plan_router
from src.routers.review_test_plan_api import router as review_test_plan_router
from src.routers.analyse_codebase_api import router as analyse_codebase_router
from src.routers.test_generation_api import router as test_generation_router

# NEW: Import the orchestration router
from src.routers.gather_generate_tests_api import router as gather_generate_tests_router


app = FastAPI(
        title="Tools API", 
        version="1.0.0", 
        root_path="/api/v1/api-qe-orchestrator")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_response = format_validation_errors(exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response
    )

# --- Include all routers ---

# NEW: Register the orchestration router
# This makes the endpoint available at /gather_response_for_generate/tests
app.include_router(gather_generate_tests_router, tags=["Test Generation Orchestrator"])


# Existing routers
app.include_router(jira_fetcher_router, tags=["Fetch Jira ticket details"], prefix="/jira")
app.include_router(validate_test_plan_router,  tags=["Test Plan Validation"])
app.include_router(attach_test_plan_router, tags=["Test Plan Attachment"])
app.include_router(review_test_plan_router, prefix="/api/v1", tags=["Test Plan Review"])
app.include_router(analyse_codebase_router, tags=["Analyse code base from Git"])
app.include_router(test_generation_router, prefix="/api/v1", tags=["Test Generation"])

@app.get("/")
async def root():
    return {"message": "Welcome to the SlingShot QE orchestrator !"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)