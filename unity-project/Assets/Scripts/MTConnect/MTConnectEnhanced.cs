using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Xml;
using UnityEngine;
using UnityEngine.Networking;

namespace CNC_SCADA.DigitalTwin.MTConnect
{
    /// <summary>
    /// Enhanced MTConnect Client with comprehensive data item support
    /// Supports streaming, conditions, assets, and advanced monitoring
    /// </summary>
    public class MTConnectEnhanced : MonoBehaviour
    {
        public static MTConnectEnhanced Instance { get; private set; }

        [Header("Agent Configuration")]
        [SerializeField] private string agentUrl = "http://localhost:5000";
        [SerializeField] private string deviceName = "CNC-001";
        [SerializeField] private float pollIntervalMs = 100f;
        [SerializeField] private bool useStreaming = true;
        [SerializeField] private int streamingHeartbeat = 10000;

        [Header("Data Collection")]
        [SerializeField] private bool collectSamples = true;
        [SerializeField] private bool collectEvents = true;
        [SerializeField] private bool collectConditions = true;
        [SerializeField] private bool collectAssets = true;

        [Header("Performance")]
        [SerializeField] private int maxStoredSamples = 10000;
        [SerializeField] private float sampleBufferFlushInterval = 1f;

        // Events
        public event Action OnConnected;
        public event Action OnDisconnected;
        public event Action<MTConnectDevice> OnDeviceProbed;
        public event Action<DataItemUpdate> OnDataItemUpdated;
        public event Action<Condition> OnConditionChanged;
        public event Action<Asset> OnAssetUpdated;
        public event Action<string> OnError;

        // State
        private bool isConnected = false;
        private bool isStreaming = false;
        private long currentSequence = 0;
        private long nextSequence = 0;
        private MTConnectDevice currentDevice;

        // Data storage
        private Dictionary<string, DataItem> dataItems = new Dictionary<string, DataItem>();
        private Dictionary<string, List<Sample>> sampleHistory = new Dictionary<string, List<Sample>>();
        private Dictionary<string, Condition> activeConditions = new Dictionary<string, Condition>();
        private Dictionary<string, Asset> assets = new Dictionary<string, Asset>();
        private Queue<DataItemUpdate> updateQueue = new Queue<DataItemUpdate>();

        // Statistics
        private MTConnectStatistics statistics = new MTConnectStatistics();

        public bool IsConnected => isConnected;
        public MTConnectDevice Device => currentDevice;
        public long CurrentSequence => currentSequence;
        public int DataItemCount => dataItems.Count;
        public int ActiveConditionCount => activeConditions.Count(c => c.Value.Level != ConditionLevel.Normal);

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

        private void Update()
        {
            // Process update queue
            ProcessUpdateQueue();
        }

        #region Connection Management

        public void Connect()
        {
            StartCoroutine(ConnectCoroutine());
        }

        private IEnumerator ConnectCoroutine()
        {
            Debug.Log($"[MTConnect] Connecting to {agentUrl}...");

            // First, probe the device
            yield return ProbeDevice();

            if (currentDevice == null)
            {
                OnError?.Invoke("Failed to probe device");
                yield break;
            }

            // Get current state
            yield return GetCurrentState();

            isConnected = true;
            OnConnected?.Invoke();
            Debug.Log($"[MTConnect] Connected to {currentDevice.Name}");

            // Start streaming or polling
            if (useStreaming)
            {
                StartCoroutine(StreamData());
            }
            else
            {
                StartCoroutine(PollData());
            }
        }

        public void Disconnect()
        {
            isConnected = false;
            isStreaming = false;
            StopAllCoroutines();
            OnDisconnected?.Invoke();
            Debug.Log("[MTConnect] Disconnected");
        }

        #endregion

        #region Device Probe

        private IEnumerator ProbeDevice()
        {
            string probeUrl = $"{agentUrl}/probe";

            using (var request = UnityWebRequest.Get(probeUrl))
            {
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    ParseProbeResponse(request.downloadHandler.text);
                }
                else
                {
                    OnError?.Invoke($"Probe failed: {request.error}");
                }
            }
        }

