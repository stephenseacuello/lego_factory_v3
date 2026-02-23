"""
LEGO Factory v3 - Flask Application Factory
============================================
Unified smart manufacturing platform with SCADA, MES, ERP, and QMS.
"""

import logging
import os
from datetime import timedelta
from typing import List, Optional, Union

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_jwt_extended import JWTManager

from config.settings import get_config
from config.logging_config import configure_for_flask, get_structured_logger
from api.middleware.rate_limiter import init_limiter, get_limiter, _update_limiter_reference
from api.middleware.request_logging import init_request_logging
from api.middleware.prometheus_metrics import init_metrics

socketio = SocketIO()
jwt = JWTManager()
logger = logging.getLogger(__name__)


def _get_cors_origins() -> Union[str, List[str]]:
    """
    Get CORS allowed origins based on environment.

    In production, returns configured origins or empty list if not set (blocks all).
    In development, returns "*" to allow all origins.
    """
    config = get_config()

    if config.is_production():
        # In production, use configured origins only
        origins_str = os.getenv('CORS_ALLOWED_ORIGINS', '')
        if origins_str:
            origins = [origin.strip() for origin in origins_str.split(',') if origin.strip()]
            if origins:
                logger.info(f"CORS configured for origins: {origins}")
                return origins
        # No origins configured in production - restrict to same-origin
        logger.warning(
            "CORS_ALLOWED_ORIGINS not configured in production. "
            "API requests from external origins will be blocked."
        )
        return []  # Empty list blocks all cross-origin requests

    # Development: allow all origins
    return "*"


def _configure_security_headers(app: Flask):
    """
    Configure security headers middleware.

    Adds security headers to all responses to protect against common vulnerabilities.
    """
    @app.after_request
    def add_security_headers(response):
        """Add security headers to every response."""
        config = get_config()

        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'DENY'

        # Enable XSS filter in older browsers
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # Prevent caching of sensitive responses
        if request.path.startswith('/api/auth'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'

        # Content Security Policy (basic, can be customized)
        if config.is_production():
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "font-src 'self'; "
                "connect-src 'self' wss: ws:; "
                "frame-ancestors 'none';"
            )

        # Strict Transport Security (HTTPS only)
        # Only set if we're behind HTTPS (check for common proxy headers)
        if (request.headers.get('X-Forwarded-Proto') == 'https' or
            request.is_secure or
            config.is_production()):
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains; preload'
            )

        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions Policy (formerly Feature Policy)
        response.headers['Permissions-Policy'] = (
            'geolocation=(), microphone=(), camera=(), '
            'payment=(), usb=(), magnetometer=(), gyroscope=()'
        )

        return response

    logger.info("Security headers middleware configured")


def get_socketio() -> SocketIO:
    """Get the global SocketIO instance."""
    return socketio


def create_app(config_name: str = None) -> Flask:
    """
    Application factory for Flask app.

    Args:
        config_name: Configuration name (development, production, testing)

    Returns:
        Configured Flask application
    """
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'),
    )
    config = get_config()

    # Configure Flask
    app.config['SECRET_KEY'] = config.flask.secret_key
    app.config['DEBUG'] = config.flask.debug
    app.config['SQLALCHEMY_DATABASE_URI'] = config.database.url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JSON_SORT_KEYS'] = False

    # Configure JWT
    configure_jwt(app, config)

    # Setup logging
    configure_logging(app, config)

    # Configure security headers middleware
    _configure_security_headers(app)

    # Get CORS origins based on environment
    cors_origins = _get_cors_origins()

    # Initialize extensions with environment-aware CORS
    CORS(app, resources={
        r"/api/*": {"origins": cors_origins},
        r"/socket.io/*": {"origins": cors_origins}
    })

    # Initialize SocketIO with environment-aware CORS
    socketio.init_app(
        app,
        cors_allowed_origins=cors_origins,
        async_mode='threading',
        ping_timeout=60,
        ping_interval=25,
        max_http_buffer_size=1000000,
        logger=False,
        engineio_logger=False
    )

    # Register WebSocket namespaces
    register_websocket_namespaces()

    # Initialize JWT
    jwt.init_app(app)

    # Setup JWT callbacks
    setup_jwt_callbacks(app)

    # Initialize rate limiter with Redis backend (fallback to memory if unavailable)
    init_limiter(app)
    _update_limiter_reference()

    # Initialize request logging middleware for structured request/response logging
    init_request_logging(app)

    # Initialize Prometheus metrics for monitoring
    init_metrics(app)
    logger.info("Prometheus metrics endpoint registered at /metrics")

    # Register blueprints
    register_blueprints(app)

    # Register error handlers
    register_error_handlers(app)

    # Register shell context
    register_shell_context(app)

    # Initialize database
    with app.app_context():
        init_database(app)

    # Register health check endpoints
    register_health_check(app)

    # Validate production configuration
    if config.is_production():
        warnings_list = config.validate_production_config()
        if config.demo_mode:
            logger.warning(
                "DEMO_MODE is enabled in a PRODUCTION environment. "
                "Set DEMO_MODE=false and configure proper secrets before handling real data."
            )

    logger.info(
        "LEGO Factory v3 initialized",
        extra={
            'event': 'app_initialized',
            'config_name': config_name or 'default',
            'environment': config.env,
            'debug': config.flask.debug,
            'host': config.flask.host,
            'port': config.flask.port,
        }
    )
    return app


