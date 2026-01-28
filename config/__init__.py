"""
LEGO Factory v3 - Configuration Package
========================================
"""

from config.settings import (
    Config,
    ConfigurationError,
    get_config,
    init_config,
    reset_config,
    DatabaseConfig,
    RedisConfig,
    FlaskConfig,
    JWTConfig,
)

from config.validators import (
    validate_environment,
    EnvironmentValidator,
    ValidationResult,
    get_required_vars,
    check_single_var,
)

__all__ = [
    # Settings
    'Config',
    'ConfigurationError',
    'get_config',
    'init_config',
    'reset_config',
    'DatabaseConfig',
    'RedisConfig',
    'FlaskConfig',
    'JWTConfig',
    # Validators
    'validate_environment',
    'EnvironmentValidator',
    'ValidationResult',
    'get_required_vars',
    'check_single_var',
]
