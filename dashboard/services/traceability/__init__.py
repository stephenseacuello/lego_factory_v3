"""
Traceability Services - Digital Thread & Audit Trail
=====================================================

LEGO MCP DoD/ONR-Class Manufacturing System v8.0
Phase 15: Digital Thread & Traceability (Enhanced for ISO 23247)

This module provides complete manufacturing traceability:
- Product genealogy with 3D visualization
- Tamper-evident audit trail with cryptographic hash chains
- Material lot tracking
- Process parameter history
- Quality event linkage
- Root cause analysis
- Supply chain correlation

V8.0 Features:
- HSM-backed audit sealing for daily chain verification
- FIPS 140-3 compliant cryptographic operations
- Tamper detection with automatic alerting
- Compliance with CMMC AU.2.041-AU.2.044

Reference: ISO 23247, NIST SP 800-171 (AU controls), IEC 62443
"""

# Digital Thread Service - Product Genealogy
from .digital_thread import (
    DigitalThreadService,
    get_digital_thread_service,
    ThreadEventType,
    ThreadVisualizationType,
    SpatialPosition,
    ThreadEvent,
    MaterialConsumption,
    ProcessSnapshot,
    QualityEvent,
    ProductGenealogy,
)

# Audit Event - Tamper-Evident Event Model
from .audit_event import (
    AuditEvent,
    AuditEventType,
    AuditChainStatus,
    EntityHistory,
    EntityType,
)

# Digital Thread Audit Chain - Hash Chain Implementation
from .audit_chain import (
    DigitalThread,
    get_digital_thread,
)

# V8 HSM-Backed Audit Sealing
try:
    from .hsm_sealer import (
        HSMSealer,
        SealedAuditRecord,
        SealVerificationResult,
        DailySeal,
        SealingSchedule,
        TamperDetection,
        create_hsm_sealer,
    )
except ImportError:
    HSMSealer = None
    SealedAuditRecord = None
    SealVerificationResult = None
    DailySeal = None
    SealingSchedule = None
    TamperDetection = None
    create_hsm_sealer = None

__all__ = [
    # Product Genealogy
    "DigitalThreadService",
    "get_digital_thread_service",
    "ThreadEventType",
    "ThreadVisualizationType",
    "SpatialPosition",
    "ThreadEvent",
    "MaterialConsumption",
    "ProcessSnapshot",
    "QualityEvent",
    "ProductGenealogy",
    # Audit Trail
    "AuditEvent",
    "AuditEventType",
    "AuditChainStatus",
    "EntityHistory",
    "EntityType",
    # Hash Chain
    "DigitalThread",
    "get_digital_thread",
    # V8 HSM Sealing
    "HSMSealer",
    "SealedAuditRecord",
    "SealVerificationResult",
    "DailySeal",
    "SealingSchedule",
    "TamperDetection",
    "create_hsm_sealer",
]

__version__ = "8.0.0"
