# CNC SCADA Scheduling UI

Interactive production scheduling with Gantt chart, drag-drop rescheduling, and OR-Tools optimization integration.

## Features

- **Interactive Gantt Chart**: Timeline visualization with machine rows and job blocks
- **Drag-Drop Rescheduling**: Visual job rescheduling with conflict detection and validation
- **OR-Tools Optimization**: Multiple algorithms (CP-SAT, Genetic, Simulated Annealing)
- **Machine Capacity View**: Real-time utilization and bottleneck visualization
- **Multi-Objective Optimization**: Minimize makespan, tardiness, or maximize utilization

## Installation

### Via Unity Package Manager

1. Open **Window > Package Manager**
2. Click **+** and select **Add package from disk**
3. Navigate to `/Packages/com.cnc-scada.scheduling-ui/package.json`

### Via Manifest

Add to `Packages/manifest.json`:
```json
{
  "dependencies": {
    "com.cnc-scada.scheduling-ui": "file:../../Packages/com.cnc-scada.scheduling-ui"
  }
}
```

## Quick Start

### 1. Setup Gantt Chart

```csharp
using CNCScada.Scheduling;

public class SchedulingDashboard : MonoBehaviour
{
    [SerializeField] private GanttChartController ganttChart;

    void Start()
    {
        ganttChart.flaskServerUrl = "http://localhost:5000";
        ganttChart.scheduleHorizonDays = 7;
        ganttChart.autoRefreshInterval = 30f;

        ganttChart.OnScheduleLoaded += HandleScheduleLoaded;
        ganttChart.OnJobSelected += HandleJobSelected;

        ganttChart.LoadSchedule();
    }

    void HandleScheduleLoaded(int jobCount, int machineCount)
    {
        Debug.Log($"Schedule loaded: {jobCount} jobs on {machineCount} machines");
    }

    void HandleJobSelected(GanttChartController.ScheduledJob job)
    {
        Debug.Log($"Selected: {job.job_id} on {job.machine_id}");
    }
}
```

### 2. Enable Drag-Drop

```csharp
using CNCScada.Scheduling;

public class InteractiveScheduler : MonoBehaviour
{
    [SerializeField] private GanttChartController ganttChart;
    [SerializeField] private JobDragDropHandler dragDropHandler;

    void Start()
    {
        dragDropHandler.ganttChart = ganttChart;
        dragDropHandler.validationEndpoint = "/api/v1/scheduling/validate";
        dragDropHandler.updateEndpoint = "/api/v1/scheduling/update";

        dragDropHandler.enableConflictDetection = true;
        dragDropHandler.snapToGrid = 15; // 15-minute increments

        dragDropHandler.OnJobRescheduled += HandleJobRescheduled;
        dragDropHandler.OnRescheduleValidationFailed += HandleValidationFailed;
    }

    void HandleJobRescheduled(JobDragDropHandler.RescheduleResult result)
    {
        Debug.Log($"Job {result.job_id} rescheduled to {result.new_start_time}");
        ganttChart.RefreshSchedule();
    }

    void HandleValidationFailed(string error)
    {
        Debug.LogWarning($"Reschedule validation failed: {error}");
    }
}
```

### 3. Run Optimization

```csharp
using CNCScada.Scheduling;

public class OptimizationController : MonoBehaviour
{
    [SerializeField] private ScheduleOptimizer optimizer;

    void Start()
    {
        optimizer.flaskServerUrl = "http://localhost:5000";
    }

    public void OptimizeSchedule()
    {
        optimizer.algorithm = "cp_sat"; // or "genetic", "simulated_annealing"
        optimizer.objective = "minimize_makespan"; // or "minimize_tardiness", "maximize_utilization"
        optimizer.timeLimit = 60; // seconds

        optimizer.respectDependencies = true;
        optimizer.respectSkills = true;
        optimizer.allowMachineChange = true;

        optimizer.OnOptimizationComplete += HandleOptimizationComplete;
        optimizer.OnOptimizationError += HandleOptimizationError;

        optimizer.StartOptimization();
    }

    void HandleOptimizationComplete(ScheduleOptimizer.OptimizationResult result)
    {
        Debug.Log($"Optimization complete: {result.improvement_percent:F1}% improvement");
        Debug.Log($"New makespan: {result.makespan_hours:F1} hours");
    }

    void HandleOptimizationError(string error)
    {
        Debug.LogError($"Optimization failed: {error}");
    }
}
```

### 4. Monitor Capacity

```csharp
using CNCScada.Scheduling;

public class CapacityMonitor : MonoBehaviour
{
    [SerializeField] private MachineCapacityView capacityView;

    void Start()
    {
        capacityView.flaskServerUrl = "http://localhost:5000";
        capacityView.updateInterval = 10f;
        capacityView.bottleneckThreshold = 0.9f;

        capacityView.OnBottleneckDetected += HandleBottleneck;
    }

    void HandleBottleneck(MachineCapacityView.MachineCapacity machine)
    {
        Debug.LogWarning($"Bottleneck detected: {machine.machine_id} at {machine.utilization:P0}");
    }
}
```

