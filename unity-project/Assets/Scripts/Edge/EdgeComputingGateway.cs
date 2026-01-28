using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;

namespace CNCDigitalTwin.Edge
{
    /// <summary>
    /// Edge Computing Gateway for CNC Digital Twin
    /// Handles real-time local processing, data aggregation, cloud synchronization,
    /// and offline operation with store-and-forward capability
    /// </summary>
    public class EdgeComputingGateway : MonoBehaviour
    {
        public static EdgeComputingGateway Instance { get; private set; }

        [Header("Edge Configuration")]
        [SerializeField] private string gatewayId = "EDGE-001";
        [SerializeField] private string siteId = "PLANT-001";
        [SerializeField] private float syncInterval = 5f; // seconds
        [SerializeField] private int maxLocalBufferSize = 10000;
        [SerializeField] private bool enableStoreAndForward = true;

        [Header("Cloud Connection")]
        [SerializeField] private string cloudEndpoint = "wss://cloud.example.com/edge";
        [SerializeField] private string mqttBroker = "mqtt://broker.example.com:1883";
        [SerializeField] private float reconnectInterval = 10f;
        [SerializeField] private int heartbeatIntervalSeconds = 30;

        [Header("Processing Configuration")]
        [SerializeField] private int dataProcessingBatchSize = 100;
        [SerializeField] private float aggregationWindowSeconds = 1f;
        [SerializeField] private bool enableLocalAnalytics = true;
        [SerializeField] private bool enableEdgeML = false;

        // Events
        public event Action<ConnectionState> OnConnectionStateChanged;
        public event Action<DataPacket> OnDataReceived;
        public event Action<DataPacket> OnDataSent;
        public event Action<ProcessedResult> OnLocalProcessingComplete;
        public event Action<EdgeAlert> OnAlertGenerated;
        public event Action<CommandMessage> OnCommandReceived;

        // Connection state
        private ConnectionState cloudConnectionState = ConnectionState.Disconnected;
        private ConnectionState mqttConnectionState = ConnectionState.Disconnected;
        private DateTime lastHeartbeatTime;
        private DateTime lastSyncTime;

        // Data management
        private Queue<DataPacket> outboundQueue = new Queue<DataPacket>();
        private Queue<DataPacket> localBuffer = new Queue<DataPacket>();
        private Dictionary<string, DataStream> dataStreams = new Dictionary<string, DataStream>();
        private Dictionary<string, AggregatedData> aggregationBuffers = new Dictionary<string, AggregatedData>();

        // Protocol handlers
        private Dictionary<string, IProtocolHandler> protocolHandlers = new Dictionary<string, IProtocolHandler>();

        // Edge functions
        private Dictionary<string, EdgeFunction> edgeFunctions = new Dictionary<string, EdgeFunction>();
        private Dictionary<string, EdgeRule> edgeRules = new Dictionary<string, EdgeRule>();

        // Statistics
        private EdgeGatewayStats stats = new EdgeGatewayStats();

        #region Data Structures

        public enum ConnectionState
        {
            Disconnected,
            Connecting,
            Connected,
            Reconnecting,
            Error
        }

        public enum DataPriority
        {
            Low,
            Normal,
            High,
            Critical
        }

        public enum DataType
        {
            Telemetry,
            Event,
            Alarm,
            Command,
            Configuration,
            File,
            Stream
        }

        public enum ProcessingMode
        {
            Passthrough,
            Aggregate,
            Filter,
            Transform,
            Analyze
        }

        public class DataPacket
        {
            public string PacketId { get; set; }
            public string SourceId { get; set; }
            public string StreamId { get; set; }
            public DataType Type { get; set; }
            public DataPriority Priority { get; set; }
            public DateTime Timestamp { get; set; }
            public Dictionary<string, object> Payload { get; set; } = new Dictionary<string, object>();
            public Dictionary<string, string> Metadata { get; set; } = new Dictionary<string, string>();
            public int RetryCount { get; set; }
            public bool RequiresAck { get; set; }
        }

        public class DataStream
        {
            public string StreamId { get; set; }
            public string SourceId { get; set; }
            public string DataTag { get; set; }
            public ProcessingMode Mode { get; set; }
            public float SampleRate { get; set; } // Hz
            public float AggregationWindow { get; set; } // seconds
            public bool IsEnabled { get; set; }
            public DateTime LastDataTime { get; set; }
            public long PacketsReceived { get; set; }
            public long PacketsProcessed { get; set; }
            public object LastValue { get; set; }
        }

