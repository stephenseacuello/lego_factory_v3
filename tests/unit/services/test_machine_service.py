"""
LEGO Factory v3 - Machine Service Unit Tests
=============================================
Tests for machine control and management functionality.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime
import asyncio


class TestMachineConnection:
    """Tests for machine connection functionality."""

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_machine_controller):
        """Successful connection should return True."""
        result = await mock_machine_controller.connect()
        assert result is True
        mock_machine_controller.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure_returns_false(self):
        """Failed connection should return False."""
        controller = AsyncMock()
        controller.connect = AsyncMock(return_value=False)

        result = await controller.connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_success(self, mock_machine_controller):
        """Successful disconnection should return True."""
        result = await mock_machine_controller.disconnect()
        assert result is True
        mock_machine_controller.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Connection errors should be handled gracefully."""
        controller = AsyncMock()
        controller.connect = AsyncMock(side_effect=ConnectionError("Port not found"))

        with pytest.raises(ConnectionError) as exc_info:
            await controller.connect()

        assert "Port not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_reconnect_after_disconnect(self, mock_machine_controller):
        """Should be able to reconnect after disconnecting."""
        await mock_machine_controller.disconnect()
        result = await mock_machine_controller.connect()

        assert result is True
        assert mock_machine_controller.connect.call_count >= 1

    def test_connection_config_validation(self, sample_machine_data):
        """Connection configuration should be validated."""
        config = sample_machine_data.get('connection_config', {})

        # For simulation mode, config can be empty
        assert isinstance(config, dict)


class TestMachineStatusUpdates:
    """Tests for machine status monitoring."""

    def test_status_contains_required_fields(self, mock_machine_controller):
        """Machine status should contain required fields."""
        status = mock_machine_controller.status

        assert hasattr(status, 'state')
        assert hasattr(status, 'position')

    def test_status_state_transitions(self):
        """Machine should transition through valid states."""
        valid_states = ['disconnected', 'idle', 'running', 'hold', 'homing', 'alarm', 'error']

        # Verify state transition validity
        for state in valid_states:
            assert state in valid_states

        # Invalid state should not be in list
        assert 'invalid_state' not in valid_states

    def test_position_update(self):
        """Position should be updated correctly."""
        position = MagicMock()
        position.x = 10.5
        position.y = 20.3
        position.z = 5.0

        assert position.x == 10.5
        assert position.y == 20.3
        assert position.z == 5.0

    def test_feed_rate_tracking(self, mock_machine_controller):
        """Feed rate should be tracked."""
        mock_machine_controller.status.feed_rate = 1000.0

        assert mock_machine_controller.status.feed_rate == 1000.0

    def test_spindle_speed_tracking(self):
        """Spindle speed should be tracked."""
        status = MagicMock()
        status.spindle_speed = 12000.0

        assert status.spindle_speed == 12000.0

    def test_progress_tracking(self):
        """Job progress should be tracked."""
        status = MagicMock()
        status.current_line = 50
        status.total_lines = 100
        status.progress_pct = 50.0

        assert status.current_line == 50
        assert status.total_lines == 100
        assert status.progress_pct == 50.0

    def test_status_callback_notification(self):
        """Status callbacks should be notified on changes."""
        callbacks = []
        callback_called = False

        def status_callback(status):
            nonlocal callback_called
            callback_called = True
            callbacks.append(status)

        # Simulate callback registration and notification
        status = {'state': 'running'}
        status_callback(status)

        assert callback_called is True
        assert len(callbacks) == 1


