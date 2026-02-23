# System Architecture

LEGO Factory v3 is a comprehensive manufacturing execution system built on the ISA-95 (ANSI/ISA-95) enterprise-control integration standard.

## Overview

```
+-----------------------------------------------------------------------------------+
|                              LEVEL 4: ENTERPRISE                                   |
|   Business Planning & Logistics (ERP Integration)                                  |
+-----------------------------------------------------------------------------------+
                                        |
+-----------------------------------------------------------------------------------+
|                         LEVEL 3: MANUFACTURING OPERATIONS                          |
|   +------------+  +------------+  +------------+  +------------+                   |
|   |    ERP     |  |    MES     |  |    QMS     |  |   CMMS     |                   |
|   | (Items,    |  | (Schedules,|  | (Documents,|  | (Assets,   |                   |
|   |  Sales,    |  |  Jobs,     |  |  NCRs,     |  |  Maint.,   |                   |
|   |  Purch.)   |  |  OEE)      |  |  CAPAs)    |  |  PMs)      |                   |
|   +------------+  +------------+  +------------+  +------------+                   |
+-----------------------------------------------------------------------------------+
                                        |
+-----------------------------------------------------------------------------------+
|                           LEVEL 2: SUPERVISORY CONTROL                             |
|   +----------------+  +----------------+  +----------------+                       |
|   |     SCADA      |  |     Alarms     |  |   Historian    |                       |
|   | (Tags, Recipes)|  | (ISA-18.2)     |  | (TimescaleDB)  |                       |
|   +----------------+  +----------------+  +----------------+                       |
+-----------------------------------------------------------------------------------+
                                        |
+-----------------------------------------------------------------------------------+
|                            LEVEL 1: CONTROL DEVICES                                |
|   +------------+  +------------+  +------------+  +------------+                   |
|   |    PLC     |  |   Robots   |  |   Vision   |  |  Sensors   |                   |
|   | (Modbus)   |  | (ROS2)     |  | (OpenCV)   |  | (MQTT)     |                   |
|   +------------+  +------------+  +------------+  +------------+                   |
+-----------------------------------------------------------------------------------+
                                        |
+-----------------------------------------------------------------------------------+
|                              LEVEL 0: PHYSICAL PROCESS                             |
|   LEGO Brick Assembly, Sorting, Quality Inspection, Packaging                      |
+-----------------------------------------------------------------------------------+
```

## Service Dependencies

```
                    +------------------+
                    |    Flask App     |
                    |   (api/routes)   |
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                   |                   |
+--------v--------+  +-------v-------+  +-------v-------+
|   ERP Services  |  | MES Services  |  | QMS Services  |
| - ItemService   |  | - Scheduling  |  | - Documents   |
| - SalesService  |  | - Dispatch    |  | - NCRService  |
| - Purchasing    |  | - OEEService  |  | - CAPAs       |
| - MRPService    |  | - WorkOrders  |  +-------+-------+
+--------+--------+  +-------+-------+
+--------+--------+          |                   |
         |                   |                   |
         +-------------------+-------------------+
                             |
                    +--------v--------+
                    | CMMS Services   |
                    | - AssetService  |
                    | - Maintenance   |
                    | - PMService     |
                    +--------+--------+
                             |
         +-------------------+-------------------+
         |                   |                   |
+--------v--------+  +-------v-------+  +-------v-------+
|  SCADA Services |  |   ML Services |  | Vision Svcs   |
| - TagService    |  | - Anomaly Det.|  | - Inspection  |
| - AlarmService  |  | - Fingerprint |  | - Color Det.  |
| - RecipeService |  | - Prediction  |  | - Defect Det. |
+-----------------+  +---------------+  +---------------+
```

## Scheduling & Optimization Subsystem

The scheduling system is the core of the MES layer, combining constraint-based optimization with real-time dispatch and interactive visualization.

### Architecture

```
                    +----------------------------+
                    |   Scheduling UI (Gantt)    |
                    |  scheduling.html + JS      |
                    +-------------+--------------+
                                  |
                    +-------------v--------------+
                    |    MES API (mes_api.py)     |
                    |  /scheduling/gantt          |
                    |  /scheduling/reschedule     |
                    |  /scheduling/what-if        |
                    |  /dispatch/auto/{machine}   |
                    +---+--------+----------+----+
                        |        |          |
           +------------v--+ +---v------+ +-v-----------+
           | Scheduling    | | Dispatch | | What-If     |
           | Service       | | Service  | | Simulator   |
           | - CP-SAT      | | - 8 rules| | - Scenario  |
           | - Heuristic   | | - SPT    | |   cloning   |
           | - Setup matrix| | - EDD    | | - Impact    |
           | - Critical    | | - WSPT   | |   analysis  |
           |   path        | | - etc.   | |             |
           +-------+-------+ +----+-----+ +------+------+
                   |               |              |
           +-------v---------------v--------------v------+
           |              Database Layer                   |
           |  Jobs, Operations, WorkOrders,                |
           |  MachineAvailability, SetupMatrix              |
           +----------------------------------------------+
```

