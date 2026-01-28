using System;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json;

namespace CNCScada.Standards
{
    /// <summary>
    /// Handles ISO 23247-4 compliant data exchange between physical and digital twins.
    /// Manages bidirectional communication and state synchronization.
    /// Part of Feature 1.4: ISO 23247 Compliance (MEDIUM PRIORITY)
    /// </summary>
    public class ISO23247DataExchange : MonoBehaviour
    {
        [Header("Exchange Configuration")]
        [SerializeField] private string exchangeEndpoint = "ws://localhost:5000/api/v1/iso23247";
        [SerializeField] private float heartbeatInterval = 1f;
        [SerializeField] private int maxQueueSize = 1000;

        [Header("Data Flow")]
        [SerializeField] private bool enablePhysicalToDigital = true;
        [SerializeField] private bool enableDigitalToPhysical = true;

        // State manager reference
        private ISO23247StateManager stateManager;

        // Message queue
        private Queue<ISO23247Message> outgoingQueue = new Queue<ISO23247Message>();
        private Queue<ISO23247Message> incomingQueue = new Queue<ISO23247Message>();

        // Heartbeat tracking
        private float heartbeatTimer = 0f;
        private DateTime lastHeartbeat;
        private bool isConnected = false;

        // Statistics
        private int messagesSent = 0;
        private int messagesReceived = 0;
        private int messagesDropped = 0;
        private DateTime sessionStart;

        // Events
        public event Action<ISO23247Message> OnMessageSent;
        public event Action<ISO23247Message> OnMessageReceived;
        public event Action<bool> OnConnectionStatusChanged;

        void Start()
        {
            stateManager = GetComponent<ISO23247StateManager>();
            if (stateManager == null)
            {
                Debug.LogError("[ISO23247Exchange] ISO23247StateManager not found!");
                return;
            }

            // Subscribe to state updates
            stateManager.OnStateUpdated += HandleStateUpdate;
            stateManager.OnStateChanged += HandleStateChange;

            sessionStart = DateTime.UtcNow;
            lastHeartbeat = DateTime.UtcNow;

            Debug.Log("[ISO23247Exchange] Data exchange initialized");
        }

        void Update()
        {
            // Process incoming messages
            ProcessIncomingMessages();

            // Send heartbeat
            heartbeatTimer += Time.deltaTime;
            if (heartbeatTimer >= heartbeatInterval)
            {
                SendHeartbeat();
                heartbeatTimer = 0f;
            }
        }

        /// <summary>
        /// Handle state update from state manager
        /// </summary>
        private void HandleStateUpdate(ISO23247State state)
        {
            if (!enablePhysicalToDigital) return;

            // Create state update message
            var message = new ISO23247Message
            {
                MessageType = ISO23247MessageType.StateUpdate,
                MessageId = Guid.NewGuid().ToString(),
                Timestamp = DateTime.UtcNow,
                EntityId = state.EntityIdentification.EntityId,
                Payload = JsonConvert.SerializeObject(state)
            };

            QueueMessage(message);
        }

        /// <summary>
        /// Handle specific state change
        /// </summary>
        private void HandleStateChange(ISO23247StateChange change)
        {
            if (!enablePhysicalToDigital) return;

            // Create change notification message
            var message = new ISO23247Message
            {
                MessageType = ISO23247MessageType.StateChangeNotification,
                MessageId = Guid.NewGuid().ToString(),
                Timestamp = change.Timestamp,
                EntityId = stateManager.EntityId,
                Payload = JsonConvert.SerializeObject(change)
            };

            QueueMessage(message);
        }

        /// <summary>
        /// Queue outgoing message
        /// </summary>
        public void QueueMessage(ISO23247Message message)
        {
            if (outgoingQueue.Count >= maxQueueSize)
            {
                // Drop oldest message
                outgoingQueue.Dequeue();
                messagesDropped++;
                Debug.LogWarning($"[ISO23247Exchange] Queue full, dropped message");
            }

            outgoingQueue.Enqueue(message);
        }

