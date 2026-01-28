# CNC SCADA Remote Control

Low-latency remote control with jog, MDI, and program execution (<20ms latency).

## Features

- **Jog Controller**: Continuous and incremental jogging with multi-axis support
- **MDI Console**: Manual Data Input with command history and validation
- **Program Executor**: Run, pause, stop, and single-step G-code programs
- **Emergency Stop**: Quick access e-stop with confirmation dialog
- **<20ms Latency**: Optimized for real-time control via priority command queue

## Installation

### Via Unity Package Manager

1. Open **Window > Package Manager**
2. Click **+** and select **Add package from disk**
3. Navigate to `/Packages/com.cnc-scada.remote-control/package.json`

### Via Manifest

Add to `Packages/manifest.json`:
```json
{
  "dependencies": {
    "com.cnc-scada.remote-control": "file:../../Packages/com.cnc-scada.remote-control"
  }
}
```

## Quick Start

### 1. Setup Jog Controller

```csharp
using CNCScada.RemoteControl;

public class RemoteJogPanel : MonoBehaviour
{
    [SerializeField] private JogController jogController;

    void Start()
    {
        jogController.flaskServerUrl = "http://localhost:5000";
        jogController.machineId = "CNC-001";

        // Configure jog modes
        jogController.enableContinuousJog = true;
        jogController.enableIncrementalJog = true;
        jogController.defaultJogSpeed = 500f; // mm/min

        // Event handlers
        jogController.OnJogStarted += HandleJogStarted;
        jogController.OnJogStopped += HandleJogStopped;
        jogController.OnJogError += HandleJogError;
    }

    void HandleJogStarted(string axis, float speed)
    {
        Debug.Log($"Jogging {axis} axis at {speed} mm/min");
    }

    void HandleJogStopped(string axis)
    {
        Debug.Log($"Stopped jogging {axis} axis");
    }

    void HandleJogError(string error)
    {
        Debug.LogError($"Jog error: {error}");
    }
}
```

### 2. Add MDI Console

```csharp
using CNCScada.RemoteControl;

public class MDIPanel : MonoBehaviour
{
    [SerializeField] private MDIConsole mdiConsole;

    void Start()
    {
        mdiConsole.flaskServerUrl = "http://localhost:5000";
        mdiConsole.machineId = "CNC-001";

        // Configure MDI
        mdiConsole.enableCommandHistory = true;
        mdiConsole.maxHistorySize = 50;
        mdiConsole.enableAutoComplete = true;

        // Event handlers
        mdiConsole.OnCommandExecuted += HandleCommandExecuted;
        mdiConsole.OnCommandValidationFailed += HandleValidationFailed;
    }

    void HandleCommandExecuted(string command, string response)
    {
        Debug.Log($"Executed: {command} -> {response}");
    }

    void HandleValidationFailed(string command, string error)
    {
        Debug.LogWarning($"Invalid command '{command}': {error}");
    }

    // Example: Execute command from code
    public void ExecuteCustomCommand()
    {
        mdiConsole.ExecuteCommand("G0 X100 Y50");
    }
}
```

### 3. Setup Program Executor

```csharp
using CNCScada.RemoteControl;

public class ProgramPanel : MonoBehaviour
{
    [SerializeField] private ProgramExecutor executor;

    void Start()
    {
        executor.flaskServerUrl = "http://localhost:5000";
        executor.machineId = "CNC-001";

        // Event handlers
        executor.OnProgramStarted += HandleProgramStarted;
        executor.OnProgramPaused += HandleProgramPaused;
        executor.OnProgramCompleted += HandleProgramCompleted;
        executor.OnProgramError += HandleProgramError;
    }

    void HandleProgramStarted(string programId)
    {
        Debug.Log($"Program {programId} started");
    }

    void HandleProgramPaused()
    {
        Debug.Log("Program paused");
    }

    void HandleProgramCompleted()
    {
        Debug.Log("Program completed successfully");
    }

    void HandleProgramError(string error)
    {
        Debug.LogError($"Program error: {error}");
    }

    // Example: Run program from code
    public void RunProgram(string programId)
    {
        executor.LoadProgram(programId);
        executor.StartExecution();
    }
}
```

### 4. Add Emergency Stop

