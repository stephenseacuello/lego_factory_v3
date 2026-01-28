"""
LEGO Factory v3 - Logging Configuration
========================================
Structured JSON logging for production and human-readable logging for development.
"""

import logging
import os
import sys
import threading
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pythonjsonlogger import jsonlogger


# Context variables for request-scoped data
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
request_path_var: ContextVar[Optional[str]] = ContextVar('request_path', default=None)
request_method_var: ContextVar[Optional[str]] = ContextVar('request_method', default=None)


# Sensitive fields to redact in logs
SENSITIVE_FIELDS = frozenset({
    'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
    'api-key', 'authorization', 'auth', 'credentials', 'credit_card',
    'creditcard', 'card_number', 'cvv', 'ssn', 'social_security',
    'private_key', 'privatekey', 'secret_key', 'secretkey', 'access_token',
    'refresh_token', 'jwt', 'session_id', 'sessionid', 'cookie',
})


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set the request ID in context."""
    request_id_var.set(request_id)


def get_user_id() -> Optional[str]:
    """Get the current user ID from context."""
    return user_id_var.get()


def set_user_id(user_id: str) -> None:
    """Set the user ID in context."""
    user_id_var.set(user_id)


def set_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    path: Optional[str] = None,
    method: Optional[str] = None
) -> str:
    """
    Set request context for structured logging.

    Returns the request_id (generated if not provided).
    """
    rid = request_id or generate_request_id()
    request_id_var.set(rid)
    if user_id:
        user_id_var.set(user_id)
    if path:
        request_path_var.set(path)
    if method:
        request_method_var.set(method)
    return rid


def clear_request_context() -> None:
    """Clear the request context after request completion."""
    request_id_var.set(None)
    user_id_var.set(None)
    request_path_var.set(None)
    request_method_var.set(None)


def redact_sensitive_data(data: Any, depth: int = 0, max_depth: int = 10) -> Any:
    """
    Recursively redact sensitive fields from data structures.

    Args:
        data: The data to redact
        depth: Current recursion depth
        max_depth: Maximum recursion depth to prevent infinite loops

    Returns:
        Data with sensitive fields redacted
    """
    if depth > max_depth:
        return '[MAX_DEPTH_EXCEEDED]'

    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            key_lower = key.lower().replace('-', '_').replace(' ', '_')
            if key_lower in SENSITIVE_FIELDS:
                result[key] = '[REDACTED]'
            else:
                result[key] = redact_sensitive_data(value, depth + 1, max_depth)
        return result
    elif isinstance(data, (list, tuple)):
        return [redact_sensitive_data(item, depth + 1, max_depth) for item in data]
    else:
        return data


class ContextInjectingFilter(logging.Filter):
    """
    Logging filter that injects context variables into log records.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context variables to the log record."""
        record.request_id = get_request_id()
        record.user_id = get_user_id()
        record.request_path = request_path_var.get()
        record.request_method = request_method_var.get()
        record.thread_name = threading.current_thread().name
        return True


class ProductionJsonFormatter(jsonlogger.JsonFormatter):
    """
    Production-ready JSON formatter with additional context fields.

    Outputs structured JSON logs suitable for log aggregation systems
    like ELK, Splunk, or cloud logging services.
    """

    def __init__(self, *args, **kwargs):
        # Define the format with standard fields
        fmt = '%(timestamp)s %(level)s %(name)s %(message)s'
        super().__init__(fmt, *args, **kwargs)
        self.service_name = os.getenv('SERVICE_NAME', 'lego-factory')
        self.service_version = os.getenv('SERVICE_VERSION', '3.0.0')
        self.environment = os.getenv('FLASK_ENV', 'production')

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any]
    ) -> None:
        """Add custom fields to the JSON log record."""
        super().add_fields(log_record, record, message_dict)

        # Standard fields
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name

        # Service identification
        log_record['service'] = self.service_name
        log_record['version'] = self.service_version
        log_record['environment'] = self.environment

        # Context fields (from ContextInjectingFilter)
        if hasattr(record, 'request_id') and record.request_id:
            log_record['request_id'] = record.request_id
        if hasattr(record, 'user_id') and record.user_id:
            log_record['user_id'] = record.user_id
        if hasattr(record, 'request_path') and record.request_path:
            log_record['path'] = record.request_path
        if hasattr(record, 'request_method') and record.request_method:
            log_record['method'] = record.request_method
        if hasattr(record, 'thread_name'):
            log_record['thread'] = record.thread_name

        # Source location
        log_record['source'] = {
            'file': record.pathname,
            'line': record.lineno,
            'function': record.funcName
        }

        # Exception info if present
        if record.exc_info:
            log_record['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
            }

        # Remove the default 'message' key if we have 'msg'
        if 'message' in log_record and log_record.get('message') == log_record.get('msg'):
            log_record.pop('msg', None)


class DevelopmentFormatter(logging.Formatter):
    """
    Human-readable formatter for development environments.

    Includes colors for different log levels when outputting to a terminal.
    """

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record for human readability."""
        # Build the timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        # Get context info
        request_id = getattr(record, 'request_id', None)
        user_id = getattr(record, 'user_id', None)

        # Build context string
        context_parts = []
        if request_id:
            context_parts.append(f'req={request_id[:8]}')
        if user_id:
            context_parts.append(f'user={user_id}')
        context_str = f' [{", ".join(context_parts)}]' if context_parts else ''

        # Build the message
        level = record.levelname
        name = record.name

        # Truncate logger name for readability
        if len(name) > 30:
            parts = name.split('.')
            if len(parts) > 2:
                name = f'{parts[0]}...{parts[-1]}'

        message = record.getMessage()

        if self.use_colors:
            color = self.COLORS.get(level, '')
            formatted = (
                f'{timestamp} {color}{self.BOLD}{level:8}{self.RESET} '
                f'{name:30}{context_str} - {message}'
            )
        else:
            formatted = f'{timestamp} {level:8} {name:30}{context_str} - {message}'

        # Add exception info if present
        if record.exc_info:
            formatted += '\n' + self.formatException(record.exc_info)

        return formatted


