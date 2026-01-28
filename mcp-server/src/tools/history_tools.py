"""
Model History and Undo/Redo System

Tracks all brick creation operations and allows undo/redo.
Also provides retry functionality for failed operations.
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import copy


# ============================================================================
# OPERATION TYPES
# ============================================================================


class OperationType(Enum):
    """Types of operations that can be tracked."""

    CREATE_BRICK = "create_brick"
    MODIFY_BRICK = "modify_brick"
    DELETE_BRICK = "delete_brick"
    EXPORT = "export"
    SLICE = "slice"
    MILL = "mill"


class OperationStatus(Enum):
    """Status of an operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    UNDONE = "undone"
    RETRYING = "retrying"


# ============================================================================
# OPERATION RECORD
# ============================================================================


@dataclass
class OperationRecord:
    """Record of a single operation."""

    id: str
    type: OperationType
    timestamp: datetime
    status: OperationStatus

    # Operation parameters
    params: Dict[str, Any]

    # Result data
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    # For undo
    undo_data: Optional[Dict[str, Any]] = None
    can_undo: bool = True

    # Retry info
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "params": self.params,
            "result": self.result,
            "error": self.error,
            "can_undo": self.can_undo,
            "retry_count": self.retry_count,
        }


# ============================================================================
# HISTORY MANAGER
# ============================================================================


