# CNC SCADA Unity Architecture

Enterprise-grade architecture documentation for the Unity Digital Twin + ROS2 Integration.

## System Overview

The CNC SCADA Unity project implements a complete Industry 4.0 digital twin solution with four integrated packages delivering real-time visualization, production scheduling, predictive maintenance, and remote machine control.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Unity Application Layer                          │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │  Digital Twin    │  │   Scheduling     │  │   Predictive    │ │
│  │      Core        │  │       UI         │  │    Overlay      │ │
│  │                  │  │                  │  │                 │ │
│  │ • ISO 23247     │  │ • Gantt Chart   │  │ • AR Calendar  │ │
│  │ • 6-Axis Anim   │  │ • Drag-Drop     │  │ • Tool Wear    │ │
│  │ • Toolpath Viz  │  │ • OR-Tools      │  │ • Anomalies    │ │
│  │ • Sensor Overlay│  │ • Capacity View │  │ • Health Score │ │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘ │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                  Remote Control Package                      │  │
│  │                                                              │  │
│  │  • Jog Controller (Continuous/Incremental)                  │  │
│  │  • MDI Console (Manual Data Input)                          │  │
│  │  • Program Executor (Run/Pause/Stop)                        │  │
│  │  • Emergency Stop (Safety System)                           │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │               Core Utilities & Infrastructure                │  │
│  │                                                              │  │
│  │  • NetworkUtility (HTTP Client with Retry)                  │  │
│  │  • Setup Wizard (Editor Configuration Tool)                 │  │
│  │  • Assembly Definitions (Code Organization)                 │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    WebSocket + Binary Protocol (60Hz)
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                      Flask SCADA Backend                            │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────┐ │
│  │    Unity     │  │   SocketIO   │  │   ROS2    │  │   MQTT   │ │
│  │   Gateway    │  │   Service    │  │  Bridge   │  │  Client  │ │
│  │              │  │              │  │           │  │          │ │
│  │ • WebSocket  │  │ • Real-time  │  │ • Topics  │  │ • QoS 1  │ │
│  │ • Binary     │  │ • Rooms      │  │ • Actions │  │ • Retain │ │
│  │ • Priority Q │  │ • Broadcast  │  │ • Services│  │          │ │
│  └──────────────┘  └──────────────┘  └───────────┘  └──────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                     Flask API Layer                          │ │
│  │                                                              │ │
│  │  • /api/v1/machine/*      (State, Control)                  │ │
│  │  • /api/v1/gcode/*        (Programs, Toolpaths)             │ │
│  │  • /api/v1/scheduling/*   (Schedule, Optimize)              │ │
│  │  • /api/v1/predictive/*   (Maintenance, Health)             │ │
│  │  • /api/v1/sensors/*      (Real-time Data)                  │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                           MQTT Broker (Mosquitto)
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                         ROS2 Cluster (Humble)                       │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │     CNC      │  │     CNC      │  │     CNC      │            │
│  │   Control    │  │  Scheduler   │  │  Predictive  │            │
│  │              │  │              │  │              │            │
│  │ • Kinematics │  │ • OR-Tools   │  │ • ML Models  │            │
│  │ • Trajectory │  │ • Optimizer  │  │ • Anomaly    │            │
│  │ • Safety     │  │ • Validator  │  │ • RUL Pred   │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                           Edge / Machine Layer
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                    Physical Machines & Sensors                      │
│                                                                     │
│  CNC Machines          Robots           Sensors        PLCs        │
│  • TinyG              • Niryo Ned2     • IMU           • Modbus    │
│  • grbl               • xArm Lite 6    • Temp          • OPC UA    │
│  • Bantam CNC         • UR5e           • Force         • EtherCAT  │
└─────────────────────────────────────────────────────────────────────┘
```

## Package Architecture

### 1. Digital Twin Core (com.cnc-scada.digital-twin-core)

**Purpose**: Real-time 60Hz machine state visualization with ISO 23247 compliance

**Components**:
- **ISO23247StateHandler.cs** (376 lines)
  - State management with JSON and binary protocols
  - 60Hz updates with interpolation and prediction
  - Alarm detection and event broadcasting
  - Statistics tracking and diagnostics

- **KinematicsAnimator.cs** (370 lines)
  - 6-axis animation (X, Y, Z linear + A, B, C rotary)
  - Smooth interpolation with configurable speed
  - Axis limit checking and violation warnings
  - Gizmo visualization for debugging

- **ToolpathVisualizer.cs** (450 lines)
  - G-code path rendering with LineRenderer
  - LOD optimization for large programs
  - Frustum culling for off-screen segments
  - Motion type coloring (rapid, linear, arc)
  - Progress tracking with completed segments

- **SensorOverlayRenderer.cs** (490 lines)
  - Thermal heatmap generation (GPU texture)
  - Vibration particle system
  - Cutting force vector visualization
  - Quality indicator overlays
  - Multi-sensor data fusion

**Key Patterns**:
- Event-driven architecture with `Action<T>` delegates
- State interpolation: `Lerp(previousState, currentState, t)`
- Prediction: `position + velocity * deltaTime`
- LOD: `if (segmentCount > maxSegments) skip = max(1, segmentCount / maxSegments)`

**Dependencies**:
- Unity 2021.3+
- TextMesh Pro 3.0.6+
- Newtonsoft.Json

### 2. Scheduling UI (com.cnc-scada.scheduling-ui)

**Purpose**: Interactive production scheduling with OR-Tools optimization

**Components**:
- **GanttChartController.cs** (550 lines)
  - Timeline visualization with dynamic scaling
  - Machine row generation
  - Job block rendering with color coding
  - Auto-refresh with configurable intervals
  - Zoom and pan controls

- **JobDragDropHandler.cs** (450 lines)
  - Drag-and-drop with ghost image
  - Grid snapping (15/30/60 minute increments)
  - Real-time conflict detection
  - Server-side validation
  - Machine change support
  - Undo/redo stack

- **ScheduleOptimizer.cs** (420 lines)
  - OR-Tools algorithm integration
    - CP-SAT (Google Constraint Programming)
    - Genetic Algorithm
    - Simulated Annealing
  - Multi-objective optimization
    - Minimize makespan
    - Minimize tardiness
    - Maximize utilization
  - Constraint configuration
  - Progress tracking with animation

- **MachineCapacityView.cs** (440 lines)
  - Real-time utilization gauges
  - Bottleneck detection (>90% utilization)
  - Color-coded capacity levels
  - Trending over time windows
  - Statistics dashboard

**Key Patterns**:
- MVVM-like architecture for UI updates
- Command pattern for undo/redo
- Observer pattern for real-time updates
- Validation pipeline: client → server → confirmation

**Dependencies**:
- Unity 2021.3+
- TextMesh Pro 3.0.6+
- Unity UI (UGUI)
- Newtonsoft.Json

### 3. Predictive Overlay (com.cnc-scada.predictive-overlay)

**Purpose**: AR maintenance visualization with ML-driven analytics

**Components**:
- **MaintenanceCalendarAR.cs** (530 lines)
  - 3D maintenance event markers
  - Event types: urgent, scheduled, preventive, predicted
  - Confidence-based filtering
  - Pulsing effects for urgent events
  - Click handling for details
  - Event list UI with scrolling

- **ToolWearIndicator.cs** (480 lines)
  - 3D tool visualization with material blending
  - Wear particle effects
  - Remaining Useful Life (RUL) prediction
  - Confidence intervals (lower/upper bounds)
  - Threshold warnings (caution 70%, critical 90%)
  - Tool change trigger functionality

- **AnomalyMarker.cs** (520 lines)
  - Severity-based visualization (low, medium, high, critical)
  - Anomaly types: vibration, temperature, force, quality
  - Auto-acknowledgment with timeout
  - Pulsing and rotating effects
  - Active anomaly tracking
  - Gizmo sphere visualization

- **HealthScoreDisplay.cs** (570 lines)
  - Overall health gauge
  - Subsystem gauges (mechanical, electrical, thermal, vibration)
  - Smooth animated transitions
  - Color-coded health indicators
  - 3D health hologram
  - Health history tracking (100 samples)
  - Statistics dashboard

**Key Patterns**:
- AR Foundation integration for marker positioning
- ML confidence filtering
- Color interpolation for gradients
- History buffers with circular queues
- Multi-factor scoring algorithms

**Dependencies**:
- Unity 2021.3+
- TextMesh Pro 3.0.6+
- AR Foundation 4.2.7+ (for AR features)
- Newtonsoft.Json

### 4. Remote Control (com.cnc-scada.remote-control)

**Purpose**: Low-latency machine control (<20ms target)

**Components**:
- **JogController.cs** (450 lines)
  - Multi-axis support (X, Y, Z, A, B, C)
  - Continuous jogging (hold to move)
  - Incremental jogging (fixed distances)
  - Wheel/MPG mode
  - Speed control with slider (min/max range)
  - Software limit checking
  - Collision detection integration

- **MDIConsole.cs** (480 lines)
  - Command input with validation
  - Command history (50 entries, persistent)
  - Auto-complete for G-codes
  - Syntax highlighting
  - Command recall (up/down arrows)
  - Client and server validation
  - Dangerous command filtering

- **ProgramExecutor.cs** (520 lines)
  - State machine (IDLE → LOADED → RUNNING → PAUSED/COMPLETED/ERROR)
  - Normal execution mode
  - Single-step mode (line-by-line)
  - Dry-run simulation
  - Pause/resume functionality
  - Stop with confirmation
  - Progress tracking
  - Error handling with auto-pause

- **EmergencyStopButton.cs** (380 lines)
  - Visual status indicators
  - Confirmation dialog
  - Hold-time requirement (0.5s)
  - Double-click safety option
  - Reset functionality with confirmation
  - E-stop event logging
  - Pulsing animation for active state

**Key Patterns**:
- Priority command queue for low latency
- State machine pattern for program execution
- Command validation pipeline
- Event-driven safety system
- Rate limiting for commands

**Dependencies**:
- Unity 2021.3+
- TextMesh Pro 3.0.6+
- Unity UI (UGUI)
- Newtonsoft.Json

## Core Utilities

### NetworkUtility.cs (~150 lines)

**Purpose**: Standardized HTTP communication with retry logic

**Features**:
- Generic GET/POST methods with JSON serialization
- Retry logic with exponential backoff (3 attempts)
- Ping functionality for server health checks
- URL builder for query parameters
- Shared HttpClient instance (connection pooling)

**Usage**:
```csharp
StartCoroutine(NetworkUtility.GetAsync<MachineState>(
    url,
    onSuccess: state => { /* handle */ },
    onError: error => { /* handle */ },
    maxRetries: 3
));
```

### CNCScadaSetupWizard.cs (~300 lines)

**Purpose**: Unity Editor configuration tool

**Features**:
- Multi-tab interface (Setup, Digital Twin, Scheduling, Predictive, Remote Control, About)
- Connection configuration (Flask URL, Machine ID)
- Package status checking
- Test connection functionality
- Scene setup helpers
- Settings persistence via EditorPrefs

**Access**: **Window > CNC SCADA > Setup Wizard**

## Communication Protocols

### WebSocket Protocol (60Hz)

**Connection**:
```
ws://server:5000/socket.io/?transport=websocket
```

**Message Format** (JSON):
```json
{
  "event": "machine_state",
  "data": {
    "machine_id": "CNC-001",
    "position": {"x": 100.5, "y": 50.2, "z": 25.0},
    "velocity": {"x": 500.0, "y": 0.0, "z": 0.0},
    "status": "running",
    "timestamp": "2026-01-15T10:30:00Z"
  }
}
```

**Binary Protocol** (FlatBuffers):
- 5x smaller than JSON
- Zero-copy deserialization
- Schemas in `schemas/flatbuffers/`
- Used for high-frequency updates (>30Hz)

### HTTP REST API

**Base URL**: `http://server:5000/api/v1`

