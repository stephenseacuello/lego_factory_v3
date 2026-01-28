"""
LEGO Factory v3 - Services Package
==================================

Business logic services for all factory operations following the ISA-95
(ANSI/ISA-95) enterprise-control system integration standard.

ISA-95 Levels Implemented
-------------------------
This package organizes services according to ISA-95 functional hierarchy:

    Level 4 - Business Planning & Logistics (services.erp):
        - Enterprise Resource Planning (ERP)
        - Materials Requirements Planning (MRP)
        - Financial management, Sales, Purchasing
        - Inventory management and forecasting

    Level 3 - Manufacturing Operations Management (services.mes, services.qms, services.cmms):
        - Work order management and scheduling
        - Overall Equipment Effectiveness (OEE)
        - Quality Management System (QMS)
        - Computerized Maintenance Management (CMMS)
        - Production tracking and genealogy

    Level 2 - Control Systems (services.scada, services.plc):
        - SCADA (Supervisory Control and Data Acquisition)
        - Tag management and real-time data
        - Alarm management and escalation
        - Historian for time-series data
        - PLC communication (OPC-UA, Modbus)

    Level 1 - Basic Control (services.robotics, services.robots):
        - Robot controllers (xArm, Ned2)
        - ROS2 integration for robot arms
        - Cell orchestration
        - Motion control

    Level 0 - Physical Process (services.vision, services.mtconnect):
        - Machine tools and equipment
        - Sensors and actuators
        - Vision systems for inspection
        - MTConnect for CNC machines

Cross-Cutting Services
----------------------
    services.digital_twin:
        ISO 23247 compliant digital twin synchronization.
        Vector clocks, CRDTs, and message validation.

    services.ml, services.predictive:
        Machine learning for quality prediction and anomaly detection.
        Predictive maintenance, tool wear, cycle time forecasting.

    services.copilot, services.claude_assistant:
        AI-powered operator assistance and conversational interfaces.
        Natural language queries and guided diagnostics.

    services.scheduling:
        Advanced production scheduling with multiple policies.
        FIFO, SPT, EDD, and AI-based scheduling algorithms.

Architecture Notes
------------------
- Services are designed for dependency injection and testability
- Most services provide both class-based and singleton patterns
- Async support throughout for high-throughput operations
- Database operations use SQLAlchemy with session management

Example:
    # Get a singleton service instance
    from services.scada import get_machine_service, get_alarm_service

    machine_svc = get_machine_service()
    status = await machine_svc.get_status("cnc_001")

    alarm_svc = get_alarm_service()
    active_alarms = await alarm_svc.get_active_alarms()
"""
