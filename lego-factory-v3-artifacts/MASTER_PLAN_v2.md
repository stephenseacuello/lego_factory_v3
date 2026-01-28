# LEGO Factory - Master Integration Plan v2

## Three Repositories → One Unified System

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SOURCE REPOSITORIES                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌───────────────────┐  │
│  │    flask_cnc_app     │  │ lego-mcp-fusion360   │  │gcode_fingerprinting│ │
│  ├──────────────────────┤  ├──────────────────────┤  ├───────────────────┤  │
│  │ • 80+ Services       │  │ • 50+ Services       │  │ • 2 ML Models     │  │
│  │ • 41 Dashboards      │  │ • 16+ Dashboards     │  │ • 19 Notebooks    │  │
│  │ • Unity Digital Twin │  │ • MCP Server         │  │ • Training Scripts│  │
│  │ • TinyG/GRBL Control │  │ • ISA-95 MES/ERP     │  │ • Inference API   │  │
│  │ • MCC/Arduino DAQ    │  │ • LEGO Brick Design  │  │ • 668-Token Vocab │  │
│  │ • Data Alignment     │  │ • Slicer Service     │  │ • Pretrained Wts  │  │
│  │ • ROS2 Workspace     │  │ • Scheduling (RL)    │  │ • Ablation Studies│  │
│  │ • Robot Arms         │  │ • Quality SPC/FMEA   │  │                   │  │
│  │ • Vision Inspection  │  │                      │  │                   │  │
│  └──────────────────────┘  └──────────────────────┘  └───────────────────┘  │
│           │                         │                         │              │
│           └─────────────────────────┼─────────────────────────┘              │
│                                     │                                        │
│                                     ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         LEGO FACTORY                                  │   │
│  │                    (Unified Repository)                               │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                       │   │
│  │  Total: 150+ Services | 65+ Dashboards | 40+ MCP Tools | 2 ML Models │   │
│  │                                                                       │   │
│  │  Complete ISA-95 Stack: ERP → MES → SCADA → Control → Sensors → ML   │   │
│  │                                                                       │   │
│  │  Full ERP: GL, AP, AR, Sales, Procurement, Inventory, MRP, CRP       │   │
│  │                                                                       │   │
│  │  ROS2 Integration: MoveIt2, Gazebo, Multi-Robot Coordination         │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
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
│  ═══════════════                                                             │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐     │
│  │  Claude   │ │   Flask   │ │   Unity   │ │  Grafana  │ │  Fusion   │     │
│  │  Desktop  │ │  Portal   │ │  3D Twin  │ │  Metrics  │ │   360     │     │
│  │  (MCP)    │ │ (65+ UIs) │ │           │ │           │ │  Add-in   │     │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘     │
│        └─────────────┴─────────────┴─────────────┴─────────────┘            │
│                                     │                                        │
│                                     ▼                                        │
│  API LAYER (Flask + FastAPI)                                                │
│  ═══════════════════════════                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ /api/lego/*      Brick design, catalog, dimensions, slicing          │   │
│  │ /api/scada/*     Machine control, sensors, jobs, alignment           │   │
│  │ /api/mes/*       Work orders, scheduling, routing, BOM               │   │
│  │ /api/erp/*       FULL ERP (see expanded section below)               │   │
│  │ /api/quality/*   SPC, FMEA, QFD, inspection, zero-defect             │   │
│  │ /api/ml/*        Fingerprinting, inference, training, anomaly        │   │
│  │ /api/unity/*     Digital twin state, commands, playback              │   │
│  │ /api/ai/*        Copilot, agents, causal AI, predictions             │   │
│  │ /api/ros/*       ROS2 bridge, robot commands, sensor topics          │   │
│  │ /api/robot/*     Niryo Ned2, xArm Lite 6 control                     │   │
│  │ /api/supply/*    Supplier portal, traceability, compliance           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│  ═══════════════════════════════════╪════════════════════════════════════   │
│                              ISA-95 LEVELS                                   │
│  ═══════════════════════════════════╪════════════════════════════════════   │
│                                     │                                        │
│  LEVEL 4: ERP (EXPANDED) ───────────┼───────────────────────────────────    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  FINANCIAL MANAGEMENT                                                 │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │
│  │  │   GL    │ │   AP    │ │   AR    │ │  Cash   │ │  Cost   │        │   │
│  │  │ Ledger  │ │Payables │ │Receivbl │ │  Mgmt   │ │  Acctg  │        │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │   │
│  │                                                                       │   │
│  │  SALES & DISTRIBUTION                                                 │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │
│  │  │Customer │ │ Pricing │ │  Sales  │ │Shipping │ │ Returns │        │   │
│  │  │ Master  │ │ & Quotes│ │ Orders  │ │& Deliver│ │  & RMA  │        │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │   │
│  │                                                                       │   │
│  │  PROCUREMENT                                                          │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │
│  │  │ Vendor  │ │  Requi- │ │Purchase │ │Receiving│ │ Invoice │        │   │
│  │  │ Master  │ │ sitions │ │ Orders  │ │& Inspect│ │ Match   │        │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │   │
│  │                                                                       │   │
│  │  INVENTORY MANAGEMENT                                                 │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │
│  │  │  Item   │ │Warehouse│ │Lot/Serial│ │  Cycle  │ │Valuation│        │   │
│  │  │ Master  │ │ & Bins  │ │ Tracking│ │ Count   │ │FIFO/AVG │        │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │   │
│  │                                                                       │   │
│  │  PRODUCTION PLANNING                                                  │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                     │   │
│  │  │   BOM   │ │   MRP   │ │   MPS   │ │   CRP   │                     │   │
│  │  │ Mgmt    │ │Material │ │ Master  │ │Capacity │                     │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘                     │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│  LEVEL 3: MES ──────────────────────┼───────────────────────────────────    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Work Orders │ Routing │ CP-SAT Scheduler │ NSGA-II │ RL Dispatch     │   │
│  │ Quality SPC (EWMA/CUSUM/T²) │ FMEA │ QFD │ Digital Thread │ OEE      │   │
│  │ Zero-Defect │ Vision AI (YOLO11) │ Traceability │ Compliance          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│  LEVEL 2: SCADA ────────────────────┼────────────────────── ◀ KEY LAYER    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────┐  │   │
│  │  │ Zero/Home  │  │  Sensor    │  │    Job     │  │ Data Alignment │  │   │
│  │  │ Machines   │  │ Collection │  │ Execution  │  │ (G-code=Truth) │  │   │
│  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └───────┬────────┘  │   │
│  │        └───────────────┴───────────────┴─────────────────┘           │   │
│  │                                │                                      │   │
│  │                                ▼                                      │   │
│  │  ┌──────────────────────────────────────────────────────────────┐    │   │
│  │  │           G-CODE FINGERPRINTING (ML Pipeline)                 │    │   │
│  │  │   Aligned Data → MM-DTAE-LSTM → MultiHead Decoder            │    │   │
│  │  │   Operation: 100% │ Token: 90.23% │ Anomaly Detection        │    │   │
│  │  └──────────────────────────────────────────────────────────────┘    │   │
│  │                                                                       │   │
│  │  Factory Cell Orchestrator │ Material Flow │ Historical Playback     │   │
│  │  Unity Digital Twin Sync │ 41 SCADA Dashboards                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│  LEVEL 1: CONTROL (HYBRID) ─────────┼───────────────────────────────────    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │   DIRECT SERIAL                          ROS2 LAYER                  │   │
│  │   (Simple Machines)                      (Complex Robotics)          │   │
│  │                                                                       │   │
│  │   ┌─────────────────┐                   ┌─────────────────────────┐  │   │
│  │   │ TinyG (Bantam)  │                   │    rosbridge_suite      │  │   │
│  │   │ GRBL            │    ◀── Flask ──▶  │    (WebSocket Bridge)   │  │   │
│  │   │ Marlin (Prusa)  │                   └───────────┬─────────────┘  │   │
│  │   │ Bambu MQTT      │                               │ DDS            │   │
│  │   └─────────────────┘                   ┌───────────┴─────────────┐  │   │
│  │                                         │                         │  │   │
│  │                                    ┌────┴────┐              ┌────┴────┐ │
│  │                                    │  Niryo  │              │  xArm   │ │
│  │                                    │  Node   │              │  Node   │ │
│  │                                    │+MoveIt2 │              │+MoveIt2 │ │
│  │                                    └────┬────┘              └────┬────┘ │
│  │                                         │                        │     │   │
│  └─────────────────────────────────────────┼────────────────────────┼─────┘   │
│                                            │                        │         │
│  LEVEL 0: SENSORS & HARDWARE ──────────────┼────────────────────────┼────    │
│  ┌─────────────────────────────────────────┼────────────────────────┼─────┐  │
│  │                                         │                        │     │  │
│  │   ┌─────────────────┐              ┌────┴────┐              ┌────┴────┐│  │
│  │   │ Bantam CNC      │              │ Niryo   │              │ xArm    ││  │
│  │   │ Bambu P1S       │              │ Ned2    │              │ Lite 6  ││  │
│  │   │ Prusa MK3S+     │              │(Ethernet)              │(Ethernet)│  │
│  │   └─────────────────┘              └─────────┘              └─────────┘│  │
│  │                                                                        │  │
│  │   ┌────────────────────────────────────────────────────────────────┐  │  │
│  │   │              ROS2 SENSOR AGGREGATOR NODE                        │  │  │
│  │   │   MCC USB-1608G ──┬──▶ /factory/sensors (synchronized)         │  │  │
│  │   │   Arduino Mega ───┤    (message_filters::TimeSynchronizer)     │  │  │
│  │   │   USB Cameras ────┘                                             │  │  │
│  │   └────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: ROS2 Integration Architecture

### Why ROS2? (And Why Not for Everything)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ROS2 DECISION MATRIX                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  USE ROS2 ✅                              DON'T USE ROS2 ❌                  │
│  ═══════════                              ══════════════════                 │
│                                                                              │
│  • Niryo Ned2 (native support)           • TinyG/GRBL (simple serial)       │
│  • xArm Lite 6 (official packages)       • Bambu/Prusa (proprietary API)    │
│  • Multi-robot coordination              • MES/ERP business logic           │
│  • Sensor fusion (time sync)             • Web dashboards                   │
│  • Motion planning (MoveIt2)             • ML inference (PyTorch)           │
│  • Collision avoidance                   • Database operations              │
│  • Gazebo simulation                     • REST API endpoints               │
│  • Real-time control loops                                                   │
│                                                                              │
│  BENEFITS:                               KEEP IN FLASK:                      │
│  • Built-in time synchronization         • Simpler for serial devices       │
│  • tf2 coordinate transforms             • Web-native (templates, REST)     │
│  • Action servers for robotics           • Python ecosystem (pandas, etc)   │
│  • Hardware abstraction                  • Rapid development                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### ROS2 Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FLASK ↔ ROS2 INTEGRATION                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         FLASK APPLICATION LAYER                        │  │
│  │                     (Orchestration, Business Logic)                    │  │
│  │                                                                        │  │
│  │  • MES/ERP services                • Web dashboards (65+)             │  │
│  │  • SCADA job orchestration         • MCP tools for Claude             │  │
│  │  • Data alignment engine           • ML fingerprinting                │  │
│  │  • Quality/SPC                     • Digital thread                   │  │
│  │                                                                        │  │
│  │  ROS2 Client (roslibpy):                                              │  │
│  │  ┌────────────────────────────────────────────────────────────────┐   │  │
│  │  │  client = roslibpy.Ros(host='localhost', port=9090)            │   │  │
│  │  │  # Subscribe to sensor topics                                   │   │  │
│  │  │  # Call robot action servers                                    │   │  │
│  │  │  # Publish commands                                             │   │  │
│  │  └────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                        │  │
│  └────────────────────────────────┬───────────────────────────────────────┘  │
│                                   │                                          │
│                          WebSocket (port 9090)                               │
│                          rosbridge_suite                                     │
│                                   │                                          │
│  ┌────────────────────────────────┴───────────────────────────────────────┐  │
│  │                         ROS2 BRIDGE LAYER                              │  │
│  │                      (rosbridge_suite + custom)                        │  │
│  │                                                                        │  │
│  │  Topics:                                                               │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │  │
│  │  │ /lego_factory/  │  │ /lego_factory/  │  │ /lego_factory/  │        │  │
│  │  │ sensors         │  │ robot_state     │  │ machine_state   │        │  │
│  │  │ (SensorData)    │  │ (JointState)    │  │ (MachineState)  │        │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘        │  │
│  │                                                                        │  │
│  │  Action Servers:                                                       │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │  │
│  │  │ /niryo/         │  │ /xarm/          │  │ /factory/       │        │  │
│  │  │ pick_place      │  │ pick_place      │  │ execute_cell    │        │  │
│  │  │ (PickPlace)     │  │ (PickPlace)     │  │ (CellWorkflow)  │        │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘        │  │
│  │                                                                        │  │
│  │  Services:                                                             │  │
│  │  ┌─────────────────┐  ┌─────────────────┐                             │  │
│  │  │ /factory/       │  │ /factory/       │                             │  │
│  │  │ emergency_stop  │  │ get_robot_state │                             │  │
│  │  └─────────────────┘  └─────────────────┘                             │  │
│  │                                                                        │  │
│  └────────────────────────────────┬───────────────────────────────────────┘  │
│                                   │                                          │
│                              DDS (Fast-RTPS)                                 │
│                                   │                                          │
│  ┌────────────────────────────────┴───────────────────────────────────────┐  │
│  │                         ROS2 CONTROL LAYER                             │  │
│  │                      (Real-time Robot Control)                         │  │
│  │                                                                        │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │  │
│  │  │  Niryo Ned2  │  │  xArm Lite 6 │  │   Sensor     │  │   Gazebo   │ │  │
│  │  │  ROS2 Node   │  │  ROS2 Node   │  │  Aggregator  │  │    Sim     │ │  │
│  │  │              │  │              │  │              │  │            │ │  │
│  │  │ • MoveIt2    │  │ • MoveIt2    │  │ • MCC DAQ    │  │ • Physics  │ │  │
│  │  │ • Gripper    │  │ • Gripper    │  │ • Arduino    │  │ • Viz      │ │  │
│  │  │ • Actions    │  │ • Actions    │  │ • Cameras    │  │ • Testing  │ │  │
│  │  │ • tf2        │  │ • tf2        │  │ • Time sync  │  │            │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### ROS2 Package Structure

```
lego_factory_ros/
├── lego_factory_msgs/               # Custom message/action definitions
│   ├── msg/
│   │   ├── SensorData.msg           # Unified sensor message
│   │   │   └── Header header
│   │   │       float32[155] continuous_data
│   │   │       int32[4] categorical_data
│   │   │       float32 mcc_temperature
│   │   │       float32 mcc_vibration
│   │   │       float32 mcc_current
│   │   │       float32 arduino_proximity
│   │   │       float32 arduino_pressure
│   │   │
│   │   ├── MachineState.msg         # CNC/Printer state
│   │   │   └── Header header
│   │   │       string machine_id
│   │   │       string state  # idle, running, error, homing
│   │   │       geometry_msgs/Point position
│   │   │       float32 feed_rate
│   │   │       int32 current_line
│   │   │       float32 progress_pct
│   │   │
│   │   └── JobStatus.msg            # SCADA job status
│   │       └── string job_id
│   │           string status
│   │           float32 progress
│   │           string current_operation
│   │
│   ├── action/
│   │   ├── PickPlace.action         # Robot pick/place
│   │   │   └── # Goal
│   │   │       string action  # pick, place, load, unload
│   │   │       geometry_msgs/Pose target_pose
│   │   │       float32 gripper_position
│   │   │       ---
│   │   │       # Result
│   │   │       bool success
│   │   │       string message
│   │   │       ---
│   │   │       # Feedback
│   │   │       float32 progress
│   │   │       string current_phase
│   │   │
│   │   ├── ExecuteGcode.action      # G-code execution
│   │   │   └── # Goal
│   │   │       string gcode_content
│   │   │       bool collect_sensors
│   │   │       ---
│   │   │       # Result
│   │   │       bool success
│   │   │       string aligned_data_path
│   │   │       ---
│   │   │       # Feedback
│   │   │       int32 current_line
│   │   │       int32 total_lines
│   │   │       float32 progress
│   │   │
│   │   └── CellWorkflow.action      # Full factory cell workflow
│   │       └── # Goal
│   │           string workflow_id
│   │           string[] steps
│   │           ---
│   │           # Result
│   │           bool success
│   │           string[] step_results
│   │           ---
│   │           # Feedback
│   │           string current_step
│   │           float32 progress
│   │
│   └── srv/
│       ├── EmergencyStop.srv
│       │   └── ---
│       │       bool success
│       │       string message
│       │
│       └── GetSensorData.srv
│           └── string[] sensor_ids
│               ---
│               SensorData data
│
├── lego_factory_bringup/            # Launch files
│   ├── launch/
│   │   ├── factory_cell.launch.py   # Full system
│   │   ├── robots_only.launch.py    # Just robots
│   │   ├── sensors_only.launch.py   # Just sensors
│   │   ├── simulation.launch.py     # Gazebo sim
│   │   └── rosbridge.launch.py      # Bridge only
│   │
│   └── config/
│       ├── niryo_config.yaml
│       ├── xarm_config.yaml
│       ├── sensor_config.yaml
│       └── moveit_config/
│           ├── niryo.srdf
│           └── xarm.srdf
│
├── lego_factory_robots/             # Robot control nodes
│   ├── niryo_controller/
│   │   ├── niryo_controller_node.py
│   │   └── niryo_moveit_interface.py
│   │
│   └── xarm_controller/
│       ├── xarm_controller_node.py
│       └── xarm_moveit_interface.py
│
├── lego_factory_sensors/            # Sensor aggregation
│   ├── mcc_daq_node/
│   │   └── mcc_daq_publisher.py
│   │
│   ├── arduino_node/
│   │   └── arduino_publisher.py
│   │
│   └── sensor_aggregator/
│       └── aggregator_node.py       # TimeSynchronizer
│
├── lego_factory_bridge/             # Flask ↔ ROS2 bridge
│   ├── rosbridge_config/
│   │   └── rosbridge_params.yaml
│   │
│   └── flask_ros_bridge/
│       └── bridge_node.py           # Custom high-level commands
│
└── lego_factory_gazebo/             # Simulation
    ├── worlds/
    │   └── factory_cell.world
    │
    ├── models/
    │   ├── niryo_ned2/
    │   │   ├── model.sdf
    │   │   └── meshes/
    │   ├── xarm_lite6/
    │   ├── bantam_cnc/
    │   ├── bambu_p1s/
    │   └── lego_bricks/
    │
    └── launch/
        └── simulation.launch.py
```

### ROS2 Key Integration Points

#### 1. Flask → ROS2 (Robot Commands)

```python
# services/ros_bridge/ros_client.py

import roslibpy
from typing import Callable, Optional

class ROSBridgeClient:
    """Flask service for ROS2 communication via rosbridge"""
    
    def __init__(self, host: str = 'localhost', port: int = 9090):
        self.client = roslibpy.Ros(host=host, port=port)
        self.client.run()
        self._action_clients = {}
        
    async def call_pick_place(
        self,
        robot: str,  # 'niryo' or 'xarm'
        action: str,  # 'pick', 'place', 'load', 'unload'
        pose: dict,
        gripper_position: float = 0.0,
        on_feedback: Optional[Callable] = None
    ) -> dict:
        """Call robot pick/place action"""
        
        action_name = f'/{robot}/pick_place'
        
        if action_name not in self._action_clients:
            self._action_clients[action_name] = roslibpy.actionlib.ActionClient(
                self.client,
                action_name,
                'lego_factory_msgs/action/PickPlace'
            )
        
        goal = roslibpy.actionlib.Goal(
            self._action_clients[action_name],
            {
                'action': action,
                'target_pose': {
                    'position': pose['position'],
                    'orientation': pose['orientation']
                },
                'gripper_position': gripper_position
            }
        )
        
        if on_feedback:
            goal.on('feedback', on_feedback)
        
        goal.send()
        result = await goal.wait()
        return result
    
    def subscribe_sensors(self, callback: Callable):
        """Subscribe to unified sensor topic"""
        topic = roslibpy.Topic(
            self.client,
            '/lego_factory/sensors',
            'lego_factory_msgs/msg/SensorData'
        )
        topic.subscribe(callback)
        return topic
    
    async def emergency_stop(self) -> bool:
        """Call emergency stop service"""
        service = roslibpy.Service(
            self.client,
            '/factory/emergency_stop',
            'lego_factory_msgs/srv/EmergencyStop'
        )
        result = await service.call({})
        return result['success']
```

#### 2. ROS2 Sensor Aggregator (Time Synchronization)

```python
# lego_factory_sensors/sensor_aggregator/aggregator_node.py

import rclpy
from rclpy.node import Node
from message_filters import Subscriber, TimeSynchronizer
from lego_factory_msgs.msg import SensorData
from std_msgs.msg import Float32MultiArray

class SensorAggregator(Node):
    """Aggregate and time-synchronize all sensor data"""
    
    def __init__(self):
        super().__init__('sensor_aggregator')
        
        # Subscribers with message_filters for time sync
        self.mcc_sub = Subscriber(self, Float32MultiArray, '/mcc_daq/data')
        self.arduino_sub = Subscriber(self, Float32MultiArray, '/arduino/data')
        self.robot_state_sub = Subscriber(self, JointState, '/joint_states')
        
        # Time synchronizer (within 10ms tolerance)
        self.sync = TimeSynchronizer(
            [self.mcc_sub, self.arduino_sub, self.robot_state_sub],
            queue_size=10,
            slop=0.01  # 10ms tolerance
        )
        self.sync.registerCallback(self.synchronized_callback)
        
        # Publisher for unified data
        self.sensor_pub = self.create_publisher(
            SensorData,
            '/lego_factory/sensors',
            10
        )
        
        self.get_logger().info('Sensor aggregator initialized')
    
    def synchronized_callback(self, mcc_msg, arduino_msg, robot_msg):
        """Called when all sensors have synchronized data"""
        
        msg = SensorData()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'factory_cell'
        
        # MCC DAQ data (high-speed acquisition)
        msg.mcc_temperature = mcc_msg.data[0]
        msg.mcc_vibration = mcc_msg.data[1]
        msg.mcc_current = mcc_msg.data[2]
        msg.mcc_load = mcc_msg.data[3]
        
        # Arduino data
        msg.arduino_proximity = arduino_msg.data[0]
        msg.arduino_pressure = arduino_msg.data[1]
        
        # Pack into continuous array for ML (155 channels)
        msg.continuous_data = list(mcc_msg.data) + list(arduino_msg.data)
        
        self.sensor_pub.publish(msg)
```

#### 3. Factory Cell Workflow (Multi-Robot Coordination)

```python
# services/factory_cell/cell_orchestrator.py

class FactoryCellOrchestrator:
    """Orchestrate multi-robot factory cell operations"""
    
    def __init__(self, ros_client: ROSBridgeClient):
        self.ros = ros_client
        
    async def execute_brick_production(
        self,
        job: SCADAJob,
        on_progress: Callable
    ) -> JobResult:
        """
        Full production workflow:
        1. Niryo loads blank into CNC
        2. CNC machines the brick
        3. xArm unloads to inspection
        4. Vision inspects
        5. xArm sorts to pass/fail bin
        """
        
        # Step 1: Niryo loads blank
        on_progress({'step': 'loading', 'progress': 0})
        
        load_result = await self.ros.call_pick_place(
            robot='niryo',
            action='pick',
            pose=BLANK_MAGAZINE_POSE
        )
        
        if not load_result['success']:
            return JobResult(success=False, error='Failed to pick blank')
        
        await self.ros.call_pick_place(
            robot='niryo',
            action='place',
            pose=CNC_FIXTURE_POSE
        )
        
        on_progress({'step': 'loading', 'progress': 100})
        
        # Step 2: CNC machines (direct serial, not ROS2)
        on_progress({'step': 'machining', 'progress': 0})
        
        async for progress in self.cnc.stream_gcode(job.gcode):
            on_progress({'step': 'machining', 'progress': progress})
        
        # Step 3: xArm unloads
        on_progress({'step': 'unloading', 'progress': 0})
        
        await self.ros.call_pick_place(
            robot='xarm',
            action='pick',
            pose=CNC_FIXTURE_POSE
        )
        
        await self.ros.call_pick_place(
            robot='xarm',
            action='place',
            pose=INSPECTION_POSE
        )
        
        # Step 4: Vision inspection
        on_progress({'step': 'inspecting', 'progress': 0})
        inspection_result = await self.vision.inspect()
        
        # Step 5: Sort
        on_progress({'step': 'sorting', 'progress': 0})
        
        destination = PASS_BIN_POSE if inspection_result.passed else FAIL_BIN_POSE
        
        await self.ros.call_pick_place(
            robot='xarm',
            action='pick',
            pose=INSPECTION_POSE
        )
        
        await self.ros.call_pick_place(
            robot='xarm',
            action='place',
            pose=destination
        )
        
        on_progress({'step': 'complete', 'progress': 100})
        
        return JobResult(
            success=True,
            inspection=inspection_result,
            aligned_data_path=job.aligned_data_path
        )
```

### Gazebo Simulation Benefits

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GAZEBO SIMULATION USE CASES                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. WORKFLOW TESTING                                                         │
│     • Test complete cell workflows before running on real hardware          │
│     • Validate robot trajectories and collision avoidance                   │
│     • Verify timing and synchronization                                     │
│                                                                              │
│  2. TRAINING DATA GENERATION                                                 │
│     • Generate synthetic sensor data for ML training                        │
│     • Create rare/edge case scenarios                                       │
│     • Augment real-world datasets                                           │
│                                                                              │
│  3. OPERATOR TRAINING                                                        │
│     • Safe environment for learning                                         │
│     • Practice emergency procedures                                         │
│     • Test HMI interfaces                                                   │
│                                                                              │
│  4. DIGITAL TWIN VALIDATION                                                  │
│     • Compare simulation to Unity visualization                             │
│     • Validate physics models                                               │
│     • Test predictive algorithms                                            │
│                                                                              │
│  5. CI/CD INTEGRATION                                                        │
│     • Automated integration tests                                           │
│     • Regression testing for robot code                                     │
│     • Performance benchmarking                                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Expanded ERP Architecture

### ERP Module Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE ERP SYSTEM                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        FINANCIAL MANAGEMENT                          │   │
│  │                                                                      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐│   │
│  │  │General Ledger│ │   Accounts   │ │   Accounts   │ │    Cash     ││   │
│  │  │     (GL)     │ │   Payable    │ │  Receivable  │ │ Management  ││   │
│  │  │              │ │     (AP)     │ │     (AR)     │ │             ││   │
│  │  │• Chart of    │ │• Vendor inv  │ │• Customer inv│ │• Bank accts ││   │
│  │  │  accounts    │ │• Payment     │ │• Payment     │ │• Forecasting││   │
│  │  │• Journal     │ │  processing  │ │  processing  │ │• Reconcile  ││   │
│  │  │  entries     │ │• 3-way match │ │• Aging       │ │             ││   │
│  │  │• Trial bal   │ │• Aging       │ │• Collections │ │             ││   │
│  │  │• Fin stmts   │ │• 1099s       │ │• Credit mgmt │ │             ││   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘│   │
│  │                                                                      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │   │
│  │  │Fixed Assets  │ │  Budgeting   │ │    Cost      │                 │   │
│  │  │              │ │              │ │  Accounting  │                 │   │
│  │  │• Asset reg   │ │• Budget def  │ │• Cost centers│                 │   │
│  │  │• Depreciation│ │• Forecasting │ │• Activity    │                 │   │
│  │  │• Disposal    │ │• Variance    │ │  based cost  │                 │   │
│  │  │• Maintenance │ │  analysis    │ │• Overhead    │                 │   │
│  │  │  schedule    │ │              │ │  allocation  │                 │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      SALES & DISTRIBUTION                            │   │
│  │                                                                      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐│   │
│  │  │   Customer   │ │  Quotations  │ │    Sales     │ │   Order     ││   │
│  │  │  Management  │ │  & Pricing   │ │    Orders    │ │  Promising  ││   │
│  │  │              │ │              │ │              │ │             ││   │
│  │  │• Customers   │ │• Price lists │ │• Order entry │ │• ATP        ││   │
│  │  │• Contacts    │ │• Discounts   │ │• Line items  │ │• CTP        ││   │
│  │  │• Credit limit│ │• Quotes      │ │• Allocations │ │• Lead times ││   │
│  │  │• Ship-to addr│ │• Validity    │ │• Holds       │ │• Scheduling ││   │
│  │  │• Payment term│ │• Approval    │ │• Priority    │ │             ││   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘│   │
│  │                                                                      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │   │
│  │  │   Shipping   │ │   Returns    │ │    Sales     │                 │   │
│  │  │  & Delivery  │ │    & RMA     │ │  Analytics   │                 │   │
│  │  │              │ │              │ │              │                 │   │
│  │  │• Pick/pack   │ │• Return auth │ │• Pipeline    │                 │   │
│  │  │• Ship confirm│ │• Credit memo │ │• Conversion  │                 │   │
│  │  │• Carrier intg│ │• Replacement │ │• Revenue     │                 │   │
│  │  │• Tracking    │ │• Restocking  │ │• Margin      │                 │   │
│  │  │• Proof of del│ │• Warranty    │ │• Forecast    │                 │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         PROCUREMENT                                  │   │
│  │                                                                      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐│   │
│  │  │   Vendor     │ │  Purchase    │ │   Purchase   │ │  Receiving  ││   │
│  │  │ Management   │ │ Requisitions │ │    Orders    │ │             ││   │
│  │  │              │ │              │ │              │ │             ││   │
│  │  │• Vendors     │ │• Request     │ │• PO creation │ │• Receipt    ││   │
│  │  │• Contacts    │ │• Approval    │ │• Approval    │ │• Inspection ││   │
│  │  │• Lead times  │ │  workflow    │ │  workflow    │ │• Put-away   ││   │
│  │  │• Performance │ │• Budget check│ │• Terms       │ │• Variance   ││   │
│  │  │• Scorecards  │ │• Conversion  │ │• Expediting  │ │             ││   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘│   │
│  │                                                                      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │   │
│  │  │   Invoice    │ │   Sourcing   │ │   Vendor     │                 │   │
│  │  │   Matching   │ │              │ │   Portal     │                 │   │
│  │  │              │ │              │ │              │                 │   │
│  │  │• 3-way match │ │• RFQ         │ │• Self-service│                 │   │
│  │  │• 2-way match │ │• Bid compare │ │• PO access   │                 │   │
│  │  │• Tolerance   │ │• Award       │ │• ASN submit  │                 │   │
│  │  │• Exception   │ │• Contracts   │ │• Invoice sub │                 │   │
│  │  │• Auto-approve│ │• Blanket PO  │ │• Payment stat│                 │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     INVENTORY MANAGEMENT                             │   │
│  │                                                                      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐│   │
│  │  │    Item      │ │  Warehouse   │ │  Lot/Serial  │ │   Cycle     ││   │
│  │  │   Master     │ │  Management  │ │   Tracking   │ │  Counting   ││   │
│  │  │              │ │              │ │              │ │             ││   │
│  │  │• SKU         │ │• Warehouses  │ │• Lot numbers │ │• Count sched││   │
│  │  │• Description │ │• Zones       │ │• Serial nums │ │• ABC class  ││   │
│  │  │• UOM         │ │• Bins        │ │• Expiration  │ │• Variance   ││   │
│  │  │• Category    │ │• Put-away    │ │• FEFO/FIFO   │ │• Adjustment ││   │
│  │  │• Attributes  │ │• Pick rules  │ │• Traceability│ │• Approval   ││   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘│   │
│  │                                                                      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │   │
│  │  │  Inventory   │ │   Reorder    │ │    Multi-    │                 │   │
│  │  │  Valuation   │ │   Planning   │ │   Location   │                 │   │
│  │  │              │ │              │ │              │                 │   │
│  │  │• FIFO        │ │• Min/Max     │ │• Transfers   │                 │   │
│  │  │• LIFO        │ │• Reorder pt  │ │• In-transit  │                 │   │
│  │  │• Avg cost    │ │• Safety stock│ │• Allocation  │                 │   │
│  │  │• Std cost    │ │• EOQ         │ │• Consignment │                 │   │
│  │  │• Variance    │ │• Demand fcst │ │              │                 │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PRODUCTION PLANNING                               │   │
│  │                                                                      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐│   │
│  │  │     BOM      │ │     MRP      │ │     MPS      │ │  Capacity   ││   │
│  │  │ Management   │ │  (Material)  │ │   (Master)   │ │  Planning   ││   │
│  │  │              │ │              │ │              │ │    (CRP)    ││   │
│  │  │• Multi-level │ │• Gross req   │ │• Demand mgmt │ │• Work center││   │
│  │  │• Revisions   │ │• Net req     │ │• Production  │ │  capacity   ││   │
│  │  │• Effectivity │ │• Planned ord │ │  plan        │ │• Load       ││   │
│  │  │• Substitutes │ │• Pegging     │ │• Rough-cut   │ │  leveling   ││   │
│  │  │• Phantoms    │ │• Exceptions  │ │• Time fences │ │• Bottleneck ││   │
│  │  │• Co-products │ │• Action msg  │ │              │ │• Finite/Inf ││   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘│   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### ERP Services Architecture

```python
# services/erp/ - Complete service structure

services/erp/
├── financial/
│   ├── __init__.py
│   ├── general_ledger_service.py      # Chart of accounts, journal entries
│   ├── accounts_payable_service.py    # Vendor invoices, payments
│   ├── accounts_receivable_service.py # Customer invoices, collections
│   ├── cash_management_service.py     # Bank accounts, reconciliation
│   ├── fixed_assets_service.py        # Asset register, depreciation
│   ├── budgeting_service.py           # Budget definition, variance
│   └── cost_accounting_service.py     # Job costing, overhead allocation
│
├── sales/
│   ├── __init__.py
│   ├── customer_service.py            # Customer master, credit management
│   ├── pricing_service.py             # Price lists, discounts, promotions
│   ├── quotation_service.py           # Quotes, validity, approval
│   ├── sales_order_service.py         # Order entry, allocation
│   ├── order_promising_service.py     # ATP, CTP, lead times
│   ├── shipping_service.py            # Pick, pack, ship, track
│   ├── returns_service.py             # RMA, credits, restocking
│   └── sales_analytics_service.py     # Pipeline, revenue, forecasts
│
├── procurement/
│   ├── __init__.py
│   ├── vendor_service.py              # Vendor master, performance
│   ├── requisition_service.py         # Purchase requisitions, approval
│   ├── purchase_order_service.py      # PO creation, approval, management
│   ├── receiving_service.py           # Receipt, inspection, put-away
│   ├── invoice_matching_service.py    # 3-way match, tolerance, exceptions
│   ├── sourcing_service.py            # RFQ, bid comparison, contracts
│   └── vendor_portal_service.py       # Self-service, ASN, invoices
│
├── inventory/
│   ├── __init__.py
│   ├── item_master_service.py         # Item definitions, attributes
│   ├── warehouse_service.py           # Warehouses, zones, bins
│   ├── inventory_transaction_service.py # Receipt, issue, transfer, adjust
│   ├── lot_serial_service.py          # Lot/serial tracking, traceability
│   ├── cycle_count_service.py         # Count scheduling, variance
│   ├── valuation_service.py           # FIFO, LIFO, average, standard
│   └── reorder_planning_service.py    # Min/max, reorder point, EOQ
│
└── planning/
    ├── __init__.py
    ├── bom_service.py                 # Bill of materials, explosions
    ├── mrp_service.py                 # Material requirements planning
    ├── mps_service.py                 # Master production scheduling
    └── capacity_planning_service.py   # CRP, load leveling, bottlenecks
```

### ERP API Routes

```python
# api/routes/erp/ - Complete route structure

# FINANCIAL
/api/erp/gl/accounts                    # GET, POST - Chart of accounts
/api/erp/gl/accounts/{id}               # GET, PUT, DELETE
/api/erp/gl/journal-entries             # GET, POST - Journal entries
/api/erp/gl/journal-entries/{id}        # GET, PUT (reverse)
/api/erp/gl/trial-balance               # GET - Trial balance report
/api/erp/gl/balance-sheet               # GET - Balance sheet
/api/erp/gl/income-statement            # GET - P&L statement
/api/erp/gl/close-period                # POST - Period close

/api/erp/ap/invoices                    # GET, POST - AP invoices
/api/erp/ap/invoices/{id}               # GET, PUT, DELETE
/api/erp/ap/invoices/{id}/match         # POST - Match to PO/receipt
/api/erp/ap/payments                    # GET, POST - Payments
/api/erp/ap/payments/schedule           # POST - Schedule payments
/api/erp/ap/aging                       # GET - AP aging report

/api/erp/ar/invoices                    # GET, POST - AR invoices
/api/erp/ar/invoices/{id}               # GET, PUT
/api/erp/ar/payments                    # GET, POST - Customer payments
/api/erp/ar/aging                       # GET - AR aging report
/api/erp/ar/collections                 # GET, POST - Collection actions

# SALES
/api/erp/customers                      # GET, POST - Customer master
/api/erp/customers/{id}                 # GET, PUT, DELETE
/api/erp/customers/{id}/credit          # GET, PUT - Credit management
/api/erp/customers/{id}/history         # GET - Order history

/api/erp/price-lists                    # GET, POST - Price lists
/api/erp/price-lists/{id}               # GET, PUT, DELETE
/api/erp/pricing/calculate              # POST - Calculate price for item/qty

/api/erp/quotations                     # GET, POST - Quotes
/api/erp/quotations/{id}                # GET, PUT, DELETE
/api/erp/quotations/{id}/convert        # POST - Convert to order

/api/erp/sales-orders                   # GET, POST - Sales orders
/api/erp/sales-orders/{id}              # GET, PUT, DELETE
/api/erp/sales-orders/{id}/allocate     # POST - Allocate inventory
/api/erp/sales-orders/{id}/release      # POST - Release to warehouse
/api/erp/sales-orders/{id}/atp          # GET - ATP check

/api/erp/shipments                      # GET, POST - Shipments
/api/erp/shipments/{id}                 # GET, PUT
/api/erp/shipments/{id}/pick            # POST - Create pick list
/api/erp/shipments/{id}/ship            # POST - Confirm shipment
/api/erp/shipments/{id}/track           # GET - Tracking info

/api/erp/returns                        # GET, POST - RMAs
/api/erp/returns/{id}                   # GET, PUT
/api/erp/returns/{id}/receive           # POST - Receive return
/api/erp/returns/{id}/credit            # POST - Issue credit

# PROCUREMENT
/api/erp/vendors                        # GET, POST - Vendor master
/api/erp/vendors/{id}                   # GET, PUT, DELETE
/api/erp/vendors/{id}/performance       # GET - Performance scorecard
/api/erp/vendors/{id}/preferred         # GET - Preferred for items

/api/erp/requisitions                   # GET, POST - Purchase requisitions
/api/erp/requisitions/{id}              # GET, PUT, DELETE
/api/erp/requisitions/{id}/approve      # POST - Approve
/api/erp/requisitions/{id}/convert      # POST - Convert to PO

/api/erp/purchase-orders                # GET, POST - Purchase orders
/api/erp/purchase-orders/{id}           # GET, PUT, DELETE
/api/erp/purchase-orders/{id}/approve   # POST - Approve
/api/erp/purchase-orders/{id}/send      # POST - Send to vendor
/api/erp/purchase-orders/{id}/receive   # POST - Receive goods
/api/erp/purchase-orders/{id}/close     # POST - Close PO

/api/erp/rfqs                           # GET, POST - RFQs
/api/erp/rfqs/{id}                      # GET, PUT
/api/erp/rfqs/{id}/send                 # POST - Send to vendors
/api/erp/rfqs/{id}/bids                 # GET, POST - Vendor bids
/api/erp/rfqs/{id}/award                # POST - Award to vendor

# INVENTORY
/api/erp/items                          # GET, POST - Item master
/api/erp/items/{id}                     # GET, PUT, DELETE
/api/erp/items/{id}/where-used          # GET - Where used in BOMs
/api/erp/items/{id}/inventory           # GET - Inventory levels
/api/erp/items/{id}/transactions        # GET - Transaction history

/api/erp/warehouses                     # GET, POST - Warehouses
/api/erp/warehouses/{id}                # GET, PUT, DELETE
/api/erp/warehouses/{id}/bins           # GET, POST - Bin locations
/api/erp/warehouses/{id}/inventory      # GET - Inventory by warehouse

/api/erp/inventory                      # GET - All inventory
/api/erp/inventory/on-hand              # GET - On-hand quantities
/api/erp/inventory/available            # GET - Available (on-hand - allocated)
/api/erp/inventory/valuation            # GET - Inventory valuation report

/api/erp/inventory/transactions         # GET, POST - Transactions
/api/erp/inventory/transactions/receive # POST - Receipt
/api/erp/inventory/transactions/issue   # POST - Issue
/api/erp/inventory/transactions/transfer# POST - Transfer
/api/erp/inventory/transactions/adjust  # POST - Adjustment

/api/erp/lots                           # GET, POST - Lot numbers
/api/erp/lots/{id}                      # GET, PUT
/api/erp/lots/{id}/trace                # GET - Forward/backward trace

/api/erp/cycle-counts                   # GET, POST - Cycle counts
/api/erp/cycle-counts/{id}              # GET, PUT
/api/erp/cycle-counts/{id}/complete     # POST - Complete count

# PLANNING
/api/erp/boms                           # GET, POST - Bills of material
/api/erp/boms/{id}                      # GET, PUT, DELETE
/api/erp/boms/{id}/explode              # GET - Explode BOM
/api/erp/boms/{id}/cost-rollup          # GET - Cost rollup

/api/erp/mrp/run                        # POST - Run MRP
/api/erp/mrp/requirements               # GET - Requirements
/api/erp/mrp/planned-orders             # GET - Planned orders
/api/erp/mrp/planned-orders/{id}/firm   # POST - Firm planned order
/api/erp/mrp/action-messages            # GET - Action messages
/api/erp/mrp/pegging/{demand_id}        # GET - Pegging

/api/erp/mps                            # GET, POST - Master schedule
/api/erp/mps/{id}                       # GET, PUT
/api/erp/mps/rough-cut                  # POST - Rough cut capacity
/api/erp/mps/atp-buckets                # GET - ATP by bucket

/api/erp/capacity/work-centers          # GET, POST - Work centers
/api/erp/capacity/work-centers/{id}     # GET, PUT
/api/erp/capacity/load                  # GET - Capacity load
/api/erp/capacity/bottlenecks           # GET - Bottleneck analysis
/api/erp/capacity/level                 # POST - Level load
```

### ERP Database Schema (Key Tables)

```sql
-- FINANCIAL
CREATE TABLE chart_of_accounts (
    account_id UUID PRIMARY KEY,
    account_number VARCHAR(20) UNIQUE NOT NULL,
    account_name VARCHAR(200) NOT NULL,
    account_type VARCHAR(50) NOT NULL, -- asset, liability, equity, revenue, expense
    parent_account_id UUID REFERENCES chart_of_accounts(account_id),
    is_active BOOLEAN DEFAULT true,
    normal_balance VARCHAR(10) NOT NULL, -- debit, credit
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE journal_entries (
    entry_id UUID PRIMARY KEY,
    entry_number VARCHAR(50) UNIQUE NOT NULL,
    entry_date DATE NOT NULL,
    period_id UUID REFERENCES fiscal_periods(period_id),
    description TEXT,
    source_document VARCHAR(100),
    status VARCHAR(20) DEFAULT 'draft', -- draft, posted, reversed
    posted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE journal_entry_lines (
    line_id UUID PRIMARY KEY,
    entry_id UUID REFERENCES journal_entries(entry_id),
    account_id UUID REFERENCES chart_of_accounts(account_id),
    debit DECIMAL(15,2) DEFAULT 0,
    credit DECIMAL(15,2) DEFAULT 0,
    description TEXT
);

CREATE TABLE ap_invoices (
    invoice_id UUID PRIMARY KEY,
    vendor_id UUID REFERENCES vendors(vendor_id),
    invoice_number VARCHAR(100) NOT NULL,
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    po_id UUID REFERENCES purchase_orders(po_id),
    subtotal DECIMAL(15,2) NOT NULL,
    tax_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL,
    amount_paid DECIMAL(15,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, paid, cancelled
    match_status VARCHAR(20), -- unmatched, partial, matched
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ar_invoices (
    invoice_id UUID PRIMARY KEY,
    customer_id UUID REFERENCES customers(customer_id),
    order_id UUID REFERENCES sales_orders(order_id),
    invoice_number VARCHAR(100) UNIQUE NOT NULL,
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    subtotal DECIMAL(15,2) NOT NULL,
    tax_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL,
    amount_paid DECIMAL(15,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'open', -- open, partial, paid, written_off
    created_at TIMESTAMP DEFAULT NOW()
);

-- SALES
CREATE TABLE customers (
    customer_id UUID PRIMARY KEY,
    customer_number VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    billing_address JSONB,
    shipping_addresses JSONB[], -- multiple ship-to
    credit_limit DECIMAL(15,2) DEFAULT 0,
    payment_terms VARCHAR(50) DEFAULT 'NET30',
    tax_exempt BOOLEAN DEFAULT false,
    sales_rep_id UUID,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE price_lists (
    price_list_id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    effective_from DATE NOT NULL,
    effective_to DATE,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE price_list_items (
    id UUID PRIMARY KEY,
    price_list_id UUID REFERENCES price_lists(price_list_id),
    item_id UUID REFERENCES items(item_id),
    unit_price DECIMAL(15,4) NOT NULL,
    min_quantity DECIMAL(15,4) DEFAULT 1,
    discount_pct DECIMAL(5,2) DEFAULT 0
);

CREATE TABLE sales_orders (
    order_id UUID PRIMARY KEY,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id UUID REFERENCES customers(customer_id),
    order_date DATE NOT NULL,
    requested_date DATE,
    promised_date DATE,
    ship_to_address JSONB,
    status VARCHAR(20) DEFAULT 'open', -- open, allocated, released, shipped, invoiced, closed
    subtotal DECIMAL(15,2),
    tax_amount DECIMAL(15,2),
    total_amount DECIMAL(15,2),
    payment_terms VARCHAR(50),
    priority INTEGER DEFAULT 5,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sales_order_lines (
    line_id UUID PRIMARY KEY,
    order_id UUID REFERENCES sales_orders(order_id),
    line_number INTEGER NOT NULL,
    item_id UUID REFERENCES items(item_id),
    quantity DECIMAL(15,4) NOT NULL,
    quantity_allocated DECIMAL(15,4) DEFAULT 0,
    quantity_shipped DECIMAL(15,4) DEFAULT 0,
    unit_price DECIMAL(15,4) NOT NULL,
    discount_pct DECIMAL(5,2) DEFAULT 0,
    line_total DECIMAL(15,2),
    requested_date DATE,
    promised_date DATE,
    status VARCHAR(20) DEFAULT 'open'
);

-- PROCUREMENT
CREATE TABLE vendors (
    vendor_id UUID PRIMARY KEY,
    vendor_number VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    address JSONB,
    payment_terms VARCHAR(50) DEFAULT 'NET30',
    lead_time_days INTEGER DEFAULT 7,
    rating DECIMAL(3,2), -- 0-5 score
    is_approved BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE purchase_orders (
    po_id UUID PRIMARY KEY,
    po_number VARCHAR(50) UNIQUE NOT NULL,
    vendor_id UUID REFERENCES vendors(vendor_id),
    requisition_id UUID REFERENCES purchase_requisitions(requisition_id),
    order_date DATE NOT NULL,
    expected_date DATE,
    status VARCHAR(20) DEFAULT 'draft', -- draft, pending_approval, approved, sent, partial, received, closed, cancelled
    subtotal DECIMAL(15,2),
    tax_amount DECIMAL(15,2),
    total_amount DECIMAL(15,2),
    approved_by UUID,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE po_receipts (
    receipt_id UUID PRIMARY KEY,
    po_id UUID REFERENCES purchase_orders(po_id),
    receipt_number VARCHAR(50) UNIQUE NOT NULL,
    receipt_date TIMESTAMP NOT NULL,
    received_by UUID,
    status VARCHAR(20) DEFAULT 'pending', -- pending, inspected, put_away
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE po_receipt_lines (
    line_id UUID PRIMARY KEY,
    receipt_id UUID REFERENCES po_receipts(receipt_id),
    po_line_id UUID REFERENCES purchase_order_lines(line_id),
    quantity_received DECIMAL(15,4) NOT NULL,
    quantity_accepted DECIMAL(15,4),
    quantity_rejected DECIMAL(15,4) DEFAULT 0,
    lot_number VARCHAR(100),
    bin_location_id UUID REFERENCES bin_locations(bin_id),
    inspection_status VARCHAR(20) -- pending, passed, failed
);

-- INVENTORY
CREATE TABLE items (
    item_id UUID PRIMARY KEY,
    sku VARCHAR(100) UNIQUE NOT NULL,
    description VARCHAR(500) NOT NULL,
    uom VARCHAR(20) NOT NULL, -- EA, KG, LB, etc.
    category VARCHAR(100),
    item_type VARCHAR(20) DEFAULT 'inventory', -- inventory, service, non-stock
    standard_cost DECIMAL(15,4),
    weight DECIMAL(10,4),
    is_lot_tracked BOOLEAN DEFAULT false,
    is_serialized BOOLEAN DEFAULT false,
    reorder_point DECIMAL(15,4),
    safety_stock DECIMAL(15,4),
    lead_time_days INTEGER,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE warehouses (
    warehouse_id UUID PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    address JSONB,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE bin_locations (
    bin_id UUID PRIMARY KEY,
    warehouse_id UUID REFERENCES warehouses(warehouse_id),
    bin_code VARCHAR(50) NOT NULL,
    zone VARCHAR(50),
    aisle VARCHAR(20),
    rack VARCHAR(20),
    level VARCHAR(20),
    bin_type VARCHAR(20) DEFAULT 'storage', -- storage, receiving, shipping, staging
    UNIQUE(warehouse_id, bin_code)
);

CREATE TABLE inventory_balances (
    id UUID PRIMARY KEY,
    item_id UUID REFERENCES items(item_id),
    warehouse_id UUID REFERENCES warehouses(warehouse_id),
    bin_id UUID REFERENCES bin_locations(bin_id),
    lot_id UUID REFERENCES lot_numbers(lot_id),
    quantity_on_hand DECIMAL(15,4) NOT NULL DEFAULT 0,
    quantity_allocated DECIMAL(15,4) NOT NULL DEFAULT 0,
    quantity_available DECIMAL(15,4) GENERATED ALWAYS AS (quantity_on_hand - quantity_allocated) STORED,
    last_count_date DATE,
    UNIQUE(item_id, warehouse_id, bin_id, lot_id)
);

CREATE TABLE inventory_transactions (
    txn_id UUID PRIMARY KEY,
    item_id UUID REFERENCES items(item_id),
    warehouse_id UUID REFERENCES warehouses(warehouse_id),
    bin_id UUID REFERENCES bin_locations(bin_id),
    lot_id UUID REFERENCES lot_numbers(lot_id),
    txn_type VARCHAR(20) NOT NULL, -- receipt, issue, transfer, adjustment, count
    quantity DECIMAL(15,4) NOT NULL,
    unit_cost DECIMAL(15,4),
    reference_type VARCHAR(50), -- PO, SO, WO, etc.
    reference_id UUID,
    txn_date TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by UUID
);

CREATE TABLE lot_numbers (
    lot_id UUID PRIMARY KEY,
    item_id UUID REFERENCES items(item_id),
    lot_number VARCHAR(100) NOT NULL,
    expiration_date DATE,
    manufacture_date DATE,
    supplier_lot VARCHAR(100),
    status VARCHAR(20) DEFAULT 'available', -- available, hold, quarantine, expired
    UNIQUE(item_id, lot_number)
);

-- PLANNING
CREATE TABLE boms (
    bom_id UUID PRIMARY KEY,
    item_id UUID REFERENCES items(item_id),
    revision VARCHAR(20) NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    status VARCHAR(20) DEFAULT 'active', -- draft, active, obsolete
    notes TEXT,
    UNIQUE(item_id, revision)
);

CREATE TABLE bom_lines (
    line_id UUID PRIMARY KEY,
    bom_id UUID REFERENCES boms(bom_id),
    component_id UUID REFERENCES items(item_id),
    quantity_per DECIMAL(15,6) NOT NULL,
    uom VARCHAR(20) NOT NULL,
    scrap_pct DECIMAL(5,2) DEFAULT 0,
    operation_sequence INTEGER,
    is_phantom BOOLEAN DEFAULT false,
    effective_from DATE,
    effective_to DATE
);

CREATE TABLE mrp_demands (
    demand_id UUID PRIMARY KEY,
    item_id UUID REFERENCES items(item_id),
    quantity DECIMAL(15,4) NOT NULL,
    due_date DATE NOT NULL,
    source_type VARCHAR(20) NOT NULL, -- sales_order, work_order, forecast, safety_stock
    source_id UUID,
    status VARCHAR(20) DEFAULT 'open', -- open, planned, firmed, released
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE mrp_supplies (
    supply_id UUID PRIMARY KEY,
    item_id UUID REFERENCES items(item_id),
    quantity DECIMAL(15,4) NOT NULL,
    available_date DATE NOT NULL,
    source_type VARCHAR(20) NOT NULL, -- on_hand, po, planned_po, work_order, planned_wo
    source_id UUID,
    status VARCHAR(20) DEFAULT 'open'
);

CREATE TABLE work_centers (
    wc_id UUID PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    hourly_rate DECIMAL(10,2),
    setup_time_mins INTEGER DEFAULT 0,
    queue_time_mins INTEGER DEFAULT 0,
    efficiency_pct DECIMAL(5,2) DEFAULT 100,
    daily_capacity_hrs DECIMAL(5,2) DEFAULT 8,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE capacity_loads (
    id UUID PRIMARY KEY,
    work_center_id UUID REFERENCES work_centers(wc_id),
    period_date DATE NOT NULL,
    available_hours DECIMAL(8,2) NOT NULL,
    planned_hours DECIMAL(8,2) DEFAULT 0,
    load_pct DECIMAL(5,2) GENERATED ALWAYS AS (
        CASE WHEN available_hours > 0 
        THEN (planned_hours / available_hours) * 100 
        ELSE 0 END
    ) STORED,
    UNIQUE(work_center_id, period_date)
);
```

### ERP MCP Tools

```python
# MCP tools for Claude - ERP operations

@mcp_tool
async def create_sales_order(
    customer_id: str,
    items: List[dict],  # [{item_id, quantity, unit_price}]
    requested_date: str,
    ship_to_address: dict = None
) -> SalesOrder:
    """Create a sales order with automatic ATP check"""

@mcp_tool
async def check_atp(
    item_id: str,
    quantity: float,
    requested_date: str
) -> ATPResult:
    """Check Available to Promise for an item"""

@mcp_tool
async def check_ctp(
    item_id: str,
    quantity: float
) -> CTPResult:
    """Check Capable to Promise (considers production capacity)"""

@mcp_tool
async def create_purchase_order(
    vendor_id: str,
    items: List[dict],  # [{item_id, quantity, unit_price}]
    expected_date: str = None
) -> PurchaseOrder:
    """Create a purchase order"""

@mcp_tool
async def receive_purchase_order(
    po_id: str,
    items: List[dict]  # [{po_line_id, quantity, lot_number, bin_id}]
) -> POReceipt:
    """Receive goods against a purchase order"""

@mcp_tool
async def check_inventory(
    item_id: str,
    warehouse_id: str = None
) -> InventoryStatus:
    """Check inventory levels and availability"""

@mcp_tool
async def run_mrp(
    item_ids: List[str] = None,
    horizon_days: int = 90
) -> MRPResult:
    """Run MRP and return planned orders and action messages"""

@mcp_tool
async def get_mrp_action_messages() -> List[ActionMessage]:
    """Get MRP action messages (expedite, defer, cancel)"""

@mcp_tool
async def firm_planned_order(
    planned_order_id: str
) -> Union[PurchaseOrder, WorkOrder]:
    """Convert planned order to firm PO or Work Order"""

@mcp_tool
async def explode_bom(
    item_id: str,
    quantity: float
) -> List[BOMLine]:
    """Explode BOM to get all components needed"""

@mcp_tool
async def check_capacity(
    work_center_id: str,
    date_from: str,
    date_to: str
) -> CapacityReport:
    """Check work center capacity and load"""

@mcp_tool
async def trace_lot(
    lot_number: str,
    direction: str = "both"  # forward, backward, both
) -> TraceResult:
    """Trace lot through supply chain"""

@mcp_tool
async def get_customer_credit_status(
    customer_id: str
) -> CreditStatus:
    """Check customer credit status and available credit"""

@mcp_tool
async def get_vendor_performance(
    vendor_id: str
) -> VendorScorecard:
    """Get vendor performance scorecard"""

@mcp_tool
async def get_inventory_valuation(
    as_of_date: str = None,
    method: str = "average"  # fifo, lifo, average, standard
) -> ValuationReport:
    """Get inventory valuation report"""

@mcp_tool
async def create_journal_entry(
    lines: List[dict],  # [{account_id, debit, credit, description}]
    description: str,
    entry_date: str = None
) -> JournalEntry:
    """Create a journal entry (auto-balances debits/credits)"""

@mcp_tool
async def get_financial_statements(
    statement_type: str,  # balance_sheet, income_statement, cash_flow
    period_id: str = None,
    as_of_date: str = None
) -> FinancialStatement:
    """Generate financial statements"""
```

### ERP Dashboards

| Dashboard | Key Features |
|-----------|--------------|
| **Financial Overview** | Cash position, AR/AP summary, P&L, Balance Sheet |
| **AP Workbench** | Invoices pending, matching queue, payment schedule |
| **AR Workbench** | Open invoices, aging, collection actions |
| **Sales Dashboard** | Pipeline, bookings, shipments, returns, revenue |
| **Order Management** | Open orders, allocations, backlog, ATP |
| **Procurement Dashboard** | Open POs, receiving queue, vendor performance |
| **Inventory Dashboard** | Stock levels, turns, aging, valuation, ABC |
| **Warehouse Dashboard** | Putaway queue, picking, cycle counts |
| **MRP Dashboard** | Exceptions, action messages, shortages, planned orders |
| **Capacity Dashboard** | Load by work center, bottlenecks, utilization |
| **BOM Workbench** | BOM maintenance, where-used, cost rollup |

---

## Part 3: Updated Implementation Phases (12 Weeks)

### Phase 1: Foundation (Week 1)
**Goal**: Unified repository, core SCADA

| Task | Source | Description |
|------|--------|-------------|
| 1.1 | New | Create unified repo structure |
| 1.2 | flask_cnc_app | Port machine controllers (TinyG, GRBL) |
| 1.3 | flask_cnc_app | Port sensor acquisition (MCC, Arduino) |
| 1.4 | flask_cnc_app | Port data alignment engine |
| 1.5 | flask_cnc_app | Port SCADA API routes |
| 1.6 | New | Create main Flask app |
| 1.7 | All | Merge requirements.txt |

**Deliverable**: Connect machine, collect sensors, align data

---

### Phase 2: ML Fingerprinting (Week 2)
**Goal**: ML pipeline working

| Task | Source | Description |
|------|--------|-------------|
| 2.1 | gcode_fingerprinting | Port model architectures (LSTM, Decoder) |
| 2.2 | gcode_fingerprinting | Port dataset classes |
| 2.3 | gcode_fingerprinting | Port training utilities |
| 2.4 | gcode_fingerprinting | Port vocabulary (668-token) |
| 2.5 | gcode_fingerprinting | Port pretrained weights |
| 2.6 | New | Create alignment → NPZ converter |
| 2.7 | New | Create inference service |
| 2.8 | New | Create ML API routes |

**Deliverable**: Real-time fingerprinting during jobs

---

### Phase 3: LEGO Services (Week 3)
**Goal**: Brick design to G-code

| Task | Source | Description |
|------|--------|-------------|
| 3.1 | lego-mcp-fusion360 | Port brick dimension specs |
| 3.2 | lego-mcp-fusion360 | Port brick service |
| 3.3 | lego-mcp-fusion360 | Port slicer service (Docker) |
| 3.4 | lego-mcp-fusion360 | Port Fusion 360 add-in |
| 3.5 | New | Create LEGO API routes |
| 3.6 | New | Connect slicer → SCADA |

**Deliverable**: Design brick → G-code → Execute

---

### Phase 4: MES Layer (Week 4)
**Goal**: Work orders and scheduling

| Task | Source | Description |
|------|--------|-------------|
| 4.1 | lego-mcp-fusion360 | Port MES models |
| 4.2 | lego-mcp-fusion360 | Port work order service |
| 4.3 | lego-mcp-fusion360 | Port CP-SAT scheduler |
| 4.4 | lego-mcp-fusion360 | Port NSGA-II scheduler |
| 4.5 | lego-mcp-fusion360 | Port RL dispatcher |
| 4.6 | New | Create MES API routes |
| 4.7 | New | Connect MES → SCADA dispatch |

**Deliverable**: Schedule work orders, dispatch to machines

---

### Phase 5A: ERP Financial (Week 5)
**Goal**: Core financial module

| Task | Description |
|------|-------------|
| 5.1 | Chart of accounts, journal entries, GL service |
| 5.2 | Accounts Payable (invoices, matching, payments) |
| 5.3 | Accounts Receivable (invoicing, payments, aging) |
| 5.4 | Cost accounting (job costing, overhead) |
| 5.5 | Financial API routes |
| 5.6 | Financial dashboards |

**Deliverable**: Complete financial management

---

### Phase 5B: ERP Sales & Procurement (Week 6)
**Goal**: Order-to-cash, procure-to-pay

| Task | Description |
|------|-------------|
| 5.7 | Customer master, credit management |
| 5.8 | Pricing, quotations |
| 5.9 | Sales orders, allocation, shipping |
| 5.10 | Returns (RMA, credits) |
| 5.11 | Vendor master, performance |
| 5.12 | Purchase requisitions, approval workflow |
| 5.13 | Purchase orders, receiving |
| 5.14 | Invoice matching (3-way) |
| 5.15 | Sales & Procurement API routes |
| 5.16 | Sales & Procurement dashboards |

**Deliverable**: Full O2C and P2P processes

---

### Phase 5C: ERP Inventory & Planning (Week 7)
**Goal**: Inventory and MRP

| Task | Description |
|------|-------------|
| 5.17 | Item master, warehouses, bins |
| 5.18 | Inventory transactions |
| 5.19 | Lot/serial tracking, traceability |
| 5.20 | Cycle counting |
| 5.21 | Inventory valuation (FIFO/LIFO/Avg) |
| 5.22 | BOM management |
| 5.23 | MRP engine |
| 5.24 | MPS (Master Production Schedule) |
| 5.25 | Capacity planning (CRP) |
| 5.26 | Inventory & Planning API routes |
| 5.27 | Inventory & Planning dashboards |

**Deliverable**: Complete inventory and production planning

---

### Phase 6: Quality System (Week 8)
**Goal**: SPC, FMEA, Zero-Defect

| Task | Source | Description |
|------|--------|-------------|
| 6.1 | lego-mcp-fusion360 | Port SPC services (EWMA/CUSUM/T²) |
| 6.2 | lego-mcp-fusion360 | Port FMEA service |
| 6.3 | lego-mcp-fusion360 | Port QFD service |
| 6.4 | lego-mcp-fusion360 | Port zero-defect services |
| 6.5 | flask_cnc_app | Port vision inspection |
| 6.6 | New | Create quality API routes |
| 6.7 | New | Connect fingerprint → quality alerts |

**Deliverable**: Complete quality management

---

### Phase 7: ROS2 & Robotics (Week 9)
**Goal**: Multi-robot integration

| Task | Source | Description |
|------|--------|-------------|
| 7.1 | New | Create lego_factory_msgs package |
| 7.2 | flask_cnc_app | Port/create Niryo ROS2 node + MoveIt2 |
| 7.3 | flask_cnc_app | Port/create xArm ROS2 node + MoveIt2 |
| 7.4 | New | Create sensor aggregator node |
| 7.5 | New | Configure rosbridge_suite |
| 7.6 | New | Create Flask ↔ ROS2 bridge service |
| 7.7 | flask_cnc_app | Port factory cell orchestrator |
| 7.8 | flask_cnc_app | Port pick-place workflows |
| 7.9 | New | Create robot API routes |
| 7.10 | New | Create Gazebo simulation world |

**Deliverable**: Multi-robot coordination with MoveIt2

---

### Phase 8: Digital Twin (Week 10)
**Goal**: Unity visualization

| Task | Source | Description |
|------|--------|-------------|
| 8.1 | flask_cnc_app | Port Unity project |
| 8.2 | flask_cnc_app | Port Unity state service |
| 8.3 | flask_cnc_app | Port historical playback |
| 8.4 | New | Add LEGO brick models |
| 8.5 | New | Add fingerprint/anomaly overlay |
| 8.6 | New | Create Unity API routes |
| 8.7 | New | Connect Unity ↔ ROS2 (optional) |

**Deliverable**: Real-time 3D visualization with ML overlay

---

### Phase 9: Dashboards & MCP (Week 11)
**Goal**: Unified UI and Claude integration

| Task | Source | Description |
|------|--------|-------------|
| 9.1 | flask_cnc_app | Port SCADA dashboards (41) |
| 9.2 | lego-mcp-fusion360 | Port MES/ERP dashboards (16+) |
| 9.3 | gcode_fingerprinting | Port fingerprint dashboard |
| 9.4 | New | Create unified portal navigation |
| 9.5 | lego-mcp-fusion360 | Port MCP server |
| 9.6 | flask_cnc_app | Add SCADA MCP tools |
| 9.7 | New | Add ERP MCP tools (expanded) |
| 9.8 | New | Add ROS2 MCP tools |
| 9.9 | New | Add ML MCP tools |

**Deliverable**: 65+ dashboards, 40+ MCP tools

---

### Phase 10: Testing & Documentation (Week 12)
**Goal**: Production ready

| Task | Description |
|------|-------------|
| 10.1 | Integration tests (end-to-end workflows) |
| 10.2 | Performance tests (latency, throughput) |
| 10.3 | ROS2 simulation tests (Gazebo) |
| 10.4 | Port all notebooks (19 from fingerprinting) |
| 10.5 | Write unified documentation |
| 10.6 | Docker compose (all services) |
| 10.7 | CI/CD pipeline (GitHub Actions) |
| 10.8 | Deployment guide |

**Deliverable**: Production-ready unified system

---

## Total Deliverables Summary

| Category | Count |
|----------|-------|
| **Services** | 150+ |
| **API Routes** | 100+ |
| **Dashboard Pages** | 65+ |
| **MCP Tools** | 40+ |
| **ML Models** | 2 (encoder + decoder) |
| **ROS2 Packages** | 6 |
| **Database Tables** | 50+ |
| **Training Notebooks** | 19 |

---

## Success Criteria

| Metric | Target |
|--------|--------|
| **Machine control** | Zero, home, jog, run on all equipment |
| **Robot coordination** | MoveIt2 collision-free multi-robot |
| **Data alignment** | >95% coverage (sensors → G-code) |
| **Fingerprint accuracy** | 90%+ token prediction |
| **Anomaly detection** | <100ms real-time inference |
| **MRP run time** | <30s for full horizon |
| **End-to-end latency** | Design → Execute < 5 minutes |
| **Dashboard load** | <2s page load |
| **MCP response** | <500ms tool execution |
| **Simulation** | Gazebo validates before hardware |

---

## Timeline Summary

```
Week 1:  Foundation (SCADA core)
Week 2:  ML Fingerprinting
Week 3:  LEGO Services
Week 4:  MES Layer
Week 5:  ERP Financial
Week 6:  ERP Sales & Procurement
Week 7:  ERP Inventory & Planning
Week 8:  Quality System
Week 9:  ROS2 & Robotics
Week 10: Digital Twin
Week 11: Dashboards & MCP
Week 12: Testing & Documentation
```

**Total: 12 weeks to production-ready system**

---

## Ready to Begin

✅ ROS2 integration architecture defined  
✅ Complete ERP system designed  
✅ All three repositories inventoried  
✅ 12-week implementation plan  
✅ No loss of function from any source  

**When you're ready, we start Phase 1!** 🏭
