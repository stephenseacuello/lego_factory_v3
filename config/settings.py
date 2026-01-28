"""
LEGO Factory v3 - Configuration Settings
=========================================
Centralized configuration for all modules.
"""

import os
import logging
import warnings
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Minimum required length for secret keys
MIN_SECRET_KEY_LENGTH = 32

# Placeholder patterns that indicate insecure configuration
PLACEHOLDER_PATTERNS = ['CHANGE_ME', 'changeme', 'placeholder', 'your-secret-here']


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


def _is_production() -> bool:
    """Check if running in production environment."""
    return os.getenv('FLASK_ENV', 'development') == 'production'


def _is_demo_mode() -> bool:
    """
    Check if running in demo mode.

    Demo mode allows insecure defaults for demonstration/development purposes.
    In production with DEMO_MODE=false (default), placeholder secrets will cause
    the application to fail fast with clear error messages.

    Environment Variables:
        DEMO_MODE: Set to 'true' to enable demo mode (default: 'false')
    """
    return os.getenv('DEMO_MODE', 'false').lower() in ('true', '1', 'yes')


def _has_placeholder_value(value: str) -> bool:
    """Check if a value contains a placeholder pattern."""
    if not value:
        return True
    return any(pattern.lower() in value.lower() for pattern in PLACEHOLDER_PATTERNS)


def _get_secret_key() -> str:
    """
    Get the SECRET_KEY from environment.

    In production (DEMO_MODE=false), this MUST be set to a secure random value.
    In demo mode or development, a warning is issued if using the fallback.

    Environment Variables:
        SECRET_KEY: The application secret key
        DEMO_MODE: Set to 'true' to allow insecure defaults
    """
    secret_key = os.getenv('SECRET_KEY', '')
    is_production = _is_production()
    is_demo = _is_demo_mode()

    # Check for empty or placeholder values
    if _has_placeholder_value(secret_key):
        if is_production and not is_demo:
            raise ConfigurationError(
                "SECRET_KEY environment variable is required in production. "
                "Generate one with: python scripts/generate_secrets.py\n"
                "Or set DEMO_MODE=true to use insecure defaults for demonstration."
            )
        # Development/demo fallback with warning
        if is_demo:
            warnings.warn(
                "DEMO_MODE is enabled - using insecure SECRET_KEY. "
                "Do NOT use in production!",
                RuntimeWarning
            )
        logger.warning(
            "SECRET_KEY not set or contains placeholder. "
            "Using insecure default for development/demo only."
        )
        return 'dev-only-insecure-key-do-not-use-in-production'

    # Check minimum length
    if len(secret_key) < MIN_SECRET_KEY_LENGTH:
        if is_production and not is_demo:
            raise ConfigurationError(
                f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters long. "
                "Generate a secure key with: python scripts/generate_secrets.py"
            )
        logger.warning(
            f"SECRET_KEY is shorter than recommended {MIN_SECRET_KEY_LENGTH} characters."
        )

    # Warn if using obviously insecure keys
    insecure_patterns = ['dev', 'test', 'secret', 'password', 'example']
    if any(pattern in secret_key.lower() for pattern in insecure_patterns):
        if is_production and not is_demo:
            raise ConfigurationError(
                "SECRET_KEY appears to be insecure for production use. "
                "Generate a secure key with: python scripts/generate_secrets.py"
            )
        logger.warning(
            "SECRET_KEY appears to be a development/example value. "
            "Use a secure random key in production."
        )

    return secret_key


