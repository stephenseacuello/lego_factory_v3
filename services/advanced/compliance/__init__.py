"""
DoD/ONR Compliance Framework

Comprehensive compliance infrastructure for defense
manufacturing requirements.

Features:
- NIST 800-171 / CMMC Level 3 compliance
- ITAR / Export control handling
- CUI (Controlled Unclassified Information) management
- DFARS 252.204-7012 compliance
- Audit logging and evidence collection

Reference: NIST SP 800-171 Rev 2, CMMC 2.0, ITAR 22 CFR 120-130
"""

from .nist_800_171 import NISTComplianceChecker, ControlFamily, ControlStatus
from .cmmc import CMMCAssessment, CMMCLevel, CMMCDomain
from .cui_handler import CUIHandler, CUICategory, CUIMarking
from .audit_logger import ComplianceAuditLogger, AuditEvent, AuditSeverity
from .access_control import AccessController, ClearanceLevel, NeedToKnow
from .sbom_generator import (
    SBOMGenerator,
    SBOM,
    Component,
    ComponentType,
    SBOMFormat,
    create_sbom_generator,
)
from .code_signing import (
    ProductionCodeSigner,
    KeyPairManager,
    CosignIntegration,
    InTotoAttestation,
    SignedArtifact,
    VerificationResult,
    SignatureAlgorithm,
    ArtifactType,
    create_code_signer,
)

__all__ = [
    "NISTComplianceChecker",
    "ControlFamily",
    "ControlStatus",
    "CMMCAssessment",
    "CMMCLevel",
    "CMMCDomain",
    "CUIHandler",
    "CUICategory",
    "CUIMarking",
    "ComplianceAuditLogger",
    "AuditEvent",
    "AuditSeverity",
    "AccessController",
    "ClearanceLevel",
    "NeedToKnow",
    # SBOM Generator
    "SBOMGenerator",
    "SBOM",
    "Component",
    "ComponentType",
    "SBOMFormat",
    "create_sbom_generator",
    # Code Signing
    "ProductionCodeSigner",
    "KeyPairManager",
    "CosignIntegration",
    "InTotoAttestation",
    "SignedArtifact",
    "VerificationResult",
    "SignatureAlgorithm",
    "ArtifactType",
    "create_code_signer",
]