        /// <summary>
        /// Send queued messages (called by network layer)
        /// </summary>
        public List<ISO23247Message> DequeueMessages(int maxCount = 10)
        {
            var messages = new List<ISO23247Message>();
            int count = 0;

            while (outgoingQueue.Count > 0 && count < maxCount)
            {
                var message = outgoingQueue.Dequeue();
                messages.Add(message);
                messagesSent++;
                count++;

                OnMessageSent?.Invoke(message);
            }

            return messages;
        }

        /// <summary>
        /// Receive incoming message from network layer
        /// </summary>
        public void ReceiveMessage(string messageJson)
        {
            try
            {
                var message = JsonConvert.DeserializeObject<ISO23247Message>(messageJson);
                if (message != null)
                {
                    incomingQueue.Enqueue(message);
                    messagesReceived++;
                }
            }
            catch (Exception e)
            {
                Debug.LogError($"[ISO23247Exchange] Failed to parse message: {e.Message}");
            }
        }

        /// <summary>
        /// Process incoming messages
        /// </summary>
        private void ProcessIncomingMessages()
        {
            while (incomingQueue.Count > 0)
            {
                var message = incomingQueue.Dequeue();
                ProcessMessage(message);
                OnMessageReceived?.Invoke(message);
            }
        }

        /// <summary>
        /// Process individual message
        /// </summary>
        private void ProcessMessage(ISO23247Message message)
        {
            switch (message.MessageType)
            {
                case ISO23247MessageType.StateUpdate:
                    if (enableDigitalToPhysical)
                    {
                        // Apply state update from physical twin
                        stateManager.ApplyStateJson(message.Payload);
                    }
                    break;

                case ISO23247MessageType.Command:
                    ProcessCommand(message);
                    break;

                case ISO23247MessageType.Heartbeat:
                    lastHeartbeat = DateTime.UtcNow;
                    if (!isConnected)
                    {
                        SetConnectionStatus(true);
                    }
                    break;

                case ISO23247MessageType.CapabilityQuery:
                    SendCapabilityResponse();
                    break;

                default:
                    Debug.LogWarning($"[ISO23247Exchange] Unknown message type: {message.MessageType}");
                    break;
            }
        }

        /// <summary>
        /// Process command message
        /// </summary>
        private void ProcessCommand(ISO23247Message message)
        {
            try
            {
                var command = JsonConvert.DeserializeObject<Dictionary<string, object>>(message.Payload);

                if (command.ContainsKey("action"))
                {
                    string action = command["action"].ToString();
                    Debug.Log($"[ISO23247Exchange] Received command: {action}");

                    // Handle different command types
                    switch (action)
                    {
                        case "set_status":
                            if (command.ContainsKey("status"))
                            {
                                stateManager.SetStatus(command["status"].ToString());
                            }
                            break;

                        case "update_capabilities":
                            if (command.ContainsKey("capabilities"))
                            {
                                var caps = JsonConvert.DeserializeObject<List<string>>(
                                    command["capabilities"].ToString());
                                stateManager.UpdateCapabilities(caps);
                            }
                            break;

                        default:
                            Debug.LogWarning($"[ISO23247Exchange] Unknown command: {action}");
                            break;
                    }

                    // Send acknowledgment
                    SendAcknowledgment(message.MessageId);
                }
            }
            catch (Exception e)
            {
                Debug.LogError($"[ISO23247Exchange] Error processing command: {e.Message}");
            }
        }

        /// <summary>
        /// Send heartbeat message
        /// </summary>
        private void SendHeartbeat()
        {
            var message = new ISO23247Message
            {
                MessageType = ISO23247MessageType.Heartbeat,
                MessageId = Guid.NewGuid().ToString(),
                Timestamp = DateTime.UtcNow,
                EntityId = stateManager.EntityId,
                Payload = "{}"
            };

            QueueMessage(message);

            // Check connection timeout
            if ((DateTime.UtcNow - lastHeartbeat).TotalSeconds > heartbeatInterval * 3)
            {
                if (isConnected)
                {
                    SetConnectionStatus(false);
                }
            }
        }

