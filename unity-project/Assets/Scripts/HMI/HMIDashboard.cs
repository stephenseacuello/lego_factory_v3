using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.UI;
using CNCDigitalTwin.Historian;
using CNC_SCADA.DigitalTwin.PLC;

namespace CNCDigitalTwin.HMI
{
    /// <summary>
    /// Enterprise HMI Dashboard for CNC SCADA Digital Twin
    /// Provides real-time machine visualization, alarms, trends, and operator controls
    /// </summary>
    public class HMIDashboard : MonoBehaviour
    {
        public static HMIDashboard Instance { get; private set; }

        [Header("Dashboard Configuration")]
        [SerializeField] private DashboardConfig config;
        [SerializeField] private float refreshRate = 10f; // Hz
        [SerializeField] private bool enableTouchMode = true;
        [SerializeField] private int maxActiveAlarms = 100;

        [Header("UI References")]
        [SerializeField] private Transform widgetContainer;
        [SerializeField] private Transform alarmBanner;
        [SerializeField] private Transform navigationBar;
        [SerializeField] private Canvas mainCanvas;

        // Widget registry
        private Dictionary<string, HMIWidget> widgets = new Dictionary<string, HMIWidget>();
        private Dictionary<string, ScreenDefinition> screens = new Dictionary<string, ScreenDefinition>();
        private string currentScreen = "main";

        // Data bindings
        private Dictionary<string, DataBinding> dataBindings = new Dictionary<string, DataBinding>();
        private Dictionary<string, object> tagValues = new Dictionary<string, object>();

        // Alarms
        private List<ActiveAlarm> activeAlarms = new List<ActiveAlarm>();
        private List<AlarmHistoryEntry> alarmHistory = new List<AlarmHistoryEntry>();
        private int unacknowledgedCount = 0;

        // Operator authentication
        private OperatorSession currentSession;
        private List<OperatorAction> auditLog = new List<OperatorAction>();

        // Events
        public event Action<HMIWidget> OnWidgetCreated;
        public event Action<string> OnScreenChanged;
        public event Action<ActiveAlarm> OnAlarmRaised;
        public event Action<ActiveAlarm> OnAlarmCleared;
        public event Action<ActiveAlarm> OnAlarmAcknowledged;
        public event Action<OperatorSession> OnOperatorLogin;
        public event Action<OperatorSession> OnOperatorLogout;
        public event Action<OperatorAction> OnOperatorAction;

        private Coroutine refreshCoroutine;

        void Awake()
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
        }

        void Start()
        {
            InitializeDefaultScreens();
            InitializeWidgetLibrary();
            LoadDashboardConfig();
            refreshCoroutine = StartCoroutine(RefreshLoop());
        }

        void OnDestroy()
        {
            if (refreshCoroutine != null)
                StopCoroutine(refreshCoroutine);
        }

        #region Screen Management

        private void InitializeDefaultScreens()
        {
            // Main overview screen
            DefineScreen(new ScreenDefinition
            {
                ScreenId = "main",
                Title = "Main Overview",
                Layout = ScreenLayout.Grid,
                RequiredRole = OperatorRole.Viewer,
                RefreshRate = 10f
            });

            // Machine status screen
            DefineScreen(new ScreenDefinition
            {
                ScreenId = "machine_status",
                Title = "Machine Status",
                Layout = ScreenLayout.Split,
                RequiredRole = OperatorRole.Viewer,
                RefreshRate = 20f
            });

            // Alarm management screen
            DefineScreen(new ScreenDefinition
            {
                ScreenId = "alarms",
                Title = "Alarm Management",
                Layout = ScreenLayout.List,
                RequiredRole = OperatorRole.Operator,
                RefreshRate = 5f
            });

            // Trends and history screen
            DefineScreen(new ScreenDefinition
            {
                ScreenId = "trends",
                Title = "Historical Trends",
                Layout = ScreenLayout.Canvas,
                RequiredRole = OperatorRole.Viewer,
                RefreshRate = 1f
            });

            // Production screen
            DefineScreen(new ScreenDefinition
            {
                ScreenId = "production",
                Title = "Production Dashboard",
                Layout = ScreenLayout.Grid,
                RequiredRole = OperatorRole.Viewer,
                RefreshRate = 5f
            });

            // Manual control screen
            DefineScreen(new ScreenDefinition
            {
                ScreenId = "manual_control",
                Title = "Manual Control",
                Layout = ScreenLayout.Custom,
                RequiredRole = OperatorRole.Operator,
                RefreshRate = 50f
            });

            // Configuration screen
            DefineScreen(new ScreenDefinition
            {
                ScreenId = "config",
                Title = "System Configuration",
                Layout = ScreenLayout.Form,
                RequiredRole = OperatorRole.Supervisor,
                RefreshRate = 1f
            });

            // Diagnostics screen
            DefineScreen(new ScreenDefinition
            {
                ScreenId = "diagnostics",
                Title = "Diagnostics",
                Layout = ScreenLayout.Split,
                RequiredRole = OperatorRole.Maintenance,
                RefreshRate = 10f
            });
        }

