# CNC SCADA Predictive Overlay

AR maintenance visualization with ML-driven predictions for tool wear, anomalies, and health scoring.

## Features

- **AR Maintenance Calendar**: 3D maintenance event markers with confidence filtering
- **Tool Wear Indicators**: Visual tool condition with remaining useful life prediction
- **Anomaly Markers**: Real-time anomaly detection with severity-based visualization
- **Health Score Display**: Multi-factor machine health gauges with trending
- **Predictive Analytics**: ML-driven failure prediction and maintenance scheduling

## Installation

### Via Unity Package Manager

1. Open **Window > Package Manager**
2. Click **+** and select **Add package from disk**
3. Navigate to `/Packages/com.cnc-scada.predictive-overlay/package.json`

### Via Manifest

Add to `Packages/manifest.json`:
```json
{
  "dependencies": {
    "com.cnc-scada.predictive-overlay": "file:../../Packages/com.cnc-scada.predictive-overlay",
    "com.unity.xr.arfoundation": "4.2.7"
  }
}
```

## Quick Start

### 1. Setup Maintenance Calendar

```csharp
using CNCScada.Predictive;

public class MaintenanceManager : MonoBehaviour
{
    [SerializeField] private MaintenanceCalendarAR calendar;
    [SerializeField] private Transform machineTransform;

    void Start()
    {
        calendar.flaskServerUrl = "http://localhost:5000";
        calendar.machineTransform = machineTransform;
        calendar.predictionHorizonDays = 30;
        calendar.confidenceThreshold = 0.7f;

        calendar.OnMaintenanceEventSelected += HandleEventSelected;
        calendar.OnUrgentMaintenanceDetected += HandleUrgentMaintenance;
    }

    void HandleEventSelected(MaintenanceCalendarAR.MaintenanceEvent evt)
    {
        Debug.Log($"Selected: {evt.maintenance_type} on {evt.predicted_date}");
    }

    void HandleUrgentMaintenance(MaintenanceCalendarAR.MaintenanceEvent evt)
    {
        Debug.LogWarning($"URGENT: {evt.description}");
    }
}
```

### 2. Add Tool Wear Indicator

```csharp
using CNCScada.Predictive;

public class ToolMonitor : MonoBehaviour
{
    [SerializeField] private ToolWearIndicator toolIndicator;

    void Start()
    {
        toolIndicator.flaskServerUrl = "http://localhost:5000";
        toolIndicator.machineId = "CNC-001";
        toolIndicator.enable3DWearVisualization = true;

        toolIndicator.OnToolWarning += HandleToolWarning;
        toolIndicator.OnToolCritical += HandleToolCritical;
    }

    void HandleToolWarning(ToolWearIndicator.ToolWearData tool)
    {
        Debug.LogWarning($"Tool {tool.tool_number} approaching end of life: {tool.wear_percent:F1}%");
    }

    void HandleToolCritical(ToolWearIndicator.ToolWearData tool)
    {
        Debug.LogError($"CRITICAL: Tool {tool.tool_number} needs immediate replacement!");
        toolIndicator.TriggerToolChange();
    }
}
```

### 3. Setup Anomaly Detection

```csharp
using CNCScada.Predictive;

public class AnomalyMonitor : MonoBehaviour
{
    [SerializeField] private AnomalyMarker anomalyMarker;

    void Start()
    {
        anomalyMarker.flaskServerUrl = "http://localhost:5000";
        anomalyMarker.machineId = "CNC-001";
        anomalyMarker.enableSeverityFiltering = true;
        anomalyMarker.minSeverity = "medium";

        anomalyMarker.OnAnomalyDetected += HandleAnomaly;
        anomalyMarker.OnCriticalAnomalyDetected += HandleCriticalAnomaly;
    }

    void HandleAnomaly(AnomalyMarker.AnomalyData anomaly)
    {
        Debug.Log($"Anomaly: {anomaly.anomaly_type} - {anomaly.description}");
    }

    void HandleCriticalAnomaly(AnomalyMarker.AnomalyData anomaly)
    {
        Debug.LogError($"CRITICAL ANOMALY: {anomaly.description}");
        // Trigger alert system
    }
}
```

### 4. Display Health Scores

