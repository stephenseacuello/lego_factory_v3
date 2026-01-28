"""
LEGO Factory v3 - Demo Mode Configuration
==========================================

Controls demo mode behavior for API endpoints.

WARNING: DEMO_MODE should NEVER be enabled in production environments.
When DEMO_MODE is True, API endpoints may return fake/demo data instead
of failing properly when services are unavailable. This can mask real
issues and lead to incorrect operational decisions.

Usage:
    from config.demo_mode import is_demo_mode_enabled

    if is_demo_mode_enabled():
        return demo_data()
    else:
        raise ServiceUnavailableError("Database connection failed")
"""

import os
import warnings
import logging

logger = logging.getLogger(__name__)

# DEMO_MODE: When True, allows endpoints to return demo data when services fail.
# This should ONLY be used in development/testing environments.
# Default: False (disabled)
DEMO_MODE = os.getenv('DEMO_MODE', 'false').lower() == 'true'

# Track if we've already warned about demo mode
_warned_about_demo_mode = False


def is_demo_mode_enabled() -> bool:
    """
    Check if demo mode is enabled.

    Returns True only if DEMO_MODE environment variable is explicitly set to 'true'.
    In production environments (FLASK_ENV=production), demo mode is ALWAYS disabled
    regardless of the DEMO_MODE setting, and an error is logged.

    Returns:
        bool: True if demo mode is enabled and allowed, False otherwise.
    """
    global _warned_about_demo_mode

    env = os.getenv('FLASK_ENV', 'development')

    # Never allow demo mode in production - this is a safety guard
    if env == 'production':
        if DEMO_MODE and not _warned_about_demo_mode:
            logger.error(
                "DEMO_MODE is set to True but FLASK_ENV is 'production'. "
                "Demo mode is DISABLED for safety. Remove DEMO_MODE=true from production config."
            )
            _warned_about_demo_mode = True
        return False

    # In development/testing, respect the DEMO_MODE setting but warn
    if DEMO_MODE and not _warned_about_demo_mode:
        warnings.warn(
            "DEMO_MODE is enabled. API endpoints may return fake data when services fail. "
            "This setting should NEVER be used in production.",
            UserWarning,
            stacklevel=2
        )
        logger.warning(
            "DEMO_MODE is enabled. API endpoints may return fake data when services fail."
        )
        _warned_about_demo_mode = True

    return DEMO_MODE


def require_demo_mode(func):
    """
    Decorator that only executes a function if demo mode is enabled.

    Usage:
        @require_demo_mode
        def get_demo_data():
            return {"demo": True, "data": [...]}
    """
    def wrapper(*args, **kwargs):
        if not is_demo_mode_enabled():
            return None
        return func(*args, **kwargs)
    return wrapper
