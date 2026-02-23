"""
Web Routes Blueprint
====================
All web page routes for the LEGO Factory application.
"""

from flask import Blueprint, render_template

# Create blueprints for different sections (using _web suffix to avoid conflicts)
dashboard_bp = Blueprint('dashboard_web', __name__)
scada_bp = Blueprint('scada_web', __name__, url_prefix='/scada')
mes_bp = Blueprint('mes_web', __name__, url_prefix='/mes')
erp_bp = Blueprint('erp_web', __name__, url_prefix='/erp')
lego_bp = Blueprint('lego_web', __name__, url_prefix='/lego')
qms_bp = Blueprint('qms_web', __name__, url_prefix='/qms')
cmms_bp = Blueprint('cmms_web', __name__, url_prefix='/cmms')
unity_bp = Blueprint('unity_web', __name__, url_prefix='/unity')
ml_bp = Blueprint('ml_web', __name__, url_prefix='/ml')
auth_bp = Blueprint('auth_web', __name__)


# =============================================================================
# Dashboard Routes
# =============================================================================

@dashboard_bp.route('/')
def home():
    """Landing page with all sections."""
    return render_template('dashboard/index.html')


# =============================================================================
# SCADA Routes (Level 1 & 2)
# =============================================================================

@scada_bp.route('/control')
def operator_control():
    """Level 1 CNC operator control panel - jog, MDI, status."""
    return render_template('scada/operator_dashboard.html')


@scada_bp.route('/machines')
def machines():
    """Machine overview dashboard."""
    return render_template('scada/machines.html')


@scada_bp.route('/machines/<machine_id>')
def machine_detail(machine_id):
    """Individual machine detail page."""
    return render_template('scada/machine_detail.html', machine_id=machine_id)


@scada_bp.route('/machines/<machine_id>/control')
def machine_control(machine_id):
    """Level 1 CNC control dashboard - jog, MDI, G-code execution."""
    return render_template('scada/machine_control.html', machine_id=machine_id)


@scada_bp.route('/alarms')
def alarms():
    """Alarm management dashboard."""
    return render_template('scada/alarms.html')


@scada_bp.route('/alarms/<alarm_id>')
def alarm_detail(alarm_id):
    """Individual alarm detail page."""
    return render_template('scada/alarm_detail.html', alarm_id=alarm_id)


@scada_bp.route('/historian')
def historian():
    """Historian/trend dashboard."""
    return render_template('scada/historian.html')


@scada_bp.route('/recipes')
def recipes():
    """Recipe management dashboard."""
    return render_template('scada/recipes.html')


@scada_bp.route('/recipes/<recipe_id>')
def recipe_detail(recipe_id):
    """Individual recipe detail page."""
    return render_template('scada/recipe_detail.html', recipe_id=recipe_id)


@scada_bp.route('/sensors')
def sensors():
    """Sensor DAQ dashboard - MCC USB-1608G, Arduino."""
    return render_template('scada/sensors.html')


@scada_bp.route('/gcode')
def gcode_manager():
    """G-code manager dashboard - editor, backplot, analysis."""
    return render_template('scada/gcode_manager.html')


@scada_bp.route('/downtime')
def downtime_analysis():
    """Downtime Pareto analysis dashboard."""
    return render_template('scada/downtime_analysis.html')


# =============================================================================
# MES Routes (Level 3)
# =============================================================================

@mes_bp.route('/work-orders')
def work_orders():
    """Work order management."""
    return render_template('mes/work_orders.html')


@mes_bp.route('/work-orders/<wo_number>')
def work_order_detail(wo_number):
    """Work order detail page."""
    return render_template('mes/work_order_detail.html', wo_number=wo_number)


@mes_bp.route('/scheduling')
def scheduling():
    """Production scheduling Gantt chart."""
    return render_template('mes/scheduling.html')


@mes_bp.route('/oee')
def oee():
    """OEE dashboard."""
    return render_template('mes/oee.html')


@mes_bp.route('/resources')
def resources():
    """Resource dashboard - MESA-11 Resource Allocation & Status."""
    return render_template('mes/resources.html')


@mes_bp.route('/resources/<machine_id>')
def resource_detail(machine_id):
    """Machine resource detail view."""
    return render_template('mes/resource_detail.html', machine_id=machine_id)