        public class AggregatedData
        {
            public string StreamId { get; set; }
            public DateTime WindowStart { get; set; }
            public DateTime WindowEnd { get; set; }
            public List<float> Values { get; set; } = new List<float>();
            public float Min { get; set; } = float.MaxValue;
            public float Max { get; set; } = float.MinValue;
            public float Sum { get; set; }
            public float Mean => Values.Count > 0 ? Sum / Values.Count : 0;
            public float StdDev { get; set; }
            public int Count { get; set; }
        }

        public class ProcessedResult
        {
            public string StreamId { get; set; }
            public DateTime Timestamp { get; set; }
            public Dictionary<string, object> Results { get; set; } = new Dictionary<string, object>();
            public string ProcessingMethod { get; set; }
            public float ProcessingTimeMs { get; set; }
        }

        public class EdgeFunction
        {
            public string FunctionId { get; set; }
            public string Name { get; set; }
            public string Description { get; set; }
            public List<string> InputStreams { get; set; } = new List<string>();
            public List<string> OutputStreams { get; set; } = new List<string>();
            public Func<Dictionary<string, object>, Dictionary<string, object>> Processor { get; set; }
            public bool IsEnabled { get; set; }
            public int ExecutionCount { get; set; }
            public float AverageExecutionTimeMs { get; set; }
        }

        public class EdgeRule
        {
            public string RuleId { get; set; }
            public string Name { get; set; }
            public string Condition { get; set; } // e.g., "temperature > 80"
            public List<string> TriggerStreams { get; set; } = new List<string>();
            public List<EdgeAction> Actions { get; set; } = new List<EdgeAction>();
            public bool IsEnabled { get; set; }
            public int TriggerCount { get; set; }
            public DateTime LastTriggered { get; set; }
        }

        public class EdgeAction
        {
            public string ActionType { get; set; } // "alert", "publish", "execute", "store"
            public Dictionary<string, object> Parameters { get; set; } = new Dictionary<string, object>();
        }

        public class EdgeAlert
        {
            public string AlertId { get; set; }
            public string Source { get; set; }
            public string Message { get; set; }
            public AlertSeverity Severity { get; set; }
            public DateTime Timestamp { get; set; }
            public Dictionary<string, object> Context { get; set; } = new Dictionary<string, object>();
            public bool Acknowledged { get; set; }
        }

        public enum AlertSeverity
        {
            Info,
            Warning,
            Error,
            Critical
        }

        public class CommandMessage
        {
            public string CommandId { get; set; }
            public string TargetId { get; set; }
            public string Command { get; set; }
            public Dictionary<string, object> Parameters { get; set; } = new Dictionary<string, object>();
            public DateTime Timestamp { get; set; }
            public DateTime? ExpiresAt { get; set; }
            public bool RequiresResponse { get; set; }
        }

        public interface IProtocolHandler
        {
            string ProtocolName { get; }
            bool Connect(string connectionString);
            void Disconnect();
            bool IsConnected { get; }
            void Send(DataPacket packet);
            event Action<DataPacket> OnDataReceived;
        }

        public class EdgeGatewayStats
        {
            public DateTime StartTime { get; set; }
            public long PacketsReceived { get; set; }
            public long PacketsSent { get; set; }
            public long PacketsDropped { get; set; }
            public long BytesReceived { get; set; }
            public long BytesSent { get; set; }
            public int ActiveStreams { get; set; }
            public int QueueDepth { get; set; }
            public float AverageLatencyMs { get; set; }
            public int ConnectionDrops { get; set; }
            public float UptimePercent { get; set; }
            public Dictionary<string, long> StreamPacketCounts { get; set; } = new Dictionary<string, long>();
        }

        public class EdgeConfiguration
        {
            public string GatewayId { get; set; }
            public string SiteId { get; set; }
            public List<DataStreamConfig> Streams { get; set; } = new List<DataStreamConfig>();
            public List<EdgeFunctionConfig> Functions { get; set; } = new List<EdgeFunctionConfig>();
            public List<EdgeRuleConfig> Rules { get; set; } = new List<EdgeRuleConfig>();
            public Dictionary<string, string> ProtocolSettings { get; set; } = new Dictionary<string, string>();
        }

