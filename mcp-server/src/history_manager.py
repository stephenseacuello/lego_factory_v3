"""
Model History and Undo System

Tracks all brick creation and modification operations with full undo/redo support.
Provides session management and operation logging.
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import hashlib


# ============================================================================
# ENUMS
# ============================================================================


class OperationType(Enum):
    """Types of model operations."""

    CREATE_BRICK = "create_brick"
    MODIFY_BRICK = "modify_brick"
    DELETE_BRICK = "delete_brick"
    EXPORT = "export"
    BATCH_CREATE = "batch_create"
    TRANSFORM = "transform"
    DUPLICATE = "duplicate"


class OperationStatus(Enum):
    """Status of an operation."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    UNDONE = "undone"
    REDONE = "redone"


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class Operation:
    """A single model operation."""

    id: str
    type: OperationType
    timestamp: float
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    status: OperationStatus = OperationStatus.PENDING
    error: Optional[str] = None
    component_name: Optional[str] = None
    duration_ms: float = 0

    # For undo/redo
    undo_data: Optional[Dict[str, Any]] = None
    can_undo: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "params": self.params,
            "result": self.result,
            "status": self.status.value,
            "error": self.error,
            "component_name": self.component_name,
            "duration_ms": self.duration_ms,
            "can_undo": self.can_undo,
        }


@dataclass
class Session:
    """A modeling session containing multiple operations."""

    id: str
    name: str
    created_at: float
    updated_at: float
    operations: List[Operation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Undo/redo stacks
    undo_stack: List[str] = field(default_factory=list)  # Operation IDs
    redo_stack: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "operation_count": len(self.operations),
            "metadata": self.metadata,
            "can_undo": len(self.undo_stack) > 0,
            "can_redo": len(self.redo_stack) > 0,
        }


# ============================================================================
# HISTORY MANAGER
# ============================================================================


