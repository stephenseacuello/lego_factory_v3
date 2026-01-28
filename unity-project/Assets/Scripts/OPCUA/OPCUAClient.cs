using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;

namespace CNCScada.OPCUA
{
    /// <summary>
    /// OPC UA client for industrial automation integration.
    /// Connects to OPC UA servers via HTTP REST proxy for Unity WebGL compatibility.
    /// Supports browsing, reading, writing, and subscribing to nodes.
    /// </summary>
    public class OPCUAClient : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string proxyUrl = "http://localhost:5001/api/opcua";
        [SerializeField] private string serverEndpoint = "opc.tcp://localhost:4840";
        [SerializeField] private bool autoConnect = true;
        [SerializeField] private float reconnectInterval = 5f;

        [Header("Authentication")]
        [SerializeField] private SecurityMode securityMode = SecurityMode.None;
        [SerializeField] private string username = "";
        [SerializeField] private string password = "";

        [Header("Subscription Settings")]
        [SerializeField] private float defaultPublishingInterval = 100f; // milliseconds
        [SerializeField] private int maxNotificationsPerPublish = 100;

        [Header("Status")]
        [SerializeField] private ConnectionState connectionState = ConnectionState.Disconnected;
        [SerializeField] private string serverApplicationName = "";
        [SerializeField] private int activeSubscriptions = 0;

        // Node cache
        private Dictionary<string, OPCUANode> nodeCache = new Dictionary<string, OPCUANode>();
        private Dictionary<string, List<Action<OPCUADataValue>>> subscriptions = new Dictionary<string, List<Action<OPCUADataValue>>>();
        private Coroutine pollingCoroutine;

        // Events
        public event Action OnConnected;
        public event Action OnDisconnected;
        public event Action<string> OnError;
        public event Action<OPCUADataValue> OnDataChanged;

        // Singleton
        public static OPCUAClient Instance { get; private set; }

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

        // =========================================================================
        // Connection Management
        // =========================================================================

        /// <summary>
        /// Connect to OPC UA server via proxy
        /// </summary>
        public void Connect()
        {
            if (connectionState == ConnectionState.Connected || connectionState == ConnectionState.Connecting)
            {
                return;
            }

            StartCoroutine(ConnectAsync());
        }

        private IEnumerator ConnectAsync()
        {
            connectionState = ConnectionState.Connecting;
            Debug.Log($"[OPCUAClient] Connecting to {serverEndpoint} via {proxyUrl}");

            // Create connection request
            var request = new OPCUAConnectRequest
            {
                serverEndpoint = serverEndpoint,
                securityMode = securityMode.ToString(),
                username = username,
                password = password
            };

            string jsonBody = JsonUtility.ToJson(request);

            using (UnityWebRequest webRequest = new UnityWebRequest($"{proxyUrl}/connect", "POST"))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonBody);
                webRequest.uploadHandler = new UploadHandlerRaw(bodyRaw);
                webRequest.downloadHandler = new DownloadHandlerBuffer();
                webRequest.SetRequestHeader("Content-Type", "application/json");
                webRequest.timeout = 10;

                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    var response = JsonUtility.FromJson<OPCUAConnectResponse>(webRequest.downloadHandler.text);