```csharp
using CNCScada.Predictive;

public class HealthMonitor : MonoBehaviour
{
    [SerializeField] private HealthScoreDisplay healthDisplay;

    void Start()
    {
        healthDisplay.flaskServerUrl = "http://localhost:5000";
        healthDisplay.machineId = "CNC-001";
        healthDisplay.enableSmoothTransitions = true;
        healthDisplay.enable3DHealthOverlay = true;

        healthDisplay.OnHealthScoreUpdated += HandleHealthUpdate;
        healthDisplay.OnSubsystemHealthCritical += HandleSubsystemCritical;
    }

    void HandleHealthUpdate(HealthScoreDisplay.HealthScoreData health)
    {
        Debug.Log($"Health: {health.overall_health_score:P0} - {health.health_status}");
    }

    void HandleSubsystemCritical(string subsystem, float score)
    {
        Debug.LogWarning($"{subsystem} subsystem critical: {score:P0}");
    }
}
```

## Component Reference

### MaintenanceCalendarAR

AR maintenance event visualization with 3D markers.

**Serialized Fields:**
- `flaskServerUrl` (string): Flask server base URL
- `updateInterval` (float): Update frequency in seconds (default: 30)
- `predictionHorizonDays` (int): Prediction window (default: 30)
- `confidenceThreshold` (float): Minimum confidence to display (default: 0.7)

**AR Settings:**
- `arCamera` (Camera): AR camera reference
- `machineTransform` (Transform): Machine reference for marker positioning
- `markerDistance` (float): Distance from machine for markers
- `markerScale` (float): Marker scale factor

**Marker Prefabs:**
- `urgentMaintenancePrefab`: Red, pulsing marker for urgent events
- `scheduledMaintenancePrefab`: Yellow marker for scheduled events
- `preventiveMaintenancePrefab`: Green marker for preventive maintenance
- `predictionMarkerPrefab`: Cyan marker for ML predictions

**Visual Settings:**
- `showLabels` (bool): Display text labels on markers
- `showTimeline` (bool): Show timeline visualization
- `enableAnimations` (bool): Animate marker appearance
- `showLowConfidence` (bool): Show predictions below threshold

**Event Types:**
- `"urgent"`: Immediate attention required
- `"scheduled"`: Pre-scheduled maintenance
- `"preventive"`: Preventive maintenance window
- `"predicted"`: ML-predicted maintenance need

**Events:**
- `OnMaintenanceEventSelected(MaintenanceEvent)`: Marker clicked
- `OnUrgentMaintenanceDetected(MaintenanceEvent)`: Urgent event detected

**Public Methods:**
```csharp
void SetARMode(bool enabled)
Dictionary<string, object> GetStatistics()
```

### ToolWearIndicator

Tool wear visualization with RUL prediction.

**Serialized Fields:**
- `flaskServerUrl` (string): Flask server base URL
- `machineId` (string): Machine identifier
- `updateInterval` (float): Update frequency (default: 5s)

**3D Tool References:**
- `toolTransform` (Transform): Tool GameObject
- `toolHolderTransform` (Transform): Tool holder reference
- `newToolMaterial` (Material): Material for new tools
- `wornToolMaterial` (Material): Material for worn tools

**UI References:**
- `wearLevelSlider` (Slider): Wear percentage gauge
- `wearPercentText` (Text): Wear percentage display
- `remainingLifeText` (Text): Remaining useful life display
- `toolNumberText` (Text): Tool number display
- `statusIndicator` (Image): Color-coded status indicator

**Visual Settings:**
- `healthyColor` (Color): <70% wear (green)
- `cautionColor` (Color): 70-90% wear (yellow)
- `criticalColor` (Color): >90% wear (red)
- `cautionThreshold` (float): Warning threshold (default: 0.7)
- `criticalThreshold` (float): Critical threshold (default: 0.9)

**Wear Visualization:**
- `enable3DWearVisualization` (bool): Enable 3D effects
- `wearParticlePrefab` (GameObject): Particle effect for wear
- `particleEmissionRate` (float): Particle rate multiplier
- `showWearHeatmap` (bool): Show thermal wear heatmap

**Prediction:**
- `enablePrediction` (bool): Enable RUL prediction
- `predictionHorizonHours` (int): Prediction window (default: 24)
- `showConfidenceInterval` (bool): Show prediction bounds

**Events:**
- `OnToolWearUpdated(ToolWearData)`: Wear data updated
- `OnToolWarning(ToolWearData)`: Tool approaching end of life
- `OnToolCritical(ToolWearData)`: Tool needs immediate replacement

**Public Methods:**
```csharp
List<float> GetWearHistory()
void TriggerToolChange()
Dictionary<string, object> GetStatistics()
```

### AnomalyMarker

Real-time anomaly detection visualization.

**Serialized Fields:**
- `flaskServerUrl` (string): Flask server base URL
- `machineId` (string): Machine identifier
- `updateInterval` (float): Update frequency (default: 2s)

