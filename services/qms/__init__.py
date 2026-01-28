"""
LEGO Factory v3 - QMS Services
===============================
Quality Management System services.

Includes:
- Document Control (21 CFR Part 11 compliant)
- NCR/CAPA Management
- Electronic Signatures (21 CFR Part 11)
- SPC (Statistical Process Control)
"""

from services.qms.document_service import DocumentService, get_document_service
from services.qms.ncr_service import NCRService, get_ncr_service
from services.qms.spc_service import SPCService, create_spc_service
from services.qms.inspection_service import InspectionService, create_inspection_service

# Import advanced QMS services
try:
    from services.advanced.compliance.electronic_signature import (
        ElectronicSignatureService,
        SignatureMeaning,
        SignatureStatus,
    )
    from services.advanced.quality.spc_service import (
        AdvancedSPCService,
        ControlLimits,
    )
except ImportError:
    # Advanced services may not be available in minimal deployments
    ElectronicSignatureService = None
    AdvancedSPCService = None
    ControlLimits = None

__all__ = [
    # Document Service
    'DocumentService',
    'get_document_service',
    # NCR/CAPA Service
    'NCRService',
    'get_ncr_service',
    # SPC Service (Western Electric rules)
    'SPCService',
    'create_spc_service',
    # Inspection Service (auto-NCR)
    'InspectionService',
    'create_inspection_service',
    # Electronic Signatures (21 CFR Part 11)
    'ElectronicSignatureService',
    'SignatureMeaning',
    'SignatureStatus',
    # Advanced SPC
    'AdvancedSPCService',
    'ControlLimits',
]
