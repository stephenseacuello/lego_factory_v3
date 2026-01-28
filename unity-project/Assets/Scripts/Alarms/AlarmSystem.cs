using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Events;

namespace CNCScada.Alarms
{
    /// <summary>
    /// Centralized alarm and notification system for the Digital Twin.
    /// Supports multiple alarm sources, severity levels, acknowledgment, and history.
    /// </summary>
    public class AlarmSystem : MonoBehaviour
    {
        [Header("Settings")]
        [SerializeField] private int maxActiveAlarms = 100;
        [SerializeField] private int maxHistorySize = 1000;
        [SerializeField] private bool enableAudioAlerts = true;
        [SerializeField] private bool enableVisualAlerts = true;

        [Header("Audio")]
        [SerializeField] private AudioSource audioSource;
        [SerializeField] private AudioClip criticalAlarmSound;
        [SerializeField] private AudioClip highAlarmSound;
        [SerializeField] private AudioClip mediumAlarmSound;
        [SerializeField] private AudioClip lowAlarmSound;

        [Header("Active Alarms")]
        [SerializeField] private List<Alarm> activeAlarms = new List<Alarm>();

        [Header("Statistics")]
        [SerializeField] private int totalAlarmsRaised;
        [SerializeField] private int unacknowledgedCount;
        [SerializeField] private AlarmSeverity highestActiveSeverity = AlarmSeverity.None;

        // Alarm history
        private Queue<AlarmHistoryEntry> alarmHistory = new Queue<AlarmHistoryEntry>();

        // Alarm definitions
        private Dictionary<string, AlarmDefinition> alarmDefinitions = new Dictionary<string, AlarmDefinition>();

        // Events
        public event Action<Alarm> OnAlarmRaised;
        public event Action<Alarm> OnAlarmCleared;
        public event Action<Alarm> OnAlarmAcknowledged;
        public event Action<AlarmSeverity> OnHighestSeverityChanged;

        // Unity Events for inspector binding
        [Header("Events")]
        public UnityEvent<Alarm> onAlarmRaised;
        public UnityEvent<Alarm> onAlarmCleared;

        // Singleton
        public static AlarmSystem Instance { get; private set; }

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

            InitializeDefaultAlarmDefinitions();
        }

        private void Start()
        {
            // Create audio source if not assigned
            if (audioSource == null && enableAudioAlerts)
            {
                audioSource = gameObject.AddComponent<AudioSource>();
                audioSource.playOnAwake = false;
            }
        }

