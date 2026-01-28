using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCDigitalTwin.SensorFusion
{
    /// <summary>
    /// Advanced Sensor Fusion System for CNC Digital Twin
    /// Combines multiple sensor inputs using Kalman filtering, complementary filtering,
    /// and weighted averaging for improved state estimation accuracy
    /// </summary>
    public class SensorFusionSystem : MonoBehaviour
    {
        public static SensorFusionSystem Instance { get; private set; }

        [Header("Fusion Configuration")]
        [SerializeField] private float updateRate = 100f; // Hz
        [SerializeField] private float processNoise = 0.01f;
        [SerializeField] private float measurementNoise = 0.1f;
        [SerializeField] private bool enableAdaptiveFiltering = true;

        [Header("Outlier Detection")]
        [SerializeField] private float outlierThresholdSigma = 3f;
        [SerializeField] private int outlierWindowSize = 10;
        [SerializeField] private bool enableOutlierRejection = true;

        [Header("Sensor Health")]
        [SerializeField] private float sensorTimeoutSeconds = 1f;
        [SerializeField] private float minSensorReliability = 0.5f;

        // Events
        public event Action<FusedState> OnStateUpdated;
        public event Action<SensorInput, SensorHealth> OnSensorHealthChanged;
        public event Action<string, float[]> OnFusedValueUpdated;
        public event Action<SensorAnomaly> OnAnomalyDetected;

        // Sensor management
        private Dictionary<string, SensorInput> sensors = new Dictionary<string, SensorInput>();
        private Dictionary<string, FusionNode> fusionNodes = new Dictionary<string, FusionNode>();
        private Dictionary<string, KalmanFilter> kalmanFilters = new Dictionary<string, KalmanFilter>();
        private Dictionary<string, ComplementaryFilter> compFilters = new Dictionary<string, ComplementaryFilter>();

        // State estimation
        private FusedState currentState = new FusedState();
        private Dictionary<string, float[]> fusedValues = new Dictionary<string, float[]>();

        // Statistics
        private SensorFusionStats stats = new SensorFusionStats();

        #region Data Structures

        public enum SensorType
        {
            Encoder,
            Resolver,
            LinearScale,
            Accelerometer,
            Gyroscope,
            Magnetometer,
            GPS,
            LaserTracker,
            VisionSystem,
            ProximitySensor,
            LoadCell,
            StrainGauge,
            Thermocouple,
            RTD,
            Tachometer,
            CurrentSensor,
            VoltageSensor,
            FlowSensor,
            PressureSensor
        }

        public enum FusionMethod
        {
            WeightedAverage,
            KalmanFilter,
            ExtendedKalmanFilter,
            UnscentedKalmanFilter,
            ComplementaryFilter,
            ParticleFilter,
            MovingHorizonEstimation
        }

        public enum SensorHealth
        {
            Healthy,
            Degraded,
            Faulty,
            Offline,
            Unknown
        }

        public class SensorInput
        {
            public string SensorId { get; set; }
            public string Name { get; set; }
            public SensorType Type { get; set; }
            public string FusionNodeId { get; set; }
            public int Dimensions { get; set; }
            public float SampleRate { get; set; }
            public float[] Accuracy { get; set; }
            public float[] Noise { get; set; }
            public float[] Bias { get; set; }
            public float[] Scale { get; set; }
            public float Latency { get; set; } // seconds
            public float Weight { get; set; }
            public float Reliability { get; set; }
            public SensorHealth Health { get; set; }
            public float[] LastValue { get; set; }
            public float[] FilteredValue { get; set; }
            public DateTime LastUpdateTime { get; set; }
            public SensorStatistics Statistics { get; set; } = new SensorStatistics();
        }

        public class SensorStatistics
        {
            public long SamplesReceived { get; set; }
            public long OutliersDetected { get; set; }
            public float[] Mean { get; set; }
            public float[] Variance { get; set; }
            public float[] Min { get; set; }
            public float[] Max { get; set; }
            public Queue<float[]> RecentSamples { get; set; } = new Queue<float[]>();
        }

        public class FusionNode
        {
            public string NodeId { get; set; }
            public string Name { get; set; }
            public string StateVariable { get; set; }
            public int Dimensions { get; set; }
            public FusionMethod Method { get; set; }
            public List<string> InputSensorIds { get; set; } = new List<string>();
            public float[] FusedValue { get; set; }
            public float[] Uncertainty { get; set; }
            public DateTime LastFusionTime { get; set; }
            public FusionStatistics Statistics { get; set; } = new FusionStatistics();
        }

        public class FusionStatistics
        {
            public long FusionCycles { get; set; }
            public float AverageLatencyMs { get; set; }
            public float InnovationRms { get; set; }
            public float ConsistencyMetric { get; set; }
        }

        public class FusedState
        {
            public DateTime Timestamp { get; set; }

            // Position
            public Vector3 Position { get; set; }
            public Vector3 PositionUncertainty { get; set; }

            // Velocity
            public Vector3 Velocity { get; set; }
            public Vector3 VelocityUncertainty { get; set; }

            // Acceleration
            public Vector3 Acceleration { get; set; }
            public Vector3 AccelerationUncertainty { get; set; }

            // Orientation (Quaternion)
            public Quaternion Orientation { get; set; }
            public Vector3 OrientationUncertainty { get; set; } // Euler uncertainty

            // Angular velocity
            public Vector3 AngularVelocity { get; set; }
            public Vector3 AngularVelocityUncertainty { get; set; }

            // Machine-specific states
            public float SpindleSpeed { get; set; }
            public float SpindleSpeedUncertainty { get; set; }
            public float[] AxisLoads { get; set; }
            public float[] AxisTemperatures { get; set; }

            // Quality metrics
            public float OverallConfidence { get; set; }
            public int ActiveSensors { get; set; }
        }

        public class KalmanFilter
        {
            public int StateDimension { get; set; }
            public int MeasurementDimension { get; set; }

            // State estimate
            public float[] State { get; set; }
            public float[,] Covariance { get; set; }

            // System matrices
            public float[,] StateTransition { get; set; }      // F
            public float[,] ControlInput { get; set; }          // B
            public float[,] MeasurementMatrix { get; set; }     // H
            public float[,] ProcessNoise { get; set; }          // Q
            public float[,] MeasurementNoise { get; set; }      // R

            // Innovation
            public float[] Innovation { get; set; }
            public float[,] InnovationCovariance { get; set; }
            public float[] KalmanGain { get; set; }

            // Adaptive parameters
            public float AdaptiveFactor { get; set; } = 1.0f;
            public Queue<float[]> InnovationHistory { get; set; } = new Queue<float[]>();
        }

        public class ComplementaryFilter
        {
            public float Alpha { get; set; } // Low-pass weight
            public int Dimensions { get; set; }
            public float[] Output { get; set; }
            public string LowFrequencySensor { get; set; }  // e.g., encoder
            public string HighFrequencySensor { get; set; }  // e.g., accelerometer
        }

        public class SensorAnomaly
        {
            public string SensorId { get; set; }
            public DateTime Timestamp { get; set; }
            public AnomalyType Type { get; set; }
            public string Description { get; set; }
            public float[] ExpectedValue { get; set; }
            public float[] ActualValue { get; set; }
            public float Severity { get; set; }
        }

        public enum AnomalyType
        {
            Outlier,
            Drift,
            Spike,
            Flatline,
            NoiseIncrease,
            LatencyIncrease,
            Inconsistency
        }

        public class SensorFusionStats
        {
            public int TotalSensors { get; set; }
            public int HealthySensors { get; set; }
            public int FusionNodes { get; set; }
            public long TotalFusionCycles { get; set; }
            public long TotalAnomalies { get; set; }
            public float AverageLatencyMs { get; set; }
        }

        #endregion

        #region Initialization

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
                return;
            }
        }

        private void Start()
        {
            InitializeDefaultConfiguration();
            StartCoroutine(FusionLoop());
            StartCoroutine(HealthMonitorLoop());
            Debug.Log($"[SensorFusion] System initialized at {updateRate}Hz");
        }

        private void InitializeDefaultConfiguration()
        {
            // Create default fusion nodes for CNC machine

            // Position fusion node (X, Y, Z)
            CreateFusionNode("position", "Position Fusion", "Position", 3, FusionMethod.KalmanFilter);

            // Velocity fusion node
            CreateFusionNode("velocity", "Velocity Fusion", "Velocity", 3, FusionMethod.KalmanFilter);

            // Spindle fusion node
            CreateFusionNode("spindle", "Spindle Fusion", "SpindleSpeed", 1, FusionMethod.ComplementaryFilter);

            // Initialize Kalman filters
            InitializeKalmanFilter("position", 6, 3); // State: [x, y, z, vx, vy, vz]
            InitializeKalmanFilter("velocity", 3, 3);
            InitializeKalmanFilter("spindle", 2, 1); // State: [speed, acceleration]

            // Initialize complementary filter for spindle
            InitializeComplementaryFilter("spindle", 0.98f, 1);
        }

        private void InitializeKalmanFilter(string nodeId, int stateDim, int measDim)
        {
            var kf = new KalmanFilter
            {
                StateDimension = stateDim,
                MeasurementDimension = measDim,
                State = new float[stateDim],
                Covariance = CreateIdentityMatrix(stateDim),
                StateTransition = CreateIdentityMatrix(stateDim),
                MeasurementMatrix = CreateMeasurementMatrix(stateDim, measDim),
                ProcessNoise = CreateDiagonalMatrix(stateDim, processNoise),
                MeasurementNoise = CreateDiagonalMatrix(measDim, measurementNoise),
                Innovation = new float[measDim],
                InnovationCovariance = CreateIdentityMatrix(measDim)
            };

            // Set up state transition for position-velocity model
            if (nodeId == "position" && stateDim == 6)
            {
                float dt = 1f / updateRate;
                // Position updates with velocity
                kf.StateTransition[0, 3] = dt;
                kf.StateTransition[1, 4] = dt;
                kf.StateTransition[2, 5] = dt;
            }

            kalmanFilters[nodeId] = kf;
        }

        private void InitializeComplementaryFilter(string nodeId, float alpha, int dimensions)
        {
            compFilters[nodeId] = new ComplementaryFilter
            {
                Alpha = alpha,
                Dimensions = dimensions,
                Output = new float[dimensions]
            };
        }

        private float[,] CreateIdentityMatrix(int size)
        {
            var matrix = new float[size, size];
            for (int i = 0; i < size; i++)
                matrix[i, i] = 1f;
            return matrix;
        }

        private float[,] CreateDiagonalMatrix(int size, float value)
        {
            var matrix = new float[size, size];
            for (int i = 0; i < size; i++)
                matrix[i, i] = value;
            return matrix;
        }

        private float[,] CreateMeasurementMatrix(int stateDim, int measDim)
        {
            var matrix = new float[measDim, stateDim];
            for (int i = 0; i < Math.Min(measDim, stateDim); i++)
                matrix[i, i] = 1f;
            return matrix;
        }

        #endregion

        #region Sensor Management

        public SensorInput RegisterSensor(string sensorId, string name, SensorType type,
            string fusionNodeId, int dimensions, float sampleRate, float[] accuracy)
        {
            var sensor = new SensorInput
            {
                SensorId = sensorId,
                Name = name,
                Type = type,
                FusionNodeId = fusionNodeId,
                Dimensions = dimensions,
                SampleRate = sampleRate,
                Accuracy = accuracy,
                Noise = new float[dimensions],
                Bias = new float[dimensions],
                Scale = Enumerable.Repeat(1f, dimensions).ToArray(),
                Latency = 0.001f,
                Weight = 1f,
                Reliability = 1f,
                Health = SensorHealth.Unknown,
                LastValue = new float[dimensions],
                FilteredValue = new float[dimensions],
                Statistics = new SensorStatistics
                {
                    Mean = new float[dimensions],
                    Variance = new float[dimensions],
                    Min = Enumerable.Repeat(float.MaxValue, dimensions).ToArray(),
                    Max = Enumerable.Repeat(float.MinValue, dimensions).ToArray()
                }
            };

            // Initialize noise from accuracy
            for (int i = 0; i < dimensions; i++)
            {
                sensor.Noise[i] = accuracy[i] * accuracy[i]; // Variance
            }

            sensors[sensorId] = sensor;
            stats.TotalSensors++;

            // Add to fusion node
            if (fusionNodes.TryGetValue(fusionNodeId, out var node))
            {
                node.InputSensorIds.Add(sensorId);
            }

            Debug.Log($"[SensorFusion] Registered sensor: {sensorId} ({type}) -> {fusionNodeId}");
            return sensor;
        }

        public void CreateFusionNode(string nodeId, string name, string stateVariable,
            int dimensions, FusionMethod method)
        {
            var node = new FusionNode
            {
                NodeId = nodeId,
                Name = name,
                StateVariable = stateVariable,
                Dimensions = dimensions,
                Method = method,
                FusedValue = new float[dimensions],
                Uncertainty = new float[dimensions]
            };

            fusionNodes[nodeId] = node;
            fusedValues[nodeId] = new float[dimensions];
            stats.FusionNodes++;

            Debug.Log($"[SensorFusion] Created fusion node: {nodeId} ({method})");
        }

        public void UpdateSensor(string sensorId, float[] values, DateTime? timestamp = null)
        {
            if (!sensors.TryGetValue(sensorId, out var sensor))
            {
                Debug.LogWarning($"[SensorFusion] Unknown sensor: {sensorId}");
                return;
            }

            if (values.Length != sensor.Dimensions)
            {
                Debug.LogWarning($"[SensorFusion] Dimension mismatch for sensor {sensorId}");
                return;
            }

            var ts = timestamp ?? DateTime.Now;

            // Apply calibration
            float[] calibratedValues = ApplyCalibration(sensor, values);

            // Outlier detection
            if (enableOutlierRejection && IsOutlier(sensor, calibratedValues))
            {
                sensor.Statistics.OutliersDetected++;

                OnAnomalyDetected?.Invoke(new SensorAnomaly
                {
                    SensorId = sensorId,
                    Timestamp = ts,
                    Type = AnomalyType.Outlier,
                    Description = "Value exceeds threshold",
                    ExpectedValue = sensor.Statistics.Mean,
                    ActualValue = calibratedValues,
                    Severity = CalculateAnomalySeverity(sensor, calibratedValues)
                });

                stats.TotalAnomalies++;
                return; // Reject outlier
            }

            // Update sensor value
            sensor.LastValue = calibratedValues;
            sensor.LastUpdateTime = ts;
            sensor.Statistics.SamplesReceived++;

            // Update statistics
            UpdateSensorStatistics(sensor, calibratedValues);

            // Update health
            UpdateSensorHealth(sensor);

            // Apply individual sensor filtering
            ApplySensorFilter(sensor);
        }

        private float[] ApplyCalibration(SensorInput sensor, float[] values)
        {
            var calibrated = new float[sensor.Dimensions];
            for (int i = 0; i < sensor.Dimensions; i++)
            {
                calibrated[i] = (values[i] - sensor.Bias[i]) * sensor.Scale[i];
            }
            return calibrated;
        }

        private bool IsOutlier(SensorInput sensor, float[] values)
        {
            if (sensor.Statistics.SamplesReceived < outlierWindowSize)
                return false;

            for (int i = 0; i < sensor.Dimensions; i++)
            {
                float stdDev = Mathf.Sqrt(sensor.Statistics.Variance[i]);
                if (stdDev > 0)
                {
                    float zscore = Mathf.Abs(values[i] - sensor.Statistics.Mean[i]) / stdDev;
                    if (zscore > outlierThresholdSigma)
                        return true;
                }
            }
            return false;
        }

        private void UpdateSensorStatistics(SensorInput sensor, float[] values)
        {
            var stats = sensor.Statistics;
            long n = stats.SamplesReceived;

            for (int i = 0; i < sensor.Dimensions; i++)
            {
                // Online mean and variance (Welford's algorithm)
                float delta = values[i] - stats.Mean[i];
                stats.Mean[i] += delta / n;
                float delta2 = values[i] - stats.Mean[i];
                stats.Variance[i] += (delta * delta2 - stats.Variance[i]) / n;

                // Min/Max
                if (values[i] < stats.Min[i]) stats.Min[i] = values[i];
                if (values[i] > stats.Max[i]) stats.Max[i] = values[i];
            }

            // Keep recent samples for analysis
            stats.RecentSamples.Enqueue((float[])values.Clone());
            while (stats.RecentSamples.Count > outlierWindowSize)
                stats.RecentSamples.Dequeue();
        }

        private void UpdateSensorHealth(SensorInput sensor)
        {
            var oldHealth = sensor.Health;
            var timeSinceUpdate = (DateTime.Now - sensor.LastUpdateTime).TotalSeconds;

            if (timeSinceUpdate > sensorTimeoutSeconds)
            {
                sensor.Health = SensorHealth.Offline;
                sensor.Reliability = 0;
            }
            else if (sensor.Statistics.OutliersDetected > sensor.Statistics.SamplesReceived * 0.1f)
            {
                sensor.Health = SensorHealth.Faulty;
                sensor.Reliability = 0.3f;
            }
            else if (sensor.Statistics.OutliersDetected > sensor.Statistics.SamplesReceived * 0.02f)
            {
                sensor.Health = SensorHealth.Degraded;
                sensor.Reliability = 0.7f;
            }
            else
            {
                sensor.Health = SensorHealth.Healthy;
                sensor.Reliability = 1.0f;
            }

            // Update weight based on reliability
            sensor.Weight = sensor.Reliability;

            if (oldHealth != sensor.Health)
            {
                OnSensorHealthChanged?.Invoke(sensor, sensor.Health);

                if (sensor.Health == SensorHealth.Healthy)
                    stats.HealthySensors++;
                else if (oldHealth == SensorHealth.Healthy)
                    stats.HealthySensors--;
            }
        }

        private void ApplySensorFilter(SensorInput sensor)
        {
            // Simple exponential smoothing per sensor
            float alpha = 0.3f;
            for (int i = 0; i < sensor.Dimensions; i++)
            {
                sensor.FilteredValue[i] = alpha * sensor.LastValue[i] +
                                          (1 - alpha) * sensor.FilteredValue[i];
            }
        }

        private float CalculateAnomalySeverity(SensorInput sensor, float[] values)
        {
            float maxZScore = 0;
            for (int i = 0; i < sensor.Dimensions; i++)
            {
                float stdDev = Mathf.Sqrt(sensor.Statistics.Variance[i]);
                if (stdDev > 0)
                {
                    float zscore = Mathf.Abs(values[i] - sensor.Statistics.Mean[i]) / stdDev;
                    if (zscore > maxZScore) maxZScore = zscore;
                }
            }
            return Mathf.Clamp01((maxZScore - outlierThresholdSigma) / outlierThresholdSigma);
        }

        #endregion

        #region Fusion Algorithms

        private IEnumerator FusionLoop()
        {
            float interval = 1f / updateRate;

            while (true)
            {
                yield return new WaitForSeconds(interval);

                var startTime = DateTime.Now;

                // Process each fusion node
                foreach (var node in fusionNodes.Values)
                {
                    FuseNode(node);
                }

                // Update global state
                UpdateFusedState();

                stats.TotalFusionCycles++;
                stats.AverageLatencyMs = (float)(DateTime.Now - startTime).TotalMilliseconds;
            }
        }

        private void FuseNode(FusionNode node)
        {
            var validSensors = node.InputSensorIds
                .Where(id => sensors.ContainsKey(id))
                .Select(id => sensors[id])
                .Where(s => s.Health != SensorHealth.Offline && s.Reliability >= minSensorReliability)
                .ToList();

            if (validSensors.Count == 0)
            {
                // Mark as unavailable
                Array.Fill(node.Uncertainty, float.MaxValue);
                return;
            }

            switch (node.Method)
            {
                case FusionMethod.WeightedAverage:
                    FuseWeightedAverage(node, validSensors);
                    break;

                case FusionMethod.KalmanFilter:
                    FuseKalman(node, validSensors);
                    break;

                case FusionMethod.ComplementaryFilter:
                    FuseComplementary(node, validSensors);
                    break;

                default:
                    FuseWeightedAverage(node, validSensors);
                    break;
            }

            node.LastFusionTime = DateTime.Now;
            node.Statistics.FusionCycles++;

            fusedValues[node.NodeId] = (float[])node.FusedValue.Clone();
            OnFusedValueUpdated?.Invoke(node.NodeId, node.FusedValue);
        }

        private void FuseWeightedAverage(FusionNode node, List<SensorInput> sensors)
        {
            Array.Clear(node.FusedValue, 0, node.FusedValue.Length);
            Array.Clear(node.Uncertainty, 0, node.Uncertainty.Length);

            float totalWeight = sensors.Sum(s => s.Weight);
            if (totalWeight == 0) totalWeight = 1;

            foreach (var sensor in sensors)
            {
                float normalizedWeight = sensor.Weight / totalWeight;

                for (int i = 0; i < Math.Min(node.Dimensions, sensor.Dimensions); i++)
                {
                    node.FusedValue[i] += sensor.FilteredValue[i] * normalizedWeight;
                    // Uncertainty decreases with more sensors
                    node.Uncertainty[i] += sensor.Noise[i] * normalizedWeight * normalizedWeight;
                }
            }

            // Take square root for standard deviation
            for (int i = 0; i < node.Dimensions; i++)
            {
                node.Uncertainty[i] = Mathf.Sqrt(node.Uncertainty[i]);
            }
        }

        private void FuseKalman(FusionNode node, List<SensorInput> sensors)
        {
            if (!kalmanFilters.TryGetValue(node.NodeId, out var kf))
            {
                FuseWeightedAverage(node, sensors);
                return;
            }

            // Predict step
            KalmanPredict(kf);

            // Update step for each sensor
            foreach (var sensor in sensors)
            {
                // Build measurement vector
                float[] measurement = new float[kf.MeasurementDimension];
                for (int i = 0; i < Math.Min(measurement.Length, sensor.Dimensions); i++)
                {
                    measurement[i] = sensor.FilteredValue[i];
                }

                // Update measurement noise based on sensor reliability
                for (int i = 0; i < kf.MeasurementDimension; i++)
                {
                    if (i < sensor.Dimensions)
                    {
                        kf.MeasurementNoise[i, i] = sensor.Noise[i] / sensor.Reliability;
                    }
                }

                KalmanUpdate(kf, measurement);
            }

            // Adaptive filtering - adjust process noise based on innovation
            if (enableAdaptiveFiltering)
            {
                AdaptProcessNoise(kf);
            }

            // Extract fused values from state
            for (int i = 0; i < Math.Min(node.Dimensions, kf.StateDimension); i++)
            {
                node.FusedValue[i] = kf.State[i];
                node.Uncertainty[i] = Mathf.Sqrt(kf.Covariance[i, i]);
            }

            // Update innovation statistics
            node.Statistics.InnovationRms = CalculateRMS(kf.Innovation);
        }

        private void KalmanPredict(KalmanFilter kf)
        {
            // x' = F * x
            var newState = new float[kf.StateDimension];
            for (int i = 0; i < kf.StateDimension; i++)
            {
                for (int j = 0; j < kf.StateDimension; j++)
                {
                    newState[i] += kf.StateTransition[i, j] * kf.State[j];
                }
            }
            kf.State = newState;

            // P' = F * P * F' + Q
            var newCov = new float[kf.StateDimension, kf.StateDimension];
            for (int i = 0; i < kf.StateDimension; i++)
            {
                for (int j = 0; j < kf.StateDimension; j++)
                {
                    float sum = 0;
                    for (int k = 0; k < kf.StateDimension; k++)
                    {
                        for (int l = 0; l < kf.StateDimension; l++)
                        {
                            sum += kf.StateTransition[i, k] * kf.Covariance[k, l] * kf.StateTransition[j, l];
                        }
                    }
                    newCov[i, j] = sum + kf.ProcessNoise[i, j];
                }
            }
            kf.Covariance = newCov;
        }

        private void KalmanUpdate(KalmanFilter kf, float[] measurement)
        {
            int n = kf.StateDimension;
            int m = kf.MeasurementDimension;

            // Innovation: y = z - H * x
            for (int i = 0; i < m; i++)
            {
                kf.Innovation[i] = measurement[i];
                for (int j = 0; j < n; j++)
                {
                    kf.Innovation[i] -= kf.MeasurementMatrix[i, j] * kf.State[j];
                }
            }

            // Store innovation for adaptive filtering
            kf.InnovationHistory.Enqueue((float[])kf.Innovation.Clone());
            while (kf.InnovationHistory.Count > 10)
                kf.InnovationHistory.Dequeue();

            // Innovation covariance: S = H * P * H' + R
            for (int i = 0; i < m; i++)
            {
                for (int j = 0; j < m; j++)
                {
                    float sum = 0;
                    for (int k = 0; k < n; k++)
                    {
                        for (int l = 0; l < n; l++)
                        {
                            sum += kf.MeasurementMatrix[i, k] * kf.Covariance[k, l] * kf.MeasurementMatrix[j, l];
                        }
                    }
                    kf.InnovationCovariance[i, j] = sum + kf.MeasurementNoise[i, j];
                }
            }

            // Kalman gain: K = P * H' * S^-1
            // Simplified for diagonal case
            var gain = new float[n, m];
            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < m; j++)
                {
                    float sum = 0;
                    for (int k = 0; k < n; k++)
                    {
                        sum += kf.Covariance[i, k] * kf.MeasurementMatrix[j, k];
                    }
                    gain[i, j] = sum / kf.InnovationCovariance[j, j];
                }
            }

            // Update state: x = x + K * y
            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < m; j++)
                {
                    kf.State[i] += gain[i, j] * kf.Innovation[j];
                }
            }

            // Update covariance: P = (I - K * H) * P
            var newCov = new float[n, n];
            for (int i = 0; i < n; i++)
            {
                for (int j = 0; j < n; j++)
                {
                    float kh = 0;
                    for (int k = 0; k < m; k++)
                    {
                        kh += gain[i, k] * kf.MeasurementMatrix[k, j];
                    }
                    newCov[i, j] = kf.Covariance[i, j] - kh * kf.Covariance[i, j];
                }
            }
            kf.Covariance = newCov;
        }

        private void AdaptProcessNoise(KalmanFilter kf)
        {
            if (kf.InnovationHistory.Count < 5) return;

            // Calculate innovation covariance from history
            var innovations = kf.InnovationHistory.ToList();
            float[] meanInnovation = new float[kf.MeasurementDimension];
            float[] varInnovation = new float[kf.MeasurementDimension];

            foreach (var inn in innovations)
            {
                for (int i = 0; i < kf.MeasurementDimension; i++)
                {
                    meanInnovation[i] += inn[i];
                }
            }
            for (int i = 0; i < kf.MeasurementDimension; i++)
            {
                meanInnovation[i] /= innovations.Count;
            }

            foreach (var inn in innovations)
            {
                for (int i = 0; i < kf.MeasurementDimension; i++)
                {
                    float diff = inn[i] - meanInnovation[i];
                    varInnovation[i] += diff * diff;
                }
            }
            for (int i = 0; i < kf.MeasurementDimension; i++)
            {
                varInnovation[i] /= innovations.Count;
            }

            // Adjust process noise if innovation variance differs from expected
            for (int i = 0; i < Math.Min(kf.StateDimension, kf.MeasurementDimension); i++)
            {
                float expectedVar = kf.InnovationCovariance[i, i];
                float actualVar = varInnovation[i];

                if (expectedVar > 0)
                {
                    float ratio = actualVar / expectedVar;
                    // Slowly adjust process noise
                    float adjustment = Mathf.Clamp(ratio, 0.5f, 2.0f);
                    kf.ProcessNoise[i, i] *= Mathf.Lerp(1f, adjustment, 0.1f);
                }
            }
        }

        private void FuseComplementary(FusionNode node, List<SensorInput> sensors)
        {
            if (!compFilters.TryGetValue(node.NodeId, out var cf))
            {
                FuseWeightedAverage(node, sensors);
                return;
            }

            // Get low and high frequency sensor values
            var lowFreqSensor = sensors.FirstOrDefault(s => s.Type == SensorType.Encoder ||
                                                           s.Type == SensorType.LinearScale ||
                                                           s.Type == SensorType.Tachometer);
            var highFreqSensor = sensors.FirstOrDefault(s => s.Type == SensorType.Accelerometer ||
                                                            s.Type == SensorType.Gyroscope);

            if (lowFreqSensor == null && highFreqSensor == null)
            {
                FuseWeightedAverage(node, sensors);
                return;
            }

            // Complementary filter: output = alpha * low_freq + (1-alpha) * integrated_high_freq
            for (int i = 0; i < cf.Dimensions; i++)
            {
                float lowFreqValue = lowFreqSensor != null && i < lowFreqSensor.Dimensions ?
                    lowFreqSensor.FilteredValue[i] : cf.Output[i];
                float highFreqValue = highFreqSensor != null && i < highFreqSensor.Dimensions ?
                    highFreqSensor.FilteredValue[i] : 0;

                // Simple complementary combination
                cf.Output[i] = cf.Alpha * lowFreqValue + (1 - cf.Alpha) * (cf.Output[i] + highFreqValue / updateRate);
                node.FusedValue[i] = cf.Output[i];
            }

            // Uncertainty from both sources
            for (int i = 0; i < node.Dimensions; i++)
            {
                float lowNoise = lowFreqSensor != null && i < lowFreqSensor.Dimensions ?
                    lowFreqSensor.Noise[i] : 1f;
                float highNoise = highFreqSensor != null && i < highFreqSensor.Dimensions ?
                    highFreqSensor.Noise[i] : 1f;

                node.Uncertainty[i] = Mathf.Sqrt(cf.Alpha * cf.Alpha * lowNoise +
                                                (1 - cf.Alpha) * (1 - cf.Alpha) * highNoise);
            }
        }

        private float CalculateRMS(float[] values)
        {
            float sum = 0;
            foreach (var v in values)
                sum += v * v;
            return Mathf.Sqrt(sum / values.Length);
        }

        #endregion

        #region State Update

        private void UpdateFusedState()
        {
            currentState.Timestamp = DateTime.Now;
            currentState.ActiveSensors = stats.HealthySensors;

            // Extract position
            if (fusedValues.TryGetValue("position", out var pos) && pos.Length >= 3)
            {
                currentState.Position = new Vector3(pos[0], pos[1], pos[2]);

                if (fusionNodes.TryGetValue("position", out var node))
                {
                    currentState.PositionUncertainty = new Vector3(
                        node.Uncertainty[0], node.Uncertainty[1], node.Uncertainty[2]);
                }
            }

            // Extract velocity
            if (fusedValues.TryGetValue("velocity", out var vel) && vel.Length >= 3)
            {
                currentState.Velocity = new Vector3(vel[0], vel[1], vel[2]);

                if (fusionNodes.TryGetValue("velocity", out var node))
                {
                    currentState.VelocityUncertainty = new Vector3(
                        node.Uncertainty[0], node.Uncertainty[1], node.Uncertainty[2]);
                }
            }

            // Extract spindle speed
            if (fusedValues.TryGetValue("spindle", out var spd) && spd.Length >= 1)
            {
                currentState.SpindleSpeed = spd[0];

                if (fusionNodes.TryGetValue("spindle", out var node))
                {
                    currentState.SpindleSpeedUncertainty = node.Uncertainty[0];
                }
            }

            // Calculate overall confidence
            float totalUncertainty = 0;
            int count = 0;
            foreach (var node in fusionNodes.Values)
            {
                foreach (var u in node.Uncertainty)
                {
                    if (u < float.MaxValue)
                    {
                        totalUncertainty += u;
                        count++;
                    }
                }
            }
            currentState.OverallConfidence = count > 0 ? Mathf.Exp(-totalUncertainty / count) * 100f : 0;

            OnStateUpdated?.Invoke(currentState);
        }

        #endregion

        #region Health Monitoring

        private IEnumerator HealthMonitorLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(1f);

                foreach (var sensor in sensors.Values)
                {
                    var timeSinceUpdate = (DateTime.Now - sensor.LastUpdateTime).TotalSeconds;

                    // Check for timeout
                    if (timeSinceUpdate > sensorTimeoutSeconds && sensor.Health != SensorHealth.Offline)
                    {
                        var oldHealth = sensor.Health;
                        sensor.Health = SensorHealth.Offline;
                        sensor.Reliability = 0;

                        if (oldHealth == SensorHealth.Healthy)
                            stats.HealthySensors--;

                        OnSensorHealthChanged?.Invoke(sensor, sensor.Health);

                        OnAnomalyDetected?.Invoke(new SensorAnomaly
                        {
                            SensorId = sensor.SensorId,
                            Timestamp = DateTime.Now,
                            Type = AnomalyType.Flatline,
                            Description = "Sensor timeout - no data received",
                            Severity = 1.0f
                        });
                    }

                    // Check for drift
                    if (sensor.Statistics.RecentSamples.Count >= outlierWindowSize)
                    {
                        DetectDrift(sensor);
                    }
                }

                // Update stats
                stats.HealthySensors = sensors.Values.Count(s => s.Health == SensorHealth.Healthy);
            }
        }

        private void DetectDrift(SensorInput sensor)
        {
            var samples = sensor.Statistics.RecentSamples.ToList();
            if (samples.Count < 5) return;

            // Check for monotonic trend (drift)
            for (int dim = 0; dim < sensor.Dimensions; dim++)
            {
                int increasing = 0;
                int decreasing = 0;

                for (int i = 1; i < samples.Count; i++)
                {
                    if (samples[i][dim] > samples[i - 1][dim]) increasing++;
                    else if (samples[i][dim] < samples[i - 1][dim]) decreasing++;
                }

                float trendRatio = (float)Math.Max(increasing, decreasing) / (samples.Count - 1);

                if (trendRatio > 0.9f) // 90% of samples in same direction
                {
                    OnAnomalyDetected?.Invoke(new SensorAnomaly
                    {
                        SensorId = sensor.SensorId,
                        Timestamp = DateTime.Now,
                        Type = AnomalyType.Drift,
                        Description = $"Potential drift detected in dimension {dim}",
                        ActualValue = sensor.LastValue,
                        Severity = trendRatio - 0.9f
                    });
                }
            }
        }

        #endregion

        #region Public API

        public SensorInput GetSensor(string sensorId)
        {
            return sensors.TryGetValue(sensorId, out var sensor) ? sensor : null;
        }

        public List<SensorInput> GetAllSensors()
        {
            return sensors.Values.ToList();
        }

        public FusionNode GetFusionNode(string nodeId)
        {
            return fusionNodes.TryGetValue(nodeId, out var node) ? node : null;
        }

        public List<FusionNode> GetAllFusionNodes()
        {
            return fusionNodes.Values.ToList();
        }

        public FusedState GetCurrentState()
        {
            return currentState;
        }

        public float[] GetFusedValue(string nodeId)
        {
            return fusedValues.TryGetValue(nodeId, out var value) ? value : null;
        }

        public void SetSensorCalibration(string sensorId, float[] bias, float[] scale)
        {
            if (sensors.TryGetValue(sensorId, out var sensor))
            {
                sensor.Bias = bias;
                sensor.Scale = scale;
                Debug.Log($"[SensorFusion] Updated calibration for {sensorId}");
            }
        }

        public void SetSensorWeight(string sensorId, float weight)
        {
            if (sensors.TryGetValue(sensorId, out var sensor))
            {
                sensor.Weight = Mathf.Clamp01(weight);
            }
        }

        public SensorFusionStats GetStats()
        {
            return stats;
        }

        #endregion
    }
}
