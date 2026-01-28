"""
Portal Routes - SCADA Dashboard Navigation Module.

This module provides Flask Blueprint routes for serving all 41 production-ready
SCADA dashboard templates in the Flask CNC SCADA system.

Dashboard Categories:
    - Core Operations: Portal Home, Factory Cell, Scheduling, G-Code
    - Manufacturing Execution (MES): Work Orders, Inventory, Traceability, Batch Tracking
    - Quality & Inspection: Quality Dashboard, Scrap Analysis, Tool Management
    - Performance Analytics: OEE, Analytics, Machine Utilization, KPI Scorecard
    - Predictive & AI: Predictive Maintenance, AI Assistant, Digital Twin
    - Maintenance & Safety: Maintenance Scheduler, Downtime, Safety Dashboard, Alarms
    - Operations Management: Shift Handover, Energy Monitoring, Recipe Management
    - Infrastructure: System Health, Sensors, Settings, Audit Log, Reports

URL Prefix: /portal

Example Usage:
    Access dashboards via browser:
    - http://localhost:5001/portal           -> Portal Home (navigation hub)
    - http://localhost:5001/portal/oee       -> OEE Dashboard
    - http://localhost:5001/portal/quality   -> Quality Dashboard
    - http://localhost:5001/portal/predictive -> Predictive Maintenance

All templates extend base.html and use consistent dark theme styling.

Author: Flask CNC SCADA System
Version: 2.0
"""

from flask import Blueprint, render_template
import logging

logger = logging.getLogger(__name__)

portal_bp = Blueprint('portal', __name__, url_prefix='/portal')


# =============================================================================
# Main Portal
# =============================================================================

@portal_bp.route('/')
def portal_home():
    """Main navigation portal with links to all dashboards."""
    return render_template('portal.html')


# =============================================================================
# Operations Dashboards
# =============================================================================

@portal_bp.route('/mes')
def mes_dashboard():
    """MES Dashboard - Work orders, labor tracking, dispatching."""
    return render_template('mes_dashboard.html')


@portal_bp.route('/oee')
def oee_dashboard():
    """OEE Dashboard - Overall Equipment Effectiveness metrics."""
    return render_template('oee_dashboard.html')


@portal_bp.route('/scheduling')
def scheduling_dashboard():
    """Scheduling Dashboard - Production scheduling."""
    return render_template('scheduling.html')


# =============================================================================
# Quality Dashboards
# =============================================================================

@portal_bp.route('/quality')
def quality_dashboard():
    """Quality Dashboard - SPC, FMEA, inspection."""
    return render_template('quality_dashboard.html')


@portal_bp.route('/traceability')
def traceability_dashboard():
    """Traceability Dashboard - Genealogy, compliance, recall support."""
    return render_template('traceability_dashboard.html')


# =============================================================================
# Analytics Dashboards
# =============================================================================

@portal_bp.route('/analytics')
def analytics_dashboard():
    """Analytics Dashboard - Vibration, anomaly detection, predictive maintenance."""
    return render_template('analytics_dashboard.html')


@portal_bp.route('/sensors')
def sensors_dashboard():
    """Sensors Dashboard - Real-time sensor monitoring."""
    return render_template('sensors.html')


# =============================================================================
# Digital Twin / Integration
# =============================================================================

@portal_bp.route('/factory')
def factory_dashboard():
    """Factory Dashboard - Digital twin visualization."""
    try:
        return render_template('dashboard/factory.html')
    except Exception:
        return render_template('dashboard.html')


@portal_bp.route('/digital-twin')
def digital_twin_dashboard():
    """Digital Twin Dashboard - 3D factory visualization."""
    return render_template('digital_twin_dashboard.html')


@portal_bp.route('/mcp')
def mcp_dashboard():
    """MCP Dashboard - Model Context Protocol integration."""
    return render_template('mcp_dashboard.html')


# =============================================================================
# Downtime Management
# =============================================================================

@portal_bp.route('/downtime')
def downtime_dashboard():
    """Downtime Dashboard - Equipment downtime tracking and analysis."""
    return render_template('downtime_dashboard.html')


# =============================================================================
# AI Assistant
# =============================================================================

@portal_bp.route('/assistant')
def assistant_dashboard():
    """AI Assistant Dashboard - Claude-powered manufacturing assistant."""
    return render_template('assistant_dashboard.html')


# =============================================================================
# Inventory Management
# =============================================================================