**Common Headers**:
```
Authorization: Bearer <token>
Content-Type: application/json
X-Client-ID: unity-digital-twin
X-Request-ID: <uuid>
```

**Rate Limits**:
- State queries: 100/second
- Control commands: 10/second
- Optimization requests: 1/minute

### MQTT Integration

**Topics**:
```
cnc/<machine_id>/state       # Machine state updates
cnc/<machine_id>/command     # Control commands
cnc/<machine_id>/alarm       # Alarm notifications
cnc/scheduling/schedule      # Schedule updates
cnc/predictive/maintenance   # Maintenance predictions
```

**QoS Levels**:
- State: QoS 0 (at most once)
- Commands: QoS 1 (at least once)
- Alarms: QoS 2 (exactly once)

## Data Flow

### Real-Time State Updates (60Hz)

```
Machine → ROS2 → MQTT → Flask → WebSocket → Unity
  10ms     5ms     2ms    2ms      1ms       60fps

Total Latency: ~20ms end-to-end
```

**Optimization Strategies**:
1. **Binary Protocol**: FlatBuffers reduces payload size
2. **Regional Edge Nodes**: Route to nearest server
3. **Priority Queue**: Control commands skip ahead
4. **Connection Pooling**: Reuse HTTP connections
5. **Prediction**: Client-side extrapolation for smooth animation

