using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using CNCDigitalTwin.Historian;

namespace CNCDigitalTwin.Environmental
{
    /// <summary>
    /// Environmental Sensor Hub for comprehensive facility monitoring
    /// Tracks temperature, humidity, vibration, air quality, lighting, and more
    /// </summary>
    public class EnvironmentalSensorHub : MonoBehaviour
    {
        public static EnvironmentalSensorHub Instance { get; private set; }

        [Header("Configuration")]
        [SerializeField] private float sampleInterval = 1.0f;
        [SerializeField] private bool enableDataLogging = true;
        [SerializeField] private int maxReadingsHistory = 10000;

        [Header("Alert Thresholds")]
        [SerializeField] private EnvironmentalThresholds thresholds;

        // Sensor registry
        private Dictionary<string, EnvironmentalSensor> sensors = new Dictionary<string, EnvironmentalSensor>();
        private Dictionary<string, Zone> zones = new Dictionary<string, Zone>();

        // Readings storage
        private Dictionary<string, List<SensorReading>> readingsHistory = new Dictionary<string, List<SensorReading>>();
        private Dictionary<string, SensorReading> latestReadings = new Dictionary<string, SensorReading>();

        // Alerts
        private List<EnvironmentalAlert> activeAlerts = new List<EnvironmentalAlert>();
        private List<EnvironmentalAlert> alertHistory = new List<EnvironmentalAlert>();

        // Comfort and compliance tracking
        private Dictionary<string, ZoneConditions> zoneConditions = new Dictionary<string, ZoneConditions>();

        // Events
        public event Action<EnvironmentalSensor> OnSensorRegistered;
        public event Action<SensorReading> OnReadingReceived;
        public event Action<EnvironmentalAlert> OnAlertRaised;
        public event Action<EnvironmentalAlert> OnAlertCleared;
        public event Action<string, ZoneConditions> OnZoneConditionsUpdated;

        private Coroutine samplingCoroutine;

        void Awake()
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

        void Start()
        {
            InitializeDefaultThresholds();
            InitializeDefaultZones();
            samplingCoroutine = StartCoroutine(SamplingLoop());
        }

        void OnDestroy()
        {
            if (samplingCoroutine != null)
                StopCoroutine(samplingCoroutine);
        }

        #region Initialization

        private void InitializeDefaultThresholds()
        {
            if (thresholds == null)
            {
                thresholds = new EnvironmentalThresholds
                {
                    // Temperature (°C)
                    TemperatureMin = 18f,
                    TemperatureMax = 28f,
                    TemperatureCriticalMin = 10f,
                    TemperatureCriticalMax = 35f,

                    // Humidity (%)
                    HumidityMin = 30f,
                    HumidityMax = 60f,
                    HumidityCriticalMin = 20f,
                    HumidityCriticalMax = 80f,

                    // Vibration (mm/s RMS)
                    VibrationWarning = 4.5f,
                    VibrationCritical = 11.2f,

                    // Air Quality (ppm)
                    CO2Warning = 1000f,
                    CO2Critical = 2000f,
                    VOCWarning = 0.5f,
                    VOCCritical = 1.0f,
                    ParticulateWarning = 35f,
                    ParticulateCritical = 150f,

                    // Noise (dB)
                    NoiseWarning = 75f,
                    NoiseCritical = 85f,

                    // Lighting (lux)
                    LightingMin = 300f,
                    LightingMax = 750f,

                    // Pressure (hPa)
                    PressureMin = 980f,
                    PressureMax = 1040f
                };
            }
        }