def _get_jwt_secret_key() -> str:
    """
    Get the JWT_SECRET_KEY from environment.

    In production (DEMO_MODE=false), this MUST be set to a secure random value.
    In demo mode or development, falls back to a development-only key with warning.

    Environment Variables:
        JWT_SECRET_KEY: The JWT signing secret key
        DEMO_MODE: Set to 'true' to allow insecure defaults
    """
    jwt_secret = os.getenv('JWT_SECRET_KEY', '')
    is_production = _is_production()
    is_demo = _is_demo_mode()

    # Check for empty or placeholder values
    if _has_placeholder_value(jwt_secret):
        if is_production and not is_demo:
            raise ConfigurationError(
                "JWT_SECRET_KEY must be set in production. "
                "Generate one with: python scripts/generate_secrets.py\n"
                "Or set DEMO_MODE=true to use insecure defaults for demonstration."
            )
        if is_demo:
            warnings.warn(
                "DEMO_MODE is enabled - using insecure JWT_SECRET_KEY. "
                "Do NOT use in production!",
                RuntimeWarning
            )
        logger.warning(
            "JWT_SECRET_KEY not set or contains placeholder. "
            "Using insecure JWT secret in development/demo."
        )
        return 'dev-jwt-secret-key-do-not-use-in-production'

    # Check minimum length for security
    if len(jwt_secret) < MIN_SECRET_KEY_LENGTH:
        if is_production and not is_demo:
            raise ConfigurationError(
                f"JWT_SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters long. "
                "Generate a secure key with: python scripts/generate_secrets.py"
            )
        logger.warning(
            f"JWT_SECRET_KEY is shorter than recommended {MIN_SECRET_KEY_LENGTH} characters."
        )

    # Warn if using obviously insecure keys
    insecure_patterns = ['dev', 'test', 'secret', 'password', 'example']
    if any(pattern in jwt_secret.lower() for pattern in insecure_patterns):
        if is_production and not is_demo:
            raise ConfigurationError(
                "JWT_SECRET_KEY appears to be insecure for production use. "
                "Generate a secure key with: python scripts/generate_secrets.py"
            )
        logger.warning(
            "JWT_SECRET_KEY appears to be a development/example value. "
            "Use a secure random key in production."
        )

    return jwt_secret


@dataclass
class DatabaseConfig:
    """PostgreSQL + TimescaleDB configuration."""
    pool_size: int = int(os.getenv('DB_POOL_SIZE', '10'))
    max_overflow: int = int(os.getenv('DB_MAX_OVERFLOW', '20'))

    # Support DATABASE_URL or individual variables
    _database_url: Optional[str] = os.getenv('DATABASE_URL')
    host: str = os.getenv('DB_HOST', 'localhost')
    port: int = int(os.getenv('DB_PORT', '5432'))
    database: str = os.getenv('DB_NAME', 'lego_factory')
    username: str = os.getenv('DB_USER', 'postgres')
    password: str = os.getenv('DB_PASSWORD', '')

    @property
    def url(self) -> str:
        # Use DATABASE_URL if provided (Docker Compose)
        if self._database_url:
            return self._database_url
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def async_url(self) -> str:
        if self._database_url:
            return self._database_url.replace('postgresql://', 'postgresql+asyncpg://')
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    """Redis configuration for caching and pub/sub."""
    _redis_url: Optional[str] = os.getenv('REDIS_URL')
    host: str = os.getenv('REDIS_HOST', 'localhost')
    port: int = int(os.getenv('REDIS_PORT', '6379'))
    db: int = int(os.getenv('REDIS_DB', '0'))
    password: Optional[str] = os.getenv('REDIS_PASSWORD')

    @property
    def url(self) -> str:
        # Use REDIS_URL if provided (Docker Compose)
        if self._redis_url:
            return self._redis_url
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class HistorianConfig:
    """TimescaleDB historian configuration."""
    buffer_size: int = int(os.getenv('HISTORIAN_BUFFER_SIZE', '1000'))
    flush_interval_seconds: float = float(os.getenv('HISTORIAN_FLUSH_INTERVAL', '1.0'))
    compression_deviation: float = float(os.getenv('HISTORIAN_COMPRESSION_DEVIATION', '0.01'))
    compression_max_time_seconds: float = float(os.getenv('HISTORIAN_COMPRESSION_MAX_TIME', '60.0'))
    retention_raw_days: int = int(os.getenv('HISTORIAN_RETENTION_RAW_DAYS', '7'))
    retention_1min_days: int = int(os.getenv('HISTORIAN_RETENTION_1MIN_DAYS', '30'))
    retention_1hour_days: int = int(os.getenv('HISTORIAN_RETENTION_1HOUR_DAYS', '365'))
    chunk_time_interval: str = os.getenv('HISTORIAN_CHUNK_INTERVAL', '1 day')


@dataclass
class AlarmConfig:
    """ISA-18.2 alarm management configuration."""
    max_unacked_alarms: int = int(os.getenv('ALARM_MAX_UNACKED', '1000'))
    shelve_max_duration_hours: int = int(os.getenv('ALARM_SHELVE_MAX_HOURS', '24'))
    alarm_rate_limit_per_minute: int = int(os.getenv('ALARM_RATE_LIMIT', '100'))
    deadband_default_percent: float = float(os.getenv('ALARM_DEADBAND_PERCENT', '1.0'))


