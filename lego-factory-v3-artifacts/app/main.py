"""
LEGO Factory - Main Application
Complete Smart Manufacturing Platform
ISA-95 Stack: ERP → MES → SCADA → Control → Sensors
"""

import os
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lego-factory-dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'postgresql://lego_factory:lego_factory@localhost:5432/lego_factory'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_SORT_KEYS'] = False

# Enable CORS
CORS(app, origins=['*'])

# Initialize SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')


# =============================================================================
# REGISTER BLUEPRINTS
# =============================================================================

def register_blueprints():
    """Register all API blueprints"""
    
    # SCADA Routes
    from api.routes.scada.routes import scada_bp
    app.register_blueprint(scada_bp)
    
    # MES Routes (to be implemented)
    # from api.routes.mes.routes import mes_bp
    # app.register_blueprint(mes_bp)
    
    # ERP Routes (to be implemented)
    # from api.routes.erp.routes import erp_bp
    # app.register_blueprint(erp_bp)
    
    # QMS Routes (to be implemented)
    # from api.routes.qms.routes import qms_bp
    # app.register_blueprint(qms_bp)
    
    # CMMS Routes (to be implemented)
    # from api.routes.cmms.routes import cmms_bp
    # app.register_blueprint(cmms_bp)
    
    # LEGO Routes (to be implemented)
    # from api.routes.lego.routes import lego_bp
    # app.register_blueprint(lego_bp)
    
    # ML Routes (to be implemented)
    # from api.routes.ml.routes import ml_bp
    # app.register_blueprint(ml_bp)
    
    logger.info("Blueprints registered")


# =============================================================================
# INITIALIZE SERVICES
# =============================================================================

def initialize_services():
    """Initialize all background services"""
    from config.database import init_database, DatabaseHealth
    from services.scada.historian.historian_service import start_historian
    from services.scada.alarm_management.alarm_service import initialize_alarm_processor
    
    # Initialize database
    try:
        init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    
    # Check database health
    if DatabaseHealth.check_connection():
        logger.info("Database connection: OK")
    else:
        logger.error("Database connection: FAILED")
    
    if DatabaseHealth.check_timescaledb():
        logger.info("TimescaleDB extension: OK")
    else:
        logger.warning("TimescaleDB extension: NOT AVAILABLE")
    
    # Start historian
    try:
        start_historian()
        logger.info("Historian service started")
    except Exception as e:
        logger.error(f"Historian start failed: {e}")
    
    # Initialize alarm processor
    try:
        from config.database import get_session
        with get_session() as session:
            initialize_alarm_processor(session)
        logger.info("Alarm processor initialized")
    except Exception as e:
        logger.error(f"Alarm processor init failed: {e}")


# =============================================================================
# ROUTES - MAIN PORTAL
# =============================================================================

@app.route('/')
def index():
    """Main portal page"""
    return render_template('common/index.html', 
                          title='LEGO Factory',
                          timestamp=datetime.utcnow())


@app.route('/health')
def health():
    """System health check"""
    from config.database import DatabaseHealth
    from services.scada.historian.historian_service import historian_writer
    from services.scada.machine_control.machine_service import machine_manager
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'database': {
            'connected': DatabaseHealth.check_connection(),
            'timescaledb': DatabaseHealth.check_timescaledb()
        },
        'historian': historian_writer.get_stats(),
        'machines': {
            'registered': len(machine_manager.list_machines()),
            'status': machine_manager.get_all_status()
        }
    })


@app.route('/api')
def api_info():
    """API information"""
    return jsonify({
        'name': 'LEGO Factory API',
        'version': '3.0.0',
        'description': 'Complete Smart Manufacturing Platform',
        'modules': {
            'scada': '/api/scada',
            'mes': '/api/mes',
            'erp': '/api/erp',
            'qms': '/api/qms',
            'cmms': '/api/cmms',
            'lego': '/api/lego',
            'ml': '/api/ml',
            'ros': '/api/ros',
            'unity': '/api/unity'
        }
    })


# =============================================================================
# SCADA DASHBOARDS
# =============================================================================

@app.route('/scada')
def scada_dashboard():
    """Main SCADA dashboard"""
    return render_template('scada/dashboard.html', title='SCADA Dashboard')


@app.route('/scada/machines')
def scada_machines():
    """Machine control dashboard"""
    return render_template('scada/machines.html', title='Machine Control')


@app.route('/scada/alarms')
def scada_alarms():
    """Alarm management dashboard"""
    return render_template('scada/alarms.html', title='Alarm Management')


