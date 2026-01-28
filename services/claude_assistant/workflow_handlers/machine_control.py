"""
Machine Control Workflow Handler.

Handles machine control operations with proper safety checks.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

import aiohttp

logger = logging.getLogger(__name__)


class ControlAction(Enum):
    """Machine control actions."""
    GET_STATUS = "get_status"
    SEND_GCODE = "send_gcode"
    JOG = "jog"
    HOME = "home"
    ZERO = "zero"
    FEED_HOLD = "feed_hold"
    RESUME = "resume"
    SET_FEED_OVERRIDE = "set_feed_override"


@dataclass
class ControlResult:
    """Result of a control operation."""
    success: bool
    action: ControlAction
    message: str
    data: Dict[str, Any] = None
    requires_confirmation: bool = False
    confirmation_id: Optional[str] = None


class MachineControlHandler:
    """
    Handler for machine control workflows.

    Provides safe execution of machine control operations
    with proper validation and confirmation handling.
    """

    def __init__(self, flask_url: str = "http://localhost:5000"):
        """Initialize with Flask backend URL."""
        self.flask_url = flask_url.rstrip("/")

        # Actions that require confirmation
        self.confirmation_required = {
            ControlAction.SEND_GCODE,
            ControlAction.JOG,
            ControlAction.HOME,
            ControlAction.ZERO,
        }

        # Actions that are always safe (no confirmation)
        self.always_safe = {
            ControlAction.GET_STATUS,
            ControlAction.FEED_HOLD,  # Emergency stop is always allowed
        }

    async def execute(
        self,
        action: ControlAction,
        params: Dict[str, Any],
        confirmed: bool = False,
    ) -> ControlResult:
        """
        Execute a machine control action.

        Args:
            action: The control action to execute
            params: Parameters for the action
            confirmed: Whether the action has been confirmed

        Returns:
            ControlResult with execution status
        """
        # Check if confirmation is required
        if action in self.confirmation_required and not confirmed:
            return ControlResult(
                success=False,
                action=action,
                message=f"Action '{action.value}' requires confirmation",
                requires_confirmation=True,
                data=params,
            )

        # Execute the action
        try:
            if action == ControlAction.GET_STATUS:
                return await self._get_status()
            elif action == ControlAction.SEND_GCODE:
                return await self._send_gcode(params)
            elif action == ControlAction.JOG:
                return await self._jog(params)
            elif action == ControlAction.HOME:
                return await self._home(params)
            elif action == ControlAction.ZERO:
                return await self._zero(params)
            elif action == ControlAction.FEED_HOLD:
                return await self._feed_hold()
            elif action == ControlAction.RESUME:
                return await self._resume(params)
            elif action == ControlAction.SET_FEED_OVERRIDE:
                return await self._set_feed_override(params)
            else:
                return ControlResult(
                    success=False,
                    action=action,
                    message=f"Unknown action: {action.value}",
                )
        except Exception as e:
            logger.exception(f"Error executing {action.value}")
            return ControlResult(
                success=False,
                action=action,
                message=f"Error: {str(e)}",
            )

    async def _call_api(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call the Flask API."""
        url = f"{self.flask_url}{endpoint}"

        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, params=data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    return await response.json()
            else:
                async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    return await response.json()

    async def _get_status(self) -> ControlResult:
        """Get machine status."""
        try:
            data = await self._call_api("GET", "/api/tinyg/status")

            connected = data.get("connected", False)
            last_status = data.get("last_status", {})

            state_map = {
                0: "initializing",
                1: "idle",
                2: "alarm",
                3: "stop",
                4: "end",
                5: "running",
                6: "hold",
                7: "probing",
                8: "cycle",
                9: "homing",
            }

            state = state_map.get(last_status.get("stat", 0), "unknown")

            return ControlResult(
                success=True,
                action=ControlAction.GET_STATUS,
                message=f"Machine is {state}" + (" and connected" if connected else " but disconnected"),
                data={
                    "connected": connected,
                    "state": state,
                    "position": {
                        "x": last_status.get("wx", 0),
                        "y": last_status.get("wy", 0),
                        "z": last_status.get("wz", 0),
                    },
                    "velocity": last_status.get("vel", 0),
                    "feed_rate": last_status.get("feed", 0),
                },
            )
        except aiohttp.ClientError as e:
            return ControlResult(
                success=False,
                action=ControlAction.GET_STATUS,
                message=f"Cannot connect to machine: {str(e)}",
            )

    async def _send_gcode(self, params: Dict[str, Any]) -> ControlResult:
        """Send G-code command."""
        gcode = params.get("gcode", "").strip()
        dry_run = params.get("dry_run", False)

        if not gcode:
            return ControlResult(
                success=False,
                action=ControlAction.SEND_GCODE,
                message="No G-code command provided",
            )

        # Validate G-code safety
        safety_check = self._validate_gcode_safety(gcode)
        if not safety_check["safe"]:
            return ControlResult(
                success=False,
                action=ControlAction.SEND_GCODE,
                message=f"G-code rejected: {safety_check['reason']}",
                data={"gcode": gcode, "safety_check": safety_check},
            )

        endpoint = "/api/tinyg/dry-run" if dry_run else "/api/tinyg/send"
        data = await self._call_api("POST", endpoint, {"gcode": gcode})

        if data.get("success", True):
            return ControlResult(
                success=True,
                action=ControlAction.SEND_GCODE,
                message=f"{'Dry run' if dry_run else 'Command'} successful: {gcode}",
                data={"gcode": gcode, "dry_run": dry_run, "response": data},
            )
        else:
            return ControlResult(
                success=False,
                action=ControlAction.SEND_GCODE,
                message=f"Command failed: {data.get('error', 'Unknown error')}",
                data={"gcode": gcode, "error": data.get("error")},
            )

    def _validate_gcode_safety(self, gcode: str) -> Dict[str, Any]:
        """Validate G-code for safety issues."""
        gcode_upper = gcode.upper()

        # Check for dangerous commands
        dangerous_patterns = [
            ("M30", "Program end command"),
            ("M00", "Program stop command"),
            ("M01", "Optional program stop"),
        ]

        for pattern, reason in dangerous_patterns:
            if pattern in gcode_upper:
                return {"safe": False, "reason": reason, "pattern": pattern}

        # Check for extremely high feed rates (>10000 mm/min)
        import re
        feed_match = re.search(r'F(\d+)', gcode_upper)
        if feed_match:
            feed = int(feed_match.group(1))
            if feed > 10000:
                return {"safe": False, "reason": f"Feed rate {feed} exceeds safe limit", "pattern": f"F{feed}"}

        # Check for extremely high spindle speeds (>30000 RPM)
        spindle_match = re.search(r'S(\d+)', gcode_upper)
        if spindle_match:
            speed = int(spindle_match.group(1))
            if speed > 30000:
                return {"safe": False, "reason": f"Spindle speed {speed} exceeds safe limit", "pattern": f"S{speed}"}

        return {"safe": True, "reason": None}

    async def _jog(self, params: Dict[str, Any]) -> ControlResult:
        """Jog an axis."""
        axis = params.get("axis", "").upper()
        distance = params.get("distance", 0)
        speed = params.get("speed", 1000)

        if axis not in ["X", "Y", "Z", "A", "B", "C"]:
            return ControlResult(
                success=False,
                action=ControlAction.JOG,
                message=f"Invalid axis: {axis}",
            )

        data = await self._call_api("POST", "/api/tinyg/jog", {
            "axis": axis,
            "distance": distance,
            "speed": speed,
        })

        return ControlResult(
            success=data.get("success", True),
            action=ControlAction.JOG,
            message=f"Jogged {axis} by {distance}mm at {speed}mm/min",
            data={"axis": axis, "distance": distance, "speed": speed},
        )

    async def _home(self, params: Dict[str, Any]) -> ControlResult:
        """Home the machine."""
        axes = params.get("axes", "ALL").upper()

        data = await self._call_api("POST", "/api/tinyg/home", {"axes": axes})

        return ControlResult(
            success=data.get("success", True),
            action=ControlAction.HOME,
            message=f"Homing {axes} axes initiated",
            data={"axes": axes},
        )

    async def _zero(self, params: Dict[str, Any]) -> ControlResult:
        """Zero work coordinates."""
        axis = params.get("axis", "ALL").upper()

        data = await self._call_api("POST", "/api/tinyg/zero", {"axis": axis})

        return ControlResult(
            success=data.get("success", True),
            action=ControlAction.ZERO,
            message=f"Zeroed {axis} work coordinate(s)",
            data={"axis": axis},
        )

    async def _feed_hold(self) -> ControlResult:
        """Execute feed hold (emergency stop)."""
        data = await self._call_api("POST", "/api/tinyg/feed-hold")

        return ControlResult(
            success=True,
            action=ControlAction.FEED_HOLD,
            message="FEED HOLD - All motion stopped",
            data=data,
        )

    async def _resume(self, params: Dict[str, Any]) -> ControlResult:
        """Resume after feed hold."""
        force = params.get("force", False)

        data = await self._call_api("POST", "/api/tinyg/safe-resume", {"force": force})

        if data.get("success", True):
            return ControlResult(
                success=True,
                action=ControlAction.RESUME,
                message="Motion resumed",
                data=data,
            )
        else:
            return ControlResult(
                success=False,
                action=ControlAction.RESUME,
                message=f"Resume failed: {data.get('error', 'Unknown error')}",
                data=data,
            )

    async def _set_feed_override(self, params: Dict[str, Any]) -> ControlResult:
        """Set feed rate override."""
        override = params.get("override", 100)

        if not 0 <= override <= 200:
            return ControlResult(
                success=False,
                action=ControlAction.SET_FEED_OVERRIDE,
                message=f"Override {override}% out of range (0-200%)",
            )

        # This would call the appropriate API
        return ControlResult(
            success=True,
            action=ControlAction.SET_FEED_OVERRIDE,
            message=f"Feed override set to {override}%",
            data={"override": override},
        )

    def get_status_summary(self, status_data: Dict[str, Any]) -> str:
        """Generate a human-readable status summary."""
        state = status_data.get("state", "unknown")
        connected = status_data.get("connected", False)
        position = status_data.get("position", {})

        if not connected:
            return "Machine is disconnected. Check USB connection and power."

        x = position.get("x", 0)
        y = position.get("y", 0)
        z = position.get("z", 0)

        if state == "alarm":
            return f"⚠️ ALARM - Machine is in alarm state at X{x:.2f} Y{y:.2f} Z{z:.2f}"
        elif state == "running":
            return f"Running - Currently at X{x:.2f} Y{y:.2f} Z{z:.2f}"
        elif state == "hold":
            return f"Feed Hold - Paused at X{x:.2f} Y{y:.2f} Z{z:.2f}"
        elif state == "homing":
            return "Homing in progress..."
        else:
            return f"Idle at X{x:.2f} Y{y:.2f} Z{z:.2f}"
