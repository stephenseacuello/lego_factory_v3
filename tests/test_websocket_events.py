"""
WebSocket Events Tests

LegoMCP v6.0 - ISO 23247 Digital Twin Manufacturing Platform
Tests for VR Training, Robotics, Unity Digital Twin, and Supply Chain WebSocket events.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock


class TestVRTrainingEvents:
    """Test VR Training WebSocket events."""

    def test_emit_vr_session_started(self):
        """Test VR session started event emission."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_vr_session_started

            emit_vr_session_started(
                session_id="VRS-001",
                scenario_id="safety-basics",
                trainee_id="TRN-001",
                scenario_name="Equipment Safety Fundamentals"
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "vr:session_started"
            assert call_args[0][1]["session_id"] == "VRS-001"
            assert call_args[0][1]["scenario_id"] == "safety-basics"
            assert call_args[1]["room"] == "vr_training"

    def test_emit_vr_step_progress(self):
        """Test VR training step progress event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_vr_step_progress

            emit_vr_step_progress(
                session_id="VRS-001",
                step_number=3,
                total_steps=10,
                step_name="Module 3: Emergency Procedures",
                status="completed",
                score=95.5
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "vr:step_progress"
            assert call_args[0][1]["step_number"] == 3
            assert call_args[0][1]["progress_percent"] == 30.0
            assert call_args[0][1]["score"] == 95.5

    def test_emit_vr_session_complete(self):
        """Test VR session completion event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_vr_session_complete

            emit_vr_session_complete(
                session_id="VRS-001",
                trainee_id="TRN-001",
                final_score=92.5,
                passed=True,
                duration_seconds=1800
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "vr:session_complete"
            assert call_args[0][1]["final_score"] == 92.5
            assert call_args[0][1]["passed"] is True

    def test_emit_vr_device_status(self):
        """Test VR device status event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_vr_device_status

            emit_vr_device_status(
                device_id="VR-HMD-001",
                device_type="headset",
                status="connected",
                battery_percent=85,
                tracking_quality="excellent"
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "vr:device_status"
            assert call_args[0][1]["battery_percent"] == 85

    def test_emit_vr_safety_event(self):
        """Test VR safety event emission."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_vr_safety_event

            emit_vr_safety_event(
                session_id="VRS-001",
                event_type="boundary_breach",
                message="User approaching play boundary",
                severity="warning"
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "vr:safety_event"
            assert call_args[0][1]["event_type"] == "boundary_breach"


class TestRoboticsEvents:
    """Test Robotics WebSocket events."""

    def test_emit_robot_status(self):
        """Test robot status event emission."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_robot_status

            emit_robot_status(
                arm_id="ARM-001",
                status="active",
                position={"x": 150.5, "y": 200.3, "z": 450.2},
                velocity=50.0,
                payload_kg=2.5
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "robot:status"
            assert call_args[0][1]["arm_id"] == "ARM-001"
            assert call_args[0][1]["payload_kg"] == 2.5

    def test_emit_robot_task_update(self):
        """Test robot task update event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_robot_task_update

            emit_robot_task_update(
                arm_id="ARM-001",
                task_id="TSK-001",
                status="in_progress",
                progress_percent=45.0,
                error=None
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "robot:task_update"
            assert call_args[0][1]["task_id"] == "TSK-001"
            assert call_args[0][1]["progress_percent"] == 45.0

    def test_emit_robot_safety_violation_critical(self):
        """Test robot safety violation event with critical severity."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_robot_safety_violation

            emit_robot_safety_violation(
                arm_id="ARM-001",
                zone_id="ZONE-RESTRICTED-01",
                violation_type="zone_intrusion",
                severity="critical",
                action_taken="emergency_stop"
            )

            # Should emit to both robotics and safety rooms
            assert mock_socketio.emit.call_count == 2

    def test_emit_robot_sync_status(self):
        """Test synchronized motion status event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_robot_sync_status

            emit_robot_sync_status(
                sync_id="SYNC-001",
                arms=["ARM-001", "ARM-002"],
                status="synchronized",
                phase="execution",
                error=None
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "robot:sync_status"
            assert len(call_args[0][1]["arms"]) == 2

    def test_emit_robot_trajectory_update(self):
        """Test trajectory execution progress event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_robot_trajectory_update

            emit_robot_trajectory_update(
                arm_id="ARM-001",
                trajectory_id="TRAJ-001",
                waypoint_index=5,
                total_waypoints=10,
                eta_seconds=30
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "robot:trajectory_update"
            assert call_args[0][1]["progress_percent"] == 50.0

    def test_emit_robot_calibration_update(self):
        """Test calibration status event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_robot_calibration_update

            emit_robot_calibration_update(
                arm_id="ARM-001",
                calibration_type="joint_calibration",
                status="completed",
                accuracy_mm=0.02
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "robot:calibration_update"
            assert call_args[0][1]["accuracy_mm"] == 0.02


class TestUnityDigitalTwinEvents:
    """Test Unity Digital Twin WebSocket events."""

    def test_emit_unity_scene_update(self):
        """Test Unity scene update event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_unity_scene_update

            equipment_updates = [
                {"equipment_id": "EQ-001", "state": "printing", "progress": 45.5},
                {"equipment_id": "EQ-002", "state": "idle"},
            ]

            emit_unity_scene_update(
                scene_name="FactoryFloor",
                equipment_updates=equipment_updates,
                delta_only=True
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "unity:scene_update"
            assert len(call_args[0][1]["equipment_updates"]) == 2
            assert call_args[1]["room"] == "unity"

    def test_emit_unity_equipment_state(self):
        """Test single equipment state change event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_unity_equipment_state

            emit_unity_equipment_state(
                equipment_id="EQ-PRINT-001",
                state="printing",
                position={"x": 0.0, "y": 0.0, "z": 0.0},
                rotation={"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                animation="print_active"
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "unity:equipment_state"
            assert call_args[0][1]["equipment_id"] == "EQ-PRINT-001"

    def test_emit_unity_highlight(self):
        """Test equipment highlight command event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_unity_highlight

            emit_unity_highlight(
                equipment_id="EQ-PRINT-001",
                highlight_type="alert",
                color="#FF0000",
                duration_ms=2000
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "unity:highlight"
            assert call_args[0][1]["highlight_type"] == "alert"

    def test_emit_unity_camera_command(self):
        """Test camera command event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_unity_camera_command

            emit_unity_camera_command(
                command="focus",
                target="EQ-PRINT-001",
                position=None,
                rotation=None,
                duration_ms=1000
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "unity:camera_command"
            assert call_args[0][1]["command"] == "focus"

    def test_emit_unity_heatmap_update(self):
        """Test heatmap data update event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_unity_heatmap_update

            data_points = [
                {"x": 0.0, "y": 0.0, "z": 0.0, "value": 0.8},
                {"x": 1.0, "y": 0.0, "z": 0.0, "value": 0.6},
            ]

            emit_unity_heatmap_update(
                heatmap_type="oee",
                data_points=data_points,
                color_scale={"min": "#00FF00", "max": "#FF0000"}
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "unity:heatmap_update"
            assert len(call_args[0][1]["data_points"]) == 2

    def test_emit_unity_annotation(self):
        """Test 3D annotation event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_unity_annotation

            emit_unity_annotation(
                equipment_id="EQ-PRINT-001",
                annotation_type="status",
                content="Printing: 45.5%",
                position_offset={"x": 0.0, "y": 1.0, "z": 0.0}
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "unity:annotation"
            assert call_args[0][1]["content"] == "Printing: 45.5%"


class TestSupplyChainTwinEvents:
    """Test Supply Chain Twin WebSocket events."""

    def test_emit_supply_chain_disruption(self):
        """Test supply chain disruption alert event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_supply_chain_disruption

            emit_supply_chain_disruption(
                disruption_id="DIS-001",
                node_id="SUP-001",
                disruption_type="supplier_shutdown",
                severity="high",
                impact_summary={"affected_nodes": 3, "production_impact_percent": 35}
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "supply_chain:disruption"
            assert call_args[0][1]["severity"] == "high"

    def test_emit_supply_chain_flow_update(self):
        """Test material flow update event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_supply_chain_flow_update

            emit_supply_chain_flow_update(
                edge_id="E-001",
                source_node="SUP-001",
                target_node="WH-001",
                material_type="ABS_RED",
                flow_rate=5000,
                eta_hours=24
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "supply_chain:flow_update"
            assert call_args[0][1]["flow_rate"] == 5000

    def test_emit_supply_chain_inventory_update_low_stock(self):
        """Test inventory update with low stock alert."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_supply_chain_inventory_update

            emit_supply_chain_inventory_update(
                node_id="WH-001",
                material_type="ABS_YELLOW",
                quantity=15000,
                reorder_point=20000,
                days_of_supply=7.5
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "supply_chain:inventory_update"
            assert call_args[0][1]["alert"] is True  # quantity <= reorder_point

    def test_emit_supply_chain_risk_update(self):
        """Test supply chain risk score update event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_supply_chain_risk_update

            emit_supply_chain_risk_update(
                node_id="SUP-001",
                risk_score=75,
                risk_factors=["single_source", "geographic_concentration"],
                recommendations=["Qualify secondary supplier", "Increase safety stock"]
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "supply_chain:risk_update"
            assert call_args[0][1]["risk_score"] == 75

    def test_emit_supply_chain_order_update(self):
        """Test purchase order status update event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_supply_chain_order_update

            emit_supply_chain_order_update(
                order_id="PO-2024-001",
                supplier_id="SUP-001",
                status="shipped",
                expected_delivery="2024-12-15",
                items=[{"material": "ABS_RED", "quantity": 10000, "unit": "kg"}]
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "supply_chain:order_update"
            assert call_args[0][1]["status"] == "shipped"

    def test_emit_supply_chain_simulation_result(self):
        """Test supply chain simulation completion event."""
        with patch('dashboard.websocket.socketio') as mock_socketio:
            from dashboard.websocket import emit_supply_chain_simulation_result

            results_summary = {
                "affected_nodes": ["WH-001", "FAC-001"],
                "production_impact_percent": 35,
                "recovery_time_days": 12
            }

            emit_supply_chain_simulation_result(
                simulation_id="SIM-001",
                scenario_name="Supplier shutdown at SUP-001",
                results_summary=results_summary,
                detailed_results=None
            )

            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == "supply_chain:simulation_result"
            assert call_args[0][1]["results_summary"]["production_impact_percent"] == 35


class TestWebSocketEventRegistration:
    """Test WebSocket event handler registration."""

    def test_register_vr_training_events(self):
        """Test VR training event handler registration."""
        mock_socketio = MagicMock()

        from dashboard.websocket import register_vr_training_events
        register_vr_training_events(mock_socketio)

        # Verify handlers were registered
        assert mock_socketio.on.called

    def test_register_robotics_events(self):
        """Test robotics event handler registration."""
        mock_socketio = MagicMock()

        from dashboard.websocket import register_robotics_events
        register_robotics_events(mock_socketio)

        assert mock_socketio.on.called

    def test_register_unity_events(self):
        """Test Unity event handler registration."""
        mock_socketio = MagicMock()

        from dashboard.websocket import register_unity_events
        register_unity_events(mock_socketio)

        assert mock_socketio.on.called

    def test_register_supply_chain_events(self):
        """Test supply chain event handler registration."""
        mock_socketio = MagicMock()

        from dashboard.websocket import register_supply_chain_events
        register_supply_chain_events(mock_socketio)

        assert mock_socketio.on.called


class TestEventExports:
    """Test that all events are properly exported."""

    def test_vr_training_events_exported(self):
        """Test VR training events are exported."""
        from dashboard.websocket.events import (
            emit_vr_session_started,
            emit_vr_step_progress,
            emit_vr_session_complete,
            emit_vr_device_status,
            emit_vr_safety_event,
            register_vr_training_events,
        )

        assert callable(emit_vr_session_started)
        assert callable(emit_vr_step_progress)
        assert callable(emit_vr_session_complete)
        assert callable(emit_vr_device_status)
        assert callable(emit_vr_safety_event)
        assert callable(register_vr_training_events)

    def test_robotics_events_exported(self):
        """Test robotics events are exported."""
        from dashboard.websocket.events import (
            emit_robot_status,
            emit_robot_task_update,
            emit_robot_safety_violation,
            emit_robot_sync_status,
            emit_robot_trajectory_update,
            emit_robot_calibration_update,
            register_robotics_events,
        )

        assert callable(emit_robot_status)
        assert callable(emit_robot_task_update)
        assert callable(emit_robot_safety_violation)
        assert callable(emit_robot_sync_status)
        assert callable(emit_robot_trajectory_update)
        assert callable(emit_robot_calibration_update)
        assert callable(register_robotics_events)

    def test_unity_events_exported(self):
        """Test Unity events are exported."""
        from dashboard.websocket.events import (
            emit_unity_scene_update,
            emit_unity_equipment_state,
            emit_unity_highlight,
            emit_unity_camera_command,
            emit_unity_heatmap_update,
            emit_unity_annotation,
            register_unity_events,
        )

        assert callable(emit_unity_scene_update)
        assert callable(emit_unity_equipment_state)
        assert callable(emit_unity_highlight)
        assert callable(emit_unity_camera_command)
        assert callable(emit_unity_heatmap_update)
        assert callable(emit_unity_annotation)
        assert callable(register_unity_events)

    def test_supply_chain_events_exported(self):
        """Test supply chain events are exported."""
        from dashboard.websocket.events import (
            emit_supply_chain_disruption,
            emit_supply_chain_flow_update,
            emit_supply_chain_inventory_update,
            emit_supply_chain_risk_update,
            emit_supply_chain_order_update,
            emit_supply_chain_simulation_result,
            register_supply_chain_events,
        )

        assert callable(emit_supply_chain_disruption)
        assert callable(emit_supply_chain_flow_update)
        assert callable(emit_supply_chain_inventory_update)
        assert callable(emit_supply_chain_risk_update)
        assert callable(emit_supply_chain_order_update)
        assert callable(emit_supply_chain_simulation_result)
        assert callable(register_supply_chain_events)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