### CP-SAT Constraint Solver

The scheduling optimizer uses Google OR-Tools CP-SAT (Constraint Programming - Satisfiability) solver:

- **Variables**: Job start times, machine assignments, job ordering
- **Constraints**: Machine capacity (1 job at a time), operation precedence, maintenance blackouts, eligible machines
- **Objectives**: Minimize makespan, minimize weighted tardiness, minimize setup time
- **Fallback**: Priority-based greedy heuristic when OR-Tools is unavailable

### Setup Time Matrix

Material changeover times between product types (PLA, ABS, PETG, etc.) are defined in `MATERIAL_SETUP_MATRIX` with per-machine multipliers. The `setup_time` objective groups similar materials on the same machine to minimize changeovers.

### Critical Path Computation

The critical path is the longest chain of dependent jobs by total duration. Computed via DFS traversal of `depends_on` relationships in `_compute_critical_path()`. Returned in the Gantt API response and visualized with orange glow + red arrows.

### Dispatch Rules

| Rule | Algorithm | Best For |
|------|-----------|----------|
| SPT | Shortest Processing Time | Minimizing average flow time |
| LPT | Longest Processing Time | Load balancing |
| EDD | Earliest Due Date | Meeting deadlines |
| FIFO | First In, First Out | Fairness |
| WSPT | Weighted SPT | Priority-weighted throughput |
| Critical Ratio | Due date / remaining time | Urgency-based |
| Setup Min | Group by material type | Reducing changeovers |
| Slack Time | Due date - processing time | Tight schedules |

Composite rules (`balanced`, `urgent_first`, `efficient`) combine multiple factors with weighted scoring.

### Maintenance-Aware Scheduling

The scheduler integrates with CMMS to respect maintenance windows:
1. `get_maintenance_blackouts()` fetches from `MachineAvailability` (MES) and `MaintenanceWorkOrder` (CMMS)
2. `schedule_with_maintenance()` excludes blackout periods from available machine time
3. Gantt chart renders maintenance blocks as hatched overlay with reason text

### WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `job_dispatched` | Server → Client | Job assigned to machine |
| `job_completed` | Server → Client | Job finished (triggers auto-dispatch) |
| `job_rescheduled` | Server → Client | Job moved to new time/machine |

## Key Workflows

### 1. Order to Production

```
Customer Order → Sales Order → MRP Explosion → Work Order → Production → Shipment
      |              |              |              |              |
      v              v              v              v              v
  validate      allocate       explode BOM    schedule       record OEE
  customer      inventory      requirements     jobs          track quality
```

**Data Flow:**
1. `SalesService.create_order()` creates a sales order
2. `MRPService.run_mrp()` explodes BOMs and generates requirements
3. `SchedulingService.schedule_jobs()` optimizes machine assignments
4. `OEEService.calculate_oee()` tracks production efficiency
5. `SalesService.create_shipment()` records fulfillment

### 2. Quality Control Loop

```
+----------------+     +----------------+     +----------------+
| Detect Issue   | --> | Create NCR     | --> | Disposition    |
| (Inspection)   |     | (Non-Conform)  |     | (Use As-Is/    |
+----------------+     +----------------+     |  Rework/Scrap) |
                              |              +--------+-------+
                              v                       |
                       +----------------+             |
                       | Create CAPA    | <-----------+
                       | (if needed)    |
                       +-------+--------+
                               |
        +----------------------+----------------------+
        |                      |                      |
+-------v-------+      +-------v-------+      +-------v-------+
| Root Cause    |      | Corrective    |      | Verify        |
| Analysis      |      | Actions       |      | Effectiveness |
+---------------+      +---------------+      +---------------+
```

**Services Involved:**
- `NCRService.create_ncr()` - Record non-conformance
- `NCRService.set_disposition()` - Determine disposition
- `NCRService.create_capa()` - Create corrective action
- `NCRService.verify_capa_effectiveness()` - Close the loop

### 3. Maintenance Cycle

```
Asset Registration → PM Schedule → Work Order Generation → Execution → Closure
        |                 |                 |                  |          |
        v                 v                 v                  v          v
   create asset      define PMs       auto-generate       record labor   update
   add meters      set triggers       when due          and materials   next due
```

**Services Involved:**
- `AssetService.create_asset()` - Register equipment
- `PMService.create_pm_schedule()` - Define preventive maintenance
- `PMService.generate_pm_work_orders()` - Auto-create work orders
- `MaintenanceService.complete_work_order()` - Close and calculate costs

## Technology Stack

### Backend
| Component | Technology | Purpose |
|-----------|------------|---------|
| Web Framework | Flask 3.x | REST API |
| ORM | SQLAlchemy 2.x | Database access |
| Migrations | Alembic | Schema management |
| Task Queue | Celery (optional) | Background jobs |
| Optimization | Google OR-Tools CP-SAT | Schedule optimization |
| Caching | Redis | Session/data cache |

### Database
| Component | Technology | Purpose |
|-----------|------------|---------|
| Primary DB | PostgreSQL 15+ | Relational data |
| Time Series | TimescaleDB | Historian data |
| Search | PostgreSQL FTS | Full-text search |

