"""
Action Executor - Equipment command execution.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 5: Algorithm-to-Action Bridge
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of action execution."""
    success: bool
    command_sent: str
    response: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class ActionExecutor:
    """
    Execute actions on manufacturing equipment.

    Translates high-level AI decisions into equipment-specific commands.

    Features:
    - Multi-protocol support (OctoPrint, Moonraker, GRBL)
    - G-code generation from semantic actions
    - Command batching and queuing
    - Execution monitoring
    """

    def __init__(self):
        self._equipment_registry: Dict[str, Any] = {}
        self._command_queue: asyncio.Queue = asyncio.Queue()
        self._execution_history: List[ExecutionResult] = []
        self._max_history = 1000

    def register_equipment(self, equipment_id: str, controller: Any) -> None:
        """Register equipment controller."""
        self._equipment_registry[equipment_id] = controller
        logger.info(f"Registered equipment: {equipment_id}")

    def unregister_equipment(self, equipment_id: str) -> None:
        """Unregister equipment controller."""
        if equipment_id in self._equipment_registry:
            del self._equipment_registry[equipment_id]
            logger.info(f"Unregistered equipment: {equipment_id}")

    async def execute(self, action: Any) -> Dict[str, Any]:
        """
        Execute an action step on equipment.

        Args:
            action: ActionStep with action_type and parameters

        Returns:
            Execution result dictionary
        """
        action_type = getattr(action, 'action_type', 'unknown')
        params = getattr(action, 'parameters', {})
        equipment_id = params.get('equipment_id', 'default')

        start_time = datetime.utcnow()

        try:
            # Get equipment controller
            controller = self._equipment_registry.get(equipment_id)

            if controller is None:
                # Simulate if no controller available
                logger.warning(f"No controller for {equipment_id}, simulating")
                await asyncio.sleep(0.1)
                return await self._simulate_execution(action_type, params)

            # Convert action to commands
            commands = self._action_to_commands(action_type, params)

            # Execute commands
            result = await self._execute_commands(controller, commands)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            exec_result = ExecutionResult(
                success=result.get('success', True),
                command_sent='; '.join(commands),
                response=result.get('response'),
                execution_time_ms=execution_time
            )
            self._record_execution(exec_result)

            return {
                'success': exec_result.success,
                'command': exec_result.command_sent,
                'response': exec_result.response,
                'execution_time_ms': exec_result.execution_time_ms
            }

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            exec_result = ExecutionResult(
                success=False,
                command_sent=f"action:{action_type}",
                error=str(e),
                execution_time_ms=execution_time
            )
            self._record_execution(exec_result)
            raise

    def _action_to_commands(self, action_type: str, params: Dict) -> List[str]:
        """Convert semantic action to G-code/equipment commands."""
        commands = []

        if action_type == 'temperature_adjust':
            target = params.get('value', params.get('temperature', 0))
            heater = params.get('heater', 'nozzle')

            if heater == 'nozzle':
                commands.append(f"M104 S{target}")
            elif heater == 'bed':
                commands.append(f"M140 S{target}")
            elif heater == 'chamber':
                commands.append(f"M141 S{target}")

        elif action_type == 'speed_adjust':
            speed_pct = int(params.get('value', 100))
            commands.append(f"M220 S{speed_pct}")

        elif action_type == 'flow_adjust':
            flow_pct = int(params.get('value', 100))
            commands.append(f"M221 S{flow_pct}")

        elif action_type == 'z_offset_adjust':
            offset = params.get('value', 0)
            commands.append(f"SET_GCODE_OFFSET Z_ADJUST={offset} MOVE=1")

        elif action_type == 'fan_adjust':
            speed = int(params.get('value', 255))
            fan_idx = params.get('fan', 0)
            if fan_idx == 0:
                commands.append(f"M106 S{speed}")
            else:
                commands.append(f"M106 P{fan_idx} S{speed}")

        elif action_type == 'pause_print':
            commands.append("PAUSE")

        elif action_type == 'resume_print':
            commands.append("RESUME")

        elif action_type == 'cancel_print':
            commands.append("CANCEL_PRINT")

        elif action_type == 'home':
            axes = params.get('axes', 'XYZ')
            commands.append(f"G28 {axes}")

        elif action_type == 'move':
            x = params.get('x')
            y = params.get('y')
            z = params.get('z')
            feedrate = params.get('feedrate', 3000)

            cmd = "G0"
            if x is not None:
                cmd += f" X{x}"
            if y is not None:
                cmd += f" Y{y}"
            if z is not None:
                cmd += f" Z{z}"
            cmd += f" F{feedrate}"
            commands.append(cmd)

        elif action_type == 'extrude':
            length = params.get('length', 10)
            feedrate = params.get('feedrate', 300)
            commands.append(f"G1 E{length} F{feedrate}")

        elif action_type == 'retract':
            length = params.get('length', 5)
            feedrate = params.get('feedrate', 1800)
            commands.append(f"G1 E-{length} F{feedrate}")

        elif action_type == 'gcode':
            # Raw G-code passthrough
            raw = params.get('commands', [])
            if isinstance(raw, str):
                raw = [raw]
            commands.extend(raw)

        else:
            logger.warning(f"Unknown action type: {action_type}")

        return commands

    async def _execute_commands(self,
                               controller: Any,
                               commands: List[str]) -> Dict[str, Any]:
        """Execute commands on equipment controller."""
        responses = []

        for cmd in commands:
            if hasattr(controller, 'send_gcode'):
                # Use protocol's send_gcode method
                result = await controller.send_gcode([cmd])
                responses.append(result)
            elif hasattr(controller, 'execute_command'):
                result = await controller.execute_command(cmd)
                responses.append(result)
            else:
                logger.warning(f"Controller has no command method")
                responses.append("No method available")

        return {
            'success': all('error' not in str(r).lower() for r in responses),
            'response': '; '.join(str(r) for r in responses)
        }

    async def _simulate_execution(self,
                                 action_type: str,
                                 params: Dict) -> Dict[str, Any]:
        """Simulate action execution for testing."""
        commands = self._action_to_commands(action_type, params)

        return {
            'success': True,
            'simulated': True,
            'command': '; '.join(commands),
            'response': 'OK (simulated)'
        }

    def _record_execution(self, result: ExecutionResult) -> None:
        """Record execution in history."""
        self._execution_history.append(result)

        # Trim history
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history:]

    def get_execution_history(self, limit: int = 50) -> List[Dict]:
        """Get recent execution history."""
        history = self._execution_history[-limit:]
        return [
            {
                'success': r.success,
                'command': r.command_sent,
                'response': r.response,
                'error': r.error,
                'execution_time_ms': r.execution_time_ms,
                'timestamp': r.timestamp.isoformat()
            }
            for r in reversed(history)
        ]

    async def execute_batch(self, actions: List[Any]) -> List[Dict[str, Any]]:
        """Execute multiple actions in sequence."""
        results = []

        for action in actions:
            result = await self.execute(action)
            results.append(result)

            # Stop on failure unless action marked as optional
            if not result.get('success', True):
                params = getattr(action, 'parameters', {})
                if not params.get('optional', False):
                    break

        return results


