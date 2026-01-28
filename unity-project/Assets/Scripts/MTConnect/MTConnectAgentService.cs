using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Xml.Linq;
using UnityEngine;

namespace CNCDigitalTwin.MTConnect
{
    /// <summary>
    /// MTConnect Agent/Adapter Service for CNC Digital Twin
    /// Full implementation of MTConnect standard for machine tool data exchange
    /// Supports MTConnect 1.8+ specification
    /// </summary>
    public class MTConnectAgentService : MonoBehaviour
    {
        public static MTConnectAgentService Instance { get; private set; }

        [Header("Agent Configuration")]
        [SerializeField] private string agentId = "CNC-AGENT-001";
        [SerializeField] private string agentName = "CNC Digital Twin Agent";
        [SerializeField] private string instanceId = "1";
        [SerializeField] private int bufferSize = 131072;
        [SerializeField] private int maxAssets = 1024;
        [SerializeField] private string schemaVersion = "1.8";

        [Header("Adapter Settings")]
        [SerializeField] private float heartbeatInterval = 10f; // seconds
        [SerializeField] private float sampleInterval = 0.1f; // 100ms
        [SerializeField] private bool enableShdr = true;
        [SerializeField] private int shdrPort = 7878;

        [Header("Device Configuration")]
        [SerializeField] private string deviceUuid = "";
        [SerializeField] private string deviceName = "CNC-MILL-001";
        [SerializeField] private string deviceManufacturer = "CNC Systems Inc";
        [SerializeField] private string deviceModel = "VMC-850";
        [SerializeField] private string deviceSerialNumber = "SN-2024-001";

        // Events
        public event Action<MTConnectDevice> OnDeviceRegistered;
        public event Action<DataItem, DataItemValue> OnDataItemChanged;
        public event Action<Condition> OnConditionChanged;
        public event Action<MTConnectAsset> OnAssetChanged;
        public event Action<string> OnShdrMessageReceived;
        public event Action<StreamRequest> OnStreamRequested;

        // Data structures
        private Dictionary<string, MTConnectDevice> devices = new Dictionary<string, MTConnectDevice>();
        private Dictionary<string, DataItem> dataItems = new Dictionary<string, DataItem>();
        private Dictionary<string, Component> components = new Dictionary<string, Component>();
        private Dictionary<string, MTConnectAsset> assets = new Dictionary<string, MTConnectAsset>();

        // Circular buffer for samples/events
        private CircularBuffer<SequenceItem> sampleBuffer;
        private long nextSequence = 1;
        private long firstSequence = 1;

        // State
        private bool isAgentRunning = false;
        private DateTime agentStartTime;

        // Statistics
        private MTConnectStats stats = new MTConnectStats();

        #region Data Structures

        public enum DataItemCategory
        {
            SAMPLE,
            EVENT,
            CONDITION
        }

        public enum DataItemType
        {
            // Samples
            POSITION,
            VELOCITY,
            ACCELERATION,
            ANGULAR_VELOCITY,
            PATH_FEEDRATE,
            PATH_POSITION,
            SPINDLE_SPEED,
            LOAD,
            TEMPERATURE,
            PRESSURE,
            FLOW,
            VOLTAGE,
            AMPERAGE,
            WATTAGE,
            POWER_FACTOR,
            FREQUENCY,
            VISCOSITY,
            CONCENTRATION,
            CONDUCTIVITY,
            DISPLACEMENT,
            ELECTRICAL_ENERGY,
            FILL_LEVEL,
            LINEAR_FORCE,
            MASS,
            PH,
            ROTARY_VELOCITY,
            SOUND_LEVEL,
            STRAIN,
            TILT,
            TORQUE,
            VIBRATION,

            // Events
            AVAILABILITY,
            EMERGENCY_STOP,
            CONTROLLER_MODE,
            EXECUTION,
            PROGRAM,
            PART_COUNT,
            BLOCK,
            LINE,
            MESSAGE,
            ALARM,
            TOOL_ID,
            TOOL_NUMBER,
            TOOL_OFFSET,
            AXIS_STATE,
            DOOR_STATE,
            CHUCK_STATE,
            ROTARY_MODE,
            PATH_MODE,
            COUPLED_AXES,
            INTERFACE_STATE,
            POWER_STATE,
            FUNCTIONAL_MODE,
            OPERATOR_ID,
            WORK_OFFSET,
            ACTIVE_AXES,

            // Conditions
            SYSTEM,
            LOGIC_PROGRAM,
            MOTION_PROGRAM,
            HARDWARE,
            DATA_RANGE,
            COMMUNICATIONS,
            ACTUATOR
        }

        public enum DataItemSubType
        {
            NONE,
            ACTUAL,
            COMMANDED,
            PROGRAMMED,
            TARGET,
            OVERRIDE,
            MAXIMUM,
            MINIMUM,
            PROBE,
            REMAINING,
            GOOD,
            BAD,
            ALL,
            REQUEST,
            RESPONSE
        }

        public enum ConditionState
        {
            UNAVAILABLE,
            NORMAL,
            WARNING,
            FAULT
        }

        public enum ControllerMode
        {
            AUTOMATIC,
            MANUAL,
            MANUAL_DATA_INPUT,
            SEMI_AUTOMATIC,
            EDIT,
            FEED_HOLD
        }

        public enum ExecutionState
        {
            UNAVAILABLE,
            READY,
            ACTIVE,
            INTERRUPTED,
            FEED_HOLD,
            STOPPED,
            OPTIONAL_STOP,
            PROGRAM_STOPPED,
            PROGRAM_COMPLETED
        }

        public enum EmergencyStopState
        {
            UNAVAILABLE,
            ARMED,
            TRIGGERED
        }

