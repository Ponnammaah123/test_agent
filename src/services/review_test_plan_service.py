from typing import Dict, Any, List, Tuple
import json
import re

from src.models.test_plan_models import TestPlan
from src.models.jira_models import JiraTicket
from src.models.review_test_plan_models import ReviewTestPlanResponse
from src.clients.gemini_client import GeminiClient
from src.utils.logger import get_logger
from src.utils.exceptions import GeminiClientException
from src.config.settings import Config

logger = get_logger(__name__)

class ReviewTestPlanService:
    """
    Service for reviewing and enhancing test plans using AI
    
    Responsibilities:
    - Validate test plan quality against standards
    - Identify gaps and issues using AI analysis
    - Generate enhancement recommendations
    - Automatically add missing scenarios
    """
    
    def __init__(self, config: Config):
        """
        Initialize review service
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.gemini_client = GeminiClient(config)
        logger.info("ReviewTestPlanService initialized")

    async def review_and_enhance_test_plan(
        self, 
        test_plan_data: Dict[str, Any],
        jira_ticket_data: Dict[str, Any],
        max_iterations: int = 2
    ) -> ReviewTestPlanResponse:
        """
        Main method to review and enhance test plan
        
        Args:
            test_plan_data: Original test plan data
            jira_ticket_data: Jira ticket data for context
            max_iterations: Maximum enhancement iterations
            
        Returns:
            ReviewTestPlanResponse with enhancement results
        """
        logger.info("Starting test plan review and enhancement process")
        
        try:
            # Step 1: Convert data to objects
            test_plan = self._create_test_plan_object(test_plan_data)
            jira_ticket = self._create_jira_ticket_object(jira_ticket_data)
            
            original_scenario_count = len(test_plan.test_scenarios)
            logger.info(f"Original test plan has {original_scenario_count} scenarios")
            
            # Step 2: Validate quality and identify issues
            logger.info("Validating test plan quality")
            quality_issues = self._validate_quality(
                test_plan.test_scenarios,
                test_plan.traceability_matrix,
                jira_ticket
            )
            
            logger.info(f"Found {len(quality_issues)} quality issues")
            for issue in quality_issues[:5]:
                logger.info(f"Quality issue: {issue}")
            
            # Step 3: Enhance if issues found
            if quality_issues:
                logger.info("Enhancing test plan to address quality issues")
                enhanced_plan = self._enhance_test_plan(
                    test_plan, 
                    jira_ticket, 
                    quality_issues, 
                    max_iterations
                )
                final_scenario_count = len(enhanced_plan.test_scenarios)
                scenarios_added = final_scenario_count - original_scenario_count
                
                logger.info(f"Enhancement complete: Added {scenarios_added} scenarios")
            else:
                logger.info("No quality issues found, using original test plan")
                enhanced_plan = test_plan
                scenarios_added = 0
                final_scenario_count = original_scenario_count
            
            # Step 4: Prepare response
            return ReviewTestPlanResponse(
                status="success",
                message="Test plan reviewed and enhanced successfully",
                enhanced_test_plan=enhanced_plan.to_dict(),
                quality_issues_found=quality_issues,
                scenarios_added=scenarios_added,
                original_scenario_count=original_scenario_count,
                final_scenario_count=final_scenario_count
            )
            
        except GeminiClientException as e:
            error_msg = f"AI enhancement failed: {str(e)}"
            logger.error(error_msg)
            return ReviewTestPlanResponse(
                status="error",
                message=error_msg,
                quality_issues_found=[],
                scenarios_added=0,
                original_scenario_count=len(test_plan_data.get('test_scenarios', [])),
                final_scenario_count=len(test_plan_data.get('test_scenarios', []))
            )
        except Exception as e:
            error_msg = f"Unexpected error during test plan review: {str(e)}"
            logger.error(error_msg)
            return ReviewTestPlanResponse(
                status="error",
                message=error_msg,
                quality_issues_found=[],
                scenarios_added=0,
                original_scenario_count=len(test_plan_data.get('test_scenarios', [])),
                final_scenario_count=len(test_plan_data.get('test_scenarios', []))
            )

    def _create_test_plan_object(self, test_plan_data: Dict[str, Any]) -> TestPlan:
        """Create TestPlan object from dictionary data"""
        return TestPlan(
            jira_ticket=test_plan_data.get('jira_ticket', ''),
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

    def _create_jira_ticket_object(self, jira_ticket_data: Dict[str, Any]) -> JiraTicket:
        """Create JiraTicket object from dictionary data"""
        return JiraTicket(
            key=jira_ticket_data.get('key', ''),
            summary=jira_ticket_data.get('summary', ''),
            description=jira_ticket_data.get('description', ''),
            story_type=jira_ticket_data.get('story_type', 'Story'),
            acceptance_criteria=jira_ticket_data.get('acceptance_criteria', []),
            components=jira_ticket_data.get('components', []),
            linked_issues=jira_ticket_data.get('linked_issues', []),
            assignee=jira_ticket_data.get('assignee', ''),
            status=jira_ticket_data.get('status', ''),
            priority=jira_ticket_data.get('priority', 'Medium'),
            reporter=jira_ticket_data.get('reporter', ''),
            labels=jira_ticket_data.get('labels', [])
        )

    def _validate_quality(
        self,
        scenarios: List[Dict],
        traceability: Dict[str, List[str]],
        ticket: JiraTicket
    ) -> List[str]:
        """
        Validate test plan quality
        
        Args:
            scenarios: Test scenarios
            traceability: Traceability matrix
            ticket: Jira ticket
            
        Returns:
            List of quality issues (empty if no issues)
        """
        issues = []
        
        # Calculate expected minimum scenarios
        ac_count = len(traceability.keys())
        expected_min = max(10, ac_count * 2)  # Reduced from original for practicality
        
        # 1. Scenario count check
        if len(scenarios) < expected_min:
            issues.append(
                f"Insufficient scenarios: {len(scenarios)} "
                f"(minimum {expected_min} recommended for {ac_count} acceptance criteria)"
            )
        
        # 2. Per-AC coverage check
        for ac, scenario_ids in traceability.items():
            if len(scenario_ids) < 2:
                issues.append(
                    f"Acceptance criterion '{ac[:50]}...' has only "
                    f"{len(scenario_ids)} scenario(s) - recommend minimum 2"
                )
        
        # 3. Test type coverage
        test_types = [s.get('test_type', 'Unknown') for s in scenarios]
        if 'API' not in test_types:
            issues.append("Missing API test scenarios")
        if 'E2E' not in test_types:
            issues.append("Missing E2E test scenarios")
        
        # 4. Priority distribution
        priority_counts = {'High': 0, 'Medium': 0, 'Low': 0}
        for s in scenarios:
            priority = s.get('priority', 'Medium')
            if priority in priority_counts:
                priority_counts[priority] += 1
        
        if priority_counts['High'] == 0:
            issues.append("No High priority scenarios - critical functionality may be untested")
        
        # 5. Scenario completeness
        incomplete_scenarios = []
        for scenario in scenarios:
            if (not scenario.get('given') or 
                not scenario.get('when') or 
                not scenario.get('then') or
                len(scenario.get('given', '')) < 10 or
                len(scenario.get('then', '')) < 10):
                incomplete_scenarios.append(scenario.get('id', 'unknown'))
        
        if incomplete_scenarios:
            issues.append(f"{len(incomplete_scenarios)} scenarios have incomplete Given/When/Then structure")
        
        logger.info(f"Quality validation complete: {len(issues)} issues found")
        return issues

    def _enhance_test_plan(
        self,
        test_plan: TestPlan,
        ticket: JiraTicket,
        quality_issues: List[str],
        max_iterations: int
    ) -> TestPlan:
        """
        Enhance test plan using AI to address quality issues
        
        Args:
            test_plan: Original test plan
            ticket: Jira ticket for context
            quality_issues: List of quality issues to address
            max_iterations: Maximum enhancement iterations
            
        Returns:
            Enhanced test plan
        """
        logger.info(f"Starting test plan enhancement with {max_iterations} iterations")
        
        iteration = 0
        current_scenarios = test_plan.test_scenarios.copy()
        current_traceability = test_plan.traceability_matrix.copy()
        remaining_issues = quality_issues.copy()
        
        while iteration < max_iterations and remaining_issues:
            iteration += 1
            logger.info(f"Enhancement iteration {iteration}/{max_iterations}")
            
            # Generate enhancements using AI
            additional_scenarios, traceability_updates = self._generate_enhancements(
                current_scenarios,
                current_traceability,
                remaining_issues,
                ticket
            )
            
            if not additional_scenarios:
                logger.warning("No additional scenarios generated, stopping enhancement")
                break
            
            # Merge enhancements
            logger.info(f"Adding {len(additional_scenarios)} additional scenarios")
            current_scenarios.extend(additional_scenarios)
            
            # Update traceability
            if traceability_updates:
                for key, scenario_ids in traceability_updates.items():
                    if key in current_traceability:
                        existing = set(str(s) for s in current_traceability[key])
                        new_ids = set(str(s) for s in scenario_ids)
                        current_traceability[key] = list(existing | new_ids)
                    else:
                        current_traceability[key] = scenario_ids
            
            # Re-validate to check if issues are resolved
            remaining_issues = self._validate_quality(current_scenarios, current_traceability, ticket)
            if remaining_issues:
                logger.info(f"Remaining quality issues after iteration {iteration}: {len(remaining_issues)}")
            else:
                logger.info("All quality issues resolved")
                break
        
        # Create enhanced test plan
        enhanced_plan = TestPlan(
            jira_ticket=test_plan.jira_ticket,
            strategy=test_plan.strategy,
            test_approach=test_plan.test_approach,
            testable_components=test_plan.testable_components,
            test_scenarios=current_scenarios,
            traceability_matrix=current_traceability,
            coverage_targets=test_plan.coverage_targets,
            confidence_score=min(100, test_plan.confidence_score + 5),  # Slight confidence boost
            environment_config=test_plan.environment_config,
            quality_issues=remaining_issues
        )
        
        logger.info(f"Enhancement complete: {len(current_scenarios)} total scenarios")
        return enhanced_plan

    def _generate_enhancements(
        self,
        current_scenarios: List[Dict],
        traceability: Dict[str, List[str]],
        quality_issues: List[str],
        ticket: JiraTicket
    ) -> Tuple[List[Dict], Dict[str, List[str]]]:
        """
        Generate additional scenarios to address quality issues using AI
        
        Args:
            current_scenarios: Existing scenarios
            traceability: Current traceability matrix
            quality_issues: List of detected issues
            ticket: Jira ticket
            
        Returns:
            Tuple of (additional_scenarios, traceability_updates)
        """
        logger.info("Generating enhancement scenarios using AI")
        
        # Prepare scenario summary
        scenario_summary = [
            {'id': s.get('id'), 'title': s.get('title'), 'test_type': s.get('test_type')}
            for s in current_scenarios
        ]
        
        # Calculate next scenario ID
        next_id = len(current_scenarios) + 1
        
        enhancement_prompt = f"""You are a QE expert enhancing a test plan that has quality issues.