        private void InitializeDefaultAlarmDefinitions()
        {
            // CNC Alarms
            RegisterAlarmDefinition(new AlarmDefinition
            {
                alarmId = "CNC_ESTOP",
                name = "Emergency Stop Active",
                description = "Emergency stop has been activated on the CNC machine",
                severity = AlarmSeverity.Critical,
                category = AlarmCategory.Safety,
                requiresAck = true
            });

            RegisterAlarmDefinition(new AlarmDefinition
            {
                alarmId = "CNC_SPINDLE_OVERLOAD",
                name = "Spindle Overload",
                description = "Spindle motor load exceeds safe limits",
                severity = AlarmSeverity.High,
                category = AlarmCategory.Equipment,
                requiresAck = true
            });

            RegisterAlarmDefinition(new AlarmDefinition
            {
                alarmId = "CNC_TEMP_HIGH",
                name = "High Temperature",
                description = "Machine temperature exceeds warning threshold",
                severity = AlarmSeverity.Medium,
                category = AlarmCategory.Equipment,
                requiresAck = false
            });

            RegisterAlarmDefinition(new AlarmDefinition
            {
                alarmId = "CNC_TOOL_WEAR",
                name = "Tool Wear Warning",
                description = "Tool approaching end of useful life",
                severity = AlarmSeverity.Low,
                category = AlarmCategory.Maintenance,
                requiresAck = false
            });

            RegisterAlarmDefinition(new AlarmDefinition
            {
                alarmId = "CNC_VIBRATION_HIGH",
                name = "High Vibration",
                description = "Abnormal vibration detected",
                severity = AlarmSeverity.Medium,
                category = AlarmCategory.Equipment,
                requiresAck = false
            });

            // Robot Alarms
            RegisterAlarmDefinition(new AlarmDefinition
            {
                alarmId = "ROBOT_COLLISION",
                name = "Collision Detected",
                description = "Robot has detected a collision or excessive force",
                severity = AlarmSeverity.Critical,
                category = AlarmCategory.Safety,
                requiresAck = true
            });

            RegisterAlarmDefinition(new AlarmDefinition
            {
                alarmId = "ROBOT_JOINT_LIMIT",
                name = "Joint Limit Reached",
                description = "Robot joint has reached its limit",
                severity = AlarmSeverity.High,
                category = AlarmCategory.Equipment,
                requiresAck = true
            });

            RegisterAlarmDefinition(new AlarmDefinition
            {
                alarmId = "ROBOT_COMM_LOSS",
                name = "Communication Loss",
                description = "Lost communication with robot controller",
                severity = AlarmSeverity.High,
                category = AlarmCategory.Communication,
                requiresAck = false
            });

            RegisterAlarmDefinition(new AlarmDefinition
            {
                alarmId = "ROBOT_GRIPPER_FAIL",
                name = "Gripper Failure",
                description = "Gripper failed to open/close properly",
                severity = AlarmSeverity.Medium,
                category = AlarmCategory.Equipment,
                requiresAck = true
            });

            // System Alarms
            RegisterAlarmDefinition(new AlarmDefinition
            {
                alarmId = "SYS_SERVER_DISCONNECT",
                name = "Server Disconnected",
                description = "Lost connection to Flask backend server",
                severity = AlarmSeverity.High,
                category = AlarmCategory.Communication,
                requiresAck = false
            });

            RegisterAlarmDefinition(new AlarmDefinition
            {
                alarmId = "SYS_SENSOR_FAIL",
                name = "Sensor Failure",
                description = "Sensor not responding or returning invalid data",
                severity = AlarmSeverity.Medium,
                category = AlarmCategory.Equipment,
                requiresAck = false
            });

            RegisterAlarmDefinition(new AlarmDefinition
            {
                alarmId = "SYS_SCHEDULE_CONFLICT",
                name = "Schedule Conflict",
                description = "Production schedule has conflicting operations",
                severity = AlarmSeverity.Low,
                category = AlarmCategory.Process,
                requiresAck = false
            });

            Debug.Log($"[AlarmSystem] Initialized {alarmDefinitions.Count} alarm definitions");
        }

        // =========================================================================
        // Alarm Management
        // =========================================================================

        /// <summary>
        /// Register a new alarm definition
        /// </summary>
        public void RegisterAlarmDefinition(AlarmDefinition definition)
        {
            alarmDefinitions[definition.alarmId] = definition;
        }

        /// <summary>
        /// Raise an alarm by ID
        /// </summary>
        public Alarm RaiseAlarm(string alarmId, string source = "", string additionalInfo = "")
        {
            if (!alarmDefinitions.TryGetValue(alarmId, out AlarmDefinition definition))
            {
                Debug.LogWarning($"[AlarmSystem] Unknown alarm ID: {alarmId}");
                return null;
            }

            // Check if alarm is already active
            var existing = activeAlarms.Find(a => a.alarmId == alarmId && a.source == source);
            if (existing != null)
            {
                // Update occurrence count
                existing.occurrenceCount++;
                existing.lastOccurrence = DateTime.Now;
                return existing;
            }

            // Create new alarm
            var alarm = new Alarm
            {
                alarmId = alarmId,
                name = definition.name,
                description = definition.description,
                severity = definition.severity,
                category = definition.category,
                source = source,
                additionalInfo = additionalInfo,
                raisedTime = DateTime.Now,
                lastOccurrence = DateTime.Now,
                occurrenceCount = 1,
                isAcknowledged = false,
                requiresAck = definition.requiresAck
            };

            // Add to active alarms
            if (activeAlarms.Count >= maxActiveAlarms)
            {
                // Remove oldest low-severity alarm
                var oldest = activeAlarms.Find(a => a.severity == AlarmSeverity.Low && a.isAcknowledged);
                if (oldest != null)
                {
                    activeAlarms.Remove(oldest);
                }
            }

            activeAlarms.Add(alarm);
            totalAlarmsRaised++;
            UpdateUnacknowledgedCount();
            UpdateHighestSeverity();

            // Add to history
            AddToHistory(alarm, AlarmAction.Raised);

            // Play audio alert
            PlayAlarmSound(alarm.severity);

            // Fire events
            OnAlarmRaised?.Invoke(alarm);
            onAlarmRaised?.Invoke(alarm);

            Debug.Log($"[AlarmSystem] ALARM: {alarm.name} [{alarm.severity}] - {alarm.source}");

            return alarm;
        }

