#!/usr/bin/env python3
"""
Checkpoint Manager for LEGO MCP Supervisor

Provides state checkpointing and restoration for fault-tolerant operations.
Enables recovery of job state after node crashes or system restarts.

Features:
- Periodic automatic checkpointing
- Manual checkpoint creation
- Checkpoint restoration
- Checkpoint cleanup and rotation
- JSON-serializable state storage

Industry 4.0/5.0 Architecture - ISA-95 Compliant State Recovery

Usage:
    from lego_mcp_supervisor import CheckpointManager

    # Create manager
    checkpoint_mgr = CheckpointManager(
        storage_path="/var/lib/lego_mcp/checkpoints",
        max_checkpoints=10,
    )

    # Save checkpoint
    checkpoint_mgr.save("job_123", {
        "position": [100, 50, 20],
        "line_number": 150,
        "tool": "end_mill_3mm",
    })

    # Restore checkpoint
    state = checkpoint_mgr.load("job_123")
    if state:
        resume_job(state)
"""

import json
import os
import hashlib
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum


class CheckpointType(Enum):
    """Types of checkpoints."""
    MANUAL = "manual"           # Explicitly created by user
    PERIODIC = "periodic"       # Created by automatic timer
    PRE_OPERATION = "pre_op"    # Created before risky operation
    RECOVERY = "recovery"       # Created during recovery process


@dataclass
class CheckpointMetadata:
    """Metadata for a checkpoint."""
    checkpoint_id: str
    timestamp: str
    checkpoint_type: str
    node_id: str
    description: str = ""
    hash: str = ""
    size_bytes: int = 0
    parent_checkpoint_id: Optional[str] = None


@dataclass
class Checkpoint:
    """A checkpoint containing state data and metadata."""
    metadata: CheckpointMetadata
    state: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "metadata": asdict(self.metadata),
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """Create from dictionary."""
        metadata = CheckpointMetadata(**data["metadata"])
        return cls(metadata=metadata, state=data["state"])