        public class DataStreamConfig
        {
            public string StreamId { get; set; }
            public string SourceId { get; set; }
            public string DataTag { get; set; }
            public ProcessingMode Mode { get; set; }
            public float SampleRate { get; set; }
        }

        public class EdgeFunctionConfig
        {
            public string FunctionId { get; set; }
            public string Type { get; set; }
            public Dictionary<string, object> Parameters { get; set; }
        }

        public class EdgeRuleConfig
        {
            public string RuleId { get; set; }
            public string Condition { get; set; }
            public List<EdgeAction> Actions { get; set; }
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
            InitializeDefaultFunctions();
            InitializeDefaultRules();

            StartCoroutine(ConnectionMonitor());
            StartCoroutine(DataProcessingLoop());
            StartCoroutine(SyncLoop());
            StartCoroutine(HeartbeatLoop());

            Debug.Log($"[EdgeGateway] Initialized - Gateway: {gatewayId}, Site: {siteId}");
        }

        private void InitializeDefaultFunctions()
        {
            // Moving average function
            RegisterFunction("MOVING_AVG", "Moving Average", "Calculate moving average over window",
                inputs => {
                    var values = inputs.ContainsKey("values") ? inputs["values"] as List<float> : new List<float>();
                    return new Dictionary<string, object>
                    {
                        ["average"] = values.Count > 0 ? values.Average() : 0f
                    };
                });

            // Min/Max function
            RegisterFunction("MIN_MAX", "Min/Max Detector", "Find min and max values",
                inputs => {
                    var values = inputs.ContainsKey("values") ? inputs["values"] as List<float> : new List<float>();
                    return new Dictionary<string, object>
                    {
                        ["min"] = values.Count > 0 ? values.Min() : 0f,
                        ["max"] = values.Count > 0 ? values.Max() : 0f,
                        ["range"] = values.Count > 0 ? values.Max() - values.Min() : 0f
                    };
                });

            // Rate of change function
            RegisterFunction("RATE_OF_CHANGE", "Rate of Change", "Calculate rate of change",
                inputs => {
                    var values = inputs.ContainsKey("values") ? inputs["values"] as List<float> : new List<float>();
                    var timespan = inputs.ContainsKey("timespan") ? (float)inputs["timespan"] : 1f;
                    float rate = 0;
                    if (values.Count >= 2)
                    {
                        rate = (values.Last() - values.First()) / timespan;
                    }
                    return new Dictionary<string, object> { ["rate"] = rate };
                });

            // Threshold detector
            RegisterFunction("THRESHOLD", "Threshold Detector", "Check if value exceeds threshold",
                inputs => {
                    var value = inputs.ContainsKey("value") ? (float)inputs["value"] : 0f;
                    var threshold = inputs.ContainsKey("threshold") ? (float)inputs["threshold"] : 0f;
                    var hysteresis = inputs.ContainsKey("hysteresis") ? (float)inputs["hysteresis"] : 0f;
                    return new Dictionary<string, object>
                    {
                        ["exceeded"] = value > threshold,
                        ["margin"] = value - threshold
                    };
                });
        }

        private void InitializeDefaultRules()
        {
            // High temperature alert
            AddRule("TEMP_HIGH", "High Temperature Alert", "temperature > 80",
                new List<string> { "TEMP_*" },
                new List<EdgeAction>
                {
                    new EdgeAction { ActionType = "alert", Parameters = new Dictionary<string, object> { ["severity"] = "Warning", ["message"] = "High temperature detected" } }
                });

            // Connection lost
            AddRule("CONN_LOST", "Connection Lost Alert", "connected == false",
                new List<string> { "SYSTEM" },
                new List<EdgeAction>
                {
                    new EdgeAction { ActionType = "alert", Parameters = new Dictionary<string, object> { ["severity"] = "Error", ["message"] = "Cloud connection lost" } },
                    new EdgeAction { ActionType = "store", Parameters = new Dictionary<string, object> { ["mode"] = "forward" } }
                });
        }

        #endregion

        #region Stream Management