```csharp
using CNCScada.RemoteControl;

public class SafetyPanel : MonoBehaviour
{
    [SerializeField] private EmergencyStopButton eStopButton;

    void Start()
    {
        eStopButton.flaskServerUrl = "http://localhost:5000";
        eStopButton.machineId = "CNC-001";
        eStopButton.requireConfirmation = true;

        eStopButton.OnEmergencyStopTriggered += HandleEStop;
        eStopButton.OnEmergencyStopReset += HandleEStopReset;
    }

    void HandleEStop()
    {
        Debug.LogWarning("EMERGENCY STOP ACTIVATED!");
    }

    void HandleEStopReset()
    {
        Debug.Log("Emergency stop reset");
    }
}
```

## Component Reference

### JogController

Multi-axis jogging with continuous and incremental modes.

**Serialized Fields:**
- `flaskServerUrl` (string): Flask server base URL
- `machineId` (string): Machine identifier
- `commandEndpoint` (string): Command API endpoint (default: "/api/v1/control/jog")

**UI References:**
- `xPlusButton`, `xMinusButton`: X-axis jog buttons
- `yPlusButton`, `yMinusButton`: Y-axis jog buttons
- `zPlusButton`, `zMinusButton`: Z-axis jog buttons
- `aPlusButton`, `aMinusButton`: A-axis jog buttons (rotary)
- `bPlusButton`, `bMinusButton`: B-axis jog buttons (rotary)
- `cPlusButton`, `cMinusButton`: C-axis jog buttons (rotary)
- `jogSpeedSlider` (Slider): Jog speed control
- `jogSpeedText` (Text): Speed display
- `jogModeDropdown` (Dropdown): Jog mode selector

**Jog Modes:**
- **Continuous**: Hold button to jog, release to stop
- **Incremental**: Click for fixed distance move
- **Wheel**: Jog distance based on input (gamepad/MPG)

**Settings:**
- `enableContinuousJog` (bool): Enable continuous mode
- `enableIncrementalJog` (bool): Enable incremental mode
- `enableWheelJog` (bool): Enable wheel/MPG mode
- `defaultJogSpeed` (float): Default speed in mm/min (default: 500)
- `minJogSpeed`, `maxJogSpeed` (float): Speed range
- `incrementalDistances` (float[]): Incremental step sizes (0.01, 0.1, 1.0, 10.0)

**Safety:**
- `enableSoftLimits` (bool): Check software limits before jogging
- `enableCollisionDetection` (bool): Collision avoidance
- `requirePositiveConfirmation` (bool): Require button hold time

**Events:**
- `OnJogStarted(string axis, float speed)`: Jog initiated
- `OnJogStopped(string axis)`: Jog stopped
- `OnJogError(string error)`: Jog command failed

**Public Methods:**
```csharp
void JogAxis(string axis, float direction, float speed)
void StopJog(string axis)
void StopAllJogging()
void SetJogSpeed(float speed)
bool IsJogging(string axis)
Dictionary<string, object> GetStatistics()
```

### MDIConsole

Manual Data Input with command history.

**Serialized Fields:**
- `flaskServerUrl` (string): Flask server base URL
- `machineId` (string): Machine identifier
- `commandEndpoint` (string): Command API endpoint (default: "/api/v1/control/mdi")

**UI References:**
- `commandInputField` (InputField): Command input
- `executeButton` (Button): Execute command button
- `historyScrollView` (ScrollRect): Command history display
- `historyItemPrefab` (GameObject): History item prefab
- `statusText` (Text): Status/error display

**Command History:**
- `enableCommandHistory` (bool): Store command history
- `maxHistorySize` (int): Maximum history entries (default: 50)
- `persistHistory` (bool): Save history between sessions
- `historyFilePath` (string): History save location

**Auto-Complete:**
- `enableAutoComplete` (bool): G-code auto-completion
- `autoCompletePrefab` (GameObject): Auto-complete suggestion UI
- `commonCommands` (string[]): Common G-code commands for suggestions

**Validation:**
- `enableClientValidation` (bool): Validate before sending
- `enableServerValidation` (bool): Server-side validation
- `allowDangerousCommands` (bool): Allow M-codes, tool changes, etc.

