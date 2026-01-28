using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Events;

namespace CNCScada.Connection
{
    /// <summary>
    /// Flask SocketIO client for real-time communication with CNC SCADA backend.
    /// Handles machine state updates, sensor data, and control commands.
    /// </summary>
    public class FlaskSocketIOClient : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string serverUrl = "http://localhost:5001";
        [SerializeField] private bool autoConnect = true;
        [SerializeField] private float reconnectDelay = 3f;

        [Header("Subscriptions")]
        [SerializeField] private bool subscribeTinyGStatus = true;
        [SerializeField] private bool subscribeSensorData = true;
        [SerializeField] private bool subscribeMCCData = true;

        [Header("Events")]
        public UnityEvent OnConnected;
        public UnityEvent OnDisconnected;
        public UnityEvent<string> OnError;
        public UnityEvent<MachineState> OnMachineStateUpdate;
        public UnityEvent<SensorData> OnSensorDataUpdate;

        // Connection state
        private bool isConnected = false;
        private WebSocketConnection webSocket;

        // Singleton pattern for easy access
        public static FlaskSocketIOClient Instance { get; private set; }

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
        /// Connect to Flask SocketIO server
        /// </summary>
        public void Connect()
        {
            if (isConnected) return;

            Debug.Log($"[FlaskSocketIO] Connecting to {serverUrl}...");
            StartCoroutine(ConnectCoroutine());
        }

        private IEnumerator ConnectCoroutine()
        {
            // Initialize WebSocket connection
            string wsUrl = serverUrl.Replace("http://", "ws://").Replace("https://", "wss://");
            wsUrl += "/socket.io/?EIO=4&transport=websocket";

            webSocket = new WebSocketConnection(wsUrl);
            webSocket.OnOpen += HandleOpen;
            webSocket.OnClose += HandleClose;
            webSocket.OnMessage += HandleMessage;
            webSocket.OnError += HandleError;

            yield return webSocket.Connect();

            if (webSocket.IsConnected)
            {
                isConnected = true;
                SubscribeToChannels();
                OnConnected?.Invoke();
            }
        }

        /// <summary>
        /// Disconnect from server
        /// </summary>
        public void Disconnect()
        {
            if (webSocket != null)
            {
                webSocket.Close();
            }
            isConnected = false;
        }

        private void SubscribeToChannels()
        {
            if (subscribeTinyGStatus)
            {
                SendMessage("subscribe", new { channel = "tinyg_status" });
            }
            if (subscribeSensorData)
            {
                SendMessage("subscribe", new { channel = "sensor_data" });
            }
            if (subscribeMCCData)
            {
                SendMessage("subscribe", new { channel = "mcc_data" });
            }

            Debug.Log("[FlaskSocketIO] Subscribed to channels");
        }

        private void HandleOpen()
        {
            Debug.Log("[FlaskSocketIO] Connected successfully");
        }

        private void HandleClose()
        {
            Debug.Log("[FlaskSocketIO] Disconnected");
            isConnected = false;
            OnDisconnected?.Invoke();

            // Auto-reconnect
            if (autoConnect)
            {
                StartCoroutine(ReconnectAfterDelay());
            }
        }

        private IEnumerator ReconnectAfterDelay()
        {
            yield return new WaitForSeconds(reconnectDelay);
            Connect();
        }

        private void HandleMessage(string message)
        {
            try
            {
                // Parse SocketIO message format
                var data = ParseSocketIOMessage(message);
                if (data.eventName == null) return;

                string eventName = data.eventName;
                string payload = data.payload;

                switch (eventName)
                {
                    case "tinyg_status":
                        var machineState = JsonUtility.FromJson<MachineState>(payload);
                        OnMachineStateUpdate?.Invoke(machineState);
                        break;

                    case "sensor_data":
                        var sensorData = JsonUtility.FromJson<SensorData>(payload);
                        OnSensorDataUpdate?.Invoke(sensorData);
                        break;

                    case "mcc_data":
                        // Handle MCC DAQ data
                        Debug.Log($"[FlaskSocketIO] MCC Data: {payload}");
                        break;

                    default:
                        Debug.Log($"[FlaskSocketIO] Unknown event: {eventName}");
                        break;
                }
            }
            catch (Exception e)
            {
                Debug.LogError($"[FlaskSocketIO] Error parsing message: {e.Message}");
            }
        }

        private void HandleError(string error)
        {
            Debug.LogError($"[FlaskSocketIO] Error: {error}");
            OnError?.Invoke(error);
        }

        /// <summary>
        /// Send a command to the CNC machine
        /// </summary>
        public void SendGCode(string gcode)
        {
            SendMessage("gcode_command", new { command = gcode });
        }

        /// <summary>
        /// Jog the machine in a specific direction
        /// </summary>
        public void Jog(string axis, float distance, float feedRate = 1000f)
        {
            SendMessage("jog", new
            {
                axis = axis,
                distance = distance,
                feed_rate = feedRate
            });
        }

        /// <summary>
        /// Emergency stop
        /// </summary>
        public void EmergencyStop()
        {
            SendMessage("emergency_stop", new { });
        }

        /// <summary>
        /// Request current machine state
        /// </summary>
        public void RequestMachineState()
        {
            SendMessage("request_state", new { });
        }

        private void SendMessage(string eventName, object data)
        {
            if (!isConnected || webSocket == null) return;

            string json = JsonUtility.ToJson(data);
            string message = $"42[\"{eventName}\",{json}]";
            webSocket.Send(message);
        }

        private (string eventName, string payload) ParseSocketIOMessage(string message)
        {
            // SocketIO message format: 42["eventName",{payload}]
            if (!message.StartsWith("42[")) return (null, null);

            try
            {
                string content = message.Substring(2);
                // Parse the array
                int firstQuote = content.IndexOf('"');
                int secondQuote = content.IndexOf('"', firstQuote + 1);
                string eventName = content.Substring(firstQuote + 1, secondQuote - firstQuote - 1);

                int payloadStart = content.IndexOf(',') + 1;
                int payloadEnd = content.LastIndexOf(']');
                string payload = content.Substring(payloadStart, payloadEnd - payloadStart);

                return (eventName, payload);
            }
            catch
            {
                return (null, null);
            }
        }

        // Public properties
        public bool IsConnected => isConnected;
        public string ServerUrl => serverUrl;
    }

    /// <summary>
    /// Machine state data from TinyG controller
    /// </summary>
    [Serializable]
    public class MachineState
    {
        public float posx;
        public float posy;
        public float posz;
        public float vel;
        public int stat;
        public int line;
        public float feed;
        public int unit;
        public int coor;
        public int momo;
        public int plan;
        public int path;
        public int dist;
        public int frmo;
        public int hold;
        public int hom;

        // Helper properties
        public Vector3 Position => new Vector3(posx, posz, posy); // Y-up conversion
        public bool IsIdle => stat == 3;
        public bool IsRunning => stat == 5;
        public bool IsHomed => hom == 1;
    }

    /// <summary>
    /// Sensor data from Arduino/sensors
    /// </summary>
    [Serializable]
    public class SensorData
    {
        public float temperature;
        public float humidity;
        public float vibration_x;
        public float vibration_y;
        public float vibration_z;
        public float sound_level;
        public long timestamp;

        public Vector3 Vibration => new Vector3(vibration_x, vibration_y, vibration_z);
    }
}
