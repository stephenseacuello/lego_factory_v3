using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using CNCScada.Connection;

namespace CNCScada.DigitalTwin
{
    /// <summary>
    /// Main controller for the CNC SCADA Digital Twin visualization.
    /// Manages machine models, animations, and real-time state updates.
    /// </summary>
    public class DigitalTwinController : MonoBehaviour
    {
        [Header("Scene References")]
        [SerializeField] private Transform machineContainer;
        [SerializeField] private Transform robotContainer;

        [Header("Machine Prefabs")]
        [SerializeField] private GameObject bantamCNCPrefab;
        [SerializeField] private GameObject niryoNed2Prefab;
        [SerializeField] private GameObject xArmPrefab;

        [Header("Visualization Settings")]
        [SerializeField] private bool showToolpath = true;
        [SerializeField] private bool showWorkEnvelope = true;
        [SerializeField] private float positionSmoothTime = 0.05f;

        [Header("Work Envelope (mm)")]
        [SerializeField] private Vector3 workEnvelopeMin = new Vector3(0, 0, 0);
        [SerializeField] private Vector3 workEnvelopeMax = new Vector3(140, 102, 152);

        // Machine instances
        private Dictionary<string, MachineController> machines = new Dictionary<string, MachineController>();
        private Dictionary<string, RobotController> robots = new Dictionary<string, RobotController>();

        // Toolpath visualization
        private LineRenderer toolpathLine;
        private List<Vector3> toolpathPoints = new List<Vector3>();
        private const int MAX_TOOLPATH_POINTS = 10000;

        // State
        private Vector3 currentPosition;
        private Vector3 targetPosition;
        private Vector3 velocity;
        private bool isHomed = false;
        private int machineStatus = 0;

        // Singleton
        public static DigitalTwinController Instance { get; private set; }

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

            InitializeContainers();
        }

        private void Start()
        {
            SetupToolpathVisualization();
            SetupWorkEnvelope();

            // Subscribe to machine state updates
            if (FlaskSocketIOClient.Instance != null)
            {
                FlaskSocketIOClient.Instance.OnMachineStateUpdate.AddListener(HandleMachineState);
                FlaskSocketIOClient.Instance.OnSensorDataUpdate.AddListener(HandleSensorData);
            }

            // Spawn default machines
            SpawnDefaultConfiguration();
        }

        private void Update()
        {
            // Smooth position interpolation for 60Hz updates
            if (machines.ContainsKey("bantam-cnc"))
            {
                var bantam = machines["bantam-cnc"];
                bantam.UpdateTargetPosition(targetPosition);
            }
        }

        private void InitializeContainers()
        {
            if (machineContainer == null)
            {
                var machineObj = new GameObject("Machines");
                machineContainer = machineObj.transform;
            }

            if (robotContainer == null)
            {
                var robotObj = new GameObject("Robots");
                robotContainer = robotObj.transform;
            }
        }

        private void SpawnDefaultConfiguration()
        {
            // Spawn Bantam CNC at center
            SpawnMachine("bantam-cnc", MachineType.BantamCNC, Vector3.zero);

            // Spawn Niryo Ned2 to the left
            SpawnRobot("niryo-ned2", RobotType.NiryoNed2, new Vector3(-0.5f, 0, 0));

            // Spawn xArm to the right
            SpawnRobot("xarm-lite6", RobotType.XArm, new Vector3(0.5f, 0, 0));

            Debug.Log("[DigitalTwin] Default configuration spawned");
        }