class CheckpointManager:
    """
    Manages state checkpoints for fault-tolerant operations.

    Provides persistent storage, rotation, and restoration of
    node state for recovery after failures.
    """

    def __init__(
        self,
        storage_path: str = "/var/lib/lego_mcp/checkpoints",
        max_checkpoints: int = 10,
        auto_cleanup: bool = True,
        node_id: str = "unknown",
    ):
        """
        Initialize the checkpoint manager.

        Args:
            storage_path: Directory to store checkpoint files
            max_checkpoints: Maximum number of checkpoints to retain per node
            auto_cleanup: Automatically remove old checkpoints
            node_id: Identifier for the node using this manager
        """
        self._storage_path = Path(storage_path)
        self._max_checkpoints = max_checkpoints
        self._auto_cleanup = auto_cleanup
        self._node_id = node_id
        self._lock = threading.RLock()

        # Create storage directory
        self._storage_path.mkdir(parents=True, exist_ok=True)

        # Checkpoint index (loaded from disk)
        self._index: Dict[str, CheckpointMetadata] = {}
        self._load_index()

    def _load_index(self):
        """Load checkpoint index from disk."""
        index_path = self._storage_path / "index.json"
        if index_path.exists():
            try:
                with open(index_path, 'r') as f:
                    data = json.load(f)
                    for cp_id, meta_dict in data.items():
                        self._index[cp_id] = CheckpointMetadata(**meta_dict)
            except (json.JSONDecodeError, KeyError) as e:
                # Index corrupted - rebuild from files
                self._rebuild_index()

    def _save_index(self):
        """Save checkpoint index to disk."""
        index_path = self._storage_path / "index.json"
        with open(index_path, 'w') as f:
            index_dict = {
                cp_id: asdict(meta) for cp_id, meta in self._index.items()
            }
            json.dump(index_dict, f, indent=2)

    def _rebuild_index(self):
        """Rebuild index from checkpoint files."""
        self._index.clear()
        for cp_file in self._storage_path.glob("*.checkpoint.json"):
            try:
                with open(cp_file, 'r') as f:
                    data = json.load(f)
                    cp = Checkpoint.from_dict(data)
                    self._index[cp.metadata.checkpoint_id] = cp.metadata
            except (json.JSONDecodeError, KeyError):
                # Corrupted checkpoint - skip
                pass
        self._save_index()

    def _generate_id(self, name: str) -> str:
        """Generate a unique checkpoint ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"{name}_{timestamp}"

    def _compute_hash(self, state: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of state data."""
        state_json = json.dumps(state, sort_keys=True)
        return hashlib.sha256(state_json.encode()).hexdigest()[:16]

    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get file path for a checkpoint."""
        safe_id = checkpoint_id.replace("/", "_").replace("\\", "_")
        return self._storage_path / f"{safe_id}.checkpoint.json"

    def save(
        self,
        name: str,
        state: Dict[str, Any],
        checkpoint_type: CheckpointType = CheckpointType.MANUAL,
        description: str = "",
        parent_id: Optional[str] = None,
    ) -> str:
        """
        Save a checkpoint.

        Args:
            name: Human-readable name for the checkpoint
            state: State dictionary to checkpoint (must be JSON-serializable)
            checkpoint_type: Type of checkpoint
            description: Optional description
            parent_id: ID of parent checkpoint (for checkpoint chains)

        Returns:
            Checkpoint ID

        Raises:
            ValueError: If state is not JSON-serializable
        """
        with self._lock:
            # Generate ID
            checkpoint_id = self._generate_id(name)

            # Compute hash
            state_hash = self._compute_hash(state)

            # Create metadata
            metadata = CheckpointMetadata(
                checkpoint_id=checkpoint_id,
                timestamp=datetime.now().isoformat(),
                checkpoint_type=checkpoint_type.value,
                node_id=self._node_id,
                description=description,
                hash=state_hash,
                size_bytes=len(json.dumps(state)),
                parent_checkpoint_id=parent_id,
            )

            # Create checkpoint
            checkpoint = Checkpoint(metadata=metadata, state=state)

            # Write to disk
            cp_path = self._get_checkpoint_path(checkpoint_id)
            with open(cp_path, 'w') as f:
                json.dump(checkpoint.to_dict(), f, indent=2)

            # Update index
            self._index[checkpoint_id] = metadata
            self._save_index()

            # Cleanup old checkpoints if needed
            if self._auto_cleanup:
                self._cleanup_old_checkpoints(name)

            return checkpoint_id

    def load(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a checkpoint's state.

        Args:
            checkpoint_id: ID of the checkpoint to load

        Returns:
            State dictionary or None if not found
        """
        with self._lock:
            cp_path = self._get_checkpoint_path(checkpoint_id)
            if not cp_path.exists():
                return None

            try:
                with open(cp_path, 'r') as f:
                    data = json.load(f)
                    checkpoint = Checkpoint.from_dict(data)
                    return checkpoint.state
            except (json.JSONDecodeError, KeyError):
                return None

    def load_latest(self, name_prefix: str) -> Optional[Dict[str, Any]]:
        """
        Load the most recent checkpoint matching a name prefix.

        Args:
            name_prefix: Prefix to match checkpoint names

        Returns:
            State dictionary or None if no matching checkpoint found
        """
        with self._lock:
            matching = [
                (cp_id, meta) for cp_id, meta in self._index.items()
                if cp_id.startswith(name_prefix)
            ]

            if not matching:
                return None

            # Sort by timestamp (embedded in ID)
            matching.sort(key=lambda x: x[1].timestamp, reverse=True)
            latest_id = matching[0][0]

            return self.load(latest_id)

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """
        Get a full checkpoint including metadata.

        Args:
            checkpoint_id: ID of the checkpoint

        Returns:
            Checkpoint object or None if not found
        """
        with self._lock:
            cp_path = self._get_checkpoint_path(checkpoint_id)
            if not cp_path.exists():
                return None

            try:
                with open(cp_path, 'r') as f:
                    data = json.load(f)
                    return Checkpoint.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                return None

    def delete(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint.

        Args:
            checkpoint_id: ID of the checkpoint to delete

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            cp_path = self._get_checkpoint_path(checkpoint_id)

            if checkpoint_id in self._index:
                del self._index[checkpoint_id]
                self._save_index()

            if cp_path.exists():
                cp_path.unlink()
                return True

            return False

    def list_checkpoints(
        self,
        name_prefix: Optional[str] = None,
        node_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[CheckpointMetadata]:
        """
        List checkpoints matching criteria.

        Args:
            name_prefix: Filter by checkpoint name prefix
            node_id: Filter by node ID
            limit: Maximum number of results

        Returns:
            List of checkpoint metadata
        """
        with self._lock:
            results = []

            for cp_id, meta in self._index.items():
                if name_prefix and not cp_id.startswith(name_prefix):
                    continue
                if node_id and meta.node_id != node_id:
                    continue
                results.append(meta)

            # Sort by timestamp descending
            results.sort(key=lambda x: x.timestamp, reverse=True)

            return results[:limit]

    def _cleanup_old_checkpoints(self, name_prefix: str):
        """Remove old checkpoints beyond max_checkpoints."""
        matching = self.list_checkpoints(name_prefix=name_prefix)

        if len(matching) > self._max_checkpoints:
            # Delete oldest checkpoints
            for meta in matching[self._max_checkpoints:]:
                self.delete(meta.checkpoint_id)

    def verify(self, checkpoint_id: str) -> bool:
        """
        Verify checkpoint integrity.

        Args:
            checkpoint_id: ID of the checkpoint to verify

        Returns:
            True if checkpoint is valid, False otherwise
        """
        with self._lock:
            checkpoint = self.get_checkpoint(checkpoint_id)
            if not checkpoint:
                return False

            # Verify hash
            computed_hash = self._compute_hash(checkpoint.state)
            return computed_hash == checkpoint.metadata.hash

    def get_checkpoint_chain(self, checkpoint_id: str) -> List[CheckpointMetadata]:
        """
        Get the chain of checkpoints leading to this one.

        Args:
            checkpoint_id: ID of the checkpoint

        Returns:
            List of checkpoint metadata from oldest to newest
        """
        with self._lock:
            chain = []
            current_id = checkpoint_id

            while current_id:
                if current_id not in self._index:
                    break

                meta = self._index[current_id]
                chain.append(meta)
                current_id = meta.parent_checkpoint_id

            chain.reverse()
            return chain


class PeriodicCheckpointer:
    """
    Utility class for automatic periodic checkpointing.

    Usage:
        checkpointer = PeriodicCheckpointer(
            manager=checkpoint_mgr,
            name="job_123",
            interval_sec=30,
            state_func=lambda: get_current_state(),
        )
        checkpointer.start()

        # Later...
        checkpointer.stop()
    """

    def __init__(
        self,
        manager: CheckpointManager,
        name: str,
        interval_sec: float,
        state_func: Callable[[], Dict[str, Any]],
        description: str = "Periodic checkpoint",
    ):
        """
        Initialize the periodic checkpointer.

        Args:
            manager: CheckpointManager instance
            name: Base name for checkpoints
            interval_sec: Interval between checkpoints
            state_func: Function that returns current state to checkpoint
            description: Description for checkpoints
        """
        self._manager = manager
        self._name = name
        self._interval = interval_sec
        self._state_func = state_func
        self._description = description
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_checkpoint_id: Optional[str] = None

    def start(self):
        """Start periodic checkpointing."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._checkpoint_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop periodic checkpointing."""
        if not self._running:
            return

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        self._running = False

    def _checkpoint_loop(self):
        """Main checkpoint loop."""
        while not self._stop_event.is_set():
            try:
                state = self._state_func()
                self._last_checkpoint_id = self._manager.save(
                    name=self._name,
                    state=state,
                    checkpoint_type=CheckpointType.PERIODIC,
                    description=self._description,
                    parent_id=self._last_checkpoint_id,
                )
            except Exception:
                pass  # Don't crash on checkpoint failure

            self._stop_event.wait(self._interval)

    @property
    def last_checkpoint_id(self) -> Optional[str]:
        """Get ID of the last checkpoint created."""
        return self._last_checkpoint_id

    @property
    def is_running(self) -> bool:
        """Check if checkpointing is active."""
        return self._running


class CheckpointMixin:
    """
    Mixin class for adding checkpoint support to ROS2 nodes.

    Usage:
        class MyNode(Node, CheckpointMixin):
            def __init__(self):
                super().__init__('my_node')
                self.init_checkpointing(interval_sec=30)

            def get_checkpoint_state(self) -> Dict[str, Any]:
                return {
                    "position": self.current_position,
                    "job_id": self.current_job_id,
                }

            def restore_from_checkpoint(self, state: Dict[str, Any]):
                self.current_position = state["position"]
                self.current_job_id = state["job_id"]
    """

    _checkpoint_manager: Optional[CheckpointManager] = None
    _periodic_checkpointer: Optional[PeriodicCheckpointer] = None
    _checkpoint_name: str = "node"

    def init_checkpointing(
        self,
        storage_path: str = "/var/lib/lego_mcp/checkpoints",
        interval_sec: float = 30.0,
        max_checkpoints: int = 10,
        auto_start: bool = True,
    ):
        """
        Initialize checkpointing for this node.

        Args:
            storage_path: Directory for checkpoint storage
            interval_sec: Interval for periodic checkpoints (0 to disable)
            max_checkpoints: Maximum checkpoints to retain
            auto_start: Automatically start periodic checkpointing
        """
        node_id = self.get_name() if hasattr(self, 'get_name') else "unknown"
        self._checkpoint_name = node_id

        self._checkpoint_manager = CheckpointManager(
            storage_path=storage_path,
            max_checkpoints=max_checkpoints,
            node_id=node_id,
        )

        if interval_sec > 0:
            self._periodic_checkpointer = PeriodicCheckpointer(
                manager=self._checkpoint_manager,
                name=self._checkpoint_name,
                interval_sec=interval_sec,
                state_func=self.get_checkpoint_state,
            )

            if auto_start:
                self._periodic_checkpointer.start()

    def get_checkpoint_state(self) -> Dict[str, Any]:
        """
        Get the current state to checkpoint.
        Override in subclass.

        Returns:
            State dictionary (must be JSON-serializable)
        """
        return {}

    def restore_from_checkpoint(self, state: Dict[str, Any]):
        """
        Restore node state from checkpoint.
        Override in subclass.

        Args:
            state: State dictionary from checkpoint
        """
        pass

    def create_checkpoint(
        self,
        description: str = "",
        checkpoint_type: CheckpointType = CheckpointType.MANUAL,
    ) -> Optional[str]:
        """
        Create a manual checkpoint.

        Args:
            description: Optional description
            checkpoint_type: Type of checkpoint

        Returns:
            Checkpoint ID or None if checkpointing not initialized
        """
        if not self._checkpoint_manager:
            return None

        state = self.get_checkpoint_state()
        return self._checkpoint_manager.save(
            name=self._checkpoint_name,
            state=state,
            checkpoint_type=checkpoint_type,
            description=description,
        )

    def restore_latest_checkpoint(self) -> bool:
        """
        Restore from the most recent checkpoint.

        Returns:
            True if restored, False if no checkpoint found
        """
        if not self._checkpoint_manager:
            return False

        state = self._checkpoint_manager.load_latest(self._checkpoint_name)
        if state:
            self.restore_from_checkpoint(state)
            return True
        return False

    def shutdown_checkpointing(self):
        """Stop checkpointing and cleanup."""
        if self._periodic_checkpointer:
            self._periodic_checkpointer.stop()
            self._periodic_checkpointer = None
