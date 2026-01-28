using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using CNCScada.Sensors;
using CNCScada.Machines;

namespace CNCScada.Predictive
{
    /// <summary>
    /// Predictive maintenance system for CNC SCADA Digital Twin.
    /// Uses sensor data trends and ML-inspired algorithms to predict failures.
    /// </summary>
    public class PredictiveMaintenanceSystem : MonoBehaviour
    {
        [Header("Configuration")]
        public string systemId = "predictive-001";
        public float analysisInterval = 60f; // seconds
        public int historyWindowSize = 1000; // data points
        public bool enableAlerts = true;

        [Header("Thresholds")]
        public float toolWearWarningPercent = 70f;
        public float toolWearCriticalPercent = 90f;
        public float bearingHealthWarning = 0.7f;
        public float vibrationTrendThreshold = 0.1f;
        public float temperatureTrendThreshold = 0.5f;

        [Header("Tool Management")]
        public List<ToolData> installedTools = new List<ToolData>();

        [Header("Status")]
        [SerializeField] private float overallHealthScore = 100f;
        [SerializeField] private int activeAlerts = 0;
        [SerializeField] private float hoursToNextMaintenance = 168f; // 1 week

        // Events
        public event Action<MaintenanceAlert> OnMaintenanceAlert;
        public event Action<MaintenancePrediction> OnPredictionUpdated;
        public event Action<ToolData> OnToolWearWarning;
        public event Action<float> OnHealthScoreChanged;

        // Internal data
        private Dictionary<string, SensorHistory> sensorHistories = new Dictionary<string, SensorHistory>();
        private List<MaintenanceAlert> activeAlertList = new List<MaintenanceAlert>();
        private List<MaintenancePrediction> predictions = new List<MaintenancePrediction>();
        private float lastAnalysisTime;

        // Component references
        private BantamCNCController cncController;

        // Singleton
        public static PredictiveMaintenanceSystem Instance { get; private set; }

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
            cncController = FindObjectOfType<BantamCNCController>();
            InitializeDefaultTools();

            // Subscribe to sensor events
            if (SensorSystem.Instance != null)
            {
                SensorSystem.Instance.OnSensorReading += RecordSensorReading;
            }
        }

        private void Update()
        {
            // Periodic analysis
            if (Time.time - lastAnalysisTime >= analysisInterval)
            {
                RunPredictiveAnalysis();
                lastAnalysisTime = Time.time;
            }

            // Update tool wear in real-time
            UpdateToolWear();
        }

        private void OnDestroy()
        {
            if (SensorSystem.Instance != null)
            {
                SensorSystem.Instance.OnSensorReading -= RecordSensorReading;
            }
        }

        // =========================================================================
        // Tool Management
        // =========================================================================

        private void InitializeDefaultTools()
        {
            if (installedTools.Count == 0)
            {
                // Add default tools for Bantam CNC
                installedTools.Add(new ToolData
                {
                    toolId = "T1",
                    toolName = "1/8\" Flat End Mill",
                    toolType = ToolType.EndMill,
                    diameter = 3.175f,
                    maxLifeMinutes = 120,
                    currentLifeMinutes = 0,
                    installDate = DateTime.UtcNow
                });

                installedTools.Add(new ToolData
                {
                    toolId = "T2",
                    toolName = "1/16\" Ball End Mill",
                    toolType = ToolType.BallEndMill,
                    diameter = 1.5875f,
                    maxLifeMinutes = 60,
                    currentLifeMinutes = 0,
                    installDate = DateTime.UtcNow
                });

                installedTools.Add(new ToolData
                {
                    toolId = "T3",
                    toolName = "V-Bit 60°",
                    toolType = ToolType.VBit,
                    diameter = 6.35f,
                    maxLifeMinutes = 180,
                    currentLifeMinutes = 0,
                    installDate = DateTime.UtcNow
                });
            }
        }

