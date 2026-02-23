"""
Inventory Services

Manages brick inventory and workspace state.
"""

from .inventory_manager import (
    InventoryManager,
    InventoryItem,
    InventoryStats,
    get_inventory_manager,
)

from .workspace_state import (
    WorkspaceStateManager,
    WorkspaceBrick,
    WorkspaceConfig,
    get_workspace_manager,
)

__all__ = [
    "InventoryManager",
    "InventoryItem",
    "InventoryStats",
    "get_inventory_manager",
    "WorkspaceStateManager",
    "WorkspaceBrick",
    "WorkspaceConfig",
    "get_workspace_manager",
]
