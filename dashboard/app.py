"""
LEGO MCP Dashboard - Flask Application v8.0

A world-class web dashboard for the LEGO MCP Cyber-Physical Production System.
ISA-95 compliant Manufacturing Execution System with Industry 4.0/5.0 capabilities.

V8.0 Features:
- Unified Command Center (UCC) - Real-time monitoring and control
- Algorithm-to-Action Pipeline - AI decisions to physical actions
- Co-Simulation Engine - DES + PINN Digital Twin + Monte Carlo
- Multi-Agent Orchestration - Coordinated autonomous operations

Core Features:
- Manufacturing Operations (MES) - Work orders, scheduling, OEE
- Quality Management - SPC, inspections, FMEA, QFD, zero-defect
- ERP Integration - BOM, costing, procurement, demand
- MRP Engine - Material planning, capacity, ATP/CTP
- Digital Twin - Real-time state, CRDTs, PINNs physics simulation
- AI Copilot - 150+ MCP tools, 3 autonomous agents
- Sustainability - Carbon tracking, LCA, ESG reporting
- ROS2 Bridge - Lifecycle control, equipment monitoring
- SCADA Integration - OPC UA, MTConnect, Sparkplug B
"""

import os
import sys
from pathlib import Path
from flask import Flask, render_template, jsonify

# Optional SocketIO support
try:
    from flask_socketio import SocketIO

    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    SocketIO = None

# Add paths for imports
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "shared"))
sys.path.insert(0, str(BASE_DIR / "mcp-server" / "src"))

# Initialize SocketIO (optional)
socketio = SocketIO() if SOCKETIO_AVAILABLE else None