def register_websocket_namespaces():
    """Register all WebSocket namespaces for real-time communication."""
    namespace_configs = [
        ('services.websocket.unity_socket', 'UnityNamespace', 'set_unity_namespace', '/unity'),
        ('services.websocket.dashboard_socket', 'DashboardNamespace', 'set_dashboard_namespace', '/dashboard'),
        ('services.websocket.alarm_socket', 'AlarmNamespace', 'set_alarm_namespace', '/alarms'),
        ('services.websocket.tag_socket', 'TagNamespace', 'set_tag_namespace', '/tags'),
    ]

    registered = []
    failed = []

    for module_path, class_name, setter_name, path in namespace_configs:
        try:
            module = __import__(module_path, fromlist=[class_name, setter_name])
            ns_class = getattr(module, class_name)
            ns_setter = getattr(module, setter_name)
            ns_instance = ns_class(path)
            socketio.on_namespace(ns_instance)
            ns_setter(ns_instance)
            registered.append(path)
        except Exception as e:
            failed.append(path)
            logger.error(f"Failed to register WebSocket namespace {path}: {e}")

    if registered:
        logger.info(f"WebSocket namespaces registered: {', '.join(registered)}")
    if failed:
        logger.error(f"WebSocket namespaces FAILED to register: {', '.join(failed)}")


def configure_jwt(app: Flask, config):
    """Configure JWT settings"""
    # JWT Secret Key
    app.config['JWT_SECRET_KEY'] = config.jwt.secret_key

    # Token expiration times
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = config.jwt.access_token_expires
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = config.jwt.refresh_token_expires

    # Token location and headers
    app.config['JWT_TOKEN_LOCATION'] = config.jwt.token_location
    app.config['JWT_HEADER_NAME'] = config.jwt.header_name
    app.config['JWT_HEADER_TYPE'] = config.jwt.header_type

    # Algorithm
    app.config['JWT_ALGORITHM'] = config.jwt.algorithm

    # Enable blocklist for token revocation
    app.config['JWT_BLACKLIST_ENABLED'] = True
    app.config['JWT_BLACKLIST_TOKEN_CHECKS'] = ['access', 'refresh']

    logger.info("JWT configuration applied")