                    if (response.success)
                    {
                        connectionState = ConnectionState.Connected;
                        serverApplicationName = response.serverName;

                        Debug.Log($"[OPCUAClient] Connected to {serverApplicationName}");
                        OnConnected?.Invoke();

                        // Start polling for subscriptions
                        if (pollingCoroutine != null)
                        {
                            StopCoroutine(pollingCoroutine);
                        }
                        pollingCoroutine = StartCoroutine(PollSubscriptions());
                    }
                    else
                    {
                        connectionState = ConnectionState.Error;
                        Debug.LogError($"[OPCUAClient] Connection failed: {response.error}");
                        OnError?.Invoke(response.error);

                        // Schedule reconnect
                        StartCoroutine(ScheduleReconnect());
                    }
                }
                else
                {
                    connectionState = ConnectionState.Error;
                    Debug.LogError($"[OPCUAClient] Connection error: {webRequest.error}");
                    OnError?.Invoke(webRequest.error);

                    // Schedule reconnect
                    StartCoroutine(ScheduleReconnect());
                }
            }
        }

        private IEnumerator ScheduleReconnect()
        {
            yield return new WaitForSeconds(reconnectInterval);

            if (connectionState != ConnectionState.Connected)
            {
                Connect();
            }
        }

        /// <summary>
        /// Disconnect from OPC UA server
        /// </summary>
        public void Disconnect()
        {
            if (connectionState != ConnectionState.Connected)
            {
                return;
            }

            if (pollingCoroutine != null)
            {
                StopCoroutine(pollingCoroutine);
                pollingCoroutine = null;
            }

            StartCoroutine(DisconnectAsync());
        }

        private IEnumerator DisconnectAsync()
        {
            using (UnityWebRequest webRequest = UnityWebRequest.PostWwwForm($"{proxyUrl}/disconnect", ""))
            {
                webRequest.timeout = 5;
                yield return webRequest.SendWebRequest();
            }

            connectionState = ConnectionState.Disconnected;
            subscriptions.Clear();
            activeSubscriptions = 0;

            Debug.Log("[OPCUAClient] Disconnected");
            OnDisconnected?.Invoke();
        }

        // =========================================================================
        // Node Operations
        // =========================================================================

        /// <summary>
        /// Browse nodes starting from a given node ID
        /// </summary>
        public void BrowseNodes(string nodeId, Action<List<OPCUANode>> callback)
        {
            StartCoroutine(BrowseNodesAsync(nodeId, callback));
        }

        private IEnumerator BrowseNodesAsync(string nodeId, Action<List<OPCUANode>> callback)
        {
            string url = $"{proxyUrl}/browse?nodeId={UnityWebRequest.EscapeURL(nodeId)}";

            using (UnityWebRequest webRequest = UnityWebRequest.Get(url))
            {
                webRequest.timeout = 10;
                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    var response = JsonUtility.FromJson<OPCUABrowseResponse>(webRequest.downloadHandler.text);
                    callback?.Invoke(response.nodes);

                    // Cache nodes
                    foreach (var node in response.nodes)
                    {
                        nodeCache[node.nodeId] = node;
                    }
                }
                else
                {
                    Debug.LogError($"[OPCUAClient] Browse error: {webRequest.error}");
                    callback?.Invoke(new List<OPCUANode>());
                }
            }
        }

        /// <summary>
        /// Read value from a node
        /// </summary>
        public void ReadValue(string nodeId, Action<OPCUADataValue> callback)
        {
            StartCoroutine(ReadValueAsync(nodeId, callback));
        }

        private IEnumerator ReadValueAsync(string nodeId, Action<OPCUADataValue> callback)
        {
            string url = $"{proxyUrl}/read?nodeId={UnityWebRequest.EscapeURL(nodeId)}";

            using (UnityWebRequest webRequest = UnityWebRequest.Get(url))
            {
                webRequest.timeout = 5;
                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    var dataValue = JsonUtility.FromJson<OPCUADataValue>(webRequest.downloadHandler.text);
                    callback?.Invoke(dataValue);
                }
                else
                {
                    Debug.LogError($"[OPCUAClient] Read error for {nodeId}: {webRequest.error}");
                    callback?.Invoke(null);
                }
            }
        }

        /// <summary>
        /// Read multiple values at once
        /// </summary>
        public void ReadValues(string[] nodeIds, Action<Dictionary<string, OPCUADataValue>> callback)
        {
            StartCoroutine(ReadValuesAsync(nodeIds, callback));
        }

        private IEnumerator ReadValuesAsync(string[] nodeIds, Action<Dictionary<string, OPCUADataValue>> callback)
        {
            var request = new OPCUAReadRequest { nodeIds = nodeIds };
            string jsonBody = JsonUtility.ToJson(request);

            using (UnityWebRequest webRequest = new UnityWebRequest($"{proxyUrl}/read-multi", "POST"))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonBody);
                webRequest.uploadHandler = new UploadHandlerRaw(bodyRaw);
                webRequest.downloadHandler = new DownloadHandlerBuffer();
                webRequest.SetRequestHeader("Content-Type", "application/json");
                webRequest.timeout = 10;

                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    var response = JsonUtility.FromJson<OPCUAReadMultiResponse>(webRequest.downloadHandler.text);
                    var result = new Dictionary<string, OPCUADataValue>();

                    for (int i = 0; i < response.values.Length; i++)
                    {
                        result[nodeIds[i]] = response.values[i];
                    }

                    callback?.Invoke(result);
                }
                else
                {
                    Debug.LogError($"[OPCUAClient] Read multi error: {webRequest.error}");
                    callback?.Invoke(new Dictionary<string, OPCUADataValue>());
                }
            }
        }

        /// <summary>
        /// Write value to a node
        /// </summary>
        public void WriteValue(string nodeId, object value, Action<bool> callback = null)
        {
            StartCoroutine(WriteValueAsync(nodeId, value, callback));
        }

        private IEnumerator WriteValueAsync(string nodeId, object value, Action<bool> callback)
        {
            var request = new OPCUAWriteRequest
            {
                nodeId = nodeId,
                value = value.ToString(),
                valueType = value.GetType().Name
            };

            string jsonBody = JsonUtility.ToJson(request);

            using (UnityWebRequest webRequest = new UnityWebRequest($"{proxyUrl}/write", "POST"))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonBody);
                webRequest.uploadHandler = new UploadHandlerRaw(bodyRaw);
                webRequest.downloadHandler = new DownloadHandlerBuffer();
                webRequest.SetRequestHeader("Content-Type", "application/json");
                webRequest.timeout = 5;

                yield return webRequest.SendWebRequest();

                bool success = webRequest.result == UnityWebRequest.Result.Success;

                if (!success)
                {
                    Debug.LogError($"[OPCUAClient] Write error for {nodeId}: {webRequest.error}");
                }

                callback?.Invoke(success);
            }
        }

        // =========================================================================
        // Subscriptions
        // =========================================================================

        /// <summary>
        /// Subscribe to data changes on a node
        /// </summary>
        public void Subscribe(string nodeId, Action<OPCUADataValue> callback)
        {
            if (!subscriptions.ContainsKey(nodeId))
            {
                subscriptions[nodeId] = new List<Action<OPCUADataValue>>();

                // Create subscription on server
                StartCoroutine(CreateSubscription(nodeId));
            }

            subscriptions[nodeId].Add(callback);
            Debug.Log($"[OPCUAClient] Subscribed to {nodeId}");
        }

        /// <summary>
        /// Unsubscribe from a node
        /// </summary>
        public void Unsubscribe(string nodeId, Action<OPCUADataValue> callback)
        {
            if (subscriptions.ContainsKey(nodeId))
            {
                subscriptions[nodeId].Remove(callback);

                if (subscriptions[nodeId].Count == 0)
                {
                    subscriptions.Remove(nodeId);
                    StartCoroutine(DeleteSubscription(nodeId));
                }
            }
        }

        private IEnumerator CreateSubscription(string nodeId)
        {
            var request = new OPCUASubscribeRequest
            {
                nodeId = nodeId,
                publishingInterval = defaultPublishingInterval
            };

            string jsonBody = JsonUtility.ToJson(request);

            using (UnityWebRequest webRequest = new UnityWebRequest($"{proxyUrl}/subscribe", "POST"))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonBody);
                webRequest.uploadHandler = new UploadHandlerRaw(bodyRaw);
                webRequest.downloadHandler = new DownloadHandlerBuffer();
                webRequest.SetRequestHeader("Content-Type", "application/json");
                webRequest.timeout = 5;

                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    activeSubscriptions++;
                    Debug.Log($"[OPCUAClient] Subscription created for {nodeId}");
                }
                else
                {
                    Debug.LogError($"[OPCUAClient] Subscribe error: {webRequest.error}");
                }
            }
        }

        private IEnumerator DeleteSubscription(string nodeId)
        {
            using (UnityWebRequest webRequest = UnityWebRequest.Delete($"{proxyUrl}/unsubscribe?nodeId={UnityWebRequest.EscapeURL(nodeId)}"))
            {
                webRequest.timeout = 5;
                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    activeSubscriptions--;
                    Debug.Log($"[OPCUAClient] Subscription deleted for {nodeId}");
                }
            }
        }

        private IEnumerator PollSubscriptions()
        {
            while (connectionState == ConnectionState.Connected)
            {
                if (subscriptions.Count > 0)
                {
                    yield return StartCoroutine(FetchSubscriptionData());
                }

                yield return new WaitForSeconds(defaultPublishingInterval / 1000f);
            }
        }

        private IEnumerator FetchSubscriptionData()
        {
            using (UnityWebRequest webRequest = UnityWebRequest.Get($"{proxyUrl}/poll"))
            {
                webRequest.timeout = 5;
                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    var response = JsonUtility.FromJson<OPCUAPollResponse>(webRequest.downloadHandler.text);

                    foreach (var dataChange in response.dataChanges)
                    {
                        if (subscriptions.ContainsKey(dataChange.nodeId))
                        {
                            foreach (var callback in subscriptions[dataChange.nodeId])
                            {
                                callback?.Invoke(dataChange);
                            }
                        }

                        OnDataChanged?.Invoke(dataChange);
                    }
                }
            }
        }

        // =========================================================================
        // Common CNC/Robot Node Paths
        // =========================================================================

        /// <summary>
        /// Get standard CNC node paths (OPC UA for Machine Tools companion spec)
        /// </summary>
        public static class CNCNodes
        {
            public const string ChannelState = "ns=2;s=Channel/State";
            public const string ActualPosition = "ns=2;s=Channel/ActPosition";
            public const string CommandedPosition = "ns=2;s=Channel/CmdPosition";
            public const string FeedRate = "ns=2;s=Channel/FeedRate";
            public const string SpindleSpeed = "ns=2;s=Channel/SpindleSpeed";
            public const string SpindleLoad = "ns=2;s=Channel/SpindleLoad";
            public const string ToolNumber = "ns=2;s=Channel/ToolNumber";
            public const string ProgramName = "ns=2;s=Channel/ProgramName";
            public const string ProgramStatus = "ns=2;s=Channel/ProgramStatus";
            public const string BlockNumber = "ns=2;s=Channel/BlockNumber";
            public const string AxisX = "ns=2;s=Axis/X/ActPosition";
            public const string AxisY = "ns=2;s=Axis/Y/ActPosition";
            public const string AxisZ = "ns=2;s=Axis/Z/ActPosition";
            public const string AxisA = "ns=2;s=Axis/A/ActPosition";
            public const string AxisB = "ns=2;s=Axis/B/ActPosition";
            public const string AxisC = "ns=2;s=Axis/C/ActPosition";
            public const string AlarmActive = "ns=2;s=Alarms/Active";
            public const string EmergencyStop = "ns=2;s/Safety/EmergencyStop";
        }

        /// <summary>
        /// Get standard robot node paths (OPC UA for Robotics companion spec)
        /// </summary>
        public static class RobotNodes
        {
            public const string MotionState = "ns=2;s=Robot/MotionState";
            public const string ExecutionMode = "ns=2;s=Robot/ExecutionMode";
            public const string SpeedOverride = "ns=2;s=Robot/SpeedOverride";
            public const string Joint1 = "ns=2;s=Robot/Axis/1/ActPosition";
            public const string Joint2 = "ns=2;s=Robot/Axis/2/ActPosition";
            public const string Joint3 = "ns=2;s=Robot/Axis/3/ActPosition";
            public const string Joint4 = "ns=2;s=Robot/Axis/4/ActPosition";
            public const string Joint5 = "ns=2;s=Robot/Axis/5/ActPosition";
            public const string Joint6 = "ns=2;s=Robot/Axis/6/ActPosition";
            public const string CartesianX = "ns=2;s=Robot/Cartesian/X";
            public const string CartesianY = "ns=2;s=Robot/Cartesian/Y";
            public const string CartesianZ = "ns=2;s=Robot/Cartesian/Z";
            public const string GripperState = "ns=2;s=Robot/Gripper/State";
            public const string GripperPosition = "ns=2;s=Robot/Gripper/Position";
            public const string SafetyState = "ns=2;s=Robot/Safety/State";
            public const string ProgramRunning = "ns=2;s=Robot/Program/Running";
        }

        // Properties
        public ConnectionState State => connectionState;
        public string ServerName => serverApplicationName;
        public bool IsConnected => connectionState == ConnectionState.Connected;
        public int SubscriptionCount => activeSubscriptions;
    }

    // =========================================================================
    // Data Types
    // =========================================================================

    public enum ConnectionState
    {
        Disconnected,
        Connecting,
        Connected,
        Error
    }

    public enum SecurityMode
    {
        None,
        Sign,
        SignAndEncrypt
    }

    [Serializable]
    public class OPCUANode
    {
        public string nodeId;
        public string browseName;
        public string displayName;
        public string nodeClass;
        public string dataType;
        public bool hasChildren;
    }

    [Serializable]
    public class OPCUADataValue
    {
        public string nodeId;
        public string value;
        public string dataType;
        public string statusCode;
        public string sourceTimestamp;
        public string serverTimestamp;

        public T GetValue<T>()
        {
            try
            {
                return (T)Convert.ChangeType(value, typeof(T));
            }
            catch
            {
                return default;
            }
        }

        public float AsFloat() => GetValue<float>();
        public int AsInt() => GetValue<int>();
        public bool AsBool() => GetValue<bool>();
        public string AsString() => value;
    }

    // Request/Response types for REST proxy
    [Serializable]
    public class OPCUAConnectRequest
    {
        public string serverEndpoint;
        public string securityMode;
        public string username;
        public string password;
    }

    [Serializable]
    public class OPCUAConnectResponse
    {
        public bool success;
        public string serverName;
        public string error;
    }

    [Serializable]
    public class OPCUABrowseResponse
    {
        public List<OPCUANode> nodes;
    }

    [Serializable]
    public class OPCUAReadRequest
    {
        public string[] nodeIds;
    }

    [Serializable]
    public class OPCUAReadMultiResponse
    {
        public OPCUADataValue[] values;
    }

    [Serializable]
    public class OPCUAWriteRequest
    {
        public string nodeId;
        public string value;
        public string valueType;
    }

    [Serializable]
    public class OPCUASubscribeRequest
    {
        public string nodeId;
        public float publishingInterval;
    }

    [Serializable]
    public class OPCUAPollResponse
    {
        public OPCUADataValue[] dataChanges;
    }
}
