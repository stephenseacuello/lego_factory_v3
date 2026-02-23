"""
AR/VR Work Instructions Service.

Implements augmented and virtual reality-based work instructions
for manufacturing operations, supporting:
- Step-by-step visual guidance overlays
- 3D model annotation and highlighting
- Real-time sensor data visualization
- Remote expert assistance
- Training simulation environments
- Hands-free operation with voice/gesture control
- Integration with digital twin

Compliant with:
- ISO 10209 (Technical Product Documentation)
- ANSI Z535 (Safety Signs and Colors)
- IEC 62366 (Usability for Medical Devices)
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging
import json

logger = logging.getLogger(__name__)


class InstructionType(Enum):
    """Types of work instructions."""
    ASSEMBLY = "assembly"
    MAINTENANCE = "maintenance"
    INSPECTION = "inspection"
    TROUBLESHOOTING = "troubleshooting"
    SAFETY = "safety"
    TRAINING = "training"
    CHANGEOVER = "changeover"


class MediaType(Enum):
    """Types of AR/VR media content."""
    TEXT_OVERLAY = "text_overlay"
    IMAGE = "image"
    VIDEO = "video"
    MODEL_3D = "model_3d"
    ANIMATION = "animation"
    AUDIO = "audio"
    HOLOGRAM = "hologram"
    POINT_CLOUD = "point_cloud"


class InteractionMode(Enum):
    """User interaction modes."""
    TOUCH = "touch"
    VOICE = "voice"
    GESTURE = "gesture"
    GAZE = "gaze"
    CONTROLLER = "controller"
    HYBRID = "hybrid"


class HighlightType(Enum):
    """Types of AR highlights."""
    OUTLINE = "outline"
    FILL = "fill"
    PULSE = "pulse"
    ARROW = "arrow"
    CIRCLE = "circle"
    BOUNDING_BOX = "bounding_box"
    HALO = "halo"


class SafetyLevel(Enum):
    """Safety indication levels (ANSI Z535)."""
    NOTICE = "notice"  # Blue
    CAUTION = "caution"  # Yellow
    WARNING = "warning"  # Orange
    DANGER = "danger"  # Red


class SessionState(Enum):
    """AR session states."""
    INITIALIZING = "initializing"
    READY = "ready"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class Position3D:
    """3D position in AR space."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Rotation3D:
    """3D rotation (Euler angles in degrees)."""
    pitch: float = 0.0  # X-axis rotation
    yaw: float = 0.0  # Y-axis rotation
    roll: float = 0.0  # Z-axis rotation


@dataclass
class Transform3D:
    """3D transform for AR elements."""
    position: Position3D = field(default_factory=Position3D)
    rotation: Rotation3D = field(default_factory=Rotation3D)
    scale: float = 1.0


@dataclass
class ARHighlight:
    """AR highlight/annotation element."""
    highlight_id: str
    target_component: str  # Component ID to highlight
    highlight_type: HighlightType
    color: str = "#00FF00"  # Hex color
    opacity: float = 0.8
    animation: Optional[str] = None  # pulse, blink, rotate
    duration_seconds: Optional[float] = None
    transform_offset: Transform3D = field(default_factory=Transform3D)


@dataclass
class AROverlay:
    """AR overlay element (text, image, etc.)."""
    overlay_id: str
    media_type: MediaType
    content: str  # Text content or URL/path
    transform: Transform3D
    anchor_target: Optional[str] = None  # Component ID to anchor to
    world_locked: bool = False  # Fixed in world vs. follows view
    interactive: bool = False
    voice_trigger: Optional[str] = None  # Voice command to activate
    auto_hide_seconds: Optional[float] = None


@dataclass
class SafetyIndicator:
    """Safety warning indicator for AR display."""
    indicator_id: str
    safety_level: SafetyLevel
    message: str
    icon: str = ""
    position: Transform3D = field(default_factory=Transform3D)
    requires_acknowledgment: bool = False
    audio_alert: bool = True
    haptic_feedback: bool = True
    blocking: bool = False  # Prevents proceeding if not acknowledged