def setup_jwt_callbacks(app: Flask):
    """Setup JWT callback functions for token validation and user loading"""
    try:
        from services.auth.auth_service import AuthService
    except Exception as e:
        logger.error(f"Failed to import AuthService at startup: {e}. JWT callbacks will not work.")
        raise

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        """Check if a JWT token has been revoked."""
        jti = jwt_payload['jti']
        return AuthService.is_token_revoked(jti)

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        """Handle revoked token errors."""
        return jsonify({
            'error': 'Token Revoked',
            'message': 'The token has been revoked'
        }), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        """Handle expired token errors."""
        return jsonify({
            'error': 'Token Expired',
            'message': 'The token has expired'
        }), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        """Handle invalid token errors."""
        return jsonify({
            'error': 'Invalid Token',
            'message': 'The token is invalid'
        }), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        """Handle missing token errors."""
        return jsonify({
            'error': 'Authorization Required',
            'message': 'Authorization token is missing'
        }), 401

    @jwt.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header, jwt_payload):
        """Handle non-fresh token errors."""
        return jsonify({
            'error': 'Fresh Token Required',
            'message': 'A fresh token is required for this action'
        }), 401

    @jwt.user_identity_loader
    def user_identity_lookup(user):
        """Convert user object to identity for JWT."""
        if isinstance(user, str):
            return user
        return str(user.id) if hasattr(user, 'id') else str(user)

    @jwt.user_lookup_loader
    def user_lookup_callback(jwt_header, jwt_payload):
        """Load user from JWT identity."""
        identity = jwt_payload['sub']
        return AuthService.get_user_by_id(identity)

    @jwt.user_lookup_error_loader
    def user_lookup_error_callback(jwt_header, jwt_payload):
        """Handle user lookup errors."""
        return jsonify({
            'error': 'User Not Found',
            'message': 'The user associated with this token was not found'
        }), 401

    logger.info("JWT callbacks configured")


def configure_logging(app: Flask, config):
    """
    Configure application logging with structured JSON support.

    In production (FLASK_ENV=production):
    - Uses JSON formatter for log aggregation compatibility
    - SocketIO logging at WARNING level with structured format

    In development:
    - Uses human-readable colored formatter
    - More verbose SocketIO logging for debugging
    """
    # Use the new structured logging configuration
    configure_for_flask(app)

    # Get the structured logger for this module
    global logger
    logger = get_structured_logger(__name__)

    # Configure SocketIO loggers based on environment
    is_production = config.env == 'production'

    socketio_logger = logging.getLogger('socketio')
    engineio_logger = logging.getLogger('engineio')

    if is_production:
        # Production: structured logs at WARNING level
        socketio_logger.setLevel(logging.WARNING)
        engineio_logger.setLevel(logging.WARNING)
    else:
        # Development: more verbose for debugging
        socketio_logger.setLevel(logging.INFO)
        engineio_logger.setLevel(logging.WARNING)

    logger.info(
        "Logging configured",
        extra={
            'event': 'logging_configured',
            'environment': config.env,
            'json_output': app.config.get('LOGGING_JSON_OUTPUT', False),
            'log_level': config.logging.level,
        }
    )


def register_blueprints(app: Flask):
    """Register all application blueprints"""
    from api import api_bp
    from api.routes.scada import scada_bp
    from api.routes.scada_api import scada_api_bp
    from api.routes.mes_api import mes_api_bp
    from api.routes.erp_api import erp_api_bp
    from api.routes.qms_api import qms_api_bp
    from api.routes.cmms_api import cmms_api_bp
    from api.routes.lego_api import lego_api_bp
    from api.routes.ml_api import ml_api_bp
    from api.routes.ros2_api import ros2_api_bp
    from api.routes.unity_api import unity_api_bp
    from api.routes.auth import auth_bp, auth_api_bp
    from api.routes.crm_views import crm_bp
    from api.routes.crm_api import crm_api_bp
    from api.routes.simulation_api import simulation_api

    # Register SCADA routes under API (must be before api_bp is registered on app)
    api_bp.register_blueprint(scada_bp)

    # Register API blueprint
    app.register_blueprint(api_bp)

    # Register all API blueprints
    app.register_blueprint(scada_api_bp)
    app.register_blueprint(mes_api_bp)
    app.register_blueprint(erp_api_bp)
    app.register_blueprint(qms_api_bp)
    app.register_blueprint(cmms_api_bp)
    app.register_blueprint(lego_api_bp)
    app.register_blueprint(ml_api_bp)
    app.register_blueprint(ros2_api_bp)
    app.register_blueprint(unity_api_bp)
    app.register_blueprint(crm_api_bp)
    app.register_blueprint(simulation_api)

    # Register Auth blueprints
    app.register_blueprint(auth_bp)  # Web routes at /auth
    app.register_blueprint(auth_api_bp)  # API routes at /api/auth

    # Register web page routes (dashboard, SCADA, MES, ERP pages, etc.)
    from routes.web import register_web_routes
    register_web_routes(app)

    # Register Flask-RESTX API documentation
    register_api_docs(app)

    logger.info("All blueprints registered: SCADA, MES, ERP, QMS, CMMS, LEGO, ML, ROS2, Unity, Auth, CRM, Simulation, API Docs")