        public enum AvailabilityState
        {
            UNAVAILABLE,
            AVAILABLE
        }

        public class MTConnectDevice
        {
            public string Id { get; set; }
            public string Uuid { get; set; }
            public string Name { get; set; }
            public string Manufacturer { get; set; }
            public string Model { get; set; }
            public string SerialNumber { get; set; }
            public string Description { get; set; }
            public string NativeName { get; set; }
            public string SampleInterval { get; set; }
            public List<Component> Components { get; set; } = new List<Component>();
            public List<DataItem> DataItems { get; set; } = new List<DataItem>();
            public DateTime RegistrationTime { get; set; }
        }

        public class Component
        {
            public string Id { get; set; }
            public string Type { get; set; }
            public string Name { get; set; }
            public string NativeName { get; set; }
            public string Uuid { get; set; }
            public string ParentId { get; set; }
            public List<Component> SubComponents { get; set; } = new List<Component>();
            public List<DataItem> DataItems { get; set; } = new List<DataItem>();
        }

        public class DataItem
        {
            public string Id { get; set; }
            public string Name { get; set; }
            public DataItemType Type { get; set; }
            public DataItemCategory Category { get; set; }
            public DataItemSubType SubType { get; set; }
            public string Units { get; set; }
            public string NativeUnits { get; set; }
            public float? NativeScale { get; set; }
            public string CoordinateSystem { get; set; }
            public string ComponentId { get; set; }
            public string CompositionId { get; set; }
            public bool IsDiscrete { get; set; }
            public DataItemValue CurrentValue { get; set; }
            public DateTime LastChanged { get; set; }

            // Constraints
            public float? Minimum { get; set; }
            public float? Maximum { get; set; }
            public float? Nominal { get; set; }
            public List<string> Constraints { get; set; } = new List<string>();
        }

        public class DataItemValue
        {
            public long Sequence { get; set; }
            public DateTime Timestamp { get; set; }
            public object Value { get; set; }
            public string StringValue => Value?.ToString() ?? "UNAVAILABLE";
            public bool IsUnavailable => Value == null || StringValue == "UNAVAILABLE";
        }

        public class Condition
        {
            public string DataItemId { get; set; }
            public ConditionState State { get; set; }
            public string Type { get; set; }
            public string NativeCode { get; set; }
            public string NativeSeverity { get; set; }
            public string Qualifier { get; set; }
            public string Message { get; set; }
            public long Sequence { get; set; }
            public DateTime Timestamp { get; set; }
        }

        public class MTConnectAsset
        {
            public string AssetId { get; set; }
            public string Type { get; set; }
            public DateTime Timestamp { get; set; }
            public string DeviceUuid { get; set; }
            public bool Removed { get; set; }
            public Dictionary<string, object> Properties { get; set; } = new Dictionary<string, object>();
        }

        public class CuttingToolAsset : MTConnectAsset
        {
            public string ToolId { get; set; }
            public string Description { get; set; }
            public string Manufacturers { get; set; }
            public List<CuttingItem> CuttingItems { get; set; } = new List<CuttingItem>();
            public ToolLife ToolLife { get; set; }
            public List<Measurement> Measurements { get; set; } = new List<Measurement>();
        }

        public class CuttingItem
        {
            public string Indices { get; set; }
            public string ItemId { get; set; }
            public string Grade { get; set; }
            public string Manufacturers { get; set; }
            public List<CuttingItemLife> ItemLife { get; set; } = new List<CuttingItemLife>();
        }

        public class ToolLife
        {
            public string Type { get; set; } // MINUTES, PART_COUNT, WEAR
            public string CountDirection { get; set; } // UP, DOWN
            public float? Initial { get; set; }
            public float? Limit { get; set; }
            public float? Warning { get; set; }
            public float Value { get; set; }
        }

        public class CuttingItemLife
        {
            public string Type { get; set; }
            public float Value { get; set; }
            public float? Initial { get; set; }
            public float? Limit { get; set; }
        }

        public class Measurement
        {
            public string Type { get; set; }
            public float Value { get; set; }
            public string Units { get; set; }
            public float? Nominal { get; set; }
            public float? Minimum { get; set; }
            public float? Maximum { get; set; }
        }

        public class SequenceItem
        {
            public long Sequence { get; set; }
            public DateTime Timestamp { get; set; }
            public string DataItemId { get; set; }
            public object Value { get; set; }
            public ConditionState? ConditionState { get; set; }
        }

        public class StreamRequest
        {
            public string DeviceId { get; set; }
            public string Path { get; set; }
            public long? From { get; set; }
            public int? Count { get; set; }
            public int? Interval { get; set; }
            public long? Heartbeat { get; set; }
        }

        public class CircularBuffer<T>
        {
            private T[] buffer;
            private int head = 0;
            private int tail = 0;
            private int count = 0;
            private int capacity;

            public CircularBuffer(int capacity)
            {
                this.capacity = capacity;
                buffer = new T[capacity];
            }

            public void Add(T item)
            {
                buffer[head] = item;
                head = (head + 1) % capacity;
                if (count < capacity)
                    count++;
                else
                    tail = (tail + 1) % capacity;
            }

            public List<T> GetRange(int start, int length)
            {
                var result = new List<T>();
                int idx = (tail + start) % capacity;
                for (int i = 0; i < Math.Min(length, count - start); i++)
                {
                    result.Add(buffer[idx]);
                    idx = (idx + 1) % capacity;
                }
                return result;
            }

            public int Count => count;
            public int Capacity => capacity;
        }