class GCodeGenerator:
    """
    Generate G-code sequences for complex operations.
    """

    @staticmethod
    def generate_purge_line(
        start_x: float = 0,
        start_y: float = 0,
        length: float = 100,
        extrusion: float = 15
    ) -> List[str]:
        """Generate purge line G-code."""
        return [
            f"G0 X{start_x} Y{start_y} Z0.3 F3000",
            f"G1 X{start_x + length} E{extrusion} F1500",
            "G1 E-2 F1800",
            "G0 Z5"
        ]

    @staticmethod
    def generate_bed_level_probe(points: List[tuple]) -> List[str]:
        """Generate bed leveling probe sequence."""
        commands = ["G28"]  # Home first

        for x, y in points:
            commands.append(f"G0 X{x} Y{y} F3000")
            commands.append("G30")  # Probe

        commands.append("G0 Z10")
        return commands

    @staticmethod
    def generate_nozzle_clean(
        wipe_x: float = 50,
        wipe_y: float = 0,
        wipe_length: float = 50
    ) -> List[str]:
        """Generate nozzle cleaning sequence."""
        return [
            f"G0 X{wipe_x} Y{wipe_y} Z0.5 F3000",
            f"G0 X{wipe_x + wipe_length} F1000",
            f"G0 X{wipe_x} F1000",
            f"G0 X{wipe_x + wipe_length} F1000",
            "G0 Z5"
        ]

    @staticmethod
    def generate_filament_change(
        park_x: float = 0,
        park_y: float = 0,
        park_z: float = 50
    ) -> List[str]:
        """Generate filament change sequence."""
        return [
            "M400",  # Wait for moves
            f"G0 Z{park_z} F600",  # Raise Z
            f"G0 X{park_x} Y{park_y} F3000",  # Park
            "M104 S0",  # Heater off
            "M400",
            "M300 S440 P200",  # Beep
        ]
