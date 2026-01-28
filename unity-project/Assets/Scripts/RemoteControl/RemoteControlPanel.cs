using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using CNC_SCADA.DigitalTwin.Audit;

namespace CNC_SCADA.DigitalTwin.RemoteControl
{
    /// <summary>
    /// Remote CNC control panel for digital twin interface
    /// Provides jog, MDI, program control, and machine override functions
    /// </summary>
    public class RemoteControlPanel : MonoBehaviour
    {
        public static RemoteControlPanel Instance { get; private set; }

        [Header("Target Machine")]
        [SerializeField] private string targetMachineId = "CNC-001";
        [SerializeField] private bool isConnected = false;

        [Header("Jog Configuration")]
        [SerializeField] private float[] jogIncrements = { 0.001f, 0.01f, 0.1f, 1.0f, 10.0f };
        [SerializeField] private int currentIncrementIndex = 2;
        [SerializeField] private float continuousJogRate = 100f; // mm/min
        [SerializeField] private float rapidJogRate = 1000f; // mm/min

        [Header("Override Limits")]
        [SerializeField] private float minFeedOverride = 0f;
        [SerializeField] private float maxFeedOverride = 200f;
        [SerializeField] private float minSpindleOverride = 50f;
        [SerializeField] private float maxSpindleOverride = 120f;
        [SerializeField] private float minRapidOverride = 25f;
        [SerializeField] private float maxRapidOverride = 100f;

        [Header("Safety")]
        [SerializeField] private bool requireConfirmationForRun = true;
        [SerializeField] private bool requireConfirmationForReset = true;
        [SerializeField] private float eStopCooldownSeconds = 2f;

        // Events
        public event Action<string, MachineCommand> OnCommandSent;
        public event Action<string, bool> OnConnectionChanged;
        public event Action<MachineState> OnStateUpdated;
        public event Action OnEmergencyStop;
        public event Action<string> OnError;

        // Current state
        private MachineState currentState = new MachineState();
        private ControlMode currentMode = ControlMode.Manual;
        private JogMode currentJogMode = JogMode.Incremental;
        private bool isJogging = false;
        private Axis activeJogAxis = Axis.None;
        private float lastEStopTime = 0f;
        private Queue<MachineCommand> commandQueue = new Queue<MachineCommand>();
        private string currentOperatorId = "OP001";