        private void InitializeDefaultZones()
        {
            // Machine shop floor
            CreateZone(new ZoneConfig
            {
                ZoneId = "SHOP_FLOOR",
                Name = "Machine Shop Floor",
                ZoneType = ZoneType.Production,
                RequiredConditions = new RequiredConditions
                {
                    MinTemperature = 20f,
                    MaxTemperature = 25f,
                    MinHumidity = 40f,
                    MaxHumidity = 55f,
                    MaxVibration = 2.5f,
                    MinLighting = 500f
                }
            });

            // Quality lab
            CreateZone(new ZoneConfig
            {
                ZoneId = "QC_LAB",
                Name = "Quality Control Lab",
                ZoneType = ZoneType.Metrology,
                RequiredConditions = new RequiredConditions
                {
                    MinTemperature = 20f,
                    MaxTemperature = 20f, // Tight control for metrology
                    TemperatureTolerance = 0.5f,
                    MinHumidity = 45f,
                    MaxHumidity = 50f,
                    MaxVibration = 0.5f,
                    MinLighting = 750f
                }
            });

            // Server room
            CreateZone(new ZoneConfig
            {
                ZoneId = "SERVER_ROOM",
                Name = "Server Room",
                ZoneType = ZoneType.DataCenter,
                RequiredConditions = new RequiredConditions
                {
                    MinTemperature = 18f,
                    MaxTemperature = 27f,
                    MinHumidity = 30f,
                    MaxHumidity = 50f,
                    MaxParticulate = 10f
                }
            });

            // Storage area
            CreateZone(new ZoneConfig
            {
                ZoneId = "STORAGE",
                Name = "Material Storage",
                ZoneType = ZoneType.Storage,
                RequiredConditions = new RequiredConditions
                {
                    MinTemperature = 15f,
                    MaxTemperature = 30f,
                    MinHumidity = 35f,
                    MaxHumidity = 65f
                }
            });
        }

        #endregion

        #region Sensor Management

        public EnvironmentalSensor RegisterSensor(SensorConfig config)
        {
            var sensor = new EnvironmentalSensor
            {
                SensorId = config.SensorId ?? Guid.NewGuid().ToString(),
                Name = config.Name,
                Type = config.Type,
                ZoneId = config.ZoneId,
                Position = config.Position,
                Unit = GetUnitForType(config.Type),
                SampleRate = config.SampleRate > 0 ? config.SampleRate : sampleInterval,
                CalibrationFactor = config.CalibrationFactor != 0 ? config.CalibrationFactor : 1f,
                Offset = config.Offset,
                Status = SensorStatus.Online,
                LastReading = DateTime.MinValue
            };

            sensors[sensor.SensorId] = sensor;
            readingsHistory[sensor.SensorId] = new List<SensorReading>();

            // Add to zone if specified
            if (!string.IsNullOrEmpty(config.ZoneId) && zones.TryGetValue(config.ZoneId, out var zone))
            {
                zone.SensorIds.Add(sensor.SensorId);
            }

            OnSensorRegistered?.Invoke(sensor);
            Debug.Log($"[EnvHub] Registered sensor: {sensor.Name} ({sensor.Type})");

            return sensor;
        }

        public void UnregisterSensor(string sensorId)
        {
            if (sensors.TryGetValue(sensorId, out var sensor))
            {
                // Remove from zone
                if (!string.IsNullOrEmpty(sensor.ZoneId) && zones.TryGetValue(sensor.ZoneId, out var zone))
                {
                    zone.SensorIds.Remove(sensorId);
                }

                sensors.Remove(sensorId);
                readingsHistory.Remove(sensorId);
                latestReadings.Remove(sensorId);
            }
        }

        public EnvironmentalSensor GetSensor(string sensorId)
        {
            return sensors.TryGetValue(sensorId, out var sensor) ? sensor : null;
        }

        public List<EnvironmentalSensor> GetSensorsByType(SensorType type)
        {
            return sensors.Values.Where(s => s.Type == type).ToList();
        }

        public List<EnvironmentalSensor> GetSensorsByZone(string zoneId)
        {
            return sensors.Values.Where(s => s.ZoneId == zoneId).ToList();
        }

        private string GetUnitForType(SensorType type)
        {
            return type switch
            {
                SensorType.Temperature => "°C",
                SensorType.Humidity => "%",
                SensorType.Pressure => "hPa",
                SensorType.Vibration => "mm/s",
                SensorType.Noise => "dB",
                SensorType.Lighting => "lux",
                SensorType.CO2 => "ppm",
                SensorType.VOC => "ppm",
                SensorType.Particulate => "µg/m³",
                SensorType.AirVelocity => "m/s",
                SensorType.DewPoint => "°C",
                SensorType.Power => "W",
                SensorType.Current => "A",
                SensorType.Voltage => "V",
                _ => ""
            };
        }

        #endregion

        #region Zone Management