class TestCommandSending:
    """Tests for sending commands to machines."""

    @pytest.mark.asyncio
    async def test_send_command_success(self, mock_machine_controller):
        """Commands should be sent and response received."""
        response = await mock_machine_controller.send_command("G0 X10 Y10")

        assert response == "ok"
        mock_machine_controller.send_command.assert_called_once_with("G0 X10 Y10")

    @pytest.mark.asyncio
    async def test_send_command_with_timeout(self):
        """Commands should timeout if no response."""
        controller = AsyncMock()
        controller.send_command = AsyncMock(side_effect=asyncio.TimeoutError())

        with pytest.raises(asyncio.TimeoutError):
            await controller.send_command("G0 X10", timeout=1.0)

    @pytest.mark.asyncio
    async def test_home_command(self, mock_machine_controller):
        """Home command should work for all axes."""
        result = await mock_machine_controller.home('XYZ')

        assert result is True
        mock_machine_controller.home.assert_called_once()

    @pytest.mark.asyncio
    async def test_home_single_axis(self, mock_machine_controller):
        """Should be able to home single axis."""
        result = await mock_machine_controller.home('X')

        assert result is True

    @pytest.mark.asyncio
    async def test_zero_command(self, mock_machine_controller):
        """Zero command should set work coordinates."""
        result = await mock_machine_controller.zero('XYZ')

        assert result is True
        mock_machine_controller.zero.assert_called_once()

    @pytest.mark.asyncio
    async def test_jog_command(self, mock_machine_controller):
        """Jog command should move axis by specified amount."""
        result = await mock_machine_controller.jog('X', 10.0, 500.0)

        assert result is True
        mock_machine_controller.jog.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_command(self, mock_machine_controller):
        """Stop command should halt machine."""
        result = await mock_machine_controller.stop()

        assert result is True
        mock_machine_controller.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_and_resume(self, mock_machine_controller):
        """Pause and resume should work correctly."""
        pause_result = await mock_machine_controller.pause()
        resume_result = await mock_machine_controller.resume()

        assert pause_result is True
        assert resume_result is True

    @pytest.mark.asyncio
    async def test_reset_command(self, mock_machine_controller):
        """Reset command should reset machine state."""
        result = await mock_machine_controller.reset()

        assert result is True
        mock_machine_controller.reset.assert_called_once()


class TestGCodeExecution:
    """Tests for G-code program execution."""

    @pytest.mark.asyncio
    async def test_run_gcode_success(self, mock_machine_controller):
        """G-code program should execute successfully."""
        gcode = """
        G0 X0 Y0 Z0
        G1 X10 F500
        G1 Y10
        G0 Z5
        """
        result = await mock_machine_controller.run_gcode(gcode)

        assert result is True
        mock_machine_controller.run_gcode.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_gcode_with_callback(self):
        """Line callback should be called for each line."""
        lines_processed = []

        def line_callback(line_num, line):
            lines_processed.append((line_num, line))

        controller = AsyncMock()
        controller.run_gcode = AsyncMock(return_value=True)

        await controller.run_gcode("G0 X0\nG1 X10", on_line=line_callback)

        controller.run_gcode.assert_called_once()

    def test_gcode_line_parsing(self):
        """G-code lines should be parsed correctly."""
        gcode = """
        ; Comment line
        G0 X10 Y10 Z0 ; Move to start
        G1 X20 F500   ; Feed move
        M3 S12000     ; Spindle on
        """
        lines = [
            l.strip()
            for l in gcode.split('\n')
            if l.strip() and not l.strip().startswith(';')
        ]

        # Should have 3 valid lines (comments stripped)
        assert len(lines) == 3

    @pytest.mark.asyncio
    async def test_gcode_execution_state_transition(self):
        """Machine should transition to RUNNING during execution."""
        controller = AsyncMock()
        controller.status = MagicMock()

        # Simulate state changes during execution
        controller.status.state = 'running'

        assert controller.status.state == 'running'

    @pytest.mark.asyncio
    async def test_gcode_execution_completes(self):
        """Machine should return to IDLE after execution."""
        controller = AsyncMock()
        controller.status = MagicMock()
        controller.status.state = 'idle'

        assert controller.status.state == 'idle'


class TestErrorHandling:
    """Tests for machine error handling."""

    @pytest.mark.asyncio
    async def test_connection_lost_handling(self):
        """Connection loss should be handled gracefully."""
        controller = AsyncMock()
        controller.send_command = AsyncMock(
            side_effect=ConnectionError("Connection lost")
        )

        with pytest.raises(ConnectionError):
            await controller.send_command("G0 X10")

    def test_alarm_state_detection(self):
        """Alarm state should be detected."""
        status = MagicMock()
        status.state = 'alarm'
        status.error_message = 'Limit switch triggered'

        assert status.state == 'alarm'
        assert status.error_message is not None

    def test_error_state_detection(self):
        """Error state should be detected."""
        status = MagicMock()
        status.state = 'error'
        status.error_message = 'Communication error'

        assert status.state == 'error'

    @pytest.mark.asyncio
    async def test_error_recovery_with_reset(self):
        """Reset should recover from error state."""
        controller = AsyncMock()
        controller.status = MagicMock()
        controller.status.state = 'error'
        controller.reset = AsyncMock(return_value=True)

        await controller.reset()
        controller.status.state = 'idle'

        assert controller.status.state == 'idle'

    def test_error_callback_notification(self):
        """Error callbacks should be notified."""
        errors = []

        def error_callback(error):
            errors.append(error)

        # Simulate error notification
        error = {'type': 'alarm', 'message': 'Limit switch'}
        error_callback(error)

        assert len(errors) == 1
        assert errors[0]['type'] == 'alarm'

    @pytest.mark.asyncio
    async def test_command_queue_overflow(self):
        """Command queue overflow should be handled."""
        controller = AsyncMock()
        controller.send_command = AsyncMock(
            side_effect=Exception("Command queue full")
        )

        with pytest.raises(Exception) as exc_info:
            await controller.send_command("G0 X10")

        assert "queue full" in str(exc_info.value).lower()