        public DataStream RegisterStream(string streamId, string sourceId, string dataTag,
            ProcessingMode mode = ProcessingMode.Passthrough, float sampleRate = 1f)
        {
            var stream = new DataStream
            {
                StreamId = streamId,
                SourceId = sourceId,
                DataTag = dataTag,
                Mode = mode,
                SampleRate = sampleRate,
                AggregationWindow = aggregationWindowSeconds,
                IsEnabled = true
            };

            dataStreams[streamId] = stream;
            aggregationBuffers[streamId] = new AggregatedData { StreamId = streamId, WindowStart = DateTime.Now };
            stats.ActiveStreams++;

            Debug.Log($"[EdgeGateway] Registered stream: {streamId} from {sourceId}");
            return stream;
        }

        public void UnregisterStream(string streamId)
        {
            if (dataStreams.ContainsKey(streamId))
            {
                dataStreams.Remove(streamId);
                aggregationBuffers.Remove(streamId);
                stats.ActiveStreams--;
            }
        }

        public void IngestData(string streamId, object value, Dictionary<string, string> metadata = null)
        {
            if (!dataStreams.TryGetValue(streamId, out var stream) || !stream.IsEnabled)
                return;

            stream.LastDataTime = DateTime.Now;
            stream.LastValue = value;
            stream.PacketsReceived++;
            stats.PacketsReceived++;

            var packet = new DataPacket
            {
                PacketId = Guid.NewGuid().ToString(),
                SourceId = stream.SourceId,
                StreamId = streamId,
                Type = DataType.Telemetry,
                Priority = DataPriority.Normal,
                Timestamp = DateTime.Now,
                Payload = new Dictionary<string, object> { ["value"] = value },
                Metadata = metadata ?? new Dictionary<string, string>()
            };

            // Process based on mode
            switch (stream.Mode)
            {
                case ProcessingMode.Passthrough:
                    EnqueueForSend(packet);
                    break;

                case ProcessingMode.Aggregate:
                    AggregateData(stream, value);
                    break;

                case ProcessingMode.Filter:
                    if (ShouldPassFilter(stream, value))
                        EnqueueForSend(packet);
                    break;

                case ProcessingMode.Transform:
                    var transformed = TransformData(stream, packet);
                    EnqueueForSend(transformed);
                    break;

                case ProcessingMode.Analyze:
                    AnalyzeData(stream, packet);
                    break;
            }

            stream.PacketsProcessed++;

            // Check rules
            EvaluateRules(streamId, value);

            OnDataReceived?.Invoke(packet);
        }

        private void AggregateData(DataStream stream, object value)
        {
            if (!aggregationBuffers.TryGetValue(stream.StreamId, out var buffer))
                return;

            float numValue = Convert.ToSingle(value);
            buffer.Values.Add(numValue);
            buffer.Sum += numValue;
            buffer.Count++;
            if (numValue < buffer.Min) buffer.Min = numValue;
            if (numValue > buffer.Max) buffer.Max = numValue;

            // Check if window is complete
            if ((DateTime.Now - buffer.WindowStart).TotalSeconds >= stream.AggregationWindow)
            {
                FlushAggregation(stream.StreamId);
            }
        }

        private void FlushAggregation(string streamId)
        {
            if (!aggregationBuffers.TryGetValue(streamId, out var buffer) || buffer.Count == 0)
                return;

            // Calculate standard deviation
            float mean = buffer.Mean;
            float sumSqDiff = buffer.Values.Sum(v => (v - mean) * (v - mean));
            buffer.StdDev = Mathf.Sqrt(sumSqDiff / buffer.Count);
            buffer.WindowEnd = DateTime.Now;

            // Create aggregated packet
            var packet = new DataPacket
            {
                PacketId = Guid.NewGuid().ToString(),
                StreamId = streamId,
                Type = DataType.Telemetry,
                Priority = DataPriority.Normal,
                Timestamp = DateTime.Now,
                Payload = new Dictionary<string, object>
                {
                    ["min"] = buffer.Min,
                    ["max"] = buffer.Max,
                    ["mean"] = buffer.Mean,
                    ["stddev"] = buffer.StdDev,
                    ["count"] = buffer.Count,
                    ["window_start"] = buffer.WindowStart,
                    ["window_end"] = buffer.WindowEnd
                }
            };

            EnqueueForSend(packet);

            // Reset buffer
            aggregationBuffers[streamId] = new AggregatedData
            {
                StreamId = streamId,
                WindowStart = DateTime.Now
            };
        }

