# CNC SCADA Digital Twin - Unity Project

Real-time 3D visualization for CNC machines and robotic arms using Unity.

## Quick Start

### Prerequisites

- **Unity Hub** (latest version)
- **Unity 2022.3 LTS** or newer
- Unity Robotics packages (auto-installed via manifest.json)

### Setup

1. **Open the project in Unity Hub:**
   - Click "Open" in Unity Hub
   - Navigate to `/flask_cnc_app/unity-project`
   - Select the folder and open

2. **Install Unity Robotics packages:**
   - Unity should auto-import packages from `Packages/manifest.json`
   - If not, go to Window > Package Manager
   - Add packages:
     - `com.unity.robotics.ros-tcp-connector`
     - `com.unity.robotics.urdf-importer`

3. **Configure server connection:**
   - Open the scene: `Assets/Scenes/DigitalTwin.unity`
   - Select `FlaskSocketIOClient` GameObject
   - Set `Server URL` to your Flask backend (default: `http://localhost:5001`)

4. **Play in Editor:**
   - Press Play to test the connection
   - The digital twin should connect to Flask and display machine state

## Project Structure

```
unity-project/
├── Assets/
│   ├── Scripts/
│   │   ├── Connection/          # Flask/ROS2 communication
│   │   │   ├── FlaskSocketIOClient.cs
│   │   │   └── WebSocketConnection.cs
│   │   ├── DigitalTwin/         # 3D visualization
│   │   │   ├── DigitalTwinController.cs
│   │   │   ├── MachineController.cs
│   │   │   └── RobotController.cs
│   │   ├── ROS2/                # ROS2 integration
│   │   │   ├── ROS2Connection.cs
│   │   │   └── ROSRobotController.cs
│   │   └── URDF/                # Robot model import
│   │       ├── URDFImportSettings.cs
│   │       └── URDFLoader.cs
│   ├── Editor/                  # Build scripts
│   │   └── WebGLBuildScript.cs
│   ├── Plugins/WebGL/           # WebGL native plugins
│   │   └── WebSocket.jslib
│   ├── Prefabs/                 # Reusable prefabs
│   ├── Scenes/                  # Unity scenes
│   └── Materials/               # Visual materials
├── Packages/
│   └── manifest.json            # Package dependencies
└── ProjectSettings/             # Unity project settings
```

## Features

### Real-Time Communication

- **Flask SocketIO**: Connects to Flask backend via WebSocket
- **ROS2 Bridge**: Optional direct ROS2 connection via TCP
- **Binary Protocol**: Optimized for <20ms latency at 60Hz

### Visualization

- **Machine State**: Real-time X/Y/Z position, spindle speed, status
- **Toolpath Display**: G-code path visualization with progress
- **Sensor Overlay**: Temperature, vibration heatmaps
- **Robot Animation**: 6-DOF joint animation with IK

### Supported Hardware

- **Bantam CNC Explorer**: Full kinematics and sensor visualization
- **Niryo Ned2**: 6-DOF collaborative robot
- **xArm Lite 6**: 6-DOF industrial robot

## Building for WebGL

### Production Build

1. Open Unity
2. Go to `CNC SCADA > Build WebGL`
3. Build outputs to: `ui/static/unity-webgl/`

### Development Build

1. Go to `CNC SCADA > Build WebGL (Development)`
2. Includes debugging symbols and stack traces

### Embedding in Flask

After building, the WebGL build is automatically placed in `ui/static/unity-webgl/`.

Add to your Flask template:

```html
<iframe
    src="/static/unity-webgl/index.html"
    style="width: 100%; height: 600px; border: none;"
    allowfullscreen
></iframe>
```

Or configure via JavaScript:

```html
<script>
    window.unityConfig = {
        serverUrl: 'http://localhost:5001',
        machineId: 'bantam-cnc'
    };
</script>
<script src="/static/unity-webgl/Build/UnityLoader.js"></script>
```

## ROS2 Integration

### Prerequisites

- ROS2 Humble or newer
- `ros_tcp_endpoint` package running

### Setup

1. Start ROS2 TCP endpoint:
   ```bash
   ros2 run ros_tcp_endpoint default_server_endpoint
   ```

2. Configure in Unity:
   - Select `ROS2Connection` GameObject
   - Set `ROS IP Address` and `ROS Port` (default: 10000)

### Available Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/cnc/machine_state` | `MachineState` | CNC position and status |
| `/cnc/joint_states` | `JointState` | Robot joint positions |
| `/cnc/command` | `Command` | G-code and jog commands |

## API Reference

### FlaskSocketIOClient

```csharp
// Connect to Flask backend
FlaskSocketIOClient.Instance.Connect();

// Send G-code
FlaskSocketIOClient.Instance.SendGCode("G1 X10 Y10 F1000");

// Jog axis
FlaskSocketIOClient.Instance.Jog("X", 10f, 500f);

// Emergency stop
FlaskSocketIOClient.Instance.EmergencyStop();
```

### DigitalTwinController

```csharp
// Spawn machines
DigitalTwinController.Instance.SpawnMachine("cnc-1", MachineType.BantamCNC, Vector3.zero);
DigitalTwinController.Instance.SpawnRobot("robot-1", RobotType.NiryoNed2, new Vector3(-0.5f, 0, 0));

// Clear toolpath
DigitalTwinController.Instance.ClearToolpath();
```

### Events

| Event | Description |
|-------|-------------|
| `OnConnected` | Connection established |
| `OnDisconnected` | Connection lost |
| `OnMachineStateUpdate` | New machine state received |
| `OnSensorDataUpdate` | New sensor data received |

## Troubleshooting

### Connection Failed

1. Verify Flask backend is running: `http://localhost:5001`
2. Check CORS settings in Flask
3. Verify WebSocket support in browser (for WebGL)

### Models Not Loading

1. Check `3d-models` path in Flask routes
2. Verify STL files exist in `unity/models/`
3. Check browser console for 404 errors

### Performance Issues

1. Reduce update rate in `FlaskSocketIOClient`
2. Enable LOD for robot models
3. Disable shadows for WebGL builds

## Development

### Adding New Machine Types

1. Create prefab in `Assets/Prefabs/Machines/`
2. Add entry to `MachineType` enum
3. Implement `MachineController` for kinematics
4. Update `DigitalTwinController.SpawnMachine()`

### Adding New Robot Types

1. Import URDF via `Assets > Import Robot from URDF`
2. Add entry to `RobotType` enum
3. Configure joint limits in `RobotController`
4. Update `URDFImportSettings` with robot config

## License

Part of the Flask CNC SCADA System.
