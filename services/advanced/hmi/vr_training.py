"""
VR Training Mode Service
========================

Immersive VR training simulations for manufacturing operations.

Features:
- Equipment operation training scenarios
- Safety procedure walkthroughs
- Quality inspection training
- Performance scoring and analytics
- Multi-user collaborative training

ISO 23247 Compliance:
- Digital twin-based training environment
- Real-world behavior simulation

Author: LegoMCP Team
Version: 2.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import threading
import logging
import json
import uuid
import time

logger = logging.getLogger(__name__)


class TrainingCategory(Enum):
    """Categories of VR training modules."""
    EQUIPMENT_OPERATION = "equipment_operation"
    SAFETY_PROCEDURES = "safety_procedures"
    QUALITY_INSPECTION = "quality_inspection"
    MAINTENANCE = "maintenance"
    EMERGENCY_RESPONSE = "emergency_response"
    ASSEMBLY = "assembly"
    TROUBLESHOOTING = "troubleshooting"
    ONBOARDING = "onboarding"


class DifficultyLevel(Enum):
    """Training difficulty levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class TrainingStatus(Enum):
    """Status of training session."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class InteractionType(Enum):
    """Types of VR interactions."""
    GRAB = "grab"
    BUTTON_PRESS = "button_press"
    LEVER_PULL = "lever_pull"
    DIAL_TURN = "dial_turn"
    TOOL_USE = "tool_use"
    GESTURE = "gesture"
    VOICE_COMMAND = "voice_command"
    GAZE = "gaze"
    PROXIMITY = "proximity"


class FeedbackType(Enum):
    """Types of training feedback."""
    VISUAL = "visual"           # Visual cues, highlights
    AUDIO = "audio"             # Voice guidance, sounds
    HAPTIC = "haptic"           # Controller vibration
    SPATIAL = "spatial"         # 3D arrows, guides
    TEXT = "text"               # On-screen text


@dataclass
class Vector3:
    """3D vector for spatial data."""
    x: float
    y: float
    z: float

    def to_dict(self) -> Dict[str, float]:
        return {'x': self.x, 'y': self.y, 'z': self.z}


@dataclass
class Transform:
    """3D transform for VR positioning."""
    position: Vector3
    rotation: Vector3  # Euler angles in degrees
    scale: Vector3 = field(default_factory=lambda: Vector3(1, 1, 1))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'position': self.position.to_dict(),
            'rotation': self.rotation.to_dict(),
            'scale': self.scale.to_dict()
        }


@dataclass
class TrainingStep:
    """Single step in a training scenario."""
    id: str
    order: int
    title: str
    description: str
    instructions: List[str]

    # Spatial info
    focus_point: Optional[Vector3] = None
    interaction_zone: Optional[Transform] = None

    # Required actions
    required_interactions: List[InteractionType] = field(default_factory=list)
    target_object_ids: List[str] = field(default_factory=list)

    # Completion criteria
    time_limit_seconds: Optional[float] = None
    min_accuracy: float = 0.0
    allow_hints: bool = True
    max_attempts: int = 3

    # Feedback
    success_feedback: str = "Well done!"
    failure_feedback: str = "Let's try again."
    hint_text: str = ""

    # Branching
    next_step_on_success: Optional[str] = None
    next_step_on_failure: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'order': self.order,
            'title': self.title,
            'description': self.description,
            'instructions': self.instructions,
            'focus_point': self.focus_point.to_dict() if self.focus_point else None,
            'interaction_zone': self.interaction_zone.to_dict() if self.interaction_zone else None,
            'required_interactions': [i.value for i in self.required_interactions],
            'target_object_ids': self.target_object_ids,
            'time_limit_seconds': self.time_limit_seconds,
            'min_accuracy': self.min_accuracy,
            'allow_hints': self.allow_hints,
            'max_attempts': self.max_attempts,
            'success_feedback': self.success_feedback,
            'hint_text': self.hint_text
        }


@dataclass
class TrainingScenario:
    """Complete training scenario definition."""
    id: str
    name: str
    description: str
    category: TrainingCategory
    difficulty: DifficultyLevel
    estimated_duration_minutes: int
    steps: List[TrainingStep]

    # Prerequisites
    required_scenarios: List[str] = field(default_factory=list)
    required_certifications: List[str] = field(default_factory=list)

    # Environment
    equipment_ids: List[str] = field(default_factory=list)
    scene_id: str = "default"
    environment_settings: Dict[str, Any] = field(default_factory=dict)

    # Scoring
    passing_score: float = 70.0
    max_score: float = 100.0

    # Metadata
    version: str = "1.0"
    author: str = "system"
    created_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category.value,
            'difficulty': self.difficulty.value,
            'estimated_duration_minutes': self.estimated_duration_minutes,
            'steps': [s.to_dict() for s in self.steps],
            'required_scenarios': self.required_scenarios,
            'equipment_ids': self.equipment_ids,
            'scene_id': self.scene_id,
            'passing_score': self.passing_score,
            'version': self.version,
            'tags': self.tags
        }


@dataclass
class StepAttempt:
    """Record of a single step attempt."""
    step_id: str
    attempt_number: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    accuracy: float = 0.0
    time_taken_seconds: float = 0.0
    hints_used: int = 0
    interactions: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_id': self.step_id,
            'attempt_number': self.attempt_number,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'success': self.success,
            'accuracy': self.accuracy,
            'time_taken_seconds': self.time_taken_seconds,
            'hints_used': self.hints_used,
            'interactions': self.interactions,
            'errors': self.errors
        }


@dataclass
class TrainingSession:
    """Active VR training session."""
    id: str
    scenario_id: str
    user_id: str
    status: TrainingStatus
    started_at: datetime
    current_step_index: int = 0
    step_attempts: List[StepAttempt] = field(default_factory=list)

    # Progress
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)

    # Scoring
    current_score: float = 0.0
    time_elapsed_seconds: float = 0.0

    # Session state
    paused_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    headset_type: str = "unknown"
    controller_type: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'user_id': self.user_id,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'current_step_index': self.current_step_index,
            'completed_steps': self.completed_steps,
            'failed_steps': self.failed_steps,
            'current_score': self.current_score,
            'time_elapsed_seconds': self.time_elapsed_seconds,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


@dataclass
class TrainingResult:
    """Final result of a training session."""
    session_id: str
    scenario_id: str
    user_id: str
    completed_at: datetime
    passed: bool
    final_score: float
    total_time_seconds: float
    steps_completed: int
    steps_failed: int
    total_attempts: int
    hints_used: int
    accuracy_breakdown: Dict[str, float] = field(default_factory=dict)
    skill_ratings: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    certification_earned: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'scenario_id': self.scenario_id,
            'user_id': self.user_id,
            'completed_at': self.completed_at.isoformat(),
            'passed': self.passed,
            'final_score': self.final_score,
            'total_time_seconds': self.total_time_seconds,
            'steps_completed': self.steps_completed,
            'steps_failed': self.steps_failed,
            'total_attempts': self.total_attempts,
            'hints_used': self.hints_used,
            'accuracy_breakdown': self.accuracy_breakdown,
            'skill_ratings': self.skill_ratings,
            'recommendations': self.recommendations,
            'certification_earned': self.certification_earned
        }


class ScoringEngine:
    """Calculates training scores and ratings."""

    def __init__(self):
        self._weights = {
            'accuracy': 0.4,
            'time': 0.2,
            'attempts': 0.2,
            'hints': 0.2
        }

    def calculate_step_score(
        self,
        step: TrainingStep,
        attempt: StepAttempt
    ) -> float:
        """Calculate score for a single step."""
        score = 0.0

        # Accuracy component
        if attempt.accuracy >= step.min_accuracy:
            accuracy_score = min(attempt.accuracy / 100.0, 1.0) * 100
        else:
            accuracy_score = 0

        # Time component
        if step.time_limit_seconds and step.time_limit_seconds > 0:
            time_ratio = attempt.time_taken_seconds / step.time_limit_seconds
            if time_ratio <= 1:
                time_score = 100 * (1 - time_ratio * 0.5)  # Faster is better
            else:
                time_score = max(0, 50 * (2 - time_ratio))  # Penalty for overtime
        else:
            time_score = 100  # No time limit = full points

        # Attempts component
        attempt_score = 100 * (1 - (attempt.attempt_number - 1) * 0.25)
        attempt_score = max(0, attempt_score)

        # Hints component
        hints_score = 100 * (1 - attempt.hints_used * 0.2)
        hints_score = max(0, hints_score)

        # Weighted total
        score = (
            accuracy_score * self._weights['accuracy'] +
            time_score * self._weights['time'] +
            attempt_score * self._weights['attempts'] +
            hints_score * self._weights['hints']
        )

        return score

    def calculate_session_score(
        self,
        scenario: TrainingScenario,
        session: TrainingSession
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate final session score and breakdown."""
        if not session.step_attempts:
            return 0.0, {}

        # Get successful attempts for each step
        step_scores: Dict[str, float] = {}
        for step in scenario.steps:
            step_attempts = [
                a for a in session.step_attempts
                if a.step_id == step.id and a.success
            ]
            if step_attempts:
                # Use best attempt score
                best_attempt = min(step_attempts, key=lambda a: a.attempt_number)
                step_scores[step.id] = self.calculate_step_score(step, best_attempt)
            else:
                step_scores[step.id] = 0.0

        # Overall score is average of step scores
        if step_scores:
            final_score = sum(step_scores.values()) / len(step_scores)
        else:
            final_score = 0.0

        return final_score, step_scores

    def generate_skill_ratings(
        self,
        session: TrainingSession,
        attempts: List[StepAttempt]
    ) -> Dict[str, float]:
        """Generate skill ratings based on performance."""
        ratings = {
            'precision': 0.0,
            'speed': 0.0,
            'consistency': 0.0,
            'problem_solving': 0.0,
            'safety_awareness': 0.0
        }

        if not attempts:
            return ratings

        successful = [a for a in attempts if a.success]
        if not successful:
            return ratings

        # Precision: based on accuracy
        accuracies = [a.accuracy for a in successful]
        ratings['precision'] = sum(accuracies) / len(accuracies)

        # Speed: based on time taken
        times = [a.time_taken_seconds for a in successful]
        avg_time = sum(times) / len(times)
        ratings['speed'] = max(0, 100 - avg_time)  # Lower time = higher rating

        # Consistency: based on variance in attempts
        if len(successful) > 1:
            variance = sum((a.accuracy - ratings['precision']) ** 2 for a in successful) / len(successful)
            ratings['consistency'] = max(0, 100 - variance)
        else:
            ratings['consistency'] = 50

        # Problem solving: based on retry success
        retry_successes = [a for a in successful if a.attempt_number > 1]
        if retry_successes:
            ratings['problem_solving'] = 100 * len(retry_successes) / len([a for a in attempts if a.attempt_number > 1]) if any(a.attempt_number > 1 for a in attempts) else 50
        else:
            ratings['problem_solving'] = 50

        # Safety awareness: based on errors
        total_errors = sum(len(a.errors) for a in attempts)
        ratings['safety_awareness'] = max(0, 100 - total_errors * 10)

        return ratings