        public Zone CreateZone(ZoneConfig config)
        {
            var zone = new Zone
            {
                ZoneId = config.ZoneId,
                Name = config.Name,
                ZoneType = config.ZoneType,
                Bounds = config.Bounds,
                RequiredConditions = config.RequiredConditions,
                SensorIds = new List<string>(),
                IsMonitored = true
            };

            zones[zone.ZoneId] = zone;
            zoneConditions[zone.ZoneId] = new ZoneConditions { ZoneId = zone.ZoneId };

            Debug.Log($"[EnvHub] Created zone: {config.Name}");
            return zone;
        }

        public Zone GetZone(string zoneId)
        {
            return zones.TryGetValue(zoneId, out var zone) ? zone : null;
        }

        public ZoneConditions GetZoneConditions(string zoneId)
        {
            return zoneConditions.TryGetValue(zoneId, out var conditions) ? conditions : null;
        }

        private void UpdateZoneConditions(string zoneId)
        {
            if (!zones.TryGetValue(zoneId, out var zone) ||
                !zoneConditions.TryGetValue(zoneId, out var conditions))
            {
                return;
            }

            var zoneSensors = GetSensorsByZone(zoneId);
            conditions.Timestamp = DateTime.UtcNow;

            // Calculate averages by sensor type
            var tempSensors = zoneSensors.Where(s => s.Type == SensorType.Temperature).ToList();
            if (tempSensors.Any())
            {
                conditions.Temperature = tempSensors.Average(s =>
                    latestReadings.TryGetValue(s.SensorId, out var r) ? r.Value : 0);
            }

            var humiditySensors = zoneSensors.Where(s => s.Type == SensorType.Humidity).ToList();
            if (humiditySensors.Any())
            {
                conditions.Humidity = humiditySensors.Average(s =>
                    latestReadings.TryGetValue(s.SensorId, out var r) ? r.Value : 0);
            }

            var vibrationSensors = zoneSensors.Where(s => s.Type == SensorType.Vibration).ToList();
            if (vibrationSensors.Any())
            {
                conditions.Vibration = vibrationSensors.Max(s =>
                    latestReadings.TryGetValue(s.SensorId, out var r) ? r.Value : 0);
            }

            var noiseSensors = zoneSensors.Where(s => s.Type == SensorType.Noise).ToList();
            if (noiseSensors.Any())
            {
                conditions.NoiseLevel = noiseSensors.Average(s =>
                    latestReadings.TryGetValue(s.SensorId, out var r) ? r.Value : 0);
            }

            var lightSensors = zoneSensors.Where(s => s.Type == SensorType.Lighting).ToList();
            if (lightSensors.Any())
            {
                conditions.LightLevel = lightSensors.Average(s =>
                    latestReadings.TryGetValue(s.SensorId, out var r) ? r.Value : 0);
            }

            var co2Sensors = zoneSensors.Where(s => s.Type == SensorType.CO2).ToList();
            if (co2Sensors.Any())
            {
                conditions.CO2Level = co2Sensors.Max(s =>
                    latestReadings.TryGetValue(s.SensorId, out var r) ? r.Value : 0);
            }

            var vocSensors = zoneSensors.Where(s => s.Type == SensorType.VOC).ToList();
            if (vocSensors.Any())
            {
                conditions.VOCLevel = vocSensors.Max(s =>
                    latestReadings.TryGetValue(s.SensorId, out var r) ? r.Value : 0);
            }

            var pmSensors = zoneSensors.Where(s => s.Type == SensorType.Particulate).ToList();
            if (pmSensors.Any())
            {
                conditions.ParticulateLevel = pmSensors.Max(s =>
                    latestReadings.TryGetValue(s.SensorId, out var r) ? r.Value : 0);
            }

            // Calculate comfort index (0-100)
            conditions.ComfortIndex = CalculateComfortIndex(conditions, zone.RequiredConditions);

            // Check compliance
            conditions.IsCompliant = CheckZoneCompliance(conditions, zone.RequiredConditions);

            // Calculate air quality index
            conditions.AirQualityIndex = CalculateAQI(conditions);

            OnZoneConditionsUpdated?.Invoke(zoneId, conditions);
        }

