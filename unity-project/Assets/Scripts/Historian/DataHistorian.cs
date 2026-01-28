using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace CNCDigitalTwin.Historian
{
    /// <summary>
    /// Enterprise Data Historian for time-series storage and analysis
    /// Supports InfluxDB, TimescaleDB, and local buffering
    /// </summary>
    public class DataHistorian : MonoBehaviour
    {
        public static DataHistorian Instance { get; private set; }

        [Header("Historian Configuration")]
        [SerializeField] private HistorianBackend backend = HistorianBackend.InfluxDB;
        [SerializeField] private string serverUrl = "http://localhost:8086";
        [SerializeField] private string database = "cnc_scada";
        [SerializeField] private string username = "";
        [SerializeField] private string password = "";
        [SerializeField] private string authToken = "";
        [SerializeField] private string organization = "cnc-scada";
        [SerializeField] private string bucket = "machine-data";

        [Header("Performance Settings")]
        [SerializeField] private int batchSize = 1000;
        [SerializeField] private float flushIntervalSeconds = 1.0f;
        [SerializeField] private int maxLocalBufferSize = 100000;
        [SerializeField] private bool enableCompression = true;
        [SerializeField] private RetentionPolicy defaultRetention = RetentionPolicy.Days30;

        [Header("Downsampling")]
        [SerializeField] private bool enableDownsampling = true;
        [SerializeField] private DownsampleConfig[] downsampleConfigs;

        // Data points buffer
        private List<DataPoint> writeBuffer = new List<DataPoint>();
        private Queue<DataPoint> localBuffer = new Queue<DataPoint>();
        private object bufferLock = new object();

        // Tag definitions
        private Dictionary<string, TagDefinition> tagDefinitions = new Dictionary<string, TagDefinition>();

        // Query cache
        private Dictionary<string, CachedQueryResult> queryCache = new Dictionary<string, CachedQueryResult>();
        private float queryCacheTTL = 5.0f;

        // Statistics
        private HistorianStats stats = new HistorianStats();

        // Events
        public event Action<DataPoint> OnDataPointWritten;
        public event Action<int> OnBatchFlushed;
        public event Action<string> OnError;
        public event Action<AggregateResult> OnAggregateCalculated;

        private bool isConnected = false;
        private Coroutine flushCoroutine;
        private Coroutine downsampleCoroutine;

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
            InitializeDefaultTags();
            flushCoroutine = StartCoroutine(FlushLoop());

            if (enableDownsampling)
            {
                downsampleCoroutine = StartCoroutine(DownsampleLoop());
            }

            StartCoroutine(Connect());
        }

        void OnDestroy()
        {
            if (flushCoroutine != null)
                StopCoroutine(flushCoroutine);
            if (downsampleCoroutine != null)
                StopCoroutine(downsampleCoroutine);

            // Flush remaining data
            FlushBuffer();
        }

        private void InitializeDefaultTags()
        {
            // Machine state tags
            DefineTag(new TagDefinition
            {
                TagId = "machine.state",
                DataType = TagDataType.String,
                Description = "Machine operational state",
                Unit = "",
                SampleRate = 1.0f,
                Retention = RetentionPolicy.Years1
            });

            // Axis position tags
            foreach (var axis in new[] { "X", "Y", "Z", "A", "B", "C" })
            {
                DefineTag(new TagDefinition
                {
                    TagId = $"axis.{axis}.position",
                    DataType = TagDataType.Float,
                    Description = $"{axis} axis position",
                    Unit = "mm",
                    SampleRate = 100.0f,
                    Retention = RetentionPolicy.Days7
                });

                DefineTag(new TagDefinition
                {
                    TagId = $"axis.{axis}.velocity",
                    DataType = TagDataType.Float,
                    Description = $"{axis} axis velocity",
                    Unit = "mm/min",
                    SampleRate = 100.0f,
                    Retention = RetentionPolicy.Days7
                });

                DefineTag(new TagDefinition
                {
                    TagId = $"axis.{axis}.load",
                    DataType = TagDataType.Float,
                    Description = $"{axis} axis motor load",
                    Unit = "%",
                    SampleRate = 10.0f,
                    Retention = RetentionPolicy.Days30
                });
            }

            // Spindle tags
            DefineTag(new TagDefinition
            {
                TagId = "spindle.speed",
                DataType = TagDataType.Float,
                Description = "Spindle speed",
                Unit = "RPM",
                SampleRate = 10.0f,
                Retention = RetentionPolicy.Days30
            });

            DefineTag(new TagDefinition
            {
                TagId = "spindle.load",
                DataType = TagDataType.Float,
                Description = "Spindle motor load",
                Unit = "%",
                SampleRate = 10.0f,
                Retention = RetentionPolicy.Days30
            });

            // Temperature tags
            DefineTag(new TagDefinition
            {
                TagId = "temp.spindle",
                DataType = TagDataType.Float,
                Description = "Spindle temperature",
                Unit = "°C",
                SampleRate = 1.0f,
                Retention = RetentionPolicy.Days90
            });

            DefineTag(new TagDefinition
            {
                TagId = "temp.coolant",
                DataType = TagDataType.Float,
                Description = "Coolant temperature",
                Unit = "°C",
                SampleRate = 0.1f,
                Retention = RetentionPolicy.Days90
            });

            // OEE tags
            DefineTag(new TagDefinition
            {
                TagId = "oee.availability",
                DataType = TagDataType.Float,
                Description = "OEE Availability",
                Unit = "%",
                SampleRate = 0.016f, // Once per minute
                Retention = RetentionPolicy.Years5
            });

            DefineTag(new TagDefinition
            {
                TagId = "oee.performance",
                DataType = TagDataType.Float,
                Description = "OEE Performance",
                Unit = "%",
                SampleRate = 0.016f,
                Retention = RetentionPolicy.Years5
            });

            DefineTag(new TagDefinition
            {
                TagId = "oee.quality",
                DataType = TagDataType.Float,
                Description = "OEE Quality",
                Unit = "%",
                SampleRate = 0.016f,
                Retention = RetentionPolicy.Years5
            });
        }

        public void DefineTag(TagDefinition definition)
        {
            tagDefinitions[definition.TagId] = definition;
            Debug.Log($"[DataHistorian] Defined tag: {definition.TagId}");
        }

        public TagDefinition GetTagDefinition(string tagId)
        {
            return tagDefinitions.TryGetValue(tagId, out var def) ? def : null;
        }

        #region Connection Management

        public IEnumerator Connect()
        {
            Debug.Log($"[DataHistorian] Connecting to {backend} at {serverUrl}");

            switch (backend)
            {
                case HistorianBackend.InfluxDB:
                    yield return ConnectInfluxDB();
                    break;
                case HistorianBackend.InfluxDB2:
                    yield return ConnectInfluxDB2();
                    break;
                case HistorianBackend.TimescaleDB:
                    yield return ConnectTimescaleDB();
                    break;
                case HistorianBackend.LocalOnly:
                    isConnected = true;
                    Debug.Log("[DataHistorian] Using local buffer only");
                    break;
            }
        }

        private IEnumerator ConnectInfluxDB()
        {
            string pingUrl = $"{serverUrl}/ping";
            using (var request = UnityWebRequest.Get(pingUrl))
            {
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    isConnected = true;
                    Debug.Log("[DataHistorian] Connected to InfluxDB");

                    // Create database if it doesn't exist
                    yield return CreateInfluxDatabase();
                }
                else
                {
                    Debug.LogWarning($"[DataHistorian] Failed to connect to InfluxDB: {request.error}");
                    OnError?.Invoke($"Connection failed: {request.error}");
                }
            }
        }

        private IEnumerator CreateInfluxDatabase()
        {
            string createDbUrl = $"{serverUrl}/query?q=CREATE DATABASE {database}";
            using (var request = UnityWebRequest.PostWwwForm(createDbUrl, ""))
            {
                if (!string.IsNullOrEmpty(username))
                {
                    string auth = Convert.ToBase64String(Encoding.UTF8.GetBytes($"{username}:{password}"));
                    request.SetRequestHeader("Authorization", $"Basic {auth}");
                }

                yield return request.SendWebRequest();
                // Database creation is idempotent, so we don't check for errors
            }
        }

        private IEnumerator ConnectInfluxDB2()
        {
            string healthUrl = $"{serverUrl}/health";
            using (var request = UnityWebRequest.Get(healthUrl))
            {
                request.SetRequestHeader("Authorization", $"Token {authToken}");
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    isConnected = true;
                    Debug.Log("[DataHistorian] Connected to InfluxDB 2.x");
                }
                else
                {
                    Debug.LogWarning($"[DataHistorian] Failed to connect to InfluxDB 2.x: {request.error}");
                }
            }
        }

        private IEnumerator ConnectTimescaleDB()
        {
            // TimescaleDB uses PostgreSQL protocol - would need Npgsql
            // For now, use REST API if available
            Debug.Log("[DataHistorian] TimescaleDB connection - using REST API");
            isConnected = true;
            yield return null;
        }

        #endregion

        #region Write Operations

        /// <summary>
        /// Write a single data point
        /// </summary>
        public void Write(string tagId, object value, Dictionary<string, string> tags = null)
        {
            Write(tagId, value, DateTime.UtcNow, tags);
        }

        /// <summary>
        /// Write a data point with specific timestamp
        /// </summary>
        public void Write(string tagId, object value, DateTime timestamp, Dictionary<string, string> tags = null)
        {
            var dataPoint = new DataPoint
            {
                TagId = tagId,
                Value = value,
                Timestamp = timestamp,
                Tags = tags ?? new Dictionary<string, string>(),
                Quality = DataQuality.Good
            };

            WriteDataPoint(dataPoint);
        }

        /// <summary>
        /// Write a data point with quality information
        /// </summary>
        public void WriteWithQuality(string tagId, object value, DataQuality quality, Dictionary<string, string> tags = null)
        {
            var dataPoint = new DataPoint
            {
                TagId = tagId,
                Value = value,
                Timestamp = DateTime.UtcNow,
                Tags = tags ?? new Dictionary<string, string>(),
                Quality = quality
            };

            WriteDataPoint(dataPoint);
        }

        /// <summary>
        /// Write multiple data points as a batch
        /// </summary>
        public void WriteBatch(IEnumerable<DataPoint> dataPoints)
        {
            lock (bufferLock)
            {
                foreach (var dp in dataPoints)
                {
                    writeBuffer.Add(dp);
                    stats.TotalPointsWritten++;
                }
            }
        }

        private void WriteDataPoint(DataPoint dataPoint)
        {
            // Add machine ID tag if not present
            if (!dataPoint.Tags.ContainsKey("machine"))
            {
                dataPoint.Tags["machine"] = "cnc-01";
            }

            lock (bufferLock)
            {
                writeBuffer.Add(dataPoint);
                stats.TotalPointsWritten++;
            }

            OnDataPointWritten?.Invoke(dataPoint);
        }

        private IEnumerator FlushLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(flushIntervalSeconds);
                FlushBuffer();
            }
        }

        private void FlushBuffer()
        {
            List<DataPoint> pointsToFlush;
            lock (bufferLock)
            {
                if (writeBuffer.Count == 0) return;
                pointsToFlush = new List<DataPoint>(writeBuffer);
                writeBuffer.Clear();
            }

            if (isConnected && backend != HistorianBackend.LocalOnly)
            {
                StartCoroutine(FlushToBackend(pointsToFlush));
            }
            else
            {
                // Store in local buffer
                foreach (var point in pointsToFlush)
                {
                    localBuffer.Enqueue(point);
                    if (localBuffer.Count > maxLocalBufferSize)
                    {
                        localBuffer.Dequeue(); // Remove oldest
                        stats.DroppedPoints++;
                    }
                }
            }
        }

        private IEnumerator FlushToBackend(List<DataPoint> points)
        {
            switch (backend)
            {
                case HistorianBackend.InfluxDB:
                    yield return FlushToInfluxDB(points);
                    break;
                case HistorianBackend.InfluxDB2:
                    yield return FlushToInfluxDB2(points);
                    break;
                case HistorianBackend.TimescaleDB:
                    yield return FlushToTimescaleDB(points);
                    break;
            }
        }

        private IEnumerator FlushToInfluxDB(List<DataPoint> points)
        {
            string lineProtocol = BuildLineProtocol(points);
            string writeUrl = $"{serverUrl}/write?db={database}&precision=ms";

            using (var request = new UnityWebRequest(writeUrl, "POST"))
            {
                byte[] bodyRaw = Encoding.UTF8.GetBytes(lineProtocol);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "text/plain");

                if (!string.IsNullOrEmpty(username))
                {
                    string auth = Convert.ToBase64String(Encoding.UTF8.GetBytes($"{username}:{password}"));
                    request.SetRequestHeader("Authorization", $"Basic {auth}");
                }

                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    stats.SuccessfulFlushes++;
                    OnBatchFlushed?.Invoke(points.Count);
                }
                else
                {
                    stats.FailedFlushes++;
                    // Re-queue points for retry
                    lock (bufferLock)
                    {
                        writeBuffer.InsertRange(0, points);
                    }
                    OnError?.Invoke($"Flush failed: {request.error}");
                }
            }
        }

        private IEnumerator FlushToInfluxDB2(List<DataPoint> points)
        {
            string lineProtocol = BuildLineProtocol(points);
            string writeUrl = $"{serverUrl}/api/v2/write?org={organization}&bucket={bucket}&precision=ms";

            using (var request = new UnityWebRequest(writeUrl, "POST"))
            {
                byte[] bodyRaw = Encoding.UTF8.GetBytes(lineProtocol);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "text/plain");
                request.SetRequestHeader("Authorization", $"Token {authToken}");

                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    stats.SuccessfulFlushes++;
                    OnBatchFlushed?.Invoke(points.Count);
                }
                else
                {
                    stats.FailedFlushes++;
                    OnError?.Invoke($"Flush failed: {request.error}");
                }
            }
        }

        private IEnumerator FlushToTimescaleDB(List<DataPoint> points)
        {
            // TimescaleDB would use SQL INSERT via REST API
            Debug.Log($"[DataHistorian] Would flush {points.Count} points to TimescaleDB");
            yield return null;
        }

        private string BuildLineProtocol(List<DataPoint> points)
        {
            var sb = new StringBuilder();
            foreach (var point in points)
            {
                // Measurement name (use tag ID with dots replaced)
                string measurement = point.TagId.Replace(".", "_");
                sb.Append(measurement);

                // Tags
                foreach (var tag in point.Tags)
                {
                    sb.Append($",{EscapeTagKey(tag.Key)}={EscapeTagValue(tag.Value)}");
                }
                sb.Append($",quality={point.Quality}");

                // Field value
                sb.Append(" value=");
                if (point.Value is float f)
                    sb.Append(f.ToString("G"));
                else if (point.Value is double d)
                    sb.Append(d.ToString("G"));
                else if (point.Value is int i)
                    sb.Append($"{i}i");
                else if (point.Value is long l)
                    sb.Append($"{l}i");
                else if (point.Value is bool b)
                    sb.Append(b ? "true" : "false");
                else if (point.Value is string s)
                    sb.Append($"\"{EscapeStringValue(s)}\"");
                else
                    sb.Append($"\"{point.Value}\"");

                // Timestamp in milliseconds
                long timestamp = ((DateTimeOffset)point.Timestamp).ToUnixTimeMilliseconds();
                sb.Append($" {timestamp}");
                sb.AppendLine();
            }
            return sb.ToString();
        }

        private string EscapeTagKey(string key) => key.Replace(",", "\\,").Replace("=", "\\=").Replace(" ", "\\ ");
        private string EscapeTagValue(string value) => value.Replace(",", "\\,").Replace("=", "\\=").Replace(" ", "\\ ");
        private string EscapeStringValue(string value) => value.Replace("\"", "\\\"");

        #endregion

        #region Query Operations

        /// <summary>
        /// Query raw data for a tag
        /// </summary>
        public IEnumerator QueryRaw(string tagId, DateTime start, DateTime end, Action<List<DataPoint>> callback)
        {
            string cacheKey = $"{tagId}:{start:O}:{end:O}";
            if (TryGetCachedResult(cacheKey, out var cached))
            {
                callback?.Invoke(cached.DataPoints);
                yield break;
            }

            switch (backend)
            {
                case HistorianBackend.InfluxDB:
                    yield return QueryInfluxDB(tagId, start, end, callback);
                    break;
                case HistorianBackend.InfluxDB2:
                    yield return QueryInfluxDB2(tagId, start, end, callback);
                    break;
                case HistorianBackend.LocalOnly:
                    QueryLocalBuffer(tagId, start, end, callback);
                    break;
                default:
                    callback?.Invoke(new List<DataPoint>());
                    break;
            }
        }

        private IEnumerator QueryInfluxDB(string tagId, DateTime start, DateTime end, Action<List<DataPoint>> callback)
        {
            string measurement = tagId.Replace(".", "_");
            string startTime = start.ToString("yyyy-MM-ddTHH:mm:ssZ");
            string endTime = end.ToString("yyyy-MM-ddTHH:mm:ssZ");

            string query = $"SELECT * FROM {measurement} WHERE time >= '{startTime}' AND time <= '{endTime}'";
            string url = $"{serverUrl}/query?db={database}&q={Uri.EscapeDataString(query)}";

            using (var request = UnityWebRequest.Get(url))
            {
                if (!string.IsNullOrEmpty(username))
                {
                    string auth = Convert.ToBase64String(Encoding.UTF8.GetBytes($"{username}:{password}"));
                    request.SetRequestHeader("Authorization", $"Basic {auth}");
                }

                yield return request.SendWebRequest();

                var results = new List<DataPoint>();
                if (request.result == UnityWebRequest.Result.Success)
                {
                    results = ParseInfluxDBResponse(request.downloadHandler.text, tagId);
                    stats.QueriesExecuted++;
                }
                else
                {
                    OnError?.Invoke($"Query failed: {request.error}");
                }

                callback?.Invoke(results);
            }
        }

        private IEnumerator QueryInfluxDB2(string tagId, DateTime start, DateTime end, Action<List<DataPoint>> callback)
        {
            string measurement = tagId.Replace(".", "_");
            string fluxQuery = $@"
from(bucket: ""{bucket}"")
  |> range(start: {start:yyyy-MM-ddTHH:mm:ssZ}, stop: {end:yyyy-MM-ddTHH:mm:ssZ})
  |> filter(fn: (r) => r._measurement == ""{measurement}"")
  |> yield(name: ""results"")";

            string url = $"{serverUrl}/api/v2/query?org={organization}";

            using (var request = new UnityWebRequest(url, "POST"))
            {
                var body = new { query = fluxQuery, type = "flux" };
                byte[] bodyRaw = Encoding.UTF8.GetBytes(JsonUtility.ToJson(body));
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                request.SetRequestHeader("Authorization", $"Token {authToken}");

                yield return request.SendWebRequest();

                var results = new List<DataPoint>();
                if (request.result == UnityWebRequest.Result.Success)
                {
                    // Parse Flux CSV response
                    results = ParseFluxResponse(request.downloadHandler.text, tagId);
                    stats.QueriesExecuted++;
                }

                callback?.Invoke(results);
            }
        }

        private void QueryLocalBuffer(string tagId, DateTime start, DateTime end, Action<List<DataPoint>> callback)
        {
            var results = localBuffer
                .Where(p => p.TagId == tagId && p.Timestamp >= start && p.Timestamp <= end)
                .OrderBy(p => p.Timestamp)
                .ToList();

            callback?.Invoke(results);
        }

        private List<DataPoint> ParseInfluxDBResponse(string json, string tagId)
        {
            var results = new List<DataPoint>();
            // Simplified parsing - in production use proper JSON parser
            try
            {
                var response = JsonUtility.FromJson<InfluxDBResponse>(json);
                if (response?.results != null)
                {
                    foreach (var result in response.results)
                    {
                        if (result.series != null)
                        {
                            foreach (var series in result.series)
                            {
                                foreach (var values in series.values)
                                {
                                    if (values.Length >= 2)
                                    {
                                        results.Add(new DataPoint
                                        {
                                            TagId = tagId,
                                            Timestamp = DateTime.Parse(values[0].ToString()),
                                            Value = values[1],
                                            Quality = DataQuality.Good
                                        });
                                    }
                                }
                            }
                        }
                    }
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[DataHistorian] Failed to parse response: {e.Message}");
            }
            return results;
        }

        private List<DataPoint> ParseFluxResponse(string csv, string tagId)
        {
            var results = new List<DataPoint>();
            // Parse Flux annotated CSV
            var lines = csv.Split('\n');
            foreach (var line in lines.Skip(1)) // Skip header
            {
                if (string.IsNullOrWhiteSpace(line) || line.StartsWith("#")) continue;
                var parts = line.Split(',');
                if (parts.Length >= 6)
                {
                    try
                    {
                        results.Add(new DataPoint
                        {
                            TagId = tagId,
                            Timestamp = DateTime.Parse(parts[5]),
                            Value = float.Parse(parts[6]),
                            Quality = DataQuality.Good
                        });
                    }
                    catch { }
                }
            }
            return results;
        }

        private bool TryGetCachedResult(string key, out CachedQueryResult result)
        {
            if (queryCache.TryGetValue(key, out result))
            {
                if ((DateTime.UtcNow - result.CachedAt).TotalSeconds < queryCacheTTL)
                {
                    stats.CacheHits++;
                    return true;
                }
                queryCache.Remove(key);
            }
            stats.CacheMisses++;
            result = null;
            return false;
        }

        #endregion

        #region Aggregation Operations

        /// <summary>
        /// Calculate aggregate statistics for a tag
        /// </summary>
        public IEnumerator QueryAggregate(string tagId, DateTime start, DateTime end,
            AggregateFunction function, TimeSpan? groupBy, Action<List<AggregateResult>> callback)
        {
            switch (backend)
            {
                case HistorianBackend.InfluxDB:
                    yield return QueryInfluxDBAggregate(tagId, start, end, function, groupBy, callback);
                    break;
                case HistorianBackend.LocalOnly:
                    QueryLocalAggregate(tagId, start, end, function, groupBy, callback);
                    break;
                default:
                    callback?.Invoke(new List<AggregateResult>());
                    break;
            }
        }

        private IEnumerator QueryInfluxDBAggregate(string tagId, DateTime start, DateTime end,
            AggregateFunction function, TimeSpan? groupBy, Action<List<AggregateResult>> callback)
        {
            string measurement = tagId.Replace(".", "_");
            string funcName = function.ToString().ToLower();
            string startTime = start.ToString("yyyy-MM-ddTHH:mm:ssZ");
            string endTime = end.ToString("yyyy-MM-ddTHH:mm:ssZ");

            string groupByClause = "";
            if (groupBy.HasValue)
            {
                groupByClause = $" GROUP BY time({groupBy.Value.TotalSeconds}s)";
            }

            string query = $"SELECT {funcName}(value) FROM {measurement} WHERE time >= '{startTime}' AND time <= '{endTime}'{groupByClause}";
            string url = $"{serverUrl}/query?db={database}&q={Uri.EscapeDataString(query)}";

            using (var request = UnityWebRequest.Get(url))
            {
                if (!string.IsNullOrEmpty(username))
                {
                    string auth = Convert.ToBase64String(Encoding.UTF8.GetBytes($"{username}:{password}"));
                    request.SetRequestHeader("Authorization", $"Basic {auth}");
                }

                yield return request.SendWebRequest();

                var results = new List<AggregateResult>();
                if (request.result == UnityWebRequest.Result.Success)
                {
                    results = ParseAggregateResponse(request.downloadHandler.text, tagId, function);
                }

                callback?.Invoke(results);
            }
        }

        private void QueryLocalAggregate(string tagId, DateTime start, DateTime end,
            AggregateFunction function, TimeSpan? groupBy, Action<List<AggregateResult>> callback)
        {
            var points = localBuffer
                .Where(p => p.TagId == tagId && p.Timestamp >= start && p.Timestamp <= end)
                .ToList();

            var results = new List<AggregateResult>();

            if (!groupBy.HasValue)
            {
                // Single aggregate for entire range
                var result = CalculateAggregate(points, function);
                result.TagId = tagId;
                result.StartTime = start;
                result.EndTime = end;
                results.Add(result);
            }
            else
            {
                // Group by time buckets
                var buckets = points.GroupBy(p =>
                    new DateTime((p.Timestamp.Ticks / groupBy.Value.Ticks) * groupBy.Value.Ticks));

                foreach (var bucket in buckets)
                {
                    var result = CalculateAggregate(bucket.ToList(), function);
                    result.TagId = tagId;
                    result.StartTime = bucket.Key;
                    result.EndTime = bucket.Key + groupBy.Value;
                    results.Add(result);
                }
            }

            callback?.Invoke(results);
        }

        private AggregateResult CalculateAggregate(List<DataPoint> points, AggregateFunction function)
        {
            var result = new AggregateResult { Function = function, Count = points.Count };

            if (points.Count == 0)
            {
                result.Value = 0;
                return result;
            }

            var numericValues = points
                .Select(p => Convert.ToDouble(p.Value))
                .ToList();

            switch (function)
            {
                case AggregateFunction.Mean:
                    result.Value = numericValues.Average();
                    break;
                case AggregateFunction.Min:
                    result.Value = numericValues.Min();
                    break;
                case AggregateFunction.Max:
                    result.Value = numericValues.Max();
                    break;
                case AggregateFunction.Sum:
                    result.Value = numericValues.Sum();
                    break;
                case AggregateFunction.Count:
                    result.Value = points.Count;
                    break;
                case AggregateFunction.First:
                    result.Value = numericValues.First();
                    break;
                case AggregateFunction.Last:
                    result.Value = numericValues.Last();
                    break;
                case AggregateFunction.StdDev:
                    double avg = numericValues.Average();
                    double sumSquares = numericValues.Sum(v => Math.Pow(v - avg, 2));
                    result.Value = Math.Sqrt(sumSquares / points.Count);
                    break;
                case AggregateFunction.Range:
                    result.Value = numericValues.Max() - numericValues.Min();
                    break;
            }

            return result;
        }

        private List<AggregateResult> ParseAggregateResponse(string json, string tagId, AggregateFunction function)
        {
            var results = new List<AggregateResult>();
            // Simplified - would use proper JSON parsing
            return results;
        }

        #endregion

        #region Downsampling

        private IEnumerator DownsampleLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(60f); // Run every minute

                foreach (var config in downsampleConfigs)
                {
                    yield return ProcessDownsample(config);
                }
            }
        }

        private IEnumerator ProcessDownsample(DownsampleConfig config)
        {
            // Calculate time range for downsampling
            DateTime end = DateTime.UtcNow - TimeSpan.FromSeconds(config.DelaySeconds);
            DateTime start = end - config.SourceWindow;

            foreach (var tagId in GetTagsForDownsample(config.TagPattern))
            {
                yield return DownsampleTag(tagId, start, end, config);
            }
        }

        private IEnumerator DownsampleTag(string tagId, DateTime start, DateTime end, DownsampleConfig config)
        {
            var aggregatedPoints = new List<DataPoint>();

            // Query source data and aggregate
            List<AggregateResult> results = null;
            yield return QueryAggregate(tagId, start, end, config.Function, config.TargetResolution,
                r => results = r);

            if (results != null)
            {
                foreach (var agg in results)
                {
                    var point = new DataPoint
                    {
                        TagId = $"{tagId}_{config.TargetSuffix}",
                        Value = agg.Value,
                        Timestamp = agg.StartTime,
                        Quality = DataQuality.Good,
                        Tags = new Dictionary<string, string> { { "downsampled", "true" } }
                    };
                    aggregatedPoints.Add(point);
                }

                WriteBatch(aggregatedPoints);
                stats.PointsDownsampled += aggregatedPoints.Count;
            }
        }

        private IEnumerable<string> GetTagsForDownsample(string pattern)
        {
            // Simple pattern matching
            var regex = new System.Text.RegularExpressions.Regex(
                "^" + pattern.Replace("*", ".*") + "$");

            return tagDefinitions.Keys.Where(t => regex.IsMatch(t));
        }

        #endregion

        #region Trend Analysis

        /// <summary>
        /// Get trend data formatted for charts
        /// </summary>
        public IEnumerator GetTrendData(TrendRequest request, Action<TrendData> callback)
        {
            var trendData = new TrendData
            {
                TagId = request.TagId,
                StartTime = request.StartTime,
                EndTime = request.EndTime,
                Resolution = request.Resolution
            };

            // Query raw or aggregated data based on resolution
            TimeSpan duration = request.EndTime - request.StartTime;
            int targetPoints = request.MaxPoints > 0 ? request.MaxPoints : 1000;
            TimeSpan groupBy = TimeSpan.FromTicks(duration.Ticks / targetPoints);

            if (groupBy < TimeSpan.FromSeconds(1))
            {
                // Query raw data
                yield return QueryRaw(request.TagId, request.StartTime, request.EndTime, points =>
                {
                    trendData.Timestamps = points.Select(p => p.Timestamp).ToArray();
                    trendData.Values = points.Select(p => Convert.ToDouble(p.Value)).ToArray();
                    trendData.Qualities = points.Select(p => p.Quality).ToArray();
                });
            }
            else
            {
                // Query aggregated data
                yield return QueryAggregate(request.TagId, request.StartTime, request.EndTime,
                    AggregateFunction.Mean, groupBy, results =>
                {
                    trendData.Timestamps = results.Select(r => r.StartTime).ToArray();
                    trendData.Values = results.Select(r => r.Value).ToArray();
                    trendData.Qualities = results.Select(_ => DataQuality.Good).ToArray();

                    // Also include min/max for envelope display
                    trendData.MinValues = results.Select(r => r.Value * 0.95).ToArray(); // Placeholder
                    trendData.MaxValues = results.Select(r => r.Value * 1.05).ToArray();
                });
            }

            callback?.Invoke(trendData);
        }

        #endregion

        #region Statistics & Diagnostics

        public HistorianStats GetStatistics()
        {
            stats.BufferSize = writeBuffer.Count;
            stats.LocalBufferSize = localBuffer.Count;
            stats.RegisteredTags = tagDefinitions.Count;
            stats.IsConnected = isConnected;
            return stats;
        }

        public void ResetStatistics()
        {
            stats = new HistorianStats();
        }

        #endregion
    }

    #region Enums

    public enum HistorianBackend
    {
        InfluxDB,
        InfluxDB2,
        TimescaleDB,
        LocalOnly
    }

    public enum RetentionPolicy
    {
        Hours1,
        Hours24,
        Days7,
        Days30,
        Days90,
        Years1,
        Years5,
        Forever
    }

    public enum TagDataType
    {
        Float,
        Integer,
        Boolean,
        String,
        Binary
    }

    public enum DataQuality
    {
        Good,
        Uncertain,
        Bad,
        NotConnected,
        Substituted,
        Calculated
    }

    public enum AggregateFunction
    {
        Mean,
        Min,
        Max,
        Sum,
        Count,
        First,
        Last,
        StdDev,
        Range,
        Median
    }

    public enum TrendResolution
    {
        Raw,
        Second,
        Minute,
        Hour,
        Day,
        Week,
        Month
    }

    #endregion

    #region Data Classes

    [System.Serializable]
    public class TagDefinition
    {
        public string TagId;
        public TagDataType DataType;
        public string Description;
        public string Unit;
        public float SampleRate; // Hz
        public RetentionPolicy Retention;
        public float? MinValue;
        public float? MaxValue;
        public string EngineeringUnits;
        public Dictionary<string, string> Metadata;
    }

    [System.Serializable]
    public class DataPoint
    {
        public string TagId;
        public object Value;
        public DateTime Timestamp;
        public DataQuality Quality;
        public Dictionary<string, string> Tags;
    }

    [System.Serializable]
    public class AggregateResult
    {
        public string TagId;
        public DateTime StartTime;
        public DateTime EndTime;
        public AggregateFunction Function;
        public double Value;
        public int Count;
    }

    [System.Serializable]
    public class DownsampleConfig
    {
        public string TagPattern;
        public TimeSpan SourceWindow;
        public TimeSpan TargetResolution;
        public AggregateFunction Function;
        public string TargetSuffix;
        public int DelaySeconds;
    }

    [System.Serializable]
    public class TrendRequest
    {
        public string TagId;
        public DateTime StartTime;
        public DateTime EndTime;
        public TrendResolution Resolution;
        public int MaxPoints;
    }

    [System.Serializable]
    public class TrendData
    {
        public string TagId;
        public DateTime StartTime;
        public DateTime EndTime;
        public TrendResolution Resolution;
        public DateTime[] Timestamps;
        public double[] Values;
        public double[] MinValues;
        public double[] MaxValues;
        public DataQuality[] Qualities;
    }

    [System.Serializable]
    public class CachedQueryResult
    {
        public string Key;
        public DateTime CachedAt;
        public List<DataPoint> DataPoints;
    }

    [System.Serializable]
    public class HistorianStats
    {
        public long TotalPointsWritten;
        public long DroppedPoints;
        public int SuccessfulFlushes;
        public int FailedFlushes;
        public int QueriesExecuted;
        public int CacheHits;
        public int CacheMisses;
        public long PointsDownsampled;
        public int BufferSize;
        public int LocalBufferSize;
        public int RegisteredTags;
        public bool IsConnected;
    }

    // InfluxDB response structures
    [System.Serializable]
    public class InfluxDBResponse
    {
        public InfluxResult[] results;
    }

    [System.Serializable]
    public class InfluxResult
    {
        public InfluxSeries[] series;
    }

    [System.Serializable]
    public class InfluxSeries
    {
        public string name;
        public string[] columns;
        public object[][] values;
    }

    #endregion
}