        /// <summary>
        /// Spawn a CNC machine instance
        /// </summary>
        public void SpawnMachine(string id, MachineType type, Vector3 position)
        {
            if (machines.ContainsKey(id))
            {
                Debug.LogWarning($"[DigitalTwin] Machine {id} already exists");
                return;
            }

            GameObject prefab = type switch
            {
                MachineType.BantamCNC => bantamCNCPrefab,
                _ => null
            };

            if (prefab == null)
            {
                // Create placeholder if no prefab assigned
                var placeholder = GameObject.CreatePrimitive(PrimitiveType.Cube);
                placeholder.name = id;
                placeholder.transform.SetParent(machineContainer);
                placeholder.transform.position = position;
                placeholder.transform.localScale = new Vector3(0.3f, 0.2f, 0.3f);

                var controller = placeholder.AddComponent<MachineController>();
                controller.Initialize(id, type);
                machines[id] = controller;

                Debug.Log($"[DigitalTwin] Spawned placeholder for {id}");
            }
            else
            {
                var instance = Instantiate(prefab, position, Quaternion.identity, machineContainer);
                instance.name = id;

                var controller = instance.GetComponent<MachineController>();
                if (controller == null)
                {
                    controller = instance.AddComponent<MachineController>();
                }
                controller.Initialize(id, type);
                machines[id] = controller;

                Debug.Log($"[DigitalTwin] Spawned {type} as {id}");
            }
        }

        /// <summary>
        /// Spawn a robot instance
        /// </summary>
        public void SpawnRobot(string id, RobotType type, Vector3 position)
        {
            if (robots.ContainsKey(id))
            {
                Debug.LogWarning($"[DigitalTwin] Robot {id} already exists");
                return;
            }

            GameObject prefab = type switch
            {
                RobotType.NiryoNed2 => niryoNed2Prefab,
                RobotType.XArm => xArmPrefab,
                _ => null
            };

            if (prefab == null)
            {
                // Create placeholder
                var placeholder = new GameObject(id);
                placeholder.transform.SetParent(robotContainer);
                placeholder.transform.position = position;

                // Simple arm representation
                var baseCyl = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                baseCyl.transform.SetParent(placeholder.transform);
                baseCyl.transform.localPosition = new Vector3(0, 0.05f, 0);
                baseCyl.transform.localScale = new Vector3(0.1f, 0.05f, 0.1f);

                var armCyl = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                armCyl.transform.SetParent(placeholder.transform);
                armCyl.transform.localPosition = new Vector3(0, 0.2f, 0);
                armCyl.transform.localScale = new Vector3(0.03f, 0.15f, 0.03f);

                var controller = placeholder.AddComponent<RobotController>();
                controller.Initialize(id, type);
                robots[id] = controller;

                Debug.Log($"[DigitalTwin] Spawned placeholder for {id}");
            }
            else
            {
                var instance = Instantiate(prefab, position, Quaternion.identity, robotContainer);
                instance.name = id;

                var controller = instance.GetComponent<RobotController>();
                if (controller == null)
                {
                    controller = instance.AddComponent<RobotController>();
                }
                controller.Initialize(id, type);
                robots[id] = controller;

                Debug.Log($"[DigitalTwin] Spawned {type} as {id}");
            }
        }

        private void SetupToolpathVisualization()
        {
            if (!showToolpath) return;

            var toolpathObj = new GameObject("Toolpath");
            toolpathObj.transform.SetParent(transform);

            toolpathLine = toolpathObj.AddComponent<LineRenderer>();
            toolpathLine.material = new Material(Shader.Find("Sprites/Default"));
            toolpathLine.startColor = Color.green;
            toolpathLine.endColor = Color.yellow;
            toolpathLine.startWidth = 0.001f;
            toolpathLine.endWidth = 0.001f;
            toolpathLine.positionCount = 0;
        }