**AR Settings:**
- `arCamera` (Camera): AR camera reference
- `machineTransform` (Transform): Machine reference
- `markerDistance` (float): Distance from machine

**Marker Prefabs:**
- `lowSeverityMarkerPrefab`: Blue marker (informational)
- `mediumSeverityMarkerPrefab`: Yellow marker (warning)
- `highSeverityMarkerPrefab`: Orange marker (significant)
- `criticalSeverityMarkerPrefab`: Red, pulsing marker (critical)

**Visual Settings:**
- `showAnomalyLabels` (bool): Display anomaly descriptions
- `enablePulsing` (bool): Pulsing effect for active anomalies
- `enableRotation` (bool): Rotating effect for markers
- `markerScale` (float): Marker size

**Filtering:**
- `enableSeverityFiltering` (bool): Filter by severity
- `minSeverity` (string): Minimum severity to display ("low", "medium", "high", "critical")
- `enableTypeFiltering` (bool): Filter by anomaly type
- `visibleTypes` (string[]): Types to display

**Anomaly Types:**
- `"vibration"`: Abnormal vibration detected
- `"temperature"`: Temperature anomaly
- `"force"`: Cutting force anomaly
- `"quality"`: Quality degradation detected
- `"predicted"`: ML-predicted anomaly

**Auto-Acknowledgment:**
- `enableAutoAcknowledge` (bool): Auto-acknowledge after timeout
- `acknowledgeTimeout` (float): Timeout in seconds (default: 300)

**Events:**
- `OnAnomalyDetected(AnomalyData)`: New anomaly detected
- `OnAnomalyAcknowledged(string)`: Anomaly acknowledged
- `OnCriticalAnomalyDetected(AnomalyData)`: Critical anomaly
- `OnAnomalyCleared(string)`: Anomaly resolved

**Public Methods:**
```csharp
void AcknowledgeAnomaly(string anomalyId)
void ClearAnomaly(string anomalyId)
List<AnomalyData> GetActiveAnomalies()
Dictionary<string, object> GetStatistics()
```

### HealthScoreDisplay

Multi-factor health scoring with gauges.

**Serialized Fields:**
- `flaskServerUrl` (string): Flask server base URL
- `machineId` (string): Machine identifier
- `updateInterval` (float): Update frequency (default: 5s)

**UI References:**
- `overallHealthFill` (Image): Overall health gauge fill
- `overallHealthText` (Text): Health status text
- `overallHealthPercent` (Text): Health percentage
- `mechanicalHealthGauge` (Image): Mechanical subsystem gauge
- `electricalHealthGauge` (Image): Electrical subsystem gauge
- `thermalHealthGauge` (Image): Thermal subsystem gauge
- `vibrationHealthGauge` (Image): Vibration subsystem gauge
- `statusSummaryText` (Text): Detailed status summary
- `warningPanel` (GameObject): Warning panel for critical health

**Gauge Settings:**
- `excellentColor` (Color): >90% health (green)
- `goodColor` (Color): 75-90% health (cyan)
- `fairColor` (Color): 50-75% health (yellow)
- `poorColor` (Color): 25-50% health (orange)
- `criticalColor` (Color): <25% health (red)
- `gaugeAnimationSpeed` (float): Smooth transition speed
- `enableSmoothTransitions` (bool): Enable animated transitions

**Health Thresholds:**
- `excellentThreshold` (float): 0.9 (90%)
- `goodThreshold` (float): 0.75 (75%)
- `fairThreshold` (float): 0.5 (50%)
- `poorThreshold` (float): 0.25 (25%)

**3D Visualization:**
- `machineTransform` (Transform): Machine reference
- `enable3DHealthOverlay` (bool): Enable 3D hologram
- `healthOverlayMaterial` (Material): Overlay material
- `healthHologramPrefab` (GameObject): Hologram prefab

**Health Factors:**
- **Overall**: Composite health score (0.0-1.0)
- **Mechanical**: Mechanical subsystems (bearings, guides, etc.)
- **Electrical**: Electrical subsystems (motors, drives, etc.)
- **Thermal**: Thermal management (cooling, temperature)
- **Vibration**: Vibration analysis (balance, alignment)

**Events:**
- `OnHealthScoreUpdated(HealthScoreData)`: Health updated
- `OnSubsystemHealthCritical(string subsystem, float score)`: Subsystem critical

**Public Methods:**
```csharp
List<float> GetHealthHistory(string component)
HealthScoreData GetCurrentHealthData()
Dictionary<string, object> GetStatistics()
```