@dataclass
class SensorVisualization:
    """Real-time sensor data visualization."""
    viz_id: str
    sensor_id: str
    sensor_name: str
    display_type: str = "gauge"  # gauge, graph, value, bar, heatmap
    unit: str = ""
    min_value: float = 0.0
    max_value: float = 100.0
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    position: Transform3D = field(default_factory=Transform3D)
    update_interval_ms: int = 100


@dataclass
class InstructionStep:
    """Single step in work instruction sequence."""
    step_id: str
    step_number: int
    title: str
    description: str
    estimated_duration_seconds: int
    highlights: List[ARHighlight] = field(default_factory=list)
    overlays: List[AROverlay] = field(default_factory=list)
    safety_indicators: List[SafetyIndicator] = field(default_factory=list)
    sensor_visualizations: List[SensorVisualization] = field(default_factory=list)
    tools_required: List[str] = field(default_factory=list)
    materials_required: List[str] = field(default_factory=list)
    verification_required: bool = False
    verification_type: Optional[str] = None  # photo, signature, scan
    voice_instruction: Optional[str] = None
    video_url: Optional[str] = None
    model_animation: Optional[str] = None
    prerequisites: List[str] = field(default_factory=list)  # Step IDs
    next_step_conditions: Dict = field(default_factory=dict)


@dataclass
class WorkInstruction:
    """Complete work instruction package."""
    instruction_id: str
    instruction_code: str
    title: str
    description: str
    instruction_type: InstructionType
    version: str
    steps: List[InstructionStep]
    model_id: Optional[str] = None  # 3D model reference
    equipment_id: Optional[str] = None
    product_id: Optional[str] = None
    total_estimated_duration_seconds: int = 0
    difficulty_level: str = "medium"  # easy, medium, hard, expert
    required_certifications: List[str] = field(default_factory=list)
    interaction_mode: InteractionMode = InteractionMode.HYBRID
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    status: str = "draft"  # draft, approved, active, archived


@dataclass
class ARSession:
    """Active AR session for a user."""
    session_id: str
    user_id: str
    user_name: str
    instruction_id: str
    device_id: str
    device_type: str  # hololens, magicleap, tablet, phone
    state: SessionState
    current_step: int
    started_at: datetime
    step_times: Dict[str, float] = field(default_factory=dict)  # step_id -> seconds
    verifications: Dict[str, Dict] = field(default_factory=dict)
    paused_duration_seconds: float = 0.0
    remote_experts: List[str] = field(default_factory=list)
    annotations: List[Dict] = field(default_factory=list)  # User annotations
    issues_reported: List[Dict] = field(default_factory=list)
    completed_at: Optional[datetime] = None


@dataclass
class RemoteExpertSession:
    """Remote expert assistance session."""
    expert_session_id: str
    ar_session_id: str
    expert_id: str
    expert_name: str
    connected_at: datetime
    annotations: List[Dict] = field(default_factory=list)
    voice_active: bool = True
    video_stream_active: bool = True
    pointer_position: Optional[Position3D] = None
    drawing_active: bool = False
    disconnected_at: Optional[datetime] = None


@dataclass
class TrainingSimulation:
    """VR training simulation scenario."""
    simulation_id: str
    simulation_name: str
    description: str
    instruction_id: str
    difficulty_levels: List[str] = field(default_factory=list)
    scenario_variants: List[Dict] = field(default_factory=list)
    error_injection: List[Dict] = field(default_factory=list)  # Simulated problems
    scoring_criteria: Dict = field(default_factory=dict)
    time_limit_seconds: Optional[int] = None
    required_score_percent: float = 80.0
    attempts_allowed: int = 3


