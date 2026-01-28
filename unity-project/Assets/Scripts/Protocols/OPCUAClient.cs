using System;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json;

namespace CNCScada.Protocols
{
    /// <summary>
    /// OPC UA client for industrial communication with CNC machines.
    /// Implements OPC UA (Unified Architecture) protocol for machine data access.
    /// Part of Feature 1.5: OPC UA Integration (HIGH PRIORITY)
    /// </summary>
    public class OPCUAClient : MonoBehaviour
    {
        [Header("OPC UA Configuration")]
        [SerializeField] private string serverEndpoint = "opc.tcp://localhost:4840";
        [SerializeField] private string applicationName = "Unity CNC SCADA Client";
        [SerializeField] private bool autoConnect = true;
        [SerializeField] private float reconnectInterval = 5f;

        [Header("Security")]
        [SerializeField] private string username = "";
        [SerializeField] private string password = "";
        [SerializeField] private bool useAnonymous = true;

        [Header("Subscription")]
        [SerializeField] private int publishingInterval = 100; // ms
        [SerializeField] private bool enableSubscriptions = true;

        // Connection state
        private bool isConnected = false;
        private DateTime lastConnectAttempt;
        private float reconnectTimer = 0f;
        private int connectionAttempts = 0;

        // Subscribed nodes
        private Dictionary<string, OPCUANode> subscribedNodes = new Dictionary<string, OPCUANode>();
        private Dictionary<string, object> nodeValues = new Dictionary<string, object>();

        // Statistics
        private int totalReads = 0;
        private int totalWrites = 0;
        private int totalUpdates = 0;
        private DateTime sessionStart;

        // Events
        public event Action OnConnected;
        public event Action OnDisconnected;
        public event Action<string, object> OnNodeValueChanged;
        public event Action<string> OnConnectionError;

        void Start()
        {
            sessionStart = DateTime.UtcNow;

            if (autoConnect)
            {
                Connect();
            }
        }

        void Update()
        {
            // Handle reconnection
            if (!isConnected && autoConnect)
            {
                reconnectTimer += Time.deltaTime;
                if (reconnectTimer >= reconnectInterval)
                {
                    Connect();
                    reconnectTimer = 0f;
                }
            }
        }

        /// <summary>
        /// Connect to OPC UA server
        /// </summary>
        public void Connect()
        {
            if (isConnected)
            {
                Debug.LogWarning("[OPCUA] Already connected");
                return;
            }

            try
            {
                lastConnectAttempt = DateTime.UtcNow;
                connectionAttempts++;

                Debug.Log($"[OPCUA] Connecting to {serverEndpoint} (attempt {connectionAttempts})...");

                // Simulate connection (in real implementation, use OPC UA library)
                // In production, this would create actual OPC UA session
                isConnected = SimulateConnection();

                if (isConnected)
                {
                    Debug.Log("[OPCUA] Connected successfully");
                    OnConnected?.Invoke();

                    // Initialize subscriptions
                    if (enableSubscriptions)
                    {
                        InitializeSubscriptions();
                    }
                }
                else
                {
                    string error = "Connection failed";
                    Debug.LogError($"[OPCUA] {error}");
                    OnConnectionError?.Invoke(error);
                }
            }
            catch (Exception e)
            {
                Debug.LogError($"[OPCUA] Connection error: {e.Message}");
                OnConnectionError?.Invoke(e.Message);
                isConnected = false;
            }
        }

        /// <summary>
        /// Disconnect from OPC UA server
        /// </summary>
        public void Disconnect()
        {
            if (!isConnected)
            {
                return;
            }

            try
            {
                Debug.Log("[OPCUA] Disconnecting...");

                // Cleanup subscriptions
                subscribedNodes.Clear();

                isConnected = false;
                OnDisconnected?.Invoke();

                Debug.Log("[OPCUA] Disconnected");
            }
            catch (Exception e)
            {
                Debug.LogError($"[OPCUA] Disconnection error: {e.Message}");
            }
        }

