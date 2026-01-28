using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using CNCScada.Sensors;
using CNC_SCADA.DigitalTwin.URDF;

namespace CNCScada.Machines
{
    /// <summary>
    /// Controller for Bantam Tools Desktop CNC Milling Machine (Explorer model).
    ///
    /// Specifications:
    /// - Work envelope: 140mm x 102mm x 152mm (X x Y x Z)
    /// - Spindle: 10,000 RPM max
    /// - Feed rate: Up to 2500mm/min
    /// - Resolution: 0.0005" (0.0127mm)
    /// </summary>
    public class BantamCNCController : MonoBehaviour
    {
        [Header("Machine Identification")]
        public string machineId = "bantam-cnc-001";
        public string machineName = "Bantam Desktop Explorer";

        [Header("Work Envelope (mm)")]
        public Vector3 workEnvelopeMin = Vector3.zero;
        public Vector3 workEnvelopeMax = new Vector3(140f, 102f, 152f);

        [Header("Current State")]
        [SerializeField] private Vector3 currentPosition;
        [SerializeField] private Vector3 targetPosition;
        [SerializeField] private float currentFeedRate;
        [SerializeField] private float spindleRPM;
        [SerializeField] private bool spindleOn;
        [SerializeField] private bool isHomed;
        [SerializeField] private MachineStatus status = MachineStatus.Idle;

        [Header("Motion Settings")]
        public float positionSmoothTime = 0.05f;
        public float maxFeedRate = 2500f; // mm/min

        [Header("Axis References")]
        public Transform xAxisCarriage;
        public Transform yAxisTable;
        public Transform zAxisSpindle;
        public Transform spindleMotor;

        [Header("Sensor Configuration")]
        public bool enableSensors = true;
        [SerializeField] private float spindleTemperature = 25f;
        [SerializeField] private float motorTemperature = 28f;
        [SerializeField] private Vector3 vibration = Vector3.zero;
        [SerializeField] private float[] axisLoads = new float[3]; // X, Y, Z
        [SerializeField] private float powerConsumption = 0f;
        [SerializeField] private float soundLevel = 45f;

        // Internal state
        private Vector3 positionVelocity;
        private float spindleAngle;

        // Sensor IDs for this machine
        private string tempSpindleSensorId;
        private string tempMotorSensorId;
        private string vibrationSensorId;
        private string[] loadSensorIds = new string[3];
        private string acousticSensorId;

        // Events
        public event Action<Vector3> OnPositionChanged;
        public event Action<MachineStatus> OnStatusChanged;
        public event Action<float> OnSpindleChanged;

        public enum MachineStatus
        {
            Initializing = 0,
            Ready = 1,
            Alarm = 2,
            Idle = 3,
            Cycle = 4,
            Running = 5,
            Homing = 6,
            Jogging = 7
        }

        private void Awake()
        {
            // Auto-find axis transforms if not assigned
            if (xAxisCarriage == null) xAxisCarriage = transform.Find("XAxis");
            if (yAxisTable == null) yAxisTable = transform.Find("YAxis");
            if (zAxisSpindle == null) zAxisSpindle = transform.Find("ZAxis");
            if (spindleMotor == null) spindleMotor = transform.Find("Spindle");

            // Initialize sensor IDs
            tempSpindleSensorId = $"{machineId}_temp_spindle";
            tempMotorSensorId = $"{machineId}_temp_motor";
            vibrationSensorId = $"{machineId}_vibration";
            loadSensorIds[0] = $"{machineId}_load_x";
            loadSensorIds[1] = $"{machineId}_load_y";
            loadSensorIds[2] = $"{machineId}_load_z";
            acousticSensorId = $"{machineId}_acoustic";
        }

        private void Start()
        {
            if (enableSensors)
            {
                RegisterSensors();
            }
        }

        private void Update()
        {
            UpdateAxisPositions();
            UpdateSpindleRotation();

            if (enableSensors)
            {
                UpdateSensorSimulation();
            }
        }

