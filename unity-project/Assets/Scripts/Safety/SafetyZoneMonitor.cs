using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Safety
{
    /// <summary>
    /// Safety zone monitoring system for industrial safety compliance.
    /// Monitors worker presence in danger zones, robot work envelopes,
    /// and machine operating areas. Triggers safety responses when violations occur.
    /// </summary>
    public class SafetyZoneMonitor : MonoBehaviour
    {
        [Header("Configuration")]
        [SerializeField] private bool enableSafetyMonitoring = true;
        [SerializeField] private float scanInterval = 0.1f;
        [SerializeField] private LayerMask detectionLayers;
        [SerializeField] private bool visualizeZones = true;

        [Header("Safety Zones")]
        [SerializeField] private List<SafetyZone> safetyZones = new List<SafetyZone>();

        [Header("Safety Interlocks")]
        [SerializeField] private List<SafetyInterlock> interlocks = new List<SafetyInterlock>();

        [Header("Status")]
        [SerializeField] private bool systemArmed = true;
        [SerializeField] private int activeViolations;
        [SerializeField] private SafetyLevel currentSafetyLevel = SafetyLevel.Normal;
        [SerializeField] private bool emergencyStopActive;

        // Violation tracking
        private Dictionary<string, SafetyViolation> activeViolationMap = new Dictionary<string, SafetyViolation>();
        private List<SafetyViolation> violationHistory = new List<SafetyViolation>();
        private const int MaxHistorySize = 500;

        // Timers
        private float lastScanTime;

        // Events
        public event Action<SafetyZone, SafetyViolation> OnZoneViolation;
        public event Action<SafetyZone> OnZoneCleared;
        public event Action<SafetyInterlock, bool> OnInterlockStateChanged;
        public event Action<SafetyLevel> OnSafetyLevelChanged;
        public event Action OnEmergencyStop;
        public event Action OnEmergencyStopReset;

        // Singleton
        public static SafetyZoneMonitor Instance { get; private set; }

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
                return;
            }

            InitializeDefaultZones();
            InitializeDefaultInterlocks();
        }

        private void Update()
        {
            if (!enableSafetyMonitoring || !systemArmed)
            {
                return;
            }

            if (Time.time - lastScanTime >= scanInterval)
            {
                ScanAllZones();
                CheckInterlocks();
                lastScanTime = Time.time;
            }
        }

        private void InitializeDefaultZones()
        {
            // CNC Danger Zone - Spindle area
            safetyZones.Add(new SafetyZone
            {
                zoneId = "CNC_SPINDLE",
                zoneName = "CNC Spindle Area",
                zoneType = SafetyZoneType.DangerZone,
                shape = ZoneShape.Box,
                center = new Vector3(0, 0.45f, -0.3f),
                size = new Vector3(0.25f, 0.15f, 0.2f),
                associatedMachine = "BantamCNC",
                requiresMachineStop = true,
                warningDistance = 0.1f,
                dangerDistance = 0.05f
            });

            // xArm Work Envelope
            safetyZones.Add(new SafetyZone
            {
                zoneId = "XARM_ENVELOPE",
                zoneName = "xArm Work Envelope",
                zoneType = SafetyZoneType.RobotWorkspace,
                shape = ZoneShape.Sphere,
                center = new Vector3(0.5f, 0.3f, 0),
                radius = 0.7f,
                associatedMachine = "xArm",
                requiresMachineStop = true,
                warningDistance = 0.2f,
                dangerDistance = 0.1f
            });

            // Niryo Work Envelope
            safetyZones.Add(new SafetyZone
            {
                zoneId = "NIRYO_ENVELOPE",
                zoneName = "Niryo Work Envelope",
                zoneType = SafetyZoneType.RobotWorkspace,
                shape = ZoneShape.Sphere,
                center = new Vector3(-0.5f, 0.3f, 0),
                radius = 0.5f,
                associatedMachine = "Niryo",
                requiresMachineStop = true,
                warningDistance = 0.15f,
                dangerDistance = 0.08f
            });

            // Collaborative Zone - Reduced speed area
            safetyZones.Add(new SafetyZone
            {
                zoneId = "COLLAB_ZONE",
                zoneName = "Collaborative Work Zone",
                zoneType = SafetyZoneType.CollaborativeZone,
                shape = ZoneShape.Box,
                center = new Vector3(0, 0.3f, 0.3f),
                size = new Vector3(1.5f, 0.6f, 0.5f),
                associatedMachine = null,
                requiresMachineStop = false,
                requiresSpeedReduction = true,
                maxSpeedPercent = 50,
                warningDistance = 0.3f,
                dangerDistance = 0.15f
            });

            // Perimeter Warning Zone
            safetyZones.Add(new SafetyZone
            {
                zoneId = "PERIMETER",
                zoneName = "Cell Perimeter",
                zoneType = SafetyZoneType.WarningZone,
                shape = ZoneShape.Box,
                center = new Vector3(0, 0.5f, 0),
                size = new Vector3(2.5f, 1f, 2f),
                requiresMachineStop = false,
                warningDistance = 0.5f,
                dangerDistance = 0.3f
            });
        }

        private void InitializeDefaultInterlocks()
        {
            // Light curtain at cell entrance
            interlocks.Add(new SafetyInterlock
            {
                interlockId = "LC_ENTRANCE",
                interlockName = "Cell Entrance Light Curtain",
                interlockType = InterlockType.LightCurtain,
                position = new Vector3(0, 0.5f, 1f),
                isTripped = false,
                affectedMachines = new List<string> { "BantamCNC", "xArm", "Niryo" },
                requiresManualReset = true
            });

            // Safety mat in collaborative zone
            interlocks.Add(new SafetyInterlock
            {
                interlockId = "MAT_COLLAB",
                interlockName = "Collaborative Zone Safety Mat",
                interlockType = InterlockType.SafetyMat,
                position = new Vector3(0, 0, 0.3f),
                size = new Vector3(1.5f, 0.02f, 0.5f),
                isTripped = false,
                affectedMachines = new List<string> { "xArm", "Niryo" },
                requiresManualReset = false
            });

            // CNC door interlock
            interlocks.Add(new SafetyInterlock
            {
                interlockId = "DOOR_CNC",
                interlockName = "CNC Enclosure Door",
                interlockType = InterlockType.DoorSwitch,
                position = new Vector3(0, 0.4f, -0.2f),
                isTripped = false,
                affectedMachines = new List<string> { "BantamCNC" },
                requiresManualReset = true
            });

            // Emergency stop button
            interlocks.Add(new SafetyInterlock
            {
                interlockId = "ESTOP_MAIN",
                interlockName = "Main Emergency Stop",
                interlockType = InterlockType.EmergencyStop,
                position = new Vector3(0.8f, 1f, 0.8f),
                isTripped = false,
                affectedMachines = new List<string> { "BantamCNC", "xArm", "Niryo" },
                requiresManualReset = true
            });
        }

        // =========================================================================
        // Zone Scanning
        // =========================================================================

        private void ScanAllZones()
        {
            int totalViolations = 0;
            SafetyLevel highestLevel = SafetyLevel.Normal;

            foreach (var zone in safetyZones)
            {
                if (!zone.isEnabled)
                {
                    continue;
                }

                var violationResult = ScanZone(zone);

                if (violationResult.hasViolation)
                {
                    totalViolations++;

                    if (violationResult.level > highestLevel)
                    {
                        highestLevel = violationResult.level;
                    }

                    // Check if this is a new violation
                    string violationKey = $"{zone.zoneId}_{violationResult.objectName}";

                    if (!activeViolationMap.ContainsKey(violationKey))
                    {
                        var violation = new SafetyViolation
                        {
                            violationId = $"VIO_{DateTime.Now.Ticks}",
                            zone = zone,
                            violationType = violationResult.level == SafetyLevel.Danger ?
                                ViolationType.DangerZoneIntrusion : ViolationType.WarningZoneIntrusion,
                            objectName = violationResult.objectName,
                            startTime = DateTime.Now,
                            distance = violationResult.distance,
                            isActive = true
                        };

                        activeViolationMap[violationKey] = violation;
                        zone.isViolated = true;

                        // Trigger safety response
                        HandleViolation(zone, violation);

                        OnZoneViolation?.Invoke(zone, violation);

                        Debug.LogWarning($"[Safety] VIOLATION: {zone.zoneName} - {violationResult.objectName} at {violationResult.distance:F2}m");
                    }
                }
                else
                {
                    // Check for cleared violations
                    var keysToRemove = new List<string>();
                    foreach (var kvp in activeViolationMap)
                    {
                        if (kvp.Value.zone.zoneId == zone.zoneId)
                        {
                            kvp.Value.isActive = false;
                            kvp.Value.endTime = DateTime.Now;
                            violationHistory.Add(kvp.Value);
                            keysToRemove.Add(kvp.Key);
                        }
                    }

                    foreach (var key in keysToRemove)
                    {
                        activeViolationMap.Remove(key);
                    }

                    if (keysToRemove.Count > 0)
                    {
                        zone.isViolated = false;
                        OnZoneCleared?.Invoke(zone);
                        Debug.Log($"[Safety] Zone cleared: {zone.zoneName}");
                    }
                }
            }

            activeViolations = totalViolations;

            // Update safety level
            if (highestLevel != currentSafetyLevel)
            {
                currentSafetyLevel = highestLevel;
                OnSafetyLevelChanged?.Invoke(currentSafetyLevel);
            }

            // Cleanup history
            while (violationHistory.Count > MaxHistorySize)
            {
                violationHistory.RemoveAt(0);
            }
        }

        private (bool hasViolation, SafetyLevel level, string objectName, float distance) ScanZone(SafetyZone zone)
        {
            Collider[] colliders;

            switch (zone.shape)
            {
                case ZoneShape.Box:
                    colliders = Physics.OverlapBox(zone.center, zone.size / 2f, Quaternion.identity, detectionLayers);
                    break;
                case ZoneShape.Sphere:
                    colliders = Physics.OverlapSphere(zone.center, zone.radius, detectionLayers);
                    break;
                case ZoneShape.Cylinder:
                    // Approximate cylinder with sphere
                    colliders = Physics.OverlapSphere(zone.center, zone.radius, detectionLayers);
                    break;
                default:
                    colliders = new Collider[0];
                    break;
            }

            foreach (var collider in colliders)
            {
                // Skip if it's a machine or zone itself
                if (IsMachineObject(collider.gameObject))
                {
                    continue;
                }

                float distance = Vector3.Distance(collider.transform.position, zone.center);

                SafetyLevel level = SafetyLevel.Normal;

                if (distance < zone.dangerDistance || IsInsideZone(zone, collider.transform.position))
                {
                    level = SafetyLevel.Danger;
                }
                else if (distance < zone.warningDistance)
                {
                    level = SafetyLevel.Warning;
                }

                if (level != SafetyLevel.Normal)
                {
                    return (true, level, collider.gameObject.name, distance);
                }
            }

            return (false, SafetyLevel.Normal, null, float.MaxValue);
        }

        private bool IsInsideZone(SafetyZone zone, Vector3 point)
        {
            switch (zone.shape)
            {
                case ZoneShape.Box:
                    Vector3 halfSize = zone.size / 2f;
                    Vector3 localPoint = point - zone.center;
                    return Mathf.Abs(localPoint.x) <= halfSize.x &&
                           Mathf.Abs(localPoint.y) <= halfSize.y &&
                           Mathf.Abs(localPoint.z) <= halfSize.z;

                case ZoneShape.Sphere:
                    return Vector3.Distance(point, zone.center) <= zone.radius;

                default:
                    return false;
            }
        }

        private bool IsMachineObject(GameObject obj)
        {
            // Check if object is part of a machine
            return obj.GetComponentInParent<CNCScada.Machines.BantamCNCController>() != null ||
                   obj.GetComponentInParent<CNCScada.Machines.XArmLite6Controller>() != null ||
                   obj.GetComponentInParent<CNCScada.Machines.NiryoNed2Controller>() != null;
        }

        private void HandleViolation(SafetyZone zone, SafetyViolation violation)
        {
            // Raise alarm
            var alarmSystem = FindObjectOfType<CNCScada.Alarms.AlarmSystem>();

            if (currentSafetyLevel == SafetyLevel.Danger)
            {
                alarmSystem?.RaiseAlarm("ROBOT_COLLISION", zone.associatedMachine,
                    $"Danger zone intrusion: {violation.objectName}");

                // Stop affected machine
                if (zone.requiresMachineStop)
                {
                    StopMachine(zone.associatedMachine);
                }
            }
            else if (currentSafetyLevel == SafetyLevel.Warning)
            {
                alarmSystem?.RaiseCustomAlarm(
                    "Safety Zone Warning",
                    $"Object detected in warning zone: {zone.zoneName}",
                    CNCScada.Alarms.AlarmSeverity.Medium,
                    CNCScada.Alarms.AlarmCategory.Safety,
                    zone.zoneId
                );

                // Reduce speed if required
                if (zone.requiresSpeedReduction)
                {
                    ReduceMachineSpeed(zone.associatedMachine, zone.maxSpeedPercent);
                }
            }
        }

        private void StopMachine(string machineId)
        {
            if (string.IsNullOrEmpty(machineId))
            {
                return;
            }

            Debug.Log($"[Safety] Stopping machine: {machineId}");

            // Find and stop machine
            switch (machineId)
            {
                case "BantamCNC":
                    var cnc = FindObjectOfType<CNCScada.Machines.BantamCNCController>();
                    cnc?.SetSpindleSpeed(0);
                    break;
                case "xArm":
                    var xarm = FindObjectOfType<CNCScada.Machines.XArmLite6Controller>();
                    xarm?.MoveToHome();
                    break;
                case "Niryo":
                    var niryo = FindObjectOfType<CNCScada.Machines.NiryoNed2Controller>();
                    niryo?.MoveToHome();
                    break;
            }
        }

        private void ReduceMachineSpeed(string machineId, float maxSpeedPercent)
        {
            Debug.Log($"[Safety] Reducing speed for {machineId} to {maxSpeedPercent}%");
            // Implement speed reduction logic
        }

        // =========================================================================
        // Interlock Management
        // =========================================================================

        private void CheckInterlocks()
        {
            foreach (var interlock in interlocks)
            {
                if (!interlock.isEnabled)
                {
                    continue;
                }

                // Simulate interlock checking (in real implementation, read from hardware)
                bool previousState = interlock.isTripped;

                // For demo, check if objects are near interlock position
                if (interlock.interlockType == InterlockType.SafetyMat ||
                    interlock.interlockType == InterlockType.LightCurtain)
                {
                    var colliders = Physics.OverlapBox(
                        interlock.position,
                        interlock.size / 2f,
                        Quaternion.identity,
                        detectionLayers
                    );

                    interlock.isTripped = colliders.Length > 0;
                }

                if (interlock.isTripped != previousState)
                {
                    OnInterlockStateChanged?.Invoke(interlock, interlock.isTripped);

                    if (interlock.isTripped)
                    {
                        Debug.LogWarning($"[Safety] Interlock tripped: {interlock.interlockName}");

                        // Stop affected machines
                        foreach (var machineId in interlock.affectedMachines)
                        {
                            StopMachine(machineId);
                        }

                        // Raise alarm
                        var alarmSystem = FindObjectOfType<CNCScada.Alarms.AlarmSystem>();
                        alarmSystem?.RaiseCustomAlarm(
                            $"Interlock Tripped",
                            $"{interlock.interlockName} has been activated",
                            CNCScada.Alarms.AlarmSeverity.High,
                            CNCScada.Alarms.AlarmCategory.Safety,
                            interlock.interlockId
                        );
                    }
                }
            }
        }

        /// <summary>
        /// Trigger emergency stop
        /// </summary>
        public void TriggerEmergencyStop()
        {
            if (emergencyStopActive)
            {
                return;
            }

            emergencyStopActive = true;
            currentSafetyLevel = SafetyLevel.EmergencyStop;

            Debug.LogError("[Safety] EMERGENCY STOP ACTIVATED");

            // Stop all machines
            var manager = FindObjectOfType<CNCScada.Core.DigitalTwinManager>();
            manager?.EmergencyStopAll();

            // Set all E-stop interlocks
            foreach (var interlock in interlocks)
            {
                if (interlock.interlockType == InterlockType.EmergencyStop)
                {
                    interlock.isTripped = true;
                }
            }

            OnEmergencyStop?.Invoke();
            OnSafetyLevelChanged?.Invoke(SafetyLevel.EmergencyStop);
        }

        /// <summary>
        /// Reset emergency stop
        /// </summary>
        public void ResetEmergencyStop()
        {
            if (!emergencyStopActive)
            {
                return;
            }

            // Check all interlocks are clear
            foreach (var interlock in interlocks)
            {
                if (interlock.isTripped && interlock.requiresManualReset)
                {
                    Debug.LogWarning($"[Safety] Cannot reset E-stop: {interlock.interlockName} still tripped");
                    return;
                }
            }

            emergencyStopActive = false;
            currentSafetyLevel = SafetyLevel.Normal;

            // Clear E-stop interlocks
            foreach (var interlock in interlocks)
            {
                if (interlock.interlockType == InterlockType.EmergencyStop)
                {
                    interlock.isTripped = false;
                }
            }

            Debug.Log("[Safety] Emergency stop reset");

            OnEmergencyStopReset?.Invoke();
            OnSafetyLevelChanged?.Invoke(SafetyLevel.Normal);
        }

        /// <summary>
        /// Reset a specific interlock
        /// </summary>
        public void ResetInterlock(string interlockId)
        {
            var interlock = interlocks.Find(i => i.interlockId == interlockId);
            if (interlock != null)
            {
                interlock.isTripped = false;
                Debug.Log($"[Safety] Interlock reset: {interlock.interlockName}");
                OnInterlockStateChanged?.Invoke(interlock, false);
            }
        }

        // =========================================================================
        // Visualization
        // =========================================================================

        private void OnDrawGizmos()
        {
            if (!visualizeZones)
            {
                return;
            }

            foreach (var zone in safetyZones)
            {
                if (!zone.isEnabled)
                {
                    continue;
                }

                Color zoneColor = GetZoneColor(zone);
                Gizmos.color = new Color(zoneColor.r, zoneColor.g, zoneColor.b, 0.3f);

                switch (zone.shape)
                {
                    case ZoneShape.Box:
                        Gizmos.DrawCube(zone.center, zone.size);
                        Gizmos.color = new Color(zoneColor.r, zoneColor.g, zoneColor.b, 0.8f);
                        Gizmos.DrawWireCube(zone.center, zone.size);
                        break;
                    case ZoneShape.Sphere:
                        Gizmos.DrawSphere(zone.center, zone.radius);
                        Gizmos.color = new Color(zoneColor.r, zoneColor.g, zoneColor.b, 0.8f);
                        Gizmos.DrawWireSphere(zone.center, zone.radius);
                        break;
                }
            }

            // Draw interlocks
            Gizmos.color = Color.magenta;
            foreach (var interlock in interlocks)
            {
                if (interlock.isTripped)
                {
                    Gizmos.color = Color.red;
                }

                Gizmos.DrawWireCube(interlock.position, interlock.size);
            }
        }

        private Color GetZoneColor(SafetyZone zone)
        {
            if (zone.isViolated)
            {
                return Color.red;
            }

            switch (zone.zoneType)
            {
                case SafetyZoneType.DangerZone:
                    return new Color(1f, 0.3f, 0f); // Orange-red
                case SafetyZoneType.WarningZone:
                    return Color.yellow;
                case SafetyZoneType.RobotWorkspace:
                    return new Color(1f, 0.5f, 0f); // Orange
                case SafetyZoneType.CollaborativeZone:
                    return Color.green;
                default:
                    return Color.cyan;
            }
        }

        // =========================================================================
        // Public API
        // =========================================================================

        public List<SafetyZone> GetAllZones() => new List<SafetyZone>(safetyZones);
        public List<SafetyInterlock> GetAllInterlocks() => new List<SafetyInterlock>(interlocks);
        public List<SafetyViolation> GetActiveViolations() => new List<SafetyViolation>(activeViolationMap.Values);
        public List<SafetyViolation> GetViolationHistory() => new List<SafetyViolation>(violationHistory);

        public void AddZone(SafetyZone zone) => safetyZones.Add(zone);
        public void RemoveZone(string zoneId) => safetyZones.RemoveAll(z => z.zoneId == zoneId);
        public void EnableZone(string zoneId, bool enabled)
        {
            var zone = safetyZones.Find(z => z.zoneId == zoneId);
            if (zone != null) zone.isEnabled = enabled;
        }

        public void ArmSystem() { systemArmed = true; Debug.Log("[Safety] System armed"); }
        public void DisarmSystem() { systemArmed = false; Debug.Log("[Safety] System disarmed"); }

        // Properties
        public bool IsSystemArmed => systemArmed;
        public bool IsEmergencyStopActive => emergencyStopActive;
        public int ActiveViolationCount => activeViolations;
        public SafetyLevel CurrentSafetyLevel => currentSafetyLevel;
    }

    // =========================================================================
    // Data Types
    // =========================================================================

    public enum SafetyLevel
    {
        Normal,
        Warning,
        Danger,
        EmergencyStop
    }

    public enum SafetyZoneType
    {
        DangerZone,
        WarningZone,
        RobotWorkspace,
        CollaborativeZone,
        RestrictedArea
    }

    public enum ZoneShape
    {
        Box,
        Sphere,
        Cylinder
    }

    public enum InterlockType
    {
        LightCurtain,
        SafetyMat,
        DoorSwitch,
        EmergencyStop,
        TwoHandControl,
        SafetyScanner
    }

    public enum ViolationType
    {
        WarningZoneIntrusion,
        DangerZoneIntrusion,
        InterlockTripped,
        SpeedLimitExceeded,
        ForceOverload
    }

    [Serializable]
    public class SafetyZone
    {
        public string zoneId;
        public string zoneName;
        public SafetyZoneType zoneType;
        public ZoneShape shape;
        public Vector3 center;
        public Vector3 size;
        public float radius;
        public string associatedMachine;
        public bool isEnabled = true;
        public bool isViolated;
        public bool requiresMachineStop;
        public bool requiresSpeedReduction;
        public float maxSpeedPercent = 100;
        public float warningDistance;
        public float dangerDistance;
    }

    [Serializable]
    public class SafetyInterlock
    {
        public string interlockId;
        public string interlockName;
        public InterlockType interlockType;
        public Vector3 position;
        public Vector3 size = Vector3.one * 0.1f;
        public bool isEnabled = true;
        public bool isTripped;
        public bool requiresManualReset;
        public List<string> affectedMachines;
    }

    [Serializable]
    public class SafetyViolation
    {
        public string violationId;
        public SafetyZone zone;
        public ViolationType violationType;
        public string objectName;
        public DateTime startTime;
        public DateTime endTime;
        public float distance;
        public bool isActive;

        public TimeSpan Duration => isActive ? DateTime.Now - startTime : endTime - startTime;
    }
}