        public class MTConnectStats
        {
            public DateTime StartTime { get; set; }
            public long TotalSamples { get; set; }
            public long TotalEvents { get; set; }
            public long TotalConditions { get; set; }
            public int ActiveDevices { get; set; }
            public int ActiveDataItems { get; set; }
            public int ActiveAssets { get; set; }
            public long BufferSequenceFirst { get; set; }
            public long BufferSequenceLast { get; set; }
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

            sampleBuffer = new CircularBuffer<SequenceItem>(bufferSize);

            if (string.IsNullOrEmpty(deviceUuid))
            {
                deviceUuid = Guid.NewGuid().ToString();
            }
        }

        private void Start()
        {
            agentStartTime = DateTime.Now;
            stats.StartTime = agentStartTime;

            // Register default device
            RegisterDefaultDevice();

            // Start agent
            StartAgent();

            Debug.Log($"[MTConnect] Agent started - ID: {agentId}, Version: {schemaVersion}");
        }

        private void RegisterDefaultDevice()
        {
            var device = new MTConnectDevice
            {
                Id = "d1",
                Uuid = deviceUuid,
                Name = deviceName,
                Manufacturer = deviceManufacturer,
                Model = deviceModel,
                SerialNumber = deviceSerialNumber,
                Description = "CNC Milling Machine Digital Twin",
                SampleInterval = "100",
                RegistrationTime = DateTime.Now
            };

            // Add Controller component
            var controller = new Component
            {
                Id = "cont",
                Type = "Controller",
                Name = "Controller",
                ParentId = device.Id
            };

            AddControllerDataItems(controller);
            device.Components.Add(controller);

            // Add Axes component
            var axes = new Component
            {
                Id = "axes",
                Type = "Axes",
                Name = "Axes",
                ParentId = device.Id
            };

            // Add Linear axes
            foreach (var axis in new[] { "X", "Y", "Z" })
            {
                var linear = new Component
                {
                    Id = $"linear_{axis.ToLower()}",
                    Type = "Linear",
                    Name = $"{axis} Axis",
                    NativeName = axis,
                    ParentId = axes.Id
                };

                AddAxisDataItems(linear, axis);
                axes.SubComponents.Add(linear);
            }

            // Add Rotary axis (Spindle)
            var spindle = new Component
            {
                Id = "spindle",
                Type = "Rotary",
                Name = "Spindle",
                NativeName = "S",
                ParentId = axes.Id
            };
            AddSpindleDataItems(spindle);
            axes.SubComponents.Add(spindle);

            device.Components.Add(axes);

            // Add Systems component
            var systems = new Component
            {
                Id = "systems",
                Type = "Systems",
                Name = "Systems",
                ParentId = device.Id
            };

            // Add Coolant system
            var coolant = new Component
            {
                Id = "coolant",
                Type = "Coolant",
                Name = "Coolant System",
                ParentId = systems.Id
            };
            AddCoolantDataItems(coolant);
            systems.SubComponents.Add(coolant);

            // Add Electric system
            var electric = new Component
            {
                Id = "electric",
                Type = "Electric",
                Name = "Electrical System",
                ParentId = systems.Id
            };
            AddElectricDataItems(electric);
            systems.SubComponents.Add(electric);

            device.Components.Add(systems);

            // Add Device-level availability
            var availability = CreateDataItem("avail", "Availability", DataItemType.AVAILABILITY,
                DataItemCategory.EVENT, device.Id);
            device.DataItems.Add(availability);

            RegisterDevice(device);
        }

        private void AddControllerDataItems(Component controller)
        {
            var items = new[]
            {
                CreateDataItem("mode", "ControllerMode", DataItemType.CONTROLLER_MODE, DataItemCategory.EVENT, controller.Id),
                CreateDataItem("exec", "Execution", DataItemType.EXECUTION, DataItemCategory.EVENT, controller.Id),
                CreateDataItem("estop", "EmergencyStop", DataItemType.EMERGENCY_STOP, DataItemCategory.EVENT, controller.Id),
                CreateDataItem("program", "Program", DataItemType.PROGRAM, DataItemCategory.EVENT, controller.Id),
                CreateDataItem("line", "Line", DataItemType.LINE, DataItemCategory.EVENT, controller.Id),
                CreateDataItem("block", "Block", DataItemType.BLOCK, DataItemCategory.EVENT, controller.Id),
                CreateDataItem("partcount", "PartCount", DataItemType.PART_COUNT, DataItemCategory.EVENT, controller.Id),
                CreateDataItem("message", "Message", DataItemType.MESSAGE, DataItemCategory.EVENT, controller.Id),
                CreateDataItem("cond_system", "SystemCondition", DataItemType.SYSTEM, DataItemCategory.CONDITION, controller.Id),
                CreateDataItem("cond_logic", "LogicCondition", DataItemType.LOGIC_PROGRAM, DataItemCategory.CONDITION, controller.Id),
                CreateDataItem("cond_motion", "MotionCondition", DataItemType.MOTION_PROGRAM, DataItemCategory.CONDITION, controller.Id)
            };

            controller.DataItems.AddRange(items);
        }

