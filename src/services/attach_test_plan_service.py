from typing import Dict, Any, List
from pathlib import Path
from src.models.test_plan_models import TestPlan
from src.models.attach_test_plan_models import AttachTestPlanResponse
from src.utils.test_plan_generator import TestPlanDocumentGenerator
from src.clients.jira_client import JiraClient
from src.utils.logger import get_logger
from src.utils.exceptions import JiraClientException
from src.config.settings import Config

logger = get_logger(__name__)

class AttachTestPlanService:
    """Service for attaching test plans to Jira tickets"""
    
    def __init__(self, config: Config):
        """
        Initialize service with configuration
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.document_generator = TestPlanDocumentGenerator()
        logger.info("AttachTestPlanService initialized")

    async def attach_test_plan_to_jira(self, jira_ticket_key: str, test_plan_data: Dict[str, Any]) -> AttachTestPlanResponse:
        """
        Main method to attach test plan to Jira ticket
        
        Args:
            jira_ticket_key: Jira ticket key
            test_plan_data: Test plan data dictionary
            
        Returns:
            AttachTestPlanResponse with operation results
        """
        logger.info(f"Starting test plan attachment process for {jira_ticket_key}")
        
        try:
            # Step 1: Initialize Jira client
            jira_client = self._get_jira_client()
            logger.info(f"Jira client initialized for {jira_ticket_key}")

            # Step 2: Convert test plan data to TestPlan object
            test_plan = self._create_test_plan_object(jira_ticket_key, test_plan_data)
            logger.info(f"Test plan object created with {len(test_plan.test_scenarios)} scenarios")

            # Step 3: Generate test plan documents
            logger.info("Generating test plan documents")
            documents = self.document_generator.generate_both(test_plan, jira_ticket_key)
            logger.info(f"Generated documents: PDF={documents['pdf']}, Excel={documents['excel']}")

            # Step 4: Attach files to Jira ticket using existing Jira client
            logger.info("Attaching files to Jira ticket")
            attached_files = self._attach_files_to_jira(jira_client, jira_ticket_key, documents)
            logger.info(f"Successfully attached {len(attached_files)} files")

            # Step 5: Add summary comment to Jira using existing Jira client
            logger.info("Adding summary comment to Jira")
            comment_success = self._add_summary_comment(jira_client, jira_ticket_key, test_plan, attached_files)
            if comment_success:
                logger.info("Summary comment added successfully")
            else:
                logger.warning("Failed to add summary comment")

            # Step 6: Add tracking label using existing Jira client
            logger.info("Adding tracking label to Jira ticket")
            label_success = self._add_tracking_label(jira_client, jira_ticket_key)
            if label_success:
                logger.info("Tracking label added successfully")
            else:
                logger.warning("Failed to add tracking label")

            return AttachTestPlanResponse(
                status="success",
                message=f"Test plan documents attached successfully to {jira_ticket_key}",
                attached_files=attached_files,
                jira_comment_id="comment_added" if comment_success else ""
            )

        except JiraClientException as e:
            error_msg = f"Jira operation failed for {jira_ticket_key}: {str(e)}"
            logger.error(error_msg)
            return AttachTestPlanResponse(
                status="error",
                message=error_msg
            )
        except Exception as e:
            error_msg = f"Unexpected error attaching test plan to {jira_ticket_key}: {str(e)}"
            logger.error(error_msg)
            return AttachTestPlanResponse(
                status="error",
                message=error_msg
            )

    def _get_jira_client(self) -> JiraClient:
        """Get Jira client instance using existing JiraClient class"""
        return JiraClient(self.config)

    def _create_test_plan_object(self, jira_ticket_key: str, test_plan_data: Dict[str, Any]) -> TestPlan:
        """Create TestPlan object from dictionary data"""
        return TestPlan(
            jira_ticket=jira_ticket_key,
            strategy=test_plan_data.get('strategy', ''),
            test_approach=test_plan_data.get('test_approach', ''),
            testable_components=test_plan_data.get('testable_components', []),
            test_scenarios=test_plan_data.get('test_scenarios', []),
            traceability_matrix=test_plan_data.get('traceability_matrix', {}),
            coverage_targets=test_plan_data.get('coverage_targets', {}),
            confidence_score=test_plan_data.get('confidence_score', 0.0),
            environment_config=test_plan_data.get('environment_config'),
            generated_at=test_plan_data.get('generated_at'),
            quality_issues=test_plan_data.get('quality_issues', [])
        )

    def _attach_files_to_jira(self, jira_client: JiraClient, jira_ticket_key: str, documents: Dict[str, str]) -> List[str]:
        """Attach generated files to Jira ticket using existing Jira client"""
        file_paths = [documents['pdf'], documents['excel']]
        
        # Use existing Jira client attach_files method
        success = jira_client.attach_files(jira_ticket_key, file_paths)
        
        if success:
            logger.info(f"Successfully attached files to {jira_ticket_key}")
            return [Path(path).name for path in file_paths]
        else:
            raise JiraClientException(f"Failed to attach files to {jira_ticket_key}")

    def _add_summary_comment(self, jira_client: JiraClient, jira_ticket_key: str, test_plan: TestPlan, attached_files: List[str]) -> bool:
        """Add summary comment to Jira ticket using existing Jira client"""
        summary_comment = self._format_summary_comment(test_plan, attached_files)
        
        # Use existing Jira client add_comment method
        success = jira_client.add_comment(jira_ticket_key, summary_comment)
        
        if success:
            logger.info(f"Successfully added comment to {jira_ticket_key}")
        else:
            logger.warning(f"Failed to add comment to {jira_ticket_key}")
            
        return success

    def _format_summary_comment(self, test_plan: TestPlan, attached_files: List[str]) -> str:
        """Format the summary comment for Jira"""
        high_priority_count = len(test_plan.get_high_priority_scenarios())
        
        comment = f"""Test Plan Generated Successfully

