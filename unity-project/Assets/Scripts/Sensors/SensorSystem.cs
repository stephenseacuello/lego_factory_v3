using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Sensors
{
    /// <summary>
    /// Comprehensive sensor system for CNC SCADA Digital Twin.
    /// Supports temperature, vibration, current, acoustic, and position sensors.
    /// </summary>
    public class SensorSystem : MonoBehaviour
    {
        [Header("System Configuration")]
        public string systemId = "sensor-system-001";
        public float updateRate = 10f; // Hz
        public bool enableDataLogging = true;

        [Header("Sensor Arrays")]
        public List<TemperatureSensor> temperatureSensors = new List<TemperatureSensor>();
        public List<VibrationSensor> vibrationSensors = new List<VibrationSensor>();
        public List<CurrentSensor> currentSensors = new List<CurrentSensor>();
        public List<AcousticSensor> acousticSensors = new List<AcousticSensor>();
        public List<ProximitySensor> proximitySensors = new List<ProximitySensor>();
        public List<ForceTorqueSensor> forceTorqueSensors = new List<ForceTorqueSensor>();

        // Events
        public event Action<SensorReading> OnSensorReading;
        public event Action<SensorAlert> OnSensorAlert;
        public event Action<SensorSystemStatus> OnSystemStatusChanged;

        // Internal state
        private float lastUpdateTime;
        private SensorSystemStatus currentStatus = SensorSystemStatus.Initializing;
        private Dictionary<string, SensorBase> allSensors = new Dictionary<string, SensorBase>();

        // Singleton
        public static SensorSystem Instance { get; private set; }

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
            }
        }

        private void Start()
        {
            InitializeSensors();
            SetStatus(SensorSystemStatus.Running);
        }

        private void Update()
        {
            if (Time.time - lastUpdateTime >= 1f / updateRate)
            {
                UpdateAllSensors();
                lastUpdateTime = Time.time;
            }
        }

        /// <summary>
        /// Initialize all configured sensors
        /// </summary>
        private void InitializeSensors()
        {
            allSensors.Clear();

            foreach (var sensor in temperatureSensors)
            {
                sensor.Initialize();
                allSensors[sensor.sensorId] = sensor;
            }

            foreach (var sensor in vibrationSensors)
            {
                sensor.Initialize();
                allSensors[sensor.sensorId] = sensor;
            }

            foreach (var sensor in currentSensors)
            {
                sensor.Initialize();
                allSensors[sensor.sensorId] = sensor;
            }

            foreach (var sensor in acousticSensors)
            {
                sensor.Initialize();
                allSensors[sensor.sensorId] = sensor;
            }

            foreach (var sensor in proximitySensors)
            {
                sensor.Initialize();
                allSensors[sensor.sensorId] = sensor;
            }

            foreach (var sensor in forceTorqueSensors)
            {
                sensor.Initialize();
                allSensors[sensor.sensorId] = sensor;
            }

            Debug.Log($"[SensorSystem] Initialized {allSensors.Count} sensors");
        }

        /// <summary>
        /// Update all sensor readings
        /// </summary>
        private void UpdateAllSensors()
        {
            foreach (var kvp in allSensors)
            {
                var sensor = kvp.Value;
                sensor.Update();

                var reading = sensor.GetReading();
                OnSensorReading?.Invoke(reading);

                // Check for alerts
                if (sensor.IsInAlertState())
                {
                    var alert = sensor.GetAlert();
                    OnSensorAlert?.Invoke(alert);
                }
            }
        }

        /// <summary>
        /// Get a specific sensor by ID
        /// </summary>
        public SensorBase GetSensor(string sensorId)
        {
            return allSensors.TryGetValue(sensorId, out var sensor) ? sensor : null;
        }

        /// <summary>
        /// Get all readings as a dictionary
        /// </summary>
        public Dictionary<string, SensorReading> GetAllReadings()
        {
            var readings = new Dictionary<string, SensorReading>();
            foreach (var kvp in allSensors)
            {
                readings[kvp.Key] = kvp.Value.GetReading();
            }
            return readings;
        }

        /// <summary>
        /// Inject sensor data from external source (Flask backend, MTConnect, etc.)
        /// </summary>
        public void InjectSensorData(string sensorId, float value)
        {
            if (allSensors.TryGetValue(sensorId, out var sensor))
            {
                sensor.SetExternalValue(value);
            }
        }

        /// <summary>
        /// Inject bulk sensor data from JSON
        /// </summary>
        public void InjectBulkData(SensorBulkData data)
        {
            if (data.temperatures != null)
            {
                foreach (var kvp in data.temperatures)
                {
                    InjectSensorData(kvp.Key, kvp.Value);
                }
            }

            if (data.vibrations != null)
            {
                foreach (var kvp in data.vibrations)
                {
                    if (allSensors.TryGetValue(kvp.Key, out var sensor) && sensor is VibrationSensor vib)
                    {
                        vib.SetExternalVector(kvp.Value);
                    }
                }
            }

            if (data.currents != null)
            {
                foreach (var kvp in data.currents)
                {
                    InjectSensorData(kvp.Key, kvp.Value);
                }
            }
        }

        private void SetStatus(SensorSystemStatus status)
        {
            if (currentStatus != status)
            {
                currentStatus = status;
                OnSystemStatusChanged?.Invoke(status);
                Debug.Log($"[SensorSystem] Status changed to: {status}");
            }
        }

        public SensorSystemStatus Status => currentStatus;
        public int ActiveSensorCount => allSensors.Count;
    }

    // =========================================================================
    // Sensor Base Class
    // =========================================================================

    [Serializable]
    public abstract class SensorBase
    {
        public string sensorId;
        public string sensorName;
        public SensorType sensorType;
        public string location;
        public string attachedTo; // Machine or robot ID

        [Header("Thresholds")]
        public float warningThreshold;
        public float criticalThreshold;

        [Header("Calibration")]
        public float offset = 0f;
        public float scaleFactor = 1f;

        // State
        protected float currentValue;
        protected float externalValue;
        protected bool useExternalData = false;
        protected SensorStatus status = SensorStatus.Unknown;
        protected DateTime lastUpdate;

        public virtual void Initialize()
        {
            status = SensorStatus.Normal;
            lastUpdate = DateTime.UtcNow;
        }

        public virtual void Update()
        {
            if (useExternalData)
            {
                currentValue = (externalValue + offset) * scaleFactor;
            }
            else
            {
                // Simulate if no external data
                SimulateValue();
            }

            UpdateStatus();
            lastUpdate = DateTime.UtcNow;
        }

        protected virtual void SimulateValue()
        {
            // Override in subclasses for realistic simulation
        }

        protected virtual void UpdateStatus()
        {
            float absValue = Mathf.Abs(currentValue);
            if (absValue >= criticalThreshold)
            {
                status = SensorStatus.Critical;
            }
            else if (absValue >= warningThreshold)
            {
                status = SensorStatus.Warning;
            }
            else
            {
                status = SensorStatus.Normal;
            }
        }

        public void SetExternalValue(float value)
        {
            externalValue = value;
            useExternalData = true;
        }

        public virtual SensorReading GetReading()
        {
            return new SensorReading
            {
                sensorId = sensorId,
                sensorType = sensorType,
                value = currentValue,
                status = status,
                timestamp = lastUpdate,
                unit = GetUnit()
            };
        }

        public bool IsInAlertState()
        {
            return status == SensorStatus.Warning || status == SensorStatus.Critical;
        }

        public SensorAlert GetAlert()
        {
            return new SensorAlert
            {
                sensorId = sensorId,
                sensorName = sensorName,
                alertLevel = status == SensorStatus.Critical ? AlertLevel.Critical : AlertLevel.Warning,
                message = $"{sensorName}: {currentValue:F2} {GetUnit()} exceeds threshold",
                value = currentValue,
                threshold = status == SensorStatus.Critical ? criticalThreshold : warningThreshold,
                timestamp = DateTime.UtcNow
            };
        }

        protected abstract string GetUnit();
    }

    // =========================================================================
    // Specific Sensor Types
    // =========================================================================

    [Serializable]
    public class TemperatureSensor : SensorBase
    {
        [Header("Temperature Settings")]
        public float ambientTemp = 22f;
        public float maxOperatingTemp = 80f;
        public TemperatureUnit unit = TemperatureUnit.Celsius;

        public TemperatureSensor()
        {
            sensorType = SensorType.Temperature;
            warningThreshold = 60f;
            criticalThreshold = 75f;
        }

        protected override void SimulateValue()
        {
            // Simulate gradual heating during operation
            float noise = UnityEngine.Random.Range(-0.5f, 0.5f);
            currentValue = ambientTemp + noise;
        }

        protected override string GetUnit()
        {
            return unit == TemperatureUnit.Celsius ? "°C" : "°F";
        }
    }

    [Serializable]
    public class VibrationSensor : SensorBase
    {
        [Header("Vibration Settings")]
        public float sampleRate = 1000f; // Hz
        public float sensitivityMvPerG = 100f;
        public VibrationAxis measureAxis = VibrationAxis.XYZ;

        private Vector3 vibrationVector;

        public VibrationSensor()
        {
            sensorType = SensorType.Vibration;
            warningThreshold = 2.5f; // mm/s RMS
            criticalThreshold = 7.1f; // ISO 10816 limits
        }

        protected override void SimulateValue()
        {
            // Simulate typical CNC vibration
            vibrationVector = new Vector3(
                UnityEngine.Random.Range(-0.5f, 0.5f),
                UnityEngine.Random.Range(-0.3f, 0.3f),
                UnityEngine.Random.Range(-0.4f, 0.4f)
            );
            currentValue = vibrationVector.magnitude;
        }

        public void SetExternalVector(Vector3 value)
        {
            vibrationVector = value;
            currentValue = value.magnitude;
            useExternalData = true;
        }

        public Vector3 VibrationVector => vibrationVector;

        protected override string GetUnit()
        {
            return "mm/s";
        }

        public override SensorReading GetReading()
        {
            var reading = base.GetReading();
            reading.vectorValue = vibrationVector;
            return reading;
        }
    }

    [Serializable]
    public class CurrentSensor : SensorBase
    {
        [Header("Current Settings")]
        public float nominalCurrent = 5f; // Amps
        public float maxCurrent = 15f;
        public CurrentSensorType currentType = CurrentSensorType.AC;

        public CurrentSensor()
        {
            sensorType = SensorType.Current;
            warningThreshold = 10f;
            criticalThreshold = 14f;
        }

        protected override void SimulateValue()
        {
            // Simulate motor current with some variation
            float noise = UnityEngine.Random.Range(-0.2f, 0.2f);
            currentValue = nominalCurrent + noise;
        }

        protected override string GetUnit()
        {
            return "A";
        }
    }

    [Serializable]
    public class AcousticSensor : SensorBase
    {
        [Header("Acoustic Settings")]
        public float sensitivityDbV = -42f;
        public float frequencyResponseMin = 20f;  // Hz
        public float frequencyResponseMax = 20000f; // Hz

        private float[] frequencySpectrum;

        public AcousticSensor()
        {
            sensorType = SensorType.Acoustic;
            warningThreshold = 85f;  // dB - OSHA warning
            criticalThreshold = 100f; // dB - hearing damage
            frequencySpectrum = new float[256];
        }

        protected override void SimulateValue()
        {
            // Simulate typical machining noise
            currentValue = 65f + UnityEngine.Random.Range(-5f, 15f);
        }

        public float[] GetFrequencySpectrum()
        {
            return frequencySpectrum;
        }

        protected override string GetUnit()
        {
            return "dB";
        }
    }

    [Serializable]
    public class ProximitySensor : SensorBase
    {
        [Header("Proximity Settings")]
        public float sensingRange = 10f; // mm
        public ProximitySensorType proximityType = ProximitySensorType.Inductive;

        private bool objectDetected;

        public ProximitySensor()
        {
            sensorType = SensorType.Proximity;
            warningThreshold = sensingRange * 0.8f;
            criticalThreshold = sensingRange * 0.9f;
        }

        protected override void SimulateValue()
        {
            // Simulate distance to nearest object
            currentValue = sensingRange * 0.5f + UnityEngine.Random.Range(-1f, 1f);
            objectDetected = currentValue < sensingRange;
        }

        public bool IsObjectDetected => objectDetected;

        protected override string GetUnit()
        {
            return "mm";
        }
    }

    [Serializable]
    public class ForceTorqueSensor : SensorBase
    {
        [Header("Force/Torque Settings")]
        public float maxForce = 100f;  // N
        public float maxTorque = 10f;  // Nm
        public int numAxes = 6;        // 6-axis F/T sensor

        private Vector3 force;
        private Vector3 torque;

        public ForceTorqueSensor()
        {
            sensorType = SensorType.ForceTorque;
            warningThreshold = 80f;
            criticalThreshold = 95f;
        }

        protected override void SimulateValue()
        {
            force = new Vector3(
                UnityEngine.Random.Range(-5f, 5f),
                UnityEngine.Random.Range(-10f, 10f),
                UnityEngine.Random.Range(-5f, 5f)
            );
            torque = new Vector3(
                UnityEngine.Random.Range(-0.5f, 0.5f),
                UnityEngine.Random.Range(-0.5f, 0.5f),
                UnityEngine.Random.Range(-1f, 1f)
            );
            currentValue = force.magnitude;
        }

        public Vector3 Force => force;
        public Vector3 Torque => torque;

        protected override string GetUnit()
        {
            return "N";
        }

        public override SensorReading GetReading()
        {
            var reading = base.GetReading();
            reading.vectorValue = force;
            reading.additionalData = new Dictionary<string, object>
            {
                { "torque", torque }
            };
            return reading;
        }
    }

    // =========================================================================
    // Enums and Data Classes
    // =========================================================================

    public enum SensorType
    {
        Temperature,
        Vibration,
        Current,
        Acoustic,
        Proximity,
        ForceTorque,
        Position,
        Pressure,
        Humidity,
        Optical
    }

    public enum SensorStatus
    {
        Unknown,
        Normal,
        Warning,
        Critical,
        Offline,
        Calibrating
    }

    public enum SensorSystemStatus
    {
        Initializing,
        Running,
        Warning,
        Error,
        Offline
    }

    public enum AlertLevel
    {
        Info,
        Warning,
        Critical,
        Emergency
    }

    public enum TemperatureUnit
    {
        Celsius,
        Fahrenheit
    }

    public enum VibrationAxis
    {
        X,
        Y,
        Z,
        XYZ
    }

    public enum CurrentSensorType
    {
        AC,
        DC,
        Both
    }

    public enum ProximitySensorType
    {
        Inductive,
        Capacitive,
        Photoelectric,
        Ultrasonic
    }

    [Serializable]
    public class SensorReading
    {
        public string sensorId;
        public SensorType sensorType;
        public float value;
        public Vector3 vectorValue;
        public SensorStatus status;
        public DateTime timestamp;
        public string unit;
        public Dictionary<string, object> additionalData;
    }

    [Serializable]
    public class SensorAlert
    {
        public string sensorId;
        public string sensorName;
        public AlertLevel alertLevel;
        public string message;
        public float value;
        public float threshold;
        public DateTime timestamp;
    }

    [Serializable]
    public class SensorBulkData
    {
        public Dictionary<string, float> temperatures;
        public Dictionary<string, Vector3> vibrations;
        public Dictionary<string, float> currents;
        public Dictionary<string, float> acoustic;
        public long timestamp;
    }
}