        private void AddAxisDataItems(Component axis, string axisName)
        {
            var items = new[]
            {
                CreateDataItem($"pos_{axisName.ToLower()}", $"{axisName}Position", DataItemType.POSITION,
                    DataItemCategory.SAMPLE, axis.Id, DataItemSubType.ACTUAL, "MILLIMETER"),
                CreateDataItem($"pos_cmd_{axisName.ToLower()}", $"{axisName}PositionCommanded", DataItemType.POSITION,
                    DataItemCategory.SAMPLE, axis.Id, DataItemSubType.COMMANDED, "MILLIMETER"),
                CreateDataItem($"vel_{axisName.ToLower()}", $"{axisName}Velocity", DataItemType.VELOCITY,
                    DataItemCategory.SAMPLE, axis.Id, DataItemSubType.ACTUAL, "MILLIMETER/SECOND"),
                CreateDataItem($"load_{axisName.ToLower()}", $"{axisName}Load", DataItemType.LOAD,
                    DataItemCategory.SAMPLE, axis.Id, DataItemSubType.ACTUAL, "PERCENT"),
                CreateDataItem($"temp_{axisName.ToLower()}", $"{axisName}Temperature", DataItemType.TEMPERATURE,
                    DataItemCategory.SAMPLE, axis.Id, DataItemSubType.ACTUAL, "CELSIUS"),
                CreateDataItem($"state_{axisName.ToLower()}", $"{axisName}AxisState", DataItemType.AXIS_STATE,
                    DataItemCategory.EVENT, axis.Id),
                CreateDataItem($"cond_{axisName.ToLower()}", $"{axisName}Condition", DataItemType.ACTUATOR,
                    DataItemCategory.CONDITION, axis.Id)
            };

            axis.DataItems.AddRange(items);
        }

        private void AddSpindleDataItems(Component spindle)
        {
            var items = new[]
            {
                CreateDataItem("spd_speed", "SpindleSpeed", DataItemType.SPINDLE_SPEED,
                    DataItemCategory.SAMPLE, spindle.Id, DataItemSubType.ACTUAL, "REVOLUTION/MINUTE"),
                CreateDataItem("spd_speed_cmd", "SpindleSpeedCommanded", DataItemType.SPINDLE_SPEED,
                    DataItemCategory.SAMPLE, spindle.Id, DataItemSubType.COMMANDED, "REVOLUTION/MINUTE"),
                CreateDataItem("spd_speed_ovr", "SpindleSpeedOverride", DataItemType.SPINDLE_SPEED,
                    DataItemCategory.SAMPLE, spindle.Id, DataItemSubType.OVERRIDE, "PERCENT"),
                CreateDataItem("spd_load", "SpindleLoad", DataItemType.LOAD,
                    DataItemCategory.SAMPLE, spindle.Id, DataItemSubType.ACTUAL, "PERCENT"),
                CreateDataItem("spd_torque", "SpindleTorque", DataItemType.TORQUE,
                    DataItemCategory.SAMPLE, spindle.Id, DataItemSubType.ACTUAL, "NEWTON_METER"),
                CreateDataItem("spd_temp", "SpindleTemperature", DataItemType.TEMPERATURE,
                    DataItemCategory.SAMPLE, spindle.Id, DataItemSubType.ACTUAL, "CELSIUS"),
                CreateDataItem("spd_state", "RotaryMode", DataItemType.ROTARY_MODE,
                    DataItemCategory.EVENT, spindle.Id),
                CreateDataItem("spd_cond", "SpindleCondition", DataItemType.ACTUATOR,
                    DataItemCategory.CONDITION, spindle.Id)
            };

            spindle.DataItems.AddRange(items);
        }

        private void AddCoolantDataItems(Component coolant)
        {
            var items = new[]
            {
                CreateDataItem("cool_temp", "CoolantTemperature", DataItemType.TEMPERATURE,
                    DataItemCategory.SAMPLE, coolant.Id, DataItemSubType.ACTUAL, "CELSIUS"),
                CreateDataItem("cool_level", "CoolantLevel", DataItemType.FILL_LEVEL,
                    DataItemCategory.SAMPLE, coolant.Id, DataItemSubType.ACTUAL, "PERCENT"),
                CreateDataItem("cool_flow", "CoolantFlow", DataItemType.FLOW,
                    DataItemCategory.SAMPLE, coolant.Id, DataItemSubType.ACTUAL, "LITER/MINUTE"),
                CreateDataItem("cool_pressure", "CoolantPressure", DataItemType.PRESSURE,
                    DataItemCategory.SAMPLE, coolant.Id, DataItemSubType.ACTUAL, "PASCAL"),
                CreateDataItem("cool_cond", "CoolantCondition", DataItemType.SYSTEM,
                    DataItemCategory.CONDITION, coolant.Id)
            };

            coolant.DataItems.AddRange(items);
        }

        private void AddElectricDataItems(Component electric)
        {
            var items = new[]
            {
                CreateDataItem("elec_voltage", "Voltage", DataItemType.VOLTAGE,
                    DataItemCategory.SAMPLE, electric.Id, DataItemSubType.ACTUAL, "VOLT"),
                CreateDataItem("elec_current", "Current", DataItemType.AMPERAGE,
                    DataItemCategory.SAMPLE, electric.Id, DataItemSubType.ACTUAL, "AMPERE"),
                CreateDataItem("elec_power", "Power", DataItemType.WATTAGE,
                    DataItemCategory.SAMPLE, electric.Id, DataItemSubType.ACTUAL, "WATT"),
                CreateDataItem("elec_energy", "Energy", DataItemType.ELECTRICAL_ENERGY,
                    DataItemCategory.SAMPLE, electric.Id, DataItemSubType.ACTUAL, "KILOWATT_HOUR"),
                CreateDataItem("elec_freq", "Frequency", DataItemType.FREQUENCY,
                    DataItemCategory.SAMPLE, electric.Id, DataItemSubType.ACTUAL, "HERTZ"),
                CreateDataItem("elec_pf", "PowerFactor", DataItemType.POWER_FACTOR,
                    DataItemCategory.SAMPLE, electric.Id, DataItemSubType.ACTUAL, "PERCENT"),
                CreateDataItem("power_state", "PowerState", DataItemType.POWER_STATE,
                    DataItemCategory.EVENT, electric.Id),
                CreateDataItem("elec_cond", "ElectricalCondition", DataItemType.SYSTEM,
                    DataItemCategory.CONDITION, electric.Id)
            };

            electric.DataItems.AddRange(items);
        }