class FeedbackGenerator:
    """Generates training feedback for VR display."""

    def generate_step_feedback(
        self,
        step: TrainingStep,
        attempt: StepAttempt,
        score: float
    ) -> Dict[str, Any]:
        """Generate feedback for completed step."""
        feedback = {
            'type': 'step_complete',
            'step_id': step.id,
            'success': attempt.success,
            'score': score,
            'messages': [],
            'visual_effects': [],
            'audio_cues': []
        }

        if attempt.success:
            feedback['messages'].append(step.success_feedback)
            feedback['visual_effects'].append('success_particle')
            feedback['audio_cues'].append('success_chime')

            if score >= 90:
                feedback['messages'].append("Excellent performance!")
                feedback['visual_effects'].append('gold_star')
            elif score >= 70:
                feedback['messages'].append("Good job!")
                feedback['visual_effects'].append('silver_star')

        else:
            feedback['messages'].append(step.failure_feedback)
            feedback['visual_effects'].append('retry_indicator')
            feedback['audio_cues'].append('retry_tone')

            if attempt.errors:
                feedback['messages'].append(f"Issues: {', '.join(attempt.errors[:3])}")

        return feedback

    def generate_hint(
        self,
        step: TrainingStep,
        hint_number: int
    ) -> Dict[str, Any]:
        """Generate progressive hint."""
        hints = [step.hint_text] if step.hint_text else []

        # Generate additional hints based on number
        if hint_number > len(hints):
            hints.append(f"Focus on the highlighted area for step: {step.title}")

        hint_text = hints[min(hint_number - 1, len(hints) - 1)] if hints else "No hints available"

        return {
            'type': 'hint',
            'step_id': step.id,
            'hint_number': hint_number,
            'text': hint_text,
            'show_guide': hint_number >= 2,
            'highlight_target': hint_number >= 3
        }

    def generate_progress_update(
        self,
        session: TrainingSession,
        scenario: TrainingScenario
    ) -> Dict[str, Any]:
        """Generate progress update for UI."""
        total_steps = len(scenario.steps)
        completed = len(session.completed_steps)

        return {
            'type': 'progress',
            'session_id': session.id,
            'completed_steps': completed,
            'total_steps': total_steps,
            'progress_percent': (completed / total_steps * 100) if total_steps > 0 else 0,
            'current_score': session.current_score,
            'time_elapsed': session.time_elapsed_seconds,
            'current_step': session.current_step_index + 1
        }


