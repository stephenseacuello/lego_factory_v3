"""
LEGO Factory v3 - Models Package
================================
All SQLAlchemy models for the LEGO Factory system.
"""

from models.base import Base, BaseModel, AuditedModel, VersionedModel

# SCADA Models
from models.scada import (
    Machine, MachineEvent, MachineType, MachineState, ControllerType, ConnectionType,
    Tag, TagValue, TagGroup, TagDataType, TagCategory, TagQuality,
    AlarmDefinition, AlarmEvent, AlarmShelveLog, AlarmGroup,
    AlarmPriority, AlarmClass, AlarmType, AlarmState,
    MasterRecipe, ControlRecipe, RecipeApproval, RecipeParameter,
    RecipeType, RecipeStatus, ApprovalStatus,
)

# MES Models
from models.mes import (
    WorkOrder, Operation, Job, WorkOrderStatus, JobStatus, OperationType,
    Worker, Skill, TimeEntry, WorkerStatus, SkillLevel,
    DowntimeEvent, ProductionCount, OEERecord, DowntimeReason,
    Shift, ShiftAssignment, DispatchQueue, ProductionSchedule,
    ShiftType, DispatchPriority, DispatchStatus,
)

# ERP Models
from models.erp import (
    # Items
    Item, ItemCategory, UnitOfMeasure, BOMLine, Routing, RoutingOperation,
    ItemType, ItemStatus, CostingMethod,
    # Partners
    Partner, Contact, PartnerAddress, VendorItem, PriceList, PriceListItem,
    PartnerType, PartnerStatus, PaymentTerms,
    # Inventory
    Location, Bin, Lot, SerialNumber, InventoryBalance, InventoryTransaction,
    LocationType, TransactionType, LotStatus,
    # Sales
    SalesQuote, SalesQuoteLine, SalesOrder, SalesOrderLine,
    Shipment, ShipmentLine, SalesOrderStatus, QuoteStatus, ShipmentStatus,
    # Purchasing
    PurchaseRequisition, PurchaseRequisitionLine, PurchaseOrder, PurchaseOrderLine,
    Receipt, ReceiptLine, RequisitionStatus, PurchaseOrderStatus, ReceiptStatus,
    # Financial
    FiscalYear, FiscalPeriod, GLAccount, JournalEntry, JournalLine,
    APInvoice, APInvoiceLine, ARInvoice, ARInvoiceLine,
    Payment, PaymentApplication, AccountType, AccountCategory,
    JournalStatus, InvoiceStatus,
    # Planning
    CostCenter, Budget, DemandForecast, MRPRun, PlannedOrder,
    BudgetStatus, ForecastMethod,
)

# QMS Models
from models.qms import (
    Document, DocumentCategory, DocumentRevision, DocumentFile,
    DocumentApproval, ESignature, DocumentType, DocumentStatus,
    ApprovalStatus as QMSApprovalStatus,
    NonConformanceReport, CAPA, CAPAAction, NCRStatus, NCRType,
    DispositionType, Severity, CAPAType, CAPAStatus,
    Audit, AuditFinding, AuditType, AuditStatus, FindingSeverity,
    TrainingCourse, TrainingRecord, TrainingStatus,
    CalibratedEquipment, CalibrationRecord, CalibrationStatus,
    SPCChart, SPCData,
    # Supplier Quality
    SupplierQualityRating, InspectionPlan, InspectionCharacteristic,
    InspectionRecord, InspectionMeasurement,
    SupplierGrade, InspectionType, InspectionResult, CharacteristicType,
)

# CMMS Models
from models.cmms import (
    Asset, AssetClass, Meter, MeterReading, Spare, AssetSpare,
    AssetStatus, AssetCriticality, MeterType,
    MaintenanceWorkOrder, PMSchedule, TaskTemplate,
    WorkOrderTask, WorkOrderLabor, WorkOrderMaterial,
    WorkOrderType, WorkOrderStatus as CMMSWorkOrderStatus, WorkOrderPriority, PMTriggerType,
    # Failure Analysis
    FailureCode, FailureAnalysis, FailureHistory, FailureType, FailureSeverity,
)

# LEGO Models
from models.lego import (
    BrickType, ExportFormat, ExportStatus, PrinterType,
    BrickDesign, BrickExportJob, BrickColor,
    # Printing
    PrintProfile, FilamentInventory, BrickTemplate, PrintJob,
    FilamentType, PrintQuality,
    # Parts Catalog
    PartCategory, MaterialType, ProcessType,
    LegoPart, LegoMaterial, LegoProductColor, LegoProduct,
    LegoProductBOM, LegoRouting, LegoRoutingOperation,
)

# ML Models
from models.ml import (
    ModelType, ModelStatus, InferenceStatus, TrainingStatus, AnomalyType,
    MLModel, TrainingRun, InferenceJob, Prediction,
    GCodeFingerprint, ToolWearPrediction,
)

# Auth Models
from models.auth import (
    User, UserRole, TokenBlocklist, UserStatus,
)

