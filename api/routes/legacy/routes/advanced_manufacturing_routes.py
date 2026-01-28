"""
Advanced Manufacturing API Routes
=================================
Unified REST API endpoints for all advanced Fusion 360 integration services.

Includes:
- Quality & Inspection (FAI, SPC, probing)
- Machining Simulation (cutting forces, thermal, chatter)
- Intelligent Manufacturing (AI optimization, toolpath repair)
- Business Integration (costing, quotes, production orders)
- Collaboration (reviews, annotations, version control)
- Advanced Integration (AR/VR, IoT, cloud processing, digital thread)

Author: Flask CNC SCADA System
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('advanced_manufacturing', __name__, url_prefix='/api/advanced')


# =============================================================================
# Quality & Inspection Routes
# =============================================================================

@bp.route('/quality/fai', methods=['POST'])
def create_fai_report():
    """Create a First Article Inspection report."""
    try:
        from services.quality_inspection_service import get_quality_inspection_service
        service = get_quality_inspection_service()

        data = request.get_json()
        report = service.fai.create_fai_report(
            part_number=data.get('part_number'),
            part_name=data.get('part_name'),
            serial_number=data.get('serial_number'),
            inspection_points=data.get('inspection_points', []),
            fusion_document_id=data.get('fusion_document_id'),
            inspector_id=data.get('inspector_id'),
            inspector_name=data.get('inspector_name')
        )

        return jsonify({
            'status': 'success',
            'report_id': report.report_id,
            'report_number': report.report_number
        })
    except Exception as e:
        logger.error(f"FAI report creation failed: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/quality/fai/<report_id>', methods=['GET'])
def get_fai_report(report_id):
    """Get FAI report by ID."""
    try:
        from services.quality_inspection_service import get_quality_inspection_service
        service = get_quality_inspection_service()

        report = service.fai.get_report(report_id)
        if not report:
            return jsonify({'error': 'Report not found'}), 404

        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/quality/fai/<report_id>/as9102', methods=['GET'])
def get_as9102_form(report_id):
    """Get AS9102 form data."""
    try:
        from services.quality_inspection_service import get_quality_inspection_service
        service = get_quality_inspection_service()

        form_data = service.fai.generate_as9102_form(report_id)
        return jsonify(form_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/quality/spc/analyze', methods=['POST'])
def analyze_spc():
    """Run SPC analysis on measurements."""
    try:
        from services.quality_inspection_service import get_quality_inspection_service
        service = get_quality_inspection_service()

        data = request.get_json()
        analysis = service.spc.analyze_measurements(
            characteristic_id=data.get('characteristic_id'),
            measurements=data.get('measurements', []),
            specification=data.get('specification', {})
        )

        return jsonify(analysis)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/quality/probing/generate', methods=['POST'])
def generate_probing_routine():
    """Generate probing routine from inspection plan."""
    try:
        from services.quality_inspection_service import get_quality_inspection_service
        service = get_quality_inspection_service()

        data = request.get_json()
        routine = service.probing.generate_probing_routine(
            inspection_points=data.get('inspection_points', []),
            machine_type=data.get('machine_type', 'cnc_mill'),
            probe_config=data.get('probe_config', {})
        )

        return jsonify({
            'routine_id': routine.routine_id,
            'gcode': routine.gcode_program,
            'estimated_time': routine.estimated_time_seconds
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Machining Simulation Routes
# =============================================================================

@bp.route('/simulation/cutting-force', methods=['POST'])
def calculate_cutting_force():
    """Calculate cutting forces."""
    try:
        from services.machining_simulation_service import get_machining_simulation_service
        service = get_machining_simulation_service()

        data = request.get_json()
        result = service.cutting_force.calculate_forces(
            tool_diameter_mm=data.get('tool_diameter_mm'),
            num_flutes=data.get('num_flutes', 4),
            helix_angle_deg=data.get('helix_angle_deg', 30),
            axial_depth_mm=data.get('axial_depth_mm'),
            radial_depth_mm=data.get('radial_depth_mm'),
            spindle_rpm=data.get('spindle_rpm'),
            feed_per_tooth_mm=data.get('feed_per_tooth_mm'),
            material=data.get('material', 'aluminum_6061')
        )

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/simulation/thermal', methods=['POST'])
def simulate_thermal():
    """Run thermal simulation."""
    try:
        from services.machining_simulation_service import get_machining_simulation_service
        service = get_machining_simulation_service()

        data = request.get_json()
        result = service.thermal.simulate_cutting_temperature(
            cutting_speed_mpm=data.get('cutting_speed_mpm'),
            feed_mm_rev=data.get('feed_mm_rev'),
            depth_of_cut_mm=data.get('depth_of_cut_mm'),
            material=data.get('material', 'steel_1018'),
            coolant_type=data.get('coolant_type', 'flood')
        )

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/simulation/chatter', methods=['POST'])
def predict_chatter():
    """Predict chatter stability."""
    try:
        from services.machining_simulation_service import get_machining_simulation_service
        service = get_machining_simulation_service()

        data = request.get_json()
        result = service.chatter.calculate_stability_lobes(
            tool_diameter_mm=data.get('tool_diameter_mm'),
            num_flutes=data.get('num_flutes', 4),
            tool_stickout_mm=data.get('tool_stickout_mm'),
            material=data.get('material', 'aluminum_6061'),
            rpm_range=data.get('rpm_range', (5000, 20000)),
            radial_immersion=data.get('radial_immersion', 0.5)
        )

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/simulation/surface-finish', methods=['POST'])
def predict_surface_finish():
    """Predict surface finish."""
    try:
        from services.machining_simulation_service import get_machining_simulation_service
        service = get_machining_simulation_service()

        data = request.get_json()
        result = service.surface_finish.predict_finish(
            feed_per_rev_mm=data.get('feed_per_rev_mm'),
            tool_nose_radius_mm=data.get('tool_nose_radius_mm'),
            cutting_speed_mpm=data.get('cutting_speed_mpm'),
            depth_of_cut_mm=data.get('depth_of_cut_mm'),
            material=data.get('material', 'aluminum_6061'),
            tool_condition=data.get('tool_condition', 'new')
        )

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Intelligent Manufacturing Routes
# =============================================================================

@bp.route('/intelligent/optimize', methods=['POST'])
def optimize_parameters():
    """Optimize cutting parameters using AI."""
    try:
        from services.intelligent_manufacturing_service import (
            get_intelligent_manufacturing_service,
            CuttingParameters,
            OptimizationObjective
        )
        service = get_intelligent_manufacturing_service()

        data = request.get_json()
        current_params = CuttingParameters(
            spindle_rpm=data.get('spindle_rpm'),
            feed_rate_mmpm=data.get('feed_rate_mmpm'),
            depth_of_cut_mm=data.get('depth_of_cut_mm'),
            width_of_cut_mm=data.get('width_of_cut_mm')
        )

        objective = OptimizationObjective(data.get('objective', 'balanced'))

        result = service.cam_optimizer.optimize_parameters(
            current_params=current_params,
            material=data.get('material'),
            tool_type=data.get('tool_type'),
            tool_diameter_mm=data.get('tool_diameter_mm'),
            operation_type=data.get('operation_type'),
            objective=objective,
            constraints=data.get('constraints', {})
        )

        return jsonify({
            'original': result.original_params.to_dict(),
            'optimized': result.optimized_params.to_dict(),
            'improvement': result.predicted_improvement,
            'confidence': result.confidence,
            'reasoning': result.reasoning
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/intelligent/toolpath/analyze', methods=['POST'])
def analyze_toolpath():
    """Analyze toolpath for issues."""
    try:
        from services.intelligent_manufacturing_service import get_intelligent_manufacturing_service
        service = get_intelligent_manufacturing_service()

        data = request.get_json()
        issues = service.toolpath_repair.analyze_toolpath(
            gcode_lines=data.get('gcode', '').split('\n'),
            stock_bounds=data.get('stock_bounds', {}),
            tool_diameter=data.get('tool_diameter'),
            material=data.get('material', 'aluminum_6061')
        )

        return jsonify({
            'issues': [
                {
                    'type': i.issue_type.value,
                    'severity': i.severity,
                    'line': i.line_number,
                    'description': i.description,
                    'fix': i.suggested_fix,
                    'auto_fixable': i.auto_fixable
                }
                for i in issues
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/intelligent/toolpath/repair', methods=['POST'])
def repair_toolpath():
    """Repair toolpath issues."""
    try:
        from services.intelligent_manufacturing_service import get_intelligent_manufacturing_service
        service = get_intelligent_manufacturing_service()

        data = request.get_json()
        gcode_lines = data.get('gcode', '').split('\n')

        # First analyze
        issues = service.toolpath_repair.analyze_toolpath(
            gcode_lines=gcode_lines,
            stock_bounds=data.get('stock_bounds', {}),
            tool_diameter=data.get('tool_diameter'),
            material=data.get('material', 'aluminum_6061')
        )

        # Then repair
        repaired_gcode, repairs = service.toolpath_repair.repair_toolpath(
            gcode_lines=gcode_lines,
            issues=issues,
            auto_only=data.get('auto_only', True)
        )

        return jsonify({
            'repaired_gcode': '\n'.join(repaired_gcode),
            'repairs_applied': len(repairs),
            'report': service.toolpath_repair.generate_repair_report(repairs)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/intelligent/tool-life/predict', methods=['POST'])
def predict_tool_life():
    """Predict tool life."""
    try:
        from services.intelligent_manufacturing_service import (
            get_intelligent_manufacturing_service,
            CuttingParameters
        )
        service = get_intelligent_manufacturing_service()

        data = request.get_json()
        params = CuttingParameters(
            spindle_rpm=data.get('spindle_rpm'),
            feed_rate_mmpm=data.get('feed_rate_mmpm'),
            depth_of_cut_mm=data.get('depth_of_cut_mm'),
            width_of_cut_mm=data.get('width_of_cut_mm')
        )

        prediction = service.tool_life_predictor.predict_tool_life(
            tool_id=data.get('tool_id'),
            tool_type=data.get('tool_type'),
            current_usage_minutes=data.get('current_usage_minutes', 0),
            cutting_params=params,
            material=data.get('material'),
            tool_diameter_mm=data.get('tool_diameter_mm')
        )

        return jsonify({
            'tool_id': prediction.tool_id,
            'remaining_minutes': prediction.predicted_remaining_minutes,
            'confidence_interval': prediction.confidence_interval,
            'wear_stage': prediction.wear_stage.value,
            'failure_probability': prediction.failure_probability_next_job,
            'recommended_action': prediction.recommended_action,
            'urgency': prediction.replacement_urgency
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Business Integration Routes
# =============================================================================

@bp.route('/business/estimates', methods=['POST'])
def create_estimate():
    """Create a job cost estimate."""
    try:
        from services.business_integration_service import get_business_integration_service
        service = get_business_integration_service()

        data = request.get_json()
        estimate = service.costing.create_estimate(
            part_number=data.get('part_number'),
            part_name=data.get('part_name'),
            quantity=data.get('quantity'),
            material=data.get('material', {}),
            operations=data.get('operations', []),
            tooling=data.get('tooling', []),
            markup_percent=data.get('markup_percent'),
            fusion_document_id=data.get('fusion_document_id'),
            is_rush=data.get('is_rush', False),
            is_prototype=data.get('is_prototype', False)
        )

        return jsonify({
            'estimate_id': estimate.estimate_id,
            'total': estimate.total,
            'unit_price': estimate.unit_price
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/business/estimates/<estimate_id>', methods=['GET'])
def get_estimate(estimate_id):
    """Get estimate by ID."""
    try:
        from services.business_integration_service import get_business_integration_service
        service = get_business_integration_service()

        estimate = service.costing.get_estimate(estimate_id)
        if not estimate:
            return jsonify({'error': 'Estimate not found'}), 404

        return jsonify(estimate)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/business/quotes', methods=['POST'])
def create_quote():
    """Create a customer quote."""
    try:
        from services.business_integration_service import get_business_integration_service
        service = get_business_integration_service()

        data = request.get_json()
        quote = service.quotes.create_quote(
            customer_id=data.get('customer_id'),
            customer_name=data.get('customer_name'),
            estimate_ids=data.get('estimate_ids', []),
            discount_percent=data.get('discount_percent', 0),
            tax_percent=data.get('tax_percent', 0),
            terms=data.get('terms', 'Net 30'),
            valid_days=data.get('valid_days', 30)
        )

        return jsonify({
            'quote_id': quote.quote_id,
            'quote_number': quote.quote_number,
            'total': quote.total
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/business/quotes/<quote_id>', methods=['GET'])
def get_quote(quote_id):
    """Get quote by ID."""
    try:
        from services.business_integration_service import get_business_integration_service
        service = get_business_integration_service()

        quote = service.quotes.get_quote(quote_id)
        if not quote:
            return jsonify({'error': 'Quote not found'}), 404

        return jsonify(quote)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/business/production-orders', methods=['POST'])
def create_production_order():
    """Create a production order."""
    try:
        from services.business_integration_service import get_business_integration_service
        service = get_business_integration_service()

        data = request.get_json()
        due_date = datetime.fromisoformat(data.get('due_date'))

        order = service.production_orders.create_production_order(
            part_number=data.get('part_number'),
            part_name=data.get('part_name'),
            quantity=data.get('quantity'),
            due_date=due_date,
            priority=data.get('priority', 5),
            customer_id=data.get('customer_id'),
            customer_po=data.get('customer_po'),
            fusion_project_id=data.get('fusion_project_id'),
            created_by=data.get('created_by', 'api')
        )

        return jsonify({
            'order_id': order.order_id,
            'order_number': order.order_number
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/business/production-orders', methods=['GET'])
def list_production_orders():
    """List production orders."""
    try:
        from services.business_integration_service import get_business_integration_service
        service = get_business_integration_service()

        orders = service.production_orders.list_orders()
        return jsonify({'orders': orders})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/business/work-orders', methods=['POST'])
def create_work_orders():
    """Generate work orders for a production order."""
    try:
        from services.business_integration_service import get_business_integration_service
        service = get_business_integration_service()

        data = request.get_json()
        work_orders = service.work_orders.generate_work_orders(
            production_order_id=data.get('production_order_id'),
            operations=data.get('operations', [])
        )

        return jsonify({
            'work_orders': [
                {'work_order_id': wo.work_order_id, 'work_order_number': wo.work_order_number}
                for wo in work_orders
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/business/status', methods=['GET'])
def get_business_status():
    """Get business status summary."""
    try:
        from services.business_integration_service import get_business_integration_service
        service = get_business_integration_service()

        return jsonify(service.get_production_status())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Collaboration Routes
# =============================================================================

@bp.route('/collaboration/reviews', methods=['POST'])
def create_review():
    """Create a design review."""
    try:
        from services.collaboration_service import get_collaboration_service
        service = get_collaboration_service()

        data = request.get_json()
        due_date = datetime.fromisoformat(data['due_date']) if data.get('due_date') else None

        review = service.reviews.create_review(
            title=data.get('title'),
            description=data.get('description', ''),
            document_id=data.get('document_id'),
            document_version=data.get('document_version', 'v1'),
            author_id=data.get('author_id'),
            reviewers=data.get('reviewers', []),
            approvers=data.get('approvers', []),
            due_date=due_date,
            fusion_project_id=data.get('fusion_project_id')
        )

        return jsonify({
            'review_id': review.review_id,
            'title': review.title
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/collaboration/reviews/<review_id>', methods=['GET'])
def get_review(review_id):
    """Get review by ID."""
    try:
        from services.collaboration_service import get_collaboration_service
        service = get_collaboration_service()

        review = service.reviews.get_review(review_id)
        if not review:
            return jsonify({'error': 'Review not found'}), 404

        return jsonify(review)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/collaboration/reviews/<review_id>/approve', methods=['POST'])
def approve_review(review_id):
    """Submit approval for a review."""
    try:
        from services.collaboration_service import get_collaboration_service
        service = get_collaboration_service()

        data = request.get_json()
        success = service.reviews.submit_approval(
            review_id=review_id,
            approver_id=data.get('approver_id'),
            approved=data.get('approved', True),
            comments=data.get('comments')
        )

        if not success:
            return jsonify({'error': 'Approval failed'}), 400

        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/collaboration/annotations', methods=['POST'])
def create_annotation():
    """Create an annotation."""
    try:
        from services.collaboration_service import (
            get_collaboration_service,
            AnnotationType,
            AnnotationSeverity
        )
        service = get_collaboration_service()

        data = request.get_json()
        annotation = service.annotations.create_annotation(
            document_id=data.get('document_id'),
            version=data.get('version', 'v1'),
            annotation_type=AnnotationType(data.get('type', 'comment')),
            author_id=data.get('author_id'),
            author_name=data.get('author_name'),
            content=data.get('content'),
            position=data.get('position', {'x': 0, 'y': 0, 'z': 0}),
            severity=AnnotationSeverity(data.get('severity', 'info')),
            tags=data.get('tags', [])
        )

        return jsonify({
            'annotation_id': annotation.annotation_id
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/collaboration/annotations/<document_id>', methods=['GET'])
def get_document_annotations(document_id):
    """Get annotations for a document."""
    try:
        from services.collaboration_service import get_collaboration_service
        service = get_collaboration_service()

        include_resolved = request.args.get('include_resolved', 'true').lower() == 'true'
        annotations = service.annotations.get_document_annotations(
            document_id=document_id,
            include_resolved=include_resolved
        )

        return jsonify({'annotations': annotations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/collaboration/sessions', methods=['POST'])
def create_collaboration_session():
    """Create a real-time collaboration session."""
    try:
        from services.collaboration_service import get_collaboration_service
        service = get_collaboration_service()

        data = request.get_json()
        session = service.realtime.create_session(
            document_id=data.get('document_id'),
            creator_id=data.get('creator_id')
        )

        return jsonify({
            'session_id': session.session_id,
            'document_id': session.document_id
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/collaboration/versions/<document_id>', methods=['GET'])
def get_document_versions(document_id):
    """Get versions of a document."""
    try:
        from services.collaboration_service import get_collaboration_service
        service = get_collaboration_service()

        versions = service.versions.get_document_versions(document_id)
        return jsonify({'versions': versions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Advanced Integration Routes
# =============================================================================

@bp.route('/ar/configs', methods=['POST'])
def create_ar_config():
    """Create AR visualization configuration."""
    try:
        from services.advanced_integration_service import (
            get_advanced_integration_service,
            ARPlatform,
            VisualizationFormat
        )
        service = get_advanced_integration_service()

        data = request.get_json()
        config = service.ar_visualization.create_visualization_config(
            model_id=data.get('model_id'),
            platform=ARPlatform(data.get('platform', 'webxr')),
            format=VisualizationFormat(data.get('format', 'glb')),
            scale_factor=data.get('scale_factor', 1.0),
            annotations_enabled=data.get('annotations_enabled', True),
            quality_level=data.get('quality_level', 'medium')
        )

        return jsonify({
            'config_id': config.config_id
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/ar/prepare', methods=['POST'])
def prepare_ar_visualization():
    """Prepare AR visualization data."""
    try:
        from services.advanced_integration_service import get_advanced_integration_service
        service = get_advanced_integration_service()

        data = request.get_json()
        vis_data = service.ar_visualization.prepare_visualization_data(
            config_id=data.get('config_id'),
            fusion_data=data.get('fusion_data', {})
        )

        return jsonify(vis_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/iot/sensors', methods=['POST'])
def register_sensor():
    """Register an IoT sensor."""
    try:
        from services.advanced_integration_service import (
            get_advanced_integration_service,
            SensorType
        )
        service = get_advanced_integration_service()

        data = request.get_json()
        node = service.iot_sensors.register_sensor_node(
            name=data.get('name'),
            sensor_type=SensorType(data.get('sensor_type')),
            machine_id=data.get('machine_id'),
            location=data.get('location', {'x': 0, 'y': 0, 'z': 0}),
            sampling_rate_hz=data.get('sampling_rate_hz', 100),
            alert_thresholds=data.get('alert_thresholds', {})
        )

        return jsonify({
            'node_id': node.node_id,
            'name': node.name
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/iot/sensors/<node_id>/readings', methods=['POST'])
def record_sensor_reading(node_id):
    """Record a sensor reading."""
    try:
        from services.advanced_integration_service import get_advanced_integration_service
        service = get_advanced_integration_service()

        data = request.get_json()
        reading = service.iot_sensors.record_reading(
            node_id=node_id,
            value=data.get('value'),
            unit=data.get('unit'),
            quality=data.get('quality', 1.0)
        )

        if not reading:
            return jsonify({'error': 'Sensor not found'}), 404

        return jsonify({'reading_id': reading.reading_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/iot/machines/<machine_id>/dashboard', methods=['GET'])
def get_machine_sensor_dashboard(machine_id):
    """Get sensor dashboard for a machine."""
    try:
        from services.advanced_integration_service import get_advanced_integration_service
        service = get_advanced_integration_service()

        dashboard = service.get_machine_sensor_dashboard(machine_id)
        return jsonify(dashboard)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/cloud/jobs', methods=['POST'])
def submit_cloud_job():
    """Submit a cloud processing job."""
    try:
        from services.advanced_integration_service import get_advanced_integration_service
        service = get_advanced_integration_service()

        data = request.get_json()
        job = service.cloud_processing.submit_job(
            job_type=data.get('job_type'),
            input_data=data.get('input_data', {}),
            priority=data.get('priority', 5)
        )

        return jsonify({
            'job_id': job.job_id,
            'status': job.status.value
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/cloud/jobs/<job_id>', methods=['GET'])
def get_cloud_job(job_id):
    """Get cloud job status."""
    try:
        from services.advanced_integration_service import get_advanced_integration_service
        service = get_advanced_integration_service()

        job = service.cloud_processing.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        return jsonify(job)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/cloud/queue', methods=['GET'])
def get_cloud_queue_status():
    """Get cloud processing queue status."""
    try:
        from services.advanced_integration_service import get_advanced_integration_service
        service = get_advanced_integration_service()

        return jsonify(service.cloud_processing.get_queue_status())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/digital-thread', methods=['POST'])
def create_digital_thread():
    """Create a digital thread."""
    try:
        from services.advanced_integration_service import get_advanced_integration_service
        service = get_advanced_integration_service()

        data = request.get_json()
        thread = service.digital_thread.create_thread(
            part_number=data.get('part_number'),
            part_name=data.get('part_name'),
            fusion_project_id=data.get('fusion_project_id')
        )

        return jsonify({
            'thread_id': thread.thread_id,
            'part_number': thread.part_number
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/digital-thread/<thread_id>', methods=['GET'])
def get_digital_thread(thread_id):
    """Get digital thread."""
    try:
        from services.advanced_integration_service import get_advanced_integration_service
        service = get_advanced_integration_service()

        thread = service.digital_thread.get_thread(thread_id)
        if not thread:
            return jsonify({'error': 'Thread not found'}), 404

        return jsonify(thread)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/digital-thread/<thread_id>/visualization', methods=['GET'])
def get_thread_visualization(thread_id):
    """Get digital thread visualization data."""
    try:
        from services.advanced_integration_service import get_advanced_integration_service
        service = get_advanced_integration_service()

        vis_data = service.digital_thread.get_thread_visualization(thread_id)
        return jsonify(vis_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/digital-thread/<thread_id>/completeness', methods=['GET'])
def get_thread_completeness(thread_id):
    """Get digital thread completeness report."""
    try:
        from services.advanced_integration_service import get_advanced_integration_service
        service = get_advanced_integration_service()

        report = service.digital_thread.get_completeness_report(thread_id)
        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Service Status Routes
# =============================================================================

@bp.route('/status', methods=['GET'])
def get_all_service_status():
    """Get status of all advanced services."""
    try:
        status = {}

        try:
            from services.quality_inspection_service import get_quality_inspection_service
            status['quality_inspection'] = get_quality_inspection_service().get_service_status()
        except Exception as e:
            status['quality_inspection'] = {'error': str(e)}

        try:
            from services.machining_simulation_service import get_machining_simulation_service
            status['machining_simulation'] = get_machining_simulation_service().get_service_status()
        except Exception as e:
            status['machining_simulation'] = {'error': str(e)}

        try:
            from services.intelligent_manufacturing_service import get_intelligent_manufacturing_service
            status['intelligent_manufacturing'] = get_intelligent_manufacturing_service().get_service_status()
        except Exception as e:
            status['intelligent_manufacturing'] = {'error': str(e)}

        try:
            from services.business_integration_service import get_business_integration_service
            status['business_integration'] = get_business_integration_service().get_service_status()
        except Exception as e:
            status['business_integration'] = {'error': str(e)}

        try:
            from services.collaboration_service import get_collaboration_service
            status['collaboration'] = get_collaboration_service().get_service_status()
        except Exception as e:
            status['collaboration'] = {'error': str(e)}

        try:
            from services.advanced_integration_service import get_advanced_integration_service
            status['advanced_integration'] = get_advanced_integration_service().get_service_status()
        except Exception as e:
            status['advanced_integration'] = {'error': str(e)}

        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
