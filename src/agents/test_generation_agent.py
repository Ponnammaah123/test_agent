# ==============================================
# Test Generation Agent
# ==============================================

from typing import Dict, Any, Optional, List
from datetime import datetime
import hashlib
import json
import os
import re

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

# Import helper utilities
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

            # Step 2: Extract locators (Legacy step - kept for logging/metrics but not used for generation)
            logger.info("Extracting locators metadata...")
            extracted_locators = self.locator_extractor.extract_from_codebase(
                self.github_client,
                codebase_analysis
            )

            # Step 3: Parse code structure (Cached)
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
                existing_analysis['existing_test_files'],
                codebase_analysis # Passing the full analysis to get file paths
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

            logger.info(f"Generation completed: {len(test_files)} test files")
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
            return cached_structure

        code_structure = self._parse_code_structure(codebase_analysis)
        self.cache_manager.set(cache_key, code_structure, ttl=86400)
        return code_structure

    def _generate_cache_key(self, repository: str, branch: str, commit_date: Optional[str]) -> str:
        key_data = f"{repository}:{branch}:{commit_date or 'latest'}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def _parse_code_structure(self, codebase_analysis: CodebaseAnalysis) -> Dict[str, Any]:
        """Parse code structure using Gemini (Metadata only)"""
        # This method is kept for metadata structure but not for raw generation context
        file_paths = []
        if isinstance(codebase_analysis.files_changed, list):
            for file_item in codebase_analysis.files_changed:
                if isinstance(file_item, dict) and 'path' in file_item:
                    file_paths.append(file_item['path'])
                elif isinstance(file_item, str):
                    file_paths.append(file_item)
        
        files_changed_count = len(file_paths)
        key_files_str = ', '.join(file_paths[:10])

        prompt = f"""
        Analyze the following codebase metadata for E2E test generation:
        Repository: {codebase_analysis.repository}
        Branch: {codebase_analysis.branch}
        Components: {', '.join(codebase_analysis.components_identified)}
        
        Files Changed: {files_changed_count} files
        Key Files: {key_files_str}
        
        Extract: components, routes, api_endpoints.
        Return JSON.
        """
        try:
            response = self.gemini_client.generate(prompt)
            text = response.replace('```json', '').replace('```', '').strip()
            if '{' in text:
                text = text[text.find('{'):text.rfind('}')+1]
            return json.loads(text)
        except Exception as e:
            logger.warning(f"Failed to parse code structure: {e}")
            return {"components": [], "routes": []}

    def _identify_coverage_gaps(self, test_plan, code_structure, codebase_analysis, scope_analysis) -> List[Dict[str, Any]]:
        """Identify gaps logic"""
        gaps = []
        if codebase_analysis.test_coverage < 80:
            gaps.append({'type': 'coverage', 'reason': 'Low coverage'})
        return gaps

    def _generate_test_files_with_scope(
        self, 
        jira_ticket: JiraTicket, 
        test_plan: TestPlan, 
        code_structure: Dict[str, Any], 
        coverage_gaps: List[Dict[str, Any]], 
        scope_analysis: Optional[Dict[str, Any]], 
        update_strategy: Dict[str, str], 
        existing_files: List[str],
        codebase_analysis: CodebaseAnalysis
    ) -> Dict[str, str]:
        """Generate test files mapping, skipping duplicates and using FULL source context."""
        test_files = {}

        # 1. Duplicate Detection Logic
        logger.info(f"Checking {len(existing_files)} existing files for duplicates...")
        existing_scenario_ids = set()
        for file_path in existing_files:
            try:
                filename = os.path.basename(file_path)
                scenario_id = filename.split('.')[0]
                if re.match(r".*-\d+$", scenario_id):
                    scenario_id = scenario_id.rsplit('-', 1)[0]
                if scenario_id:
                    existing_scenario_ids.add(scenario_id.lower())
            except Exception as e:
                logger.warning(f"Could not parse scenario ID from filename {file_path}: {e}")

        # 2. Fetch FULL Source Code Content
        source_code_context = {}
        logger.info("Gathering REAL source code content for AI context...")
        
        if codebase_analysis and codebase_analysis.files_changed:
            for file_info in codebase_analysis.files_changed:
                try:
                    file_path = file_info['path'] if isinstance(file_info, dict) else file_info.path
                    
                    if file_path.endswith(('.js', '.jsx', '.ts', '.tsx', '.vue', '.html', '.css', '.scss')):
                        content = self.github_client.get_cached_file_content(
                            branch=codebase_analysis.branch,
                            file_path=file_path
                        )
                        if content:
                            source_code_context[file_path] = content
                            logger.info(f"  -> Added source context: {file_path}")
                except Exception as e:
                     logger.warning(f"Could not get content for {file_path}: {e}")
        
        if not source_code_context:
            logger.warning("⚠️ No UI source code content found! Tests may use guessed locators.")

        # 3. Generate Code for Scenarios
        scenarios_generated = 0
        scenarios_skipped = 0
        
        for scenario in test_plan.test_scenarios:
            scenario_id_str = str(scenario.get('id', '')).lower()

            if scenario_id_str in existing_scenario_ids:
                logger.warning(f"Skipping scenario {scenario_id_str}: Test file already exists.")
                scenarios_skipped += 1
                continue
            
            file_path = self.naming_strategy.generate_test_file_path(
                ticket=jira_ticket, 
                scenario=scenario,
                test_type=scenario.get('test_type', 'e2e')
            )
            
            file_path = self.naming_strategy.generate_unique_filename(
                file_path, 
                existing_files + list(test_files.keys())
            )
            
            content = self._generate_playwright_content(scenario, source_code_context)
            test_files[file_path] = content
            scenarios_generated += 1
        
        logger.info(f"Test generation complete. Generated: {scenarios_generated} new files. Skipped: {scenarios_skipped} duplicates.")
        return test_files

    def _generate_playwright_content(
        self, 
        scenario: Dict[str, Any], 
        source_code_context: Dict[str, str]
    ) -> str:
        """Generate content using the full file context to find real locators."""
        
        # Prepare the context string
        code_context_str = ""
        if source_code_context:
            code_context_str = "\n\n=== RELEVANT APPLICATION SOURCE CODE ===\n"
            for file_path, content in source_code_context.items():
                truncated_content = content[:8000] 
                code_context_str += f"\n--- File: {file_path} ---\n{truncated_content}\n"
            code_context_str += "\n=== END SOURCE CODE ===\n"
        else:
            code_context_str = "\n(No source code context available. Use generic, robust locators.)\n"
        
        # Fixed F-String Syntax: Doubled curly braces {{ }} for literal use
        prompt = f"""
        You are an expert Playwright automation engineer.
        
        **TASK:**
        Write a complete, runnable Playwright test script (`.spec.ts`) for the following scenario.
        
        **SCENARIO:**
        - ID: {scenario.get('id')}
        - Title: {scenario.get('title')}
        - Given: {scenario.get('given')}
        - When: {scenario.get('when')}
        - Then: {scenario.get('then')}
        
        **CRITICAL INSTRUCTIONS FOR LOCATORS:**
        1.  **ANALYZE** the provided "RELEVANT APPLICATION SOURCE CODE" section below.
        2.  **FIND** the *actual* elements described in the scenario within that code.
        3.  **EXTRACT** the real locators used in the code.
            - **Priority 1:** `data-testid` (e.g., `page.locator('[data-testid="submit-btn"]')`) - ONLY if seen in source.
            - **Priority 2:** `id` (e.g., `page.locator('#main-nav')`) - ONLY if seen in source.
            - **Priority 3:** Accessible Roles (e.g., `page.getByRole('button', {{ name: 'Save' }})`).  <-- FIXED
            - **Priority 4:** Text content (e.g., `page.getByText('Welcome')`) - If text is visible in source.
            - **Priority 5:** CSS Classes (e.g., `page.locator('.login-form')`) - ONLY if seen in source.
        4.  **DO NOT** invent or guess `data-testid` or `id` attributes if they are not in the source code.
        5.  **DO NOT** use placeholders like `YOUR_URL`, `#your-id`, or `[data-testid="placeholder"]`.
        6.  If the specific element is not found in the source code provided, fallback to robust, generic locators (like `getByRole` or `getByText`) and add a comment: `// NOTE: Exact locator not found in provided source context`.
        
        {code_context_str}
        
        **OUTPUT FORMAT:**
        Return ONLY the TypeScript code. Start with `import {{ test, expect }}`.
        """
        
        try:
            return self.gemini_client.generate(prompt)
        except Exception as e:
            logger.error(f"Failed to generate code for scenario {scenario.get('id')}: {e}")
            return f"// Error generating test code: {e}"

    def _generate_page_objects(self, code_structure, codebase_analysis) -> Dict[str, str]:
        """Generate POMs (Placeholder implementation)"""
        return {"tests/pages/base.page.ts": "// Base page object structure"}

    def _generate_test_configuration(self, codebase_analysis) -> Dict[str, str]:
        """Generate Configs"""
        return {
            "playwright.config.ts": "// Playwright configuration",
            "package.json": "{}"
        }