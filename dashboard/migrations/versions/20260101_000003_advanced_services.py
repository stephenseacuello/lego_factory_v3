"""Advanced Services Schema

Revision ID: 20260101_000003
Revises: 20260101_000002
Create Date: 2026-01-01 00:00:03

Advanced manufacturing services:
- Anomaly Response Automation
- Supply Chain Digital Twin
- VR Training System
- Quality Heatmaps

ISO 23247 compliant extensions for world-class manufacturing.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '20260101_000003'
down_revision: Union[str, None] = '20260101_000002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create advanced services tables."""

    # =========================================================================
    # ANOMALY RESPONSE AUTOMATION
    # =========================================================================

    # Anomalies detected in the system
    op.create_table(
        'anomalies',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ome_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id')),
        sa.Column('twin_id', sa.String(36), sa.ForeignKey('digital_twin_instances.id')),

        sa.Column('anomaly_type', sa.String(50), nullable=False),
        # Types: temperature, vibration, pressure, quality, process, safety, sensor, equipment
        sa.Column('severity', sa.String(20), nullable=False),
        # Severities: info, low, medium, high, critical
        sa.Column('status', sa.String(50), default='detected'),
        # Statuses: detected, investigating, responding, escalated, resolved, false_positive

        # Detection details
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.Column('detection_source', sa.String(100)),  # ml_model, threshold, pattern, manual
        sa.Column('detection_confidence', sa.Float()),
        sa.Column('model_id', sa.String(100)),

        # Anomaly data
        sa.Column('sensor_readings', sa.JSON()),
        sa.Column('context_data', sa.JSON()),
        sa.Column('deviation_metrics', sa.JSON()),

        # Resolution
        sa.Column('resolved_at', sa.DateTime()),
        sa.Column('resolution_method', sa.String(100)),
        sa.Column('root_cause', sa.Text()),
        sa.Column('corrective_actions', sa.JSON()),

        # Impact assessment
        sa.Column('impact_assessment', sa.JSON()),
        sa.Column('estimated_cost', sa.Float()),
        sa.Column('actual_cost', sa.Float()),

        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )
    op.create_index('ix_anomaly_type', 'anomalies', ['anomaly_type'])
    op.create_index('ix_anomaly_severity', 'anomalies', ['severity'])
    op.create_index('ix_anomaly_status', 'anomalies', ['status'])
    op.create_index('ix_anomaly_detected', 'anomalies', ['detected_at'])
    op.create_index('ix_anomaly_ome', 'anomalies', ['ome_id'])

    # Response rules for automated actions
    op.create_table(
        'response_rules',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('rule_id', sa.String(100), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),

        # Matching criteria
        sa.Column('anomaly_type_pattern', sa.String(100)),  # Regex pattern
        sa.Column('severity_threshold', sa.String(20)),
        sa.Column('ome_type_filter', sa.String(100)),

        # Response configuration
        sa.Column('response_type', sa.String(50), nullable=False),
        # Types: automatic, semi_automatic, manual, escalate
        sa.Column('response_action', sa.String(100), nullable=False),
        # Actions: notify, adjust_parameters, pause, stop, maintenance_request, escalate
        sa.Column('action_parameters', sa.JSON()),

        # Escalation
        sa.Column('escalation_level', sa.String(20)),
        sa.Column('escalation_contacts', sa.JSON()),
        sa.Column('escalation_delay_minutes', sa.Integer()),

        # Effectiveness tracking
        sa.Column('times_triggered', sa.Integer(), default=0),
        sa.Column('successful_responses', sa.Integer(), default=0),
        sa.Column('average_response_time_sec', sa.Float()),

        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('priority', sa.Integer(), default=100),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100)),
    )
    op.create_index('ix_rule_active', 'response_rules', ['is_active'])
    op.create_index('ix_rule_priority', 'response_rules', ['priority'])

    # Response executions (audit trail)
    op.create_table(
        'response_executions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('anomaly_id', sa.String(36), sa.ForeignKey('anomalies.id'), nullable=False),
        sa.Column('rule_id', sa.String(36), sa.ForeignKey('response_rules.id')),

        sa.Column('response_type', sa.String(50), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('parameters', sa.JSON()),

        # Execution timing
        sa.Column('triggered_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),

        # Status
        sa.Column('status', sa.String(50), nullable=False),
        # Statuses: pending, executing, completed, failed, cancelled, escalated
        sa.Column('result', sa.JSON()),
        sa.Column('error_message', sa.Text()),

        # Human-in-the-loop
        sa.Column('requires_approval', sa.Boolean(), default=False),
        sa.Column('approved_by', sa.String(100)),
        sa.Column('approved_at', sa.DateTime()),
        sa.Column('approval_notes', sa.Text()),

        # Effectiveness
        sa.Column('was_effective', sa.Boolean()),
        sa.Column('effectiveness_notes', sa.Text()),
        sa.Column('feedback_by', sa.String(100)),
    )
    op.create_index('ix_execution_anomaly', 'response_executions', ['anomaly_id'])
    op.create_index('ix_execution_status', 'response_executions', ['status'])
    op.create_index('ix_execution_triggered', 'response_executions', ['triggered_at'])

    # =========================================================================
    # SUPPLY CHAIN DIGITAL TWIN
    # =========================================================================

    # Supply chain nodes (suppliers, warehouses, factories)
    op.create_table(
        'supply_chain_nodes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('node_id', sa.String(100), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),

        sa.Column('node_type', sa.String(50), nullable=False),
        # Types: supplier, manufacturer, warehouse, distribution_center, customer, port
        sa.Column('status', sa.String(50), default='active'),
        # Statuses: active, at_risk, disrupted, inactive

        # Location
        sa.Column('latitude', sa.Float()),
        sa.Column('longitude', sa.Float()),
        sa.Column('country', sa.String(100)),
        sa.Column('region', sa.String(100)),
        sa.Column('address', sa.Text()),
        sa.Column('timezone', sa.String(50)),

        # Capabilities
        sa.Column('capabilities', sa.JSON()),
        sa.Column('capacity', sa.JSON()),
        sa.Column('lead_time_days', sa.Float()),
        sa.Column('reliability_score', sa.Float()),

        # Contact
        sa.Column('contact_info', sa.JSON()),

        # Certifications
        sa.Column('certifications', sa.JSON()),

        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )
    op.create_index('ix_sc_node_type', 'supply_chain_nodes', ['node_type'])
    op.create_index('ix_sc_node_status', 'supply_chain_nodes', ['status'])
    op.create_index('ix_sc_node_country', 'supply_chain_nodes', ['country'])

    # Supply chain edges (connections between nodes)
    op.create_table(
        'supply_chain_edges',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('source_id', sa.String(36), sa.ForeignKey('supply_chain_nodes.id'), nullable=False),
        sa.Column('target_id', sa.String(36), sa.ForeignKey('supply_chain_nodes.id'), nullable=False),

        sa.Column('edge_type', sa.String(50), nullable=False),
        # Types: supply, logistics, information, financial
        sa.Column('transport_mode', sa.String(50)),
        # Modes: road, rail, sea, air, pipeline, multimodal

        # Characteristics
        sa.Column('distance_km', sa.Float()),
        sa.Column('transit_time_hours', sa.Float()),
        sa.Column('cost_per_unit', sa.Float()),
        sa.Column('capacity', sa.Float()),
        sa.Column('reliability', sa.Float()),

        # Current state
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('utilization_percent', sa.Float()),

        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_sc_edge_source', 'supply_chain_edges', ['source_id'])
    op.create_index('ix_sc_edge_target', 'supply_chain_edges', ['target_id'])
    op.create_index('ix_sc_edge_mode', 'supply_chain_edges', ['transport_mode'])

    # Materials in the supply chain
    op.create_table(
        'supply_chain_materials',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('material_id', sa.String(100), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('category', sa.String(50)),
        # Categories: raw_material, component, subassembly, finished_good, consumable

        # Specifications
        sa.Column('specifications', sa.JSON()),
        sa.Column('unit_of_measure', sa.String(50)),
        sa.Column('unit_cost', sa.Float()),
        sa.Column('unit_weight_kg', sa.Float()),

        # Sourcing
        sa.Column('primary_supplier_id', sa.String(36), sa.ForeignKey('supply_chain_nodes.id')),
        sa.Column('alternate_suppliers', sa.JSON()),
        sa.Column('lead_time_days', sa.Float()),
        sa.Column('min_order_quantity', sa.Float()),

        # Inventory settings
        sa.Column('safety_stock', sa.Float()),
        sa.Column('reorder_point', sa.Float()),
        sa.Column('reorder_quantity', sa.Float()),

        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_sc_material_category', 'supply_chain_materials', ['category'])
    op.create_index('ix_sc_material_supplier', 'supply_chain_materials', ['primary_supplier_id'])

    # Inventory levels at nodes
    op.create_table(
        'supply_chain_inventory',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('node_id', sa.String(36), sa.ForeignKey('supply_chain_nodes.id'), nullable=False),
        sa.Column('material_id', sa.String(36), sa.ForeignKey('supply_chain_materials.id'), nullable=False),

        sa.Column('quantity', sa.Float(), default=0),
        sa.Column('reserved_quantity', sa.Float(), default=0),
        sa.Column('available_quantity', sa.Float(), default=0),

        sa.Column('last_updated', sa.DateTime()),
        sa.Column('next_replenishment', sa.DateTime()),

        sa.UniqueConstraint('node_id', 'material_id', name='uq_inventory_node_material'),
    )
    op.create_index('ix_inventory_node', 'supply_chain_inventory', ['node_id'])
    op.create_index('ix_inventory_material', 'supply_chain_inventory', ['material_id'])

    # Shipments in transit
    op.create_table(
        'supply_chain_shipments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('shipment_id', sa.String(100), unique=True, nullable=False),
        sa.Column('edge_id', sa.String(36), sa.ForeignKey('supply_chain_edges.id'), nullable=False),

        sa.Column('material_id', sa.String(36), sa.ForeignKey('supply_chain_materials.id'), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),

        sa.Column('status', sa.String(50), default='pending'),
        # Statuses: pending, in_transit, delayed, delivered, cancelled

        # Timing
        sa.Column('departed_at', sa.DateTime()),
        sa.Column('expected_arrival', sa.DateTime()),
        sa.Column('actual_arrival', sa.DateTime()),

        # Tracking
        sa.Column('current_location', sa.JSON()),  # {lat, lng, timestamp}
        sa.Column('tracking_history', sa.JSON()),

        # Issues
        sa.Column('delay_reason', sa.Text()),
        sa.Column('delay_hours', sa.Float()),

        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_shipment_status', 'supply_chain_shipments', ['status'])
    op.create_index('ix_shipment_edge', 'supply_chain_shipments', ['edge_id'])
    op.create_index('ix_shipment_material', 'supply_chain_shipments', ['material_id'])
    op.create_index('ix_shipment_expected', 'supply_chain_shipments', ['expected_arrival'])

    # Risk factors affecting supply chain
    op.create_table(
        'supply_chain_risks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('node_id', sa.String(36), sa.ForeignKey('supply_chain_nodes.id')),
        sa.Column('edge_id', sa.String(36), sa.ForeignKey('supply_chain_edges.id')),

        sa.Column('risk_category', sa.String(50), nullable=False),
        # Categories: geopolitical, natural_disaster, financial, operational, quality, cyber
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('probability', sa.Float()),
        sa.Column('impact_score', sa.Float()),

        sa.Column('description', sa.Text()),
        sa.Column('mitigation_strategy', sa.Text()),
        sa.Column('mitigation_status', sa.String(50)),

        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime()),
        sa.Column('is_active', sa.Boolean(), default=True),

        sa.Column('source', sa.String(100)),  # news, supplier_report, internal, ai_prediction
    )
    op.create_index('ix_risk_node', 'supply_chain_risks', ['node_id'])
    op.create_index('ix_risk_edge', 'supply_chain_risks', ['edge_id'])
    op.create_index('ix_risk_category', 'supply_chain_risks', ['risk_category'])
    op.create_index('ix_risk_active', 'supply_chain_risks', ['is_active'])

    # Disruption scenarios for simulation
    op.create_table(
        'disruption_scenarios',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scenario_id', sa.String(100), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),

        sa.Column('scenario_type', sa.String(50)),
        # Types: supplier_failure, transport_disruption, demand_spike, natural_disaster
        sa.Column('affected_nodes', sa.JSON()),
        sa.Column('affected_edges', sa.JSON()),
        sa.Column('parameters', sa.JSON()),

        # Simulation results
        sa.Column('last_simulated', sa.DateTime()),
        sa.Column('impact_summary', sa.JSON()),
        sa.Column('recovery_time_days', sa.Float()),
        sa.Column('estimated_cost', sa.Float()),
        sa.Column('recommendations', sa.JSON()),

        sa.Column('created_by', sa.String(100)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_scenario_type', 'disruption_scenarios', ['scenario_type'])

    # =========================================================================
    # VR TRAINING SYSTEM
    # =========================================================================

    # Training scenarios
    op.create_table(
        'vr_training_scenarios',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scenario_id', sa.String(100), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),

        sa.Column('category', sa.String(50), nullable=False),
        # Categories: equipment_operation, safety_procedures, quality_inspection, maintenance, emergency
        sa.Column('difficulty', sa.String(20), default='intermediate'),
        # Difficulties: beginner, intermediate, advanced, expert

        # Equipment association
        sa.Column('ome_type', sa.String(50)),
        sa.Column('ome_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id')),

        # Content
        sa.Column('steps', sa.JSON(), nullable=False),
        # Format: [{step_id, title, instructions, interactions, success_criteria, hints}]
        sa.Column('step_count', sa.Integer()),
        sa.Column('estimated_duration_minutes', sa.Integer()),

        # 3D scene configuration
        sa.Column('scene_config', sa.JSON()),
        sa.Column('equipment_positions', sa.JSON()),
        sa.Column('interaction_points', sa.JSON()),

        # Scoring
        sa.Column('max_score', sa.Integer(), default=100),
        sa.Column('passing_score', sa.Integer(), default=70),
        sa.Column('scoring_weights', sa.JSON()),

        # Prerequisites
        sa.Column('prerequisites', sa.JSON()),
        sa.Column('required_certifications', sa.JSON()),

        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('version', sa.Integer(), default=1),
        sa.Column('created_by', sa.String(100)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )
    op.create_index('ix_training_category', 'vr_training_scenarios', ['category'])
    op.create_index('ix_training_difficulty', 'vr_training_scenarios', ['difficulty'])
    op.create_index('ix_training_active', 'vr_training_scenarios', ['is_active'])

    # Training sessions
    op.create_table(
        'vr_training_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scenario_id', sa.String(36), sa.ForeignKey('vr_training_scenarios.id'), nullable=False),
        sa.Column('user_id', sa.String(100), nullable=False),

        # Session timing
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('duration_seconds', sa.Float()),
        sa.Column('active_time_seconds', sa.Float()),

        # Status
        sa.Column('status', sa.String(50), default='in_progress'),
        # Statuses: in_progress, completed, abandoned, paused

        # Progress tracking
        sa.Column('current_step', sa.Integer(), default=1),
        sa.Column('steps_completed', sa.Integer(), default=0),
        sa.Column('step_attempts', sa.JSON()),  # Per-step attempt counts

        # Scoring
        sa.Column('score', sa.Float()),
        sa.Column('passed', sa.Boolean()),
        sa.Column('step_scores', sa.JSON()),

        # Analytics
        sa.Column('interactions', sa.JSON()),  # Detailed interaction log
        sa.Column('errors_made', sa.Integer(), default=0),
        sa.Column('hints_used', sa.Integer(), default=0),

        # Hardware info
        sa.Column('headset_type', sa.String(100)),
        sa.Column('controller_type', sa.String(100)),
        sa.Column('room_scale', sa.Boolean()),

        # Feedback
        sa.Column('feedback_given', sa.JSON()),

        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_session_scenario', 'vr_training_sessions', ['scenario_id'])
    op.create_index('ix_session_user', 'vr_training_sessions', ['user_id'])
    op.create_index('ix_session_status', 'vr_training_sessions', ['status'])
    op.create_index('ix_session_started', 'vr_training_sessions', ['started_at'])

    # Training results and certifications
    op.create_table(
        'vr_training_results',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('vr_training_sessions.id'), nullable=False),
        sa.Column('user_id', sa.String(100), nullable=False),
        sa.Column('scenario_id', sa.String(36), sa.ForeignKey('vr_training_scenarios.id'), nullable=False),

        # Results
        sa.Column('final_score', sa.Float(), nullable=False),
        sa.Column('passed', sa.Boolean(), nullable=False),
        sa.Column('attempt_number', sa.Integer()),

        # Performance breakdown
        sa.Column('accuracy_score', sa.Float()),
        sa.Column('time_score', sa.Float()),
        sa.Column('safety_score', sa.Float()),
        sa.Column('efficiency_score', sa.Float()),

        # Certification
        sa.Column('certification_earned', sa.Boolean(), default=False),
        sa.Column('certification_id', sa.String(100)),
        sa.Column('certification_expires', sa.DateTime()),

        # Improvement areas
        sa.Column('strengths', sa.JSON()),
        sa.Column('improvement_areas', sa.JSON()),
        sa.Column('recommendations', sa.JSON()),

        sa.Column('recorded_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_result_user', 'vr_training_results', ['user_id'])
    op.create_index('ix_result_scenario', 'vr_training_results', ['scenario_id'])
    op.create_index('ix_result_passed', 'vr_training_results', ['passed'])
    op.create_index('ix_result_cert', 'vr_training_results', ['certification_earned'])

    # =========================================================================
    # QUALITY HEATMAPS
    # =========================================================================

    # Generated heatmaps
    op.create_table(
        'quality_heatmaps',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('heatmap_id', sa.String(100), unique=True, nullable=False),
        sa.Column('name', sa.String(255)),

        sa.Column('heatmap_type', sa.String(50), nullable=False),
        # Types: defect_density, quality_score, cycle_time, temperature, oee
        sa.Column('ome_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id')),

        # Spatial bounds
        sa.Column('bounds_min', sa.JSON()),  # {x, y, z}
        sa.Column('bounds_max', sa.JSON()),  # {x, y, z}
        sa.Column('resolution', sa.JSON()),  # {x, y, z} cell counts

        # Time range
        sa.Column('time_start', sa.DateTime()),
        sa.Column('time_end', sa.DateTime()),

        # Data
        sa.Column('cell_count', sa.Integer()),
        sa.Column('data_points_count', sa.Integer()),
        sa.Column('cells_data', sa.JSON()),  # Compressed/encoded cell values

        # Statistics
        sa.Column('min_value', sa.Float()),
        sa.Column('max_value', sa.Float()),
        sa.Column('mean_value', sa.Float()),
        sa.Column('std_dev', sa.Float()),
        sa.Column('hot_spots', sa.JSON()),  # Identified problem areas

        # Configuration
        sa.Column('interpolation_method', sa.String(50)),
        sa.Column('color_scale', sa.String(50)),
        sa.Column('config', sa.JSON()),

        # Export
        sa.Column('unity_export_url', sa.String(500)),

        sa.Column('generated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('generated_by', sa.String(100)),
    )
    op.create_index('ix_heatmap_type', 'quality_heatmaps', ['heatmap_type'])
    op.create_index('ix_heatmap_ome', 'quality_heatmaps', ['ome_id'])
    op.create_index('ix_heatmap_time', 'quality_heatmaps', ['time_start', 'time_end'])

    # Quality data points for heatmap generation
    op.create_table(
        'quality_data_points',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('ome_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id')),

        # Spatial location
        sa.Column('x', sa.Float(), nullable=False),
        sa.Column('y', sa.Float(), nullable=False),
        sa.Column('z', sa.Float()),

        # Value
        sa.Column('metric_type', sa.String(50), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float()),

        # Source
        sa.Column('source', sa.String(100)),
        sa.Column('source_id', sa.String(100)),  # e.g., inspection record ID

        sa.Column('timestamp', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_qdp_ome', 'quality_data_points', ['ome_id'])
    op.create_index('ix_qdp_metric', 'quality_data_points', ['metric_type'])
    op.create_index('ix_qdp_time', 'quality_data_points', ['timestamp'])
    op.create_index('ix_qdp_spatial', 'quality_data_points', ['x', 'y', 'z'])


def downgrade() -> None:
    """Drop advanced services tables."""
    # Quality Heatmaps
    op.drop_table('quality_data_points')
    op.drop_table('quality_heatmaps')

    # VR Training
    op.drop_table('vr_training_results')
    op.drop_table('vr_training_sessions')
    op.drop_table('vr_training_scenarios')

    # Supply Chain
    op.drop_table('disruption_scenarios')
    op.drop_table('supply_chain_risks')
    op.drop_table('supply_chain_shipments')
    op.drop_table('supply_chain_inventory')
    op.drop_table('supply_chain_materials')
    op.drop_table('supply_chain_edges')
    op.drop_table('supply_chain_nodes')

    # Anomaly Response
    op.drop_table('response_executions')
    op.drop_table('response_rules')
    op.drop_table('anomalies')
