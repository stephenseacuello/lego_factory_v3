"""
Standards Compliance Layer
==========================

LEGO MCP DoD/ONR-Class Manufacturing System v8.0

Industrial protocol and standard implementations:
- OPC UA (IEC 62541) - Industrial automation interoperability
- MTConnect - CNC machine communication
- ISA-95 (IEC 62264) - Enterprise/Control integration

V8.0 Features:
- Complete ISA-95/IEC 62264 integration
- Equipment hierarchy management
- B2MML message generation
- Operations definition and scheduling
- Production performance tracking

Reference: IEC 62541, MTConnect v2.0, IEC 62264, ISA-95
"""

from .opcua import (
    OPCUAServer,
    OPCUAClient,
    OPCUANamespace,
    LegoMCPNodeSet,
)

from .mtconnect import (
    MTConnectAdapter,
    MTConnectAgent,
    MTConnectDevice,
    MTConnectDataItem,
)

from .isa95 import (
    ISA95MessageMapper,
    B2MMLGenerator,
    OperationsSchedule,
    ProductionPerformance,
)

# V8 Enhanced ISA-95 Integration
try:
    from .isa95_integration import (
        ISA95IntegrationService,
        EquipmentHierarchy,
        EquipmentLevel,
        EquipmentClass,
        EquipmentCapability,
        OperationsDefinition,
        OperationsRequest,
        OperationsResponse,
        ProductionSchedule,
        ProductionRecord,
        MaterialLot,
        MaterialClass,
        PersonnelClass,
        create_isa95_service,
    )
except ImportError:
    ISA95IntegrationService = None
    EquipmentHierarchy = None
    EquipmentLevel = None
    EquipmentClass = None
    EquipmentCapability = None
    OperationsDefinition = None
    OperationsRequest = None
    OperationsResponse = None
    ProductionSchedule = None
    ProductionRecord = None
    MaterialLot = None
    MaterialClass = None
    PersonnelClass = None
    create_isa95_service = None

__all__ = [
    # OPC UA
    "OPCUAServer",
    "OPCUAClient",
    "OPCUANamespace",
    "LegoMCPNodeSet",
    # MTConnect
    "MTConnectAdapter",
    "MTConnectAgent",
    "MTConnectDevice",
    "MTConnectDataItem",
    # ISA-95 Core
    "ISA95MessageMapper",
    "B2MMLGenerator",
    "OperationsSchedule",
    "ProductionPerformance",
    # V8 ISA-95 Integration
    "ISA95IntegrationService",
    "EquipmentHierarchy",
    "EquipmentLevel",
    "EquipmentClass",
    "EquipmentCapability",
    "OperationsDefinition",
    "OperationsRequest",
    "OperationsResponse",
    "ProductionSchedule",
    "ProductionRecord",
    "MaterialLot",
    "MaterialClass",
    "PersonnelClass",
    "create_isa95_service",
]

__version__ = "8.0.0"