__all__ = [
    # Base
    'Base', 'BaseModel', 'AuditedModel', 'VersionedModel',

    # SCADA
    'Machine', 'MachineEvent', 'MachineType', 'MachineState', 'ControllerType', 'ConnectionType',
    'Tag', 'TagValue', 'TagGroup', 'TagDataType', 'TagCategory', 'TagQuality',
    'AlarmDefinition', 'AlarmEvent', 'AlarmShelveLog', 'AlarmGroup',
    'AlarmPriority', 'AlarmClass', 'AlarmType', 'AlarmState',
    'MasterRecipe', 'ControlRecipe', 'RecipeApproval', 'RecipeParameter',
    'RecipeType', 'RecipeStatus', 'ApprovalStatus',

    # MES
    'WorkOrder', 'Operation', 'Job', 'WorkOrderStatus', 'JobStatus', 'OperationType',
    'Worker', 'Skill', 'TimeEntry', 'WorkerStatus', 'SkillLevel',
    'DowntimeEvent', 'ProductionCount', 'OEERecord', 'DowntimeReason',
    'Shift', 'ShiftAssignment', 'DispatchQueue', 'ProductionSchedule',
    'ShiftType', 'DispatchPriority', 'DispatchStatus',

    # ERP
    'Item', 'ItemCategory', 'UnitOfMeasure', 'BOMLine', 'Routing', 'RoutingOperation',
    'ItemType', 'ItemStatus', 'CostingMethod',
    'Partner', 'Contact', 'PartnerAddress', 'VendorItem', 'PriceList', 'PriceListItem',
    'PartnerType', 'PartnerStatus', 'PaymentTerms',
    'Location', 'Bin', 'Lot', 'SerialNumber', 'InventoryBalance', 'InventoryTransaction',
    'LocationType', 'TransactionType', 'LotStatus',
    'SalesQuote', 'SalesQuoteLine', 'SalesOrder', 'SalesOrderLine',
    'Shipment', 'ShipmentLine', 'SalesOrderStatus', 'QuoteStatus', 'ShipmentStatus',
    'PurchaseRequisition', 'PurchaseRequisitionLine', 'PurchaseOrder', 'PurchaseOrderLine',
    'Receipt', 'ReceiptLine', 'RequisitionStatus', 'PurchaseOrderStatus', 'ReceiptStatus',
    'FiscalYear', 'FiscalPeriod', 'GLAccount', 'JournalEntry', 'JournalLine',
    'APInvoice', 'APInvoiceLine', 'ARInvoice', 'ARInvoiceLine',
    'Payment', 'PaymentApplication', 'AccountType', 'AccountCategory',
    'JournalStatus', 'InvoiceStatus',
    'CostCenter', 'Budget', 'DemandForecast', 'MRPRun', 'PlannedOrder',
    'BudgetStatus', 'ForecastMethod',

    # QMS
    'Document', 'DocumentCategory', 'DocumentRevision', 'DocumentFile',
    'DocumentApproval', 'ESignature', 'DocumentType', 'DocumentStatus',
    'NonConformanceReport', 'CAPA', 'CAPAAction', 'NCRStatus', 'NCRType',
    'DispositionType', 'Severity', 'CAPAType', 'CAPAStatus',
    'Audit', 'AuditFinding', 'AuditType', 'AuditStatus', 'FindingSeverity',
    'TrainingCourse', 'TrainingRecord', 'TrainingStatus',
    'CalibratedEquipment', 'CalibrationRecord', 'CalibrationStatus',
    'SPCChart', 'SPCData',
    'SupplierQualityRating', 'InspectionPlan', 'InspectionCharacteristic',
    'InspectionRecord', 'InspectionMeasurement',
    'SupplierGrade', 'InspectionType', 'InspectionResult', 'CharacteristicType',

    # CMMS
    'Asset', 'AssetClass', 'Meter', 'MeterReading', 'Spare', 'AssetSpare',
    'AssetStatus', 'AssetCriticality', 'MeterType',
    'MaintenanceWorkOrder', 'PMSchedule', 'TaskTemplate',
    'WorkOrderTask', 'WorkOrderLabor', 'WorkOrderMaterial',
    'WorkOrderType', 'WorkOrderPriority', 'PMTriggerType',
    'FailureCode', 'FailureAnalysis', 'FailureHistory', 'FailureType', 'FailureSeverity',

    # LEGO
    'BrickType', 'ExportFormat', 'ExportStatus', 'PrinterType',
    'BrickDesign', 'BrickExportJob', 'BrickColor',
    'PrintProfile', 'FilamentInventory', 'BrickTemplate', 'PrintJob',
    'FilamentType', 'PrintQuality',
    # Parts Catalog
    'PartCategory', 'MaterialType', 'ProcessType',
    'LegoPart', 'LegoMaterial', 'LegoProductColor', 'LegoProduct',
    'LegoProductBOM', 'LegoRouting', 'LegoRoutingOperation',

    # ML
    'ModelType', 'ModelStatus', 'InferenceStatus', 'TrainingStatus', 'AnomalyType',
    'MLModel', 'TrainingRun', 'InferenceJob', 'Prediction',
    'GCodeFingerprint', 'ToolWearPrediction',

    # Auth
    'User', 'UserRole', 'TokenBlocklist', 'UserStatus',
]