### Control Commands (<20ms)

```
Unity → WebSocket → Flask → MQTT → ROS2 → Machine
 1ms      2ms       2ms      2ms     5ms     hardware

Target Latency: <20ms total
```

**Low-Latency Path**:
- WebSocket bypasses HTTP overhead
- Priority queue for jog commands
- Direct serial path for emergency stop
- No database writes on critical path

### Predictive Analytics

```
Sensors → InfluxDB → ML Service → Flask → Unity
 realtime   buffer    batch (1h)  push    display

Update Frequency: Every 5-30 seconds
```

**ML Pipeline**:
1. Sensors write to InfluxDB (time-series)
2. ML service queries last N hours
3. Model inference (tool wear, anomalies, health)
4. Results cached in Redis (5 min TTL)
5. Unity polls or receives push notifications

## Performance Characteristics

### Unity Performance

**Target Frame Rates**:
- Desktop: 60 FPS (16.67ms per frame)
- WebGL: 30 FPS (33.33ms per frame)
- Mobile: 30 FPS (33.33ms per frame)
- VR: 90 FPS (11.11ms per frame)

**Profiling**:
- State updates: <1ms per machine
- Toolpath rendering: <5ms for 1000 segments
- Heatmap generation: <2ms per frame
- UI updates: <0.5ms per frame

