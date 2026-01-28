using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using CNC_SCADA.DigitalTwin.ROS2;

namespace CNC_SCADA.DigitalTwin.Sensors
{
    /// <summary>
    /// Advanced sensor simulation system for Digital Twin
    /// Simulates LiDAR, IMU, Force/Torque, Proximity, and Encoder sensors
    /// Publishes to ROS2 topics for integration with robot controllers
    /// </summary>
    public class AdvancedSensorSimulation : MonoBehaviour
    {
        public static AdvancedSensorSimulation Instance { get; private set; }

        [Header("Sensor Configuration")]
        [SerializeField] private bool enableLiDAR = true;
        [SerializeField] private bool enableIMU = true;
        [SerializeField] private bool enableForceTorque = true;
        [SerializeField] private bool enableProximity = true;
        [SerializeField] private bool enableEncoders = true;

        [Header("ROS2 Integration")]
        [SerializeField] private bool publishToROS = true;
        [SerializeField] private string sensorNamespace = "/sensors";

        // Events
        public event Action<LiDARScanData> OnLiDARScan;
        public event Action<IMUData> OnIMUUpdate;
        public event Action<ForceTorqueData> OnForceTorqueUpdate;
        public event Action<ProximitySensorData> OnProximityUpdate;
        public event Action<EncoderData> OnEncoderUpdate;

        // Sensor collections
        private List<LiDARSensor> lidarSensors = new List<LiDARSensor>();
        private List<IMUSensor> imuSensors = new List<IMUSensor>();
        private List<ForceTorqueSensor> forceTorqueSensors = new List<ForceTorqueSensor>();
        private List<ProximitySensor> proximitySensors = new List<ProximitySensor>();
        private List<EncoderSensor> encoderSensors = new List<EncoderSensor>();

        private ROS2UnityBridge rosBridge;

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
            rosBridge = ROS2UnityBridge.Instance;
            InitializeDemoSensors();
        }

        private void FixedUpdate()
        {
            if (enableLiDAR) UpdateLiDARSensors();
            if (enableIMU) UpdateIMUSensors();
            if (enableForceTorque) UpdateForceTorqueSensors();
            if (enableProximity) UpdateProximitySensors();
            if (enableEncoders) UpdateEncoderSensors();
        }

        private void InitializeDemoSensors()
        {
            // Demo LiDAR sensor
            CreateLiDARSensor(new LiDARConfig
            {
                SensorId = "lidar_main",
                FrameId = "lidar_link",
                Position = new Vector3(0, 1.5f, 0),
                AngleMin = -Mathf.PI,
                AngleMax = Mathf.PI,
                AngleIncrement = Mathf.PI / 180f, // 1 degree
                RangeMin = 0.1f,
                RangeMax = 30f,
                ScanRateHz = 10f
            });

            // Demo IMU sensors
            CreateIMUSensor(new IMUConfig
            {
                SensorId = "imu_base",
                FrameId = "base_link",
                Position = Vector3.zero,
                UpdateRateHz = 100f,
                AccelerometerNoise = 0.01f,
                GyroscopeNoise = 0.001f,
                MagnetometerNoise = 0.1f
            });

            // Force/Torque sensor at end effector
            CreateForceTorqueSensor(new ForceTorqueConfig
            {
                SensorId = "ft_wrist",
                FrameId = "wrist_3_link",
                Position = Vector3.zero,
                UpdateRateHz = 500f,
                ForceRange = new Vector3(500, 500, 1000),
                TorqueRange = new Vector3(50, 50, 50),
                ForceNoise = 0.5f,
                TorqueNoise = 0.05f
            });

            // Proximity sensors
            CreateProximitySensor(new ProximitySensorConfig
            {
                SensorId = "prox_front",
                FrameId = "front_sensor",
                Position = new Vector3(0.5f, 0.1f, 0),
                Direction = Vector3.right,
                MaxRange = 0.5f,
                UpdateRateHz = 50f,
                SensorType = ProximitySensorType.Infrared
            });

            CreateProximitySensor(new ProximitySensorConfig
            {
                SensorId = "prox_back",
                FrameId = "back_sensor",
                Position = new Vector3(-0.5f, 0.1f, 0),
                Direction = Vector3.left,
                MaxRange = 0.5f,
                UpdateRateHz = 50f,
                SensorType = ProximitySensorType.Ultrasonic
            });

            // Encoder sensors for each joint
            for (int i = 1; i <= 6; i++)
            {
                CreateEncoderSensor(new EncoderConfig
                {
                    SensorId = $"encoder_joint_{i}",
                    JointName = $"joint_{i}",
                    Resolution = 4096, // ticks per revolution
                    UpdateRateHz = 1000f,
                    IndexPulse = true
                });
            }

            Debug.Log($"[SensorSim] Initialized {lidarSensors.Count} LiDAR, {imuSensors.Count} IMU, " +
                     $"{forceTorqueSensors.Count} F/T, {proximitySensors.Count} Proximity, {encoderSensors.Count} Encoder sensors");
        }

