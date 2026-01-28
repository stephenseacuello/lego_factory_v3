"""
LEGO Factory v3 - API Schemas Package
======================================
Pydantic schemas for comprehensive input validation across all API routes.

This package provides validation schemas organized by domain:
- common_schemas: Base classes, pagination, error responses
- auth_schemas: Authentication and user management
- scada_schemas: SCADA operations (machines, tags, alarms)
- mes_schemas: Manufacturing execution (work orders, jobs, OEE)
- erp_schemas: Enterprise resource planning (orders, inventory)

Usage:
    from api.schemas import (
        # Common
        PaginationParams, ErrorResponse, SuccessResponse,
        # Auth
        LoginRequest, RegisterRequest, TokenResponse,
        # SCADA
        MachineCreate, TagCreate, AlarmAcknowledge,
        # MES
        WorkOrderCreate, JobCreate, OEECalculationRequest,
        # ERP
        SalesOrderCreate, PurchaseOrderCreate, InventoryAdjustment,
    )
"""

# =============================================================================
# Common Schemas
# =============================================================================
from api.schemas.common_schemas import (
    # Base
    BaseSchema,
    TimestampMixin,
    AuditMixin,
    # Pagination
    PaginationParams,
    PaginatedResponse,
    # Errors
    FieldError,
    ErrorResponse,
    ValidationErrorResponse,
    # Success
    SuccessResponse,
    MessageResponse,
    CountResponse,
    # IDs
    UUIDSchema,
    StringIdSchema,
    # Date/Time
    DateTimeRange,
    DateRange,
    # Search
    SearchParams,
    BulkOperationRequest,
    BulkOperationResponse,
)

# =============================================================================
# Auth Schemas
# =============================================================================
from api.schemas.auth_schemas import (
    # Login
    LoginRequest,
    LoginResponse,
    # Registration
    RegisterRequest,
    RegisterResponse,
    # Tokens
    TokenResponse,
    RefreshTokenRequest,
    TokenValidationRequest,
    TokenValidationResponse,
    # Password Management
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    # User
    UserInfo,
    UserProfileUpdate,
    # Sessions
    SessionInfo,
    RevokeSessionRequest,
)

# =============================================================================
# SCADA Schemas
# =============================================================================
from api.schemas.scada_schemas import (
    # Enums
    TagDataType,
    TagCategory,
    AlarmPriority,
    AlarmClass,
    AlarmType,
    AlarmState,
    MachineType,
    ControllerType,
    MachineState,
    # Machine
    MachineCreate,
    MachineUpdate,
    MachineResponse,
    MachineJogRequest,
    MachineHomeRequest,
    GCodeExecuteRequest,
    # Tag
    TagCreate,
    TagUpdate,
    TagValueWrite,
    TagValueBulkWrite,
    TagValueWriteItem,
    TagGroupCreate,
    TagBulkCreate,
    TagImportRequest,
    TagScaleRequest,
    TagListParams,
    # Alarm
    AlarmDefinitionCreate,
    AlarmDefinitionUpdate,
    AlarmAcknowledge,
    AlarmShelveRequest,
    AlarmUnshelveRequest,
    AlarmGroupCreate,
    AlarmListParams,
    ActiveAlarmParams,
    AlarmHistoryParams,
    # Historian
    HistorianQueryRequest,
    HistorianWriteRequest,
    HistorianValue,
)

# =============================================================================
# MES Schemas
# =============================================================================
from api.schemas.mes_schemas import (
    # Enums
    WorkOrderStatus,
    JobStatus,
    OperationType,
    DowntimeCategory,
    ShiftType,
    # Work Order
    WorkOrderCreate,
    WorkOrderUpdate,
    WorkOrderStatusChange,
    WorkOrderResponse,
    WorkOrderListParams,
    # Operation
    OperationCreate,
    OperationUpdate,
    # Job
    JobCreate,
    JobUpdate,
    JobStatusUpdate,
    JobResponse,
    JobListParams,
    # OEE
    OEECalculationRequest,
    OEEResponse,
    DowntimeRecord,
    DowntimeUpdate,
    # Scheduling
    ScheduleJobRequest,
    ScheduleOptimizeRequest,
    ScheduleConflict,
    # Labor
    LaborEntry,
    LaborEntryUpdate,
    # Production Reporting
    ProductionCountReport,
    QualityDefect,
)

# =============================================================================
# ERP Schemas
# =============================================================================
from api.schemas.erp_schemas import (
    # Enums
    SalesOrderStatus,
    PurchaseOrderStatus,
    QuoteStatus,
    ShipmentStatus,
    ReceiptStatus,
    PartnerType,
    ItemType,
    UnitOfMeasure,
    PaymentTerms,
    # Partner
    PartnerCreate,
    PartnerUpdate,
    AddressCreate,
    # Item
    ItemCreate,
    ItemUpdate,
    # Sales Order
    SalesOrderCreate,
    SalesOrderLineCreate,
    SalesOrderUpdate,
    SalesOrderStatusChange,
    SalesOrderListParams,
    # Purchase Order
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderUpdate,
    PurchaseOrderStatusChange,
    PurchaseOrderListParams,
    # Inventory
    InventoryAdjustment,
    InventoryTransfer,
    InventoryCountRequest,
    InventoryQueryParams,
    # Receipt
    ReceiptCreate,
    ReceiptLineCreate,
    # Shipment
    ShipmentCreate,
    ShipmentLineCreate,
    ShipmentStatusUpdate,
    # MRP
    MRPRunRequest,
    MRPPlannedOrder,
)

