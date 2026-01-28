# CNC SCADA Digital Twin Core

Real-time 60Hz digital twin visualization with ISO 23247 compliance for CNC machine monitoring and control.

## Features

- **ISO 23247 State Handling**: International standard compliant digital twin state management
- **60Hz Real-Time Updates**: Smooth visualization with interpolation and prediction
- **6-Axis Kinematics**: Animate X, Y, Z linear axes and A, B, C rotary axes
- **Toolpath Visualization**: Render G-code paths with motion type coloring and LOD optimization
- **Sensor Overlays**: Thermal heatmaps, vibration particles, force vectors, and quality indicators

## Installation

### Via Unity Package Manager

1. Open **Window > Package Manager**
2. Click **+** and select **Add package from disk**
3. Navigate to `/Packages/com.cnc-scada.digital-twin-core/package.json`

### Via Manifest

Add to `Packages/manifest.json`:
```json
{
  "dependencies": {
    "com.cnc-scada.digital-twin-core": "file:../../Packages/com.cnc-scada.digital-twin-core"
  }
}
```

## Quick Start

### 1. Setup State Handler

```csharp
using CNCScada.DigitalTwin;

public class MachineController : MonoBehaviour
{
    private ISO23247StateHandler stateHandler;

    void Start()
    {
        stateHandler = gameObject.AddComponent<ISO23247StateHandler>();
        stateHandler.flaskServerUrl = "http://localhost:5000";
        stateHandler.machineId = "CNC-001";
        stateHandler.updateInterval = 0.016f; // 60Hz

        stateHandler.OnStateUpdated += HandleStateUpdate;
        stateHandler.OnAlarmTriggered += HandleAlarm;
    }

    void HandleStateUpdate(ISO23247StateHandler.MachineState state)
    {
        Debug.Log($"Position: {state.position}, Status: {state.status}");
    }

    void HandleAlarm(ISO23247StateHandler.AlarmData alarm)
    {
        Debug.LogWarning($"Alarm {alarm.alarm_code}: {alarm.message}");
    }
}
```

### 2. Add Kinematics Animation

```csharp
using CNCScada.DigitalTwin;

public class MachineAnimator : MonoBehaviour
{
    [SerializeField] private ISO23247StateHandler stateHandler;
    [SerializeField] private KinematicsAnimator kinematicsAnimator;

    void Start()
    {
        kinematicsAnimator.stateHandler = stateHandler;
        kinematicsAnimator.enablePrediction = true;
        kinematicsAnimator.predictionTime = 0.1f;
    }
}
```

### 3. Visualize Toolpath

```csharp
using CNCScada.DigitalTwin;

public class ToolpathManager : MonoBehaviour
{
    [SerializeField] private ToolpathVisualizer toolpathVisualizer;

    void Start()
    {
        toolpathVisualizer.flaskServerUrl = "http://localhost:5000";
        toolpathVisualizer.programId = "PART-001";

        toolpathVisualizer.OnPathLoadComplete += () => {
            Debug.Log("Toolpath loaded successfully");
        };
    }
}
```

### 4. Add Sensor Overlays

```csharp
using CNCScada.DigitalTwin;

public class SensorVisualizer : MonoBehaviour
{
    [SerializeField] private SensorOverlayRenderer sensorRenderer;

    void Start()
    {
        sensorRenderer.flaskServerUrl = "http://localhost:5000";
        sensorRenderer.machineId = "CNC-001";
        sensorRenderer.showThermalHeatmap = true;
        sensorRenderer.showVibrationParticles = true;
    }
}
```

## Component Reference

### ISO23247StateHandler

Manages machine state with ISO 23247 compliance.

**Serialized Fields:**
- `flaskServerUrl` (string): Flask server base URL
- `machineId` (string): Machine identifier
- `updateInterval` (float): Update frequency in seconds (default: 0.016 for 60Hz)
- `enablePrediction` (bool): Enable state prediction
- `enableInterpolation` (bool): Enable smooth interpolation

**Events:**
- `OnStateUpdated(MachineState)`: Fired when state updates
- `OnAlarmTriggered(AlarmData)`: Fired on alarms
- `OnConnectionLost()`: Fired on connection failure

**Public Methods:**
```csharp
MachineState GetCurrentState()
MachineState GetInterpolatedState()
MachineState GetPredictedState(float predictionTime)
Dictionary<string, object> GetStatistics()
```

### KinematicsAnimator

Animates 6-axis CNC machine kinematics.

**Serialized Fields:**
- `xAxisTransform`, `yAxisTransform`, `zAxisTransform`: Linear axis transforms
- `aAxisTransform`, `bAxisTransform`, `cAxisTransform`: Rotary axis transforms
- `xAxisDirection`, `yAxisDirection`, `zAxisDirection`: Linear axis directions
- `positionScale` (float): Scale factor for position visualization
- `rotationScale` (float): Scale factor for rotation visualization

**Configuration:**
- `xLimits`, `yLimits`, `zLimits` (Vector2): Axis travel limits
- `aLimits`, `bLimits`, `cLimits` (Vector2): Rotary axis limits
- `animationSpeed` (float): Interpolation speed

**Events:**
- `OnPositionChanged(Vector3)`: Fired on position change
- `OnLimitExceeded(string)`: Fired when axis exceeds limits

**Public Methods:**
```csharp
void SetTargetPosition(Vector3 position, Vector3 rotation)
Vector3 GetCurrentPosition()
Vector3 GetCurrentRotation()
bool IsWithinLimits()
```

### ToolpathVisualizer

Renders G-code toolpaths with LOD and culling.

