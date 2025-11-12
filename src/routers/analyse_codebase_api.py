from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.auth.authentication import authenticate_user

class FileChange(BaseModel):
    """Model for individual file changes"""
    path: str = Field(..., description="File path")
    status: str = Field(..., description="Change status (added, modified, deleted)")
    additions: int = Field(0, description="Lines added")
    deletions: int = Field(0, description="Lines deleted")


class RepositoryConfig(BaseModel):
    """Model for repository configuration"""
    test_environment_url: Optional[str] = Field(None, description="Test environment URL")
    api_base_url: Optional[str] = Field(None, description="API base URL")


class CodebaseAnalysisResponse(BaseModel):
    """Model for codebase analysis response data"""
    repository: str = Field(..., description="Repository name")
    branch: str = Field(..., description="Branch name")
    files_changed: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of changed files with categorization and impact"
    )
    components_identified: List[str] = Field(
        default_factory=list,
        description="Identified components"
    )
    test_coverage: float = Field(0.0, description="Test coverage percentage")
    repository_config: Optional[RepositoryConfig] = Field(
        None,
        description="Repository configuration"
    )


class AnalyzeCodebaseRequest(BaseModel):
    """Request model for codebase analysis"""
    jira_ticket_key: str = Field(..., description="Jira ticket key (e.g., TP-1)")
    branch: str = Field(..., description="Git branch to analyse")

class AnalyzeCodebaseResponse(BaseModel):
    """Response model for codebase analysis"""
    status: str = Field(..., description="Response status (success or error)")
    message: str = Field(..., description="Response message")
    analysis: Optional[CodebaseAnalysisResponse] = Field(
        None,
        description="Analysis details"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of errors if any"
    )

class SimpleLogger:
    """Simple logger for when actual logger is not available"""
    def info(self, msg: str, extra: Dict = None):
        print(f"[INFO] {msg}")
        if extra:
            print(f"       {extra}")
    
    def warning(self, msg: str):
        print(f"[WARNING] {msg}")
    
    def error(self, msg: str, exc_info: bool = False):
        print(f"[ERROR] {msg}")


try:
    from src.utils.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = SimpleLogger()

try:
    from src.utils.exceptions import GitHubClientException
except ImportError:
    class GitHubClientException(Exception):
        pass

# Import your existing GitHub client (works with GitHub, GitLab, etc.)
try:
    from src.clients.github_client import GitHubClient
except ImportError:
    logger.error("Could not import GitHubClient from src.clients.github_client")
    raise

try:
    from src.config.settings import Config
    config = Config()
except ImportError:
    config = None


# ============================================================================
# FILE CHANGE ANALYSIS CLASS
# ============================================================================

class FileChangeAnalysis:
    """Helper class to analyze file changes"""
    
    BACKEND_EXTENSIONS = {'.py', '.java', '.go', '.rb', '.php', '.js', '.ts', '.kotlin', '.scala', '.cpp', '.c', '.h'}
    FRONTEND_EXTENSIONS = {'.jsx', '.tsx', '.vue', '.css', '.scss', '.html', '.xml'}
    DATABASE_EXTENSIONS = {'.sql', '.migration', '.sqlf', '.db'}
    CONFIG_EXTENSIONS = {'.yaml', '.yml', '.json', '.toml', '.cfg', '.conf', '.xml', '.env', '.properties'}
    
    @staticmethod
    def categorize_file(filename: str) -> str:
        """Categorize file based on extension and path"""
        filename_lower = filename.lower()
        
        # Test files
        if any(test in filename_lower for test in ['test', 'spec', '_test', '.test']):
            return 'tests'
        
        # Frontend
        if any(filename_lower.endswith(ext) for ext in FileChangeAnalysis.FRONTEND_EXTENSIONS):
            return 'frontend'
        
        # Database
        if any(filename_lower.endswith(ext) for ext in FileChangeAnalysis.DATABASE_EXTENSIONS):
            return 'database'
        
        # Configuration
        if any(filename_lower.endswith(ext) for ext in FileChangeAnalysis.CONFIG_EXTENSIONS):
            if any(x in filename_lower for x in ['docker', 'k8s', 'infra', 'terraform']):
                return 'infrastructure'
            return 'configuration'
        
        # Backend (default for code files)
        if any(filename_lower.endswith(ext) for ext in FileChangeAnalysis.BACKEND_EXTENSIONS):
            return 'backend'
        
        # Documentation
        if any(ext in filename_lower for ext in ['.md', '.txt', '.rst', '.adoc']):
            return 'documentation'
        
        return 'other'
    
    @staticmethod
    def calculate_impact_level(additions: int, deletions: int) -> str:
        """Calculate impact level based on line changes"""
        total_changes = additions + deletions
        if total_changes < 10:
            return 'low'
        elif total_changes < 50:
            return 'medium'
        elif total_changes < 200:
            return 'high'
        else:
            return 'critical'


