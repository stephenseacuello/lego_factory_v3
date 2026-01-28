#!/usr/bin/env python3
"""
Inspection Action Server - Quality Inspection with AI Detection

Provides comprehensive quality inspection capabilities including:
- Dimensional measurement (CMM-style)
- Surface defect detection (AI-powered)
- GD&T validation
- ISO 9001/IATF 16949 compliant reporting

LEGO MCP Manufacturing System v7.0
"""

import json
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy

from std_msgs.msg import String
from std_srvs.srv import Trigger

try:
    from lego_mcp_msgs.action import PerformInspection
    from lego_mcp_msgs.msg import (
        InspectionResult, Measurement, DefectDetection
    )
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False
    print("Warning: lego_mcp_msgs not available, running in stub mode")


class InspectionType(Enum):
    """Types of inspection."""
    INCOMING = 0
    IN_PROCESS = 1
    FINAL = 2
    FIRST_ARTICLE = 3
    PERIODIC = 4
    REWORK = 5


class MeasurementType(Enum):
    """Measurement types."""
    DIMENSION = 0
    POSITION = 1
    FLATNESS = 2
    PERPENDICULARITY = 3
    PARALLELISM = 4
    CIRCULARITY = 5
    CYLINDRICITY = 6
    SURFACE_FINISH = 7


class DefectType(Enum):
    """Defect classification."""
    SCRATCH = 0
    CRACK = 1
    VOID = 2
    INCLUSION = 3
    WARPAGE = 4
    FLASH = 5
    SHORT_SHOT = 6
    SINK_MARK = 7
    DISCOLORATION = 8


@dataclass
class MeasurementResult:
    """Single measurement result."""
    characteristic: str
    measurement_type: MeasurementType
    nominal: float
    tolerance_upper: float
    tolerance_lower: float
    actual: float
    deviation: float = 0.0
    in_tolerance: bool = True
    unit: str = "mm"

    def __post_init__(self):
        self.deviation = self.actual - self.nominal
        self.in_tolerance = (
            self.tolerance_lower <= self.deviation <= self.tolerance_upper
        )


@dataclass
class DefectResult:
    """Single defect detection result."""
    defect_type: DefectType
    severity: int  # 1-5, 5 being most severe
    location_x: float
    location_y: float
    location_z: float
    size_mm: float
    confidence: float
    is_critical: bool = False


@dataclass
class InspectionSession:
    """Track inspection session state."""
    inspection_id: str
    part_id: str
    serial_number: str
    inspection_type: InspectionType
    inspection_plan_id: str

    # Progress
    current_check: str = ""
    check_index: int = 0
    total_checks: int = 0

    # Results
    measurements: List[MeasurementResult] = field(default_factory=list)
    defects: List[DefectResult] = field(default_factory=list)

    # Timing
    start_time: float = 0.0
    end_time: float = 0.0

    # State
    is_cancelled: bool = False
    waiting_for_part: bool = False
    manual_intervention_required: bool = False

    # AI
    use_ai: bool = True
    ai_confidence_threshold: float = 0.8