        private void UpdateToolWear()
        {
            if (cncController == null) return;

            // Only accumulate wear when spindle is on and cutting
            if (!cncController.IsSpindleOn) return;

            float wearRate = CalculateWearRate();

            foreach (var tool in installedTools)
            {
                if (tool.isInstalled)
                {
                    tool.currentLifeMinutes += wearRate * Time.deltaTime / 60f;
                    tool.wearPercent = (tool.currentLifeMinutes / tool.maxLifeMinutes) * 100f;

                    // Check for wear warnings
                    if (tool.wearPercent >= toolWearCriticalPercent && !tool.criticalWarningIssued)
                    {
                        tool.criticalWarningIssued = true;
                        OnToolWearWarning?.Invoke(tool);
                        CreateAlert(AlertSeverity.Critical, "Tool Wear",
                            $"{tool.toolName} has reached {tool.wearPercent:F1}% wear. Replace immediately.",
                            tool.toolId);
                    }
                    else if (tool.wearPercent >= toolWearWarningPercent && !tool.warningIssued)
                    {
                        tool.warningIssued = true;
                        OnToolWearWarning?.Invoke(tool);
                        CreateAlert(AlertSeverity.Warning, "Tool Wear",
                            $"{tool.toolName} has reached {tool.wearPercent:F1}% wear. Plan replacement soon.",
                            tool.toolId);
                    }
                }
            }
        }

        private float CalculateWearRate()
        {
            // Base wear rate adjusted by operating conditions
            float baseRate = 1f;

            if (cncController != null)
            {
                // Higher spindle speed = faster wear
                float spindleRatio = cncController.SpindleSpeed / 10000f;
                baseRate *= 1f + spindleRatio * 0.5f;

                // Higher load = faster wear
                float[] loads = cncController.AxisLoads;
                float avgLoad = (loads[0] + loads[1] + loads[2]) / 3f;
                baseRate *= 1f + (avgLoad / 100f) * 0.3f;

                // Vibration increases wear
                float vibration = cncController.Vibration.magnitude;
                baseRate *= 1f + vibration * 0.2f;
            }

            return baseRate;
        }

        /// <summary>
        /// Replace a tool and reset its wear
        /// </summary>
        public void ReplaceTool(string toolId)
        {
            var tool = installedTools.Find(t => t.toolId == toolId);
            if (tool != null)
            {
                tool.currentLifeMinutes = 0;
                tool.wearPercent = 0;
                tool.warningIssued = false;
                tool.criticalWarningIssued = false;
                tool.installDate = DateTime.UtcNow;
                tool.replacementCount++;

                Debug.Log($"[Predictive] Tool {tool.toolName} replaced. Total replacements: {tool.replacementCount}");

                // Clear related alerts
                activeAlertList.RemoveAll(a => a.componentId == toolId);
                UpdateAlertCount();
            }
        }

        // =========================================================================
        // Sensor Data Collection
        // =========================================================================

        private void RecordSensorReading(SensorReading reading)
        {
            if (!sensorHistories.ContainsKey(reading.sensorId))
            {
                sensorHistories[reading.sensorId] = new SensorHistory
                {
                    sensorId = reading.sensorId,
                    sensorType = reading.sensorType,
                    readings = new Queue<TimestampedValue>()
                };
            }

            var history = sensorHistories[reading.sensorId];

            // Add new reading
            history.readings.Enqueue(new TimestampedValue
            {
                timestamp = reading.timestamp,
                value = reading.value
            });

            // Trim old readings
            while (history.readings.Count > historyWindowSize)
            {
                history.readings.Dequeue();
            }

            // Update statistics
            UpdateSensorStatistics(history);
        }

        private void UpdateSensorStatistics(SensorHistory history)
        {
            if (history.readings.Count < 10) return;

            var values = history.readings.Select(r => r.value).ToArray();

            history.mean = values.Average();
            history.min = values.Min();
            history.max = values.Max();
            history.stdDev = CalculateStdDev(values, history.mean);

            // Calculate trend (slope of linear regression)
            history.trend = CalculateTrend(values);
        }