        private DataItem CreateDataItem(string id, string name, DataItemType type,
            DataItemCategory category, string componentId,
            DataItemSubType subType = DataItemSubType.NONE, string units = null)
        {
            var item = new DataItem
            {
                Id = id,
                Name = name,
                Type = type,
                Category = category,
                SubType = subType,
                Units = units,
                ComponentId = componentId,
                CurrentValue = new DataItemValue
                {
                    Sequence = 0,
                    Timestamp = DateTime.Now,
                    Value = "UNAVAILABLE"
                },
                LastChanged = DateTime.Now
            };

            dataItems[id] = item;
            stats.ActiveDataItems++;

            return item;
        }

        #endregion

        #region Agent Operations

        public void StartAgent()
        {
            if (isAgentRunning) return;

            isAgentRunning = true;
            StartCoroutine(AgentHeartbeat());
            StartCoroutine(SampleLoop());

            if (enableShdr)
            {
                StartCoroutine(ShdrSimulator());
            }

            Debug.Log("[MTConnect] Agent started");
        }

        public void StopAgent()
        {
            isAgentRunning = false;
            StopAllCoroutines();
            Debug.Log("[MTConnect] Agent stopped");
        }

        private IEnumerator AgentHeartbeat()
        {
            while (isAgentRunning)
            {
                yield return new WaitForSeconds(heartbeatInterval);

                // Update availability
                SetDataItemValue("avail", AvailabilityState.AVAILABLE.ToString());

                stats.BufferSequenceFirst = firstSequence;
                stats.BufferSequenceLast = nextSequence - 1;
            }
        }

        private IEnumerator SampleLoop()
        {
            while (isAgentRunning)
            {
                yield return new WaitForSeconds(sampleInterval);

                // Simulate sensor data updates
                SimulateMachineData();
            }
        }

        private void SimulateMachineData()
        {
            float time = Time.time;

            // Position data (simulated motion)
            float xPos = 100f * Mathf.Sin(time * 0.5f);
            float yPos = 100f * Mathf.Cos(time * 0.5f);
            float zPos = 50f * Mathf.Sin(time * 0.3f);

            SetDataItemValue("pos_x", xPos);
            SetDataItemValue("pos_y", yPos);
            SetDataItemValue("pos_z", zPos);

            // Velocity
            SetDataItemValue("vel_x", Mathf.Cos(time * 0.5f) * 50f);
            SetDataItemValue("vel_y", -Mathf.Sin(time * 0.5f) * 50f);
            SetDataItemValue("vel_z", Mathf.Cos(time * 0.3f) * 15f);

            // Load
            SetDataItemValue("load_x", 20f + UnityEngine.Random.Range(-5f, 5f));
            SetDataItemValue("load_y", 25f + UnityEngine.Random.Range(-5f, 5f));
            SetDataItemValue("load_z", 15f + UnityEngine.Random.Range(-3f, 3f));

            // Spindle
            SetDataItemValue("spd_speed", 12000f + UnityEngine.Random.Range(-100f, 100f));
            SetDataItemValue("spd_load", 45f + UnityEngine.Random.Range(-5f, 5f));
            SetDataItemValue("spd_torque", 8.5f + UnityEngine.Random.Range(-0.5f, 0.5f));
            SetDataItemValue("spd_temp", 42f + UnityEngine.Random.Range(-1f, 1f));

            // Coolant
            SetDataItemValue("cool_temp", 22f + UnityEngine.Random.Range(-0.5f, 0.5f));
            SetDataItemValue("cool_level", 85f + UnityEngine.Random.Range(-2f, 2f));
            SetDataItemValue("cool_flow", 15f + UnityEngine.Random.Range(-1f, 1f));
            SetDataItemValue("cool_pressure", 500000f + UnityEngine.Random.Range(-10000f, 10000f));

            // Electrical
            SetDataItemValue("elec_voltage", 480f + UnityEngine.Random.Range(-5f, 5f));
            SetDataItemValue("elec_current", 35f + UnityEngine.Random.Range(-2f, 2f));
            SetDataItemValue("elec_power", 15000f + UnityEngine.Random.Range(-500f, 500f));
            SetDataItemValue("elec_freq", 60f + UnityEngine.Random.Range(-0.1f, 0.1f));
            SetDataItemValue("elec_pf", 0.92f + UnityEngine.Random.Range(-0.02f, 0.02f));
        }

        #endregion

        #region SHDR Protocol

        private IEnumerator ShdrSimulator()
        {
            // SHDR (Simple Host Data Representation) is the adapter protocol
            // Format: timestamp|key|value or timestamp|key1|value1|key2|value2...

            while (isAgentRunning)
            {
                yield return new WaitForSeconds(sampleInterval);

                // Build SHDR message
                var sb = new StringBuilder();
                var timestamp = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ");

                sb.Append(timestamp);

                // Add all sample data items
                foreach (var item in dataItems.Values.Where(d => d.Category == DataItemCategory.SAMPLE))
                {
                    if (item.CurrentValue != null && !item.CurrentValue.IsUnavailable)
                    {
                        sb.Append($"|{item.Id}|{item.CurrentValue.StringValue}");
                    }
                }

                string shdrMessage = sb.ToString();
                OnShdrMessageReceived?.Invoke(shdrMessage);
            }
        }