        /// <summary>
        /// Send capability response
        /// </summary>
        private void SendCapabilityResponse()
        {
            var capabilities = stateManager.CurrentState.CapabilityInformation;
            var message = new ISO23247Message
            {
                MessageType = ISO23247MessageType.CapabilityResponse,
                MessageId = Guid.NewGuid().ToString(),
                Timestamp = DateTime.UtcNow,
                EntityId = stateManager.EntityId,
                Payload = JsonConvert.SerializeObject(capabilities)
            };

            QueueMessage(message);
        }

        /// <summary>
        /// Send command acknowledgment
        /// </summary>
        private void SendAcknowledgment(string originalMessageId)
        {
            var ack = new Dictionary<string, object>
            {
                { "original_message_id", originalMessageId },
                { "status", "acknowledged" },
                { "timestamp", DateTime.UtcNow }
            };

            var message = new ISO23247Message
            {
                MessageType = ISO23247MessageType.Acknowledgment,
                MessageId = Guid.NewGuid().ToString(),
                Timestamp = DateTime.UtcNow,
                EntityId = stateManager.EntityId,
                Payload = JsonConvert.SerializeObject(ack)
            };

            QueueMessage(message);
        }

        /// <summary>
        /// Set connection status
        /// </summary>
        private void SetConnectionStatus(bool connected)
        {
            if (isConnected != connected)
            {
                isConnected = connected;
                OnConnectionStatusChanged?.Invoke(connected);
                Debug.Log($"[ISO23247Exchange] Connection status: {(connected ? "Connected" : "Disconnected")}");
            }
        }

        /// <summary>
        /// Get exchange statistics
        /// </summary>
        public ExchangeStatistics GetStatistics()
        {
            TimeSpan uptime = DateTime.UtcNow - sessionStart;

            return new ExchangeStatistics
            {
                MessagesSent = messagesSent,
                MessagesReceived = messagesReceived,
                MessagesDropped = messagesDropped,
                QueueSize = outgoingQueue.Count,
                IsConnected = isConnected,
                LastHeartbeat = lastHeartbeat,
                Uptime = uptime,
                MessageRate = messagesSent / (float)uptime.TotalSeconds
            };
        }

        void OnDestroy()
        {
            if (stateManager != null)
            {
                stateManager.OnStateUpdated -= HandleStateUpdate;
                stateManager.OnStateChanged -= HandleStateChange;
            }
        }

        #region Public Properties

        public bool IsConnected => isConnected;
        public int QueuedMessages => outgoingQueue.Count;
        public string ExchangeEndpoint => exchangeEndpoint;

        #endregion
    }

    #region ISO 23247-4 Data Structures

    /// <summary>
    /// ISO 23247-4 message types
    /// </summary>
    public enum ISO23247MessageType
    {
        StateUpdate,
        StateChangeNotification,
        Command,
        Acknowledgment,
        Heartbeat,
        CapabilityQuery,
        CapabilityResponse,
        Error
    }

    /// <summary>
    /// ISO 23247-4 message structure
    /// </summary>
    [Serializable]
    public class ISO23247Message
    {
        public ISO23247MessageType MessageType { get; set; }
        public string MessageId { get; set; }
        public DateTime Timestamp { get; set; }
        public string EntityId { get; set; }
        public string Payload { get; set; }
    }

    /// <summary>
    /// Exchange statistics
    /// </summary>
    [Serializable]
    public struct ExchangeStatistics
    {
        public int MessagesSent;
        public int MessagesReceived;
        public int MessagesDropped;
        public int QueueSize;
        public bool IsConnected;
        public DateTime LastHeartbeat;
        public TimeSpan Uptime;
        public float MessageRate;
    }

    #endregion
}