**Serialized Fields:**
- `flaskServerUrl` (string): Server URL
- `programId` (string): G-code program identifier
- `pathLineRenderer` (LineRenderer): Renderer for path
- `progressLineRenderer` (LineRenderer): Renderer for completed segments

**Visual Settings:**
- `rapidColor`, `linearColor`, `arcCWColor`, `arcCCWColor`: Motion type colors
- `completedColor` (Color): Color for completed segments
- `lineWidth` (float): Path line width
- `colorByFeedrate` (bool): Color by feedrate instead of motion type

**Performance:**
- `enableLOD` (bool): Level-of-detail optimization
- `enableCulling` (bool): Camera frustum culling
- `maxSegmentsLOD0`, `maxSegmentsLOD1`, `maxSegmentsLOD2`: LOD segment limits

**Events:**
- `OnPathLoadComplete()`: Fired when toolpath loads
- `OnProgressUpdated(float)`: Fired on progress change

**Public Methods:**
```csharp
void LoadProgram(string programId)
void SetProgress(float progress) // 0.0 to 1.0
void ClearPath()
List<PathSegment> GetPathData()
```

### SensorOverlayRenderer

Visualizes sensor data with heatmaps and particles.

**Serialized Fields:**
- `flaskServerUrl` (string): Server URL
- `machineId` (string): Machine identifier
- `machineTransform` (Transform): Machine reference for overlays

**Visualization Options:**
- `showThermalHeatmap` (bool): Display thermal heatmap
- `showVibrationParticles` (bool): Display vibration particles
- `showForceVectors` (bool): Display cutting force vectors
- `showQualityIndicators` (bool): Display quality metrics

**Heatmap Settings:**
- `heatmapResolution` (int): Texture resolution (default: 128)
- `temperatureGradient` (Gradient): Temperature color mapping
- `minTemperature`, `maxTemperature` (float): Temp range

**Events:**
- `OnSensorDataUpdated(SensorData)`: Fired on data update
- `OnAnomalyDetected(string)`: Fired on sensor anomaly

**Public Methods:**
```csharp
void SetHeatmapVisible(bool visible)
void SetVibrationVisible(bool visible)
SensorData GetCurrentSensorData()
Dictionary<string, object> GetStatistics()
```

## Configuration

### Setup Wizard

Open **CNC SCADA > Setup Wizard** from Unity menu to configure connection settings and test connectivity.

### Connection Settings

```csharp
// Configure via code
var stateHandler = GetComponent<ISO23247StateHandler>();
stateHandler.flaskServerUrl = "http://192.168.1.100:5000";
stateHandler.machineId = "CNC-001";
stateHandler.updateInterval = 0.016f; // 60Hz
```

### Performance Tuning

```csharp
// For high-frequency updates
stateHandler.enableInterpolation = true;
stateHandler.enablePrediction = true;
stateHandler.predictionTime = 0.1f; // 100ms lookahead

// For low-end hardware
toolpathVisualizer.enableLOD = true;
toolpathVisualizer.enableCulling = true;
toolpathVisualizer.maxSegmentsLOD0 = 1000;
```

## Backend API Requirements

### State Endpoint
```
GET /api/v1/machine/state?machine_id={id}

Response:
{
  "success": true,
  "state": {
    "machine_id": "CNC-001",
    "position": {"x": 100.5, "y": 50.2, "z": 25.0},
    "rotation": {"a": 0.0, "b": 0.0, "c": 45.0},
    "velocity": {"x": 500.0, "y": 0.0, "z": 0.0},
    "status": "running",
    "feedrate": 1000.0,
    "spindle_speed": 5000.0
  }
}
```

### Toolpath Endpoint
```
GET /api/v1/gcode/toolpath?program_id={id}

Response:
{
  "success": true,
  "segments": [
    {
      "motion_type": "G1",
      "start": {"x": 0, "y": 0, "z": 0},
      "end": {"x": 100, "y": 0, "z": 0},
      "feedrate": 1000.0
    }
  ]
}
```

### Sensor Endpoint
```
GET /api/v1/sensors/realtime?machine_id={id}

Response:
{
  "success": true,
  "sensors": {
    "temperature": [
      {"x": 0.0, "y": 0.0, "z": 0.0, "value": 45.5}
    ],
    "vibration": {"x": 0.1, "y": 0.2, "z": 0.05},
    "force": {"x": 150.0, "y": 80.0, "z": 200.0}
  }
}
```

## Troubleshooting

### No State Updates

1. Check Flask server is running: `curl http://localhost:5000/api/v1/health`
2. Verify machine_id matches backend configuration
3. Check Unity Console for connection errors
4. Test connection in Setup Wizard

### Choppy Animation

1. Increase `updateInterval` for higher frequency (e.g., 0.016 for 60Hz)
2. Enable `enableInterpolation` on ISO23247StateHandler
3. Reduce `animationSpeed` on KinematicsAnimator for smoother transitions

### Performance Issues

1. Enable LOD on ToolpathVisualizer
2. Reduce `heatmapResolution` on SensorOverlayRenderer
3. Disable unused visualizations
4. Check backend response times (should be <50ms)

### Axis Limits Exceeded

1. Verify axis limits match machine specifications
2. Check `positionScale` matches backend units (mm vs inches)
3. Review backend state data for invalid values

## Examples

See `Samples~/` directory for:
- Basic machine visualization scene
- Multi-machine monitoring dashboard
- Toolpath preview application
- Sensor heatmap demo

## Dependencies

- Unity 2021.3 or later
- TextMesh Pro 3.0.6+
- Newtonsoft.Json (included)

## License

Proprietary - Part of CNC SCADA Enterprise System

## Support

For issues and feature requests, contact the CNC SCADA development team.