JIRA TICKET: {ticket.key} - {ticket.summary}

Acceptance Criteria:
{chr(10).join(['- ' + ac for ac in ticket.acceptance_criteria]) if ticket.acceptance_criteria else 'Infer from description'}

Description:
{ticket.description or 'No description available'}

QUALITY ISSUES TO ADDRESS:
{chr(10).join(['- ' + issue for issue in quality_issues[:8]])}

CURRENT SCENARIOS ({len(current_scenarios)} total):
{json.dumps(scenario_summary, indent=2)}

YOUR TASK:
Generate 5-10 additional test scenarios to address the quality issues above.

Focus on:
1. Missing test types (API/E2E)
2. Acceptance criteria with insufficient coverage
3. Edge cases and boundary conditions
4. Negative test scenarios

RETURN ONLY VALID JSON (no markdown):
{{
  "additional_scenarios": [
    {{
      "id": "TS-{next_id:03d}",
      "title": "Clear, specific title",
      "given": "Detailed preconditions",
      "when": "Specific action",
      "then": "Specific expected outcome", 
      "priority": "High|Medium|Low",
      "test_type": "API|E2E"
    }}
  ],
  "traceability_updates": {{
    "Full acceptance criterion text": ["TS-{next_id:03d}"]
  }}
}}

