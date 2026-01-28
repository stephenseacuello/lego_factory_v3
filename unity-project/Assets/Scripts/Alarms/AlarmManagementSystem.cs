using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCDigitalTwin.Alarms
{
    /// <summary>
    /// Industrial Alarm Management System
    /// Implements ISA-18.2 / IEC 62682 alarm management lifecycle
    /// </summary>
    public class AlarmManagementSystem : MonoBehaviour
    {
        public static AlarmManagementSystem Instance { get; private set; }

        [Header("Configuration")]
        [SerializeField] private float scanInterval = 0.1f; // 100ms
        [SerializeField] private int maxActiveAlarms = 1000;
        [SerializeField] private int maxAlarmHistory = 10000;
        [SerializeField] private float deadbandPercentage = 2.0f;
        [SerializeField] private bool enableShelving = true;
        [SerializeField] private float maxShelveTimeMinutes = 480f; // 8 hours

        // Alarm definitions
        private Dictionary<string, AlarmDefinition> alarmDefinitions = new Dictionary<string, AlarmDefinition>();

        // Active alarms
        private Dictionary<string, ActiveAlarm> activeAlarms = new Dictionary<string, ActiveAlarm>();

        // Alarm history
        private Queue<AlarmHistoryEntry> alarmHistory = new Queue<AlarmHistoryEntry>();

        // Shelved alarms
        private Dictionary<string, ShelvedAlarm> shelvedAlarms = new Dictionary<string, ShelvedAlarm>();

        // Suppressed alarms
        private Dictionary<string, SuppressionRule> suppressionRules = new Dictionary<string, SuppressionRule>();

        // Alarm groups
        private Dictionary<string, AlarmGroup> alarmGroups = new Dictionary<string, AlarmGroup>();

        // Process variables
        private Dictionary<string, float> processVariables = new Dictionary<string, float>();

        // Statistics
        private AlarmStatistics statistics = new AlarmStatistics();

        // Events
        public event Action<ActiveAlarm> OnAlarmActivated;
        public event Action<ActiveAlarm> OnAlarmCleared;
        public event Action<ActiveAlarm, string> OnAlarmAcknowledged;
        public event Action<ActiveAlarm> OnAlarmEscalated;
        public event Action<string, ShelvedAlarm> OnAlarmShelved;
        public event Action<string> OnAlarmUnshelved;

        #region Data Structures

        [System.Serializable]
        public class AlarmDefinition
        {
            public string alarmId;
            public string tag;
            public string description;
            public AlarmType type;
            public AlarmPriority priority;
            public string groupId;

            // Setpoints
            public float highHighLimit;
            public float highLimit;
            public float lowLimit;
            public float lowLowLimit;
            public float deadband;

            // Timing
            public float onDelaySeconds;
            public float offDelaySeconds;
            public float rateOfChangeLimit;
            public float rateOfChangePeriod;

            // States
            public bool enabled;
            public bool isCritical;
            public string consequenceDescription;
            public string responseAction;
            public string equipmentId;

            // Escalation
            public bool enableEscalation;
            public float escalationTimeMinutes;
            public AlarmPriority escalatedPriority;
            public string[] notificationTargets;
        }

        public enum AlarmType
        {
            HighHigh,
            High,
            Low,
            LowLow,
            Deviation,
            RateOfChange,
            Discrete,
            Equipment,
            System,
            Diagnostic
        }

        public enum AlarmPriority
        {
            Diagnostic = 0,    // Informational
            Low = 1,           // No immediate action
            Medium = 2,        // Action within shift
            High = 3,          // Immediate action needed
            Critical = 4       // Emergency - immediate response
        }

        public enum AlarmState
        {
            Normal,            // Condition normal, not alarming
            Active,            // Alarm condition present
            Acknowledged,      // Alarm acknowledged by operator
            Cleared,           // Condition returned to normal
            Suppressed,        // Alarm suppressed by design
            Shelved,           // Temporarily shelved
            OutOfService       // Disabled/out of service
        }

        [System.Serializable]
        public class ActiveAlarm
        {
            public string alarmId;
            public string tag;
            public string description;
            public AlarmType type;
            public AlarmPriority priority;
            public AlarmState state;
            public DateTime activatedTime;
            public DateTime? acknowledgedTime;
            public DateTime? clearedTime;
            public string acknowledgedBy;
            public float triggerValue;
            public float setpoint;
            public int activationCount;
            public bool isEscalated;
            public string equipmentId;
            public string areaId;
        }

        [System.Serializable]
        public class AlarmHistoryEntry
        {
            public string alarmId;
            public string tag;
            public string description;
            public AlarmType type;
            public AlarmPriority priority;
            public AlarmEventType eventType;
            public DateTime timestamp;
            public float value;
            public string operatorId;
            public string comment;
            public TimeSpan? duration;
        }

        public enum AlarmEventType
        {
            Activated,
            Acknowledged,
            Cleared,
            Reset,
            Shelved,
            Unshelved,
            Suppressed,
            Unsuppressed,
            Escalated,
            PriorityChanged,
            Commented
        }

        [System.Serializable]
        public class ShelvedAlarm
        {
            public string alarmId;
            public string shelvedBy;
            public DateTime shelvedTime;
            public DateTime expiryTime;
            public string reason;
            public ShelveType shelveType;
        }

        public enum ShelveType
        {
            TimedShelve,
            OneShotShelve,
            OperatorShelve
        }

        [System.Serializable]
        public class SuppressionRule
        {
            public string ruleId;
            public string name;
            public string description;
            public SuppressionType type;
            public string[] alarmIds;
            public string conditionTag;
            public float conditionValue;
            public bool isActive;
            public DateTime? activeUntil;
        }

        public enum SuppressionType
        {
            ByDesign,          // Normal suppression (e.g., during startup)
            OutOfService,      // Equipment out of service
            Maintenance,       // Maintenance mode
            StateDependent,    // Dependent on process state
            ConditionalBased   // Based on another condition
        }

        [System.Serializable]
        public class AlarmGroup
        {
            public string groupId;
            public string name;
            public string description;
            public string areaId;
            public string[] alarmIds;
            public bool isEnabled;
            public int activeCount;
            public int unacknowledgedCount;
            public AlarmPriority highestPriority;
        }

        [System.Serializable]
        public class AlarmStatistics
        {
            public int totalDefinedAlarms;
            public int activeAlarmsCount;
            public int unacknowledgedCount;
            public int shelvedCount;
            public int suppressedCount;

            // ISA-18.2 KPIs
            public float alarmsPerHour;
            public float averageTimeToAcknowledge;
            public float averageAlarmDuration;
            public int standingAlarmCount;
            public int floodingAlarmCount;
            public int chattingAlarmCount;
            public int staleAlarmCount;

            // Priority distribution
            public int criticalCount;
            public int highCount;
            public int mediumCount;
            public int lowCount;
            public int diagnosticCount;

            // Time windows
            public DateTime statisticsStartTime;
            public int alarmsLast10Minutes;
            public int alarmsLastHour;
            public int alarmsLast24Hours;
        }

        // Alarm rate tracking
        private List<DateTime> alarmActivationTimes = new List<DateTime>();
        private Dictionary<string, List<DateTime>> alarmChatHistory = new Dictionary<string, List<DateTime>>();

        #endregion

        #region Unity Lifecycle

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
            }
        }

        private void Start()
        {
            InitializeSystem();
            StartCoroutine(AlarmScanLoop());
            StartCoroutine(ShelveExpiryLoop());
            StartCoroutine(StatisticsUpdateLoop());
        }

        private void OnDestroy()
        {
            StopAllCoroutines();
        }

        #endregion

        #region Initialization

        private void InitializeSystem()
        {
            Debug.Log("[AlarmMgmt] Initializing Industrial Alarm Management System");

            // Create default alarm groups
            CreateAlarmGroup("spindle", "Spindle System", "Spindle-related alarms", "machine");
            CreateAlarmGroup("axis", "Axis Systems", "Axis motion alarms", "machine");
            CreateAlarmGroup("coolant", "Coolant System", "Coolant and lubrication alarms", "machine");
            CreateAlarmGroup("hydraulic", "Hydraulic System", "Hydraulic pressure and flow alarms", "machine");
            CreateAlarmGroup("safety", "Safety System", "Safety interlock alarms", "safety");
            CreateAlarmGroup("quality", "Quality Control", "Quality and SPC alarms", "quality");
            CreateAlarmGroup("maintenance", "Maintenance", "Predictive maintenance alarms", "maintenance");

            // Create default alarm definitions
            CreateDefaultAlarmDefinitions();

            statistics.statisticsStartTime = DateTime.Now;
            Debug.Log($"[AlarmMgmt] Initialized with {alarmDefinitions.Count} alarm definitions");
        }

        private void CreateDefaultAlarmDefinitions()
        {
            // Spindle alarms
            CreateAnalogAlarm("ALM_SPINDLE_TEMP_HH", "SPINDLE_TEMP", "Spindle temperature very high",
                AlarmType.HighHigh, AlarmPriority.Critical, "spindle",
                highHighLimit: 85f, highLimit: 75f, lowLimit: 15f, lowLowLimit: 5f,
                deadband: 1f, consequenceDesc: "Spindle bearing damage", responseAction: "Stop machine immediately");

            CreateAnalogAlarm("ALM_SPINDLE_TEMP_H", "SPINDLE_TEMP", "Spindle temperature high",
                AlarmType.High, AlarmPriority.High, "spindle",
                highHighLimit: 85f, highLimit: 75f, lowLimit: 15f, lowLowLimit: 5f,
                deadband: 1f, consequenceDesc: "Reduced spindle life", responseAction: "Reduce speed, check cooling");

            CreateAnalogAlarm("ALM_SPINDLE_VIB_H", "SPINDLE_VIB", "Spindle vibration high",
                AlarmType.High, AlarmPriority.High, "spindle",
                highHighLimit: 10f, highLimit: 7f, lowLimit: 0f, lowLowLimit: 0f,
                deadband: 0.5f, consequenceDesc: "Poor surface finish", responseAction: "Check tool balance");

            CreateAnalogAlarm("ALM_SPINDLE_LOAD_H", "SPINDLE_LOAD", "Spindle load high",
                AlarmType.High, AlarmPriority.Medium, "spindle",
                highHighLimit: 120f, highLimit: 100f, lowLimit: 0f, lowLowLimit: 0f,
                deadband: 2f, consequenceDesc: "Tool breakage risk", responseAction: "Reduce feed rate");

            // Axis alarms
            CreateAnalogAlarm("ALM_AXIS_X_POS_ERR", "AXIS_X_FOLLOWING_ERR", "X axis following error high",
                AlarmType.High, AlarmPriority.High, "axis",
                highHighLimit: 0.1f, highLimit: 0.05f, lowLimit: -0.05f, lowLowLimit: -0.1f,
                deadband: 0.005f, consequenceDesc: "Part accuracy affected", responseAction: "Check servo parameters");

            CreateAnalogAlarm("ALM_AXIS_Y_POS_ERR", "AXIS_Y_FOLLOWING_ERR", "Y axis following error high",
                AlarmType.High, AlarmPriority.High, "axis",
                highHighLimit: 0.1f, highLimit: 0.05f, lowLimit: -0.05f, lowLowLimit: -0.1f,
                deadband: 0.005f, consequenceDesc: "Part accuracy affected", responseAction: "Check servo parameters");

            CreateAnalogAlarm("ALM_AXIS_Z_POS_ERR", "AXIS_Z_FOLLOWING_ERR", "Z axis following error high",
                AlarmType.High, AlarmPriority.High, "axis",
                highHighLimit: 0.1f, highLimit: 0.05f, lowLimit: -0.05f, lowLowLimit: -0.1f,
                deadband: 0.005f, consequenceDesc: "Part accuracy affected", responseAction: "Check servo parameters");

            // Coolant alarms
            CreateAnalogAlarm("ALM_COOLANT_PRESS_L", "COOLANT_PRESSURE", "Coolant pressure low",
                AlarmType.Low, AlarmPriority.Medium, "coolant",
                highHighLimit: 100f, highLimit: 80f, lowLimit: 30f, lowLowLimit: 20f,
                deadband: 2f, consequenceDesc: "Inadequate chip flushing", responseAction: "Check pump and filters");

            CreateAnalogAlarm("ALM_COOLANT_LEVEL_L", "COOLANT_LEVEL", "Coolant level low",
                AlarmType.Low, AlarmPriority.Medium, "coolant",
                highHighLimit: 100f, highLimit: 90f, lowLimit: 20f, lowLowLimit: 10f,
                deadband: 2f, consequenceDesc: "Pump cavitation risk", responseAction: "Refill coolant tank");

            CreateAnalogAlarm("ALM_COOLANT_TEMP_H", "COOLANT_TEMP", "Coolant temperature high",
                AlarmType.High, AlarmPriority.Medium, "coolant",
                highHighLimit: 45f, highLimit: 40f, lowLimit: 10f, lowLowLimit: 5f,
                deadband: 1f, consequenceDesc: "Thermal expansion effects", responseAction: "Check chiller");

            // Hydraulic alarms
            CreateAnalogAlarm("ALM_HYD_PRESS_L", "HYDRAULIC_PRESSURE", "Hydraulic pressure low",
                AlarmType.Low, AlarmPriority.High, "hydraulic",
                highHighLimit: 250f, highLimit: 220f, lowLimit: 150f, lowLowLimit: 120f,
                deadband: 5f, consequenceDesc: "Clamp force insufficient", responseAction: "Check hydraulic system");

            CreateAnalogAlarm("ALM_HYD_TEMP_H", "HYDRAULIC_TEMP", "Hydraulic oil temperature high",
                AlarmType.High, AlarmPriority.Medium, "hydraulic",
                highHighLimit: 65f, highLimit: 55f, lowLimit: 15f, lowLowLimit: 10f,
                deadband: 2f, consequenceDesc: "Oil degradation", responseAction: "Check cooler");

            // Safety alarms
            CreateDiscreteAlarm("ALM_ESTOP", "ESTOP_ACTIVE", "Emergency stop activated",
                AlarmPriority.Critical, "safety",
                consequenceDesc: "Machine stopped", responseAction: "Clear E-stop, verify safety");

            CreateDiscreteAlarm("ALM_DOOR_OPEN", "DOOR_INTERLOCK", "Safety door open during operation",
                AlarmPriority.Critical, "safety",
                consequenceDesc: "Machine stopped", responseAction: "Close door before resuming");

            CreateDiscreteAlarm("ALM_LIGHT_CURTAIN", "LIGHT_CURTAIN", "Light curtain interrupted",
                AlarmPriority.Critical, "safety",
                consequenceDesc: "Machine stopped", responseAction: "Clear intrusion");

            // Quality alarms
            CreateAnalogAlarm("ALM_SPC_OOC", "SPC_CONTROL_STATUS", "SPC out of control",
                AlarmType.High, AlarmPriority.High, "quality",
                highHighLimit: 2f, highLimit: 1f, lowLimit: 0f, lowLowLimit: 0f,
                deadband: 0.1f, consequenceDesc: "Process shift detected", responseAction: "Investigate root cause");

            CreateAnalogAlarm("ALM_CPK_LOW", "PROCESS_CPK", "Process capability low",
                AlarmType.Low, AlarmPriority.Medium, "quality",
                highHighLimit: 3f, highLimit: 2f, lowLimit: 1.33f, lowLowLimit: 1.0f,
                deadband: 0.1f, consequenceDesc: "Quality risk", responseAction: "Review process parameters");

            // Maintenance alarms
            CreateAnalogAlarm("ALM_TOOL_WEAR", "TOOL_WEAR_PCT", "Tool wear limit approaching",
                AlarmType.High, AlarmPriority.Medium, "maintenance",
                highHighLimit: 100f, highLimit: 80f, lowLimit: 0f, lowLowLimit: 0f,
                deadband: 2f, consequenceDesc: "Surface finish degradation", responseAction: "Schedule tool change");

            CreateAnalogAlarm("ALM_RUL_LOW", "REMAINING_USEFUL_LIFE", "Remaining useful life low",
                AlarmType.Low, AlarmPriority.Medium, "maintenance",
                highHighLimit: 1000f, highLimit: 500f, lowLimit: 100f, lowLowLimit: 50f,
                deadband: 10f, consequenceDesc: "Component failure risk", responseAction: "Schedule maintenance");
        }

        private void CreateAnalogAlarm(string alarmId, string tag, string description,
            AlarmType type, AlarmPriority priority, string groupId,
            float highHighLimit, float highLimit, float lowLimit, float lowLowLimit,
            float deadband, string consequenceDesc, string responseAction)
        {
            var definition = new AlarmDefinition
            {
                alarmId = alarmId,
                tag = tag,
                description = description,
                type = type,
                priority = priority,
                groupId = groupId,
                highHighLimit = highHighLimit,
                highLimit = highLimit,
                lowLimit = lowLimit,
                lowLowLimit = lowLowLimit,
                deadband = deadband,
                enabled = true,
                consequenceDescription = consequenceDesc,
                responseAction = responseAction,
                enableEscalation = priority >= AlarmPriority.High,
                escalationTimeMinutes = 15f,
                escalatedPriority = (AlarmPriority)Math.Min((int)priority + 1, (int)AlarmPriority.Critical)
            };

            alarmDefinitions[alarmId] = definition;

            // Add to group
            if (alarmGroups.TryGetValue(groupId, out var group))
            {
                var alarmIds = group.alarmIds?.ToList() ?? new List<string>();
                alarmIds.Add(alarmId);
                group.alarmIds = alarmIds.ToArray();
            }
        }

        private void CreateDiscreteAlarm(string alarmId, string tag, string description,
            AlarmPriority priority, string groupId,
            string consequenceDesc, string responseAction)
        {
            var definition = new AlarmDefinition
            {
                alarmId = alarmId,
                tag = tag,
                description = description,
                type = AlarmType.Discrete,
                priority = priority,
                groupId = groupId,
                enabled = true,
                isCritical = priority >= AlarmPriority.Critical,
                consequenceDescription = consequenceDesc,
                responseAction = responseAction,
                enableEscalation = priority >= AlarmPriority.High,
                escalationTimeMinutes = 5f,
                escalatedPriority = AlarmPriority.Critical
            };

            alarmDefinitions[alarmId] = definition;

            if (alarmGroups.TryGetValue(groupId, out var group))
            {
                var alarmIds = group.alarmIds?.ToList() ?? new List<string>();
                alarmIds.Add(alarmId);
                group.alarmIds = alarmIds.ToArray();
            }
        }

        private void CreateAlarmGroup(string groupId, string name, string description, string areaId)
        {
            alarmGroups[groupId] = new AlarmGroup
            {
                groupId = groupId,
                name = name,
                description = description,
                areaId = areaId,
                alarmIds = new string[0],
                isEnabled = true
            };
        }

        #endregion

        #region Alarm Processing

        private IEnumerator AlarmScanLoop()
        {
            while (true)
            {
                ScanAllAlarms();
                CheckEscalations();
                yield return new WaitForSeconds(scanInterval);
            }
        }

        private void ScanAllAlarms()
        {
            foreach (var kvp in alarmDefinitions)
            {
                var definition = kvp.Value;

                if (!definition.enabled)
                    continue;

                if (IsAlarmSuppressed(definition.alarmId))
                    continue;

                if (IsAlarmShelved(definition.alarmId))
                    continue;

                // Get current value
                if (!processVariables.TryGetValue(definition.tag, out float currentValue))
                    continue;

                // Evaluate alarm condition
                bool alarmCondition = EvaluateAlarmCondition(definition, currentValue);

                // Handle state transitions
                ProcessAlarmState(definition, alarmCondition, currentValue);
            }
        }

        private bool EvaluateAlarmCondition(AlarmDefinition definition, float value)
        {
            switch (definition.type)
            {
                case AlarmType.HighHigh:
                    return value >= definition.highHighLimit;

                case AlarmType.High:
                    if (activeAlarms.ContainsKey(definition.alarmId))
                        return value >= (definition.highLimit - definition.deadband);
                    return value >= definition.highLimit;

                case AlarmType.Low:
                    if (activeAlarms.ContainsKey(definition.alarmId))
                        return value <= (definition.lowLimit + definition.deadband);
                    return value <= definition.lowLimit;

                case AlarmType.LowLow:
                    return value <= definition.lowLowLimit;

                case AlarmType.Discrete:
                    return value != 0;

                case AlarmType.RateOfChange:
                    // Rate of change calculation would require historical data
                    return false;

                case AlarmType.Deviation:
                    float setpoint = definition.highLimit; // Use as setpoint
                    float deviation = Mathf.Abs(value - setpoint);
                    return deviation > definition.deadband;

                default:
                    return false;
            }
        }

        private void ProcessAlarmState(AlarmDefinition definition, bool alarmCondition, float currentValue)
        {
            bool isCurrentlyActive = activeAlarms.ContainsKey(definition.alarmId);

            if (alarmCondition && !isCurrentlyActive)
            {
                // New alarm activation
                ActivateAlarm(definition, currentValue);
            }
            else if (!alarmCondition && isCurrentlyActive)
            {
                // Alarm clearing
                var active = activeAlarms[definition.alarmId];

                if (active.state == AlarmState.Active || active.state == AlarmState.Acknowledged)
                {
                    ClearAlarm(definition.alarmId, currentValue);
                }
            }
        }

        private void ActivateAlarm(AlarmDefinition definition, float triggerValue)
        {
            // Check for alarm chattering
            if (IsAlarmChattering(definition.alarmId))
            {
                Debug.LogWarning($"[AlarmMgmt] Alarm {definition.alarmId} is chattering");
                return;
            }

            var alarm = new ActiveAlarm
            {
                alarmId = definition.alarmId,
                tag = definition.tag,
                description = definition.description,
                type = definition.type,
                priority = definition.priority,
                state = AlarmState.Active,
                activatedTime = DateTime.Now,
                triggerValue = triggerValue,
                setpoint = GetSetpointForAlarm(definition),
                activationCount = GetActivationCount(definition.alarmId) + 1,
                equipmentId = definition.equipmentId
            };

            activeAlarms[definition.alarmId] = alarm;

            // Track activation time
            alarmActivationTimes.Add(DateTime.Now);
            TrackAlarmChat(definition.alarmId);

            // Add to history
            AddHistoryEntry(alarm, AlarmEventType.Activated, triggerValue, null, null);

            // Update statistics
            UpdatePriorityCount(definition.priority, 1);
            statistics.activeAlarmsCount++;
            statistics.unacknowledgedCount++;

            // Update group
            UpdateAlarmGroup(definition.groupId);

            Debug.Log($"[AlarmMgmt] ALARM ACTIVATED: {definition.alarmId} - {definition.description} (Value: {triggerValue})");
            OnAlarmActivated?.Invoke(alarm);
        }

        private void ClearAlarm(string alarmId, float value)
        {
            if (!activeAlarms.TryGetValue(alarmId, out var alarm))
                return;

            alarm.state = AlarmState.Cleared;
            alarm.clearedTime = DateTime.Now;

            // Calculate duration
            var duration = DateTime.Now - alarm.activatedTime;

            // Add to history
            AddHistoryEntry(alarm, AlarmEventType.Cleared, value, null, null);

            // If acknowledged, remove from active
            if (alarm.acknowledgedTime.HasValue)
            {
                activeAlarms.Remove(alarmId);
                UpdatePriorityCount(alarm.priority, -1);
                statistics.activeAlarmsCount--;
            }

            // Update group
            if (alarmDefinitions.TryGetValue(alarmId, out var def))
            {
                UpdateAlarmGroup(def.groupId);
            }

            Debug.Log($"[AlarmMgmt] ALARM CLEARED: {alarmId} (Duration: {duration.TotalMinutes:F1} min)");
            OnAlarmCleared?.Invoke(alarm);
        }

        #endregion

        #region Operator Actions

        public bool AcknowledgeAlarm(string alarmId, string operatorId, string comment = null)
        {
            if (!activeAlarms.TryGetValue(alarmId, out var alarm))
            {
                Debug.LogWarning($"[AlarmMgmt] Cannot acknowledge - alarm not active: {alarmId}");
                return false;
            }

            if (alarm.state != AlarmState.Active)
            {
                Debug.LogWarning($"[AlarmMgmt] Alarm already acknowledged: {alarmId}");
                return false;
            }

            alarm.state = AlarmState.Acknowledged;
            alarm.acknowledgedTime = DateTime.Now;
            alarm.acknowledgedBy = operatorId;

            statistics.unacknowledgedCount--;

            // Calculate time to acknowledge
            var timeToAck = (DateTime.Now - alarm.activatedTime).TotalSeconds;
            UpdateAverageTimeToAcknowledge(timeToAck);

            // Add to history
            AddHistoryEntry(alarm, AlarmEventType.Acknowledged, 0, operatorId, comment);

            // Update group
            if (alarmDefinitions.TryGetValue(alarmId, out var def))
            {
                UpdateAlarmGroup(def.groupId);
            }

            // If already cleared, remove from active
            if (alarm.clearedTime.HasValue)
            {
                activeAlarms.Remove(alarmId);
                UpdatePriorityCount(alarm.priority, -1);
                statistics.activeAlarmsCount--;
            }

            Debug.Log($"[AlarmMgmt] Alarm acknowledged: {alarmId} by {operatorId}");
            OnAlarmAcknowledged?.Invoke(alarm, operatorId);

            return true;
        }

        public int AcknowledgeAllAlarms(string operatorId, AlarmPriority? maxPriority = null)
        {
            int count = 0;
            var alarmsToAck = activeAlarms.Values
                .Where(a => a.state == AlarmState.Active)
                .Where(a => !maxPriority.HasValue || a.priority <= maxPriority.Value)
                .Select(a => a.alarmId)
                .ToList();

            foreach (var alarmId in alarmsToAck)
            {
                if (AcknowledgeAlarm(alarmId, operatorId))
                    count++;
            }

            Debug.Log($"[AlarmMgmt] Acknowledged {count} alarms");
            return count;
        }

        public bool ShelveAlarm(string alarmId, string operatorId, float durationMinutes, string reason)
        {
            if (!enableShelving)
            {
                Debug.LogWarning("[AlarmMgmt] Shelving is disabled");
                return false;
            }

            if (!alarmDefinitions.ContainsKey(alarmId))
            {
                Debug.LogWarning($"[AlarmMgmt] Unknown alarm: {alarmId}");
                return false;
            }

            // Limit shelve duration
            durationMinutes = Mathf.Min(durationMinutes, maxShelveTimeMinutes);

            var shelved = new ShelvedAlarm
            {
                alarmId = alarmId,
                shelvedBy = operatorId,
                shelvedTime = DateTime.Now,
                expiryTime = DateTime.Now.AddMinutes(durationMinutes),
                reason = reason,
                shelveType = ShelveType.TimedShelve
            };

            shelvedAlarms[alarmId] = shelved;
            statistics.shelvedCount++;

            // If currently active, change state
            if (activeAlarms.TryGetValue(alarmId, out var active))
            {
                active.state = AlarmState.Shelved;
                statistics.activeAlarmsCount--;
                statistics.unacknowledgedCount = Math.Max(0, statistics.unacknowledgedCount - 1);
            }

            Debug.Log($"[AlarmMgmt] Alarm shelved: {alarmId} for {durationMinutes} minutes by {operatorId}");
            OnAlarmShelved?.Invoke(alarmId, shelved);

            return true;
        }

        public bool UnshelveAlarm(string alarmId)
        {
            if (!shelvedAlarms.ContainsKey(alarmId))
            {
                return false;
            }

            shelvedAlarms.Remove(alarmId);
            statistics.shelvedCount--;

            Debug.Log($"[AlarmMgmt] Alarm unshelved: {alarmId}");
            OnAlarmUnshelved?.Invoke(alarmId);

            return true;
        }

        #endregion

        #region Suppression

        public void CreateSuppressionRule(string ruleId, string name, SuppressionType type,
            string[] alarmIds, string conditionTag = null, float conditionValue = 0, float? durationMinutes = null)
        {
            var rule = new SuppressionRule
            {
                ruleId = ruleId,
                name = name,
                type = type,
                alarmIds = alarmIds,
                conditionTag = conditionTag,
                conditionValue = conditionValue,
                isActive = true,
                activeUntil = durationMinutes.HasValue ? DateTime.Now.AddMinutes(durationMinutes.Value) : (DateTime?)null
            };

            suppressionRules[ruleId] = rule;

            statistics.suppressedCount += alarmIds.Length;
            Debug.Log($"[AlarmMgmt] Suppression rule created: {ruleId} affecting {alarmIds.Length} alarms");
        }

        public void DeactivateSuppressionRule(string ruleId)
        {
            if (suppressionRules.TryGetValue(ruleId, out var rule))
            {
                rule.isActive = false;
                statistics.suppressedCount -= rule.alarmIds.Length;
            }
        }

        private bool IsAlarmSuppressed(string alarmId)
        {
            foreach (var rule in suppressionRules.Values)
            {
                if (!rule.isActive)
                    continue;

                if (rule.activeUntil.HasValue && DateTime.Now > rule.activeUntil.Value)
                {
                    rule.isActive = false;
                    continue;
                }

                if (rule.alarmIds.Contains(alarmId))
                {
                    // Check condition if state-dependent
                    if (rule.type == SuppressionType.ConditionalBased && !string.IsNullOrEmpty(rule.conditionTag))
                    {
                        if (processVariables.TryGetValue(rule.conditionTag, out float value))
                        {
                            if (value != rule.conditionValue)
                                continue;
                        }
                    }

                    return true;
                }
            }

            return false;
        }

        private bool IsAlarmShelved(string alarmId)
        {
            return shelvedAlarms.ContainsKey(alarmId);
        }

        #endregion

        #region Escalation

        private void CheckEscalations()
        {
            var now = DateTime.Now;

            foreach (var kvp in activeAlarms)
            {
                var alarm = kvp.Value;

                if (alarm.isEscalated || alarm.state != AlarmState.Active)
                    continue;

                if (!alarmDefinitions.TryGetValue(alarm.alarmId, out var definition))
                    continue;

                if (!definition.enableEscalation)
                    continue;

                var timeSinceActivation = (now - alarm.activatedTime).TotalMinutes;

                if (timeSinceActivation >= definition.escalationTimeMinutes)
                {
                    EscalateAlarm(alarm, definition);
                }
            }
        }

        private void EscalateAlarm(ActiveAlarm alarm, AlarmDefinition definition)
        {
            var originalPriority = alarm.priority;
            alarm.priority = definition.escalatedPriority;
            alarm.isEscalated = true;

            // Update statistics
            UpdatePriorityCount(originalPriority, -1);
            UpdatePriorityCount(alarm.priority, 1);

            // Add to history
            AddHistoryEntry(alarm, AlarmEventType.Escalated, 0, null,
                $"Escalated from {originalPriority} to {alarm.priority}");

            Debug.LogWarning($"[AlarmMgmt] ALARM ESCALATED: {alarm.alarmId} -> {alarm.priority}");
            OnAlarmEscalated?.Invoke(alarm);
        }

        #endregion

        #region Shelve Expiry

        private IEnumerator ShelveExpiryLoop()
        {
            while (true)
            {
                var now = DateTime.Now;
                var expiredShelves = shelvedAlarms
                    .Where(kvp => kvp.Value.expiryTime <= now)
                    .Select(kvp => kvp.Key)
                    .ToList();

                foreach (var alarmId in expiredShelves)
                {
                    UnshelveAlarm(alarmId);
                    Debug.Log($"[AlarmMgmt] Shelve expired for: {alarmId}");
                }

                yield return new WaitForSeconds(60f); // Check every minute
            }
        }

        #endregion

        #region Statistics

        private IEnumerator StatisticsUpdateLoop()
        {
            while (true)
            {
                UpdateStatistics();
                yield return new WaitForSeconds(10f);
            }
        }

        private void UpdateStatistics()
        {
            var now = DateTime.Now;

            // Clean old activation times
            alarmActivationTimes.RemoveAll(t => (now - t).TotalHours > 24);

            // Calculate rates
            statistics.alarmsLast10Minutes = alarmActivationTimes.Count(t => (now - t).TotalMinutes <= 10);
            statistics.alarmsLastHour = alarmActivationTimes.Count(t => (now - t).TotalHours <= 1);
            statistics.alarmsLast24Hours = alarmActivationTimes.Count;

            // Alarms per hour
            var hoursSinceStart = (now - statistics.statisticsStartTime).TotalHours;
            if (hoursSinceStart > 0)
            {
                statistics.alarmsPerHour = statistics.alarmsLast24Hours / (float)Math.Min(hoursSinceStart, 24);
            }

            // Flooding detection (>10 alarms in 10 minutes)
            statistics.floodingAlarmCount = statistics.alarmsLast10Minutes > 10 ? statistics.alarmsLast10Minutes : 0;

            // Standing alarms (active > 24 hours)
            statistics.standingAlarmCount = activeAlarms.Values
                .Count(a => (now - a.activatedTime).TotalHours > 24);

            // Stale alarms (acknowledged but not cleared > 8 hours)
            statistics.staleAlarmCount = activeAlarms.Values
                .Count(a => a.state == AlarmState.Acknowledged &&
                           a.acknowledgedTime.HasValue &&
                           (now - a.acknowledgedTime.Value).TotalHours > 8);

            // Total defined
            statistics.totalDefinedAlarms = alarmDefinitions.Count;

            // Update chattering count
            UpdateChatteringCount();
        }

        private void UpdatePriorityCount(AlarmPriority priority, int delta)
        {
            switch (priority)
            {
                case AlarmPriority.Critical:
                    statistics.criticalCount += delta;
                    break;
                case AlarmPriority.High:
                    statistics.highCount += delta;
                    break;
                case AlarmPriority.Medium:
                    statistics.mediumCount += delta;
                    break;
                case AlarmPriority.Low:
                    statistics.lowCount += delta;
                    break;
                case AlarmPriority.Diagnostic:
                    statistics.diagnosticCount += delta;
                    break;
            }
        }

        private void UpdateAverageTimeToAcknowledge(double seconds)
        {
            // Running average
            int n = statistics.alarmsLast24Hours;
            if (n > 0)
            {
                statistics.averageTimeToAcknowledge = statistics.averageTimeToAcknowledge +
                    ((float)seconds - statistics.averageTimeToAcknowledge) / n;
            }
        }

        private void UpdateAlarmGroup(string groupId)
        {
            if (!alarmGroups.TryGetValue(groupId, out var group))
                return;

            group.activeCount = activeAlarms.Values
                .Count(a => alarmDefinitions.TryGetValue(a.alarmId, out var def) && def.groupId == groupId);

            group.unacknowledgedCount = activeAlarms.Values
                .Count(a => a.state == AlarmState.Active &&
                           alarmDefinitions.TryGetValue(a.alarmId, out var def) && def.groupId == groupId);

            var groupAlarms = activeAlarms.Values
                .Where(a => alarmDefinitions.TryGetValue(a.alarmId, out var def) && def.groupId == groupId)
                .ToList();

            group.highestPriority = groupAlarms.Any() ? groupAlarms.Max(a => a.priority) : AlarmPriority.Diagnostic;
        }

        #endregion

        #region Chattering Detection

        private void TrackAlarmChat(string alarmId)
        {
            if (!alarmChatHistory.ContainsKey(alarmId))
            {
                alarmChatHistory[alarmId] = new List<DateTime>();
            }

            alarmChatHistory[alarmId].Add(DateTime.Now);

            // Keep only last hour
            alarmChatHistory[alarmId].RemoveAll(t => (DateTime.Now - t).TotalHours > 1);
        }

        private bool IsAlarmChattering(string alarmId)
        {
            if (!alarmChatHistory.TryGetValue(alarmId, out var history))
                return false;

            // Chattering: >5 activations in 10 minutes
            int recentCount = history.Count(t => (DateTime.Now - t).TotalMinutes <= 10);
            return recentCount >= 5;
        }

        private void UpdateChatteringCount()
        {
            statistics.chattingAlarmCount = alarmChatHistory.Values
                .Count(history => history.Count(t => (DateTime.Now - t).TotalMinutes <= 10) >= 5);
        }

        #endregion

        #region History

        private void AddHistoryEntry(ActiveAlarm alarm, AlarmEventType eventType, float value,
            string operatorId, string comment)
        {
            var entry = new AlarmHistoryEntry
            {
                alarmId = alarm.alarmId,
                tag = alarm.tag,
                description = alarm.description,
                type = alarm.type,
                priority = alarm.priority,
                eventType = eventType,
                timestamp = DateTime.Now,
                value = value,
                operatorId = operatorId,
                comment = comment
            };

            if (eventType == AlarmEventType.Cleared && alarm.activatedTime != default)
            {
                entry.duration = DateTime.Now - alarm.activatedTime;
            }

            alarmHistory.Enqueue(entry);

            while (alarmHistory.Count > maxAlarmHistory)
            {
                alarmHistory.Dequeue();
            }
        }

        public List<AlarmHistoryEntry> GetAlarmHistory(DateTime? startTime = null, DateTime? endTime = null,
            string alarmId = null, AlarmPriority? minPriority = null)
        {
            var query = alarmHistory.AsEnumerable();

            if (startTime.HasValue)
                query = query.Where(h => h.timestamp >= startTime.Value);
            if (endTime.HasValue)
                query = query.Where(h => h.timestamp <= endTime.Value);
            if (!string.IsNullOrEmpty(alarmId))
                query = query.Where(h => h.alarmId == alarmId);
            if (minPriority.HasValue)
                query = query.Where(h => h.priority >= minPriority.Value);

            return query.OrderByDescending(h => h.timestamp).ToList();
        }

        #endregion

        #region Process Variable Interface

        public void UpdateProcessVariable(string tag, float value)
        {
            processVariables[tag] = value;
        }

        public void UpdateProcessVariables(Dictionary<string, float> values)
        {
            foreach (var kvp in values)
            {
                processVariables[kvp.Key] = kvp.Value;
            }
        }

        #endregion

        #region Helpers

        private float GetSetpointForAlarm(AlarmDefinition definition)
        {
            switch (definition.type)
            {
                case AlarmType.HighHigh:
                    return definition.highHighLimit;
                case AlarmType.High:
                    return definition.highLimit;
                case AlarmType.Low:
                    return definition.lowLimit;
                case AlarmType.LowLow:
                    return definition.lowLowLimit;
                default:
                    return 0;
            }
        }

        private int GetActivationCount(string alarmId)
        {
            return alarmHistory.Count(h => h.alarmId == alarmId && h.eventType == AlarmEventType.Activated);
        }

        public List<ActiveAlarm> GetActiveAlarms(AlarmPriority? minPriority = null)
        {
            var query = activeAlarms.Values.AsEnumerable();

            if (minPriority.HasValue)
                query = query.Where(a => a.priority >= minPriority.Value);

            return query.OrderByDescending(a => a.priority)
                       .ThenBy(a => a.activatedTime)
                       .ToList();
        }

        public List<ActiveAlarm> GetUnacknowledgedAlarms()
        {
            return activeAlarms.Values
                .Where(a => a.state == AlarmState.Active)
                .OrderByDescending(a => a.priority)
                .ThenBy(a => a.activatedTime)
                .ToList();
        }

        public AlarmStatistics GetStatistics()
        {
            return statistics;
        }

        public List<AlarmGroup> GetAlarmGroups()
        {
            return alarmGroups.Values.ToList();
        }

        #endregion
    }
}
