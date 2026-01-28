"""
LEGO Factory v3 - CMMS Models
=============================
Computerized Maintenance Management System data models.
"""

from models.cmms.assets import (
    Asset,
    AssetClass,
    Meter,
    MeterReading,
    Spare,
    AssetSpare,
    AssetStatus,
    AssetCriticality,
    MeterType,
)

from models.cmms.maintenance import (
    MaintenanceWorkOrder,
    PMSchedule,
    TaskTemplate,
    WorkOrderTask,
    WorkOrderLabor,
    WorkOrderMaterial,
    WorkOrderType,
    WorkOrderStatus,
    WorkOrderPriority,
    PMTriggerType,
)

from models.cmms.failure import (
    FailureCode,
    FailureAnalysis,
    FailureHistory,
    FailureType,
    FailureSeverity,
)

__all__ = [
    # Assets
    'Asset',
    'AssetClass',
    'Meter',
    'MeterReading',
    'Spare',
    'AssetSpare',
    'AssetStatus',
    'AssetCriticality',
    'MeterType',
    # Maintenance
    'MaintenanceWorkOrder',
    'PMSchedule',
    'TaskTemplate',
    'WorkOrderTask',
    'WorkOrderLabor',
    'WorkOrderMaterial',
    'WorkOrderType',
    'WorkOrderStatus',
    'WorkOrderPriority',
    'PMTriggerType',
    # Failure Analysis
    'FailureCode',
    'FailureAnalysis',
    'FailureHistory',
    'FailureType',
    'FailureSeverity',
]