        public void DefineScreen(ScreenDefinition definition)
        {
            screens[definition.ScreenId] = definition;
            Debug.Log($"[HMI] Defined screen: {definition.ScreenId}");
        }

        public bool NavigateTo(string screenId)
        {
            if (!screens.TryGetValue(screenId, out var screen))
            {
                Debug.LogWarning($"[HMI] Screen not found: {screenId}");
                return false;
            }

            // Check authorization
            if (!IsAuthorized(screen.RequiredRole))
            {
                Debug.LogWarning($"[HMI] Access denied to screen: {screenId}");
                RaiseAlarm("HMI_ACCESS_DENIED", $"Unauthorized access attempt to {screen.Title}", AlarmSeverity.Medium);
                return false;
            }

            // Unload current screen widgets
            UnloadScreen(currentScreen);

            // Load new screen
            currentScreen = screenId;
            LoadScreen(screen);

            OnScreenChanged?.Invoke(screenId);
            LogOperatorAction("NAVIGATE", $"Navigated to {screen.Title}");

            return true;
        }

        private void LoadScreen(ScreenDefinition screen)
        {
            Debug.Log($"[HMI] Loading screen: {screen.Title}");
            // Widget instantiation would happen here based on screen configuration
        }

        private void UnloadScreen(string screenId)
        {
            var screenWidgets = widgets.Values
                .Where(w => w.ScreenId == screenId)
                .ToList();

            foreach (var widget in screenWidgets)
            {
                widget.Deactivate();
            }
        }

        #endregion

        #region Widget Management

        private void InitializeWidgetLibrary()
        {
            // Register built-in widget types
            RegisterWidgetType<NumericDisplayWidget>("numeric_display");
            RegisterWidgetType<GaugeWidget>("gauge");
            RegisterWidgetType<TrendChartWidget>("trend_chart");
            RegisterWidgetType<BarChartWidget>("bar_chart");
            RegisterWidgetType<StatusIndicatorWidget>("status_indicator");
            RegisterWidgetType<ButtonWidget>("button");
            RegisterWidgetType<SliderWidget>("slider");
            RegisterWidgetType<TextInputWidget>("text_input");
            RegisterWidgetType<AlarmListWidget>("alarm_list");
            RegisterWidgetType<MachineViewWidget>("machine_view");
            RegisterWidgetType<AxisDisplayWidget>("axis_display");
            RegisterWidgetType<SpindleDisplayWidget>("spindle_display");
            RegisterWidgetType<ProgramDisplayWidget>("program_display");
            RegisterWidgetType<OEEWidget>("oee_display");
            RegisterWidgetType<ProductionCounterWidget>("production_counter");
        }

        private Dictionary<string, Type> widgetTypes = new Dictionary<string, Type>();

        private void RegisterWidgetType<T>(string typeName) where T : HMIWidget
        {
            widgetTypes[typeName] = typeof(T);
        }

        public HMIWidget CreateWidget(WidgetConfig widgetConfig)
        {
            if (!widgetTypes.TryGetValue(widgetConfig.WidgetType, out var type))
            {
                Debug.LogWarning($"[HMI] Unknown widget type: {widgetConfig.WidgetType}");
                return null;
            }

            var widgetGO = new GameObject($"Widget_{widgetConfig.WidgetId}");
            widgetGO.transform.SetParent(widgetContainer);

            var widget = (HMIWidget)widgetGO.AddComponent(type);
            widget.Initialize(widgetConfig);

            widgets[widgetConfig.WidgetId] = widget;
            OnWidgetCreated?.Invoke(widget);

            // Set up data bindings
            foreach (var binding in widgetConfig.DataBindings)
            {
                BindData(widget, binding);
            }

            return widget;
        }

        public T GetWidget<T>(string widgetId) where T : HMIWidget
        {
            if (widgets.TryGetValue(widgetId, out var widget))
            {
                return widget as T;
            }
            return null;
        }

        public void RemoveWidget(string widgetId)
        {
            if (widgets.TryGetValue(widgetId, out var widget))
            {
                // Remove data bindings
                var bindingsToRemove = dataBindings
                    .Where(kvp => kvp.Value.WidgetId == widgetId)
                    .Select(kvp => kvp.Key)
                    .ToList();

                foreach (var key in bindingsToRemove)
                {
                    dataBindings.Remove(key);
                }

                Destroy(widget.gameObject);
                widgets.Remove(widgetId);
            }
        }

        #endregion

