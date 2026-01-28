"""
V8 Industrial Cybersecurity Services
=====================================

Implements IEC 62443 SL-3 compliant security framework for
DoD/ONR-class manufacturing and industrial control systems:

- Zero-Trust Architecture (NIST SP 800-207)
- Post-Quantum Cryptography (NIST FIPS 203/204/205)
- Hardware Security Module (HSM) Integration
- Security Anomaly Detection
- Role-Based Access Control (RBAC)
- JWT authentication with continuous validation

Reference Standards:
- IEC 62443 (Industrial Cybersecurity)
- NIST 800-171 (CUI Protection)
- CMMC Level 3 (DoD Cybersecurity)

Author: LEGO MCP Security Engineering
Version: 8.0.0
"""

from .iec62443_framework import (
    IEC62443SecurityService,
    create_security_service
)

from .rbac import (
    RBACService,
    Permission,
    Role,
    ResourceType,
    User,
    Session,
    AccessDecision,
    PolicyRule,
    RoleDefinition,
    get_rbac_service,
    create_user,
    check_permission,
    get_user_permissions,
    require_permission,
    require_role,
    require_any_role,
)

from .pq_crypto import (
    PQCryptoProvider,
    EncryptionMode,
    SignatureMode,
    KeyEncapsulation,
    DigitalSignature,
    HybridEncryption,
)

from .zero_trust import (
    ZeroTrustGateway,
    AuthenticationResult,
    AuthorizationDecision,
    TrustScore,
    DevicePosture,
    ContinuousAuth,
)

from .anomaly_detection import (
    SecurityAnomalyDetector,
    AnomalyType,
    AnomalySeverity,
    AnomalyResult,
    GeographicAnalyzer,
    TemporalAnalyzer,
    BehaviorAnalyzer,
)

__all__ = [
    # IEC 62443
    "IEC62443SecurityService",
    "create_security_service",

    # RBAC
    "RBACService",
    "Permission",
    "Role",
    "ResourceType",
    "User",
    "Session",
    "AccessDecision",
    "PolicyRule",
    "RoleDefinition",
    "get_rbac_service",
    "create_user",
    "check_permission",
    "get_user_permissions",
    "require_permission",
    "require_role",
    "require_any_role",

    # Post-Quantum Cryptography
    "PQCryptoProvider",
    "EncryptionMode",
    "SignatureMode",
    "KeyEncapsulation",
    "DigitalSignature",
    "HybridEncryption",

    # Zero Trust
    "ZeroTrustGateway",
    "AuthenticationResult",
    "AuthorizationDecision",
    "TrustScore",
    "DevicePosture",
    "ContinuousAuth",

    # Anomaly Detection
    "SecurityAnomalyDetector",
    "AnomalyType",
    "AnomalySeverity",
    "AnomalyResult",
    "GeographicAnalyzer",
    "TemporalAnalyzer",
    "BehaviorAnalyzer",
]

__version__ = "8.0.0"
