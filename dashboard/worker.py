"""
LEGO MCP V8 Background Worker
=============================

Celery worker configuration for background jobs including:
- OEE data collection
- Simulation runs
- Report generation
- Data exports
- Alert processing
- KPI aggregation

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from celery import Celery, Task
from celery.schedules import crontab

# Configuration from environment
BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/2")
TIMEZONE = os.environ.get("CELERY_TIMEZONE", "UTC")
COLLECTION_INTERVAL = int(os.environ.get("OEE_COLLECTION_INTERVAL", "60"))
KPI_INTERVAL = int(os.environ.get("KPI_COLLECTION_INTERVAL", "300"))

celery_app = Celery("lego_mcp_dashboard", broker=BROKER_URL, backend=RESULT_BACKEND)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=TIMEZONE,
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3000,  # 50 min soft limit
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# Beat schedule for periodic tasks
beat_schedule = {}

if COLLECTION_INTERVAL > 0:
    beat_schedule["oee-heartbeat"] = {
        "task": "worker.oee_heartbeat",
        "schedule": timedelta(seconds=COLLECTION_INTERVAL),
    }

if KPI_INTERVAL > 0:
    beat_schedule["kpi-aggregation"] = {
        "task": "worker.aggregate_kpis",
        "schedule": timedelta(seconds=KPI_INTERVAL),
    }

# Daily tasks
beat_schedule["daily-report"] = {
    "task": "worker.generate_daily_report",
    "schedule": crontab(hour=6, minute=0),  # 6 AM daily
}

beat_schedule["compliance-check"] = {
    "task": "worker.run_compliance_check",
    "schedule": crontab(hour=0, minute=0),  # Midnight daily
}

# Alert cleanup
beat_schedule["alert-cleanup"] = {
    "task": "worker.cleanup_old_alerts",
    "schedule": crontab(hour=2, minute=0),  # 2 AM daily
}

celery_app.conf.beat_schedule = beat_schedule

logger = logging.getLogger(__name__)


# ============================================
# Base Task with Error Handling
# ============================================

class BaseTask(Task):
    """Base task with error handling and logging."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {self.name}[{task_id}] failed: {exc}")

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {self.name}[{task_id}] completed successfully")


# ============================================
# Heartbeat and Health Tasks
# ============================================

@celery_app.task(name="worker.oee_heartbeat", base=BaseTask)
def oee_heartbeat() -> dict:
    """Periodic OEE data collection heartbeat."""
    logger.info("OEE scheduler heartbeat")
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "task": "oee_heartbeat"
    }


@celery_app.task(name="worker.aggregate_kpis", base=BaseTask)
def aggregate_kpis() -> dict:
    """Aggregate KPIs from all sources."""
    logger.info("Running KPI aggregation")

    try:
        # Import here to avoid circular imports
        from services.command_center import KPIAggregator

        aggregator = KPIAggregator()
        dashboard = aggregator.get_dashboard()

        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "kpi_count": len(dashboard.get("kpis", [])),
        }
    except Exception as e:
        logger.error(f"KPI aggregation failed: {e}")
        return {"status": "error", "message": str(e)}


# ============================================
# Simulation Tasks
# ============================================

@celery_app.task(name="worker.run_simulation", base=BaseTask, bind=True)
def run_simulation(
    self,
    simulation_id: str,
    mode: str,
    config: Dict[str, Any],
    duration_hours: float = 1.0
) -> dict:
    """Run a co-simulation in the background."""
    logger.info(f"Starting simulation {simulation_id} in {mode} mode")

    try:
        from services.cosimulation import CoSimulationCoordinator, SimulationMode

        coordinator = CoSimulationCoordinator()
        sim_mode = SimulationMode(mode)

        # Update progress
        self.update_state(
            state="RUNNING",
            meta={"progress": 0, "status": "initializing"}
        )

        result = coordinator.run_simulation(
            mode=sim_mode,
            duration_hours=duration_hours,
            config=config
        )

        return {
            "status": "completed",
            "simulation_id": simulation_id,
            "result": result.to_dict() if hasattr(result, "to_dict") else result,
            "completed_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Simulation {simulation_id} failed: {e}")
        return {
            "status": "failed",
            "simulation_id": simulation_id,
            "error": str(e)
        }


@celery_app.task(name="worker.run_scenario", base=BaseTask, bind=True)
def run_scenario(
    self,
    scenario_id: str,
    compare_with: Optional[List[str]] = None
) -> dict:
    """Run a scenario simulation."""
    logger.info(f"Running scenario {scenario_id}")

    try:
        from services.cosimulation import ScenarioManager

        manager = ScenarioManager()
        result = manager.run_scenario(scenario_id)

        comparison = None
        if compare_with:
            all_scenarios = [scenario_id] + compare_with
            comparison = manager.compare_scenarios(all_scenarios)

        return {
            "status": "completed",
            "scenario_id": scenario_id,
            "result": result,
            "comparison": comparison,
            "completed_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Scenario {scenario_id} failed: {e}")
        return {"status": "failed", "error": str(e)}


# ============================================
# Report Generation Tasks
# ============================================

@celery_app.task(name="worker.generate_daily_report", base=BaseTask)
def generate_daily_report() -> dict:
    """Generate daily manufacturing report."""
    logger.info("Generating daily report")

    try:
        from services.command_center import KPIAggregator
        from services.compliance.audit_logger import get_audit_logger

        aggregator = KPIAggregator()
        audit = get_audit_logger()

        # Get KPI summary
        kpi_dashboard = aggregator.get_dashboard()

        # Get compliance data
        compliance_data = audit.get_compliance_dashboard_data()

        report = {
            "report_type": "daily",
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start": (datetime.now() - timedelta(days=1)).isoformat(),
                "end": datetime.now().isoformat()
            },
            "kpis": kpi_dashboard,
            "compliance": compliance_data,
            "status": "completed"
        }

        logger.info("Daily report generated successfully")
        return report
    except Exception as e:
        logger.error(f"Daily report generation failed: {e}")
        return {"status": "failed", "error": str(e)}