        public void ProcessShdrMessage(string message)
        {
            // Parse incoming SHDR message
            // Format: timestamp|key|value|key|value...
            // Or: |key|value|key|value... (no timestamp)

            try
            {
                var parts = message.Split('|');
                int startIndex = 0;
                DateTime timestamp = DateTime.UtcNow;

                // Check if first part is timestamp
                if (parts[0].Contains("-") || parts[0].Contains(":"))
                {
                    timestamp = DateTime.Parse(parts[0]);
                    startIndex = 1;
                }

                // Process key-value pairs
                for (int i = startIndex; i < parts.Length - 1; i += 2)
                {
                    string key = parts[i];
                    string value = parts[i + 1];

                    SetDataItemValue(key, value, timestamp);
                }
            }
            catch (Exception e)
            {
                Debug.LogError($"[MTConnect] SHDR parse error: {e.Message}");
            }
        }

        public string GenerateShdrOutput()
        {
            var sb = new StringBuilder();
            var timestamp = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ");
            sb.Append(timestamp);

            foreach (var item in dataItems.Values)
            {
                if (item.CurrentValue != null)
                {
                    sb.Append($"|{item.Id}|{item.CurrentValue.StringValue}");
                }
            }

            return sb.ToString();
        }

        #endregion

        #region Device/Data Management

        public void RegisterDevice(MTConnectDevice device)
        {
            devices[device.Id] = device;
            stats.ActiveDevices++;

            // Register all data items from components
            RegisterComponentDataItems(device.Components);

            foreach (var item in device.DataItems)
            {
                if (!dataItems.ContainsKey(item.Id))
                {
                    dataItems[item.Id] = item;
                    stats.ActiveDataItems++;
                }
            }

            OnDeviceRegistered?.Invoke(device);
            Debug.Log($"[MTConnect] Device registered: {device.Name} ({device.Uuid})");
        }

        private void RegisterComponentDataItems(List<Component> components)
        {
            foreach (var comp in components)
            {
                this.components[comp.Id] = comp;

                foreach (var item in comp.DataItems)
                {
                    if (!dataItems.ContainsKey(item.Id))
                    {
                        dataItems[item.Id] = item;
                        stats.ActiveDataItems++;
                    }
                }

                RegisterComponentDataItems(comp.SubComponents);
            }
        }

        public void SetDataItemValue(string dataItemId, object value, DateTime? timestamp = null)
        {
            if (!dataItems.TryGetValue(dataItemId, out var item))
            {
                Debug.LogWarning($"[MTConnect] Unknown data item: {dataItemId}");
                return;
            }

            var ts = timestamp ?? DateTime.UtcNow;
            var oldValue = item.CurrentValue;

            item.CurrentValue = new DataItemValue
            {
                Sequence = nextSequence++,
                Timestamp = ts,
                Value = value
            };

            item.LastChanged = ts;

            // Add to buffer
            sampleBuffer.Add(new SequenceItem
            {
                Sequence = item.CurrentValue.Sequence,
                Timestamp = ts,
                DataItemId = dataItemId,
                Value = value
            });

            // Update stats
            switch (item.Category)
            {
                case DataItemCategory.SAMPLE:
                    stats.TotalSamples++;
                    break;
                case DataItemCategory.EVENT:
                    stats.TotalEvents++;
                    break;
                case DataItemCategory.CONDITION:
                    stats.TotalConditions++;
                    break;
            }

            // Trim buffer
            while (sampleBuffer.Count >= bufferSize)
            {
                firstSequence++;
            }

            OnDataItemChanged?.Invoke(item, item.CurrentValue);
        }

        public void SetCondition(string dataItemId, ConditionState state, string nativeCode = null,
            string message = null, string qualifier = null)
        {
            if (!dataItems.TryGetValue(dataItemId, out var item))
                return;

            if (item.Category != DataItemCategory.CONDITION)
            {
                Debug.LogWarning($"[MTConnect] {dataItemId} is not a condition data item");
                return;
            }

            var condition = new Condition
            {
                DataItemId = dataItemId,
                State = state,
                Type = item.Type.ToString(),
                NativeCode = nativeCode,
                Message = message,
                Qualifier = qualifier,
                Sequence = nextSequence,
                Timestamp = DateTime.UtcNow
            };

            SetDataItemValue(dataItemId, state.ToString());

            OnConditionChanged?.Invoke(condition);
        }

        #endregion

        #region Asset Management

        public void RegisterAsset(MTConnectAsset asset)
        {
            if (assets.Count >= maxAssets)
            {
                // Remove oldest asset
                var oldest = assets.Values.OrderBy(a => a.Timestamp).First();
                assets.Remove(oldest.AssetId);
            }

            asset.Timestamp = DateTime.UtcNow;
            assets[asset.AssetId] = asset;
            stats.ActiveAssets++;

            OnAssetChanged?.Invoke(asset);
            Debug.Log($"[MTConnect] Asset registered: {asset.AssetId} ({asset.Type})");
        }

        public void RegisterCuttingTool(string toolId, string description, float diameter,
            float length, int flutes, float toolLifeMinutes)
        {
            var tool = new CuttingToolAsset
            {
                AssetId = $"CT_{toolId}",
                Type = "CuttingTool",
                ToolId = toolId,
                Description = description,
                DeviceUuid = deviceUuid,
                ToolLife = new ToolLife
                {
                    Type = "MINUTES",
                    CountDirection = "UP",
                    Initial = 0,
                    Limit = toolLifeMinutes,
                    Warning = toolLifeMinutes * 0.8f,
                    Value = 0
                },
                Measurements = new List<Measurement>
                {
                    new Measurement { Type = "CuttingDiameter", Value = diameter, Units = "MILLIMETER" },
                    new Measurement { Type = "BodyLength", Value = length, Units = "MILLIMETER" },
                    new Measurement { Type = "FluteCount", Value = flutes, Units = "COUNT" }
                }
            };

            RegisterAsset(tool);
        }

