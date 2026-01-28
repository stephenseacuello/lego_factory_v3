"""
LEGO Factory v3 - MES (Manufacturing Execution System) Services
================================================================

ISA-95 Level 3 services for manufacturing operations management.
These services bridge the gap between business planning (ERP) and
shop floor control (SCADA), providing real-time production management.

Core Capabilities
-----------------
**Work Order Management** (WorkOrderService):
    - Create and manage production work orders
    - Track order status through production lifecycle
    - Link to bills of material (BOM) and routings
    - Support for batch, discrete, and continuous processes

**Production Scheduling** (SchedulingService):
    - Finite capacity scheduling with machine constraints
    - Multiple scheduling policies (FIFO, SPT, EDD)
    - Real-time schedule adjustment based on actual progress
    - Integration with maintenance windows and shift patterns

**OEE Monitoring** (OEEService):
    - Real-time Overall Equipment Effectiveness calculation
    - Breakdown: Availability × Performance × Quality
    - Loss categorization (planned downtime, breakdowns, speed loss, defects)
    - Trend analysis and benchmarking

ISA-95 Integration
------------------
These services implement ISA-95 Activity Models:

    Production Operations Management:
        - Dispatching: Release work to production
        - Detailed scheduling: Sequence operations
        - Production tracking: Monitor execution
        - Production performance: Analyze results

    Data Interfaces:
        - B2MML (Business to Manufacturing Markup Language) support
        - Integration with ERP (Level 4) via work orders
        - Integration with SCADA (Level 2) via machine data

Example:
    from services.mes import (
        WorkOrderService, SchedulingService, OEEService,
        calculate_oee, get_oee_dashboard
    )

    # Schedule production
    scheduler = SchedulingService()
    result = await scheduler.schedule_jobs(
        jobs=[ScheduleJob(id="WO-001", operation="milling", duration=60)],
        machines=[Machine(id="cnc_001", capabilities=["milling"])]
    )

    # Calculate OEE for a machine
    oee = await calculate_oee(
        machine_id="cnc_001",
        start_time=datetime(2024, 1, 15, 6, 0),
        end_time=datetime(2024, 1, 15, 14, 0)
    )
    print(f"OEE: {oee.overall:.1%}")  # e.g., "OEE: 78.5%"
"""

from services.mes.work_order_service import WorkOrderService, get_work_order_service
from services.mes.scheduling_service import SchedulingService, ScheduleJob, Machine, ScheduledJob, ScheduleResult
from services.mes.oee_service import OEEService, calculate_oee, get_oee_dashboard
from services.mes.labor_service import LaborService, create_labor_service, SkillLevel

__all__ = [
    # Work Order Service
    'WorkOrderService',
    'get_work_order_service',
    # Scheduling Service
    'SchedulingService',
    'ScheduleJob',
    'Machine',
    'ScheduledJob',
    'ScheduleResult',
    # OEE Service
    'OEEService',
    'calculate_oee',
    'get_oee_dashboard',
    # Labor Service
    'LaborService',
    'create_labor_service',
    'SkillLevel',
]
