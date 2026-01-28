using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCDigitalTwin.Historian
{
    /// <summary>
    /// Industrial Data Historian Service
    /// Time-series data storage, compression, and retrieval for SCADA/DCS systems
    /// </summary>
    public class DataHistorianService : MonoBehaviour
    {
        public static DataHistorianService Instance { get; private set; }

        [Header("Configuration")]
        [SerializeField] private float collectionInterval = 1.0f; // seconds
        [SerializeField] private int maxPointsInMemory = 100000;
        [SerializeField] private float compressionDeadband = 0.5f; // percentage
        [SerializeField] private bool enableCompression = true;
        [SerializeField] private int archiveRetentionDays = 365;

        // Tag definitions
        private Dictionary<string, TagDefinition> tagDefinitions = new Dictionary<string, TagDefinition>();

        // Real-time cache (last values)
        private Dictionary<string, TagValue> realtimeCache = new Dictionary<string, TagValue>();

        // Time-series data storage
        private Dictionary<string, List<HistoricalPoint>> historicalData = new Dictionary<string, List<HistoricalPoint>>();

        // Archive partitions (by date)
        private Dictionary<DateTime, ArchivePartition> archivePartitions = new Dictionary<DateTime, ArchivePartition>();

        // Compression state
        private Dictionary<string, CompressionState> compressionStates = new Dictionary<string, CompressionState>();

        // Calculated tags
        private Dictionary<string, CalculatedTag> calculatedTags = new Dictionary<string, CalculatedTag>();

        // Statistics
        private HistorianStatistics statistics = new HistorianStatistics();

        // Events
        public event Action<string, TagValue> OnTagValueChanged;
        public event Action<string, List<HistoricalPoint>> OnDataArchived;
        public event Action<string> OnTagCreated;

        #region Data Structures

        [System.Serializable]
        public class TagDefinition
        {
            public string tagId;
            public string name;
            public string description;
            public string unit;
            public TagDataType dataType;
            public TagType tagType;

            // Engineering units
            public float euLow;
            public float euHigh;
            public float rawLow;
            public float rawHigh;

            // Collection settings
            public float scanRate; // seconds
            public CompressionMethod compressionMethod;
            public float compressionDeviation;
            public float compressionTimeout;

            // Alarming
            public float alarmHigh;
            public float alarmLow;
            public float warningHigh;
            public float warningLow;

            // Metadata
            public string sourceSystem;
            public string equipmentId;
            public string areaId;
            public Dictionary<string, string> attributes;
            public DateTime createdAt;
            public DateTime lastModified;
            public bool isEnabled;
        }

        public enum TagDataType
        {
            Float,
            Double,
            Int16,
            Int32,
            Int64,
            Boolean,
            String,
            DateTime
        }

        public enum TagType
        {
            Analog,
            Digital,
            String,
            Calculated,
            Manual
        }

        public enum CompressionMethod
        {
            None,
            SwingingDoor,  // Most common for process data
            BoxcarBackslope,
            DeadbandCompression,
            ExceptionBased
        }

        [System.Serializable]
        public class TagValue
        {
            public string tagId;
            public object value;
            public DateTime timestamp;
            public QualityStatus quality;
            public bool isStale;
            public string annotation;
        }

        public enum QualityStatus
        {
            Good = 0,
            Uncertain = 1,
            Bad = 2,
            ConfigurationError = 3,
            NotConnected = 4,
            DeviceFailure = 5,
            SensorFailure = 6,
            OutOfRange = 7,
            Substituted = 8,
            Manual = 9
        }

        [System.Serializable]
        public class HistoricalPoint
        {
            public DateTime timestamp;
            public float value;
            public QualityStatus quality;
            public PointType pointType;
            public bool isCompressed;
        }

        public enum PointType
        {
            Raw,
            Interpolated,
            Average,
            Min,
            Max,
            Delta,
            StdDev,
            Count,
            StartOfDay,
            EndOfDay
        }

        [System.Serializable]
        public class CompressionState
        {
            public string tagId;
            public float lastStoredValue;
            public DateTime lastStoredTime;
            public float archiveValue;
            public DateTime archiveTime;
            public float snapValue;
            public DateTime snapTime;
            public float slope;
            public bool heldValue;
        }

        [System.Serializable]
        public class ArchivePartition
        {
            public DateTime date;
            public Dictionary<string, List<HistoricalPoint>> data;
            public int totalPoints;
            public long sizeBytes;
            public bool isCompressed;
            public DateTime createdAt;
        }

        [System.Serializable]
        public class CalculatedTag
        {
            public string tagId;
            public string name;
            public string expression;
            public string[] sourceTags;
            public CalculationType calculationType;
            public float calculationPeriod; // seconds
            public DateTime lastCalculation;
        }

        public enum CalculationType
        {
            Expression,
            Average,
            Sum,
            Min,
            Max,
            Delta,
            RateOfChange,
            RunningTotal,
            StandardDeviation
        }

        [System.Serializable]
        public class TimeSeriesQuery
        {
            public string[] tagIds;
            public DateTime startTime;
            public DateTime endTime;
            public RetrievalMode retrievalMode;
            public int? maxPoints;
            public TimeSpan? interval;
            public bool includeAnnotations;
        }

        public enum RetrievalMode
        {
            Raw,
            Interpolated,
            Average,
            Min,
            Max,
            Delta,
            Count,
            StdDev,
            Range,
            PlotValues
        }

        [System.Serializable]
        public class TimeSeriesResult
        {
            public string tagId;
            public string tagName;
            public string unit;
            public List<HistoricalPoint> points;
            public float? minValue;
            public float? maxValue;
            public float? avgValue;
            public int pointCount;
            public DateTime queryStart;
            public DateTime queryEnd;
        }

        [System.Serializable]
        public class HistorianStatistics
        {
            public int totalTags;
            public int enabledTags;
            public int totalPointsInMemory;
            public int totalPointsArchived;
            public int pointsPerSecond;
            public int compressedPoints;
            public float compressionRatio;
            public long memorySizeBytes;
            public long archiveSizeBytes;
            public DateTime oldestData;
            public DateTime newestData;
            public int queryCount;
            public float averageQueryTimeMs;
        }

        #endregion

        #region Unity Lifecycle

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
            InitializeHistorian();
            StartCoroutine(CollectionLoop());
            StartCoroutine(CalculationLoop());
            StartCoroutine(ArchiveMaintenanceLoop());
        }

        private void OnDestroy()
        {
            StopAllCoroutines();
        }

        #endregion

        #region Initialization

        private void InitializeHistorian()
        {
            Debug.Log("[Historian] Initializing Data Historian Service");

            // Create default CNC machine tags
            CreateDefaultTags();

            statistics.oldestData = DateTime.Now;
            statistics.newestData = DateTime.Now;

            Debug.Log($"[Historian] Initialized with {tagDefinitions.Count} tags");
        }

        private void CreateDefaultTags()
        {
            // Spindle tags
            CreateAnalogTag("SPINDLE.SPEED", "Spindle Speed", "RPM", 0, 24000,
                scanRate: 0.1f, compressionDev: 10f);
            CreateAnalogTag("SPINDLE.LOAD", "Spindle Load", "%", 0, 150,
                scanRate: 0.1f, compressionDev: 1f);
            CreateAnalogTag("SPINDLE.TEMP", "Spindle Temperature", "°C", 0, 100,
                scanRate: 1f, compressionDev: 0.5f);
            CreateAnalogTag("SPINDLE.VIBRATION", "Spindle Vibration", "mm/s", 0, 20,
                scanRate: 0.1f, compressionDev: 0.1f);
            CreateAnalogTag("SPINDLE.POWER", "Spindle Power", "kW", 0, 50,
                scanRate: 0.5f, compressionDev: 0.5f);

            // Axis position tags
            CreateAnalogTag("AXIS.X.POSITION", "X Axis Position", "mm", -1000, 1000,
                scanRate: 0.05f, compressionDev: 0.001f);
            CreateAnalogTag("AXIS.Y.POSITION", "Y Axis Position", "mm", -1000, 1000,
                scanRate: 0.05f, compressionDev: 0.001f);
            CreateAnalogTag("AXIS.Z.POSITION", "Z Axis Position", "mm", -500, 500,
                scanRate: 0.05f, compressionDev: 0.001f);
            CreateAnalogTag("AXIS.A.POSITION", "A Axis Position", "deg", -360, 360,
                scanRate: 0.05f, compressionDev: 0.01f);
            CreateAnalogTag("AXIS.B.POSITION", "B Axis Position", "deg", -120, 120,
                scanRate: 0.05f, compressionDev: 0.01f);

            // Feed and velocity tags
            CreateAnalogTag("FEED.RATE", "Feed Rate", "mm/min", 0, 30000,
                scanRate: 0.1f, compressionDev: 10f);
            CreateAnalogTag("FEED.OVERRIDE", "Feed Override", "%", 0, 200,
                scanRate: 0.5f, compressionDev: 1f);
            CreateAnalogTag("RAPID.OVERRIDE", "Rapid Override", "%", 0, 100,
                scanRate: 0.5f, compressionDev: 1f);

            // Coolant system tags
            CreateAnalogTag("COOLANT.PRESSURE", "Coolant Pressure", "bar", 0, 100,
                scanRate: 1f, compressionDev: 0.5f);
            CreateAnalogTag("COOLANT.FLOW", "Coolant Flow", "L/min", 0, 50,
                scanRate: 1f, compressionDev: 0.5f);
            CreateAnalogTag("COOLANT.TEMP", "Coolant Temperature", "°C", 0, 50,
                scanRate: 5f, compressionDev: 0.2f);
            CreateAnalogTag("COOLANT.LEVEL", "Coolant Level", "%", 0, 100,
                scanRate: 10f, compressionDev: 1f);

            // Hydraulic system tags
            CreateAnalogTag("HYDRAULIC.PRESSURE", "Hydraulic Pressure", "bar", 0, 300,
                scanRate: 1f, compressionDev: 1f);
            CreateAnalogTag("HYDRAULIC.TEMP", "Hydraulic Temperature", "°C", 0, 80,
                scanRate: 5f, compressionDev: 0.5f);

            // Power and energy tags
            CreateAnalogTag("POWER.TOTAL", "Total Power", "kW", 0, 100,
                scanRate: 1f, compressionDev: 0.5f);
            CreateAnalogTag("ENERGY.DAILY", "Daily Energy", "kWh", 0, 1000,
                scanRate: 60f, compressionDev: 1f);

            // Environmental tags
            CreateAnalogTag("AMBIENT.TEMP", "Ambient Temperature", "°C", 10, 40,
                scanRate: 60f, compressionDev: 0.2f);
            CreateAnalogTag("AMBIENT.HUMIDITY", "Ambient Humidity", "%", 20, 80,
                scanRate: 60f, compressionDev: 1f);

            // Digital status tags
            CreateDigitalTag("STATUS.RUNNING", "Machine Running");
            CreateDigitalTag("STATUS.ALARM", "Alarm Active");
            CreateDigitalTag("STATUS.ESTOP", "E-Stop Active");
            CreateDigitalTag("STATUS.DOOR_CLOSED", "Door Closed");
            CreateDigitalTag("STATUS.COOLANT_ON", "Coolant Active");
            CreateDigitalTag("STATUS.SPINDLE_ON", "Spindle Active");

            // Production tags
            CreateAnalogTag("PROD.PART_COUNT", "Part Count", "pcs", 0, 999999,
                scanRate: 1f, compressionDev: 0.5f);
            CreateAnalogTag("PROD.CYCLE_TIME", "Cycle Time", "sec", 0, 3600,
                scanRate: 1f, compressionDev: 1f);
            CreateAnalogTag("PROD.OEE", "OEE", "%", 0, 100,
                scanRate: 60f, compressionDev: 0.5f);

            // Quality tags
            CreateAnalogTag("QUALITY.CPK", "Process Capability", "", 0, 3,
                scanRate: 60f, compressionDev: 0.01f);
            CreateAnalogTag("QUALITY.REJECT_RATE", "Reject Rate", "%", 0, 100,
                scanRate: 60f, compressionDev: 0.1f);

            // Tool tags
            CreateAnalogTag("TOOL.NUMBER", "Tool Number", "", 0, 99,
                scanRate: 1f, compressionDev: 0.5f);
            CreateAnalogTag("TOOL.WEAR", "Tool Wear", "%", 0, 100,
                scanRate: 60f, compressionDev: 1f);
            CreateAnalogTag("TOOL.LIFE_REMAINING", "Tool Life Remaining", "min", 0, 1000,
                scanRate: 60f, compressionDev: 1f);

            // Create calculated tags
            CreateCalculatedTag("CALC.POWER_EFFICIENCY", "Power Efficiency",
                CalculationType.Expression, "SPINDLE.POWER / POWER.TOTAL * 100",
                new[] { "SPINDLE.POWER", "POWER.TOTAL" }, 60f);

            CreateCalculatedTag("CALC.AVG_SPINDLE_LOAD", "Average Spindle Load (1hr)",
                CalculationType.Average, null,
                new[] { "SPINDLE.LOAD" }, 3600f);
        }

        public void CreateAnalogTag(string tagId, string name, string unit,
            float euLow, float euHigh, float scanRate = 1f, float compressionDev = 1f)
        {
            var tag = new TagDefinition
            {
                tagId = tagId,
                name = name,
                description = $"Analog tag: {name}",
                unit = unit,
                dataType = TagDataType.Float,
                tagType = TagType.Analog,
                euLow = euLow,
                euHigh = euHigh,
                rawLow = 0,
                rawHigh = 65535,
                scanRate = scanRate,
                compressionMethod = CompressionMethod.SwingingDoor,
                compressionDeviation = compressionDev,
                compressionTimeout = 300f, // 5 minutes
                isEnabled = true,
                createdAt = DateTime.Now,
                lastModified = DateTime.Now,
                attributes = new Dictionary<string, string>()
            };

            tagDefinitions[tagId] = tag;
            historicalData[tagId] = new List<HistoricalPoint>();
            compressionStates[tagId] = new CompressionState { tagId = tagId };

            statistics.totalTags++;
            statistics.enabledTags++;

            OnTagCreated?.Invoke(tagId);
        }

        public void CreateDigitalTag(string tagId, string name)
        {
            var tag = new TagDefinition
            {
                tagId = tagId,
                name = name,
                description = $"Digital tag: {name}",
                unit = "",
                dataType = TagDataType.Boolean,
                tagType = TagType.Digital,
                euLow = 0,
                euHigh = 1,
                scanRate = 0.5f,
                compressionMethod = CompressionMethod.ExceptionBased,
                compressionDeviation = 0,
                isEnabled = true,
                createdAt = DateTime.Now,
                lastModified = DateTime.Now,
                attributes = new Dictionary<string, string>()
            };

            tagDefinitions[tagId] = tag;
            historicalData[tagId] = new List<HistoricalPoint>();
            compressionStates[tagId] = new CompressionState { tagId = tagId };

            statistics.totalTags++;
            statistics.enabledTags++;

            OnTagCreated?.Invoke(tagId);
        }

        public void CreateCalculatedTag(string tagId, string name, CalculationType calcType,
            string expression, string[] sourceTags, float period)
        {
            var calcTag = new CalculatedTag
            {
                tagId = tagId,
                name = name,
                calculationType = calcType,
                expression = expression,
                sourceTags = sourceTags,
                calculationPeriod = period,
                lastCalculation = DateTime.MinValue
            };

            calculatedTags[tagId] = calcTag;

            // Also create the tag definition
            var tag = new TagDefinition
            {
                tagId = tagId,
                name = name,
                description = $"Calculated tag: {name}",
                dataType = TagDataType.Float,
                tagType = TagType.Calculated,
                scanRate = period,
                compressionMethod = CompressionMethod.SwingingDoor,
                compressionDeviation = 0.5f,
                isEnabled = true,
                createdAt = DateTime.Now,
                lastModified = DateTime.Now
            };

            tagDefinitions[tagId] = tag;
            historicalData[tagId] = new List<HistoricalPoint>();

            statistics.totalTags++;
            statistics.enabledTags++;
        }

        #endregion

        #region Data Collection

        private IEnumerator CollectionLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(collectionInterval);
                // Collection is primarily event-driven via RecordValue
            }
        }

        public void RecordValue(string tagId, float value, QualityStatus quality = QualityStatus.Good,
            DateTime? timestamp = null)
        {
            if (!tagDefinitions.TryGetValue(tagId, out var definition))
            {
                Debug.LogWarning($"[Historian] Unknown tag: {tagId}");
                return;
            }

            var time = timestamp ?? DateTime.Now;

            // Update realtime cache
            var tagValue = new TagValue
            {
                tagId = tagId,
                value = value,
                timestamp = time,
                quality = quality,
                isStale = false
            };

            realtimeCache[tagId] = tagValue;
            OnTagValueChanged?.Invoke(tagId, tagValue);

            // Apply compression
            bool shouldStore = true;

            if (enableCompression && definition.compressionMethod != CompressionMethod.None)
            {
                shouldStore = ApplyCompression(tagId, value, time, definition);
            }

            if (shouldStore)
            {
                StoreHistoricalPoint(tagId, value, time, quality, false);
            }
        }

        public void RecordDigitalValue(string tagId, bool value, DateTime? timestamp = null)
        {
            RecordValue(tagId, value ? 1f : 0f, QualityStatus.Good, timestamp);
        }

        public void RecordValues(Dictionary<string, float> values, DateTime? timestamp = null)
        {
            var time = timestamp ?? DateTime.Now;

            foreach (var kvp in values)
            {
                RecordValue(kvp.Key, kvp.Value, QualityStatus.Good, time);
            }
        }

        private void StoreHistoricalPoint(string tagId, float value, DateTime timestamp,
            QualityStatus quality, bool isCompressed)
        {
            if (!historicalData.TryGetValue(tagId, out var points))
            {
                points = new List<HistoricalPoint>();
                historicalData[tagId] = points;
            }

            var point = new HistoricalPoint
            {
                timestamp = timestamp,
                value = value,
                quality = quality,
                pointType = PointType.Raw,
                isCompressed = isCompressed
            };

            points.Add(point);
            statistics.totalPointsInMemory++;

            if (timestamp > statistics.newestData)
                statistics.newestData = timestamp;

            // Trim in-memory data
            while (points.Count > maxPointsInMemory / tagDefinitions.Count)
            {
                // Archive old data
                ArchiveOldData(tagId, points);
            }
        }

        #endregion

        #region Compression (Swinging Door Algorithm)

        private bool ApplyCompression(string tagId, float value, DateTime timestamp, TagDefinition definition)
        {
            if (!compressionStates.TryGetValue(tagId, out var state))
            {
                state = new CompressionState { tagId = tagId };
                compressionStates[tagId] = state;
            }

            // First value always stored
            if (state.lastStoredTime == default)
            {
                state.lastStoredValue = value;
                state.lastStoredTime = timestamp;
                state.archiveValue = value;
                state.archiveTime = timestamp;
                state.snapValue = value;
                state.snapTime = timestamp;
                return true;
            }

            float deviation = definition.compressionDeviation;
            float timeDiff = (float)(timestamp - state.lastStoredTime).TotalSeconds;

            // Check timeout
            if (timeDiff >= definition.compressionTimeout)
            {
                // Store held value if any, then current value
                if (state.heldValue)
                {
                    StoreHistoricalPoint(tagId, state.snapValue, state.snapTime,
                        QualityStatus.Good, true);
                    statistics.compressedPoints++;
                }

                state.lastStoredValue = value;
                state.lastStoredTime = timestamp;
                state.archiveValue = value;
                state.archiveTime = timestamp;
                state.heldValue = false;
                return true;
            }

            // Swinging Door algorithm
            float upperSlope = (value + deviation - state.archiveValue) /
                              (float)(timestamp - state.archiveTime).TotalSeconds;
            float lowerSlope = (value - deviation - state.archiveValue) /
                              (float)(timestamp - state.archiveTime).TotalSeconds;

            // Check if current point is within the door
            float projectedValue = state.archiveValue + state.slope *
                                  (float)(timestamp - state.archiveTime).TotalSeconds;

            if (Mathf.Abs(value - projectedValue) <= deviation)
            {
                // Point within tolerance - can be compressed
                state.snapValue = value;
                state.snapTime = timestamp;
                state.heldValue = true;

                // Update slope bounds
                if (upperSlope < state.slope)
                    state.slope = (state.slope + upperSlope) / 2;
                if (lowerSlope > state.slope)
                    state.slope = (state.slope + lowerSlope) / 2;

                return false; // Don't store
            }
            else
            {
                // Point outside tolerance - store held value and reset
                if (state.heldValue)
                {
                    StoreHistoricalPoint(tagId, state.snapValue, state.snapTime,
                        QualityStatus.Good, true);
                    statistics.compressedPoints++;
                }

                state.archiveValue = state.snapValue;
                state.archiveTime = state.snapTime;
                state.lastStoredValue = value;
                state.lastStoredTime = timestamp;
                state.slope = (value - state.archiveValue) /
                             (float)(timestamp - state.archiveTime).TotalSeconds;
                state.heldValue = false;

                return true;
            }
        }

        #endregion

        #region Calculated Tags

        private IEnumerator CalculationLoop()
        {
            while (true)
            {
                var now = DateTime.Now;

                foreach (var kvp in calculatedTags)
                {
                    var calc = kvp.Value;

                    if ((now - calc.lastCalculation).TotalSeconds >= calc.calculationPeriod)
                    {
                        float result = CalculateTag(calc);
                        RecordValue(calc.tagId, result, QualityStatus.Good, now);
                        calc.lastCalculation = now;
                    }
                }

                yield return new WaitForSeconds(1f);
            }
        }

        private float CalculateTag(CalculatedTag calc)
        {
            switch (calc.calculationType)
            {
                case CalculationType.Average:
                    return CalculateAverage(calc.sourceTags[0], calc.calculationPeriod);

                case CalculationType.Sum:
                    return CalculateSum(calc.sourceTags);

                case CalculationType.Min:
                    return CalculateMin(calc.sourceTags[0], calc.calculationPeriod);

                case CalculationType.Max:
                    return CalculateMax(calc.sourceTags[0], calc.calculationPeriod);

                case CalculationType.Delta:
                    return CalculateDelta(calc.sourceTags[0], calc.calculationPeriod);

                case CalculationType.RateOfChange:
                    return CalculateRateOfChange(calc.sourceTags[0], calc.calculationPeriod);

                case CalculationType.Expression:
                    return EvaluateExpression(calc.expression, calc.sourceTags);

                default:
                    return 0;
            }
        }

        private float CalculateAverage(string tagId, float periodSeconds)
        {
            var endTime = DateTime.Now;
            var startTime = endTime.AddSeconds(-periodSeconds);

            if (!historicalData.TryGetValue(tagId, out var points))
                return 0;

            var relevantPoints = points.Where(p => p.timestamp >= startTime && p.timestamp <= endTime).ToList();

            if (relevantPoints.Count == 0)
            {
                return realtimeCache.TryGetValue(tagId, out var current) ?
                    Convert.ToSingle(current.value) : 0;
            }

            return relevantPoints.Average(p => p.value);
        }

        private float CalculateSum(string[] tagIds)
        {
            float sum = 0;

            foreach (var tagId in tagIds)
            {
                if (realtimeCache.TryGetValue(tagId, out var value))
                {
                    sum += Convert.ToSingle(value.value);
                }
            }

            return sum;
        }

        private float CalculateMin(string tagId, float periodSeconds)
        {
            var endTime = DateTime.Now;
            var startTime = endTime.AddSeconds(-periodSeconds);

            if (!historicalData.TryGetValue(tagId, out var points))
                return 0;

            var relevantPoints = points.Where(p => p.timestamp >= startTime && p.timestamp <= endTime).ToList();

            return relevantPoints.Count > 0 ? relevantPoints.Min(p => p.value) : 0;
        }

        private float CalculateMax(string tagId, float periodSeconds)
        {
            var endTime = DateTime.Now;
            var startTime = endTime.AddSeconds(-periodSeconds);

            if (!historicalData.TryGetValue(tagId, out var points))
                return 0;

            var relevantPoints = points.Where(p => p.timestamp >= startTime && p.timestamp <= endTime).ToList();

            return relevantPoints.Count > 0 ? relevantPoints.Max(p => p.value) : 0;
        }

        private float CalculateDelta(string tagId, float periodSeconds)
        {
            var endTime = DateTime.Now;
            var startTime = endTime.AddSeconds(-periodSeconds);

            if (!historicalData.TryGetValue(tagId, out var points))
                return 0;

            var relevantPoints = points.Where(p => p.timestamp >= startTime && p.timestamp <= endTime)
                                       .OrderBy(p => p.timestamp).ToList();

            if (relevantPoints.Count < 2)
                return 0;

            return relevantPoints.Last().value - relevantPoints.First().value;
        }

        private float CalculateRateOfChange(string tagId, float periodSeconds)
        {
            float delta = CalculateDelta(tagId, periodSeconds);
            return delta / periodSeconds * 60f; // Per minute
        }

        private float EvaluateExpression(string expression, string[] sourceTags)
        {
            // Simple expression evaluator
            try
            {
                string evalExpr = expression;

                foreach (var tagId in sourceTags)
                {
                    if (realtimeCache.TryGetValue(tagId, out var value))
                    {
                        evalExpr = evalExpr.Replace(tagId, Convert.ToSingle(value.value).ToString());
                    }
                    else
                    {
                        evalExpr = evalExpr.Replace(tagId, "0");
                    }
                }

                // Basic evaluation (for production use a proper expression parser)
                if (evalExpr.Contains("/"))
                {
                    var parts = evalExpr.Split('/');
                    if (parts.Length == 2)
                    {
                        float a = float.Parse(parts[0].Trim());
                        float b = float.Parse(parts[1].Split('*')[0].Trim());
                        if (b != 0)
                        {
                            float result = a / b;
                            if (evalExpr.Contains("* 100"))
                                result *= 100;
                            return result;
                        }
                    }
                }

                return 0;
            }
            catch
            {
                return 0;
            }
        }

        #endregion

        #region Data Retrieval

        public TimeSeriesResult QueryData(TimeSeriesQuery query)
        {
            var startTime = DateTime.Now;
            statistics.queryCount++;

            if (query.tagIds == null || query.tagIds.Length == 0)
                return null;

            var tagId = query.tagIds[0]; // Single tag for now

            if (!tagDefinitions.TryGetValue(tagId, out var definition))
            {
                Debug.LogWarning($"[Historian] Unknown tag in query: {tagId}");
                return null;
            }

            var result = new TimeSeriesResult
            {
                tagId = tagId,
                tagName = definition.name,
                unit = definition.unit,
                queryStart = query.startTime,
                queryEnd = query.endTime,
                points = new List<HistoricalPoint>()
            };

            // Get from in-memory data
            if (historicalData.TryGetValue(tagId, out var memoryData))
            {
                var relevantPoints = memoryData
                    .Where(p => p.timestamp >= query.startTime && p.timestamp <= query.endTime)
                    .ToList();

                result.points.AddRange(relevantPoints);
            }

            // Get from archives
            var archiveStart = query.startTime.Date;
            var archiveEnd = query.endTime.Date;

            for (var date = archiveStart; date <= archiveEnd; date = date.AddDays(1))
            {
                if (archivePartitions.TryGetValue(date, out var partition))
                {
                    if (partition.data.TryGetValue(tagId, out var archivePoints))
                    {
                        var relevantArchive = archivePoints
                            .Where(p => p.timestamp >= query.startTime && p.timestamp <= query.endTime);
                        result.points.AddRange(relevantArchive);
                    }
                }
            }

            // Sort by timestamp
            result.points = result.points.OrderBy(p => p.timestamp).ToList();

            // Apply retrieval mode
            result.points = ApplyRetrievalMode(result.points, query);

            // Apply max points limit
            if (query.maxPoints.HasValue && result.points.Count > query.maxPoints.Value)
            {
                result.points = DownsamplePoints(result.points, query.maxPoints.Value);
            }

            // Calculate statistics
            if (result.points.Count > 0)
            {
                result.minValue = result.points.Min(p => p.value);
                result.maxValue = result.points.Max(p => p.value);
                result.avgValue = result.points.Average(p => p.value);
            }

            result.pointCount = result.points.Count;

            // Update query statistics
            var queryTime = (float)(DateTime.Now - startTime).TotalMilliseconds;
            statistics.averageQueryTimeMs = statistics.averageQueryTimeMs +
                (queryTime - statistics.averageQueryTimeMs) / statistics.queryCount;

            return result;
        }

        private List<HistoricalPoint> ApplyRetrievalMode(List<HistoricalPoint> points, TimeSeriesQuery query)
        {
            if (points.Count == 0 || query.retrievalMode == RetrievalMode.Raw)
                return points;

            if (!query.interval.HasValue)
                return points;

            var interval = query.interval.Value;
            var result = new List<HistoricalPoint>();
            var currentBucket = query.startTime;

            while (currentBucket < query.endTime)
            {
                var bucketEnd = currentBucket.Add(interval);
                var bucketPoints = points.Where(p => p.timestamp >= currentBucket && p.timestamp < bucketEnd).ToList();

                if (bucketPoints.Count > 0)
                {
                    float value = 0;
                    PointType pointType = PointType.Raw;

                    switch (query.retrievalMode)
                    {
                        case RetrievalMode.Average:
                            value = bucketPoints.Average(p => p.value);
                            pointType = PointType.Average;
                            break;
                        case RetrievalMode.Min:
                            value = bucketPoints.Min(p => p.value);
                            pointType = PointType.Min;
                            break;
                        case RetrievalMode.Max:
                            value = bucketPoints.Max(p => p.value);
                            pointType = PointType.Max;
                            break;
                        case RetrievalMode.Delta:
                            value = bucketPoints.Last().value - bucketPoints.First().value;
                            pointType = PointType.Delta;
                            break;
                        case RetrievalMode.Count:
                            value = bucketPoints.Count;
                            pointType = PointType.Count;
                            break;
                        case RetrievalMode.Interpolated:
                            // Linear interpolation at bucket midpoint
                            var midpoint = currentBucket.AddTicks(interval.Ticks / 2);
                            value = InterpolateValue(points, midpoint);
                            pointType = PointType.Interpolated;
                            break;
                    }

                    result.Add(new HistoricalPoint
                    {
                        timestamp = currentBucket,
                        value = value,
                        quality = QualityStatus.Good,
                        pointType = pointType
                    });
                }

                currentBucket = bucketEnd;
            }

            return result;
        }

        private float InterpolateValue(List<HistoricalPoint> points, DateTime targetTime)
        {
            var before = points.LastOrDefault(p => p.timestamp <= targetTime);
            var after = points.FirstOrDefault(p => p.timestamp > targetTime);

            if (before == null && after == null)
                return 0;
            if (before == null)
                return after.value;
            if (after == null)
                return before.value;

            // Linear interpolation
            var totalTime = (after.timestamp - before.timestamp).TotalSeconds;
            var elapsed = (targetTime - before.timestamp).TotalSeconds;

            if (totalTime == 0)
                return before.value;

            return before.value + (after.value - before.value) * (float)(elapsed / totalTime);
        }

        private List<HistoricalPoint> DownsamplePoints(List<HistoricalPoint> points, int targetCount)
        {
            if (points.Count <= targetCount)
                return points;

            // Largest-Triangle-Three-Buckets algorithm
            var result = new List<HistoricalPoint>();
            int bucketSize = (points.Count - 2) / (targetCount - 2);

            result.Add(points[0]); // Always include first

            for (int i = 0; i < targetCount - 2; i++)
            {
                int rangeStart = (int)(i * bucketSize) + 1;
                int rangeEnd = Math.Min((int)((i + 1) * bucketSize) + 1, points.Count - 1);

                // Find point with largest triangle area
                float maxArea = -1;
                int maxIndex = rangeStart;

                var prevPoint = result.Last();
                var avgNext = rangeEnd < points.Count - 1 ?
                    points.Skip(rangeEnd).Take(bucketSize).Average(p => p.value) :
                    points.Last().value;

                for (int j = rangeStart; j < rangeEnd; j++)
                {
                    float area = Math.Abs(
                        (prevPoint.timestamp.Ticks - points[j].timestamp.Ticks) * (avgNext - prevPoint.value) -
                        (prevPoint.timestamp.Ticks - points[j].timestamp.Ticks) * (points[j].value - prevPoint.value)
                    ) / 2;

                    if (area > maxArea)
                    {
                        maxArea = area;
                        maxIndex = j;
                    }
                }

                result.Add(points[maxIndex]);
            }

            result.Add(points.Last()); // Always include last

            return result;
        }

        public TagValue GetCurrentValue(string tagId)
        {
            return realtimeCache.TryGetValue(tagId, out var value) ? value : null;
        }

        public Dictionary<string, TagValue> GetCurrentValues(string[] tagIds = null)
        {
            if (tagIds == null)
                return new Dictionary<string, TagValue>(realtimeCache);

            return realtimeCache
                .Where(kvp => tagIds.Contains(kvp.Key))
                .ToDictionary(kvp => kvp.Key, kvp => kvp.Value);
        }

        #endregion

        #region Archiving

        private void ArchiveOldData(string tagId, List<HistoricalPoint> points)
        {
            if (points.Count < 100)
                return;

            // Archive oldest 10%
            int archiveCount = points.Count / 10;
            var toArchive = points.Take(archiveCount).ToList();

            if (toArchive.Count == 0)
                return;

            var date = toArchive[0].timestamp.Date;

            if (!archivePartitions.TryGetValue(date, out var partition))
            {
                partition = new ArchivePartition
                {
                    date = date,
                    data = new Dictionary<string, List<HistoricalPoint>>(),
                    createdAt = DateTime.Now
                };
                archivePartitions[date] = partition;
            }

            if (!partition.data.ContainsKey(tagId))
            {
                partition.data[tagId] = new List<HistoricalPoint>();
            }

            partition.data[tagId].AddRange(toArchive);
            partition.totalPoints += toArchive.Count;

            // Remove from memory
            points.RemoveRange(0, archiveCount);
            statistics.totalPointsInMemory -= archiveCount;
            statistics.totalPointsArchived += archiveCount;

            OnDataArchived?.Invoke(tagId, toArchive);
        }

        private IEnumerator ArchiveMaintenanceLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(3600f); // Every hour

                // Clean old archives
                var cutoffDate = DateTime.Now.AddDays(-archiveRetentionDays).Date;
                var oldPartitions = archivePartitions
                    .Where(kvp => kvp.Key < cutoffDate)
                    .Select(kvp => kvp.Key)
                    .ToList();

                foreach (var date in oldPartitions)
                {
                    var partition = archivePartitions[date];
                    statistics.totalPointsArchived -= partition.totalPoints;
                    archivePartitions.Remove(date);
                    Debug.Log($"[Historian] Removed archive partition: {date:yyyy-MM-dd}");
                }

                // Update compression ratio
                if (statistics.totalPointsArchived > 0)
                {
                    statistics.compressionRatio = 1f - ((float)statistics.compressedPoints /
                        (statistics.totalPointsInMemory + statistics.totalPointsArchived));
                }
            }
        }

        #endregion

        #region Statistics

        public HistorianStatistics GetStatistics()
        {
            return statistics;
        }

        public TagDefinition GetTagDefinition(string tagId)
        {
            return tagDefinitions.TryGetValue(tagId, out var def) ? def : null;
        }

        public List<TagDefinition> GetAllTags()
        {
            return tagDefinitions.Values.ToList();
        }

        public List<string> SearchTags(string pattern)
        {
            pattern = pattern.ToLower();
            return tagDefinitions.Keys
                .Where(k => k.ToLower().Contains(pattern) ||
                           tagDefinitions[k].name.ToLower().Contains(pattern))
                .ToList();
        }

        #endregion
    }
}
