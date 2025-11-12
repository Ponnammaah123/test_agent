# ==============================================
# Structured logging setup with JSON support
# ==============================================

import logging
import sys
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime
import threading

# Thread-local storage for correlation IDs
_thread_local = threading.local()


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter for structured logging with contextual fields

    Supports both human-readable and JSON formats
    """

    def __init__(self, json_format: bool = False):
        """
        Initialize structured formatter

        Args:
            json_format: If True, output JSON format; otherwise human-readable
        """
        super().__init__()
        self.json_format = json_format

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with contextual fields"""

        # Base log data
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # Add correlation ID if available
        correlation_id = get_correlation_id()
        if correlation_id:
            log_data['correlation_id'] = correlation_id

        # Add contextual fields from extra
        if hasattr(record, 'agent'):
            log_data['agent'] = record.agent
        if hasattr(record, 'ticket_key'):
            log_data['ticket_key'] = record.ticket_key
        if hasattr(record, 'execution_id'):
            log_data['execution_id'] = record.execution_id
        if hasattr(record, 'error_code'):
            log_data['error_code'] = record.error_code
        if hasattr(record, 'context'):
            log_data['context'] = record.context

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        if self.json_format:
            # JSON format for production/parsing
            return json.dumps(log_data)
        else:
            # Human-readable format for development
            parts = [
                log_data['timestamp'],
                f"{log_data['level']:<8}",
                f"{log_data['logger']:<30}"
            ]

            # Add contextual fields
            context_parts = []
            if 'correlation_id' in log_data:
                context_parts.append(f"[{log_data['correlation_id'][:8]}]")
            if 'agent' in log_data:
                context_parts.append(f"[{log_data['agent']}]")
            if 'ticket_key' in log_data:
                context_parts.append(f"[{log_data['ticket_key']}]")
            if 'error_code' in log_data:
                context_parts.append(f"[{log_data['error_code']}]")

            if context_parts:
                parts.append(' '.join(context_parts))

            # Add message
            parts.append(f"| {log_data['message']}")

            # Add exception if present
            if 'exception' in log_data:
                parts.append(f"\n{log_data['exception']}")

            return ' '.join(parts)


class StructuredLogger(logging.LoggerAdapter):
    """
    Logger adapter that adds contextual fields to all log records

    Usage:
        logger = StructuredLogger.get_logger(__name__, agent='TestAgent', ticket_key='JIRA-123')
        logger.info("Processing test", extra={'execution_id': 'exec-001'})
    """

    def __init__(self, logger: logging.Logger, context: Dict[str, Any]):
        """
        Initialize structured logger

        Args:
            logger: Base logger instance
            context: Default context fields to add to all logs
        """
        super().__init__(logger, context)

    def process(self, msg, kwargs):
        """Add context to log record"""
        # Merge default context with per-call extra fields
        extra = kwargs.get('extra', {})
        extra.update(self.extra)
        kwargs['extra'] = extra
        return msg, kwargs


# ==============================================
# Correlation ID Management
# ==============================================

def set_correlation_id(correlation_id: str):
    """
    Set correlation ID for current thread

    Args:
        correlation_id: Unique identifier for request/workflow
    """
    _thread_local.correlation_id = correlation_id


def get_correlation_id() -> Optional[str]:
    """
    Get correlation ID for current thread

    Returns:
        Correlation ID or None
    """
    return getattr(_thread_local, 'correlation_id', None)


def clear_correlation_id():
    """Clear correlation ID for current thread"""
    if hasattr(_thread_local, 'correlation_id'):
        delattr(_thread_local, 'correlation_id')


def generate_correlation_id(prefix: str = '') -> str:
    """
    Generate a new correlation ID

    Args:
        prefix: Optional prefix for the ID

    Returns:
        Generated correlation ID
    """
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    if prefix:
        return f"{prefix}-{timestamp}-{unique_id}"
    return f"{timestamp}-{unique_id}"


# ==============================================
# Logger Factory
# ==============================================

