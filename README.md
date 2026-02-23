# LEGO Factory v3

A unified smart manufacturing platform for LEGO brick production, combining industrial control systems (SCADA), manufacturing execution (MES), enterprise resource planning (ERP), quality management (QMS), ML-based anomaly detection, and digital twin visualization.

## Architecture Overview

LEGO Factory v3 follows the ISA-95 automation pyramid:

```
┌─────────────────────────────────────────────────────────────┐
│                    Level 4: ERP                              │
│     Sales Orders, MRP, Inventory, Financial, Customers       │
├─────────────────────────────────────────────────────────────┤
│                    Level 3: MES                              │
│   Work Orders, Scheduling, OEE, Labor, Recipes (ISA-88)     │
├─────────────────────────────────────────────────────────────┤
│                    Level 2: SCADA                            │
│    Tag Management, Alarms (ISA-18.2), Historian, HMI        │
├─────────────────────────────────────────────────────────────┤
│                    Level 1: PLC                              │
│   Modbus TCP/RTU, OPC-UA, Machine Controllers (GRBL/TinyG)  │
├─────────────────────────────────────────────────────────────┤
│                    Level 0: Field                            │
│       Sensors, Actuators, 3D Printers, CNC, Robots          │
└─────────────────────────────────────────────────────────────┘
```

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/GETTING_STARTED.md) | Quick setup guide and first steps |
| [API Reference](docs/API_REFERENCE.md) | Complete REST API documentation |
| [Architecture](docs/ARCHITECTURE.md) | System design and ISA-95 layers |
| [Environment Variables](docs/ENVIRONMENT_VARIABLES.md) | All configuration options |
| [Development](docs/DEVELOPMENT.md) | Developer guide and coding standards |
| [Test Strategy](docs/TEST_STRATEGY.md) | Testing approach and coverage targets |
| [Deployment](docs/DEPLOYMENT.md) | Production deployment guide |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [Security](docs/SECURITY.md) | Security considerations |

## Production Scheduling & Optimization

The MES layer includes a full-featured production scheduling system with an interactive Gantt chart, constraint-based optimizer, and real-time dispatch engine.

### Gantt Chart (`/mes/scheduling`)

Interactive drag-and-drop Gantt chart with:

- **Job visualization** across 10 physical machines with lane-stacking for concurrent jobs
- **Priority encoding** — left-border color/thickness indicates High (red), Medium (yellow), Low (gray)
- **Critical path highlighting** — orange glow on jobs forming the longest dependency chain, with red bold arrows
- **Maintenance windows** — hatched overlay blocks showing scheduled PM and downtime from CMMS
- **Bottleneck detection** — highest-utilization machine row highlighted with red accent and per-machine utilization badges
- **Rich tooltips** — hover any job to see duration, priority, machine utilization, dependencies, and due date
- **Dependency arrows** — curved SVG arrows between sequential operations within a work order
- **Drag-and-drop rescheduling** — move jobs between eligible machines with conflict detection
- **Search & quick filters** — text search across jobs/products/WOs, plus one-click filters for Overdue, High Priority, Running, Critical Path, and Unassigned

### Schedule Optimizer

Three optimization objectives powered by Google OR-Tools CP-SAT constraint solver:

| Objective | Description | Algorithm |
|-----------|-------------|-----------|
| **Minimize Makespan** | Complete all jobs as fast as possible | CP-SAT solver (optimal) |
| **Meet Due Dates** | Minimize weighted tardiness by priority | CP-SAT solver (optimal) |
| **Minimize Setup Time** | Group similar materials to reduce changeovers | Material-sorted heuristic |

Before/after comparison table shows makespan, setup time, and scheduled job deltas.

### Auto-Dispatch Engine

8 dispatch rules for real-time job assignment:

| Rule | Strategy |
|------|----------|
| SPT | Shortest Processing Time first |
| LPT | Longest Processing Time first |
| EDD | Earliest Due Date first |
| FIFO | First In, First Out |
| WSPT | Weighted Shortest Processing Time |
| Critical Ratio | Due date urgency / remaining time |
| Setup Min | Minimize material changeover time |
| Balanced | Composite of multiple factors |

