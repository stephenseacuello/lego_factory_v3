"""
Observability Dashboard Integration

Provides HTTP endpoints for metrics, health, and tracing.

Reference: Prometheus HTTP API, OpenTelemetry Collector
"""

import logging
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import json
import threading

logger = logging.getLogger(__name__)


class ObservabilityDashboard:
    """
    Unified observability dashboard for manufacturing system.

    Provides:
    - Prometheus metrics endpoint
    - Health check endpoints
    - Trace viewer API
    - Real-time event streaming

    Usage:
        >>> dashboard = ObservabilityDashboard()
        >>> dashboard.register_routes(app)
    """

    def __init__(
        self,
        tracer=None,
        metrics=None,
        health_checker=None,
        structured_logger=None
    ):
        """
        Initialize dashboard.

        Args:
            tracer: TracingManager instance
            metrics: ManufacturingMetrics instance
            health_checker: HealthChecker instance
            structured_logger: StructuredLogger instance
        """
        from .tracing import get_tracer, TracingManager
        from .metrics import get_metrics, ManufacturingMetrics
        from .health import get_health_checker, HealthChecker
        from .logging import get_logger, StructuredLogger

        self.tracer = tracer or get_tracer()
        self.metrics = metrics or get_metrics()
        self.health_checker = health_checker or get_health_checker()
        self.logger = structured_logger or get_logger()

        # Event buffer for streaming
        self._events: List[Dict[str, Any]] = []
        self._max_events = 1000
        self._event_lock = threading.Lock()

        logger.info("ObservabilityDashboard initialized")

    def register_routes(self, app) -> None:
        """
        Register Flask routes for observability endpoints.

        Args:
            app: Flask application
        """
        from flask import jsonify, request, Response

        @app.route('/metrics')
        def metrics_endpoint():
            """Prometheus metrics endpoint."""
            return Response(
                self.metrics.exposition(),
                mimetype='text/plain; charset=utf-8'
            )

        @app.route('/health')
        def health_endpoint():
            """Overall health check."""
            loop = asyncio.new_event_loop()
            try:
                report = loop.run_until_complete(
                    self.health_checker.check_all()
                )
                status_code = 200 if report.status.value == "healthy" else 503
                return jsonify(report.to_dict()), status_code
            finally:
                loop.close()

        @app.route('/health/live')
        def liveness_endpoint():
            """Kubernetes liveness probe."""
            loop = asyncio.new_event_loop()
            try:
                report = loop.run_until_complete(
                    self.health_checker.check_liveness()
                )
                status_code = 200 if report.status.value == "healthy" else 503
                return jsonify(report.to_dict()), status_code
            finally:
                loop.close()

        @app.route('/health/ready')
        def readiness_endpoint():
            """Kubernetes readiness probe."""
            loop = asyncio.new_event_loop()
            try:
                report = loop.run_until_complete(
                    self.health_checker.check_readiness()
                )
                status_code = 200 if report.status.value == "healthy" else 503
                return jsonify(report.to_dict()), status_code
            finally:
                loop.close()

        @app.route('/health/startup')
        def startup_endpoint():
            """Kubernetes startup probe."""
            loop = asyncio.new_event_loop()
            try:
                report = loop.run_until_complete(
                    self.health_checker.check_startup()
                )
                status_code = 200 if report.status.value == "healthy" else 503
                return jsonify(report.to_dict()), status_code
            finally:
                loop.close()

        @app.route('/api/observability/traces')
        def traces_endpoint():
            """List recent traces."""
            limit = request.args.get('limit', 100, type=int)
            # This would integrate with trace storage
            return jsonify({
                "traces": [],
                "total": 0,
                "message": "Trace storage not configured"
            })

        @app.route('/api/observability/events')
        def events_endpoint():
            """Get recent observability events."""
            limit = request.args.get('limit', 100, type=int)
            with self._event_lock:
                events = self._events[-limit:]
            return jsonify({
                "events": events,
                "total": len(self._events)
            })

        @app.route('/api/observability/events/stream')
        def events_stream():
            """Server-sent events for real-time observability."""
            def generate():
                last_index = len(self._events)
                while True:
                    with self._event_lock:
                        new_events = self._events[last_index:]
                        last_index = len(self._events)

                    for event in new_events:
                        yield f"data: {json.dumps(event)}\n\n"

                    import time
                    time.sleep(0.5)

            return Response(
                generate(),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive'
                }
            )

        @app.route('/api/observability/dashboard')
        def dashboard_overview():
            """Get dashboard overview data."""
            loop = asyncio.new_event_loop()
            try:
                health_report = loop.run_until_complete(
                    self.health_checker.check_all()
                )

                return jsonify({
                    "health": health_report.to_dict(),
                    "metrics_endpoint": "/metrics",
                    "traces_endpoint": "/api/observability/traces",
                    "events_endpoint": "/api/observability/events",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
            finally:
                loop.close()

        logger.info("Observability routes registered")

    def add_event(
        self,
        event_type: str,
        message: str,
        severity: str = "info",
        **kwargs
    ) -> None:
        """
        Add an observability event.

        Args:
            event_type: Type of event
            message: Event message
            severity: Event severity
            **kwargs: Additional event data
        """
        event = {
            "type": event_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **kwargs
        }

        with self._event_lock:
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

    def equipment_event(
        self,
        equipment_id: str,
        event: str,
        state: Optional[str] = None
    ) -> None:
        """Record equipment event."""
        self.add_event(
            event_type="equipment",
            message=f"Equipment {equipment_id}: {event}",
            equipment_id=equipment_id,
            equipment_state=state
        )

    def job_event(
        self,
        job_id: str,
        event: str,
        equipment_id: Optional[str] = None
    ) -> None:
        """Record job event."""
        self.add_event(
            event_type="job",
            message=f"Job {job_id}: {event}",
            job_id=job_id,
            equipment_id=equipment_id
        )

    def alert_event(
        self,
        alert_type: str,
        message: str,
        severity: str = "warning"
    ) -> None:
        """Record alert event."""
        self.add_event(
            event_type="alert",
            message=message,
            severity=severity,
            alert_type=alert_type
        )


class GrafanaDashboardExporter:
    """
    Exports Grafana dashboard JSON for observability metrics.

    Generates pre-configured dashboards for manufacturing monitoring.
    """

    def __init__(self, title: str = "LEGO MCP Manufacturing"):
        self.title = title
        self.uid = "lego-mcp-manufacturing"

    def generate_dashboard(self) -> Dict[str, Any]:
        """Generate complete Grafana dashboard JSON."""
        return {
            "uid": self.uid,
            "title": self.title,
            "tags": ["manufacturing", "lego-mcp", "observability"],
            "timezone": "browser",
            "schemaVersion": 38,
            "version": 1,
            "refresh": "5s",
            "panels": [
                self._oee_panel(),
                self._production_panel(),
                self._equipment_panel(),
                self._quality_panel(),
                self._latency_panel(),
                self._health_panel()
            ],
            "templating": {
                "list": [
                    {
                        "name": "equipment",
                        "type": "query",
                        "query": "label_values(lego_mcp_equipment_state, equipment_id)",
                        "refresh": 2,
                        "multi": True
                    }
                ]
            }
        }

    def _oee_panel(self) -> Dict[str, Any]:
        """OEE gauge panel."""
        return {
            "id": 1,
            "title": "Overall Equipment Effectiveness (OEE)",
            "type": "gauge",
            "gridPos": {"x": 0, "y": 0, "w": 8, "h": 6},
            "targets": [
                {
                    "expr": "lego_mcp_oee_overall{equipment_id=~\"$equipment\"}",
                    "legendFormat": "{{equipment_id}}"
                }
            ],
            "options": {
                "minValue": 0,
                "maxValue": 1,
                "thresholds": {
                    "mode": "percentage",
                    "steps": [
                        {"value": 0, "color": "red"},
                        {"value": 60, "color": "yellow"},
                        {"value": 85, "color": "green"}
                    ]
                }
            }
        }

    def _production_panel(self) -> Dict[str, Any]:
        """Production rate panel."""
        return {
            "id": 2,
            "title": "Production Rate",
            "type": "timeseries",
            "gridPos": {"x": 8, "y": 0, "w": 8, "h": 6},
            "targets": [
                {
                    "expr": "rate(lego_mcp_parts_produced_total{equipment_id=~\"$equipment\"}[5m])",
                    "legendFormat": "{{equipment_id}} - {{quality}}"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "parts/min"
                }
            }
        }

    def _equipment_panel(self) -> Dict[str, Any]:
        """Equipment state panel."""
        return {
            "id": 3,
            "title": "Equipment Status",
            "type": "stat",
            "gridPos": {"x": 16, "y": 0, "w": 8, "h": 6},
            "targets": [
                {
                    "expr": "lego_mcp_equipment_state{equipment_id=~\"$equipment\"}",
                    "legendFormat": "{{equipment_id}}"
                }
            ],
            "options": {
                "colorMode": "background",
                "graphMode": "none"
            }
        }

    def _quality_panel(self) -> Dict[str, Any]:
        """Quality metrics panel."""
        return {
            "id": 4,
            "title": "Quality Score",
            "type": "timeseries",
            "gridPos": {"x": 0, "y": 6, "w": 12, "h": 6},
            "targets": [
                {
                    "expr": "lego_mcp_quality_score{equipment_id=~\"$equipment\"}",
                    "legendFormat": "{{equipment_id}} - {{measurement_type}}"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "min": 0,
                    "max": 100,
                    "unit": "percent"
                }
            }
        }

    def _latency_panel(self) -> Dict[str, Any]:
        """Message latency panel."""
        return {
            "id": 5,
            "title": "Message Latency",
            "type": "heatmap",
            "gridPos": {"x": 12, "y": 6, "w": 12, "h": 6},
            "targets": [
                {
                    "expr": "histogram_quantile(0.99, rate(lego_mcp_message_latency_seconds_bucket[5m]))",
                    "legendFormat": "p99"
                },
                {
                    "expr": "histogram_quantile(0.95, rate(lego_mcp_message_latency_seconds_bucket[5m]))",
                    "legendFormat": "p95"
                }
            ]
        }

    def _health_panel(self) -> Dict[str, Any]:
        """Health status panel."""
        return {
            "id": 6,
            "title": "System Health",
            "type": "table",
            "gridPos": {"x": 0, "y": 12, "w": 24, "h": 6},
            "targets": [
                {
                    "expr": "up",
                    "legendFormat": "{{instance}}"
                }
            ]
        }

    def export_json(self) -> str:
        """Export dashboard as JSON string."""
        return json.dumps(self.generate_dashboard(), indent=2)


# Integration helper functions
def setup_observability(app, config: Optional[Dict[str, Any]] = None) -> ObservabilityDashboard:
    """
    Set up complete observability for a Flask application.

    Args:
        app: Flask application
        config: Optional configuration dict

    Returns:
        Configured ObservabilityDashboard
    """
    from .tracing import TracingManager, OTLPSpanExporter
    from .metrics import ManufacturingMetrics, MetricsCollector
    from .health import HealthChecker, DiskSpaceHealthCheck, MemoryHealthCheck
    from .logging import configure_logging

    config = config or {}

    # Set up tracing
    exporters = []
    if config.get("otlp_endpoint"):
        exporters.append(OTLPSpanExporter(config["otlp_endpoint"]))

    tracer = TracingManager(
        service_name=config.get("service_name", "lego-mcp"),
        exporters=exporters,
        sample_rate=config.get("sample_rate", 1.0)
    )
    tracer.start()

    # Set up metrics
    metrics = ManufacturingMetrics()

    # Set up health checker
    health_checker = HealthChecker(
        service_name=config.get("service_name", "lego-mcp"),
        version=config.get("version", "2.0.0")
    )

    # Add default checks
    health_checker.add_check(DiskSpaceHealthCheck("disk", min_free_gb=1.0))

    # Set up structured logging
    structured_logger = configure_logging(
        service_name=config.get("service_name", "lego-mcp"),
        json_format=config.get("json_logs", True)
    )

    # Create dashboard
    dashboard = ObservabilityDashboard(
        tracer=tracer,
        metrics=metrics,
        health_checker=health_checker,
        structured_logger=structured_logger
    )

    # Register routes
    dashboard.register_routes(app)

    logger.info("Observability setup complete")
    return dashboard
