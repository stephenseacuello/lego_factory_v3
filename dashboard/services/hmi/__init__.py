"""
HMI Services - Human Machine Interface

LegoMCP World-Class Manufacturing System v5.0
Phase 20: HMI & Operator Interface
"""

from .work_instructions import WorkInstructionService
from .voice_interface import VoiceInterface, get_voice_interface
from .vr_training import (
    VRTrainingService,
    TrainingCategory,
    DifficultyLevel,
    TrainingStatus,
    InteractionType,
    FeedbackType,
    TrainingStep,
    TrainingScenario,
    TrainingSession,
    TrainingResult,
    ScoringEngine,
    FeedbackGenerator,
    get_vr_training_service,
)

__all__ = [
    "WorkInstructionService",
    "VoiceInterface",
    "get_voice_interface",
    "VRTrainingService",
    "TrainingCategory",
    "DifficultyLevel",
    "TrainingStatus",
    "InteractionType",
    "FeedbackType",
    "TrainingStep",
    "TrainingScenario",
    "TrainingSession",
    "TrainingResult",
    "ScoringEngine",
    "FeedbackGenerator",
    "get_vr_training_service",
]