@dataclass
class MachineControlConfig:
    """Machine controller configuration."""
    default_baud_rate: int = int(os.getenv('MACHINE_BAUD_RATE', '115200'))
    connection_timeout: float = float(os.getenv('MACHINE_CONN_TIMEOUT', '10.0'))
    command_timeout: float = float(os.getenv('MACHINE_CMD_TIMEOUT', '5.0'))
    status_poll_interval: float = float(os.getenv('MACHINE_POLL_INTERVAL', '0.1'))


@dataclass
class ROS2Config:
    """ROS2 Jazzy configuration."""
    enabled: bool = os.getenv('ROS2_ENABLED', 'true').lower() == 'true'
    mqtt_host: str = os.getenv('ROS2_MQTT_HOST', 'localhost')
    mqtt_port: int = int(os.getenv('ROS2_MQTT_PORT', '1883'))
    mqtt_prefix: str = os.getenv('ROS2_MQTT_PREFIX', 'ros2_bridge')
    service_timeout: float = float(os.getenv('ROS2_SERVICE_TIMEOUT', '10.0'))
    action_timeout: float = float(os.getenv('ROS2_ACTION_TIMEOUT', '60.0'))
    rosbridge_port: int = int(os.getenv('ROSBRIDGE_PORT', '9090'))


@dataclass
class MLConfig:
    """ML fingerprinting configuration."""
    model_path: str = os.getenv('ML_MODEL_PATH', 'services/ml/checkpoints')
    vocab_path: str = os.getenv('ML_VOCAB_PATH', 'services/ml/dataset/vocabulary.json')
    inference_batch_size: int = int(os.getenv('ML_BATCH_SIZE', '32'))
    inference_device: str = os.getenv('ML_DEVICE', 'cpu')
    anomaly_threshold: float = float(os.getenv('ML_ANOMALY_THRESHOLD', '0.8'))


@dataclass
class LEGOConfig:
    """LEGO design service configuration."""
    slicer_host: str = os.getenv('SLICER_HOST', 'localhost')
    slicer_port: int = int(os.getenv('SLICER_PORT', '8766'))
    fusion360_host: str = os.getenv('FUSION360_HOST', 'localhost')
    fusion360_port: int = int(os.getenv('FUSION360_PORT', '8767'))
    brick_catalog_path: str = os.getenv('BRICK_CATALOG_PATH', 'services/lego/brick_catalog.json')


@dataclass
class UnityConfig:
    """Unity Digital Twin configuration."""
    websocket_port: int = int(os.getenv('UNITY_WS_PORT', '8765'))
    state_update_rate_hz: float = float(os.getenv('UNITY_UPDATE_RATE', '30.0'))


@dataclass
class MCPConfig:
    """MCP server configuration."""
    server_name: str = os.getenv('MCP_SERVER_NAME', 'lego-factory-v3')
    server_version: str = os.getenv('MCP_SERVER_VERSION', '3.0.0')


@dataclass
class JWTConfig:
    """JWT authentication configuration."""
    secret_key: str = field(default_factory=_get_jwt_secret_key)
    access_token_expires_minutes: int = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES_MINUTES', '15'))
    refresh_token_expires_days: int = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES_DAYS', '30'))
    algorithm: str = os.getenv('JWT_ALGORITHM', 'HS256')
    token_location: List[str] = field(default_factory=lambda: ['headers'])
    header_name: str = 'Authorization'
    header_type: str = 'Bearer'

    @property
    def access_token_expires(self):
        from datetime import timedelta
        return timedelta(minutes=self.access_token_expires_minutes)

    @property
    def refresh_token_expires(self):
        from datetime import timedelta
        return timedelta(days=self.refresh_token_expires_days)


@dataclass
class FlaskConfig:
    """Flask server configuration."""
    debug: bool = os.getenv('FLASK_DEBUG', 'false').lower() in ('true', '1', 'yes')
    secret_key: str = field(default_factory=_get_secret_key)
    host: str = os.getenv('FLASK_HOST', '0.0.0.0')
    port: int = int(os.getenv('FLASK_PORT', '5000'))


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = os.getenv('LOG_LEVEL', 'INFO')
    format: str = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@dataclass
