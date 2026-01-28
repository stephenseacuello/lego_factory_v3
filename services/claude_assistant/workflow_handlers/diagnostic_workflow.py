"""
Diagnostic Workflow Handler.

Handles machine diagnostics, alarm resolution, and troubleshooting workflows.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import aiohttp

logger = logging.getLogger(__name__)


class DiagnosticType(Enum):
    """Types of diagnostic operations."""
    ALARM = "alarm"
    COMMUNICATION = "communication"
    MOTION = "motion"
    QUALITY = "quality"
    MAINTENANCE = "maintenance"
    GENERAL = "general"


class Severity(Enum):
    """Issue severity levels."""
    CRITICAL = "critical"  # Machine stopped, safety issue
    HIGH = "high"          # Production impacted
    MEDIUM = "medium"      # Degraded performance
    LOW = "low"            # Informational


@dataclass
class DiagnosticIssue:
    """A diagnosed issue."""
    id: str
    type: DiagnosticType
    severity: Severity
    title: str
    description: str
    possible_causes: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    related_data: Dict[str, Any] = field(default_factory=dict)
    diagnosed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DiagnosticResult:
    """Result of a diagnostic operation."""
    success: bool
    diagnostic_type: DiagnosticType
    issues: List[DiagnosticIssue]
    summary: str
    machine_status: Dict[str, Any] = None
    recommendations: List[str] = field(default_factory=list)


class DiagnosticWorkflowHandler:
    """
    Handler for diagnostic workflows.

    Provides:
    - Alarm diagnosis
    - Communication troubleshooting
    - Motion problem analysis
    - Quality issue investigation
    - Maintenance recommendations
    """

    def __init__(self, flask_url: str = "http://localhost:5000"):
        """Initialize with Flask backend URL."""
        self.flask_url = flask_url.rstrip("/")

        # Alarm database (would normally come from controller-specific data)
        self._load_alarm_database()

    def _load_alarm_database(self):
        """Load alarm code database."""
        # TinyG alarm codes
        self.tinyg_alarms = {
            1: {
                "name": "Limit Switch Hit",
                "severity": Severity.HIGH,
                "causes": [
                    "Machine moved past soft/hard limits",
                    "Limit switch triggered by debris",
                    "Wiring issue with limit switch",
                ],
                "actions": [
                    "Clear alarm with $clear or cycle start",
                    "Jog away from the limit switch",
                    "Check for physical obstructions",
                    "Re-home the machine",
                ],
            },
            2: {
                "name": "Soft Limit Exceeded",
                "severity": Severity.MEDIUM,
                "causes": [
                    "G-code contains coordinates outside work envelope",
                    "Work offset not set correctly",
                    "Soft limits configured incorrectly",
                ],
                "actions": [
                    "Review G-code for out-of-bounds coordinates",
                    "Verify work coordinate system (G54-G59)",
                    "Check soft limit configuration",
                ],
            },
            3: {
                "name": "Motor Fault",
                "severity": Severity.CRITICAL,
                "causes": [
                    "Motor overheating",
                    "Driver overload",
                    "Mechanical binding",
                    "Wiring issue",
                ],
                "actions": [
                    "Check motor temperature",
                    "Verify motor connections",
                    "Check for mechanical obstructions",
                    "Reduce feed rate or acceleration",
                    "Power cycle controller",
                ],
            },
            4: {
                "name": "Probe Fail",
                "severity": Severity.MEDIUM,
                "causes": [
                    "Probe not connected",
                    "Probe didn't trigger during cycle",
                    "Incorrect probe configuration",
                ],
                "actions": [
                    "Verify probe is connected",
                    "Check probe wiring",
                    "Test probe manually",
                    "Adjust probe settings",
                ],
            },
        }

    async def diagnose_alarm(
        self,
        alarm_code: int,
        controller_type: str = "tinyg",
        include_context: bool = True,
    ) -> DiagnosticResult:
        """
        Diagnose a machine alarm.

        Args:
            alarm_code: The alarm code to diagnose
            controller_type: Controller type (tinyg, grbl)
            include_context: Include current machine context

        Returns:
            DiagnosticResult with diagnosis
        """
        # Get alarm info
        if controller_type == "tinyg":
            alarm_info = self.tinyg_alarms.get(alarm_code)
        else:
            alarm_info = None  # Would have GRBL database

        # Get machine context
        machine_status = None
        if include_context:
            machine_status = await self._get_machine_status()

        if alarm_info:
            issue = DiagnosticIssue(
                id=f"alarm_{alarm_code}",
                type=DiagnosticType.ALARM,
                severity=alarm_info["severity"],
                title=f"Alarm {alarm_code}: {alarm_info['name']}",
                description=f"Machine has triggered alarm code {alarm_code}",
                possible_causes=alarm_info["causes"],
                recommended_actions=alarm_info["actions"],
                related_data={"alarm_code": alarm_code, "controller": controller_type},
            )

            return DiagnosticResult(
                success=True,
                diagnostic_type=DiagnosticType.ALARM,
                issues=[issue],
                summary=f"Diagnosed alarm {alarm_code}: {alarm_info['name']}",
                machine_status=machine_status,
                recommendations=alarm_info["actions"][:3],
            )
        else:
            return DiagnosticResult(
                success=True,
                diagnostic_type=DiagnosticType.ALARM,
                issues=[DiagnosticIssue(
                    id=f"alarm_{alarm_code}",
                    type=DiagnosticType.ALARM,
                    severity=Severity.MEDIUM,
                    title=f"Unknown Alarm {alarm_code}",
                    description=f"Alarm code {alarm_code} is not in the database",
                    possible_causes=["Unknown - check controller documentation"],
                    recommended_actions=[
                        "Check controller documentation for this alarm code",
                        "Try clearing the alarm",
                        "Power cycle if alarm persists",
                    ],
                )],
                summary=f"Unknown alarm code {alarm_code}",
                machine_status=machine_status,
            )

    async def troubleshoot_communication(self) -> DiagnosticResult:
        """Troubleshoot communication issues with the machine."""
        issues = []

        # Try to connect
        try:
            machine_status = await self._get_machine_status()
            connected = machine_status.get("connected", False)
        except Exception as e:
            connected = False
            issues.append(DiagnosticIssue(
                id="comm_connection_error",
                type=DiagnosticType.COMMUNICATION,
                severity=Severity.CRITICAL,
                title="Connection Error",
                description=f"Cannot connect to Flask backend: {str(e)}",
                possible_causes=[
                    "Flask server not running",
                    "Network connectivity issue",
                    "Incorrect URL configuration",
                ],
                recommended_actions=[
                    "Verify Flask server is running",
                    "Check network connectivity",
                    "Verify FLASK_URL configuration",
                ],
            ))
            machine_status = None

        if not connected and not issues:
            issues.append(DiagnosticIssue(
                id="comm_not_connected",
                type=DiagnosticType.COMMUNICATION,
                severity=Severity.HIGH,
                title="Machine Not Connected",
                description="The CNC controller is not connected",
                possible_causes=[
                    "USB cable disconnected",
                    "Wrong serial port configured",
                    "Controller not powered on",
                    "Another application using the port",
                ],
                recommended_actions=[
                    "Check USB cable connection",
                    "Verify serial port configuration",
                    "Ensure controller is powered on",
                    "Close other applications that may use the port",
                ],
            ))

        if issues:
            return DiagnosticResult(
                success=True,
                diagnostic_type=DiagnosticType.COMMUNICATION,
                issues=issues,
                summary=f"Found {len(issues)} communication issue(s)",
                machine_status=machine_status,
            )
        else:
            return DiagnosticResult(
                success=True,
                diagnostic_type=DiagnosticType.COMMUNICATION,
                issues=[],
                summary="Communication is working normally",
                machine_status=machine_status,
            )

    async def analyze_motion_issue(
        self,
        issue_type: str,
        axis: str = "all",
        description: str = "",
    ) -> DiagnosticResult:
        """
        Analyze motion-related issues.

        Args:
            issue_type: Type of motion issue (position_error, missed_steps, etc.)
            axis: Affected axis or "all"
            description: Additional description from user
        """
        motion_diagnostics = {
            "position_error": {
                "title": "Position Error",
                "severity": Severity.HIGH,
                "causes": [
                    "Steps/mm calibration incorrect",
                    "Mechanical backlash",
                    "Lost steps due to high acceleration",
                    "Motor current too low",
                ],
                "actions": [
                    "Run calibration test pattern",
                    "Measure actual vs commanded position",
                    "Reduce acceleration settings",
                    "Increase motor current",
                ],
            },
            "missed_steps": {
                "title": "Missed Steps",
                "severity": Severity.HIGH,
                "causes": [
                    "Acceleration too high",
                    "Motor current too low",
                    "Mechanical binding",
                    "Electrical noise",
                ],
                "actions": [
                    "Reduce max velocity and acceleration",
                    "Increase motor current",
                    "Lubricate linear guides",
                    "Check for binding",
                ],
            },
            "vibration": {
                "title": "Excessive Vibration",
                "severity": Severity.MEDIUM,
                "causes": [
                    "Resonance at certain speeds",
                    "Unbalanced tooling",
                    "Loose components",
                    "Worn bearings",
                ],
                "actions": [
                    "Avoid resonant feed rates",
                    "Check tool balance",
                    "Tighten all fasteners",
                    "Inspect bearings",
                ],
            },
            "stalling": {
                "title": "Motor Stalling",
                "severity": Severity.CRITICAL,
                "causes": [
                    "Motor current too low",
                    "Mechanical obstruction",
                    "Overloaded axis",
                    "Driver overheating",
                ],
                "actions": [
                    "Increase motor current",
                    "Check for obstructions",
                    "Reduce cutting load",
                    "Add driver cooling",
                ],
            },
        }

        info = motion_diagnostics.get(issue_type, {
            "title": "Motion Issue",
            "severity": Severity.MEDIUM,
            "causes": ["Unknown cause"],
            "actions": ["Describe the issue in more detail"],
        })

        issue = DiagnosticIssue(
            id=f"motion_{issue_type}_{axis}",
            type=DiagnosticType.MOTION,
            severity=info["severity"],
            title=f"{info['title']} on {axis.upper()} axis",
            description=description or f"Motion issue detected on {axis} axis",
            possible_causes=info["causes"],
            recommended_actions=info["actions"],
            related_data={"issue_type": issue_type, "axis": axis},
        )

        machine_status = await self._get_machine_status()

        return DiagnosticResult(
            success=True,
            diagnostic_type=DiagnosticType.MOTION,
            issues=[issue],
            summary=f"Analyzed {info['title'].lower()} on {axis} axis",
            machine_status=machine_status,
            recommendations=info["actions"][:3],
        )

    async def get_health_assessment(self) -> DiagnosticResult:
        """Get overall machine health assessment."""
        issues = []
        score = 100

        # Get machine status
        machine_status = await self._get_machine_status()

        if not machine_status:
            return DiagnosticResult(
                success=False,
                diagnostic_type=DiagnosticType.GENERAL,
                issues=[DiagnosticIssue(
                    id="health_no_connection",
                    type=DiagnosticType.COMMUNICATION,
                    severity=Severity.CRITICAL,
                    title="Cannot Assess Health",
                    description="Unable to connect to machine for health assessment",
                    recommended_actions=["Check machine connection"],
                )],
                summary="Health assessment failed - no connection",
            )

        # Check connection
        if not machine_status.get("connected", False):
            score -= 50
            issues.append(DiagnosticIssue(
                id="health_disconnected",
                type=DiagnosticType.COMMUNICATION,
                severity=Severity.HIGH,
                title="Machine Disconnected",
                description="Machine is not connected",
                recommended_actions=["Check USB connection", "Verify port settings"],
            ))

        # Check state
        state = machine_status.get("state", "unknown")
        if state == "alarm":
            score -= 30
            issues.append(DiagnosticIssue(
                id="health_alarm",
                type=DiagnosticType.ALARM,
                severity=Severity.HIGH,
                title="Machine in Alarm",
                description="Machine is currently in alarm state",
                recommended_actions=["Diagnose and clear alarm"],
            ))

        # Get sensor data for additional health indicators
        try:
            sensor_data = await self._get_sensor_data()
            if sensor_data:
                # Check spindle temperature
                spindle_temp = sensor_data.get("spindle_temp", 0)
                if spindle_temp > 60:
                    score -= 20
                    issues.append(DiagnosticIssue(
                        id="health_spindle_temp",
                        type=DiagnosticType.MAINTENANCE,
                        severity=Severity.MEDIUM,
                        title="Elevated Spindle Temperature",
                        description=f"Spindle temperature is {spindle_temp}°C",
                        recommended_actions=["Allow spindle to cool", "Check cooling system"],
                    ))

                # Check vibration
                vibration = sensor_data.get("vibration", 0)
                if vibration > 5:
                    score -= 15
                    issues.append(DiagnosticIssue(
                        id="health_vibration",
                        type=DiagnosticType.MOTION,
                        severity=Severity.MEDIUM,
                        title="High Vibration Detected",
                        description=f"Vibration level: {vibration}",
                        recommended_actions=["Check tool balance", "Inspect spindle bearings"],
                    ))
        except Exception:
            pass  # Sensor data not available

        # Determine health level
        if score >= 80:
            health_level = "Excellent"
        elif score >= 60:
            health_level = "Good"
        elif score >= 40:
            health_level = "Fair"
        else:
            health_level = "Poor"

        recommendations = []
        for issue in sorted(issues, key=lambda i: i.severity.value):
            if issue.recommended_actions:
                recommendations.append(issue.recommended_actions[0])

        return DiagnosticResult(
            success=True,
            diagnostic_type=DiagnosticType.GENERAL,
            issues=issues,
            summary=f"Machine health: {health_level} ({score}/100)",
            machine_status=machine_status,
            recommendations=recommendations[:5],
        )

    async def _get_machine_status(self) -> Optional[Dict[str, Any]]:
        """Get current machine status."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.flask_url}/api/tinyg/status",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        last_status = data.get("last_status", {})

                        state_map = {0: "init", 1: "idle", 2: "alarm", 3: "stop",
                                     4: "end", 5: "running", 6: "hold", 9: "homing"}

                        return {
                            "connected": data.get("connected", False),
                            "state": state_map.get(last_status.get("stat", 0), "unknown"),
                            "position": {
                                "x": last_status.get("wx", 0),
                                "y": last_status.get("wy", 0),
                                "z": last_status.get("wz", 0),
                            },
                        }
        except Exception:
            pass
        return None

    async def _get_sensor_data(self) -> Optional[Dict[str, Any]]:
        """Get current sensor data."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.flask_url}/api/sensor/latest",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("data", {})
        except Exception:
            pass
        return None

    def format_diagnostic_result(self, result: DiagnosticResult) -> str:
        """Format diagnostic result for display."""
        lines = [f"## {result.summary}", ""]

        severity_emoji = {
            Severity.CRITICAL: "🔴",
            Severity.HIGH: "🟠",
            Severity.MEDIUM: "🟡",
            Severity.LOW: "🟢",
        }

        if result.issues:
            lines.append("### Issues Found")
            for issue in result.issues:
                emoji = severity_emoji.get(issue.severity, "❓")
                lines.append(f"\n#### {emoji} {issue.title}")
                lines.append(f"{issue.description}")

                if issue.possible_causes:
                    lines.append("\n**Possible Causes:**")
                    for cause in issue.possible_causes:
                        lines.append(f"- {cause}")

                if issue.recommended_actions:
                    lines.append("\n**Recommended Actions:**")
                    for i, action in enumerate(issue.recommended_actions, 1):
                        lines.append(f"{i}. {action}")
        else:
            lines.append("✅ No issues detected.")

        if result.recommendations:
            lines.extend(["", "### Next Steps"])
            for rec in result.recommendations:
                lines.append(f"- {rec}")

        return "\n".join(lines)
