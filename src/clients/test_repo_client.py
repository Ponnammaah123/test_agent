from typing import List, Optional, Dict
from src.config.settings import Config
from src.clients.github_client import GitHubClient
from src.utils.logger import get_logger

logger = get_logger(__name__)

class TestRepoClient:
    """Client for interacting with the Test Repository"""
    
    def __init__(self, config: Config, repo_url: str):
        self.config = config
        self.repo_url = repo_url
        # We reuse GitHubClient logic but need to point it to the test repo
        # Since GitHubClient takes config and reads repo from it, 
        # we instantiate it and then override the repo details manually.
        self.client = GitHubClient(config)
        self._override_repo_details(repo_url)
        
    def _override_repo_details(self, repo_url: str):
        """Override the repo details in the underlying client"""
        try:
            # Logic to parse owner/repo from URL
            # Expected format: owner/repo
            if "github.com/" in repo_url:
                parts = repo_url.split("github.com/")[-1].replace(".git", "").split("/")
                self.client.owner = parts[0]
                self.client.repo = parts[1]
            elif "/" in repo_url:
                parts = repo_url.split("/")
                self.client.owner = parts[0]
                self.client.repo = parts[1]
            logger.info(f"TestRepoClient configured for {self.client.owner}/{self.client.repo}")
        except Exception as e:
            logger.error(f"Failed to parse test repo URL {repo_url}: {e}")

    def list_test_files(self, path: str = "tests") -> List[str]:
        """List all test files in the repo"""
        try:
            # Using GitHubClient's tree fetch
            files_dict = self.client.get_all_files_in_branch("main") # Assuming main branch
            return list(files_dict.keys())
        except Exception as e:
            logger.error(f"Error listing test files: {e}")
            return []

    def get_file_content(self, path: str) -> Optional[str]:
        return self.client.get_cached_file_content("main", path)