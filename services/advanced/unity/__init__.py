"""
Unity Integration Services
==========================

Real-time communication and data services for Unity 3D clients.

Supports:
- WebGL (Browser-based)
- Desktop (Windows/Mac/Linux)
- VR (Meta Quest, HTC Vive)
- AR (HoloLens, iOS ARKit)

Key Components:
---------------
1. **UnityBridge**: WebSocket bridge for real-time bidirectional communication
2. **SceneDataService**: 3D scene state preparation for Unity consumption
3. **UnityWebSocketServer**: Standalone WebSocket server entry point

Author: LegoMCP Team
Version: 2.0.0
"""

from .bridge import (
    UnityBridge,
    UnityClient,
    ClientType,
    MessageType,
    SubscriptionRoom,
    UnityMessage,
    get_unity_bridge,
)
from .scene_data import (
    SceneDataService,
    SceneObject,
    EquipmentSceneObject,
    Vector3,
    Quaternion,
    ModelFormat,
    LODLevel,
    get_scene_data_service,
)
from .server import (
    UnityWebSocketServer,
)

__all__ = [
    # Bridge
    "UnityBridge",
    "UnityClient",
    "ClientType",
    "MessageType",
    "SubscriptionRoom",
    "UnityMessage",
    "get_unity_bridge",

    # Scene Data
    "SceneDataService",
    "SceneObject",
    "EquipmentSceneObject",
    "Vector3",
    "Quaternion",
    "ModelFormat",
    "LODLevel",
    "get_scene_data_service",

    # Server
    "UnityWebSocketServer",
]

__version__ = "2.0.0"
