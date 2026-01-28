"""
Digital Thread Audit Chain - Tamper-Evident Audit Trail

LegoMCP World-Class Manufacturing System v5.0
Phase 15: Digital Thread with Cryptographic Hash Chain

Provides tamper-evident audit logging for manufacturing events using:
- Cryptographic hash chains (SHA-256)
- SQLite persistence
- Chain verification capability
- Entity history queries
- Support for work orders, parts, equipment, and quality events

Author: LegoMCP Team
Version: 2.0.0
"""

import hashlib
import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union
from uuid import uuid4

from .audit_event import (
    AuditEvent,
    AuditEventType,
    AuditChainStatus,
    EntityHistory,
    EntityType,
)

logger = logging.getLogger(__name__)


class DigitalThread:
    """
    Digital Thread with Tamper-Evident Audit Trail.

    Implements a cryptographic hash chain for audit events, ensuring
    that any modification to historical records can be detected.

    Features:
    - SHA-256 hash chain linking all events
    - SQLite persistence with proper indexing
    - Chain verification for tamper detection
    - Entity history queries
    - Thread-safe operations

    Usage:
        thread = DigitalThread(db_path="audit.db")

        # Log events
        thread.log_work_order_event(
            entity_id="WO-001",
            action="created",
            description="Work order created for LEGO brick batch",
            data={"quantity": 1000, "part_id": "3001"}
        )

        # Verify chain integrity
        status = thread.verify_chain()
        print(f"Chain valid: {status.is_valid}")

        # Query entity history
        history = thread.get_entity_history(EntityType.WORK_ORDER, "WO-001")
    """

    # Genesis block hash (first event links to this)
    GENESIS_HASH = hashlib.sha256(b"LEGO_MCP_GENESIS_BLOCK_V1").hexdigest()

    def __init__(
        self,
        db_path: Optional[str] = None,
        auto_verify: bool = False,
        verify_on_startup: bool = True,
    ):
        """
        Initialize the Digital Thread.

        Args:
            db_path: Path to SQLite database. Defaults to 'audit_chain.db' in current dir.
            auto_verify: If True, verify chain integrity after each write (slower but safer).
            verify_on_startup: If True, verify chain integrity when initialized.
        """
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "audit_chain.db"
        )
        self.auto_verify = auto_verify
        self._lock = threading.RLock()
        self._sequence_counter = 0
        self._last_hash = self.GENESIS_HASH

        # Initialize database
        self._init_database()

        # Load state from database
        self._load_chain_state()

        # Verify on startup if requested
        if verify_on_startup and self._sequence_counter > 0:
            status = self.verify_chain()
            if not status.is_valid:
                logger.error(
                    f"Chain verification failed on startup: {status.error_message}"
                )
                raise RuntimeError(
                    f"Audit chain integrity compromised: {status.error_message}"
                )
            logger.info(
                f"Chain verified on startup: {status.verified_events} events valid"
            )

    def _init_database(self) -> None:
        """Initialize SQLite database with required tables and indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Main audit events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    sequence_number INTEGER UNIQUE NOT NULL,
                    event_type TEXT NOT NULL,
                    event_subtype TEXT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    entity_name TEXT,
                    action TEXT NOT NULL,
                    description TEXT,
                    data TEXT,
                    metadata TEXT,
                    previous_value TEXT,
                    new_value TEXT,
                    user_id TEXT,
                    user_name TEXT,
                    session_id TEXT,
                    source_system TEXT,
                    source_ip TEXT,
                    timestamp TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    signature TEXT,
                    signature_algorithm TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Chain state table (stores current chain head)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chain_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    last_sequence INTEGER NOT NULL,
                    last_hash TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_entity
                ON audit_events(entity_type, entity_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON audit_events(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type
                ON audit_events(event_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user
                ON audit_events(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sequence
                ON audit_events(sequence_number)
            """)

            conn.commit()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with proper settings."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _load_chain_state(self) -> None:
        """Load the current chain state from the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT last_sequence, last_hash FROM chain_state WHERE id = 1"
            )
            row = cursor.fetchone()

            if row:
                self._sequence_counter = row['last_sequence']
                self._last_hash = row['last_hash']
            else:
                # Initialize chain state
                self._sequence_counter = 0
                self._last_hash = self.GENESIS_HASH
                cursor.execute(
                    """
                    INSERT INTO chain_state (id, last_sequence, last_hash)
                    VALUES (1, ?, ?)
                """,
                    (self._sequence_counter, self._last_hash),
                )
                conn.commit()

    def _update_chain_state(self, conn: sqlite3.Connection) -> None:
        """Update the chain state in the database."""
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE chain_state
            SET last_sequence = ?, last_hash = ?, updated_at = ?
            WHERE id = 1
        """,
            (self._sequence_counter, self._last_hash, datetime.utcnow().isoformat()),
        )

    def _save_event(self, event: AuditEvent) -> None:
        """Save an event to the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_events (
                    event_id, sequence_number, event_type, event_subtype,
                    entity_type, entity_id, entity_name, action, description,
                    data, metadata, previous_value, new_value,
                    user_id, user_name, session_id, source_system, source_ip,
                    timestamp, previous_hash, event_hash, signature, signature_algorithm
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    event.event_id,
                    event.sequence_number,
                    event.event_type.value,
                    event.event_subtype,
                    event.entity_type.value,
                    event.entity_id,
                    event.entity_name,
                    event.action,
                    event.description,
                    json.dumps(event.data),
                    json.dumps(event.metadata),
                    json.dumps(event.previous_value) if event.previous_value else None,
                    json.dumps(event.new_value) if event.new_value else None,
                    event.user_id,
                    event.user_name,
                    event.session_id,
                    event.source_system,
                    event.source_ip,
                    event.timestamp.isoformat(),
                    event.previous_hash,
                    event.event_hash,
                    event.signature,
                    event.signature_algorithm,
                ),
            )
            self._update_chain_state(conn)
            conn.commit()

    def _load_event(self, row: sqlite3.Row) -> AuditEvent:
        """Load an AuditEvent from a database row."""
        return AuditEvent(
            event_id=row['event_id'],
            sequence_number=row['sequence_number'],
            event_type=AuditEventType(row['event_type']),
            event_subtype=row['event_subtype'] or '',
            entity_type=EntityType(row['entity_type']),
            entity_id=row['entity_id'],
            entity_name=row['entity_name'] or '',
            action=row['action'],
            description=row['description'] or '',
            data=json.loads(row['data']) if row['data'] else {},
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
            previous_value=json.loads(row['previous_value']) if row['previous_value'] else None,
            new_value=json.loads(row['new_value']) if row['new_value'] else None,
            user_id=row['user_id'] or '',
            user_name=row['user_name'] or '',
            session_id=row['session_id'] or '',
            source_system=row['source_system'] or 'lego_mcp',
            source_ip=row['source_ip'] or '',
            timestamp=datetime.fromisoformat(row['timestamp']),
            previous_hash=row['previous_hash'],
            event_hash=row['event_hash'],
            signature=row['signature'] or '',
            signature_algorithm=row['signature_algorithm'] or 'sha256',
        )

    def log_event(
        self,
        event_type: AuditEventType,
        entity_type: EntityType,
        entity_id: str,
        action: str,
        description: str = "",
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        user_name: str = "",
        session_id: str = "",
        source_ip: str = "",
        entity_name: str = "",
        event_subtype: str = "",
    ) -> AuditEvent:
        """
        Log a new audit event to the chain.

        This is the primary method for adding events to the audit trail.
        Each event is linked to the previous event via cryptographic hash.

        Args:
            event_type: Type of event (from AuditEventType enum)
            entity_type: Type of entity affected (from EntityType enum)
            entity_id: Unique identifier of the affected entity
            action: Action performed (e.g., "created", "modified", "deleted")
            description: Human-readable description of the event
            data: Additional event data
            metadata: Event metadata
            previous_value: Previous state (for modifications)
            new_value: New state (for modifications)
            user_id: ID of user who triggered the event
            user_name: Name of user who triggered the event
            session_id: Session identifier
            source_ip: Source IP address
            entity_name: Human-readable name of the entity
            event_subtype: More specific event classification

        Returns:
            The created AuditEvent with computed hash
        """
        with self._lock:
            # Increment sequence number
            self._sequence_counter += 1

            # Create the event
            event = AuditEvent(
                event_id=str(uuid4()),
                sequence_number=self._sequence_counter,
                event_type=event_type,
                event_subtype=event_subtype,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
                action=action,
                description=description,
                data=data or {},
                metadata=metadata or {},
                previous_value=previous_value,
                new_value=new_value,
                user_id=user_id,
                user_name=user_name,
                session_id=session_id,
                source_system="lego_mcp",
                source_ip=source_ip,
                timestamp=datetime.utcnow(),
                previous_hash=self._last_hash,
                event_hash="",  # Will be computed
            )

            # Compute the hash
            event.event_hash = event.compute_hash()

            # Update chain state
            self._last_hash = event.event_hash

            # Save to database
            self._save_event(event)

            # Auto-verify if enabled
            if self.auto_verify:
                status = self.verify_chain()
                if not status.is_valid:
                    logger.error(f"Chain verification failed: {status.error_message}")

            logger.debug(
                f"Logged event {event.sequence_number}: {event.event_type.value} "
                f"on {entity_type.value}:{entity_id}"
            )

            return event

    # ===========================
    # Convenience logging methods
    # ===========================

    def log_work_order_event(
        self,
        entity_id: str,
        action: str,
        description: str = "",
        data: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        user_name: str = "",
        entity_name: str = "",
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log a work order event."""
        # Map action to event type
        event_type_map = {
            "created": AuditEventType.WORK_ORDER_CREATED,
            "started": AuditEventType.WORK_ORDER_STARTED,
            "completed": AuditEventType.WORK_ORDER_COMPLETED,
            "cancelled": AuditEventType.WORK_ORDER_CANCELLED,
            "modified": AuditEventType.WORK_ORDER_MODIFIED,
        }
        event_type = event_type_map.get(action, AuditEventType.WORK_ORDER_MODIFIED)

        return self.log_event(
            event_type=event_type,
            entity_type=EntityType.WORK_ORDER,
            entity_id=entity_id,
            action=action,
            description=description,
            data=data,
            user_id=user_id,
            user_name=user_name,
            entity_name=entity_name,
            previous_value=previous_value,
            new_value=new_value,
        )

    def log_part_event(
        self,
        entity_id: str,
        action: str,
        description: str = "",
        data: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        user_name: str = "",
        entity_name: str = "",
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log a part event."""
        event_type_map = {
            "created": AuditEventType.PART_CREATED,
            "modified": AuditEventType.PART_MODIFIED,
            "inspected": AuditEventType.PART_INSPECTED,
            "shipped": AuditEventType.PART_SHIPPED,
            "received": AuditEventType.PART_RECEIVED,
            "scrapped": AuditEventType.PART_SCRAPPED,
            "reworked": AuditEventType.PART_REWORKED,
        }
        event_type = event_type_map.get(action, AuditEventType.PART_MODIFIED)

        return self.log_event(
            event_type=event_type,
            entity_type=EntityType.PART,
            entity_id=entity_id,
            action=action,
            description=description,
            data=data,
            user_id=user_id,
            user_name=user_name,
            entity_name=entity_name,
            previous_value=previous_value,
            new_value=new_value,
        )

    def log_equipment_event(
        self,
        entity_id: str,
        action: str,
        description: str = "",
        data: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        user_name: str = "",
        entity_name: str = "",
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log an equipment event."""
        event_type_map = {
            "started": AuditEventType.EQUIPMENT_STARTED,
            "stopped": AuditEventType.EQUIPMENT_STOPPED,
            "maintenance": AuditEventType.EQUIPMENT_MAINTENANCE,
            "calibrated": AuditEventType.EQUIPMENT_CALIBRATED,
            "fault": AuditEventType.EQUIPMENT_FAULT,
            "parameter_change": AuditEventType.EQUIPMENT_PARAMETER_CHANGE,
        }
        event_type = event_type_map.get(action, AuditEventType.EQUIPMENT_PARAMETER_CHANGE)

        return self.log_event(
            event_type=event_type,
            entity_type=EntityType.EQUIPMENT,
            entity_id=entity_id,
            action=action,
            description=description,
            data=data,
            user_id=user_id,
            user_name=user_name,
            entity_name=entity_name,
            previous_value=previous_value,
            new_value=new_value,
        )

    def log_quality_event(
        self,
        entity_id: str,
        action: str,
        description: str = "",
        data: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        user_name: str = "",
        entity_name: str = "",
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log a quality event."""
        event_type_map = {
            "inspection": AuditEventType.QUALITY_INSPECTION,
            "defect_detected": AuditEventType.QUALITY_DEFECT_DETECTED,
            "hold_placed": AuditEventType.QUALITY_HOLD_PLACED,
            "hold_released": AuditEventType.QUALITY_HOLD_RELEASED,
            "ncr_created": AuditEventType.QUALITY_NCR_CREATED,
            "capa_initiated": AuditEventType.QUALITY_CAPA_INITIATED,
        }
        event_type = event_type_map.get(action, AuditEventType.QUALITY_INSPECTION)

        return self.log_event(
            event_type=event_type,
            entity_type=EntityType.QUALITY_RECORD,
            entity_id=entity_id,
            action=action,
            description=description,
            data=data,
            user_id=user_id,
            user_name=user_name,
            entity_name=entity_name,
            previous_value=previous_value,
            new_value=new_value,
        )

    def log_material_event(
        self,
        entity_id: str,
        action: str,
        description: str = "",
        data: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        user_name: str = "",
        entity_name: str = "",
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log a material event."""
        event_type_map = {
            "received": AuditEventType.MATERIAL_RECEIVED,
            "consumed": AuditEventType.MATERIAL_CONSUMED,
            "lot_created": AuditEventType.MATERIAL_LOT_CREATED,
            "quarantined": AuditEventType.MATERIAL_QUARANTINED,
        }
        event_type = event_type_map.get(action, AuditEventType.MATERIAL_RECEIVED)

        return self.log_event(
            event_type=event_type,
            entity_type=EntityType.MATERIAL,
            entity_id=entity_id,
            action=action,
            description=description,
            data=data,
            user_id=user_id,
            user_name=user_name,
            entity_name=entity_name,
            previous_value=previous_value,
            new_value=new_value,
        )

    # ===========================
    # Chain Verification
    # ===========================

    def verify_chain(
        self,
        start_sequence: int = 1,
        end_sequence: Optional[int] = None,
    ) -> AuditChainStatus:
        """
        Verify the integrity of the audit chain.

        Checks that:
        1. Each event's hash matches its computed hash (no tampering)
        2. Each event's previous_hash matches the previous event's hash (chain intact)

        Args:
            start_sequence: Start verification from this sequence number
            end_sequence: End verification at this sequence number (None = end of chain)

        Returns:
            AuditChainStatus indicating verification result
        """
        status = AuditChainStatus()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get events in sequence order
            if end_sequence:
                cursor.execute(
                    """
                    SELECT * FROM audit_events
                    WHERE sequence_number >= ? AND sequence_number <= ?
                    ORDER BY sequence_number ASC
                """,
                    (start_sequence, end_sequence),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM audit_events
                    WHERE sequence_number >= ?
                    ORDER BY sequence_number ASC
                """,
                    (start_sequence,),
                )

            rows = cursor.fetchall()
            status.total_events = len(rows)

            if not rows:
                status.verified_events = 0
                return status

            # Get the expected previous hash for the first event
            if start_sequence == 1:
                expected_prev_hash = self.GENESIS_HASH
            else:
                cursor.execute(
                    "SELECT event_hash FROM audit_events WHERE sequence_number = ?",
                    (start_sequence - 1,),
                )
                prev_row = cursor.fetchone()
                if not prev_row:
                    status.is_valid = False
                    status.error_message = f"Cannot find event before sequence {start_sequence}"
                    return status
                expected_prev_hash = prev_row['event_hash']

            # Verify each event
            for row in rows:
                event = self._load_event(row)

                # Check previous hash link
                if event.previous_hash != expected_prev_hash:
                    status.is_valid = False
                    status.first_invalid_sequence = event.sequence_number
                    status.first_invalid_event_id = event.event_id
                    status.error_message = (
                        f"Chain broken at sequence {event.sequence_number}: "
                        f"expected previous_hash {expected_prev_hash[:16]}..., "
                        f"got {event.previous_hash[:16]}..."
                    )
                    return status

                # Verify event hash
                if not event.verify_hash():
                    status.is_valid = False
                    status.first_invalid_sequence = event.sequence_number
                    status.first_invalid_event_id = event.event_id
                    status.error_message = (
                        f"Hash mismatch at sequence {event.sequence_number}: "
                        f"event has been tampered with"
                    )
                    return status

                # Update expected previous hash for next iteration
                expected_prev_hash = event.event_hash
                status.verified_events += 1

        logger.info(f"Chain verification complete: {status.verified_events} events verified")
        return status

    def verify_event(self, event_id: str) -> Tuple[bool, str]:
        """
        Verify a single event's integrity.

        Args:
            event_id: The event ID to verify

        Returns:
            Tuple of (is_valid, error_message)
        """
        event = self.get_event(event_id)
        if not event:
            return False, f"Event {event_id} not found"

        if not event.verify_hash():
            return False, "Event hash does not match computed hash"

        # Verify chain link
        if event.sequence_number == 1:
            expected_prev = self.GENESIS_HASH
        else:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT event_hash FROM audit_events WHERE sequence_number = ?",
                    (event.sequence_number - 1,),
                )
                row = cursor.fetchone()
                if not row:
                    return False, f"Previous event (sequence {event.sequence_number - 1}) not found"
                expected_prev = row['event_hash']

        if event.previous_hash != expected_prev:
            return False, "Previous hash does not match chain"

        return True, ""

    # ===========================
    # Query Methods
    # ===========================

    def get_event(self, event_id: str) -> Optional[AuditEvent]:
        """Get a specific event by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_events WHERE event_id = ?", (event_id,))
            row = cursor.fetchone()
            if row:
                return self._load_event(row)
        return None

    def get_event_by_sequence(self, sequence_number: int) -> Optional[AuditEvent]:
        """Get a specific event by sequence number."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM audit_events WHERE sequence_number = ?",
                (sequence_number,),
            )
            row = cursor.fetchone()
            if row:
                return self._load_event(row)
        return None

    def get_entity_history(
        self,
        entity_type: EntityType,
        entity_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> EntityHistory:
        """
        Get the complete history of an entity.

        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            EntityHistory containing all events for the entity
        """
        history = EntityHistory(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name="",
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Build query
            query = """
                SELECT * FROM audit_events
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY sequence_number ASC
            """
            params: List[Any] = [entity_type.value, entity_id]

            if limit:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            for row in rows:
                event = self._load_event(row)
                history.events.append(event)

                # Update entity name from first event that has it
                if not history.entity_name and event.entity_name:
                    history.entity_name = event.entity_name

            if history.events:
                history.first_event_timestamp = history.events[0].timestamp
                history.last_event_timestamp = history.events[-1].timestamp

            # Get total count
            cursor.execute(
                """
                SELECT COUNT(*) FROM audit_events
                WHERE entity_type = ? AND entity_id = ?
            """,
                (entity_type.value, entity_id),
            )
            history.total_events = cursor.fetchone()[0]

        return history

    def query_events(
        self,
        entity_type: Optional[EntityType] = None,
        entity_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """
        Query events with filters.

        Args:
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            event_type: Filter by event type
            user_id: Filter by user ID
            start_time: Filter events after this time
            end_time: Filter events before this time
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List of matching AuditEvents
        """
        conditions = []
        params: List[Any] = []

        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type.value)

        if entity_id:
            conditions.append("entity_id = ?")
            params.append(entity_id)

        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type.value)

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())

        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"""
            SELECT * FROM audit_events
            WHERE {where_clause}
            ORDER BY sequence_number DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        events = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor.fetchall():
                events.append(self._load_event(row))

        return events

    def get_recent_events(self, limit: int = 50) -> List[AuditEvent]:
        """Get the most recent events."""
        return self.query_events(limit=limit)

    def get_events_for_timerange(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> List[AuditEvent]:
        """Get all events within a time range."""
        return self.query_events(start_time=start_time, end_time=end_time, limit=10000)

    # ===========================
    # Statistics and Summary
    # ===========================

    def get_chain_statistics(self) -> Dict[str, Any]:
        """Get statistics about the audit chain."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total events
            cursor.execute("SELECT COUNT(*) FROM audit_events")
            total_events = cursor.fetchone()[0]

            # Events by type
            cursor.execute("""
                SELECT event_type, COUNT(*) as count
                FROM audit_events
                GROUP BY event_type
            """)
            events_by_type = {row['event_type']: row['count'] for row in cursor.fetchall()}

            # Events by entity type
            cursor.execute("""
                SELECT entity_type, COUNT(*) as count
                FROM audit_events
                GROUP BY entity_type
            """)
            events_by_entity = {row['entity_type']: row['count'] for row in cursor.fetchall()}

            # Date range
            cursor.execute("""
                SELECT MIN(timestamp) as first, MAX(timestamp) as last
                FROM audit_events
            """)
            date_row = cursor.fetchone()

            # Recent activity
            cursor.execute("""
                SELECT COUNT(*) FROM audit_events
                WHERE timestamp >= datetime('now', '-24 hours')
            """)
            events_last_24h = cursor.fetchone()[0]

        return {
            'total_events': total_events,
            'current_sequence': self._sequence_counter,
            'last_hash': self._last_hash[:32] + '...',
            'events_by_type': events_by_type,
            'events_by_entity': events_by_entity,
            'first_event': date_row['first'] if date_row else None,
            'last_event': date_row['last'] if date_row else None,
            'events_last_24h': events_last_24h,
            'genesis_hash': self.GENESIS_HASH[:32] + '...',
        }

    def export_chain(
        self,
        output_path: str,
        start_sequence: int = 1,
        end_sequence: Optional[int] = None,
    ) -> int:
        """
        Export the audit chain to a JSON file.

        Args:
            output_path: Path to output file
            start_sequence: Start from this sequence number
            end_sequence: End at this sequence number

        Returns:
            Number of events exported
        """
        events = []

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if end_sequence:
                cursor.execute(
                    """
                    SELECT * FROM audit_events
                    WHERE sequence_number >= ? AND sequence_number <= ?
                    ORDER BY sequence_number ASC
                """,
                    (start_sequence, end_sequence),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM audit_events
                    WHERE sequence_number >= ?
                    ORDER BY sequence_number ASC
                """,
                    (start_sequence,),
                )

            for row in cursor.fetchall():
                event = self._load_event(row)
                events.append(event.to_dict())

        export_data = {
            'export_timestamp': datetime.utcnow().isoformat(),
            'genesis_hash': self.GENESIS_HASH,
            'total_events': len(events),
            'events': events,
        }

        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Exported {len(events)} events to {output_path}")
        return len(events)


# Singleton instance
_digital_thread_instance: Optional[DigitalThread] = None
_instance_lock = threading.Lock()


def get_digital_thread(
    db_path: Optional[str] = None,
    auto_verify: bool = False,
) -> DigitalThread:
    """
    Get or create the singleton DigitalThread instance.

    Args:
        db_path: Path to SQLite database (only used on first call)
        auto_verify: Enable auto-verification (only used on first call)

    Returns:
        The DigitalThread singleton instance
    """
    global _digital_thread_instance

    if _digital_thread_instance is None:
        with _instance_lock:
            if _digital_thread_instance is None:
                _digital_thread_instance = DigitalThread(
                    db_path=db_path,
                    auto_verify=auto_verify,
                )

    return _digital_thread_instance
