# ROS2 User Guide - LEGO Manufacturing Control Platform

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Packages](#packages)
4. [Messages, Services & Actions](#messages-services--actions)
5. [Node Graph](#node-graph)
6. [Topic Architecture](#topic-architecture)
7. [Data Flow](#data-flow)
8. [Runtime Dependencies](#runtime-dependencies)
9. [Launch System](#launch-system)
10. [Operations Guide](#operations-guide)
11. [CLI Reference](#cli-reference)
12. [API Integration](#api-integration)
13. [Troubleshooting](#troubleshooting)

---

## Overview

The LEGO Factory v3 ROS2 system is a comprehensive Industry 4.0 manufacturing control platform built on ROS2 Humble. It implements the ISA-95 automation pyramid with 52 packages, 60+ custom messages, 35+ services, and 11+ actions.

### Key Features
- **ISA-95 Compliance**: 5-level automation hierarchy (Field → Cell → Supervision → MES → ERP)
- **OTP Supervision**: Erlang-style fault tolerance with ONE_FOR_ONE, ONE_FOR_ALL, REST_FOR_ONE strategies
- **Multi-Protocol Support**: GRBL, HTTP, MQTT, OPC UA, MTConnect, Sparkplug B
- **Digital Twin**: Physics-Informed Neural Network (PINN) with Unity visualization
- **Vision QC**: YOLO-based defect detection and quality control
- **Multiple Scheduling Algorithms**: CP-SAT, NSGA2, priority dispatch, QAOA

### System Stats
| Metric | Count |
|--------|-------|
| ROS2 Packages | 52 |
| Custom Messages | 60+ |
| Custom Services | 35+ |
| Custom Actions | 11+ |
| Launch Files | 33 |
| Active Nodes (full system) | ~30 |

---

## Architecture

### ISA-95 Automation Pyramid

```
┌─────────────────────────────────────────────────────────────────┐
│                    LEVEL 3+ (Enterprise)                        │
│         cloud_sync, OPC UA, MTConnect, Sparkplug B              │
├─────────────────────────────────────────────────────────────────┤
│                    LEVEL 2 (Supervision)                        │
│    orchestrator, supervisor, scheduler, fleet_manager           │
│              digital_twin, pinn_twin, analytics                 │
├─────────────────────────────────────────────────────────────────┤
│                    LEVEL 1 (Cell Control)                       │
│     safety_node, cnc_control, yolo_inference, collision         │
├─────────────────────────────────────────────────────────────────┤
│                    LEVEL 0 (Field Devices)                      │
│   grbl_node, formlabs_node, bambu_node, camera_node, robots     │
└─────────────────────────────────────────────────────────────────┘
```

### Workspace Location
```
/Users/stepheneacuello/Documents/lego_factory/ros2_ws/
├── src/                    # Source packages
│   ├── lego_mcp_msgs/      # Core messages/services/actions
│   ├── cnc_interfaces/     # CNC interface definitions
│   ├── lego_mcp_bringup/   # Launch files and configs
│   ├── lego_mcp_orchestrator/
│   ├── lego_mcp_supervisor/
│   ├── grbl_ros2/
│   ├── formlabs_ros2/
│   ├── bambu_ros2/
│   └── ... (52 packages total)
├── install/                # Built packages
├── build/                  # Build artifacts
└── log/                    # Build logs
```

---

## Packages

### Package Categories

#### Interface Packages (Message Definitions)
| Package | Purpose |
|---------|---------|
| `lego_mcp_msgs` | Core manufacturing messages, services, actions |
| `cnc_interfaces` | CNC machine interface definitions |
| `lego_factory_msgs` | Legacy LEGO factory messages |

#### Core System Packages
| Package | Purpose |
|---------|---------|
| `lego_mcp_bringup` | Launch files and system configuration |
| `lego_mcp_supervisor` | OTP-style supervision tree with lifecycle management |
| `lego_mcp_orchestrator` | Work order dispatch and equipment coordination |
| `lego_mcp_safety` | Safety subsystem (ISA-95 Level 1) |
| `lego_mcp_security` | SROS2 security and audit systems |
| `lego_mcp_simulation` | System simulation components |

#### Equipment Driver Packages
| Package | Equipment | Protocol |
|---------|-----------|----------|
| `grbl_ros2` | CNC/Laser machines | Serial (115200 baud) |
| `formlabs_ros2` | SLA 3D printer | HTTP API |
| `bambu_ros2` | FDM 3D printer | MQTT |
| `tinyg_ros` | TinyG motion controller | Serial |
| `linuxcnc_ros` | LinuxCNC integration | HAL |
| `mach_ros` | Mach3 CNC integration | Serial |

#### CNC Control System Packages
| Package | Purpose |
|---------|---------|
| `cnc_control` | Main CNC machine control |
| `cnc_motion` | Motion planning and collision detection |
| `cnc_safety` | Machine-level safety monitoring |
| `cnc_diagnostics` | Diagnostic monitoring |
| `cnc_scheduler` | Job scheduling engine |
| `cnc_predictive` | Predictive maintenance (LSTM models) |
| `cnc_fleet` | Machine fleet management |
| `cnc_vision` | Computer vision and YOLO inference |
| `cnc_visualization` | Unity 3D bridge |
| `cnc_cloud` | Cloud synchronization |
| `cnc_oee` | OEE metrics calculation |
| `cnc_voice` | Voice command control |
| `mqtt_client` | MQTT bridge |

#### Advanced Feature Packages
| Package | Purpose |
|---------|---------|
| `lego_mcp_agv` | Autonomous vehicle fleet |
| `lego_mcp_discovery` | Equipment discovery and topology |
| `lego_mcp_pinn_twin` | Physics-Informed Neural Network digital twin |
| `lego_mcp_calibration` | Robot calibration systems |
| `lego_mcp_vision` | Vision quality control |
| `lego_mcp_causal_engine` | Causal inference engine |
| `lego_mcp_chaos` | Chaos engineering/fault injection |
| `lego_mcp_compliance` | Compliance monitoring |
| `lego_mcp_formal_verification` | Formal verification tools |
| `lego_mcp_hsm` | Hierarchical State Machine |
| `lego_mcp_microros` | Micro-ROS agent launcher |
| `lego_mcp_moveit_config` | MoveIt2 robot arm configuration |
| `lego_mcp_observability` | Observability and tracing |
| `lego_mcp_opcua` | OPC UA gateway |
| `lego_mcp_pq_crypto` | Post-quantum cryptography |
| `lego_mcp_realtime` | Real-time constraints |
| `lego_mcp_bft_consensus` | Byzantine Fault Tolerance |
| `lego_mcp_safety_certified` | Safety certification compliance |

---

## Messages, Services & Actions

### Core Messages (`lego_mcp_msgs/msg/`)

#### Equipment & Status
| Message | Purpose | Key Fields |
|---------|---------|------------|
| `EquipmentStatus.msg` | Complete equipment state | position, temperature, OEE metrics, safety (57 fields) |
| `PrintJob.msg` | 3D print job specification | file, material, settings |
| `AssemblyStep.msg` | Robot assembly operation | pick/place positions, gripper |
| `Heartbeat.msg` | System heartbeat | node_id, timestamp, status |

#### Quality & Events
| Message | Purpose | Key Fields |
|---------|---------|------------|
| `QualityEvent.msg` | Quality control events | defect_type, severity, location |
| `FailureEvent.msg` | Equipment failure notifications | equipment_id, failure_code, timestamp |
| `DefectDetection.msg` | Vision defect detection results | bounding_box, confidence, class |
| `InspectionResult.msg` | Quality inspection results | pass/fail, measurements |

#### Digital Twin & AGV
| Message | Purpose | Key Fields |
|---------|---------|------------|
| `TwinState.msg` | Digital twin synchronization | equipment states, positions |
| `TwinSync.msg` | Twin state synchronization | delta updates |
| `AGVStatus.msg` | Autonomous vehicle status | position, battery, mission |
| `AGVMission.msg` | AGV mission specification | waypoints, payload |

#### Supervisor
| Message | Purpose | Key Fields |
|---------|---------|------------|
| `SupervisorStatus.msg` | Supervision tree status | children, restart_counts |
| `ChildStatus.msg` | Child process status | node_name, state, last_heartbeat |
| `EquipmentDiscovery.msg` | Equipment discovery announcements | equipment_id, capabilities |

### CNC Messages (`cnc_interfaces/msg/`)

#### Machine State
| Message | Purpose |
|---------|---------|
| `MachineStatus.msg` | Complete machine state (50+ fields) |
| `GrblStatus.msg` | GRBL-specific status |
| `MachinePosition.msg` | Machine coordinate positions |
| `AxisState.msg` | Individual axis state |
| `SpindleState.msg` | Spindle status |
| `ToolStateMsg.msg` | Tool management |
| `ToolWear.msg` | Tool wear tracking |

#### Vision & Quality
| Message | Purpose |
|---------|---------|
| `VisionDetection.msg` | Single YOLO detection |
| `VisionDetectionArray.msg` | Array of detections |
| `VisionStatus.msg` | Vision system status |
| `VisionSafetyAlert.msg` | Vision-based safety alerts |
| `Defect.msg` | Part defects |
| `QualityRecord.msg` | Quality inspection records |

#### Analytics & Events
| Message | Purpose |
|---------|---------|
| `PredictiveMaintenance.msg` | Maintenance predictions |
| `OeeMetrics.msg` | Overall Equipment Effectiveness |
| `JobEvent.msg` | Job lifecycle events |
| `FleetEvent.msg` | Fleet management events |
| `CollisionWarning.msg` | Collision detection warnings |
| `DigitalTwinState.msg` | Digital twin model state |

---

### Services (`lego_mcp_msgs/srv/`)

#### Orchestration Services
| Service | Purpose | Key Parameters |
|---------|---------|----------------|
| `CreateWorkOrder.srv` | Create new work order | part_id, quantity, priority, customer_id |
| `ScheduleJob.srv` | Schedule manufacturing job | work_order_id, strategy (cp_sat, nsga2, priority_dispatch, qaoa) |
| `RescheduleRemaining.srv` | Reschedule remaining operations | work_order_id |
| `DispatchAGV.srv` | Dispatch AGV missions | destination, payload |
| `GetSupervisorStatus.srv` | Query supervisor state | - |
| `GetTwinState.srv` | Get digital twin state | equipment_id |
| `RequestInspection.srv` | Request quality inspection | part_id, inspection_type |
| `RestartNode.srv` | Restart system nodes | node_name |
| `LifecycleTransition.srv` | Trigger lifecycle transitions | node_name, transition |
| `DiscoverEquipment.srv` | Discover available equipment | - |

#### CNC Services (`cnc_interfaces/srv/`)
| Service | Purpose |
|---------|---------|
| `SendGcode.srv` | Send G-code to machine |
| `Jog.srv` | Jog machine axes |
| `Home.srv` | Home machine |
| `EmergencyStop.srv` | Emergency stop |
| `SafetyReset.srv` | Safety system reset |
| `CheckSafetyZone.srv` | Check safety zone collision |
| `SetFeedOverride.srv` | Set feed rate override |
| `PlanPath.srv` | Plan machine path |
| `VerifyPartPosition.srv` | Verify part position |
| `AllocateMachine.srv` | Allocate machine resource |
| `DispatchJob.srv` | Dispatch job to equipment |
| `ScheduleJobs.srv` | Schedule multiple jobs |
| `GetFleetStatus.srv` | Get fleet status |
| `InspectPart.srv` | Inspect part quality |
| `GetPrediction.srv` | Get predictive maintenance prediction |
| `CheckToolWear.srv` | Check tool wear status |
| `ScanBarcode.srv` | Scan barcode |
| `ProcessVoice.srv` | Process voice command |
| `CloudBroadcast.srv` | Broadcast to cloud |
| `AnalyzeBag.srv` | Analyze ROS bag file |
| `GetGenealogy.srv` | Get part genealogy/traceability |

---

### Actions

#### Core Actions (`lego_mcp_msgs/action/`)

**PrintBrick.action** - Long-running 3D print operation
```
# Goal
string work_order_id
string brick_id
string printer_id
string source_file
float32 layer_height
int32 infill_percent
---
# Result
bool success
string message
float32 print_time_sec
string[] defects_found
---
# Feedback
int32 phase  # 0=queued, 1=slicing, 2=preheating, 3=printing, 4=cooling, 5=post_processing, 6=inspecting
float32 progress_percent
int32 current_layer
int32 total_layers
float32 nozzle_temp
float32 bed_temp
float32 elapsed_sec
float32 remaining_sec
```

| Action | Purpose |
|--------|---------|
| `AssembleLego.action` | Robot assembly operation |
| `ExecuteWorkOrder.action` | Execute complete work order |
| `MachineOperation.action` | Generic machine operation |
| `AGVNavigation.action` | AGV navigation mission |
| `PerformInspection.action` | Quality inspection operation |
| `SupervisorRecovery.action` | Recovery from failures |
| `StopOperation.action` | Stop running operation |

#### CNC Actions (`cnc_interfaces/action/`)

**ExecuteGcode.action** - G-code execution with streaming feedback
```
# Goal
string gcode
string machine_id
---
# Result
bool success
int32 lines_executed
float32 execution_time
---
# Feedback
int32 current_line
float32 progress_percent
geometry_msgs/Point position
float32 spindle_speed
```

| Action | Purpose |
|--------|---------|
| `TrainModel.action` | Train ML models (predictive maintenance) |

---

## Node Graph

### Full System RQT Graph

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         ROS2 NODE GRAPH - LEGO MCP                                              │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────────────┐
                                    │   supervisor_node   │
                                    │  (lifecycle mgmt)   │
                                    └──────────┬──────────┘
                                               │ /supervisor/status
                                               │ /supervisor/heartbeat
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                          ORCHESTRATION LAYER                                                      │
│                                                                                                                   │
│  ┌────────────────────┐         ┌─────────────────────┐         ┌─────────────────────┐                          │
│  │  scheduler_node    │◄───────►│  orchestrator_node  │◄───────►│  fleet_manager_node │                          │
│  │  (job scheduling)  │         │  (work orders)      │         │  (AGV fleet)        │                          │
│  └────────────────────┘         └──────────┬──────────┘         └─────────────────────┘                          │
│           │                                │                              │                                       │
│           │ /schedule/jobs                 │ ~/status                     │ /agv/fleet_status                     │
│           │ /schedule/events               │ /lego_mcp/job_complete       │ /agv/missions                         │
│           ▼                                ▼                              ▼                                       │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           EQUIPMENT LAYER                                                         │
│                                                                                                                   │
│  ┌────────────────────┐    ┌────────────────────┐    ┌────────────────────┐    ┌────────────────────┐            │
│  │    grbl_node       │    │   formlabs_node    │    │    bambu_node      │    │    tinyg_node      │            │
│  │  (CNC/Laser)       │    │  (SLA Printer)     │    │  (FDM Printer)     │    │  (Motion Ctrl)     │            │
│  └─────────┬──────────┘    └─────────┬──────────┘    └─────────┬──────────┘    └─────────┬──────────┘            │
│            │                         │                         │                         │                        │
│            │ /grbl/status            │ /formlabs/status        │ /bambu/status           │ /tinyg/status          │
│            │ /grbl/position          │ /formlabs/job_progress  │ /bambu/job_progress     │ /tinyg/position        │
│            │ /grbl/state             │                         │                         │                        │
│            ▼                         ▼                         ▼                         ▼                        │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                    │                          │                          │
                    └──────────────────────────┼──────────────────────────┘
                                               │
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            SAFETY LAYER                                                           │
│                                                                                                                   │
│  ┌────────────────────┐              ┌────────────────────┐              ┌────────────────────┐                   │
│  │    safety_node     │─────────────►│  collision_detector│◄─────────────│ runtime_monitor    │                   │
│  │  (E-stop, GPIO)    │              │  (motion safety)   │              │ (RT constraints)   │                   │
│  └─────────┬──────────┘              └────────────────────┘              └────────────────────┘                   │
│            │                                                                                                      │
│            │ /safety/estop_status ──────────────────────────────────────────────────────► ALL EQUIPMENT           │
│            │ /safety/heartbeat ─────────────────────────────────────────────────────────► orchestrator            │
│            │ /safety/zone_violations                                                                              │
│            ▼                                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            VISION LAYER                                                           │
│                                                                                                                   │
│  ┌────────────────────┐         ┌────────────────────┐         ┌────────────────────┐                            │
│  │    camera_node     │────────►│ yolo_inference_node│────────►│quality_feedback_node│                            │
│  │  (USB camera)      │         │  (YOLO v8)         │         │  (QC events)       │                            │
│  └────────────────────┘         └────────────────────┘         └─────────┬──────────┘                            │
│            │                             │                               │                                        │
│            │ /camera/image_raw           │ /vision/detections            │ /quality/events ────► orchestrator     │
│            │ /camera/camera_info         │ /vision/status                │ /quality/feedback                      │
│            │ (30 FPS, 1280x720)          │ /vision/safety_alerts ────────┼──────────────────► safety_node         │
│            ▼                             ▼                               ▼                                        │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                          DISCOVERY LAYER                                                          │
│                                                                                                                   │
│  ┌────────────────────┐         ┌────────────────────┐         ┌────────────────────┐                            │
│  │ discovery_server   │◄───────►│ equipment_registry │◄───────►│ topology_manager   │                            │
│  │ (mDNS/announce)    │         │ (equipment DB)     │         │ (network map)      │                            │
│  └─────────┬──────────┘         └────────────────────┘         └─────────┬──────────┘                            │
│            │                                                             │                                        │
│            │ /equipment/discovered                                       │ /equipment/topology ──► orchestrator   │
│            │ /equipment/events                                           │                                        │
│            ▼                                                             ▼                                        │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         DIGITAL TWIN LAYER                                                        │
│                                                                                                                   │
│  ┌────────────────────┐         ┌────────────────────┐         ┌────────────────────┐                            │
│  │   pinn_twin_node   │◄───────►│  twin_sync_node    │────────►│   unity_bridge     │                            │
│  │ (Physics-Informed) │         │ (state sync)       │         │ (3D visualization) │                            │
│  └────────────────────┘         └─────────┬──────────┘         └─────────┬──────────┘                            │
│                                           │                              │                                        │
│       ◄──── ALL EQUIPMENT STATUS ─────────┤                              │ /unity/command ────► equipment         │
│                                           │ /digital_twin/state          │ /unity/scene_state                     │
│                                           ▼                              ▼                                        │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         ANALYTICS LAYER                                                           │
│                                                                                                                   │
│  ┌────────────────────┐         ┌────────────────────┐         ┌────────────────────┐                            │
│  │  predictive_node   │         │  oee_aggregator    │         │ anomaly_detector   │                            │
│  │ (LSTM maintenance) │         │  (OEE metrics)     │         │ (sensor anomalies) │                            │
│  └─────────┬──────────┘         └─────────┬──────────┘         └─────────┬──────────┘                            │
│            │                              │                              │                                        │
│       ◄─── EQUIPMENT STATUS ──────────────┼──────────────────────────────┤                                        │
│            │ /predictive/alerts           │ /oee/metrics                 │ /anomaly/alerts                        │
│            ▼                              ▼                              ▼                                        │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                          EXTERNAL BRIDGES                                                         │
│                                                                                                                   │
│  ┌────────────────────┐    ┌────────────────────┐    ┌────────────────────┐    ┌────────────────────┐            │
│  │   mqtt_bridge      │    │   opcua_gateway    │    │  mtconnect_agent   │    │   cloud_sync       │            │
│  │ (Bambu, external)  │    │  (OPC UA server)   │    │ (MTConnect adapter)│    │ (cloud DB sync)    │            │
│  └─────────┬──────────┘    └─────────┬──────────┘    └─────────┬──────────┘    └─────────┬──────────┘            │
│            │                         │                         │                         │                        │
│            │ MQTT ◄──► bambu_node    │ OPC UA ◄──► SCADA       │ MTConnect ◄──► MES      │ HTTP ◄──► Cloud       │
│            ▼                         ▼                         ▼                         ▼                        │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Node Count Summary

| Layer | Nodes |
|-------|-------|
| Supervision | 1 |
| Orchestration | 3 (orchestrator, scheduler, fleet_manager) |
| Equipment | 4-6 (grbl, formlabs, bambu, tinyg, etc.) |
| Safety | 3 (safety, collision_detector, runtime_monitor) |
| Vision | 3 (camera, yolo, quality_feedback) |
| Discovery | 3 (discovery_server, registry, topology) |
| Digital Twin | 3 (pinn_twin, twin_sync, unity_bridge) |
| Analytics | 3 (predictive, oee, anomaly) |
| Bridges | 4 (mqtt, opcua, mtconnect, cloud) |
| **Total** | **~27-30 nodes** |

---

## Topic Architecture

### Topic Connection Matrix

```
PUBLISHERS                          TOPIC                              SUBSCRIBERS
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
grbl_node                     ───►  /grbl/status                  ───► orchestrator, twin_sync, oee_aggregator
grbl_node                     ───►  /grbl/position                ───► collision_detector, path_planner
formlabs_node                 ───►  /formlabs/status              ───► orchestrator, twin_sync, oee_aggregator
bambu_node                    ───►  /bambu/status                 ───► orchestrator, twin_sync, oee_aggregator
camera_node                   ───►  /camera/image_raw             ───► yolo_inference_node
yolo_inference_node           ───►  /vision/detections            ───► quality_feedback_node, safety_node
yolo_inference_node           ───►  /vision/safety_alerts         ───► safety_node
quality_feedback_node         ───►  /quality/events               ───► orchestrator_node
safety_node                   ───►  /safety/estop_status          ───► ALL EQUIPMENT NODES
safety_node                   ───►  /safety/heartbeat             ───► orchestrator, supervisor
orchestrator_node             ───►  /lego_mcp/job_complete        ───► scheduler, cloud_sync
orchestrator_node             ───►  ~/status                      ───► supervisor, monitoring
supervisor_node               ───►  /supervisor/status            ───► diagnostics, monitoring
discovery_server              ───►  /equipment/discovered         ───► equipment_registry
topology_manager              ───►  /equipment/topology           ───► orchestrator
twin_sync_node                ───►  /digital_twin/state           ───► unity_bridge, pinn_twin
predictive_node               ───►  /predictive/alerts            ───► orchestrator, notification
oee_aggregator                ───►  /oee/metrics                  ───► cloud_sync, dashboard
fleet_manager                 ───►  /agv/fleet_status             ───► orchestrator
fleet_manager                 ───►  /agv/missions                 ───► agv_nodes
```

### Service Connections

```
CLIENT                              SERVICE                            SERVER
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
orchestrator         ────────────►  /grbl/send_gcode              ───► grbl_node
orchestrator         ────────────►  /scheduler/schedule_job       ───► scheduler_node
orchestrator         ────────────►  /fleet/dispatch_agv           ───► fleet_manager
orchestrator         ────────────►  /vision/request_inspection    ───► yolo_inference_node
safety_node          ────────────►  /equipment/emergency_stop     ───► ALL EQUIPMENT
supervisor           ────────────►  /*/lifecycle_transition       ───► ALL LIFECYCLE NODES
```

### Action Connections

```
CLIENT                              ACTION                             SERVER
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
orchestrator         ════════════►  /print_brick                  ═══► formlabs_node, bambu_node
orchestrator         ════════════►  /assemble_lego                ═══► robot_arm_node
orchestrator         ════════════►  /execute_gcode                ═══► grbl_node
orchestrator         ════════════►  /agv_navigation               ═══► fleet_manager
orchestrator         ════════════►  /perform_inspection           ═══► yolo_inference_node
supervisor           ════════════►  /supervisor_recovery          ═══► supervisor_node
```

---

## Data Flow

### Work Order Execution Flow

```
Work Order (Service Call)
    │
    ▼
OrchestratorNode::_create_work_order_callback()
    │
    ▼
Generate Operations (based on part type)
    │
    ▼
Schedule Job Service Call
    │
    ▼
Match Operations to Equipment
    │
    ▼
Dispatch to Equipment via ActionClient
    │
    ▼
Poll Equipment Status (via EquipmentStatus topic)
    │
    ▼
Handle Failures (FailureEvent topic)
    │
    ▼
Quality Check (QualityEvent topic)
    │
    ▼
Job Complete (published on /lego_mcp/job_complete)
```

### Equipment Control Flow

```
GRBLNode / FormlabsNode / BambuNode (Equipment Driver)
    │ (Publishers)
    ▼
Equipment Status Topic (position, temp, state, OEE)
    │ (consumed by)
    ▼
OrchestratorNode (state tracking)
SupervisorNode (health monitoring)
DiagnosticsNode (system monitoring)
    ▲ (Subscribers)
    │
E-stop Topic, Command Topics
    ▲ (from)
    │
Safety System, Motion Planning, Control Nodes
```

### Vision Pipeline

```
CameraNode (publisher)
    │
    ▼
/camera/image_raw (Image messages @ 30 FPS)
    │
    ▼
YOLOInferenceNode (subscriber + inference)
    │
    ▼
/vision/detections (VisionDetectionArray)
    │
    ▼
QualityFeedbackNode / SafetyMonitorNode
    │
    ▼
/quality/events → OrchestratorNode
/vision/safety_alerts → SafetyNode
```

### Discovery & Monitoring Flow

```
Equipment Nodes (startup)
    │ (publish announcement)
    ▼
EquipmentDiscovery Topic
    │
    ▼
DiscoveryServerNode (aggregates)
    │
    ▼
/equipment/topology (TopologyUpdate)
    │
    ▼
OrchestrationNode (available equipment)
TopologyManagerNode (network map)
```

### Digital Twin Sync Flow

```
Equipment Status Topic (EquipmentStatus)
    │ (published by)
    ▼
TwinSyncNode
    │
    ▼
/digital_twin/state (TwinState)
    │
    ▼
VisualizationNode → UnityBridge
/unity/command (commands back)
```

---

## Runtime Dependencies

### Infrastructure Services (Docker)

| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL + TimescaleDB | 5432 | Job history, OEE metrics, part genealogy |
| Redis | 6379 | Cache, pub/sub, session state |
| Mosquitto MQTT | 1883 | Bambu printer comms, event streaming |
| Slicer Service | 8766 | PrusaSlicer for STL→G-code |
| Flask App | 5000 | Web UI, REST API |
| Rosbridge | 9090 | WebSocket bridge (Flask ↔ ROS2) |

### Hardware Connections

**Serial Ports:**
```
/dev/ttyUSB0  →  TinyG CNC Controller (115200 baud)
/dev/ttyUSB1  →  GRBL Laser Engraver (115200 baud)
/dev/ttyUSB2  →  CoastRunner 3D Printer (115200 baud)
```

**Network Equipment:**
```
192.168.1.10:6666  →  Niryo Ned2 Robot Arm
192.168.1.11       →  xArm 6 Lite Robot Arm
192.168.1.100      →  Bambu Lab Printer (MQTT)
localhost:44388    →  Formlabs PreForm Server API
```

**GPIO (Raspberry Pi):**
```
GPIO 17  →  E-stop input
GPIO 27  →  Safety watchdog output
```

**Camera:**
```
/dev/video0  →  USB camera for vision system
```

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://lego:lego_factory_2024@localhost:5432/lego_factory

# Redis
REDIS_URL=redis://localhost:6379/0

# MQTT
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883

# Serial Ports
TINYG_PORT=/dev/ttyUSB0
GRBL_PORT=/dev/ttyUSB1

# Robots
NED2_IP=192.168.1.10
XARM_IP=192.168.1.11

# Vision (optional)
ROBOFLOW_API_KEY=sk-...

# ROS2
ROS2_DOMAIN_ID=0
ROSBRIDGE_URL=ws://localhost:9090
```

---

## Launch System

### Main Launch File

**Location:** `ros2_ws/src/lego_mcp_bringup/launch/full_system.launch.py`

### Launch Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `use_sim` | false | Simulation mode (no hardware) |
| `enable_safety` | true | Safety subsystem |
| `enable_equipment` | true | Equipment nodes |
| `enable_robotics` | false | Robot arms (MoveIt2) |
| `enable_agv` | false | AGV fleet |
| `enable_vision` | false | Computer vision |
| `enable_supervision` | true | OTP supervision tree |
| `enable_security` | false | SROS2 security |
| `enable_scada` | false | SCADA bridges (OPC UA, MTConnect) |
| `heartbeat_timeout_ms` | 500 | Supervision heartbeat timeout |
| `max_restarts` | 5 | Max restart attempts |

### Phased Startup Sequence

```
T=0s   → Supervision tree starts
T=2s   → Safety systems (E-stop, watchdog)
T=5s   → Equipment nodes (CNC, printers)
T=8s   → Vision systems (cameras, defect detection)
T=12s  → Orchestration (job scheduling, MoveIt2)
T=15s  → Robotics (Ned2, xArm grippers, assembly)
T=18s  → AGV fleet (if enabled)
T=22s  → SCADA bridges (OPC UA, MTConnect, Sparkplug)
T=25s  → System ready
```

### Available Launch Files

| Launch File | Purpose |
|-------------|---------|
| `full_system.launch.py` | Complete system with all subsystems |
| `v8_full_system.launch.py` | Version 8 enhanced system |
| `robotics.launch.py` | Robot arms + MoveIt2 |
| `simulation.launch.py` | Full simulation without hardware |
| `factory_cell.launch.py` | Single cell configuration |
| `factory_lifecycle.launch.py` | Lifecycle node coordination |
| `lifecycle_manager.launch.py` | Lifecycle state transitions |
| `industry40.launch.py` | Industry 4.0 mode (SCADA bridges) |
| `scada_bridges.launch.py` | OPC UA, MTConnect, Sparkplug B |
| `deterministic_startup.launch.py` | Phased startup with timing |

### Launch Commands

```bash
# Minimum (simulation)
ros2 launch lego_mcp_bringup full_system.launch.py use_sim:=true

# With equipment (real hardware)
ros2 launch lego_mcp_bringup full_system.launch.py \
  enable_equipment:=true \
  enable_safety:=true

# Full production
ros2 launch lego_mcp_bringup full_system.launch.py \
  enable_safety:=true \
  enable_equipment:=true \
  enable_robotics:=true \
  enable_vision:=true \
  enable_supervision:=true \
  enable_scada:=true
```

---

## Operations Guide

### Pre-Launch Checklist

1. **Start infrastructure services:**
   ```bash
   docker-compose up -d postgres redis mosquitto slicer app
   ```

2. **Source ROS2 workspace:**
   ```bash
   cd ros2_ws
   source install/setup.bash
   ```

3. **Verify hardware connections** (if not simulation):
   - Serial ports available (`ls /dev/ttyUSB*`)
   - Network equipment reachable (`ping 192.168.1.10`)
   - Camera connected (`ls /dev/video*`)

### Starting the System

```bash
# Simulation mode
ros2 launch lego_mcp_bringup full_system.launch.py use_sim:=true

# Production mode
ros2 launch lego_mcp_bringup full_system.launch.py
```

### Verifying System Health

```bash
# List active nodes
ros2 node list

# Check topics
ros2 topic list

# Echo equipment status
ros2 topic echo /grbl/status --once

# Check service availability
ros2 service list | grep manufacturing

# Via REST API
curl -s http://localhost:5000/health | jq
curl -s http://localhost:5000/api/ros2/bridge/status | jq
```

### Creating a Work Order

**Via ROS2 Service:**
```bash
ros2 service call /manufacturing/create_work_order lego_mcp_msgs/srv/CreateWorkOrder \
  "{part_id: 'brick_2x4_red', quantity: 100, priority: 2, auto_schedule: true}"
```

**Via REST API:**
```bash
curl -s -X POST http://localhost:5000/api/mes/work-orders \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "brick_2x4_red",
    "quantity_ordered": 100,
    "priority": 2
  }' | jq
```

### Monitoring Jobs

```bash
# Via ROS2 topic
ros2 topic echo /lego_mcp/job_complete

# Via REST API
curl -s http://localhost:5000/api/mes/jobs?status=running | jq
```

### Emergency Stop

**Via ROS2:**
```bash
ros2 service call /safety/emergency_stop std_srvs/srv/Trigger "{}"
```

**Via REST API:**
```bash
curl -s -X POST http://localhost:5000/api/scada/machines/ALL/emergency-stop
```

---

## CLI Reference

### Node Management

```bash
# List nodes
ros2 node list

# Get node info
ros2 node info /orchestrator_node

# List node parameters
ros2 param list /grbl_node
```

### Topic Operations

```bash
# List topics
ros2 topic list

# Topic info
ros2 topic info /grbl/status

# Echo topic
ros2 topic echo /grbl/status

# Publish to topic
ros2 topic pub /grbl/command std_msgs/msg/String "data: 'G0 X10 Y10'"
```

### Service Operations

```bash
# List services
ros2 service list

# Service type
ros2 service type /manufacturing/create_work_order

# Call service
ros2 service call /grbl/home std_srvs/srv/Trigger "{}"

ros2 service call /manufacturing/schedule_job lego_mcp_msgs/srv/ScheduleJob \
  "{work_order_id: 'WO-001', scheduling_strategy: 'cp_sat'}"
```

### Action Operations

```bash
# List actions
ros2 action list

# Action info
ros2 action info /print_brick

# Send goal
ros2 action send_goal /print_brick lego_mcp_msgs/action/PrintBrick \
  "{brick_id: 'brick_2x4_red', printer_id: 'prusa_mk4_1'}"

# Send goal with feedback
ros2 action send_goal --feedback /print_brick lego_mcp_msgs/action/PrintBrick \
  "{brick_id: 'brick_2x4_red', printer_id: 'prusa_mk4_1'}"
```

### Lifecycle Management

```bash
# List lifecycle nodes
ros2 lifecycle nodes

# Get state
ros2 lifecycle get /grbl_node_lifecycle

# Transition state
ros2 lifecycle set /grbl_node_lifecycle configure
ros2 lifecycle set /grbl_node_lifecycle activate
ros2 lifecycle set /grbl_node_lifecycle deactivate
ros2 lifecycle set /grbl_node_lifecycle cleanup
```

### Diagnostics

```bash
# View diagnostics
ros2 topic echo /diagnostics

# Launch rqt_graph
rqt_graph

# Launch rqt_console
rqt_console

# Record bag
ros2 bag record -a -o my_recording

# Play bag
ros2 bag play my_recording
```

---

## API Integration

### REST API Endpoints

| Action | Endpoint | Method |
|--------|----------|--------|
| Health check | `/health` | GET |
| Bridge status | `/api/ros2/bridge/status` | GET |
| List robots | `/api/ros2/robots` | GET |
| Submit task | `/api/ros2/tasks` | POST |
| Home robot | `/api/ros2/robots/{id}/home` | POST |
| Gripper control | `/api/ros2/robots/{id}/gripper` | POST |
| Create work order | `/api/mes/work-orders` | POST |
| List machines | `/api/scada/machines` | GET |
| Send G-code | `/api/scada/machines/{id}/gcode` | POST |
| Emergency stop | `/api/scada/machines/{id}/emergency-stop` | POST |

### Example: Complete Workflow

```bash
# 1. Create work order
WO_ID=$(curl -s -X POST http://localhost:5000/api/mes/work-orders \
  -H "Content-Type: application/json" \
  -d '{"product_id": "brick_2x4_red", "quantity_ordered": 100}' | jq -r '.work_order_id')

echo "Created: $WO_ID"

# 2. Release work order
curl -s -X POST "http://localhost:5000/api/mes/work-orders/$WO_ID/release" | jq

# 3. Start production
curl -s -X POST "http://localhost:5000/api/mes/work-orders/$WO_ID/start" | jq

# 4. Monitor progress
watch -n 5 "curl -s http://localhost:5000/api/mes/work-orders/$WO_ID | jq '.status, .progress'"

# 5. Complete
curl -s -X POST "http://localhost:5000/api/mes/work-orders/$WO_ID/complete" | jq
```

### MCP Tools Integration

```bash
# List available AI tools
curl -s http://localhost:5000/api/mcp/tools | jq '.[] | .name'

# Execute MCP tool
curl -s -X POST http://localhost:5000/api/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "create_work_order", "arguments": {"product_id": "brick_2x4_red", "quantity": 100}}'
```

---

## Troubleshooting

### Common Issues

#### Nodes not starting
```bash
# Check for missing dependencies
ros2 doctor

# Check specific package
colcon build --packages-select lego_mcp_orchestrator
```

#### Bridge connection failed
```bash
# Verify rosbridge is running
curl -s http://localhost:9090

# Check WebSocket
websocat ws://localhost:9090
```

#### Equipment not responding
```bash
# Check serial ports
ls -la /dev/ttyUSB*

# Test serial connection
screen /dev/ttyUSB0 115200

# Check network equipment
ping 192.168.1.10
nc -zv 192.168.1.10 6666
```

#### MQTT issues
```bash
# Check Mosquitto
docker-compose logs mosquitto

# Test MQTT
mosquitto_sub -h localhost -t '#' -v
```

### Log Locations

| Component | Log Location |
|-----------|--------------|
| ROS2 nodes | `~/.ros/log/` |
| Colcon build | `ros2_ws/log/` |
| Flask app | Docker logs or stdout |
| Mosquitto | `docker-compose logs mosquitto` |

### Useful Debug Commands

```bash
# Verbose node launch
ros2 launch lego_mcp_bringup full_system.launch.py --debug

# Check TF tree
ros2 run tf2_tools view_frames

# Monitor bandwidth
ros2 topic bw /camera/image_raw

# Check message frequency
ros2 topic hz /grbl/status
```

---

## Key Files Reference

| Purpose | Path |
|---------|------|
| Main orchestrator | `ros2_ws/src/lego_mcp_orchestrator/lego_mcp_orchestrator/orchestrator_node.py` |
| GRBL driver | `ros2_ws/src/grbl_ros2/grbl_ros2/grbl_node.py` |
| Supervisor | `ros2_ws/src/lego_mcp_supervisor/lego_mcp_supervisor/supervisor_node.py` |
| YOLO inference | `ros2_ws/src/cnc_vision/cnc_vision/yolo_inference_node.py` |
| Camera node | `ros2_ws/src/cnc_vision/cnc_vision/camera_node.py` |
| Full system launch | `ros2_ws/src/lego_mcp_bringup/launch/full_system.launch.py` |
| Equipment params | `ros2_ws/src/lego_mcp_bringup/config/equipment_params.yaml` |
| Core messages | `ros2_ws/src/lego_mcp_msgs/msg/` |
| Core services | `ros2_ws/src/lego_mcp_msgs/srv/` |
| Core actions | `ros2_ws/src/lego_mcp_msgs/action/` |
| CNC interfaces | `ros2_ws/src/cnc_interfaces/` |

---

## Appendix: Building the Workspace

```bash
# Navigate to workspace
cd /Users/stepheneacuello/Documents/lego_factory/ros2_ws

# Install dependencies
rosdep install --from-paths src --ignore-src -r -y

# Build (skip problematic packages)
colcon build --symlink-install \
  --packages-skip lego_mcp_safety_certified lego_mcp_pinn_twin

# Source the workspace
source install/setup.bash

# Verify build
colcon test --packages-select lego_mcp_msgs
```

---

*Document generated from LEGO Factory v3 codebase analysis. Last updated: January 2026.*