        private float CalculateStdDev(float[] values, float mean)
        {
            float sumSquares = values.Sum(v => (v - mean) * (v - mean));
            return Mathf.Sqrt(sumSquares / values.Length);
        }

        private float CalculateTrend(float[] values)
        {
            // Simple linear regression slope
            int n = values.Length;
            float sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;

            for (int i = 0; i < n; i++)
            {
                sumX += i;
                sumY += values[i];
                sumXY += i * values[i];
                sumX2 += i * i;
            }

            float slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
            return slope;
        }

        // =========================================================================
        // Predictive Analysis
        // =========================================================================

        private void RunPredictiveAnalysis()
        {
            predictions.Clear();
            float healthScore = 100f;

            // Analyze each sensor's trends
            foreach (var history in sensorHistories.Values)
            {
                if (history.readings.Count < 50) continue;

                var prediction = AnalyzeSensor(history);
                if (prediction != null)
                {
                    predictions.Add(prediction);
                    OnPredictionUpdated?.Invoke(prediction);

                    // Adjust health score based on predictions
                    healthScore -= GetHealthImpact(prediction);
                }
            }

            // Analyze component health
            AnalyzeSpindleBearings();
            AnalyzeAxisHealth();

            // Update overall health score
            overallHealthScore = Mathf.Clamp(healthScore, 0, 100);
            OnHealthScoreChanged?.Invoke(overallHealthScore);

            // Calculate hours to next maintenance
            hoursToNextMaintenance = CalculateMaintenanceInterval();

            Debug.Log($"[Predictive] Analysis complete. Health: {overallHealthScore:F1}%, " +
                      $"Next maintenance: {hoursToNextMaintenance:F1}h, Alerts: {activeAlerts}");
        }

        private MaintenancePrediction AnalyzeSensor(SensorHistory history)
        {
            MaintenancePrediction prediction = null;

            // Check for concerning trends
            if (history.sensorType == SensorType.Temperature)
            {
                if (history.trend > temperatureTrendThreshold)
                {
                    // Temperature is trending up
                    float hoursToLimit = EstimateTimeToLimit(history, 70f); // 70°C limit

                    prediction = new MaintenancePrediction
                    {
                        componentId = history.sensorId,
                        componentName = "Temperature Sensor",
                        predictionType = PredictionType.OverheatingRisk,
                        confidencePercent = CalculateConfidence(history),
                        estimatedHoursToFailure = hoursToLimit,
                        currentValue = history.mean,
                        trendPerHour = history.trend * 3600f,
                        recommendation = "Check cooling system and reduce duty cycle",
                        severity = hoursToLimit < 8 ? AlertSeverity.Critical : AlertSeverity.Warning
                    };
                }
            }
            else if (history.sensorType == SensorType.Vibration)
            {
                if (history.trend > vibrationTrendThreshold || history.stdDev > 2f)
                {
                    // Vibration is increasing or unstable
                    prediction = new MaintenancePrediction
                    {
                        componentId = history.sensorId,
                        componentName = "Vibration Sensor",
                        predictionType = PredictionType.MechanicalWear,
                        confidencePercent = CalculateConfidence(history),
                        estimatedHoursToFailure = EstimateTimeToLimit(history, 7f), // ISO limit
                        currentValue = history.mean,
                        trendPerHour = history.trend * 3600f,
                        recommendation = "Inspect bearings, check for loose components",
                        severity = history.mean > 5f ? AlertSeverity.Critical : AlertSeverity.Warning
                    };
                }
            }
            else if (history.sensorType == SensorType.Current)
            {
                if (history.mean > history.max * 0.8f)
                {
                    // Current draw is consistently high
                    prediction = new MaintenancePrediction
                    {
                        componentId = history.sensorId,
                        componentName = "Motor Current",
                        predictionType = PredictionType.MotorStress,
                        confidencePercent = CalculateConfidence(history),
                        estimatedHoursToFailure = 100f, // Estimate
                        currentValue = history.mean,
                        trendPerHour = history.trend * 3600f,
                        recommendation = "Check motor brushes, reduce load, inspect drive belt",
                        severity = AlertSeverity.Warning
                    };
                }
            }

            return prediction;
        }