## Configuration

### Setup Wizard

Open **CNC SCADA > Setup Wizard** and navigate to the **Predictive** tab to configure settings.

### AR Configuration

```csharp
// Enable AR mode for maintenance calendar
calendar.SetARMode(true);
calendar.arCamera = Camera.main;

// Position markers relative to machine
calendar.machineTransform = machineObject.transform;
calendar.markerDistance = 0.5f; // 0.5m above machine
```

### Prediction Tuning

```csharp
// Aggressive prediction for proactive maintenance
calendar.predictionHorizonDays = 60;
calendar.confidenceThreshold = 0.5f; // Show more predictions
calendar.showLowConfidence = true;

// Conservative prediction for critical operations
calendar.predictionHorizonDays = 14;
calendar.confidenceThreshold = 0.9f; // Only high confidence
calendar.showLowConfidence = false;
```

### Performance Optimization

```csharp
// For many machines or low-end devices
calendar.updateInterval = 60f; // Update every minute
healthDisplay.enableSmoothTransitions = false;
anomalyMarker.enablePulsing = false;
anomalyMarker.enableRotation = false;
```

## Backend API Requirements

### Maintenance Prediction Endpoint
```
GET /api/v1/predictive/maintenance?horizon_days={days}

Response:
{
  "success": true,
  "events": [
    {
      "event_id": "MAINT-001",
      "machine_id": "CNC-001",
      "event_type": "predicted",
      "maintenance_type": "tool_change",
      "predicted_date": "2026-01-20T14:00:00Z",
      "days_until": 5,
      "confidence": 0.85,
      "description": "Tool T5 predicted failure",
      "severity": "high"
    }
  ],
  "summary": {
    "total_events": 3,
    "urgent_count": 1,
    "predicted_count": 2
  }
}
```

### Tool Wear Endpoint
```
GET /api/v1/predictive/tool-wear?machine_id={id}

Response:
{
  "success": true,
  "tool_data": {
    "tool_number": 5,
    "tool_type": "End Mill 10mm",
    "wear_percent": 72.5,
    "remaining_life_hours": 12.5,
    "condition": "caution"
  },
  "prediction": {
    "predicted_remaining_hours": 12.5,
    "confidence": 0.82,
    "lower_bound_hours": 10.0,
    "upper_bound_hours": 15.0
  }
}
```

### Anomaly Detection Endpoint
```
GET /api/v1/predictive/anomalies?machine_id={id}

Response:
{
  "success": true,
  "anomalies": [
    {
      "anomaly_id": "ANOM-001",
      "anomaly_type": "vibration",
      "severity": "high",
      "confidence": 0.91,
      "description": "Abnormal vibration on X-axis",
      "detected_at": "2026-01-15T10:30:00Z"
    }
  ]
}
```

### Health Score Endpoint
```
GET /api/v1/predictive/health-score?machine_id={id}

Response:
{
  "success": true,
  "health_data": {
    "machine_id": "CNC-001",
    "overall_health_score": 0.78,
    "mechanical": {"score": 0.85, "status": "good"},
    "electrical": {"score": 0.72, "status": "fair"},
    "thermal": {"score": 0.80, "status": "good"},
    "vibration": {"score": 0.75, "status": "good"},
    "health_status": "good",
    "predicted_failure_probability": 0.15,
    "days_until_maintenance": 12
  }
}
```

## Troubleshooting

### Markers Not Appearing

1. Check AR camera is properly assigned
2. Verify machine transform is set
3. Check console for API errors
4. Ensure confidence threshold isn't too high

### Tool Wear Not Updating

1. Verify machine_id matches backend
2. Check update interval is reasonable
3. Ensure backend is publishing tool data
4. Test endpoint manually with curl

### Health Score Incorrect

1. Verify all subsystem gauges are assigned
2. Check backend health calculation
3. Ensure smooth transitions aren't disabled
4. Review health thresholds

### Performance Issues

1. Increase update intervals
2. Disable smooth transitions
3. Disable 3D visualizations
4. Reduce marker count with higher confidence threshold

## Examples

See `Samples~/` directory for:
- AR maintenance calendar scene
- Tool wear monitoring dashboard
- Anomaly detection visualization
- Health score dashboard

## Dependencies

- Unity 2021.3 or later
- TextMesh Pro 3.0.6+
- Unity UI (UGUI)
- AR Foundation 4.2.7+ (for AR features)
- Newtonsoft.Json (included)

## License

Proprietary - Part of CNC SCADA Enterprise System

## Support

For issues and feature requests, contact the CNC SCADA development team.