        private float CalculateComfortIndex(ZoneConditions conditions, RequiredConditions requirements)
        {
            if (requirements == null) return 100f;

            float score = 100f;

            // Temperature contribution (30%)
            if (requirements.MaxTemperature > 0)
            {
                float tempMid = (requirements.MinTemperature + requirements.MaxTemperature) / 2;
                float tempRange = requirements.MaxTemperature - requirements.MinTemperature;
                float tempDeviation = Mathf.Abs(conditions.Temperature - tempMid) / (tempRange / 2);
                score -= Mathf.Clamp01(tempDeviation) * 30f;
            }

            // Humidity contribution (25%)
            if (requirements.MaxHumidity > 0)
            {
                float humidMid = (requirements.MinHumidity + requirements.MaxHumidity) / 2;
                float humidRange = requirements.MaxHumidity - requirements.MinHumidity;
                float humidDeviation = Mathf.Abs(conditions.Humidity - humidMid) / (humidRange / 2);
                score -= Mathf.Clamp01(humidDeviation) * 25f;
            }

            // Air quality contribution (25%)
            float aqScore = 25f;
            if (thresholds.CO2Warning > 0 && conditions.CO2Level > 0)
            {
                aqScore -= (conditions.CO2Level / thresholds.CO2Warning) * 10f;
            }
            if (thresholds.VOCWarning > 0 && conditions.VOCLevel > 0)
            {
                aqScore -= (conditions.VOCLevel / thresholds.VOCWarning) * 10f;
            }
            if (thresholds.ParticulateWarning > 0 && conditions.ParticulateLevel > 0)
            {
                aqScore -= (conditions.ParticulateLevel / thresholds.ParticulateWarning) * 5f;
            }
            score -= (25f - Mathf.Max(0, aqScore));

            // Noise contribution (10%)
            if (thresholds.NoiseWarning > 0 && conditions.NoiseLevel > 0)
            {
                float noiseRatio = conditions.NoiseLevel / thresholds.NoiseWarning;
                score -= Mathf.Clamp01(noiseRatio - 0.5f) * 20f;
            }

            // Lighting contribution (10%)
            if (requirements.MinLighting > 0 && conditions.LightLevel > 0)
            {
                float lightRatio = conditions.LightLevel / requirements.MinLighting;
                if (lightRatio < 0.8f || lightRatio > 1.5f)
                {
                    score -= 10f;
                }
            }

            return Mathf.Clamp(score, 0f, 100f);
        }

        private bool CheckZoneCompliance(ZoneConditions conditions, RequiredConditions requirements)
        {
            if (requirements == null) return true;

            // Temperature check
            if (requirements.MaxTemperature > 0)
            {
                float tolerance = requirements.TemperatureTolerance > 0 ? requirements.TemperatureTolerance : 2f;
                if (conditions.Temperature < requirements.MinTemperature - tolerance ||
                    conditions.Temperature > requirements.MaxTemperature + tolerance)
                {
                    return false;
                }
            }

            // Humidity check
            if (requirements.MaxHumidity > 0)
            {
                if (conditions.Humidity < requirements.MinHumidity ||
                    conditions.Humidity > requirements.MaxHumidity)
                {
                    return false;
                }
            }

            // Vibration check
            if (requirements.MaxVibration > 0 && conditions.Vibration > requirements.MaxVibration)
            {
                return false;
            }

            // Particulate check
            if (requirements.MaxParticulate > 0 && conditions.ParticulateLevel > requirements.MaxParticulate)
            {
                return false;
            }

            return true;
        }

        private int CalculateAQI(ZoneConditions conditions)
        {
            // Simplified AQI calculation based on PM2.5 primarily
            float pm = conditions.ParticulateLevel;

            if (pm <= 12) return (int)MapRange(pm, 0, 12, 0, 50);
            if (pm <= 35.4f) return (int)MapRange(pm, 12.1f, 35.4f, 51, 100);
            if (pm <= 55.4f) return (int)MapRange(pm, 35.5f, 55.4f, 101, 150);
            if (pm <= 150.4f) return (int)MapRange(pm, 55.5f, 150.4f, 151, 200);
            if (pm <= 250.4f) return (int)MapRange(pm, 150.5f, 250.4f, 201, 300);
            return (int)MapRange(pm, 250.5f, 500, 301, 500);
        }

        private float MapRange(float value, float fromMin, float fromMax, float toMin, float toMax)
        {
            return (value - fromMin) / (fromMax - fromMin) * (toMax - toMin) + toMin;
        }

        #endregion

        #region Sampling & Reading

        private IEnumerator SamplingLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(sampleInterval);