@dataclass
class TrainingResult:
    """Result of a training simulation."""
    result_id: str
    simulation_id: str
    user_id: str
    attempt_number: int
    started_at: datetime
    completed_at: Optional[datetime]
    score_percent: float = 0.0
    steps_completed: int = 0
    errors_made: List[Dict] = field(default_factory=list)
    time_elapsed_seconds: float = 0.0
    passed: bool = False


class ARInstructionsService:
    """
    AR/VR Work Instructions Service.

    Provides immersive visual work instructions with real-time
    guidance, sensor integration, and remote expert support.
    """

    def __init__(self):
        self.instructions: Dict[str, WorkInstruction] = {}
        self.sessions: Dict[str, ARSession] = {}
        self.expert_sessions: Dict[str, RemoteExpertSession] = {}
        self.simulations: Dict[str, TrainingSimulation] = {}
        self.training_results: Dict[str, TrainingResult] = {}
        self._sensor_callbacks: Dict[str, List] = {}
        self._device_registry: Dict[str, Dict] = {}

    def _generate_id(self, prefix: str = "AR") -> str:
        """Generate unique identifier."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique = uuid.uuid4().hex[:8].upper()
        return f"{prefix}-{timestamp}-{unique}"

    # =========================================================================
    # Work Instruction Management
    # =========================================================================

    async def create_instruction(
        self,
        instruction_code: str,
        title: str,
        description: str,
        instruction_type: InstructionType,
        steps: List[Dict],
        created_by: str,
        model_id: str = None,
        equipment_id: str = None,
        interaction_mode: InteractionMode = InteractionMode.HYBRID
    ) -> WorkInstruction:
        """
        Create a new AR work instruction.

        Args:
            instruction_code: Unique code for the instruction
            title: Instruction title
            description: Detailed description
            instruction_type: Type of instruction
            steps: List of step definitions
            created_by: Author user ID
            model_id: Associated 3D model
            equipment_id: Target equipment
            interaction_mode: User interaction mode

        Returns:
            Created WorkInstruction
        """
        instruction_id = self._generate_id("WI")

        # Build instruction steps
        instruction_steps = []
        for i, step_data in enumerate(steps, 1):
            step = InstructionStep(
                step_id=f"{instruction_id}-STEP-{i:03d}",
                step_number=i,
                title=step_data.get("title", f"Step {i}"),
                description=step_data.get("description", ""),
                estimated_duration_seconds=step_data.get("duration_seconds", 60),
                highlights=[
                    ARHighlight(
                        highlight_id=f"{instruction_id}-HL-{i}-{j}",
                        target_component=h["target"],
                        highlight_type=HighlightType(h.get("type", "outline")),
                        color=h.get("color", "#00FF00")
                    )
                    for j, h in enumerate(step_data.get("highlights", []))
                ],
                overlays=[
                    AROverlay(
                        overlay_id=f"{instruction_id}-OV-{i}-{j}",
                        media_type=MediaType(o.get("media_type", "text_overlay")),
                        content=o.get("content", ""),
                        transform=Transform3D()
                    )
                    for j, o in enumerate(step_data.get("overlays", []))
                ],
                safety_indicators=[
                    SafetyIndicator(
                        indicator_id=f"{instruction_id}-SI-{i}-{j}",
                        safety_level=SafetyLevel(s.get("level", "notice")),
                        message=s.get("message", ""),
                        requires_acknowledgment=s.get("requires_ack", False)
                    )
                    for j, s in enumerate(step_data.get("safety", []))
                ],
                tools_required=step_data.get("tools", []),
                materials_required=step_data.get("materials", []),
                verification_required=step_data.get("verify", False),
                voice_instruction=step_data.get("voice", None),
                video_url=step_data.get("video", None)
            )
            instruction_steps.append(step)

        # Calculate total duration
        total_duration = sum(s.estimated_duration_seconds for s in instruction_steps)

        instruction = WorkInstruction(
            instruction_id=instruction_id,
            instruction_code=instruction_code,
            title=title,
            description=description,
            instruction_type=instruction_type,
            version="1.0",
            steps=instruction_steps,
            model_id=model_id,
            equipment_id=equipment_id,
            total_estimated_duration_seconds=total_duration,
            interaction_mode=interaction_mode,
            created_by=created_by,
            created_at=datetime.now()
        )

        self.instructions[instruction_id] = instruction
        logger.info(f"Created AR instruction: {title} ({instruction_id})")

        return instruction

    async def approve_instruction(
        self,
        instruction_id: str,
        approved_by: str
    ) -> WorkInstruction:
        """Approve an instruction for use."""
        if instruction_id not in self.instructions:
            raise ValueError(f"Instruction not found: {instruction_id}")

        instruction = self.instructions[instruction_id]
        instruction.approved_by = approved_by
        instruction.approved_at = datetime.now()
        instruction.status = "approved"

        logger.info(f"Approved instruction: {instruction_id}")

        return instruction

    async def add_step_highlight(
        self,
        instruction_id: str,
        step_number: int,
        target_component: str,
        highlight_type: HighlightType,
        color: str = "#00FF00",
        animation: str = None
    ) -> ARHighlight:
        """Add a highlight to a step."""
        if instruction_id not in self.instructions:
            raise ValueError(f"Instruction not found: {instruction_id}")

        instruction = self.instructions[instruction_id]
        step = next((s for s in instruction.steps if s.step_number == step_number), None)

        if not step:
            raise ValueError(f"Step not found: {step_number}")

        highlight = ARHighlight(
            highlight_id=self._generate_id("HL"),
            target_component=target_component,
            highlight_type=highlight_type,
            color=color,
            animation=animation
        )

        step.highlights.append(highlight)

        return highlight

    async def add_sensor_visualization(
        self,
        instruction_id: str,
        step_number: int,
        sensor_id: str,
        sensor_name: str,
        display_type: str = "gauge",
        unit: str = "",
        warning_threshold: float = None,
        critical_threshold: float = None
    ) -> SensorVisualization:
        """Add real-time sensor visualization to a step."""
        if instruction_id not in self.instructions:
            raise ValueError(f"Instruction not found: {instruction_id}")

        instruction = self.instructions[instruction_id]
        step = next((s for s in instruction.steps if s.step_number == step_number), None)

        if not step:
            raise ValueError(f"Step not found: {step_number}")

        viz = SensorVisualization(
            viz_id=self._generate_id("VIZ"),
            sensor_id=sensor_id,
            sensor_name=sensor_name,
            display_type=display_type,
            unit=unit,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold
        )

        step.sensor_visualizations.append(viz)

        return viz

    # =========================================================================
    # AR Session Management
    # =========================================================================

    async def start_session(
        self,
        instruction_id: str,
        user_id: str,
        user_name: str,
        device_id: str,
        device_type: str
    ) -> ARSession:
        """
        Start an AR instruction session.

        Args:
            instruction_id: Instruction to execute
            user_id: User starting the session
            user_name: User display name
            device_id: AR device identifier
            device_type: Type of AR device

        Returns:
            New ARSession
        """
        if instruction_id not in self.instructions:
            raise ValueError(f"Instruction not found: {instruction_id}")

        instruction = self.instructions[instruction_id]

        if instruction.status != "approved" and instruction.status != "active":
            raise ValueError(f"Instruction not approved: {instruction.status}")

        session_id = self._generate_id("SES")

        session = ARSession(
            session_id=session_id,
            user_id=user_id,
            user_name=user_name,
            instruction_id=instruction_id,
            device_id=device_id,
            device_type=device_type,
            state=SessionState.READY,
            current_step=1,
            started_at=datetime.now()
        )

        self.sessions[session_id] = session

        # Register device
        self._device_registry[device_id] = {
            "session_id": session_id,
            "device_type": device_type,
            "connected_at": datetime.now()
        }

        logger.info(f"Started AR session: {session_id} for user {user_name}")

        return session

    async def get_current_step_content(
        self,
        session_id: str
    ) -> Dict:
        """Get current step content for AR display."""
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = self.sessions[session_id]
        instruction = self.instructions[session.instruction_id]

        step = next(
            (s for s in instruction.steps if s.step_number == session.current_step),
            None
        )

        if not step:
            return {"error": "Step not found"}

        return {
            "session_id": session_id,
            "step_number": step.step_number,
            "total_steps": len(instruction.steps),
            "title": step.title,
            "description": step.description,
            "estimated_duration_seconds": step.estimated_duration_seconds,
            "highlights": [
                {
                    "id": h.highlight_id,
                    "target": h.target_component,
                    "type": h.highlight_type.value,
                    "color": h.color,
                    "animation": h.animation
                }
                for h in step.highlights
            ],
            "overlays": [
                {
                    "id": o.overlay_id,
                    "media_type": o.media_type.value,
                    "content": o.content,
                    "interactive": o.interactive
                }
                for o in step.overlays
            ],
            "safety_indicators": [
                {
                    "id": s.indicator_id,
                    "level": s.safety_level.value,
                    "message": s.message,
                    "requires_ack": s.requires_acknowledgment,
                    "blocking": s.blocking
                }
                for s in step.safety_indicators
            ],
            "sensor_visualizations": [
                {
                    "id": v.viz_id,
                    "sensor_id": v.sensor_id,
                    "name": v.sensor_name,
                    "display_type": v.display_type,
                    "unit": v.unit,
                    "warning": v.warning_threshold,
                    "critical": v.critical_threshold
                }
                for v in step.sensor_visualizations
            ],
            "tools_required": step.tools_required,
            "materials_required": step.materials_required,
            "verification_required": step.verification_required,
            "voice_instruction": step.voice_instruction,
            "video_url": step.video_url
        }

    async def advance_step(
        self,
        session_id: str,
        verification_data: Dict = None
    ) -> Tuple[bool, Dict]:
        """
        Advance to next step.

        Returns:
            Tuple of (success, next_step_content or completion_data)
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = self.sessions[session_id]
        instruction = self.instructions[session.instruction_id]

        current_step = next(
            (s for s in instruction.steps if s.step_number == session.current_step),
            None
        )

        # Record step time
        if current_step:
            step_start = session.step_times.get(f"start_{current_step.step_id}",
                                                  session.started_at.timestamp())
            elapsed = datetime.now().timestamp() - step_start
            session.step_times[current_step.step_id] = elapsed

            # Handle verification if required
            if current_step.verification_required:
                if not verification_data:
                    return False, {"error": "Verification required", "type": current_step.verification_type}
                session.verifications[current_step.step_id] = {
                    "data": verification_data,
                    "timestamp": datetime.now().isoformat()
                }

        # Check if completed
        if session.current_step >= len(instruction.steps):
            session.state = SessionState.COMPLETED
            session.completed_at = datetime.now()

            total_time = (session.completed_at - session.started_at).total_seconds()
            total_time -= session.paused_duration_seconds

            return True, {
                "completed": True,
                "total_time_seconds": total_time,
                "steps_completed": len(instruction.steps),
                "verifications": len(session.verifications)
            }

        # Advance to next step
        session.current_step += 1
        session.state = SessionState.ACTIVE

        # Record start time for new step
        next_step = instruction.steps[session.current_step - 1]
        session.step_times[f"start_{next_step.step_id}"] = datetime.now().timestamp()

        content = await self.get_current_step_content(session_id)

        return True, content

    async def go_to_step(
        self,
        session_id: str,
        step_number: int
    ) -> Dict:
        """Navigate to a specific step."""
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = self.sessions[session_id]
        instruction = self.instructions[session.instruction_id]

        if step_number < 1 or step_number > len(instruction.steps):
            raise ValueError(f"Invalid step number: {step_number}")

        session.current_step = step_number
        session.state = SessionState.ACTIVE

        return await self.get_current_step_content(session_id)

    async def pause_session(self, session_id: str) -> ARSession:
        """Pause the current session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = self.sessions[session_id]
        session.state = SessionState.PAUSED
        session.step_times["pause_start"] = datetime.now().timestamp()

        return session

    async def resume_session(self, session_id: str) -> ARSession:
        """Resume a paused session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = self.sessions[session_id]

        if session.state == SessionState.PAUSED:
            pause_start = session.step_times.get("pause_start", datetime.now().timestamp())
            session.paused_duration_seconds += datetime.now().timestamp() - pause_start
            del session.step_times["pause_start"]

        session.state = SessionState.ACTIVE

        return session

    async def end_session(
        self,
        session_id: str,
        reason: str = "completed"
    ) -> Dict:
        """End an AR session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = self.sessions[session_id]
        session.state = SessionState.COMPLETED
        session.completed_at = datetime.now()

        # Calculate statistics
        total_time = (session.completed_at - session.started_at).total_seconds()
        active_time = total_time - session.paused_duration_seconds

        # Clean up device registry
        if session.device_id in self._device_registry:
            del self._device_registry[session.device_id]

        # Disconnect any remote experts
        for expert_id in session.remote_experts:
            if expert_id in self.expert_sessions:
                self.expert_sessions[expert_id].disconnected_at = datetime.now()

        logger.info(f"Ended AR session: {session_id}, reason: {reason}")

        return {
            "session_id": session_id,
            "reason": reason,
            "total_time_seconds": total_time,
            "active_time_seconds": active_time,
            "steps_completed": session.current_step,
            "verifications": len(session.verifications),
            "issues_reported": len(session.issues_reported)
        }

    # =========================================================================
    # Remote Expert Assistance
    # =========================================================================

    async def request_expert(
        self,
        session_id: str,
        expert_id: str,
        expert_name: str
    ) -> RemoteExpertSession:
        """Request remote expert assistance."""
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")

        expert_session_id = self._generate_id("EXP")

        expert_session = RemoteExpertSession(
            expert_session_id=expert_session_id,
            ar_session_id=session_id,
            expert_id=expert_id,
            expert_name=expert_name,
            connected_at=datetime.now()
        )

        self.expert_sessions[expert_session_id] = expert_session
        self.sessions[session_id].remote_experts.append(expert_session_id)

        logger.info(f"Expert {expert_name} joined session {session_id}")

        return expert_session

    async def add_expert_annotation(
        self,
        expert_session_id: str,
        annotation_type: str,
        content: Dict,
        position: Position3D = None
    ) -> Dict:
        """Add annotation from remote expert."""
        if expert_session_id not in self.expert_sessions:
            raise ValueError(f"Expert session not found: {expert_session_id}")

        expert_session = self.expert_sessions[expert_session_id]

        annotation = {
            "annotation_id": self._generate_id("ANN"),
            "type": annotation_type,  # drawing, pointer, text, highlight
            "content": content,
            "position": {"x": position.x, "y": position.y, "z": position.z} if position else None,
            "timestamp": datetime.now().isoformat(),
            "expert_id": expert_session.expert_id
        }

        expert_session.annotations.append(annotation)

        # Also add to main session for persistence
        ar_session = self.sessions[expert_session.ar_session_id]
        ar_session.annotations.append(annotation)

        return annotation

    async def update_expert_pointer(
        self,
        expert_session_id: str,
        position: Position3D
    ) -> RemoteExpertSession:
        """Update expert's pointer position in AR space."""
        if expert_session_id not in self.expert_sessions:
            raise ValueError(f"Expert session not found: {expert_session_id}")

        expert_session = self.expert_sessions[expert_session_id]
        expert_session.pointer_position = position

        return expert_session

    async def disconnect_expert(
        self,
        expert_session_id: str
    ) -> RemoteExpertSession:
        """Disconnect remote expert."""
        if expert_session_id not in self.expert_sessions:
            raise ValueError(f"Expert session not found: {expert_session_id}")

        expert_session = self.expert_sessions[expert_session_id]
        expert_session.disconnected_at = datetime.now()
        expert_session.voice_active = False
        expert_session.video_stream_active = False

        logger.info(f"Expert disconnected from session {expert_session.ar_session_id}")

        return expert_session

    # =========================================================================
    # Training Simulation
    # =========================================================================

    async def create_simulation(
        self,
        simulation_name: str,
        description: str,
        instruction_id: str,
        error_injection: List[Dict] = None,
        scoring_criteria: Dict = None,
        time_limit_seconds: int = None
    ) -> TrainingSimulation:
        """Create a VR training simulation."""
        if instruction_id not in self.instructions:
            raise ValueError(f"Instruction not found: {instruction_id}")

        simulation_id = self._generate_id("SIM")

        simulation = TrainingSimulation(
            simulation_id=simulation_id,
            simulation_name=simulation_name,
            description=description,
            instruction_id=instruction_id,
            error_injection=error_injection or [],
            scoring_criteria=scoring_criteria or {
                "time_weight": 0.3,
                "accuracy_weight": 0.4,
                "safety_weight": 0.3
            },
            time_limit_seconds=time_limit_seconds
        )

        self.simulations[simulation_id] = simulation
        logger.info(f"Created training simulation: {simulation_name}")

        return simulation

    async def start_training_attempt(
        self,
        simulation_id: str,
        user_id: str
    ) -> TrainingResult:
        """Start a training attempt."""
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation not found: {simulation_id}")

        simulation = self.simulations[simulation_id]

        # Count previous attempts
        previous_attempts = sum(
            1 for r in self.training_results.values()
            if r.simulation_id == simulation_id and r.user_id == user_id
        )

        if previous_attempts >= simulation.attempts_allowed:
            raise ValueError("Maximum attempts exceeded")

        result_id = self._generate_id("RES")

        result = TrainingResult(
            result_id=result_id,
            simulation_id=simulation_id,
            user_id=user_id,
            attempt_number=previous_attempts + 1,
            started_at=datetime.now(),
            completed_at=None
        )

        self.training_results[result_id] = result

        return result

    async def complete_training_attempt(
        self,
        result_id: str,
        steps_completed: int,
        errors_made: List[Dict],
        score_percent: float
    ) -> TrainingResult:
        """Complete a training attempt with results."""
        if result_id not in self.training_results:
            raise ValueError(f"Training result not found: {result_id}")

        result = self.training_results[result_id]
        result.completed_at = datetime.now()
        result.steps_completed = steps_completed
        result.errors_made = errors_made
        result.score_percent = score_percent
        result.time_elapsed_seconds = (result.completed_at - result.started_at).total_seconds()

        simulation = self.simulations[result.simulation_id]
        result.passed = score_percent >= simulation.required_score_percent

        logger.info(f"Training attempt completed: {result_id}, score: {score_percent}%, passed: {result.passed}")

        return result

    async def get_training_history(
        self,
        user_id: str,
        simulation_id: str = None
    ) -> List[Dict]:
        """Get training history for a user."""
        results = [
            r for r in self.training_results.values()
            if r.user_id == user_id and
            (simulation_id is None or r.simulation_id == simulation_id)
        ]

        return [
            {
                "result_id": r.result_id,
                "simulation_id": r.simulation_id,
                "attempt_number": r.attempt_number,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "score_percent": r.score_percent,
                "time_seconds": r.time_elapsed_seconds,
                "passed": r.passed,
                "errors": len(r.errors_made)
            }
            for r in sorted(results, key=lambda x: x.started_at, reverse=True)
        ]

    # =========================================================================
    # Issue Reporting
    # =========================================================================

    async def report_issue(
        self,
        session_id: str,
        issue_type: str,
        description: str,
        step_number: int = None,
        screenshot: str = None
    ) -> Dict:
        """Report an issue during instruction execution."""
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = self.sessions[session_id]

        issue = {
            "issue_id": self._generate_id("ISS"),
            "type": issue_type,  # unclear_instruction, missing_tool, safety_concern, technical
            "description": description,
            "step_number": step_number or session.current_step,
            "screenshot": screenshot,
            "reported_at": datetime.now().isoformat(),
            "user_id": session.user_id
        }

        session.issues_reported.append(issue)
        logger.warning(f"Issue reported in session {session_id}: {issue_type}")

        return issue

    # =========================================================================
    # Analytics
    # =========================================================================

    async def get_session_analytics(
        self,
        session_id: str
    ) -> Dict:
        """Get analytics for a session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = self.sessions[session_id]
        instruction = self.instructions[session.instruction_id]

        step_times = {}
        for step in instruction.steps:
            if step.step_id in session.step_times:
                step_times[step.step_number] = {
                    "actual_seconds": session.step_times[step.step_id],
                    "estimated_seconds": step.estimated_duration_seconds,
                    "variance_percent": round(
                        (session.step_times[step.step_id] - step.estimated_duration_seconds) /
                        step.estimated_duration_seconds * 100, 2
                    ) if step.estimated_duration_seconds > 0 else 0
                }

        return {
            "session_id": session_id,
            "instruction_id": session.instruction_id,
            "user_id": session.user_id,
            "device_type": session.device_type,
            "state": session.state.value,
            "started_at": session.started_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "current_step": session.current_step,
            "total_steps": len(instruction.steps),
            "completion_percent": round(session.current_step / len(instruction.steps) * 100, 1),
            "step_times": step_times,
            "verifications_completed": len(session.verifications),
            "issues_reported": len(session.issues_reported),
            "expert_sessions": len(session.remote_experts),
            "paused_duration_seconds": session.paused_duration_seconds
        }

    async def get_instruction_analytics(
        self,
        instruction_id: str
    ) -> Dict:
        """Get aggregated analytics for an instruction."""
        if instruction_id not in self.instructions:
            raise ValueError(f"Instruction not found: {instruction_id}")

        instruction = self.instructions[instruction_id]

        sessions = [
            s for s in self.sessions.values()
            if s.instruction_id == instruction_id
        ]

        completed_sessions = [s for s in sessions if s.state == SessionState.COMPLETED]

        # Calculate average times per step
        step_averages = {}
        for step in instruction.steps:
            times = [
                s.step_times.get(step.step_id, 0)
                for s in completed_sessions
                if step.step_id in s.step_times
            ]
            if times:
                step_averages[step.step_number] = {
                    "average_seconds": round(sum(times) / len(times), 2),
                    "min_seconds": round(min(times), 2),
                    "max_seconds": round(max(times), 2),
                    "estimated_seconds": step.estimated_duration_seconds
                }

        # Count issues by step
        issues_by_step = {}
        for session in sessions:
            for issue in session.issues_reported:
                step_num = issue.get("step_number", 0)
                if step_num not in issues_by_step:
                    issues_by_step[step_num] = 0
                issues_by_step[step_num] += 1

        return {
            "instruction_id": instruction_id,
            "title": instruction.title,
            "total_sessions": len(sessions),
            "completed_sessions": len(completed_sessions),
            "completion_rate_percent": round(
                len(completed_sessions) / len(sessions) * 100, 2
            ) if sessions else 0,
            "step_averages": step_averages,
            "issues_by_step": issues_by_step,
            "total_issues": sum(len(s.issues_reported) for s in sessions),
            "expert_assists": sum(len(s.remote_experts) for s in sessions)
        }


# Factory function
def create_ar_instructions_service() -> ARInstructionsService:
    """Create and return an ARInstructionsService instance."""
    return ARInstructionsService()
