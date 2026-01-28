"""
Input Validation Utilities for Flask CNC SCADA System
======================================================
Provides security-focused input validation for file paths, filenames,
and query parameters to prevent path traversal and injection attacks.

Security Features:
- Path traversal prevention
- Filename sanitization
- Query parameter validation
- Safe path joining within allowed directories

Usage:
    from api.utils.validation import sanitize_filename, safe_path_join, validate_in_directory

    # Sanitize user-provided filename
    safe_name = sanitize_filename("../../../etc/passwd.nc")  # Returns "etc_passwd.nc"

    # Safely join paths within allowed directory
    filepath = safe_path_join("/data/gcode", user_filename)

    # Validate file is within allowed directory
    if not validate_in_directory(filepath, "/data/gcode"):
        raise SecurityError("Access denied")
"""

import os
import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks.

    Removes:
    - Directory separators (/ and \\)
    - Parent directory references (..)
    - Current directory references (.)
    - Control characters
    - Leading/trailing whitespace

    Args:
        filename: User-provided filename

    Returns:
        Sanitized filename safe for file system use
    """
    if not filename:
        return "unnamed"

    # Get just the base filename (remove any directory components)
    filename = os.path.basename(filename)

    # Remove any remaining path traversal attempts
    filename = filename.replace('..', '')
    filename = filename.replace('/', '')
    filename = filename.replace('\\', '')

    # Replace unsafe characters with underscore
    # Allow only alphanumeric, dash, underscore, and dot
    filename = re.sub(r'[^\w\-_.]', '_', filename)

    # Remove leading dots (hidden files) except for the extension
    while filename.startswith('.') and len(filename) > 1:
        filename = filename[1:]

    # Collapse multiple underscores/dots
    filename = re.sub(r'_+', '_', filename)
    filename = re.sub(r'\.+', '.', filename)

    # Remove leading/trailing underscores and whitespace
    filename = filename.strip('_ ')

    # Ensure filename is not empty after sanitization
    if not filename or filename == '.':
        return "unnamed"

    # Limit length
    max_length = 255
    if len(filename) > max_length:
        # Preserve extension
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext

    return filename


def safe_path_join(base_dir: str, *paths: str) -> Optional[str]:
    """
    Safely join paths ensuring result stays within base directory.

    Prevents path traversal by:
    1. Sanitizing each path component
    2. Resolving to absolute path
    3. Verifying result is within base_dir

    Args:
        base_dir: Allowed base directory (absolute path)
        *paths: Path components to join (will be sanitized)

    Returns:
        Safe absolute path within base_dir, or None if path escapes
    """
    # Resolve base directory to absolute path
    base_dir = os.path.abspath(base_dir)

    # Sanitize each path component
    safe_paths = [sanitize_filename(p) for p in paths if p]

    if not safe_paths:
        return base_dir

    # Join and resolve
    joined = os.path.join(base_dir, *safe_paths)
    resolved = os.path.abspath(joined)

    # Verify path is within base directory
    if not resolved.startswith(base_dir + os.sep) and resolved != base_dir:
        logger.warning(f"Path traversal attempt blocked: {paths} -> {resolved}")
        return None

    return resolved


def validate_in_directory(filepath: str, allowed_dir: str) -> bool:
    """
    Validate that a filepath is within an allowed directory.

    Args:
        filepath: Path to validate
        allowed_dir: Allowed base directory

    Returns:
        True if filepath is within allowed_dir, False otherwise
    """
    # Resolve both paths to absolute
    filepath = os.path.abspath(filepath)
    allowed_dir = os.path.abspath(allowed_dir)

    # Check if filepath starts with allowed_dir
    return filepath.startswith(allowed_dir + os.sep) or filepath == allowed_dir


def validate_query_param(
    value: str,
    param_name: str,
    max_length: int = 1000,
    allowed_pattern: Optional[str] = None,
    allow_empty: bool = False
) -> Tuple[bool, str, str]:
    """
    Validate a query parameter.

    Args:
        value: Parameter value to validate
        param_name: Name of parameter (for error messages)
        max_length: Maximum allowed length
        allowed_pattern: Optional regex pattern to match
        allow_empty: Whether empty values are allowed

    Returns:
        Tuple of (is_valid, sanitized_value, error_message)
    """
    # Check for None
    if value is None:
        if allow_empty:
            return True, "", ""
        return False, "", f"{param_name} is required"

    # Convert to string
    value = str(value).strip()

    # Check empty
    if not value and not allow_empty:
        return False, "", f"{param_name} cannot be empty"

    # Check length
    if len(value) > max_length:
        return False, "", f"{param_name} exceeds maximum length of {max_length}"

    # Check pattern if provided
    if allowed_pattern and not re.match(allowed_pattern, value):
        return False, "", f"{param_name} contains invalid characters"

    # Basic sanitization - remove control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)

    return True, sanitized, ""


def validate_uuid(value: str, param_name: str = "ID") -> Tuple[bool, str]:
    """
    Validate a UUID string.

    Args:
        value: String to validate as UUID
        param_name: Name for error messages

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value:
        return False, f"{param_name} is required"

    # UUID pattern: 8-4-4-4-12 hex digits
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'

    if not re.match(uuid_pattern, value.lower()):
        return False, f"Invalid {param_name} format"

    return True, ""


def validate_session_id(session_id: str) -> Tuple[bool, str, str]:
    """
    Validate and sanitize a session identifier.

    Session IDs should be alphanumeric with underscores, dashes, and dots.
    Used for sensor session files, etc.

    Args:
        session_id: Session identifier to validate

    Returns:
        Tuple of (is_valid, sanitized_value, error_message)
    """
    if not session_id:
        return False, "", "Session ID is required"

    # Allow alphanumeric, underscore, dash, dot
    pattern = r'^[\w\-_.]+$'

    if not re.match(pattern, session_id):
        return False, "", "Session ID contains invalid characters"

    if len(session_id) > 255:
        return False, "", "Session ID too long"

    # Sanitize any remaining issues
    sanitized = sanitize_filename(session_id)

    return True, sanitized, ""
