"""Robotic Arm Scheduling Tables

Revision ID: 20260101_000002
Revises: 20260101_000001
Create Date: 2026-01-01 00:00:02

Robotic arm task scheduling and coordination:
- Robot tasks with acknowledgment flow
- Synchronized multi-arm motions
- Task history and analytics

Standards Compliance:
- ISO 10218 (Industrial Robot Safety)
- ISO/TS 15066 (Collaborative Robots)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '20260101_000002'
down_revision: Union[str, None] = '20260101_000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create robotic arm scheduling tables."""

    # =========================================================================
    # ROBOT TASKS (ISO 10218 Compliant Task Queue)
    # =========================================================================
    op.create_table(
        'robot_tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('arm_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id'), nullable=False),

        # Task definition
        sa.Column('task_type', sa.String(50), nullable=False),
        # Types: move_joint, move_linear, pick, place, home, calibrate, synchronized, custom
        sa.Column('priority', sa.String(20), default='normal'),
        # Priorities: low, normal, high, critical
        sa.Column('parameters', sa.JSON()),

        # Status tracking
        sa.Column('status', sa.String(50), default='pending'),
        # Statuses: pending, queued, executing, paused, completed, failed, cancelled
        sa.Column('progress', sa.Float(), default=0.0),  # 0.0 to 1.0

        # Scheduling
        sa.Column('scheduled_at', sa.DateTime()),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('estimated_duration_ms', sa.Float()),
        sa.Column('actual_duration_ms', sa.Float()),

        # Trajectory data
        sa.Column('trajectory_id', sa.String(36)),
        sa.Column('waypoint_count', sa.Integer()),
        sa.Column('current_waypoint', sa.Integer()),

        # Safety (ISO 10218)
        sa.Column('velocity_limit_percent', sa.Float(), default=100.0),
        sa.Column('force_limit_n', sa.Float()),
        sa.Column('collision_detection_enabled', sa.Boolean(), default=True),
        sa.Column('zone_restrictions', sa.JSON()),

        # Synchronization
        sa.Column('sync_motion_id', sa.String(36)),  # If part of synchronized motion
        sa.Column('barrier_id', sa.String(36)),  # Synchronization barrier

        # Error handling
        sa.Column('error_code', sa.String(50)),
        sa.Column('error_message', sa.Text()),
        sa.Column('retry_count', sa.Integer(), default=0),
        sa.Column('max_retries', sa.Integer(), default=3),

        # Metadata
        sa.Column('created_by', sa.String(100)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )
    op.create_index('ix_robot_task_arm', 'robot_tasks', ['arm_id'])
    op.create_index('ix_robot_task_status', 'robot_tasks', ['status'])
    op.create_index('ix_robot_task_priority', 'robot_tasks', ['priority'])
    op.create_index('ix_robot_task_scheduled', 'robot_tasks', ['scheduled_at'])
    op.create_index('ix_robot_task_sync', 'robot_tasks', ['sync_motion_id'])

    # =========================================================================
    # TASK ACKNOWLEDGMENTS (Command Flow Tracking)
    # =========================================================================
    op.create_table(
        'task_acknowledgments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('robot_tasks.id'), nullable=False),

        sa.Column('ack_type', sa.String(50), nullable=False),
        # Types: received, queued, started, progress, completed, failed, cancelled

        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('progress', sa.Float()),  # For progress acks
        sa.Column('message', sa.Text()),
        sa.Column('data', sa.JSON()),

        # Source
        sa.Column('source', sa.String(100)),  # scheduler, arm_controller, safety_system
    )
    op.create_index('ix_ack_task', 'task_acknowledgments', ['task_id'])
    op.create_index('ix_ack_type', 'task_acknowledgments', ['ack_type'])
    op.create_index('ix_ack_time', 'task_acknowledgments', ['timestamp'])

    # =========================================================================
    # SYNCHRONIZED MOTIONS (Multi-Arm Coordination)
    # =========================================================================
    op.create_table(
        'synchronized_motions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('motion_id', sa.String(100), unique=True, nullable=False),

        # Participating arms
        sa.Column('arm_ids', sa.JSON(), nullable=False),  # List of arm OME IDs
        sa.Column('arm_count', sa.Integer(), nullable=False),

        # Coordination
        sa.Column('sync_type', sa.String(50), default='barrier'),
        # Types: barrier (wait for all), timed (clock sync), master_slave
        sa.Column('master_arm_id', sa.String(36)),  # For master_slave mode

        # Status
        sa.Column('status', sa.String(50), default='pending'),
        # Statuses: pending, waiting, executing, completed, failed, cancelled
        sa.Column('arms_ready', sa.Integer(), default=0),

        # Timing
        sa.Column('scheduled_at', sa.DateTime()),
        sa.Column('barrier_reached_at', sa.DateTime()),  # When all arms ready
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),

        # Results
        sa.Column('task_results', sa.JSON()),  # Per-arm results
        sa.Column('success', sa.Boolean()),

        # Metadata
        sa.Column('created_by', sa.String(100)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_sync_motion_id', 'synchronized_motions', ['motion_id'])
    op.create_index('ix_sync_motion_status', 'synchronized_motions', ['status'])

    # =========================================================================
    # ARM TRAJECTORIES (Pre-computed Motion Paths)
    # =========================================================================
    op.create_table(
        'arm_trajectories',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('arm_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id'), nullable=False),

        sa.Column('trajectory_name', sa.String(255)),
        sa.Column('trajectory_type', sa.String(50)),
        # Types: point_to_point, linear, arc, spline, pick_place

        # Waypoints
        sa.Column('waypoint_count', sa.Integer(), nullable=False),
        sa.Column('waypoints', sa.JSON(), nullable=False),
        # Format: [{time: float, positions: [j1..j6], velocities: [...], accelerations: [...]}]

        # Timing
        sa.Column('total_duration_ms', sa.Float()),
        sa.Column('interpolation', sa.String(50), default='quintic'),
        # Types: linear, cubic, quintic

        # Constraints
        sa.Column('max_velocity_scale', sa.Float(), default=1.0),
        sa.Column('max_acceleration_scale', sa.Float(), default=1.0),
        sa.Column('constraints', sa.JSON()),

        # Validation
        sa.Column('is_validated', sa.Boolean(), default=False),
        sa.Column('validated_at', sa.DateTime()),
        sa.Column('validation_result', sa.JSON()),

        # Metadata
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100)),
    )
    op.create_index('ix_trajectory_arm', 'arm_trajectories', ['arm_id'])
    op.create_index('ix_trajectory_type', 'arm_trajectories', ['trajectory_type'])

    # =========================================================================
    # SAFETY ZONES (ISO 10218 / ISO/TS 15066)
    # =========================================================================
    op.create_table(
        'arm_safety_zones',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('zone_id', sa.String(100), unique=True, nullable=False),
        sa.Column('arm_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id')),
        # If arm_id is NULL, zone applies to all arms in namespace

        sa.Column('zone_name', sa.String(255), nullable=False),
        sa.Column('zone_type', sa.String(50), nullable=False),
        # Types: restricted, reduced_speed, collaborative, stop, warning

        # Geometry
        sa.Column('geometry_type', sa.String(50), nullable=False),
        # Types: box, sphere, cylinder, mesh
        sa.Column('geometry_data', sa.JSON(), nullable=False),
        # Format depends on type: box: {min: {x,y,z}, max: {x,y,z}}, sphere: {center: {x,y,z}, radius}

        # Behavior
        sa.Column('velocity_limit_percent', sa.Float()),  # For reduced_speed zones
        sa.Column('force_limit_n', sa.Float()),  # For collaborative zones
        sa.Column('stop_on_entry', sa.Boolean(), default=False),
        sa.Column('alarm_on_entry', sa.Boolean(), default=True),

        # Scheduling
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('active_schedule', sa.JSON()),  # Time-based activation

        sa.Column('namespace', sa.String(100), default='default'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_zone_arm', 'arm_safety_zones', ['arm_id'])
    op.create_index('ix_zone_type', 'arm_safety_zones', ['zone_type'])
    op.create_index('ix_zone_active', 'arm_safety_zones', ['is_active'])

    # =========================================================================
    # ZONE VIOLATIONS (Safety Events)
    # =========================================================================
    op.create_table(
        'zone_violations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('zone_id', sa.String(36), sa.ForeignKey('arm_safety_zones.id'), nullable=False),
        sa.Column('arm_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id'), nullable=False),

        sa.Column('violation_type', sa.String(50), nullable=False),
        # Types: entry, proximity, force_exceeded, velocity_exceeded
        sa.Column('severity', sa.String(20), nullable=False),
        # Severities: warning, critical, emergency_stop

        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime()),

        # Location
        sa.Column('violation_point', sa.JSON()),  # {x, y, z}
        sa.Column('arm_joint_positions', sa.JSON()),

        # Response
        sa.Column('action_taken', sa.String(100)),
        # Actions: warning_issued, speed_reduced, stopped, emergency_stop
        sa.Column('response_time_ms', sa.Float()),

        sa.Column('operator_acknowledged', sa.Boolean(), default=False),
        sa.Column('acknowledged_by', sa.String(100)),
        sa.Column('acknowledged_at', sa.DateTime()),

        sa.Column('notes', sa.Text()),
    )
    op.create_index('ix_violation_zone', 'zone_violations', ['zone_id'])
    op.create_index('ix_violation_arm', 'zone_violations', ['arm_id'])
    op.create_index('ix_violation_time', 'zone_violations', ['detected_at'])
    op.create_index('ix_violation_severity', 'zone_violations', ['severity'])

    # =========================================================================
    # ARM CALIBRATION RECORDS
    # =========================================================================
    op.create_table(
        'arm_calibrations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('arm_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id'), nullable=False),

        sa.Column('calibration_type', sa.String(50), nullable=False),
        # Types: joint_offsets, tool_center_point, base_frame, payload

        sa.Column('performed_at', sa.DateTime(), nullable=False),
        sa.Column('performed_by', sa.String(100)),

        # Before/After
        sa.Column('parameters_before', sa.JSON()),
        sa.Column('parameters_after', sa.JSON()),

        # Validation
        sa.Column('validation_method', sa.String(100)),
        sa.Column('accuracy_achieved_mm', sa.Float()),
        sa.Column('repeatability_achieved_mm', sa.Float()),
        sa.Column('passed', sa.Boolean()),

        # Next calibration
        sa.Column('next_calibration_due', sa.DateTime()),

        sa.Column('notes', sa.Text()),
    )
    op.create_index('ix_calibration_arm', 'arm_calibrations', ['arm_id'])
    op.create_index('ix_calibration_type', 'arm_calibrations', ['calibration_type'])
    op.create_index('ix_calibration_date', 'arm_calibrations', ['performed_at'])


def downgrade() -> None:
    """Drop robotic arm scheduling tables."""
    op.drop_table('arm_calibrations')
    op.drop_table('zone_violations')
    op.drop_table('arm_safety_zones')
    op.drop_table('arm_trajectories')
    op.drop_table('synchronized_motions')
    op.drop_table('task_acknowledgments')
    op.drop_table('robot_tasks')
