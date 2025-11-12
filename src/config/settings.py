# ==============================================
# Configuration management for QE Orchestrator
# ==============================================

import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root directory
# This ensures .env is found regardless of where the script is run from
project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env'

load_dotenv(dotenv_path=env_path, override=True)

@dataclass
class JiraConfig:
    """Jira integration configuration"""
    server: str
    email: str
    api_token: str
    webhook_secret: Optional[str]
    agent_name: str
    
    def __post_init__(self):
        if not self.server.startswith('https://'):
            raise ValueError("JIRA_SERVER must start with https://")

@dataclass
class GitHubConfig:
    """GitHub integration configuration"""
    token: str
    repo: str  # format: "organization/repository"
    
    def __post_init__(self):
        if '/' not in self.repo:
            raise ValueError("GITHUB_REPO must be in format 'org/repo'")

@dataclass
class GeminiConfig:
    """Google Gemini AI configuration"""
    api_key: str
    model: str = "gemini-2.0-flash"
    temperature: float = 0.7
    max_tokens: int = 2048

@dataclass
class EmailConfig:
    """Email notification configuration"""
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    from_email: Optional[str] = None

@dataclass
class TestRepoConfig:
    """Test repository configuration"""
    repo_url: str  # format: "organization/repository"

    def __post_init__(self):
        if '/' not in self.repo_url:
            raise ValueError("TEST_REPO_URL must be in format 'org/repo'")

@dataclass
class ServerConfig:
    """Webhook server configuration"""
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    workers: int = 4

class Config:
    """Main configuration class"""

    def __init__(self):
        self.jira = JiraConfig(
            server=os.getenv('JIRA_SERVER', ''),
            email=os.getenv('JIRA_EMAIL', ''),
            api_token=os.getenv('JIRA_API_TOKEN', ''),
            webhook_secret=os.getenv('JIRA_WEBHOOK_SECRET'),
            agent_name=os.getenv('QE_AGENT_NAME', 'QE Agent')
        )

        self.github = GitHubConfig(
            token=os.getenv('GITHUB_TOKEN', ''),
            repo=os.getenv('GITHUB_REPO', '')
        )

        self.gemini = GeminiConfig(
            api_key=os.getenv('GEMINI_API_KEY', ''),
            model=os.getenv('GEMINI_MODEL', 'gemini-pro'),
            temperature=float(os.getenv('GEMINI_TEMPERATURE', '0.7')),
            max_tokens=int(os.getenv('GEMINI_MAX_TOKENS', '2048'))
        )

        self.email = EmailConfig(
            smtp_server=os.getenv('EMAIL_SMTP_SERVER'),
            smtp_port=int(os.getenv('EMAIL_SMTP_PORT', '587')),
            username=os.getenv('EMAIL_USERNAME'),
            password=os.getenv('EMAIL_PASSWORD'),
            from_email=os.getenv('EMAIL_FROM')
        )

        self.test_repo = TestRepoConfig(
            repo_url=os.getenv('TEST_REPO_URL', 'org/test-repo')
        )

        self.server = ServerConfig(
            host=os.getenv('WEBHOOK_HOST', '0.0.0.0'),
            port=int(os.getenv('WEBHOOK_PORT', '8080')),
            debug=os.getenv('DEBUG', 'False').lower() == 'true',
            workers=int(os.getenv('WORKERS', '4'))
        )

        self.gcp_project_id = os.getenv('GCP_PROJECT_ID')
    
    def validate(self) -> bool:
        """Validate required configuration"""
        required_fields = {
            'JIRA_SERVER': self.jira.server,
            'JIRA_EMAIL': self.jira.email,
            'JIRA_API_TOKEN': self.jira.api_token,
            'GITHUB_TOKEN': self.github.token,
            'GITHUB_REPO': self.github.repo,
            'GEMINI_API_KEY': self.gemini.api_key
        }
        
        missing = [field for field, value in required_fields.items() if not value]
        
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                f"Please check your .env file"
            )
        
        return True
    
    def to_dict(self) -> dict:
        """Convert config to dictionary (for logging, debugging)"""
        return {
            'jira': {
                'server': self.jira.server,
                'email': self.jira.email,
                'agent_name': self.jira.agent_name,
                'webhook_secret_set': bool(self.jira.webhook_secret)
            },
            'github': {
                'repo': self.github.repo
            },
            'gemini': {
                'model': self.gemini.model,
                'temperature': self.gemini.temperature
            },
            'server': {
                'host': self.server.host,
                'port': self.server.port,
                'debug': self.server.debug
            }
        }

# config/__init__.py
from .settings import Config, JiraConfig, GitHubConfig, GeminiConfig, EmailConfig, TestRepoConfig, ServerConfig

__all__ = ['Config', 'JiraConfig', 'GitHubConfig', 'GeminiConfig', 'EmailConfig', 'TestRepoConfig', 'ServerConfig']