class CircuitBreakerServiceConfig:
    """Configuration for a single circuit breaker."""
    fail_max: int
    reset_timeout: int
    exclude: List[str] = field(default_factory=list)

    def get_exclude_exceptions(self) -> List[type]:
        """Convert exception names to exception classes."""
        exceptions = []
        exception_map = {
            'ConnectionError': ConnectionError,
            'TimeoutError': TimeoutError,
            'KeyError': KeyError,
            'ValueError': ValueError,
            'OSError': OSError,
        }
        for exc_name in self.exclude:
            if exc_name in exception_map:
                exceptions.append(exception_map[exc_name])
        return exceptions


@dataclass
class CircuitBreakerConfig:
    """
    Circuit breaker configuration for all services.

    Environment Variables:
        CB_REDIS_FAIL_MAX: Max failures before Redis circuit opens (default: 5)
        CB_REDIS_RESET_TIMEOUT: Seconds before Redis circuit resets (default: 30)
        CB_MQTT_FAIL_MAX: Max failures before MQTT circuit opens (default: 3)
        CB_MQTT_RESET_TIMEOUT: Seconds before MQTT circuit resets (default: 60)
        CB_DATABASE_FAIL_MAX: Max failures before Database circuit opens (default: 5)
        CB_DATABASE_RESET_TIMEOUT: Seconds before Database circuit resets (default: 30)
        CB_EXTERNAL_API_FAIL_MAX: Max failures before External API circuit opens (default: 3)
        CB_EXTERNAL_API_RESET_TIMEOUT: Seconds before External API circuit resets (default: 45)
        CB_ROS2_FAIL_MAX: Max failures before ROS2 circuit opens (default: 3)
        CB_ROS2_RESET_TIMEOUT: Seconds before ROS2 circuit resets (default: 30)
        CB_LOCAL_CACHE_MAX_SIZE: Max items in local fallback cache (default: 1000)
        CB_LOCAL_CACHE_TTL: Default TTL for local cache items in seconds (default: 300)
        CB_RETRY_QUEUE_MAX_SIZE: Max messages in retry queues (default: 1000)
    """
    # Redis circuit breaker
    redis: CircuitBreakerServiceConfig = field(default_factory=lambda: CircuitBreakerServiceConfig(
        fail_max=int(os.getenv('CB_REDIS_FAIL_MAX', '5')),
        reset_timeout=int(os.getenv('CB_REDIS_RESET_TIMEOUT', '30')),
        exclude=os.getenv('CB_REDIS_EXCLUDE', 'KeyError').split(',') if os.getenv('CB_REDIS_EXCLUDE') else ['KeyError'],
    ))

    # MQTT circuit breaker
    mqtt: CircuitBreakerServiceConfig = field(default_factory=lambda: CircuitBreakerServiceConfig(
        fail_max=int(os.getenv('CB_MQTT_FAIL_MAX', '3')),
        reset_timeout=int(os.getenv('CB_MQTT_RESET_TIMEOUT', '60')),
        exclude=[],
    ))

    # Database circuit breaker
    database: CircuitBreakerServiceConfig = field(default_factory=lambda: CircuitBreakerServiceConfig(
        fail_max=int(os.getenv('CB_DATABASE_FAIL_MAX', '5')),
        reset_timeout=int(os.getenv('CB_DATABASE_RESET_TIMEOUT', '30')),
        exclude=[],
    ))

    # External API circuit breaker (Fusion 360, Slicer)
    external_api: CircuitBreakerServiceConfig = field(default_factory=lambda: CircuitBreakerServiceConfig(
        fail_max=int(os.getenv('CB_EXTERNAL_API_FAIL_MAX', '3')),
        reset_timeout=int(os.getenv('CB_EXTERNAL_API_RESET_TIMEOUT', '45')),
        exclude=[],
    ))

    # ROS2 bridge circuit breaker
    ros2: CircuitBreakerServiceConfig = field(default_factory=lambda: CircuitBreakerServiceConfig(
        fail_max=int(os.getenv('CB_ROS2_FAIL_MAX', '3')),
        reset_timeout=int(os.getenv('CB_ROS2_RESET_TIMEOUT', '30')),
        exclude=[],
    ))

    # Local cache configuration (fallback when Redis is unavailable)
    local_cache_max_size: int = int(os.getenv('CB_LOCAL_CACHE_MAX_SIZE', '1000'))
    local_cache_ttl: int = int(os.getenv('CB_LOCAL_CACHE_TTL', '300'))

    # Retry queue configuration
    retry_queue_max_size: int = int(os.getenv('CB_RETRY_QUEUE_MAX_SIZE', '1000'))

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'redis': {
                'fail_max': self.redis.fail_max,
                'reset_timeout': self.redis.reset_timeout,
                'exclude': self.redis.exclude,
            },
            'mqtt': {
                'fail_max': self.mqtt.fail_max,
                'reset_timeout': self.mqtt.reset_timeout,
                'exclude': self.mqtt.exclude,
            },
            'database': {
                'fail_max': self.database.fail_max,
                'reset_timeout': self.database.reset_timeout,
                'exclude': self.database.exclude,
            },
            'external_api': {
                'fail_max': self.external_api.fail_max,
                'reset_timeout': self.external_api.reset_timeout,
                'exclude': self.external_api.exclude,
            },
            'ros2': {
                'fail_max': self.ros2.fail_max,
                'reset_timeout': self.ros2.reset_timeout,
                'exclude': self.ros2.exclude,
            },
            'local_cache': {
                'max_size': self.local_cache_max_size,
                'ttl': self.local_cache_ttl,
            },
            'retry_queue': {
                'max_size': self.retry_queue_max_size,
            },
        }


