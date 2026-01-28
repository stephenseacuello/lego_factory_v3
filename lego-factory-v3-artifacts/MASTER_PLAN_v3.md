# LEGO Factory - Master Integration Plan v3

## Executive Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LEGO FACTORY v3                                      │
│                  Complete Smart Manufacturing Platform                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SOURCES           UNIFIED SYSTEM                    CAPABILITIES           │
│  ═══════           ══════════════                    ════════════           │
│                                                                              │
│  flask_cnc_app ─┐                                   • Full ISA-95 Stack     │
│                 │   ┌─────────────────────────┐     • Complete ERP          │
│  lego-mcp-     ─┼──▶│     LEGO FACTORY        │     • Full QMS (ISO 9001)   │
│  fusion360      │   │                         │     • CMMS/Maintenance      │
│                 │   │  170+ Services          │     • ROS2 Robotics         │
│  gcode_        ─┘   │  75+ Dashboards         │     • ML Fingerprinting     │
│  fingerprinting     │  50+ MCP Tools          │     • Historian (Postgres)  │
│                     │  60+ Database Tables    │     • Alarm Management      │
│                     │                         │     • Digital Twin          │
│                     └─────────────────────────┘                              │
│                                                                              │
│  Timeline: 14 weeks │ Database: PostgreSQL (all) │ No loss of function     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LEGO FACTORY - COMPLETE ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  USER INTERFACES                                                             │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐     │
│  │  Claude   │ │   Flask   │ │   Unity   │ │  Grafana  │ │  Fusion   │     │
│  │  Desktop  │ │  Portal   │ │  3D Twin  │ │  Metrics  │ │   360     │     │
│  │  (MCP)    │ │ (75+ UIs) │ │           │ │           │ │  Add-in   │     │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘     │
│                                                                              │
│  API LAYER                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ /api/scada/*    Machine, sensors, alarms, historian, tags, recipes   │   │
│  │ /api/mes/*      Work orders, scheduling, dispatch, labor, downtime   │   │
│  │ /api/erp/*      Financial, sales, procurement, inventory, planning   │   │
│  │ /api/qms/*      Documents, NCR, CAPA, audits, training, calibration  │   │
│  │ /api/cmms/*     Assets, maintenance, work requests, spare parts      │   │
│  │ /api/lego/*     Brick design, catalog, slicing                       │   │
│  │ /api/ml/*       Fingerprinting, inference, anomaly, tool wear        │   │
│  │ /api/ros/*      Robot commands, sensor topics, cell workflows        │   │
│  │ /api/unity/*    Digital twin state, playback                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│                              ISA-95 LEVELS                                   │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  LEVEL 4: ERP                                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Financial (GL/AP/AR) │ Sales & Distribution │ Procurement            │   │
│  │ Inventory Management │ Production Planning (BOM/MRP/MPS/CRP)         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  LEVEL 3: MES + QMS + CMMS                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  MES CORE                          QMS (ISO 9001)                    │   │
│  │  ┌─────────────────────────┐      ┌─────────────────────────┐       │   │
│  │  │ • Work Orders           │      │ • Document Control      │       │   │
│  │  │ • Scheduling (3 engines)│      │ • NCR Management        │       │   │
│  │  │ • Dispatch Lists        │      │ • CAPA System           │       │   │
│  │  │ • Labor Management      │      │ • Audit Management      │       │   │
│  │  │ • Downtime Tracking     │      │ • Training Records      │       │   │
│  │  │ • OEE                   │      │ • Calibration           │       │   │
│  │  │ • Digital Thread        │      │ • Supplier Quality      │       │   │
│  │  └─────────────────────────┘      │ • Customer Complaints   │       │   │
│  │                                    │ • Management Review     │       │   │
│  │  QUALITY ENGINEERING              │ • Risk Management       │       │   │
│  │  ┌─────────────────────────┐      └─────────────────────────┘       │   │
│  │  │ • SPC (EWMA/CUSUM/T²)   │                                         │   │
│  │  │ • Process Capability    │      CMMS                               │   │
│  │  │ • FMEA / QFD            │      ┌─────────────────────────┐       │   │
│  │  │ • MSA / Gage R&R        │      │ • Asset Hierarchy       │       │   │
│  │  │ • Zero-Defect           │      │ • PM Schedules          │       │   │
│  │  │ • Vision AI (YOLO11)    │      │ • Work Orders           │       │   │
│  │  └─────────────────────────┘      │ • Spare Parts           │       │   │
│  │                                    │ • MTBF/MTTR             │       │   │
│  │  TOOL MANAGEMENT                  │ • Predictive Maint      │       │   │
│  │  ┌─────────────────────────┐      └─────────────────────────┘       │   │
│  │  │ • Tool Inventory        │                                         │   │
│  │  │ • Tool Life Tracking    │                                         │   │
│  │  │ • Tool Wear Prediction  │                                         │   │
│  │  │ • Tool Kitting          │                                         │   │
│  │  └─────────────────────────┘                                         │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  LEVEL 2: SCADA (EXPANDED)                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  CORE SCADA                        ALARM MANAGEMENT (ISA-18.2)       │   │
│  │  ┌─────────────────────────┐      ┌─────────────────────────┐       │   │
│  │  │ • Machine Control       │      │ • Alarm Configuration   │       │   │
│  │  │ • Sensor Acquisition    │      │ • Priority Levels       │       │   │
│  │  │ • Job Execution         │      │ • Acknowledgment        │       │   │
│  │  │ • Data Alignment        │      │ • Shelving/Suppression  │       │   │
│  │  │ • Factory Cell Orch     │      │ • Standing Alarm List   │       │   │
│  │  │ • Material Flow         │      │ • Alarm History         │       │   │
│  │  └─────────────────────────┘      │ • Statistics/Analysis   │       │   │
│  │                                    └─────────────────────────┘       │   │
│  │  TAG MANAGEMENT                    HISTORIAN (PostgreSQL)            │   │
│  │  ┌─────────────────────────┐      ┌─────────────────────────┐       │   │
│  │  │ • Tag Database          │      │ • High-Speed Logging    │       │   │
│  │  │ • Engineering Units     │      │ • Data Compression      │       │   │
│  │  │ • Alarm Limits          │      │ • Trend Analysis        │       │   │
│  │  │ • Tag Hierarchies       │      │ • Ad-hoc Queries        │       │   │
│  │  │ • Tag Templates         │      │ • Partitioning          │       │   │
│  │  └─────────────────────────┘      │ • Retention Policies    │       │   │
│  │                                    └─────────────────────────┘       │   │
│  │  RECIPE MANAGEMENT (ISA-88)        ML FINGERPRINTING                 │   │
│  │  ┌─────────────────────────┐      ┌─────────────────────────┐       │   │
│  │  │ • Master Recipes        │      │ • MM-DTAE-LSTM Encoder  │       │   │
│  │  │ • Recipe Parameters     │      │ • MultiHead Decoder     │       │   │
│  │  │ • Versioning            │      │ • Anomaly Detection     │       │   │
│  │  │ • Approval Workflow     │      │ • Process Fingerprint   │       │   │
│  │  │ • Recipe Download       │      │ • Tool Wear Prediction  │       │   │
│  │  │ • Execution Tracking    │      │ • Real-time Inference   │       │   │
│  │  └─────────────────────────┘      └─────────────────────────┘       │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  LEVEL 1: CONTROL (HYBRID)                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │   DIRECT SERIAL                          ROS2 LAYER                  │   │
│  │   ┌─────────────────┐                   ┌─────────────────────────┐  │   │
│  │   │ TinyG (Bantam)  │                   │ rosbridge_suite         │  │   │
│  │   │ GRBL            │    ◀── Flask ──▶  │         │               │  │   │
│  │   │ Marlin (Prusa)  │                   │    ┌────┴────┐          │  │   │
│  │   │ Bambu MQTT      │                   │    │         │          │  │   │
│  │   └─────────────────┘                   │  Niryo    xArm          │  │   │
│  │                                         │  MoveIt2  MoveIt2       │  │   │
│  │                                         └─────────────────────────┘  │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  LEVEL 0: SENSORS & HARDWARE                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ MCC USB-1608G │ Arduino Mega │ Cameras │ Niryo Ned2 │ xArm Lite 6   │   │
│  │ Bantam CNC │ Bambu P1S │ Prusa MK3S+ │ Proximity │ Temperature      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  DATABASE: PostgreSQL (Single Instance)                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ • TimescaleDB extension for historian (time-series optimization)     │   │
│  │ • Partitioned tables for high-volume data                            │   │
│  │ • 60+ tables across all modules                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Expanded SCADA Layer

### 1.1 Alarm Management (ISA-18.2)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ALARM MANAGEMENT SYSTEM                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ALARM LIFECYCLE                                                             │
│  ════════════════                                                            │
│                                                                              │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐  │
│  │ NORMAL  │───▶│ ACTIVE  │───▶│ ACKED   │───▶│ CLEARED │───▶│ NORMAL  │  │
│  │         │    │ UNACKED │    │ ACTIVE  │    │ ACKED   │    │         │  │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘  │
│       │              │              │              │                        │
│       │         Operator       Condition      Auto-clear                   │
│       │         acknowledges   returns to     after delay                  │
│       │                        normal                                       │
│       │                                                                     │
│  Condition exceeds alarm limit                                              │
│                                                                              │
│  PRIORITY LEVELS (ISA-18.2)                                                 │
│  ══════════════════════════                                                 │
│                                                                              │
│  ┌──────────────┬──────────────────────────────────────────────────────┐   │
│  │ Priority     │ Description                          │ Response Time │   │
│  ├──────────────┼──────────────────────────────────────┼───────────────┤   │
│  │ CRITICAL (1) │ Immediate danger, safety hazard      │ < 1 minute    │   │
│  │ HIGH (2)     │ Serious abnormal, equipment damage   │ < 5 minutes   │   │
│  │ MEDIUM (3)   │ Abnormal, requires attention soon    │ < 30 minutes  │   │
│  │ LOW (4)      │ Minor deviation, awareness           │ < 4 hours     │   │
│  │ DIAGNOSTIC   │ Information only, troubleshooting    │ Next shift    │   │
│  └──────────────┴──────────────────────────────────────┴───────────────┘   │
│                                                                              │
│  ALARM TYPES                                                                 │
│  ═══════════                                                                 │
│  • HI-HI    : High-High limit (critical)                                    │
│  • HI       : High limit                                                    │
│  • LO       : Low limit                                                     │
│  • LO-LO    : Low-Low limit (critical)                                      │
│  • RATE     : Rate of change exceeded                                       │
│  • DEV      : Deviation from setpoint                                       │
│  • DISCRETE : Digital state change                                          │
│  • ML       : Machine learning anomaly detected                             │
│                                                                              │
│  SPECIAL FEATURES                                                            │
│  ════════════════                                                            │
│  • Shelving     : Temporarily suppress alarm (with time limit)              │
│  • Suppression  : Suppress based on plant state (e.g., during startup)      │
│  • Deadband     : Prevent chattering on noisy signals                       │
│  • Delay        : On-delay, off-delay to filter transients                  │
│  • State-based  : Different limits based on operating mode                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Alarm Management Database Schema (PostgreSQL)

```sql
-- Alarm configuration
CREATE TABLE alarm_definitions (
    alarm_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tag_id UUID REFERENCES tags(tag_id),
    alarm_type VARCHAR(20) NOT NULL, -- HI_HI, HI, LO, LO_LO, RATE, DEV, DISCRETE, ML
    priority INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 5),
    setpoint DECIMAL(15,6),
    deadband DECIMAL(15,6) DEFAULT 0,
    on_delay_ms INTEGER DEFAULT 0,
    off_delay_ms INTEGER DEFAULT 0,
    message_template TEXT NOT NULL,
    consequence TEXT, -- What happens if ignored
    response_instruction TEXT, -- What operator should do
    is_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Operating states for state-based alarming
CREATE TABLE operating_states (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT
);

-- State-specific alarm limits
CREATE TABLE alarm_state_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alarm_id UUID REFERENCES alarm_definitions(alarm_id),
    state_id UUID REFERENCES operating_states(state_id),
    setpoint DECIMAL(15,6),
    is_suppressed BOOLEAN DEFAULT false,
    UNIQUE(alarm_id, state_id)
);

-- Active alarms (current state)
CREATE TABLE active_alarms (
    instance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alarm_id UUID REFERENCES alarm_definitions(alarm_id),
    tag_id UUID REFERENCES tags(tag_id),
    status VARCHAR(20) NOT NULL, -- ACTIVE_UNACKED, ACKED_ACTIVE, CLEARED_UNACKED
    priority INTEGER NOT NULL,
    alarm_value DECIMAL(15,6),
    alarm_time TIMESTAMP NOT NULL,
    ack_time TIMESTAMP,
    ack_by UUID, -- user_id
    clear_time TIMESTAMP,
    shelved_until TIMESTAMP,
    shelved_by UUID,
    shelve_reason TEXT
);

-- Alarm history (immutable log)
CREATE TABLE alarm_history (
    id BIGSERIAL PRIMARY KEY,
    instance_id UUID NOT NULL,
    alarm_id UUID NOT NULL,
    tag_id UUID NOT NULL,
    event_type VARCHAR(20) NOT NULL, -- ACTIVATED, ACKNOWLEDGED, CLEARED, SHELVED, UNSHELVED
    event_time TIMESTAMP NOT NULL DEFAULT NOW(),
    priority INTEGER NOT NULL,
    alarm_value DECIMAL(15,6),
    user_id UUID,
    notes TEXT
) PARTITION BY RANGE (event_time);

-- Create partitions (monthly)
CREATE TABLE alarm_history_2026_01 PARTITION OF alarm_history
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

-- Alarm statistics (for rationalization)
CREATE TABLE alarm_statistics (
    stat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alarm_id UUID REFERENCES alarm_definitions(alarm_id),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    activation_count INTEGER DEFAULT 0,
    avg_duration_seconds DECIMAL(10,2),
    max_duration_seconds DECIMAL(10,2),
    ack_response_avg_seconds DECIMAL(10,2),
    chattering_count INTEGER DEFAULT 0, -- activations within 1 min
    standing_time_seconds INTEGER DEFAULT 0,
    UNIQUE(alarm_id, period_start)
);

-- Indexes
CREATE INDEX idx_active_alarms_status ON active_alarms(status);
CREATE INDEX idx_active_alarms_priority ON active_alarms(priority);
CREATE INDEX idx_alarm_history_time ON alarm_history(event_time);
CREATE INDEX idx_alarm_history_alarm ON alarm_history(alarm_id);
```

#### Alarm Management Services

```python
# services/scada/alarm_management/

class AlarmService:
    """Core alarm processing and state management"""
    
    async def evaluate_tag(self, tag_id: str, value: float, timestamp: datetime) -> List[AlarmEvent]:
        """Evaluate tag value against all configured alarms"""
    
    async def acknowledge(self, instance_id: str, user_id: str, notes: str = None) -> None:
        """Acknowledge an active alarm"""
    
    async def shelve(self, instance_id: str, user_id: str, duration_minutes: int, reason: str) -> None:
        """Temporarily suppress alarm"""
    
    async def get_standing_alarms(self) -> List[ActiveAlarm]:
        """Get all unacknowledged active alarms"""
    
    async def get_alarm_summary(self) -> AlarmSummary:
        """Get count by priority and status"""

class AlarmConfigurationService:
    """Manage alarm definitions"""
    
    async def create_alarm(self, alarm: AlarmDefinition) -> AlarmDefinition:
        """Create new alarm definition"""
    
    async def update_limits(self, alarm_id: str, limits: AlarmLimits) -> None:
        """Update alarm setpoints"""
    
    async def set_state_limits(self, alarm_id: str, state_id: str, limits: AlarmLimits) -> None:
        """Configure state-based limits"""
    
    async def enable_disable(self, alarm_id: str, enabled: bool, user_id: str) -> None:
        """Enable or disable alarm with audit"""

class AlarmAnalyticsService:
    """Alarm rationalization and analysis"""
    
    async def get_top_alarms(self, days: int = 30, limit: int = 10) -> List[AlarmStats]:
        """Most frequent alarms"""
    
    async def get_chattering_alarms(self, days: int = 7) -> List[AlarmStats]:
        """Alarms activating too frequently"""
    
    async def get_standing_time_report(self) -> List[AlarmStats]:
        """Alarms in active state longest"""
    
    async def get_response_time_report(self) -> List[AlarmStats]:
        """Time to acknowledge by priority"""

class AlarmNotificationService:
    """Alert delivery to operators"""
    
    async def send_notification(self, alarm: ActiveAlarm) -> None:
        """Send via WebSocket, email, SMS based on priority"""
    
    async def escalate(self, alarm: ActiveAlarm) -> None:
        """Escalate unacknowledged alarm"""
```

### 1.2 Historian (PostgreSQL + TimescaleDB)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HISTORIAN SYSTEM (PostgreSQL)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DATA FLOW                                                                   │
│  ═════════                                                                   │
│                                                                              │
│  Sensors ──▶ Tag Values ──▶ Buffer Queue ──▶ Batch Insert ──▶ PostgreSQL   │
│                   │                                              │           │
│                   │                                              ▼           │
│                   │                                    ┌─────────────────┐  │
│                   │                                    │  TimescaleDB    │  │
│                   ▼                                    │  Hypertable     │  │
│            Real-time                                   │  (auto-partition│  │
│            Dashboard                                   │   by time)      │  │
│                                                        └─────────────────┘  │
│                                                                              │
│  STORAGE TIERS                                                               │
│  ═════════════                                                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │  HOT (0-7 days)        WARM (7-90 days)       COLD (90+ days)       │    │
│  │  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐       │    │
│  │  │ Full res     │      │ Compressed   │      │ Aggregated   │       │    │
│  │  │ No compress  │ ──▶  │ 10:1 ratio   │ ──▶  │ 1-min avg    │       │    │
│  │  │ SSD storage  │      │ HDD storage  │      │ Archive      │       │    │
│  │  │              │      │              │      │              │       │    │
│  │  │ ~100 Hz      │      │ ~100 Hz      │      │ 1/min        │       │    │
│  │  │ all tags     │      │ compressed   │      │ aggregates   │       │    │
│  │  └──────────────┘      └──────────────┘      └──────────────┘       │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  COMPRESSION (Swinging Door)                                                 │
│  ═══════════════════════════                                                 │
│                                                                              │
│  Before: ●──●──●──●──●──●──●──●──●──●  (10 points)                          │
│  After:  ●────────────●────────────●  (3 points, within tolerance)          │
│                                                                              │
│  QUERY CAPABILITIES                                                          │
│  ══════════════════                                                          │
│  • Time range queries with automatic partition pruning                       │
│  • Aggregations (avg, min, max, sum, count) with time bucketing             │
│  • Interpolation (linear, previous, next)                                   │
│  • Downsampling for trend displays                                          │
│  • Tag pattern matching                                                      │
│  • Cross-tag correlation                                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Historian Database Schema (PostgreSQL + TimescaleDB)

```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Tag values (hypertable - auto-partitioned by time)
CREATE TABLE tag_values (
    time TIMESTAMPTZ NOT NULL,
    tag_id UUID NOT NULL,
    value_numeric DOUBLE PRECISION,
    value_text TEXT,
    value_bool BOOLEAN,
    quality INTEGER DEFAULT 192, -- OPC quality code (192 = good)
    source VARCHAR(50) -- which collector wrote this
);

-- Convert to hypertable (7-day chunks)
SELECT create_hypertable('tag_values', 'time', chunk_time_interval => INTERVAL '7 days');

-- Compression policy (compress chunks older than 7 days)
ALTER TABLE tag_values SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tag_id'
);

SELECT add_compression_policy('tag_values', INTERVAL '7 days');

-- Retention policy (drop chunks older than 2 years)
SELECT add_retention_policy('tag_values', INTERVAL '2 years');

-- Continuous aggregates for fast queries
CREATE MATERIALIZED VIEW tag_values_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    tag_id,
    AVG(value_numeric) AS avg_value,
    MIN(value_numeric) AS min_value,
    MAX(value_numeric) AS max_value,
    COUNT(*) AS sample_count,
    LAST(value_numeric, time) AS last_value
FROM tag_values
WHERE value_numeric IS NOT NULL
GROUP BY bucket, tag_id;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('tag_values_1min',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute'
);

-- Hourly aggregates
CREATE MATERIALIZED VIEW tag_values_1hour
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    tag_id,
    AVG(value_numeric) AS avg_value,
    MIN(value_numeric) AS min_value,
    MAX(value_numeric) AS max_value,
    COUNT(*) AS sample_count
FROM tag_values
WHERE value_numeric IS NOT NULL
GROUP BY bucket, tag_id;

SELECT add_continuous_aggregate_policy('tag_values_1hour',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour'
);

-- Daily aggregates
CREATE MATERIALIZED VIEW tag_values_1day
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    tag_id,
    AVG(value_numeric) AS avg_value,
    MIN(value_numeric) AS min_value,
    MAX(value_numeric) AS max_value,
    COUNT(*) AS sample_count
FROM tag_values
WHERE value_numeric IS NOT NULL
GROUP BY bucket, tag_id;

SELECT add_continuous_aggregate_policy('tag_values_1day',
    start_offset => INTERVAL '1 week',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day'
);

-- Indexes
CREATE INDEX idx_tag_values_tag_time ON tag_values (tag_id, time DESC);
```

#### Historian Services

```python
# services/scada/historian/

class HistorianWriterService:
    """High-speed data collection and buffering"""
    
    def __init__(self, buffer_size: int = 10000, flush_interval_ms: int = 1000):
        self.buffer = []
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval_ms
    
    async def write(self, tag_id: str, value: float, timestamp: datetime, quality: int = 192):
        """Buffer a single value"""
    
    async def write_batch(self, values: List[TagValue]):
        """Write multiple values"""
    
    async def flush(self):
        """Flush buffer to database"""

class HistorianReaderService:
    """Query historical data"""
    
    async def get_raw(
        self, 
        tag_ids: List[str], 
        start: datetime, 
        end: datetime,
        limit: int = 100000
    ) -> pd.DataFrame:
        """Get raw values"""
    
    async def get_interpolated(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        interval_seconds: int,
        method: str = 'linear'  # linear, previous, next
    ) -> pd.DataFrame:
        """Get interpolated values at fixed intervals"""
    
    async def get_aggregated(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        bucket: str,  # '1 minute', '1 hour', '1 day'
        agg: str = 'avg'  # avg, min, max, sum, count
    ) -> pd.DataFrame:
        """Get aggregated values"""
    
    async def get_trend(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        max_points: int = 1000
    ) -> pd.DataFrame:
        """Auto-downsample for trend display"""

class HistorianExportService:
    """Export data for analysis/ML"""
    
    async def export_csv(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        output_path: str
    ) -> str:
        """Export to CSV file"""
    
    async def export_parquet(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        output_path: str
    ) -> str:
        """Export to Parquet file"""
    
    async def export_npz(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        output_path: str
    ) -> str:
        """Export in NPZ format for fingerprinting ML"""
```

### 1.3 Tag Management

```sql
-- Tag hierarchy
CREATE TABLE tag_groups (
    group_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_group_id UUID REFERENCES tag_groups(group_id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    path VARCHAR(500) GENERATED ALWAYS AS (
        -- Materialized path for hierarchy queries
        CASE WHEN parent_group_id IS NULL THEN name
        ELSE NULL -- Computed by trigger
        END
    ) STORED
);

-- Tag definitions
CREATE TABLE tags (
    tag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tag_name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    group_id UUID REFERENCES tag_groups(group_id),
    
    -- Data type
    data_type VARCHAR(20) NOT NULL, -- FLOAT, INT, BOOL, STRING
    
    -- Engineering units
    eng_units VARCHAR(50),
    eng_low DECIMAL(15,6),
    eng_high DECIMAL(15,6),
    raw_low DECIMAL(15,6),
    raw_high DECIMAL(15,6),
    
    -- Alarm limits (default - can override per state)
    alarm_hh DECIMAL(15,6),
    alarm_hi DECIMAL(15,6),
    alarm_lo DECIMAL(15,6),
    alarm_ll DECIMAL(15,6),
    alarm_deadband DECIMAL(15,6),
    
    -- Collection settings
    scan_rate_ms INTEGER DEFAULT 1000,
    historian_enabled BOOLEAN DEFAULT true,
    compression_enabled BOOLEAN DEFAULT true,
    compression_deviation DECIMAL(15,6),
    
    -- Source
    source_type VARCHAR(50), -- MCC_DAQ, ARDUINO, MACHINE, CALCULATED
    source_address VARCHAR(200), -- Channel, register, etc.
    
    -- Metadata
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Tag templates for quick creation
CREATE TABLE tag_templates (
    template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_name VARCHAR(100) NOT NULL,
    data_type VARCHAR(20) NOT NULL,
    eng_units VARCHAR(50),
    alarm_hh_offset DECIMAL(15,6),
    alarm_hi_offset DECIMAL(15,6),
    alarm_lo_offset DECIMAL(15,6),
    alarm_ll_offset DECIMAL(15,6),
    scan_rate_ms INTEGER,
    compression_deviation DECIMAL(15,6)
);
```

### 1.4 Recipe Management (ISA-88)

```sql
-- Master recipes (the "template")
CREATE TABLE master_recipes (
    recipe_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_name VARCHAR(200) NOT NULL,
    recipe_type VARCHAR(50) NOT NULL, -- GCODE, PRINT_PROFILE, ROBOT_PROGRAM
    product_id UUID REFERENCES items(item_id),
    version INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) DEFAULT 'draft', -- draft, pending_approval, approved, obsolete
    
    -- The actual recipe content
    content_type VARCHAR(50), -- text/gcode, application/json, etc.
    content TEXT, -- G-code, JSON parameters, etc.
    content_hash VARCHAR(64), -- SHA-256 for integrity
    
    -- Parameters that can be overridden
    parameters JSONB DEFAULT '{}',
    
    -- Approval
    created_by UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    approved_by UUID,
    approved_at TIMESTAMP,
    
    UNIQUE(recipe_name, version)
);

-- Recipe parameters definition
CREATE TABLE recipe_parameters (
    param_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_id UUID REFERENCES master_recipes(recipe_id),
    param_name VARCHAR(100) NOT NULL,
    param_type VARCHAR(20) NOT NULL, -- FLOAT, INT, STRING, BOOL
    default_value TEXT,
    min_value DECIMAL(15,6),
    max_value DECIMAL(15,6),
    units VARCHAR(50),
    description TEXT,
    is_required BOOLEAN DEFAULT false,
    UNIQUE(recipe_id, param_name)
);

-- Control recipes (instance of master for specific job)
CREATE TABLE control_recipes (
    control_recipe_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_recipe_id UUID REFERENCES master_recipes(recipe_id),
    work_order_id UUID REFERENCES work_orders(work_order_id),
    
    -- Parameter values for this instance
    parameter_values JSONB DEFAULT '{}',
    
    -- Execution
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, aborted
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Results
    actual_parameters JSONB, -- What was actually used
    execution_log TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Recipe change history (audit trail)
CREATE TABLE recipe_change_log (
    log_id BIGSERIAL PRIMARY KEY,
    recipe_id UUID NOT NULL,
    change_type VARCHAR(50) NOT NULL, -- CREATED, MODIFIED, APPROVED, OBSOLETED
    changed_by UUID NOT NULL,
    changed_at TIMESTAMP DEFAULT NOW(),
    old_values JSONB,
    new_values JSONB,
    reason TEXT
);
```

---

## Part 2: Expanded MES Layer

### 2.1 Labor Management

```sql
-- Operators / workers
CREATE TABLE workers (
    worker_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_number VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(200),
    phone VARCHAR(50),
    department VARCHAR(100),
    shift VARCHAR(50),
    hire_date DATE,
    is_active BOOLEAN DEFAULT true,
    user_id UUID, -- Link to auth system
    created_at TIMESTAMP DEFAULT NOW()
);

-- Skills / certifications
CREATE TABLE skills (
    skill_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    requires_recertification BOOLEAN DEFAULT false,
    recertification_months INTEGER
);

-- Worker skill matrix
CREATE TABLE worker_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id UUID REFERENCES workers(worker_id),
    skill_id UUID REFERENCES skills(skill_id),
    proficiency_level INTEGER CHECK (proficiency_level BETWEEN 1 AND 5),
    certified_date DATE,
    expiration_date DATE,
    certified_by UUID,
    UNIQUE(worker_id, skill_id)
);

-- Work center skill requirements
CREATE TABLE work_center_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_center_id UUID REFERENCES work_centers(wc_id),
    skill_id UUID REFERENCES skills(skill_id),
    min_proficiency INTEGER DEFAULT 1,
    is_required BOOLEAN DEFAULT true,
    UNIQUE(work_center_id, skill_id)
);

-- Time & attendance (clock in/out)
CREATE TABLE time_entries (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id UUID REFERENCES workers(worker_id),
    clock_in TIMESTAMP NOT NULL,
    clock_out TIMESTAMP,
    work_center_id UUID REFERENCES work_centers(wc_id),
    entry_type VARCHAR(20) DEFAULT 'regular', -- regular, overtime, training
    notes TEXT
);

-- Labor assigned to work orders
CREATE TABLE work_order_labor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_order_id UUID REFERENCES work_orders(work_order_id),
    worker_id UUID REFERENCES workers(worker_id),
    operation_seq INTEGER,
    
    -- Time tracking
    setup_start TIMESTAMP,
    setup_end TIMESTAMP,
    run_start TIMESTAMP,
    run_end TIMESTAMP,
    
    -- Quantities
    qty_good INTEGER DEFAULT 0,
    qty_scrap INTEGER DEFAULT 0,
    
    -- Calculated
    setup_hours DECIMAL(8,2) GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (setup_end - setup_start)) / 3600.0
    ) STORED,
    run_hours DECIMAL(8,2) GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (run_end - run_start)) / 3600.0
    ) STORED,
    
    notes TEXT
);

-- Shift definitions
CREATE TABLE shifts (
    shift_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shift_name VARCHAR(50) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    days_of_week INTEGER[], -- 0=Sunday, 6=Saturday
    is_active BOOLEAN DEFAULT true
);

-- Crew scheduling
CREATE TABLE crew_schedules (
    schedule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id UUID REFERENCES workers(worker_id),
    shift_id UUID REFERENCES shifts(shift_id),
    work_center_id UUID REFERENCES work_centers(wc_id),
    schedule_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'scheduled', -- scheduled, confirmed, absent, modified
    UNIQUE(worker_id, schedule_date)
);
```

### 2.2 CMMS / Maintenance Management

```sql
-- Asset hierarchy
CREATE TABLE assets (
    asset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_number VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    parent_asset_id UUID REFERENCES assets(asset_id),
    
    -- Location
    site VARCHAR(100),
    area VARCHAR(100),
    line VARCHAR(100),
    
    -- Classification
    asset_type VARCHAR(50), -- MACHINE, TOOL, FIXTURE, SENSOR, ROBOT
    category VARCHAR(100),
    manufacturer VARCHAR(200),
    model VARCHAR(200),
    serial_number VARCHAR(200),
    
    -- Dates
    install_date DATE,
    warranty_expiration DATE,
    expected_life_years INTEGER,
    
    -- Status
    status VARCHAR(20) DEFAULT 'operational', -- operational, degraded, down, decommissioned
    criticality VARCHAR(20) DEFAULT 'medium', -- critical, high, medium, low
    
    -- Costs
    purchase_cost DECIMAL(15,2),
    replacement_cost DECIMAL(15,2),
    
    -- Links
    work_center_id UUID REFERENCES work_centers(wc_id),
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Preventive maintenance schedules
CREATE TABLE pm_schedules (
    pm_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID REFERENCES assets(asset_id),
    pm_name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Frequency
    frequency_type VARCHAR(20) NOT NULL, -- TIME, METER, CONDITION
    frequency_value INTEGER, -- days, hours, cycles, etc.
    frequency_unit VARCHAR(20), -- day, week, month, hour, cycle
    
    -- Meter-based
    meter_tag_id UUID REFERENCES tags(tag_id),
    meter_interval DECIMAL(15,2),
    last_meter_reading DECIMAL(15,2),
    
    -- Scheduling
    lead_time_days INTEGER DEFAULT 7,
    estimated_hours DECIMAL(8,2),
    
    -- Work
    instructions TEXT,
    required_skills UUID[], -- skill_ids
    required_parts JSONB, -- [{item_id, qty}]
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    last_completed DATE,
    next_due DATE,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Maintenance work orders
CREATE TABLE maintenance_work_orders (
    mwo_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mwo_number VARCHAR(50) UNIQUE NOT NULL,
    asset_id UUID REFERENCES assets(asset_id),
    pm_id UUID REFERENCES pm_schedules(pm_id), -- NULL if corrective
    
    -- Type
    work_type VARCHAR(20) NOT NULL, -- PREVENTIVE, CORRECTIVE, PREDICTIVE, EMERGENCY
    priority VARCHAR(20) DEFAULT 'medium',
    
    -- Description
    title VARCHAR(200) NOT NULL,
    description TEXT,
    failure_code VARCHAR(50),
    
    -- Scheduling
    requested_date TIMESTAMP DEFAULT NOW(),
    scheduled_start TIMESTAMP,
    scheduled_end TIMESTAMP,
    actual_start TIMESTAMP,
    actual_end TIMESTAMP,
    
    -- Assignment
    assigned_to UUID REFERENCES workers(worker_id),
    
    -- Status
    status VARCHAR(20) DEFAULT 'requested', -- requested, planned, in_progress, completed, cancelled
    
    -- Results
    work_performed TEXT,
    root_cause TEXT,
    corrective_action TEXT,
    
    -- Costs
    labor_hours DECIMAL(8,2),
    labor_cost DECIMAL(15,2),
    parts_cost DECIMAL(15,2),
    total_cost DECIMAL(15,2),
    
    created_by UUID,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Parts used on maintenance
CREATE TABLE mwo_parts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mwo_id UUID REFERENCES maintenance_work_orders(mwo_id),
    item_id UUID REFERENCES items(item_id),
    quantity_used DECIMAL(15,4),
    unit_cost DECIMAL(15,4),
    lot_number VARCHAR(100)
);

-- Failure codes (for analysis)
CREATE TABLE failure_codes (
    code VARCHAR(50) PRIMARY KEY,
    description TEXT,
    category VARCHAR(100),
    recommended_action TEXT
);

-- Asset meter readings (for meter-based PM)
CREATE TABLE asset_meter_readings (
    reading_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID REFERENCES assets(asset_id),
    meter_type VARCHAR(50), -- HOURS, CYCLES, MILES, etc.
    reading_value DECIMAL(15,2) NOT NULL,
    reading_time TIMESTAMP DEFAULT NOW(),
    recorded_by UUID
);

-- MTBF/MTTR tracking (calculated from work orders)
CREATE TABLE asset_reliability_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID REFERENCES assets(asset_id),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    
    -- Failures
    failure_count INTEGER DEFAULT 0,
    total_downtime_hours DECIMAL(10,2) DEFAULT 0,
    
    -- Metrics
    mtbf_hours DECIMAL(10,2), -- Mean Time Between Failures
    mttr_hours DECIMAL(10,2), -- Mean Time To Repair
    availability_pct DECIMAL(5,2),
    
    UNIQUE(asset_id, period_start)
);
```

### 2.3 Tool Management

```sql
-- Tool inventory
CREATE TABLE tools (
    tool_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_number VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Classification
    tool_type VARCHAR(50), -- END_MILL, DRILL, INSERT, HOLDER, etc.
    category VARCHAR(100),
    
    -- Specifications
    diameter DECIMAL(10,4),
    length DECIMAL(10,4),
    flutes INTEGER,
    material VARCHAR(50),
    coating VARCHAR(50),
    
    -- Manufacturer
    manufacturer VARCHAR(200),
    part_number VARCHAR(200),
    
    -- Status
    status VARCHAR(20) DEFAULT 'available', -- available, in_use, worn, scrapped
    location VARCHAR(100), -- Tool crib, machine, etc.
    current_machine_id UUID REFERENCES assets(asset_id),
    
    -- Life tracking
    max_life_minutes INTEGER,
    max_life_cuts INTEGER,
    current_life_minutes INTEGER DEFAULT 0,
    current_life_cuts INTEGER DEFAULT 0,
    life_remaining_pct DECIMAL(5,2) GENERATED ALWAYS AS (
        CASE 
            WHEN max_life_minutes > 0 THEN 
                GREATEST(0, (1 - current_life_minutes::DECIMAL / max_life_minutes) * 100)
            WHEN max_life_cuts > 0 THEN
                GREATEST(0, (1 - current_life_cuts::DECIMAL / max_life_cuts) * 100)
            ELSE 100
        END
    ) STORED,
    
    -- Cost
    purchase_cost DECIMAL(15,2),
    regrind_cost DECIMAL(15,2),
    
    -- Calibration
    last_calibration DATE,
    calibration_due DATE,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tool usage history
CREATE TABLE tool_usage (
    usage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_id UUID REFERENCES tools(tool_id),
    work_order_id UUID REFERENCES work_orders(work_order_id),
    machine_id UUID REFERENCES assets(asset_id),
    
    -- Usage
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    runtime_minutes DECIMAL(10,2),
    cut_count INTEGER,
    
    -- Wear tracking (from ML fingerprinting!)
    wear_score DECIMAL(5,2), -- 0-100, from ML model
    vibration_avg DECIMAL(10,4),
    current_avg DECIMAL(10,4),
    
    -- Parameters used
    spindle_speed INTEGER,
    feed_rate DECIMAL(10,4),
    depth_of_cut DECIMAL(10,4)
);

-- Tool kits for jobs (tools needed)
CREATE TABLE tool_kits (
    kit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kit_name VARCHAR(200) NOT NULL,
    item_id UUID REFERENCES items(item_id), -- Product this kit is for
    routing_operation INTEGER,
    notes TEXT
);

CREATE TABLE tool_kit_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kit_id UUID REFERENCES tool_kits(kit_id),
    tool_id UUID REFERENCES tools(tool_id),
    quantity INTEGER DEFAULT 1,
    is_optional BOOLEAN DEFAULT false
);

-- Tool change predictions (from ML)
CREATE TABLE tool_change_predictions (
    prediction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_id UUID REFERENCES tools(tool_id),
    predicted_at TIMESTAMP DEFAULT NOW(),
    predicted_failure_time TIMESTAMP,
    confidence DECIMAL(5,2),
    model_version VARCHAR(50),
    features_used JSONB, -- What sensor data led to prediction
    recommended_action VARCHAR(200)
);
```

### 2.4 Downtime Tracking

```sql
-- Downtime reason codes (hierarchical)
CREATE TABLE downtime_reasons (
    reason_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reason_code VARCHAR(50) UNIQUE NOT NULL,
    parent_reason_id UUID REFERENCES downtime_reasons(reason_id),
    description TEXT NOT NULL,
    category VARCHAR(50) NOT NULL, -- PLANNED, UNPLANNED, CHANGEOVER, BREAKDOWN, MATERIAL, QUALITY
    affects_availability BOOLEAN DEFAULT true,
    affects_performance BOOLEAN DEFAULT false,
    typical_duration_minutes INTEGER
);

-- Downtime events
CREATE TABLE downtime_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID REFERENCES assets(asset_id),
    work_center_id UUID REFERENCES work_centers(wc_id),
    work_order_id UUID REFERENCES work_orders(work_order_id),
    
    -- Timing
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_minutes DECIMAL(10,2) GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (end_time - start_time)) / 60.0
    ) STORED,
    
    -- Reason
    reason_id UUID REFERENCES downtime_reasons(reason_id),
    reason_notes TEXT,
    
    -- Classification
    is_planned BOOLEAN DEFAULT false,
    
    -- Related records
    maintenance_wo_id UUID REFERENCES maintenance_work_orders(mwo_id),
    ncr_id UUID, -- Link to NCR if quality-related
    
    -- Who reported
    reported_by UUID REFERENCES workers(worker_id),
    reported_at TIMESTAMP DEFAULT NOW()
);

-- Downtime targets (per asset or work center)
CREATE TABLE downtime_targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID REFERENCES assets(asset_id),
    work_center_id UUID REFERENCES work_centers(wc_id),
    period_type VARCHAR(20) NOT NULL, -- DAILY, WEEKLY, MONTHLY
    
    -- Targets (minutes)
    target_planned_downtime INTEGER,
    target_unplanned_downtime INTEGER,
    target_changeover_time INTEGER,
    
    effective_from DATE NOT NULL,
    effective_to DATE,
    
    CHECK (asset_id IS NOT NULL OR work_center_id IS NOT NULL)
);
```

### 2.5 Dispatch List

```sql
-- Real-time dispatch queue (what to run next)
CREATE TABLE dispatch_queue (
    dispatch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_center_id UUID REFERENCES work_centers(wc_id) NOT NULL,
    work_order_id UUID REFERENCES work_orders(work_order_id) NOT NULL,
    operation_seq INTEGER NOT NULL,
    
    -- Priority (calculated from multiple factors)
    priority_score INTEGER NOT NULL, -- Higher = more urgent
    priority_reason TEXT, -- Why this priority
    
    -- Scheduling
    scheduled_start TIMESTAMP,
    scheduled_end TIMESTAMP,
    
    -- Status
    status VARCHAR(20) DEFAULT 'queued', -- queued, ready, in_setup, running, complete
    
    -- Assignment
    assigned_worker_id UUID REFERENCES workers(worker_id),
    
    -- Actual times
    actual_start TIMESTAMP,
    actual_end TIMESTAMP,
    
    -- Position in queue
    queue_position INTEGER,
    
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(work_center_id, work_order_id, operation_seq)
);

-- Priority rules
CREATE TABLE priority_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- DUE_DATE, CUSTOMER, HOT_JOB, FIFO, etc.
    priority_weight INTEGER DEFAULT 100,
    conditions JSONB, -- When this rule applies
    is_active BOOLEAN DEFAULT true
);
```

---

## Part 3: Complete QMS (Quality Management System)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    QUALITY MANAGEMENT SYSTEM (ISO 9001)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        QMS PROCESS MODEL                               │  │
│  │                                                                        │  │
│  │                    ┌─────────────────────┐                             │  │
│  │                    │  MANAGEMENT         │                             │  │
│  │                    │  RESPONSIBILITY     │                             │  │
│  │                    │  • Policy           │                             │  │
│  │                    │  • Objectives       │                             │  │
│  │                    │  • Management Review│                             │  │
│  │                    └──────────┬──────────┘                             │  │
│  │                               │                                        │  │
│  │    ┌──────────────────────────┼──────────────────────────┐            │  │
│  │    │                          │                          │            │  │
│  │    ▼                          ▼                          ▼            │  │
│  │  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐           │  │
│  │  │  RESOURCE   │      │  PRODUCT    │      │ MEASUREMENT │           │  │
│  │  │ MANAGEMENT  │      │ REALIZATION │      │  ANALYSIS   │           │  │
│  │  │             │      │             │      │ IMPROVEMENT │           │  │
│  │  │ • Training  │─────▶│ • Design    │─────▶│ • Audits    │           │  │
│  │  │ • Equipment │      │ • Production│      │ • NCR/CAPA  │           │  │
│  │  │ • Calibrate │      │ • Inspection│      │ • SPC       │           │  │
│  │  └─────────────┘      └─────────────┘      └──────┬──────┘           │  │
│  │                                                   │                   │  │
│  │                                                   │                   │  │
│  │                    ┌──────────────────────────────┘                   │  │
│  │                    │                                                  │  │
│  │                    ▼                                                  │  │
│  │         ┌─────────────────────┐                                      │  │
│  │         │    CONTINUAL        │                                      │  │
│  │         │    IMPROVEMENT      │                                      │  │
│  │         └─────────────────────┘                                      │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  QMS MODULES                                                                 │
│  ═══════════                                                                 │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ DOCUMENT        │  │ TRAINING        │  │ CALIBRATION     │             │
│  │ CONTROL         │  │ MANAGEMENT      │  │ MANAGEMENT      │             │
│  │                 │  │                 │  │                 │             │
│  │ • Procedures    │  │ • Requirements  │  │ • Equipment     │             │
│  │ • Work Instruct │  │ • Records       │  │ • Schedules     │             │
│  │ • Specifications│  │ • Effectiveness │  │ • Certificates  │             │
│  │ • Revision Ctrl │  │ • Compliance    │  │ • Standards     │             │
│  │ • Approval Flow │  │ • Matrix        │  │ • Traceability  │             │
│  │ • Distribution  │  │                 │  │                 │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ NCR             │  │ CAPA            │  │ AUDIT           │             │
│  │ MANAGEMENT      │  │ SYSTEM          │  │ MANAGEMENT      │             │
│  │                 │  │                 │  │                 │             │
│  │ • Detection     │  │ • Root Cause    │  │ • Internal      │             │
│  │ • Documentation │  │ • Corrective    │  │ • External      │             │
│  │ • Disposition   │  │ • Preventive    │  │ • Schedule      │             │
│  │ • Containment   │  │ • Verification  │  │ • Findings      │             │
│  │ • Cost Tracking │  │ • Effectiveness │  │ • Action Items  │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ SUPPLIER        │  │ CUSTOMER        │  │ MANAGEMENT      │             │
│  │ QUALITY         │  │ COMPLAINTS      │  │ REVIEW          │             │
│  │                 │  │                 │  │                 │             │
│  │ • Evaluation    │  │ • Intake        │  │ • KPIs          │             │
│  │ • Scorecards    │  │ • Investigation │  │ • Trends        │             │
│  │ • Audits        │  │ • Resolution    │  │ • Objectives    │             │
│  │ • Development   │  │ • Feedback      │  │ • Minutes       │             │
│  │ • Certification │  │ • Trending      │  │ • Actions       │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐                                   │
│  │ RISK            │  │ QUALITY         │                                   │
│  │ MANAGEMENT      │  │ ENGINEERING     │                                   │
│  │                 │  │                 │                                   │
│  │ • FMEA          │  │ • SPC           │                                   │
│  │ • Risk Register │  │ • Cp/Cpk        │                                   │
│  │ • Assessment    │  │ • MSA/Gage R&R  │                                   │
│  │ • Mitigation    │  │ • QFD           │                                   │
│  │ • Monitoring    │  │ • DoE           │                                   │
│  └─────────────────┘  └─────────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Document Control

```sql
-- Document types
CREATE TABLE document_types (
    type_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_code VARCHAR(20) UNIQUE NOT NULL,
    type_name VARCHAR(100) NOT NULL,
    description TEXT,
    prefix VARCHAR(10), -- For document numbering
    review_interval_months INTEGER DEFAULT 12,
    requires_training BOOLEAN DEFAULT false
);

-- Documents
CREATE TABLE documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_number VARCHAR(100) UNIQUE NOT NULL,
    type_id UUID REFERENCES document_types(type_id),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    
    -- Current version info
    current_version INTEGER DEFAULT 1,
    current_revision VARCHAR(10) DEFAULT 'A',
    
    -- Status
    status VARCHAR(20) DEFAULT 'draft', -- draft, pending_review, pending_approval, approved, obsolete
    effective_date DATE,
    review_due_date DATE,
    obsolete_date DATE,
    
    -- Classification
    department VARCHAR(100),
    process_area VARCHAR(100),
    confidentiality VARCHAR(20) DEFAULT 'internal', -- public, internal, confidential, restricted
    
    -- Links
    supersedes_id UUID REFERENCES documents(document_id),
    
    created_by UUID,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Document versions (all revisions)
CREATE TABLE document_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(document_id),
    version_number INTEGER NOT NULL,
    revision VARCHAR(10) NOT NULL,
    
    -- Content
    file_path VARCHAR(500),
    file_name VARCHAR(255),
    file_size INTEGER,
    file_hash VARCHAR(64), -- SHA-256
    content_text TEXT, -- Extracted text for search
    
    -- Change info
    change_summary TEXT,
    change_reason TEXT,
    
    -- Approval
    status VARCHAR(20) DEFAULT 'draft',
    submitted_by UUID,
    submitted_at TIMESTAMP,
    approved_by UUID,
    approved_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(document_id, version_number, revision)
);

-- Document approval workflow
CREATE TABLE document_approvals (
    approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID REFERENCES document_versions(version_id),
    approver_id UUID NOT NULL,
    approval_role VARCHAR(50), -- REVIEWER, APPROVER, QA_APPROVER
    approval_order INTEGER,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected
    decision_at TIMESTAMP,
    comments TEXT,
    
    -- E-signature
    signature_hash VARCHAR(64),
    signature_meaning TEXT -- "I have reviewed and approve this document"
);

-- Document distribution (who has access)
CREATE TABLE document_distribution (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(document_id),
    recipient_type VARCHAR(20) NOT NULL, -- USER, ROLE, DEPARTMENT, ALL
    recipient_id VARCHAR(200), -- user_id, role_name, department_name
    distribution_date TIMESTAMP DEFAULT NOW(),
    acknowledged BOOLEAN DEFAULT false,
    acknowledged_at TIMESTAMP
);

-- Document links (to other records)
CREATE TABLE document_links (
    link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(document_id),
    linked_type VARCHAR(50) NOT NULL, -- ITEM, WORK_ORDER, NCR, CAPA, ASSET, etc.
    linked_id UUID NOT NULL,
    link_reason TEXT
);
```

### 3.2 NCR (Non-Conformance Reports)

```sql
-- NCR main record
CREATE TABLE ncrs (
    ncr_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ncr_number VARCHAR(50) UNIQUE NOT NULL,
    
    -- Detection
    detected_date TIMESTAMP NOT NULL DEFAULT NOW(),
    detected_by UUID REFERENCES workers(worker_id),
    detection_point VARCHAR(50), -- INCOMING, IN_PROCESS, FINAL, CUSTOMER, AUDIT
    
    -- Classification
    ncr_type VARCHAR(50) NOT NULL, -- MATERIAL, PROCESS, PRODUCT, DOCUMENTATION, SUPPLIER
    severity VARCHAR(20) DEFAULT 'minor', -- critical, major, minor
    
    -- Description
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    evidence TEXT, -- Photos, measurements, etc.
    
    -- Affected items
    item_id UUID REFERENCES items(item_id),
    lot_number VARCHAR(100),
    serial_numbers TEXT[],
    quantity_affected DECIMAL(15,4),
    
    -- Source
    work_order_id UUID REFERENCES work_orders(work_order_id),
    work_center_id UUID REFERENCES work_centers(wc_id),
    supplier_id UUID REFERENCES vendors(vendor_id),
    customer_id UUID REFERENCES customers(customer_id),
    po_id UUID REFERENCES purchase_orders(po_id),
    
    -- Disposition
    disposition VARCHAR(50), -- USE_AS_IS, REWORK, REPAIR, SCRAP, RETURN_TO_SUPPLIER, SORT
    disposition_by UUID,
    disposition_date TIMESTAMP,
    disposition_justification TEXT,
    
    -- Status
    status VARCHAR(20) DEFAULT 'open', -- open, investigating, disposition, containment, closed
    
    -- Containment
    containment_action TEXT,
    containment_effective BOOLEAN,
    containment_verified_by UUID,
    containment_verified_date TIMESTAMP,
    
    -- Costs
    material_cost DECIMAL(15,2),
    labor_cost DECIMAL(15,2),
    scrap_cost DECIMAL(15,2),
    rework_cost DECIMAL(15,2),
    total_cost DECIMAL(15,2) GENERATED ALWAYS AS (
        COALESCE(material_cost, 0) + COALESCE(labor_cost, 0) + 
        COALESCE(scrap_cost, 0) + COALESCE(rework_cost, 0)
    ) STORED,
    
    -- Links
    capa_id UUID, -- Created CAPA (added after CAPA creation)
    
    -- Closure
    closed_by UUID,
    closed_date TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- NCR investigation (root cause)
CREATE TABLE ncr_investigations (
    investigation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ncr_id UUID REFERENCES ncrs(ncr_id),
    
    -- Investigation
    investigator_id UUID REFERENCES workers(worker_id),
    investigation_start TIMESTAMP DEFAULT NOW(),
    investigation_end TIMESTAMP,
    
    -- Root cause analysis
    root_cause_method VARCHAR(50), -- 5_WHY, FISHBONE, FAULT_TREE, 8D
    root_cause_analysis TEXT,
    root_cause_summary TEXT,
    
    -- Contributing factors
    contributing_factors TEXT[],
    
    -- Immediate cause
    immediate_cause TEXT,
    
    -- Systemic issue?
    is_systemic BOOLEAN DEFAULT false,
    systemic_scope TEXT
);

-- NCR defect codes (for Pareto analysis)
CREATE TABLE defect_codes (
    code VARCHAR(50) PRIMARY KEY,
    description TEXT NOT NULL,
    category VARCHAR(100),
    process_area VARCHAR(100)
);

CREATE TABLE ncr_defects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ncr_id UUID REFERENCES ncrs(ncr_id),
    defect_code VARCHAR(50) REFERENCES defect_codes(code),
    quantity DECIMAL(15,4) DEFAULT 1
);
```

### 3.3 CAPA (Corrective and Preventive Actions)

```sql
-- CAPA main record
CREATE TABLE capas (
    capa_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capa_number VARCHAR(50) UNIQUE NOT NULL,
    
    -- Type
    capa_type VARCHAR(20) NOT NULL, -- CORRECTIVE, PREVENTIVE
    
    -- Source
    source_type VARCHAR(50) NOT NULL, -- NCR, AUDIT, CUSTOMER_COMPLAINT, MANAGEMENT_REVIEW, TREND, SELF_IDENTIFIED
    source_id UUID, -- Link to source record
    source_description TEXT,
    
    -- Problem statement
    title VARCHAR(500) NOT NULL,
    problem_description TEXT NOT NULL,
    
    -- Risk assessment
    risk_priority VARCHAR(20), -- HIGH, MEDIUM, LOW
    potential_impact TEXT,
    
    -- Root cause
    root_cause_analysis TEXT,
    root_cause_summary TEXT NOT NULL,
    
    -- Status
    status VARCHAR(20) DEFAULT 'open', -- open, planning, implementing, verifying, closed
    
    -- Ownership
    owner_id UUID REFERENCES workers(worker_id),
    
    -- Dates
    opened_date TIMESTAMP DEFAULT NOW(),
    target_close_date DATE,
    actual_close_date TIMESTAMP,
    
    -- Effectiveness
    effectiveness_criteria TEXT,
    effectiveness_verified BOOLEAN DEFAULT false,
    effectiveness_verified_by UUID,
    effectiveness_verified_date TIMESTAMP,
    effectiveness_results TEXT,
    
    -- Approval
    approved_by UUID,
    approved_date TIMESTAMP,
    
    created_by UUID,
    created_at TIMESTAMP DEFAULT NOW()
);

-- CAPA actions (multiple per CAPA)
CREATE TABLE capa_actions (
    action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capa_id UUID REFERENCES capas(capa_id),
    action_number INTEGER NOT NULL,
    
    -- Action details
    action_type VARCHAR(20) NOT NULL, -- CONTAINMENT, CORRECTIVE, PREVENTIVE
    description TEXT NOT NULL,
    
    -- Assignment
    assigned_to UUID REFERENCES workers(worker_id),
    
    -- Dates
    due_date DATE NOT NULL,
    completed_date TIMESTAMP,
    
    -- Status
    status VARCHAR(20) DEFAULT 'open', -- open, in_progress, completed, verified, cancelled
    
    -- Verification
    verified_by UUID,
    verified_date TIMESTAMP,
    verification_method TEXT,
    verification_results TEXT,
    
    -- Evidence
    evidence_required TEXT,
    evidence_provided TEXT,
    
    UNIQUE(capa_id, action_number)
);

-- CAPA effectiveness monitoring
CREATE TABLE capa_effectiveness_checks (
    check_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capa_id UUID REFERENCES capas(capa_id),
    check_number INTEGER NOT NULL,
    
    scheduled_date DATE NOT NULL,
    actual_date TIMESTAMP,
    
    -- Results
    result VARCHAR(20), -- EFFECTIVE, PARTIALLY_EFFECTIVE, NOT_EFFECTIVE
    findings TEXT,
    checked_by UUID,
    
    -- If not effective
    follow_up_required BOOLEAN DEFAULT false,
    follow_up_capa_id UUID REFERENCES capas(capa_id),
    
    UNIQUE(capa_id, check_number)
);
```

### 3.4 Audit Management

```sql
-- Audit programs
CREATE TABLE audit_programs (
    program_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_year INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active', -- draft, active, completed
    approved_by UUID,
    approved_date TIMESTAMP
);

-- Audits
CREATE TABLE audits (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID REFERENCES audit_programs(program_id),
    audit_number VARCHAR(50) UNIQUE NOT NULL,
    
    -- Type
    audit_type VARCHAR(50) NOT NULL, -- INTERNAL, EXTERNAL, SUPPLIER, CUSTOMER, CERTIFICATION
    
    -- Scope
    title VARCHAR(200) NOT NULL,
    scope TEXT NOT NULL,
    standard VARCHAR(100), -- ISO 9001, ISO 14001, AS9100, etc.
    clauses TEXT[], -- Which clauses being audited
    
    -- Areas
    departments TEXT[],
    processes TEXT[],
    
    -- Schedule
    scheduled_start DATE,
    scheduled_end DATE,
    actual_start DATE,
    actual_end DATE,
    
    -- Team
    lead_auditor_id UUID REFERENCES workers(worker_id),
    
    -- Status
    status VARCHAR(20) DEFAULT 'planned', -- planned, in_progress, reporting, closed
    
    -- Results
    overall_result VARCHAR(50), -- PASS, CONDITIONAL_PASS, FAIL
    summary TEXT,
    strengths TEXT[],
    opportunities TEXT[],
    
    -- Report
    report_issued_date DATE,
    report_document_id UUID REFERENCES documents(document_id),
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit team
CREATE TABLE audit_team (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id UUID REFERENCES audits(audit_id),
    auditor_id UUID REFERENCES workers(worker_id),
    role VARCHAR(50), -- LEAD, AUDITOR, OBSERVER, TECHNICAL_EXPERT
    areas_assigned TEXT[]
);

-- Audit findings
CREATE TABLE audit_findings (
    finding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id UUID REFERENCES audits(audit_id),
    finding_number INTEGER NOT NULL,
    
    -- Classification
    finding_type VARCHAR(50) NOT NULL, -- MAJOR_NC, MINOR_NC, OBSERVATION, OPPORTUNITY, POSITIVE
    
    -- Details
    clause VARCHAR(50), -- Standard clause reference
    requirement TEXT,
    evidence TEXT NOT NULL,
    finding_statement TEXT NOT NULL,
    
    -- Location
    department VARCHAR(100),
    process VARCHAR(100),
    
    -- Status
    status VARCHAR(20) DEFAULT 'open', -- open, capa_created, closed
    
    -- Link to CAPA
    capa_id UUID REFERENCES capas(capa_id),
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(audit_id, finding_number)
);
```

### 3.5 Training Management

```sql
-- Training requirements by role/skill
CREATE TABLE training_requirements (
    requirement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- What triggers this requirement
    trigger_type VARCHAR(50) NOT NULL, -- ROLE, SKILL, DOCUMENT, NEW_HIRE
    trigger_value VARCHAR(200), -- role_name, skill_id, document_id
    
    -- Training details
    training_name VARCHAR(200) NOT NULL,
    description TEXT,
    training_type VARCHAR(50), -- CLASSROOM, OJT, ONLINE, SELF_STUDY, EXAM
    
    -- Documents
    training_document_id UUID REFERENCES documents(document_id),
    
    -- Duration
    estimated_hours DECIMAL(5,2),
    
    -- Recurrence
    recurrence_months INTEGER, -- NULL = one-time
    
    is_active BOOLEAN DEFAULT true
);

-- Training records
CREATE TABLE training_records (
    record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id UUID REFERENCES workers(worker_id),
    requirement_id UUID REFERENCES training_requirements(requirement_id),
    
    -- Training details
    training_date DATE NOT NULL,
    trainer_id UUID REFERENCES workers(worker_id),
    
    -- Completion
    status VARCHAR(20) DEFAULT 'completed', -- scheduled, in_progress, completed, failed
    completion_date DATE,
    
    -- Assessment
    assessment_score DECIMAL(5,2),
    passed BOOLEAN DEFAULT true,
    
    -- Expiration
    expiration_date DATE,
    
    -- Evidence
    certificate_path VARCHAR(500),
    
    -- E-signature
    trainee_signature_hash VARCHAR(64),
    trainer_signature_hash VARCHAR(64),
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Training compliance view
CREATE VIEW training_compliance AS
SELECT 
    w.worker_id,
    w.employee_number,
    w.first_name || ' ' || w.last_name AS worker_name,
    tr.training_name,
    tr.requirement_id,
    rec.completion_date,
    rec.expiration_date,
    CASE 
        WHEN rec.record_id IS NULL THEN 'NOT_COMPLETED'
        WHEN rec.expiration_date < CURRENT_DATE THEN 'EXPIRED'
        WHEN rec.expiration_date < CURRENT_DATE + INTERVAL '30 days' THEN 'EXPIRING_SOON'
        ELSE 'CURRENT'
    END AS compliance_status
FROM workers w
CROSS JOIN training_requirements tr
LEFT JOIN training_records rec ON rec.worker_id = w.worker_id 
    AND rec.requirement_id = tr.requirement_id
    AND rec.status = 'completed'
WHERE w.is_active = true 
    AND tr.is_active = true;
```

### 3.6 Calibration Management

```sql
-- Calibration equipment (measurement devices)
CREATE TABLE calibration_equipment (
    equipment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_number VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Classification
    equipment_type VARCHAR(50), -- CALIPER, MICROMETER, CMM, GAGE, SCALE, THERMOMETER
    category VARCHAR(100),
    
    -- Specifications
    manufacturer VARCHAR(200),
    model VARCHAR(200),
    serial_number VARCHAR(200),
    range_min DECIMAL(15,6),
    range_max DECIMAL(15,6),
    resolution DECIMAL(15,6),
    accuracy DECIMAL(15,6),
    units VARCHAR(50),
    
    -- Location
    location VARCHAR(200),
    assigned_to UUID REFERENCES workers(worker_id),
    
    -- Calibration
    calibration_interval_days INTEGER NOT NULL,
    last_calibration DATE,
    next_calibration DATE,
    calibration_procedure_id UUID REFERENCES documents(document_id),
    
    -- Status
    status VARCHAR(20) DEFAULT 'active', -- active, out_for_calibration, out_of_tolerance, retired
    
    -- Traceability
    traceable_to VARCHAR(200), -- NIST, etc.
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Calibration records
CREATE TABLE calibration_records (
    record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id UUID REFERENCES calibration_equipment(equipment_id),
    
    -- Calibration info
    calibration_date DATE NOT NULL,
    next_due_date DATE NOT NULL,
    calibration_type VARCHAR(20), -- INTERNAL, EXTERNAL
    
    -- Performer
    calibrated_by VARCHAR(200), -- Internal person or external lab
    calibration_lab VARCHAR(200),
    
    -- Standards used
    standards_used TEXT,
    standard_traceability TEXT,
    
    -- Results
    result VARCHAR(20) NOT NULL, -- PASS, FAIL, ADJUSTED_PASS, LIMITED_USE
    as_found_data JSONB,
    as_left_data JSONB,
    
    -- If failed
    out_of_tolerance BOOLEAN DEFAULT false,
    oot_action_taken TEXT,
    impact_assessment TEXT,
    
    -- Certificate
    certificate_number VARCHAR(100),
    certificate_path VARCHAR(500),
    
    -- Environmental conditions
    temperature DECIMAL(5,2),
    humidity DECIMAL(5,2),
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Equipment affected by OOT (Out of Tolerance)
CREATE TABLE calibration_oot_impact (
    impact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID REFERENCES calibration_records(record_id),
    
    -- What was measured with this equipment
    work_order_id UUID REFERENCES work_orders(work_order_id),
    lot_number VARCHAR(100),
    date_range_start DATE,
    date_range_end DATE,
    
    -- Assessment
    impact_assessment TEXT,
    action_required VARCHAR(50), -- NONE, RE_INSPECT, RECALL, NOTIFY_CUSTOMER
    action_taken TEXT,
    
    -- NCR if needed
    ncr_id UUID REFERENCES ncrs(ncr_id)
);
```

### 3.7 Customer Complaints

```sql
-- Customer complaints
CREATE TABLE customer_complaints (
    complaint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_number VARCHAR(50) UNIQUE NOT NULL,
    
    -- Customer info
    customer_id UUID REFERENCES customers(customer_id),
    contact_name VARCHAR(200),
    contact_email VARCHAR(200),
    contact_phone VARCHAR(50),
    
    -- Receipt
    received_date TIMESTAMP NOT NULL DEFAULT NOW(),
    received_by UUID REFERENCES workers(worker_id),
    received_via VARCHAR(50), -- PHONE, EMAIL, WEB, LETTER, IN_PERSON
    
    -- Complaint details
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    
    -- Affected products
    item_id UUID REFERENCES items(item_id),
    lot_number VARCHAR(100),
    serial_numbers TEXT[],
    quantity_affected DECIMAL(15,4),
    sales_order_id UUID REFERENCES sales_orders(order_id),
    invoice_number VARCHAR(100),
    
    -- Classification
    complaint_type VARCHAR(50), -- PRODUCT_QUALITY, DELIVERY, DOCUMENTATION, SERVICE
    severity VARCHAR(20), -- CRITICAL, MAJOR, MINOR
    
    -- Investigation
    investigator_id UUID REFERENCES workers(worker_id),
    investigation_notes TEXT,
    root_cause TEXT,
    
    -- Resolution
    resolution TEXT,
    resolution_date TIMESTAMP,
    customer_satisfaction VARCHAR(20), -- SATISFIED, PARTIALLY_SATISFIED, NOT_SATISFIED
    
    -- Links
    ncr_id UUID REFERENCES ncrs(ncr_id),
    capa_id UUID REFERENCES capas(capa_id),
    rma_id UUID, -- Return authorization
    
    -- Credits/Replacements
    credit_issued DECIMAL(15,2),
    replacement_order_id UUID REFERENCES sales_orders(order_id),
    
    -- Status
    status VARCHAR(20) DEFAULT 'open', -- open, investigating, resolved, closed
    
    -- Closure
    closed_by UUID,
    closed_date TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Complaint communications
CREATE TABLE complaint_communications (
    comm_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id UUID REFERENCES customer_complaints(complaint_id),
    
    direction VARCHAR(10) NOT NULL, -- INBOUND, OUTBOUND
    comm_type VARCHAR(50), -- PHONE, EMAIL, LETTER
    comm_date TIMESTAMP DEFAULT NOW(),
    
    subject VARCHAR(500),
    content TEXT,
    
    sent_by UUID,
    received_from VARCHAR(200)
);
```

### 3.8 Management Review

```sql
-- Management review meetings
CREATE TABLE management_reviews (
    review_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_number VARCHAR(50) UNIQUE NOT NULL,
    
    -- Meeting info
    review_date DATE NOT NULL,
    review_type VARCHAR(50), -- QUARTERLY, SEMI_ANNUAL, ANNUAL, SPECIAL
    
    -- Attendees
    attendees JSONB, -- [{name, role, present}]
    
    -- Agenda items (ISO 9001 required inputs)
    agenda JSONB,
    
    -- Review data
    quality_objectives_review TEXT,
    audit_results_review TEXT,
    customer_feedback_review TEXT,
    process_performance_review TEXT,
    nc_capa_review TEXT,
    previous_actions_review TEXT,
    changes_affecting_qms TEXT,
    improvement_opportunities TEXT,
    resource_needs TEXT,
    
    -- Minutes
    minutes TEXT,
    
    -- Decisions and actions
    decisions TEXT,
    
    -- Status
    status VARCHAR(20) DEFAULT 'scheduled', -- scheduled, completed, minutes_approved
    
    minutes_approved_by UUID,
    minutes_approved_date TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Management review actions
CREATE TABLE management_review_actions (
    action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id UUID REFERENCES management_reviews(review_id),
    action_number INTEGER NOT NULL,
    
    description TEXT NOT NULL,
    assigned_to UUID REFERENCES workers(worker_id),
    due_date DATE,
    
    status VARCHAR(20) DEFAULT 'open', -- open, in_progress, completed
    completion_date TIMESTAMP,
    completion_notes TEXT,
    
    UNIQUE(review_id, action_number)
);

-- Quality objectives
CREATE TABLE quality_objectives (
    objective_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    year INTEGER NOT NULL,
    
    objective_name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Metrics
    metric_name VARCHAR(100),
    target_value DECIMAL(15,4),
    target_unit VARCHAR(50),
    
    -- Tracking
    current_value DECIMAL(15,4),
    last_updated TIMESTAMP,
    
    -- Status
    status VARCHAR(20), -- ON_TRACK, AT_RISK, NOT_MET, ACHIEVED
    
    owner_id UUID REFERENCES workers(worker_id),
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Part 4: Updated Implementation Phases (14 Weeks)

### Timeline Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         14-WEEK IMPLEMENTATION                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FOUNDATION          MES/ERP              QMS              INTEGRATION       │
│  ══════════          ═══════              ═══              ═══════════       │
│                                                                              │
│  Week 1: SCADA Core  Week 5: ERP Fin      Week 9: Doc Ctrl  Week 12: Twin   │
│  Week 2: ML Pipeline Week 6: ERP S&P      Week 10: NCR/CAPA Week 13: UI/MCP │
│  Week 3: LEGO        Week 7: ERP Inv      Week 11: Full QMS Week 14: Test   │
│  Week 4: MES + Maint Week 8: ROS2                                           │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
│  SCADA ENHANCEMENTS (Throughout):                                           │
│  • Alarm Management (Week 1)                                                │
│  • Historian/TimescaleDB (Week 1-2)                                         │
│  • Tag Management (Week 1)                                                  │
│  • Recipe Management (Week 3)                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Phase 1: Foundation + SCADA Enhancements (Week 1)
**Goal**: Core SCADA with alarms, historian, tags

| Task | Description |
|------|-------------|
| 1.1 | Create unified repository structure |
| 1.2 | Set up PostgreSQL with TimescaleDB extension |
| 1.3 | Port machine controllers (TinyG, GRBL, Marlin) |
| 1.4 | Port sensor acquisition (MCC, Arduino) |
| 1.5 | Port data alignment engine |
| 1.6 | **NEW**: Implement tag management service |
| 1.7 | **NEW**: Implement alarm management (ISA-18.2) |
| 1.8 | **NEW**: Implement historian writer/reader |
| 1.9 | Port SCADA API routes |
| 1.10 | Create alarm dashboard |

**Deliverable**: SCADA with professional alarm handling and data historian

---

### Phase 2: ML Fingerprinting (Week 2)
**Goal**: ML pipeline with historian integration

| Task | Description |
|------|-------------|
| 2.1 | Port model architectures (LSTM, Decoder) |
| 2.2 | Port dataset classes and training utilities |
| 2.3 | Port vocabulary (668-token) |
| 2.4 | Port pretrained weights |
| 2.5 | Create alignment → NPZ converter |
| 2.6 | Create real-time inference service |
| 2.7 | **NEW**: Create tool wear prediction service |
| 2.8 | **NEW**: Integrate with historian for trend analysis |
| 2.9 | Create ML API routes |
| 2.10 | Create anomaly alert → alarm integration |

**Deliverable**: Real-time fingerprinting with historian storage

---

### Phase 3: LEGO Services + Recipe Management (Week 3)
**Goal**: Brick design with recipe versioning

| Task | Description |
|------|-------------|
| 3.1 | Port brick dimension specs |
| 3.2 | Port brick service |
| 3.3 | Port slicer service (Docker) |
| 3.4 | Port Fusion 360 add-in |
| 3.5 | **NEW**: Implement recipe management (ISA-88) |
| 3.6 | **NEW**: Recipe approval workflow |
| 3.7 | Create LEGO API routes |
| 3.8 | Connect slicer output → recipe → SCADA |

**Deliverable**: Design → Versioned Recipe → Execute

---

### Phase 4: MES + CMMS + Labor + Tools (Week 4)
**Goal**: Complete MES with maintenance and labor

| Task | Description |
|------|-------------|
| 4.1 | Port MES models and work order service |
| 4.2 | Port scheduling services (CP-SAT, NSGA-II, RL) |
| 4.3 | **NEW**: Implement labor management |
| 4.4 | **NEW**: Implement CMMS/maintenance service |
| 4.5 | **NEW**: Implement tool management |
| 4.6 | **NEW**: Implement downtime tracking |
| 4.7 | **NEW**: Implement dispatch list service |
| 4.8 | **NEW**: Connect tool wear ML to tool management |
| 4.9 | Create MES API routes |
| 4.10 | Create maintenance dashboard |

**Deliverable**: Full MES with labor, tools, maintenance, downtime

---

### Phase 5: ERP Financial (Week 5)
**Goal**: Core financial module

| Task | Description |
|------|-------------|
| 5.1 | Implement chart of accounts, GL service |
| 5.2 | Implement journal entries |
| 5.3 | Implement accounts payable |
| 5.4 | Implement accounts receivable |
| 5.5 | Implement cost accounting |
| 5.6 | Create financial API routes |
| 5.7 | Create financial dashboards |

**Deliverable**: Complete financial management

---

### Phase 6: ERP Sales & Procurement (Week 6)
**Goal**: Order-to-cash, procure-to-pay

| Task | Description |
|------|-------------|
| 6.1 | Implement customer master, credit management |
| 6.2 | Implement pricing, quotations |
| 6.3 | Implement sales orders, allocation, shipping |
| 6.4 | Implement returns (RMA, credits) |
| 6.5 | Implement vendor master, performance |
| 6.6 | Implement purchase requisitions, approval |
| 6.7 | Implement purchase orders, receiving |
| 6.8 | Implement invoice matching (3-way) |
| 6.9 | Create sales & procurement API routes |
| 6.10 | Create sales & procurement dashboards |

**Deliverable**: Full O2C and P2P processes

---

### Phase 7: ERP Inventory & Planning (Week 7)
**Goal**: Inventory and MRP

| Task | Description |
|------|-------------|
| 7.1 | Implement item master, warehouses, bins |
| 7.2 | Implement inventory transactions |
| 7.3 | Implement lot/serial tracking |
| 7.4 | Implement cycle counting |
| 7.5 | Implement inventory valuation (FIFO/LIFO/Avg) |
| 7.6 | Implement BOM management |
| 7.7 | Implement MRP engine |
| 7.8 | Implement MPS (Master Production Schedule) |
| 7.9 | Implement capacity planning (CRP) |
| 7.10 | Create inventory & planning API routes |
| 7.11 | Create inventory & planning dashboards |

**Deliverable**: Complete inventory and production planning

---

### Phase 8: ROS2 & Robotics (Week 8)
**Goal**: Multi-robot integration

| Task | Description |
|------|-------------|
| 8.1 | Create lego_factory_msgs package |
| 8.2 | Create Niryo ROS2 node + MoveIt2 |
| 8.3 | Create xArm ROS2 node + MoveIt2 |
| 8.4 | Create sensor aggregator node |
| 8.5 | Configure rosbridge_suite |
| 8.6 | Create Flask ↔ ROS2 bridge service |
| 8.7 | Port factory cell orchestrator |
| 8.8 | Create robot API routes |
| 8.9 | Create Gazebo simulation world |

**Deliverable**: Multi-robot coordination with MoveIt2

---

### Phase 9: QMS - Document Control + Core (Week 9)
**Goal**: Document control foundation

| Task | Description |
|------|-------------|
| 9.1 | Implement document types and documents |
| 9.2 | Implement version control |
| 9.3 | Implement approval workflow |
| 9.4 | Implement e-signatures (21 CFR Part 11) |
| 9.5 | Implement document distribution |
| 9.6 | Implement document search |
| 9.7 | Create document control API routes |
| 9.8 | Create document control dashboard |

**Deliverable**: Complete document management system

---

### Phase 10: QMS - NCR/CAPA (Week 10)
**Goal**: Non-conformance and corrective action

| Task | Description |
|------|-------------|
| 10.1 | Implement NCR service |
| 10.2 | Implement NCR investigation |
| 10.3 | Implement defect codes and Pareto |
| 10.4 | Implement CAPA service |
| 10.5 | Implement CAPA actions and tracking |
| 10.6 | Implement effectiveness verification |
| 10.7 | Connect NCR → CAPA workflow |
| 10.8 | Create NCR/CAPA API routes |
| 10.9 | Create NCR/CAPA dashboards |

**Deliverable**: Complete NCR and CAPA management

---

### Phase 11: QMS - Complete (Week 11)
**Goal**: Full QMS

| Task | Description |
|------|-------------|
| 11.1 | Implement audit management |
| 11.2 | Implement training management |
| 11.3 | Implement calibration management |
| 11.4 | Implement customer complaints |
| 11.5 | Implement supplier quality |
| 11.6 | Implement management review |
| 11.7 | Implement quality objectives |
| 11.8 | Port SPC services (EWMA/CUSUM/T²) |
| 11.9 | Port FMEA/QFD services |
| 11.10 | Port vision inspection |
| 11.11 | Create QMS API routes |
| 11.12 | Create QMS dashboards |

**Deliverable**: ISO 9001-ready QMS

---

### Phase 12: Digital Twin (Week 12)
**Goal**: Unity visualization with full integration

| Task | Description |
|------|-------------|
| 12.1 | Port Unity project |
| 12.2 | Port Unity state service |
| 12.3 | Port historical playback |
| 12.4 | Add LEGO brick models |
| 12.5 | Add alarm status overlay |
| 12.6 | Add ML anomaly overlay |
| 12.7 | Add maintenance status overlay |
| 12.8 | Create Unity API routes |

**Deliverable**: Real-time 3D visualization with all system data

---

### Phase 13: Dashboards & MCP (Week 13)
**Goal**: Unified UI and Claude integration

| Task | Description |
|------|-------------|
| 13.1 | Port/create SCADA dashboards (alarm, historian, tags) |
| 13.2 | Port/create MES dashboards (dispatch, labor, tools) |
| 13.3 | Port/create CMMS dashboards |
| 13.4 | Port/create ERP dashboards |
| 13.5 | Port/create QMS dashboards |
| 13.6 | Create unified portal navigation |
| 13.7 | Port MCP server |
| 13.8 | Add SCADA MCP tools (alarms, tags, recipes) |
| 13.9 | Add MES MCP tools (dispatch, labor) |
| 13.10 | Add CMMS MCP tools (work orders, PM) |
| 13.11 | Add QMS MCP tools (NCR, CAPA, audits) |
| 13.12 | Add ERP MCP tools |

**Deliverable**: 75+ dashboards, 50+ MCP tools

---

### Phase 14: Testing & Documentation (Week 14)
**Goal**: Production ready

| Task | Description |
|------|-------------|
| 14.1 | Integration tests (end-to-end workflows) |
| 14.2 | Performance tests (historian, alarm processing) |
| 14.3 | ROS2 simulation tests (Gazebo) |
| 14.4 | QMS workflow tests |
| 14.5 | Port all notebooks (19 from fingerprinting) |
| 14.6 | Write unified documentation |
| 14.7 | Docker compose (all services) |
| 14.8 | CI/CD pipeline (GitHub Actions) |
| 14.9 | Deployment guide |
| 14.10 | User training materials |

**Deliverable**: Production-ready unified system

---

## Part 5: Complete Deliverables Summary

### Service Counts by Module

| Module | Services | API Routes | Dashboards |
|--------|----------|------------|------------|
| **SCADA Core** | 15 | 12 | 8 |
| **SCADA Enhanced** (Alarm/Historian/Tag/Recipe) | 12 | 15 | 6 |
| **MES Core** | 10 | 10 | 6 |
| **MES Enhanced** (Labor/Downtime/Dispatch) | 8 | 12 | 5 |
| **CMMS** | 8 | 10 | 4 |
| **Tool Management** | 4 | 6 | 2 |
| **ERP Financial** | 6 | 15 | 4 |
| **ERP Sales** | 8 | 18 | 5 |
| **ERP Procurement** | 6 | 12 | 4 |
| **ERP Inventory** | 8 | 20 | 5 |
| **ERP Planning** | 5 | 12 | 4 |
| **QMS Core** (Doc Control) | 5 | 10 | 3 |
| **QMS NCR/CAPA** | 6 | 12 | 4 |
| **QMS Full** (Audit/Training/Cal/etc.) | 10 | 18 | 8 |
| **Quality Engineering** | 8 | 10 | 4 |
| **ML Fingerprinting** | 6 | 8 | 3 |
| **ROS2/Robotics** | 8 | 8 | 2 |
| **Digital Twin** | 5 | 6 | 2 |
| **AI/Copilot** | 4 | 4 | 1 |
| **LEGO** | 5 | 6 | 2 |
| **TOTAL** | **~170** | **~220** | **~75** |

### Database Tables by Module

| Module | Tables |
|--------|--------|
| SCADA (Alarm/Historian/Tag/Recipe) | 15 |
| MES (Core + Labor + Downtime + Dispatch) | 12 |
| CMMS | 8 |
| Tool Management | 5 |
| ERP Financial | 8 |
| ERP Sales | 10 |
| ERP Procurement | 8 |
| ERP Inventory | 12 |
| ERP Planning | 8 |
| QMS Document Control | 5 |
| QMS NCR/CAPA | 8 |
| QMS Full | 15 |
| Quality Engineering | 6 |
| **TOTAL** | **~120** |

### MCP Tools by Category

| Category | Tools |
|----------|-------|
| **SCADA** | connect_machine, home_machine, zero_machine, start_job, get_alarms, ack_alarm, get_tag_value, get_trend |
| **MES** | create_work_order, schedule_work_order, dispatch_job, assign_labor, log_downtime, get_oee |
| **CMMS** | create_maintenance_wo, schedule_pm, log_meter_reading, get_asset_health |
| **Tools** | check_tool_life, predict_tool_change, assign_tool_kit |
| **ERP** | create_sales_order, check_atp, create_po, receive_po, run_mrp, explode_bom |
| **QMS** | create_ncr, create_capa, schedule_audit, check_training_compliance, check_calibration_due |
| **ML** | get_fingerprint, detect_anomaly, predict_tool_wear, export_training_data |
| **ROS2** | pick_place, execute_cell_workflow, get_robot_state, emergency_stop |
| **LEGO** | create_brick, slice_brick, create_recipe |
| **TOTAL** | **~50** |

---

## Part 6: Technology Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TECHNOLOGY STACK                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  APPLICATION                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Flask 3.0          Web framework, API routes, templates             │    │
│  │ FastAPI            ML inference endpoints (async)                   │    │
│  │ SQLAlchemy 2.0     ORM, database models                            │    │
│  │ Celery             Background tasks (MRP, reporting)               │    │
│  │ Redis              Task queue, caching, pub/sub                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  DATABASE                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ PostgreSQL 16      Primary database (ALL data)                     │    │
│  │ TimescaleDB 2.x    Extension for time-series (historian)           │    │
│  │ pg_partman         Table partitioning for large tables             │    │
│  │ pgvector           Vector embeddings (future: semantic search)     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ML / DATA SCIENCE                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ PyTorch 2.0        Model training and inference                    │    │
│  │ NumPy/Pandas       Data processing                                 │    │
│  │ scikit-learn       SPC, process capability                         │    │
│  │ ONNX Runtime       Optimized inference                             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ROBOTICS                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ROS2 Humble        Robot middleware                                │    │
│  │ MoveIt2            Motion planning                                 │    │
│  │ Gazebo             Simulation                                      │    │
│  │ rosbridge_suite    WebSocket bridge to Flask                       │    │
│  │ roslibpy           Python ROS2 client                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  VISUALIZATION                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Unity 2022 LTS     Digital twin                                    │    │
│  │ Grafana            Metrics dashboards                              │    │
│  │ Chart.js           Web charts                                      │    │
│  │ DataTables         Web tables                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  INFRASTRUCTURE                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Docker             Containerization                                │    │
│  │ Docker Compose     Multi-service orchestration                     │    │
│  │ Nginx              Reverse proxy, static files                     │    │
│  │ Keycloak           Authentication, RBAC                            │    │
│  │ Prometheus         Metrics collection                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  COMMUNICATION                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ WebSocket          Real-time updates (alarms, machine state)       │    │
│  │ MQTT (Mosquitto)   IoT messaging (Bambu printers)                  │    │
│  │ Serial (pyserial)  Machine communication (TinyG, GRBL)             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 7: Success Criteria

| Area | Metric | Target |
|------|--------|--------|
| **Machine Control** | Connect, home, jog, run | All equipment |
| **Alarm Response** | Time to display new alarm | < 500ms |
| **Historian Write** | Sustained write rate | > 100,000 pts/sec |
| **Historian Query** | 1-day trend, 1000 points | < 1 second |
| **ML Inference** | Real-time anomaly detection | < 100ms |
| **Tool Wear Prediction** | Advance warning | > 30 minutes |
| **MRP Run** | Full horizon (90 days) | < 30 seconds |
| **Robot Coordination** | Pick-place cycle | < 10 seconds |
| **End-to-End** | Design → Execute | < 5 minutes |
| **Dashboard Load** | Page render | < 2 seconds |
| **MCP Response** | Tool execution | < 500ms |
| **QMS Compliance** | Document retrieval | < 3 seconds |
| **Uptime** | System availability | > 99.5% |

---

## Ready to Build

```
COMPLETE SCOPE
══════════════

✅ 3 source repositories analyzed
✅ 170+ services designed
✅ 120+ database tables (all PostgreSQL)
✅ 75+ dashboards planned
✅ 50+ MCP tools specified
✅ Full ISA-95 stack (ERP → MES → SCADA → Control)
✅ Complete QMS (ISO 9001 ready)
✅ CMMS/Maintenance management
✅ Professional alarm management (ISA-18.2)
✅ Historian with TimescaleDB
✅ Recipe management (ISA-88)
✅ ROS2 robotics integration
✅ ML fingerprinting + tool wear
✅ 14-week implementation plan

NO LOSS OF FUNCTION FROM ANY SOURCE

When you're ready, we begin Phase 1! 🏭
```