def register_api_docs(app: Flask):
    """
    Register Flask-RESTX API documentation with Swagger UI.

    The API documentation will be available at /api/docs/swagger
    """
    try:
        from api.docs import api_docs_bp, init_namespaces

        # Initialize all namespaces (auth, scada, mes, erp, ros2, ml)
        init_namespaces()

        # Register the API docs blueprint
        app.register_blueprint(api_docs_bp)

        logger.info("API documentation registered at /api/docs/swagger")
    except Exception as e:
        logger.warning(f"Failed to register API documentation: {e}")


def register_error_handlers(app: Flask):
    """Register error handlers"""
    from flask import jsonify

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': 'Bad request', 'message': str(error)}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'error': 'Unauthorized', 'message': 'Authentication required'}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'error': 'Forbidden', 'message': 'Access denied'}), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found', 'message': str(error)}), 404

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        """Handle rate limit exceeded errors."""
        # Extract retry-after information if available
        retry_after = None
        if hasattr(error, 'description') and isinstance(error.description, dict):
            retry_after = error.description.get('retry_after')

        response = {
            'error': 'Rate Limit Exceeded',
            'message': 'Too many requests. Please wait before making another request.',
        }

        if retry_after:
            response['retry_after'] = retry_after

        return jsonify(response), 429

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {error}")
        return jsonify({'error': 'Internal server error'}), 500


def register_shell_context(app: Flask):
    """Register shell context for flask shell"""
    @app.shell_context_processor
    def make_shell_context():
        from config.database import get_engine, get_db_session
        from models.auth.user import User, TokenBlocklist
        from services.auth.auth_service import AuthService
        return {
            'app': app,
            'get_engine': get_engine,
            'get_db_session': get_db_session,
            'User': User,
            'TokenBlocklist': TokenBlocklist,
            'AuthService': AuthService,
        }


def init_database(app: Flask):
    """Initialize database tables and extensions"""
    from config.database import init_timescaledb, get_engine
    from models.base import Base

    # Import all models so they register with Base.metadata
    model_modules = [
        'models.auth.user',
        'models.scada.machines', 'models.scada.tags',
        'models.scada.alarms', 'models.scada.recipes',
        'models.mes.work_orders', 'models.mes.scheduling',
        'models.mes.labor', 'models.mes.oee',
        'models.mes.resources', 'models.mes.sensor_data',
        'models.mes.genealogy',
        'models.mes.operations',
        'models.mes.setup',
        'models.mes.recipe_run',
        'models.qms.first_article',
        'models.erp.financial', 'models.erp.sales',
        'models.erp.inventory', 'models.erp.items',
        'models.erp.partners', 'models.erp.planning',
        'models.erp.purchasing',
        'models.qms.documents',
        'models.cmms.assets', 'models.cmms.maintenance',
        'models.cmms.failure',
        'models.erp.fixed_assets', 'models.erp.bank_reconciliation',
        'models.erp.tax',
        'models.lego.brick_designs', 'models.lego.parts_catalog',
        'models.lego.printing',
    ]
    for mod in model_modules:
        try:
            __import__(mod)
        except Exception as e:
            logger.warning(f"Could not import model {mod}: {e}")

    engine = get_engine()
    # Create tables one at a time, each in its own connection to isolate errors
    for table in Base.metadata.sorted_tables:
        try:
            with engine.connect() as conn:
                table.create(bind=conn, checkfirst=True)
                conn.commit()
        except Exception as e:
            if 'already exists' in str(e):
                logger.debug(f"Table/index already exists for {table.name}, skipping")
            else:
                logger.warning(f"Failed to create table {table.name}: {e}")
    logger.info("Database tables created/verified")

    try:
        init_timescaledb()
        logger.info("Database initialized with TimescaleDB")
    except Exception as e:
        logger.warning(
            f"TimescaleDB initialization failed: {e}. "
            "Time-series features (historian, continuous aggregates) will NOT work. "
            "The app will still run with standard PostgreSQL tables."
        )