## Component Reference

### GanttChartController

Interactive Gantt chart with timeline visualization.

**Serialized Fields:**
- `flaskServerUrl` (string): Flask server base URL
- `scheduleHorizonDays` (int): Number of days to display (default: 7)
- `autoRefreshInterval` (float): Auto-refresh interval in seconds (0 = disabled)
- `pixelsPerHour` (float): Timeline scale (default: 50)

**UI References:**
- `timelineContainer` (RectTransform): Container for timeline header
- `machineRowsContainer` (RectTransform): Container for machine rows
- `jobBlockPrefab` (GameObject): Prefab for job blocks
- `machineRowPrefab` (GameObject): Prefab for machine rows

**Visual Settings:**
- `jobColorPalette` (Color[]): Colors for job types
- `completedJobColor` (Color): Color for completed jobs
- `overdueJobColor` (Color): Color for overdue jobs
- `selectedJobColor` (Color): Color for selected job

**Events:**
- `OnScheduleLoaded(int jobCount, int machineCount)`: Fired when schedule loads
- `OnJobSelected(ScheduledJob)`: Fired when job is clicked
- `OnTimelineChanged(DateTime start, DateTime end)`: Fired on timeline change

**Public Methods:**
```csharp
void LoadSchedule()
void RefreshSchedule()
void SetTimeRange(DateTime start, DateTime end)
void ZoomToFit()
void SelectJob(string jobId)
List<ScheduledJob> GetVisibleJobs()
Dictionary<string, object> GetStatistics()
```

### JobDragDropHandler

Drag-and-drop rescheduling with validation.

**Serialized Fields:**
- `ganttChart` (GanttChartController): Reference to Gantt chart
- `validationEndpoint` (string): API endpoint for validation
- `updateEndpoint` (string): API endpoint for updates
- `snapToGrid` (float): Grid snap in minutes (0 = disabled)

**Visual Feedback:**
- `ghostImagePrefab` (GameObject): Ghost image during drag
- `validDropColor` (Color): Valid drop position color
- `invalidDropColor` (Color): Invalid drop position color
- `conflictIndicatorPrefab` (GameObject): Conflict indicator prefab

**Validation:**
- `enableConflictDetection` (bool): Check for conflicts
- `enableSkillValidation` (bool): Validate machine skills
- `enableDependencyValidation` (bool): Validate dependencies
- `allowMachineChange` (bool): Allow dropping on different machine

**Events:**
- `OnJobRescheduled(RescheduleResult)`: Fired on successful reschedule
- `OnRescheduleValidationFailed(string)`: Fired on validation failure
- `OnDragStarted(ScheduledJob)`: Fired when drag starts
- `OnDragEnded()`: Fired when drag ends

**Public Methods:**
```csharp
void EnableDragDrop(bool enabled)
bool IsValidDropPosition(ScheduledJob job, DateTime newStart, string targetMachine)
void UndoLastReschedule()
```

### ScheduleOptimizer

OR-Tools optimization integration.

**Serialized Fields:**
- `flaskServerUrl` (string): Flask server base URL
- `algorithm` (string): Optimization algorithm
  - `"cp_sat"`: Google CP-SAT solver (best for small-medium problems)
  - `"genetic"`: Genetic algorithm (best for large problems)
  - `"simulated_annealing"`: Simulated annealing (fast, good approximation)

**Objective Functions:**
- `"minimize_makespan"`: Minimize total completion time
- `"minimize_tardiness"`: Minimize late jobs
- `"maximize_utilization"`: Maximize machine utilization
- `"minimize_changeovers"`: Minimize setup changes

**Constraints:**
- `respectDependencies` (bool): Honor job dependencies
- `respectSkills` (bool): Respect machine skills
- `allowMachineChange` (bool): Allow changing machine assignments
- `allowJobSplitting` (bool): Allow splitting jobs across machines
- `timeLimit` (int): Optimization time limit in seconds

**UI References:**
- `statusText` (Text): Optimization status display
- `progressBar` (Slider): Progress indicator
- `algorithmDropdown` (Dropdown): Algorithm selector
- `objectiveDropdown` (Dropdown): Objective selector

**Events:**
- `OnOptimizationStarted()`: Fired when optimization begins
- `OnOptimizationComplete(OptimizationResult)`: Fired on completion
- `OnOptimizationError(string)`: Fired on error
- `OnProgressUpdated(float)`: Fired on progress update

**Public Methods:**
```csharp
void StartOptimization()
void CancelOptimization()
OptimizationResult GetLastResult()
bool IsOptimizing()
```

### MachineCapacityView

Real-time capacity and bottleneck visualization.

**Serialized Fields:**
- `flaskServerUrl` (string): Flask server base URL
- `updateInterval` (float): Update frequency in seconds
- `utilizationThreshold` (float): High utilization threshold (default: 0.8)
- `bottleneckThreshold` (float): Bottleneck threshold (default: 0.9)

