"""
Enhanced caching system for GitHub/GitLab client
Stores file content, diffs, and metadata with efficient retrieval

NEW METHODS ADDED:
- get_file() - Get full CachedFile object by path
- get_all_files_as_dict() - Get all files as dictionary with metadata
- get_all_files_as_json() - Get all files as JSON string
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class CachedFile:
    """Represents a cached file with content and diff"""
    
    # File identification
    path: str
    status: str  # 'added', 'modified', 'deleted'
    
    # Primary content
    content: Optional[str] = None  # Full file content (current version)
    original_content: Optional[str] = None  # Original content (for modified files)
    diff: Optional[str] = None  # Unified diff format
    
    # Change metrics
    additions: int = 0
    deletions: int = 0
    
    # Metadata
    file_size_bytes: int = 0
    file_hash: str = ""  # SHA256 of content for deduplication
    language: str = ""  # Programming language if detected
    extension: str = ""
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "path": self.path,
            "status": self.status,
            "content": self.content,
            "original_content": self.original_content,
            "diff": self.diff,
            "additions": self.additions,
            "deletions": self.deletions,
            "file_size_bytes": self.file_size_bytes,
            "file_hash": self.file_hash,
            "language": self.language,
            "extension": self.extension,
            "created_at": self.created_at.isoformat()
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'CachedFile':
        """Reconstruct from dictionary"""
        return CachedFile(
            path=data['path'],
            status=data['status'],
            content=data.get('content'),
            original_content=data.get('original_content'),
            diff=data.get('diff'),
            additions=data.get('additions', 0),
            deletions=data.get('deletions', 0),
            file_size_bytes=data.get('file_size_bytes', 0),
            file_hash=data.get('file_hash', ''),
            language=data.get('language', ''),
            extension=data.get('extension', ''),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary without full content (for API responses)"""
        return {
            "path": self.path,
            "status": self.status,
            "additions": self.additions,
            "deletions": self.deletions,
            "file_size_bytes": self.file_size_bytes,
            "language": self.language,
            "extension": self.extension,
            "has_content": self.content is not None,
            "has_diff": self.diff is not None
        }


@dataclass
class CachedAnalysis:
    """Represents a cached codebase analysis for a specific branch"""
    
    # Identifiers
    repository: str
    branch: str
    commit_id: str
    
    # Files with full content and diffs
    files: Dict[str, CachedFile] = field(default_factory=dict)  # path -> CachedFile
    
    # Metadata
    total_files: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    components_identified: List[str] = field(default_factory=list)
    test_coverage: float = 0.0
    
    # Cache metadata
    cached_at: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 3600  # 1 hour default
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        age = datetime.now() - self.cached_at
        return age.total_seconds() > self.ttl_seconds
    
    def total_content_size_mb(self) -> float:
        """Calculate total cached content size in MB"""
        total_bytes = 0
        for file in self.files.values():
            if file.content:
                total_bytes += len(file.content.encode('utf-8'))
            if file.original_content:
                total_bytes += len(file.original_content.encode('utf-8'))
            if file.diff:
                total_bytes += len(file.diff.encode('utf-8'))
        return total_bytes / (1024 * 1024)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "repository": self.repository,
            "branch": self.branch,
            "commit_id": self.commit_id,
            "files": {path: f.to_dict() for path, f in self.files.items()},
            "total_files": self.total_files,
            "total_additions": self.total_additions,
            "total_deletions": self.total_deletions,
            "components_identified": self.components_identified,
            "test_coverage": self.test_coverage,
            "cached_at": self.cached_at.isoformat(),
            "is_expired": self.is_expired(),
            "total_content_size_mb": self.total_content_size_mb()
        }
    
    def to_summary(self) -> Dict[str, Any]:
        """Get summary without full file content"""
        return {
            "repository": self.repository,
            "branch": self.branch,
            "commit_id": self.commit_id,
            "files": {path: f.get_summary() for path, f in self.files.items()},
            "total_files": self.total_files,
            "total_additions": self.total_additions,
            "total_deletions": self.total_deletions,
            "components_identified": self.components_identified,
            "test_coverage": self.test_coverage,
            "cached_at": self.cached_at.isoformat(),
            "is_expired": self.is_expired(),
            "total_content_size_mb": self.total_content_size_mb()
        }


