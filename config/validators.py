"""
LEGO Factory v3 - Environment Variable Validators
===================================================
Validates that all required environment variables are set before application startup.
"""

import os
import sys
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of environment variable validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class EnvironmentValidator:
    """
    Validates environment variables for the LEGO Factory application.

    Usage:
        from config.validators import validate_environment

        # Call at application startup
        validate_environment()  # Raises ConfigurationError if validation fails in production
    """

    # Required variables that MUST be set in production
    REQUIRED_PRODUCTION_VARS: Dict[str, str] = {
        'SECRET_KEY': 'Application secret key for session management and CSRF protection',
        'POSTGRES_PASSWORD': 'PostgreSQL database password',
    }

    # Variables that should be set but have fallback defaults
    RECOMMENDED_VARS: Dict[str, str] = {
        'DATABASE_URL': 'Full database connection URL',
        'REDIS_URL': 'Redis connection URL',
        'JWT_SECRET_KEY': 'JWT authentication secret (falls back to SECRET_KEY)',
        'GF_SECURITY_ADMIN_PASSWORD': 'Grafana admin password',
    }

    # Variables that indicate insecure values when they contain these patterns
    INSECURE_PATTERNS = ['dev', 'test', 'change', 'secret', 'password', 'example', 'admin', 'default']

    # Variables that should be checked for insecure values
    SENSITIVE_VARS = ['SECRET_KEY', 'JWT_SECRET_KEY', 'POSTGRES_PASSWORD', 'GF_SECURITY_ADMIN_PASSWORD']

    @classmethod
    def validate(cls, strict: bool = False) -> ValidationResult:
        """
        Validate all environment variables.

        Args:
            strict: If True, treat warnings as errors

        Returns:
            ValidationResult with validation status, errors, and warnings
        """
        errors: List[str] = []
        warnings: List[str] = []
        env = os.getenv('FLASK_ENV', 'development')
        is_production = env == 'production'

        # Check required production variables
        for var, description in cls.REQUIRED_PRODUCTION_VARS.items():
            value = os.getenv(var)
            if not value:
                if is_production:
                    errors.append(
                        f"Missing required environment variable: {var}\n"
                        f"  Description: {description}\n"
                        f"  Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                    )
                else:
                    warnings.append(
                        f"Environment variable {var} not set (required in production)\n"
                        f"  Description: {description}"
                    )

        # Check recommended variables
        for var, description in cls.RECOMMENDED_VARS.items():
            value = os.getenv(var)
            if not value:
                warnings.append(
                    f"Recommended environment variable {var} not set\n"
                    f"  Description: {description}"
                )

        # Check for insecure values in sensitive variables
        for var in cls.SENSITIVE_VARS:
            value = os.getenv(var, '')
            if value:
                is_insecure = any(pattern in value.lower() for pattern in cls.INSECURE_PATTERNS)
                if is_insecure:
                    if is_production:
                        errors.append(
                            f"Insecure value detected for {var}\n"
                            f"  The value appears to be a development/example value.\n"
                            f"  Generate a secure value with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                        )
                    else:
                        warnings.append(
                            f"Potentially insecure value for {var}\n"
                            f"  Consider using a secure random value in production."
                        )

        # Check for minimum secret key length
        for var in ['SECRET_KEY', 'JWT_SECRET_KEY']:
            value = os.getenv(var, '')
            if value and len(value) < 32:
                if is_production:
                    errors.append(
                        f"{var} is too short (minimum 32 characters recommended)\n"
                        f"  Current length: {len(value)} characters\n"
                        f"  Generate a secure value with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                    )
                else:
                    warnings.append(
                        f"{var} is shorter than recommended (32+ characters)\n"
                        f"  Current length: {len(value)} characters"
                    )

        # In strict mode, treat warnings as errors
        if strict:
            errors.extend(warnings)
            warnings = []

        is_valid = len(errors) == 0
        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    @classmethod
    def print_validation_report(cls, result: ValidationResult) -> None:
        """Print a formatted validation report."""
        if result.errors:
            print("\n" + "=" * 60)
            print("ENVIRONMENT VALIDATION ERRORS")
            print("=" * 60)
            for i, error in enumerate(result.errors, 1):
                print(f"\n{i}. {error}")
            print("\n" + "=" * 60)

        if result.warnings:
            print("\n" + "-" * 60)
            print("ENVIRONMENT VALIDATION WARNINGS")
            print("-" * 60)
            for i, warning in enumerate(result.warnings, 1):
                print(f"\n{i}. {warning}")
            print("\n" + "-" * 60)

        if result.is_valid and not result.warnings:
            print("\nEnvironment validation passed successfully.")


def validate_environment(exit_on_error: bool = True, strict: bool = False) -> ValidationResult:
    """
    Validate environment variables at application startup.

    This function should be called early in the application startup process,
    before initializing Flask or connecting to databases.

    Args:
        exit_on_error: If True, exit the application if validation fails in production
        strict: If True, treat warnings as errors

    Returns:
        ValidationResult with validation status

    Raises:
        SystemExit: If validation fails and exit_on_error is True in production

    Example:
        # In app/__init__.py or app.py:
        from config.validators import validate_environment

        # Validate before creating the Flask app
        validation_result = validate_environment()

        # Continue with app initialization...
        app = Flask(__name__)
    """
    from config.settings import ConfigurationError

    result = EnvironmentValidator.validate(strict=strict)
    env = os.getenv('FLASK_ENV', 'development')
    is_production = env == 'production'

    if not result.is_valid:
        EnvironmentValidator.print_validation_report(result)
        if exit_on_error and is_production:
            print("\nApplication cannot start with missing or insecure configuration.")
            print("Please set the required environment variables and try again.")
            print("\nSee .env.example for a template of required variables.")
            sys.exit(1)
        elif is_production:
            raise ConfigurationError(
                "Environment validation failed. See validation report above."
            )
    elif result.warnings:
        EnvironmentValidator.print_validation_report(result)

    return result


def get_required_vars() -> Dict[str, str]:
    """
    Get a dictionary of all required environment variables and their descriptions.

    Useful for generating documentation or help text.
    """
    all_vars = {}
    all_vars.update(EnvironmentValidator.REQUIRED_PRODUCTION_VARS)
    all_vars.update(EnvironmentValidator.RECOMMENDED_VARS)
    return all_vars


def check_single_var(var_name: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a single environment variable is set and valid.

    Args:
        var_name: Name of the environment variable to check

    Returns:
        Tuple of (is_valid, error_message)
    """
    value = os.getenv(var_name)
    if not value:
        return False, f"Environment variable {var_name} is not set"

    if var_name in EnvironmentValidator.SENSITIVE_VARS:
        is_insecure = any(
            pattern in value.lower()
            for pattern in EnvironmentValidator.INSECURE_PATTERNS
        )
        if is_insecure:
            return False, f"Environment variable {var_name} appears to have an insecure value"

    return True, None
