"""
Robot Controllers Package

Enhanced robot controllers for factory digital twin:
- Niryo Ned2 collaborative robot
- UFactory xArm Lite 6 industrial robot

Each controller provides:
- Forward/inverse kinematics
- Pick-and-place primitives
- Trajectory planning
- Gripper control
- Safety monitoring
"""

from .ned2_controller import Ned2Controller, Ned2Configuration
from .xarm_controller import XArmLite6Controller, XArmLite6Configuration

__all__ = [
    'Ned2Controller',
    'Ned2Configuration',
    'XArmLite6Controller',
    'XArmLite6Configuration'
]