def get_logger(
    name: str,
    level: Optional[int] = None,
    json_format: Optional[bool] = None,
    **context
) -> logging.Logger:
    """
    Get configured logger with structured formatting

    Args:
        name: Logger name (usually __name__)
        level: Logging level (default: INFO)
        json_format: Use JSON format (default: from env LOG_FORMAT=json)
        **context: Default context fields (agent, ticket_key, etc.)

    Returns:
        Configured logger instance (StructuredLogger if context provided)

    Examples:
        # Basic logger
        logger = get_logger(__name__)
        logger.info("Simple message")

        # Logger with context
        logger = get_logger(__name__, agent='TestAgent', ticket_key='JIRA-123')
        logger.info("Contextual message")

        # JSON format
        logger = get_logger(__name__, json_format=True)
        logger.info("JSON output")
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        # Console handler
        handler = logging.StreamHandler(sys.stdout)

        # Determine format from environment or parameter
        if json_format is None:
            json_format = os.environ.get('LOG_FORMAT', 'text').lower() == 'json'

        # Use structured formatter
        formatter = StructuredFormatter(json_format=json_format)

        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level or logging.INFO)
        logger.propagate = False

    # Return structured logger if context provided
    if context:
        return StructuredLogger(logger, context)

    return logger


# ==============================================
# Convenience Functions
# ==============================================

def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **context
):
    """
    Log message with context fields

    Args:
        logger: Logger instance
        level: Log level (logging.INFO, logging.ERROR, etc.)
        message: Log message
        **context: Context fields to add

    Example:
        log_with_context(
            logger,
            logging.INFO,
            "Processing started",
            agent='TestAgent',
            ticket_key='JIRA-123',
            execution_id='exec-001'
        )
    """
    logger.log(level, message, extra=context)


# ==============================================
# Performance Tracking
# ==============================================

import time
import functools


class PerformanceTimer:
    """
    Context manager for timing operations and logging duration

    Usage:
        with PerformanceTimer(logger, "operation_name", ticket_key="PROJ-123"):
            # ... operation code
    """

    def __init__(
        self,
        logger: logging.Logger,
        operation: str,
        log_level: int = logging.INFO,
        **context
    ):
        """
        Initialize performance timer

        Args:
            logger: Logger instance
            operation: Operation name
            log_level: Log level for duration message
            **context: Additional context fields
        """
        self.logger = logger
        self.operation = operation
        self.log_level = log_level
        self.context = context
        self.start_time = None
        self.duration_ms = None

    def __enter__(self):
        """Start timing"""
        self.start_time = time.time()
        self.logger.debug(
            f"Starting {self.operation}",
            extra={'operation': self.operation, **self.context}
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and log duration"""
        self.duration_ms = int((time.time() - self.start_time) * 1000)

        if exc_type is None:
            # Success
            self.logger.log(
                self.log_level,
                f"✓ {self.operation} completed in {self.duration_ms}ms",
                extra={
                    'operation': self.operation,
                    'duration_ms': self.duration_ms,
                    'success': True,
                    **self.context
                }
            )
        else:
            # Error occurred
            self.logger.error(
                f"✗ {self.operation} failed after {self.duration_ms}ms: {exc_val}",
                extra={
                    'operation': self.operation,
                    'duration_ms': self.duration_ms,
                    'success': False,
                    'error': str(exc_val),
                    **self.context
                }
            )
        return False  # Don't suppress exception

    def get_duration(self) -> Optional[int]:
        """Get duration in milliseconds"""
        return self.duration_ms