Toggle auto-dispatch to listen for `job_completed` WebSocket events and automatically assign the next best job. Per-machine dispatch buttons allow manual triggering.

### What-If Scenario Simulator

Build scenarios and simulate impact before committing:

- **Rush Order** — inject a high-priority job and see makespan/displacement impact
- **Machine Down** — model unplanned downtime on any machine
- **Priority Change** — reprioritize a job and see cascade effects

### Dashboard KPIs

6-metric summary bar: Scheduled count, Makespan, Avg Utilization, On-Time %, Bottleneck machine, Overdue count.

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone and start all services
cd lego_factory
cp .env.example .env
docker-compose up -d

# Open in browser
open http://localhost:5000
```

### Option 2: Demo Mode (Quick Testing)

```bash
# No database required - uses in-memory SQLite
cd lego_factory
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run in demo mode
DEMO_MODE=true python run.py
```

### Option 3: Local Development

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate secure secrets (for production)
python scripts/generate_secrets.py --output .env.secrets

# Run application
python run.py
# Or: FLASK_APP=app.main:create_app flask run --port 5002
```

### Verify Installation

```bash
# Health check
curl http://localhost:5000/health

# API test (with demo credentials)
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | jq -r '.access_token')

curl http://localhost:5000/api/v1/erp/items \
  -H "Authorization: Bearer $TOKEN"
```

## Services & Ports

| Service | Port | Description |
|---------|------|-------------|
| Flask App | 5000/5002 | Main web application |
| PostgreSQL + TimescaleDB | 5432 | Database with time-series |
| Redis | 6379 | Cache and pub/sub |
| Slicer Service | 8766 | PrusaSlicer API |
| Fusion 360 Bridge | 8767 | CAD integration |
| ROS2 Bridge | 9090 | rosbridge WebSocket |
| noVNC | 6080 | Browser-based RViz/Gazebo |
| Grafana | 3000 | Metrics dashboards |

## API Reference

### Core APIs

| API | Base URL | Description |
|-----|----------|-------------|
| Health | `/health` | Service health check |
| SCADA | `/api/scada/*` | Tags, alarms, historian |
| PLC | `/api/plc/*` | Level 1 machine control |
| MES | `/api/mes/*` | Work orders, scheduling, recipes |
| ERP | `/api/erp/*` | Sales, MRP, inventory, financials |
| QMS | `/api/qms/*` | Documents, NCR/CAPA |
| CMMS | `/api/cmms/*` | Assets, maintenance |
| LEGO | `/api/lego/*` | Brick catalog, design |
| ML | `/api/ml/*` | Anomaly detection, inference |
| ROS2 | `/api/ros2/*` | Robot control, tasks |
| Unity | `/api/unity/*` | Digital twin state |
| MCP | `/api/mcp/*` | AI tool execution |
| Slicer | `/api/slicer/*` | STL slicing |

### Key Endpoints

#### Work Orders (MES)
```bash
# List work orders
GET /api/mes/work-orders

# Create work order
POST /api/mes/work-orders
{
  "product_id": "brick_2x4_red",
  "quantity_ordered": 500,
  "priority": 3,
  "due_date": "2024-01-25",
  "customer_id": "CUST001"
}

# Release for production
POST /api/mes/work-orders/{id}/release

# Get OEE metrics
GET /api/mes/oee?machine_id=prusa_mk4_1
```

#### Scheduling & Optimization (MES)
```bash
# Get Gantt chart data (jobs, machines, critical path, maintenance windows)
GET /api/mes/scheduling/gantt

# Run schedule optimizer (CP-SAT or heuristic)
POST /api/mes/scheduling/reschedule
{
  "algorithm": "cpsat",
  "objective": "makespan",
  "apply": true
}

# What-if scenario simulation
POST /api/mes/scheduling/what-if
{
  "name": "Rush order test",
  "changes": [
    {"type": "add_job", "duration_minutes": 120, "priority": 1}
  ]
}

# Auto-dispatch next job to a machine
POST /api/mes/dispatch/auto/{machine_id}
{"rule": "balanced"}

# Get available dispatch rules
GET /api/mes/dispatch/rules
```

