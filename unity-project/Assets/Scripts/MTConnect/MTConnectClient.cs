using System;
using System.Collections;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;
using UnityEngine.Networking;
using CNCScada.Sensors;

namespace CNCScada.MTConnect
{
    /// <summary>
    /// MTConnect client for Unity Digital Twin.
    /// Connects to MTConnect agents to receive real-time machine data.
    ///
    /// MTConnect Standard: https://www.mtconnect.org/
    /// Supports MTConnect versions 1.3 - 2.0
    /// </summary>
    public class MTConnectClient : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string agentUrl = "http://localhost:5000";
        [SerializeField] private float pollingInterval = 0.5f; // seconds
        [SerializeField] private bool autoConnect = true;
        [SerializeField] private int connectionTimeout = 5; // seconds

        [Header("MTConnect Settings")]
        [SerializeField] private string deviceName = "BantamCNC";
        [SerializeField] private MTConnectVersion protocolVersion = MTConnectVersion.V2_0;
        [SerializeField] private bool useStreaming = false; // HTTP streaming vs polling

        [Header("Data Items to Monitor")]
        [SerializeField] private List<string> monitoredDataItems = new List<string>
        {
            "Xact", "Yact", "Zact",           // Axis positions
            "Xload", "Yload", "Zload",        // Axis loads
            "Sspeed", "Sload",                // Spindle speed and load
            "execution", "mode",              // Controller state
            "program", "line",                // Program info
            "estop", "avail"                  // Status flags
        };

        [Header("Status")]
        [SerializeField] private bool isConnected;
        [SerializeField] private long lastSequence;
        [SerializeField] private string connectionStatus = "Disconnected";

        // Events
        public event Action OnConnected;
        public event Action OnDisconnected;
        public event Action<MTConnectDeviceData> OnDeviceDataReceived;
        public event Action<MTConnectSample> OnSampleReceived;
        public event Action<MTConnectCondition> OnConditionReceived;
        public event Action<string> OnError;

        // Internal state
        private Coroutine pollingCoroutine;
        private MTConnectDeviceData currentDeviceData;
        private Dictionary<string, MTConnectDataItem> dataItemCache = new Dictionary<string, MTConnectDataItem>();
        private string instanceId;