class InspectionActionServer(Node):
    """
    ROS2 Action Server for quality inspection operations.

    Features:
    - Multi-characteristic inspection plans
    - AI-powered defect detection
    - GD&T measurement support
    - Real-time progress feedback
    - ISO 9001/IATF 16949 compliance
    """

    def __init__(self):
        super().__init__('inspection_action_server')

        # Parameters
        self.declare_parameter('feedback_rate_hz', 5.0)
        self.declare_parameter('measurement_timeout_sec', 30.0)
        self.declare_parameter('ai_model_path', '')
        self.declare_parameter('camera_topic', '/vision/image_raw')
        self.declare_parameter('enable_ai_detection', True)

        self._feedback_rate = self.get_parameter('feedback_rate_hz').value
        self._measurement_timeout = self.get_parameter('measurement_timeout_sec').value
        self._enable_ai = self.get_parameter('enable_ai_detection').value

        # Active inspections
        self._inspections: Dict[str, InspectionSession] = {}
        self._lock = threading.RLock()

        # Inspection plans cache
        self._inspection_plans: Dict[str, Dict] = {}
        self._load_inspection_plans()

        # Callback groups
        self._action_group = ReentrantCallbackGroup()
        self._service_group = MutuallyExclusiveCallbackGroup()

        # QoS
        reliable_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            depth=10
        )

        # Action server
        if MSGS_AVAILABLE:
            self._inspection_server = ActionServer(
                self,
                PerformInspection,
                '/lego_mcp/perform_inspection',
                execute_callback=self._execute_inspection,
                goal_callback=self._goal_callback,
                cancel_callback=self._cancel_callback,
                callback_group=self._action_group
            )

        # Publishers
        self._result_pub = self.create_publisher(
            String,
            '/lego_mcp/inspection/results',
            reliable_qos
        )

        self._defect_pub = self.create_publisher(
            String,
            '/lego_mcp/inspection/defects',
            10
        )

        self._event_pub = self.create_publisher(
            String,
            '/lego_mcp/inspection/events',
            10
        )

        # Services
        self._get_plans_srv = self.create_service(
            Trigger,
            '/lego_mcp/inspection/get_plans',
            self._get_inspection_plans,
            callback_group=self._service_group
        )

        self._get_active_srv = self.create_service(
            Trigger,
            '/lego_mcp/inspection/get_active',
            self._get_active_inspections,
            callback_group=self._service_group
        )

        self.get_logger().info(
            f'Inspection Action Server started - AI enabled: {self._enable_ai}'
        )

    def _load_inspection_plans(self):
        """Load inspection plans from configuration."""
        # Standard LEGO brick inspection plan
        self._inspection_plans['LEGO_BRICK_STANDARD'] = {
            'plan_id': 'LEGO_BRICK_STANDARD',
            'name': 'Standard LEGO Brick Inspection',
            'characteristics': [
                {
                    'name': 'length',
                    'type': 'DIMENSION',
                    'nominal': 31.8,  # 4-stud brick
                    'tolerance_upper': 0.1,
                    'tolerance_lower': -0.1,
                    'unit': 'mm',
                },
                {
                    'name': 'width',
                    'type': 'DIMENSION',
                    'nominal': 15.8,  # 2-stud brick
                    'tolerance_upper': 0.1,
                    'tolerance_lower': -0.1,
                    'unit': 'mm',
                },
                {
                    'name': 'height',
                    'type': 'DIMENSION',
                    'nominal': 9.6,
                    'tolerance_upper': 0.05,
                    'tolerance_lower': -0.05,
                    'unit': 'mm',
                },
                {
                    'name': 'stud_diameter',
                    'type': 'DIMENSION',
                    'nominal': 4.8,
                    'tolerance_upper': 0.05,
                    'tolerance_lower': -0.05,
                    'unit': 'mm',
                },
                {
                    'name': 'stud_height',
                    'type': 'DIMENSION',
                    'nominal': 1.7,
                    'tolerance_upper': 0.1,
                    'tolerance_lower': -0.1,
                    'unit': 'mm',
                },
                {
                    'name': 'top_flatness',
                    'type': 'FLATNESS',
                    'nominal': 0.0,
                    'tolerance_upper': 0.05,
                    'tolerance_lower': -0.05,
                    'unit': 'mm',
                },
                {
                    'name': 'surface_quality',
                    'type': 'SURFACE_FINISH',
                    'nominal': 0.8,  # Ra in micrometers
                    'tolerance_upper': 0.4,
                    'tolerance_lower': -0.4,
                    'unit': 'um',
                },
            ],
            'visual_checks': [
                'surface_defects',
                'color_consistency',
                'flash_presence',
            ],
        }

        # First article inspection plan
        self._inspection_plans['LEGO_BRICK_FAI'] = {
            'plan_id': 'LEGO_BRICK_FAI',
            'name': 'First Article LEGO Brick Inspection',
            'characteristics': self._inspection_plans['LEGO_BRICK_STANDARD']['characteristics'] + [
                {
                    'name': 'clutch_force',
                    'type': 'DIMENSION',
                    'nominal': 2.5,  # Newtons
                    'tolerance_upper': 0.5,
                    'tolerance_lower': -0.5,
                    'unit': 'N',
                },
                {
                    'name': 'stud_perpendicularity',
                    'type': 'PERPENDICULARITY',
                    'nominal': 0.0,
                    'tolerance_upper': 0.02,
                    'tolerance_lower': -0.02,
                    'unit': 'mm',
                },
            ],
            'visual_checks': [
                'surface_defects',
                'color_consistency',
                'flash_presence',
                'internal_structure',
                'material_consistency',
            ],
        }

    def _goal_callback(self, goal_request) -> GoalResponse:
        """Accept or reject inspection goal."""
        part_id = goal_request.part_id
        plan_id = goal_request.inspection_plan_id

        self.get_logger().info(
            f'Received inspection request: {part_id} with plan {plan_id}'
        )

        # Validate inspection plan exists
        if plan_id and plan_id not in self._inspection_plans:
            self.get_logger().warning(f'Unknown inspection plan: {plan_id}')
            # Will use default plan

        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle: ServerGoalHandle) -> CancelResponse:
        """Handle cancellation request."""
        self.get_logger().info('Received cancel request for inspection')
        return CancelResponse.ACCEPT

    async def _execute_inspection(self, goal_handle: ServerGoalHandle):
        """Execute inspection with progress feedback."""
        request = goal_handle.request
        inspection_id = f"INS-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        # Get inspection plan
        plan_id = request.inspection_plan_id or 'LEGO_BRICK_STANDARD'
        plan = self._inspection_plans.get(plan_id, self._inspection_plans['LEGO_BRICK_STANDARD'])

        # Determine characteristics to inspect
        if request.characteristics:
            characteristics = [
                c for c in plan['characteristics']
                if c['name'] in request.characteristics
            ]
        else:
            characteristics = plan['characteristics']

        visual_checks = plan.get('visual_checks', [])

        # Create session
        session = InspectionSession(
            inspection_id=inspection_id,
            part_id=request.part_id,
            serial_number=request.serial_number,
            inspection_type=InspectionType(request.inspection_type),
            inspection_plan_id=plan_id,
            total_checks=len(characteristics) + len(visual_checks),
            start_time=time.time(),
            use_ai=request.use_ai_detection,
            ai_confidence_threshold=request.ai_confidence_threshold or 0.8,
        )

        with self._lock:
            self._inspections[inspection_id] = session

        self._publish_event('inspection_started', {
            'inspection_id': inspection_id,
            'part_id': request.part_id,
            'serial_number': request.serial_number,
            'plan_id': plan_id,
        })

        # Create result and feedback
        if MSGS_AVAILABLE:
            result = PerformInspection.Result()
            feedback = PerformInspection.Feedback()
        else:
            result = type('Result', (), {})()
            feedback = type('Feedback', (), {})()

        try:
            # Phase 1: Dimensional measurements
            for i, char in enumerate(characteristics):
                if session.is_cancelled:
                    break

                session.check_index = i
                session.current_check = char['name']

                # Update feedback
                self._update_feedback(feedback, session)
                goal_handle.publish_feedback(feedback)

                # Perform measurement
                measurement = await self._measure_characteristic(char, session)
                session.measurements.append(measurement)

                # Small delay between measurements
                await self._async_sleep(0.2)

            # Phase 2: Visual/AI inspection
            if session.use_ai and self._enable_ai:
                for i, check in enumerate(visual_checks):
                    if session.is_cancelled:
                        break

                    session.check_index = len(characteristics) + i
                    session.current_check = check

                    self._update_feedback(feedback, session)
                    goal_handle.publish_feedback(feedback)

                    # Perform AI detection
                    defects = await self._ai_detect_defects(check, session)
                    session.defects.extend(defects)

                    await self._async_sleep(0.3)

        except Exception as e:
            self.get_logger().error(f'Inspection error: {e}')
            result.success = False
            result.message = str(e)

        finally:
            session.end_time = time.time()

            with self._lock:
                del self._inspections[inspection_id]

        # Compute results
        measurements_passed = sum(1 for m in session.measurements if m.in_tolerance)
        measurements_total = len(session.measurements)
        defects_found = len(session.defects)
        critical_defects = sum(1 for d in session.defects if d.is_critical)

        # Overall verdict
        all_measurements_pass = measurements_passed == measurements_total
        no_critical_defects = critical_defects == 0

        if session.is_cancelled:
            goal_handle.canceled()
            result.success = False
            result.message = "Inspection cancelled"
        elif all_measurements_pass and no_critical_defects:
            goal_handle.succeed()
            result.success = True
            result.message = "Part passes all inspection criteria"
        else:
            goal_handle.succeed()  # Inspection completed, even if part failed
            result.success = True
            failures = []
            if not all_measurements_pass:
                failures.append(f"{measurements_total - measurements_passed} measurements out of tolerance")
            if not no_critical_defects:
                failures.append(f"{critical_defects} critical defects found")
            result.message = "Part FAILED: " + ", ".join(failures)

        # Populate result
        result.measurements_taken = measurements_total
        result.measurements_passed = measurements_passed
        result.defects_found = defects_found
        result.inspection_duration_sec = session.end_time - session.start_time

        if session.use_ai and session.defects:
            result.ai_confidence = sum(d.confidence for d in session.defects) / len(session.defects)
            result.ai_detections = len(session.defects)
        else:
            result.ai_confidence = 1.0
            result.ai_detections = 0

        # Create InspectionResult message if available
        if MSGS_AVAILABLE:
            result.result = self._create_inspection_result_msg(session)

        # Publish results
        self._publish_results(session)

        self._publish_event('inspection_completed', {
            'inspection_id': inspection_id,
            'part_id': request.part_id,
            'passed': all_measurements_pass and no_critical_defects,
            'measurements_passed': measurements_passed,
            'defects_found': defects_found,
            'duration_sec': result.inspection_duration_sec,
        })

        return result

    async def _measure_characteristic(
        self,
        characteristic: Dict,
        session: InspectionSession
    ) -> MeasurementResult:
        """Measure a single characteristic."""
        # Simulate measurement with slight variation
        import random

        nominal = characteristic['nominal']
        tol_upper = characteristic['tolerance_upper']
        tol_lower = characteristic['tolerance_lower']

        # Simulate actual measurement (mostly in tolerance)
        variation = random.gauss(0, abs(tol_upper) / 3)  # 3-sigma within tolerance
        actual = nominal + variation

        measurement = MeasurementResult(
            characteristic=characteristic['name'],
            measurement_type=MeasurementType[characteristic['type']],
            nominal=nominal,
            tolerance_upper=tol_upper,
            tolerance_lower=tol_lower,
            actual=actual,
            unit=characteristic.get('unit', 'mm'),
        )

        self.get_logger().debug(
            f"Measured {characteristic['name']}: {actual:.4f} "
            f"(nominal: {nominal}, {'PASS' if measurement.in_tolerance else 'FAIL'})"
        )

        return measurement

    async def _ai_detect_defects(
        self,
        check_type: str,
        session: InspectionSession
    ) -> List[DefectResult]:
        """Perform AI-based defect detection."""
        defects = []

        # Simulate AI detection (low defect rate)
        import random

        if random.random() < 0.1:  # 10% chance of finding a defect
            defect_type = random.choice(list(DefectType))
            severity = random.randint(1, 3)  # Usually minor defects

            defect = DefectResult(
                defect_type=defect_type,
                severity=severity,
                location_x=random.uniform(0, 31.8),
                location_y=random.uniform(0, 15.8),
                location_z=random.uniform(0, 9.6),
                size_mm=random.uniform(0.1, 0.5),
                confidence=random.uniform(session.ai_confidence_threshold, 1.0),
                is_critical=(severity >= 4),
            )
            defects.append(defect)

            self.get_logger().info(
                f"AI detected {defect_type.name} at ({defect.location_x:.2f}, "
                f"{defect.location_y:.2f}) with confidence {defect.confidence:.2f}"
            )

            # Publish defect
            self._publish_defect(session, defect)

        return defects

    def _update_feedback(self, feedback, session: InspectionSession):
        """Update feedback message."""
        feedback.current_check = session.current_check
        feedback.check_index = session.check_index
        feedback.total_checks = session.total_checks
        feedback.progress_percent = (
            session.check_index / session.total_checks * 100
            if session.total_checks > 0 else 0
        )

        feedback.measurements_complete = len(session.measurements)
        feedback.defects_so_far = len(session.defects)

        feedback.status_message = f"Inspecting: {session.current_check}"
        feedback.waiting_for_part = session.waiting_for_part
        feedback.manual_intervention_required = session.manual_intervention_required

    def _create_inspection_result_msg(self, session: InspectionSession):
        """Create InspectionResult message."""
        if not MSGS_AVAILABLE:
            return None

        result = InspectionResult()
        result.inspection_id = session.inspection_id
        result.part_id = session.part_id
        result.serial_number = session.serial_number
        result.inspection_type = session.inspection_type.value

        # Verdict
        all_pass = all(m.in_tolerance for m in session.measurements)
        critical_defects = any(d.is_critical for d in session.defects)
        result.passed = all_pass and not critical_defects
        result.verdict = "PASS" if result.passed else "FAIL"

        # Quality score (0-100)
        measurement_score = (
            sum(1 for m in session.measurements if m.in_tolerance) /
            len(session.measurements) * 100
            if session.measurements else 100
        )
        defect_penalty = len(session.defects) * 5  # 5 points per defect
        result.quality_score = max(0, measurement_score - defect_penalty)

        # Counts
        result.total_measurements = len(session.measurements)
        result.passed_measurements = sum(1 for m in session.measurements if m.in_tolerance)
        result.failed_measurements = len(session.measurements) - result.passed_measurements
        result.defects_found = len(session.defects)
        result.critical_defects = sum(1 for d in session.defects if d.is_critical)

        return result

    def _publish_results(self, session: InspectionSession):
        """Publish inspection results."""
        results_data = {
            'inspection_id': session.inspection_id,
            'part_id': session.part_id,
            'serial_number': session.serial_number,
            'inspection_type': session.inspection_type.name,
            'timestamp': time.time(),
            'measurements': [
                {
                    'characteristic': m.characteristic,
                    'type': m.measurement_type.name,
                    'nominal': m.nominal,
                    'actual': m.actual,
                    'deviation': m.deviation,
                    'in_tolerance': m.in_tolerance,
                    'unit': m.unit,
                }
                for m in session.measurements
            ],
            'defects': [
                {
                    'type': d.defect_type.name,
                    'severity': d.severity,
                    'location': [d.location_x, d.location_y, d.location_z],
                    'size_mm': d.size_mm,
                    'confidence': d.confidence,
                    'is_critical': d.is_critical,
                }
                for d in session.defects
            ],
            'passed': all(m.in_tolerance for m in session.measurements) and
                     not any(d.is_critical for d in session.defects),
        }

        msg = String()
        msg.data = json.dumps(results_data)
        self._result_pub.publish(msg)

    def _publish_defect(self, session: InspectionSession, defect: DefectResult):
        """Publish defect detection."""
        defect_data = {
            'inspection_id': session.inspection_id,
            'part_id': session.part_id,
            'serial_number': session.serial_number,
            'timestamp': time.time(),
            'defect': {
                'type': defect.defect_type.name,
                'severity': defect.severity,
                'location': [defect.location_x, defect.location_y, defect.location_z],
                'size_mm': defect.size_mm,
                'confidence': defect.confidence,
                'is_critical': defect.is_critical,
            },
        }

        msg = String()
        msg.data = json.dumps(defect_data)
        self._defect_pub.publish(msg)

    def _publish_event(self, event_type: str, data: dict):
        """Publish inspection event."""
        event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'data': data,
        }
        msg = String()
        msg.data = json.dumps(event)
        self._event_pub.publish(msg)

    def _get_inspection_plans(self, request, response):
        """Get available inspection plans."""
        plans = [
            {
                'plan_id': plan_id,
                'name': plan['name'],
                'characteristic_count': len(plan['characteristics']),
                'visual_check_count': len(plan.get('visual_checks', [])),
            }
            for plan_id, plan in self._inspection_plans.items()
        ]

        response.success = True
        response.message = json.dumps({
            'plan_count': len(plans),
            'plans': plans,
        })
        return response

    def _get_active_inspections(self, request, response):
        """Get active inspections."""
        with self._lock:
            active = [
                {
                    'inspection_id': session.inspection_id,
                    'part_id': session.part_id,
                    'progress': session.check_index / session.total_checks * 100
                              if session.total_checks > 0 else 0,
                    'current_check': session.current_check,
                }
                for session in self._inspections.values()
            ]

        response.success = True
        response.message = json.dumps({
            'active_count': len(active),
            'inspections': active,
        })
        return response

    async def _async_sleep(self, duration: float):
        """Async sleep helper."""
        import asyncio
        await asyncio.sleep(duration)


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = InspectionActionServer()

    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
