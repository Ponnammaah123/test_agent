# ==============================================
# Google Gemini AI client
# ==============================================

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import json
from typing import Dict, Any

from src.config.settings import Config
from src.models.jira_models import JiraTicket
from src.models.github_models import CodebaseAnalysis
from src.models.test_plan_models import TestPlan
from src.utils.logger import get_logger
from src.utils.exceptions import GeminiClientException
from src.utils.helpers import truncate_string

logger = get_logger(__name__)

class GeminiClient:
    """Client for Google Gemini AI integration"""
    
    def __init__(self, config: Config):
        """
        Initialize Gemini client
        
        Args:
            config: Application configuration
        """
        self.config = config
        
        try:
            genai.configure(api_key=config.gemini.api_key)

            # Use models/gemini-1.5-flash or models/gemini-1.5-pro format
            model_name = config.gemini.model
            if not model_name.startswith('models/'):
                model_name = f'models/{model_name}'

            # Configure model with safety settings
            self.model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={
                    "temperature": config.gemini.temperature,
                    "max_output_tokens": config.gemini.max_tokens,
                }
            )

            logger.info(f"Initialized Gemini model: {model_name}")

        except Exception as e:
            raise GeminiClientException(f"Failed to initialize Gemini: {str(e)}")
    
    def generate_test_plan(
        self, 
        ticket: JiraTicket, 
        codebase: CodebaseAnalysis
    ) -> TestPlan:
        """
        Generate comprehensive test plan using Gemini AI
        
        Args:
            ticket: Jira ticket object
            codebase: Codebase analysis object
            
        Returns:
            TestPlan object
            
        Raises:
            GeminiClientException: If generation fails
        """
        logger.info(f"Generating test plan for {ticket.key} using Gemini AI")
        
        try:
            # Create comprehensive prompt
            prompt = self._create_planning_prompt(ticket, codebase)
            
            # Generate content
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                raise GeminiClientException("Empty response from Gemini")
            
            # Parse structured response
            plan_data = self._parse_gemini_response(response.text)
            
            # Create TestPlan object
            test_plan = TestPlan(
                jira_ticket=ticket.key,
                strategy=plan_data['strategy'],
                test_approach='BDD',
                testable_components=plan_data['testable_components'],
                test_scenarios=plan_data['test_scenarios'],
                traceability_matrix=plan_data['traceability_matrix'],
                coverage_targets=plan_data['coverage_targets'],
                confidence_score=plan_data['confidence_score'],
                environment_config=codebase.repository_config
            )
            
            logger.info(
                f"Generated test plan with {len(test_plan.test_scenarios)} scenarios, "
                f"confidence: {test_plan.confidence_score:.0f}%"
            )
            
            return test_plan
            
        except Exception as e:
            raise GeminiClientException(f"Failed to generate test plan: {str(e)}")
    
    def _create_planning_prompt(
        self, 
        ticket: JiraTicket, 
        codebase: CodebaseAnalysis
    ) -> str:
        """
        Create comprehensive prompt for test planning
        
        Args:
            ticket: Jira ticket object
            codebase: Codebase analysis object
            
        Returns:
            Formatted prompt string
        """
        # Environment configuration section
        env_config = ""
        if codebase.repository_config:
            env_config = f"""
ENVIRONMENT CONFIGURATION (from qe.config.json):
-----------------------------------------------
Test Environment URL: {codebase.repository_config.test_environment_url}
API Base URL: {codebase.repository_config.api_base_url}
Browser Config: {json.dumps(codebase.repository_config.browser_config, indent=2)}
"""
        
        # Business logic section (truncated for token limits)
        business_logic_summary = {}
        for file_path, code in list(codebase.business_logic.items())[:3]:
            business_logic_summary[file_path] = truncate_string(code, 300)
        
        prompt = f"""
You are an expert QE (Quality Engineering) Agent specializing in test planning for BDD (Behavior-Driven Development) approach.

CONTEXT:
--------
You are analyzing a Jira story for which implementation is already complete. Your task is to generate a comprehensive test plan that validates the existing implementation against business requirements.

JIRA STORY DETAILS:
-------------------
Ticket: {ticket.key}
Summary: {ticket.summary}
Type: {ticket.story_type}
Priority: {ticket.priority}
Status: {ticket.status}

Description:
{truncate_string(ticket.description, 500)}

Acceptance Criteria:
{chr(10).join(['- ' + ac for ac in ticket.acceptance_criteria]) if ticket.acceptance_criteria else 'None explicitly specified - infer from description and implementation'}

Components: {', '.join(ticket.components) if ticket.components else 'Not specified'}
Linked Issues: {', '.join(ticket.linked_issues) if ticket.linked_issues else 'None'}

CODEBASE ANALYSIS:
-----------------
Repository: {codebase.repository}
Branch: {codebase.branch}
Commits Analyzed: {codebase.commit_count}
Files Changed: {len(codebase.files_changed)} files
Key Files: {', '.join(codebase.files_changed[:10])}

Components Identified: {', '.join(codebase.components_identified) if codebase.components_identified else 'None identified'}
Current Test Coverage: {codebase.test_coverage:.1f}%
Dependencies: {', '.join(codebase.dependencies[:15])}
{env_config}

IMPLEMENTATION CODE SAMPLES:
---------------------------
{json.dumps(business_logic_summary, indent=2)}

TASK:
-----
Generate a comprehensive test plan in VALID JSON format with the following exact structure:

{{
  "strategy": "High-level test strategy description (2-3 sentences explaining the overall testing approach)",
  "testable_components": ["Component1", "Component2", "Component3"],
  "test_scenarios": [
    {{
      "id": "TS-001",
      "title": "Clear, descriptive scenario title",
      "given": "Given precondition/context (detailed setup and prerequisites)",
      "when": "When action/event occurs (specific user action or system trigger)",
      "then": "Then expected outcome (specific, measurable validation criteria)",
      "priority": "High|Medium|Low",
      "test_type": "API|E2E"
    }}
  ],
  "traceability_matrix": {{
    "Acceptance Criterion 1 full text": ["TS-001", "TS-002"],
    "Acceptance Criterion 2 full text": ["TS-003", "TS-004"],
    "Edge case or validation requirement": ["TS-005"]
  }},
  "coverage_targets": {{
    "api_tests": "80%",
    "e2e_tests": "90%",
    "integration_tests": "75%"
  }},
  "confidence_score": 85
}}

REQUIREMENTS:
-------------
1. BDD Approach: Tests verify existing behavior against requirements
2. Focus on API Integration Tests: Validate backend APIs, data flow, service integration
3. Focus on E2E Tests (Playwright): Validate complete user workflows through UI
4. DETAILED Traceability Matrix:
   - Use FULL TEXT of acceptance criteria as keys (not just "AC-1", "AC-2")
   - Map each criterion to ALL test scenarios that validate it
   - Include edge cases and implied requirements as separate entries
   - Each acceptance criterion should have at least 2-3 test scenarios covering happy path, edge cases, and error scenarios
5. DETAILED Test Scenarios (5-15 scenarios):
   - Given: Detailed preconditions, test data setup, system state
   - When: Specific user action, API call, or system event
   - Then: Specific validation criteria with expected values
   - Happy path scenarios (priority: High)
   - Edge cases and boundary conditions (priority: Medium)
   - Error handling and negative scenarios (priority: Medium/Low)
6. Confidence score should reflect:
   - Completeness of requirements
   - Code quality and coverage
   - Complexity of functionality
   - Test scenario comprehensiveness

CRITICAL INSTRUCTIONS:
---------------------
- Return ONLY valid JSON, no markdown formatting, no code blocks
- Ensure all JSON is properly escaped
- Make test scenarios specific and actionable
- Use realistic effort estimates
- Confidence score should be 0-100

Generate the test plan now:
"""
        
        return prompt
    
    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse and validate Gemini response

        Args:
            response_text: Raw response from Gemini

        Returns:
            Parsed dictionary

        Raises:
            GeminiClientException: If parsing fails
        """
        try:
            # Remove markdown code blocks if present
            text = response_text.strip()

            if text.startswith('```'):
                # Remove opening ```json or ```
                text = text.split('\n', 1)[1] if '\n' in text else text[3:]

                # Remove closing ```
                if text.endswith('```'):
                    text = text.rsplit('```', 1)[0]

            # Find JSON boundaries
            json_start = text.find('{')
            json_end = text.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON object found in response")

            json_str = text[json_start:json_end]

            # Try to fix common JSON issues
            json_str = self._fix_common_json_issues(json_str)

            # Parse JSON
            plan_data = json.loads(json_str)
            
            # Validate required fields
            required_fields = [
                'strategy',
                'testable_components',
                'test_scenarios',
                'confidence_score'
            ]

            missing_fields = [field for field in required_fields if field not in plan_data]

            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

            # Set defaults for optional fields
            if 'coverage_targets' not in plan_data:
                logger.warning("coverage_targets not provided by AI, using defaults")
                plan_data['coverage_targets'] = {
                    'unit_tests': '80%',
                    'integration_tests': '70%',
                    'e2e_tests': '60%'
                }

            if 'traceability_matrix' not in plan_data:
                logger.warning("traceability_matrix not provided by AI, generating from test scenarios")
                # Generate traceability matrix from test scenarios
                traceability = {}
                for scenario in plan_data.get('test_scenarios', []):
                    scenario_id = scenario.get('id', 'unknown')
                    # Map to components based on scenario title/description
                    for component in plan_data.get('testable_components', []):
                        if component.lower() in scenario.get('title', '').lower():
                            if component not in traceability:
                                traceability[component] = []
                            traceability[component].append(scenario_id)
                plan_data['traceability_matrix'] = traceability if traceability else {'default': [s.get('id') for s in plan_data.get('test_scenarios', [])]}
            
            # Validate test scenarios structure
            if not isinstance(plan_data['test_scenarios'], list):
                raise ValueError("test_scenarios must be a list")
            
            for idx, scenario in enumerate(plan_data['test_scenarios']):
                required_scenario_fields = ['id', 'title', 'given', 'when', 'then', 'priority', 'test_type']
                missing = [f for f in required_scenario_fields if f not in scenario]
                
                if missing:
                    raise ValueError(f"Scenario {idx} missing fields: {', '.join(missing)}")
            
            # Validate confidence score range
            if not (0 <= plan_data['confidence_score'] <= 100):
                logger.warning(f"Confidence score {plan_data['confidence_score']} out of range, clamping to 0-100")
                plan_data['confidence_score'] = max(0, min(100, plan_data['confidence_score']))
            
            logger.info("Successfully parsed and validated Gemini response")
            return plan_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            logger.error(f"Failed to parse JSON at position {e.pos}")
            logger.debug(f"Response text (first 1000 chars): {response_text[:1000]}")

            # Save problematic response for debugging
            try:
                with open('.cache/last_failed_response.txt', 'w') as f:
                    f.write(response_text)
                logger.info("Saved failed response to .cache/last_failed_response.txt")
            except:
                pass

            raise GeminiClientException(f"Invalid JSON in Gemini response: {str(e)}")

        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            raise GeminiClientException(f"Response validation failed: {str(e)}")
    
    def _fix_common_json_issues(self, json_str: str) -> str:
        """
        Attempt to fix common JSON formatting issues

        Args:
            json_str: JSON string to fix

        Returns:
            Fixed JSON string
        """
        import re

        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

        # Fix incomplete strings (unmatched quotes at the end)
        # Check if there's an odd number of quotes after the last complete structure
        lines = json_str.split('\n')
        if lines:
            last_line = lines[-1].strip()
            # If last line has unclosed string (ends with quote or has incomplete array)
            if last_line.endswith('["') or last_line.endswith(', "') or re.search(r':\s*\["[^"]*$', last_line):
                logger.warning("Detected incomplete string/array at end, truncating")
                # Remove the incomplete last line
                json_str = '\n'.join(lines[:-1])

        # Count opening and closing brackets/braces
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')

        # Remove trailing commas and incomplete elements
        json_str = json_str.rstrip().rstrip(',').rstrip()

        # Close incomplete arrays first
        if open_brackets > close_brackets:
            missing_brackets = open_brackets - close_brackets
            logger.warning(f"Incomplete arrays detected: {open_brackets} opening, {close_brackets} closing brackets")
            json_str += ']' * missing_brackets
            logger.info(f"Added {missing_brackets} closing brackets")

        # Close incomplete objects
        if open_braces > close_braces:
            missing_braces = open_braces - close_braces
            logger.warning(f"Incomplete JSON detected: {open_braces} opening braces, {close_braces} closing braces")

            # Add default confidence_score if missing
            if '"confidence_score"' not in json_str:
                # Find the last complete field and add confidence_score before closing
                json_str = json_str.rstrip().rstrip(',')
                json_str += ',\n  "confidence_score": 85'

            json_str += '\n' + '}' * missing_braces
            logger.info(f"Added {missing_braces} closing braces to complete JSON")

        # Remove any trailing text after the final closing brace
        last_brace = json_str.rfind('}')
        if last_brace != -1 and last_brace < len(json_str) - 1:
            extra_text = json_str[last_brace + 1:].strip()
            if extra_text:
                logger.warning(f"Removing extra text after JSON: {extra_text[:50]}")
                json_str = json_str[:last_brace + 1]

        return json_str

    def generate(self, prompt: str) -> str:
        """
        Generic text generation method

        Args:
            prompt: Input prompt for generation

        Returns:
            Generated text response

        Raises:
            GeminiClientException: If generation fails
        """
        try:
            response = self.model.generate_content(prompt)

            if not response or not response.text:
                raise GeminiClientException("Empty response from Gemini")

            return response.text

        except Exception as e:
            raise GeminiClientException(f"Generation failed: {str(e)}")

    def analyze_test_failure(self, failure_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use Gemini to analyze test failures and suggest fixes
        (Future enhancement for test execution phase)

        Args:
            failure_details: Test failure information

        Returns:
            Analysis with suggestions
        """
        logger.info("Analyzing test failure with Gemini")

        prompt = f"""
Analyze this test failure and provide actionable insights:

{json.dumps(failure_details, indent=2)}

Provide:
1. Root cause analysis
2. Suggested fixes
3. Prevention strategies

Return as JSON with keys: root_cause, suggestions, prevention
"""

        try:
            response = self.model.generate_content(prompt)
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Failure analysis error: {str(e)}")
            return {
                "root_cause": "Analysis failed",
                "suggestions": [],
                "prevention": []
            }