        // Properties
        public MachineState CurrentState => currentState;
        public ControlMode CurrentMode => currentMode;
        public bool IsConnected => isConnected;
        public float CurrentJogIncrement => jogIncrements[currentIncrementIndex];
        public float FeedOverride => currentState.FeedOverride;
        public float SpindleOverride => currentState.SpindleOverride;

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
                InitializeControlPanel();
            }
            else
            {
                Destroy(gameObject);
            }
        }

        private void Update()
        {
            // Handle keyboard shortcuts for jog
            HandleJogInput();

            // Process command queue
            ProcessCommandQueue();
        }

        private void InitializeControlPanel()
        {
            currentState = new MachineState
            {
                MachineId = targetMachineId,
                Mode = MachineMode.Idle,
                Position = new MachinePosition(),
                FeedOverride = 100f,
                SpindleOverride = 100f,
                RapidOverride = 100f,
                IsSpindleOn = false,
                IsCoolantOn = false,
                IsHomed = false,
                CurrentTool = 0,
                ProgramName = "",
                ProgramLine = 0
            };

            Debug.Log($"[RemoteControl] Initialized for machine: {targetMachineId}");
        }

        #region Connection

        public void Connect(string machineId)
        {
            targetMachineId = machineId;
            currentState.MachineId = machineId;

            // Simulate connection (in real system, this would connect via WebSocket/ROS2)
            StartCoroutine(SimulateConnection());
        }

        private IEnumerator SimulateConnection()
        {
            yield return new WaitForSeconds(0.5f);

            isConnected = true;
            OnConnectionChanged?.Invoke(targetMachineId, true);

            LogAuditEvent("MACHINE_CONNECTED", $"Connected to machine {targetMachineId}");
            Debug.Log($"[RemoteControl] Connected to {targetMachineId}");
        }

        public void Disconnect()
        {
            if (isJogging)
            {
                StopJog();
            }

            isConnected = false;
            OnConnectionChanged?.Invoke(targetMachineId, false);

            LogAuditEvent("MACHINE_DISCONNECTED", $"Disconnected from machine {targetMachineId}");
            Debug.Log($"[RemoteControl] Disconnected from {targetMachineId}");
        }

        #endregion

        #region Mode Control

        public void SetMode(ControlMode mode)
        {
            if (!ValidateConnection()) return;

            var previousMode = currentMode;
            currentMode = mode;

            var command = new MachineCommand
            {
                Type = CommandType.ModeChange,
                Parameter = mode.ToString(),
                Timestamp = DateTime.Now
            };

            SendCommand(command);

            LogAuditEvent("MODE_CHANGED", $"Mode changed from {previousMode} to {mode}");
            Debug.Log($"[RemoteControl] Mode changed to: {mode}");
        }

        public void SetMachineMode(MachineMode mode)
        {
            if (!ValidateConnection()) return;

            currentState.Mode = mode;

            var command = new MachineCommand
            {
                Type = CommandType.ModeChange,
                Parameter = $"MACHINE_{mode}",
                Timestamp = DateTime.Now
            };

            SendCommand(command);
        }

        #endregion

        #region Jog Control

        public void SetJogMode(JogMode mode)
        {
            currentJogMode = mode;
            Debug.Log($"[RemoteControl] Jog mode: {mode}");
        }

        public void SetJogIncrement(int index)
        {
            if (index >= 0 && index < jogIncrements.Length)
            {
                currentIncrementIndex = index;
                Debug.Log($"[RemoteControl] Jog increment: {jogIncrements[index]} mm");
            }
        }

        public void IncrementJogStep()
        {
            if (currentIncrementIndex < jogIncrements.Length - 1)
            {
                currentIncrementIndex++;
                Debug.Log($"[RemoteControl] Jog increment: {CurrentJogIncrement} mm");
            }
        }

        public void DecrementJogStep()
        {
            if (currentIncrementIndex > 0)
            {
                currentIncrementIndex--;
                Debug.Log($"[RemoteControl] Jog increment: {CurrentJogIncrement} mm");
            }
        }

        public void StartJog(Axis axis, JogDirection direction)
        {
            if (!ValidateConnection() || !ValidateJogSafe()) return;

            isJogging = true;
            activeJogAxis = axis;

            float distance = currentJogMode == JogMode.Incremental ? CurrentJogIncrement : 0f;
            float feedRate = currentJogMode == JogMode.Rapid ? rapidJogRate : continuousJogRate;

            if (direction == JogDirection.Negative)
            {
                distance = -distance;
                feedRate = -feedRate;
            }

            var command = new MachineCommand
            {
                Type = CommandType.Jog,
                Axis = axis,
                Value = currentJogMode == JogMode.Incremental ? distance : feedRate,
                Parameter = currentJogMode.ToString(),
                Timestamp = DateTime.Now
            };

            SendCommand(command);

            if (currentJogMode == JogMode.Continuous || currentJogMode == JogMode.Rapid)
            {
                StartCoroutine(ContinuousJogCoroutine(axis, direction, feedRate));
            }
            else
            {
                // Incremental jog - update simulated position
                UpdateSimulatedPosition(axis, distance);
                isJogging = false;
            }

            Debug.Log($"[RemoteControl] Jog {axis} {direction} at {(currentJogMode == JogMode.Incremental ? $"{distance} mm" : $"{feedRate} mm/min")}");
        }

        public void StopJog()
        {
            if (!isJogging) return;

            isJogging = false;
            activeJogAxis = Axis.None;

            var command = new MachineCommand
            {
                Type = CommandType.JogStop,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            Debug.Log("[RemoteControl] Jog stopped");
        }

        private IEnumerator ContinuousJogCoroutine(Axis axis, JogDirection direction, float rate)
        {
            float increment = rate / 60f * Time.fixedDeltaTime; // Convert mm/min to mm/frame
            if (direction == JogDirection.Negative) increment = -increment;

            while (isJogging && activeJogAxis == axis)
            {
                UpdateSimulatedPosition(axis, increment);
                yield return new WaitForFixedUpdate();
            }
        }

        private void UpdateSimulatedPosition(Axis axis, float delta)
        {
            switch (axis)
            {
                case Axis.X: currentState.Position.X += delta; break;
                case Axis.Y: currentState.Position.Y += delta; break;
                case Axis.Z: currentState.Position.Z += delta; break;
                case Axis.A: currentState.Position.A += delta; break;
                case Axis.B: currentState.Position.B += delta; break;
                case Axis.C: currentState.Position.C += delta; break;
            }

            OnStateUpdated?.Invoke(currentState);
        }

        private void HandleJogInput()
        {
            if (!isConnected || currentMode != ControlMode.Manual) return;

#if ENABLE_LEGACY_INPUT_MANAGER
            // Keyboard jog controls
            if (Input.GetKeyDown(KeyCode.X) && Input.GetKey(KeyCode.LeftShift))
                StartJog(Axis.X, JogDirection.Negative);
            else if (Input.GetKeyDown(KeyCode.X))
                StartJog(Axis.X, JogDirection.Positive);

            if (Input.GetKeyDown(KeyCode.Y) && Input.GetKey(KeyCode.LeftShift))
                StartJog(Axis.Y, JogDirection.Negative);
            else if (Input.GetKeyDown(KeyCode.Y))
                StartJog(Axis.Y, JogDirection.Positive);

            if (Input.GetKeyDown(KeyCode.Z) && Input.GetKey(KeyCode.LeftShift))
                StartJog(Axis.Z, JogDirection.Negative);
            else if (Input.GetKeyDown(KeyCode.Z))
                StartJog(Axis.Z, JogDirection.Positive);

            // Stop on key up (for continuous mode)
            if (Input.GetKeyUp(KeyCode.X) || Input.GetKeyUp(KeyCode.Y) || Input.GetKeyUp(KeyCode.Z))
            {
                if (currentJogMode == JogMode.Continuous || currentJogMode == JogMode.Rapid)
                {
                    StopJog();
                }
            }

            // Increment/decrement jog step
            if (Input.GetKeyDown(KeyCode.PageUp)) IncrementJogStep();
            if (Input.GetKeyDown(KeyCode.PageDown)) DecrementJogStep();
#endif
        }

        private bool ValidateJogSafe()
        {
            if (currentState.Mode == MachineMode.Running)
            {
                OnError?.Invoke("Cannot jog while program is running");
                return false;
            }

            if (currentMode != ControlMode.Manual)
            {
                OnError?.Invoke("Must be in Manual mode to jog");
                return false;
            }

            return true;
        }

        #endregion

        #region Override Controls

        public void SetFeedOverride(float percent)
        {
            if (!ValidateConnection()) return;

            percent = Mathf.Clamp(percent, minFeedOverride, maxFeedOverride);
            currentState.FeedOverride = percent;

            var command = new MachineCommand
            {
                Type = CommandType.Override,
                Parameter = "FEED",
                Value = percent,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            OnStateUpdated?.Invoke(currentState);

            Debug.Log($"[RemoteControl] Feed override: {percent}%");
        }

        public void SetSpindleOverride(float percent)
        {
            if (!ValidateConnection()) return;

            percent = Mathf.Clamp(percent, minSpindleOverride, maxSpindleOverride);
            currentState.SpindleOverride = percent;

            var command = new MachineCommand
            {
                Type = CommandType.Override,
                Parameter = "SPINDLE",
                Value = percent,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            OnStateUpdated?.Invoke(currentState);

            Debug.Log($"[RemoteControl] Spindle override: {percent}%");
        }

        public void SetRapidOverride(float percent)
        {
            if (!ValidateConnection()) return;

            percent = Mathf.Clamp(percent, minRapidOverride, maxRapidOverride);
            currentState.RapidOverride = percent;

            var command = new MachineCommand
            {
                Type = CommandType.Override,
                Parameter = "RAPID",
                Value = percent,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            OnStateUpdated?.Invoke(currentState);

            Debug.Log($"[RemoteControl] Rapid override: {percent}%");
        }

        public void AdjustFeedOverride(float delta)
        {
            SetFeedOverride(currentState.FeedOverride + delta);
        }

        public void AdjustSpindleOverride(float delta)
        {
            SetSpindleOverride(currentState.SpindleOverride + delta);
        }

        #endregion

        #region Spindle Control

        public void SpindleOn(SpindleDirection direction, float rpm)
        {
            if (!ValidateConnection()) return;

            currentState.IsSpindleOn = true;
            currentState.SpindleRPM = rpm;
            currentState.SpindleDirection = direction;

            var command = new MachineCommand
            {
                Type = CommandType.Spindle,
                Parameter = direction == SpindleDirection.CW ? "M03" : "M04",
                Value = rpm,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            LogAuditEvent("SPINDLE_ON", $"Spindle ON {direction} at {rpm} RPM");

            Debug.Log($"[RemoteControl] Spindle ON {direction} at {rpm} RPM");
        }

        public void SpindleOff()
        {
            if (!ValidateConnection()) return;

            currentState.IsSpindleOn = false;
            currentState.SpindleRPM = 0;

            var command = new MachineCommand
            {
                Type = CommandType.Spindle,
                Parameter = "M05",
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            LogAuditEvent("SPINDLE_OFF", "Spindle OFF");

            Debug.Log("[RemoteControl] Spindle OFF");
        }

        #endregion

        #region Coolant Control

        public void CoolantOn(CoolantType type = CoolantType.Flood)
        {
            if (!ValidateConnection()) return;

            currentState.IsCoolantOn = true;
            currentState.CoolantType = type;

            string mCode = type == CoolantType.Mist ? "M07" : "M08";

            var command = new MachineCommand
            {
                Type = CommandType.Coolant,
                Parameter = mCode,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            Debug.Log($"[RemoteControl] Coolant ON ({type})");
        }

        public void CoolantOff()
        {
            if (!ValidateConnection()) return;

            currentState.IsCoolantOn = false;

            var command = new MachineCommand
            {
                Type = CommandType.Coolant,
                Parameter = "M09",
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            Debug.Log("[RemoteControl] Coolant OFF");
        }

        #endregion

        #region Program Control

        public void LoadProgram(string programName)
        {
            if (!ValidateConnection()) return;

            currentState.ProgramName = programName;
            currentState.ProgramLine = 0;

            var command = new MachineCommand
            {
                Type = CommandType.ProgramLoad,
                Parameter = programName,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            LogAuditEvent("PROGRAM_LOADED", $"Program loaded: {programName}");

            Debug.Log($"[RemoteControl] Program loaded: {programName}");
        }

        public void CycleStart()
        {
            if (!ValidateConnection()) return;

            if (string.IsNullOrEmpty(currentState.ProgramName))
            {
                OnError?.Invoke("No program loaded");
                return;
            }

            if (requireConfirmationForRun)
            {
                // In a real UI, this would show a confirmation dialog
                Debug.Log("[RemoteControl] Cycle start requires confirmation");
            }

            currentState.Mode = MachineMode.Running;

            var command = new MachineCommand
            {
                Type = CommandType.CycleStart,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            LogAuditEvent("CYCLE_START", $"Program started: {currentState.ProgramName}");

            Debug.Log("[RemoteControl] Cycle Start");
        }

        public void FeedHold()
        {
            if (!ValidateConnection()) return;

            currentState.Mode = MachineMode.Paused;

            var command = new MachineCommand
            {
                Type = CommandType.FeedHold,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            LogAuditEvent("FEED_HOLD", "Program paused");

            Debug.Log("[RemoteControl] Feed Hold");
        }

        public void ProgramStop()
        {
            if (!ValidateConnection()) return;

            currentState.Mode = MachineMode.Idle;
            currentState.ProgramLine = 0;

            var command = new MachineCommand
            {
                Type = CommandType.ProgramStop,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            LogAuditEvent("PROGRAM_STOP", "Program stopped");

            Debug.Log("[RemoteControl] Program Stop");
        }

        public void SingleBlock(bool enabled)
        {
            if (!ValidateConnection()) return;

            currentState.IsSingleBlock = enabled;

            var command = new MachineCommand
            {
                Type = CommandType.SingleBlock,
                Value = enabled ? 1 : 0,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            Debug.Log($"[RemoteControl] Single Block: {(enabled ? "ON" : "OFF")}");
        }

        public void OptionalStop(bool enabled)
        {
            if (!ValidateConnection()) return;

            currentState.IsOptionalStop = enabled;

            var command = new MachineCommand
            {
                Type = CommandType.OptionalStop,
                Value = enabled ? 1 : 0,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            Debug.Log($"[RemoteControl] Optional Stop: {(enabled ? "ON" : "OFF")}");
        }

        #endregion

        #region MDI (Manual Data Input)

        public void ExecuteMDI(string gcode)
        {
            if (!ValidateConnection()) return;

            if (currentMode != ControlMode.MDI)
            {
                OnError?.Invoke("Must be in MDI mode to execute G-code");
                return;
            }

            if (string.IsNullOrWhiteSpace(gcode))
            {
                OnError?.Invoke("Empty G-code command");
                return;
            }

            var command = new MachineCommand
            {
                Type = CommandType.MDI,
                Parameter = gcode.Trim().ToUpper(),
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            LogAuditEvent("MDI_EXECUTED", $"MDI: {gcode}");

            Debug.Log($"[RemoteControl] MDI: {gcode}");
        }

        #endregion

        #region Homing & Reference

        public void HomeAll()
        {
            if (!ValidateConnection()) return;

            currentState.Mode = MachineMode.Homing;

            var command = new MachineCommand
            {
                Type = CommandType.Home,
                Parameter = "ALL",
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            StartCoroutine(SimulateHoming());

            LogAuditEvent("HOME_ALL", "Homing all axes");
            Debug.Log("[RemoteControl] Homing all axes");
        }

        public void HomeAxis(Axis axis)
        {
            if (!ValidateConnection()) return;

            var command = new MachineCommand
            {
                Type = CommandType.Home,
                Axis = axis,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            LogAuditEvent("HOME_AXIS", $"Homing axis {axis}");

            Debug.Log($"[RemoteControl] Homing axis {axis}");
        }

        private IEnumerator SimulateHoming()
        {
            yield return new WaitForSeconds(3f);

            currentState.Position = new MachinePosition();
            currentState.IsHomed = true;
            currentState.Mode = MachineMode.Idle;

            OnStateUpdated?.Invoke(currentState);
            Debug.Log("[RemoteControl] Homing complete");
        }

        public void SetWorkOffset(WorkOffset offset)
        {
            if (!ValidateConnection()) return;

            currentState.ActiveWorkOffset = offset;

            var command = new MachineCommand
            {
                Type = CommandType.WorkOffset,
                Parameter = offset.ToString(),
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            Debug.Log($"[RemoteControl] Work offset: {offset}");
        }

        #endregion

        #region Tool Control

        public void ToolChange(int toolNumber)
        {
            if (!ValidateConnection()) return;

            currentState.CurrentTool = toolNumber;

            var command = new MachineCommand
            {
                Type = CommandType.ToolChange,
                Value = toolNumber,
                Parameter = $"T{toolNumber} M06",
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            LogAuditEvent("TOOL_CHANGE", $"Tool change to T{toolNumber}");

            Debug.Log($"[RemoteControl] Tool change: T{toolNumber}");
        }

        #endregion

        #region Emergency Stop

        public void EmergencyStop()
        {
            // E-Stop always works, even if disconnected
            if (Time.time - lastEStopTime < eStopCooldownSeconds)
            {
                Debug.LogWarning("[RemoteControl] E-Stop cooldown active");
                return;
            }

            lastEStopTime = Time.time;

            // Stop all motion immediately
            isJogging = false;
            currentState.Mode = MachineMode.EStop;
            currentState.IsSpindleOn = false;
            currentState.IsCoolantOn = false;

            var command = new MachineCommand
            {
                Type = CommandType.EmergencyStop,
                Timestamp = DateTime.Now
            };

            // Send immediately, bypass queue
            OnCommandSent?.Invoke(targetMachineId, command);
            OnEmergencyStop?.Invoke();
            OnStateUpdated?.Invoke(currentState);

            LogAuditEvent("EMERGENCY_STOP", "Emergency stop activated", AuditSeverity.Critical);
            Debug.LogWarning("[RemoteControl] EMERGENCY STOP");
        }

        public void ResetEStop()
        {
            if (!ValidateConnection()) return;

            if (requireConfirmationForReset)
            {
                // In real UI, show confirmation
                Debug.Log("[RemoteControl] E-Stop reset requires confirmation");
            }

            currentState.Mode = MachineMode.Idle;

            var command = new MachineCommand
            {
                Type = CommandType.Reset,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            OnStateUpdated?.Invoke(currentState);

            LogAuditEvent("ESTOP_RESET", "Emergency stop reset");
            Debug.Log("[RemoteControl] E-Stop Reset");
        }

        public void Reset()
        {
            if (!ValidateConnection()) return;

            currentState.Mode = MachineMode.Idle;
            currentState.Alarms.Clear();

            var command = new MachineCommand
            {
                Type = CommandType.Reset,
                Timestamp = DateTime.Now
            };

            SendCommand(command);
            OnStateUpdated?.Invoke(currentState);

            LogAuditEvent("MACHINE_RESET", "Machine reset");
            Debug.Log("[RemoteControl] Machine Reset");
        }

        #endregion

        #region Command Processing

        private void SendCommand(MachineCommand command)
        {
            command.OperatorId = currentOperatorId;
            command.MachineId = targetMachineId;

            commandQueue.Enqueue(command);
        }

        private void ProcessCommandQueue()
        {
            while (commandQueue.Count > 0)
            {
                var command = commandQueue.Dequeue();
                OnCommandSent?.Invoke(targetMachineId, command);

                // In a real system, this would send via WebSocket/ROS2
                // For simulation, we process locally
                ProcessCommandLocally(command);
            }
        }

        private void ProcessCommandLocally(MachineCommand command)
        {
            // Simulate command execution
            Debug.Log($"[RemoteControl] Processing command: {command.Type} - {command.Parameter}");
        }

        private bool ValidateConnection()
        {
            if (!isConnected)
            {
                OnError?.Invoke("Not connected to machine");
                Debug.LogWarning("[RemoteControl] Not connected");
                return false;
            }

            if (currentState.Mode == MachineMode.EStop)
            {
                OnError?.Invoke("Machine is in E-Stop state");
                return false;
            }

            return true;
        }

        #endregion

        #region State Updates

        public void UpdateState(MachineState newState)
        {
            currentState = newState;
            OnStateUpdated?.Invoke(currentState);
        }

        public void SetOperator(string operatorId)
        {
            currentOperatorId = operatorId;
            LogAuditEvent("OPERATOR_CHANGED", $"Operator changed to {operatorId}");
        }

        #endregion

        #region Audit Logging

        private void LogAuditEvent(string action, string description, AuditSeverity severity = AuditSeverity.Info)
        {
            if (AuditTrailSystem.Instance != null)
            {
                AuditTrailSystem.Instance.LogMachineControl(
                    currentOperatorId,
                    targetMachineId,
                    action,
                    description,
                    new Dictionary<string, string>
                    {
                        { "mode", currentMode.ToString() },
                        { "machine_mode", currentState.Mode.ToString() }
                    });
            }
        }

        #endregion

        #region Status Display

        public ControlPanelStatus GetStatus()
        {
            return new ControlPanelStatus
            {
                MachineId = targetMachineId,
                IsConnected = isConnected,
                ControlMode = currentMode,
                MachineMode = currentState.Mode,
                Position = currentState.Position,
                FeedOverride = currentState.FeedOverride,
                SpindleOverride = currentState.SpindleOverride,
                RapidOverride = currentState.RapidOverride,
                SpindleRPM = currentState.SpindleRPM,
                IsSpindleOn = currentState.IsSpindleOn,
                IsCoolantOn = currentState.IsCoolantOn,
                CurrentTool = currentState.CurrentTool,
                ProgramName = currentState.ProgramName,
                ProgramLine = currentState.ProgramLine,
                IsHomed = currentState.IsHomed,
                JogMode = currentJogMode,
                JogIncrement = CurrentJogIncrement,
                ActiveAlarms = currentState.Alarms.Count,
                Timestamp = DateTime.Now
            };
        }

        #endregion
    }

    #region Data Classes

    [Serializable]
    public class MachineCommand
    {
        public string MachineId;
        public string OperatorId;
        public CommandType Type;
        public Axis Axis;
        public float Value;
        public string Parameter;
        public DateTime Timestamp;
    }

    public enum CommandType
    {
        Jog,
        JogStop,
        Override,
        Spindle,
        Coolant,
        ProgramLoad,
        CycleStart,
        FeedHold,
        ProgramStop,
        SingleBlock,
        OptionalStop,
        MDI,
        Home,
        WorkOffset,
        ToolChange,
        EmergencyStop,
        Reset,
        ModeChange
    }

    [Serializable]
    public class MachineState
    {
        public string MachineId;
        public MachineMode Mode;
        public MachinePosition Position;
        public float FeedOverride;
        public float SpindleOverride;
        public float RapidOverride;
        public float SpindleRPM;
        public SpindleDirection SpindleDirection;
        public bool IsSpindleOn;
        public bool IsCoolantOn;
        public CoolantType CoolantType;
        public bool IsHomed;
        public int CurrentTool;
        public string ProgramName;
        public int ProgramLine;
        public int TotalLines;
        public WorkOffset ActiveWorkOffset;
        public bool IsSingleBlock;
        public bool IsOptionalStop;
        public List<MachineAlarm> Alarms = new List<MachineAlarm>();
    }

    [Serializable]
    public class MachinePosition
    {
        public float X;
        public float Y;
        public float Z;
        public float A;
        public float B;
        public float C;

        public override string ToString()
        {
            return $"X:{X:F3} Y:{Y:F3} Z:{Z:F3} A:{A:F3} B:{B:F3} C:{C:F3}";
        }
    }

    [Serializable]
    public class MachineAlarm
    {
        public string Code;
        public string Message;
        public DateTime Timestamp;
        public AlarmSeverity Severity;
    }

    public enum AlarmSeverity
    {
        Warning,
        Error,
        Critical
    }

    public enum MachineMode
    {
        Idle,
        Running,
        Paused,
        Homing,
        EStop,
        Alarm,
        ToolChange
    }

    public enum ControlMode
    {
        Manual,
        MDI,
        Auto
    }

    public enum JogMode
    {
        Incremental,
        Continuous,
        Rapid
    }

    public enum JogDirection
    {
        Positive,
        Negative
    }

    public enum Axis
    {
        None,
        X,
        Y,
        Z,
        A,
        B,
        C
    }

    public enum SpindleDirection
    {
        CW,
        CCW
    }

    public enum CoolantType
    {
        Off,
        Flood,
        Mist
    }

    public enum WorkOffset
    {
        G54,
        G55,
        G56,
        G57,
        G58,
        G59
    }

    [Serializable]
    public class ControlPanelStatus
    {
        public string MachineId;
        public bool IsConnected;
        public ControlMode ControlMode;
        public MachineMode MachineMode;
        public MachinePosition Position;
        public float FeedOverride;
        public float SpindleOverride;
        public float RapidOverride;
        public float SpindleRPM;
        public bool IsSpindleOn;
        public bool IsCoolantOn;
        public int CurrentTool;
        public string ProgramName;
        public int ProgramLine;
        public bool IsHomed;
        public JogMode JogMode;
        public float JogIncrement;
        public int ActiveAlarms;
        public DateTime Timestamp;
    }

    #endregion
}