        public void UpdateToolLife(string toolId, float currentLifeMinutes)
        {
            string assetId = $"CT_{toolId}";
            if (assets.TryGetValue(assetId, out var asset) && asset is CuttingToolAsset tool)
            {
                tool.ToolLife.Value = currentLifeMinutes;
                tool.Timestamp = DateTime.UtcNow;
                OnAssetChanged?.Invoke(tool);
            }
        }

        public void RemoveAsset(string assetId)
        {
            if (assets.TryGetValue(assetId, out var asset))
            {
                asset.Removed = true;
                asset.Timestamp = DateTime.UtcNow;
                OnAssetChanged?.Invoke(asset);
                assets.Remove(assetId);
                stats.ActiveAssets--;
            }
        }

        #endregion

        #region XML Generation

        public string GenerateProbeResponse()
        {
            var doc = new XElement("MTConnectDevices",
                new XAttribute("xmlns", "urn:mtconnect.org:MTConnectDevices:1.8"),
                new XAttribute("schemaVersion", schemaVersion),
                new XElement("Header",
                    new XAttribute("instanceId", instanceId),
                    new XAttribute("version", schemaVersion),
                    new XAttribute("sender", agentName),
                    new XAttribute("bufferSize", bufferSize),
                    new XAttribute("assetBufferSize", maxAssets),
                    new XAttribute("assetCount", assets.Count),
                    new XAttribute("creationTime", DateTime.UtcNow.ToString("o"))),
                new XElement("Devices",
                    devices.Values.Select(d => GenerateDeviceXml(d))));

            return doc.ToString();
        }

        private XElement GenerateDeviceXml(MTConnectDevice device)
        {
            return new XElement("Device",
                new XAttribute("id", device.Id),
                new XAttribute("uuid", device.Uuid),
                new XAttribute("name", device.Name),
                device.Manufacturer != null ? new XAttribute("manufacturer", device.Manufacturer) : null,
                device.Model != null ? new XAttribute("model", device.Model) : null,
                device.SerialNumber != null ? new XAttribute("serialNumber", device.SerialNumber) : null,
                device.SampleInterval != null ? new XAttribute("sampleInterval", device.SampleInterval) : null,
                new XElement("Description", device.Description),
                device.DataItems.Count > 0 ? new XElement("DataItems",
                    device.DataItems.Select(di => GenerateDataItemXml(di))) : null,
                new XElement("Components",
                    device.Components.Select(c => GenerateComponentXml(c))));
        }

        private XElement GenerateComponentXml(Component component)
        {
            return new XElement(component.Type,
                new XAttribute("id", component.Id),
                new XAttribute("name", component.Name),
                component.NativeName != null ? new XAttribute("nativeName", component.NativeName) : null,
                component.DataItems.Count > 0 ? new XElement("DataItems",
                    component.DataItems.Select(di => GenerateDataItemXml(di))) : null,
                component.SubComponents.Count > 0 ? new XElement("Components",
                    component.SubComponents.Select(sc => GenerateComponentXml(sc))) : null);
        }

        private XElement GenerateDataItemXml(DataItem item)
        {
            return new XElement("DataItem",
                new XAttribute("id", item.Id),
                new XAttribute("type", item.Type.ToString()),
                new XAttribute("category", item.Category.ToString()),
                item.Name != null ? new XAttribute("name", item.Name) : null,
                item.SubType != DataItemSubType.NONE ? new XAttribute("subType", item.SubType.ToString()) : null,
                item.Units != null ? new XAttribute("units", item.Units) : null,
                item.NativeUnits != null ? new XAttribute("nativeUnits", item.NativeUnits) : null,
                item.NativeScale.HasValue ? new XAttribute("nativeScale", item.NativeScale.Value) : null,
                item.CoordinateSystem != null ? new XAttribute("coordinateSystem", item.CoordinateSystem) : null);
        }

        public string GenerateCurrentResponse(string deviceId = null, string path = null)
        {
            var items = dataItems.Values.AsEnumerable();

            if (!string.IsNullOrEmpty(deviceId))
            {
                // Filter by device
            }

            var doc = new XElement("MTConnectStreams",
                new XAttribute("xmlns", "urn:mtconnect.org:MTConnectStreams:1.8"),
                new XAttribute("schemaVersion", schemaVersion),
                new XElement("Header",
                    new XAttribute("instanceId", instanceId),
                    new XAttribute("version", schemaVersion),
                    new XAttribute("sender", agentName),
                    new XAttribute("bufferSize", bufferSize),
                    new XAttribute("nextSequence", nextSequence),
                    new XAttribute("firstSequence", firstSequence),
                    new XAttribute("lastSequence", nextSequence - 1),
                    new XAttribute("creationTime", DateTime.UtcNow.ToString("o"))),
                new XElement("Streams",
                    devices.Values.Select(d => GenerateDeviceStreamXml(d))));

            return doc.ToString();
        }

        private XElement GenerateDeviceStreamXml(MTConnectDevice device)
        {
            var deviceItems = dataItems.Values.Where(di =>
                device.DataItems.Any(d => d.Id == di.Id) ||
                device.Components.Any(c => ComponentContainsDataItem(c, di.Id)));

            var samples = deviceItems.Where(i => i.Category == DataItemCategory.SAMPLE);
            var events = deviceItems.Where(i => i.Category == DataItemCategory.EVENT);
            var conditions = deviceItems.Where(i => i.Category == DataItemCategory.CONDITION);

            return new XElement("DeviceStream",
                new XAttribute("name", device.Name),
                new XAttribute("uuid", device.Uuid),
                new XElement("ComponentStream",
                    new XAttribute("component", "Device"),
                    new XAttribute("name", device.Name),
                    samples.Any() ? new XElement("Samples",
                        samples.Select(s => GenerateValueXml(s))) : null,
                    events.Any() ? new XElement("Events",
                        events.Select(e => GenerateValueXml(e))) : null,
                    conditions.Any() ? new XElement("Condition",
                        conditions.Select(c => GenerateConditionXml(c))) : null));
        }

