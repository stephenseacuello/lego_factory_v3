"""
Observability Infrastructure
============================

LEGO MCP DoD/ONR-Class Manufacturing System v8.0

Comprehensive observability for manufacturing operations including:
- Distributed tracing (OpenTelemetry)
- Metrics collection (Prometheus)
- Structured logging with correlation
- Health checks and diagnostics
- SIEM integration (Splunk, Sentinel, Elastic)
- Security event forwarding

V8.0 Features:
- SIEM connectors with CEF/LEEF format support
- Real-time security event streaming
- Trace-to-audit correlation
- Compliance logging for CMMC/NIST 800-171

Reference: OpenTelemetry Specification, NIST SP 800-92, CEF Format
"""

from .tracing import TracingManager, SpanContext, trace_operation
from .metrics import MetricsCollector, ManufacturingMetrics
from .logging import StructuredLogger, LogContext
from .health import HealthChecker, HealthStatus

# V8 SIEM Integration
try:
    from .siem_integration import (
        SIEMConnector,
        SIEMProvider,
        SIEMEvent,
        SIEMEventType,
        SIEMSeverity,
        CEFFormatter,
        LEEFFormatter,
        SplunkHECConnector,
        SentinelConnector,
        ElasticSecurityConnector,
        create_siem_connector,
    )
except ImportError:
    SIEMConnector = None
    SIEMProvider = None
    SIEMEvent = None
    SIEMEventType = None
    SIEMSeverity = None
    CEFFormatter = None
    LEEFFormatter = None
    SplunkHECConnector = None
    SentinelConnector = None
    ElasticSecurityConnector = None
    create_siem_connector = None

__all__ = [
    # Core Observability
    "TracingManager",
    "SpanContext",
    "trace_operation",
    "MetricsCollector",
    "ManufacturingMetrics",
    "StructuredLogger",
    "LogContext",
    "HealthChecker",
    "HealthStatus",

    # V8 SIEM Integration
    "SIEMConnector",
    "SIEMProvider",
    "SIEMEvent",
    "SIEMEventType",
    "SIEMSeverity",
    "CEFFormatter",
    "LEEFFormatter",
    "SplunkHECConnector",
    "SentinelConnector",
    "ElasticSecurityConnector",
    "create_siem_connector",
]

__version__ = "8.0.0"
