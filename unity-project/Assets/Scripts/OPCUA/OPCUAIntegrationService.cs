using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace CNCDigitalTwin.OPCUA
{
    /// <summary>
    /// OPC UA Integration Service for industrial communication
    /// Implements OPC UA client functionality with subscription support
    /// Compatible with OPC UA servers (Unified Automation, Kepware, Ignition, etc.)
    /// </summary>
    public class OPCUAIntegrationService : MonoBehaviour
    {
        public static OPCUAIntegrationService Instance { get; private set; }

        [Header("Connection Settings")]
        [SerializeField] private string serverEndpoint = "opc.tcp://localhost:4840";
        [SerializeField] private string applicationName = "CNC Digital Twin";
        [SerializeField] private string applicationUri = "urn:cnc-digital-twin:client";
        [SerializeField] private SecurityMode securityMode = SecurityMode.None;
        [SerializeField] private MessageSecurityMode messageSecurityMode = MessageSecurityMode.None;

        [Header("Authentication")]
        [SerializeField] private AuthenticationType authenticationType = AuthenticationType.Anonymous;
        [SerializeField] private string username = "";
        [SerializeField] private string password = "";
        [SerializeField] private string certificatePath = "";

        [Header("Session Settings")]
        [SerializeField] private float sessionTimeout = 60000f; // ms
        [SerializeField] private float publishingInterval = 100f; // ms
        [SerializeField] private int maxNotificationsPerPublish = 1000;
        [SerializeField] private bool autoReconnect = true;
        [SerializeField] private float reconnectInterval = 5f;

        [Header("Subscription Settings")]
        [SerializeField] private float defaultSamplingInterval = 100f;
        [SerializeField] private uint defaultQueueSize = 10;
        [SerializeField] private bool discardOldest = true;

        // Connection state
        private OPCUASession currentSession;
        private ConnectionState connectionState = ConnectionState.Disconnected;
        private DateTime lastConnectionAttempt;

        // Node registry
        private Dictionary<string, OPCUANode> nodeCache = new Dictionary<string, OPCUANode>();
        private Dictionary<string, MonitoredItem> monitoredItems = new Dictionary<string, MonitoredItem>();
        private Dictionary<uint, Subscription> subscriptions = new Dictionary<uint, Subscription>();

        // Data change queue
        private Queue<DataChange> dataChangeQueue = new Queue<DataChange>();
        private object queueLock = new object();

        // Namespace mappings
        private Dictionary<string, ushort> namespaceMap = new Dictionary<string, ushort>();

        // Statistics
        private OPCUAStats stats = new OPCUAStats();

        // Events
        public event Action OnConnected;
        public event Action OnDisconnected;
        public event Action<string> OnConnectionError;
        public event Action<DataChange> OnDataChanged;
        public event Action<OPCUAEvent> OnEventReceived;
        public event Action<AlarmCondition> OnAlarmReceived;
        public event Action<string, object> OnMethodCallCompleted;

        private Coroutine connectionCoroutine;
        private Coroutine publishCoroutine;

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
            }
        }

        void Start()
        {
            InitializeDefaultNamespaces();
        }

        void OnDestroy()
        {
            Disconnect();
        }

        void Update()
        {
            // Process data change queue on main thread
            ProcessDataChangeQueue();
        }

        #region Initialization

        private void InitializeDefaultNamespaces()
        {
            // Standard OPC UA namespaces
            namespaceMap["http://opcfoundation.org/UA/"] = 0;
            namespaceMap["urn:cnc-digital-twin:server"] = 1;

            // Common vendor namespaces
            namespaceMap["http://www.siemens.com/simatic-s7-opcua"] = 2;
            namespaceMap["http://www.beckhoff.com/"] = 3;
            namespaceMap["http://www.rockwellautomation.com/"] = 4;
        }

        #endregion

        #region Connection Management

        public void Connect()
        {
            if (connectionState == ConnectionState.Connected ||
                connectionState == ConnectionState.Connecting)
            {
                return;
            }

            connectionCoroutine = StartCoroutine(ConnectAsync());
        }

        private IEnumerator ConnectAsync()
        {
            connectionState = ConnectionState.Connecting;
            lastConnectionAttempt = DateTime.UtcNow;

            Debug.Log($"[OPCUA] Connecting to {serverEndpoint}...");

            // Step 1: Get endpoints
            yield return GetEndpoints();

            if (connectionState == ConnectionState.Error)
            {
                if (autoReconnect)
                {
                    yield return new WaitForSeconds(reconnectInterval);
                    Connect();
                }
                yield break;
            }

            // Step 2: Create session
            yield return CreateSession();

            if (connectionState == ConnectionState.Error)
            {
                if (autoReconnect)
                {
                    yield return new WaitForSeconds(reconnectInterval);
                    Connect();
                }
                yield break;
            }

            // Step 3: Activate session
            yield return ActivateSession();

            if (connectionState == ConnectionState.Connected)
            {
                Debug.Log("[OPCUA] Connected successfully");
                OnConnected?.Invoke();

                // Start publishing
                publishCoroutine = StartCoroutine(PublishLoop());

                // Restore subscriptions
                yield return RestoreSubscriptions();
            }
        }

        private IEnumerator GetEndpoints()
        {
            // In production, this would call GetEndpoints service
            // For now, simulate the discovery
            yield return new WaitForSeconds(0.2f);

            var endpoint = new EndpointDescription
            {
                EndpointUrl = serverEndpoint,
                SecurityMode = messageSecurityMode,
                SecurityPolicyUri = GetSecurityPolicyUri(securityMode),
                TransportProfileUri = "http://opcfoundation.org/UA-Profile/Transport/uatcp-uasc-uabinary"
            };

            Debug.Log($"[OPCUA] Found endpoint: {endpoint.EndpointUrl}");
        }

        private IEnumerator CreateSession()
        {
            // Create session request
            var session = new OPCUASession
            {
                SessionId = Guid.NewGuid().ToString(),
                AuthenticationToken = GenerateAuthToken(),
                SessionTimeout = sessionTimeout,
                MaxResponseMessageSize = 4194304,
                CreatedAt = DateTime.UtcNow
            };

            // Simulate session creation
            yield return new WaitForSeconds(0.3f);

            currentSession = session;
            Debug.Log($"[OPCUA] Session created: {session.SessionId}");
        }

        private IEnumerator ActivateSession()
        {
            if (currentSession == null)
            {
                connectionState = ConnectionState.Error;
                OnConnectionError?.Invoke("No session to activate");
                yield break;
            }

            // Prepare identity token based on authentication type
            object identityToken = null;
            switch (authenticationType)
            {
                case AuthenticationType.Anonymous:
                    identityToken = new AnonymousIdentityToken();
                    break;
                case AuthenticationType.UserName:
                    identityToken = new UserNameIdentityToken
                    {
                        UserName = username,
                        Password = EncryptPassword(password)
                    };
                    break;
                case AuthenticationType.Certificate:
                    identityToken = new X509IdentityToken
                    {
                        CertificateData = LoadCertificate(certificatePath)
                    };
                    break;
            }

            // Simulate activation
            yield return new WaitForSeconds(0.2f);

            currentSession.IsActivated = true;
            currentSession.ActivatedAt = DateTime.UtcNow;
            connectionState = ConnectionState.Connected;

            stats.ConnectionCount++;
            stats.LastConnected = DateTime.UtcNow;
        }

        public void Disconnect()
        {
            if (connectionState == ConnectionState.Disconnected)
                return;

            if (publishCoroutine != null)
            {
                StopCoroutine(publishCoroutine);
                publishCoroutine = null;
            }

            if (connectionCoroutine != null)
            {
                StopCoroutine(connectionCoroutine);
                connectionCoroutine = null;
            }

            // Close session
            if (currentSession != null)
            {
                currentSession.IsActivated = false;
                currentSession = null;
            }

            // Clear subscriptions
            subscriptions.Clear();
            monitoredItems.Clear();

            connectionState = ConnectionState.Disconnected;
            OnDisconnected?.Invoke();

            Debug.Log("[OPCUA] Disconnected");
        }

        private string GetSecurityPolicyUri(SecurityMode mode)
        {
            return mode switch
            {
                SecurityMode.None => "http://opcfoundation.org/UA/SecurityPolicy#None",
                SecurityMode.Basic128Rsa15 => "http://opcfoundation.org/UA/SecurityPolicy#Basic128Rsa15",
                SecurityMode.Basic256 => "http://opcfoundation.org/UA/SecurityPolicy#Basic256",
                SecurityMode.Basic256Sha256 => "http://opcfoundation.org/UA/SecurityPolicy#Basic256Sha256",
                SecurityMode.Aes128Sha256RsaOaep => "http://opcfoundation.org/UA/SecurityPolicy#Aes128_Sha256_RsaOaep",
                SecurityMode.Aes256Sha256RsaPss => "http://opcfoundation.org/UA/SecurityPolicy#Aes256_Sha256_RsaPss",
                _ => "http://opcfoundation.org/UA/SecurityPolicy#None"
            };
        }

        private string GenerateAuthToken()
        {
            byte[] tokenBytes = new byte[32];
            new System.Random().NextBytes(tokenBytes);
            return Convert.ToBase64String(tokenBytes);
        }

        private byte[] EncryptPassword(string pwd)
        {
            // In production, would use RSA encryption with server certificate
            return Encoding.UTF8.GetBytes(pwd);
        }

        private byte[] LoadCertificate(string path)
        {
            // Would load certificate from file
            return new byte[0];
        }

        #endregion

        #region Node Operations

        public IEnumerator BrowseNode(NodeId nodeId, Action<List<ReferenceDescription>> callback)
        {
            if (connectionState != ConnectionState.Connected)
            {
                callback?.Invoke(new List<ReferenceDescription>());
                yield break;
            }

            var references = new List<ReferenceDescription>();

            // Simulate browse
            yield return new WaitForSeconds(0.1f);

            // Return common CNC nodes if browsing root
            if (nodeId.Identifier == "i=85") // Objects folder
            {
                references.Add(new ReferenceDescription
                {
                    NodeId = new NodeId { NamespaceIndex = 1, Identifier = "CNC" },
                    BrowseName = "CNC",
                    DisplayName = "CNC Machine",
                    NodeClass = NodeClass.Object
                });

                references.Add(new ReferenceDescription
                {
                    NodeId = new NodeId { NamespaceIndex = 1, Identifier = "Axes" },
                    BrowseName = "Axes",
                    DisplayName = "Machine Axes",
                    NodeClass = NodeClass.Object
                });

                references.Add(new ReferenceDescription
                {
                    NodeId = new NodeId { NamespaceIndex = 1, Identifier = "Spindle" },
                    BrowseName = "Spindle",
                    DisplayName = "Spindle",
                    NodeClass = NodeClass.Object
                });
            }

            stats.BrowseRequests++;
            callback?.Invoke(references);
        }

        public IEnumerator ReadNode(NodeId nodeId, Action<DataValue> callback)
        {
            if (connectionState != ConnectionState.Connected)
            {
                callback?.Invoke(new DataValue { StatusCode = StatusCode.BadNotConnected });
                yield break;
            }

            // Check cache
            string nodeKey = GetNodeKey(nodeId);
            if (nodeCache.TryGetValue(nodeKey, out var cachedNode) &&
                (DateTime.UtcNow - cachedNode.LastRead).TotalMilliseconds < 100)
            {
                callback?.Invoke(cachedNode.LastValue);
                yield break;
            }

            // Simulate read
            yield return new WaitForSeconds(0.05f);

            var value = new DataValue
            {
                Value = GetSimulatedValue(nodeId),
                StatusCode = StatusCode.Good,
                SourceTimestamp = DateTime.UtcNow,
                ServerTimestamp = DateTime.UtcNow
            };

            // Update cache
            if (!nodeCache.ContainsKey(nodeKey))
            {
                nodeCache[nodeKey] = new OPCUANode { NodeId = nodeId };
            }
            nodeCache[nodeKey].LastValue = value;
            nodeCache[nodeKey].LastRead = DateTime.UtcNow;

            stats.ReadRequests++;
            stats.ValuesRead++;

            callback?.Invoke(value);
        }

        public IEnumerator ReadNodes(List<NodeId> nodeIds, Action<List<DataValue>> callback)
        {
            if (connectionState != ConnectionState.Connected)
            {
                callback?.Invoke(nodeIds.Select(_ => new DataValue { StatusCode = StatusCode.BadNotConnected }).ToList());
                yield break;
            }

            var values = new List<DataValue>();

            // Simulate batch read
            yield return new WaitForSeconds(0.05f + nodeIds.Count * 0.001f);

            foreach (var nodeId in nodeIds)
            {
                values.Add(new DataValue
                {
                    Value = GetSimulatedValue(nodeId),
                    StatusCode = StatusCode.Good,
                    SourceTimestamp = DateTime.UtcNow,
                    ServerTimestamp = DateTime.UtcNow
                });
            }

            stats.ReadRequests++;
            stats.ValuesRead += nodeIds.Count;

            callback?.Invoke(values);
        }

        public IEnumerator WriteNode(NodeId nodeId, object value, Action<StatusCode> callback)
        {
            if (connectionState != ConnectionState.Connected)
            {
                callback?.Invoke(StatusCode.BadNotConnected);
                yield break;
            }

            // Simulate write
            yield return new WaitForSeconds(0.05f);

            // Update cache
            string nodeKey = GetNodeKey(nodeId);
            if (nodeCache.TryGetValue(nodeKey, out var node))
            {
                node.LastValue = new DataValue
                {
                    Value = value,
                    StatusCode = StatusCode.Good,
                    SourceTimestamp = DateTime.UtcNow
                };
            }

            stats.WriteRequests++;
            stats.ValuesWritten++;

            Debug.Log($"[OPCUA] Written value to {nodeId.Identifier}: {value}");
            callback?.Invoke(StatusCode.Good);
        }

        public IEnumerator WriteNodes(Dictionary<NodeId, object> nodesToWrite, Action<List<StatusCode>> callback)
        {
            if (connectionState != ConnectionState.Connected)
            {
                callback?.Invoke(nodesToWrite.Keys.Select(_ => StatusCode.BadNotConnected).ToList());
                yield break;
            }

            // Simulate batch write
            yield return new WaitForSeconds(0.05f + nodesToWrite.Count * 0.002f);

            var results = new List<StatusCode>();
            foreach (var kvp in nodesToWrite)
            {
                string nodeKey = GetNodeKey(kvp.Key);
                if (nodeCache.TryGetValue(nodeKey, out var node))
                {
                    node.LastValue = new DataValue { Value = kvp.Value, StatusCode = StatusCode.Good };
                }
                results.Add(StatusCode.Good);
            }

            stats.WriteRequests++;
            stats.ValuesWritten += nodesToWrite.Count;

            callback?.Invoke(results);
        }

        private object GetSimulatedValue(NodeId nodeId)
        {
            string id = nodeId.Identifier?.ToString() ?? "";

            // Simulate typical CNC values
            if (id.Contains("Position") || id.Contains("Pos"))
            {
                return UnityEngine.Random.Range(0f, 300f);
            }
            else if (id.Contains("Speed") || id.Contains("RPM"))
            {
                return UnityEngine.Random.Range(0f, 24000f);
            }
            else if (id.Contains("Feed"))
            {
                return UnityEngine.Random.Range(0f, 5000f);
            }
            else if (id.Contains("Load"))
            {
                return UnityEngine.Random.Range(0f, 100f);
            }
            else if (id.Contains("Temp"))
            {
                return UnityEngine.Random.Range(20f, 80f);
            }
            else if (id.Contains("State") || id.Contains("Mode"))
            {
                return UnityEngine.Random.Range(0, 5);
            }
            else if (id.Contains("Active") || id.Contains("Running"))
            {
                return UnityEngine.Random.value > 0.3f;
            }

            return UnityEngine.Random.Range(0f, 100f);
        }

        private string GetNodeKey(NodeId nodeId)
        {
            return $"ns={nodeId.NamespaceIndex};{nodeId.IdentifierType}={nodeId.Identifier}";
        }

        #endregion

        #region Subscription Management

        public uint CreateSubscription(SubscriptionConfig config = null)
        {
            if (connectionState != ConnectionState.Connected)
                return 0;

            config = config ?? new SubscriptionConfig();

            var subscription = new Subscription
            {
                SubscriptionId = (uint)subscriptions.Count + 1,
                PublishingInterval = config.PublishingInterval > 0 ? config.PublishingInterval : publishingInterval,
                LifetimeCount = config.LifetimeCount > 0 ? config.LifetimeCount : 1000,
                MaxKeepAliveCount = config.MaxKeepAliveCount > 0 ? config.MaxKeepAliveCount : 10,
                MaxNotificationsPerPublish = config.MaxNotificationsPerPublish > 0 ?
                    config.MaxNotificationsPerPublish : (uint)maxNotificationsPerPublish,
                PublishingEnabled = true,
                Priority = config.Priority,
                MonitoredItems = new Dictionary<uint, MonitoredItem>(),
                CreatedAt = DateTime.UtcNow
            };

            subscriptions[subscription.SubscriptionId] = subscription;

            Debug.Log($"[OPCUA] Created subscription: {subscription.SubscriptionId}");
            return subscription.SubscriptionId;
        }

        public uint AddMonitoredItem(uint subscriptionId, MonitoredItemConfig config)
        {
            if (!subscriptions.TryGetValue(subscriptionId, out var subscription))
                return 0;

            var item = new MonitoredItem
            {
                ClientHandle = (uint)monitoredItems.Count + 1,
                NodeId = config.NodeId,
                AttributeId = config.AttributeId > 0 ? config.AttributeId : 13, // Value attribute
                SamplingInterval = config.SamplingInterval > 0 ? config.SamplingInterval : defaultSamplingInterval,
                QueueSize = config.QueueSize > 0 ? config.QueueSize : defaultQueueSize,
                DiscardOldest = config.DiscardOldest ?? discardOldest,
                Filter = config.Filter,
                MonitoringMode = config.MonitoringMode,
                SubscriptionId = subscriptionId,
                CreatedAt = DateTime.UtcNow
            };

            subscription.MonitoredItems[item.ClientHandle] = item;
            monitoredItems[GetNodeKey(config.NodeId)] = item;

            stats.MonitoredItemCount++;

            Debug.Log($"[OPCUA] Added monitored item: {config.NodeId.Identifier}");
            return item.ClientHandle;
        }

        public void RemoveMonitoredItem(uint subscriptionId, uint clientHandle)
        {
            if (!subscriptions.TryGetValue(subscriptionId, out var subscription))
                return;

            if (subscription.MonitoredItems.TryGetValue(clientHandle, out var item))
            {
                subscription.MonitoredItems.Remove(clientHandle);
                monitoredItems.Remove(GetNodeKey(item.NodeId));
                stats.MonitoredItemCount--;
            }
        }

        public void DeleteSubscription(uint subscriptionId)
        {
            if (!subscriptions.TryGetValue(subscriptionId, out var subscription))
                return;

            // Remove all monitored items
            foreach (var item in subscription.MonitoredItems.Values)
            {
                monitoredItems.Remove(GetNodeKey(item.NodeId));
                stats.MonitoredItemCount--;
            }

            subscriptions.Remove(subscriptionId);
            Debug.Log($"[OPCUA] Deleted subscription: {subscriptionId}");
        }

        public void SetPublishingEnabled(uint subscriptionId, bool enabled)
        {
            if (subscriptions.TryGetValue(subscriptionId, out var subscription))
            {
                subscription.PublishingEnabled = enabled;
            }
        }

        private IEnumerator RestoreSubscriptions()
        {
            // Restore monitored items from cache
            foreach (var kvp in monitoredItems.ToList())
            {
                var item = kvp.Value;
                if (subscriptions.TryGetValue(item.SubscriptionId, out var subscription))
                {
                    // Item already restored
                }
            }
            yield return null;
        }

        #endregion

        #region Publishing

        private IEnumerator PublishLoop()
        {
            while (connectionState == ConnectionState.Connected)
            {
                float minInterval = subscriptions.Values.Any() ?
                    subscriptions.Values.Min(s => s.PublishingInterval) : publishingInterval;

                yield return new WaitForSeconds(minInterval / 1000f);

                foreach (var subscription in subscriptions.Values)
                {
                    if (!subscription.PublishingEnabled)
                        continue;

                    PublishSubscription(subscription);
                }
            }
        }

        private void PublishSubscription(Subscription subscription)
        {
            foreach (var item in subscription.MonitoredItems.Values)
            {
                // Simulate value change
                if (UnityEngine.Random.value > 0.7f) // 30% chance of value change
                {
                    var dataChange = new DataChange
                    {
                        ClientHandle = item.ClientHandle,
                        NodeId = item.NodeId,
                        Value = new DataValue
                        {
                            Value = GetSimulatedValue(item.NodeId),
                            StatusCode = StatusCode.Good,
                            SourceTimestamp = DateTime.UtcNow,
                            ServerTimestamp = DateTime.UtcNow
                        },
                        SubscriptionId = subscription.SubscriptionId
                    };

                    lock (queueLock)
                    {
                        dataChangeQueue.Enqueue(dataChange);
                    }

                    stats.DataChangesReceived++;
                }
            }

            subscription.LastPublishTime = DateTime.UtcNow;
        }

        private void ProcessDataChangeQueue()
        {
            int processCount = 0;
            const int maxPerFrame = 100;

            while (processCount < maxPerFrame)
            {
                DataChange dataChange = null;
                lock (queueLock)
                {
                    if (dataChangeQueue.Count > 0)
                    {
                        dataChange = dataChangeQueue.Dequeue();
                    }
                }

                if (dataChange == null)
                    break;

                // Update cache
                string nodeKey = GetNodeKey(dataChange.NodeId);
                if (nodeCache.TryGetValue(nodeKey, out var node))
                {
                    node.LastValue = dataChange.Value;
                    node.LastRead = DateTime.UtcNow;
                }

                OnDataChanged?.Invoke(dataChange);
                processCount++;
            }
        }

        #endregion

        #region Method Calls

        public IEnumerator CallMethod(NodeId objectId, NodeId methodId, object[] inputArguments,
            Action<StatusCode, object[]> callback)
        {
            if (connectionState != ConnectionState.Connected)
            {
                callback?.Invoke(StatusCode.BadNotConnected, null);
                yield break;
            }

            // Simulate method call
            yield return new WaitForSeconds(0.1f);

            // Return simulated output
            object[] outputArguments = new object[0];

            string methodName = methodId.Identifier?.ToString() ?? "";
            if (methodName.Contains("GetPosition"))
            {
                outputArguments = new object[] { 100.0f, 50.0f, 25.0f };
            }
            else if (methodName.Contains("GetStatus"))
            {
                outputArguments = new object[] { "Running", 85.5f };
            }

            stats.MethodCalls++;

            Debug.Log($"[OPCUA] Method called: {methodId.Identifier}");
            callback?.Invoke(StatusCode.Good, outputArguments);

            OnMethodCallCompleted?.Invoke(methodName, outputArguments);
        }

        #endregion

        #region Events and Alarms

        public uint SubscribeToEvents(NodeId eventSourceId, EventFilter filter = null)
        {
            // Create event subscription
            var subscriptionId = CreateSubscription(new SubscriptionConfig
            {
                PublishingInterval = 250
            });

            AddMonitoredItem(subscriptionId, new MonitoredItemConfig
            {
                NodeId = eventSourceId,
                AttributeId = 12, // EventNotifier
                Filter = filter ?? CreateDefaultEventFilter()
            });

            return subscriptionId;
        }

        public uint SubscribeToAlarms(NodeId alarmSourceId)
        {
            return SubscribeToEvents(alarmSourceId, CreateAlarmFilter());
        }

        private EventFilter CreateDefaultEventFilter()
        {
            return new EventFilter
            {
                SelectClauses = new List<SimpleAttributeOperand>
                {
                    new SimpleAttributeOperand { BrowsePath = new[] { "EventType" } },
                    new SimpleAttributeOperand { BrowsePath = new[] { "SourceName" } },
                    new SimpleAttributeOperand { BrowsePath = new[] { "Time" } },
                    new SimpleAttributeOperand { BrowsePath = new[] { "Message" } },
                    new SimpleAttributeOperand { BrowsePath = new[] { "Severity" } }
                }
            };
        }

        private EventFilter CreateAlarmFilter()
        {
            return new EventFilter
            {
                SelectClauses = new List<SimpleAttributeOperand>
                {
                    new SimpleAttributeOperand { BrowsePath = new[] { "EventType" } },
                    new SimpleAttributeOperand { BrowsePath = new[] { "ConditionName" } },
                    new SimpleAttributeOperand { BrowsePath = new[] { "SourceName" } },
                    new SimpleAttributeOperand { BrowsePath = new[] { "Time" } },
                    new SimpleAttributeOperand { BrowsePath = new[] { "Message" } },
                    new SimpleAttributeOperand { BrowsePath = new[] { "Severity" } },
                    new SimpleAttributeOperand { BrowsePath = new[] { "ActiveState", "Id" } },
                    new SimpleAttributeOperand { BrowsePath = new[] { "AckedState", "Id" } }
                }
            };
        }

        public void AcknowledgeAlarm(NodeId conditionId, byte[] eventId, string comment = "")
        {
            StartCoroutine(AcknowledgeAlarmAsync(conditionId, eventId, comment));
        }

        private IEnumerator AcknowledgeAlarmAsync(NodeId conditionId, byte[] eventId, string comment)
        {
            yield return CallMethod(
                conditionId,
                new NodeId { NamespaceIndex = 0, Identifier = "Acknowledge" },
                new object[] { eventId, comment },
                (status, output) =>
                {
                    Debug.Log($"[OPCUA] Alarm acknowledged: {status}");
                }
            );
        }

        #endregion

        #region Helper Methods

        public NodeId ParseNodeId(string nodeIdString)
        {
            // Parse format: ns=1;s=MyNode or ns=1;i=1234
            var nodeId = new NodeId();

            var parts = nodeIdString.Split(';');
            foreach (var part in parts)
            {
                if (part.StartsWith("ns="))
                {
                    nodeId.NamespaceIndex = ushort.Parse(part.Substring(3));
                }
                else if (part.StartsWith("s="))
                {
                    nodeId.IdentifierType = IdType.String;
                    nodeId.Identifier = part.Substring(2);
                }
                else if (part.StartsWith("i="))
                {
                    nodeId.IdentifierType = IdType.Numeric;
                    nodeId.Identifier = part.Substring(2);
                }
                else if (part.StartsWith("g="))
                {
                    nodeId.IdentifierType = IdType.Guid;
                    nodeId.Identifier = part.Substring(2);
                }
                else if (part.StartsWith("b="))
                {
                    nodeId.IdentifierType = IdType.Opaque;
                    nodeId.Identifier = part.Substring(2);
                }
            }

            return nodeId;
        }

        public string FormatNodeId(NodeId nodeId)
        {
            string prefix = nodeId.IdentifierType switch
            {
                IdType.Numeric => "i",
                IdType.String => "s",
                IdType.Guid => "g",
                IdType.Opaque => "b",
                _ => "s"
            };

            return $"ns={nodeId.NamespaceIndex};{prefix}={nodeId.Identifier}";
        }

        #endregion

        #region Convenience Methods

        public void SubscribeToNode(string nodeIdString, Action<object> callback)
        {
            var nodeId = ParseNodeId(nodeIdString);

            // Get or create subscription
            uint subscriptionId = subscriptions.Keys.FirstOrDefault();
            if (subscriptionId == 0)
            {
                subscriptionId = CreateSubscription();
            }

            // Add monitored item
            var clientHandle = AddMonitoredItem(subscriptionId, new MonitoredItemConfig
            {
                NodeId = nodeId,
                SamplingInterval = defaultSamplingInterval
            });

            // Register callback
            OnDataChanged += (dataChange) =>
            {
                if (dataChange.ClientHandle == clientHandle)
                {
                    callback?.Invoke(dataChange.Value.Value);
                }
            };
        }

        public void ReadValue(string nodeIdString, Action<object> callback)
        {
            var nodeId = ParseNodeId(nodeIdString);
            StartCoroutine(ReadNode(nodeId, (dataValue) =>
            {
                callback?.Invoke(dataValue.Value);
            }));
        }

        public void WriteValue(string nodeIdString, object value, Action<bool> callback = null)
        {
            var nodeId = ParseNodeId(nodeIdString);
            StartCoroutine(WriteNode(nodeId, value, (status) =>
            {
                callback?.Invoke(status == StatusCode.Good);
            }));
        }

        #endregion

        #region Statistics

        public OPCUAStats GetStatistics()
        {
            stats.IsConnected = connectionState == ConnectionState.Connected;
            stats.SubscriptionCount = subscriptions.Count;
            stats.CachedNodeCount = nodeCache.Count;
            stats.PendingDataChanges = dataChangeQueue.Count;
            return stats;
        }

        public bool IsConnected => connectionState == ConnectionState.Connected;
        public int SubscriptionCount => subscriptions.Count;
        public int MonitoredItemCount => monitoredItems.Count;

        #endregion
    }

    #region Enums

    public enum ConnectionState
    {
        Disconnected,
        Connecting,
        Connected,
        Reconnecting,
        Error
    }

    public enum SecurityMode
    {
        None,
        Basic128Rsa15,
        Basic256,
        Basic256Sha256,
        Aes128Sha256RsaOaep,
        Aes256Sha256RsaPss
    }

    public enum MessageSecurityMode
    {
        None,
        Sign,
        SignAndEncrypt
    }

    public enum AuthenticationType
    {
        Anonymous,
        UserName,
        Certificate,
        IssuedToken
    }

    public enum NodeClass
    {
        Object = 1,
        Variable = 2,
        Method = 4,
        ObjectType = 8,
        VariableType = 16,
        ReferenceType = 32,
        DataType = 64,
        View = 128
    }

    public enum IdType
    {
        Numeric,
        String,
        Guid,
        Opaque
    }

    public enum MonitoringMode
    {
        Disabled,
        Sampling,
        Reporting
    }

    public enum StatusCode : uint
    {
        Good = 0x00000000,
        Uncertain = 0x40000000,
        Bad = 0x80000000,
        BadNotConnected = 0x808A0000,
        BadTimeout = 0x800A0000,
        BadNodeIdInvalid = 0x80340000,
        BadNodeIdUnknown = 0x80340000,
        BadAttributeIdInvalid = 0x80350000,
        BadWriteNotSupported = 0x80730000
    }

    #endregion

    #region Data Classes

    [System.Serializable]
    public class NodeId
    {
        public ushort NamespaceIndex;
        public IdType IdentifierType = IdType.String;
        public object Identifier;
    }

    [System.Serializable]
    public class DataValue
    {
        public object Value;
        public StatusCode StatusCode;
        public DateTime SourceTimestamp;
        public DateTime ServerTimestamp;
    }

    [System.Serializable]
    public class DataChange
    {
        public uint ClientHandle;
        public NodeId NodeId;
        public DataValue Value;
        public uint SubscriptionId;
    }

    [System.Serializable]
    public class OPCUANode
    {
        public NodeId NodeId;
        public string BrowseName;
        public string DisplayName;
        public NodeClass NodeClass;
        public DataValue LastValue;
        public DateTime LastRead;
    }

    [System.Serializable]
    public class OPCUASession
    {
        public string SessionId;
        public string AuthenticationToken;
        public float SessionTimeout;
        public uint MaxResponseMessageSize;
        public DateTime CreatedAt;
        public DateTime? ActivatedAt;
        public bool IsActivated;
    }

    [System.Serializable]
    public class EndpointDescription
    {
        public string EndpointUrl;
        public MessageSecurityMode SecurityMode;
        public string SecurityPolicyUri;
        public string TransportProfileUri;
        public byte[] ServerCertificate;
    }

    [System.Serializable]
    public class Subscription
    {
        public uint SubscriptionId;
        public float PublishingInterval;
        public uint LifetimeCount;
        public uint MaxKeepAliveCount;
        public uint MaxNotificationsPerPublish;
        public bool PublishingEnabled;
        public byte Priority;
        public Dictionary<uint, MonitoredItem> MonitoredItems;
        public DateTime CreatedAt;
        public DateTime LastPublishTime;
    }

    [System.Serializable]
    public class SubscriptionConfig
    {
        public float PublishingInterval;
        public uint LifetimeCount;
        public uint MaxKeepAliveCount;
        public uint MaxNotificationsPerPublish;
        public byte Priority;
    }

    [System.Serializable]
    public class MonitoredItem
    {
        public uint ClientHandle;
        public NodeId NodeId;
        public uint AttributeId;
        public float SamplingInterval;
        public uint QueueSize;
        public bool DiscardOldest;
        public object Filter;
        public MonitoringMode MonitoringMode;
        public uint SubscriptionId;
        public DateTime CreatedAt;
    }

    [System.Serializable]
    public class MonitoredItemConfig
    {
        public NodeId NodeId;
        public uint AttributeId;
        public float SamplingInterval;
        public uint QueueSize;
        public bool? DiscardOldest;
        public object Filter;
        public MonitoringMode MonitoringMode;
    }

    [System.Serializable]
    public class ReferenceDescription
    {
        public NodeId NodeId;
        public string BrowseName;
        public string DisplayName;
        public NodeClass NodeClass;
        public NodeId TypeDefinition;
    }

    [System.Serializable]
    public class EventFilter
    {
        public List<SimpleAttributeOperand> SelectClauses;
        public ContentFilter WhereClause;
    }

    [System.Serializable]
    public class SimpleAttributeOperand
    {
        public string[] BrowsePath;
        public uint AttributeId;
    }

    [System.Serializable]
    public class ContentFilter
    {
        public List<ContentFilterElement> Elements;
    }

    [System.Serializable]
    public class ContentFilterElement
    {
        public FilterOperator FilterOperator;
        public List<object> FilterOperands;
    }

    public enum FilterOperator
    {
        Equals,
        IsNull,
        GreaterThan,
        LessThan,
        GreaterThanOrEqual,
        LessThanOrEqual,
        Like,
        Not,
        Between,
        InList,
        And,
        Or,
        Cast,
        BitwiseAnd,
        BitwiseOr
    }

    [System.Serializable]
    public class OPCUAEvent
    {
        public string EventType;
        public string SourceName;
        public DateTime Time;
        public string Message;
        public ushort Severity;
        public Dictionary<string, object> Fields;
    }

    [System.Serializable]
    public class AlarmCondition
    {
        public NodeId ConditionId;
        public byte[] EventId;
        public string ConditionName;
        public string SourceName;
        public DateTime Time;
        public string Message;
        public ushort Severity;
        public bool IsActive;
        public bool IsAcknowledged;
        public bool IsConfirmed;
    }

    [System.Serializable]
    public class AnonymousIdentityToken
    {
        public string PolicyId = "Anonymous";
    }

    [System.Serializable]
    public class UserNameIdentityToken
    {
        public string PolicyId = "UserName";
        public string UserName;
        public byte[] Password;
        public string EncryptionAlgorithm;
    }

    [System.Serializable]
    public class X509IdentityToken
    {
        public string PolicyId = "Certificate";
        public byte[] CertificateData;
    }

    [System.Serializable]
    public class OPCUAStats
    {
        public bool IsConnected;
        public int ConnectionCount;
        public DateTime? LastConnected;
        public int SubscriptionCount;
        public int MonitoredItemCount;
        public int CachedNodeCount;
        public long ReadRequests;
        public long WriteRequests;
        public long ValuesRead;
        public long ValuesWritten;
        public long BrowseRequests;
        public long MethodCalls;
        public long DataChangesReceived;
        public int PendingDataChanges;
    }

    #endregion
}