**Optimization Techniques**:
- LOD for distant objects
- Frustum culling for off-screen elements
- Object pooling for frequent instantiation
- Texture atlasing for UI elements
- Async loading for large assets

### Network Performance

**Bandwidth Usage** (per machine):
- JSON protocol: ~50 KB/s at 60Hz
- Binary protocol: ~10 KB/s at 60Hz
- With 10 machines: ~100-500 KB/s total

**Connection Limits**:
- WebSocket: 1000 concurrent connections per server
- HTTP: 10,000 requests per second per server
- MQTT: 10,000 clients per broker

### Scaling Characteristics

**Single Server Capacity**:
- 50 machines at 60Hz (binary protocol)
- 20 machines at 60Hz (JSON protocol)
- 100 clients (viewers)

**Multi-Region Deployment**:
- Regional edge nodes for latency
- NATS JetStream for cross-region sync
- Anycast DNS for automatic routing

## Security Architecture

### Authentication

**OAuth2 PKCE Flow**:
1. Unity redirects to auth server
2. User logs in via browser
3. Auth code returned to Unity
4. Exchange code for access token
5. Token stored securely (keychain/keystore)

**Token Format** (JWT):
```json
{
  "sub": "user-123",
  "roles": ["OPERATOR", "SUPERVISOR"],
  "permissions": ["VIEW_STATE", "CONTROL_MACHINE"],
  "exp": 1737000000
}
```

### Authorization

**Command Authorization**:
```
POST /api/v1/control/jog
Headers:
  Authorization: Bearer <token>
  X-Command-Type: JOG
  X-Machine-Id: CNC-001

Backend checks:
1. Token valid and not expired
2. User has CONTROL_MACHINE permission
3. Machine CNC-001 accessible to user
4. Rate limit not exceeded
```

