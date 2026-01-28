"""
LEGO Factory v3 - Simple Application Entry Point
=================================================
Minimal Flask app that works out of the box.
"""

import os
import logging
import warnings
from datetime import timedelta
from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize JWT extension
jwt = JWTManager()


def _get_secret_key() -> str:
    """Get secret key from environment with proper validation."""
    secret_key = os.environ.get('SECRET_KEY')
    env = os.environ.get('FLASK_ENV', 'development')

    if not secret_key:
        if env == 'production':
            raise RuntimeError(
                "SECRET_KEY environment variable is required in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        warnings.warn(
            "SECRET_KEY not set. Using insecure default for development only.",
            UserWarning
        )
        return 'dev-only-insecure-key-do-not-use-in-production'

    return secret_key


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')

    # Configuration - use secure secret key handling
    app.config['SECRET_KEY'] = _get_secret_key()
    app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', '0') == '1'

    # Enable CORS
    CORS(app)

    # Configure JWT
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', app.config['SECRET_KEY'])
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=15)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'
    app.config['JWT_ALGORITHM'] = 'HS256'
    jwt.init_app(app)
    logger.info("JWT configured")

    # Health check endpoint with API status
    @app.route('/health')
    def health():
        loaded = app.config.get('LOADED_APIS', [])
        failed = app.config.get('FAILED_APIS', [])

        # Determine overall health based on critical APIs
        critical_apis = {'SCADA', 'MES', 'ERP'}
        loaded_names = {api['name'] for api in loaded}
        critical_loaded = critical_apis & loaded_names
        critical_missing = critical_apis - loaded_names

        if critical_missing:
            status = 'degraded'
        elif failed:
            status = 'healthy_with_warnings'
        else:
            status = 'healthy'

        return jsonify({
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
            'version': '3.0.0',
            'service': 'lego-factory',
            'apis': {
                'loaded': len(loaded),
                'failed': len(failed),
                'critical_missing': list(critical_missing) if critical_missing else None,
            },
            'loaded_apis': [api['name'] for api in loaded],
            'failed_apis': [{'name': api['name'], 'error': api['error']} for api in failed] if failed else None,
        })

    # Main dashboard - REMOVED: Using routes/web/__init__.py dashboard_web.home instead
    # The proper dashboard template is in templates/dashboard/index.html

    # API info
    @app.route('/api')
    def api_info():
        return jsonify({
            'name': 'LEGO Factory v3 API',
            'version': '3.0.0',
            'endpoints': {
                'health': '/health',
                'scada': '/api/scada/*',
                'plc': '/api/plc/*',
                'mes': '/api/mes/*',
                'erp': '/api/erp/*',
                'qms': '/api/qms/*',
                'cmms': '/api/cmms/*',
                'lego': '/api/lego/*',
                'slicer': '/api/slicer/*',
                'ml': '/api/ml/*',
                'ros2': '/api/ros2/*',
                'unity': '/api/unity/*',
                'mcp': '/api/mcp/*'
            }
        })

    # Track which APIs load successfully for health check
    app.config['LOADED_APIS'] = []
    app.config['FAILED_APIS'] = []

    # Try to register full blueprints, but don't fail if dependencies missing
    try:
        from api.routes import register_blueprints
        register_blueprints(app)
        logger.info("Full blueprints registered")
    except ImportError as e:
        logger.warning(f"Some blueprints not loaded: {e}")
        register_demo_routes(app)

    # Helper function to register blueprints with tracking
    def register_api(name: str, import_path: str, blueprint_name: str, url_prefix: str):
        """Register an API blueprint with error tracking."""
        try:
            module = __import__(import_path, fromlist=[blueprint_name])
            blueprint = getattr(module, blueprint_name)
            app.register_blueprint(blueprint)
            app.config['LOADED_APIS'].append({
                'name': name,
                'prefix': url_prefix,
                'status': 'loaded'
            })
            logger.info(f"{name} API registered at {url_prefix}")
            return True
        except ImportError as e:
            app.config['FAILED_APIS'].append({
                'name': name,
                'prefix': url_prefix,
                'error': f"Import error: {e}",
                'status': 'failed'
            })
            logger.warning(f"{name} API not loaded (import error): {e}")
            return False
        except Exception as e:
            app.config['FAILED_APIS'].append({
                'name': name,
                'prefix': url_prefix,
                'error': str(e),
                'status': 'failed'
            })
            logger.error(f"{name} API failed to load: {e}")
            return False

    # Register all APIs with tracking
    register_api('Auth', 'api.routes.auth', 'auth_api_bp', '/api/auth/*')
    register_api('SCADA', 'api.routes.scada_api', 'scada_api_bp', '/api/scada/*')
    register_api('PLC', 'api.routes.plc_api', 'plc_api_bp', '/api/plc/*')
    register_api('Slicer', 'api.routes.slicer_api', 'slicer_api_bp', '/api/slicer/*')
    register_api('MES', 'api.routes.mes_api', 'mes_api_bp', '/api/mes/*')
    register_api('ERP', 'api.routes.erp_api', 'erp_api_bp', '/api/erp/*')
    register_api('CRM', 'api.routes.crm_api', 'crm_api_bp', '/api/crm/*')
    register_api('QMS', 'api.routes.qms_api', 'qms_api_bp', '/api/qms/*')
    register_api('Unity', 'api.routes.unity_api', 'unity_api_bp', '/api/unity/*')
    register_api('MCP', 'api.routes.mcp_api', 'mcp_api_bp', '/api/mcp/*')
    register_api('ROS2', 'api.routes.ros2_api', 'ros2_api_bp', '/api/ros2/*')
    register_api('CMMS', 'api.routes.cmms_api', 'cmms_api_bp', '/api/cmms/*')
    register_api('LEGO', 'api.routes.lego_api', 'lego_api_bp', '/api/lego/*')
    register_api('ML', 'api.routes.ml_api', 'ml_api_bp', '/api/ml/*')

    # Register web routes (HTML pages)
    try:
        from routes.web import register_web_routes
        register_web_routes(app)
        logger.info("Web routes registered")
    except ImportError as e:
        logger.warning(f"Web routes not loaded: {e}")
        # Fall back to demo routes
        register_demo_routes(app)

    logger.info("LEGO Factory v3 started successfully")
    return app