        #region LiDAR Simulation

        public LiDARSensor CreateLiDARSensor(LiDARConfig config)
        {
            var sensor = new LiDARSensor
            {
                Config = config,
                LastScanTime = 0f,
                CurrentScan = new LiDARScanData
                {
                    SensorId = config.SensorId,
                    Ranges = new float[Mathf.CeilToInt((config.AngleMax - config.AngleMin) / config.AngleIncrement)],
                    Intensities = new float[Mathf.CeilToInt((config.AngleMax - config.AngleMin) / config.AngleIncrement)]
                }
            };

            lidarSensors.Add(sensor);
            return sensor;
        }

        private void UpdateLiDARSensors()
        {
            foreach (var sensor in lidarSensors)
            {
                float scanInterval = 1f / sensor.Config.ScanRateHz;
                if (Time.time - sensor.LastScanTime < scanInterval) continue;

                sensor.LastScanTime = Time.time;
                PerformLiDARScan(sensor);
            }
        }

        private void PerformLiDARScan(LiDARSensor sensor)
        {
            var config = sensor.Config;
            var scan = sensor.CurrentScan;
            scan.Timestamp = DateTime.UtcNow;

            Vector3 origin = transform.TransformPoint(config.Position);
            int numRays = scan.Ranges.Length;

            for (int i = 0; i < numRays; i++)
            {
                float angle = config.AngleMin + i * config.AngleIncrement;
                Vector3 direction = Quaternion.Euler(0, angle * Mathf.Rad2Deg, 0) * Vector3.forward;
                direction = transform.TransformDirection(direction);

                RaycastHit hit;
                if (Physics.Raycast(origin, direction, out hit, config.RangeMax))
                {
                    scan.Ranges[i] = hit.distance;
                    scan.Intensities[i] = CalculateLiDARIntensity(hit);
                }
                else
                {
                    scan.Ranges[i] = float.PositiveInfinity;
                    scan.Intensities[i] = 0f;
                }

                // Add noise
                if (config.RangeNoise > 0 && scan.Ranges[i] < float.PositiveInfinity)
                {
                    scan.Ranges[i] += UnityEngine.Random.Range(-config.RangeNoise, config.RangeNoise);
                }
            }

            OnLiDARScan?.Invoke(scan);

            // Publish to ROS2
            if (publishToROS && rosBridge != null && rosBridge.IsConnected)
            {
                var rosMsg = new LaserScanMessage
                {
                    Header = new HeaderMessage
                    {
                        FrameId = config.FrameId,
                        Stamp = new ROSTime
                        {
                            Sec = (int)(Time.time),
                            Nanosec = (uint)((Time.time % 1) * 1e9)
                        }
                    },
                    AngleMin = config.AngleMin,
                    AngleMax = config.AngleMax,
                    AngleIncrement = config.AngleIncrement,
                    RangeMin = config.RangeMin,
                    RangeMax = config.RangeMax,
                    Ranges = scan.Ranges,
                    Intensities = scan.Intensities
                };

                rosBridge.PublishLaserScan($"{sensorNamespace}/{config.SensorId}/scan", rosMsg);
            }
        }

