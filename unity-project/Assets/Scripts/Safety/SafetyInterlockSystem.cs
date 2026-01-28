using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCDigitalTwin.Safety
{
    /// <summary>
    /// Safety Interlock System for CNC Digital Twin
    /// Implements IEC 62443 / ISO 13849 safety concepts
    /// Monitors safety circuits, interlocks, zones, and emergency stops
    /// </summary>
    public class SafetyInterlockSystem : MonoBehaviour
    {
        public static SafetyInterlockSystem Instance { get; private set; }

        [Header("Safety Configuration")]
        [SerializeField] private SafetyIntegrityLevel systemSIL = SafetyIntegrityLevel.SIL2;
        [SerializeField] private PerformanceLevel systemPL = PerformanceLevel.PLd;
        [SerializeField] private float safetyLoopTime = 0.01f; // 10ms safety loop
        [SerializeField] private bool enableRedundantMonitoring = true;

        [Header("E-Stop Configuration")]
        [SerializeField] private EStopCategory estopCategory = EStopCategory.Category1;
        [SerializeField] private float category1StopTime = 1.0f; // seconds
        [SerializeField] private float maxSafeSpeed = 10f; // mm/s for reduced speed

        [Header("Zone Configuration")]
        [SerializeField] private float defaultWarningDistance = 1000f; // mm
        [SerializeField] private float defaultDangerDistance = 500f; // mm
        [SerializeField] private float zoneCheckInterval = 0.02f; // 50Hz

        // Events
        public event Action<SafetyState> OnSafetyStateChanged;
        public event Action<EStopEvent> OnEmergencyStop;
        public event Action<InterlockEvent> OnInterlockTriggered;
        public event Action<SafetyZone, ZoneViolation> OnZoneViolation;
        public event Action<SafetyDevice, DeviceState> OnDeviceStateChanged;
        public event Action<SafetyFault> OnSafetyFault;
        public event Action OnSafetyReset;

        // Safety devices
        private Dictionary<string, SafetyDevice> safetyDevices = new Dictionary<string, SafetyDevice>();
        private Dictionary<string, SafetyInterlock> interlocks = new Dictionary<string, SafetyInterlock>();
        private Dictionary<string, SafetyZone> safetyZones = new Dictionary<string, SafetyZone>();
        private Dictionary<string, SafetyCircuit> safetyCircuits = new Dictionary<string, SafetyCircuit>();

        // State
        private SafetyState currentState = new SafetyState();
        private List<SafetyFault> activeFaults = new List<SafetyFault>();
        private List<EStopEvent> estopHistory = new List<EStopEvent>();
        private bool systemSafe = true;
        private bool estopActive = false;
        private DateTime lastSafetyCheck;

        // Statistics
        private SafetyStats stats = new SafetyStats();

        #region Data Structures

        public enum SafetyIntegrityLevel
        {
            SIL1,
            SIL2,
            SIL3,
            SIL4
        }

        public enum PerformanceLevel
        {
            PLa,
            PLb,
            PLc,
            PLd,
            PLe
        }

        public enum EStopCategory
        {
            Category0,  // Immediate power removal
            Category1,  // Controlled stop then power removal
            Category2   // Controlled stop, power maintained
        }

        public enum DeviceType
        {
            EmergencyStop,
            LightCurtain,
            SafetyMat,
            SafetyScanner,
            SafetyDoor,
            SafetyGate,
            TwoHandControl,
            EnableSwitch,
            SafetyRelay,
            SafetyPLC,
            MotionMonitor,
            SpeedMonitor,
            PositionMonitor,
            TorqueLimiter,
            SafetyBrake,
            GuardLock
        }

        public enum DeviceState
        {
            Safe,
            Triggered,
            Bypassed,
            Fault,
            Unknown,
            Testing
        }

        public enum ZoneType
        {
            Danger,
            Warning,
            Restricted,
            SafeOperating,
            Collaborative
        }

        public enum InterlockType
        {
            MachineGuard,
            AxisLimit,
            SpindleSpeed,
            ToolChange,
            DoorAccess,
            ProgramStart,
            FeedHold,
            CoolantPressure,
            LubricationFlow,
            AirPressure,
            Temperature,
            Overload
        }

        public enum InterlockCondition
        {
            MustBeClosed,
            MustBeOpen,
            MustBeInRange,
            MustBeZero,
            MustBeNonZero,
            MustMatch,
            MustBeLessThan,
            MustBeGreaterThan
        }

        public class SafetyDevice
        {
            public string DeviceId { get; set; }
            public string Name { get; set; }
            public DeviceType Type { get; set; }
            public string CircuitId { get; set; }
            public DeviceState State { get; set; }
            public DeviceState RedundantState { get; set; }
            public bool IsDualChannel { get; set; }
            public SafetyIntegrityLevel SIL { get; set; }
            public PerformanceLevel PL { get; set; }
            public Vector3 Position { get; set; }
            public bool CanBeBypassed { get; set; }
            public bool IsBypassed { get; set; }
            public string BypassReason { get; set; }
            public DateTime? BypassExpiry { get; set; }
            public DateTime LastStateChange { get; set; }
            public int TriggerCount { get; set; }
            public float ResponseTimeMs { get; set; }
            public DeviceDiagnostics Diagnostics { get; set; } = new DeviceDiagnostics();
        }

        public class DeviceDiagnostics
        {
            public bool CrossFaultDetected { get; set; }
            public bool WiringFaultDetected { get; set; }
            public bool TimingFaultDetected { get; set; }
            public float Channel1Voltage { get; set; }
            public float Channel2Voltage { get; set; }
            public int DiagnosticCode { get; set; }
            public DateTime LastTest { get; set; }
            public bool TestPassed { get; set; }
        }

        public class SafetyInterlock
        {
            public string InterlockId { get; set; }
            public string Name { get; set; }
            public string Description { get; set; }
            public InterlockType Type { get; set; }
            public InterlockCondition Condition { get; set; }
            public string MonitoredVariable { get; set; }
            public float? SetPoint { get; set; }
            public float? Hysteresis { get; set; }
            public float? LowerLimit { get; set; }
            public float? UpperLimit { get; set; }
            public string[] RequiredDevices { get; set; }
            public bool IsSatisfied { get; set; }
            public bool IsEnabled { get; set; }
            public string BlockedAction { get; set; }
            public string OverrideRequirement { get; set; }
            public DateTime LastChecked { get; set; }
            public int ViolationCount { get; set; }
        }

        public class SafetyZone
        {
            public string ZoneId { get; set; }
            public string Name { get; set; }
            public ZoneType Type { get; set; }
            public Bounds Bounds { get; set; }
            public float WarningDistance { get; set; }
            public float DangerDistance { get; set; }
            public float MaxSpeed { get; set; }
            public float MaxForce { get; set; }
            public bool IsActive { get; set; }
            public List<string> MonitoringDevices { get; set; } = new List<string>();
            public ZoneState CurrentState { get; set; }
            public List<string> DetectedObjects { get; set; } = new List<string>();
            public DateTime LastViolation { get; set; }
            public int ViolationCount { get; set; }
        }

        public class ZoneState
        {
            public bool IsOccupied { get; set; }
            public bool IsViolated { get; set; }
            public float MinDistance { get; set; }
            public Vector3 NearestPoint { get; set; }
            public string NearestObjectId { get; set; }
        }

        public class ZoneViolation
        {
            public string ZoneId { get; set; }
            public DateTime Timestamp { get; set; }
            public string ObjectId { get; set; }
            public Vector3 Position { get; set; }
            public float Distance { get; set; }
            public float Speed { get; set; }
            public ViolationType Type { get; set; }
            public string ActionTaken { get; set; }
        }

        public enum ViolationType
        {
            WarningZoneEntry,
            DangerZoneEntry,
            SpeedExceeded,
            ForceExceeded,
            UnauthorizedEntry
        }

        public class SafetyCircuit
        {
            public string CircuitId { get; set; }
            public string Name { get; set; }
            public SafetyIntegrityLevel SIL { get; set; }
            public List<string> DeviceIds { get; set; } = new List<string>();
            public bool IsClosed { get; set; }
            public bool IsHealthy { get; set; }
            public bool Channel1State { get; set; }
            public bool Channel2State { get; set; }
            public float LoopResistance { get; set; }
            public float ResponseTimeMs { get; set; }
            public DateTime LastTest { get; set; }
        }

        public class SafetyState
        {
            public DateTime Timestamp { get; set; }
            public bool SystemSafe { get; set; }
            public bool EStopActive { get; set; }
            public bool AllInterlocksSatisfied { get; set; }
            public bool AllZonesClear { get; set; }
            public bool AllCircuitsHealthy { get; set; }
            public int ActiveFaults { get; set; }
            public OperatingMode CurrentMode { get; set; }
            public float MaxAllowedSpeed { get; set; }
            public float MaxAllowedForce { get; set; }
        }

        public enum OperatingMode
        {
            Normal,
            ReducedSpeed,
            Manual,
            Setup,
            Maintenance,
            Teach,
            Emergency,
            Stopped
        }

        public class EStopEvent
        {
            public string EventId { get; set; }
            public DateTime Timestamp { get; set; }
            public string DeviceId { get; set; }
            public string TriggeredBy { get; set; }
            public EStopCategory Category { get; set; }
            public float StopTime { get; set; }
            public bool WasControlled { get; set; }
            public DateTime? ResetTime { get; set; }
            public string ResetBy { get; set; }
            public string RootCause { get; set; }
        }

        public class InterlockEvent
        {
            public string InterlockId { get; set; }
            public DateTime Timestamp { get; set; }
            public bool WasSatisfied { get; set; }
            public string BlockedAction { get; set; }
            public string CurrentValue { get; set; }
            public string RequiredValue { get; set; }
        }

        public class SafetyFault
        {
            public string FaultId { get; set; }
            public DateTime Timestamp { get; set; }
            public string DeviceId { get; set; }
            public FaultType Type { get; set; }
            public FaultSeverity Severity { get; set; }
            public string Description { get; set; }
            public string DiagnosticCode { get; set; }
            public bool RequiresReset { get; set; }
            public bool Acknowledged { get; set; }
            public DateTime? ClearedTime { get; set; }
        }

        public enum FaultType
        {
            CrossFault,
            WiringFault,
            TimingDiscrepancy,
            DeviceFailure,
            CommunicationLoss,
            ConfigurationError,
            CalibrationError,
            ExternalFault,
            InternalFault
        }

        public enum FaultSeverity
        {
            Warning,
            Fault,
            Critical
        }

        public class SafetyStats
        {
            public DateTime StartTime { get; set; }
            public int TotalDevices { get; set; }
            public int HealthyDevices { get; set; }
            public int TotalInterlocks { get; set; }
            public int SatisfiedInterlocks { get; set; }
            public int TotalZones { get; set; }
            public int ClearZones { get; set; }
            public long EStopCount { get; set; }
            public long InterlockViolations { get; set; }
            public long ZoneViolations { get; set; }
            public float SystemUptime { get; set; }
            public float SafeStatePercent { get; set; }
        }

        #endregion

        #region Initialization

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
            }
            else
            {
                Destroy(gameObject);
                return;
            }

            stats.StartTime = DateTime.Now;
        }

        private void Start()
        {
            InitializeDefaultConfiguration();
            StartCoroutine(SafetyLoop());
            StartCoroutine(ZoneMonitorLoop());
            StartCoroutine(DiagnosticsLoop());

            Debug.Log($"[Safety] System initialized - SIL{(int)systemSIL}, PL{systemPL}");
        }

        private void InitializeDefaultConfiguration()
        {
            // Register E-Stop devices
            RegisterDevice("estop_main", "Main E-Stop", DeviceType.EmergencyStop, "circuit_estop",
                isDualChannel: true, sil: SafetyIntegrityLevel.SIL3);
            RegisterDevice("estop_pendant", "Pendant E-Stop", DeviceType.EmergencyStop, "circuit_estop",
                isDualChannel: true, sil: SafetyIntegrityLevel.SIL3);
            RegisterDevice("estop_remote", "Remote E-Stop", DeviceType.EmergencyStop, "circuit_estop",
                isDualChannel: true, sil: SafetyIntegrityLevel.SIL3);

            // Register guard doors
            RegisterDevice("door_front", "Front Guard Door", DeviceType.SafetyDoor, "circuit_guards",
                isDualChannel: true, sil: SafetyIntegrityLevel.SIL2);
            RegisterDevice("door_side", "Side Access Door", DeviceType.SafetyDoor, "circuit_guards",
                isDualChannel: true, sil: SafetyIntegrityLevel.SIL2);

            // Register light curtains
            RegisterDevice("lc_load", "Load Area Light Curtain", DeviceType.LightCurtain, "circuit_lc",
                isDualChannel: true, sil: SafetyIntegrityLevel.SIL2);

            // Register safety circuits
            RegisterCircuit("circuit_estop", "E-Stop Circuit", SafetyIntegrityLevel.SIL3);
            RegisterCircuit("circuit_guards", "Guard Circuit", SafetyIntegrityLevel.SIL2);
            RegisterCircuit("circuit_lc", "Light Curtain Circuit", SafetyIntegrityLevel.SIL2);

            // Register safety zones
            RegisterZone("zone_work", "Work Envelope", ZoneType.Danger,
                new Bounds(Vector3.zero, new Vector3(1000, 800, 600)));
            RegisterZone("zone_load", "Load/Unload Area", ZoneType.Warning,
                new Bounds(new Vector3(0, 0, 400), new Vector3(500, 500, 200)));

            // Register interlocks
            RegisterInterlock("il_door_run", "Door Closed for Run", InterlockType.MachineGuard,
                InterlockCondition.MustBeClosed, blockedAction: "Cycle Start",
                requiredDevices: new[] { "door_front", "door_side" });

            RegisterInterlock("il_spindle_door", "Spindle Stop for Door", InterlockType.SpindleSpeed,
                InterlockCondition.MustBeZero, blockedAction: "Door Open",
                monitoredVariable: "SpindleSpeed");

            RegisterInterlock("il_axis_limits", "Axis Within Limits", InterlockType.AxisLimit,
                InterlockCondition.MustBeInRange, blockedAction: "Motion",
                monitoredVariable: "AxisPosition", lowerLimit: -500, upperLimit: 500);

            RegisterInterlock("il_air_pressure", "Air Pressure OK", InterlockType.AirPressure,
                InterlockCondition.MustBeGreaterThan, blockedAction: "Cycle Start",
                monitoredVariable: "AirPressure", setPoint: 400000); // 4 bar minimum
        }

        #endregion

        #region Device Management

        public SafetyDevice RegisterDevice(string deviceId, string name, DeviceType type,
            string circuitId, bool isDualChannel = false, SafetyIntegrityLevel sil = SafetyIntegrityLevel.SIL2,
            PerformanceLevel pl = PerformanceLevel.PLd, bool canBeBypassed = false)
        {
            var device = new SafetyDevice
            {
                DeviceId = deviceId,
                Name = name,
                Type = type,
                CircuitId = circuitId,
                State = DeviceState.Safe,
                RedundantState = isDualChannel ? DeviceState.Safe : DeviceState.Unknown,
                IsDualChannel = isDualChannel,
                SIL = sil,
                PL = pl,
                CanBeBypassed = canBeBypassed,
                IsBypassed = false,
                LastStateChange = DateTime.Now
            };

            safetyDevices[deviceId] = device;
            stats.TotalDevices++;
            stats.HealthyDevices++;

            // Add to circuit
            if (safetyCircuits.TryGetValue(circuitId, out var circuit))
            {
                circuit.DeviceIds.Add(deviceId);
            }

            Debug.Log($"[Safety] Registered device: {deviceId} ({type})");
            return device;
        }

        public void RegisterCircuit(string circuitId, string name, SafetyIntegrityLevel sil)
        {
            var circuit = new SafetyCircuit
            {
                CircuitId = circuitId,
                Name = name,
                SIL = sil,
                IsClosed = true,
                IsHealthy = true,
                Channel1State = true,
                Channel2State = true,
                LastTest = DateTime.Now
            };

            safetyCircuits[circuitId] = circuit;
        }

        public void RegisterZone(string zoneId, string name, ZoneType type, Bounds bounds,
            float warningDist = 0, float dangerDist = 0)
        {
            var zone = new SafetyZone
            {
                ZoneId = zoneId,
                Name = name,
                Type = type,
                Bounds = bounds,
                WarningDistance = warningDist > 0 ? warningDist : defaultWarningDistance,
                DangerDistance = dangerDist > 0 ? dangerDist : defaultDangerDistance,
                MaxSpeed = type == ZoneType.Collaborative ? maxSafeSpeed : float.MaxValue,
                MaxForce = type == ZoneType.Collaborative ? 150f : float.MaxValue, // ISO 10218
                IsActive = true,
                CurrentState = new ZoneState()
            };

            safetyZones[zoneId] = zone;
            stats.TotalZones++;
            stats.ClearZones++;
        }

        public SafetyInterlock RegisterInterlock(string interlockId, string name, InterlockType type,
            InterlockCondition condition, string blockedAction, string monitoredVariable = null,
            float? setPoint = null, float? lowerLimit = null, float? upperLimit = null,
            string[] requiredDevices = null)
        {
            var interlock = new SafetyInterlock
            {
                InterlockId = interlockId,
                Name = name,
                Type = type,
                Condition = condition,
                MonitoredVariable = monitoredVariable,
                SetPoint = setPoint,
                LowerLimit = lowerLimit,
                UpperLimit = upperLimit,
                RequiredDevices = requiredDevices ?? new string[0],
                BlockedAction = blockedAction,
                IsEnabled = true,
                IsSatisfied = true
            };

            interlocks[interlockId] = interlock;
            stats.TotalInterlocks++;
            stats.SatisfiedInterlocks++;

            Debug.Log($"[Safety] Registered interlock: {interlockId} ({type})");
            return interlock;
        }

        #endregion

        #region Device State Updates

        public void UpdateDeviceState(string deviceId, DeviceState state, DeviceState? redundantState = null)
        {
            if (!safetyDevices.TryGetValue(deviceId, out var device))
                return;

            var oldState = device.State;
            device.State = state;

            if (device.IsDualChannel && redundantState.HasValue)
            {
                device.RedundantState = redundantState.Value;

                // Check for cross-fault (discrepancy between channels)
                if (state != redundantState.Value)
                {
                    device.Diagnostics.CrossFaultDetected = true;
                    RaiseFault(deviceId, FaultType.CrossFault, FaultSeverity.Critical,
                        $"Channel discrepancy: Ch1={state}, Ch2={redundantState}");
                }
            }

            device.LastStateChange = DateTime.Now;

            if (state == DeviceState.Triggered)
            {
                device.TriggerCount++;
            }

            // Handle E-Stop trigger
            if (device.Type == DeviceType.EmergencyStop && state == DeviceState.Triggered)
            {
                TriggerEmergencyStop(deviceId, "Device triggered");
            }

            // Update circuit state
            UpdateCircuitState(device.CircuitId);

            if (oldState != state)
            {
                OnDeviceStateChanged?.Invoke(device, state);
            }
        }

        private void UpdateCircuitState(string circuitId)
        {
            if (!safetyCircuits.TryGetValue(circuitId, out var circuit))
                return;

            bool allSafe = true;
            bool channel1Ok = true;
            bool channel2Ok = true;

            foreach (var deviceId in circuit.DeviceIds)
            {
                if (safetyDevices.TryGetValue(deviceId, out var device))
                {
                    if (device.State != DeviceState.Safe && !device.IsBypassed)
                    {
                        allSafe = false;
                    }

                    if (device.IsDualChannel)
                    {
                        if (device.State != DeviceState.Safe) channel1Ok = false;
                        if (device.RedundantState != DeviceState.Safe) channel2Ok = false;
                    }
                }
            }

            circuit.IsClosed = allSafe;
            circuit.Channel1State = channel1Ok;
            circuit.Channel2State = channel2Ok;
            circuit.IsHealthy = channel1Ok && channel2Ok;
        }

        #endregion

        #region Emergency Stop

        public void TriggerEmergencyStop(string deviceId, string reason)
        {
            if (estopActive) return;

            estopActive = true;
            var evt = new EStopEvent
            {
                EventId = Guid.NewGuid().ToString(),
                Timestamp = DateTime.Now,
                DeviceId = deviceId,
                TriggeredBy = reason,
                Category = estopCategory
            };

            estopHistory.Add(evt);
            stats.EStopCount++;

            // Execute stop sequence
            StartCoroutine(ExecuteEmergencyStop(evt));

            OnEmergencyStop?.Invoke(evt);
            Debug.LogWarning($"[Safety] EMERGENCY STOP triggered by {deviceId}: {reason}");
        }

        private IEnumerator ExecuteEmergencyStop(EStopEvent evt)
        {
            float startTime = Time.time;
            currentState.CurrentMode = OperatingMode.Emergency;

            switch (estopCategory)
            {
                case EStopCategory.Category0:
                    // Immediate power removal
                    evt.StopTime = 0;
                    evt.WasControlled = false;
                    Debug.Log("[Safety] Category 0 stop - immediate power removal");
                    break;

                case EStopCategory.Category1:
                    // Controlled stop then power removal
                    yield return new WaitForSeconds(category1StopTime);
                    evt.StopTime = Time.time - startTime;
                    evt.WasControlled = true;
                    Debug.Log($"[Safety] Category 1 stop completed in {evt.StopTime:F2}s");
                    break;

                case EStopCategory.Category2:
                    // Controlled stop, power maintained
                    yield return new WaitForSeconds(category1StopTime);
                    evt.StopTime = Time.time - startTime;
                    evt.WasControlled = true;
                    Debug.Log($"[Safety] Category 2 stop completed in {evt.StopTime:F2}s");
                    break;
            }

            currentState.CurrentMode = OperatingMode.Stopped;
            UpdateSafetyState();
        }

        public bool ResetEmergencyStop(string operatorId)
        {
            // Verify all E-Stop devices are reset
            foreach (var device in safetyDevices.Values.Where(d => d.Type == DeviceType.EmergencyStop))
            {
                if (device.State != DeviceState.Safe)
                {
                    Debug.LogWarning($"[Safety] Cannot reset - {device.Name} still triggered");
                    return false;
                }
            }

            // Verify no active faults
            var criticalFaults = activeFaults.Where(f => f.Severity == FaultSeverity.Critical && !f.Acknowledged);
            if (criticalFaults.Any())
            {
                Debug.LogWarning($"[Safety] Cannot reset - {criticalFaults.Count()} unacknowledged critical faults");
                return false;
            }

            estopActive = false;

            // Update last E-Stop event
            var lastEstop = estopHistory.LastOrDefault();
            if (lastEstop != null)
            {
                lastEstop.ResetTime = DateTime.Now;
                lastEstop.ResetBy = operatorId;
            }

            currentState.CurrentMode = OperatingMode.Normal;
            UpdateSafetyState();

            OnSafetyReset?.Invoke();
            Debug.Log($"[Safety] E-Stop reset by {operatorId}");

            return true;
        }

        #endregion

        #region Interlock Checking

        public bool CheckInterlock(string interlockId)
        {
            if (!interlocks.TryGetValue(interlockId, out var interlock))
                return true; // Unknown interlock passes

            if (!interlock.IsEnabled)
                return true;

            bool satisfied = EvaluateInterlock(interlock);
            bool wasViolated = interlock.IsSatisfied && !satisfied;

            interlock.IsSatisfied = satisfied;
            interlock.LastChecked = DateTime.Now;

            if (wasViolated)
            {
                interlock.ViolationCount++;
                stats.InterlockViolations++;

                OnInterlockTriggered?.Invoke(new InterlockEvent
                {
                    InterlockId = interlockId,
                    Timestamp = DateTime.Now,
                    WasSatisfied = false,
                    BlockedAction = interlock.BlockedAction
                });
            }

            return satisfied;
        }

        private bool EvaluateInterlock(SafetyInterlock interlock)
        {
            // Check required devices first
            if (interlock.RequiredDevices != null && interlock.RequiredDevices.Length > 0)
            {
                foreach (var deviceId in interlock.RequiredDevices)
                {
                    if (safetyDevices.TryGetValue(deviceId, out var device))
                    {
                        if (device.State != DeviceState.Safe && !device.IsBypassed)
                        {
                            return false;
                        }
                    }
                }
            }

            // Check monitored variable if specified
            if (!string.IsNullOrEmpty(interlock.MonitoredVariable))
            {
                float value = GetMonitoredValue(interlock.MonitoredVariable);

                switch (interlock.Condition)
                {
                    case InterlockCondition.MustBeZero:
                        return Mathf.Abs(value) < 0.001f;

                    case InterlockCondition.MustBeNonZero:
                        return Mathf.Abs(value) >= 0.001f;

                    case InterlockCondition.MustBeLessThan:
                        return value < (interlock.SetPoint ?? 0);

                    case InterlockCondition.MustBeGreaterThan:
                        return value > (interlock.SetPoint ?? 0);

                    case InterlockCondition.MustBeInRange:
                        return value >= (interlock.LowerLimit ?? float.MinValue) &&
                               value <= (interlock.UpperLimit ?? float.MaxValue);
                }
            }

            return true;
        }

        private float GetMonitoredValue(string variableName)
        {
            // In real implementation, this would query actual sensor values
            // For now, return simulated values
            return variableName switch
            {
                "SpindleSpeed" => UnityEngine.Random.Range(0f, 100f),
                "AxisPosition" => UnityEngine.Random.Range(-400f, 400f),
                "AirPressure" => UnityEngine.Random.Range(380000f, 420000f),
                "Temperature" => UnityEngine.Random.Range(20f, 60f),
                _ => 0f
            };
        }

        public bool CheckAllInterlocks()
        {
            bool allSatisfied = true;

            foreach (var interlock in interlocks.Values)
            {
                if (!CheckInterlock(interlock.InterlockId))
                {
                    allSatisfied = false;
                }
            }

            currentState.AllInterlocksSatisfied = allSatisfied;
            stats.SatisfiedInterlocks = interlocks.Values.Count(i => i.IsSatisfied);

            return allSatisfied;
        }

        public bool CanPerformAction(string action)
        {
            // Check all interlocks that block this action
            var blockingInterlocks = interlocks.Values.Where(i =>
                i.IsEnabled && i.BlockedAction == action && !i.IsSatisfied);

            return !blockingInterlocks.Any();
        }

        #endregion

        #region Zone Monitoring

        private IEnumerator ZoneMonitorLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(zoneCheckInterval);

                foreach (var zone in safetyZones.Values.Where(z => z.IsActive))
                {
                    CheckZone(zone);
                }

                currentState.AllZonesClear = safetyZones.Values.All(z =>
                    !z.IsActive || !z.CurrentState.IsViolated);
                stats.ClearZones = safetyZones.Values.Count(z => !z.CurrentState.IsViolated);
            }
        }

        private void CheckZone(SafetyZone zone)
        {
            // In real implementation, this would use actual detection from safety scanners,
            // light curtains, or collision detection systems

            // Simulate object detection
            bool objectDetected = UnityEngine.Random.value < 0.01f; // 1% chance
            Vector3 objectPos = zone.Bounds.center + UnityEngine.Random.insideUnitSphere * 200f;
            float distance = Vector3.Distance(objectPos, zone.Bounds.center);

            zone.CurrentState.IsOccupied = objectDetected;

            if (objectDetected)
            {
                zone.CurrentState.MinDistance = distance;
                zone.CurrentState.NearestPoint = objectPos;

                // Check for zone violation
                if (zone.Type == ZoneType.Danger && distance < zone.DangerDistance)
                {
                    zone.CurrentState.IsViolated = true;
                    zone.ViolationCount++;
                    zone.LastViolation = DateTime.Now;
                    stats.ZoneViolations++;

                    var violation = new ZoneViolation
                    {
                        ZoneId = zone.ZoneId,
                        Timestamp = DateTime.Now,
                        Position = objectPos,
                        Distance = distance,
                        Type = ViolationType.DangerZoneEntry,
                        ActionTaken = "Machine Stop"
                    };

                    OnZoneViolation?.Invoke(zone, violation);

                    // Trigger safety stop
                    if (zone.Type == ZoneType.Danger)
                    {
                        TriggerEmergencyStop("zone_" + zone.ZoneId, "Danger zone intrusion");
                    }
                }
                else if (distance < zone.WarningDistance)
                {
                    var violation = new ZoneViolation
                    {
                        ZoneId = zone.ZoneId,
                        Timestamp = DateTime.Now,
                        Position = objectPos,
                        Distance = distance,
                        Type = ViolationType.WarningZoneEntry,
                        ActionTaken = "Speed Reduction"
                    };

                    OnZoneViolation?.Invoke(zone, violation);

                    // Reduce speed for collaborative zones
                    if (zone.Type == ZoneType.Collaborative)
                    {
                        currentState.MaxAllowedSpeed = zone.MaxSpeed;
                        currentState.MaxAllowedForce = zone.MaxForce;
                        currentState.CurrentMode = OperatingMode.ReducedSpeed;
                    }
                }
            }
            else
            {
                zone.CurrentState.IsViolated = false;
                zone.CurrentState.MinDistance = float.MaxValue;
            }
        }

        public void SetZoneActive(string zoneId, bool active)
        {
            if (safetyZones.TryGetValue(zoneId, out var zone))
            {
                zone.IsActive = active;
                Debug.Log($"[Safety] Zone {zoneId} {(active ? "activated" : "deactivated")}");
            }
        }

        #endregion

        #region Safety Loop

        private IEnumerator SafetyLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(safetyLoopTime);

                lastSafetyCheck = DateTime.Now;

                // Update all device states
                UpdateAllDeviceStates();

                // Check all circuits
                UpdateAllCircuitStates();

                // Check all interlocks
                CheckAllInterlocks();

                // Update overall safety state
                UpdateSafetyState();
            }
        }

        private void UpdateAllDeviceStates()
        {
            foreach (var device in safetyDevices.Values)
            {
                // Check for timeout
                if ((DateTime.Now - device.LastStateChange).TotalSeconds > 5 &&
                    device.State == DeviceState.Unknown)
                {
                    RaiseFault(device.DeviceId, FaultType.CommunicationLoss, FaultSeverity.Fault,
                        "Device communication timeout");
                }

                // Check bypass expiry
                if (device.IsBypassed && device.BypassExpiry.HasValue &&
                    DateTime.Now > device.BypassExpiry.Value)
                {
                    device.IsBypassed = false;
                    device.BypassReason = null;
                    device.BypassExpiry = null;
                    Debug.Log($"[Safety] Bypass expired for {device.DeviceId}");
                }
            }

            stats.HealthyDevices = safetyDevices.Values.Count(d =>
                d.State == DeviceState.Safe || d.State == DeviceState.Bypassed);
        }

        private void UpdateAllCircuitStates()
        {
            foreach (var circuitId in safetyCircuits.Keys)
            {
                UpdateCircuitState(circuitId);
            }

            currentState.AllCircuitsHealthy = safetyCircuits.Values.All(c => c.IsHealthy);
        }

        private void UpdateSafetyState()
        {
            currentState.Timestamp = DateTime.Now;
            currentState.EStopActive = estopActive;
            currentState.ActiveFaults = activeFaults.Count(f => f.ClearedTime == null);

            systemSafe = !estopActive &&
                        currentState.AllInterlocksSatisfied &&
                        currentState.AllCircuitsHealthy &&
                        currentState.ActiveFaults == 0;

            currentState.SystemSafe = systemSafe;

            // Update operating mode based on conditions
            if (estopActive)
            {
                currentState.CurrentMode = OperatingMode.Emergency;
                currentState.MaxAllowedSpeed = 0;
                currentState.MaxAllowedForce = 0;
            }
            else if (!currentState.AllZonesClear)
            {
                currentState.CurrentMode = OperatingMode.ReducedSpeed;
                currentState.MaxAllowedSpeed = maxSafeSpeed;
            }
            else
            {
                if (currentState.CurrentMode == OperatingMode.ReducedSpeed ||
                    currentState.CurrentMode == OperatingMode.Emergency)
                {
                    currentState.CurrentMode = OperatingMode.Normal;
                    currentState.MaxAllowedSpeed = float.MaxValue;
                    currentState.MaxAllowedForce = float.MaxValue;
                }
            }

            OnSafetyStateChanged?.Invoke(currentState);
        }

        #endregion

        #region Diagnostics

        private IEnumerator DiagnosticsLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(60f); // Run diagnostics every minute

                if (enableRedundantMonitoring)
                {
                    RunDualChannelDiagnostics();
                }

                RunCircuitDiagnostics();

                // Calculate uptime
                stats.SystemUptime = (float)(DateTime.Now - stats.StartTime).TotalHours;

                // This is simplified - in real implementation would track actual safe time
                stats.SafeStatePercent = systemSafe ? 100f : stats.SafeStatePercent * 0.99f;
            }
        }

        private void RunDualChannelDiagnostics()
        {
            foreach (var device in safetyDevices.Values.Where(d => d.IsDualChannel))
            {
                // Check channel discrepancy timing
                if (device.State != device.RedundantState)
                {
                    device.Diagnostics.TimingFaultDetected = true;

                    if (!device.Diagnostics.CrossFaultDetected)
                    {
                        RaiseFault(device.DeviceId, FaultType.CrossFault, FaultSeverity.Critical,
                            "Dual channel discrepancy detected");
                    }
                }
                else
                {
                    device.Diagnostics.CrossFaultDetected = false;
                    device.Diagnostics.TimingFaultDetected = false;
                }
            }
        }

        private void RunCircuitDiagnostics()
        {
            foreach (var circuit in safetyCircuits.Values)
            {
                // Check dual-channel integrity
                if (circuit.Channel1State != circuit.Channel2State)
                {
                    RaiseFault(circuit.CircuitId, FaultType.CrossFault, FaultSeverity.Critical,
                        "Circuit channel discrepancy");
                }

                circuit.LastTest = DateTime.Now;
            }
        }

        public void RaiseFault(string deviceId, FaultType type, FaultSeverity severity, string description)
        {
            var fault = new SafetyFault
            {
                FaultId = Guid.NewGuid().ToString(),
                Timestamp = DateTime.Now,
                DeviceId = deviceId,
                Type = type,
                Severity = severity,
                Description = description,
                RequiresReset = severity == FaultSeverity.Critical
            };

            activeFaults.Add(fault);
            OnSafetyFault?.Invoke(fault);

            Debug.LogError($"[Safety] FAULT: {type} on {deviceId} - {description}");

            // Critical faults trigger E-Stop
            if (severity == FaultSeverity.Critical)
            {
                TriggerEmergencyStop(deviceId, $"Safety fault: {type}");
            }
        }

        public void AcknowledgeFault(string faultId)
        {
            var fault = activeFaults.FirstOrDefault(f => f.FaultId == faultId);
            if (fault != null)
            {
                fault.Acknowledged = true;
            }
        }

        public void ClearFault(string faultId)
        {
            var fault = activeFaults.FirstOrDefault(f => f.FaultId == faultId);
            if (fault != null && fault.Acknowledged)
            {
                fault.ClearedTime = DateTime.Now;
            }
        }

        #endregion

        #region Bypass Management

        public bool SetDeviceBypass(string deviceId, string reason, float durationMinutes, string authorizedBy)
        {
            if (!safetyDevices.TryGetValue(deviceId, out var device))
                return false;

            if (!device.CanBeBypassed)
            {
                Debug.LogWarning($"[Safety] Device {deviceId} cannot be bypassed");
                return false;
            }

            device.IsBypassed = true;
            device.BypassReason = reason;
            device.BypassExpiry = DateTime.Now.AddMinutes(durationMinutes);

            Debug.LogWarning($"[Safety] Device {deviceId} bypassed by {authorizedBy}: {reason} (expires in {durationMinutes} min)");

            return true;
        }

        public void ClearDeviceBypass(string deviceId)
        {
            if (safetyDevices.TryGetValue(deviceId, out var device))
            {
                device.IsBypassed = false;
                device.BypassReason = null;
                device.BypassExpiry = null;
                Debug.Log($"[Safety] Bypass cleared for {deviceId}");
            }
        }

        #endregion

        #region Public API

        public SafetyDevice GetDevice(string deviceId)
        {
            return safetyDevices.TryGetValue(deviceId, out var device) ? device : null;
        }

        public List<SafetyDevice> GetAllDevices()
        {
            return safetyDevices.Values.ToList();
        }

        public SafetyInterlock GetInterlock(string interlockId)
        {
            return interlocks.TryGetValue(interlockId, out var interlock) ? interlock : null;
        }

        public List<SafetyInterlock> GetAllInterlocks()
        {
            return interlocks.Values.ToList();
        }

        public SafetyZone GetZone(string zoneId)
        {
            return safetyZones.TryGetValue(zoneId, out var zone) ? zone : null;
        }

        public List<SafetyZone> GetAllZones()
        {
            return safetyZones.Values.ToList();
        }

        public SafetyState GetCurrentState()
        {
            return currentState;
        }

        public bool IsSystemSafe()
        {
            return systemSafe;
        }

        public bool IsEStopActive()
        {
            return estopActive;
        }

        public List<SafetyFault> GetActiveFaults()
        {
            return activeFaults.Where(f => f.ClearedTime == null).ToList();
        }

        public List<EStopEvent> GetEStopHistory(int count = 10)
        {
            return estopHistory.TakeLast(count).ToList();
        }

        public SafetyStats GetStats()
        {
            return stats;
        }

        public void SetOperatingMode(OperatingMode mode)
        {
            if (estopActive && mode != OperatingMode.Emergency)
            {
                Debug.LogWarning("[Safety] Cannot change mode while E-Stop is active");
                return;
            }

            currentState.CurrentMode = mode;

            switch (mode)
            {
                case OperatingMode.Manual:
                case OperatingMode.Setup:
                case OperatingMode.Teach:
                    currentState.MaxAllowedSpeed = maxSafeSpeed;
                    break;
                case OperatingMode.Normal:
                    currentState.MaxAllowedSpeed = float.MaxValue;
                    break;
            }

            Debug.Log($"[Safety] Operating mode changed to {mode}");
        }

        #endregion
    }
}