**Events:**
- `OnCommandExecuted(string command, string response)`: Command succeeded
- `OnCommandValidationFailed(string command, string error)`: Validation failed
- `OnCommandError(string command, string error)`: Execution failed

**Public Methods:**
```csharp
void ExecuteCommand(string command)
void ClearHistory()
List<string> GetCommandHistory()
void RecallCommand(int historyIndex)
Dictionary<string, object> GetStatistics()
```

### ProgramExecutor

G-code program execution with state machine.

**Serialized Fields:**
- `flaskServerUrl` (string): Flask server base URL
- `machineId` (string): Machine identifier
- `programEndpoint` (string): Program API endpoint (default: "/api/v1/control/program")

**UI References:**
- `programSelectDropdown` (Dropdown): Program selector
- `loadButton` (Button): Load program button
- `startButton` (Button): Start execution button
- `pauseButton` (Button): Pause button
- `stopButton` (Button): Stop button
- `singleStepButton` (Button): Single step button
- `progressBar` (Slider): Execution progress
- `currentLineText` (Text): Current line display
- `statusText` (Text): Execution status

**Execution Modes:**
- `normalExecution`: Run program continuously
- `singleStep`: Execute one line at a time
- `dryRun`: Simulate without machine movement

**Settings:**
- `enableSingleStep` (bool): Enable single-step mode
- `enableDryRun` (bool): Enable simulation mode
- `autoLoadOnSelect` (bool): Auto-load when program selected
- `confirmBeforeStart` (bool): Require start confirmation

**Program Control:**
- `allowPause` (bool): Enable pause button
- `allowStop` (bool): Enable stop button
- `allowSkip` (bool): Enable skip line functionality
- `pauseOnError` (bool): Auto-pause on execution error

**State Machine:**
- `IDLE`: No program loaded
- `LOADED`: Program loaded, ready to start
- `RUNNING`: Executing program
- `PAUSED`: Execution paused
- `COMPLETED`: Program finished successfully
- `ERROR`: Execution error occurred
- `STOPPED`: User-initiated stop

**Events:**
- `OnProgramLoaded(string programId, int lineCount)`: Program loaded
- `OnProgramStarted(string programId)`: Execution started
- `OnProgramPaused()`: Execution paused
- `OnProgramResumed()`: Execution resumed
- `OnProgramCompleted()`: Program finished
- `OnProgramStopped()`: User stopped execution
- `OnProgramError(string error)`: Execution error
- `OnLineExecuted(int lineNumber, string line)`: Line executed

**Public Methods:**
```csharp
void LoadProgram(string programId)
void StartExecution()
void PauseExecution()
void ResumeExecution()
void StopExecution()
void ExecuteSingleStep()
void SetDryRunMode(bool enabled)
string GetCurrentState()
float GetProgress()
Dictionary<string, object> GetStatistics()
```

### EmergencyStopButton

Quick-access emergency stop with safety features.

**Serialized Fields:**
- `flaskServerUrl` (string): Flask server base URL
- `machineId` (string): Machine identifier
- `eStopEndpoint` (string): E-stop endpoint (default: "/api/v1/control/estop")

**UI References:**
- `eStopButton` (Button): Main e-stop button
- `resetButton` (Button): E-stop reset button
- `statusIndicator` (Image): Visual status indicator
- `confirmationDialog` (GameObject): Confirmation dialog
- `statusText` (Text): Status message

**Visual Settings:**
- `normalColor` (Color): Normal state color (green)
- `activeColor` (Color): E-stop active color (red)
- `buttonScale` (float): Button size multiplier
- `pulseEffect` (bool): Pulsing animation when active

**Safety Settings:**
- `requireConfirmation` (bool): Show confirmation dialog
- `requireHoldTime` (float): Button hold time in seconds (default: 0.5)
- `requireDoubleClick` (bool): Require double-click
- `doubleClickWindow` (float): Double-click time window (default: 0.5s)

**Reset Settings:**
- `requireResetConfirmation` (bool): Confirm reset
- `autoResetTimeout` (float): Auto-reset after timeout (0 = disabled)
- `logEStopEvents` (bool): Log all e-stop activations