        private bool ShouldPassFilter(DataStream stream, object value)
        {
            // Deadband filter - only pass if value changed significantly
            if (stream.LastValue != null)
            {
                float lastVal = Convert.ToSingle(stream.LastValue);
                float newVal = Convert.ToSingle(value);
                float deadband = Mathf.Abs(lastVal) * 0.01f; // 1% deadband
                return Mathf.Abs(newVal - lastVal) > deadband;
            }
            return true;
        }

        private DataPacket TransformData(DataStream stream, DataPacket packet)
        {
            // Apply any registered transforms
            // For now, add metadata
            packet.Metadata["gateway_id"] = gatewayId;
            packet.Metadata["site_id"] = siteId;
            packet.Metadata["processed_at"] = DateTime.Now.ToString("O");
            return packet;
        }

        private void AnalyzeData(DataStream stream, DataPacket packet)
        {
            // Run all applicable edge functions
            foreach (var func in edgeFunctions.Values.Where(f => f.IsEnabled && f.InputStreams.Contains(stream.StreamId)))
            {
                ExecuteFunction(func.FunctionId, packet.Payload);
            }
        }

        #endregion

        #region Edge Functions

        public void RegisterFunction(string functionId, string name, string description,
            Func<Dictionary<string, object>, Dictionary<string, object>> processor)
        {
            var func = new EdgeFunction
            {
                FunctionId = functionId,
                Name = name,
                Description = description,
                Processor = processor,
                IsEnabled = true
            };

            edgeFunctions[functionId] = func;
            Debug.Log($"[EdgeGateway] Registered function: {functionId}");
        }

        public Dictionary<string, object> ExecuteFunction(string functionId, Dictionary<string, object> inputs)
        {
            if (!edgeFunctions.TryGetValue(functionId, out var func) || !func.IsEnabled)
                return null;

            var startTime = DateTime.Now;

            try
            {
                var result = func.Processor(inputs);
                func.ExecutionCount++;

                float execTime = (float)(DateTime.Now - startTime).TotalMilliseconds;
                func.AverageExecutionTimeMs = (func.AverageExecutionTimeMs * (func.ExecutionCount - 1) + execTime) / func.ExecutionCount;

                var processed = new ProcessedResult
                {
                    StreamId = inputs.ContainsKey("streamId") ? inputs["streamId"]?.ToString() : "",
                    Timestamp = DateTime.Now,
                    Results = result,
                    ProcessingMethod = functionId,
                    ProcessingTimeMs = execTime
                };

                OnLocalProcessingComplete?.Invoke(processed);
                return result;
            }
            catch (Exception e)
            {
                Debug.LogError($"[EdgeGateway] Function {functionId} error: {e.Message}");
                return null;
            }
        }

        #endregion

        #region Edge Rules

        public void AddRule(string ruleId, string name, string condition, List<string> triggerStreams, List<EdgeAction> actions)
        {
            var rule = new EdgeRule
            {
                RuleId = ruleId,
                Name = name,
                Condition = condition,
                TriggerStreams = triggerStreams,
                Actions = actions,
                IsEnabled = true
            };

            edgeRules[ruleId] = rule;
            Debug.Log($"[EdgeGateway] Added rule: {ruleId}");
        }

        private void EvaluateRules(string streamId, object value)
        {
            foreach (var rule in edgeRules.Values.Where(r => r.IsEnabled))
            {
                // Check if this stream triggers the rule (supports wildcards)
                bool triggers = rule.TriggerStreams.Any(ts =>
                    ts == streamId ||
                    (ts.EndsWith("*") && streamId.StartsWith(ts.TrimEnd('*'))));

                if (!triggers) continue;

                // Evaluate condition
                if (EvaluateCondition(rule.Condition, streamId, value))
                {
                    rule.TriggerCount++;
                    rule.LastTriggered = DateTime.Now;
                    ExecuteRuleActions(rule, streamId, value);
                }
            }
        }

        private bool EvaluateCondition(string condition, string streamId, object value)
        {
            // Simple condition parser
            // Supports: >, <, >=, <=, ==, !=

            try
            {
                float numValue = Convert.ToSingle(value);

                // Parse condition like "temperature > 80"
                var parts = condition.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length >= 3)
                {
                    string op = parts[1];
                    float threshold = float.Parse(parts[2]);

                    return op switch
                    {
                        ">" => numValue > threshold,
                        "<" => numValue < threshold,
                        ">=" => numValue >= threshold,
                        "<=" => numValue <= threshold,
                        "==" => Mathf.Approximately(numValue, threshold),
                        "!=" => !Mathf.Approximately(numValue, threshold),
                        _ => false
                    };
                }
            }
            catch
            {
                // Non-numeric comparison
                if (condition.Contains("=="))
                {
                    var parts = condition.Split(new[] { "==" }, StringSplitOptions.None);
                    return value?.ToString() == parts[1].Trim();
                }
            }

