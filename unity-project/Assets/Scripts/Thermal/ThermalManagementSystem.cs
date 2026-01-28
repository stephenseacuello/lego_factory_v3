using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCDigitalTwin.Thermal
{
    /// <summary>
    /// Thermal Management System for CNC Digital Twin
    /// Monitors temperature distribution, predicts thermal drift, and applies compensation
    /// Critical for maintaining machining accuracy in precision manufacturing
    /// </summary>
    public class ThermalManagementSystem : MonoBehaviour
    {
        public static ThermalManagementSystem Instance { get; private set; }

        [Header("System Configuration")]
        [SerializeField] private float updateInterval = 1f; // seconds
        [SerializeField] private float referenceTemperature = 20f; // °C
        [SerializeField] private bool enableThermalCompensation = true;
        [SerializeField] private bool enablePredictiveWarming = false;

        [Header("Material Properties")]
        [SerializeField] private float steelCTE = 11.7f; // Coefficient of thermal expansion (µm/m/°C)
        [SerializeField] private float aluminumCTE = 23.1f;
        [SerializeField] private float castIronCTE = 10.8f;
        [SerializeField] private float graniteCTE = 5.0f;

        [Header("Alert Thresholds")]
        [SerializeField] private float temperatureAlarmDelta = 5f; // °C from setpoint
        [SerializeField] private float gradientAlarmThreshold = 2f; // °C between adjacent points
        [SerializeField] private float driftAlarmThreshold = 10f; // µm

        // Events
        public event Action<ThermalSensor, ThermalReading> OnTemperatureChanged;
        public event Action<ThermalZone, ThermalGradient> OnGradientDetected;
        public event Action<ThermalDrift> OnDriftCalculated;
        public event Action<ThermalAlarm> OnAlarmTriggered;
        public event Action<ThermalCompensation> OnCompensationApplied;

        // Data collections
        private Dictionary<string, ThermalSensor> sensors = new Dictionary<string, ThermalSensor>();
        private Dictionary<string, ThermalZone> zones = new Dictionary<string, ThermalZone>();
        private Dictionary<string, ThermalModel> thermalModels = new Dictionary<string, ThermalModel>();
        private Dictionary<string, List<ThermalReading>> temperatureHistory = new Dictionary<string, List<ThermalReading>>();
        private List<ThermalAlarm> activeAlarms = new List<ThermalAlarm>();

        // Current state
        private ThermalState currentState = new ThermalState();
        private Vector3 currentCompensation = Vector3.zero;

        // Statistics
        private ThermalSystemStats stats = new ThermalSystemStats();

        #region Data Structures

        public enum SensorType
        {
            RTD_PT100,
            RTD_PT1000,
            Thermocouple_K,
            Thermocouple_J,
            Thermistor_NTC,
            Infrared_Pyrometer,
            Fiber_Optic
        }

        public enum ThermalZoneType
        {
            Spindle,
            Ballscrew_X,
            Ballscrew_Y,
            Ballscrew_Z,
            LinearGuide_X,
            LinearGuide_Y,
            LinearGuide_Z,
            Column,
            Bed,
            Headstock,
            Tailstock,
            Ambient,
            Coolant
        }

        public enum AlarmSeverity
        {
            Info,
            Warning,
            Alarm,
            Critical
        }

        public enum MaterialType
        {
            Steel,
            Aluminum,
            CastIron,
            Granite,
            Polymer,
            Composite
        }

        public class ThermalSensor
        {
            public string SensorId { get; set; }
            public string Name { get; set; }
            public SensorType Type { get; set; }
            public string ZoneId { get; set; }
            public Vector3 Position { get; set; }
            public float Accuracy { get; set; } // °C
            public float ResponseTime { get; set; } // seconds
            public float MinRange { get; set; }
            public float MaxRange { get; set; }
            public bool IsEnabled { get; set; }
            public ThermalReading LastReading { get; set; }
            public DateTime LastUpdateTime { get; set; }
        }

        public class ThermalReading
        {
            public DateTime Timestamp { get; set; }
            public float Temperature { get; set; } // °C
            public float DeltaFromReference { get; set; }
            public float RateOfChange { get; set; } // °C/min
            public bool IsValid { get; set; }
        }

        public class ThermalZone
        {
            public string ZoneId { get; set; }
            public string Name { get; set; }
            public ThermalZoneType Type { get; set; }
            public List<string> SensorIds { get; set; } = new List<string>();
            public MaterialType Material { get; set; }
            public float Length { get; set; } // mm - for expansion calculation
            public float TargetTemperature { get; set; }
            public float TemperatureTolerance { get; set; }
            public float CurrentTemperature { get; set; }
            public Vector3 ExpansionAxis { get; set; } // Direction of expansion effect
            public bool HasCooling { get; set; }
            public float CoolingCapacity { get; set; } // kW
            public bool CoolingActive { get; set; }
        }

        public class ThermalGradient
        {
            public string ZoneId { get; set; }
            public DateTime Timestamp { get; set; }
            public float MaxGradient { get; set; } // °C
            public Vector3 GradientDirection { get; set; }
            public string HighTempSensor { get; set; }
            public string LowTempSensor { get; set; }
        }

        public class ThermalDrift
        {
            public DateTime Timestamp { get; set; }
            public Vector3 PositionDrift { get; set; } // µm
            public Vector3 AngularDrift { get; set; } // µrad
            public float TotalError { get; set; } // µm
            public Dictionary<string, float> ContributingZones { get; set; } = new Dictionary<string, float>();
        }

        public class ThermalCompensation
        {
            public DateTime Timestamp { get; set; }
            public Vector3 LinearOffset { get; set; } // µm
            public Vector3 AngularOffset { get; set; } // µrad
            public float ConfidenceLevel { get; set; }
            public string Method { get; set; }
        }

        public class ThermalModel
        {
            public string ModelId { get; set; }
            public string ZoneId { get; set; }
            public ModelType Type { get; set; }
            public float TimeConstant { get; set; } // seconds
            public float HeatGeneration { get; set; } // Watts
            public float HeatDissipation { get; set; } // W/°C
            public List<float> Coefficients { get; set; } = new List<float>();
            public float ModelAccuracy { get; set; }
        }

        public enum ModelType
        {
            FirstOrder,
            SecondOrder,
            Neural_Network,
            Finite_Element
        }

        public class ThermalAlarm
        {
            public string AlarmId { get; set; }
            public string SensorId { get; set; }
            public string ZoneId { get; set; }
            public AlarmSeverity Severity { get; set; }
            public string Message { get; set; }
            public float Temperature { get; set; }
            public float Threshold { get; set; }
            public DateTime TriggeredTime { get; set; }
            public bool Acknowledged { get; set; }
        }

        public class ThermalState
        {
            public float AmbientTemperature { get; set; }
            public float MachineAverageTemp { get; set; }
            public float CoolantTemperature { get; set; }
            public float SpindleTemperature { get; set; }
            public Vector3 EstimatedDrift { get; set; }
            public bool IsStable { get; set; }
            public float StabilityIndex { get; set; } // 0-100
            public DateTime WarmupStartTime { get; set; }
            public bool WarmupComplete { get; set; }
        }

        public class ThermalSystemStats
        {
            public int TotalSensors { get; set; }
            public int ActiveSensors { get; set; }
            public int TotalZones { get; set; }
            public long ReadingsProcessed { get; set; }
            public int CompensationsApplied { get; set; }
            public int AlarmsTriggered { get; set; }
            public float MaxDriftObserved { get; set; }
            public float AverageAccuracy { get; set; }
        }

        public class FiniteElementNode
        {
            public int NodeId { get; set; }
            public Vector3 Position { get; set; }
            public float Temperature { get; set; }
            public float HeatCapacity { get; set; }
            public List<int> ConnectedNodes { get; set; } = new List<int>();
            public List<float> ConductanceValues { get; set; } = new List<float>();
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
            StartCoroutine(ThermalUpdateLoop());
            StartCoroutine(DriftCalculationLoop());
            Debug.Log($"[ThermalManagement] System initialized - Reference temp: {referenceTemperature}°C");
        }

        #endregion

        #region Sensor Management

        public ThermalSensor RegisterSensor(string sensorId, string name, SensorType type,
            Vector3 position, string zoneId = null)
        {
            var sensor = new ThermalSensor
            {
                SensorId = sensorId,
                Name = name,
                Type = type,
                Position = position,
                ZoneId = zoneId,
                Accuracy = GetTypicalAccuracy(type),
                ResponseTime = GetTypicalResponseTime(type),
                MinRange = GetMinRange(type),
                MaxRange = GetMaxRange(type),
                IsEnabled = true
            };

            sensors[sensorId] = sensor;
            temperatureHistory[sensorId] = new List<ThermalReading>();
            stats.TotalSensors++;
            stats.ActiveSensors++;

            // Add to zone if specified
            if (!string.IsNullOrEmpty(zoneId) && zones.ContainsKey(zoneId))
            {
                zones[zoneId].SensorIds.Add(sensorId);
            }

            Debug.Log($"[ThermalManagement] Registered sensor: {sensorId} ({type})");
            return sensor;
        }

        public ThermalZone CreateZone(string zoneId, string name, ThermalZoneType type,
            MaterialType material, float length, Vector3 expansionAxis)
        {
            var zone = new ThermalZone
            {
                ZoneId = zoneId,
                Name = name,
                Type = type,
                Material = material,
                Length = length,
                TargetTemperature = referenceTemperature,
                TemperatureTolerance = 2f,
                ExpansionAxis = expansionAxis.normalized
            };

            zones[zoneId] = zone;
            stats.TotalZones++;

            Debug.Log($"[ThermalManagement] Created zone: {zoneId} ({type})");
            return zone;
        }

        private float GetTypicalAccuracy(SensorType type)
        {
            return type switch
            {
                SensorType.RTD_PT100 => 0.1f,
                SensorType.RTD_PT1000 => 0.1f,
                SensorType.Thermocouple_K => 0.5f,
                SensorType.Thermocouple_J => 0.5f,
                SensorType.Thermistor_NTC => 0.2f,
                SensorType.Infrared_Pyrometer => 1.0f,
                SensorType.Fiber_Optic => 0.05f,
                _ => 0.5f
            };
        }

        private float GetTypicalResponseTime(SensorType type)
        {
            return type switch
            {
                SensorType.RTD_PT100 => 0.5f,
                SensorType.RTD_PT1000 => 0.3f,
                SensorType.Thermocouple_K => 0.2f,
                SensorType.Thermocouple_J => 0.2f,
                SensorType.Thermistor_NTC => 1.0f,
                SensorType.Infrared_Pyrometer => 0.01f,
                SensorType.Fiber_Optic => 0.001f,
                _ => 0.5f
            };
        }

        private float GetMinRange(SensorType type)
        {
            return type switch
            {
                SensorType.RTD_PT100 => -200f,
                SensorType.Thermocouple_K => -270f,
                SensorType.Infrared_Pyrometer => -50f,
                _ => -50f
            };
        }

        private float GetMaxRange(SensorType type)
        {
            return type switch
            {
                SensorType.RTD_PT100 => 850f,
                SensorType.Thermocouple_K => 1372f,
                SensorType.Infrared_Pyrometer => 500f,
                _ => 200f
            };
        }

        #endregion

        #region Temperature Processing

        public void UpdateTemperature(string sensorId, float temperature)
        {
            if (!sensors.TryGetValue(sensorId, out var sensor))
            {
                Debug.LogWarning($"[ThermalManagement] Unknown sensor: {sensorId}");
                return;
            }

            if (!sensor.IsEnabled) return;

            // Validate reading
            bool isValid = temperature >= sensor.MinRange && temperature <= sensor.MaxRange;

            // Calculate rate of change
            float rateOfChange = 0;
            var history = temperatureHistory[sensorId];
            if (history.Count > 0)
            {
                var lastReading = history.Last();
                float timeDelta = (float)(DateTime.Now - lastReading.Timestamp).TotalMinutes;
                if (timeDelta > 0)
                {
                    rateOfChange = (temperature - lastReading.Temperature) / timeDelta;
                }
            }

            var reading = new ThermalReading
            {
                Timestamp = DateTime.Now,
                Temperature = temperature,
                DeltaFromReference = temperature - referenceTemperature,
                RateOfChange = rateOfChange,
                IsValid = isValid
            };

            sensor.LastReading = reading;
            sensor.LastUpdateTime = DateTime.Now;

            // Store in history (keep last 60 readings = 1 hour at 1 reading/min)
            history.Add(reading);
            while (history.Count > 60)
                history.RemoveAt(0);

            stats.ReadingsProcessed++;

            // Check alarms
            CheckTemperatureAlarms(sensor, reading);

            // Update zone temperature
            if (!string.IsNullOrEmpty(sensor.ZoneId) && zones.ContainsKey(sensor.ZoneId))
            {
                UpdateZoneTemperature(sensor.ZoneId);
            }

            OnTemperatureChanged?.Invoke(sensor, reading);
        }

        private void UpdateZoneTemperature(string zoneId)
        {
            var zone = zones[zoneId];
            var zoneSensors = zone.SensorIds
                .Where(id => sensors.ContainsKey(id))
                .Select(id => sensors[id])
                .Where(s => s.LastReading != null && s.LastReading.IsValid)
                .ToList();

            if (zoneSensors.Count == 0) return;

            // Calculate weighted average temperature
            zone.CurrentTemperature = zoneSensors.Average(s => s.LastReading.Temperature);

            // Check for thermal gradients
            if (zoneSensors.Count >= 2)
            {
                float maxTemp = zoneSensors.Max(s => s.LastReading.Temperature);
                float minTemp = zoneSensors.Min(s => s.LastReading.Temperature);
                float gradient = maxTemp - minTemp;

                if (gradient > gradientAlarmThreshold)
                {
                    var highSensor = zoneSensors.OrderByDescending(s => s.LastReading.Temperature).First();
                    var lowSensor = zoneSensors.OrderBy(s => s.LastReading.Temperature).First();

                    var gradientInfo = new ThermalGradient
                    {
                        ZoneId = zoneId,
                        Timestamp = DateTime.Now,
                        MaxGradient = gradient,
                        GradientDirection = (highSensor.Position - lowSensor.Position).normalized,
                        HighTempSensor = highSensor.SensorId,
                        LowTempSensor = lowSensor.SensorId
                    };

                    OnGradientDetected?.Invoke(zone, gradientInfo);
                }
            }
        }

        private void CheckTemperatureAlarms(ThermalSensor sensor, ThermalReading reading)
        {
            string zoneId = sensor.ZoneId ?? "Unknown";
            float target = referenceTemperature;

            if (!string.IsNullOrEmpty(sensor.ZoneId) && zones.ContainsKey(sensor.ZoneId))
            {
                target = zones[sensor.ZoneId].TargetTemperature;
            }

            float delta = Mathf.Abs(reading.Temperature - target);

            AlarmSeverity? severity = null;
            string message = null;

            if (delta > temperatureAlarmDelta * 2)
            {
                severity = AlarmSeverity.Critical;
                message = $"Critical temperature deviation: {reading.Temperature:F1}°C (target {target:F1}°C)";
            }
            else if (delta > temperatureAlarmDelta)
            {
                severity = AlarmSeverity.Alarm;
                message = $"Temperature alarm: {reading.Temperature:F1}°C (target {target:F1}°C)";
            }
            else if (delta > temperatureAlarmDelta * 0.5f)
            {
                severity = AlarmSeverity.Warning;
                message = $"Temperature warning: {reading.Temperature:F1}°C (target {target:F1}°C)";
            }

            // Check rate of change
            if (Mathf.Abs(reading.RateOfChange) > 1f) // More than 1°C/min
            {
                if (severity == null || severity < AlarmSeverity.Warning)
                {
                    severity = AlarmSeverity.Warning;
                    message = $"Rapid temperature change: {reading.RateOfChange:F2}°C/min";
                }
            }

            if (severity.HasValue)
            {
                TriggerAlarm(sensor.SensorId, zoneId, severity.Value, message, reading.Temperature, target);
            }
        }

        private void TriggerAlarm(string sensorId, string zoneId, AlarmSeverity severity,
            string message, float temperature, float threshold)
        {
            // Check if alarm already exists
            var existingAlarm = activeAlarms.FirstOrDefault(a =>
                a.SensorId == sensorId && a.Severity == severity && !a.Acknowledged);

            if (existingAlarm != null) return;

            var alarm = new ThermalAlarm
            {
                AlarmId = Guid.NewGuid().ToString(),
                SensorId = sensorId,
                ZoneId = zoneId,
                Severity = severity,
                Message = message,
                Temperature = temperature,
                Threshold = threshold,
                TriggeredTime = DateTime.Now,
                Acknowledged = false
            };

            activeAlarms.Add(alarm);
            stats.AlarmsTriggered++;

            OnAlarmTriggered?.Invoke(alarm);
            Debug.LogWarning($"[ThermalManagement] ALARM: {severity} - {message}");
        }

        #endregion

        #region Thermal Drift Calculation

        private IEnumerator DriftCalculationLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(5f); // Calculate drift every 5 seconds
                CalculateThermalDrift();
            }
        }

        private void CalculateThermalDrift()
        {
            var drift = new ThermalDrift
            {
                Timestamp = DateTime.Now,
                PositionDrift = Vector3.zero,
                AngularDrift = Vector3.zero,
                ContributingZones = new Dictionary<string, float>()
            };

            foreach (var kvp in zones)
            {
                var zone = kvp.Value;
                if (zone.CurrentTemperature == 0) continue;

                float deltaT = zone.CurrentTemperature - referenceTemperature;
                float cte = GetCTE(zone.Material);

                // Calculate linear expansion: dL = L * CTE * dT (in micrometers)
                float expansion = zone.Length * cte * deltaT / 1000f; // Result in µm

                // Apply expansion along the zone's axis
                Vector3 zoneDrift = zone.ExpansionAxis * expansion;
                drift.PositionDrift += zoneDrift;
                drift.ContributingZones[zone.ZoneId] = expansion;

                // For ballscrews, calculate lead screw pitch error
                if (zone.Type == ThermalZoneType.Ballscrew_X ||
                    zone.Type == ThermalZoneType.Ballscrew_Y ||
                    zone.Type == ThermalZoneType.Ballscrew_Z)
                {
                    // Additional positioning error due to pitch change
                    // Assuming typical ballscrew pitch of 10mm
                    float pitchError = 10f * cte * deltaT / 1000f; // µm per revolution
                    drift.ContributingZones[$"{zone.ZoneId}_pitch"] = pitchError;
                }
            }

            drift.TotalError = drift.PositionDrift.magnitude;
            currentState.EstimatedDrift = drift.PositionDrift;

            // Update max observed drift
            if (drift.TotalError > stats.MaxDriftObserved)
                stats.MaxDriftObserved = drift.TotalError;

            // Check drift alarm
            if (drift.TotalError > driftAlarmThreshold)
            {
                TriggerAlarm("DRIFT", "SYSTEM", AlarmSeverity.Alarm,
                    $"Thermal drift {drift.TotalError:F1}µm exceeds threshold {driftAlarmThreshold}µm",
                    drift.TotalError, driftAlarmThreshold);
            }

            OnDriftCalculated?.Invoke(drift);

            // Apply compensation if enabled
            if (enableThermalCompensation)
            {
                ApplyThermalCompensation(drift);
            }
        }

        private float GetCTE(MaterialType material)
        {
            return material switch
            {
                MaterialType.Steel => steelCTE,
                MaterialType.Aluminum => aluminumCTE,
                MaterialType.CastIron => castIronCTE,
                MaterialType.Granite => graniteCTE,
                MaterialType.Polymer => 70f,
                MaterialType.Composite => 8f,
                _ => steelCTE
            };
        }

        private void ApplyThermalCompensation(ThermalDrift drift)
        {
            // Apply opposite offset to counteract drift
            var compensation = new ThermalCompensation
            {
                Timestamp = DateTime.Now,
                LinearOffset = -drift.PositionDrift, // Opposite direction
                AngularOffset = -drift.AngularDrift,
                ConfidenceLevel = CalculateCompensationConfidence(),
                Method = "Linear CTE Model"
            };

            currentCompensation = compensation.LinearOffset;
            stats.CompensationsApplied++;

            OnCompensationApplied?.Invoke(compensation);
        }

        private float CalculateCompensationConfidence()
        {
            // Base confidence on data quality
            float confidence = 100f;

            // Reduce for missing sensor data
            float sensorCoverage = (float)stats.ActiveSensors / Mathf.Max(stats.TotalSensors, 1);
            confidence *= sensorCoverage;

            // Reduce for high rate of change (system not stable)
            var avgRateOfChange = temperatureHistory.Values
                .Where(h => h.Count > 0)
                .Average(h => Mathf.Abs(h.Last().RateOfChange));
            if (avgRateOfChange > 0.5f)
                confidence *= 0.8f;
            if (avgRateOfChange > 1f)
                confidence *= 0.6f;

            return Mathf.Clamp(confidence, 0, 100);
        }

        #endregion

        #region Thermal Stability

        private IEnumerator ThermalUpdateLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(updateInterval);
                UpdateThermalState();
                CheckWarmupStatus();

                // Simulate sensors for testing
                SimulateSensorReadings();
            }
        }

        private void UpdateThermalState()
        {
            var validReadings = sensors.Values
                .Where(s => s.LastReading != null && s.LastReading.IsValid)
                .Select(s => s.LastReading)
                .ToList();

            if (validReadings.Count == 0) return;

            currentState.MachineAverageTemp = validReadings.Average(r => r.Temperature);

            // Get specific zone temperatures
            if (zones.TryGetValue("AMBIENT", out var ambient))
                currentState.AmbientTemperature = ambient.CurrentTemperature;
            if (zones.TryGetValue("COOLANT", out var coolant))
                currentState.CoolantTemperature = coolant.CurrentTemperature;
            if (zones.TryGetValue("SPINDLE", out var spindle))
                currentState.SpindleTemperature = spindle.CurrentTemperature;

            // Calculate stability index
            float maxRateOfChange = validReadings.Max(r => Mathf.Abs(r.RateOfChange));
            float avgDelta = validReadings.Average(r => Mathf.Abs(r.DeltaFromReference));

            // Stability: low rate of change and low deviation from reference
            float rateScore = Mathf.Max(0, 100 - maxRateOfChange * 100); // 0 score if 1°C/min or more
            float deltaScore = Mathf.Max(0, 100 - avgDelta * 20); // 0 score if 5°C average delta

            currentState.StabilityIndex = (rateScore + deltaScore) / 2f;
            currentState.IsStable = currentState.StabilityIndex > 80f;
        }

        private void CheckWarmupStatus()
        {
            if (currentState.WarmupComplete) return;

            // Machine is considered warmed up when:
            // 1. Spindle temperature is within 2°C of target
            // 2. Stability index > 90
            // 3. At least 30 minutes have passed

            bool spindleWarm = Mathf.Abs(currentState.SpindleTemperature - referenceTemperature) < 2f;
            bool isStable = currentState.StabilityIndex > 90f;
            bool timeElapsed = currentState.WarmupStartTime != default &&
                              (DateTime.Now - currentState.WarmupStartTime).TotalMinutes > 30;

            if (spindleWarm && isStable && timeElapsed)
            {
                currentState.WarmupComplete = true;
                Debug.Log("[ThermalManagement] Machine warmup complete - ready for precision work");
            }
        }

        public void StartWarmup()
        {
            currentState.WarmupStartTime = DateTime.Now;
            currentState.WarmupComplete = false;

            if (enablePredictiveWarming)
            {
                // Enable any pre-heating systems
                foreach (var zone in zones.Values)
                {
                    if (zone.HasCooling)
                    {
                        // Actually for warmup, we might run the machine
                        // but in controlled manner
                    }
                }
            }

            Debug.Log("[ThermalManagement] Warmup cycle started");
        }

        #endregion

        #region Simulation

        private void SimulateSensorReadings()
        {
            // Simulate temperature readings for testing
            float time = Time.time;

            foreach (var sensor in sensors.Values)
            {
                if (!sensor.IsEnabled) continue;

                // Base temperature around reference with some variation
                float baseTemp = referenceTemperature;

                // Add zone-specific behavior
                if (zones.TryGetValue(sensor.ZoneId ?? "", out var zone))
                {
                    switch (zone.Type)
                    {
                        case ThermalZoneType.Spindle:
                            // Spindle heats up over time
                            baseTemp = referenceTemperature + 5f * (1f - Mathf.Exp(-time / 600f));
                            break;
                        case ThermalZoneType.Ballscrew_X:
                        case ThermalZoneType.Ballscrew_Y:
                        case ThermalZoneType.Ballscrew_Z:
                            // Ballscrews heat up moderately
                            baseTemp = referenceTemperature + 3f * (1f - Mathf.Exp(-time / 900f));
                            break;
                        case ThermalZoneType.Ambient:
                            // Ambient varies slowly
                            baseTemp = referenceTemperature + Mathf.Sin(time / 3600f) * 2f;
                            break;
                        case ThermalZoneType.Coolant:
                            // Coolant maintained close to target
                            baseTemp = referenceTemperature + UnityEngine.Random.Range(-0.5f, 0.5f);
                            break;
                    }
                }

                // Add some noise
                float noise = UnityEngine.Random.Range(-0.2f, 0.2f);
                float temperature = baseTemp + noise;

                UpdateTemperature(sensor.SensorId, temperature);
            }
        }

        #endregion

        #region Thermal Modeling

        public void CreateThermalModel(string modelId, string zoneId, ModelType type)
        {
            var model = new ThermalModel
            {
                ModelId = modelId,
                ZoneId = zoneId,
                Type = type,
                TimeConstant = 300f, // 5 minute default
                HeatGeneration = 100f, // Watts default
                HeatDissipation = 10f, // W/°C default
                Coefficients = new List<float> { 1f, 0f, 0f }
            };

            thermalModels[modelId] = model;
            Debug.Log($"[ThermalManagement] Created thermal model: {modelId} for zone {zoneId}");
        }

        public void TrainModel(string modelId, List<ThermalReading> trainingData)
        {
            if (!thermalModels.TryGetValue(modelId, out var model))
            {
                Debug.LogError($"[ThermalManagement] Model not found: {modelId}");
                return;
            }

            // Simple first-order model fitting
            // T(t) = T_ambient + (T_initial - T_ambient) * exp(-t/tau) + Q*R*(1 - exp(-t/tau))
            // Where tau = time constant, Q = heat generation, R = thermal resistance

            if (trainingData.Count < 10)
            {
                Debug.LogWarning("[ThermalManagement] Insufficient data for model training");
                return;
            }

            // Estimate time constant from rate of change
            var ratesOfChange = trainingData.Select(r => r.RateOfChange).Where(r => r != 0).ToList();
            if (ratesOfChange.Count > 0)
            {
                float avgRate = ratesOfChange.Average();
                float avgTemp = trainingData.Average(r => r.Temperature);
                float deltaT = avgTemp - referenceTemperature;

                if (Mathf.Abs(avgRate) > 0.01f && Mathf.Abs(deltaT) > 0.1f)
                {
                    model.TimeConstant = Mathf.Abs(deltaT / avgRate) * 60f; // Convert to seconds
                }
            }

            model.ModelAccuracy = 85f; // Placeholder
            Debug.Log($"[ThermalManagement] Model {modelId} trained - Time constant: {model.TimeConstant:F1}s");
        }

        public float PredictTemperature(string modelId, float timeAhead)
        {
            if (!thermalModels.TryGetValue(modelId, out var model))
                return referenceTemperature;

            if (!zones.TryGetValue(model.ZoneId, out var zone))
                return referenceTemperature;

            // First-order prediction
            float currentDelta = zone.CurrentTemperature - referenceTemperature;
            float steadyStateDelta = model.HeatGeneration / model.HeatDissipation;

            float predictedDelta = steadyStateDelta +
                (currentDelta - steadyStateDelta) * Mathf.Exp(-timeAhead / model.TimeConstant);

            return referenceTemperature + predictedDelta;
        }

        #endregion

        #region Public API

        public ThermalSensor GetSensor(string sensorId)
        {
            return sensors.TryGetValue(sensorId, out var sensor) ? sensor : null;
        }

        public List<ThermalSensor> GetAllSensors()
        {
            return sensors.Values.ToList();
        }

        public ThermalZone GetZone(string zoneId)
        {
            return zones.TryGetValue(zoneId, out var zone) ? zone : null;
        }

        public List<ThermalZone> GetAllZones()
        {
            return zones.Values.ToList();
        }

        public ThermalState GetCurrentState()
        {
            return currentState;
        }

        public Vector3 GetCurrentCompensation()
        {
            return currentCompensation;
        }

        public List<ThermalAlarm> GetActiveAlarms()
        {
            return activeAlarms.Where(a => !a.Acknowledged).ToList();
        }

        public void AcknowledgeAlarm(string alarmId)
        {
            var alarm = activeAlarms.FirstOrDefault(a => a.AlarmId == alarmId);
            if (alarm != null)
            {
                alarm.Acknowledged = true;
            }
        }

        public List<ThermalReading> GetTemperatureHistory(string sensorId)
        {
            return temperatureHistory.TryGetValue(sensorId, out var history)
                ? history.ToList()
                : new List<ThermalReading>();
        }

        public ThermalSystemStats GetStats()
        {
            return stats;
        }

        public void SetCoolingState(string zoneId, bool enabled)
        {
            if (zones.TryGetValue(zoneId, out var zone) && zone.HasCooling)
            {
                zone.CoolingActive = enabled;
                Debug.Log($"[ThermalManagement] Cooling for zone {zoneId}: {(enabled ? "ON" : "OFF")}");
            }
        }

        public void SetReferenceTemperature(float temperature)
        {
            referenceTemperature = temperature;
            foreach (var zone in zones.Values)
            {
                zone.TargetTemperature = temperature;
            }
            Debug.Log($"[ThermalManagement] Reference temperature set to {temperature}°C");
        }

        #endregion
    }
}