        private float EstimateTimeToLimit(SensorHistory history, float limit)
        {
            if (history.trend <= 0) return float.MaxValue;

            float delta = limit - history.mean;
            float hoursToLimit = delta / (history.trend * 3600f);

            return Mathf.Max(hoursToLimit, 0);
        }

        private float CalculateConfidence(SensorHistory history)
        {
            // Confidence based on data quality
            float dataPoints = Mathf.Min(history.readings.Count / (float)historyWindowSize, 1f);
            float consistency = 1f - Mathf.Min(history.stdDev / (history.max - history.min + 0.001f), 1f);

            return (dataPoints * 0.5f + consistency * 0.5f) * 100f;
        }

        private float GetHealthImpact(MaintenancePrediction prediction)
        {
            return prediction.severity switch
            {
                AlertSeverity.Critical => 30f,
                AlertSeverity.Warning => 15f,
                AlertSeverity.Info => 5f,
                _ => 0f
            };
        }

        private void AnalyzeSpindleBearings()
        {
            // Spindle bearing health estimation based on vibration spectrum
            // In a real system, this would use FFT analysis

            if (sensorHistories.TryGetValue("bantam-cnc-001_vibration", out var vibHistory))
            {
                float bearingHealth = 1f - (vibHistory.mean / 10f);
                bearingHealth = Mathf.Clamp01(bearingHealth);

                if (bearingHealth < bearingHealthWarning)
                {
                    CreateAlert(AlertSeverity.Warning, "Spindle Bearings",
                        $"Bearing health at {bearingHealth * 100:F0}%. Schedule inspection.",
                        "spindle_bearing");
                }
            }
        }

        private void AnalyzeAxisHealth()
        {
            // Check each axis motor health
            string[] axes = { "x", "y", "z" };

            foreach (var axis in axes)
            {
                string sensorId = $"bantam-cnc-001_load_{axis}";

                if (sensorHistories.TryGetValue(sensorId, out var loadHistory))
                {
                    // Check for increasing load trend (possible leadscrew wear)
                    if (loadHistory.trend > 0.05f)
                    {
                        predictions.Add(new MaintenancePrediction
                        {
                            componentId = sensorId,
                            componentName = $"{axis.ToUpper()}-Axis",
                            predictionType = PredictionType.MechanicalWear,
                            confidencePercent = CalculateConfidence(loadHistory),
                            estimatedHoursToFailure = 200f,
                            currentValue = loadHistory.mean,
                            recommendation = $"Lubricate {axis.ToUpper()}-axis leadscrew",
                            severity = AlertSeverity.Info
                        });
                    }
                }
            }
        }

        private float CalculateMaintenanceInterval()
        {
            // Find the minimum time to any predicted issue
            float minTime = 168f; // Default 1 week

            foreach (var prediction in predictions)
            {
                if (prediction.estimatedHoursToFailure < minTime)
                {
                    minTime = prediction.estimatedHoursToFailure;
                }
            }

            // Also consider tool wear
            foreach (var tool in installedTools)
            {
                if (tool.isInstalled && tool.wearPercent > 0)
                {
                    float remainingLife = (100f - tool.wearPercent) / 100f * tool.maxLifeMinutes / 60f;
                    if (remainingLife < minTime)
                    {
                        minTime = remainingLife;
                    }
                }
            }

            return Mathf.Max(minTime, 1f);
        }

        // =========================================================================
        // Alert Management
        // =========================================================================

        private void CreateAlert(AlertSeverity severity, string category, string message, string componentId)
        {
            if (!enableAlerts) return;

            // Check for duplicate
            if (activeAlertList.Any(a => a.componentId == componentId && a.category == category))
                return;

            var alert = new MaintenanceAlert
            {
                alertId = Guid.NewGuid().ToString(),
                severity = severity,
                category = category,
                message = message,
                componentId = componentId,
                timestamp = DateTime.UtcNow,
                isAcknowledged = false
            };

            activeAlertList.Add(alert);
            UpdateAlertCount();

            OnMaintenanceAlert?.Invoke(alert);
            Debug.Log($"[Predictive] Alert: [{severity}] {category} - {message}");
        }

