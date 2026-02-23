"""
Rollback Manager - Action undo/recovery capabilities.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 5: Algorithm-to-Action Bridge
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class RollbackStrategy(Enum):
    """Strategy for rollback execution."""
    REVERSE = "reverse"      # Execute inverse commands
    CHECKPOINT = "checkpoint"  # Restore from checkpoint
    COMPENSATE = "compensate"  # Execute compensating actions
    MANUAL = "manual"        # Require manual intervention


@dataclass
class RollbackAction:
    """Definition of a rollback action."""
    action_id: str
    original_action_type: str
    rollback_type: str
    rollback_commands: List[str]
    strategy: RollbackStrategy
    priority: int = 0
    prerequisites: List[str] = field(default_factory=list)
    estimated_duration_ms: int = 1000


@dataclass
class Checkpoint:
    """System state checkpoint for rollback."""
    checkpoint_id: str
    timestamp: datetime
    state: Dict[str, Any]
    description: str


@dataclass
class RollbackResult:
    """Result of rollback execution."""
    action_id: str
    success: bool
    strategy_used: RollbackStrategy
    commands_executed: List[str]
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


class RollbackManager:
    """
    Manage action rollback and recovery.

    Features:
    - Automatic rollback generation
    - Checkpoint-based recovery
    - Compensating transactions
    - Priority-based rollback ordering
    """

    def __init__(self):
        self._rollback_registry: Dict[str, RollbackAction] = {}
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._executor: Optional[Any] = None
        self._rollback_history: List[RollbackResult] = []
        self._max_checkpoints = 50

    def set_executor(self, executor: Any) -> None:
        """Set action executor for rollback commands."""
        self._executor = executor

    def register_rollback(self,
                         action_id: str,
                         original_type: str,
                         rollback_commands: List[str],
                         strategy: RollbackStrategy = RollbackStrategy.REVERSE,
                         priority: int = 0) -> None:
        """
        Register rollback for an action.

        Args:
            action_id: ID of the action this rolls back
            original_type: Type of original action
            rollback_commands: Commands to execute for rollback
            strategy: Rollback strategy
            priority: Higher priority rolls back first
        """
        self._rollback_registry[action_id] = RollbackAction(
            action_id=action_id,
            original_action_type=original_type,
            rollback_type=f"rollback_{original_type}",
            rollback_commands=rollback_commands,
            strategy=strategy,
            priority=priority
        )
        logger.debug(f"Registered rollback for action {action_id}")

    def auto_register_rollback(self,
                              action_id: str,
                              action_type: str,
                              parameters: Dict[str, Any],
                              pre_state: Dict[str, Any]) -> None:
        """
        Automatically generate and register rollback.

        Args:
            action_id: Action identifier
            action_type: Type of action
            parameters: Action parameters
            pre_state: System state before action
        """
        rollback = self._generate_rollback(action_type, parameters, pre_state)

        if rollback:
            self.register_rollback(
                action_id=action_id,
                original_type=action_type,
                rollback_commands=rollback['commands'],
                strategy=rollback.get('strategy', RollbackStrategy.REVERSE)
            )

    def _generate_rollback(self,
                          action_type: str,
                          params: Dict[str, Any],
                          pre_state: Dict[str, Any]) -> Optional[Dict]:
        """Generate rollback commands for action type."""
        rollback = {'commands': [], 'strategy': RollbackStrategy.REVERSE}

        if action_type == 'temperature_adjust':
            # Restore previous temperature
            heater = params.get('heater', 'nozzle')
            prev_temp = pre_state.get('temperatures', {}).get(f'{heater}_target', 0)

            if heater == 'nozzle':
                rollback['commands'].append(f"M104 S{prev_temp}")
            elif heater == 'bed':
                rollback['commands'].append(f"M140 S{prev_temp}")

        elif action_type == 'speed_adjust':
            prev_speed = pre_state.get('speed_override', 100)
            rollback['commands'].append(f"M220 S{prev_speed}")

        elif action_type == 'flow_adjust':
            prev_flow = pre_state.get('flow_override', 100)
            rollback['commands'].append(f"M221 S{prev_flow}")

        elif action_type == 'z_offset_adjust':
            offset = params.get('value', 0)
            rollback['commands'].append(f"SET_GCODE_OFFSET Z_ADJUST={-offset} MOVE=1")

        elif action_type == 'fan_adjust':
            prev_fan = pre_state.get('fan_speed', 0)
            fan_idx = params.get('fan', 0)
            if fan_idx == 0:
                rollback['commands'].append(f"M106 S{prev_fan}")
            else:
                rollback['commands'].append(f"M106 P{fan_idx} S{prev_fan}")

        elif action_type == 'pause_print':
            rollback['commands'].append("RESUME")

        elif action_type == 'resume_print':
            rollback['commands'].append("PAUSE")

        elif action_type == 'move':
            # Return to previous position
            prev_pos = pre_state.get('position', {})
            x = prev_pos.get('x')
            y = prev_pos.get('y')
            z = prev_pos.get('z')

            cmd = "G0"
            if x is not None:
                cmd += f" X{x}"
            if y is not None:
                cmd += f" Y{y}"
            if z is not None:
                cmd += f" Z{z}"
            cmd += " F3000"

            rollback['commands'].append(cmd)

        elif action_type == 'extrude':
            # Retract
            length = params.get('length', 10)
            rollback['commands'].append(f"G1 E-{length} F1800")

        elif action_type == 'retract':
            # Extrude back
            length = params.get('length', 5)
            rollback['commands'].append(f"G1 E{length} F300")

        elif action_type == 'cancel_print':
            # Cannot undo cancel
            rollback['strategy'] = RollbackStrategy.MANUAL
            rollback['commands'] = []

        if not rollback['commands']:
            return None

        return rollback

    def create_checkpoint(self,
                         checkpoint_id: str,
                         state: Dict[str, Any],
                         description: str = "") -> Checkpoint:
        """
        Create system state checkpoint.

        Args:
            checkpoint_id: Unique checkpoint identifier
            state: Current system state
            description: Human-readable description

        Returns:
            Created checkpoint
        """
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            timestamp=datetime.utcnow(),
            state=state.copy(),
            description=description
        )
        self._checkpoints[checkpoint_id] = checkpoint

        # Trim old checkpoints
        if len(self._checkpoints) > self._max_checkpoints:
            oldest = min(self._checkpoints.values(), key=lambda c: c.timestamp)
            del self._checkpoints[oldest.checkpoint_id]

        logger.info(f"Created checkpoint: {checkpoint_id}")
        return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get checkpoint by ID."""
        return self._checkpoints.get(checkpoint_id)

    async def rollback_action(self, action_id: str) -> RollbackResult:
        """
        Execute rollback for a specific action.

        Args:
            action_id: ID of action to roll back

        Returns:
            Rollback result
        """
        start_time = datetime.utcnow()

        if action_id not in self._rollback_registry:
            return RollbackResult(
                action_id=action_id,
                success=False,
                strategy_used=RollbackStrategy.MANUAL,
                commands_executed=[],
                errors=[f"No rollback registered for action {action_id}"]
            )

        rollback = self._rollback_registry[action_id]
        errors = []
        executed = []

        try:
            if rollback.strategy == RollbackStrategy.MANUAL:
                return RollbackResult(
                    action_id=action_id,
                    success=False,
                    strategy_used=RollbackStrategy.MANUAL,
                    commands_executed=[],
                    errors=["Manual intervention required"]
                )

            # Execute rollback commands
            for cmd in rollback.rollback_commands:
                try:
                    if self._executor:
                        await self._executor.execute_gcode(cmd)
                    executed.append(cmd)
                except Exception as e:
                    errors.append(f"Command '{cmd}' failed: {str(e)}")

            duration = (datetime.utcnow() - start_time).total_seconds() * 1000

            result = RollbackResult(
                action_id=action_id,
                success=len(errors) == 0,
                strategy_used=rollback.strategy,
                commands_executed=executed,
                errors=errors,
                duration_ms=duration
            )

            self._rollback_history.append(result)
            logger.info(f"Rolled back action {action_id}: {result.success}")

            return result

        except Exception as e:
            logger.error(f"Rollback failed for {action_id}: {e}")
            return RollbackResult(
                action_id=action_id,
                success=False,
                strategy_used=rollback.strategy,
                commands_executed=executed,
                errors=[str(e)]
            )

    async def rollback_to_checkpoint(self,
                                    checkpoint_id: str,
                                    state_applier: Callable) -> bool:
        """
        Restore system to checkpoint state.

        Args:
            checkpoint_id: Checkpoint to restore
            state_applier: Function to apply state

        Returns:
            Success status
        """
        checkpoint = self._checkpoints.get(checkpoint_id)

        if not checkpoint:
            logger.error(f"Checkpoint not found: {checkpoint_id}")
            return False

        try:
            if asyncio.iscoroutinefunction(state_applier):
                await state_applier(checkpoint.state)
            else:
                state_applier(checkpoint.state)

            logger.info(f"Restored to checkpoint: {checkpoint_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore checkpoint: {e}")
            return False

    async def rollback_sequence(self,
                               action_ids: List[str],
                               reverse: bool = True) -> List[RollbackResult]:
        """
        Roll back multiple actions.

        Args:
            action_ids: Actions to roll back
            reverse: If True, roll back in reverse order

        Returns:
            List of rollback results
        """
        if reverse:
            action_ids = list(reversed(action_ids))

        # Sort by priority
        rollbacks = []
        for aid in action_ids:
            rb = self._rollback_registry.get(aid)
            if rb:
                rollbacks.append((rb.priority, aid))

        rollbacks.sort(key=lambda x: -x[0])  # Higher priority first

        results = []
        for _, action_id in rollbacks:
            result = await self.rollback_action(action_id)
            results.append(result)

            if not result.success:
                logger.warning(f"Rollback sequence interrupted at {action_id}")
                break

        return results

    def unregister_rollback(self, action_id: str) -> None:
        """Remove rollback registration (action completed successfully)."""
        if action_id in self._rollback_registry:
            del self._rollback_registry[action_id]

    def get_pending_rollbacks(self) -> List[RollbackAction]:
        """Get all registered rollbacks."""
        return list(self._rollback_registry.values())

    def get_rollback_history(self, limit: int = 50) -> List[Dict]:
        """Get rollback history."""
        history = self._rollback_history[-limit:]
        return [
            {
                'action_id': r.action_id,
                'success': r.success,
                'strategy': r.strategy_used.value,
                'commands_executed': r.commands_executed,
                'errors': r.errors,
                'duration_ms': r.duration_ms
            }
            for r in reversed(history)
        ]