# =============================================================================
# All exports
# =============================================================================
__all__ = [
    # Common
    'BaseSchema',
    'TimestampMixin',
    'AuditMixin',
    'PaginationParams',
    'PaginatedResponse',
    'FieldError',
    'ErrorResponse',
    'ValidationErrorResponse',
    'SuccessResponse',
    'MessageResponse',
    'CountResponse',
    'UUIDSchema',
    'StringIdSchema',
    'DateTimeRange',
    'DateRange',
    'SearchParams',
    'BulkOperationRequest',
    'BulkOperationResponse',
    # Auth
    'LoginRequest',
    'LoginResponse',
    'RegisterRequest',
    'RegisterResponse',
    'TokenResponse',
    'RefreshTokenRequest',
    'TokenValidationRequest',
    'TokenValidationResponse',
    'PasswordChangeRequest',
    'PasswordResetRequest',
    'PasswordResetConfirm',
    'UserInfo',
    'UserProfileUpdate',
    'SessionInfo',
    'RevokeSessionRequest',
    # SCADA Enums
    'TagDataType',
    'TagCategory',
    'AlarmPriority',
    'AlarmClass',
    'AlarmType',
    'AlarmState',
    'MachineType',
    'ControllerType',
    'MachineState',
    # SCADA Machine
    'MachineCreate',
    'MachineUpdate',
    'MachineResponse',
    'MachineJogRequest',
    'MachineHomeRequest',
    'GCodeExecuteRequest',
    # SCADA Tag
    'TagCreate',
    'TagUpdate',
    'TagValueWrite',
    'TagValueBulkWrite',
    'TagValueWriteItem',
    'TagGroupCreate',
    'TagBulkCreate',
    'TagImportRequest',
    'TagScaleRequest',
    'TagListParams',
    # SCADA Alarm
    'AlarmDefinitionCreate',
    'AlarmDefinitionUpdate',
    'AlarmAcknowledge',
    'AlarmShelveRequest',
    'AlarmUnshelveRequest',
    'AlarmGroupCreate',
    'AlarmListParams',
    'ActiveAlarmParams',
    'AlarmHistoryParams',
    # SCADA Historian
    'HistorianQueryRequest',
    'HistorianWriteRequest',
    'HistorianValue',
    # MES Enums
    'WorkOrderStatus',
    'JobStatus',
    'OperationType',
    'DowntimeCategory',
    'ShiftType',
    # MES Work Order
    'WorkOrderCreate',
    'WorkOrderUpdate',
    'WorkOrderStatusChange',
    'WorkOrderResponse',
    'WorkOrderListParams',
    # MES Operation
    'OperationCreate',
    'OperationUpdate',
    # MES Job
    'JobCreate',
    'JobUpdate',
    'JobStatusUpdate',
    'JobResponse',
    'JobListParams',
    # MES OEE
    'OEECalculationRequest',
    'OEEResponse',
    'DowntimeRecord',
    'DowntimeUpdate',
    # MES Scheduling
    'ScheduleJobRequest',
    'ScheduleOptimizeRequest',
    'ScheduleConflict',
    # MES Labor
    'LaborEntry',
    'LaborEntryUpdate',
    # MES Production
    'ProductionCountReport',
    'QualityDefect',
    # ERP Enums
    'SalesOrderStatus',
    'PurchaseOrderStatus',
    'QuoteStatus',
    'ShipmentStatus',
    'ReceiptStatus',
    'PartnerType',
    'ItemType',
    'UnitOfMeasure',
    'PaymentTerms',
    # ERP Partner
    'PartnerCreate',
    'PartnerUpdate',
    'AddressCreate',
    # ERP Item
    'ItemCreate',
    'ItemUpdate',
    # ERP Sales
    'SalesOrderCreate',
    'SalesOrderLineCreate',
    'SalesOrderUpdate',
    'SalesOrderStatusChange',
    'SalesOrderListParams',
    # ERP Purchasing
    'PurchaseOrderCreate',
    'PurchaseOrderLineCreate',
    'PurchaseOrderUpdate',
    'PurchaseOrderStatusChange',
    'PurchaseOrderListParams',
    # ERP Inventory
    'InventoryAdjustment',
    'InventoryTransfer',
    'InventoryCountRequest',
    'InventoryQueryParams',
    # ERP Receipt
    'ReceiptCreate',
    'ReceiptLineCreate',
    # ERP Shipment
    'ShipmentCreate',
    'ShipmentLineCreate',
    'ShipmentStatusUpdate',
    # ERP MRP
    'MRPRunRequest',
    'MRPPlannedOrder',
]