        private void UpdateAlertCount()
        {
            activeAlerts = activeAlertList.Count(a => !a.isAcknowledged);
        }

        /// <summary>
        /// Acknowledge an alert
        /// </summary>
        public void AcknowledgeAlert(string alertId)
        {
            var alert = activeAlertList.Find(a => a.alertId == alertId);
            if (alert != null)
            {
                alert.isAcknowledged = true;
                alert.acknowledgedTime = DateTime.UtcNow;
                UpdateAlertCount();
            }
        }

        /// <summary>
        /// Get health report
        /// </summary>
        public MaintenanceHealthReport GetHealthReport()
        {
            return new MaintenanceHealthReport
            {
                overallHealthPercent = overallHealthScore,
                hoursToNextMaintenance = hoursToNextMaintenance,
                activeAlertCount = activeAlerts,
                toolWearPercents = installedTools.ToDictionary(t => t.toolId, t => t.wearPercent),
                predictions = predictions.ToList(),
                alerts = activeAlertList.Where(a => !a.isAcknowledged).ToList(),
                timestamp = DateTime.UtcNow
            };
        }

        // Properties
        public float OverallHealthScore => overallHealthScore;
        public int ActiveAlerts => activeAlerts;
        public float HoursToNextMaintenance => hoursToNextMaintenance;
        public List<MaintenancePrediction> Predictions => predictions;
        public List<MaintenanceAlert> Alerts => activeAlertList;
        public List<ToolData> Tools => installedTools;
    }

    // =========================================================================
    // Data Classes
    // =========================================================================

    public enum ToolType
    {
        EndMill,
        BallEndMill,
        VBit,
        DrillBit,
        FaceMill,
        Engraver
    }

    public enum PredictionType
    {
        ToolWear,
        OverheatingRisk,
        MechanicalWear,
        MotorStress,
        BearingFailure,
        ElectricalIssue
    }

    public enum AlertSeverity
    {
        Info,
        Warning,
        Critical
    }

    [Serializable]
    public class ToolData
    {
        public string toolId;
        public string toolName;
        public ToolType toolType;
        public float diameter; // mm
        public float maxLifeMinutes;
        public float currentLifeMinutes;
        public float wearPercent;
        public bool isInstalled = true;
        public DateTime installDate;
        public int replacementCount;
        public bool warningIssued;
        public bool criticalWarningIssued;
    }

    [Serializable]
    public class SensorHistory
    {
        public string sensorId;
        public SensorType sensorType;
        public Queue<TimestampedValue> readings;
        public float mean;
        public float min;
        public float max;
        public float stdDev;
        public float trend;
    }

    [Serializable]
    public class TimestampedValue
    {
        public DateTime timestamp;
        public float value;
    }

    [Serializable]
    public class MaintenancePrediction
    {
        public string componentId;
        public string componentName;
        public PredictionType predictionType;
        public float confidencePercent;
        public float estimatedHoursToFailure;
        public float currentValue;
        public float trendPerHour;
        public string recommendation;
        public AlertSeverity severity;
    }

    [Serializable]
    public class MaintenanceAlert
    {
        public string alertId;
        public AlertSeverity severity;
        public string category;
        public string message;
        public string componentId;
        public DateTime timestamp;
        public bool isAcknowledged;
        public DateTime? acknowledgedTime;
    }

    [Serializable]
    public class MaintenanceHealthReport
    {
        public float overallHealthPercent;
        public float hoursToNextMaintenance;
        public int activeAlertCount;
        public Dictionary<string, float> toolWearPercents;
        public List<MaintenancePrediction> predictions;
        public List<MaintenanceAlert> alerts;
        public DateTime timestamp;
    }
}