        private bool ComponentContainsDataItem(Component component, string dataItemId)
        {
            if (component.DataItems.Any(di => di.Id == dataItemId))
                return true;

            return component.SubComponents.Any(sc => ComponentContainsDataItem(sc, dataItemId));
        }

        private XElement GenerateValueXml(DataItem item)
        {
            var value = item.CurrentValue;
            return new XElement(item.Type.ToString(),
                new XAttribute("dataItemId", item.Id),
                new XAttribute("timestamp", value.Timestamp.ToString("o")),
                new XAttribute("sequence", value.Sequence),
                item.SubType != DataItemSubType.NONE ? new XAttribute("subType", item.SubType.ToString()) : null,
                value.StringValue);
        }

        private XElement GenerateConditionXml(DataItem item)
        {
            var value = item.CurrentValue;
            ConditionState state = ConditionState.UNAVAILABLE;
            Enum.TryParse(value.StringValue, out state);

            return new XElement(state.ToString(),
                new XAttribute("dataItemId", item.Id),
                new XAttribute("timestamp", value.Timestamp.ToString("o")),
                new XAttribute("sequence", value.Sequence),
                new XAttribute("type", item.Type.ToString()));
        }

        public string GenerateAssetsResponse(string type = null, int? count = null)
        {
            var assetList = assets.Values.AsEnumerable();

            if (!string.IsNullOrEmpty(type))
                assetList = assetList.Where(a => a.Type == type);

            if (count.HasValue)
                assetList = assetList.Take(count.Value);

            var doc = new XElement("MTConnectAssets",
                new XAttribute("xmlns", "urn:mtconnect.org:MTConnectAssets:1.8"),
                new XAttribute("schemaVersion", schemaVersion),
                new XElement("Header",
                    new XAttribute("instanceId", instanceId),
                    new XAttribute("version", schemaVersion),
                    new XAttribute("sender", agentName),
                    new XAttribute("assetBufferSize", maxAssets),
                    new XAttribute("assetCount", assets.Count),
                    new XAttribute("creationTime", DateTime.UtcNow.ToString("o"))),
                new XElement("Assets",
                    assetList.Select(a => GenerateAssetXml(a))));

            return doc.ToString();
        }

        private XElement GenerateAssetXml(MTConnectAsset asset)
        {
            if (asset is CuttingToolAsset tool)
            {
                return new XElement("CuttingTool",
                    new XAttribute("assetId", tool.AssetId),
                    new XAttribute("timestamp", tool.Timestamp.ToString("o")),
                    new XAttribute("deviceUuid", tool.DeviceUuid),
                    new XAttribute("toolId", tool.ToolId),
                    new XElement("Description", tool.Description),
                    tool.ToolLife != null ? new XElement("CuttingToolLifeCycle",
                        new XElement("ToolLife",
                            new XAttribute("type", tool.ToolLife.Type),
                            new XAttribute("countDirection", tool.ToolLife.CountDirection),
                            tool.ToolLife.Initial.HasValue ? new XAttribute("initial", tool.ToolLife.Initial.Value) : null,
                            tool.ToolLife.Limit.HasValue ? new XAttribute("limit", tool.ToolLife.Limit.Value) : null,
                            tool.ToolLife.Warning.HasValue ? new XAttribute("warning", tool.ToolLife.Warning.Value) : null,
                            tool.ToolLife.Value),
                        tool.Measurements.Count > 0 ? new XElement("Measurements",
                            tool.Measurements.Select(m => new XElement(m.Type,
                                new XAttribute("units", m.Units),
                                m.Nominal.HasValue ? new XAttribute("nominal", m.Nominal.Value) : null,
                                m.Value))) : null) : null);
            }

            return new XElement(asset.Type,
                new XAttribute("assetId", asset.AssetId),
                new XAttribute("timestamp", asset.Timestamp.ToString("o")));
        }

        #endregion

        #region Public API

        public MTConnectDevice GetDevice(string deviceId)
        {
            return devices.TryGetValue(deviceId, out var device) ? device : null;
        }

        public List<MTConnectDevice> GetAllDevices()
        {
            return devices.Values.ToList();
        }

        public DataItem GetDataItem(string dataItemId)
        {
            return dataItems.TryGetValue(dataItemId, out var item) ? item : null;
        }

        public List<DataItem> GetAllDataItems()
        {
            return dataItems.Values.ToList();
        }

        public DataItemValue GetCurrentValue(string dataItemId)
        {
            return dataItems.TryGetValue(dataItemId, out var item) ? item.CurrentValue : null;
        }

        public MTConnectAsset GetAsset(string assetId)
        {
            return assets.TryGetValue(assetId, out var asset) ? asset : null;
        }

        public List<MTConnectAsset> GetAllAssets()
        {
            return assets.Values.ToList();
        }

        public List<SequenceItem> GetSampleRange(long from, int count)
        {
            int startIndex = (int)(from - firstSequence);
            if (startIndex < 0) startIndex = 0;
            return sampleBuffer.GetRange(startIndex, count);
        }

        public MTConnectStats GetStats()
        {
            return stats;
        }

        public bool IsAgentRunning()
        {
            return isAgentRunning;
        }

        #endregion
    }
}