        // Singleton
        public static MTConnectClient Instance { get; private set; }

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
            if (autoConnect)
            {
                Connect();
            }
        }

        private void OnDestroy()
        {
            Disconnect();
        }

        /// <summary>
        /// Connect to MTConnect agent
        /// </summary>
        public void Connect()
        {
            if (isConnected) return;

            Debug.Log($"[MTConnect] Connecting to {agentUrl}...");
            connectionStatus = "Connecting...";
            StartCoroutine(ConnectCoroutine());
        }

        /// <summary>
        /// Disconnect from MTConnect agent
        /// </summary>
        public void Disconnect()
        {
            isConnected = false;
            connectionStatus = "Disconnected";

            if (pollingCoroutine != null)
            {
                StopCoroutine(pollingCoroutine);
                pollingCoroutine = null;
            }

            OnDisconnected?.Invoke();
            Debug.Log("[MTConnect] Disconnected");
        }

        private IEnumerator ConnectCoroutine()
        {
            // First, probe the agent to get device information
            string probeUrl = $"{agentUrl}/probe";

            using (UnityWebRequest request = UnityWebRequest.Get(probeUrl))
            {
                request.timeout = connectionTimeout;
                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    string error = $"Failed to connect: {request.error}";
                    Debug.LogError($"[MTConnect] {error}");
                    connectionStatus = $"Error: {request.error}";
                    OnError?.Invoke(error);
                    yield break;
                }

                // Parse probe response
                string xml = request.downloadHandler.text;
                ParseProbeResponse(xml);
            }

            // Get initial current state
            yield return GetCurrentState();

            isConnected = true;
            connectionStatus = "Connected";
            OnConnected?.Invoke();
            Debug.Log("[MTConnect] Connected successfully");

            // Start polling or streaming
            if (useStreaming)
            {
                pollingCoroutine = StartCoroutine(StreamingSample());
            }
            else
            {
                pollingCoroutine = StartCoroutine(PollingLoop());
            }
        }

        private void ParseProbeResponse(string xml)
        {
            // Parse MTConnect probe XML to extract device and data item info
            // Simplified XML parsing - in production use proper XML parser

            // Extract instance ID
            var instanceMatch = Regex.Match(xml, @"instanceId=""(\d+)""");
            if (instanceMatch.Success)
            {
                instanceId = instanceMatch.Groups[1].Value;
            }

            // Extract data items
            var dataItemMatches = Regex.Matches(xml, @"<DataItem[^>]*id=""([^""]+)""[^>]*type=""([^""]+)""[^>]*/>");
            foreach (Match match in dataItemMatches)
            {
                string id = match.Groups[1].Value;
                string type = match.Groups[2].Value;

                dataItemCache[id] = new MTConnectDataItem
                {
                    id = id,
                    type = type,
                    category = DetermineCategory(type)
                };
            }

            Debug.Log($"[MTConnect] Parsed {dataItemCache.Count} data items");
        }

        private MTConnectCategory DetermineCategory(string type)
        {
            // Categorize data item types
            string[] samples = { "POSITION", "VELOCITY", "ACCELERATION", "LOAD", "TEMPERATURE", "PRESSURE" };
            string[] events = { "EXECUTION", "MODE", "PROGRAM", "LINE", "AVAILABILITY" };
            string[] conditions = { "SYSTEM", "LOGIC_PROGRAM", "MOTION_PROGRAM" };

            type = type.ToUpper();

            foreach (var s in samples) if (type.Contains(s)) return MTConnectCategory.Sample;
            foreach (var e in events) if (type.Contains(e)) return MTConnectCategory.Event;
            foreach (var c in conditions) if (type.Contains(c)) return MTConnectCategory.Condition;

            return MTConnectCategory.Sample;
        }

        private IEnumerator GetCurrentState()
        {
            string currentUrl = $"{agentUrl}/current";
            if (!string.IsNullOrEmpty(deviceName))
            {
                currentUrl += $"?device={deviceName}";
            }

            using (UnityWebRequest request = UnityWebRequest.Get(currentUrl))
            {
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    ParseCurrentResponse(request.downloadHandler.text);
                }
            }
        }

        private IEnumerator PollingLoop()
        {
            while (isConnected)
            {
                yield return new WaitForSeconds(pollingInterval);

                // Use sample endpoint with from/count for efficient polling
                string sampleUrl = $"{agentUrl}/sample?from={lastSequence + 1}&count=1000";
                if (!string.IsNullOrEmpty(deviceName))
                {
                    sampleUrl += $"&device={deviceName}";
                }

                using (UnityWebRequest request = UnityWebRequest.Get(sampleUrl))
                {
                    request.timeout = connectionTimeout;
                    yield return request.SendWebRequest();

                    if (request.result == UnityWebRequest.Result.Success)
                    {
                        ParseSampleResponse(request.downloadHandler.text);
                    }
                    else if (request.result == UnityWebRequest.Result.ConnectionError)
                    {
                        Debug.LogWarning($"[MTConnect] Connection lost: {request.error}");
                        Disconnect();
                    }
                }
            }
        }

        private IEnumerator StreamingSample()
        {
            // HTTP streaming endpoint (chunked transfer)
            string streamUrl = $"{agentUrl}/sample?interval=100&count=1000";

            // Note: Unity's UnityWebRequest doesn't support true HTTP streaming
            // For production, use a native WebSocket or custom HTTP client
            Debug.LogWarning("[MTConnect] HTTP streaming not fully supported in Unity, using polling instead");
            pollingCoroutine = StartCoroutine(PollingLoop());
            yield break;
        }

        private void ParseCurrentResponse(string xml)
        {
            ParseDataItems(xml, true);
        }

        private void ParseSampleResponse(string xml)
        {
            // Extract nextSequence
            var nextSeqMatch = Regex.Match(xml, @"nextSequence=""(\d+)""");
            if (nextSeqMatch.Success)
            {
                lastSequence = long.Parse(nextSeqMatch.Groups[1].Value);
            }

            ParseDataItems(xml, false);
        }

        private void ParseDataItems(string xml, bool isCurrentResponse)
        {
            var deviceData = new MTConnectDeviceData
            {
                deviceId = deviceName,
                timestamp = DateTime.UtcNow,
                samples = new Dictionary<string, MTConnectSample>(),
                events = new Dictionary<string, MTConnectEvent>(),
                conditions = new List<MTConnectCondition>()
            };

            // Parse position data items (samples)
            ParseSampleValues(xml, deviceData, "Position", @"<Position[^>]*dataItemId=""([^""]+)""[^>]*>([^<]+)</Position>");
            ParseSampleValues(xml, deviceData, "Load", @"<Load[^>]*dataItemId=""([^""]+)""[^>]*>([^<]+)</Load>");
            ParseSampleValues(xml, deviceData, "SpindleSpeed", @"<SpindleSpeed[^>]*dataItemId=""([^""]+)""[^>]*>([^<]+)</SpindleSpeed>");
            ParseSampleValues(xml, deviceData, "Temperature", @"<Temperature[^>]*dataItemId=""([^""]+)""[^>]*>([^<]+)</Temperature>");
            ParseSampleValues(xml, deviceData, "Velocity", @"<Velocity[^>]*dataItemId=""([^""]+)""[^>]*>([^<]+)</Velocity>");

            // Parse events
            ParseEventValues(xml, deviceData, "Execution", @"<Execution[^>]*dataItemId=""([^""]+)""[^>]*>([^<]+)</Execution>");
            ParseEventValues(xml, deviceData, "ControllerMode", @"<ControllerMode[^>]*dataItemId=""([^""]+)""[^>]*>([^<]+)</ControllerMode>");
            ParseEventValues(xml, deviceData, "Program", @"<Program[^>]*dataItemId=""([^""]+)""[^>]*>([^<]+)</Program>");
            ParseEventValues(xml, deviceData, "Line", @"<Line[^>]*dataItemId=""([^""]+)""[^>]*>([^<]+)</Line>");
            ParseEventValues(xml, deviceData, "EmergencyStop", @"<EmergencyStop[^>]*dataItemId=""([^""]+)""[^>]*>([^<]+)</EmergencyStop>");
            ParseEventValues(xml, deviceData, "Availability", @"<Availability[^>]*dataItemId=""([^""]+)""[^>]*>([^<]+)</Availability>");

            // Parse conditions
            ParseConditions(xml, deviceData);

            currentDeviceData = deviceData;
            OnDeviceDataReceived?.Invoke(deviceData);

            // Forward to sensor system if available
            ForwardToSensorSystem(deviceData);
        }

        private void ParseSampleValues(string xml, MTConnectDeviceData data, string type, string pattern)
        {
            var matches = Regex.Matches(xml, pattern);
            foreach (Match match in matches)
            {
                string dataItemId = match.Groups[1].Value;
                string valueStr = match.Groups[2].Value;

                if (float.TryParse(valueStr, out float value))
                {
                    var sample = new MTConnectSample
                    {
                        dataItemId = dataItemId,
                        type = type,
                        value = value,
                        timestamp = DateTime.UtcNow
                    };
                    data.samples[dataItemId] = sample;
                    OnSampleReceived?.Invoke(sample);
                }
            }
        }

        private void ParseEventValues(string xml, MTConnectDeviceData data, string type, string pattern)
        {
            var matches = Regex.Matches(xml, pattern);
            foreach (Match match in matches)
            {
                string dataItemId = match.Groups[1].Value;
                string value = match.Groups[2].Value;

                var evt = new MTConnectEvent
                {
                    dataItemId = dataItemId,
                    type = type,
                    value = value,
                    timestamp = DateTime.UtcNow
                };
                data.events[dataItemId] = evt;
            }
        }

        private void ParseConditions(string xml, MTConnectDeviceData data)
        {
            // Parse condition elements (Normal, Warning, Fault)
            var conditionPattern = @"<(Normal|Warning|Fault)[^>]*dataItemId=""([^""]+)""[^>]*>([^<]*)</(Normal|Warning|Fault)>";
            var matches = Regex.Matches(xml, conditionPattern);

            foreach (Match match in matches)
            {
                string level = match.Groups[1].Value;
                string dataItemId = match.Groups[2].Value;
                string message = match.Groups[3].Value;

                var condition = new MTConnectCondition
                {
                    dataItemId = dataItemId,
                    level = ParseConditionLevel(level),
                    message = message,
                    timestamp = DateTime.UtcNow
                };
                data.conditions.Add(condition);
                OnConditionReceived?.Invoke(condition);
            }
        }

        private ConditionLevel ParseConditionLevel(string level)
        {
            return level switch
            {
                "Normal" => ConditionLevel.Normal,
                "Warning" => ConditionLevel.Warning,
                "Fault" => ConditionLevel.Fault,
                _ => ConditionLevel.Unavailable
            };
        }

        private void ForwardToSensorSystem(MTConnectDeviceData data)
        {
            if (SensorSystem.Instance == null) return;

            // Convert MTConnect samples to sensor readings
            foreach (var kvp in data.samples)
            {
                var sample = kvp.Value;

                // Map MTConnect data items to sensor IDs
                string sensorId = MapDataItemToSensor(sample.dataItemId, sample.type);
                if (!string.IsNullOrEmpty(sensorId))
                {
                    SensorSystem.Instance.InjectSensorData(sensorId, sample.value);
                }
            }
        }

        private string MapDataItemToSensor(string dataItemId, string type)
        {
            // Map MTConnect data items to Unity sensor IDs
            // This mapping should be configured per installation
            return type switch
            {
                "Temperature" when dataItemId.Contains("spindle") => "temp-spindle",
                "Temperature" when dataItemId.Contains("motor") => "temp-motor",
                "Load" when dataItemId.Contains("X") => "current-x-axis",
                "Load" when dataItemId.Contains("Y") => "current-y-axis",
                "Load" when dataItemId.Contains("Z") => "current-z-axis",
                "Load" when dataItemId.Contains("spindle") => "current-spindle",
                _ => null
            };
        }

        /// <summary>
        /// Send an asset to the MTConnect agent (if supported)
        /// </summary>
        public void SendAsset(string assetId, string assetType, string body)
        {
            StartCoroutine(SendAssetCoroutine(assetId, assetType, body));
        }

        private IEnumerator SendAssetCoroutine(string assetId, string assetType, string body)
        {
            string assetUrl = $"{agentUrl}/assets/{assetId}?type={assetType}";

            using (UnityWebRequest request = UnityWebRequest.Put(assetUrl, body))
            {
                request.SetRequestHeader("Content-Type", "text/xml");
                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogError($"[MTConnect] Failed to send asset: {request.error}");
                }
                else
                {
                    Debug.Log($"[MTConnect] Asset sent: {assetId}");
                }
            }
        }

        /// <summary>
        /// Get specific data item value
        /// </summary>
        public float GetSampleValue(string dataItemId, float defaultValue = 0f)
        {
            if (currentDeviceData?.samples != null &&
                currentDeviceData.samples.TryGetValue(dataItemId, out var sample))
            {
                return sample.value;
            }
            return defaultValue;
        }

        /// <summary>
        /// Get specific event value
        /// </summary>
        public string GetEventValue(string dataItemId, string defaultValue = "")
        {
            if (currentDeviceData?.events != null &&
                currentDeviceData.events.TryGetValue(dataItemId, out var evt))
            {
                return evt.value;
            }
            return defaultValue;
        }

        /// <summary>
        /// Get axis positions as Vector3
        /// </summary>
        public Vector3 GetAxisPositions()
        {
            return new Vector3(
                GetSampleValue("Xact"),
                GetSampleValue("Yact"),
                GetSampleValue("Zact")
            );
        }

        /// <summary>
        /// Get axis loads as Vector3
        /// </summary>
        public Vector3 GetAxisLoads()
        {
            return new Vector3(
                GetSampleValue("Xload"),
                GetSampleValue("Yload"),
                GetSampleValue("Zload")
            );
        }

        // Public properties
        public bool IsConnected => isConnected;
        public string ConnectionStatus => connectionStatus;
        public MTConnectDeviceData CurrentData => currentDeviceData;
        public string AgentUrl => agentUrl;
    }

    // =========================================================================
    // MTConnect Data Types
    // =========================================================================

    public enum MTConnectVersion
    {
        V1_3,
        V1_4,
        V1_5,
        V1_6,
        V1_7,
        V1_8,
        V2_0
    }

    public enum MTConnectCategory
    {
        Sample,
        Event,
        Condition
    }

    public enum ConditionLevel
    {
        Unavailable,
        Normal,
        Warning,
        Fault
    }

    [Serializable]
    public class MTConnectDataItem
    {
        public string id;
        public string name;
        public string type;
        public MTConnectCategory category;
        public string units;
        public string subType;
    }

    [Serializable]
    public class MTConnectDeviceData
    {
        public string deviceId;
        public DateTime timestamp;
        public Dictionary<string, MTConnectSample> samples;
        public Dictionary<string, MTConnectEvent> events;
        public List<MTConnectCondition> conditions;
    }

    [Serializable]
    public class MTConnectSample
    {
        public string dataItemId;
        public string type;
        public float value;
        public DateTime timestamp;
        public long sequence;
    }

    [Serializable]
    public class MTConnectEvent
    {
        public string dataItemId;
        public string type;
        public string value;
        public DateTime timestamp;
        public long sequence;
    }

    [Serializable]
    public class MTConnectCondition
    {
        public string dataItemId;
        public ConditionLevel level;
        public string nativeCode;
        public string nativeSeverity;
        public string qualifier;
        public string message;
        public DateTime timestamp;
    }
}