#### Recipes (ISA-88)
```bash
# List recipes
GET /api/mes/recipes

# Create recipe
POST /api/mes/recipes
{
  "name": "2x4 Brick Standard",
  "product_id": "brick_2x4",
  "operations": [
    {"sequence": 10, "name": "Slice", "type": "design", "duration_min": 5},
    {"sequence": 20, "name": "Print", "type": "printing_fdm", "duration_min": 45}
  ],
  "parameters": {"infill": 20, "layer_height": 0.2}
}

# Submit for approval
POST /api/mes/recipes/{id}/submit

# Approve recipe
POST /api/mes/recipes/{id}/approve

# Download to machine
GET /api/mes/recipes/{id}/download?machine_id=prusa_mk4_1
```

#### Sales Orders (ERP)
```bash
# List sales orders
GET /api/erp/sales-orders

# Create sales order
POST /api/erp/sales-orders
{
  "customer_id": "CUST001",
  "lines": [
    {"item_id": "brick_2x4_red", "quantity": 500},
    {"item_id": "brick_2x2_blue", "quantity": 300}
  ]
}

# Confirm order
POST /api/erp/sales-orders/{id}/confirm
```

#### MRP (Material Requirements Planning)
```bash
# Run MRP
POST /api/erp/mrp/run
{
  "horizon_days": 90,
  "include_safety_stock": true
}

# View shortages
GET /api/erp/mrp/shortages

# View planned orders
GET /api/erp/mrp/runs/{run_id}
```

#### Alarms (SCADA)
```bash
# Get active alarms
GET /api/scada/alarms/active

# Acknowledge alarm
POST /api/scada/alarms/{id}/acknowledge
{
  "user_id": "operator1"
}
```

#### Level 1 PLC
```bash
# Machine status
GET /api/plc/{machine_id}/status

# Work coordinate systems
GET /api/plc/{machine_id}/wcs
POST /api/plc/{machine_id}/wcs/G54/zero

# Probing cycles
POST /api/plc/{machine_id}/probe/z
POST /api/plc/{machine_id}/probe/tool-length

# Tool management
GET /api/plc/{machine_id}/tools
POST /api/plc/{machine_id}/tools/1/change

# Execute G-code
POST /api/plc/{machine_id}/gcode
{"command": "G0 X10 Y10 Z5"}
```

#### LEGO Brick Design
```bash
# Get brick catalog
GET /api/lego/catalog

# Get brick dimensions
GET /api/lego/dimensions/2x4

# Create custom design
POST /api/lego/design
{
  "brick_type": "custom",
  "width_studs": 4,
  "length_studs": 6,
  "height_plates": 3,
  "color": "#FF0000"
}

# Slice for printing
POST /api/lego/slice
{
  "design_id": "...",
  "printer_profile": "prusa_mk4",
  "infill": 20
}
```

#### ML Inference
```bash
# Get model status
GET /api/ml/status

# Run anomaly detection
POST /api/ml/anomaly/detect
{
  "sensor_data": {...}
}

# Predict from G-code
POST /api/ml/predict
{
  "gcode": "G1 X10 Y20 F1000\nG1 Z5"
}
```

#### Robot Control (ROS2)
```bash
# Bridge status
GET /api/ros2/bridge/status

# List active robots
GET /api/ros2/robots

# Execute pick-place
POST /api/ros2/tasks
{
  "task_type": "pick_and_place",
  "robot_id": "niryo_ned2",
  "pick_position": {"x": 0.3, "y": 0.1, "z": 0.05},
  "place_position": {"x": 0.3, "y": -0.1, "z": 0.05}
}
```

#### Digital Twin (Unity)
```bash
# Get factory scene state
GET /api/unity/scene

# Update entity position
PUT /api/unity/entities/{entity_id}
{
  "transform": {
    "position": {"x": 1.0, "y": 0, "z": 0}
  }
}
```

## Project Structure