        private void ParseProbeResponse(string xml)
        {
            try
            {
                var doc = new XmlDocument();
                doc.LoadXml(xml);

                var nsManager = new XmlNamespaceManager(doc.NameTable);
                nsManager.AddNamespace("m", "urn:mtconnect.org:MTConnectDevices:2.0");

                var deviceNode = doc.SelectSingleNode("//m:Device", nsManager);
                if (deviceNode == null) return;

                currentDevice = new MTConnectDevice
                {
                    Id = deviceNode.Attributes["id"]?.Value,
                    Name = deviceNode.Attributes["name"]?.Value,
                    Uuid = deviceNode.Attributes["uuid"]?.Value,
                    Components = new List<Component>(),
                    DataItems = new List<DataItemDefinition>()
                };

                // Parse components
                ParseComponents(deviceNode, nsManager, currentDevice.Components);

                // Parse data items
                ParseDataItemDefinitions(deviceNode, nsManager);

                OnDeviceProbed?.Invoke(currentDevice);
                Debug.Log($"[MTConnect] Probed device: {currentDevice.Name} with {dataItems.Count} data items");
            }
            catch (Exception ex)
            {
                OnError?.Invoke($"Parse error: {ex.Message}");
            }
        }

        private void ParseComponents(XmlNode parentNode, XmlNamespaceManager nsManager, List<Component> components)
        {
            var componentNodes = parentNode.SelectNodes("m:Components/*", nsManager);
            if (componentNodes == null) return;

            foreach (XmlNode node in componentNodes)
            {
                var component = new Component
                {
                    Type = node.LocalName,
                    Id = node.Attributes["id"]?.Value,
                    Name = node.Attributes["name"]?.Value,
                    SubComponents = new List<Component>()
                };

                // Parse sub-components recursively
                ParseComponents(node, nsManager, component.SubComponents);

                components.Add(component);
            }
        }

        private void ParseDataItemDefinitions(XmlNode deviceNode, XmlNamespaceManager nsManager)
        {
            var dataItemNodes = deviceNode.SelectNodes("//m:DataItem", nsManager);
            if (dataItemNodes == null) return;

            foreach (XmlNode node in dataItemNodes)
            {
                var definition = new DataItemDefinition
                {
                    Id = node.Attributes["id"]?.Value,
                    Name = node.Attributes["name"]?.Value,
                    Type = node.Attributes["type"]?.Value,
                    Category = ParseCategory(node.Attributes["category"]?.Value),
                    SubType = node.Attributes["subType"]?.Value,
                    Units = node.Attributes["units"]?.Value,
                    NativeUnits = node.Attributes["nativeUnits"]?.Value,
                    CoordinateSystem = node.Attributes["coordinateSystem"]?.Value,
                    Statistic = node.Attributes["statistic"]?.Value
                };

                // Create data item instance
                var dataItem = new DataItem
                {
                    Definition = definition,
                    Value = null,
                    Timestamp = DateTime.MinValue,
                    Sequence = 0
                };

                dataItems[definition.Id] = dataItem;
                currentDevice.DataItems.Add(definition);

                // Initialize sample history for samples
                if (definition.Category == DataCategory.Sample)
                {
                    sampleHistory[definition.Id] = new List<Sample>();
                }
            }
        }

        private DataCategory ParseCategory(string category)
        {
            return category?.ToUpper() switch
            {
                "SAMPLE" => DataCategory.Sample,
                "EVENT" => DataCategory.Event,
                "CONDITION" => DataCategory.Condition,
                _ => DataCategory.Sample
            };
        }

        #endregion

        #region Current State