        /// <summary>
        /// Raise a custom alarm (not from definition)
        /// </summary>
        public Alarm RaiseCustomAlarm(string name, string description, AlarmSeverity severity,
            AlarmCategory category, string source = "")
        {
            var alarm = new Alarm
            {
                alarmId = $"CUSTOM_{DateTime.Now.Ticks}",
                name = name,
                description = description,
                severity = severity,
                category = category,
                source = source,
                raisedTime = DateTime.Now,
                lastOccurrence = DateTime.Now,
                occurrenceCount = 1,
                isAcknowledged = false,
                requiresAck = severity >= AlarmSeverity.High
            };

            activeAlarms.Add(alarm);
            totalAlarmsRaised++;
            UpdateUnacknowledgedCount();
            UpdateHighestSeverity();

            AddToHistory(alarm, AlarmAction.Raised);
            PlayAlarmSound(alarm.severity);

            OnAlarmRaised?.Invoke(alarm);
            onAlarmRaised?.Invoke(alarm);

            return alarm;
        }

        /// <summary>
        /// Clear an alarm
        /// </summary>
        public void ClearAlarm(string alarmId, string source = "")
        {
            var alarm = activeAlarms.Find(a => a.alarmId == alarmId &&
                (string.IsNullOrEmpty(source) || a.source == source));

            if (alarm != null)
            {
                alarm.clearedTime = DateTime.Now;
                activeAlarms.Remove(alarm);

                UpdateUnacknowledgedCount();
                UpdateHighestSeverity();

                AddToHistory(alarm, AlarmAction.Cleared);

                OnAlarmCleared?.Invoke(alarm);
                onAlarmCleared?.Invoke(alarm);

                Debug.Log($"[AlarmSystem] Cleared: {alarm.name} - {alarm.source}");
            }
        }

        /// <summary>
        /// Acknowledge an alarm
        /// </summary>
        public void AcknowledgeAlarm(string alarmId, string acknowledgedBy = "Operator")
        {
            var alarm = activeAlarms.Find(a => a.alarmId == alarmId && !a.isAcknowledged);

            if (alarm != null)
            {
                alarm.isAcknowledged = true;
                alarm.acknowledgedTime = DateTime.Now;
                alarm.acknowledgedBy = acknowledgedBy;

                UpdateUnacknowledgedCount();

                AddToHistory(alarm, AlarmAction.Acknowledged);

                OnAlarmAcknowledged?.Invoke(alarm);

                Debug.Log($"[AlarmSystem] Acknowledged: {alarm.name} by {acknowledgedBy}");
            }
        }

        /// <summary>
        /// Acknowledge all active alarms
        /// </summary>
        public void AcknowledgeAll(string acknowledgedBy = "Operator")
        {
            foreach (var alarm in activeAlarms)
            {
                if (!alarm.isAcknowledged)
                {
                    alarm.isAcknowledged = true;
                    alarm.acknowledgedTime = DateTime.Now;
                    alarm.acknowledgedBy = acknowledgedBy;

                    AddToHistory(alarm, AlarmAction.Acknowledged);
                    OnAlarmAcknowledged?.Invoke(alarm);
                }
            }

            UpdateUnacknowledgedCount();
            Debug.Log($"[AlarmSystem] All alarms acknowledged by {acknowledgedBy}");
        }

        /// <summary>
        /// Clear all alarms (use with caution)
        /// </summary>
        public void ClearAll()
        {
            foreach (var alarm in activeAlarms.ToArray())
            {
                alarm.clearedTime = DateTime.Now;
                AddToHistory(alarm, AlarmAction.Cleared);
                OnAlarmCleared?.Invoke(alarm);
            }

            activeAlarms.Clear();
            UpdateUnacknowledgedCount();
            UpdateHighestSeverity();

            Debug.Log("[AlarmSystem] All alarms cleared");
        }

        // =========================================================================
        // Query Methods
        // =========================================================================

        /// <summary>
        /// Get all active alarms
        /// </summary>
        public List<Alarm> GetActiveAlarms()
        {
            return new List<Alarm>(activeAlarms);
        }

        /// <summary>
        /// Get alarms by severity
        /// </summary>
        public List<Alarm> GetAlarmsBySeverity(AlarmSeverity severity)
        {
            return activeAlarms.FindAll(a => a.severity == severity);
        }