```
lego_factory/
├── app/                        # Flask application factory
│   └── main.py                 # App entry point
├── api/routes/                 # REST API endpoints (220+)
│   ├── scada_api.py            # SCADA: tags, alarms, historian
│   ├── plc_api.py              # Level 1: machine control
│   ├── mes_api.py              # MES: work orders, recipes, OEE
│   ├── erp_api.py              # ERP: sales, MRP, inventory
│   ├── qms_api.py              # QMS: documents, NCR/CAPA
│   ├── cmms_api.py             # CMMS: assets, maintenance
│   ├── lego_api.py             # LEGO: brick design
│   ├── ml_api.py               # ML: inference, anomaly
│   ├── ros2_api.py             # ROS2: robot control
│   ├── unity_api.py            # Unity: digital twin
│   ├── mcp_api.py              # MCP: AI tools
│   └── slicer_api.py           # Slicer: STL processing
├── config/
│   ├── database.py             # SQLAlchemy setup
│   ├── machines.json           # Machine definitions
│   └── plc_config.json         # Level 1 PLC tag mappings
├── models/                     # SQLAlchemy ORM (120+ tables)
│   ├── base.py                 # Base model with audit
│   ├── scada/                  # Tags, alarms, historian
│   ├── mes/                    # Work orders, operations, jobs
│   ├── erp/                    # Financial, sales, inventory
│   ├── qms/                    # Documents, NCR, CAPA
│   ├── cmms/                   # Assets, PM schedules
│   ├── lego/                   # Brick designs
│   └── ml/                     # Model versions, predictions
├── services/                   # Business logic (170+ services)
│   ├── scada/
│   │   ├── tag_management/     # Real-time tag values
│   │   ├── alarm_management/   # ISA-18.2 alarm lifecycle
│   │   ├── historian/          # TimescaleDB time-series
│   │   ├── machine_control/    # GRBL/TinyG controllers
│   │   └── sensor_acquisition/ # OPC-UA quality codes
│   ├── plc/                    # Level 1 industrial protocols
│   │   ├── modbus_client.py    # Modbus TCP/RTU
│   │   ├── opcua_client.py     # OPC-UA client
│   │   └── plc_manager.py      # Unified interface
│   ├── mes/
│   │   ├── work_order_service.py
│   │   ├── scheduling_service.py  # CP-SAT solver + dispatch + what-if
│   │   ├── dispatch_service.py    # 8 dispatch rules (SPT, EDD, WSPT...)
│   │   └── oee_service.py
│   ├── erp/
│   │   ├── financial_service.py
│   │   ├── sales_service.py
│   │   └── mrp_service.py
│   ├── qms/                    # Quality management
│   ├── cmms/                   # Maintenance
│   ├── lego/
│   │   ├── brick_catalog.py    # 400+ brick variants
│   │   ├── custom_brick_builder.py
│   │   └── fusion_client.py    # Fusion 360 integration
│   ├── ml/
│   │   ├── model/              # MM-DTAE-LSTM architecture
│   │   └── inference_service.py
│   ├── robotics/
│   │   └── ros2_bridge_service.py
│   ├── unity/
│   │   └── unity_state_service.py
│   └── mcp/
│       ├── server.py           # 50+ AI tools
│       └── tools/              # Tool implementations
├── templates/                  # 75+ dashboard templates
│   ├── scada/                  # Alarms, historian, HMI
│   ├── mes/                    # Work orders, scheduling
│   ├── erp/                    # Financial, sales
│   ├── lego/                   # Brick catalog
│   └── unity/                  # Digital twin viewer
├── ros2_ws/                    # ROS2 Jazzy workspace
│   └── src/
│       ├── lego_factory_msgs/  # Custom ROS2 messages
│       ├── lego_factory_niryo/ # Niryo Ned2 driver
│       └── lego_factory_xarm/  # xArm Lite 6 driver
├── slicer-service/             # Docker PrusaSlicer API
├── docker/
│   └── ros2-novnc/             # noVNC for RViz/Gazebo
├── database/migrations/        # Alembic migrations
├── tests/                      # Unit and integration tests
├── docker-compose.yml          # Full stack deployment
├── Dockerfile                  # Flask app image
└── requirements.txt            # Python dependencies
```

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Flask, SQLAlchemy, Flask-SocketIO, Celery |
| **Database** | PostgreSQL 15 + TimescaleDB (time-series) |
| **Cache** | Redis |
| **Messaging** | MQTT (Mosquitto), WebSocket |
| **ML** | PyTorch, MM-DTAE-LSTM encoder, NumPy |
| **Robotics** | ROS2 Jazzy, MoveIt2, Gazebo Harmonic |
| **3D Printing** | PrusaSlicer, OrcaSlicer |
| **CAD** | Fusion 360 API, STL/3MF |
| **Digital Twin** | Unity (ISO 23247) |
| **Optimization** | Google OR-Tools CP-SAT constraint solver |
| **Visualization** | Chart.js, Plotly, noVNC |
| **Industrial** | Modbus TCP/RTU, OPC-UA, GRBL, TinyG |

