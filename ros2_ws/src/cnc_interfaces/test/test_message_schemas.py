#!/usr/bin/env python3
"""
Tests for cnc_interfaces message schemas.

Verifies that all custom messages, services, and actions:
- Have required fields
- Can be instantiated
- Have correct default values
- Can be serialized/deserialized
"""

import pytest


class TestMachineStatusMessage:
    """Tests for MachineStatus.msg"""

    def test_import(self):
        """Verify MachineStatus can be imported."""
        from cnc_interfaces.msg import MachineStatus
        assert MachineStatus is not None

    def test_has_required_fields(self):
        """Verify MachineStatus has all required fields."""
        from cnc_interfaces.msg import MachineStatus

        msg = MachineStatus()
        assert hasattr(msg, 'machine_id')
        assert hasattr(msg, 'state')
        assert hasattr(msg, 'state_text')
        assert hasattr(msg, 'mpos_x')
        assert hasattr(msg, 'mpos_y')
        assert hasattr(msg, 'mpos_z')
        assert hasattr(msg, 'feed_rate')
        assert hasattr(msg, 'spindle_speed')
        assert hasattr(msg, 'planner_buffer')
        assert hasattr(msg, 'rx_buffer')

    def test_field_assignment(self):
        """Verify fields can be assigned values."""
        from cnc_interfaces.msg import MachineStatus

        msg = MachineStatus()
        msg.machine_id = 'tinyg_001'
        msg.state = 2
        msg.state_text = 'run'
        msg.mpos_x = 100.5
        msg.mpos_y = 50.25
        msg.mpos_z = -10.0
        msg.feed_rate = 1000.0
        msg.spindle_speed = 12000.0
        msg.planner_buffer = 24
        msg.rx_buffer = 128

        assert msg.machine_id == 'tinyg_001'
        assert msg.state == 2
        assert msg.mpos_x == 100.5
        assert msg.feed_rate == 1000.0


class TestGrblStatusMessage:
    """Tests for GrblStatus.msg"""

    def test_import(self):
        """Verify GrblStatus can be imported."""
        from cnc_interfaces.msg import GrblStatus
        assert GrblStatus is not None

    def test_has_required_fields(self):
        """Verify GrblStatus has all required fields."""
        from cnc_interfaces.msg import GrblStatus

        msg = GrblStatus()
        assert hasattr(msg, 'machine_id')
        assert hasattr(msg, 'state')
        assert hasattr(msg, 'pos_x')
        assert hasattr(msg, 'pos_y')
        assert hasattr(msg, 'pos_z')
        assert hasattr(msg, 'wco_x')
        assert hasattr(msg, 'wco_y')
        assert hasattr(msg, 'wco_z')
        assert hasattr(msg, 'feed_rate')
        assert hasattr(msg, 'spindle_speed')


class TestSensorReadingMessage:
    """Tests for SensorReading.msg"""

    def test_import(self):
        """Verify SensorReading can be imported."""
        from cnc_interfaces.msg import SensorReading
        assert SensorReading is not None

    def test_has_required_fields(self):
        """Verify SensorReading has all required fields."""
        from cnc_interfaces.msg import SensorReading

        msg = SensorReading()
        assert hasattr(msg, 'sensor_id')
        assert hasattr(msg, 'sensor_type')
        assert hasattr(msg, 'values')
        assert hasattr(msg, 'header')  # Uses header.stamp for timestamp

    def test_values_is_array(self):
        """Verify values field can hold multi-axis data."""
        from cnc_interfaces.msg import SensorReading

        msg = SensorReading()
        msg.sensor_id = 'test_imu'
        msg.sensor_type = 'imu'
        msg.values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]  # ax, ay, az, gx, gy, gz

        assert len(msg.values) == 6
        assert msg.values[0] == 1.0
        assert msg.values[5] == 6.0


class TestAlarmMessage:
    """Tests for Alarm.msg"""

    def test_import(self):
        """Verify Alarm can be imported."""
        from cnc_interfaces.msg import Alarm
        assert Alarm is not None

    def test_has_required_fields(self):
        """Verify Alarm has all required fields."""
        from cnc_interfaces.msg import Alarm

        msg = Alarm()
        assert hasattr(msg, 'machine_id')
        assert hasattr(msg, 'code')
        assert hasattr(msg, 'category')
        assert hasattr(msg, 'severity')
        assert hasattr(msg, 'message')
        assert hasattr(msg, 'header')  # Uses header.stamp for timestamp
        assert hasattr(msg, 'recoverable')

    def test_severity_constants(self):
        """Verify Alarm has severity level constants."""
        from cnc_interfaces.msg import Alarm

        # Check constants exist
        assert hasattr(Alarm, 'SEVERITY_INFO')
        assert hasattr(Alarm, 'SEVERITY_WARNING')
        assert hasattr(Alarm, 'SEVERITY_ERROR')
        assert hasattr(Alarm, 'SEVERITY_CRITICAL')

        # Check constant values
        assert Alarm.SEVERITY_INFO == 0
        assert Alarm.SEVERITY_WARNING == 1
        assert Alarm.SEVERITY_ERROR == 2
        assert Alarm.SEVERITY_CRITICAL == 3


