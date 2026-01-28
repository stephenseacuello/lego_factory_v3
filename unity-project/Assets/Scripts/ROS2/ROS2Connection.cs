using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.ROS2
{
    /// <summary>
    /// ROS2 connection manager for Unity.
    /// Uses Unity Robotics Hub's ROS-TCP-Connector for communication.
    ///
    /// Requires packages:
    /// - com.unity.robotics.ros-tcp-connector
    /// - com.unity.robotics.urdf-importer
    /// </summary>
    public class ROS2Connection : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string rosIPAddress = "127.0.0.1";
        [SerializeField] private int rosPort = 10000;
        [SerializeField] private bool autoConnect = true;
        [SerializeField] private float reconnectDelay = 3f;

        [Header("Topic Configuration")]
        [SerializeField] private string machineStateTopic = "/cnc/machine_state";
        [SerializeField] private string jointStateTopic = "/cnc/joint_states";
        [SerializeField] private string commandTopic = "/cnc/command";
        [SerializeField] private string diagnosticsTopic = "/cnc/diagnostics";

        [Header("Status")]
        [SerializeField] private bool isConnected = false;

        // Events
        public event Action OnConnected;
        public event Action OnDisconnected;
        public event Action<MachineStateMsg> OnMachineStateReceived;
        public event Action<JointStateMsg> OnJointStateReceived;

        // Singleton
        public static ROS2Connection Instance { get; private set; }

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

        /// <summary>
        /// Connect to ROS2 via TCP connector
        /// </summary>
        public void Connect()
        {
            Debug.Log($"[ROS2] Connecting to {rosIPAddress}:{rosPort}...");

#if UNITY_ROBOTICS_ROS_TCP_CONNECTOR
            // Configure ROSConnection from Unity Robotics Hub
            var rosConnection = ROSConnection.GetOrCreateInstance();
            rosConnection.RosIPAddress = rosIPAddress;
            rosConnection.RosPort = rosPort;
            rosConnection.Connect();

            // Subscribe to topics
            rosConnection.Subscribe<MachineStateMsg>(machineStateTopic, HandleMachineState);
            rosConnection.Subscribe<JointStateMsg>(jointStateTopic, HandleJointState);

            isConnected = true;
            OnConnected?.Invoke();
            Debug.Log("[ROS2] Connected and subscribed to topics");
#else
            // Fallback for when ROS-TCP-Connector is not installed
            Debug.LogWarning("[ROS2] ROS-TCP-Connector not installed. Using mock connection.");
            StartCoroutine(MockConnection());
#endif
        }

        /// <summary>
        /// Disconnect from ROS2
        /// </summary>
        public void Disconnect()
        {
#if UNITY_ROBOTICS_ROS_TCP_CONNECTOR
            var rosConnection = ROSConnection.GetOrCreateInstance();
            rosConnection.Disconnect();
#endif
            isConnected = false;
            OnDisconnected?.Invoke();
            Debug.Log("[ROS2] Disconnected");
        }

        /// <summary>
        /// Publish a command to ROS2
        /// </summary>
        public void PublishCommand(CommandMsg command)
        {
#if UNITY_ROBOTICS_ROS_TCP_CONNECTOR
            var rosConnection = ROSConnection.GetOrCreateInstance();
            rosConnection.Publish(commandTopic, command);
#else
            Debug.Log($"[ROS2 Mock] Would publish command: {command.command_type}");
#endif
        }

        /// <summary>
        /// Send G-code via ROS2
        /// </summary>
        public void SendGCode(string gcode)
        {
            var cmd = new CommandMsg
            {
                command_type = "gcode",
                gcode = gcode,
                timestamp = GetTimestamp()
            };
            PublishCommand(cmd);
        }

        /// <summary>
        /// Send jog command via ROS2
        /// </summary>
        public void Jog(string axis, float distance, float feedRate = 1000f)
        {
            var cmd = new CommandMsg
            {
                command_type = "jog",
                axis = axis,
                distance = distance,
                feed_rate = feedRate,
                timestamp = GetTimestamp()
            };
            PublishCommand(cmd);
        }

        /// <summary>
        /// Emergency stop via ROS2
        /// </summary>
        public void EmergencyStop()
        {
            var cmd = new CommandMsg
            {
                command_type = "estop",
                priority = 255, // Highest priority
                timestamp = GetTimestamp()
            };
            PublishCommand(cmd);
            Debug.LogWarning("[ROS2] Emergency stop sent!");
        }

        private void HandleMachineState(MachineStateMsg msg)
        {
            OnMachineStateReceived?.Invoke(msg);
        }

        private void HandleJointState(JointStateMsg msg)
        {
            OnJointStateReceived?.Invoke(msg);
        }

        private double GetTimestamp()
        {
            return DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;
        }

        // Mock connection for development without ROS
        private IEnumerator MockConnection()
        {
            yield return new WaitForSeconds(0.5f);
            isConnected = true;
            OnConnected?.Invoke();
            Debug.Log("[ROS2 Mock] Mock connection established");

            // Simulate periodic state updates
            while (isConnected)
            {
                yield return new WaitForSeconds(0.1f);

                // Generate mock machine state
                var mockState = new MachineStateMsg
                {
                    position_x = UnityEngine.Random.Range(0f, 140f),
                    position_y = UnityEngine.Random.Range(0f, 102f),
                    position_z = UnityEngine.Random.Range(0f, 152f),
                    velocity = 100f,
                    status = 3, // Idle
                    is_homed = true
                };
                OnMachineStateReceived?.Invoke(mockState);
            }
        }

        // Public accessors
        public bool IsConnected => isConnected;
        public string RosIP => rosIPAddress;
        public int RosPort => rosPort;
    }

    // =========================================================================
    // ROS2 Message Types (matching ROS2 message definitions)
    // =========================================================================

    /// <summary>
    /// Machine state message from CNC controller
    /// Matches: cnc_interfaces/msg/MachineState
    /// </summary>
    [Serializable]
    public class MachineStateMsg
    {
        public double timestamp;
        public string machine_id;

        // Position (mm)
        public float position_x;
        public float position_y;
        public float position_z;

        // Velocity and feed
        public float velocity;
        public float feed_rate;

        // Status
        public int status; // 0=Init, 1=Ready, 2=Alarm, 3=Idle, 4=Cycle, 5=Running
        public bool is_homed;
        public bool is_alarm;
        public string alarm_message;

        // Spindle
        public float spindle_rpm;
        public bool spindle_on;

        // Program
        public int current_line;
        public string current_file;

        // Helper properties for Unity
        public Vector3 Position => new Vector3(position_x, position_z, position_y) * 0.001f;
        public bool IsIdle => status == 3;
        public bool IsRunning => status == 5;
    }

    /// <summary>
    /// Joint state message for robot arms
    /// Matches: sensor_msgs/msg/JointState
    /// </summary>
    [Serializable]
    public class JointStateMsg
    {
        public double timestamp;
        public string[] name;
        public double[] position;  // radians
        public double[] velocity;  // rad/s
        public double[] effort;    // Nm

        public float[] GetPositionsDegrees()
        {
            if (position == null) return new float[0];
            float[] degrees = new float[position.Length];
            for (int i = 0; i < position.Length; i++)
            {
                degrees[i] = (float)(position[i] * Mathf.Rad2Deg);
            }
            return degrees;
        }
    }

    /// <summary>
    /// Command message to CNC/robot
    /// Matches: cnc_interfaces/msg/Command
    /// </summary>
    [Serializable]
    public class CommandMsg
    {
        public double timestamp;
        public string command_type; // "gcode", "jog", "estop", "home", "program"
        public string gcode;
        public string axis;
        public float distance;
        public float feed_rate;
        public int priority; // 0-255, higher = more urgent
        public string program_file;
    }

    /// <summary>
    /// Diagnostic message for health monitoring
    /// Matches: diagnostic_msgs/msg/DiagnosticStatus
    /// </summary>
    [Serializable]
    public class DiagnosticMsg
    {
        public string name;
        public int level; // 0=OK, 1=WARN, 2=ERROR, 3=STALE
        public string message;
        public string hardware_id;
        public KeyValue[] values;
    }

    [Serializable]
    public class KeyValue
    {
        public string key;
        public string value;
    }
}
