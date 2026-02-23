"""
Robotic Arm Drivers

Hardware-specific drivers for supported robotic arms:
- Niryo Ned2: 6-DOF collaborative robot
- xArm Lite 6: 6-DOF industrial robot

Each driver implements the BaseArmDriver interface.
"""

from .niryo_ned2 import NiryoNed2Driver, NIRYO_NED2_SPEC
from .xarm_lite6 import XArmLite6Driver, XARM_LITE6_SPEC

__all__ = [
    "NiryoNed2Driver",
    "NIRYO_NED2_SPEC",
    "XArmLite6Driver",
    "XARM_LITE6_SPEC",
]