**Events:**
- `OnEmergencyStopTriggered()`: E-stop activated
- `OnEmergencyStopReset()`: E-stop reset
- `OnConfirmationRequired()`: Confirmation dialog shown

**Public Methods:**
```csharp
void TriggerEmergencyStop()
void ResetEmergencyStop()
bool IsEmergencyStopActive()
Dictionary<string, object> GetStatistics()
```

## Configuration

### Setup Wizard

Open **CNC SCADA > Setup Wizard** and navigate to the **Remote Control** tab to configure settings.

### Latency Optimization

```csharp
// Priority command queue (backend configuration required)
jogController.usePriorityQueue = true;
jogController.commandPriority = "high";

// Regional edge nodes (route to nearest)
jogController.flaskServerUrl = "http://edge-us-east.example.com:5000";

// Binary protocol (if supported by backend)
jogController.useBinaryProtocol = true;
```

### Safety Configuration

```csharp
// Conservative safety settings
jogController.enableSoftLimits = true;
jogController.requirePositiveConfirmation = true;
mdiConsole.allowDangerousCommands = false;
executor.confirmBeforeStart = true;
eStopButton.requireConfirmation = true;

// Relaxed settings for experienced operators
jogController.requirePositiveConfirmation = false;
mdiConsole.allowDangerousCommands = true;
executor.confirmBeforeStart = false;
```

## Backend API Requirements

### Jog Command Endpoint
```
POST /api/v1/control/jog

Request:
{
  "machine_id": "CNC-001",
  "axis": "X",
  "direction": 1,
  "speed": 500.0
}

Response:
{
  "success": true,
  "message": "Jogging X axis at 500 mm/min"
}
```

### MDI Command Endpoint
```
POST /api/v1/control/mdi

Request:
{
  "machine_id": "CNC-001",
  "command": "G0 X100 Y50"
}

Response:
{
  "success": true,
  "response": "ok",
  "execution_time_ms": 15
}
```

### Program Control Endpoint
```
POST /api/v1/control/program

Request:
{
  "machine_id": "CNC-001",
  "action": "start",
  "program_id": "PART-001"
}

Response:
{
  "success": true,
  "state": "running",
  "current_line": 1,
  "total_lines": 245
}
```

### Emergency Stop Endpoint
```
POST /api/v1/control/estop

Request:
{
  "machine_id": "CNC-001",
  "action": "trigger"
}

Response:
{
  "success": true,
  "message": "Emergency stop activated"
}
```

## Troubleshooting

### High Latency

1. Check network latency with ping: `ping your-server.com`
2. Use regional edge node instead of cloud
3. Enable binary protocol if supported
4. Check backend command queue performance

### Jog Not Responding

1. Verify machine is not in e-stop state
2. Check machine mode allows jogging
3. Test jog endpoint manually with curl
4. Review Unity Console for command errors

### MDI Commands Failing

1. Check command syntax is valid G-code
2. Verify machine mode allows MDI
3. Review backend validation rules
4. Check for conflicting operations

### Program Won't Start

1. Verify program is loaded
2. Check machine state allows execution
3. Ensure no active alarms
4. Review program validation results

## Security Considerations

### Authentication

Remote control operations require elevated permissions. Configure user roles appropriately:

```csharp
// Check user permissions before allowing control
if (!UserHasPermission("CONTROL_MACHINE"))
{
    Debug.LogError("User lacks permission for remote control");
    return;
}
```

### Command Authorization

Backend should implement per-command authorization:

```
POST /api/v1/control/mdi
Headers:
  Authorization: Bearer <token>
  X-Command-Type: MDI
  X-Machine-Id: CNC-001
```

### Rate Limiting

Implement rate limiting to prevent abuse:

```csharp
jogController.maxCommandsPerSecond = 10;
mdiConsole.maxCommandsPerMinute = 30;
```

## Examples

See `Samples~/` directory for:
- Full remote control panel scene
- Mobile jog interface
- VR remote control demo
- Multi-machine control dashboard

## Dependencies

- Unity 2021.3 or later
- TextMesh Pro 3.0.6+
- Unity UI (UGUI)
- Newtonsoft.Json (included)

## License

Proprietary - Part of CNC SCADA Enterprise System

## Support

For issues and feature requests, contact the CNC SCADA development team.