def log_performance(operation: str, log_level: int = logging.INFO, **context):
    """
    Decorator for logging function execution time

    Args:
        operation: Operation name
        log_level: Log level for duration message
        **context: Additional context fields

    Example:
        @log_performance("generate_tests", ticket_key="PROJ-123")
        def generate_tests(scenarios):
            # ... generation logic
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Try to get logger from self if method, otherwise use module logger
            logger_instance = None
            if args and hasattr(args[0], 'logger'):
                logger_instance = args[0].logger
            else:
                logger_instance = logging.getLogger(func.__module__)

            with PerformanceTimer(logger_instance, operation, log_level, **context):
                return func(*args, **kwargs)

        return wrapper
    return decorator


# ==============================================
# Stage Progress Tracking
# ==============================================

class StageProgressTracker:
    """
    Helper for tracking and logging workflow stage progress

    Usage:
        tracker = StageProgressTracker(logger, "test_generation", total_steps=5)
        tracker.start()
        tracker.step("Extracting locators", progress=20)
        tracker.step("Generating code", progress=40)
        # ...
        tracker.complete()
    """

    def __init__(
        self,
        logger: logging.Logger,
        stage: str,
        total_steps: int = 100,
        **context
    ):
        """
        Initialize stage progress tracker

        Args:
            logger: Logger instance
            stage: Stage name
            total_steps: Total number of steps (for progress calculation)
            **context: Additional context fields
        """
        self.logger = logger
        self.stage = stage
        self.total_steps = total_steps
        self.context = context
        self.current_step = 0
        self.start_time = None

    def start(self, message: str = None):
        """Start tracking stage"""
        self.start_time = time.time()
        msg = message or f"Starting {self.stage}"
        self.logger.info(
            msg,
            extra={
                'stage': self.stage,
                'progress': 0,
                'status': 'processing',
                **self.context
            }
        )

    def step(self, message: str, progress: Optional[int] = None):
        """
        Log a step in the stage

        Args:
            message: Step description
            progress: Optional explicit progress (0-100), otherwise auto-calculated
        """
        self.current_step += 1

        if progress is None:
            progress = int((self.current_step / self.total_steps) * 100)

        self.logger.info(
            message,
            extra={
                'stage': self.stage,
                'progress': min(progress, 99),  # Never show 100% until complete
                'status': 'processing',
                'step': self.current_step,
                **self.context
            }
        )

    def complete(self, message: str = None):
        """Complete stage tracking"""
        duration_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0
        msg = message or f"✓ {self.stage} completed"

        self.logger.info(
            msg,
            extra={
                'stage': self.stage,
                'progress': 100,
                'status': 'completed',
                'duration_ms': duration_ms,
                **self.context
            }
        )

    def error(self, message: str, error: Exception = None):
        """Mark stage as failed"""
        duration_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0
        error_msg = f"✗ {message}"

        self.logger.error(
            error_msg,
            exc_info=error is not None,
            extra={
                'stage': self.stage,
                'progress': 100,
                'status': 'error',
                'duration_ms': duration_ms,
                'error': str(error) if error else None,
                **self.context
            }
        )


# ==============================================
# Cache Logging Utilities
# ==============================================

def log_cache_operation(
    logger: logging.Logger,
    operation: str,
    cache_key: str,
    hit: bool,
    time_saved_seconds: Optional[int] = None,
    **context
):
    """
    Log cache operation (hit/miss) consistently

    Args:
        logger: Logger instance
        operation: Operation description
        cache_key: Cache key used
        hit: Whether cache was hit
        time_saved_seconds: Estimated time saved by cache hit
        **context: Additional context fields

    Example:
        log_cache_operation(
            logger,
            "locator extraction",
            cache_key="repo-abc123",
            hit=True,
            time_saved_seconds=60
        )
    """
    if hit:
        msg = f"✓ Cache hit for {operation}"
        if time_saved_seconds:
            msg += f" - saved ~{time_saved_seconds}s"
    else:
        msg = f"Cache miss for {operation} - fetching fresh data"

    logger.info(
        msg,
        extra={
            'operation': operation,
            'cache_key': cache_key,
            'cache_hit': hit,
            'time_saved_seconds': time_saved_seconds,
            **context
        }
    )


# ==============================================
# Error Code Management
# ==============================================

class ErrorCodeRegistry:
    """
    Registry for standardized error codes

    Categories:
    - ERR_JIRA_* : Jira client errors
    - ERR_GITHUB_* : GitHub client errors
    - ERR_GEN_* : Test generation errors
    - ERR_EXEC_* : Test execution errors
    - ERR_CONFIG_* : Configuration errors
    """

    # Jira errors
    ERR_JIRA_FETCH = "ERR_JIRA_001"
    ERR_JIRA_NOT_FOUND = "ERR_JIRA_002"
    ERR_JIRA_COMMENT = "ERR_JIRA_003"
    ERR_JIRA_ATTACH = "ERR_JIRA_004"
    ERR_JIRA_FORMAT = "ERR_JIRA_005"

    # GitHub errors
    ERR_GITHUB_BRANCH = "ERR_GITHUB_001"
    ERR_GITHUB_COMMIT = "ERR_GITHUB_002"
    ERR_GITHUB_PR = "ERR_GITHUB_003"
    ERR_GITHUB_NOT_FOUND = "ERR_GITHUB_004"
    ERR_GITHUB_AUTH = "ERR_GITHUB_005"

    # Generation errors
    ERR_GEN_FAILED = "ERR_GEN_001"
    ERR_GEN_PLAN = "ERR_GEN_002"
    ERR_GEN_CODE = "ERR_GEN_003"
    ERR_GEN_LOCATOR = "ERR_GEN_004"
    ERR_GEN_COVERAGE = "ERR_GEN_005"

    # Execution errors
    ERR_EXEC_FAILED = "ERR_EXEC_001"
    ERR_EXEC_ENV = "ERR_EXEC_002"
    ERR_EXEC_TIMEOUT = "ERR_EXEC_003"
    ERR_EXEC_PLAYWRIGHT = "ERR_EXEC_004"
    ERR_EXEC_SETUP = "ERR_EXEC_005"

    # Configuration errors
    ERR_CONFIG_MISSING = "ERR_CONFIG_001"
    ERR_CONFIG_INVALID = "ERR_CONFIG_002"
    ERR_CONFIG_CLIENT = "ERR_CONFIG_003"
    ERR_CONFIG_ENV = "ERR_CONFIG_004"

    @classmethod
    def get_description(cls, error_code: str) -> str:
        """Get human-readable description for error code"""
        descriptions = {
            cls.ERR_JIRA_FETCH: "Failed to fetch Jira ticket",
            cls.ERR_JIRA_NOT_FOUND: "Jira ticket not found",
            cls.ERR_JIRA_COMMENT: "Failed to add Jira comment",
            cls.ERR_JIRA_ATTACH: "Failed to attach file to Jira",
            cls.ERR_JIRA_FORMAT: "Invalid Jira ticket format",
            cls.ERR_GITHUB_BRANCH: "Failed to create GitHub branch",
            cls.ERR_GITHUB_COMMIT: "Failed to commit to GitHub",
            cls.ERR_GITHUB_PR: "Failed to create GitHub PR",
            cls.ERR_GITHUB_NOT_FOUND: "GitHub repository not found",
            cls.ERR_GITHUB_AUTH: "GitHub authentication failed",
            cls.ERR_GEN_FAILED: "Test generation failed",
            cls.ERR_GEN_PLAN: "Invalid test plan",
            cls.ERR_GEN_CODE: "Code generation failed",
            cls.ERR_GEN_LOCATOR: "Locator extraction failed",
            cls.ERR_GEN_COVERAGE: "Insufficient test coverage",
            cls.ERR_EXEC_FAILED: "Test execution failed",
            cls.ERR_EXEC_ENV: "Test environment unavailable",
            cls.ERR_EXEC_TIMEOUT: "Test execution timeout",
            cls.ERR_EXEC_PLAYWRIGHT: "Playwright error",
            cls.ERR_EXEC_SETUP: "Test setup failed",
            cls.ERR_CONFIG_MISSING: "Missing required configuration",
            cls.ERR_CONFIG_INVALID: "Invalid configuration value",
            cls.ERR_CONFIG_CLIENT: "Client initialization failed",
            cls.ERR_CONFIG_ENV: "Environment variable missing",
        }
        return descriptions.get(error_code, "Unknown error")


def log_error_with_code(
    logger: logging.Logger,
    error_code: str,
    message: str,
    exception: Optional[Exception] = None,
    **context
):
    """
    Log error with standardized error code

    Args:
        logger: Logger instance
        error_code: Error code from ErrorCodeRegistry
        message: Error message
        exception: Optional exception object
        **context: Additional context fields

    Example:
        log_error_with_code(
            logger,
            ErrorCodeRegistry.ERR_GEN_FAILED,
            "Failed to generate tests",
            exception=e,
            ticket_key="PROJ-123"
        )
    """
    error_description = ErrorCodeRegistry.get_description(error_code)
    full_message = f"[{error_code}] {message}"

    logger.error(
        full_message,
        exc_info=exception is not None,
        extra={
            'error_code': error_code,
            'error_description': error_description,
            'error_type': type(exception).__name__ if exception else None,
            **context
        }
    )