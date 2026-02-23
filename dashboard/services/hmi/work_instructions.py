"""
Digital Work Instructions - Human-Machine Interface

LegoMCP World-Class Manufacturing System v5.0
Phase 20: Advanced Human-Machine Interface

AR-ready digital work instructions:
- Step-by-step guidance
- Media support (images, videos, 3D)
- Quality checkpoints
- Skill-based routing
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class MediaType(str, Enum):
    """Type of instruction media."""
    IMAGE = "image"
    VIDEO = "video"
    MODEL_3D = "model_3d"
    DOCUMENT = "document"
    ANIMATION = "animation"


class VerificationType(str, Enum):
    """How to verify step completion."""
    VISUAL = "visual"  # Operator visual check
    MEASUREMENT = "measurement"  # Take measurement
    SCAN = "scan"  # Barcode/RFID scan
    SENSOR = "sensor"  # Automatic sensor
    PHOTO = "photo"  # Take photo evidence
    SIGNATURE = "signature"  # Operator sign-off


class SkillLevel(str, Enum):
    """Required skill level."""
    TRAINEE = "trainee"
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class InstructionMedia:
    """Media attachment for instructions."""
    media_id: str
    media_type: MediaType
    url: str
    title: str = ""
    description: str = ""
    duration_seconds: int = 0  # For video/animation

    def to_dict(self) -> Dict[str, Any]:
        return {
            'media_id': self.media_id,
            'media_type': self.media_type.value,
            'url': self.url,
            'title': self.title,
            'description': self.description,
        }


@dataclass
class QualityCheckpoint:
    """Quality check within an instruction step."""
    checkpoint_id: str
    description: str
    verification_type: VerificationType
    is_mandatory: bool = True

    # Measurement details (if verification_type is MEASUREMENT)
    target_value: Optional[float] = None
    tolerance: Optional[float] = None
    unit: str = ""

    # Pass/fail
    passed: Optional[bool] = None
    actual_value: Optional[float] = None
    checked_at: Optional[datetime] = None
    checked_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'checkpoint_id': self.checkpoint_id,
            'description': self.description,
            'verification_type': self.verification_type.value,
            'is_mandatory': self.is_mandatory,
            'target_value': self.target_value,
            'tolerance': self.tolerance,
            'unit': self.unit,
            'passed': self.passed,
        }


@dataclass
class SafetyWarning:
    """Safety warning for a step."""
    warning_id: str
    severity: str  # caution, warning, danger
    message: str
    ppe_required: List[str] = field(default_factory=list)  # PPE items

    def to_dict(self) -> Dict[str, Any]:
        return {
            'warning_id': self.warning_id,
            'severity': self.severity,
            'message': self.message,
            'ppe_required': self.ppe_required,
        }


@dataclass
class AROverlay:
    """AR overlay annotation."""
    overlay_id: str
    anchor_type: str  # MACHINE, PART, WORKSTATION
    overlay_type: str  # TEXT, ARROW, HIGHLIGHT, 3D_MODEL
    content: Dict[str, Any] = field(default_factory=dict)
    position: Dict[str, float] = field(default_factory=dict)  # x, y, z

    def to_dict(self) -> Dict[str, Any]:
        return {
            'overlay_id': self.overlay_id,
            'anchor_type': self.anchor_type,
            'overlay_type': self.overlay_type,
            'content': self.content,
            'position': self.position,
        }


@dataclass
class InstructionStep:
    """Single step in work instructions."""
    step_id: str
    step_number: int
    title: str
    description: str
    duration_seconds: int = 60

    # Media
    media: List[InstructionMedia] = field(default_factory=list)
    ar_overlays: List[AROverlay] = field(default_factory=list)

    # Quality
    quality_checkpoints: List[QualityCheckpoint] = field(default_factory=list)

    # Safety
    safety_warnings: List[SafetyWarning] = field(default_factory=list)

    # Requirements
    skill_level_required: SkillLevel = SkillLevel.BASIC
    tools_required: List[str] = field(default_factory=list)

    # Tracking
    is_complete: bool = False
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None

    def __post_init__(self):
        if not self.step_id:
            self.step_id = str(uuid4())

    def complete(self, operator_id: str) -> None:
        """Mark step as complete."""
        self.is_complete = True
        self.completed_at = datetime.utcnow()
        self.completed_by = operator_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_id': self.step_id,
            'step_number': self.step_number,
            'title': self.title,
            'description': self.description,
            'duration_seconds': self.duration_seconds,
            'media': [m.to_dict() for m in self.media],
            'ar_overlays': [a.to_dict() for a in self.ar_overlays],
            'quality_checkpoints': [q.to_dict() for q in self.quality_checkpoints],
            'safety_warnings': [s.to_dict() for s in self.safety_warnings],
            'skill_level_required': self.skill_level_required.value,
            'tools_required': self.tools_required,
            'is_complete': self.is_complete,
        }


@dataclass
class WorkInstruction:
    """Complete work instruction document."""
    instruction_id: str
    operation_id: str
    operation_name: str
    part_id: str
    part_name: str

    # Steps
    steps: List[InstructionStep] = field(default_factory=list)

    # Metadata
    version: str = "1.0"
    effective_date: Optional[datetime] = None
    created_by: Optional[str] = None

    # Requirements
    min_skill_level: SkillLevel = SkillLevel.BASIC
    estimated_duration_minutes: int = 0

    # Status
    status: str = "draft"  # draft, review, approved, active

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.instruction_id:
            self.instruction_id = str(uuid4())
        self._recalculate()

    def _recalculate(self) -> None:
        """Recalculate derived values."""
        self.estimated_duration_minutes = sum(s.duration_seconds for s in self.steps) // 60

        # Find max skill level
        skill_order = [SkillLevel.TRAINEE, SkillLevel.BASIC, SkillLevel.INTERMEDIATE,
                       SkillLevel.ADVANCED, SkillLevel.EXPERT]
        max_skill = SkillLevel.BASIC
        for step in self.steps:
            if skill_order.index(step.skill_level_required) > skill_order.index(max_skill):
                max_skill = step.skill_level_required
        self.min_skill_level = max_skill

    def add_step(self, step: InstructionStep) -> None:
        """Add a step to instructions."""
        self.steps.append(step)
        self.steps.sort(key=lambda s: s.step_number)
        self._recalculate()
        self.updated_at = datetime.utcnow()

    def get_current_step(self) -> Optional[InstructionStep]:
        """Get the current (first incomplete) step."""
        for step in self.steps:
            if not step.is_complete:
                return step
        return None

    def get_progress(self) -> Dict[str, Any]:
        """Get completion progress."""
        total = len(self.steps)
        completed = sum(1 for s in self.steps if s.is_complete)

        return {
            'total_steps': total,
            'completed_steps': completed,
            'percent_complete': (completed / total * 100) if total > 0 else 0,
            'is_complete': completed == total,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'instruction_id': self.instruction_id,
            'operation_id': self.operation_id,
            'operation_name': self.operation_name,
            'part_id': self.part_id,
            'part_name': self.part_name,
            'steps': [s.to_dict() for s in self.steps],
            'version': self.version,
            'min_skill_level': self.min_skill_level.value,
            'estimated_duration_minutes': self.estimated_duration_minutes,
            'status': self.status,
            'progress': self.get_progress(),
        }


class WorkInstructionService:
    """
    Work Instruction Service.

    Manages digital work instructions with AR support.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._instructions: Dict[str, WorkInstruction] = {}
        self._by_operation: Dict[str, str] = {}

    def create_instruction(
        self,
        operation_id: str,
        operation_name: str,
        part_id: str,
        part_name: str,
    ) -> WorkInstruction:
        """Create a new work instruction."""
        instruction = WorkInstruction(
            instruction_id=str(uuid4()),
            operation_id=operation_id,
            operation_name=operation_name,
            part_id=part_id,
            part_name=part_name,
        )

        self._instructions[instruction.instruction_id] = instruction
        self._by_operation[operation_id] = instruction.instruction_id

        logger.info(f"Created work instruction for operation {operation_name}")
        return instruction

    def add_step(
        self,
        instruction_id: str,
        step_number: int,
        title: str,
        description: str,
        duration_seconds: int = 60,
        skill_level: SkillLevel = SkillLevel.BASIC,
    ) -> Optional[InstructionStep]:
        """Add a step to an instruction."""
        instruction = self._instructions.get(instruction_id)
        if not instruction:
            return None

        step = InstructionStep(
            step_id=str(uuid4()),
            step_number=step_number,
            title=title,
            description=description,
            duration_seconds=duration_seconds,
            skill_level_required=skill_level,
        )

        instruction.add_step(step)
        return step

    def get_instruction(self, instruction_id: str) -> Optional[WorkInstruction]:
        """Get instruction by ID."""
        return self._instructions.get(instruction_id)

    def get_by_operation(self, operation_id: str) -> Optional[WorkInstruction]:
        """Get instruction for an operation."""
        instruction_id = self._by_operation.get(operation_id)
        if instruction_id:
            return self._instructions.get(instruction_id)
        return None

    def complete_step(
        self,
        instruction_id: str,
        step_id: str,
        operator_id: str,
    ) -> bool:
        """Mark a step as complete."""
        instruction = self._instructions.get(instruction_id)
        if not instruction:
            return False

        for step in instruction.steps:
            if step.step_id == step_id:
                step.complete(operator_id)
                return True
        return False

    def get_summary(self) -> Dict[str, Any]:
        """Get work instruction summary."""
        return {
            'total_instructions': len(self._instructions),
            'by_status': {
                'draft': sum(1 for i in self._instructions.values() if i.status == 'draft'),
                'active': sum(1 for i in self._instructions.values() if i.status == 'active'),
            },
        }
