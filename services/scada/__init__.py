"""
LEGO Factory v3 - SCADA (Supervisory Control and Data Acquisition) Services
===========================================================================

ISA-95 Level 2 services for real-time control and monitoring of production
equipment. These services provide the bridge between process control (Level 1)
and manufacturing operations (Level 3).

Core Capabilities
-----------------
**Machine Control** (machine_control/):
    - Unified machine controller interface
    - Support for TinyG, GRBL, and simulation controllers
    - Machine state management (idle, running, paused, error)
    - G-code execution and position feedback
    - Jog, home, and coordinate system management

**Tag Management** (tag_management/):
    - Real-time tag value cache with subscription support
    - Read/write access to PLC and device tags
    - Tag metadata (description, units, limits, deadband)
    - Engineering unit conversion
    - Tag quality indicators (good, bad, uncertain)

**Alarm Management** (alarm_management/):
    - Real-time alarm detection and notification
    - Alarm priorities (critical, high, medium, low, info)
    - Alarm acknowledgment and shelving
    - Alarm escalation rules
    - ISA-18.2 compliant alarm states

**Historian** (historian/):
    - Time-series data storage for process variables
    - Configurable sampling rates and compression
    - Query interface for historical analysis
    - Data aggregation (min, max, avg, interpolation)
    - Integration with tag management for automatic logging

Architecture
------------
SCADA services follow a layered architecture:

    Tag Cache (in-memory) ← Scan Tasks ← PLC/Device Drivers
          ↓
    Alarm Processor → Notification System
          ↓
    Historian → Time-Series Database

Real-Time Requirements:
    - Tag updates: < 100ms typical scan rate
    - Alarm detection: < 1s from condition to notification
    - Historian writes: Configurable, typically 1-60s intervals

Example:
    from services.scada import (
        get_machine_service, get_tag_service, get_alarm_service,
        read_tag_value, write_tag_value,
        start_historian, write_to_historian
    )

    # Machine control
    machine_svc = get_machine_service()
    await machine_svc.send_command("cnc_001", "G0 X100 Y50")

    # Tag operations
    spindle_speed = await read_tag_value("cnc_001.spindle_speed")
    await write_tag_value("cnc_001.feed_override", 100.0)

    # Alarm monitoring
    alarm_svc = get_alarm_service()
    active = await alarm_svc.get_active_alarms(priority="critical")

    # Historical data
    await start_historian()
    await write_to_historian("cnc_001.spindle_speed", 2500.0)
"""

from services.scada.machine_control.machine_service import (
    machine_manager,
    get_machine_manager,
    get_machine,
    list_machines,
    MachineController,
    TinyGController,
    GRBLController,
    SimulationController
)

from services.scada.tag_management.tag_service import (
    tag_cache,
    get_tag_service,
    read_tag_value,
    read_tag_values,
    write_tag_value
)

from services.scada.alarm_management.alarm_service import (
    alarm_processor,
    get_alarm_service,
    initialize_alarm_processor,
    process_tag_value
)

from services.scada.historian.historian_service import (
    historian_writer,
    start_historian,
    stop_historian,
    write_to_historian,
    read_from_historian,
    get_historian_stats
)

__all__ = [
    # Machine control
    'machine_manager',
    'get_machine_manager',
    'get_machine',
    'list_machines',
    'MachineController',
    'TinyGController',
    'GRBLController',
    'SimulationController',
    # Tags
    'tag_cache',
    'get_tag_service',
    'read_tag_value',
    'read_tag_values',
    'write_tag_value',
    # Alarms
    'alarm_processor',
    'get_alarm_service',
    'initialize_alarm_processor',
    'process_tag_value',
    # Historian
    'historian_writer',
    'start_historian',
    'stop_historian',
    'write_to_historian',
    'read_from_historian',
    'get_historian_stats',
]