            return false;
        }

        private void ExecuteRuleActions(EdgeRule rule, string streamId, object value)
        {
            foreach (var action in rule.Actions)
            {
                switch (action.ActionType.ToLower())
                {
                    case "alert":
                        var severity = action.Parameters.ContainsKey("severity")
                            ? Enum.Parse<AlertSeverity>(action.Parameters["severity"].ToString())
                            : AlertSeverity.Warning;
                        var message = action.Parameters.ContainsKey("message")
                            ? action.Parameters["message"].ToString()
                            : $"Rule {rule.RuleId} triggered";

                        GenerateAlert(rule.RuleId, message, severity, new Dictionary<string, object>
                        {
                            ["stream"] = streamId,
                            ["value"] = value,
                            ["condition"] = rule.Condition
                        });
                        break;

                    case "publish":
                        var topic = action.Parameters.ContainsKey("topic")
                            ? action.Parameters["topic"].ToString()
                            : $"edge/{gatewayId}/alerts";
                        PublishToMqtt(topic, new { rule = rule.RuleId, stream = streamId, value });
                        break;

                    case "execute":
                        var functionId = action.Parameters.ContainsKey("function")
                            ? action.Parameters["function"].ToString()
                            : "";
                        if (!string.IsNullOrEmpty(functionId))
                        {
                            ExecuteFunction(functionId, new Dictionary<string, object>
                            {
                                ["streamId"] = streamId,
                                ["value"] = value
                            });
                        }
                        break;

                    case "store":
                        StoreLocally(new DataPacket
                        {
                            StreamId = streamId,
                            Timestamp = DateTime.Now,
                            Payload = new Dictionary<string, object> { ["value"] = value }
                        });
                        break;
                }
            }
        }

        private void GenerateAlert(string source, string message, AlertSeverity severity,
            Dictionary<string, object> context)
        {
            var alert = new EdgeAlert
            {
                AlertId = Guid.NewGuid().ToString(),
                Source = source,
                Message = message,
                Severity = severity,
                Timestamp = DateTime.Now,
                Context = context,
                Acknowledged = false
            };

            OnAlertGenerated?.Invoke(alert);
            Debug.Log($"[EdgeGateway] ALERT [{severity}]: {message}");

            // Send to cloud if connected
            if (cloudConnectionState == ConnectionState.Connected)
            {
                var packet = new DataPacket
                {
                    Type = DataType.Alarm,
                    Priority = severity >= AlertSeverity.Error ? DataPriority.Critical : DataPriority.High,
                    Timestamp = DateTime.Now,
                    Payload = new Dictionary<string, object>
                    {
                        ["alert"] = alert
                    }
                };
                EnqueueForSend(packet);
            }
        }

        #endregion

        #region Communication

        private void EnqueueForSend(DataPacket packet)
        {
            if (cloudConnectionState == ConnectionState.Connected)
            {
                outboundQueue.Enqueue(packet);
                stats.QueueDepth = outboundQueue.Count;
            }
            else if (enableStoreAndForward)
            {
                StoreLocally(packet);
            }
            else
            {
                stats.PacketsDropped++;
            }
        }

        private void StoreLocally(DataPacket packet)
        {
            if (localBuffer.Count >= maxLocalBufferSize)
            {
                // Remove oldest
                localBuffer.Dequeue();
                stats.PacketsDropped++;
            }
            localBuffer.Enqueue(packet);
        }

        private void PublishToMqtt(string topic, object payload)
        {
            if (mqttConnectionState != ConnectionState.Connected)
            {
                Debug.LogWarning("[EdgeGateway] MQTT not connected, message not sent");
                return;
            }

            // Simulate MQTT publish
            string json = JsonUtility.ToJson(payload);
            Debug.Log($"[EdgeGateway] MQTT Publish: {topic}");
            stats.PacketsSent++;
        }