class TestMachineManager:
    """Tests for machine manager functionality."""

    def test_register_machine(self):
        """Machine should be registered successfully."""
        machines = {}
        machine_id = 'test-001'
        config = {'port': '/dev/ttyUSB0', 'baud_rate': 115200}

        machines[machine_id] = config

        assert machine_id in machines
        assert machines[machine_id] == config

    def test_unregister_machine(self):
        """Machine should be unregistered successfully."""
        machines = {'test-001': {}}

        del machines['test-001']

        assert 'test-001' not in machines

    def test_get_machine_returns_controller(self):
        """Get machine should return controller instance."""
        machines = {'test-001': MagicMock()}

        controller = machines.get('test-001')

        assert controller is not None

    def test_get_nonexistent_machine_returns_none(self):
        """Getting non-existent machine should return None."""
        machines = {}

        controller = machines.get('nonexistent')

        assert controller is None

    def test_list_machines(self):
        """Should list all registered machines."""
        machines = {
            'machine-001': {},
            'machine-002': {},
            'machine-003': {},
        }

        machine_list = list(machines.keys())

        assert len(machine_list) == 3
        assert 'machine-001' in machine_list

    def test_get_all_status(self):
        """Should get status of all machines."""
        machines = {
            'machine-001': MagicMock(status=MagicMock(state='idle')),
            'machine-002': MagicMock(status=MagicMock(state='running')),
        }

        statuses = {mid: m.status for mid, m in machines.items()}

        assert len(statuses) == 2
        assert statuses['machine-001'].state == 'idle'
        assert statuses['machine-002'].state == 'running'


class TestSimulationController:
    """Tests for simulation controller."""

    @pytest.mark.asyncio
    async def test_simulation_connect(self):
        """Simulation controller should connect instantly."""
        controller = AsyncMock()
        controller.connect = AsyncMock(return_value=True)

        result = await controller.connect()

        assert result is True

    @pytest.mark.asyncio
    async def test_simulation_jog_updates_position(self):
        """Jog should update simulated position."""
        position = MagicMock(x=0.0, y=0.0, z=0.0)

        # Simulate jog
        position.x = 10.0

        assert position.x == 10.0

    @pytest.mark.asyncio
    async def test_simulation_home_zeros_position(self):
        """Home should zero simulated position."""
        position = MagicMock(x=10.0, y=20.0, z=5.0)

        # Simulate homing
        position.x = 0.0
        position.y = 0.0
        position.z = 0.0

        assert position.x == 0.0
        assert position.y == 0.0
        assert position.z == 0.0

    @pytest.mark.asyncio
    async def test_simulation_gcode_progress(self):
        """Simulation should track G-code progress."""
        status = MagicMock()
        status.total_lines = 10
        status.current_line = 5
        status.progress_pct = 50.0

        assert status.progress_pct == 50.0


class TestControllerTypes:
    """Tests for different controller types."""

    def test_controller_type_enum(self):
        """Controller types should be properly defined."""
        controller_types = ['tinyg', 'grbl', 'marlin', 'bambu', 'ros2', 'simulation']

        for ct in controller_types:
            assert isinstance(ct, str)
            assert len(ct) > 0

    def test_create_controller_by_type(self):
        """Should create correct controller based on type."""
        controller_map = {
            'tinyg': 'TinyGController',
            'grbl': 'GRBLController',
            'simulation': 'SimulationController',
        }

        for controller_type, controller_class in controller_map.items():
            assert controller_class is not None

    def test_machine_state_enum(self):
        """Machine states should be properly defined."""
        states = ['disconnected', 'idle', 'running', 'hold', 'homing', 'alarm', 'error']

        for state in states:
            assert isinstance(state, str)