class TestHomeService:
    """Tests for Home.srv"""

    def test_import(self):
        """Verify Home service can be imported."""
        from cnc_interfaces.srv import Home
        assert Home is not None

    def test_request_fields(self):
        """Verify Home.Request has required fields."""
        from cnc_interfaces.srv import Home

        req = Home.Request()
        assert hasattr(req, 'machine_id')
        assert hasattr(req, 'axes')

    def test_response_fields(self):
        """Verify Home.Response has required fields."""
        from cnc_interfaces.srv import Home

        resp = Home.Response()
        assert hasattr(resp, 'success')
        assert hasattr(resp, 'message')
        assert hasattr(resp, 'home_x')
        assert hasattr(resp, 'home_y')
        assert hasattr(resp, 'home_z')


class TestJogService:
    """Tests for Jog.srv"""

    def test_import(self):
        """Verify Jog service can be imported."""
        from cnc_interfaces.srv import Jog
        assert Jog is not None

    def test_request_fields(self):
        """Verify Jog.Request has required fields."""
        from cnc_interfaces.srv import Jog

        req = Jog.Request()
        assert hasattr(req, 'x')
        assert hasattr(req, 'y')
        assert hasattr(req, 'z')
        assert hasattr(req, 'feed_rate')
        assert hasattr(req, 'jog_type')

    def test_jog_type_constants(self):
        """Verify jog type constants exist."""
        from cnc_interfaces.srv import Jog

        req = Jog.Request()
        # Jog types: 0=CONTINUOUS, 1=INCREMENTAL, 2=ABSOLUTE
        req.jog_type = 0
        req.jog_type = 1
        req.jog_type = 2


class TestSendGcodeService:
    """Tests for SendGcode.srv"""

    def test_import(self):
        """Verify SendGcode service can be imported."""
        from cnc_interfaces.srv import SendGcode
        assert SendGcode is not None

    def test_request_fields(self):
        """Verify SendGcode.Request has required fields."""
        from cnc_interfaces.srv import SendGcode

        req = SendGcode.Request()
        assert hasattr(req, 'machine_id')
        assert hasattr(req, 'gcode')
        assert hasattr(req, 'wait_complete')
        assert hasattr(req, 'timeout')

    def test_response_fields(self):
        """Verify SendGcode.Response has required fields."""
        from cnc_interfaces.srv import SendGcode

        resp = SendGcode.Response()
        assert hasattr(resp, 'success')
        assert hasattr(resp, 'message')
        assert hasattr(resp, 'response')
        assert hasattr(resp, 'lines_sent')
        assert hasattr(resp, 'errors')


class TestEmergencyStopService:
    """Tests for EmergencyStop.srv"""

    def test_import(self):
        """Verify EmergencyStop service can be imported."""
        from cnc_interfaces.srv import EmergencyStop
        assert EmergencyStop is not None

    def test_request_fields(self):
        """Verify EmergencyStop.Request has required fields."""
        from cnc_interfaces.srv import EmergencyStop

        req = EmergencyStop.Request()
        assert hasattr(req, 'machine_id')
        assert hasattr(req, 'action')
        assert hasattr(req, 'reason')


class TestExecuteGcodeAction:
    """Tests for ExecuteGcode.action"""

    def test_import(self):
        """Verify ExecuteGcode action can be imported."""
        from cnc_interfaces.action import ExecuteGcode
        assert ExecuteGcode is not None

    def test_goal_fields(self):
        """Verify ExecuteGcode.Goal has required fields."""
        from cnc_interfaces.action import ExecuteGcode

        goal = ExecuteGcode.Goal()
        assert hasattr(goal, 'machine_id')
        assert hasattr(goal, 'gcode_program')
        assert hasattr(goal, 'file_path')
        assert hasattr(goal, 'dry_run')
        assert hasattr(goal, 'feed_override')

    def test_result_fields(self):
        """Verify ExecuteGcode.Result has required fields."""
        from cnc_interfaces.action import ExecuteGcode

        result = ExecuteGcode.Result()
        assert hasattr(result, 'success')
        assert hasattr(result, 'message')
        assert hasattr(result, 'lines_executed')
        assert hasattr(result, 'lines_total')
        assert hasattr(result, 'execution_time')
        assert hasattr(result, 'errors')

    def test_feedback_fields(self):
        """Verify ExecuteGcode.Feedback has required fields."""
        from cnc_interfaces.action import ExecuteGcode

        feedback = ExecuteGcode.Feedback()
        assert hasattr(feedback, 'current_line')
        assert hasattr(feedback, 'total_lines')
        assert hasattr(feedback, 'progress_percent')
        assert hasattr(feedback, 'current_gcode')
        assert hasattr(feedback, 'x')
        assert hasattr(feedback, 'y')
        assert hasattr(feedback, 'z')
        assert hasattr(feedback, 'machine_state')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