**Role Hierarchy**:
- **Viewer**: Read-only access
- **Operator**: Jog, MDI, run programs
- **Supervisor**: Schedule changes, maintenance
- **Admin**: All permissions

### Encryption

- **TLS 1.3**: All network communication
- **Certificate Pinning**: Mobile apps
- **E2E Encryption**: Critical commands (e-stop)

## Deployment Architecture

### Development

```
Docker Compose:
- flask-scada:5000
- mosquitto:1883
- influxdb:8086
- postgres:5432
- ros2 (optional)

Unity Editor:
- Connect to localhost:5000
- Hot reload on code changes
```

### Production (Kubernetes)

```
Regional Clusters (3):
- US-East, EU-West, Asia-Pacific

Per Cluster:
  Namespace: cnc-scada
    - flask-scada (3 replicas, HPA)
    - unity-gateway (2 replicas, HPA)
    - ros2-bridge (2 replicas)
    - scheduler-service (2 replicas)
    - predictive-service (2 replicas)

  Namespace: data
    - postgres (primary + replica)
    - influxdb (regional)
    - redis-cluster (state cache)

  Namespace: messaging
    - mosquitto (MQTT)
    - nats-jetstream (cross-region)

Edge Clusters (K3s per plant):
  - machine-agents (DaemonSet)
  - local-mqtt (store & forward)
  - local-influxdb (24h buffer)
```

## Testing Strategy

### Unit Tests

**Coverage Target**: 80%+

**Test Categories**:
- State interpolation logic
- Command validation
- Optimization algorithms
- Health scoring calculations

**Framework**: NUnit + Unity Test Runner

### Integration Tests

**Test Scenarios**:
- WebSocket connection and reconnection
- API endpoint responses
- ROS2 topic communication
- MQTT message flow

**Mock Services**: WireMock for Flask API

### Performance Tests

**Metrics**:
- State update latency (p50, p95, p99)
- Frame rate stability (desktop, WebGL, mobile)
- Memory usage over time
- Network bandwidth consumption

**Tools**: Unity Profiler, Chrome DevTools

### User Acceptance Tests

**Test Plans**:
- Machine visualization accuracy
- Schedule optimization results
- Predictive maintenance alerts
- Remote control responsiveness

## Monitoring and Observability

### Metrics (Prometheus)

```
unity_state_updates_total{machine_id}
unity_state_update_latency_ms{machine_id, percentile}
unity_frame_rate{platform}
unity_websocket_connections_total
unity_command_execution_duration_ms{command_type}
```

### Logging (Structured JSON)

```json
{
  "timestamp": "2026-01-15T10:30:00Z",
  "level": "INFO",
  "component": "ISO23247StateHandler",
  "machine_id": "CNC-001",
  "message": "State updated",
  "latency_ms": 15
}
```

### Tracing (OpenTelemetry)

**Trace Example**:
```
unity_jog_command [parent_span_id: abc123]
├─ validate_command [duration: 2ms]
├─ send_to_backend [duration: 15ms]
│  ├─ websocket_send [duration: 1ms]
│  └─ backend_process [duration: 14ms]
└─ update_ui [duration: 1ms]
```

## Version History

**v1.0.0** (2026-01-15):
- Initial release
- All 4 packages complete
- 35 features implemented across 6 phases
- Documentation complete
- Assembly definitions and package manifests
- Setup wizard and utilities

**Planned v1.1.0**:
- WebGL binary protocol support
- Advanced shader effects
- Time-series data visualization
- Multi-machine synchronization
- VR/AR optimizations

## Contributing

**Internal Development Only**

**Workflow**:
1. Create feature branch from `develop`
2. Implement with tests (80% coverage minimum)
3. Update CHANGELOG.md
4. Submit PR for review
5. Merge after approval and CI pass

**Code Standards**:
- C# coding conventions
- XML documentation for public APIs
- Unit tests for business logic
- Integration tests for external dependencies

## License

Proprietary - Copyright © 2026 CNC SCADA Enterprise System

---

**Document Version**: 1.0.0
**Last Updated**: 2026-01-15
**Maintained By**: CNC SCADA Development Team