def register_demo_routes(app):
    """Register demo routes when full app isn't available."""

    @app.route('/scada/alarms')
    def scada_alarms():
        return render_template_string(ALARMS_TEMPLATE)

    @app.route('/scada/machines')
    def scada_machines():
        return render_template_string(MACHINES_TEMPLATE)

    @app.route('/mes/work-orders')
    def mes_work_orders():
        return render_template_string(WORK_ORDERS_TEMPLATE)

    @app.route('/lego/catalog')
    def lego_catalog():
        return render_template_string(CATALOG_TEMPLATE)

    @app.route('/api/scada/alarms/active')
    def api_alarms():
        return jsonify({
            'alarms': [
                {'id': 'ALM-001', 'priority': 'high', 'source': 'Printer 1', 'message': 'Temperature warning'},
                {'id': 'ALM-002', 'priority': 'medium', 'source': 'Conveyor A', 'message': 'Belt tension low'}
            ],
            'count': 2
        })


# =============================================================================
# HTML Templates (embedded for simplicity)
# =============================================================================

HOME_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>LEGO Factory v3</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); min-height: 100vh; }
        .card { border: none; border-radius: 1rem; }
        .hero { padding: 4rem 0; }
        .feature-icon { font-size: 2.5rem; color: #E3000B; }
    </style>
</head>
<body class="text-white">
    <div class="container">
        <div class="hero text-center">
            <h1 class="display-3 fw-bold"><i class="bi bi-bricks text-danger"></i> LEGO Factory v3</h1>
            <p class="lead">Unified Smart Manufacturing Platform</p>
            <p class="text-muted">SCADA • MES • ERP • QMS • ML • Digital Twin</p>
        </div>

        <div class="row g-4 mb-5">
            <div class="col-md-4">
                <div class="card bg-dark text-white h-100">
                    <div class="card-body text-center">
                        <i class="bi bi-cpu feature-icon"></i>
                        <h5 class="mt-3">SCADA</h5>
                        <p class="text-muted small">Machine control, alarms, historian</p>
                        <a href="/scada/machines" class="btn btn-outline-light btn-sm">Machines</a>
                        <a href="/scada/alarms" class="btn btn-outline-danger btn-sm">Alarms</a>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card bg-dark text-white h-100">
                    <div class="card-body text-center">
                        <i class="bi bi-clipboard-check feature-icon"></i>
                        <h5 class="mt-3">MES</h5>
                        <p class="text-muted small">Work orders, scheduling, OEE</p>
                        <a href="/mes/work-orders" class="btn btn-outline-light btn-sm">Work Orders</a>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card bg-dark text-white h-100">
                    <div class="card-body text-center">
                        <i class="bi bi-grid-3x3 feature-icon"></i>
                        <h5 class="mt-3">LEGO Design</h5>
                        <p class="text-muted small">Brick catalog, custom builder</p>
                        <a href="/lego/catalog" class="btn btn-outline-light btn-sm">Brick Catalog</a>
                    </div>
                </div>
            </div>
        </div>

        <div class="row g-4">
            <div class="col-md-3">
                <div class="card bg-success text-white">
                    <div class="card-body text-center">
                        <h3>85.2%</h3>
                        <small>OEE</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-danger text-white">
                    <div class="card-body text-center">
                        <h3>2</h3>
                        <small>Active Alarms</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-primary text-white">
                    <div class="card-body text-center">
                        <h3>12</h3>
                        <small>Work Orders</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-warning text-dark">
                    <div class="card-body text-center">
                        <h3>5/8</h3>
                        <small>Machines Running</small>
                    </div>
                </div>
            </div>
        </div>

        <div class="text-center mt-5">
            <p class="text-muted">
                <a href="/health" class="text-muted">Health Check</a> •
                <a href="/api" class="text-muted">API Info</a>
            </p>
        </div>
    </div>
</body>
</html>
'''

ALARMS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Alarms - LEGO Factory v3</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="bi bi-bricks"></i> LEGO Factory v3</a>
        </div>
    </nav>
    <div class="container mt-4">
        <h2><i class="bi bi-bell"></i> Active Alarms</h2>
        <table class="table table-striped">
            <thead><tr><th>Priority</th><th>Source</th><th>Message</th><th>Time</th></tr></thead>
            <tbody>
                <tr class="table-danger"><td><span class="badge bg-danger">HIGH</span></td><td>Printer 1</td><td>Temperature warning</td><td>2 min ago</td></tr>
                <tr class="table-warning"><td><span class="badge bg-warning">MEDIUM</span></td><td>Conveyor A</td><td>Belt tension low</td><td>15 min ago</td></tr>
            </tbody>
        </table>
        <a href="/" class="btn btn-secondary">← Back</a>
    </div>
</body>
</html>
'''

MACHINES_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Machines - LEGO Factory v3</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="bi bi-bricks"></i> LEGO Factory v3</a>
        </div>
    </nav>
    <div class="container mt-4">
        <h2><i class="bi bi-cpu"></i> Machines</h2>
        <div class="row g-3">
            <div class="col-md-4"><div class="card"><div class="card-body"><h5>Prusa MK4 #1</h5><span class="badge bg-success">Running</span><p class="mt-2 mb-0">Job: WO-2024-001 (67%)</p></div></div></div>
            <div class="col-md-4"><div class="card"><div class="card-body"><h5>Prusa MK4 #2</h5><span class="badge bg-success">Running</span><p class="mt-2 mb-0">Job: WO-2024-002 (23%)</p></div></div></div>
            <div class="col-md-4"><div class="card"><div class="card-body"><h5>Bambu X1C</h5><span class="badge bg-secondary">Idle</span><p class="mt-2 mb-0">Ready</p></div></div></div>
            <div class="col-md-4"><div class="card"><div class="card-body"><h5>Niryo Ned2</h5><span class="badge bg-success">Running</span><p class="mt-2 mb-0">Pick-Place cycle</p></div></div></div>
            <div class="col-md-4"><div class="card"><div class="card-body"><h5>xArm Lite 6</h5><span class="badge bg-danger">Alarm</span><p class="mt-2 mb-0">Joint 3 error</p></div></div></div>
        </div>
        <a href="/" class="btn btn-secondary mt-3">← Back</a>
    </div>
</body>
</html>
'''

WORK_ORDERS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Work Orders - LEGO Factory v3</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="bi bi-bricks"></i> LEGO Factory v3</a>
        </div>
    </nav>
    <div class="container mt-4">
        <h2><i class="bi bi-clipboard-check"></i> Work Orders</h2>
        <table class="table table-striped">
            <thead><tr><th>WO #</th><th>Product</th><th>Qty</th><th>Status</th><th>Progress</th></tr></thead>
            <tbody>
                <tr><td>WO-2024-156</td><td>2x4 Red Brick</td><td>500</td><td><span class="badge bg-primary">In Progress</span></td><td><div class="progress"><div class="progress-bar" style="width:67%">67%</div></div></td></tr>
                <tr><td>WO-2024-155</td><td>2x2 Blue Brick</td><td>1000</td><td><span class="badge bg-success">Completed</span></td><td><div class="progress"><div class="progress-bar bg-success" style="width:100%">100%</div></div></td></tr>
                <tr><td>WO-2024-154</td><td>Custom Gear 24T</td><td>50</td><td><span class="badge bg-secondary">Pending</span></td><td><div class="progress"><div class="progress-bar" style="width:0%">0%</div></div></td></tr>
            </tbody>
        </table>
        <a href="/" class="btn btn-secondary">← Back</a>
    </div>
</body>
</html>
'''

CATALOG_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Brick Catalog - LEGO Factory v3</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>.brick { width: 80px; height: 60px; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; }</style>
</head>
<body class="bg-light">
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="bi bi-bricks"></i> LEGO Factory v3</a>
        </div>
    </nav>
    <div class="container mt-4">
        <h2><i class="bi bi-grid-3x3"></i> Brick Catalog</h2>
        <div class="row g-3">
            <div class="col-md-3"><div class="card"><div class="card-body text-center"><div class="brick bg-danger mx-auto">2x4</div><h6 class="mt-2">2x4 Brick</h6><small class="text-muted">Part #3001</small></div></div></div>
            <div class="col-md-3"><div class="card"><div class="card-body text-center"><div class="brick bg-primary mx-auto">2x2</div><h6 class="mt-2">2x2 Brick</h6><small class="text-muted">Part #3003</small></div></div></div>
            <div class="col-md-3"><div class="card"><div class="card-body text-center"><div class="brick bg-warning mx-auto">1x4</div><h6 class="mt-2">1x4 Brick</h6><small class="text-muted">Part #3010</small></div></div></div>
            <div class="col-md-3"><div class="card"><div class="card-body text-center"><div class="brick bg-success mx-auto">2x4</div><h6 class="mt-2">2x4 Plate</h6><small class="text-muted">Part #3020</small></div></div></div>
        </div>
        <a href="/" class="btn btn-secondary mt-3">← Back</a>
    </div>
</body>
</html>
'''


# Run directly
if __name__ == '__main__':
    app = create_app()
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', '5000'))
    app.run(host=host, port=port, debug=debug_mode)
