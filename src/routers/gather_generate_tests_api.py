import re
import io
import requests
import openpyxl
from fastapi import APIRouter, HTTPException, Body, status
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Tuple

# Import core clients and config
from src.config.settings import Config
from src.clients.jira_client import JiraClient
from src.clients.github_client import GitHubClient
from src.utils.logger import get_logger
from src.utils.exceptions import JiraClientException, GitHubClientException

# --- NEW IMPORTS ---
# Import the agent and models needed for generation
from src.agents.test_generation_agent import TestGenerationAgent
from src.models.test_plan_models import TestPlan
from src.models.github_models import CodebaseAnalysis
# --- END NEW IMPORTS ---

logger = get_logger(__name__)
router = APIRouter()

# --- Pydantic Models ---

class GatherGenerateTestsRequest(BaseModel):
    """Input model for the new orchestration endpoint"""
    jira_ticket_key: str = Field(..., description="Jira ticket key (e.g., QEA-19)")
    scope_analysis: Dict[str, Any] = Field(..., description="Scope analysis provided by the user")

# --- MODEL REMOVED ---
# The GenerateTestsPayload model is no longer needed as an output from this file.
# --- END MODEL REMOVED ---


# --- Helper Functions (No changes) ---

def _parse_comment_data(comments: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Parses comments to find the latest branch and test repo URL.
    """
    logger.info(f"Parsing {len(comments)} comments for branch and repo URL...")
    
    # Regex patterns to find data in comments
    repo_pattern = re.compile(r"\*Test Repository:\*.*?\[(https://.*?)\|")
    branch_pattern = re.compile(r"\*Branch:\*.*?{monospace}(.*?){monospace}")
    
    # Iterate in reverse (newest comments first)
    for comment in reversed(comments):
        body = comment.get('body', '')
        if "E2E Tests Generated Successfully" in body:
            logger.info("Found 'E2E Tests Generated' comment.")
            try:
                repo_url_match = repo_pattern.search(body)
                branch_match = branch_pattern.search(body)
                
                if repo_url_match and branch_match:
                    repo_url = repo_url_match.group(1)
                    branch = branch_match.group(1)
                    logger.info(f"Successfully parsed: Branch='{branch}', Repo='{repo_url}'")
                    return branch, repo_url
            except Exception as e:
                logger.warning(f"Failed to parse comment body: {e}")
                continue
                
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Could not find a comment with 'E2E Tests Generated Successfully' containing branch and repo URL."
    )

def _parse_excel_test_plan(attachments: List[Dict[str, Any]], config: Config) -> Dict[str, Any]:
    """
    Downloads and parses the .xlsx test plan attachment.
    
    Args:
        attachments: List of attachment metadata from Jira.
        config: The application configuration object (for auth).
    """
    logger.info(f"Searching for .xlsx test plan in {len(attachments)} attachments...")
    
    excel_url = None
    for attachment in attachments:
        filename = attachment.get('filename', '')
        if "TestPlan" in filename and filename.endswith(".xlsx"):
            excel_url = attachment.get('content')
            logger.info(f"Found Excel test plan: {filename}")
            break
            
    if not excel_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find a '.xlsx' test plan attachment."
        )
        
    try:
        # Download the Excel file
        logger.info(f"Downloading Excel file from: {excel_url}")
        
        # --- FIX: Add authentication to the download request ---
        # Jira attachments require the same auth as the API.
        jira_auth = (config.jira.email, config.jira.api_token)
        response = requests.get(excel_url, auth=jira_auth)
        # --- End of FIX ---
        
        response.raise_for_status()
        
        # Load into memory
        file_bytes = io.BytesIO(response.content)
        wb = openpyxl.load_workbook(file_bytes, data_only=True)
        
        # --- Parse "Overview" Sheet ---
        overview_data = {}
        ws_overview = wb.get_sheet_by_name("Overview")
        for row in ws_overview.iter_rows(min_row=3, max_col=2):
            key = row[0].value
            value = row[1].value
            if key:
                overview_data[key.lower().replace(' ', '_')] = value
        
        # --- Parse "Test Scenarios" Sheet ---
        scenarios = []
        ws_scenarios = wb.get_sheet_by_name("Test Scenarios")
        
        # Get headers
        headers = [cell.value.lower() for cell in ws_scenarios[1]]
        
        for row in ws_scenarios.iter_rows(min_row=2):
            scenario_data = {headers[i]: cell.value for i, cell in enumerate(row)}
            if scenario_data.get('id'): # Only add if row has data
                scenarios.append({
                    "id": scenario_data.get('id'),
                    "title": scenario_data.get('title'),
                    "priority": scenario_data.get('priority'),
                    "test_type": scenario_data.get('type'), # Map 'type' from Excel to 'test_type'
                    "given": scenario_data.get('given'),
                    "when": scenario_data.get('when'),
                    "then": scenario_data.get('then'),
                })
        
        logger.info(f"Parsed {len(scenarios)} test scenarios from Excel.")
        
        # Assemble the test_plan object
        test_plan = {
            "jira_ticket": overview_data.get('jira_ticket', ''),
            "strategy": overview_data.get('strategy', ''),
            "test_approach": overview_data.get('test_approach', ''),
            "confidence_score": overview_data.get('confidence_score', 0.0),
            "test_scenarios": scenarios,
            # Note: Other fields like traceability_matrix are not in the Excel, so they are omitted
        }
        
        return test_plan

    except requests.RequestException as e:
        logger.error(f"Failed to download Excel file: {e}")
        # Pass the error response text if available
        error_detail = f"Failed to download attachment: {e}"
        if e.response is not None:
             error_detail = f"Failed to download attachment: {e.response.status_code} {e.response.reason} for url: {excel_url}"
        raise HTTPException(status_code=502, detail=error_detail)
    except Exception as e:
        logger.error(f"Failed to parse Excel file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to parse Excel file: {e}")

# --- API Endpoint (Modified) ---

@router.post(
    "/gather_response_for_generate/tests",
    # --- RESPONSE MODEL CHANGED ---
    response_model=Dict[str, Any],
    summary="Orchestrate and Generate Tests",
    description="Gathers all data AND generates the test code in a single call."
    # --- END RESPONSE MODEL CHANGED ---
)
async def gather_response_for_generate_tests(
    request: GatherGenerateTestsRequest = Body(...)
) -> Dict[str, Any]: # --- RETURN TYPE CHANGED ---
    """
    This endpoint automates the entire data gathering and generation service.
    
    1. Fetches Jira ticket details (comments, attachments).
    2. Parses comments for the Git branch and Test Repo URL.
    3. Downloads and parses the `.xlsx` Test Plan attachment.
    4. Calls the `/analyze-codebase` logic with the found branch.
    5. Initializes the TestGenerationAgent.
    6. Calls the agent's generate_tests method.
    7. Assembles and returns the final generated test files.
    """
    
    try:
        config = Config()
        config.validate()
        
        jira_ticket_key = request.jira_ticket_key
        logger.info(f"[{jira_ticket_key}] Starting full test generation orchestration...")
        
        # --- Step 1: Fetch Jira Data ---
        jira_client = JiraClient(config)
        
        logger.info(f"[{jira_ticket_key}] (1/5) Fetching comments and attachments...")
        comments = jira_client.get_comments(jira_ticket_key, top_n=10) # Get latest 10
        attachments = jira_client.get_attachments(jira_ticket_key)
        
        if not comments or not attachments:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No comments or attachments found for this ticket. Agent may not have run."
            )

        # --- Step 2: Parse Comments for Branch & Repo URL ---
        logger.info(f"[{jira_ticket_key}] (2/5) Parsing comment data...")
        branch, test_repo_url = _parse_comment_data(comments)

        # --- Step 3: Parse Test Plan from Excel Attachment ---
        logger.info(f"[{jira_ticket_key}] (3/5) Parsing test plan from Excel attachment...")
        test_plan = _parse_excel_test_plan(attachments, config)
        
        # --- Step 4: Get Codebase Analysis ---
        logger.info(f"[{jira_ticket_key}] (4/5) Analyzing codebase for branch: {branch}...")
        github_client = GitHubClient(config)
        
        codebase_analysis_obj = github_client.analyze_codebase(branch)
        codebase_analysis = codebase_analysis_obj.model_dump()
        logger.info(f"[{jira_ticket_key}] Codebase analysis complete.")

        # --- Step 5: (NEW) Call Test Generation Agent ---
        logger.info(f"[{jira_ticket_key}] (5/5) Initializing and running Test Generation Agent...")
        
        # Initialize Agent
        agent = TestGenerationAgent(config)

        # Convert Dictionary inputs to Domain Models
        try:
            test_plan_obj = TestPlan(**test_plan)
            codebase_analysis_obj_typed = CodebaseAnalysis(**codebase_analysis)
        except Exception as e:
            logger.error(f"Failed to parse models for agent: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid data for agent models: {e}")

        # Determine Test Repo URL
        target_repo_url = test_repo_url # Use the one parsed from comments

        # Execute Generation
        result = await agent.generate_tests(
            jira_ticket_key=jira_ticket_key,
            test_plan=test_plan_obj,
            codebase_analysis=codebase_analysis_obj_typed,
            test_repo_url=target_repo_url,
            scope_analysis=request.scope_analysis
        )

        logger.info(f"[{jira_ticket_key}] Orchestration and generation complete. Returning final response.")

        # Return the response from the generation step
        return {
            "status": "success",
            "message": f"Generated {len(result.get('test_files', {}))} test files",
            "data": result
        }
        
    except HTTPException:
        raise # Re-raise known HTTP exceptions
    except (JiraClientException, GitHubClientException) as e:
        logger.error(f"[{request.jira_ticket_key}] Client Error: {e}")
        raise HTTPException(status_code=502, detail=f"Client Error: {e}")
    except Exception as e:
        logger.error(f"[{request.jira_ticket_key}] Unexpected Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected Internal Error: {e}")