        /// <summary>
        /// Register sensors with the SensorSystem
        /// </summary>
        private void RegisterSensors()
        {
            if (SensorSystem.Instance == null)
            {
                Debug.LogWarning($"[{machineId}] SensorSystem not available");
                return;
            }

            // Add temperature sensors
            SensorSystem.Instance.temperatureSensors.Add(new TemperatureSensor
            {
                sensorId = tempSpindleSensorId,
                sensorName = $"{machineName} Spindle Temperature",
                location = "Spindle",
                attachedTo = machineId,
                warningThreshold = 55f,
                criticalThreshold = 70f,
                ambientTemp = 25f,
                maxOperatingTemp = 80f
            });

            SensorSystem.Instance.temperatureSensors.Add(new TemperatureSensor
            {
                sensorId = tempMotorSensorId,
                sensorName = $"{machineName} Motor Temperature",
                location = "Motor",
                attachedTo = machineId,
                warningThreshold = 50f,
                criticalThreshold = 65f,
                ambientTemp = 28f
            });

            // Add vibration sensor
            SensorSystem.Instance.vibrationSensors.Add(new VibrationSensor
            {
                sensorId = vibrationSensorId,
                sensorName = $"{machineName} Vibration",
                location = "Spindle Base",
                attachedTo = machineId,
                warningThreshold = 2.5f,
                criticalThreshold = 7.0f
            });

            // Add current/load sensors for each axis
            for (int i = 0; i < 3; i++)
            {
                string axis = new[] { "X", "Y", "Z" }[i];
                SensorSystem.Instance.currentSensors.Add(new CurrentSensor
                {
                    sensorId = loadSensorIds[i],
                    sensorName = $"{machineName} {axis}-Axis Load",
                    location = $"{axis}-Axis Motor",
                    attachedTo = machineId,
                    nominalCurrent = 2f,
                    maxCurrent = 8f,
                    warningThreshold = 6f,
                    criticalThreshold = 7.5f
                });
            }

            // Add acoustic sensor
            SensorSystem.Instance.acousticSensors.Add(new AcousticSensor
            {
                sensorId = acousticSensorId,
                sensorName = $"{machineName} Sound Level",
                location = "Enclosure",
                attachedTo = machineId,
                warningThreshold = 80f,
                criticalThreshold = 90f
            });

            Debug.Log($"[{machineId}] Registered sensors with SensorSystem");
        }

        /// <summary>
        /// Simulate sensor values based on machine state
        /// </summary>
        private void UpdateSensorSimulation()
        {
            // Spindle temperature increases with RPM
            float spindleHeatFactor = spindleOn ? (spindleRPM / 10000f) * 30f : 0f;
            spindleTemperature = Mathf.Lerp(spindleTemperature, 25f + spindleHeatFactor, Time.deltaTime * 0.1f);
            spindleTemperature += UnityEngine.Random.Range(-0.2f, 0.2f);

            // Motor temperature increases with feed rate
            float motorHeatFactor = (currentFeedRate / maxFeedRate) * 15f;
            motorTemperature = Mathf.Lerp(motorTemperature, 28f + motorHeatFactor, Time.deltaTime * 0.1f);
            motorTemperature += UnityEngine.Random.Range(-0.1f, 0.1f);

            // Vibration increases with spindle speed and cutting
            float vibrationBase = spindleOn ? (spindleRPM / 10000f) * 1.5f : 0.1f;
            vibration = new Vector3(
                vibrationBase + UnityEngine.Random.Range(-0.3f, 0.3f),
                vibrationBase * 0.8f + UnityEngine.Random.Range(-0.2f, 0.2f),
                vibrationBase * 0.6f + UnityEngine.Random.Range(-0.2f, 0.2f)
            );

            // Axis loads based on movement
            axisLoads[0] = Mathf.Abs(positionVelocity.x) * 50f + UnityEngine.Random.Range(0.5f, 1.5f);
            axisLoads[1] = Mathf.Abs(positionVelocity.z) * 50f + UnityEngine.Random.Range(0.5f, 1.5f);
            axisLoads[2] = Mathf.Abs(positionVelocity.y) * 60f + UnityEngine.Random.Range(0.5f, 1.5f);

            // Sound level
            float baseSound = 45f;
            if (spindleOn) baseSound += 20f + (spindleRPM / 10000f) * 15f;
            if (status == MachineStatus.Running) baseSound += 10f;
            soundLevel = baseSound + UnityEngine.Random.Range(-2f, 2f);

            // Power consumption
            powerConsumption = 50f; // Base
            if (spindleOn) powerConsumption += (spindleRPM / 10000f) * 200f;
            powerConsumption += (currentFeedRate / maxFeedRate) * 100f;

            // Update sensor system with values
            if (SensorSystem.Instance != null)
            {
                SensorSystem.Instance.InjectSensorData(tempSpindleSensorId, spindleTemperature);
                SensorSystem.Instance.InjectSensorData(tempMotorSensorId, motorTemperature);

                var vibSensor = SensorSystem.Instance.GetSensor(vibrationSensorId) as VibrationSensor;
                if (vibSensor != null)
                {
                    vibSensor.SetExternalVector(vibration);
                }

                for (int i = 0; i < 3; i++)
                {
                    SensorSystem.Instance.InjectSensorData(loadSensorIds[i], axisLoads[i]);
                }

                SensorSystem.Instance.InjectSensorData(acousticSensorId, soundLevel);
            }

            // Log data if DataLogger is available
            if (DataLogger.Instance != null)
            {
                DataLogger.Instance.LogMachineState(
                    machineId,
                    currentPosition,
                    currentFeedRate,
                    spindleRPM,
                    status.ToString()
                );
            }
        }