class HistoryManager:
    """
    Manages operation history with undo/redo support.
    """

    def __init__(self, max_history: int = 100):
        self._history: List[OperationRecord] = []
        self._undo_stack: List[OperationRecord] = []
        self._redo_stack: List[OperationRecord] = []
        self._max_history = max_history
        self._op_counter = 0

        # Callbacks for operations
        self._undo_handlers: Dict[OperationType, Callable] = {}
        self._redo_handlers: Dict[OperationType, Callable] = {}

    def _generate_id(self) -> str:
        """Generate unique operation ID."""
        self._op_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"op_{timestamp}_{self._op_counter}"

    def register_undo_handler(self, op_type: OperationType, handler: Callable):
        """Register handler for undoing an operation type."""
        self._undo_handlers[op_type] = handler

    def register_redo_handler(self, op_type: OperationType, handler: Callable):
        """Register handler for redoing an operation type."""
        self._redo_handlers[op_type] = handler

    def record_operation(
        self,
        op_type: OperationType,
        params: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        undo_data: Optional[Dict[str, Any]] = None,
        can_undo: bool = True,
    ) -> OperationRecord:
        """
        Record an operation in history.

        Args:
            op_type: Type of operation
            params: Parameters used
            result: Result data (if successful)
            error: Error message (if failed)
            undo_data: Data needed to undo this operation
            can_undo: Whether this operation can be undone

        Returns:
            The created operation record
        """
        status = (
            OperationStatus.COMPLETED
            if result
            else (OperationStatus.FAILED if error else OperationStatus.PENDING)
        )

        record = OperationRecord(
            id=self._generate_id(),
            type=op_type,
            timestamp=datetime.now(),
            status=status,
            params=params,
            result=result,
            error=error,
            undo_data=undo_data,
            can_undo=can_undo,
        )

        self._history.append(record)

        # Clear redo stack on new operation
        if status == OperationStatus.COMPLETED:
            self._redo_stack.clear()

        # Trim history if needed
        while len(self._history) > self._max_history:
            self._history.pop(0)

        return record

    def start_operation(self, op_type: OperationType, params: Dict[str, Any]) -> OperationRecord:
        """Start recording an operation (mark as in progress)."""
        record = OperationRecord(
            id=self._generate_id(),
            type=op_type,
            timestamp=datetime.now(),
            status=OperationStatus.IN_PROGRESS,
            params=params,
        )
        self._history.append(record)
        return record

    def complete_operation(
        self,
        record: OperationRecord,
        result: Dict[str, Any],
        undo_data: Optional[Dict[str, Any]] = None,
    ):
        """Mark an operation as completed."""
        record.status = OperationStatus.COMPLETED
        record.result = result
        record.undo_data = undo_data
        self._redo_stack.clear()

    def fail_operation(self, record: OperationRecord, error: str):
        """Mark an operation as failed."""
        record.status = OperationStatus.FAILED
        record.error = error

    def get_history(
        self,
        limit: int = 50,
        op_type: Optional[OperationType] = None,
        status: Optional[OperationStatus] = None,
    ) -> List[OperationRecord]:
        """
        Get operation history.

        Args:
            limit: Maximum number of records to return
            op_type: Filter by operation type
            status: Filter by status

        Returns:
            List of operation records (newest first)
        """
        records = self._history.copy()
        records.reverse()

        if op_type:
            records = [r for r in records if r.type == op_type]

        if status:
            records = [r for r in records if r.status == status]

        return records[:limit]

    def get_last_operation(self) -> Optional[OperationRecord]:
        """Get the most recent operation."""
        return self._history[-1] if self._history else None

    def get_undoable_operations(self) -> List[OperationRecord]:
        """Get operations that can be undone."""
        return [
            r
            for r in reversed(self._history)
            if r.can_undo and r.status == OperationStatus.COMPLETED
        ]

    def can_undo(self) -> bool:
        """Check if there's an operation to undo."""
        return bool(self.get_undoable_operations())

    def can_redo(self) -> bool:
        """Check if there's an operation to redo."""
        return bool(self._redo_stack)

    async def undo(self) -> Optional[Dict[str, Any]]:
        """
        Undo the last operation.

        Returns:
            Result of undo operation, or None if nothing to undo
        """
        undoable = self.get_undoable_operations()
        if not undoable:
            return None

        record = undoable[0]
        handler = self._undo_handlers.get(record.type)

        if not handler:
            return {"error": f"No undo handler for {record.type.value}"}

        try:
            result = await handler(record.params, record.undo_data)
            record.status = OperationStatus.UNDONE
            self._redo_stack.append(record)

            return {
                "success": True,
                "operation_id": record.id,
                "operation_type": record.type.value,
                "result": result,
            }
        except Exception as e:
            return {"success": False, "operation_id": record.id, "error": str(e)}

    async def redo(self) -> Optional[Dict[str, Any]]:
        """
        Redo the last undone operation.

        Returns:
            Result of redo operation, or None if nothing to redo
        """
        if not self._redo_stack:
            return None

        record = self._redo_stack.pop()
        handler = self._redo_handlers.get(record.type)

        if not handler:
            # No special handler, just re-run the operation
            return {"error": f"No redo handler for {record.type.value}"}

        try:
            result = await handler(record.params)
            record.status = OperationStatus.COMPLETED

            return {
                "success": True,
                "operation_id": record.id,
                "operation_type": record.type.value,
                "result": result,
            }
        except Exception as e:
            return {"success": False, "operation_id": record.id, "error": str(e)}

    def clear_history(self):
        """Clear all history."""
        self._history.clear()
        self._undo_stack.clear()
        self._redo_stack.clear()


# ============================================================================
# RETRY MANAGER
# ============================================================================