@celery_app.task(name="worker.generate_compliance_report", base=BaseTask)
def generate_compliance_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    standard: Optional[str] = None
) -> dict:
    """Generate compliance audit report."""
    logger.info("Generating compliance report")

    try:
        from services.compliance.audit_logger import get_audit_logger

        audit = get_audit_logger()
        report = audit.generate_compliance_report(
            start_date=start_date,
            end_date=end_date
        )

        return {
            "status": "completed",
            "report": report,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Compliance report failed: {e}")
        return {"status": "failed", "error": str(e)}


@celery_app.task(name="worker.export_data", base=BaseTask, bind=True)
def export_data(
    self,
    export_type: str,
    format: str = "json",
    filters: Optional[Dict[str, Any]] = None
) -> dict:
    """Export data to specified format."""
    logger.info(f"Exporting {export_type} data as {format}")

    try:
        # This would be expanded based on export_type
        data = {"export_type": export_type, "format": format}

        if export_type == "kpis":
            from services.command_center import KPIAggregator
            aggregator = KPIAggregator()
            data["content"] = aggregator.get_dashboard()
        elif export_type == "alerts":
            from services.command_center import AlertManager
            manager = AlertManager()
            data["content"] = manager.get_summary()
        elif export_type == "audit":
            from services.compliance.audit_logger import get_audit_logger
            audit = get_audit_logger()
            data["content"] = audit.get_compliance_dashboard_data()

        return {
            "status": "completed",
            "data": data,
            "exported_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return {"status": "failed", "error": str(e)}


# ============================================
# Alert Processing Tasks
# ============================================

@celery_app.task(name="worker.process_alert", base=BaseTask)
def process_alert(
    alert_id: str,
    alert_data: Dict[str, Any]
) -> dict:
    """Process and route an alert."""
    logger.info(f"Processing alert {alert_id}")

    try:
        from services.command_center import AlertManager

        manager = AlertManager()

        # Check for escalation rules
        severity = alert_data.get("severity", "low")
        if severity in ["critical", "high"]:
            # Would trigger escalation logic
            logger.warning(f"High severity alert: {alert_id}")

        return {
            "status": "processed",
            "alert_id": alert_id,
            "processed_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Alert processing failed: {e}")
        return {"status": "failed", "error": str(e)}


@celery_app.task(name="worker.cleanup_old_alerts", base=BaseTask)
def cleanup_old_alerts(days_old: int = 30) -> dict:
    """Cleanup resolved alerts older than specified days."""
    logger.info(f"Cleaning up alerts older than {days_old} days")

    try:
        # This would cleanup old resolved alerts from database
        cutoff = datetime.now() - timedelta(days=days_old)

        return {
            "status": "completed",
            "cutoff_date": cutoff.isoformat(),
            "cleaned_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Alert cleanup failed: {e}")
        return {"status": "failed", "error": str(e)}


# ============================================
# Compliance Tasks
# ============================================

@celery_app.task(name="worker.run_compliance_check", base=BaseTask)
def run_compliance_check() -> dict:
    """Run daily compliance checks."""
    logger.info("Running compliance check")

    try:
        from services.compliance.audit_logger import get_audit_logger

        audit = get_audit_logger()

        # Verify audit chain integrity
        integrity = audit.verify_chain_integrity()

        checks = {
            "chain_integrity": integrity.get("integrity_valid", False),
            "event_count": integrity.get("event_count", 0),
            "checked_at": datetime.now().isoformat()
        }

        return {
            "status": "completed",
            "checks": checks
        }
    except Exception as e:
        logger.error(f"Compliance check failed: {e}")
        return {"status": "failed", "error": str(e)}


# ============================================
# Action Execution Tasks
# ============================================

@celery_app.task(name="worker.execute_action", base=BaseTask, bind=True)
def execute_action(
    self,
    action_id: str,
    action_type: str,
    target: str,
    parameters: Dict[str, Any]
) -> dict:
    """Execute an approved action from the command center."""
    logger.info(f"Executing action {action_id}: {action_type} on {target}")

    try:
        from services.command_center import ActionConsole

        console = ActionConsole()

        # Update action status
        self.update_state(
            state="EXECUTING",
            meta={"action_id": action_id, "progress": 0}
        )

        # Execute the action
        result = console.execute_action(action_id)

        return {
            "status": "completed",
            "action_id": action_id,
            "result": result.to_dict() if hasattr(result, "to_dict") else result,
            "executed_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Action {action_id} execution failed: {e}")
        return {
            "status": "failed",
            "action_id": action_id,
            "error": str(e)
        }


# ============================================
# Performance Tasks
# ============================================

@celery_app.task(name="worker.collect_performance_metrics", base=BaseTask)
def collect_performance_metrics() -> dict:
    """Collect system performance metrics."""
    logger.info("Collecting performance metrics")

    try:
        from services.monitoring import get_performance_collector

        collector = get_performance_collector()
        report = collector.generate_report(period_minutes=15)

        return {
            "status": "ok",
            "health_score": report.health_score,
            "alert_count": len(report.alerts),
            "collected_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Performance collection failed: {e}")
        return {"status": "failed", "error": str(e)}


# Celery looks for "app" by default when using -A <module>.
app = celery_app