def create_app(config_name=None):
    """Application factory for LEGO MCP v7.0 Industry 4.0/5.0 Manufacturing Platform."""

    app = Flask(__name__)

    # Load configuration
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    from config import config

    app.config.from_object(config.get(config_name, config["default"]))

    # Initialize extensions
    if SOCKETIO_AVAILABLE and socketio:
        socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")

    # ========================================
    # Core UI Blueprints (Phases 1-2)
    # ========================================
    from routes.main import main_bp
    from routes.catalog import catalog_bp
    from routes.builder import builder_bp
    from routes.files import files_bp
    from routes.history import history_bp
    from routes.status import status_bp
    from routes.tools import tools_bp
    from routes.settings import settings_bp
    from routes.api import api_bp

    # Phase 2: Digital Twin UI blueprints
    from routes.workspace import workspace_bp
    from routes.scan import scan_bp
    from routes.collection import collection_bp
    from routes.builds_routes import builds_bp
    from routes.insights import insights_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(catalog_bp, url_prefix="/catalog")
    app.register_blueprint(builder_bp, url_prefix="/builder")
    app.register_blueprint(files_bp, url_prefix="/files")
    app.register_blueprint(history_bp, url_prefix="/history")
    app.register_blueprint(status_bp, url_prefix="/status")
    app.register_blueprint(tools_bp, url_prefix="/tools")
    app.register_blueprint(settings_bp, url_prefix="/settings")
    app.register_blueprint(api_bp, url_prefix="/api")

    # Phase 2: Digital Twin routes
    app.register_blueprint(workspace_bp, url_prefix="/workspace")
    app.register_blueprint(scan_bp, url_prefix="/scan")

    # Auto-configure IP camera for Docker (webcam stream from host)
    try:
        from services.vision import get_camera_manager
        webcam_url = os.environ.get("WEBCAM_STREAM_URL", "http://host.docker.internal:8081/video")
        camera_manager = get_camera_manager()
        # Check if webcam already added (prevents duplicates on app reload)
        existing_urls = [c.url for c in camera_manager.list_cameras()]
        if webcam_url not in existing_urls:
            camera_manager.add_ip_camera(webcam_url, "Logitech C920e (Webcam)")
            app.logger.info(f"Added webcam stream: {webcam_url}")
    except Exception as e:
        app.logger.warning(f"Could not add webcam stream: {e}")
    app.register_blueprint(collection_bp, url_prefix="/collection")
    app.register_blueprint(builds_bp, url_prefix="/builds")
    app.register_blueprint(insights_bp, url_prefix="/insights")

    # ========================================
    # World-Class v5.0 API Blueprints (Phases 3-25)
    # ========================================

    # Phase 3: Manufacturing Operations (MES) - /api/mes/*
    from routes.manufacturing import manufacturing_bp
    app.register_blueprint(manufacturing_bp)

    # Phase 3: Quality Management - /api/quality/*
    from routes.quality import quality_bp
    app.register_blueprint(quality_bp)

    # Phase 4: ERP Integration - /api/erp/*
    from routes.erp import erp_bp
    app.register_blueprint(erp_bp)

    # Phase 5: MRP Engine - /api/mrp/*
    from routes.mrp import mrp_bp
    app.register_blueprint(mrp_bp)

    # Phase 6: Digital Twin API - /api/twin/*
    from routes.digital_twin import digital_twin_bp
    app.register_blueprint(digital_twin_bp)

    # Phase 7: Event-Driven Architecture - /api/events/*
    from routes.events import events_bp
    app.register_blueprint(events_bp)

    # Phase 17: AI Copilot - /api/ai/*
    from routes.ai import ai_bp
    app.register_blueprint(ai_bp)

    # Phase 12: Advanced Scheduling - /api/scheduling/*
    from routes.scheduling import scheduling_bp
    app.register_blueprint(scheduling_bp)

    # Phase 18: DES Simulation - /api/simulation/*
    from routes.simulation import simulation_bp
    app.register_blueprint(simulation_bp)

    # Phase 19: Sustainability & Carbon Tracking - /api/sustainability/*
    from routes.sustainability import sustainability_bp
    app.register_blueprint(sustainability_bp)

    # Phase 20: HMI & Operator Interface - /api/hmi/*
    from routes.hmi import hmi_bp
    app.register_blueprint(hmi_bp)

    # Phase 22: Supply Chain Integration - /api/supply-chain/*
    from routes.supply_chain import supply_chain_bp
    app.register_blueprint(supply_chain_bp)

    # Phase 24: Regulatory Compliance - /api/compliance/*
    from routes.compliance import compliance_bp
    app.register_blueprint(compliance_bp)

    # Phase 25: Edge Computing & IIoT - /api/edge/*
    from routes.edge import edge_bp
    app.register_blueprint(edge_bp)

    # ========================================
    # Unity Digital Twin Integration (ISO 23247)
    # ========================================
    from routes.unity import unity_bp
    app.register_blueprint(unity_bp)

    # ========================================
    # Robotics Control (ISO 10218 / ISO/TS 15066)
    # ========================================
    from routes.robotics import robotics_bp
    app.register_blueprint(robotics_bp)

    # ========================================
    # v7.0 Supervision Tree (OTP-style Fault Tolerance)
    # ========================================
    from routes.supervision import supervision_bp
    app.register_blueprint(supervision_bp)

    # ========================================
    # V8.0 Unified Command Center
    # ========================================
    from routes.command_center import command_center_bp
    app.register_blueprint(command_center_bp)

    # ========================================
    # V8.0 Health Check & Monitoring
    # ========================================
    from routes.health import health_bp
    app.register_blueprint(health_bp)

    # Prometheus metrics endpoint
    from services.monitoring import metrics_bp
    app.register_blueprint(metrics_bp)

    # ========================================
    # v6.0 World-Class Research Platform Extensions
    # ========================================
    # Phase 1: Multi-Agent Orchestration - /api/v6/agents/*
    from routes.ai import orchestration_bp
    app.register_blueprint(orchestration_bp)

    # Phase 2: Causal AI & Explainability - /api/v6/causal/*
    from routes.ai import causal_bp
    app.register_blueprint(causal_bp)

    # Phase 3: Generative Design - /api/v6/generative/*
    from routes.ai import generative_bp
    app.register_blueprint(generative_bp)

    # Phase 4: Closed-Loop Learning - /api/v6/closed-loop/*
    from routes.ai import closed_loop_bp
    app.register_blueprint(closed_loop_bp)

    # Phase 5: Algorithm-to-Action Bridge - /api/v6/actions/*
    from routes.ai import actions_bp
    app.register_blueprint(actions_bp)

    # Phase 6: Research Platform - /api/v6/research/*
    from routes.ai import research_bp
    app.register_blueprint(research_bp)

    # Register WebSocket events (if available)
    if SOCKETIO_AVAILABLE and socketio:
        from websocket.events import (
            register_events,
            register_phase2_events,
            register_manufacturing_events,
            register_vr_training_events,
            register_robotics_events,
            register_unity_events,
            register_supply_chain_events,
            register_command_center_events,
        )

        # Core events
        register_events(socketio)

        # Phase 2: Digital Twin events
        register_phase2_events(socketio)

        # Phase 5: Manufacturing events
        register_manufacturing_events(socketio)

        # Phase 6: VR Training events
        register_vr_training_events(socketio)

        # Phase 7: Robotics events (ISO 10218)
        register_robotics_events(socketio)

        # Phase 8: Unity Digital Twin events (ISO 23247)
        register_unity_events(socketio)

        # Phase 9: Supply Chain Twin events
        register_supply_chain_events(socketio)

        # V8: Command Center events
        register_command_center_events(socketio)

    # ========================================
    # Error Handlers with API Support
    # ========================================
    @app.errorhandler(404)
    def not_found(e):
        # Return JSON for API routes, HTML for UI routes
        if hasattr(e, 'description') and 'request' in dir():
            from flask import request
            if request.path.startswith('/api/'):
                return jsonify({
                    'error': 'Not Found',
                    'message': f'Endpoint {request.path} not found',
                    'status': 404
                }), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import request
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Internal Server Error',
                'message': str(e),
                'status': 500
            }), 500
        return render_template("errors/500.html"), 500

    # ========================================
    # Context Processors
    # ========================================
    @app.context_processor
    def inject_globals():
        """Inject global variables into templates."""
        from services.status_service import get_quick_status

        return {"services_status": get_quick_status()}

    # ========================================
    # API Health Check
    # ========================================
    @app.route('/api/v5/health')
    def api_health():
        """Health check endpoint for the v5.0 API."""
        return jsonify({
            'status': 'healthy',
            'version': '5.0.0',
            'platform': 'LegoMCP World-Class CPPS',
            'modules': {
                'manufacturing': True,
                'quality': True,
                'erp': True,
                'mrp': True,
                'digital_twin': True,
                'unity_3d': True,
                'robotics': True,
                'vr_training': True,
                'supply_chain_twin': True,
            },
            'websocket_events': {
                'core': True,
                'phase2_digital_twin': True,
                'manufacturing': True,
                'vr_training': True,
                'robotics': True,
                'unity': True,
                'supply_chain': True,
            }
        })

    @app.route('/api/v6/health')
    def api_v6_health():
        """Health check endpoint for the v6.0 Research Platform API."""
        return jsonify({
            'status': 'healthy',
            'version': '6.0.0',
            'platform': 'LegoMCP World-Class Manufacturing Research Platform',
            'modules': {
                'orchestration': True,
                'causal_ai': True,
                'generative_design': True,
                'closed_loop': True,
                'actions': True,
                'research': True,
            },
            'capabilities': {
                'multi_agent_coordination': True,
                'counterfactual_reasoning': True,
                'topology_optimization': True,
                'active_learning': True,
                'equipment_control': True,
                'experiment_tracking': True,
            }
        })

    @app.route('/api/v8/health')
    def api_v8_health():
        """Health check endpoint for the V8.0 Command & Control Platform."""
        return jsonify({
            'status': 'healthy',
            'version': '8.0.0',
            'platform': 'LegoMCP V8 Unified Command & Control Platform',
            'modules': {
                'command_center': True,
                'orchestration': True,
                'cosimulation': True,
                'decision_engine': True,
                'action_console': True,
                'alert_manager': True,
                'kpi_aggregator': True,
            },
            'capabilities': {
                'unified_command_center': True,
                'algorithm_to_action': True,
                'co_simulation': True,
                'event_correlation': True,
                'real_time_kpis': True,
                'approval_workflows': True,
                'scenario_analysis': True,
            },
            'simulation_engines': {
                'des': True,
                'pinn_digital_twin': True,
                'monte_carlo': True,
                'fmu_fmi': True,
            },
            'websocket_events': {
                'command_center': True,
                'action_console': True,
                'cosimulation': True,
                'priority_alerts': True,
            }
        })

    return app


# Create app instance for development
app = create_app()


if __name__ == "__main__":
    if SOCKETIO_AVAILABLE and socketio:
        socketio.run(app, host="0.0.0.0", port=5000, debug=True)
    else:
        app.run(host="0.0.0.0", port=5000, debug=True)