        private IEnumerator ConnectionMonitor()
        {
            while (true)
            {
                yield return new WaitForSeconds(reconnectInterval);

                // Attempt reconnection if disconnected
                if (cloudConnectionState == ConnectionState.Disconnected ||
                    cloudConnectionState == ConnectionState.Error)
                {
                    yield return StartCoroutine(ConnectToCloud());
                }

                if (mqttConnectionState == ConnectionState.Disconnected ||
                    mqttConnectionState == ConnectionState.Error)
                {
                    yield return StartCoroutine(ConnectToMqtt());
                }
            }
        }

        private IEnumerator ConnectToCloud()
        {
            cloudConnectionState = ConnectionState.Connecting;
            OnConnectionStateChanged?.Invoke(cloudConnectionState);
            Debug.Log("[EdgeGateway] Connecting to cloud...");

            // Simulate connection attempt
            yield return new WaitForSeconds(1f);

            // Simulate success
            cloudConnectionState = ConnectionState.Connected;
            OnConnectionStateChanged?.Invoke(cloudConnectionState);
            Debug.Log("[EdgeGateway] Cloud connected");

            // Flush local buffer
            if (enableStoreAndForward && localBuffer.Count > 0)
            {
                yield return StartCoroutine(FlushLocalBuffer());
            }
        }

        private IEnumerator ConnectToMqtt()
        {
            mqttConnectionState = ConnectionState.Connecting;
            Debug.Log("[EdgeGateway] Connecting to MQTT...");

            yield return new WaitForSeconds(0.5f);

            mqttConnectionState = ConnectionState.Connected;
            Debug.Log("[EdgeGateway] MQTT connected");
        }

        private IEnumerator FlushLocalBuffer()
        {
            Debug.Log($"[EdgeGateway] Flushing {localBuffer.Count} buffered packets");

            while (localBuffer.Count > 0 && cloudConnectionState == ConnectionState.Connected)
            {
                var packet = localBuffer.Dequeue();
                outboundQueue.Enqueue(packet);
                yield return null;
            }
        }

        private IEnumerator SyncLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(syncInterval);

                if (cloudConnectionState != ConnectionState.Connected)
                    continue;

                // Send batched data
                int batchCount = 0;
                while (outboundQueue.Count > 0 && batchCount < dataProcessingBatchSize)
                {
                    var packet = outboundQueue.Dequeue();
                    yield return StartCoroutine(SendPacket(packet));
                    batchCount++;
                }

                // Flush any pending aggregations
                foreach (var streamId in aggregationBuffers.Keys.ToList())
                {
                    var buffer = aggregationBuffers[streamId];
                    if (buffer.Count > 0 && (DateTime.Now - buffer.WindowStart).TotalSeconds >= aggregationWindowSeconds)
                    {
                        FlushAggregation(streamId);
                    }
                }