        private float CalculateLiDARIntensity(RaycastHit hit)
        {
            // Simple intensity based on angle and material
            float angleIntensity = Mathf.Abs(Vector3.Dot(hit.normal, -hit.point.normalized));
            float distanceAttenuation = 1f - (hit.distance / 30f);
            return Mathf.Clamp01(angleIntensity * distanceAttenuation * 255f);
        }

        #endregion

        #region IMU Simulation

        public IMUSensor CreateIMUSensor(IMUConfig config)
        {
            var sensor = new IMUSensor
            {
                Config = config,
                LastUpdateTime = 0f,
                PreviousVelocity = Vector3.zero,
                CurrentData = new IMUData
                {
                    SensorId = config.SensorId
                }
            };

            imuSensors.Add(sensor);
            return sensor;
        }

        private void UpdateIMUSensors()
        {
            foreach (var sensor in imuSensors)
            {
                float updateInterval = 1f / sensor.Config.UpdateRateHz;
                if (Time.fixedTime - sensor.LastUpdateTime < updateInterval) continue;

                sensor.LastUpdateTime = Time.fixedTime;
                CalculateIMUData(sensor);
            }
        }

        private void CalculateIMUData(IMUSensor sensor)
        {
            var config = sensor.Config;
            var data = sensor.CurrentData;
            data.Timestamp = DateTime.UtcNow;

            // Get current transform state
            Vector3 worldPos = transform.TransformPoint(config.Position);
            Quaternion worldRot = transform.rotation;

            // Calculate linear acceleration (derivative of velocity + gravity)
            Vector3 velocity = (worldPos - sensor.PreviousPosition) / Time.fixedDeltaTime;
            Vector3 acceleration = (velocity - sensor.PreviousVelocity) / Time.fixedDeltaTime;

            // Add gravity in local frame
            Vector3 gravityLocal = Quaternion.Inverse(worldRot) * Physics.gravity;
            acceleration = Quaternion.Inverse(worldRot) * acceleration - gravityLocal;

            // Add noise
            data.LinearAcceleration = new Vector3(
                acceleration.x + UnityEngine.Random.Range(-config.AccelerometerNoise, config.AccelerometerNoise),
                acceleration.y + UnityEngine.Random.Range(-config.AccelerometerNoise, config.AccelerometerNoise),
                acceleration.z + UnityEngine.Random.Range(-config.AccelerometerNoise, config.AccelerometerNoise)
            );

            // Angular velocity
            Quaternion deltaRot = worldRot * Quaternion.Inverse(sensor.PreviousRotation);
            deltaRot.ToAngleAxis(out float angle, out Vector3 axis);
            Vector3 angularVelocity = (angle * Mathf.Deg2Rad / Time.fixedDeltaTime) * axis;
            angularVelocity = Quaternion.Inverse(worldRot) * angularVelocity;

            data.AngularVelocity = new Vector3(
                angularVelocity.x + UnityEngine.Random.Range(-config.GyroscopeNoise, config.GyroscopeNoise),
                angularVelocity.y + UnityEngine.Random.Range(-config.GyroscopeNoise, config.GyroscopeNoise),
                angularVelocity.z + UnityEngine.Random.Range(-config.GyroscopeNoise, config.GyroscopeNoise)
            );

            // Orientation
            data.Orientation = worldRot;

            // Magnetometer (simplified - assumes North is +Z)
            Vector3 northLocal = Quaternion.Inverse(worldRot) * Vector3.forward;
            data.MagneticField = new Vector3(
                northLocal.x * 50f + UnityEngine.Random.Range(-config.MagnetometerNoise, config.MagnetometerNoise),
                northLocal.y * 50f + UnityEngine.Random.Range(-config.MagnetometerNoise, config.MagnetometerNoise),
                northLocal.z * 50f + UnityEngine.Random.Range(-config.MagnetometerNoise, config.MagnetometerNoise)
            );

            // Store for next frame
            sensor.PreviousPosition = worldPos;
            sensor.PreviousVelocity = velocity;
            sensor.PreviousRotation = worldRot;

            OnIMUUpdate?.Invoke(data);

            // Publish to ROS2
            if (publishToROS && rosBridge != null && rosBridge.IsConnected)
            {
                // IMU message would be published here
            }
        }

