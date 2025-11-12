"""
Enhanced GitHub Client with Integrated Caching System

Features:
- Fetches file content and diffs from GitHub/GitLab
- Caches all content with automatic TTL and LRU eviction
- Provides fast retrieval of cached content by repository:branch
- Supports searching and filtering cached files
- Full statistics and management capabilities
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import requests
from typing import List, Optional, Dict, Any, Tuple
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.config.settings import Config
import hashlib
import base64

# Import caching system
from src.clients.github_client_cache import (
    GitHubClientCache,
    CachedFile,
    get_cache
)

try:
    from src.routers.analyse_codebase_api import FileChange, CodebaseAnalysisResponse, RepositoryConfig
except ImportError:
    from pydantic import BaseModel, Field
    
    class FileChange(BaseModel):
        path: str = Field(..., description="File path")
        status: str = Field(..., description="Change status (added, modified, deleted)")
        additions: int = Field(0, description="Lines added")
        deletions: int = Field(0, description="Lines deleted")

    class RepositoryConfig(BaseModel):
        test_environment_url: Optional[str] = Field(None)
        api_base_url: Optional[str] = Field(None)

    class CodebaseAnalysisResponse(BaseModel):
        repository: str
        branch: str
        files_changed: List[dict]
        components_identified: List[str]
        test_coverage: float
        repository_config: Optional[RepositoryConfig]

# Configure logging
logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for interacting with Git services (GitHub, GitLab, etc.) with caching"""
    
    def __init__(self, config: Config, enable_cache: bool = True, cache_ttl: int = 3600):
        """
        Initialize Git client with caching
        
        Args:
            config: Configuration object with GITHUB_REPO and GITHUB_TOKEN
            enable_cache: Whether to enable caching (default: True)
            cache_ttl: Cache TTL in seconds (default: 3600 = 1 hour)
        """
        self.config = config
        self.enable_cache = enable_cache
        
        # Get repo URL from config
        try:
            self.repo_url = config.github.repo
        except Exception as e:
            logger.warning(f"Could not get repo from config.github.repo: {e}")
            self.repo_url = getattr(config, 'GITHUB_REPO', None)
        
        if not self.repo_url:
            raise ValueError("GITHUB_REPO not configured")
        
        # Get token from config
        try:
            self.pat_token = config.github.token
        except Exception as e:
            logger.warning(f"Could not get token from config.github.token: {e}")
            self.pat_token = getattr(config, 'GITHUB_TOKEN', None)
        
        if not self.pat_token:
            raise ValueError("GITHUB_TOKEN not configured")
        
        # Parse repository information
        self._parse_repo_url()
        
        # Detect Git service type
        self.git_service = self._detect_git_service()
        
        # Initialize cache
        self.cache = get_cache() if enable_cache else None
        
        # Create session with retry logic
        self.session = self._create_session_with_retries()
        
        logger.info(f"GitHubClient initialized for: {self.owner}/{self.repo} ({self.git_service})")
        if self.cache:
            logger.info(f"✅ Caching ENABLED - TTL: {cache_ttl}s")
    
    def _create_session_with_retries(self):
        """Create a requests session with retry logic"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        logger.info(" Session with retry logic ")
        return session
    
    def _detect_git_service(self) -> str:
        """Detect which Git service is being used"""
        if "github.com" in self.repo_url.lower():
            return "github"
        elif "gitlab" in self.repo_url.lower():
            return "gitlab"
        elif "gitea" in self.repo_url.lower():
            return "gitea"
        else:
            return "gitlab"  # Default to GitLab for self-hosted
    
    def _parse_repo_url(self):
        """Parse repository URL to extract owner and repo name"""
        try:
            url = self.repo_url.rstrip("/")
            if url.endswith(".git"):
                url = url[:-4]
            
            parts = url.split("/")
            
            if len(parts) >= 2:
                self.repo = parts[-1]
                self.owner = parts[-2]
            else:
                raise ValueError(f"Could not parse Git URL: {self.repo_url}")
            
            logger.info(f"Parsed Git repo: {self.owner}/{self.repo}")
            
        except Exception as e:
            logger.error(f"Failed to parse repo URL: {str(e)}")
            raise
    
    def analyze_codebase(self, branch: str) -> CodebaseAnalysisResponse:
        """
        Analyze codebase for a given branch with caching
        
        Args:
            branch: Git branch name (e.g., "main", "feature/TP-1")
        
        Returns:
            CodebaseAnalysisResponse with analysis results
        """
        logger.info(f"Analyzing codebase for branch: {branch}")
        
        try:
            # CHECK CACHE FIRST
            if self.cache:
                cached_analysis = self.cache.get_analysis(self.repo, branch)
                if cached_analysis:
                    logger.info(f"✅ Cache HIT: {self.repo}:{branch}")
                    return self._build_response_from_cache(cached_analysis)
                else:
                    logger.info(f"Cache MISS: {self.repo}:{branch}")
            
            # Step 1: Get files changed from Git
            logger.info("Step 1: Getting files changed")
            files_changed = self._get_files_changed(branch)
            # can get all files from a branch
            logger.info(f"  ✓ Found {len(files_changed)} changed files")
            
            # Step 2: Fetch file content and diffs
            logger.info("Step 2: Fetching file content and diffs")
            cached_files = self._enrich_files_with_content(files_changed, branch)
            logger.info(f"  ✓ Enriched {len(cached_files)} files with content/diffs")
            
            # Step 3: Analyze components
            logger.info("Step 3: Analyzing components")
            components = self._analyze_components(files_changed)
            logger.info(f"  ✓ Identified {len(components)} components")
            
            # Step 4: Get test coverage
            logger.info("Step 4: Getting test coverage")
            test_coverage = self._get_test_coverage()
            logger.info(f"  ✓ Test coverage: {test_coverage}%")
            
            # Step 5: Cache results
            if self.cache:
                logger.info("Step 5: Caching analysis results")
                latest_commit = self._get_latest_commit_id(branch)
                self.cache.set_analysis(
                    repository=self.repo,
                    branch=branch,
                    commit_id=latest_commit,
                    files=cached_files,
                    components=components,
                    test_coverage=test_coverage
                )
                cache_stats = self.cache.get_stats()
                logger.info(f"  ✓ Cache size: {cache_stats['total_content_size_mb']:.2f}MB / {cache_stats['max_content_size_mb']}MB")
                logger.info(f"  ✓ Hit rate: {cache_stats['hit_rate_percent']}")
            
            # Step 6: Build response
            logger.info("Step 6: Building response")
            response = CodebaseAnalysisResponse(
                repository=self.repo,
                branch=branch,
                files_changed=[
                    {
                        "path": f.path,
                        "status": f.status,
                        "additions": f.additions,
                        "deletions": f.deletions,
                        "language": f.language,
                        "extension": f.extension,
                        "file_size_bytes": f.file_size_bytes,
                        "has_content": f.content is not None,
                        "has_diff": f.diff is not None
                    } for f in cached_files
                ],
                components_identified=components,
                test_coverage=test_coverage,
                repository_config=RepositoryConfig(
                    test_environment_url="https://test.example.com",
                    api_base_url="https://api.example.com"
                )
            )
            
            logger.info("✓ Codebase analysis completed successfully")
            return response
            
        except Exception as e:
            logger.error(f"Error during codebase analysis: {str(e)}", exc_info=True)
            raise
    
    def _get_files_changed(self, branch: str) -> List[FileChange]:
        """Get files changed in a branch"""
        try:
            if self.git_service == "github":
                return self._get_files_changed_github(branch)
            else:
                return self._get_files_changed_gitlab(branch)
        except Exception as e:
            logger.error(f"Error getting files changed: {str(e)}")
            return []
    
    def _get_files_changed_github(self, branch: str) -> List[FileChange]:
        """Get files changed from GitHub API"""
        try:
            headers = {"Authorization": f"token {self.pat_token}"}
            
            logger.info(f" Fetching commits from GitHub for branch: {branch}")
            
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/commits"
            response = self.session.get(
                url,
                params={"sha": branch, "per_page": 1},
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            commits = response.json()
            
            if not commits:
                logger.warning(f" No commits found on branch {branch}")
                return []
            
            latest_commit_sha = commits[0]['sha']
            logger.info(f" Latest commit: {latest_commit_sha}")
            
            commit_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/commits/{latest_commit_sha}"
            commit_response = self.session.get(commit_url, headers=headers, timeout=30)
            commit_response.raise_for_status()
            commit = commit_response.json()
            
            files_changed = []
            for file in commit.get('files', []):
                files_changed.append(FileChange(
                    path=file['filename'],
                    status=file['status'],
                    additions=file.get('additions', 0),
                    deletions=file.get('deletions', 0)
                ))
            
            logger.info(f"✅ GitHub: Found {len(files_changed)} files")
            return files_changed
            
        except Exception as e:
            logger.error(f"❌ Error getting files from GitHub: {str(e)}")
            return []
    
    def _get_files_changed_gitlab(self, branch: str) -> List[FileChange]:
        """Get files changed from GitLab API"""
        try:
            headers = {"PRIVATE-TOKEN": self.pat_token}
            project_id = f"{self.owner}%2F{self.repo}"
            
            logger.info(f" Fetching commits from GitLab for branch: {branch}")
            
            url = f"https://pscode.lioncloud.net/api/v4/projects/{project_id}/repository/commits"
            response = self.session.get(
                url,
                params={"ref_name": branch, "per_page": 1},
                headers=headers,
                timeout=60
            )
            response.raise_for_status()
            commits = response.json()
            
            if not commits:
                logger.warning(f" No commits found on branch {branch}")
                return []
            
            latest_commit_id = commits[0]['id']
            logger.info(f" Latest commit ID: {latest_commit_id}")
            
            commit_url = f"https://pscode.lioncloud.net/api/v4/projects/{project_id}/repository/commits/{latest_commit_id}/diff"
            commit_response = self.session.get(commit_url, headers=headers, timeout=60)
            commit_response.raise_for_status()
            diffs = commit_response.json()
            
            files_changed = []
            for diff in diffs:
                if diff.get('new_file'):
                    status = 'added'
                elif diff.get('deleted_file'):
                    status = 'deleted'
                else:
                    status = 'modified'
                
                file_path = diff['new_path'] or diff['old_path']
                additions = self._count_additions(diff.get('diff', ''))
                deletions = self._count_deletions(diff.get('diff', ''))
                
                files_changed.append(FileChange(
                    path=file_path,
                    status=status,
                    additions=additions,
                    deletions=deletions
                ))
            
            logger.info(f" GitLab: Found {len(files_changed)} files")
            return files_changed
            
        except Exception as e:
            logger.error(f" Error getting files from GitLab: {str(e)}")
            return []
    
    def _enrich_files_with_content(
        self,
        files_changed: List[FileChange],
        branch: str
    ) -> List[CachedFile]:
        """
        Enrich file list with actual content and diffs
        
        Args:
            files_changed: List of FileChange objects
            branch: Branch name
        
        Returns:
            List of CachedFile objects with content/diffs
        """
        cached_files = []
        
        for file_change in files_changed:
            try:
                # Get current content
                content = self._get_file_content(file_change.path, branch)
                
                # Get original content for modified files
                original_content = None
                if file_change.status == 'modified' and content:
                    try:
                        original_content = self._get_file_content_at_parent(file_change.path, branch)
                    except Exception as e:
                        logger.debug(f"Could not get original content: {e}")
                
                # Get diff
                diff = self._get_file_diff(file_change.path, branch)
                
                # Metadata
                extension = self._get_extension(file_change.path)
                language = self._detect_language(extension)
                file_hash = self._calculate_hash(content) if content else ""
                
                # Create CachedFile
                cached_file = CachedFile(
                    path=file_change.path,
                    status=file_change.status,
                    content=content,
                    original_content=original_content,
                    diff=diff,
                    additions=file_change.additions,
                    deletions=file_change.deletions,
                    file_size_bytes=len(content.encode('utf-8')) if content else 0,
                    file_hash=file_hash,
                    language=language,
                    extension=extension
                )
                
                cached_files.append(cached_file)
                
                logger.debug(f"✅ Enriched {file_change.path}: {file_change.status}")
                
            except Exception as e:
                logger.error(f"Error enriching {file_change.path}: {e}")
                # Still create CachedFile without content
                cached_file = CachedFile(
                    path=file_change.path,
                    status=file_change.status,
                    additions=file_change.additions,
                    deletions=file_change.deletions,
                    extension=self._get_extension(file_change.path),
                    language=self._detect_language(self._get_extension(file_change.path))
                )
                cached_files.append(cached_file)
        
        return cached_files
    
    def _get_file_content(self, file_path: str, branch: str) -> Optional[str]:
        """Fetch file content from Git"""
        try:
            if self.git_service == "github":
                headers = {"Authorization": f"token {self.pat_token}"}
                url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{file_path}"
                response = self.session.get(url, params={"ref": branch}, headers=headers, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                if 'content' in data and data['size'] < 1_000_000:
                    try:
                        content = base64.b64decode(data['content']).decode('utf-8')
                        return content
                    except (UnicodeDecodeError, ValueError):
                        return None
            else:
                headers = {"PRIVATE-TOKEN": self.pat_token}
                project_id = f"{self.owner}%2F{self.repo}"
                file_path_encoded = file_path.replace('/', '%2F')
                
                url = f"https://pscode.lioncloud.net/api/v4/projects/{project_id}/repository/files/{file_path_encoded}/raw"
                response = self.session.get(url, params={"ref": branch}, headers=headers, timeout=30)
                response.raise_for_status()
                
                content = response.text
                if len(content.encode('utf-8')) < 1_000_000:
                    return content
                    
        except Exception as e:
            logger.debug(f"Could not fetch content for {file_path}: {e}")
        
        return None
    
    def _get_file_content_at_parent(self, file_path: str, branch: str) -> Optional[str]:
        """Get file content from parent commit"""
        try:
            if self.git_service == "github":
                headers = {"Authorization": f"token {self.pat_token}"}
                
                url = f"https://api.github.com/repos/{self.owner}/{self.repo}/commits"
                response = self.session.get(
                    url,
                    params={"sha": branch, "per_page": 2},
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                commits = response.json()
                
                if len(commits) < 2:
                    return None
                
                parent_sha = commits[1]['sha']
                
                url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{file_path}"
                response = self.session.get(
                    url,
                    params={"ref": parent_sha},
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                
                data = response.json()
                if 'content' in data:
                    return base64.b64decode(data['content']).decode('utf-8')
        
        except Exception as e:
            logger.debug(f"Could not get parent content: {e}")
        
        return None
    
    def _get_file_diff(self, file_path: str, branch: str) -> Optional[str]:
        """Get unified diff for a file"""
        try:
            if self.git_service == "github":
                headers = {"Authorization": f"token {self.pat_token}"}
                
                url = f"https://api.github.com/repos/{self.owner}/{self.repo}/commits"
                response = self.session.get(
                    url,
                    params={"sha": branch, "per_page": 1},
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                commits = response.json()
                
                if not commits:
                    return None
                
                commit_sha = commits[0]['sha']
                
                # Request diff format
                headers = {"Authorization": f"token {self.pat_token}", "Accept": "application/vnd.github.v3.diff"}
                url = f"https://api.github.com/repos/{self.owner}/{self.repo}/commits/{commit_sha}"
                response = self.session.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                
                return response.text
            
            else:
                # GitLab: diffs included in commit endpoint
                return None
        
        except Exception as e:
            logger.debug(f"Could not get diff for {file_path}: {e}")
            return None
    
    def _count_additions(self, diff: str) -> int:
        """Count additions in diff"""
        return sum(1 for line in diff.split('\n') if line.startswith('+') and not line.startswith('+++'))
    
    def _count_deletions(self, diff: str) -> int:
        """Count deletions in diff"""
        return sum(1 for line in diff.split('\n') if line.startswith('-') and not line.startswith('---'))
    
    def _get_extension(self, file_path: str) -> str:
        """Get file extension"""
        if '.' in file_path:
            return file_path.split('.')[-1].lower()
        return ""
    
    def _detect_language(self, extension: str) -> str:
        """Detect programming language from extension"""
        language_map = {
            'py': 'python', 'js': 'javascript', 'ts': 'typescript', 'tsx': 'typescript',
            'jsx': 'javascript', 'java': 'java', 'go': 'go', 'rs': 'rust',
            'cpp': 'cpp', 'c': 'c', 'h': 'c', 'hpp': 'cpp', 'cs': 'csharp',
            'sql': 'sql', 'sh': 'bash', 'yaml': 'yaml', 'yml': 'yaml',
            'json': 'json', 'xml': 'xml', 'html': 'html', 'css': 'css'
        }
        return language_map.get(extension, "")
    
    def _calculate_hash(self, content: Optional[str]) -> str:
        """Calculate SHA256 hash of content"""
        if not content:
            return ""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _get_latest_commit_id(self, branch: str) -> str:
        """Get latest commit ID for a branch"""
        try:
            if self.git_service == "github":
                headers = {"Authorization": f"token {self.pat_token}"}
                url = f"https://api.github.com/repos/{self.owner}/{self.repo}/commits"
                response = self.session.get(
                    url,
                    params={"sha": branch, "per_page": 1},
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                commits = response.json()
                return commits[0]['sha'] if commits else "unknown"
            else:
                headers = {"PRIVATE-TOKEN": self.pat_token}
                project_id = f"{self.owner}%2F{self.repo}"
                url = f"https://pscode.lioncloud.net/api/v4/projects/{project_id}/repository/commits"
                response = self.session.get(
                    url,
                    params={"ref_name": branch, "per_page": 1},
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                commits = response.json()
                return commits[0]['id'] if commits else "unknown"
        except Exception as e:
            logger.warning(f"Could not get commit ID: {e}")
            return "unknown"
    
    def _analyze_components(self, files_changed: List[FileChange]) -> List[str]:
        """Analyze files to identify components"""
        if not files_changed:
            return []
        
        components = set()
        
        for file in files_changed:
            path = file.path.lower()
            
            if '/services/' in path:
                parts = path.split('/services/')
                if len(parts) > 1:
                    component = parts[1].split('/')[0].replace('_service', '')
                    if component:
                        components.add(component)
            elif '/modules/' in path:
                parts = path.split('/modules/')
                if len(parts) > 1:
                    component = parts[1].split('/')[0]
                    if component:
                        components.add(component)
            elif '/' in path:
                parts = path.split('/')
                if len(parts) > 1:
                    component = parts[1] if parts[0] == 'src' else parts[0]
                    if component not in ['src', '.github', 'tests', 'docs', 'config', 'utils']:
                        components.add(component)
        
        return sorted(list(components))[:5]
    
    def _get_test_coverage(self) -> float:
        """Get test coverage"""
        logger.info(" Test coverage retrieval: returning default value (85%)")
        return 85.0
    
    def _build_response_from_cache(self, cached_analysis) -> CodebaseAnalysisResponse:
        """Build API response from cached analysis"""
        return CodebaseAnalysisResponse(
            repository=cached_analysis.repository,
            branch=cached_analysis.branch,
            files_changed=[
                {
                    "path": f.path,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "language": f.language,
                    "extension": f.extension,
                    "has_content": f.content is not None,
                    "has_diff": f.diff is not None
                } for f in cached_analysis.files.values()
            ],
            components_identified=cached_analysis.components_identified,
            test_coverage=cached_analysis.test_coverage,
            repository_config=RepositoryConfig(
                test_environment_url="https://test.example.com",
                api_base_url="https://api.example.com"
            )
        )
    
    def get_all_files_in_branch(self, branch: str) -> Dict[str, str]:
        """Fetch ALL files from a branch (not just changed files)"""
        try:
            if self.git_service == "github":
                return self._get_all_files_github(branch)
            else:
                return self._get_all_files_gitlab(branch)
        except Exception as e:
            logger.error(f"Error getting all files: {e}")
            return {}


    def _get_all_files_github(self, branch: str) -> Dict[str, str]:
        """Fetch all files from GitHub using tree API"""
        try:
            headers = {"Authorization": f"token {self.pat_token}"}
            
            logger.info(f"📊 Fetching entire codebase: {branch}")
            
            # Get complete tree recursively
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/git/trees/{branch}"
            response = self.session.get(
                url,
                params={"recursive": "1"},
                headers=headers,
                timeout=60
            )
            response.raise_for_status()
            tree_data = response.json()
            
            if 'tree' not in tree_data:
                logger.warning(f"No tree data for {branch}")
                return {}
            
            # Extract file paths (blob = file, tree = directory)
            file_paths = [
                item['path'] for item in tree_data['tree']
                if item['type'] == 'blob'
            ]
            
            logger.info(f"📁 Found {len(file_paths)} files to fetch")
            
            # Fetch all files in parallel
            all_files = {}
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {
                    executor.submit(self._get_file_content, path, branch): path
                    for path in file_paths
                }
                
                completed = 0
                for future in as_completed(futures):
                    path = futures[future]
                    completed += 1
                    
                    try:
                        content = future.result()
                        if content:
                            all_files[path] = content
                        
                        if completed % 10 == 0:
                            logger.info(f"  ⏳ Progress: {completed}/{len(file_paths)}")
                    except Exception as e:
                        logger.debug(f"Could not fetch {path}: {e}")
            
            logger.info(f"✅ Fetched {len(all_files)} files")
            return all_files
            
        except Exception as e:
            logger.error(f"Error getting files from GitHub: {e}")
            return {}


    def _get_all_files_gitlab(self, branch: str) -> Dict[str, str]:
        """Fetch all files from GitLab (with pagination)"""
        try:
            headers = {"PRIVATE-TOKEN": self.pat_token}
            project_id = f"{self.owner}%2F{self.repo}"
            
            logger.info(f"📊 Fetching entire codebase from GitLab: {branch}")
            
            all_files = {}
            page = 1
            
            while True:
                url = f"https://pscode.lioncloud.net/api/v4/projects/{project_id}/repository/tree"
                response = self.session.get(
                    url,
                    params={"ref": branch, "recursive": True, "per_page": 100, "page": page},
                    headers=headers,
                    timeout=60
                )
                response.raise_for_status()
                items = response.json()
                
                if not items:
                    break
                
                # Fetch content for files on this page
                for item in items:
                    if item['type'] == 'blob':
                        try:
                            content = self._get_file_content(item['path'], branch)
                            if content:
                                all_files[item['path']] = content
                        except Exception as e:
                            logger.debug(f"Could not fetch {item['path']}: {e}")
                
                page += 1
            
            logger.info(f"✅ Fetched {len(all_files)} files from GitLab")
            return all_files
            
        except Exception as e:
            logger.error(f"Error getting files from GitLab: {e}")
            return {}
        
    # ====================================================================
    # CACHE MANAGEMENT APIs
    # ====================================================================
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.cache:
            return {"caching": "disabled"}
        return self.cache.get_stats()
    
    def clear_cache(self) -> None:
        """Clear all cache"""
        if self.cache:
            self.cache.clear()
    
    def invalidate_branch_cache(self, branch: str) -> bool:
        """Invalidate cache for specific branch"""
        if not self.cache:
            return False
        return self.cache.invalidate(self.repo, branch)
    
    def get_cached_files(self, branch: str) -> Dict[str, CachedFile]:
        """Get all cached files for a branch"""
        if not self.cache:
            return {}
        return self.cache.get_all_files(self.repo, branch)
    
    def get_cached_file_content(self, branch: str, file_path: str) -> Optional[str]:
        """Get cached content of specific file"""
        if not self.cache:
            return None
        return self.cache.get_file_content(self.repo, branch, file_path)
    
    def get_cached_file_diff(self, branch: str, file_path: str) -> Optional[str]:
        """Get cached diff of specific file"""
        if not self.cache:
            return None
        return self.cache.get_file_diff(self.repo, branch, file_path)
    
    def get_files_by_status(self, branch: str, status: str) -> Dict[str, CachedFile]:
        """Get cached files filtered by status"""
        if not self.cache:
            return {}
        return self.cache.get_files_by_status(self.repo, branch, status)
    
    def get_files_by_language(self, branch: str, language: str) -> Dict[str, CachedFile]:
        """Get cached files filtered by language"""
        if not self.cache:
            return {}
        return self.cache.get_files_by_language(self.repo, branch, language)
    
    def search_cached_content(
        self,
        branch: str,
        search_term: str,
        case_sensitive: bool = False
    ) -> Dict[str, List[Tuple[int, str]]]:
        """Search in cached content"""
        if not self.cache:
            return {}
        return self.cache.search_content(self.repo, branch, search_term, case_sensitive)
    
    def export_cache(self, branch: str, filepath: str) -> bool:
        """Export cache to JSON"""
        if not self.cache:
            return False
        return self.cache.export_to_json(self.repo, branch, filepath)
    
    def import_cache(self, filepath: str) -> bool:
        """Import cache from JSON"""
        if not self.cache:
            return False
        return self.cache.import_from_json(filepath)