        private IEnumerator GetCurrentState()
        {
            string currentUrl = $"{agentUrl}/current?device={deviceName}";

            using (var request = UnityWebRequest.Get(currentUrl))
            {
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    ParseStreamsResponse(request.downloadHandler.text);
                }
                else
                {
                    OnError?.Invoke($"Current request failed: {request.error}");
                }
            }
        }

        #endregion

        #region Data Streaming

        private IEnumerator StreamData()
        {
            isStreaming = true;
            string streamUrl = $"{agentUrl}/sample?from={nextSequence}&count=1000&interval={pollIntervalMs}&heartbeat={streamingHeartbeat}";

            while (isConnected && isStreaming)
            {
                using (var request = UnityWebRequest.Get(streamUrl))
                {
                    request.timeout = streamingHeartbeat / 1000 + 5;
                    yield return request.SendWebRequest();

                    if (request.result == UnityWebRequest.Result.Success)
                    {
                        ParseStreamsResponse(request.downloadHandler.text);
                        statistics.SuccessfulRequests++;
                    }
                    else if (request.result == UnityWebRequest.Result.ConnectionError)
                    {
                        OnError?.Invoke("Connection lost, attempting reconnect...");
                        statistics.FailedRequests++;
                        yield return new WaitForSeconds(1f);
                    }
                }

                // Update stream URL with new sequence
                streamUrl = $"{agentUrl}/sample?from={nextSequence}&count=1000&interval={pollIntervalMs}&heartbeat={streamingHeartbeat}";
            }
        }

        private IEnumerator PollData()
        {
            while (isConnected)
            {
                yield return new WaitForSeconds(pollIntervalMs / 1000f);

                string sampleUrl = $"{agentUrl}/sample?from={nextSequence}&count=100";

                using (var request = UnityWebRequest.Get(sampleUrl))
                {
                    yield return request.SendWebRequest();

                    if (request.result == UnityWebRequest.Result.Success)
                    {
                        ParseStreamsResponse(request.downloadHandler.text);
                        statistics.SuccessfulRequests++;
                    }
                    else
                    {
                        statistics.FailedRequests++;
                    }
                }
            }
        }

        private void ParseStreamsResponse(string xml)
        {
            try
            {
                var doc = new XmlDocument();
                doc.LoadXml(xml);

                var nsManager = new XmlNamespaceManager(doc.NameTable);
                nsManager.AddNamespace("m", "urn:mtconnect.org:MTConnectStreams:2.0");

                // Get header info
                var header = doc.SelectSingleNode("//m:Header", nsManager);
                if (header != null)
                {
                    nextSequence = long.Parse(header.Attributes["nextSequence"]?.Value ?? "0");
                    currentSequence = long.Parse(header.Attributes["lastSequence"]?.Value ?? "0");
                }

                // Parse samples
                if (collectSamples)
                {
                    ParseSamples(doc, nsManager);
                }

                // Parse events
                if (collectEvents)
                {
                    ParseEvents(doc, nsManager);
                }

                // Parse conditions
                if (collectConditions)
                {
                    ParseConditions(doc, nsManager);
                }

                statistics.TotalUpdates++;
            }
            catch (Exception ex)
            {
                OnError?.Invoke($"Stream parse error: {ex.Message}");
            }
        }

        private void ParseSamples(XmlDocument doc, XmlNamespaceManager nsManager)
        {
            var samplesNode = doc.SelectSingleNode("//m:Samples", nsManager);
            if (samplesNode == null) return;

            foreach (XmlNode node in samplesNode.ChildNodes)
            {
                string dataItemId = node.Attributes["dataItemId"]?.Value;
                if (string.IsNullOrEmpty(dataItemId)) continue;

                if (!dataItems.TryGetValue(dataItemId, out var dataItem)) continue;

                var update = new DataItemUpdate
                {
                    DataItemId = dataItemId,
                    Name = node.Attributes["name"]?.Value ?? dataItem.Definition.Name,
                    Type = node.LocalName,
                    Value = node.InnerText,
                    Timestamp = ParseTimestamp(node.Attributes["timestamp"]?.Value),
                    Sequence = long.Parse(node.Attributes["sequence"]?.Value ?? "0")
                };

                // Update data item
                dataItem.Value = ParseValue(node.InnerText, dataItem.Definition.Type);
                dataItem.Timestamp = update.Timestamp;
                dataItem.Sequence = update.Sequence;

                // Store in history
                if (sampleHistory.TryGetValue(dataItemId, out var history))
                {
                    history.Add(new Sample
                    {
                        Timestamp = update.Timestamp,
                        Value = (float)dataItem.Value,
                        Sequence = update.Sequence
                    });

                    // Trim history
                    if (history.Count > maxStoredSamples)
                    {
                        history.RemoveAt(0);
                    }
                }

                updateQueue.Enqueue(update);
                statistics.SamplesReceived++;
            }
        }

        private void ParseEvents(XmlDocument doc, XmlNamespaceManager nsManager)
        {
            var eventsNode = doc.SelectSingleNode("//m:Events", nsManager);
            if (eventsNode == null) return;

            foreach (XmlNode node in eventsNode.ChildNodes)
            {
                string dataItemId = node.Attributes["dataItemId"]?.Value;
                if (string.IsNullOrEmpty(dataItemId)) continue;

                if (!dataItems.TryGetValue(dataItemId, out var dataItem)) continue;

                var update = new DataItemUpdate
                {
                    DataItemId = dataItemId,
                    Name = node.Attributes["name"]?.Value ?? dataItem.Definition.Name,
                    Type = node.LocalName,
                    Value = node.InnerText,
                    Timestamp = ParseTimestamp(node.Attributes["timestamp"]?.Value),
                    Sequence = long.Parse(node.Attributes["sequence"]?.Value ?? "0")
                };

                // Handle special event types
                switch (node.LocalName)
                {
                    case "Execution":
                        statistics.LastExecution = node.InnerText;
                        break;
                    case "ControllerMode":
                        statistics.LastControllerMode = node.InnerText;
                        break;
                    case "EmergencyStop":
                        if (node.InnerText == "TRIGGERED")
                        {
                            OnError?.Invoke("Emergency Stop Triggered!");
                        }
                        break;
                    case "Program":
                        statistics.CurrentProgram = node.InnerText;
                        break;
                    case "Block":
                        statistics.CurrentBlock = node.InnerText;
                        break;
                    case "Line":
                        statistics.CurrentLine = int.TryParse(node.InnerText, out int line) ? line : 0;
                        break;
                }

                dataItem.Value = node.InnerText;
                dataItem.Timestamp = update.Timestamp;
                dataItem.Sequence = update.Sequence;

                updateQueue.Enqueue(update);
                statistics.EventsReceived++;
            }
        }

        private void ParseConditions(XmlDocument doc, XmlNamespaceManager nsManager)
        {
            var conditionsNode = doc.SelectSingleNode("//m:Condition", nsManager);
            if (conditionsNode == null) return;

            foreach (XmlNode node in conditionsNode.ChildNodes)
            {
                string dataItemId = node.Attributes["dataItemId"]?.Value;
                if (string.IsNullOrEmpty(dataItemId)) continue;

                var condition = new Condition
                {
                    DataItemId = dataItemId,
                    Type = node.Attributes["type"]?.Value,
                    Level = ParseConditionLevel(node.LocalName),
                    NativeCode = node.Attributes["nativeCode"]?.Value,
                    NativeSeverity = node.Attributes["nativeSeverity"]?.Value,
                    Qualifier = node.Attributes["qualifier"]?.Value,
                    Message = node.InnerText,
                    Timestamp = ParseTimestamp(node.Attributes["timestamp"]?.Value),
                    Sequence = long.Parse(node.Attributes["sequence"]?.Value ?? "0")
                };

                // Update or add condition
                string conditionKey = $"{dataItemId}_{condition.NativeCode ?? "default"}";
                bool isNew = !activeConditions.ContainsKey(conditionKey);
                activeConditions[conditionKey] = condition;

                if (condition.Level != ConditionLevel.Normal || isNew)
                {
                    OnConditionChanged?.Invoke(condition);
                }

                statistics.ConditionsReceived++;
            }
        }

        private ConditionLevel ParseConditionLevel(string level)
        {
            return level?.ToUpper() switch
            {
                "NORMAL" => ConditionLevel.Normal,
                "WARNING" => ConditionLevel.Warning,
                "FAULT" => ConditionLevel.Fault,
                "UNAVAILABLE" => ConditionLevel.Unavailable,
                _ => ConditionLevel.Normal
            };
        }

        private DateTime ParseTimestamp(string timestamp)
        {
            if (DateTime.TryParse(timestamp, out var dt))
            {
                return dt;
            }
            return DateTime.UtcNow;
        }

        private object ParseValue(string value, string type)
        {
            if (string.IsNullOrEmpty(value) || value == "UNAVAILABLE")
            {
                return null;
            }

            // Try to parse as number for sample types
            if (float.TryParse(value, out float numValue))
            {
                return numValue;
            }

            return value;
        }

        private void ProcessUpdateQueue()
        {
            int maxPerFrame = 100;
            int processed = 0;

            while (updateQueue.Count > 0 && processed < maxPerFrame)
            {
                var update = updateQueue.Dequeue();
                OnDataItemUpdated?.Invoke(update);
                processed++;
            }
        }

        #endregion

        #region Asset Management

        public IEnumerator GetAssets()
        {
            if (!collectAssets) yield break;

            string assetUrl = $"{agentUrl}/asset";

            using (var request = UnityWebRequest.Get(assetUrl))
            {
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    ParseAssetsResponse(request.downloadHandler.text);
                }
            }
        }

        private void ParseAssetsResponse(string xml)
        {
            try
            {
                var doc = new XmlDocument();
                doc.LoadXml(xml);

                var nsManager = new XmlNamespaceManager(doc.NameTable);
                nsManager.AddNamespace("m", "urn:mtconnect.org:MTConnectAssets:2.0");

                var assetNodes = doc.SelectNodes("//m:Asset", nsManager);
                if (assetNodes == null) return;

                foreach (XmlNode node in assetNodes)
                {
                    var asset = new Asset
                    {
                        AssetId = node.Attributes["assetId"]?.Value,
                        Type = node.LocalName,
                        Timestamp = ParseTimestamp(node.Attributes["timestamp"]?.Value),
                        DeviceUuid = node.Attributes["deviceUuid"]?.Value,
                        Removed = bool.Parse(node.Attributes["removed"]?.Value ?? "false"),
                        Properties = new Dictionary<string, string>()
                    };

                    // Parse asset-specific properties
                    foreach (XmlNode child in node.ChildNodes)
                    {
                        asset.Properties[child.LocalName] = child.InnerText;
                    }

                    assets[asset.AssetId] = asset;
                    OnAssetUpdated?.Invoke(asset);
                }
            }
            catch (Exception ex)
            {
                OnError?.Invoke($"Asset parse error: {ex.Message}");
            }
        }

        public IEnumerator StoreAsset(string assetId, string assetType, string assetXml)
        {
            string assetUrl = $"{agentUrl}/asset/{assetId}";

            using (var request = new UnityWebRequest(assetUrl, "POST"))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(assetXml);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/xml");

                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    OnError?.Invoke($"Failed to store asset: {request.error}");
                }
            }
        }

        #endregion

        #region Data Access

        public DataItem GetDataItem(string dataItemId)
        {
            return dataItems.TryGetValue(dataItemId, out var item) ? item : null;
        }

        public T GetValue<T>(string dataItemId)
        {
            if (dataItems.TryGetValue(dataItemId, out var item) && item.Value != null)
            {
                try
                {
                    return (T)Convert.ChangeType(item.Value, typeof(T));
                }
                catch
                {
                    return default;
                }
            }
            return default;
        }

        public float GetPosition(string axis)
        {
            string dataItemId = $"Xabs"; // Example - would need proper mapping
            return GetValue<float>(dataItemId);
        }

        public List<Sample> GetSampleHistory(string dataItemId, int count = 100)
        {
            if (sampleHistory.TryGetValue(dataItemId, out var history))
            {
                return history.TakeLast(count).ToList();
            }
            return new List<Sample>();
        }

        public List<Condition> GetActiveConditions(ConditionLevel minLevel = ConditionLevel.Warning)
        {
            return activeConditions.Values
                .Where(c => c.Level >= minLevel)
                .OrderByDescending(c => c.Level)
                .ToList();
        }

        public Asset GetAsset(string assetId)
        {
            return assets.TryGetValue(assetId, out var asset) ? asset : null;
        }

        public List<Asset> GetAssetsByType(string assetType)
        {
            return assets.Values.Where(a => a.Type == assetType && !a.Removed).ToList();
        }

        #endregion

        #region Common Data Items

        // Convenience methods for common data items
        public MachineState GetMachineState()
        {
            return new MachineState
            {
                Execution = GetValue<string>("execution") ?? "UNAVAILABLE",
                ControllerMode = GetValue<string>("mode") ?? "UNAVAILABLE",
                Program = GetValue<string>("program"),
                Block = GetValue<string>("block"),
                Line = GetValue<int>("line"),
                PathFeedrate = GetValue<float>("path_feedrate"),
                PathPosition = new Vector3(
                    GetValue<float>("Xabs"),
                    GetValue<float>("Yabs"),
                    GetValue<float>("Zabs")
                ),
                SpindleSpeed = GetValue<float>("Sspeed"),
                SpindleLoad = GetValue<float>("Sload"),
                ToolNumber = GetValue<int>("tool_number"),
                PartCount = GetValue<int>("part_count"),
                EmergencyStop = GetValue<string>("estop") == "TRIGGERED"
            };
        }

        public AxisState GetAxisState(string axis)
        {
            string prefix = axis.ToLower();
            return new AxisState
            {
                Name = axis,
                Position = GetValue<float>($"{prefix}pos"),
                ActualPosition = GetValue<float>($"{prefix}act"),
                CommandedPosition = GetValue<float>($"{prefix}cmd"),
                Load = GetValue<float>($"{prefix}load"),
                Temperature = GetValue<float>($"{prefix}temp"),
                Following = GetValue<float>($"{prefix}following")
            };
        }

        public SpindleState GetSpindleState()
        {
            return new SpindleState
            {
                Speed = GetValue<float>("Sspeed"),
                CommandedSpeed = GetValue<float>("Scmd"),
                Load = GetValue<float>("Sload"),
                Temperature = GetValue<float>("Stemp"),
                RotaryMode = GetValue<string>("Srotary"),
                Override = GetValue<float>("Sovr")
            };
        }

        #endregion

        #region Statistics

        public MTConnectStatistics GetStatistics()
        {
            statistics.Uptime = isConnected ? Time.time : 0;
            statistics.DataItemCount = dataItems.Count;
            statistics.ActiveConditions = ActiveConditionCount;
            return statistics;
        }

        #endregion
    }

    #region Data Classes

    [Serializable]
    public class MTConnectDevice
    {
        public string Id;
        public string Name;
        public string Uuid;
        public List<Component> Components;
        public List<DataItemDefinition> DataItems;
    }

    [Serializable]
    public class Component
    {
        public string Type;
        public string Id;
        public string Name;
        public List<Component> SubComponents;
    }

    [Serializable]
    public class DataItemDefinition
    {
        public string Id;
        public string Name;
        public string Type;
        public DataCategory Category;
        public string SubType;
        public string Units;
        public string NativeUnits;
        public string CoordinateSystem;
        public string Statistic;
    }

    public enum DataCategory
    {
        Sample,
        Event,
        Condition
    }

    [Serializable]
    public class DataItem
    {
        public DataItemDefinition Definition;
        public object Value;
        public DateTime Timestamp;
        public long Sequence;
    }

    [Serializable]
    public class DataItemUpdate
    {
        public string DataItemId;
        public string Name;
        public string Type;
        public string Value;
        public DateTime Timestamp;
        public long Sequence;
    }

    [Serializable]
    public class Sample
    {
        public DateTime Timestamp;
        public float Value;
        public long Sequence;
    }

    [Serializable]
    public class Condition
    {
        public string DataItemId;
        public string Type;
        public ConditionLevel Level;
        public string NativeCode;
        public string NativeSeverity;
        public string Qualifier;
        public string Message;
        public DateTime Timestamp;
        public long Sequence;
    }

    public enum ConditionLevel
    {
        Normal = 0,
        Warning = 1,
        Fault = 2,
        Unavailable = 3
    }

    [Serializable]
    public class Asset
    {
        public string AssetId;
        public string Type;
        public DateTime Timestamp;
        public string DeviceUuid;
        public bool Removed;
        public Dictionary<string, string> Properties;
    }

    [Serializable]
    public class MachineState
    {
        public string Execution;
        public string ControllerMode;
        public string Program;
        public string Block;
        public int Line;
        public float PathFeedrate;
        public Vector3 PathPosition;
        public float SpindleSpeed;
        public float SpindleLoad;
        public int ToolNumber;
        public int PartCount;
        public bool EmergencyStop;
    }

    [Serializable]
    public class AxisState
    {
        public string Name;
        public float Position;
        public float ActualPosition;
        public float CommandedPosition;
        public float Load;
        public float Temperature;
        public float Following;
    }

    [Serializable]
    public class SpindleState
    {
        public float Speed;
        public float CommandedSpeed;
        public float Load;
        public float Temperature;
        public string RotaryMode;
        public float Override;
    }

    [Serializable]
    public class MTConnectStatistics
    {
        public float Uptime;
        public int DataItemCount;
        public int SamplesReceived;
        public int EventsReceived;
        public int ConditionsReceived;
        public int ActiveConditions;
        public int SuccessfulRequests;
        public int FailedRequests;
        public int TotalUpdates;
        public string LastExecution;
        public string LastControllerMode;
        public string CurrentProgram;
        public string CurrentBlock;
        public int CurrentLine;
    }

    #endregion
}
