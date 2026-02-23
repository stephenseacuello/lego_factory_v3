"""
WebSocket Events Module

Re-exports from __init__ for cleaner imports.

LegoMCP v6.0 - Complete Manufacturing WebSocket Events
ISO 23247 Digital Twin, Unity 3D, Robotics, VR Training, Supply Chain
"""

from . import (
    # Core events (Phase 1)
    register_events,
    emit_operation_progress,
    emit_operation_complete,
    emit_file_created,
    emit_error,
    start_status_monitoring,
    stop_status_monitoring,

    # Digital Twin events (Phase 2)
    emit_workspace_update,
    emit_detection_result,
    emit_collection_update,
    emit_scan_progress,
    emit_build_check,
    register_phase2_events,

    # Manufacturing events (Phase 5)
    emit_work_order_update,
    emit_machine_status,
    emit_quality_alert,
    emit_spc_violation,
    emit_oee_update,
    emit_andon_event,
    emit_maintenance_alert,
    emit_schedule_update,
    emit_carbon_update,
    emit_edge_data,
    emit_ai_insight,
    register_manufacturing_events,

    # VR Training events (Phase 6)
    emit_vr_session_started,
    emit_vr_step_progress,
    emit_vr_session_complete,
    emit_vr_device_status,
    emit_vr_safety_event,
    register_vr_training_events,

    # Robotics events (Phase 7)
    emit_robot_status,
    emit_robot_task_update,
    emit_robot_safety_violation,
    emit_robot_sync_status,
    emit_robot_trajectory_update,
    emit_robot_calibration_update,
    register_robotics_events,

    # Unity Digital Twin events (Phase 8)
    emit_unity_scene_update,
    emit_unity_equipment_state,
    emit_unity_highlight,
    emit_unity_camera_command,
    emit_unity_heatmap_update,
    emit_unity_annotation,
    register_unity_events,

    # Supply Chain Twin events (Phase 9)
    emit_supply_chain_disruption,
    emit_supply_chain_flow_update,
    emit_supply_chain_inventory_update,
    emit_supply_chain_risk_update,
    emit_supply_chain_order_update,
    emit_supply_chain_simulation_result,
    register_supply_chain_events,

    # V8 Command Center events
    emit_command_center_status,
    emit_kpi_update,
    emit_kpi_dashboard,
    emit_alert_created,
    emit_alert_updated,
    emit_alert_summary,
    emit_action_created,
    emit_action_status_change,
    emit_action_execution_progress,
    emit_cosim_started,
    emit_cosim_progress,
    emit_cosim_completed,
    emit_decision_made,
    emit_event_correlated,
    emit_subsystem_health_change,
    register_command_center_events,
)

__all__ = [
    # Core events
    "register_events",
    "emit_operation_progress",
    "emit_operation_complete",
    "emit_file_created",
    "emit_error",
    "start_status_monitoring",
    "stop_status_monitoring",

    # Digital Twin events
    "emit_workspace_update",
    "emit_detection_result",
    "emit_collection_update",
    "emit_scan_progress",
    "emit_build_check",
    "register_phase2_events",

    # Manufacturing events
    "emit_work_order_update",
    "emit_machine_status",
    "emit_quality_alert",
    "emit_spc_violation",
    "emit_oee_update",
    "emit_andon_event",
    "emit_maintenance_alert",
    "emit_schedule_update",
    "emit_carbon_update",
    "emit_edge_data",
    "emit_ai_insight",
    "register_manufacturing_events",

    # VR Training events
    "emit_vr_session_started",
    "emit_vr_step_progress",
    "emit_vr_session_complete",
    "emit_vr_device_status",
    "emit_vr_safety_event",
    "register_vr_training_events",

    # Robotics events
    "emit_robot_status",
    "emit_robot_task_update",
    "emit_robot_safety_violation",
    "emit_robot_sync_status",
    "emit_robot_trajectory_update",
    "emit_robot_calibration_update",
    "register_robotics_events",

    # Unity Digital Twin events
    "emit_unity_scene_update",
    "emit_unity_equipment_state",
    "emit_unity_highlight",
    "emit_unity_camera_command",
    "emit_unity_heatmap_update",
    "emit_unity_annotation",
    "register_unity_events",

    # Supply Chain Twin events
    "emit_supply_chain_disruption",
    "emit_supply_chain_flow_update",
    "emit_supply_chain_inventory_update",
    "emit_supply_chain_risk_update",
    "emit_supply_chain_order_update",
    "emit_supply_chain_simulation_result",
    "register_supply_chain_events",

    # V8 Command Center events
    "emit_command_center_status",
    "emit_kpi_update",
    "emit_kpi_dashboard",
    "emit_alert_created",
    "emit_alert_updated",
    "emit_alert_summary",
    "emit_action_created",
    "emit_action_status_change",
    "emit_action_execution_progress",
    "emit_cosim_started",
    "emit_cosim_progress",
    "emit_cosim_completed",
    "emit_decision_made",
    "emit_event_correlated",
    "emit_subsystem_health_change",
    "register_command_center_events",
]