                foreach (var sensor in sensors.Values.ToList())
                {
                    if (sensor.Status == SensorStatus.Online)
                    {
                        ProcessSensorReading(sensor);
                    }
                }

                // Update zone conditions
                foreach (var zoneId in zones.Keys)
                {
                    UpdateZoneConditions(zoneId);
                }
            }
        }

        private void ProcessSensorReading(EnvironmentalSensor sensor)
        {
            // Get raw reading (simulated or from actual hardware)
            float rawValue = GetSensorValue(sensor);

            // Apply calibration
            float calibratedValue = rawValue * sensor.CalibrationFactor + sensor.Offset;

            var reading = new SensorReading
            {
                SensorId = sensor.SensorId,
                Timestamp = DateTime.UtcNow,
                RawValue = rawValue,
                Value = calibratedValue,
                Unit = sensor.Unit,
                Quality = DataQuality.Good
            };

            // Store reading
            latestReadings[sensor.SensorId] = reading;

            if (readingsHistory.TryGetValue(sensor.SensorId, out var history))
            {
                history.Add(reading);

                // Trim history
                if (history.Count > maxReadingsHistory)
                {
                    history.RemoveRange(0, history.Count - maxReadingsHistory);
                }
            }

            sensor.LastReading = reading.Timestamp;
            sensor.LastValue = reading.Value;

            // Check thresholds
            CheckThresholds(sensor, reading);

            // Log to historian
            if (enableDataLogging && DataHistorian.Instance != null)
            {
                DataHistorian.Instance.Write(
                    $"env.{sensor.Type.ToString().ToLower()}.{sensor.SensorId}",
                    reading.Value,
                    new Dictionary<string, string>
                    {
                        { "zone", sensor.ZoneId ?? "unassigned" },
                        { "sensor_name", sensor.Name }
                    }
                );
            }

            OnReadingReceived?.Invoke(reading);
        }

        private float GetSensorValue(EnvironmentalSensor sensor)
        {
            // Simulate realistic sensor values
            float baseValue = sensor.Type switch
            {
                SensorType.Temperature => 22f + UnityEngine.Random.Range(-2f, 2f),
                SensorType.Humidity => 45f + UnityEngine.Random.Range(-5f, 5f),
                SensorType.Pressure => 1013f + UnityEngine.Random.Range(-5f, 5f),
                SensorType.Vibration => 1.5f + UnityEngine.Random.Range(-0.5f, 1.5f),
                SensorType.Noise => 65f + UnityEngine.Random.Range(-5f, 10f),
                SensorType.Lighting => 500f + UnityEngine.Random.Range(-50f, 100f),
                SensorType.CO2 => 600f + UnityEngine.Random.Range(-50f, 200f),
                SensorType.VOC => 0.2f + UnityEngine.Random.Range(-0.1f, 0.2f),
                SensorType.Particulate => 15f + UnityEngine.Random.Range(-5f, 20f),
                SensorType.AirVelocity => 0.3f + UnityEngine.Random.Range(-0.1f, 0.2f),
                SensorType.DewPoint => 10f + UnityEngine.Random.Range(-2f, 2f),
                SensorType.Power => 1500f + UnityEngine.Random.Range(-200f, 500f),
                SensorType.Current => 6.5f + UnityEngine.Random.Range(-1f, 2f),
                SensorType.Voltage => 230f + UnityEngine.Random.Range(-5f, 5f),
                _ => 0f
            };

            // Add some continuity with previous reading
            if (sensor.LastValue > 0)
            {
                float smoothing = 0.7f;
                baseValue = sensor.LastValue * smoothing + baseValue * (1 - smoothing);
            }

            return baseValue;
        }

        public void InjectReading(string sensorId, float value)
        {
            if (!sensors.TryGetValue(sensorId, out var sensor))
                return;

            var reading = new SensorReading
            {
                SensorId = sensorId,
                Timestamp = DateTime.UtcNow,
                RawValue = value,
                Value = value * sensor.CalibrationFactor + sensor.Offset,
                Unit = sensor.Unit,
                Quality = DataQuality.Good
            };

            latestReadings[sensorId] = reading;
            sensor.LastReading = reading.Timestamp;
            sensor.LastValue = reading.Value;

            CheckThresholds(sensor, reading);
            OnReadingReceived?.Invoke(reading);
        }

        #endregion

        #region Threshold Checking & Alerts

        private void CheckThresholds(EnvironmentalSensor sensor, SensorReading reading)
        {
            AlertLevel level = AlertLevel.None;
            string message = null;

            switch (sensor.Type)
            {
                case SensorType.Temperature:
                    if (reading.Value < thresholds.TemperatureCriticalMin || reading.Value > thresholds.TemperatureCriticalMax)
                    {
                        level = AlertLevel.Critical;
                        message = $"Critical temperature: {reading.Value:F1}°C";
                    }
                    else if (reading.Value < thresholds.TemperatureMin || reading.Value > thresholds.TemperatureMax)
                    {
                        level = AlertLevel.Warning;
                        message = $"Temperature out of range: {reading.Value:F1}°C";
                    }
                    break;

                case SensorType.Humidity:
                    if (reading.Value < thresholds.HumidityCriticalMin || reading.Value > thresholds.HumidityCriticalMax)
                    {
                        level = AlertLevel.Critical;
                        message = $"Critical humidity: {reading.Value:F0}%";
                    }
                    else if (reading.Value < thresholds.HumidityMin || reading.Value > thresholds.HumidityMax)
                    {
                        level = AlertLevel.Warning;
                        message = $"Humidity out of range: {reading.Value:F0}%";
                    }
                    break;

                case SensorType.Vibration:
                    if (reading.Value > thresholds.VibrationCritical)
                    {
                        level = AlertLevel.Critical;
                        message = $"Critical vibration: {reading.Value:F2} mm/s";
                    }
                    else if (reading.Value > thresholds.VibrationWarning)
                    {
                        level = AlertLevel.Warning;
                        message = $"High vibration: {reading.Value:F2} mm/s";
                    }
                    break;

                case SensorType.Noise:
                    if (reading.Value > thresholds.NoiseCritical)
                    {
                        level = AlertLevel.Critical;
                        message = $"Dangerous noise level: {reading.Value:F0} dB";
                    }
                    else if (reading.Value > thresholds.NoiseWarning)
                    {
                        level = AlertLevel.Warning;
                        message = $"High noise level: {reading.Value:F0} dB";
                    }
                    break;

                case SensorType.CO2:
                    if (reading.Value > thresholds.CO2Critical)
                    {
                        level = AlertLevel.Critical;
                        message = $"Critical CO2 level: {reading.Value:F0} ppm";
                    }
                    else if (reading.Value > thresholds.CO2Warning)
                    {
                        level = AlertLevel.Warning;
                        message = $"High CO2 level: {reading.Value:F0} ppm";
                    }
                    break;

                case SensorType.VOC:
                    if (reading.Value > thresholds.VOCCritical)
                    {
                        level = AlertLevel.Critical;
                        message = $"Critical VOC level: {reading.Value:F2} ppm";
                    }
                    else if (reading.Value > thresholds.VOCWarning)
                    {
                        level = AlertLevel.Warning;
                        message = $"High VOC level: {reading.Value:F2} ppm";
                    }
                    break;

                case SensorType.Particulate:
                    if (reading.Value > thresholds.ParticulateCritical)
                    {
                        level = AlertLevel.Critical;
                        message = $"Critical particulate level: {reading.Value:F0} µg/m³";
                    }
                    else if (reading.Value > thresholds.ParticulateWarning)
                    {
                        level = AlertLevel.Warning;
                        message = $"High particulate level: {reading.Value:F0} µg/m³";
                    }
                    break;

                case SensorType.Lighting:
                    if (reading.Value < thresholds.LightingMin)
                    {
                        level = AlertLevel.Info;
                        message = $"Low lighting: {reading.Value:F0} lux";
                    }
                    else if (reading.Value > thresholds.LightingMax)
                    {
                        level = AlertLevel.Info;
                        message = $"High lighting: {reading.Value:F0} lux";
                    }
                    break;
            }

            if (level != AlertLevel.None && message != null)
            {
                RaiseAlert(sensor, level, message, reading.Value);
            }
            else
            {
                // Clear any existing alerts for this sensor
                ClearAlertForSensor(sensor.SensorId);
            }
        }

        private void RaiseAlert(EnvironmentalSensor sensor, AlertLevel level, string message, float value)
        {
            // Check if alert already exists
            var existing = activeAlerts.FirstOrDefault(a =>
                a.SensorId == sensor.SensorId && a.AlertLevel >= level);

            if (existing != null)
            {
                // Update existing alert
                existing.Value = value;
                existing.LastUpdate = DateTime.UtcNow;
                existing.OccurrenceCount++;
                return;
            }

            var alert = new EnvironmentalAlert
            {
                AlertId = Guid.NewGuid().ToString(),
                SensorId = sensor.SensorId,
                SensorName = sensor.Name,
                SensorType = sensor.Type,
                ZoneId = sensor.ZoneId,
                AlertLevel = level,
                Message = message,
                Value = value,
                Unit = sensor.Unit,
                Timestamp = DateTime.UtcNow,
                LastUpdate = DateTime.UtcNow,
                OccurrenceCount = 1,
                IsActive = true
            };

            activeAlerts.Add(alert);
            OnAlertRaised?.Invoke(alert);

            Debug.LogWarning($"[EnvHub] Alert: {message}");
        }

        private void ClearAlertForSensor(string sensorId)
        {
            var alert = activeAlerts.FirstOrDefault(a => a.SensorId == sensorId);
            if (alert != null)
            {
                alert.IsActive = false;
                alert.ClearedAt = DateTime.UtcNow;
                activeAlerts.Remove(alert);
                alertHistory.Add(alert);

                OnAlertCleared?.Invoke(alert);
            }
        }

        public void AcknowledgeAlert(string alertId, string acknowledgedBy = null)
        {
            var alert = activeAlerts.FirstOrDefault(a => a.AlertId == alertId);
            if (alert != null)
            {
                alert.AcknowledgedAt = DateTime.UtcNow;
                alert.AcknowledgedBy = acknowledgedBy;
            }
        }

        public List<EnvironmentalAlert> GetActiveAlerts(AlertLevel? minLevel = null)
        {
            var query = activeAlerts.AsEnumerable();
            if (minLevel.HasValue)
            {
                query = query.Where(a => a.AlertLevel >= minLevel.Value);
            }
            return query.OrderByDescending(a => a.AlertLevel).ToList();
        }

        #endregion

        #region Data Access

        public SensorReading GetLatestReading(string sensorId)
        {
            return latestReadings.TryGetValue(sensorId, out var reading) ? reading : null;
        }

        public List<SensorReading> GetReadingHistory(string sensorId, DateTime? start = null, DateTime? end = null)
        {
            if (!readingsHistory.TryGetValue(sensorId, out var history))
                return new List<SensorReading>();

            var query = history.AsEnumerable();
            if (start.HasValue)
                query = query.Where(r => r.Timestamp >= start.Value);
            if (end.HasValue)
                query = query.Where(r => r.Timestamp <= end.Value);

            return query.ToList();
        }

        public Dictionary<string, float> GetAllLatestReadings()
        {
            return latestReadings.ToDictionary(
                kvp => kvp.Key,
                kvp => kvp.Value.Value
            );
        }

        #endregion

        #region Statistics

        public EnvironmentalStats GetStatistics()
        {
            return new EnvironmentalStats
            {
                TotalSensors = sensors.Count,
                OnlineSensors = sensors.Values.Count(s => s.Status == SensorStatus.Online),
                OfflineSensors = sensors.Values.Count(s => s.Status == SensorStatus.Offline),
                TotalZones = zones.Count,
                CompliantZones = zoneConditions.Values.Count(z => z.IsCompliant),
                ActiveAlerts = activeAlerts.Count,
                CriticalAlerts = activeAlerts.Count(a => a.AlertLevel == AlertLevel.Critical),
                WarningAlerts = activeAlerts.Count(a => a.AlertLevel == AlertLevel.Warning),
                AverageComfortIndex = zoneConditions.Values.Any() ?
                    zoneConditions.Values.Average(z => z.ComfortIndex) : 0,
                SensorsByType = sensors.Values.GroupBy(s => s.Type)
                    .ToDictionary(g => g.Key, g => g.Count())
            };
        }

        public int SensorCount => sensors.Count;

        #endregion
    }

    #region Enums

    public enum SensorType
    {
        Temperature,
        Humidity,
        Pressure,
        Vibration,
        Noise,
        Lighting,
        CO2,
        VOC,
        Particulate,
        AirVelocity,
        DewPoint,
        Power,
        Current,
        Voltage
    }

    public enum SensorStatus
    {
        Online,
        Offline,
        Error,
        Calibrating,
        Maintenance
    }

    public enum ZoneType
    {
        Production,
        Metrology,
        Assembly,
        Storage,
        Office,
        DataCenter,
        Cleanroom,
        Outdoor
    }

    public enum AlertLevel
    {
        None = 0,
        Info = 1,
        Warning = 2,
        Critical = 3
    }

    public enum DataQuality
    {
        Good,
        Uncertain,
        Bad,
        Stale
    }

    #endregion

    #region Data Classes

    [System.Serializable]
    public class EnvironmentalThresholds
    {
        public float TemperatureMin;
        public float TemperatureMax;
        public float TemperatureCriticalMin;
        public float TemperatureCriticalMax;

        public float HumidityMin;
        public float HumidityMax;
        public float HumidityCriticalMin;
        public float HumidityCriticalMax;

        public float VibrationWarning;
        public float VibrationCritical;

        public float CO2Warning;
        public float CO2Critical;
        public float VOCWarning;
        public float VOCCritical;
        public float ParticulateWarning;
        public float ParticulateCritical;

        public float NoiseWarning;
        public float NoiseCritical;

        public float LightingMin;
        public float LightingMax;

        public float PressureMin;
        public float PressureMax;
    }

    [System.Serializable]
    public class EnvironmentalSensor
    {
        public string SensorId;
        public string Name;
        public SensorType Type;
        public string ZoneId;
        public Vector3 Position;
        public string Unit;
        public float SampleRate;
        public float CalibrationFactor;
        public float Offset;
        public SensorStatus Status;
        public DateTime LastReading;
        public float LastValue;
    }

    [System.Serializable]
    public class SensorConfig
    {
        public string SensorId;
        public string Name;
        public SensorType Type;
        public string ZoneId;
        public Vector3 Position;
        public float SampleRate;
        public float CalibrationFactor;
        public float Offset;
    }

    [System.Serializable]
    public class SensorReading
    {
        public string SensorId;
        public DateTime Timestamp;
        public float RawValue;
        public float Value;
        public string Unit;
        public DataQuality Quality;
    }

    [System.Serializable]
    public class Zone
    {
        public string ZoneId;
        public string Name;
        public ZoneType ZoneType;
        public Bounds Bounds;
        public RequiredConditions RequiredConditions;
        public List<string> SensorIds;
        public bool IsMonitored;
    }

    [System.Serializable]
    public class ZoneConfig
    {
        public string ZoneId;
        public string Name;
        public ZoneType ZoneType;
        public Bounds Bounds;
        public RequiredConditions RequiredConditions;
    }

    [System.Serializable]
    public class RequiredConditions
    {
        public float MinTemperature;
        public float MaxTemperature;
        public float TemperatureTolerance;
        public float MinHumidity;
        public float MaxHumidity;
        public float MaxVibration;
        public float MinLighting;
        public float MaxNoise;
        public float MaxCO2;
        public float MaxParticulate;
    }

    [System.Serializable]
    public class ZoneConditions
    {
        public string ZoneId;
        public DateTime Timestamp;
        public float Temperature;
        public float Humidity;
        public float Vibration;
        public float NoiseLevel;
        public float LightLevel;
        public float CO2Level;
        public float VOCLevel;
        public float ParticulateLevel;
        public float ComfortIndex;
        public int AirQualityIndex;
        public bool IsCompliant;
    }

    [System.Serializable]
    public class EnvironmentalAlert
    {
        public string AlertId;
        public string SensorId;
        public string SensorName;
        public SensorType SensorType;
        public string ZoneId;
        public AlertLevel AlertLevel;
        public string Message;
        public float Value;
        public string Unit;
        public DateTime Timestamp;
        public DateTime LastUpdate;
        public DateTime? AcknowledgedAt;
        public string AcknowledgedBy;
        public DateTime? ClearedAt;
        public int OccurrenceCount;
        public bool IsActive;
    }

    [System.Serializable]
    public class EnvironmentalStats
    {
        public int TotalSensors;
        public int OnlineSensors;
        public int OfflineSensors;
        public int TotalZones;
        public int CompliantZones;
        public int ActiveAlerts;
        public int CriticalAlerts;
        public int WarningAlerts;
        public float AverageComfortIndex;
        public Dictionary<SensorType, int> SensorsByType;
    }

    #endregion
}