        /// <summary>
        /// Update machine state from Flask/TinyG data
        /// </summary>
        public void UpdateFromState(MachineStateData state)
        {
            targetPosition = new Vector3(state.posX, state.posY, state.posZ);
            currentFeedRate = state.feedRate;
            spindleRPM = state.spindleRPM;
            spindleOn = state.spindleOn;
            isHomed = state.isHomed;

            var newStatus = (MachineStatus)state.status;
            if (newStatus != status)
            {
                status = newStatus;
                OnStatusChanged?.Invoke(status);
            }
        }

        /// <summary>
        /// Set target position directly (mm)
        /// </summary>
        public void SetTargetPosition(float x, float y, float z)
        {
            targetPosition = ClampToWorkEnvelope(new Vector3(x, y, z));
        }

        /// <summary>
        /// Set spindle speed
        /// </summary>
        public void SetSpindleSpeed(float rpm)
        {
            spindleRPM = Mathf.Clamp(rpm, 0, 10000);
            spindleOn = rpm > 0;
            OnSpindleChanged?.Invoke(spindleRPM);
        }

        private void UpdateAxisPositions()
        {
            // Smooth interpolation to target
            currentPosition = Vector3.SmoothDamp(
                currentPosition,
                targetPosition,
                ref positionVelocity,
                positionSmoothTime
            );

            // Convert mm to Unity units (1 unit = 1 meter, so divide by 1000)
            float scale = 0.001f;

            // Apply to axis transforms
            if (xAxisCarriage != null)
            {
                var pos = xAxisCarriage.localPosition;
                pos.x = currentPosition.x * scale;
                xAxisCarriage.localPosition = pos;
            }

            if (yAxisTable != null)
            {
                var pos = yAxisTable.localPosition;
                pos.z = currentPosition.y * scale; // Y axis moves table in Z direction
                yAxisTable.localPosition = pos;
            }

            if (zAxisSpindle != null)
            {
                var pos = zAxisSpindle.localPosition;
                pos.y = currentPosition.z * scale; // Z axis moves spindle up/down
                zAxisSpindle.localPosition = pos;
            }

            OnPositionChanged?.Invoke(currentPosition);
        }

        private void UpdateSpindleRotation()
        {
            if (spindleMotor == null || !spindleOn) return;

            // Rotate spindle based on RPM
            float degreesPerSecond = (spindleRPM / 60f) * 360f;
            spindleAngle += degreesPerSecond * Time.deltaTime;
            spindleAngle %= 360f;

            spindleMotor.localRotation = Quaternion.Euler(0, spindleAngle, 0);
        }

        private Vector3 ClampToWorkEnvelope(Vector3 pos)
        {
            return new Vector3(
                Mathf.Clamp(pos.x, workEnvelopeMin.x, workEnvelopeMax.x),
                Mathf.Clamp(pos.y, workEnvelopeMin.y, workEnvelopeMax.y),
                Mathf.Clamp(pos.z, workEnvelopeMin.z, workEnvelopeMax.z)
            );
        }