        #region Data Binding

        public void BindData(HMIWidget widget, DataBindingConfig bindingConfig)
        {
            var binding = new DataBinding
            {
                BindingId = $"{widget.WidgetId}_{bindingConfig.TagId}",
                WidgetId = widget.WidgetId,
                TagId = bindingConfig.TagId,
                Property = bindingConfig.Property,
                Mode = bindingConfig.Mode,
                Transform = bindingConfig.Transform,
                Format = bindingConfig.Format
            };

            dataBindings[binding.BindingId] = binding;

            // Subscribe to PLC tag if available
            if (PLCIntegration.Instance != null)
            {
                // Initial read
                var tag = PLCIntegration.Instance.GetTag(bindingConfig.TagId);
                if (tag != null)
                {
                    UpdateBinding(binding, tag.Value);
                }
            }
        }

        public void UnbindData(string widgetId, string tagId)
        {
            string key = $"{widgetId}_{tagId}";
            dataBindings.Remove(key);
        }

        public void SetTagValue(string tagId, object value)
        {
            tagValues[tagId] = value;

            // Update all widgets bound to this tag
            var bindings = dataBindings.Values
                .Where(b => b.TagId == tagId)
                .ToList();

            foreach (var binding in bindings)
            {
                UpdateBinding(binding, value);
            }

            // Write to historian
            if (DataHistorian.Instance != null)
            {
                DataHistorian.Instance.Write(tagId, value);
            }
        }

        public object GetTagValue(string tagId)
        {
            return tagValues.TryGetValue(tagId, out var value) ? value : null;
        }

        private void UpdateBinding(DataBinding binding, object value)
        {
            if (!widgets.TryGetValue(binding.WidgetId, out var widget))
                return;

            // Apply transform if configured
            object transformedValue = ApplyTransform(value, binding.Transform);

            // Apply format if configured
            string formattedValue = ApplyFormat(transformedValue, binding.Format);

            // Update widget property
            widget.UpdateProperty(binding.Property, transformedValue, formattedValue);
        }

        private object ApplyTransform(object value, DataTransform transform)
        {
            if (transform == null) return value;

            try
            {
                double numValue = Convert.ToDouble(value);

                switch (transform.Type)
                {
                    case TransformType.Scale:
                        return numValue * transform.Factor + transform.Offset;
                    case TransformType.Clamp:
                        return Math.Max(transform.Min, Math.Min(transform.Max, numValue));
                    case TransformType.Deadband:
                        return Math.Abs(numValue) < transform.Deadband ? 0 : numValue;
                    case TransformType.Map:
                        // Linear map from input range to output range
                        double normalized = (numValue - transform.InputMin) / (transform.InputMax - transform.InputMin);
                        return transform.OutputMin + normalized * (transform.OutputMax - transform.OutputMin);
                    default:
                        return value;
                }
            }
            catch
            {
                return value;
            }
        }

        private string ApplyFormat(object value, string format)
        {
            if (string.IsNullOrEmpty(format)) return value?.ToString() ?? "";

            try
            {
                if (value is double d)
                    return d.ToString(format);
                if (value is float f)
                    return f.ToString(format);
                if (value is int i)
                    return i.ToString(format);
                if (value is DateTime dt)
                    return dt.ToString(format);
                return value?.ToString() ?? "";
            }
            catch
            {
                return value?.ToString() ?? "";
            }
        }