                lastSyncTime = DateTime.Now;
                stats.QueueDepth = outboundQueue.Count;
            }
        }

        private IEnumerator SendPacket(DataPacket packet)
        {
            // Simulate send
            yield return new WaitForSeconds(0.01f);

            stats.PacketsSent++;
            OnDataSent?.Invoke(packet);
        }

        private IEnumerator HeartbeatLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(heartbeatIntervalSeconds);

                if (cloudConnectionState == ConnectionState.Connected)
                {
                    var heartbeat = new DataPacket
                    {
                        Type = DataType.Event,
                        Priority = DataPriority.Low,
                        Timestamp = DateTime.Now,
                        Payload = new Dictionary<string, object>
                        {
                            ["type"] = "heartbeat",
                            ["gateway_id"] = gatewayId,
                            ["uptime"] = (DateTime.Now - stats.StartTime).TotalSeconds,
                            ["queue_depth"] = outboundQueue.Count,
                            ["active_streams"] = stats.ActiveStreams,
                            ["packets_received"] = stats.PacketsReceived,
                            ["packets_sent"] = stats.PacketsSent
                        }
                    };

                    EnqueueForSend(heartbeat);
                    lastHeartbeatTime = DateTime.Now;
                }
            }
        }

        private IEnumerator DataProcessingLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(0.1f);

                if (enableLocalAnalytics)
                {
                    // Run analytics on streams that need it
                    foreach (var stream in dataStreams.Values.Where(s => s.Mode == ProcessingMode.Analyze && s.IsEnabled))
                    {
                        if (stream.LastValue != null)
                        {
                            // Run all enabled functions for this stream
                            foreach (var func in edgeFunctions.Values.Where(f =>
                                f.IsEnabled && f.InputStreams.Contains(stream.StreamId)))
                            {
                                ExecuteFunction(func.FunctionId, new Dictionary<string, object>
                                {
                                    ["streamId"] = stream.StreamId,
                                    ["value"] = stream.LastValue
                                });
                            }
                        }
                    }
                }
            }
        }

        #endregion

        #region Command Handling

        public void HandleCommand(CommandMessage command)
        {
            Debug.Log($"[EdgeGateway] Received command: {command.Command} for {command.TargetId}");

            // Check expiration
            if (command.ExpiresAt.HasValue && DateTime.Now > command.ExpiresAt.Value)
            {
                Debug.LogWarning($"[EdgeGateway] Command {command.CommandId} expired");
                return;
            }

            OnCommandReceived?.Invoke(command);

            // Execute command
            switch (command.Command.ToUpper())
            {
                case "CONFIGURE":
                    ApplyConfiguration(command.Parameters);
                    break;

                case "RESTART":
                    Debug.Log("[EdgeGateway] Restart requested");
                    break;

                case "FLUSH":
                    StartCoroutine(FlushLocalBuffer());
                    break;

                case "STATUS":
                    SendStatusResponse(command.CommandId);
                    break;

                default:
                    Debug.LogWarning($"[EdgeGateway] Unknown command: {command.Command}");
                    break;
            }
        }

        private void ApplyConfiguration(Dictionary<string, object> config)
        {
            if (config.ContainsKey("sync_interval"))
                syncInterval = Convert.ToSingle(config["sync_interval"]);

            if (config.ContainsKey("aggregation_window"))
                aggregationWindowSeconds = Convert.ToSingle(config["aggregation_window"]);

            Debug.Log("[EdgeGateway] Configuration updated");
        }

        private void SendStatusResponse(string commandId)
        {
            var response = new DataPacket
            {
                Type = DataType.Event,
                Priority = DataPriority.High,
                Timestamp = DateTime.Now,
                Payload = new Dictionary<string, object>
                {
                    ["type"] = "command_response",
                    ["command_id"] = commandId,
                    ["status"] = GetStats()
                }
            };

            EnqueueForSend(response);
        }

        #endregion

        #region Public API

        public DataStream GetStream(string streamId)
        {
            return dataStreams.TryGetValue(streamId, out var stream) ? stream : null;
        }

        public List<DataStream> GetAllStreams()
        {
            return dataStreams.Values.ToList();
        }

        public EdgeFunction GetFunction(string functionId)
        {
            return edgeFunctions.TryGetValue(functionId, out var func) ? func : null;
        }

        public List<EdgeFunction> GetAllFunctions()
        {
            return edgeFunctions.Values.ToList();
        }

        public EdgeRule GetRule(string ruleId)
        {
            return edgeRules.TryGetValue(ruleId, out var rule) ? rule : null;
        }

        public List<EdgeRule> GetAllRules()
        {
            return edgeRules.Values.ToList();
        }

        public ConnectionState GetCloudConnectionState()
        {
            return cloudConnectionState;
        }

        public ConnectionState GetMqttConnectionState()
        {
            return mqttConnectionState;
        }

        public EdgeGatewayStats GetStats()
        {
            stats.UptimePercent = cloudConnectionState == ConnectionState.Connected ? 100f :
                (float)(DateTime.Now - stats.StartTime).TotalSeconds /
                (float)(DateTime.Now - stats.StartTime + TimeSpan.FromSeconds(stats.ConnectionDrops * reconnectInterval)).TotalSeconds * 100f;

            return stats;
        }

        public void SetStreamEnabled(string streamId, bool enabled)
        {
            if (dataStreams.TryGetValue(streamId, out var stream))
            {
                stream.IsEnabled = enabled;
            }
        }

        public void SetFunctionEnabled(string functionId, bool enabled)
        {
            if (edgeFunctions.TryGetValue(functionId, out var func))
            {
                func.IsEnabled = enabled;
            }
        }

        public void SetRuleEnabled(string ruleId, bool enabled)
        {
            if (edgeRules.TryGetValue(ruleId, out var rule))
            {
                rule.IsEnabled = enabled;
            }
        }

        public int GetQueueDepth()
        {
            return outboundQueue.Count;
        }

        public int GetLocalBufferSize()
        {
            return localBuffer.Count;
        }

        #endregion
    }
}