        #endregion

        #region Force/Torque Simulation

        public ForceTorqueSensor CreateForceTorqueSensor(ForceTorqueConfig config)
        {
            var sensor = new ForceTorqueSensor
            {
                Config = config,
                LastUpdateTime = 0f,
                CurrentData = new ForceTorqueData
                {
                    SensorId = config.SensorId
                }
            };

            forceTorqueSensors.Add(sensor);
            return sensor;
        }

        private void UpdateForceTorqueSensors()
        {
            foreach (var sensor in forceTorqueSensors)
            {
                float updateInterval = 1f / sensor.Config.UpdateRateHz;
                if (Time.fixedTime - sensor.LastUpdateTime < updateInterval) continue;

                sensor.LastUpdateTime = Time.fixedTime;
                CalculateForceTorqueData(sensor);
            }
        }

        private void CalculateForceTorqueData(ForceTorqueSensor sensor)
        {
            var config = sensor.Config;
            var data = sensor.CurrentData;
            data.Timestamp = DateTime.UtcNow;

            // Get applied forces from physics (if attached to rigidbody)
            // For simulation, we can use external force inputs or simulated contact
            Vector3 appliedForce = sensor.ExternalForce;
            Vector3 appliedTorque = sensor.ExternalTorque;

            // Add gravity compensation if enabled
            if (config.GravityCompensation && sensor.AttachedRigidbody != null)
            {
                appliedForce -= sensor.AttachedRigidbody.mass * Physics.gravity;
            }

            // Clamp to sensor range
            data.Force = new Vector3(
                Mathf.Clamp(appliedForce.x, -config.ForceRange.x, config.ForceRange.x),
                Mathf.Clamp(appliedForce.y, -config.ForceRange.y, config.ForceRange.y),
                Mathf.Clamp(appliedForce.z, -config.ForceRange.z, config.ForceRange.z)
            );

            data.Torque = new Vector3(
                Mathf.Clamp(appliedTorque.x, -config.TorqueRange.x, config.TorqueRange.x),
                Mathf.Clamp(appliedTorque.y, -config.TorqueRange.y, config.TorqueRange.y),
                Mathf.Clamp(appliedTorque.z, -config.TorqueRange.z, config.TorqueRange.z)
            );

            // Add noise
            data.Force += new Vector3(
                UnityEngine.Random.Range(-config.ForceNoise, config.ForceNoise),
                UnityEngine.Random.Range(-config.ForceNoise, config.ForceNoise),
                UnityEngine.Random.Range(-config.ForceNoise, config.ForceNoise)
            );

            data.Torque += new Vector3(
                UnityEngine.Random.Range(-config.TorqueNoise, config.TorqueNoise),
                UnityEngine.Random.Range(-config.TorqueNoise, config.TorqueNoise),
                UnityEngine.Random.Range(-config.TorqueNoise, config.TorqueNoise)
            );

            // Check overload
            data.IsOverloaded = data.Force.magnitude > config.ForceRange.magnitude * 0.9f ||
                               data.Torque.magnitude > config.TorqueRange.magnitude * 0.9f;

            OnForceTorqueUpdate?.Invoke(data);

            // Publish to ROS2
            if (publishToROS && rosBridge != null && rosBridge.IsConnected)
            {
                var rosMsg = new WrenchMessage
                {
                    Force = ROS2UnityBridge.UnityToROSPosition(data.Force),
                    Torque = ROS2UnityBridge.UnityToROSPosition(data.Torque)
                };

                rosBridge.Publish($"{sensorNamespace}/{config.SensorId}/wrench", rosMsg);
            }
        }