        /// <summary>
        /// Create visual representation of this CNC
        /// </summary>
        public static GameObject CreateVisual(Transform parent = null)
        {
            var cnc = new GameObject("BantamCNC");
            if (parent != null) cnc.transform.SetParent(parent);

            // Machine base/enclosure (dark gray)
            var baseObj = CreatePrimitive(cnc.transform, "Base", PrimitiveType.Cube,
                new Vector3(0, 0.075f, 0), new Vector3(0.35f, 0.15f, 0.30f),
                new Color(0.15f, 0.15f, 0.18f));

            // Work table (aluminum)
            var table = CreatePrimitive(cnc.transform, "YAxis", PrimitiveType.Cube,
                new Vector3(0, 0.155f, 0), new Vector3(0.20f, 0.01f, 0.15f),
                new Color(0.75f, 0.75f, 0.78f));

            // Spoilboard (tan)
            var spoilboard = CreatePrimitive(table.transform, "Spoilboard", PrimitiveType.Cube,
                new Vector3(0, 0.006f, 0), new Vector3(0.14f, 0.005f, 0.10f),
                new Color(0.85f, 0.75f, 0.55f));

            // Gantry uprights
            var leftUpright = CreatePrimitive(cnc.transform, "LeftUpright", PrimitiveType.Cube,
                new Vector3(-0.16f, 0.22f, -0.08f), new Vector3(0.02f, 0.14f, 0.02f),
                new Color(0.2f, 0.2f, 0.22f));

            var rightUpright = CreatePrimitive(cnc.transform, "RightUpright", PrimitiveType.Cube,
                new Vector3(0.16f, 0.22f, -0.08f), new Vector3(0.02f, 0.14f, 0.02f),
                new Color(0.2f, 0.2f, 0.22f));

            // X-axis gantry beam
            var xAxis = CreatePrimitive(cnc.transform, "XAxis", PrimitiveType.Cube,
                new Vector3(0, 0.28f, -0.08f), new Vector3(0.30f, 0.025f, 0.025f),
                new Color(0.25f, 0.25f, 0.28f));

            // Z-axis carriage
            var zAxis = CreatePrimitive(xAxis.transform, "ZAxis", PrimitiveType.Cube,
                new Vector3(0, -0.02f, 0.03f), new Vector3(0.04f, 0.08f, 0.04f),
                new Color(0.3f, 0.3f, 0.33f));

            // Spindle (silver)
            var spindle = CreatePrimitive(zAxis.transform, "Spindle", PrimitiveType.Cylinder,
                new Vector3(0, -0.06f, 0), new Vector3(0.025f, 0.04f, 0.025f),
                new Color(0.7f, 0.7f, 0.73f));

            // Tool holder (brass colored)
            var toolHolder = CreatePrimitive(spindle.transform, "ToolHolder", PrimitiveType.Cylinder,
                new Vector3(0, -0.045f, 0), new Vector3(0.015f, 0.015f, 0.015f),
                new Color(0.85f, 0.75f, 0.4f));

            // Add controller component
            var controller = cnc.AddComponent<BantamCNCController>();
            controller.xAxisCarriage = xAxis.transform;
            controller.yAxisTable = table.transform;
            controller.zAxisSpindle = zAxis.transform;
            controller.spindleMotor = spindle.transform;

            return cnc;
        }

        /// <summary>
        /// Create visual representation from actual STL model file
        /// </summary>
        public static GameObject CreateVisualFromSTL(Transform parent = null)
        {
            var cnc = new GameObject("BantamCNC");
            if (parent != null) cnc.transform.SetParent(parent);

            // Path to STL file
            string stlPath = Path.Combine(Application.streamingAssetsPath, "URDF", "bantam", "bantam_cnc.stl");

            if (File.Exists(stlPath))
            {
                // Load the actual STL mesh
                var mesh = STLMeshLoader.LoadMesh(stlPath);
                if (mesh != null)
                {
                    var meshHolder = new GameObject("CNC_Model");
                    meshHolder.transform.SetParent(cnc.transform);
                    meshHolder.transform.localPosition = Vector3.zero;
                    // STL is in mm, Unity uses meters - scale down
                    meshHolder.transform.localScale = new Vector3(0.001f, 0.001f, 0.001f);
                    // STLMeshLoader already handles coordinate conversion, no rotation needed
                    meshHolder.transform.localRotation = Quaternion.identity;

                    var meshFilter = meshHolder.AddComponent<MeshFilter>();
                    meshFilter.mesh = mesh;

                    var meshRenderer = meshHolder.AddComponent<MeshRenderer>();
                    var mat = new Material(Shader.Find("Standard"));
                    mat.color = new Color(0.2f, 0.2f, 0.22f); // Dark gray Bantam color
                    mat.SetFloat("_Metallic", 0.6f);
                    mat.SetFloat("_Glossiness", 0.4f);
                    meshRenderer.material = mat;

                    Debug.Log("[BantamCNC] Loaded STL model successfully");
                }
                else
                {
                    Debug.LogError("[BantamCNC] Failed to load STL mesh");
                    CreatePlaceholderVisuals(cnc.transform);
                }
            }
            else
            {
                Debug.LogWarning($"[BantamCNC] STL file not found at: {stlPath}, using placeholder");
                CreatePlaceholderVisuals(cnc.transform);
            }

            // Create axis transform placeholders for animation (invisible)
            var xAxis = new GameObject("XAxis");
            xAxis.transform.SetParent(cnc.transform);
            xAxis.transform.localPosition = new Vector3(0, 0.28f, -0.08f);

            var yAxis = new GameObject("YAxis");
            yAxis.transform.SetParent(cnc.transform);
            yAxis.transform.localPosition = new Vector3(0, 0.155f, 0);

            var zAxis = new GameObject("ZAxis");
            zAxis.transform.SetParent(xAxis.transform);
            zAxis.transform.localPosition = Vector3.zero;

            var spindle = new GameObject("Spindle");
            spindle.transform.SetParent(zAxis.transform);
            spindle.transform.localPosition = new Vector3(0, -0.06f, 0);

            // Add controller component
            var controller = cnc.AddComponent<BantamCNCController>();
            controller.xAxisCarriage = xAxis.transform;
            controller.yAxisTable = yAxis.transform;
            controller.zAxisSpindle = zAxis.transform;
            controller.spindleMotor = spindle.transform;

            return cnc;
        }