@portal_bp.route('/inventory')
def inventory_dashboard():
    """Inventory Dashboard - Parts, materials, and tool inventory."""
    return render_template('inventory_dashboard.html')


# =============================================================================
# API Documentation
# =============================================================================

@portal_bp.route('/api-docs')
def api_docs():
    """Interactive API Documentation."""
    return render_template('api_docs.html')


# =============================================================================
# G-Code & CAM
# =============================================================================

@portal_bp.route('/gcode')
def gcode_dashboard():
    """G-Code Manager - Program library, backplot, validation."""
    return render_template('gcode_dashboard.html')


@portal_bp.route('/predictive')
def predictive_dashboard():
    """Predictive Maintenance Dashboard - ML predictions, alerts."""
    return render_template('predictive_dashboard.html')


@portal_bp.route('/system-health')
def system_health():
    """System Health Dashboard - Service status, performance."""
    return render_template('system_health.html')


# =============================================================================
# Notifications
# =============================================================================

@portal_bp.route('/notifications')
def notifications():
    """Notification Center - Alert history and management."""
    return render_template('notifications.html')


@portal_bp.route('/settings')
def settings():
    """User Settings - Profile, preferences, and configuration."""
    return render_template('settings.html')


@portal_bp.route('/reports')
def reports():
    """Report Center - Generate and manage reports."""
    return render_template('reports.html')


@portal_bp.route('/audit-log')
def audit_log():
    """Audit Log - System event history and tracking."""
    return render_template('audit_log.html')


@portal_bp.route('/machine-comparison')
def machine_comparison():
    """Machine Comparison - Side-by-side performance analysis."""
    return render_template('machine_comparison.html')


@portal_bp.route('/shift-handover')
def shift_handover():
    """Shift Handover - Digital logbook for shift transitions."""
    return render_template('shift_handover.html')


# =============================================================================
# Tool & Maintenance Management
# =============================================================================

@portal_bp.route('/tools')
def tool_management():
    """Tool Management - Tool inventory, life tracking, offsets."""
    return render_template('tool_management.html')


@portal_bp.route('/maintenance')
def maintenance_scheduler():
    """Maintenance Scheduler - Preventive maintenance planning."""
    return render_template('maintenance_scheduler.html')


@portal_bp.route('/energy')
def energy_monitoring():
    """Energy Monitoring - Power consumption and efficiency tracking."""
    return render_template('energy_monitoring.html')


@portal_bp.route('/operators')
def operator_performance():
    """Operator Performance - Productivity and skills tracking."""
    return render_template('operator_performance.html')


@portal_bp.route('/workorder/<wo_id>')
def workorder_detail(wo_id):
    """Work Order Detail - Comprehensive work order view."""
    return render_template('workorder_detail.html', wo_id=wo_id)


# =============================================================================
# Configuration & Safety
# =============================================================================

@portal_bp.route('/alarms')
def alarm_config():
    """Alarm Configuration - Alert rules and thresholds."""
    return render_template('alarm_config.html')


@portal_bp.route('/recipes')
def recipe_management():
    """Recipe Management - CNC program parameters and presets."""
    return render_template('recipe_management.html')


@portal_bp.route('/floor-map')
def floor_map():
    """Floor Map - Visual factory floor layout with machine positions."""
    return render_template('floor_map.html')


@portal_bp.route('/safety')
def safety_dashboard():
    """Safety Dashboard - Safety incidents, compliance, and training."""
    return render_template('safety_dashboard.html')


@portal_bp.route('/job-costing')
def job_costing():
    """Job Costing - Production cost tracking and analysis."""
    return render_template('job_costing.html')


@portal_bp.route('/batch-tracking')
def batch_tracking():
    """Batch/Lot Tracking - Production batch and lot number traceability."""
    return render_template('batch_tracking.html')


@portal_bp.route('/scrap-analysis')
def scrap_analysis():
    """Scrap Analysis - Scrap rates, causes, and reduction tracking."""
    return render_template('scrap_analysis.html')


@portal_bp.route('/machine-utilization')
def machine_utilization():
    """Machine Utilization - Detailed machine usage analytics."""
    return render_template('machine_utilization.html')


@portal_bp.route('/kpi-scorecard')
def kpi_scorecard():
    """KPI Scorecard - Executive summary dashboard."""
    return render_template('kpi_scorecard.html')


@portal_bp.route('/customer-portal')
def customer_portal():
    """Customer Portal - Customer-facing order status view."""
    return render_template('customer_portal.html')
