"""
LEGO MCP Security Package

SROS2 Security Framework implementing:
- IEC 62443 compliant security zones
- NIST 800-82 industrial cybersecurity
- DDS encryption and authentication
- Security audit pipeline
- Intrusion detection

Industry 4.0/5.0 Architecture - ISA-95 Security Layer
"""

from .sros2_manager import SROS2Manager, SecurityZone, SecurityLevel
from .security_zones import IEC62443ZoneManager
from .access_control import AccessControlManager
from .audit_pipeline import SecurityAuditPipeline, SecurityEvent, SecuritySeverity
from .intrusion_detector import IntrusionDetector
from .compliance_checker import (
    IEC62443ComplianceChecker,
    ComplianceLevel,
    ComplianceReport,
    FunctionalRequirement,
)

__all__ = [
    # Core managers
    'SROS2Manager',
    'SecurityZone',
    'SecurityLevel',
    'IEC62443ZoneManager',
    'AccessControlManager',
    # Audit pipeline
    'SecurityAuditPipeline',
    'SecurityEvent',
    'SecuritySeverity',
    # Intrusion detection
    'IntrusionDetector',
    # Compliance
    'IEC62443ComplianceChecker',
    'ComplianceLevel',
    'ComplianceReport',
    'FunctionalRequirement',
]