class GitHubClientCache:
    """
    High-performance cache for GitHub/GitLab code analysis
    
    Features:
    - In-memory caching with TTL support
    - LRU (Least Recently Used) eviction
    - File content and diff storage
    - Metadata indexing for fast retrieval
    - Serialization support for persistence
    
    Usage:
        cache = GitHubClientCache(max_entries=50, max_size_mb=500)
        cache.set_analysis(repo, branch, commit_id, files, components, coverage)
        analysis = cache.get_analysis(repo, branch)
        files_by_status = cache.get_files_by_status(repo, branch, 'modified')
    """
    
    def __init__(self, max_entries: int = 50, max_size_mb: int = 500, default_ttl: int = 3600):
        """
        Initialize cache
        
        Args:
            max_entries: Maximum number of analyses to cache (LRU eviction)
            max_size_mb: Maximum total content size before LRU cleanup
            default_ttl: Default TTL in seconds
        """
        self.cache: Dict[str, CachedAnalysis] = {}
        self.max_entries = max_entries
        self.max_size_mb = max_size_mb
        self.default_ttl = default_ttl
        
        # Access tracking for LRU
        self.access_times: Dict[str, datetime] = {}
        
        # Statistics
        self.hit_count = 0
        self.miss_count = 0
        self.current_size_mb = 0.0
        
        logger.info(f"✅ GitHubClientCache initialized")
        logger.info(f"   Max entries: {max_entries}")
        logger.info(f"   Max size: {max_size_mb}MB")
        logger.info(f"   Default TTL: {default_ttl}s")
    
    def _make_key(self, repository: str, branch: str) -> str:
        """Create cache key from repository and branch"""
        return f"{repository}:{branch}"
    
    def _evict_lru(self):
        """Evict least recently used entry if cache is full"""
        if len(self.cache) >= self.max_entries or self.current_size_mb >= self.max_size_mb:
            if self.access_times:
                # Find LRU key
                lru_key = min(self.access_times.keys(), key=self.access_times.get)
                
                # Remove from cache
                if lru_key in self.cache:
                    removed_size = self.cache[lru_key].total_content_size_mb()
                    del self.cache[lru_key]
                    self.current_size_mb -= removed_size
                    
                del self.access_times[lru_key]
                
                logger.info(f"⚠️  LRU evicted: {lru_key} (freed {removed_size:.2f}MB)")
    
    def set_analysis(
        self,
        repository: str,
        branch: str,
        commit_id: str,
        files: List['CachedFile'],
        components: List[str],
        test_coverage: float
    ) -> None:
        """
        Cache analysis result with complete file content and diffs
        
        Args:
            repository: Repository name
            branch: Branch name
            commit_id: Latest commit SHA
            files: List of CachedFile objects (with content/diffs populated)
            components: List of identified components
            test_coverage: Test coverage percentage
        """
        key = self._make_key(repository, branch)
        
        # Create analysis cache object
        files_dict = {f.path: f for f in files}
        
        analysis = CachedAnalysis(
            repository=repository,
            branch=branch,
            commit_id=commit_id,
            files=files_dict,
            components_identified=components,
            test_coverage=test_coverage,
            total_files=len(files),
            total_additions=sum(f.additions for f in files),
            total_deletions=sum(f.deletions for f in files),
            ttl_seconds=self.default_ttl
        )
        
        # Check if we need to evict
        analysis_size = analysis.total_content_size_mb()
        if self.current_size_mb + analysis_size >= self.max_size_mb:
            self._evict_lru()
        
        # Store in cache
        self.cache[key] = analysis
        self.access_times[key] = datetime.now()
        self.current_size_mb += analysis_size
        
        logger.info(f"✅ Cached analysis: {key}")
        logger.info(f"   Files: {len(files)}")
        logger.info(f"   Size: {analysis_size:.2f}MB")
        logger.info(f"   Cache size: {self.current_size_mb:.2f}MB / {self.max_size_mb}MB")
    
    def get_analysis(self, repository: str, branch: str) -> Optional[CachedAnalysis]:
        """
        Retrieve cached analysis
        
        Args:
            repository: Repository name
            branch: Branch name
        
        Returns:
            CachedAnalysis if found and not expired, None otherwise
        """
        key = self._make_key(repository, branch)
        
        if key not in self.cache:
            self.miss_count += 1
            logger.debug(f"❌ Cache miss: {key}")
            return None
        
        analysis = self.cache[key]
        
        # Check expiration
        if analysis.is_expired():
            logger.warning(f"⏰ Cache expired: {key}")
            del self.cache[key]
            del self.access_times[key]
            self.current_size_mb -= analysis.total_content_size_mb()
            self.miss_count += 1
            return None
        
        # Update access time for LRU
        self.access_times[key] = datetime.now()
        self.hit_count += 1
        
        logger.debug(f"✅ Cache hit: {key}")
        return analysis
    
    def get_file(self, repository: str, branch: str, file_path: str) -> Optional[CachedFile]:
        """
        ✅ NEW METHOD: Get full file object with all metadata from cache
        
        Args:
            repository: Repository name
            branch: Branch name
            file_path: Path to file
        
        Returns:
            CachedFile object if found, None otherwise
        """
        analysis = self.get_analysis(repository, branch)
        if not analysis or file_path not in analysis.files:
            logger.warning(f"❌ File not found: {repository}:{branch}:{file_path}")
            return None
        
        return analysis.files[file_path]
    
    def get_file_content(self, repository: str, branch: str, file_path: str) -> Optional[str]:
        """
        Get content of a specific file from cache
        
        Args:
            repository: Repository name
            branch: Branch name
            file_path: Path to file
        
        Returns:
            File content if found, None otherwise
        """
        cached_file = self.get_file(repository, branch, file_path)
        return cached_file.content if cached_file else None
    
    def get_file_diff(self, repository: str, branch: str, file_path: str) -> Optional[str]:
        """
        Get diff of a specific file from cache
        
        Args:
            repository: Repository name
            branch: Branch name
            file_path: Path to file
        
        Returns:
            File diff if found, None otherwise
        """
        analysis = self.get_analysis(repository, branch)
        if not analysis or file_path not in analysis.files:
            return None
        
        return analysis.files[file_path].diff
    
    def get_all_files(self, repository: str, branch: str) -> Dict[str, CachedFile]:
        """
        ✅ GET ALL CACHED FILES BY KEY (repository:branch)
        Get all cached files for a repository:branch
        
        Args:
            repository: Repository name
            branch: Branch name
        
        Returns:
            Dictionary of {file_path: CachedFile}
        """
        analysis = self.get_analysis(repository, branch)
        return analysis.files if analysis else {}
    
    def get_all_files_as_dict(self, repository: str, branch: str) -> Dict[str, Any]:
        """
        ✅ NEW METHOD: Get all files as dictionary with full metadata
        
        Args:
            repository: Repository name
            branch: Branch name
        
        Returns:
            Dictionary with all file data including content
        """
        files = self.get_all_files(repository, branch)
        
        return {
            "repository": repository,
            "branch": branch,
            "total_files": len(files),
            "files": {
                path: cached_file.to_dict()
                for path, cached_file in files.items()
            }
        }
    
    def get_all_files_as_json(self, repository: str, branch: str, indent: int = 2) -> str:
        """
        ✅ NEW METHOD: Get all files as JSON string
        
        Args:
            repository: Repository name
            branch: Branch name
            indent: JSON indentation level
        
        Returns:
            JSON string with all file data
        """
        data = self.get_all_files_as_dict(repository, branch)
        return json.dumps(data, indent=indent, default=str)
    
    def get_files_by_status(
        self,
        repository: str,
        branch: str,
        status: str
    ) -> Dict[str, CachedFile]:
        """
        Get files filtered by status
        
        Args:
            repository: Repository name
            branch: Branch name
            status: File status ('added', 'modified', 'deleted')
        
        Returns:
            Dictionary of {file_path: CachedFile} matching status
        """
        analysis = self.get_analysis(repository, branch)
        if not analysis:
            return {}
        
        return {
            path: f for path, f in analysis.files.items()
            if f.status == status
        }
    
    def get_files_by_language(
        self,
        repository: str,
        branch: str,
        language: str
    ) -> Dict[str, CachedFile]:
        """
        Get files filtered by programming language
        
        Args:
            repository: Repository name
            branch: Branch name
            language: Programming language (e.g., 'python', 'javascript')
        
        Returns:
            Dictionary of {file_path: CachedFile} for that language
        """
        analysis = self.get_analysis(repository, branch)
        if not analysis:
            return {}
        
        return {
            path: f for path, f in analysis.files.items()
            if f.language.lower() == language.lower()
        }
    
    def search_content(
        self,
        repository: str,
        branch: str,
        search_term: str,
        case_sensitive: bool = False
    ) -> Dict[str, List[Tuple[int, str]]]:
        """
        Search for text in cached file contents
        
        Args:
            repository: Repository name
            branch: Branch name
            search_term: Text to search for
            case_sensitive: Whether search is case-sensitive
        
        Returns:
            Dictionary of {file_path: [(line_number, line_text), ...]}
        """
        analysis = self.get_analysis(repository, branch)
        if not analysis:
            return {}
        
        results = {}
        
        for file_path, cached_file in analysis.files.items():
            if not cached_file.content:
                continue
            
            matches = []
            for line_num, line in enumerate(cached_file.content.split('\n'), 1):
                if case_sensitive:
                    if search_term in line:
                        matches.append((line_num, line))
                else:
                    if search_term.lower() in line.lower():
                        matches.append((line_num, line))
            
            if matches:
                results[file_path] = matches
        
        return results
    
    def invalidate(self, repository: str, branch: str) -> bool:
        """
        Remove specific cache entry
        
        Args:
            repository: Repository name
            branch: Branch name
        
        Returns:
            True if removed, False if not found
        """
        key = self._make_key(repository, branch)
        
        if key not in self.cache:
            logger.warning(f"❌ Cache not found for invalidation: {key}")
            return False
        
        analysis = self.cache[key]
        size = analysis.total_content_size_mb()
        
        del self.cache[key]
        del self.access_times[key]
        self.current_size_mb -= size
        
        logger.info(f"❌ Cache invalidated: {key} (freed {size:.2f}MB)")
        return True
    
    def clear(self) -> None:
        """Clear entire cache"""
        self.cache.clear()
        self.access_times.clear()
        self.current_size_mb = 0.0
        logger.info("🗑️  Cache cleared completely")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_files = sum(len(a.files) for a in self.cache.values())
        hit_rate = (self.hit_count / (self.hit_count + self.miss_count) * 100) \
                   if (self.hit_count + self.miss_count) > 0 else 0
        
        return {
            "cache_entries": len(self.cache),
            "max_entries": self.max_entries,
            "total_files_cached": total_files,
            "total_content_size_mb": self.current_size_mb,
            "max_content_size_mb": self.max_size_mb,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate_percent": f"{hit_rate:.1f}%",
            "entries": list(self.cache.keys()),
            "entries_detail": {
                key: {
                    "files": analysis.total_files,
                    "size_mb": analysis.total_content_size_mb(),
                    "additions": analysis.total_additions,
                    "deletions": analysis.total_deletions,
                    "expired": analysis.is_expired()
                }
                for key, analysis in self.cache.items()
            }
        }
    
    def export_to_json(self, repository: str, branch: str, filepath: str) -> bool:
        """
        Export cached analysis to JSON file
        
        Args:
            repository: Repository name
            branch: Branch name
            filepath: Path to save JSON file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            analysis = self.get_analysis(repository, branch)
            if not analysis:
                logger.error(f"No cache found to export: {repository}:{branch}")
                return False
            
            data = analysis.to_dict()
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"✅ Exported cache to: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error exporting cache: {e}")
            return False
    
    def import_from_json(self, filepath: str) -> bool:
        """
        Import cached analysis from JSON file
        
        Args:
            filepath: Path to JSON file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Reconstruct CachedFile objects
            files = []
            for file_data in data.get('files', {}).values():
                files.append(CachedFile.from_dict(file_data))
            
            # Store in cache
            self.set_analysis(
                repository=data['repository'],
                branch=data['branch'],
                commit_id=data['commit_id'],
                files=files,
                components=data.get('components_identified', []),
                test_coverage=data.get('test_coverage', 0.0)
            )
            
            logger.info(f"✅ Imported cache from: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error importing cache: {e}")
            return False


# Global cache instance
github_client_cache = GitHubClientCache(max_entries=50, max_size_mb=500, default_ttl=3600)


def get_cache() -> GitHubClientCache:
    """Get global cache instance"""
    return github_client_cache