The QE Agent has generated a comprehensive test plan for this ticket.

Documents Attached:
- {attached_files[0]} (detailed scenarios and traceability)
- {attached_files[1]} (editable spreadsheet with multiple sheets)

Summary:
- Total Scenarios: {test_plan.get_scenario_count()}
- High Priority Scenarios: {high_priority_count}
- Confidence Score: {test_plan.confidence_score}%

Next Steps:
Review the attached documents and approve the test plan to proceed with test generation."""
        
        return comment

    def _add_tracking_label(self, jira_client: JiraClient, jira_ticket_key: str) -> bool:
        """Add tracking label to Jira ticket using existing Jira client"""
        
        # Use existing Jira client add_label method
        success = jira_client.add_label(jira_ticket_key, 'qe-agent-processed')
        
        if success:
            logger.info(f"Successfully added label to {jira_ticket_key}")
        else:
            logger.warning(f"Failed to add label to {jira_ticket_key}")
            
        return success

# Service instance (singleton pattern)
_attach_test_plan_service = None

async def attach_test_plan_to_jira(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main function to attach test plan to Jira
    
    Args:
        request_data: Dictionary with jira_ticket_key and test_plan
        
    Returns:
        Dictionary with operation results
    """
    global _attach_test_plan_service
    
    try:
        if _attach_test_plan_service is None:
            config = Config()
            config.validate()
            _attach_test_plan_service = AttachTestPlanService(config)
        
        jira_ticket_key = request_data['jira_ticket_key']
        test_plan_data = request_data['test_plan']
        
        response = await _attach_test_plan_service.attach_test_plan_to_jira(
            jira_ticket_key, test_plan_data
        )
        
        return response.dict()
        
    except Exception as e:
        logger.error(f"Error in attach_test_plan_to_jira: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to attach test plan: {str(e)}"
        }