        private static void CreatePlaceholderVisuals(Transform parent)
        {
            // Fallback simple box representation
            var placeholder = GameObject.CreatePrimitive(PrimitiveType.Cube);
            placeholder.name = "Placeholder";
            placeholder.transform.SetParent(parent);
            placeholder.transform.localPosition = new Vector3(0, 0.1f, 0);
            placeholder.transform.localScale = new Vector3(0.35f, 0.2f, 0.30f);

            var mat = new Material(Shader.Find("Standard"));
            mat.color = new Color(0.15f, 0.15f, 0.18f);
            placeholder.GetComponent<Renderer>().material = mat;

            var collider = placeholder.GetComponent<Collider>();
            if (collider != null) UnityEngine.Object.DestroyImmediate(collider);
        }

        private static GameObject CreatePrimitive(Transform parent, string name, PrimitiveType type,
            Vector3 localPos, Vector3 localScale, Color color)
        {
            var obj = GameObject.CreatePrimitive(type);
            obj.name = name;
            obj.transform.SetParent(parent);
            obj.transform.localPosition = localPos;
            obj.transform.localScale = localScale;

            var mat = new Material(Shader.Find("Standard"));
            mat.color = color;
            mat.SetFloat("_Metallic", 0.6f);
            mat.SetFloat("_Glossiness", 0.5f);
            obj.GetComponent<Renderer>().material = mat;

            // Remove collider for visual-only objects
            var collider = obj.GetComponent<Collider>();
            if (collider != null) UnityEngine.Object.DestroyImmediate(collider);

            return obj;
        }

        // Properties
        public Vector3 Position => currentPosition;
        public Vector3 Target => targetPosition;
        public float FeedRate => currentFeedRate;
        public float SpindleSpeed => spindleRPM;
        public bool IsSpindleOn => spindleOn;
        public bool IsHomed => isHomed;
        public MachineStatus Status => status;

        // Sensor Properties
        public float SpindleTemperature => spindleTemperature;
        public float MotorTemperature => motorTemperature;
        public Vector3 Vibration => vibration;
        public float[] AxisLoads => (float[])axisLoads.Clone();
        public float PowerConsumption => powerConsumption;
        public float SoundLevel => soundLevel;

        /// <summary>
        /// Get all sensor readings as a dictionary
        /// </summary>
        public Dictionary<string, float> GetSensorReadings()
        {
            return new Dictionary<string, float>
            {
                { "spindle_temperature", spindleTemperature },
                { "motor_temperature", motorTemperature },
                { "vibration_x", vibration.x },
                { "vibration_y", vibration.y },
                { "vibration_z", vibration.z },
                { "vibration_magnitude", vibration.magnitude },
                { "load_x", axisLoads[0] },
                { "load_y", axisLoads[1] },
                { "load_z", axisLoads[2] },
                { "power_consumption", powerConsumption },
                { "sound_level", soundLevel }
            };
        }
    }

    /// <summary>
    /// Machine state data from Flask backend
    /// </summary>
    [Serializable]
    public class MachineStateData
    {
        public float posX;
        public float posY;
        public float posZ;
        public float feedRate;
        public float spindleRPM;
        public bool spindleOn;
        public bool isHomed;
        public int status;
        public int currentLine;
        public string programName;
    }
}