## Industrial Protocol Support

### Modbus TCP/RTU
```python
from services.plc import ModbusClient, ModbusConnectionConfig, ModbusTag

config = ModbusConnectionConfig(
    name='siemens_plc',
    protocol=ModbusProtocol.TCP,
    host='192.168.1.100',
    port=502,
    tags=[
        ModbusTag('conveyor_speed', 0, ModbusDataType.FLOAT32,
                  ModbusFunctionCode.READ_HOLDING_REGISTERS),
    ]
)

client = ModbusClient(config)
await client.connect()
value = await client.read_tag('conveyor_speed')
```

### OPC-UA
```python
from services.plc import OPCUAClient, OPCUAConnectionConfig, OPCUANode

config = OPCUAConnectionConfig(
    name='kepware',
    endpoint_url='opc.tcp://192.168.1.200:49320',
    nodes=[
        OPCUANode('temperature', 'ns=2;s=Channel1.Device1.Temp'),
    ]
)

client = OPCUAClient(config)
await client.connect()
await client.subscribe(callback=on_value_change)
```

## MCP Server (AI Integration)

The platform includes an MCP server with 50+ tools for AI assistants:

```bash
# List available tools
curl http://localhost:5000/api/mcp/tools

# Execute a tool
curl -X POST http://localhost:5000/api/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "create_work_order",
    "arguments": {
      "product_id": "brick_2x4_red",
      "quantity": 100
    }
  }'
```

Tool categories:
- **SCADA**: `connect_machine`, `get_alarms`, `ack_alarm`, `read_tag`
- **MES**: `create_work_order`, `schedule_jobs`, `get_oee`
- **ERP**: `create_sales_order`, `run_mrp`, `check_inventory`
- **LEGO**: `create_brick`, `slice_brick`, `export_stl`
- **ML**: `detect_anomaly`, `predict_from_gcode`
- **QMS**: `create_ncr`, `check_training`

## Performance Targets

| Metric | Target |
|--------|--------|
| Alarm response | < 500ms |
| Historian write rate | > 100k pts/sec |
| ML inference | < 100ms |
| MRP run (90 days) | < 30 seconds |
| Robot pick-place | < 10 seconds |
| Dashboard load | < 2 seconds |
| System uptime | > 99.5% |

## Troubleshooting

### Database Connection
```bash
# Check PostgreSQL
docker-compose logs postgres

# Verify TimescaleDB
docker-compose exec postgres psql -U lego -d lego_factory \
  -c "SELECT default_version, installed_version FROM pg_available_extensions WHERE name = 'timescaledb';"
```

### Serial Port (Linux)
```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

### ROS2 Bridge
```bash
# Check rosbridge
docker-compose logs ros2

# Test WebSocket
wscat -c ws://localhost:9090
```

## Running Tests

```bash
# Run all tests
make test
# Or: pytest tests/ -v

# Run unit tests only
make test-unit

# Run with coverage report
make coverage
# Or: pytest --cov=services --cov-report=html

# Run specific test file
pytest tests/unit/services/test_item_service.py -v
```

## Development

See [Development Guide](docs/DEVELOPMENT.md) for:
- Project structure and conventions
- Coding standards
- Testing patterns
- Database migrations
- Adding new features

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Write tests for new functionality
4. Run tests: `make test`
5. Run linting: `make lint`
6. Commit: `git commit -m "feat: add my feature"`
7. Submit a pull request

See [Development Guide](docs/DEVELOPMENT.md) for detailed contribution guidelines.

## License

Proprietary - LEGO Factory v3