# ============================================================================
# ROUTER
# ============================================================================

router = APIRouter()

#@router.post("/analyze-codebase", response_model=AnalyzeCodebaseResponse, dependencies=[Depends(authenticate_user)])
@router.post("/analyze-codebase", response_model=AnalyzeCodebaseResponse)
async def analyze_codebase_route(request: AnalyzeCodebaseRequest) -> AnalyzeCodebaseResponse:
    """
    Analyze codebase for a Jira ticket
    
    Works with: GitHub, GitLab, or any Git service
    Uses your existing GitHubClient from src.clients.github_client
    
    Enhanced with:
    - File categorization (8 types)
    - Impact assessment (4 levels)
    - Comprehensive metrics
    - Better logging
    """

    logger.info(f"Starting codebase analysis for ticket: {request.jira_ticket_key}")

    try:
        # Step 1: Initialize GitHub client (works with your Git service)
        logger.info(f"[1/5] Initializing GitHub client")
        github_client = GitHubClient(config)
        
        # Step 2: Get initial analysis from your existing client
        logger.info(f"[2/5] Fetching repository analysis")
        analysis = github_client.analyze_codebase(request.branch)
        logger.info(f"Analysis result: repository={analysis.repository}, branch={analysis.branch}, files={len(analysis.files_changed or [])}")
        
        if not analysis:
            raise ValueError("No analysis data returned from GitHub client")

        # Step 3: Enhance file analysis with categorization and impact
        logger.info(f"[3/5] Analyzing file changes and calculating impact")
        
        files_by_category = {
            'backend': [],
            'frontend': [],
            'database': [],
            'tests': [],
            'infrastructure': [],
            'configuration': [],
            'documentation': [],
            'other': []
        }
        
        total_additions = 0
        total_deletions = 0
        file_impacts = []
        
        if analysis.files_changed:
            for file in analysis.files_changed:
                # Handle both dict and object formats
                # github_client returns dicts, so access with file['key']
                file_path = file['path'] if isinstance(file, dict) else file.path
                file_status = file['status'] if isinstance(file, dict) else file.status
                file_additions = file['additions'] if isinstance(file, dict) else file.additions
                file_deletions = file['deletions'] if isinstance(file, dict) else file.deletions
                
                # Categorize file
                category = FileChangeAnalysis.categorize_file(file_path)
                files_by_category[category].append({
                    "path": file_path,
                    "status": file_status,
                    "additions": file_additions,
                    "deletions": file_deletions
                })
                
                # Calculate metrics
                total_additions += file_additions
                total_deletions += file_deletions
                
                # Calculate impact
                impact_level = FileChangeAnalysis.calculate_impact_level(
                    file_additions, 
                    file_deletions
                )
                
                file_impacts.append({
                    "path": file_path,
                    "category": category,
                    "status": file_status,
                    "impact": impact_level,
                    "changes": file_additions + file_deletions
                })
        
        logger.info(f"Total files changed: {len(analysis.files_changed) if analysis.files_changed else 0}")
        logger.info(f"Total additions: {total_additions:,} lines")
        logger.info(f"Total deletions: {total_deletions:,} lines")
        
        # Step 4: Identify high-impact areas
        logger.info(f"[4/5] Identifying high-impact components")
        
        high_impact_files = [f for f in file_impacts if f['impact'] in ['high', 'critical']]
        critical_categories = set(f['category'] for f in high_impact_files)
        
        if high_impact_files:
            logger.info(f"High-impact files identified: {len(high_impact_files)}")
            if critical_categories:
                logger.info(f"Critical categories: {', '.join(critical_categories)}")
        
        # Step 5: Build comprehensive analysis response
        logger.info(f"[5/5] Building analysis response")
        
        # Prepare component metrics
        components_identified = analysis.components_identified or []
        category_counts = {
            'backend': len(files_by_category['backend']),
            'frontend': len(files_by_category['frontend']),
            'database': len(files_by_category['database']),
            'tests': len(files_by_category['tests']),
            'infrastructure': len(files_by_category['infrastructure']),
            'configuration': len(files_by_category['configuration']),
            'documentation': len(files_by_category['documentation']),
            'other': len(files_by_category['other'])
        }
        
        # Build detailed files list with categorization
        files_changed_detailed = []
        for file in analysis.files_changed or []:
            # Handle both dict and object formats
            file_path = file['path'] if isinstance(file, dict) else file.path
            file_status = file['status'] if isinstance(file, dict) else file.status
            file_additions = file['additions'] if isinstance(file, dict) else file.additions
            file_deletions = file['deletions'] if isinstance(file, dict) else file.deletions
            
            category = FileChangeAnalysis.categorize_file(file_path)
            impact = FileChangeAnalysis.calculate_impact_level(file_additions, file_deletions)
            
            files_changed_detailed.append({
                "path": file_path,
                "status": file_status,
                "additions": file_additions,
                "deletions": file_deletions,
                "category": category,
                "impact": impact,
                "total_changes": file_additions + file_deletions
            })
        
        # Calculate overall impact
        overall_impact = "critical" if len(high_impact_files) > 5 else \
                        "high" if len(high_impact_files) > 0 else \
                        "medium" if total_additions + total_deletions > 100 else "low"
        
        # Build final analysis dictionary
        analysis_dict = {
            "repository": analysis.repository,
            "branch": analysis.branch,
            "files_changed": files_changed_detailed,
            "components_identified": components_identified,
            "test_coverage": analysis.test_coverage or 0.0,
            "repository_config": {
                "test_environment_url": analysis.repository_config.test_environment_url if analysis.repository_config else None,
                "api_base_url": analysis.repository_config.api_base_url if analysis.repository_config else None
            } if analysis.repository_config else None
        }
        
        response = AnalyzeCodebaseResponse(
            status="success",
            message="Codebase analysis completed successfully",
            analysis=CodebaseAnalysisResponse(**analysis_dict),
            errors=[]
        )

        # Log comprehensive summary
        logger.info(
            f" Analysis response prepared",
            extra={
                'files_changed': len(files_changed_detailed),
                'total_additions': total_additions,
                'total_deletions': total_deletions,
                'components': len(components_identified),
                'test_coverage': f"{analysis.test_coverage:.1f}%" if analysis.test_coverage else "N/A",
                'overall_impact': overall_impact,
                'high_impact_files': len(high_impact_files)
            }
        )
        
        logger.info(f"  Analysis Summary:")
        logger.info(f"  Repository: {analysis.repository}")
        logger.info(f"  Branch: {analysis.branch}")
        logger.info(f"  Files Changed: {len(files_changed_detailed)}")
        logger.info(f"  Code Changes: +{total_additions} -{total_deletions} lines")
        logger.info(f"  Components: {len(components_identified)}")
        if analysis.test_coverage:
            logger.info(f"  Test Coverage: {analysis.test_coverage:.1f}%")
        logger.info(f"  Overall Impact: {overall_impact.upper()}")
        logger.info(f"\n  Category Breakdown:")
        for category, count in category_counts.items():
            if count > 0:
                logger.info(f"    • {category.capitalize()}: {count} files")

        return response

    except GitHubClientException as e:
        error_msg = f"GitHub client error: {str(e)}"
        logger.error(f"✗ {error_msg}")

        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": "Failed to analyze codebase",
                "error": str(e),
                "error_type": "github_client_error"
            }
        )

    except ValueError as e:
        error_msg = f"Validation error: {str(e)}"
        logger.error(f"✗ {error_msg}")
        
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "message": "Invalid analysis data",
                "error": str(e),
                "error_type": "validation_error"
            }
        )

    except Exception as e:
        error_msg = f"Unexpected error during codebase analysis: {str(e)}"
        logger.error(f"✗ {error_msg}")
        logger.error(f"  Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"  Traceback: {traceback.format_exc()}")

        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An unexpected error occurred during codebase analysis",
                "error": str(e),
                "exception_type": type(e).__name__
            }
        )