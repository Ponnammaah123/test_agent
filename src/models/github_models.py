# ==============================================
# GitHub data models
# ==============================================

from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class RepositoryConfig:
    """Configuration from repository qe.config.json"""
    test_environment_url: str  # Dev/Local URL
    api_base_url: str
    staging_url: Optional[str] = None
    production_url: Optional[str] = None
    qa_url: Optional[str] = None
    admin_url: Optional[str] = None
    database_config: Dict = field(default_factory=dict)
    browser_config: Dict = field(default_factory=dict)
    test_data_config: Dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> 'RepositoryConfig':
        """Create from dictionary"""
        # Support both flat and nested structure
        test_env = data.get('test_environment', {})

        return cls(
            test_environment_url=test_env.get('test_environment_url', data.get('test_environment_url', '')),
            api_base_url=test_env.get('api_base_url', data.get('api_base_url', '')),
            staging_url=test_env.get('staging_url', data.get('staging_url')),
            production_url=test_env.get('production_url', data.get('production_url')),
            qa_url=test_env.get('qa_url', data.get('qa_url')),
            admin_url=data.get('admin_url'),
            database_config=data.get('database', {}),
            browser_config=data.get('browser_config', {}),
            test_data_config=data.get('test_data', {})
        )

    def get_url_for_environment(self, environment: str) -> str:
        """Get base URL for specified environment"""
        env_map = {
            'dev': self.test_environment_url,
            'staging': self.staging_url or self.test_environment_url,
            'production': self.production_url or self.test_environment_url,
            'qa': self.qa_url or self.test_environment_url
        }
        return env_map.get(environment, self.test_environment_url)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'test_environment_url': self.test_environment_url,
            'api_base_url': self.api_base_url,
            'staging_url': self.staging_url,
            'production_url': self.production_url,
            'qa_url': self.qa_url,
            'admin_url': self.admin_url,
            'database': self.database_config,
            'browser_config': self.browser_config,
            'test_data': self.test_data_config
        }

@dataclass
class CodebaseAnalysis:
    """Results from code analysis"""
    repository: str
    branch: str
    files_changed: List[str]
    components_identified: List[str]
    business_logic: Dict[str, str]
    dependencies: List[str]
    test_coverage: float
    repository_config: Optional[RepositoryConfig] = None
    commit_count: int = 0
    last_commit_date: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'repository': self.repository,
            'branch': self.branch,
            'files_changed': self.files_changed,
            'components_identified': self.components_identified,
            'dependencies': self.dependencies[:10],  # Limit for readability
            'test_coverage': self.test_coverage,
            'commit_count': self.commit_count,
            'has_config': self.repository_config is not None
        }