class HistoryManager:
    """
    Manages operation history with undo/redo support.

    Features:
    - Track all model operations
    - Full undo/redo support
    - Session management
    - Operation logging
    - Export history
    """

    def __init__(self, storage_dir: str = "/tmp/lego-mcp-history"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.current_session: Optional[Session] = None
        self.sessions: Dict[str, Session] = {}

        # Callbacks for undo/redo execution
        self._undo_handlers: Dict[OperationType, Callable] = {}
        self._redo_handlers: Dict[OperationType, Callable] = {}

        # Load existing sessions
        self._load_sessions()

    def _generate_id(self, prefix: str = "op") -> str:
        """Generate a unique ID."""
        timestamp = str(time.time()).replace(".", "")
        random_part = hashlib.md5(os.urandom(8)).hexdigest()[:6]
        return f"{prefix}_{timestamp}_{random_part}"

    def _load_sessions(self):
        """Load sessions from storage."""
        sessions_file = self.storage_dir / "sessions.json"
        if sessions_file.exists():
            try:
                with open(sessions_file) as f:
                    data = json.load(f)
                    for session_data in data.get("sessions", []):
                        session = Session(
                            id=session_data["id"],
                            name=session_data["name"],
                            created_at=session_data["created_at"],
                            updated_at=session_data["updated_at"],
                            metadata=session_data.get("metadata", {}),
                        )
                        self.sessions[session.id] = session
            except Exception:
                pass

    def _save_sessions(self):
        """Save sessions to storage."""
        sessions_file = self.storage_dir / "sessions.json"
        data = {"sessions": [s.to_dict() for s in self.sessions.values()]}
        with open(sessions_file, "w") as f:
            json.dump(data, f, indent=2)

    def _save_session_operations(self, session: Session):
        """Save operations for a session."""
        ops_file = self.storage_dir / f"session_{session.id}_ops.json"
        data = {"session_id": session.id, "operations": [op.to_dict() for op in session.operations]}
        with open(ops_file, "w") as f:
            json.dump(data, f, indent=2)

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def create_session(self, name: str = None) -> Session:
        """Create a new modeling session."""
        session_id = self._generate_id("session")

        if name is None:
            name = f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        session = Session(id=session_id, name=name, created_at=time.time(), updated_at=time.time())

        self.sessions[session_id] = session
        self.current_session = session
        self._save_sessions()

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        return [
            s.to_dict()
            for s in sorted(self.sessions.values(), key=lambda s: s.updated_at, reverse=True)
        ]

    def switch_session(self, session_id: str) -> Optional[Session]:
        """Switch to a different session."""
        session = self.sessions.get(session_id)
        if session:
            self.current_session = session
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]

            if self.current_session and self.current_session.id == session_id:
                self.current_session = None

            # Delete operations file
            ops_file = self.storage_dir / f"session_{session_id}_ops.json"
            if ops_file.exists():
                ops_file.unlink()

            self._save_sessions()
            return True
        return False

    # =========================================================================
    # OPERATION TRACKING
    # =========================================================================

    def start_operation(
        self, op_type: OperationType, params: Dict[str, Any], can_undo: bool = True
    ) -> Operation:
        """
        Start tracking an operation.

        Call complete_operation() or fail_operation() when done.
        """
        if not self.current_session:
            self.create_session()

        operation = Operation(
            id=self._generate_id("op"),
            type=op_type,
            timestamp=time.time(),
            params=params,
            status=OperationStatus.PENDING,
            can_undo=can_undo,
        )

        self.current_session.operations.append(operation)
        self.current_session.updated_at = time.time()

        return operation

    def complete_operation(
        self,
        operation: Operation,
        result: Dict[str, Any],
        component_name: str = None,
        undo_data: Dict[str, Any] = None,
    ):
        """Mark an operation as completed."""
        operation.status = OperationStatus.COMPLETED
        operation.result = result
        operation.component_name = component_name
        operation.undo_data = undo_data
        operation.duration_ms = (time.time() - operation.timestamp) * 1000

        # Add to undo stack if undoable
        if operation.can_undo and self.current_session:
            self.current_session.undo_stack.append(operation.id)
            # Clear redo stack on new operation
            self.current_session.redo_stack.clear()

        self._save_session_operations(self.current_session)

    def fail_operation(self, operation: Operation, error: str):
        """Mark an operation as failed."""
        operation.status = OperationStatus.FAILED
        operation.error = error
        operation.duration_ms = (time.time() - operation.timestamp) * 1000

        self._save_session_operations(self.current_session)

    def record_operation(
        self,
        op_type: OperationType,
        params: Dict[str, Any],
        result: Dict[str, Any],
        component_name: str = None,
        can_undo: bool = True,
        undo_data: Dict[str, Any] = None,
    ) -> Operation:
        """Record a completed operation in one call."""
        op = self.start_operation(op_type, params, can_undo)
        self.complete_operation(op, result, component_name, undo_data)
        return op

    # =========================================================================
    # UNDO/REDO
    # =========================================================================

    def register_undo_handler(self, op_type: OperationType, handler: Callable[[Operation], bool]):
        """Register a handler for undoing an operation type."""
        self._undo_handlers[op_type] = handler

    def register_redo_handler(self, op_type: OperationType, handler: Callable[[Operation], bool]):
        """Register a handler for redoing an operation type."""
        self._redo_handlers[op_type] = handler

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self.current_session is not None and len(self.current_session.undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self.current_session is not None and len(self.current_session.redo_stack) > 0

    def undo(self) -> Optional[Dict[str, Any]]:
        """
        Undo the last operation.

        Returns:
            Result of undo operation, or None if nothing to undo
        """
        if not self.can_undo():
            return None

        # Get the last operation ID
        op_id = self.current_session.undo_stack.pop()

        # Find the operation
        operation = None
        for op in self.current_session.operations:
            if op.id == op_id:
                operation = op
                break

        if not operation:
            return None

        # Execute undo handler if registered
        handler = self._undo_handlers.get(operation.type)
        if handler:
            try:
                success = handler(operation)
                if success:
                    operation.status = OperationStatus.UNDONE
                    self.current_session.redo_stack.append(op_id)
                    self._save_session_operations(self.current_session)

                    return {
                        "success": True,
                        "operation": operation.to_dict(),
                        "message": f"Undid {operation.type.value}",
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}

        # Default undo (just mark as undone)
        operation.status = OperationStatus.UNDONE
        self.current_session.redo_stack.append(op_id)
        self._save_session_operations(self.current_session)

        return {
            "success": True,
            "operation": operation.to_dict(),
            "message": f"Marked {operation.type.value} as undone (no handler registered)",
        }

    def redo(self) -> Optional[Dict[str, Any]]:
        """
        Redo the last undone operation.

        Returns:
            Result of redo operation, or None if nothing to redo
        """
        if not self.can_redo():
            return None

        op_id = self.current_session.redo_stack.pop()

        operation = None
        for op in self.current_session.operations:
            if op.id == op_id:
                operation = op
                break

        if not operation:
            return None

        handler = self._redo_handlers.get(operation.type)
        if handler:
            try:
                success = handler(operation)
                if success:
                    operation.status = OperationStatus.REDONE
                    self.current_session.undo_stack.append(op_id)
                    self._save_session_operations(self.current_session)

                    return {
                        "success": True,
                        "operation": operation.to_dict(),
                        "message": f"Redid {operation.type.value}",
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}

        operation.status = OperationStatus.REDONE
        self.current_session.undo_stack.append(op_id)
        self._save_session_operations(self.current_session)

        return {
            "success": True,
            "operation": operation.to_dict(),
            "message": f"Marked {operation.type.value} as redone",
        }

    def undo_all(self) -> List[Dict[str, Any]]:
        """Undo all operations in current session."""
        results = []
        while self.can_undo():
            result = self.undo()
            if result:
                results.append(result)
        return results

    # =========================================================================
    # HISTORY QUERIES
    # =========================================================================

    def get_history(
        self, limit: int = 50, op_type: OperationType = None, status: OperationStatus = None
    ) -> List[Dict[str, Any]]:
        """Get operation history with optional filters."""
        if not self.current_session:
            return []

        operations = self.current_session.operations.copy()

        # Filter by type
        if op_type:
            operations = [op for op in operations if op.type == op_type]

        # Filter by status
        if status:
            operations = [op for op in operations if op.status == status]

        # Sort by timestamp (newest first) and limit
        operations.sort(key=lambda op: op.timestamp, reverse=True)
        operations = operations[:limit]

        return [op.to_dict() for op in operations]

    def get_operation(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific operation by ID."""
        if not self.current_session:
            return None

        for op in self.current_session.operations:
            if op.id == operation_id:
                return op.to_dict()
        return None

    def get_component_history(self, component_name: str) -> List[Dict[str, Any]]:
        """Get all operations for a specific component."""
        if not self.current_session:
            return []

        operations = [
            op for op in self.current_session.operations if op.component_name == component_name
        ]

        operations.sort(key=lambda op: op.timestamp, reverse=True)
        return [op.to_dict() for op in operations]

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the current session."""
        if not self.current_session:
            return {}

        ops = self.current_session.operations

        # Count by type
        by_type = {}
        for op in ops:
            type_name = op.type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1

        # Count by status
        by_status = {}
        for op in ops:
            status_name = op.status.value
            by_status[status_name] = by_status.get(status_name, 0) + 1

        # Calculate timing
        completed_ops = [op for op in ops if op.status == OperationStatus.COMPLETED]
        total_time_ms = sum(op.duration_ms for op in completed_ops)
        avg_time_ms = total_time_ms / len(completed_ops) if completed_ops else 0

        return {
            "session_id": self.current_session.id,
            "session_name": self.current_session.name,
            "total_operations": len(ops),
            "by_type": by_type,
            "by_status": by_status,
            "total_time_ms": total_time_ms,
            "average_time_ms": round(avg_time_ms, 2),
            "can_undo": self.can_undo(),
            "can_redo": self.can_redo(),
            "undo_stack_size": len(self.current_session.undo_stack),
            "redo_stack_size": len(self.current_session.redo_stack),
        }

    # =========================================================================
    # EXPORT
    # =========================================================================

    def export_history(self, format: str = "json") -> str:
        """Export current session history."""
        if not self.current_session:
            return "{}"

        data = {
            "session": self.current_session.to_dict(),
            "operations": [op.to_dict() for op in self.current_session.operations],
            "exported_at": datetime.now().isoformat(),
        }

        return json.dumps(data, indent=2)

    def clear_history(self):
        """Clear all history for current session."""
        if self.current_session:
            self.current_session.operations.clear()
            self.current_session.undo_stack.clear()
            self.current_session.redo_stack.clear()
            self._save_session_operations(self.current_session)


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_history_manager: Optional[HistoryManager] = None


def get_history_manager() -> HistoryManager:
    """Get the global history manager instance."""
    global _history_manager
    if _history_manager is None:
        _history_manager = HistoryManager()
    return _history_manager


# ============================================================================
# MCP TOOL DEFINITIONS
# ============================================================================

HISTORY_TOOLS = {
    "undo": {
        "description": "Undo the last operation.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "redo": {
        "description": "Redo the last undone operation.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "get_history": {
        "description": "Get operation history for the current session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 50,
                    "description": "Maximum number of operations to return",
                },
                "operation_type": {
                    "type": "string",
                    "enum": [
                        "create_brick",
                        "modify_brick",
                        "delete_brick",
                        "export",
                        "batch_create",
                    ],
                    "description": "Filter by operation type",
                },
            },
        },
    },
    "get_statistics": {
        "description": "Get statistics about the current modeling session.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "create_session": {
        "description": "Create a new modeling session.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Session name"}},
        },
    },
    "list_sessions": {
        "description": "List all modeling sessions.",
        "inputSchema": {"type": "object", "properties": {}},
    },
}