class VRTrainingService:
    """
    Main VR training service.

    Manages training scenarios, sessions, scoring, and feedback
    for immersive VR training experiences.
    """

    def __init__(self):
        self._scenarios: Dict[str, TrainingScenario] = {}
        self._sessions: Dict[str, TrainingSession] = {}
        self._results: Dict[str, TrainingResult] = {}
        self._user_progress: Dict[str, Dict[str, Any]] = {}

        self._scoring_engine = ScoringEngine()
        self._feedback_generator = FeedbackGenerator()

        self._lock = threading.RLock()

        # Register default scenarios
        self._register_default_scenarios()

        logger.info("VRTrainingService initialized")

    def _register_default_scenarios(self):
        """Register built-in training scenarios."""
        # 3D Printer Operation Training
        printer_scenario = TrainingScenario(
            id="printer_basic_operation",
            name="3D Printer Basic Operation",
            description="Learn the fundamentals of 3D printer operation including startup, calibration, and basic printing.",
            category=TrainingCategory.EQUIPMENT_OPERATION,
            difficulty=DifficultyLevel.BEGINNER,
            estimated_duration_minutes=15,
            steps=[
                TrainingStep(
                    id="power_on",
                    order=1,
                    title="Power On Printer",
                    description="Locate and press the power button",
                    instructions=[
                        "Find the power button on the front panel",
                        "Press and hold for 2 seconds",
                        "Wait for startup sequence"
                    ],
                    required_interactions=[InteractionType.BUTTON_PRESS],
                    target_object_ids=["printer_power_button"],
                    time_limit_seconds=30,
                    hint_text="The power button is on the lower right of the control panel"
                ),
                TrainingStep(
                    id="load_filament",
                    order=2,
                    title="Load Filament",
                    description="Insert filament into the extruder",
                    instructions=[
                        "Pick up the filament spool",
                        "Insert filament end into the extruder inlet",
                        "Push until you feel resistance"
                    ],
                    required_interactions=[InteractionType.GRAB, InteractionType.TOOL_USE],
                    target_object_ids=["filament_spool", "extruder_inlet"],
                    time_limit_seconds=60,
                    hint_text="Cut the filament at an angle for easier insertion"
                ),
                TrainingStep(
                    id="bed_leveling",
                    order=3,
                    title="Check Bed Leveling",
                    description="Verify the print bed is properly leveled",
                    instructions=[
                        "Navigate to bed leveling menu",
                        "Use the paper test at each corner",
                        "Adjust knobs until proper resistance"
                    ],
                    required_interactions=[InteractionType.BUTTON_PRESS, InteractionType.DIAL_TURN],
                    target_object_ids=["control_screen", "bed_knob_fl", "bed_knob_fr", "bed_knob_bl", "bed_knob_br"],
                    time_limit_seconds=120,
                    min_accuracy=80,
                    hint_text="The paper should have slight friction when pulled"
                ),
                TrainingStep(
                    id="start_print",
                    order=4,
                    title="Start Print Job",
                    description="Select and start a print file",
                    instructions=[
                        "Insert SD card or connect USB",
                        "Navigate to file browser",
                        "Select test print file",
                        "Confirm and start print"
                    ],
                    required_interactions=[InteractionType.GRAB, InteractionType.BUTTON_PRESS],
                    target_object_ids=["sd_card_slot", "control_screen"],
                    time_limit_seconds=60,
                    hint_text="Test prints are in the 'samples' folder"
                )
            ],
            equipment_ids=["printer_001"],
            passing_score=70.0,
            tags=["3d_printing", "beginner", "equipment"]
        )
        self._scenarios[printer_scenario.id] = printer_scenario

        # Safety Procedures Training
        safety_scenario = TrainingScenario(
            id="emergency_stop_procedure",
            name="Emergency Stop Procedures",
            description="Learn proper emergency stop procedures for manufacturing equipment.",
            category=TrainingCategory.SAFETY_PROCEDURES,
            difficulty=DifficultyLevel.BEGINNER,
            estimated_duration_minutes=10,
            steps=[
                TrainingStep(
                    id="identify_estop",
                    order=1,
                    title="Identify E-Stop Buttons",
                    description="Locate all emergency stop buttons in your area",
                    instructions=[
                        "Look around the virtual factory floor",
                        "Point at each red E-Stop button",
                        "Verify all locations are memorized"
                    ],
                    required_interactions=[InteractionType.GAZE],
                    target_object_ids=["estop_1", "estop_2", "estop_3"],
                    time_limit_seconds=60,
                    hint_text="E-Stop buttons are always red and mushroom-shaped"
                ),
                TrainingStep(
                    id="activate_estop",
                    order=2,
                    title="Activate Emergency Stop",
                    description="Practice activating the E-Stop",
                    instructions=[
                        "Approach the nearest E-Stop",
                        "Press the button firmly",
                        "Verify all equipment stops"
                    ],
                    required_interactions=[InteractionType.BUTTON_PRESS],
                    target_object_ids=["estop_1"],
                    time_limit_seconds=10,
                    hint_text="Press firmly - the button should lock in place"
                ),
                TrainingStep(
                    id="report_emergency",
                    order=3,
                    title="Report the Emergency",
                    description="Follow proper reporting procedures",
                    instructions=[
                        "Locate the intercom",
                        "Press talk button",
                        "State: location, nature of emergency, injuries"
                    ],
                    required_interactions=[InteractionType.BUTTON_PRESS, InteractionType.VOICE_COMMAND],
                    target_object_ids=["intercom_panel"],
                    time_limit_seconds=30,
                    hint_text="Remember: Location, Emergency type, Injuries"
                ),
                TrainingStep(
                    id="reset_estop",
                    order=4,
                    title="Reset E-Stop (When Safe)",
                    description="Learn to properly reset after emergency",
                    instructions=[
                        "Verify area is safe",
                        "Twist E-Stop button to release",
                        "Follow restart procedures"
                    ],
                    required_interactions=[InteractionType.DIAL_TURN],
                    target_object_ids=["estop_1"],
                    time_limit_seconds=30,
                    hint_text="Never reset until supervisor confirms it's safe"
                )
            ],
            equipment_ids=[],
            passing_score=90.0,  # Higher threshold for safety
            tags=["safety", "emergency", "required"]
        )
        self._scenarios[safety_scenario.id] = safety_scenario

        # Quality Inspection Training
        inspection_scenario = TrainingScenario(
            id="visual_inspection_basics",
            name="Visual Quality Inspection",
            description="Learn to identify common defects in 3D printed parts.",
            category=TrainingCategory.QUALITY_INSPECTION,
            difficulty=DifficultyLevel.INTERMEDIATE,
            estimated_duration_minutes=20,
            steps=[
                TrainingStep(
                    id="surface_inspection",
                    order=1,
                    title="Surface Quality Check",
                    description="Examine part surface for defects",
                    instructions=[
                        "Pick up the test part",
                        "Rotate to view all surfaces",
                        "Identify any surface defects",
                        "Mark defects with the pointer tool"
                    ],
                    required_interactions=[InteractionType.GRAB, InteractionType.TOOL_USE],
                    target_object_ids=["test_part_1", "inspection_pointer"],
                    time_limit_seconds=90,
                    min_accuracy=80,
                    hint_text="Look for layer lines, blobs, and stringing"
                ),
                TrainingStep(
                    id="dimensional_check",
                    order=2,
                    title="Dimensional Verification",
                    description="Measure critical dimensions",
                    instructions=[
                        "Select the digital caliper",
                        "Measure the marked dimension",
                        "Record the measurement",
                        "Compare to specification"
                    ],
                    required_interactions=[InteractionType.GRAB, InteractionType.TOOL_USE],
                    target_object_ids=["digital_caliper", "test_part_1"],
                    time_limit_seconds=120,
                    min_accuracy=90,
                    hint_text="Ensure caliper jaws are clean before measuring"
                ),
                TrainingStep(
                    id="defect_classification",
                    order=3,
                    title="Classify Defects",
                    description="Categorize identified defects",
                    instructions=[
                        "Review the defects found",
                        "Select appropriate category for each",
                        "Rate severity level",
                        "Submit inspection report"
                    ],
                    required_interactions=[InteractionType.BUTTON_PRESS],
                    target_object_ids=["classification_panel"],
                    time_limit_seconds=60,
                    hint_text="Use the defect reference chart if unsure"
                )
            ],
            required_scenarios=["printer_basic_operation"],
            equipment_ids=["inspection_station"],
            passing_score=75.0,
            tags=["quality", "inspection", "intermediate"]
        )
        self._scenarios[inspection_scenario.id] = inspection_scenario

    def register_scenario(self, scenario: TrainingScenario):
        """Register a new training scenario."""
        with self._lock:
            self._scenarios[scenario.id] = scenario
            logger.info(f"Registered training scenario: {scenario.name}")

    def get_scenario(self, scenario_id: str) -> Optional[TrainingScenario]:
        """Get scenario by ID."""
        with self._lock:
            return self._scenarios.get(scenario_id)

    def list_scenarios(
        self,
        category: Optional[TrainingCategory] = None,
        difficulty: Optional[DifficultyLevel] = None
    ) -> List[TrainingScenario]:
        """List available scenarios with optional filtering."""
        with self._lock:
            scenarios = list(self._scenarios.values())

            if category:
                scenarios = [s for s in scenarios if s.category == category]
            if difficulty:
                scenarios = [s for s in scenarios if s.difficulty == difficulty]

            return scenarios

    def start_session(
        self,
        scenario_id: str,
        user_id: str,
        headset_type: str = "unknown",
        controller_type: str = "unknown"
    ) -> Optional[TrainingSession]:
        """Start a new training session."""
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            logger.error(f"Scenario not found: {scenario_id}")
            return None

        # Check prerequisites
        if not self._check_prerequisites(user_id, scenario):
            logger.warning(f"User {user_id} missing prerequisites for {scenario_id}")

        session = TrainingSession(
            id=str(uuid.uuid4()),
            scenario_id=scenario_id,
            user_id=user_id,
            status=TrainingStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
            headset_type=headset_type,
            controller_type=controller_type
        )

        with self._lock:
            self._sessions[session.id] = session

        logger.info(f"Started training session {session.id} for user {user_id}")
        return session

    def _check_prerequisites(self, user_id: str, scenario: TrainingScenario) -> bool:
        """Check if user meets prerequisites."""
        if not scenario.required_scenarios:
            return True

        with self._lock:
            user_results = [
                r for r in self._results.values()
                if r.user_id == user_id and r.passed
            ]
            completed_ids = {r.scenario_id for r in user_results}

            return all(req in completed_ids for req in scenario.required_scenarios)

    def get_session(self, session_id: str) -> Optional[TrainingSession]:
        """Get session by ID."""
        with self._lock:
            return self._sessions.get(session_id)

    def get_current_step(self, session_id: str) -> Optional[TrainingStep]:
        """Get current step for session."""
        session = self.get_session(session_id)
        if not session:
            return None

        scenario = self.get_scenario(session.scenario_id)
        if not scenario:
            return None

        if session.current_step_index < len(scenario.steps):
            return scenario.steps[session.current_step_index]
        return None

    def record_interaction(
        self,
        session_id: str,
        interaction_type: InteractionType,
        target_object_id: str,
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Record user interaction during training."""
        session = self.get_session(session_id)
        if not session or session.status != TrainingStatus.IN_PROGRESS:
            return {'error': 'Invalid session'}

        step = self.get_current_step(session_id)
        if not step:
            return {'error': 'No current step'}

        interaction = {
            'type': interaction_type.value,
            'target': target_object_id,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data or {}
        }

        # Add to current attempt
        with self._lock:
            current_attempts = [
                a for a in session.step_attempts
                if a.step_id == step.id and a.completed_at is None
            ]

            if current_attempts:
                current_attempts[-1].interactions.append(interaction)
            else:
                # Start new attempt
                attempt = StepAttempt(
                    step_id=step.id,
                    attempt_number=len([a for a in session.step_attempts if a.step_id == step.id]) + 1,
                    started_at=datetime.utcnow(),
                    interactions=[interaction]
                )
                session.step_attempts.append(attempt)

        return {'recorded': True, 'interaction': interaction}

    def complete_step(
        self,
        session_id: str,
        success: bool,
        accuracy: float = 100.0,
        errors: List[str] = None
    ) -> Dict[str, Any]:
        """Mark current step as complete."""
        session = self.get_session(session_id)
        if not session:
            return {'error': 'Session not found'}

        scenario = self.get_scenario(session.scenario_id)
        step = self.get_current_step(session_id)
        if not step:
            return {'error': 'No current step'}

        with self._lock:
            # Find current attempt
            current_attempts = [
                a for a in session.step_attempts
                if a.step_id == step.id and a.completed_at is None
            ]

            if current_attempts:
                attempt = current_attempts[-1]
                attempt.completed_at = datetime.utcnow()
                attempt.success = success
                attempt.accuracy = accuracy
                attempt.time_taken_seconds = (
                    attempt.completed_at - attempt.started_at
                ).total_seconds()
                attempt.errors = errors or []

                # Calculate step score
                step_score = self._scoring_engine.calculate_step_score(step, attempt)

                if success:
                    session.completed_steps.append(step.id)
                    session.current_score = (
                        session.current_score * len(session.completed_steps) + step_score
                    ) / (len(session.completed_steps) + 1)

                    # Move to next step
                    session.current_step_index += 1

                    # Check if scenario complete
                    if session.current_step_index >= len(scenario.steps):
                        return self._complete_session(session, scenario)

                else:
                    if attempt.attempt_number >= step.max_attempts:
                        session.failed_steps.append(step.id)

                # Generate feedback
                feedback = self._feedback_generator.generate_step_feedback(
                    step, attempt, step_score
                )

                return {
                    'step_complete': True,
                    'success': success,
                    'score': step_score,
                    'feedback': feedback,
                    'next_step': session.current_step_index < len(scenario.steps)
                }

        return {'error': 'No active attempt'}

    def request_hint(self, session_id: str) -> Dict[str, Any]:
        """Request hint for current step."""
        session = self.get_session(session_id)
        step = self.get_current_step(session_id)
        if not session or not step:
            return {'error': 'Invalid session or step'}

        if not step.allow_hints:
            return {'error': 'Hints not allowed for this step'}

        with self._lock:
            current_attempts = [
                a for a in session.step_attempts
                if a.step_id == step.id and a.completed_at is None
            ]

            if current_attempts:
                attempt = current_attempts[-1]
                attempt.hints_used += 1
                hint = self._feedback_generator.generate_hint(step, attempt.hints_used)
                return hint

        return {'error': 'No active attempt'}

    def pause_session(self, session_id: str) -> bool:
        """Pause training session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.status == TrainingStatus.IN_PROGRESS:
                session.status = TrainingStatus.PAUSED
                session.paused_at = datetime.utcnow()
                logger.info(f"Paused session {session_id}")
                return True
        return False

    def resume_session(self, session_id: str) -> bool:
        """Resume paused session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.status == TrainingStatus.PAUSED:
                session.status = TrainingStatus.IN_PROGRESS
                if session.paused_at:
                    pause_duration = (datetime.utcnow() - session.paused_at).total_seconds()
                    # Don't count pause time
                session.paused_at = None
                logger.info(f"Resumed session {session_id}")
                return True
        return False

    def abandon_session(self, session_id: str) -> bool:
        """Abandon training session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.status in [TrainingStatus.IN_PROGRESS, TrainingStatus.PAUSED]:
                session.status = TrainingStatus.ABANDONED
                session.completed_at = datetime.utcnow()
                logger.info(f"Abandoned session {session_id}")
                return True
        return False

    def _complete_session(
        self,
        session: TrainingSession,
        scenario: TrainingScenario
    ) -> Dict[str, Any]:
        """Complete training session and generate results."""
        session.status = TrainingStatus.COMPLETED
        session.completed_at = datetime.utcnow()
        session.time_elapsed_seconds = (
            session.completed_at - session.started_at
        ).total_seconds()

        # Calculate final score
        final_score, score_breakdown = self._scoring_engine.calculate_session_score(
            scenario, session
        )

        # Generate skill ratings
        skill_ratings = self._scoring_engine.generate_skill_ratings(
            session, session.step_attempts
        )

        passed = final_score >= scenario.passing_score

        # Generate recommendations
        recommendations = self._generate_recommendations(
            scenario, session, score_breakdown, skill_ratings
        )

        # Check for certification
        certification = None
        if passed and scenario.category == TrainingCategory.SAFETY_PROCEDURES:
            certification = f"Safety Certified: {scenario.name}"

        result = TrainingResult(
            session_id=session.id,
            scenario_id=scenario.id,
            user_id=session.user_id,
            completed_at=session.completed_at,
            passed=passed,
            final_score=final_score,
            total_time_seconds=session.time_elapsed_seconds,
            steps_completed=len(session.completed_steps),
            steps_failed=len(session.failed_steps),
            total_attempts=len(session.step_attempts),
            hints_used=sum(a.hints_used for a in session.step_attempts),
            accuracy_breakdown=score_breakdown,
            skill_ratings=skill_ratings,
            recommendations=recommendations,
            certification_earned=certification
        )

        with self._lock:
            self._results[result.session_id] = result

            # Update user progress
            if session.user_id not in self._user_progress:
                self._user_progress[session.user_id] = {
                    'completed_scenarios': [],
                    'certifications': [],
                    'total_training_hours': 0
                }

            progress = self._user_progress[session.user_id]
            if passed and scenario.id not in progress['completed_scenarios']:
                progress['completed_scenarios'].append(scenario.id)
            if certification:
                progress['certifications'].append(certification)
            progress['total_training_hours'] += session.time_elapsed_seconds / 3600

        logger.info(
            f"Completed session {session.id}: "
            f"Score={final_score:.1f}, Passed={passed}"
        )

        return {
            'session_complete': True,
            'result': result.to_dict()
        }

    def _generate_recommendations(
        self,
        scenario: TrainingScenario,
        session: TrainingSession,
        score_breakdown: Dict[str, float],
        skill_ratings: Dict[str, float]
    ) -> List[str]:
        """Generate personalized recommendations."""
        recommendations = []

        # Find weak areas
        weak_steps = [
            step_id for step_id, score in score_breakdown.items()
            if score < 70
        ]

        if weak_steps:
            recommendations.append(
                f"Review steps: {', '.join(weak_steps[:3])}"
            )

        # Skill-based recommendations
        for skill, rating in skill_ratings.items():
            if rating < 60:
                if skill == 'precision':
                    recommendations.append("Practice fine motor control exercises")
                elif skill == 'speed':
                    recommendations.append("Focus on efficiency - practice common sequences")
                elif skill == 'safety_awareness':
                    recommendations.append("Re-take safety training module")

        # Suggest next training
        if session.current_score >= scenario.passing_score:
            next_difficulty = {
                DifficultyLevel.BEGINNER: DifficultyLevel.INTERMEDIATE,
                DifficultyLevel.INTERMEDIATE: DifficultyLevel.ADVANCED,
                DifficultyLevel.ADVANCED: DifficultyLevel.EXPERT
            }
            next_level = next_difficulty.get(scenario.difficulty)
            if next_level:
                recommendations.append(
                    f"Try {next_level.value} level scenarios in {scenario.category.value}"
                )

        return recommendations

    def get_result(self, session_id: str) -> Optional[TrainingResult]:
        """Get training result by session ID."""
        with self._lock:
            return self._results.get(session_id)

    def get_user_progress(self, user_id: str) -> Dict[str, Any]:
        """Get user's training progress."""
        with self._lock:
            progress = self._user_progress.get(user_id, {
                'completed_scenarios': [],
                'certifications': [],
                'total_training_hours': 0
            })

            # Add detailed results
            user_results = [
                r.to_dict() for r in self._results.values()
                if r.user_id == user_id
            ]

            return {
                **progress,
                'results': user_results,
                'available_scenarios': [
                    s.id for s in self._scenarios.values()
                    if self._check_prerequisites(user_id, s)
                ]
            }

    def get_leaderboard(
        self,
        scenario_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get leaderboard for scenario."""
        with self._lock:
            results = [
                r for r in self._results.values()
                if r.scenario_id == scenario_id and r.passed
            ]

            # Sort by score descending, then time ascending
            results.sort(key=lambda r: (-r.final_score, r.total_time_seconds))

            return [
                {
                    'rank': i + 1,
                    'user_id': r.user_id,
                    'score': r.final_score,
                    'time_seconds': r.total_time_seconds,
                    'completed_at': r.completed_at.isoformat()
                }
                for i, r in enumerate(results[:limit])
            ]

    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics."""
        with self._lock:
            return {
                'total_scenarios': len(self._scenarios),
                'active_sessions': len([
                    s for s in self._sessions.values()
                    if s.status == TrainingStatus.IN_PROGRESS
                ]),
                'completed_sessions': len(self._results),
                'total_users': len(self._user_progress),
                'pass_rate': (
                    len([r for r in self._results.values() if r.passed]) /
                    len(self._results) * 100 if self._results else 0
                )
            }


# Singleton instance
_vr_training_service: Optional[VRTrainingService] = None


def get_vr_training_service() -> VRTrainingService:
    """Get or create VR training service."""
    global _vr_training_service
    if _vr_training_service is None:
        _vr_training_service = VRTrainingService()
    return _vr_training_service