# Health check endpoint
def register_health_check(app: Flask):
    """
    Register comprehensive health check endpoints.

    Provides:
    - /health - Full health status with all component checks
    - /ready - Kubernetes readiness probe
    - /live - Kubernetes liveness probe
    """
    from flask import jsonify
    from datetime import datetime
    import time
    import os
    import shutil

    from config.settings import get_config

    # Application start time for uptime tracking
    _app_start_time = time.time()

    def _check_database() -> dict:
        """Check PostgreSQL/TimescaleDB connectivity."""
        start = time.time()
        try:
            from config.database import get_engine
            from sqlalchemy import text

            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            latency_ms = round((time.time() - start) * 1000, 2)
            return {
                "status": "healthy",
                "latency_ms": latency_ms
            }
        except Exception as e:
            latency_ms = round((time.time() - start) * 1000, 2)
            return {
                "status": "unhealthy",
                "latency_ms": latency_ms,
                "error": str(e)
            }

    def _check_redis() -> dict:
        """Check Redis connectivity."""
        start = time.time()
        try:
            import redis
            config = get_config()

            client = redis.Redis.from_url(
                config.redis.url,
                socket_timeout=5.0,
                socket_connect_timeout=5.0
            )
            client.ping()
            client.close()

            latency_ms = round((time.time() - start) * 1000, 2)
            return {
                "status": "healthy",
                "latency_ms": latency_ms
            }
        except ImportError:
            return {
                "status": "degraded",
                "latency_ms": 0,
                "error": "redis package not installed"
            }
        except Exception as e:
            latency_ms = round((time.time() - start) * 1000, 2)
            return {
                "status": "unhealthy",
                "latency_ms": latency_ms,
                "error": str(e)
            }

    def _check_mqtt() -> dict:
        """Check MQTT broker status."""
        start = time.time()
        try:
            import socket
            config = get_config()

            # Resolve MQTT host/port: prefer MQTT_BROKER_HOST/PORT env vars
            # (set in docker-compose) over config.ros2 defaults
            mqtt_host = os.getenv('MQTT_BROKER_HOST', config.ros2.mqtt_host)
            mqtt_port = int(os.getenv('MQTT_BROKER_PORT', str(config.ros2.mqtt_port)))

            # Attempt TCP connection to MQTT broker
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            result = sock.connect_ex((mqtt_host, mqtt_port))
            sock.close()

            latency_ms = round((time.time() - start) * 1000, 2)

            if result == 0:
                return {
                    "status": "healthy",
                    "connected": True,
                    "latency_ms": latency_ms,
                    "host": mqtt_host,
                    "port": mqtt_port
                }
            else:
                return {
                    "status": "unhealthy",
                    "connected": False,
                    "latency_ms": latency_ms,
                    "error": f"Connection refused (code: {result})"
                }
        except Exception as e:
            latency_ms = round((time.time() - start) * 1000, 2)
            return {
                "status": "unhealthy",
                "connected": False,
                "latency_ms": latency_ms,
                "error": str(e)
            }

    def _check_socketio() -> dict:
        """Check SocketIO status."""
        try:
            from app import socketio as sio

            # Check if SocketIO is initialized and has a server
            if sio is not None and hasattr(sio, 'server') and sio.server is not None:
                return {
                    "status": "healthy",
                    "connected_clients": len(sio.server.manager.rooms.get('/', {}).get(None, set())) if hasattr(sio, 'server') and sio.server else 0
                }
            elif sio is not None:
                return {
                    "status": "healthy",
                    "note": "SocketIO initialized"
                }
            else:
                return {
                    "status": "degraded",
                    "error": "SocketIO not initialized"
                }
        except Exception as e:
            return {
                "status": "degraded",
                "error": str(e)
            }

    def _check_disk() -> dict:
        """Check disk space availability."""
        try:
            total, used, free = shutil.disk_usage("/")
            free_gb = round(free / (1024 ** 3), 2)
            total_gb = round(total / (1024 ** 3), 2)
            used_percent = round((used / total) * 100, 2)

            # Thresholds: unhealthy < 5%, degraded < 15%
            if free / total < 0.05:
                status = "unhealthy"
            elif free / total < 0.15:
                status = "degraded"
            else:
                status = "healthy"

            return {
                "status": status,
                "free_gb": free_gb,
                "total_gb": total_gb,
                "used_percent": used_percent
            }
        except Exception as e:
            return {
                "status": "unknown",
                "error": str(e)
            }

    def _check_memory() -> dict:
        """Check memory usage."""
        try:
            import psutil
            memory = psutil.virtual_memory()
            used_percent = round(memory.percent, 2)
            available_gb = round(memory.available / (1024 ** 3), 2)

            # Thresholds: unhealthy > 95%, degraded > 85%
            if used_percent > 95:
                status = "unhealthy"
            elif used_percent > 85:
                status = "degraded"
            else:
                status = "healthy"

            return {
                "status": status,
                "used_percent": used_percent,
                "available_gb": available_gb
            }
        except ImportError:
            # Fallback for systems without psutil
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = {}
                    for line in f:
                        parts = line.split(':')
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = int(parts[1].strip().split()[0])
                            meminfo[key] = value

                total_kb = meminfo.get('MemTotal', 0)
                available_kb = meminfo.get('MemAvailable', 0)

                if total_kb == 0:
                    raise ValueError("Could not read memory info")

                used_percent = round(((total_kb - available_kb) / total_kb) * 100, 2)
                available_gb = round(available_kb / (1024 ** 2), 2)

                if used_percent > 95:
                    status = "unhealthy"
                elif used_percent > 85:
                    status = "degraded"
                else:
                    status = "healthy"

                return {
                    "status": status,
                    "used_percent": used_percent,
                    "available_gb": available_gb
                }
            except Exception:
                return {
                    "status": "unknown",
                    "error": "psutil not installed and /proc/meminfo not available"
                }
        except Exception as e:
            return {
                "status": "unknown",
                "error": str(e)
            }

    def _get_overall_status(components: dict) -> str:
        """Determine overall health status from component statuses."""
        statuses = [c.get("status", "unknown") for c in components.values()]

        if "unhealthy" in statuses:
            return "unhealthy"
        elif "degraded" in statuses:
            return "degraded"
        elif all(s == "healthy" for s in statuses):
            return "healthy"
        else:
            return "degraded"

    @app.route('/health')
    def health():
        """
        Comprehensive health check endpoint.

        Returns detailed status of all system components.
        """
        components = {
            "database": _check_database(),
            "redis": _check_redis(),
            "mqtt": _check_mqtt(),
            "socketio": _check_socketio(),
            "disk": _check_disk(),
            "memory": _check_memory()
        }

        overall_status = _get_overall_status(components)

        response = {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "3.0.0",
            "service": "lego-factory",
            "uptime_seconds": round(time.time() - _app_start_time, 2),
            "components": components
        }

        # Return 503 for unhealthy, 200 for everything else
        status_code = 503 if overall_status == "unhealthy" else 200
        return jsonify(response), status_code

    @app.route('/ready')
    def readiness_probe():
        """
        Kubernetes readiness probe endpoint.

        Checks if the application is ready to serve traffic.
        Verifies critical dependencies: database and core services.
        """
        # Check critical components for readiness
        db_status = _check_database()
        socketio_status = _check_socketio()

        # Database must be healthy for readiness
        is_ready = db_status.get("status") == "healthy"

        if is_ready:
            return jsonify({
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "checks": {
                    "database": db_status.get("status"),
                    "socketio": socketio_status.get("status")
                }
            }), 200
        else:
            return jsonify({
                "status": "not_ready",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "checks": {
                    "database": db_status.get("status"),
                    "socketio": socketio_status.get("status")
                },
                "reason": "Critical dependency check failed"
            }), 503

    @app.route('/live')
    def liveness_probe():
        """
        Kubernetes liveness probe endpoint.

        Simple check to verify the application process is alive.
        This should be lightweight and always succeed if the app is running.
        """
        return jsonify({
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime_seconds": round(time.time() - _app_start_time, 2)
        }), 200

    logger.info("Health check endpoints registered: /health, /ready, /live")