class RetryManager:
    """
    Manages retry logic for failed operations.
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._retry_callbacks: Dict[str, Callable] = {}

    def register_retry_callback(self, op_type: str, callback: Callable):
        """Register callback for retrying an operation type."""
        self._retry_callbacks[op_type] = callback

    async def retry_operation(
        self, record: OperationRecord, execute_func: Callable
    ) -> Dict[str, Any]:
        """
        Retry a failed operation with exponential backoff.

        Args:
            record: The failed operation record
            execute_func: Function to execute the operation

        Returns:
            Result of the retry attempt
        """
        import asyncio

        if record.retry_count >= record.max_retries:
            return {
                "success": False,
                "error": f"Max retries ({record.max_retries}) exceeded",
                "operation_id": record.id,
            }

        record.retry_count += 1
        record.status = OperationStatus.RETRYING

        # Calculate delay with exponential backoff
        delay = self._base_delay * (2 ** (record.retry_count - 1))
        await asyncio.sleep(delay)

        try:
            result = await execute_func(record.params)

            if result.get("success"):
                record.status = OperationStatus.COMPLETED
                record.result = result
                record.error = None
            else:
                record.error = result.get("error", "Unknown error")
                if record.retry_count < record.max_retries:
                    record.status = OperationStatus.FAILED

            return {
                "success": result.get("success", False),
                "operation_id": record.id,
                "retry_count": record.retry_count,
                "result": result,
            }

        except Exception as e:
            record.status = OperationStatus.FAILED
            record.error = str(e)

            return {
                "success": False,
                "operation_id": record.id,
                "retry_count": record.retry_count,
                "error": str(e),
            }

    def get_failed_operations(self, history: HistoryManager) -> List[OperationRecord]:
        """Get operations that failed and can be retried."""
        return [
            r
            for r in history.get_history(100)
            if r.status == OperationStatus.FAILED and r.retry_count < r.max_retries
        ]


# ============================================================================
# MODEL STATE TRACKER
# ============================================================================


class ModelStateTracker:
    """
    Tracks the state of created models for undo/redo.
    """

    def __init__(self):
        self._models: Dict[str, Dict[str, Any]] = {}
        self._snapshots: List[Dict[str, Dict[str, Any]]] = []
        self._snapshot_index = -1

    def register_model(self, model_id: str, model_data: Dict[str, Any]):
        """Register a new model."""
        self._models[model_id] = copy.deepcopy(model_data)
        self._take_snapshot()

    def update_model(self, model_id: str, model_data: Dict[str, Any]):
        """Update model data."""
        if model_id in self._models:
            self._models[model_id] = copy.deepcopy(model_data)
            self._take_snapshot()

    def remove_model(self, model_id: str):
        """Remove a model."""
        if model_id in self._models:
            del self._models[model_id]
            self._take_snapshot()

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get model data."""
        return copy.deepcopy(self._models.get(model_id))

    def list_models(self) -> List[str]:
        """List all model IDs."""
        return list(self._models.keys())

    def _take_snapshot(self):
        """Take a snapshot of current state."""
        # Remove any snapshots after current index (for redo)
        self._snapshots = self._snapshots[: self._snapshot_index + 1]

        # Add new snapshot
        self._snapshots.append(copy.deepcopy(self._models))
        self._snapshot_index = len(self._snapshots) - 1

        # Limit snapshot history
        if len(self._snapshots) > 50:
            self._snapshots.pop(0)
            self._snapshot_index -= 1

    def can_undo_state(self) -> bool:
        """Check if we can undo state."""
        return self._snapshot_index > 0

    def can_redo_state(self) -> bool:
        """Check if we can redo state."""
        return self._snapshot_index < len(self._snapshots) - 1

    def undo_state(self) -> bool:
        """Restore previous state."""
        if self.can_undo_state():
            self._snapshot_index -= 1
            self._models = copy.deepcopy(self._snapshots[self._snapshot_index])
            return True
        return False

    def redo_state(self) -> bool:
        """Restore next state."""
        if self.can_redo_state():
            self._snapshot_index += 1
            self._models = copy.deepcopy(self._snapshots[self._snapshot_index])
            return True
        return False


# ============================================================================
# MCP TOOL DEFINITIONS
# ============================================================================

HISTORY_TOOLS = {
    "get_history": {
        "description": "Get operation history.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "description": "Maximum records to return",
                },
                "type": {
                    "type": "string",
                    "enum": [
                        "create_brick",
                        "modify_brick",
                        "delete_brick",
                        "export",
                        "slice",
                        "mill",
                    ],
                    "description": "Filter by operation type",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "failed", "undone"],
                    "description": "Filter by status",
                },
            },
        },
    },
    "undo": {
        "description": "Undo the last operation.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "redo": {
        "description": "Redo the last undone operation.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "retry_failed": {
        "description": "Retry a failed operation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "operation_id": {"type": "string", "description": "ID of the operation to retry"}
            },
            "required": ["operation_id"],
        },
    },
    "list_models": {
        "description": "List all created models.",
        "inputSchema": {"type": "object", "properties": {}},
    },
}


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

# Global history manager instance
history_manager = HistoryManager(max_history=100)
retry_manager = RetryManager(max_retries=3)
model_tracker = ModelStateTracker()