class StructuredLogger(logging.LoggerAdapter):
    """
    Logger adapter that allows adding structured context to log messages.

    Usage:
        logger = get_structured_logger(__name__)
        logger.info("User logged in", extra={'user_id': '123', 'ip': '192.168.1.1'})
    """

    def __init__(self, logger: logging.Logger, extra: Optional[Dict[str, Any]] = None):
        super().__init__(logger, extra or {})

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process the logging call to add extra context."""
        extra = kwargs.get('extra', {})

        # Merge adapter's extra with call's extra
        combined_extra = {**self.extra, **extra}

        # Add timing info if present
        if 'duration_ms' in combined_extra:
            combined_extra['duration_ms'] = round(combined_extra['duration_ms'], 2)

        kwargs['extra'] = combined_extra
        return msg, kwargs

    def with_context(self, **context) -> 'StructuredLogger':
        """Create a new logger with additional context."""
        new_extra = {**self.extra, **context}
        return StructuredLogger(self.logger, new_extra)


def get_structured_logger(name: str, **initial_context) -> StructuredLogger:
    """
    Get a structured logger for the given module.

    Args:
        name: The module name (usually __name__)
        **initial_context: Initial context to include in all log messages

    Returns:
        A StructuredLogger instance
    """
    logger = logging.getLogger(name)
    return StructuredLogger(logger, initial_context)


def configure_logging(
    level: str = 'INFO',
    json_output: bool = False,
    log_to_file: Optional[str] = None
) -> None:
    """
    Configure application-wide logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, use JSON formatter (for production)
        log_to_file: Optional file path to also log to
    """
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create the context filter
    context_filter = ContextInjectingFilter()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG)
    console_handler.addFilter(context_filter)

    # Set formatter based on environment
    if json_output:
        console_handler.setFormatter(ProductionJsonFormatter())
    else:
        console_handler.setFormatter(DevelopmentFormatter())

    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_to_file:
        file_handler = logging.FileHandler(log_to_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.addFilter(context_filter)
        # Always use JSON for file logging
        file_handler.setFormatter(ProductionJsonFormatter())
        root_logger.addHandler(file_handler)

    # Configure specific loggers to reduce noise
    noisy_loggers = [
        'werkzeug',
        'sqlalchemy',
        'urllib3',
        'engineio',
        'socketio',
        'eventlet',
        'gevent',
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Log startup message
    root_logger.info(
        f"Logging configured: level={level}, json={json_output}",
        extra={'event': 'logging_configured'}
    )


def configure_for_flask(app) -> None:
    """
    Configure logging specifically for a Flask application.

    This should be called during app factory setup.

    Args:
        app: The Flask application instance
    """
    from config.settings import get_config

    config = get_config()

    # Determine if we should use JSON output
    is_production = config.env == 'production'
    json_output = is_production or os.getenv('LOG_JSON', 'false').lower() == 'true'

    # Get log level from config
    log_level = config.logging.level

    # Configure logging
    configure_logging(
        level=log_level,
        json_output=json_output,
        log_to_file=os.getenv('LOG_FILE')
    )

    # Configure SocketIO logging based on environment
    socketio_logger = logging.getLogger('socketio')
    engineio_logger = logging.getLogger('engineio')

    if is_production:
        # In production, keep socketio logs at WARNING level with JSON format
        socketio_logger.setLevel(logging.WARNING)
        engineio_logger.setLevel(logging.WARNING)
    else:
        # In development, enable more verbose socketio logging
        socketio_logger.setLevel(logging.INFO)
        engineio_logger.setLevel(logging.WARNING)

    # Store logging state on app
    app.config['LOGGING_JSON_OUTPUT'] = json_output
    app.config['LOGGING_LEVEL'] = log_level


# Utility functions for common logging patterns

def log_operation_start(logger: logging.Logger, operation: str, **context) -> float:
    """
    Log the start of an operation and return the start time for duration calculation.

    Args:
        logger: The logger to use
        operation: Name of the operation
        **context: Additional context to log

    Returns:
        The start time (for use with log_operation_end)
    """
    import time
    start_time = time.perf_counter()
    logger.info(f"Starting {operation}", extra={'operation': operation, 'event': 'start', **context})
    return start_time


def log_operation_end(
    logger: logging.Logger,
    operation: str,
    start_time: float,
    success: bool = True,
    **context
) -> None:
    """
    Log the end of an operation with duration.

    Args:
        logger: The logger to use
        operation: Name of the operation
        start_time: The start time from log_operation_start
        success: Whether the operation succeeded
        **context: Additional context to log
    """
    import time
    duration_ms = (time.perf_counter() - start_time) * 1000

    extra = {
        'operation': operation,
        'event': 'end',
        'success': success,
        'duration_ms': round(duration_ms, 2),
        **context
    }

    if success:
        logger.info(f"Completed {operation} in {duration_ms:.2f}ms", extra=extra)
    else:
        logger.warning(f"Failed {operation} after {duration_ms:.2f}ms", extra=extra)
