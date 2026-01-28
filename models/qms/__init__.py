"""
LEGO Factory v3 - QMS Models
=============================
Quality Management System data models.
"""

from models.qms.documents import (
    Document,
    DocumentCategory,
    DocumentRevision,
    DocumentFile,
    DocumentApproval,
    ESignature,
    DocumentType,
    DocumentStatus,
    ApprovalStatus,
)

from models.qms.ncr_capa import (
    NonConformanceReport,
    CAPA,
    CAPAAction,
    NCRStatus,
    NCRType,
    DispositionType,
    Severity,
    CAPAType,
    CAPAStatus,
)

from models.qms.quality import (
    Audit,
    AuditFinding,
    TrainingCourse,
    TrainingRecord,
    CalibratedEquipment,
    CalibrationRecord,
    SPCChart,
    SPCData,
    AuditType,
    AuditStatus,
    FindingSeverity,
    TrainingStatus,
    CalibrationStatus,
)

from models.qms.supplier_quality import (
    SupplierQualityRating,
    InspectionPlan,
    InspectionCharacteristic,
    InspectionRecord,
    InspectionMeasurement,
    SupplierGrade,
    InspectionType,
    InspectionResult,
    CharacteristicType,
)

__all__ = [
    # Documents
    'Document',
    'DocumentCategory',
    'DocumentRevision',
    'DocumentFile',
    'DocumentApproval',
    'ESignature',
    'DocumentType',
    'DocumentStatus',
    'ApprovalStatus',
    # NCR/CAPA
    'NonConformanceReport',
    'CAPA',
    'CAPAAction',
    'NCRStatus',
    'NCRType',
    'DispositionType',
    'Severity',
    'CAPAType',
    'CAPAStatus',
    # Audit
    'Audit',
    'AuditFinding',
    'AuditType',
    'AuditStatus',
    'FindingSeverity',
    # Training
    'TrainingCourse',
    'TrainingRecord',
    'TrainingStatus',
    # Calibration
    'CalibratedEquipment',
    'CalibrationRecord',
    'CalibrationStatus',
    # SPC
    'SPCChart',
    'SPCData',
    # Supplier Quality
    'SupplierQualityRating',
    'InspectionPlan',
    'InspectionCharacteristic',
    'InspectionRecord',
    'InspectionMeasurement',
    'SupplierGrade',
    'InspectionType',
    'InspectionResult',
    'CharacteristicType',
]
