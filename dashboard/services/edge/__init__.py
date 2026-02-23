"""
Edge Computing & IIoT Services

LegoMCP World-Class Manufacturing System v7.0
Phase 25: Edge Computing & IIoT
Sprint 6: Edge Deployment & Hardware Optimization
Sprint 7: SCADA/MES Integration

Components:
- IIoTGateway: Industrial IoT gateway
- EdgeRuntime: Edge computing runtime
- EdgeInference: Hardware-aware inference engine
- ModelQuantizer: INT8/FP16 quantization pipeline
- DeviceRegistry: Multi-device management and selection
- OPCUAServer: Production OPC UA server per OPC 40501
- SparkplugBClient: MQTT Sparkplug B with birth/death certificates
- MTConnectSHDRAdapter: MTConnect SHDR protocol for CNC
"""

from .iiot_gateway import IIoTGateway, get_iiot_gateway
from .edge_runtime import EdgeRuntime, get_edge_runtime

# v6.0 Edge Inference Components
from .edge_inference import (
    EdgeInference,
    InferenceResult,
    InferenceConfig,
    DeviceType as InferenceDeviceType,
    PrecisionMode,
    InferenceSession,
    InferenceBatch,
    LatencyProfile,
    get_edge_inference,
)

from .model_quantization import (
    ModelQuantizer,
    QuantizationConfig,
    QuantizationType,
    QuantizationMethod,
    CalibrationDataset,
    QuantizationResult,
    AccuracyReport,
    CompressionStats,
    ExportFormat,
    get_model_quantizer,
)

from .device_registry import (
    DeviceRegistry,
    DeviceInfo,
    DeviceCapability,
    DeviceStatus,
    DeviceProfile,
    DeviceType,
    HealthStatus,
    ResourceMonitor,
    ResourceMetrics,
    DeviceSelector,
    SelectionStrategy,
    get_device_registry,
)

# v7.0 SCADA/MES Integration Components
from .opcua_server import (
    OPCUAServer,
    OPCUAEquipmentNode,
    CNCMachineState,
    CNCOperationMode,
    CNCAlarmSeverity,
    CNCAlarm,
    CNCChannelStatus,
    CNCSpindleStatus,
    CNCToolStatus,
    GRBLBridge,
    BambuLabBridge,
    RobotBridge,
    get_opcua_server,
    init_opcua_server,
)

from .sparkplug_b import (
    SparkplugBClient,
    SparkplugMessageType,
    SparkplugDataType,
    SparkplugMetric,
    SparkplugPayload,
    SparkplugDevice,
    get_sparkplug_client,
    init_sparkplug_client,
)

from .mtconnect_adapter import (
    MTConnectSHDRAdapter,
    MTConnectDevice,
    MTConnectCategory,
    MTConnectConditionState,
    MTConnectExecution,
    MTConnectControllerMode,
    MTConnectEmergencyStop,
    MTConnectAvailability,
    MTConnectAsset,
    SHDRDataItem,
    get_mtconnect_adapter,
    init_mtconnect_adapter,
)

__all__ = [
    # v5.0 Components
    "IIoTGateway",
    "get_iiot_gateway",
    "EdgeRuntime",
    "get_edge_runtime",
    # v6.0 Edge Inference
    "EdgeInference",
    "InferenceResult",
    "InferenceConfig",
    "InferenceDeviceType",
    "PrecisionMode",
    "InferenceSession",
    "InferenceBatch",
    "LatencyProfile",
    "get_edge_inference",
    # v6.0 Model Quantization
    "ModelQuantizer",
    "QuantizationConfig",
    "QuantizationType",
    "QuantizationMethod",
    "CalibrationDataset",
    "QuantizationResult",
    "AccuracyReport",
    "CompressionStats",
    "ExportFormat",
    "get_model_quantizer",
    # v6.0 Device Registry
    "DeviceRegistry",
    "DeviceInfo",
    "DeviceCapability",
    "DeviceStatus",
    "DeviceProfile",
    "DeviceType",
    "HealthStatus",
    "ResourceMonitor",
    "ResourceMetrics",
    "DeviceSelector",
    "SelectionStrategy",
    "get_device_registry",
    # v7.0 OPC UA Server (OPC 40501)
    "OPCUAServer",
    "OPCUAEquipmentNode",
    "CNCMachineState",
    "CNCOperationMode",
    "CNCAlarmSeverity",
    "CNCAlarm",
    "CNCChannelStatus",
    "CNCSpindleStatus",
    "CNCToolStatus",
    "GRBLBridge",
    "BambuLabBridge",
    "RobotBridge",
    "get_opcua_server",
    "init_opcua_server",
    # v7.0 Sparkplug B
    "SparkplugBClient",
    "SparkplugMessageType",
    "SparkplugDataType",
    "SparkplugMetric",
    "SparkplugPayload",
    "SparkplugDevice",
    "get_sparkplug_client",
    "init_sparkplug_client",
    # v7.0 MTConnect SHDR
    "MTConnectSHDRAdapter",
    "MTConnectDevice",
    "MTConnectCategory",
    "MTConnectConditionState",
    "MTConnectExecution",
    "MTConnectControllerMode",
    "MTConnectEmergencyStop",
    "MTConnectAvailability",
    "MTConnectAsset",
    "SHDRDataItem",
    "get_mtconnect_adapter",
    "init_mtconnect_adapter",
]

__version__ = "7.0.0"
