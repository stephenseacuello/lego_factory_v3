using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCDigitalTwin.Core
{
    /// <summary>
    /// Digital Twin Synchronization Manager
    /// Manages bidirectional synchronization between physical assets and digital representations
    /// Implements ISO 23247 Digital Twin Framework concepts
    /// </summary>
    public class DigitalTwinSyncManager : MonoBehaviour
    {
        public static DigitalTwinSyncManager Instance { get; private set; }

        [Header("Synchronization Settings")]
        [SerializeField] private float syncInterval = 0.02f; // 50Hz default
        [SerializeField] private float stateValidityTimeout = 5.0f; // seconds
        [SerializeField] private bool enablePrediction = true;
        [SerializeField] private float predictionHorizon = 0.1f; // 100ms lookahead
        [SerializeField] private SyncMode syncMode = SyncMode.RealTime;

        [Header("Network Settings")]
        [SerializeField] private float networkLatencyMs = 20f;
        [SerializeField] private int maxPendingUpdates = 100;
        [SerializeField] private bool enableInterpolation = true;
        [SerializeField] private bool enableExtrapolation = true;

        // Twin instances
        private Dictionary<string, DigitalTwinInstance> twinInstances = new Dictionary<string, DigitalTwinInstance>();

        // Property mappings
        private Dictionary<string, List<PropertyMapping>> propertyMappings = new Dictionary<string, List<PropertyMapping>>();

        // State buffers for interpolation
        private Dictionary<string, StateBuffer> stateBuffers = new Dictionary<string, StateBuffer>();

        // Synchronization statistics
        private SyncStatistics statistics = new SyncStatistics();

        // Pending updates queue
        private Queue<StateUpdate> pendingUpdates = new Queue<StateUpdate>();

        // Events
        public event Action<string, TwinState> OnTwinStateChanged;
        public event Action<string, SyncStatus> OnSyncStatusChanged;
        public event Action<string, TwinEvent> OnTwinEvent;
        public event Action<string, CommandResult> OnCommandExecuted;

        #region Data Structures

        public enum SyncMode
        {
            RealTime,       // Continuous synchronization
            OnDemand,       // Manual trigger
            EventDriven,    // On state changes
            Scheduled,      // Periodic intervals
            Hybrid          // Combination based on data type
        }

        [System.Serializable]
        public class DigitalTwinInstance
        {
            public string twinId;
            public string name;
            public string description;
            public TwinType type;
            public string physicalAssetId;
            public SyncStatus syncStatus;
            public DateTime lastSync;
            public DateTime createdAt;

            // State
            public TwinState currentState;
            public TwinState predictedState;

            // Configuration
            public TwinConfiguration configuration;

            // Relationships
            public List<TwinRelationship> relationships;

            // Capabilities
            public List<TwinCapability> capabilities;

            // Properties
            public Dictionary<string, TwinProperty> properties;

            // Sub-elements (for composite twins)
            public List<string> subElementIds;

            // Unity references
            public GameObject visualRepresentation;
            public List<TwinVisualizer> visualizers;
        }

        public enum TwinType
        {
            Machine,
            Component,
            Assembly,
            Process,
            Product,
            Environment,
            System,
            Composite
        }

        public enum SyncStatus
        {
            Synchronized,
            Synchronizing,
            Desynchronized,
            Offline,
            Error,
            Initializing
        }

        [System.Serializable]
        public class TwinState
        {
            public string twinId;
            public DateTime timestamp;
            public long sequenceNumber;

            // Kinematic state
            public Vector3 position;
            public Quaternion rotation;
            public Vector3 velocity;
            public Vector3 angularVelocity;
            public Vector3 acceleration;

            // Axis positions (for CNC)
            public Dictionary<string, float> axisPositions;
            public Dictionary<string, float> axisVelocities;
            public Dictionary<string, float> axisLoads;

            // Operational state
            public OperationalMode operationalMode;
            public MachineStatus machineStatus;
            public int programNumber;
            public int toolNumber;
            public float spindleSpeed;
            public float feedRate;

            // Environmental state
            public float temperature;
            public float vibration;
            public float power;

            // Quality flags
            public QualityFlags qualityFlags;
            public float confidence;
        }

        public enum OperationalMode
        {
            Manual,
            MDI,
            Automatic,
            Edit,
            Reference,
            JogMode,
            Stopped,
            Emergency
        }

        public enum MachineStatus
        {
            Idle,
            Running,
            Paused,
            Stopped,
            Alarm,
            Emergency,
            Warmup,
            Maintenance
        }

        [Flags]
        public enum QualityFlags
        {
            None = 0,
            Interpolated = 1,
            Extrapolated = 2,
            Stale = 4,
            Uncertain = 8,
            Simulated = 16,
            Substituted = 32
        }

        [System.Serializable]
        public class TwinConfiguration
        {
            public float syncRate; // Hz
            public float deadband; // Change threshold
            public bool enableHistory;
            public bool enableEvents;
            public bool enableCommands;
            public Dictionary<string, float> propertyDeadbands;
        }

        [System.Serializable]
        public class TwinRelationship
        {
            public string relationshipId;
            public string targetTwinId;
            public RelationshipType type;
            public string description;
        }

        public enum RelationshipType
        {
            Contains,
            PartOf,
            Controls,
            ControlledBy,
            Feeds,
            FedBy,
            AdjacentTo,
            DependsOn,
            DependencyOf
        }

        [System.Serializable]
        public class TwinCapability
        {
            public string capabilityId;
            public string name;
            public CapabilityType type;
            public bool isAvailable;
            public Dictionary<string, object> parameters;
        }

        public enum CapabilityType
        {
            Move,
            Rotate,
            Grip,
            Release,
            Cut,
            Measure,
            Heat,
            Cool,
            Dispense
        }

        [System.Serializable]
        public class TwinProperty
        {
            public string propertyId;
            public string name;
            public string unit;
            public object value;
            public object previousValue;
            public DateTime timestamp;
            public PropertyType type;
            public PropertyDirection direction;
            public bool isWritable;
            public float? minValue;
            public float? maxValue;
            public float? deadband;
        }

        public enum PropertyType
        {
            Boolean,
            Integer,
            Float,
            Double,
            String,
            Vector3,
            Quaternion,
            DateTime,
            Enum,
            Array
        }

        public enum PropertyDirection
        {
            Input,      // From physical to digital
            Output,     // From digital to physical
            Bidirectional
        }

        [System.Serializable]
        public class PropertyMapping
        {
            public string mappingId;
            public string twinId;
            public string propertyId;
            public string sourceTag;
            public string targetTag;
            public MappingDirection direction;
            public float scaleFactor;
            public float offset;
            public TransformFunction transform;
        }

        public enum MappingDirection
        {
            PhysicalToDigital,
            DigitalToPhysical,
            Bidirectional
        }

        public delegate float TransformFunction(float input);

        [System.Serializable]
        public class StateUpdate
        {
            public string twinId;
            public TwinState state;
            public UpdateSource source;
            public DateTime receivedAt;
            public int priority;
        }

        public enum UpdateSource
        {
            Physical,
            Simulation,
            Prediction,
            User,
            System
        }

        [System.Serializable]
        public class StateBuffer
        {
            public string twinId;
            public Queue<TwinState> states;
            public int maxStates;
            public TwinState interpolatedState;
            public TwinState extrapolatedState;
        }

        [System.Serializable]
        public class TwinEvent
        {
            public string eventId;
            public string twinId;
            public TwinEventType type;
            public string message;
            public Dictionary<string, object> data;
            public DateTime timestamp;
            public EventSeverity severity;
        }

        public enum TwinEventType
        {
            StateChange,
            PropertyChange,
            AlarmActivated,
            AlarmCleared,
            CommandExecuted,
            SyncLost,
            SyncRestored,
            Error,
            Warning,
            Info
        }

        public enum EventSeverity
        {
            Info,
            Warning,
            Error,
            Critical
        }

        [System.Serializable]
        public class TwinCommand
        {
            public string commandId;
            public string twinId;
            public CommandType type;
            public Dictionary<string, object> parameters;
            public DateTime issuedAt;
            public DateTime? executedAt;
            public CommandStatus status;
            public string issuedBy;
        }

        public enum CommandType
        {
            Start,
            Stop,
            Pause,
            Resume,
            Reset,
            Home,
            Jog,
            MoveTo,
            SetParameter,
            ExecuteProgram,
            LoadTool,
            Custom
        }

        public enum CommandStatus
        {
            Pending,
            Executing,
            Completed,
            Failed,
            Cancelled,
            Timeout
        }

        [System.Serializable]
        public class CommandResult
        {
            public string commandId;
            public CommandStatus status;
            public string message;
            public Dictionary<string, object> resultData;
            public float executionTimeMs;
        }

        [System.Serializable]
        public class SyncStatistics
        {
            public int totalTwins;
            public int synchronizedTwins;
            public int desynchronizedTwins;
            public float averageSyncLatencyMs;
            public float maxSyncLatencyMs;
            public int totalUpdatesReceived;
            public int totalUpdatesSent;
            public int droppedUpdates;
            public float updateRate; // Updates per second
            public DateTime lastStatisticsUpdate;
        }

        [System.Serializable]
        public class TwinVisualizer
        {
            public string visualizerId;
            public VisualizerType type;
            public GameObject visualObject;
            public bool isActive;
        }

        public enum VisualizerType
        {
            Model3D,
            Trajectory,
            ForceVector,
            HeatMap,
            FlowVisualization,
            StateIndicator,
            DataOverlay
        }

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
            InitializeManager();
            StartCoroutine(SynchronizationLoop());
            StartCoroutine(PredictionLoop());
            StartCoroutine(StatisticsLoop());
        }

        private void Update()
        {
            // Process pending updates
            ProcessPendingUpdates();

            // Update interpolated states
            if (enableInterpolation)
            {
                UpdateInterpolatedStates();
            }
        }

        private void OnDestroy()
        {
            StopAllCoroutines();
        }

        #endregion

        #region Initialization

        private void InitializeManager()
        {
            Debug.Log("[TwinSync] Initializing Digital Twin Synchronization Manager");

            // Create default CNC machine twin
            CreateDefaultMachineTwin();

            statistics.lastStatisticsUpdate = DateTime.Now;
            Debug.Log($"[TwinSync] Initialized with {twinInstances.Count} twin instances");
        }

        private void CreateDefaultMachineTwin()
        {
            // Create main machine twin
            var machineTwin = new DigitalTwinInstance
            {
                twinId = "cnc_machine_001",
                name = "CNC Machining Center",
                description = "5-Axis CNC Vertical Machining Center",
                type = TwinType.Machine,
                physicalAssetId = "MC-001",
                syncStatus = SyncStatus.Initializing,
                createdAt = DateTime.Now,
                currentState = CreateInitialState("cnc_machine_001"),
                configuration = new TwinConfiguration
                {
                    syncRate = 50f, // 50 Hz
                    deadband = 0.001f,
                    enableHistory = true,
                    enableEvents = true,
                    enableCommands = true,
                    propertyDeadbands = new Dictionary<string, float>
                    {
                        { "position", 0.001f },
                        { "speed", 1f },
                        { "temperature", 0.1f }
                    }
                },
                relationships = new List<TwinRelationship>(),
                capabilities = CreateMachineCapabilities(),
                properties = CreateMachineProperties(),
                subElementIds = new List<string>(),
                visualizers = new List<TwinVisualizer>()
            };

            twinInstances[machineTwin.twinId] = machineTwin;
            stateBuffers[machineTwin.twinId] = new StateBuffer
            {
                twinId = machineTwin.twinId,
                states = new Queue<TwinState>(),
                maxStates = 10
            };

            // Create spindle sub-twin
            var spindleTwin = new DigitalTwinInstance
            {
                twinId = "spindle_001",
                name = "Main Spindle",
                description = "High-speed spindle assembly",
                type = TwinType.Component,
                physicalAssetId = "SPINDLE-001",
                syncStatus = SyncStatus.Initializing,
                createdAt = DateTime.Now,
                currentState = CreateInitialState("spindle_001"),
                configuration = new TwinConfiguration
                {
                    syncRate = 100f, // 100 Hz for spindle
                    deadband = 0.5f,
                    enableHistory = true,
                    enableEvents = true
                },
                relationships = new List<TwinRelationship>
                {
                    new TwinRelationship
                    {
                        relationshipId = "rel_001",
                        targetTwinId = "cnc_machine_001",
                        type = RelationshipType.PartOf,
                        description = "Spindle is part of machine"
                    }
                },
                capabilities = new List<TwinCapability>
                {
                    new TwinCapability
                    {
                        capabilityId = "rotate",
                        name = "Rotation",
                        type = CapabilityType.Rotate,
                        isAvailable = true,
                        parameters = new Dictionary<string, object>
                        {
                            { "maxSpeed", 24000f },
                            { "minSpeed", 100f }
                        }
                    }
                },
                properties = CreateSpindleProperties()
            };

            twinInstances[spindleTwin.twinId] = spindleTwin;
            stateBuffers[spindleTwin.twinId] = new StateBuffer
            {
                twinId = spindleTwin.twinId,
                states = new Queue<TwinState>(),
                maxStates = 10
            };

            // Add spindle as sub-element
            machineTwin.subElementIds.Add(spindleTwin.twinId);
            machineTwin.relationships.Add(new TwinRelationship
            {
                relationshipId = "rel_contains_spindle",
                targetTwinId = spindleTwin.twinId,
                type = RelationshipType.Contains,
                description = "Machine contains spindle"
            });

            // Create axis twins
            CreateAxisTwins(machineTwin);

            // Create property mappings
            CreateDefaultMappings();

            statistics.totalTwins = twinInstances.Count;
        }

        private TwinState CreateInitialState(string twinId)
        {
            return new TwinState
            {
                twinId = twinId,
                timestamp = DateTime.Now,
                sequenceNumber = 0,
                position = Vector3.zero,
                rotation = Quaternion.identity,
                velocity = Vector3.zero,
                angularVelocity = Vector3.zero,
                acceleration = Vector3.zero,
                axisPositions = new Dictionary<string, float>
                {
                    { "X", 0f }, { "Y", 0f }, { "Z", 0f }, { "A", 0f }, { "B", 0f }
                },
                axisVelocities = new Dictionary<string, float>
                {
                    { "X", 0f }, { "Y", 0f }, { "Z", 0f }, { "A", 0f }, { "B", 0f }
                },
                axisLoads = new Dictionary<string, float>
                {
                    { "X", 0f }, { "Y", 0f }, { "Z", 0f }, { "A", 0f }, { "B", 0f }
                },
                operationalMode = OperationalMode.Manual,
                machineStatus = MachineStatus.Idle,
                spindleSpeed = 0f,
                feedRate = 0f,
                temperature = 20f,
                vibration = 0f,
                power = 0f,
                qualityFlags = QualityFlags.None,
                confidence = 1.0f
            };
        }

        private List<TwinCapability> CreateMachineCapabilities()
        {
            return new List<TwinCapability>
            {
                new TwinCapability
                {
                    capabilityId = "move_linear",
                    name = "Linear Motion",
                    type = CapabilityType.Move,
                    isAvailable = true,
                    parameters = new Dictionary<string, object>
                    {
                        { "maxVelocity", 30000f },
                        { "maxAcceleration", 1000f },
                        { "axes", new[] { "X", "Y", "Z" } }
                    }
                },
                new TwinCapability
                {
                    capabilityId = "move_rotary",
                    name = "Rotary Motion",
                    type = CapabilityType.Rotate,
                    isAvailable = true,
                    parameters = new Dictionary<string, object>
                    {
                        { "maxVelocity", 360f },
                        { "axes", new[] { "A", "B" } }
                    }
                },
                new TwinCapability
                {
                    capabilityId = "cut",
                    name = "Material Removal",
                    type = CapabilityType.Cut,
                    isAvailable = true,
                    parameters = new Dictionary<string, object>
                    {
                        { "maxSpindleSpeed", 24000f },
                        { "maxPower", 30f }
                    }
                }
            };
        }

        private Dictionary<string, TwinProperty> CreateMachineProperties()
        {
            return new Dictionary<string, TwinProperty>
            {
                { "status", CreateProperty("status", "Machine Status", "", PropertyType.Enum, PropertyDirection.Input) },
                { "mode", CreateProperty("mode", "Operational Mode", "", PropertyType.Enum, PropertyDirection.Bidirectional) },
                { "program", CreateProperty("program", "Program Number", "", PropertyType.Integer, PropertyDirection.Bidirectional) },
                { "tool", CreateProperty("tool", "Tool Number", "", PropertyType.Integer, PropertyDirection.Bidirectional) },
                { "feedOverride", CreateProperty("feedOverride", "Feed Override", "%", PropertyType.Float, PropertyDirection.Bidirectional, 0, 200) },
                { "spindleOverride", CreateProperty("spindleOverride", "Spindle Override", "%", PropertyType.Float, PropertyDirection.Bidirectional, 0, 200) },
                { "partCount", CreateProperty("partCount", "Part Count", "", PropertyType.Integer, PropertyDirection.Input) },
                { "cycleTime", CreateProperty("cycleTime", "Cycle Time", "sec", PropertyType.Float, PropertyDirection.Input) },
                { "totalPower", CreateProperty("totalPower", "Total Power", "kW", PropertyType.Float, PropertyDirection.Input) }
            };
        }

        private Dictionary<string, TwinProperty> CreateSpindleProperties()
        {
            return new Dictionary<string, TwinProperty>
            {
                { "speed", CreateProperty("speed", "Speed", "RPM", PropertyType.Float, PropertyDirection.Bidirectional, 0, 24000) },
                { "load", CreateProperty("load", "Load", "%", PropertyType.Float, PropertyDirection.Input, 0, 150) },
                { "temperature", CreateProperty("temperature", "Temperature", "°C", PropertyType.Float, PropertyDirection.Input, 0, 100) },
                { "vibration", CreateProperty("vibration", "Vibration", "mm/s", PropertyType.Float, PropertyDirection.Input, 0, 20) },
                { "power", CreateProperty("power", "Power", "kW", PropertyType.Float, PropertyDirection.Input, 0, 30) },
                { "running", CreateProperty("running", "Running", "", PropertyType.Boolean, PropertyDirection.Input) },
                { "direction", CreateProperty("direction", "Direction", "", PropertyType.Integer, PropertyDirection.Bidirectional, -1, 1) }
            };
        }

        private TwinProperty CreateProperty(string id, string name, string unit, PropertyType type,
            PropertyDirection direction, float? min = null, float? max = null)
        {
            return new TwinProperty
            {
                propertyId = id,
                name = name,
                unit = unit,
                type = type,
                direction = direction,
                isWritable = direction != PropertyDirection.Input,
                minValue = min,
                maxValue = max,
                timestamp = DateTime.Now
            };
        }

        private void CreateAxisTwins(DigitalTwinInstance machineTwin)
        {
            string[] axes = { "X", "Y", "Z", "A", "B" };

            foreach (var axis in axes)
            {
                var axisTwin = new DigitalTwinInstance
                {
                    twinId = $"axis_{axis.ToLower()}_001",
                    name = $"{axis} Axis",
                    description = $"{axis} axis servo system",
                    type = TwinType.Component,
                    physicalAssetId = $"AXIS-{axis}-001",
                    syncStatus = SyncStatus.Initializing,
                    createdAt = DateTime.Now,
                    currentState = CreateInitialState($"axis_{axis.ToLower()}_001"),
                    configuration = new TwinConfiguration
                    {
                        syncRate = 100f,
                        deadband = 0.001f,
                        enableHistory = true
                    },
                    properties = new Dictionary<string, TwinProperty>
                    {
                        { "position", CreateProperty("position", "Position", axis == "A" || axis == "B" ? "deg" : "mm", PropertyType.Float, PropertyDirection.Input) },
                        { "velocity", CreateProperty("velocity", "Velocity", axis == "A" || axis == "B" ? "deg/s" : "mm/s", PropertyType.Float, PropertyDirection.Input) },
                        { "acceleration", CreateProperty("acceleration", "Acceleration", axis == "A" || axis == "B" ? "deg/s²" : "mm/s²", PropertyType.Float, PropertyDirection.Input) },
                        { "load", CreateProperty("load", "Motor Load", "%", PropertyType.Float, PropertyDirection.Input, 0, 200) },
                        { "followingError", CreateProperty("followingError", "Following Error", "mm", PropertyType.Float, PropertyDirection.Input) },
                        { "inPosition", CreateProperty("inPosition", "In Position", "", PropertyType.Boolean, PropertyDirection.Input) }
                    }
                };

                twinInstances[axisTwin.twinId] = axisTwin;
                stateBuffers[axisTwin.twinId] = new StateBuffer
                {
                    twinId = axisTwin.twinId,
                    states = new Queue<TwinState>(),
                    maxStates = 10
                };

                machineTwin.subElementIds.Add(axisTwin.twinId);
            }
        }

        private void CreateDefaultMappings()
        {
            // Map spindle properties
            AddPropertyMapping("spindle_001", "speed", "SPINDLE.SPEED", MappingDirection.Bidirectional);
            AddPropertyMapping("spindle_001", "load", "SPINDLE.LOAD", MappingDirection.PhysicalToDigital);
            AddPropertyMapping("spindle_001", "temperature", "SPINDLE.TEMP", MappingDirection.PhysicalToDigital);
            AddPropertyMapping("spindle_001", "vibration", "SPINDLE.VIBRATION", MappingDirection.PhysicalToDigital);

            // Map axis properties
            string[] axes = { "x", "y", "z", "a", "b" };
            foreach (var axis in axes)
            {
                AddPropertyMapping($"axis_{axis}_001", "position", $"AXIS.{axis.ToUpper()}.POSITION", MappingDirection.PhysicalToDigital);
                AddPropertyMapping($"axis_{axis}_001", "velocity", $"AXIS.{axis.ToUpper()}.VELOCITY", MappingDirection.PhysicalToDigital);
                AddPropertyMapping($"axis_{axis}_001", "load", $"AXIS.{axis.ToUpper()}.LOAD", MappingDirection.PhysicalToDigital);
            }

            // Map machine properties
            AddPropertyMapping("cnc_machine_001", "feedOverride", "FEED.OVERRIDE", MappingDirection.Bidirectional);
            AddPropertyMapping("cnc_machine_001", "totalPower", "POWER.TOTAL", MappingDirection.PhysicalToDigital);
        }

        private void AddPropertyMapping(string twinId, string propertyId, string sourceTag, MappingDirection direction)
        {
            var mapping = new PropertyMapping
            {
                mappingId = $"map_{twinId}_{propertyId}",
                twinId = twinId,
                propertyId = propertyId,
                sourceTag = sourceTag,
                direction = direction,
                scaleFactor = 1.0f,
                offset = 0f
            };

            if (!propertyMappings.ContainsKey(twinId))
            {
                propertyMappings[twinId] = new List<PropertyMapping>();
            }

            propertyMappings[twinId].Add(mapping);
        }

        #endregion

        #region Synchronization

        private IEnumerator SynchronizationLoop()
        {
            while (true)
            {
                var startTime = DateTime.Now;

                foreach (var kvp in twinInstances)
                {
                    SynchronizeTwin(kvp.Value);
                }

                // Calculate sync rate
                var elapsed = (DateTime.Now - startTime).TotalMilliseconds;
                statistics.averageSyncLatencyMs = statistics.averageSyncLatencyMs * 0.9f + (float)elapsed * 0.1f;

                yield return new WaitForSeconds(syncInterval);
            }
        }

        private void SynchronizeTwin(DigitalTwinInstance twin)
        {
            // Check state validity
            var timeSinceLastSync = (DateTime.Now - twin.lastSync).TotalSeconds;

            if (timeSinceLastSync > stateValidityTimeout)
            {
                if (twin.syncStatus != SyncStatus.Desynchronized)
                {
                    twin.syncStatus = SyncStatus.Desynchronized;
                    OnSyncStatusChanged?.Invoke(twin.twinId, twin.syncStatus);

                    RaiseTwinEvent(twin.twinId, TwinEventType.SyncLost,
                        "Synchronization lost - state timeout", EventSeverity.Warning);
                }
            }

            // Apply property mappings
            ApplyPropertyMappings(twin);

            // Update visual representation
            UpdateVisualization(twin);
        }

        private void ApplyPropertyMappings(DigitalTwinInstance twin)
        {
            if (!propertyMappings.TryGetValue(twin.twinId, out var mappings))
                return;

            foreach (var mapping in mappings)
            {
                if (mapping.direction == MappingDirection.PhysicalToDigital ||
                    mapping.direction == MappingDirection.Bidirectional)
                {
                    // Get value from historian/data source
                    if (Historian.DataHistorianService.Instance != null)
                    {
                        var tagValue = Historian.DataHistorianService.Instance.GetCurrentValue(mapping.sourceTag);
                        if (tagValue != null && twin.properties.TryGetValue(mapping.propertyId, out var prop))
                        {
                            float rawValue = Convert.ToSingle(tagValue.value);
                            float transformedValue = rawValue * mapping.scaleFactor + mapping.offset;

                            if (mapping.transform != null)
                            {
                                transformedValue = mapping.transform(rawValue);
                            }

                            prop.previousValue = prop.value;
                            prop.value = transformedValue;
                            prop.timestamp = tagValue.timestamp;
                        }
                    }
                }
            }
        }

        public void UpdateTwinState(string twinId, TwinState newState, UpdateSource source = UpdateSource.Physical)
        {
            if (!twinInstances.TryGetValue(twinId, out var twin))
            {
                Debug.LogWarning($"[TwinSync] Unknown twin: {twinId}");
                return;
            }

            // Queue update
            var update = new StateUpdate
            {
                twinId = twinId,
                state = newState,
                source = source,
                receivedAt = DateTime.Now,
                priority = source == UpdateSource.Physical ? 1 : 0
            };

            pendingUpdates.Enqueue(update);
            statistics.totalUpdatesReceived++;

            // Limit queue size
            while (pendingUpdates.Count > maxPendingUpdates)
            {
                pendingUpdates.Dequeue();
                statistics.droppedUpdates++;
            }
        }

        private void ProcessPendingUpdates()
        {
            int processedCount = 0;
            int maxPerFrame = 10;

            while (pendingUpdates.Count > 0 && processedCount < maxPerFrame)
            {
                var update = pendingUpdates.Dequeue();
                ApplyStateUpdate(update);
                processedCount++;
            }
        }

        private void ApplyStateUpdate(StateUpdate update)
        {
            if (!twinInstances.TryGetValue(update.twinId, out var twin))
                return;

            var previousState = twin.currentState;
            twin.currentState = update.state;
            twin.currentState.timestamp = DateTime.Now;
            twin.currentState.sequenceNumber = previousState.sequenceNumber + 1;
            twin.lastSync = DateTime.Now;

            // Update state buffer
            if (stateBuffers.TryGetValue(update.twinId, out var buffer))
            {
                buffer.states.Enqueue(update.state);
                while (buffer.states.Count > buffer.maxStates)
                {
                    buffer.states.Dequeue();
                }
            }

            // Check for sync status change
            if (twin.syncStatus == SyncStatus.Desynchronized)
            {
                twin.syncStatus = SyncStatus.Synchronized;
                OnSyncStatusChanged?.Invoke(twin.twinId, twin.syncStatus);

                RaiseTwinEvent(twin.twinId, TwinEventType.SyncRestored,
                    "Synchronization restored", EventSeverity.Info);
            }

            OnTwinStateChanged?.Invoke(twin.twinId, twin.currentState);
        }

        #endregion

        #region Interpolation & Extrapolation

        private void UpdateInterpolatedStates()
        {
            var renderTime = DateTime.Now.AddMilliseconds(-networkLatencyMs);

            foreach (var kvp in stateBuffers)
            {
                var buffer = kvp.Value;

                if (buffer.states.Count < 2)
                    continue;

                var stateList = buffer.states.ToList();

                // Find states to interpolate between
                TwinState before = null;
                TwinState after = null;

                for (int i = 0; i < stateList.Count - 1; i++)
                {
                    if (stateList[i].timestamp <= renderTime && stateList[i + 1].timestamp > renderTime)
                    {
                        before = stateList[i];
                        after = stateList[i + 1];
                        break;
                    }
                }

                if (before != null && after != null)
                {
                    buffer.interpolatedState = InterpolateStates(before, after, renderTime);
                }
                else if (enableExtrapolation && stateList.Count >= 2)
                {
                    // Extrapolate from last two states
                    var last = stateList[stateList.Count - 1];
                    var secondLast = stateList[stateList.Count - 2];
                    buffer.extrapolatedState = ExtrapolateState(secondLast, last, DateTime.Now);
                }
            }
        }

        private TwinState InterpolateStates(TwinState before, TwinState after, DateTime targetTime)
        {
            var totalTime = (after.timestamp - before.timestamp).TotalSeconds;
            var elapsed = (targetTime - before.timestamp).TotalSeconds;
            float t = totalTime > 0 ? (float)(elapsed / totalTime) : 0f;
            t = Mathf.Clamp01(t);

            var interpolated = new TwinState
            {
                twinId = before.twinId,
                timestamp = targetTime,
                sequenceNumber = before.sequenceNumber,
                position = Vector3.Lerp(before.position, after.position, t),
                rotation = Quaternion.Slerp(before.rotation, after.rotation, t),
                velocity = Vector3.Lerp(before.velocity, after.velocity, t),
                angularVelocity = Vector3.Lerp(before.angularVelocity, after.angularVelocity, t),
                spindleSpeed = Mathf.Lerp(before.spindleSpeed, after.spindleSpeed, t),
                feedRate = Mathf.Lerp(before.feedRate, after.feedRate, t),
                temperature = Mathf.Lerp(before.temperature, after.temperature, t),
                operationalMode = t < 0.5f ? before.operationalMode : after.operationalMode,
                machineStatus = t < 0.5f ? before.machineStatus : after.machineStatus,
                qualityFlags = QualityFlags.Interpolated,
                confidence = 0.95f
            };

            // Interpolate axis positions
            interpolated.axisPositions = new Dictionary<string, float>();
            foreach (var axis in before.axisPositions.Keys)
            {
                float beforeVal = before.axisPositions.TryGetValue(axis, out float bv) ? bv : 0;
                float afterVal = after.axisPositions.TryGetValue(axis, out float av) ? av : 0;
                interpolated.axisPositions[axis] = Mathf.Lerp(beforeVal, afterVal, t);
            }

            return interpolated;
        }

        private TwinState ExtrapolateState(TwinState older, TwinState newer, DateTime targetTime)
        {
            var dt = (newer.timestamp - older.timestamp).TotalSeconds;
            var extrapolationTime = (targetTime - newer.timestamp).TotalSeconds;

            if (dt <= 0 || extrapolationTime > predictionHorizon)
            {
                return newer;
            }

            var extrapolated = new TwinState
            {
                twinId = newer.twinId,
                timestamp = targetTime,
                sequenceNumber = newer.sequenceNumber,
                velocity = newer.velocity,
                angularVelocity = newer.angularVelocity,
                spindleSpeed = newer.spindleSpeed,
                feedRate = newer.feedRate,
                operationalMode = newer.operationalMode,
                machineStatus = newer.machineStatus,
                qualityFlags = QualityFlags.Extrapolated,
                confidence = Mathf.Max(0.5f, 1f - (float)extrapolationTime / predictionHorizon)
            };

            // Extrapolate position
            extrapolated.position = newer.position + newer.velocity * (float)extrapolationTime;
            extrapolated.rotation = newer.rotation * Quaternion.Euler(newer.angularVelocity * (float)extrapolationTime);

            // Extrapolate axis positions
            extrapolated.axisPositions = new Dictionary<string, float>();
            foreach (var axis in newer.axisPositions.Keys)
            {
                float pos = newer.axisPositions.TryGetValue(axis, out float p) ? p : 0;
                float vel = newer.axisVelocities?.TryGetValue(axis, out float v) == true ? v : 0;
                extrapolated.axisPositions[axis] = pos + vel * (float)extrapolationTime;
            }

            return extrapolated;
        }

        #endregion

        #region Prediction

        private IEnumerator PredictionLoop()
        {
            while (enablePrediction)
            {
                foreach (var kvp in twinInstances)
                {
                    if (kvp.Value.currentState != null)
                    {
                        kvp.Value.predictedState = PredictFutureState(kvp.Value, predictionHorizon);
                    }
                }

                yield return new WaitForSeconds(syncInterval);
            }
        }

        private TwinState PredictFutureState(DigitalTwinInstance twin, float horizonSeconds)
        {
            var current = twin.currentState;
            if (current == null)
                return null;

            var predicted = new TwinState
            {
                twinId = twin.twinId,
                timestamp = DateTime.Now.AddSeconds(horizonSeconds),
                sequenceNumber = current.sequenceNumber,
                operationalMode = current.operationalMode,
                machineStatus = current.machineStatus,
                qualityFlags = QualityFlags.Extrapolated,
                confidence = 0.8f
            };

            // Simple linear prediction
            predicted.position = current.position + current.velocity * horizonSeconds +
                                0.5f * current.acceleration * horizonSeconds * horizonSeconds;
            predicted.velocity = current.velocity + current.acceleration * horizonSeconds;
            predicted.rotation = current.rotation * Quaternion.Euler(current.angularVelocity * horizonSeconds);

            // Predict axis positions
            predicted.axisPositions = new Dictionary<string, float>();
            foreach (var axis in current.axisPositions.Keys)
            {
                float pos = current.axisPositions.TryGetValue(axis, out float p) ? p : 0;
                float vel = current.axisVelocities?.TryGetValue(axis, out float v) == true ? v : 0;
                predicted.axisPositions[axis] = pos + vel * horizonSeconds;
            }

            return predicted;
        }

        #endregion

        #region Commands

        public string SendCommand(string twinId, CommandType type, Dictionary<string, object> parameters, string issuedBy)
        {
            if (!twinInstances.TryGetValue(twinId, out var twin))
            {
                Debug.LogWarning($"[TwinSync] Unknown twin for command: {twinId}");
                return null;
            }

            var command = new TwinCommand
            {
                commandId = Guid.NewGuid().ToString(),
                twinId = twinId,
                type = type,
                parameters = parameters ?? new Dictionary<string, object>(),
                issuedAt = DateTime.Now,
                status = CommandStatus.Pending,
                issuedBy = issuedBy
            };

            // Execute command
            StartCoroutine(ExecuteCommand(command));

            return command.commandId;
        }

        private IEnumerator ExecuteCommand(TwinCommand command)
        {
            command.status = CommandStatus.Executing;
            var startTime = DateTime.Now;

            // Simulate command execution
            yield return new WaitForSeconds(0.1f);

            command.executedAt = DateTime.Now;
            command.status = CommandStatus.Completed;

            var result = new CommandResult
            {
                commandId = command.commandId,
                status = CommandStatus.Completed,
                message = $"Command {command.type} executed successfully",
                executionTimeMs = (float)(DateTime.Now - startTime).TotalMilliseconds,
                resultData = new Dictionary<string, object>()
            };

            statistics.totalUpdatesSent++;

            RaiseTwinEvent(command.twinId, TwinEventType.CommandExecuted,
                $"Executed: {command.type}", EventSeverity.Info);

            OnCommandExecuted?.Invoke(command.commandId, result);
        }

        #endregion

        #region Visualization

        private void UpdateVisualization(DigitalTwinInstance twin)
        {
            if (twin.visualRepresentation == null)
                return;

            var state = twin.currentState;
            if (state == null)
                return;

            // Update transform
            twin.visualRepresentation.transform.position = state.position;
            twin.visualRepresentation.transform.rotation = state.rotation;

            // Update visualizers
            foreach (var visualizer in twin.visualizers)
            {
                if (visualizer.isActive && visualizer.visualObject != null)
                {
                    UpdateVisualizer(visualizer, state);
                }
            }
        }

        private void UpdateVisualizer(TwinVisualizer visualizer, TwinState state)
        {
            switch (visualizer.type)
            {
                case VisualizerType.StateIndicator:
                    // Update color based on machine status
                    var renderer = visualizer.visualObject.GetComponent<Renderer>();
                    if (renderer != null)
                    {
                        Color color = state.machineStatus switch
                        {
                            MachineStatus.Running => Color.green,
                            MachineStatus.Idle => Color.yellow,
                            MachineStatus.Alarm => Color.red,
                            MachineStatus.Emergency => Color.magenta,
                            _ => Color.gray
                        };
                        renderer.material.color = color;
                    }
                    break;

                case VisualizerType.Trajectory:
                    // Update trajectory line
                    var line = visualizer.visualObject.GetComponent<LineRenderer>();
                    if (line != null)
                    {
                        // Add current position to trajectory
                        int posCount = line.positionCount;
                        line.positionCount = posCount + 1;
                        line.SetPosition(posCount, state.position);
                    }
                    break;
            }
        }

        public void RegisterVisualRepresentation(string twinId, GameObject visual)
        {
            if (twinInstances.TryGetValue(twinId, out var twin))
            {
                twin.visualRepresentation = visual;
                Debug.Log($"[TwinSync] Registered visual for twin: {twinId}");
            }
        }

        #endregion

        #region Events

        private void RaiseTwinEvent(string twinId, TwinEventType type, string message, EventSeverity severity)
        {
            var twinEvent = new TwinEvent
            {
                eventId = Guid.NewGuid().ToString(),
                twinId = twinId,
                type = type,
                message = message,
                severity = severity,
                timestamp = DateTime.Now,
                data = new Dictionary<string, object>()
            };

            OnTwinEvent?.Invoke(twinId, twinEvent);
        }

        #endregion

        #region Statistics

        private IEnumerator StatisticsLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(1f);

                // Count synchronized twins
                statistics.synchronizedTwins = twinInstances.Values
                    .Count(t => t.syncStatus == SyncStatus.Synchronized);
                statistics.desynchronizedTwins = statistics.totalTwins - statistics.synchronizedTwins;

                // Calculate update rate
                statistics.updateRate = statistics.totalUpdatesReceived;
                statistics.totalUpdatesReceived = 0; // Reset counter

                statistics.lastStatisticsUpdate = DateTime.Now;
            }
        }

        public SyncStatistics GetStatistics()
        {
            return statistics;
        }

        public DigitalTwinInstance GetTwin(string twinId)
        {
            return twinInstances.TryGetValue(twinId, out var twin) ? twin : null;
        }

        public List<DigitalTwinInstance> GetAllTwins()
        {
            return twinInstances.Values.ToList();
        }

        public TwinState GetInterpolatedState(string twinId)
        {
            if (stateBuffers.TryGetValue(twinId, out var buffer))
            {
                return buffer.interpolatedState ?? buffer.extrapolatedState;
            }
            return twinInstances.TryGetValue(twinId, out var twin) ? twin.currentState : null;
        }

        #endregion
    }
}
