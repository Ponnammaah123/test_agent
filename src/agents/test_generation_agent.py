# ==============================================
# Test Generation Agent
# ==============================================

from typing import Dict, Any, Optional, List
from datetime import datetime
import hashlib
import json

from src.config.settings import Config
from src.clients.jira_client import JiraClient
from src.clients.gemini_client import GeminiClient
from src.clients.github_client import GitHubClient
from src.clients.test_repo_client import TestRepoClient

from src.models.test_plan_models import TestPlan
from src.models.github_models import CodebaseAnalysis
from src.models.jira_models import JiraTicket

from src.utils.logger import get_logger
from src.utils.exceptions import WorkflowException

# Import helper utilities (implemented in separate file)
from src.utils.test_generation_utils import (
    CacheManager, 
    ScopeDetector, 
    TestRepoAnalyzer, 
    TestFileNamingStrategy,
    LocatorExtractor
)

logger = get_logger(__name__)

class TestGenerationAgent:
    """
    Agent for generating E2E test cases with intelligent caching.
    Adapted for SlingShot QE Orchestrator.
    """

    def __init__(self, config: Config):
        """
        Initialize Test Generation Agent
        """
        self.config = config
        self.agent_name = "Test Generation Agent"
        
        # Initialize Clients
        self.jira_client = JiraClient(config)
        self.gemini_client = GeminiClient(config)
        
        # We use GitHubClient for the application repo
        self.github_client = GitHubClient(config)

        # Utilities
        self.cache_manager = CacheManager()
        self.naming_strategy = TestFileNamingStrategy()
        self.locator_extractor = LocatorExtractor()
        self.scope_detector = ScopeDetector()

        logger.info(f"{self.agent_name} initialized")

    async def generate_tests(
        self,
        jira_ticket_key: str,
        test_plan: TestPlan,
        codebase_analysis: CodebaseAnalysis,
        test_repo_url: str,
        scope_analysis: Optional[Dict[str, Any]] = None,
        dashboard_logger = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive E2E tests based on test plan
        """
        logger.info(f"Starting test generation for {jira_ticket_key}")

        try:
            # Step 0: Fetch Jira ticket
            logger.info("Fetching ticket hierarchy information from Jira")
            jira_ticket = self.jira_client.get_ticket(jira_ticket_key)
            logger.info(f"Ticket hierarchy: {jira_ticket.get_hierarchy_path()}")

            # Step 1: Analyze existing tests in repository
            logger.info("Analyzing existing tests in repository")
            test_repo_client = TestRepoClient(self.config, test_repo_url)
            test_repo_analyzer = TestRepoAnalyzer(test_repo_client)

            existing_analysis = test_repo_analyzer.analyze_existing_tests(jira_ticket_key)
            
            # Use or Detect Scope
            if not scope_analysis:
                logger.info("No scope analysis provided, detecting now...")
                scope_analysis = self.scope_detector.detect(jira_ticket)

            # Get update strategy
            update_strategy = test_repo_analyzer.suggest_update_strategy(
                existing_analysis['existing_test_files'],
                jira_ticket_key,
                scope_analysis
            )
            logger.info(f"Update strategy: {update_strategy['action']}")

            # Step 2: Extract locators from application code
            logger.info("Extracting locators from application code")
            # Using codebase_analysis to know which files to check
            extracted_locators = self.locator_extractor.extract_from_codebase(
                self.github_client,
                codebase_analysis
            )
            logger.info(f"Extracted {len(extracted_locators.get('data-testid', []))} locators")

            # Step 3: Parse code structure (with caching)
            logger.info("Parsing code structure")
            code_structure = self._parse_code_structure_cached(codebase_analysis)
            code_structure['locators'] = extracted_locators

            # Step 4: Identify coverage gaps
            logger.info("Identifying coverage gaps")
            coverage_gaps = self._identify_coverage_gaps(
                test_plan,
                code_structure,
                codebase_analysis,
                scope_analysis
            )

            # Step 5: Generate test cases
            logger.info("Generating test cases with AI")
            test_files = self._generate_test_files_with_scope(
                jira_ticket,
                test_plan,
                code_structure,
                coverage_gaps,
                scope_analysis,
                update_strategy,
                existing_analysis['existing_test_files']
            )

            # Step 6: Generate Page Object Models
            logger.info("Generating Page Object Models")
            page_objects = self._generate_page_objects(
                code_structure,
                codebase_analysis
            )

            # Step 7: Generate test configuration
            logger.info("Generating test configuration files")
            test_config = self._generate_test_configuration(codebase_analysis)

            result = {
                'jira_ticket_key': jira_ticket_key,
                'test_files': test_files,
                'page_objects': page_objects,
                'test_config': test_config,
                'coverage_gaps': coverage_gaps,
                'scope_analysis': scope_analysis,
                'existing_analysis': existing_analysis,
                'update_strategy': update_strategy,
                'generated_at': datetime.now().isoformat(),
                'test_repo_url': test_repo_url
            }

            logger.info(f"Generation completed: {len(test_files)} test files, {len(page_objects)} page objects")
            return result

        except Exception as e:
            logger.error(f"Test generation failed: {str(e)}", exc_info=True)
            raise WorkflowException(f"Failed to generate tests: {str(e)}")

    def _parse_code_structure_cached(self, codebase_analysis: CodebaseAnalysis) -> Dict[str, Any]:
        """Parse code structure with intelligent caching"""
        cache_key = self._generate_cache_key(
            codebase_analysis.repository,
            codebase_analysis.branch,
            codebase_analysis.last_commit_date
        )

        cached_structure = self.cache_manager.get(cache_key)
        if cached_structure:
            logger.info("Using cached code structure")
            return cached_structure

        code_structure = self._parse_code_structure(codebase_analysis)
        self.cache_manager.set(cache_key, code_structure, ttl=86400)
        return code_structure

    def _generate_cache_key(self, repository: str, branch: str, commit_date: Optional[str]) -> str:
        key_data = f"{repository}:{branch}:{commit_date or 'latest'}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def _parse_code_structure(self, codebase_analysis: CodebaseAnalysis) -> Dict[str, Any]:
        """Parse code structure using Gemini"""
        prompt = f"""
        Analyze the following codebase for E2E test generation:
        Repository: {codebase_analysis.repository}
        Branch: {codebase_analysis.branch}
        Components: {', '.join(codebase_analysis.components_identified)}
        Files Changed: {', '.join(codebase_analysis.files_changed)}
        
        Extract: components, routes, api_endpoints, workflows.
        Return JSON.
        """
        # NOTE: Real implementation would pass more context. 
        # Using simplified generation call here.
        try:
            response = self.gemini_client.generate(prompt)
            # Basic cleanup
            text = response.replace('```json', '').replace('```', '').strip()
            if '{' in text:
                text = text[text.find('{'):text.rfind('}')+1]
            return json.loads(text)
        except Exception as e:
            logger.warning(f"Failed to parse code structure: {e}")
            return {"components": [], "routes": [], "workflows": []}

    def _identify_coverage_gaps(self, test_plan, code_structure, codebase_analysis, scope_analysis) -> List[Dict[str, Any]]:
        """Identify gaps logic"""
        gaps = []
        # Simplified gap logic
        if codebase_analysis.test_coverage < 80:
            gaps.append({'type': 'coverage', 'reason': 'Low coverage'})
        return gaps

    def _generate_test_files_with_scope(
        self, jira_ticket, test_plan, code_structure, coverage_gaps, scope_analysis, update_strategy, existing_files
    ) -> Dict[str, str]:
        """Generate test files mapping"""
        test_files = {}
        
        # 1. Generate core scenarios
        for scenario in test_plan.test_scenarios:
            # Logic to generate single scenario file or grouped
            # For integration, we use a simplified generator
            file_path = self.naming_strategy.generate_test_file_path(
                ticket=jira_ticket, category=scenario.get('test_type', 'e2e'), test_type='e2e'
            )
            file_path = self.naming_strategy.generate_unique_filename(file_path, existing_files + list(test_files.keys()))
            
            content = self._generate_playwright_content(scenario, code_structure)
            test_files[file_path] = content
            
        return test_files

    def _generate_playwright_content(self, scenario, code_structure) -> str:
        """Generate content for a single test file"""
        # Prompt Gemini for code
        prompt = f"Generate Playwright test for scenario: {scenario.get('title')}. Context: {json.dumps(code_structure.get('locators', {}))}"
        try:
            return self.gemini_client.generate(prompt)
        except:
            return "// Failed to generate code"

    def _generate_page_objects(self, code_structure, codebase_analysis) -> Dict[str, str]:
        """Generate POMs"""
        # Simplified implementation
        return {"tests/pages/base.page.ts": "// Base page object"}

    def _generate_test_configuration(self, codebase_analysis) -> Dict[str, str]:
        """Generate Configs"""
        return {
            "playwright.config.ts": "// Config",
            "package.json": "{}"
        }