        private IEnumerator RefreshLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(1f / refreshRate);
                RefreshBindings();
                RefreshAlarms();
            }
        }

        private void RefreshBindings()
        {
            // Update tag values from PLC
            if (PLCIntegration.Instance != null)
            {
                foreach (var binding in dataBindings.Values)
                {
                    var tag = PLCIntegration.Instance.GetTag(binding.TagId);
                    if (tag != null && tag.Value != null)
                    {
                        if (!tagValues.TryGetValue(binding.TagId, out var cached) ||
                            !Equals(cached, tag.Value))
                        {
                            SetTagValue(binding.TagId, tag.Value);
                        }
                    }
                }
            }
        }

        #endregion

        #region Alarm Management

        public void RaiseAlarm(string alarmId, string message, AlarmSeverity severity,
            Dictionary<string, object> context = null)
        {
            // Check if alarm is already active
            var existing = activeAlarms.FirstOrDefault(a => a.AlarmId == alarmId);
            if (existing != null)
            {
                // Update count for repeated alarm
                existing.OccurrenceCount++;
                existing.LastOccurrence = DateTime.UtcNow;
                return;
            }

            var alarm = new ActiveAlarm
            {
                AlarmId = alarmId,
                Message = message,
                Severity = severity,
                RaisedAt = DateTime.UtcNow,
                LastOccurrence = DateTime.UtcNow,
                OccurrenceCount = 1,
                Context = context ?? new Dictionary<string, object>(),
                State = AlarmState.Active,
                Priority = CalculateAlarmPriority(severity)
            };

            activeAlarms.Add(alarm);
            unacknowledgedCount++;

            // Sort by priority
            activeAlarms = activeAlarms.OrderByDescending(a => a.Priority).ToList();

            // Trim if over limit
            while (activeAlarms.Count > maxActiveAlarms)
            {
                var removed = activeAlarms.Last();
                activeAlarms.RemoveAt(activeAlarms.Count - 1);
                AddToHistory(removed, "AUTO_REMOVED");
            }

            OnAlarmRaised?.Invoke(alarm);

            // Log to audit
            LogOperatorAction("ALARM_RAISED", $"[{severity}] {alarmId}: {message}");

            Debug.Log($"[HMI] Alarm raised: [{severity}] {alarmId} - {message}");
        }

        public void ClearAlarm(string alarmId, string reason = "")
        {
            var alarm = activeAlarms.FirstOrDefault(a => a.AlarmId == alarmId);
            if (alarm == null) return;

            alarm.ClearedAt = DateTime.UtcNow;
            alarm.State = AlarmState.Cleared;

            activeAlarms.Remove(alarm);
            AddToHistory(alarm, reason);

            OnAlarmCleared?.Invoke(alarm);
            LogOperatorAction("ALARM_CLEARED", $"{alarmId}: {reason}");
        }

        public void AcknowledgeAlarm(string alarmId, string operatorNote = "")
        {
            var alarm = activeAlarms.FirstOrDefault(a => a.AlarmId == alarmId);
            if (alarm == null) return;

            alarm.AcknowledgedAt = DateTime.UtcNow;
            alarm.AcknowledgedBy = currentSession?.OperatorId ?? "SYSTEM";
            alarm.State = AlarmState.Acknowledged;
            alarm.OperatorNote = operatorNote;

            unacknowledgedCount = activeAlarms.Count(a => a.State == AlarmState.Active);

            OnAlarmAcknowledged?.Invoke(alarm);
            LogOperatorAction("ALARM_ACK", $"{alarmId}: {operatorNote}");
        }

        public void AcknowledgeAll()
        {
            foreach (var alarm in activeAlarms.Where(a => a.State == AlarmState.Active))
            {
                AcknowledgeAlarm(alarm.AlarmId, "Batch acknowledge");
            }
        }

        private int CalculateAlarmPriority(AlarmSeverity severity)
        {
            return severity switch
            {
                AlarmSeverity.Critical => 1000,
                AlarmSeverity.High => 750,
                AlarmSeverity.Medium => 500,
                AlarmSeverity.Low => 250,
                AlarmSeverity.Info => 100,
                _ => 0
            };
        }

        private void AddToHistory(ActiveAlarm alarm, string reason)
        {
            var entry = new AlarmHistoryEntry
            {
                AlarmId = alarm.AlarmId,
                Message = alarm.Message,
                Severity = alarm.Severity,
                RaisedAt = alarm.RaisedAt,
                ClearedAt = alarm.ClearedAt ?? DateTime.UtcNow,
                AcknowledgedAt = alarm.AcknowledgedAt,
                AcknowledgedBy = alarm.AcknowledgedBy,
                OccurrenceCount = alarm.OccurrenceCount,
                ClearReason = reason
            };

            alarmHistory.Insert(0, entry);

            // Limit history size
            if (alarmHistory.Count > 10000)
            {
                alarmHistory.RemoveRange(10000, alarmHistory.Count - 10000);
            }
        }

        private void RefreshAlarms()
        {
            // Check for stale alarms that should auto-clear
            var staleAlarms = activeAlarms
                .Where(a => a.AutoClearSeconds > 0 &&
                    (DateTime.UtcNow - a.LastOccurrence).TotalSeconds > a.AutoClearSeconds)
                .ToList();

            foreach (var alarm in staleAlarms)
            {
                ClearAlarm(alarm.AlarmId, "AUTO_CLEAR_TIMEOUT");
            }
        }

        public List<ActiveAlarm> GetActiveAlarms(AlarmSeverity? minSeverity = null)
        {
            if (minSeverity.HasValue)
            {
                return activeAlarms.Where(a => a.Severity >= minSeverity.Value).ToList();
            }
            return new List<ActiveAlarm>(activeAlarms);
        }

        public List<AlarmHistoryEntry> GetAlarmHistory(DateTime? start = null, DateTime? end = null,
            AlarmSeverity? minSeverity = null, int limit = 100)
        {
            var query = alarmHistory.AsEnumerable();

            if (start.HasValue)
                query = query.Where(a => a.RaisedAt >= start.Value);
            if (end.HasValue)
                query = query.Where(a => a.RaisedAt <= end.Value);
            if (minSeverity.HasValue)
                query = query.Where(a => a.Severity >= minSeverity.Value);

            return query.Take(limit).ToList();
        }

        #endregion

        #region Operator Authentication

        public bool Login(string operatorId, string password)
        {
            // In production, validate against authentication system
            var session = new OperatorSession
            {
                SessionId = Guid.NewGuid().ToString(),
                OperatorId = operatorId,
                LoginTime = DateTime.UtcNow,
                Role = DetermineOperatorRole(operatorId),
                IsActive = true
            };

            currentSession = session;
            OnOperatorLogin?.Invoke(session);
            LogOperatorAction("LOGIN", $"Operator {operatorId} logged in");

            Debug.Log($"[HMI] Operator logged in: {operatorId} ({session.Role})");
            return true;
        }

        public void Logout()
        {
            if (currentSession == null) return;

            currentSession.LogoutTime = DateTime.UtcNow;
            currentSession.IsActive = false;

            LogOperatorAction("LOGOUT", $"Operator {currentSession.OperatorId} logged out");
            OnOperatorLogout?.Invoke(currentSession);

            currentSession = null;

            // Navigate to login screen or main screen
            NavigateTo("main");
        }

        public bool IsAuthorized(OperatorRole requiredRole)
        {
            if (currentSession == null) return requiredRole == OperatorRole.Viewer;
            return currentSession.Role >= requiredRole;
        }

        private OperatorRole DetermineOperatorRole(string operatorId)
        {
            // In production, look up from database/LDAP
            if (operatorId.StartsWith("admin"))
                return OperatorRole.Administrator;
            if (operatorId.StartsWith("super"))
                return OperatorRole.Supervisor;
            if (operatorId.StartsWith("maint"))
                return OperatorRole.Maintenance;
            if (operatorId.StartsWith("eng"))
                return OperatorRole.Engineer;
            if (operatorId.StartsWith("op"))
                return OperatorRole.Operator;
            return OperatorRole.Viewer;
        }

        private void LogOperatorAction(string actionType, string description)
        {
            var action = new OperatorAction
            {
                ActionId = Guid.NewGuid().ToString(),
                Timestamp = DateTime.UtcNow,
                OperatorId = currentSession?.OperatorId ?? "SYSTEM",
                ActionType = actionType,
                Description = description,
                ScreenId = currentScreen
            };

            auditLog.Add(action);
            OnOperatorAction?.Invoke(action);

            // Limit audit log size
            if (auditLog.Count > 50000)
            {
                auditLog.RemoveRange(0, 10000);
            }
        }

        public List<OperatorAction> GetAuditLog(DateTime? start = null, DateTime? end = null,
            string operatorId = null, string actionType = null, int limit = 100)
        {
            var query = auditLog.AsEnumerable();

            if (start.HasValue)
                query = query.Where(a => a.Timestamp >= start.Value);
            if (end.HasValue)
                query = query.Where(a => a.Timestamp <= end.Value);
            if (!string.IsNullOrEmpty(operatorId))
                query = query.Where(a => a.OperatorId == operatorId);
            if (!string.IsNullOrEmpty(actionType))
                query = query.Where(a => a.ActionType == actionType);

            return query.OrderByDescending(a => a.Timestamp).Take(limit).ToList();
        }

        #endregion

        #region Commands & Control

        public bool ExecuteCommand(string commandId, Dictionary<string, object> parameters = null)
        {
            // Validate authorization
            var command = GetCommandDefinition(commandId);
            if (command == null)
            {
                Debug.LogWarning($"[HMI] Unknown command: {commandId}");
                return false;
            }

            if (!IsAuthorized(command.RequiredRole))
            {
                Debug.LogWarning($"[HMI] Unauthorized command attempt: {commandId}");
                RaiseAlarm("HMI_UNAUTHORIZED", $"Unauthorized command: {commandId}", AlarmSeverity.Medium);
                return false;
            }

            // Log the action
            LogOperatorAction("COMMAND", $"{commandId}: {string.Join(", ", parameters?.Select(p => $"{p.Key}={p.Value}") ?? Array.Empty<string>())}");

            // Execute the command
            switch (commandId)
            {
                case "MACHINE_START":
                    return ExecuteMachineStart();
                case "MACHINE_STOP":
                    return ExecuteMachineStop();
                case "EMERGENCY_STOP":
                    return ExecuteEmergencyStop();
                case "SPINDLE_ON":
                    return ExecuteSpindleOn(parameters);
                case "SPINDLE_OFF":
                    return ExecuteSpindleOff();
                case "JOG":
                    return ExecuteJog(parameters);
                case "HOME":
                    return ExecuteHome(parameters);
                case "PROGRAM_START":
                    return ExecuteProgramStart(parameters);
                case "PROGRAM_STOP":
                    return ExecuteProgramStop();
                case "PROGRAM_PAUSE":
                    return ExecuteProgramPause();
                case "RESET":
                    return ExecuteReset();
                default:
                    Debug.LogWarning($"[HMI] Unhandled command: {commandId}");
                    return false;
            }
        }

        private CommandDefinition GetCommandDefinition(string commandId)
        {
            // In production, load from configuration
            var commands = new Dictionary<string, CommandDefinition>
            {
                { "MACHINE_START", new CommandDefinition { CommandId = "MACHINE_START", RequiredRole = OperatorRole.Operator } },
                { "MACHINE_STOP", new CommandDefinition { CommandId = "MACHINE_STOP", RequiredRole = OperatorRole.Operator } },
                { "EMERGENCY_STOP", new CommandDefinition { CommandId = "EMERGENCY_STOP", RequiredRole = OperatorRole.Viewer } },
                { "SPINDLE_ON", new CommandDefinition { CommandId = "SPINDLE_ON", RequiredRole = OperatorRole.Operator } },
                { "SPINDLE_OFF", new CommandDefinition { CommandId = "SPINDLE_OFF", RequiredRole = OperatorRole.Operator } },
                { "JOG", new CommandDefinition { CommandId = "JOG", RequiredRole = OperatorRole.Operator } },
                { "HOME", new CommandDefinition { CommandId = "HOME", RequiredRole = OperatorRole.Operator } },
                { "PROGRAM_START", new CommandDefinition { CommandId = "PROGRAM_START", RequiredRole = OperatorRole.Operator } },
                { "PROGRAM_STOP", new CommandDefinition { CommandId = "PROGRAM_STOP", RequiredRole = OperatorRole.Operator } },
                { "PROGRAM_PAUSE", new CommandDefinition { CommandId = "PROGRAM_PAUSE", RequiredRole = OperatorRole.Operator } },
                { "RESET", new CommandDefinition { CommandId = "RESET", RequiredRole = OperatorRole.Maintenance } }
            };

            return commands.TryGetValue(commandId, out var cmd) ? cmd : null;
        }

        private bool ExecuteMachineStart()
        {
            Debug.Log("[HMI] Executing MACHINE_START");
            // Write to PLC
            if (PLCIntegration.Instance != null)
            {
                StartCoroutine(PLCIntegration.Instance.WriteTag("machine.control.start", true));
            }
            return true;
        }

        private bool ExecuteMachineStop()
        {
            Debug.Log("[HMI] Executing MACHINE_STOP");
            if (PLCIntegration.Instance != null)
            {
                StartCoroutine(PLCIntegration.Instance.WriteTag("machine.control.stop", true));
            }
            return true;
        }

        private bool ExecuteEmergencyStop()
        {
            Debug.Log("[HMI] Executing EMERGENCY_STOP");
            RaiseAlarm("ESTOP_PRESSED", "Emergency stop activated by operator", AlarmSeverity.Critical);
            if (PLCIntegration.Instance != null)
            {
                StartCoroutine(PLCIntegration.Instance.WriteTag("machine.control.estop", true));
            }
            return true;
        }

        private bool ExecuteSpindleOn(Dictionary<string, object> parameters)
        {
            float speed = 1000f;
            if (parameters != null && parameters.TryGetValue("speed", out var s))
            {
                speed = Convert.ToSingle(s);
            }
            Debug.Log($"[HMI] Executing SPINDLE_ON at {speed} RPM");
            return true;
        }

        private bool ExecuteSpindleOff()
        {
            Debug.Log("[HMI] Executing SPINDLE_OFF");
            return true;
        }

        private bool ExecuteJog(Dictionary<string, object> parameters)
        {
            if (parameters == null) return false;
            string axis = parameters.TryGetValue("axis", out var a) ? a.ToString() : "X";
            float distance = parameters.TryGetValue("distance", out var d) ? Convert.ToSingle(d) : 1.0f;
            Debug.Log($"[HMI] Executing JOG: {axis} by {distance}mm");
            return true;
        }

        private bool ExecuteHome(Dictionary<string, object> parameters)
        {
            string axes = parameters?.TryGetValue("axes", out var a) == true ? a.ToString() : "XYZ";
            Debug.Log($"[HMI] Executing HOME for axes: {axes}");
            return true;
        }

        private bool ExecuteProgramStart(Dictionary<string, object> parameters)
        {
            string programId = parameters?.TryGetValue("program", out var p) == true ? p.ToString() : "";
            Debug.Log($"[HMI] Executing PROGRAM_START: {programId}");
            return true;
        }

        private bool ExecuteProgramStop()
        {
            Debug.Log("[HMI] Executing PROGRAM_STOP");
            return true;
        }

        private bool ExecuteProgramPause()
        {
            Debug.Log("[HMI] Executing PROGRAM_PAUSE");
            return true;
        }

        private bool ExecuteReset()
        {
            Debug.Log("[HMI] Executing RESET");
            AcknowledgeAll();
            return true;
        }

        #endregion

        #region Configuration

        private void LoadDashboardConfig()
        {
            // Load default configuration
            if (config == null)
            {
                config = new DashboardConfig
                {
                    Theme = HMITheme.Dark,
                    Language = "en-US",
                    TimeZone = "UTC",
                    DateFormat = "yyyy-MM-dd HH:mm:ss"
                };
            }

            ApplyTheme(config.Theme);
        }

        public void ApplyTheme(HMITheme theme)
        {
            config.Theme = theme;

            var colors = GetThemeColors(theme);
            foreach (var widget in widgets.Values)
            {
                widget.ApplyTheme(colors);
            }
        }

        private ThemeColors GetThemeColors(HMITheme theme)
        {
            return theme switch
            {
                HMITheme.Light => new ThemeColors
                {
                    Background = new Color(0.95f, 0.95f, 0.95f),
                    Foreground = new Color(0.1f, 0.1f, 0.1f),
                    Primary = new Color(0.2f, 0.4f, 0.8f),
                    Secondary = new Color(0.4f, 0.6f, 0.9f),
                    Success = new Color(0.2f, 0.7f, 0.3f),
                    Warning = new Color(0.9f, 0.7f, 0.2f),
                    Error = new Color(0.8f, 0.2f, 0.2f),
                    AlarmCritical = new Color(0.9f, 0.1f, 0.1f),
                    AlarmHigh = new Color(0.9f, 0.5f, 0.1f),
                    AlarmMedium = new Color(0.9f, 0.9f, 0.1f),
                    AlarmLow = new Color(0.1f, 0.7f, 0.9f)
                },
                _ => new ThemeColors // Dark theme
                {
                    Background = new Color(0.1f, 0.1f, 0.12f),
                    Foreground = new Color(0.9f, 0.9f, 0.9f),
                    Primary = new Color(0.3f, 0.5f, 0.9f),
                    Secondary = new Color(0.5f, 0.7f, 1.0f),
                    Success = new Color(0.3f, 0.8f, 0.4f),
                    Warning = new Color(1.0f, 0.8f, 0.3f),
                    Error = new Color(0.9f, 0.3f, 0.3f),
                    AlarmCritical = new Color(1.0f, 0.2f, 0.2f),
                    AlarmHigh = new Color(1.0f, 0.6f, 0.2f),
                    AlarmMedium = new Color(1.0f, 1.0f, 0.2f),
                    AlarmLow = new Color(0.2f, 0.8f, 1.0f)
                }
            };
        }

        #endregion

        #region Statistics

        public HMIStats GetStatistics()
        {
            return new HMIStats
            {
                WidgetCount = widgets.Count,
                BindingCount = dataBindings.Count,
                ActiveAlarmCount = activeAlarms.Count,
                UnacknowledgedAlarmCount = unacknowledgedCount,
                CurrentScreen = currentScreen,
                CurrentOperator = currentSession?.OperatorId,
                SessionDuration = currentSession != null ? DateTime.UtcNow - currentSession.LoginTime : TimeSpan.Zero,
                AuditLogEntries = auditLog.Count
            };
        }

        #endregion
    }

    #region Widget Base Classes

    public abstract class HMIWidget : MonoBehaviour
    {
        public string WidgetId { get; private set; }
        public string ScreenId { get; private set; }
        protected WidgetConfig Config { get; private set; }

        public virtual void Initialize(WidgetConfig config)
        {
            WidgetId = config.WidgetId;
            ScreenId = config.ScreenId;
            Config = config;
        }

        public abstract void UpdateProperty(string property, object value, string formattedValue);
        public abstract void ApplyTheme(ThemeColors colors);
        public virtual void Activate() { gameObject.SetActive(true); }
        public virtual void Deactivate() { gameObject.SetActive(false); }
    }

    // Placeholder widget implementations
    public class NumericDisplayWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class GaugeWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class TrendChartWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class BarChartWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class StatusIndicatorWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class ButtonWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class SliderWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class TextInputWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class AlarmListWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class MachineViewWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class AxisDisplayWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class SpindleDisplayWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class ProgramDisplayWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class OEEWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    public class ProductionCounterWidget : HMIWidget
    {
        public override void UpdateProperty(string property, object value, string formattedValue) { }
        public override void ApplyTheme(ThemeColors colors) { }
    }

    #endregion

    #region Enums

    public enum ScreenLayout
    {
        Grid,
        Split,
        List,
        Canvas,
        Form,
        Custom
    }

    public enum OperatorRole
    {
        Viewer = 0,
        Operator = 1,
        Maintenance = 2,
        Engineer = 3,
        Supervisor = 4,
        Administrator = 5
    }

    public enum AlarmSeverity
    {
        Info = 0,
        Low = 1,
        Medium = 2,
        High = 3,
        Critical = 4
    }

    public enum AlarmState
    {
        Active,
        Acknowledged,
        Cleared
    }

    public enum BindingMode
    {
        OneWay,
        TwoWay,
        OneTime
    }

    public enum TransformType
    {
        None,
        Scale,
        Clamp,
        Deadband,
        Map
    }

    public enum HMITheme
    {
        Light,
        Dark,
        HighContrast
    }

    #endregion

    #region Data Classes

    [System.Serializable]
    public class DashboardConfig
    {
        public HMITheme Theme;
        public string Language;
        public string TimeZone;
        public string DateFormat;
        public List<ScreenConfig> Screens;
    }

    [System.Serializable]
    public class ScreenConfig
    {
        public string ScreenId;
        public List<WidgetConfig> Widgets;
    }

    [System.Serializable]
    public class ScreenDefinition
    {
        public string ScreenId;
        public string Title;
        public ScreenLayout Layout;
        public OperatorRole RequiredRole;
        public float RefreshRate;
    }

    [System.Serializable]
    public class WidgetConfig
    {
        public string WidgetId;
        public string WidgetType;
        public string ScreenId;
        public Vector2 Position;
        public Vector2 Size;
        public string Title;
        public List<DataBindingConfig> DataBindings;
        public Dictionary<string, object> Properties;
    }

    [System.Serializable]
    public class DataBindingConfig
    {
        public string TagId;
        public string Property;
        public BindingMode Mode;
        public DataTransform Transform;
        public string Format;
    }

    [System.Serializable]
    public class DataBinding
    {
        public string BindingId;
        public string WidgetId;
        public string TagId;
        public string Property;
        public BindingMode Mode;
        public DataTransform Transform;
        public string Format;
    }

    [System.Serializable]
    public class DataTransform
    {
        public TransformType Type;
        public double Factor;
        public double Offset;
        public double Min;
        public double Max;
        public double Deadband;
        public double InputMin;
        public double InputMax;
        public double OutputMin;
        public double OutputMax;
    }

    [System.Serializable]
    public class ActiveAlarm
    {
        public string AlarmId;
        public string Message;
        public AlarmSeverity Severity;
        public AlarmState State;
        public DateTime RaisedAt;
        public DateTime LastOccurrence;
        public DateTime? AcknowledgedAt;
        public DateTime? ClearedAt;
        public string AcknowledgedBy;
        public string OperatorNote;
        public int OccurrenceCount;
        public int Priority;
        public int AutoClearSeconds;
        public Dictionary<string, object> Context;
    }

    [System.Serializable]
    public class AlarmHistoryEntry
    {
        public string AlarmId;
        public string Message;
        public AlarmSeverity Severity;
        public DateTime RaisedAt;
        public DateTime ClearedAt;
        public DateTime? AcknowledgedAt;
        public string AcknowledgedBy;
        public int OccurrenceCount;
        public string ClearReason;
    }

    [System.Serializable]
    public class OperatorSession
    {
        public string SessionId;
        public string OperatorId;
        public OperatorRole Role;
        public DateTime LoginTime;
        public DateTime? LogoutTime;
        public bool IsActive;
    }

    [System.Serializable]
    public class OperatorAction
    {
        public string ActionId;
        public DateTime Timestamp;
        public string OperatorId;
        public string ActionType;
        public string Description;
        public string ScreenId;
    }

    [System.Serializable]
    public class CommandDefinition
    {
        public string CommandId;
        public string Description;
        public OperatorRole RequiredRole;
        public bool RequiresConfirmation;
        public Dictionary<string, CommandParameter> Parameters;
    }

    [System.Serializable]
    public class CommandParameter
    {
        public string Name;
        public string Type;
        public object DefaultValue;
        public bool Required;
    }

    [System.Serializable]
    public class ThemeColors
    {
        public Color Background;
        public Color Foreground;
        public Color Primary;
        public Color Secondary;
        public Color Success;
        public Color Warning;
        public Color Error;
        public Color AlarmCritical;
        public Color AlarmHigh;
        public Color AlarmMedium;
        public Color AlarmLow;
    }

    [System.Serializable]
    public class HMIStats
    {
        public int WidgetCount;
        public int BindingCount;
        public int ActiveAlarmCount;
        public int UnacknowledgedAlarmCount;
        public string CurrentScreen;
        public string CurrentOperator;
        public TimeSpan SessionDuration;
        public int AuditLogEntries;
    }

    #endregion
}