        public void ApplyExternalForce(string sensorId, Vector3 force, Vector3 torque)
        {
            var sensor = forceTorqueSensors.Find(s => s.Config.SensorId == sensorId);
            if (sensor != null)
            {
                sensor.ExternalForce = force;
                sensor.ExternalTorque = torque;
            }
        }

        #endregion

        #region Proximity Sensor Simulation

        public ProximitySensor CreateProximitySensor(ProximitySensorConfig config)
        {
            var sensor = new ProximitySensor
            {
                Config = config,
                LastUpdateTime = 0f,
                CurrentData = new ProximitySensorData
                {
                    SensorId = config.SensorId
                }
            };

            proximitySensors.Add(sensor);
            return sensor;
        }

        private void UpdateProximitySensors()
        {
            foreach (var sensor in proximitySensors)
            {
                float updateInterval = 1f / sensor.Config.UpdateRateHz;
                if (Time.fixedTime - sensor.LastUpdateTime < updateInterval) continue;

                sensor.LastUpdateTime = Time.fixedTime;
                CalculateProximityData(sensor);
            }
        }

        private void CalculateProximityData(ProximitySensor sensor)
        {
            var config = sensor.Config;
            var data = sensor.CurrentData;
            data.Timestamp = DateTime.UtcNow;

            Vector3 origin = transform.TransformPoint(config.Position);
            Vector3 direction = transform.TransformDirection(config.Direction);

            RaycastHit hit;
            if (Physics.Raycast(origin, direction, out hit, config.MaxRange, config.LayerMask))
            {
                data.Distance = hit.distance;
                data.IsTriggered = hit.distance <= config.TriggerDistance;
                data.DetectedObject = hit.collider.gameObject.name;
                data.HitPoint = hit.point;
                data.HitNormal = hit.normal;
            }
            else
            {
                data.Distance = config.MaxRange;
                data.IsTriggered = false;
                data.DetectedObject = null;
                data.HitPoint = origin + direction * config.MaxRange;
                data.HitNormal = Vector3.zero;
            }

            // Apply sensor-specific characteristics
            switch (config.SensorType)
            {
                case ProximitySensorType.Ultrasonic:
                    // Ultrasonic has wider beam angle
                    data.Distance += UnityEngine.Random.Range(-0.01f, 0.01f);
                    break;

                case ProximitySensorType.Infrared:
                    // IR affected by surface reflectivity
                    if (hit.collider != null)
                    {
                        float reflectivity = GetSurfaceReflectivity(hit.collider);
                        if (reflectivity < 0.3f)
                        {
                            data.Distance = config.MaxRange; // Dark surfaces not detected
                        }
                    }
                    break;

                case ProximitySensorType.Inductive:
                    // Only detects metal
                    if (hit.collider != null && !IsMetal(hit.collider))
                    {
                        data.Distance = config.MaxRange;
                        data.IsTriggered = false;
                    }
                    break;

                case ProximitySensorType.Capacitive:
                    // Detects most materials
                    break;

                case ProximitySensorType.Photoelectric:
                    // Check for beam break mode
                    break;
            }

            OnProximityUpdate?.Invoke(data);
        }

        private float GetSurfaceReflectivity(Collider collider)
        {
            var renderer = collider.GetComponent<Renderer>();
            if (renderer != null && renderer.material != null)
            {
                Color color = renderer.material.color;
                return (color.r + color.g + color.b) / 3f;
            }
            return 0.5f;
        }

        private bool IsMetal(Collider collider)
        {
            // Check for metal tag or layer
            return collider.CompareTag("Metal") || collider.gameObject.layer == LayerMask.NameToLayer("Metal");
        }

        #endregion

        #region Encoder Simulation

        public EncoderSensor CreateEncoderSensor(EncoderConfig config)
        {
            var sensor = new EncoderSensor
            {
                Config = config,
                LastUpdateTime = 0f,
                AccumulatedTicks = 0,
                CurrentData = new EncoderData
                {
                    SensorId = config.SensorId,
                    JointName = config.JointName
                }
            };

            encoderSensors.Add(sensor);
            return sensor;
        }