        /// <summary>
        /// Read value from OPC UA node
        /// </summary>
        public T ReadNode<T>(string nodeId)
        {
            if (!isConnected)
            {
                Debug.LogError("[OPCUA] Not connected");
                return default(T);
            }

            try
            {
                // In production, this would use OPC UA ReadAsync
                object value = SimulateReadNode(nodeId);
                totalReads++;

                if (value != null && value is T)
                {
                    return (T)value;
                }

                return default(T);
            }
            catch (Exception e)
            {
                Debug.LogError($"[OPCUA] Read error for node {nodeId}: {e.Message}");
                return default(T);
            }
        }

        /// <summary>
        /// Write value to OPC UA node
        /// </summary>
        public bool WriteNode<T>(string nodeId, T value)
        {
            if (!isConnected)
            {
                Debug.LogError("[OPCUA] Not connected");
                return false;
            }

            try
            {
                Debug.Log($"[OPCUA] Writing to {nodeId}: {value}");

                // In production, this would use OPC UA WriteAsync
                bool success = SimulateWriteNode(nodeId, value);
                if (success)
                {
                    totalWrites++;
                }

                return success;
            }
            catch (Exception e)
            {
                Debug.LogError($"[OPCUA] Write error for node {nodeId}: {e.Message}");
                return false;
            }
        }

        /// <summary>
        /// Subscribe to node value changes
        /// </summary>
        public bool SubscribeToNode(string nodeId, string displayName)
        {
            if (!isConnected)
            {
                Debug.LogError("[OPCUA] Not connected");
                return false;
            }

            if (subscribedNodes.ContainsKey(nodeId))
            {
                Debug.LogWarning($"[OPCUA] Already subscribed to {nodeId}");
                return true;
            }

            try
            {
                var node = new OPCUANode
                {
                    NodeId = nodeId,
                    DisplayName = displayName,
                    SubscribedAt = DateTime.UtcNow,
                    LastUpdate = DateTime.UtcNow
                };

                subscribedNodes[nodeId] = node;

                Debug.Log($"[OPCUA] Subscribed to node: {displayName} ({nodeId})");
                return true;
            }
            catch (Exception e)
            {
                Debug.LogError($"[OPCUA] Subscription error: {e.Message}");
                return false;
            }
        }

        /// <summary>
        /// Unsubscribe from node
        /// </summary>
        public bool UnsubscribeFromNode(string nodeId)
        {
            if (subscribedNodes.Remove(nodeId))
            {
                nodeValues.Remove(nodeId);
                Debug.Log($"[OPCUA] Unsubscribed from node: {nodeId}");
                return true;
            }

            return false;
        }

        /// <summary>
        /// Initialize subscriptions
        /// </summary>
        private void InitializeSubscriptions()
        {
            // Subscribe to common machine nodes
            SubscribeToNode("ns=2;s=Machine.Position.X", "Position X");
            SubscribeToNode("ns=2;s=Machine.Position.Y", "Position Y");
            SubscribeToNode("ns=2;s=Machine.Position.Z", "Position Z");
            SubscribeToNode("ns=2;s=Machine.Status", "Machine Status");
            SubscribeToNode("ns=2;s=Machine.Spindle.Speed", "Spindle Speed");
            SubscribeToNode("ns=2;s=Machine.Feedrate", "Feed Rate");

            Debug.Log($"[OPCUA] Initialized {subscribedNodes.Count} subscriptions");
        }

        /// <summary>
        /// Simulate node value update (replace with real OPC UA data change notification)
        /// </summary>
        public void SimulateNodeUpdate(string nodeId, object value)
        {
            if (!subscribedNodes.ContainsKey(nodeId))
            {
                return;
            }

            var node = subscribedNodes[nodeId];
            node.LastUpdate = DateTime.UtcNow;
            node.LastValue = value;
            subscribedNodes[nodeId] = node;

            nodeValues[nodeId] = value;
            totalUpdates++;

            OnNodeValueChanged?.Invoke(nodeId, value);
        }