        private void SetupWorkEnvelope()
        {
            if (!showWorkEnvelope) return;

            var envelopeObj = new GameObject("WorkEnvelope");
            envelopeObj.transform.SetParent(machineContainer);

            // Create wireframe cube representing work envelope
            var lineRenderer = envelopeObj.AddComponent<LineRenderer>();
            lineRenderer.material = new Material(Shader.Find("Sprites/Default"));
            lineRenderer.startColor = new Color(0, 1, 1, 0.3f);
            lineRenderer.endColor = new Color(0, 1, 1, 0.3f);
            lineRenderer.startWidth = 0.001f;
            lineRenderer.endWidth = 0.001f;

            // Convert mm to meters for Unity
            Vector3 min = workEnvelopeMin * 0.001f;
            Vector3 max = workEnvelopeMax * 0.001f;

            // Draw wireframe box
            Vector3[] corners = new Vector3[]
            {
                new Vector3(min.x, min.y, min.z),
                new Vector3(max.x, min.y, min.z),
                new Vector3(max.x, min.y, max.z),
                new Vector3(min.x, min.y, max.z),
                new Vector3(min.x, min.y, min.z),
                new Vector3(min.x, max.y, min.z),
                new Vector3(max.x, max.y, min.z),
                new Vector3(max.x, min.y, min.z),
                new Vector3(max.x, max.y, min.z),
                new Vector3(max.x, max.y, max.z),
                new Vector3(max.x, min.y, max.z),
                new Vector3(max.x, max.y, max.z),
                new Vector3(min.x, max.y, max.z),
                new Vector3(min.x, min.y, max.z),
                new Vector3(min.x, max.y, max.z),
                new Vector3(min.x, max.y, min.z)
            };

            lineRenderer.positionCount = corners.Length;
            lineRenderer.SetPositions(corners);
        }

        /// <summary>
        /// Handle machine state updates from Flask backend
        /// </summary>
        private void HandleMachineState(MachineState state)
        {
            // Update target position (mm to meters)
            targetPosition = new Vector3(
                state.posx * 0.001f,
                state.posz * 0.001f,  // Z in TinyG becomes Y in Unity (height)
                state.posy * 0.001f   // Y in TinyG becomes Z in Unity (depth)
            );

            machineStatus = state.stat;
            isHomed = state.IsHomed;

            // Add to toolpath if cutting
            if (state.IsRunning && showToolpath)
            {
                AddToolpathPoint(targetPosition);
            }

            // Update UI indicators
            UpdateStatusIndicators(state);
        }

        /// <summary>
        /// Handle sensor data updates
        /// </summary>
        private void HandleSensorData(SensorData data)
        {
            // Could visualize temperature as color on machine model
            // Could show vibration as particle effects
            Debug.Log($"[DigitalTwin] Sensor: Temp={data.temperature:F1}°C, Vibration={data.Vibration.magnitude:F3}");
        }

        private void AddToolpathPoint(Vector3 point)
        {
            toolpathPoints.Add(point);

            // Limit points to prevent memory issues
            if (toolpathPoints.Count > MAX_TOOLPATH_POINTS)
            {
                toolpathPoints.RemoveAt(0);
            }

            if (toolpathLine != null)
            {
                toolpathLine.positionCount = toolpathPoints.Count;
                toolpathLine.SetPositions(toolpathPoints.ToArray());
            }
        }

        /// <summary>
        /// Clear the toolpath visualization
        /// </summary>
        public void ClearToolpath()
        {
            toolpathPoints.Clear();
            if (toolpathLine != null)
            {
                toolpathLine.positionCount = 0;
            }
        }

        private void UpdateStatusIndicators(MachineState state)
        {
            // Could update UI elements, LEDs on machine model, etc.
            // Status codes: 0=Init, 1=Ready, 2=Alarm, 3=Idle, 4=Cycle, 5=Running
        }

        /// <summary>
        /// Send jog command via SocketIO
        /// </summary>
        public void JogAxis(string axis, float distance)
        {
            FlaskSocketIOClient.Instance?.Jog(axis, distance);
        }

        /// <summary>
        /// Send G-code command
        /// </summary>
        public void SendGCode(string gcode)
        {
            FlaskSocketIOClient.Instance?.SendGCode(gcode);
        }

        /// <summary>
        /// Trigger emergency stop
        /// </summary>
        public void EmergencyStop()
        {
            FlaskSocketIOClient.Instance?.EmergencyStop();
        }

        // Public accessors
        public Vector3 CurrentPosition => currentPosition;
        public Vector3 TargetPosition => targetPosition;
        public bool IsHomed => isHomed;
        public int MachineStatus => machineStatus;
    }

    public enum MachineType
    {
        BantamCNC,
        Generic3Axis,
        Generic5Axis
    }

    public enum RobotType
    {
        NiryoNed2,
        XArm,
        Generic6DOF
    }
}