        private void UpdateEncoderSensors()
        {
            foreach (var sensor in encoderSensors)
            {
                float updateInterval = 1f / sensor.Config.UpdateRateHz;
                if (Time.fixedTime - sensor.LastUpdateTime < updateInterval) continue;

                sensor.LastUpdateTime = Time.fixedTime;
                CalculateEncoderData(sensor);
            }
        }

        private void CalculateEncoderData(EncoderSensor sensor)
        {
            var config = sensor.Config;
            var data = sensor.CurrentData;
            data.Timestamp = DateTime.UtcNow;

            // Get joint angle (this would come from actual joint transform)
            float currentAngle = sensor.JointAngle; // radians

            // Convert to encoder ticks
            float ticksPerRadian = config.Resolution / (2f * Mathf.PI);
            int currentTicks = Mathf.RoundToInt(currentAngle * ticksPerRadian);

            // Calculate velocity
            int deltaTicks = currentTicks - sensor.PreviousTicks;
            float deltaTime = Time.fixedDeltaTime;

            data.Position = currentTicks;
            data.Velocity = deltaTicks / deltaTime; // ticks per second
            data.PositionRadians = currentAngle;
            data.VelocityRadians = (currentAngle - sensor.PreviousAngle) / deltaTime;

            // Index pulse detection
            if (config.IndexPulse)
            {
                int previousRevolution = Mathf.FloorToInt(sensor.PreviousAngle / (2f * Mathf.PI));
                int currentRevolution = Mathf.FloorToInt(currentAngle / (2f * Mathf.PI));
                data.IndexPulseTriggered = currentRevolution != previousRevolution;
            }

            // Error flags
            data.HasError = false;
            data.ErrorCode = 0;

            // Check for excessive velocity (possible encoder error)
            if (Mathf.Abs(data.VelocityRadians) > config.MaxVelocity)
            {
                data.HasError = true;
                data.ErrorCode = 1; // Velocity exceeded
            }

            sensor.PreviousTicks = currentTicks;
            sensor.PreviousAngle = currentAngle;
            sensor.AccumulatedTicks += Mathf.Abs(deltaTicks);

            OnEncoderUpdate?.Invoke(data);
        }

        public void SetJointAngle(string sensorId, float angleRadians)
        {
            var sensor = encoderSensors.Find(s => s.Config.SensorId == sensorId);
            if (sensor != null)
            {
                sensor.JointAngle = angleRadians;
            }
        }

        public void SetJointAngles(float[] anglesRadians)
        {
            for (int i = 0; i < Mathf.Min(anglesRadians.Length, encoderSensors.Count); i++)
            {
                encoderSensors[i].JointAngle = anglesRadians[i];
            }
        }

        #endregion

        #region Sensor Statistics

        public SensorStatistics GetStatistics()
        {
            return new SensorStatistics
            {
                LiDARCount = lidarSensors.Count,
                IMUCount = imuSensors.Count,
                ForceTorqueCount = forceTorqueSensors.Count,
                ProximityCount = proximitySensors.Count,
                EncoderCount = encoderSensors.Count,
                TotalSensors = lidarSensors.Count + imuSensors.Count + forceTorqueSensors.Count +
                              proximitySensors.Count + encoderSensors.Count,
                PublishingToROS = publishToROS && rosBridge != null && rosBridge.IsConnected
            };
        }