**UI References:**
- `machineCapacityContainer` (RectTransform): Container for capacity bars
- `capacityBarPrefab` (GameObject): Prefab for capacity bars
- `bottleneckIndicatorPrefab` (GameObject): Bottleneck indicator prefab

**Visual Settings:**
- `lowUtilizationColor` (Color): <50% utilization
- `mediumUtilizationColor` (Color): 50-80% utilization
- `highUtilizationColor` (Color): 80-90% utilization
- `bottleneckColor` (Color): >90% utilization

**Trending:**
- `enableTrending` (bool): Show utilization trends
- `trendingWindowHours` (int): Trending time window
- `trendIndicatorPrefab` (GameObject): Trend arrow prefab

**Events:**
- `OnCapacityUpdated(List<MachineCapacity>)`: Fired on data update
- `OnBottleneckDetected(MachineCapacity)`: Fired when bottleneck detected
- `OnBottleneckCleared(string machineId)`: Fired when bottleneck cleared

**Public Methods:**
```csharp
void RefreshCapacity()
List<MachineCapacity> GetCurrentCapacity()
List<string> GetBottlenecks()
Dictionary<string, object> GetStatistics()
```

## Configuration

### Setup Wizard

Open **CNC SCADA > Setup Wizard** and navigate to the **Scheduling** tab to configure settings.

### Performance Settings

```csharp
// For large schedules (100+ jobs)
ganttChart.enableVirtualization = true;
ganttChart.maxVisibleJobs = 50;
ganttChart.cullingMargin = 100f;

// For real-time updates
ganttChart.autoRefreshInterval = 5f;
capacityView.updateInterval = 10f;
```

### Optimization Tuning

```csharp
// Fast optimization for interactive use
optimizer.algorithm = "genetic";
optimizer.timeLimit = 10; // 10 seconds

// High-quality optimization for overnight runs
optimizer.algorithm = "cp_sat";
optimizer.timeLimit = 3600; // 1 hour
optimizer.respectDependencies = true;
optimizer.respectSkills = true;
```

## Backend API Requirements

### Schedule Endpoint
```
GET /api/v1/scheduling/schedule?horizon_days={days}

Response:
{
  "success": true,
  "schedule": {
    "jobs": [
      {
        "job_id": "JOB-001",
        "machine_id": "CNC-001",
        "start_time": "2026-01-15T08:00:00Z",
        "duration_hours": 2.5,
        "status": "scheduled",
        "priority": 1
      }
    ],
    "machines": ["CNC-001", "CNC-002"]
  }
}
```

### Validation Endpoint
```
POST /api/v1/scheduling/validate

Request:
{
  "job_id": "JOB-001",
  "machine_id": "CNC-002",
  "start_time": "2026-01-15T10:00:00Z"
}

Response:
{
  "success": true,
  "valid": true,
  "conflicts": []
}
```

### Optimization Endpoint
```
POST /api/v1/scheduling/optimize

Request:
{
  "algorithm": "cp_sat",
  "objective": "minimize_makespan",
  "time_limit_seconds": 60,
  "constraints": {
    "respect_dependencies": true,
    "respect_skills": true
  }
}

Response:
{
  "success": true,
  "result": {
    "makespan_hours": 48.5,
    "improvement_percent": 12.3,
    "schedule": { ... }
  }
}
```

### Capacity Endpoint
```
GET /api/v1/scheduling/capacity

Response:
{
  "success": true,
  "machines": [
    {
      "machine_id": "CNC-001",
      "utilization": 0.85,
      "scheduled_hours": 34.0,
      "available_hours": 40.0,
      "is_bottleneck": false
    }
  ]
}
```

## Troubleshooting

### Jobs Not Displaying

1. Check Flask server is running and schedule endpoint is accessible
2. Verify `scheduleHorizonDays` includes your jobs
3. Check Unity Console for JSON parsing errors
4. Ensure job times are in ISO 8601 format

### Drag-Drop Not Working

1. Verify `JobDragDropHandler` is attached to job block prefab
2. Check `enableDragDrop` is true
3. Ensure validation endpoint is configured
4. Review console for validation errors

### Optimization Slow

1. Reduce `timeLimit` for faster results
2. Switch to `"genetic"` algorithm for large problems
3. Disable unused constraints
4. Check backend CPU usage during optimization

### Capacity Data Incorrect

1. Verify `updateInterval` is reasonable (10-30s)
2. Check backend capacity calculation logic
3. Ensure machine IDs match between schedule and capacity endpoints

## Examples

See `Samples~/` directory for:
- Basic scheduling dashboard scene
- Multi-factory scheduling application
- Optimization comparison tool
- Capacity planning simulator

## Dependencies

- Unity 2021.3 or later
- TextMesh Pro 3.0.6+
- Unity UI (UGUI)
- Newtonsoft.Json (included)

## License

Proprietary - Part of CNC SCADA Enterprise System

## Support

For issues and feature requests, contact the CNC SCADA development team.