@app.route('/scada/historian')
def scada_historian():
    """Historian trends dashboard"""
    return render_template('scada/historian.html', title='Historian')


@app.route('/scada/tags')
def scada_tags():
    """Tag management dashboard"""
    return render_template('scada/tags.html', title='Tag Management')


@app.route('/scada/recipes')
def scada_recipes():
    """Recipe management dashboard"""
    return render_template('scada/recipes.html', title='Recipe Management')


# =============================================================================
# MES DASHBOARDS
# =============================================================================

@app.route('/mes')
def mes_dashboard():
    """Main MES dashboard"""
    return render_template('mes/dashboard.html', title='MES Dashboard')


@app.route('/mes/work-orders')
def mes_work_orders():
    """Work order management"""
    return render_template('mes/work_orders.html', title='Work Orders')


@app.route('/mes/scheduling')
def mes_scheduling():
    """Production scheduling"""
    return render_template('mes/scheduling.html', title='Scheduling')


@app.route('/mes/dispatch')
def mes_dispatch():
    """Dispatch list"""
    return render_template('mes/dispatch.html', title='Dispatch List')


@app.route('/mes/oee')
def mes_oee():
    """OEE dashboard"""
    return render_template('mes/oee.html', title='OEE')


# =============================================================================
# ERP DASHBOARDS
# =============================================================================

@app.route('/erp')
def erp_dashboard():
    """Main ERP dashboard"""
    return render_template('erp/dashboard.html', title='ERP Dashboard')


@app.route('/erp/sales')
def erp_sales():
    """Sales management"""
    return render_template('erp/sales.html', title='Sales')


@app.route('/erp/procurement')
def erp_procurement():
    """Procurement management"""
    return render_template('erp/procurement.html', title='Procurement')


@app.route('/erp/inventory')
def erp_inventory():
    """Inventory management"""
    return render_template('erp/inventory.html', title='Inventory')


@app.route('/erp/mrp')
def erp_mrp():
    """MRP dashboard"""
    return render_template('erp/mrp.html', title='MRP')


# =============================================================================
# QMS DASHBOARDS
# =============================================================================

@app.route('/qms')
def qms_dashboard():
    """Main QMS dashboard"""
    return render_template('qms/dashboard.html', title='QMS Dashboard')


@app.route('/qms/documents')
def qms_documents():
    """Document control"""
    return render_template('qms/documents.html', title='Document Control')


@app.route('/qms/ncr')
def qms_ncr():
    """NCR management"""
    return render_template('qms/ncr.html', title='NCR')


@app.route('/qms/capa')
def qms_capa():
    """CAPA management"""
    return render_template('qms/capa.html', title='CAPA')


@app.route('/qms/audits')
def qms_audits():
    """Audit management"""
    return render_template('qms/audits.html', title='Audits')


# =============================================================================
# CMMS DASHBOARDS
# =============================================================================

@app.route('/cmms')
def cmms_dashboard():
    """Main CMMS dashboard"""
    return render_template('cmms/dashboard.html', title='CMMS Dashboard')


@app.route('/cmms/assets')
def cmms_assets():
    """Asset management"""
    return render_template('cmms/assets.html', title='Assets')


@app.route('/cmms/maintenance')
def cmms_maintenance():
    """Maintenance management"""
    return render_template('cmms/maintenance.html', title='Maintenance')


# =============================================================================
# LEGO DASHBOARDS
# =============================================================================

@app.route('/lego')
def lego_dashboard():
    """LEGO brick designer"""
    return render_template('lego/dashboard.html', title='LEGO Designer')


@app.route('/lego/catalog')
def lego_catalog():
    """Brick catalog"""
    return render_template('lego/catalog.html', title='Brick Catalog')


# =============================================================================
# WEBSOCKET EVENTS
# =============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected")


@socketio.on('subscribe_machine')
def handle_subscribe_machine(data):
    """Subscribe to machine updates"""
    machine_id = data.get('machine_id')
    logger.info(f"Client subscribed to machine: {machine_id}")


@socketio.on('subscribe_alarms')
def handle_subscribe_alarms():
    """Subscribe to alarm updates"""
    logger.info("Client subscribed to alarms")


@socketio.on('subscribe_tags')
def handle_subscribe_tags(data):
    """Subscribe to tag value updates"""
    tag_ids = data.get('tag_ids', [])
    logger.info(f"Client subscribed to {len(tag_ids)} tags")


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


# =============================================================================
# MAIN
# =============================================================================

def create_app():
    """Create and configure the application"""
    register_blueprints()
    initialize_services()
    return app


if __name__ == '__main__':
    create_app()
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=5000, 
        debug=os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    )