        /// <summary>
        /// Get alarms by category
        /// </summary>
        public List<Alarm> GetAlarmsByCategory(AlarmCategory category)
        {
            return activeAlarms.FindAll(a => a.category == category);
        }

        /// <summary>
        /// Get alarms by source
        /// </summary>
        public List<Alarm> GetAlarmsBySource(string source)
        {
            return activeAlarms.FindAll(a => a.source == source);
        }

        /// <summary>
        /// Get unacknowledged alarms
        /// </summary>
        public List<Alarm> GetUnacknowledgedAlarms()
        {
            return activeAlarms.FindAll(a => !a.isAcknowledged);
        }

        /// <summary>
        /// Check if a specific alarm is active
        /// </summary>
        public bool IsAlarmActive(string alarmId, string source = "")
        {
            return activeAlarms.Exists(a => a.alarmId == alarmId &&
                (string.IsNullOrEmpty(source) || a.source == source));
        }

        /// <summary>
        /// Get alarm history
        /// </summary>
        public List<AlarmHistoryEntry> GetAlarmHistory()
        {
            return new List<AlarmHistoryEntry>(alarmHistory);
        }

        // =========================================================================
        // Private Methods
        // =========================================================================

        private void UpdateUnacknowledgedCount()
        {
            unacknowledgedCount = activeAlarms.FindAll(a => !a.isAcknowledged).Count;
        }

        private void UpdateHighestSeverity()
        {
            highestActiveSeverity = AlarmSeverity.None;

            foreach (var alarm in activeAlarms)
            {
                if (alarm.severity > highestActiveSeverity)
                {
                    highestActiveSeverity = alarm.severity;
                }
            }

            OnHighestSeverityChanged?.Invoke(highestActiveSeverity);
        }

        private void AddToHistory(Alarm alarm, AlarmAction action)
        {
            var entry = new AlarmHistoryEntry
            {
                alarm = alarm,
                action = action,
                timestamp = DateTime.Now
            };

            alarmHistory.Enqueue(entry);

            while (alarmHistory.Count > maxHistorySize)
            {
                alarmHistory.Dequeue();
            }
        }

        private void PlayAlarmSound(AlarmSeverity severity)
        {
            if (!enableAudioAlerts || audioSource == null) return;

            AudioClip clip = severity switch
            {
                AlarmSeverity.Critical => criticalAlarmSound,
                AlarmSeverity.High => highAlarmSound,
                AlarmSeverity.Medium => mediumAlarmSound,
                AlarmSeverity.Low => lowAlarmSound,
                _ => null
            };

            if (clip != null)
            {
                audioSource.PlayOneShot(clip);
            }
        }

        // Properties
        public int ActiveAlarmCount => activeAlarms.Count;
        public int UnacknowledgedCount => unacknowledgedCount;
        public AlarmSeverity HighestSeverity => highestActiveSeverity;
        public int TotalAlarmsRaised => totalAlarmsRaised;
    }

    // =========================================================================
    // Data Types
    // =========================================================================

    public enum AlarmSeverity
    {
        None = 0,
        Low = 1,
        Medium = 2,
        High = 3,
        Critical = 4
    }

    public enum AlarmCategory
    {
        Safety,
        Equipment,
        Process,
        Communication,
        Maintenance,
        Quality,
        System
    }

    public enum AlarmAction
    {
        Raised,
        Acknowledged,
        Cleared
    }

    [Serializable]
    public class AlarmDefinition
    {
        public string alarmId;
        public string name;
        public string description;
        public AlarmSeverity severity;
        public AlarmCategory category;
        public bool requiresAck;
    }

    [Serializable]
    public class Alarm
    {
        public string alarmId;
        public string name;
        public string description;
        public AlarmSeverity severity;
        public AlarmCategory category;
        public string source;
        public string additionalInfo;
        public DateTime raisedTime;
        public DateTime lastOccurrence;
        public int occurrenceCount;
        public bool isAcknowledged;
        public bool requiresAck;
        public DateTime acknowledgedTime;
        public string acknowledgedBy;
        public DateTime clearedTime;

        public TimeSpan Duration => (clearedTime != default ? clearedTime : DateTime.Now) - raisedTime;
    }

    [Serializable]
    public class AlarmHistoryEntry
    {
        public Alarm alarm;
        public AlarmAction action;
        public DateTime timestamp;
    }
}