CRITICAL: Return ONLY the JSON object above. No markdown, no explanations.
"""
        
        try:
            # FIX: Call generate synchronously (without await)
            response = self.gemini_client.generate(enhancement_prompt)
            
            # Parse response
            text = response.strip()
            
            # Remove markdown if present
            if text.startswith('```'):
                text = text.split('\n', 1)[1] if '\n' in text else text[3:]
                if text.endswith('```'):
                    text = text.rsplit('```', 1)[0]
            
            # Find JSON
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.error("No JSON found in enhancement response")
                return [], {}
            
            json_str = text[json_start:json_end]
            
            # Fix common JSON issues
            json_str = self._fix_json_issues(json_str)
            
            data = json.loads(json_str)
            
            additional_scenarios = data.get('additional_scenarios', [])
            traceability_updates = data.get('traceability_updates', {})
            
            logger.info(f"Generated {len(additional_scenarios)} enhancement scenarios")
            return additional_scenarios, traceability_updates
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse enhancement JSON: {str(e)}")
            logger.debug(f"Problematic JSON string: {json_str[:500] if 'json_str' in locals() else 'N/A'}")
            return [], {}
        except Exception as e:
            logger.error(f"Enhancement generation failed: {str(e)}")
            return [], {}

    def _fix_json_issues(self, json_str: str) -> str:
        """
        Fix common JSON formatting issues
        
        Args:
            json_str: JSON string to fix
            
        Returns:
            Fixed JSON string
        """
        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Fix missing commas between array elements
        json_str = re.sub(r'\}(\s*)\{', r'},\1{', json_str)
        
        # Remove any trailing text after the final closing brace
        last_brace = json_str.rfind('}')
        if last_brace != -1 and last_brace < len(json_str) - 1:
            json_str = json_str[:last_brace + 1]
        
        return json_str

# Service instance (singleton pattern)
_review_test_plan_service = None

async def review_and_enhance_test_plan(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main function to review and enhance test plan
    
    Args:
        request_data: Dictionary with test_plan, jira_ticket, and max_iterations
        
    Returns:
        Dictionary with operation results
    """
    global _review_test_plan_service
    
    try:
        if _review_test_plan_service is None:
            config = Config()
            config.validate()
            _review_test_plan_service = ReviewTestPlanService(config)
        
        test_plan_data = request_data['test_plan']
        jira_ticket_data = request_data['jira_ticket']
        max_iterations = request_data.get('max_iterations', 2)
        
        response = await _review_test_plan_service.review_and_enhance_test_plan(
            test_plan_data, jira_ticket_data, max_iterations
        )
        
        return response.dict()
        
    except Exception as e:
        logger.error(f"Error in review_and_enhance_test_plan: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to review and enhance test plan: {str(e)}"
        }