"""
Digital Twin Synchronization Services.

This module provides real-time synchronization for manufacturing digital twins:
- CRDT-based conflict resolution for distributed state
- Event sourcing for complete audit trail
- Formal state machine verification

Research Value:
- Novel CRDT types for manufacturing state
- Formal methods for digital twin correctness
- Distributed consensus for edge-cloud sync
"""

from .conflict_resolver import (
    CRDTConflictResolver,
    GCounter,
    PNCounter,
    LWWRegister,
    ORSet,
    MVRegister,
    CRDTState
)
from .event_sourcing import (
    EventStore,
    DomainEvent,
    EventStream,
    Aggregate,
    Snapshot
)
from .state_machine import (
    StateMachine,
    State,
    Transition,
    Guard,
    Action,
    StateMachineVerifier
)

__all__ = [
    # CRDT
    'CRDTConflictResolver',
    'GCounter',
    'PNCounter',
    'LWWRegister',
    'ORSet',
    'MVRegister',
    'CRDTState',
    # Event Sourcing
    'EventStore',
    'DomainEvent',
    'EventStream',
    'Aggregate',
    'Snapshot',
    # State Machine
    'StateMachine',
    'State',
    'Transition',
    'Guard',
    'Action',
    'StateMachineVerifier',
]