@dataclass
class Config:
    """Master configuration class."""
    # Environment
    env: str = os.getenv('FLASK_ENV', 'development')
    debug: bool = os.getenv('FLASK_DEBUG', 'false').lower() in ('true', '1', 'yes')
    demo_mode: bool = field(default_factory=_is_demo_mode)
    secret_key: str = field(default_factory=_get_secret_key)
    jwt_secret_key: str = field(default_factory=_get_jwt_secret_key)

    # Server
    host: str = os.getenv('FLASK_HOST', '0.0.0.0')
    port: int = int(os.getenv('FLASK_PORT', '5000'))

    # Sub-configurations
    flask: FlaskConfig = field(default_factory=FlaskConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    historian: HistorianConfig = field(default_factory=HistorianConfig)
    alarm: AlarmConfig = field(default_factory=AlarmConfig)
    machine_control: MachineControlConfig = field(default_factory=MachineControlConfig)
    ros2: ROS2Config = field(default_factory=ROS2Config)
    ml: MLConfig = field(default_factory=MLConfig)
    lego: LEGOConfig = field(default_factory=LEGOConfig)
    unity: UnityConfig = field(default_factory=UnityConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    jwt: JWTConfig = field(default_factory=JWTConfig)

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.env == 'production'

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.env == 'development'

    def is_demo_mode(self) -> bool:
        """Check if running in demo mode."""
        return self.demo_mode

    def validate_production_config(self) -> List[str]:
        """
        Validate configuration for production readiness.

        Returns:
            List of warning messages (empty if all checks pass)
        """
        warnings_list = []

        if not self.is_production():
            return warnings_list  # Skip validation for non-production

        # Warn if demo mode is enabled in production
        if self.demo_mode:
            warnings_list.append(
                "DEMO_MODE is enabled in production. "
                "This allows insecure defaults and should NEVER be used with real data!"
            )

        # Check for localhost in service configurations
        localhost_checks = [
            (self.database.host, 'Database (DB_HOST)'),
            (self.redis.host, 'Redis (REDIS_HOST)'),
            (self.ros2.mqtt_host, 'ROS2 MQTT (ROS2_MQTT_HOST)'),
            (self.lego.slicer_host, 'Slicer (SLICER_HOST)'),
            (self.lego.fusion360_host, 'Fusion360 (FUSION360_HOST)'),
        ]

        for host, service_name in localhost_checks:
            if host in ('localhost', '127.0.0.1'):
                warnings_list.append(
                    f"{service_name} is set to '{host}' in production. "
                    "Update to the actual service hostname."
                )

        # Check for debug mode in production
        if self.debug:
            warnings_list.append(
                "FLASK_DEBUG is enabled in production. "
                "This exposes sensitive information and should be disabled."
            )

        # Check for DATABASE_URL
        if not self.database._database_url:
            warnings_list.append(
                "DATABASE_URL not set. Using individual DB_* variables. "
                "Consider using DATABASE_URL for production."
            )

        # Log warnings
        for warning in warnings_list:
            logger.warning(f"Production config issue: {warning}")

        return warnings_list


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def init_config(**overrides) -> Config:
    """Initialize configuration with optional overrides."""
    global _config
    _config = Config(**overrides)
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