@mes_bp.route('/materials')
def materials():
    """Material inventory dashboard."""
    return render_template('mes/materials.html')


@mes_bp.route('/algorithm-compare')
def algorithm_compare():
    """Scheduling algorithm comparison dashboard."""
    return render_template('mes/algorithm_compare.html')


@mes_bp.route('/dispatch')
def dispatch():
    """Dispatch dashboard - MESA-11 Dispatching Production Units."""
    return render_template('mes/dispatch.html')


@mes_bp.route('/genealogy')
def genealogy():
    """Genealogy and traceability dashboard - MESA-11 Product Tracking."""
    return render_template('mes/genealogy.html')


@mes_bp.route('/process-monitor')
def process_monitor():
    """Process monitor dashboard - MESA-11 Process Management."""
    return render_template('mes/process_monitor.html')


@mes_bp.route('/performance')
def performance():
    """Performance analysis dashboard - MESA-11 Performance Analysis."""
    return render_template('mes/performance.html')


@mes_bp.route('/shift-report')
def shift_report():
    """Shift handover report - printable shift summary."""
    return render_template('mes/shift_report.html')


@mes_bp.route('/operator')
def operator():
    """Operator workstation - combined view for production workers."""
    return render_template('mes/operator.html')


@mes_bp.route('/capacity')
def capacity():
    """Capacity planning & bottleneck analysis."""
    return render_template('mes/capacity.html')


@mes_bp.route('/kanban')
def kanban():
    """WIP Kanban board."""
    return render_template('mes/kanban.html')


@mes_bp.route('/timeclock')
def timeclock():
    """Time clock & labor tracking."""
    return render_template('mes/timeclock.html')


@mes_bp.route('/line-balance')
def line_balance():
    """Takt time & line balancing."""
    return render_template('mes/line_balance.html')


@mes_bp.route('/downtime')
def downtime():
    """MES production downtime tracking."""
    return render_template('mes/downtime.html')


@mes_bp.route('/labor')
def labor():
    """Labor management & skills matrix."""
    return render_template('mes/labor.html')


@mes_bp.route('/setup-analysis')
def setup_analysis():
    """Setup time & SMED tracking."""
    return render_template('mes/setup_analysis.html')


@mes_bp.route('/rework')
def rework():
    """Rework & scrap analysis."""
    return render_template('mes/rework_analysis.html')


@mes_bp.route('/shift-handover')
def shift_handover():
    """Shift handover checklist."""
    return render_template('mes/shift_handover.html')


# =============================================================================
# ERP Routes (Level 4)
# =============================================================================

@erp_bp.route('/sales-orders')
def sales_orders():
    """Sales order management."""
    return render_template('erp/sales_orders.html')


@erp_bp.route('/inventory')
def inventory():
    """Inventory management."""
    return render_template('erp/inventory.html')


@erp_bp.route('/mrp')
def mrp():
    """MRP dashboard."""
    return render_template('erp/mrp.html')


@erp_bp.route('/costing')
def costing():
    """Costing analysis dashboard."""
    return render_template('erp/costing.html')


@erp_bp.route('/vendors')
def vendors():
    """Vendor management."""
    return render_template('erp/vendors.html')


@erp_bp.route('/budget')
def budget():
    """Budget vs actual reporting."""
    return render_template('erp/budget_vs_actual.html')


@erp_bp.route('/job-costing')
def job_costing():
    """Job costing analysis."""
    return render_template('erp/job_costing.html')


@erp_bp.route('/cashflow')
def cashflow():
    """Cash flow dashboard."""
    return render_template('erp/cashflow.html')


@erp_bp.route('/fixed-assets')
def fixed_assets():
    """Fixed asset register & depreciation."""
    return render_template('erp/fixed_assets.html')


@erp_bp.route('/customers')
def customers():
    """Customer management."""
    return render_template('erp/customers.html')


@erp_bp.route('/items')
def items():
    """Item master."""
    return render_template('erp/items.html')


@erp_bp.route('/purchase-orders')
def purchase_orders():
    """Purchase order management."""
    return render_template('erp/purchase_orders.html')


# =============================================================================
# LEGO Design Routes
# =============================================================================

