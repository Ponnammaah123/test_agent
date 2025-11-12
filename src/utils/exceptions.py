# ==============================================
# Custom exceptions for QE Orchestrator
# ==============================================

"""
Exception Hierarchy for QE Orchestrator

This module defines a comprehensive exception hierarchy following these principles:
1. All exceptions inherit from QEOrchestratorException
2. Exceptions are categorized by domain (Client, Agent, Workflow)
3. Each exception includes context information for debugging
4. Recoverable vs non-recoverable errors are clearly distinguished
"""

from typing import Optional, Dict, Any


# ==============================================
# Base Exception
# ==============================================

class QEOrchestratorException(Exception):
    """
    Base exception for all QE Orchestrator errors

    All custom exceptions should inherit from this class.
    Includes support for error context and categorization.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        """
        Initialize base exception

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code (e.g., "JIRA_001")
            context: Additional context information (ticket key, agent name, etc.)
            original_exception: Original exception if this is a wrapped error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.original_exception = original_exception

    def __str__(self):
        """Format exception as string with context"""
        base = self.message
        if self.error_code:
            base = f"[{self.error_code}] {base}"
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            base = f"{base} (Context: {context_str})"
        return base


# ==============================================
# Client Exceptions
# ==============================================

class ClientException(QEOrchestratorException):
    """Base exception for client errors (Jira, GitHub, etc.)"""
    pass


class JiraClientException(ClientException):
    """Jira client errors"""
    pass


class JiraAuthenticationException(JiraClientException):
    """Jira authentication failed"""
    pass


class JiraTicketNotFoundException(JiraClientException):
    """Jira ticket not found"""
    pass


class JiraPermissionException(JiraClientException):
    """Insufficient Jira permissions"""
    pass


class GitHubClientException(ClientException):
    """GitHub client errors"""
    pass


class GitHubAuthenticationException(GitHubClientException):
    """GitHub authentication failed"""
    pass


class GitHubRepositoryNotFoundException(GitHubClientException):
    """GitHub repository not found"""
    pass


class GitHubRateLimitException(GitHubClientException):
    """GitHub rate limit exceeded"""
    pass


class GeminiClientException(ClientException):
    """Gemini AI client errors"""
    pass


class GeminiAuthenticationException(GeminiClientException):
    """Gemini authentication failed"""
    pass


class GeminiQuotaException(GeminiClientException):
    """Gemini quota exceeded"""
    pass


class GeminiGenerationException(GeminiClientException):
    """Gemini failed to generate response"""
    pass


# ==============================================
# Configuration Exceptions
# ==============================================

class ConfigurationException(QEOrchestratorException):
    """Configuration errors"""
    pass


class MissingConfigException(ConfigurationException):
    """Required configuration is missing"""
    pass


class InvalidConfigException(ConfigurationException):
    """Configuration value is invalid"""
    pass


# ==============================================
# Agent Exceptions
# ==============================================

class AgentException(QEOrchestratorException):
    """Base exception for agent errors"""
    pass


class TestGenerationException(AgentException):
    """Test generation agent errors"""
    pass


class LocatorExtractionException(TestGenerationException):
    """Failed to extract locators from codebase"""
    pass


class CodeGenerationException(TestGenerationException):
    """Failed to generate test code"""
    pass


class TestExecutionException(AgentException):
    """Test execution agent errors"""
    pass


class TestRunnerException(TestExecutionException):
    """Failed to run tests"""
    pass


class ResultParsingException(TestExecutionException):
    """Failed to parse test results"""
    pass


class ArtifactCollectionException(TestExecutionException):
    """Failed to collect test artifacts"""
    pass


class DefectDetectionException(AgentException):
    """Defect detection agent errors"""
    pass


class FailureAnalysisException(DefectDetectionException):
    """Failed to analyze test failures"""
    pass


class SelfHealingException(DefectDetectionException):
    """Failed to self-heal tests"""
    pass


class BugReportingException(DefectDetectionException):
    """Failed to create bug reports"""
    pass


# ==============================================
# Workflow Exceptions
# ==============================================

class WorkflowException(QEOrchestratorException):
    """Workflow execution errors"""
    pass


class WorkflowStateException(WorkflowException):
    """Invalid workflow state"""
    pass


class WorkflowTimeoutException(WorkflowException):
    """Workflow execution timed out"""
    pass


class WorkflowValidationException(WorkflowException):
    """Workflow validation failed"""
    pass


# ==============================================
# Data Exceptions
# ==============================================

class DataException(QEOrchestratorException):
    """Data processing errors"""
    pass


class ValidationException(DataException):
    """Data validation failed"""
    pass


class ParsingException(DataException):
    """Failed to parse data"""
    pass


class CacheException(DataException):
    """Cache operation failed"""
    pass


# ==============================================
# Recoverable vs Non-Recoverable
# ==============================================

class RecoverableException(QEOrchestratorException):
    """
    Base class for recoverable errors

    These errors can potentially be retried or handled gracefully.
    Examples: network timeouts, rate limits, temporary service unavailability
    """
    pass


class NonRecoverableException(QEOrchestratorException):
    """
    Base class for non-recoverable errors

    These errors require manual intervention and cannot be automatically fixed.
    Examples: authentication failures, missing configuration, permission errors
    """
    pass


# ==============================================
# Exception Utilities
# ==============================================

def is_recoverable(exception: Exception) -> bool:
    """
    Check if an exception is recoverable

    Args:
        exception: Exception to check

    Returns:
        True if recoverable, False otherwise
    """
    return isinstance(exception, RecoverableException)


def get_exception_context(exception: Exception) -> Dict[str, Any]:
    """
    Extract context from exception

    Args:
        exception: Exception to extract context from

    Returns:
        Context dictionary
    """
    if isinstance(exception, QEOrchestratorException):
        return exception.context
    return {}


def format_exception_for_jira(exception: Exception) -> str:
    """
    Format exception for Jira comment

    Args:
        exception: Exception to format

    Returns:
        Formatted Jira markdown string
    """
    if isinstance(exception, QEOrchestratorException):
        message = f"*Error:* {exception.message}"
        if exception.error_code:
            message = f"*Error Code:* {{monospace}}{exception.error_code}{{monospace}}\n{message}"
        if exception.context:
            message += f"\n*Context:*\n"
            for key, value in exception.context.items():
                message += f"- {key}: {value}\n"
        return message
    else:
        return f"*Error:* {str(exception)}"