        #endregion
    }

    #region Sensor Data Classes

    // LiDAR
    [Serializable]
    public class LiDARConfig
    {
        public string SensorId;
        public string FrameId;
        public Vector3 Position;
        public float AngleMin;
        public float AngleMax;
        public float AngleIncrement;
        public float RangeMin;
        public float RangeMax;
        public float ScanRateHz;
        public float RangeNoise;
    }

    [Serializable]
    public class LiDARSensor
    {
        public LiDARConfig Config;
        public float LastScanTime;
        public LiDARScanData CurrentScan;
    }

    [Serializable]
    public class LiDARScanData
    {
        public string SensorId;
        public DateTime Timestamp;
        public float[] Ranges;
        public float[] Intensities;
    }

    // IMU
    [Serializable]
    public class IMUConfig
    {
        public string SensorId;
        public string FrameId;
        public Vector3 Position;
        public float UpdateRateHz;
        public float AccelerometerNoise;
        public float GyroscopeNoise;
        public float MagnetometerNoise;
        public Vector3 AccelerometerBias;
        public Vector3 GyroscopeBias;
    }

    [Serializable]
    public class IMUSensor
    {
        public IMUConfig Config;
        public float LastUpdateTime;
        public Vector3 PreviousPosition;
        public Vector3 PreviousVelocity;
        public Quaternion PreviousRotation;
        public IMUData CurrentData;
    }

    [Serializable]
    public class IMUData
    {
        public string SensorId;
        public DateTime Timestamp;
        public Vector3 LinearAcceleration;
        public Vector3 AngularVelocity;
        public Quaternion Orientation;
        public Vector3 MagneticField;
    }

    // Force/Torque
    [Serializable]
    public class ForceTorqueConfig
    {
        public string SensorId;
        public string FrameId;
        public Vector3 Position;
        public float UpdateRateHz;
        public Vector3 ForceRange;
        public Vector3 TorqueRange;
        public float ForceNoise;
        public float TorqueNoise;
        public bool GravityCompensation;
    }

    [Serializable]
    public class ForceTorqueSensor
    {
        public ForceTorqueConfig Config;
        public float LastUpdateTime;
        public Rigidbody AttachedRigidbody;
        public Vector3 ExternalForce;
        public Vector3 ExternalTorque;
        public ForceTorqueData CurrentData;
    }

    [Serializable]
    public class ForceTorqueData
    {
        public string SensorId;
        public DateTime Timestamp;
        public Vector3 Force;
        public Vector3 Torque;
        public bool IsOverloaded;
    }

    // Proximity
    [Serializable]
    public class ProximitySensorConfig
    {
        public string SensorId;
        public string FrameId;
        public Vector3 Position;
        public Vector3 Direction;
        public float MaxRange;
        public float TriggerDistance;
        public float UpdateRateHz;
        public ProximitySensorType SensorType;
        public LayerMask LayerMask;
    }

    public enum ProximitySensorType
    {
        Infrared,
        Ultrasonic,
        Inductive,
        Capacitive,
        Photoelectric,
        Laser
    }

    [Serializable]
    public class ProximitySensor
    {
        public ProximitySensorConfig Config;
        public float LastUpdateTime;
        public ProximitySensorData CurrentData;
    }

    [Serializable]
    public class ProximitySensorData
    {
        public string SensorId;
        public DateTime Timestamp;
        public float Distance;
        public bool IsTriggered;
        public string DetectedObject;
        public Vector3 HitPoint;
        public Vector3 HitNormal;
    }

    // Encoder
    [Serializable]
    public class EncoderConfig
    {
        public string SensorId;
        public string JointName;
        public int Resolution; // ticks per revolution
        public float UpdateRateHz;
        public bool IndexPulse;
        public float MaxVelocity; // rad/s
    }

    [Serializable]
    public class EncoderSensor
    {
        public EncoderConfig Config;
        public float LastUpdateTime;
        public float JointAngle;
        public int PreviousTicks;
        public float PreviousAngle;
        public long AccumulatedTicks;
        public EncoderData CurrentData;
    }

    [Serializable]
    public class EncoderData
    {
        public string SensorId;
        public string JointName;
        public DateTime Timestamp;
        public int Position; // ticks
        public float Velocity; // ticks/sec
        public float PositionRadians;
        public float VelocityRadians;
        public bool IndexPulseTriggered;
        public bool HasError;
        public int ErrorCode;
    }

    // Statistics
    [Serializable]
    public class SensorStatistics
    {
        public int LiDARCount;
        public int IMUCount;
        public int ForceTorqueCount;
        public int ProximityCount;
        public int EncoderCount;
        public int TotalSensors;
        public bool PublishingToROS;
    }

    #endregion
}