@lego_bp.route('/catalog')
def catalog():
    """Brick catalog."""
    return render_template('lego/catalog.html')


@lego_bp.route('/designer')
def designer():
    """Brick designer."""
    return render_template('lego/designer.html')


@lego_bp.route('/export-jobs')
def export_jobs():
    """Export jobs management."""
    return render_template('lego/export_jobs.html')


# =============================================================================
# QMS Routes
# =============================================================================

@qms_bp.route('/documents')
def documents():
    """Document control."""
    return render_template('qms/documents.html')


@qms_bp.route('/ncr')
def ncr_list():
    """NCR/CAPA list."""
    return render_template('qms/ncr_list.html')


@qms_bp.route('/ncrs/<ncr_number>')
def ncr_detail(ncr_number):
    """NCR detail view."""
    return render_template('qms/ncr_detail.html', ncr_number=ncr_number)


@qms_bp.route('/spc')
def spc():
    """SPC control charts dashboard."""
    return render_template('qms/spc.html')


@qms_bp.route('/inspections')
def inspections():
    """Quality inspections dashboard."""
    return render_template('qms/inspection.html')


@qms_bp.route('/supplier-scorecard')
def supplier_scorecard():
    """Supplier quality scorecard."""
    return render_template('qms/supplier_scorecard.html')


@qms_bp.route('/capas')
def capas():
    """CAPA list."""
    return render_template('qms/capa_list.html')


@qms_bp.route('/audits')
def audits():
    """Audit management."""
    return render_template('qms/audits.html')


@qms_bp.route('/calibration')
def calibration():
    """Calibration management."""
    return render_template('qms/calibration.html')


@qms_bp.route('/training')
def training():
    """Training management."""
    return render_template('qms/training.html')


# =============================================================================
# CMMS Routes
# =============================================================================

@cmms_bp.route('/assets')
def assets():
    """Asset management."""
    return render_template('cmms/assets.html')


@cmms_bp.route('/work-orders')
def cmms_work_orders():
    """Maintenance work orders."""
    return render_template('cmms/work_orders.html')


@cmms_bp.route('/reliability')
def reliability():
    """MTBF/MTTR reliability dashboard."""
    return render_template('cmms/reliability.html')


@cmms_bp.route('/pm-calendar')
def pm_calendar():
    """PM calendar view."""
    return render_template('cmms/pm_calendar.html')


@cmms_bp.route('/pm-schedules')
def pm_schedules():
    """PM schedules list."""
    return render_template('cmms/pm_schedules.html')


@cmms_bp.route('/spare-parts')
def spare_parts():
    """Spare parts inventory."""
    return render_template('cmms/spare_parts.html')


# =============================================================================
# Unity Digital Twin Routes
# =============================================================================

@unity_bp.route('/viewer')
def viewer():
    """3D digital twin viewer."""
    return render_template('unity/viewer.html', scene={'entities': {}}, config={})


# =============================================================================
# ML/Analytics Routes
# =============================================================================

@ml_bp.route('/fingerprint')
def fingerprint():
    """G-code fingerprinting dashboard."""
    return render_template('ml/fingerprint.html')


@ml_bp.route('/anomaly')
def anomaly():
    """Anomaly detection dashboard."""
    return render_template('ml/anomaly.html')


# =============================================================================
# Auth Routes
# =============================================================================

@auth_bp.route('/login')
def login():
    """Login page."""
    return render_template('auth/login.html')


@auth_bp.route('/profile')
def profile():
    """User profile page."""
    return render_template('auth/profile.html')


@auth_bp.route('/settings')
def settings():
    """User settings page."""
    return render_template('auth/settings.html')


def register_web_routes(app):
    """Register all web route blueprints."""
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(scada_bp)
    app.register_blueprint(mes_bp)
    app.register_blueprint(erp_bp)
    app.register_blueprint(lego_bp)
    app.register_blueprint(qms_bp)
    app.register_blueprint(cmms_bp)
    app.register_blueprint(unity_bp)
    app.register_blueprint(ml_bp)
    app.register_blueprint(auth_bp)

    # CRM web routes
    from api.routes.crm_views import crm_bp
    app.register_blueprint(crm_bp)

    # Simulation web routes
    from api.routes.simulation_views import simulation_views
    app.register_blueprint(simulation_views)