### Messaging
| Component | Technology | Purpose |
|-----------|------------|---------|
| Event Broker | MQTT (Mosquitto) | Real-time events |
| ROS2 Bridge | roslibpy | Robot integration |
| WebSocket | Flask-SocketIO | Real-time UI |

### Machine Learning
| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | PyTorch | ML models |
| Vision | OpenCV | Image processing |
| Inference | ONNX Runtime | Optimized inference |

### Security
| Component | Technology | Purpose |
|-----------|------------|---------|
| Authentication | JWT (Flask-JWT-Extended) | API auth |
| TPM | python-tpm2-pytss | Hardware security |
| Encryption | cryptography | Data protection |

### Deployment
| Component | Technology | Purpose |
|-----------|------------|---------|
| Containerization | Docker | Packaging |
| Orchestration | Kubernetes | Production |
| Monitoring | Prometheus + Grafana | Observability |

## Data Models

### Core Entities

```
+------------------+       +------------------+       +------------------+
|      Item        |<----->|      BOM         |<----->|   BOMLine        |
| - item_id        |       | - parent_id      |       | - component_id   |
| - name           |       | - effective_date |       | - quantity       |
| - item_type      |       +------------------+       | - uom            |
| - standard_cost  |                                  +------------------+
+------------------+
        |
        v
+------------------+       +------------------+       +------------------+
|   SalesOrder     |<----->|  SalesOrderLine  |<----->|    Shipment      |
| - order_number   |       | - item_id        |       | - tracking       |
| - customer_id    |       | - quantity       |       | - carrier        |
| - status         |       | - unit_price     |       | - shipped_date   |
+------------------+       +------------------+       +------------------+
```

### ISA-95 Work Order Model

```
+------------------+       +------------------+       +------------------+
|   WorkOrder      |<----->|      Job         |<----->|   Operation      |
| - wo_id          |       | - job_id         |       | - sequence       |
| - product_id     |       | - machine_id     |       | - work_center    |
| - quantity       |       | - status         |       | - run_time       |
| - planned_start  |       | - actual_start   |       | - setup_time     |
+------------------+       +------------------+       +------------------+
```

## API Structure

All APIs follow RESTful conventions with consistent patterns:

```
/api/v1/
├── erp/
│   ├── items/          # Item master data
│   ├── sales/          # Sales orders
│   ├── purchasing/     # Purchase orders
│   └── mrp/            # MRP planning
├── mes/
│   ├── work-orders/    # Production orders
│   ├── jobs/           # Job scheduling
│   └── oee/            # OEE metrics
├── qms/
│   ├── documents/      # Document control
│   ├── ncrs/           # Non-conformances
│   └── capas/          # Corrective actions
├── cmms/
│   ├── assets/         # Asset management
│   ├── maintenance/    # Work orders
│   └── pm/             # PM schedules
├── scada/
│   ├── tags/           # Process variables
│   ├── alarms/         # Alarm management
│   └── historian/      # Historical data
└── health/             # Health checks
```

## Configuration

Configuration follows a layered approach:

1. **Defaults** - Defined in `config/settings.py`
2. **Environment** - Override via environment variables
3. **Runtime** - Dynamic configuration via API

Key configuration files:
- `config/settings.py` - Master configuration
- `config/machines.json` - Machine definitions
- `config/plc_config.json` - PLC mappings

See [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) for complete reference.

## Deployment Architectures

### Development (Single Node)

```
+------------------------------------------+
|              Developer Machine            |
| +--------+ +--------+ +--------+         |
| | Flask  | | Postgres| | Redis  |         |
| | :5000  | | :5432  | | :6379  |         |
| +--------+ +--------+ +--------+         |
+------------------------------------------+
```

### Production (Kubernetes)

```
+------------------+     +------------------+
|   Load Balancer  |     |   Ingress        |
+--------+---------+     +--------+---------+
         |                        |
+--------v------------------------v---------+
|              Kubernetes Cluster            |
|                                            |
| +------------+ +------------+ +----------+ |
| | Flask Pods | | Worker Pods| | ML Pods  | |
| | (replicas) | | (Celery)   | | (Infer.) | |
| +------------+ +------------+ +----------+ |
|                                            |
| +------------------------------------------+
| |              StatefulSets                |
| | +----------+ +----------+ +----------+   |
| | | Postgres | | Redis    | | Mosquitto|   |
| | | (HA)     | | (Cluster)| | (MQTT)   |   |
| | +----------+ +----------+ +----------+   |
+--------------------------------------------+
```

## Security Architecture

### Authentication Flow

```
Client --> API Gateway --> JWT Validation --> Service
                |
                v
          Token Refresh
                |
                v
          Rate Limiting
```

### Data Protection

- **At Rest**: AES-256 encryption for sensitive fields
- **In Transit**: TLS 1.3 for all connections
- **TPM**: Hardware-backed key storage (optional)

See [SECURITY.md](SECURITY.md) for detailed security documentation.