        /// <summary>
        /// Get current value for subscribed node
        /// </summary>
        public object GetNodeValue(string nodeId)
        {
            if (nodeValues.ContainsKey(nodeId))
            {
                return nodeValues[nodeId];
            }
            return null;
        }

        /// <summary>
        /// Browse OPC UA server namespace
        /// </summary>
        public List<OPCUANode> BrowseNodes(string startingNodeId = "i=85")
        {
            if (!isConnected)
            {
                Debug.LogError("[OPCUA] Not connected");
                return new List<OPCUANode>();
            }

            // In production, this would use OPC UA Browse service
            var nodes = new List<OPCUANode>();

            // Simulate browsing
            nodes.Add(new OPCUANode
            {
                NodeId = "ns=2;s=Machine",
                DisplayName = "Machine",
                NodeClass = "Object"
            });

            nodes.Add(new OPCUANode
            {
                NodeId = "ns=2;s=Machine.Position",
                DisplayName = "Position",
                NodeClass = "Object"
            });

            Debug.Log($"[OPCUA] Browsed {nodes.Count} nodes");
            return nodes;
        }

        /// <summary>
        /// Get connection statistics
        /// </summary>
        public OPCUAStatistics GetStatistics()
        {
            TimeSpan uptime = DateTime.UtcNow - sessionStart;

            return new OPCUAStatistics
            {
                IsConnected = isConnected,
                ServerEndpoint = serverEndpoint,
                ConnectionAttempts = connectionAttempts,
                LastConnectAttempt = lastConnectAttempt,
                TotalReads = totalReads,
                TotalWrites = totalWrites,
                TotalUpdates = totalUpdates,
                SubscribedNodes = subscribedNodes.Count,
                Uptime = uptime
            };
        }

        #region Simulation Methods (Replace with real OPC UA implementation)

        private bool SimulateConnection()
        {
            // In production, create real OPC UA ApplicationConfiguration and Session
            return true;
        }

        private object SimulateReadNode(string nodeId)
        {
            // Return simulated values
            if (nodeId.Contains("Position.X")) return 0.1f;
            if (nodeId.Contains("Position.Y")) return 0.05f;
            if (nodeId.Contains("Position.Z")) return 0.2f;
            if (nodeId.Contains("Status")) return "Idle";
            if (nodeId.Contains("Spindle")) return 10000f;
            if (nodeId.Contains("Feedrate")) return 500f;

            return null;
        }

        private bool SimulateWriteNode<T>(string nodeId, T value)
        {
            // Simulate write success
            nodeValues[nodeId] = value;
            return true;
        }

        #endregion

        void OnDestroy()
        {
            Disconnect();
        }

        #region Public Properties

        public bool IsConnected => isConnected;
        public int SubscribedNodeCount => subscribedNodes.Count;
        public string ServerEndpoint => serverEndpoint;

        #endregion
    }

    #region OPC UA Data Structures

    /// <summary>
    /// OPC UA node information
    /// </summary>
    [Serializable]
    public struct OPCUANode
    {
        public string NodeId;
        public string DisplayName;
        public string NodeClass;
        public DateTime SubscribedAt;
        public DateTime LastUpdate;
        public object LastValue;
    }

    /// <summary>
    /// OPC UA client statistics
    /// </summary>
    [Serializable]
    public struct OPCUAStatistics
    {
        public bool IsConnected;
        public string ServerEndpoint;
        public int ConnectionAttempts;
        public DateTime LastConnectAttempt;
        public int TotalReads;
        public int TotalWrites;
        public int TotalUpdates;
        public int SubscribedNodes;
        public TimeSpan Uptime;
    }

    #endregion
}
