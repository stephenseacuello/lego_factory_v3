using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace CNCScada.Sensors
{
    /// <summary>
    /// Data logger for recording sensor data, machine states, and events.
    /// Supports local file storage, InfluxDB, and Flask backend integration.
    /// </summary>
    public class DataLogger : MonoBehaviour
    {
        [Header("Logging Configuration")]
        public bool enableLogging = true;
        public LoggingMode loggingMode = LoggingMode.LocalAndRemote;
        public float logInterval = 1f; // seconds
        public int bufferSize = 100; // records before flush

        [Header("Local Storage")]
        public string localLogDirectory = "Logs/SensorData";
        public bool useCompression = false;
        public long maxFileSize = 10 * 1024 * 1024; // 10MB
        public int maxLogFiles = 10;

        [Header("Remote Storage - Flask Backend")]
        public string flaskEndpoint = "http://localhost:5001/api/sensor-data";
        public bool enableFlaskLogging = true;

        [Header("Remote Storage - InfluxDB")]
        public string influxDbUrl = "http://localhost:8086";
        public string influxDbToken = "";
        public string influxDbOrg = "cnc-scada";
        public string influxDbBucket = "sensor_data";
        public bool enableInfluxDb = false;

        [Header("Data Retention")]
        public int retentionDays = 30;
        public bool autoCleanup = true;

        [Header("Status")]
        [SerializeField] private int recordsLogged = 0;
        [SerializeField] private int recordsDropped = 0;
        [SerializeField] private string lastLogTime = "";

        // Internal state
        private Queue<SensorLogEntry> logBuffer = new Queue<SensorLogEntry>();
        private StreamWriter currentLogFile;
        private string currentLogFilePath;
        private DateTime logFileStartTime;
        private Coroutine loggingCoroutine;

        // Singleton
        public static DataLogger Instance { get; private set; }

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
            if (enableLogging)
            {
                InitializeLogging();
            }
        }

        private void OnDestroy()
        {
            StopLogging();
        }

        // =========================================================================
        // Initialization
        // =========================================================================

        private void InitializeLogging()
        {
            // Create log directory
            string fullPath = Path.Combine(Application.persistentDataPath, localLogDirectory);
            if (!Directory.Exists(fullPath))
            {
                Directory.CreateDirectory(fullPath);
            }

            // Start new log file
            CreateNewLogFile();

            // Subscribe to sensor events
            if (SensorSystem.Instance != null)
            {
                SensorSystem.Instance.OnSensorReading += HandleSensorReading;
                SensorSystem.Instance.OnSensorAlert += HandleSensorAlert;
            }

            // Start logging coroutine
            loggingCoroutine = StartCoroutine(LoggingLoop());

            Debug.Log($"[DataLogger] Initialized. Log path: {fullPath}");
        }

        private void CreateNewLogFile()
        {
            // Close existing file
            currentLogFile?.Close();

            // Create new file with timestamp
            logFileStartTime = DateTime.UtcNow;
            string timestamp = logFileStartTime.ToString("yyyyMMdd_HHmmss");
            string fullPath = Path.Combine(Application.persistentDataPath, localLogDirectory);
            currentLogFilePath = Path.Combine(fullPath, $"sensor_log_{timestamp}.csv");

            currentLogFile = new StreamWriter(currentLogFilePath, false, Encoding.UTF8);

            // Write header
            currentLogFile.WriteLine("timestamp,sensor_id,sensor_type,value,status,unit,machine_id,metadata");
            currentLogFile.Flush();

            Debug.Log($"[DataLogger] Created new log file: {currentLogFilePath}");

            // Cleanup old files if needed
            if (autoCleanup)
            {
                CleanupOldLogFiles();
            }
        }

        public void StopLogging()
        {
            if (loggingCoroutine != null)
            {
                StopCoroutine(loggingCoroutine);
            }

            // Flush remaining buffer
            FlushBuffer();

            // Close file
            currentLogFile?.Close();
            currentLogFile = null;

            if (SensorSystem.Instance != null)
            {
                SensorSystem.Instance.OnSensorReading -= HandleSensorReading;
                SensorSystem.Instance.OnSensorAlert -= HandleSensorAlert;
            }
        }

        // =========================================================================
        // Event Handlers
        // =========================================================================

        private void HandleSensorReading(SensorReading reading)
        {
            LogSensorReading(reading);
        }

        private void HandleSensorAlert(SensorAlert alert)
        {
            LogAlert(alert);
        }

        // =========================================================================
        // Logging Methods
        // =========================================================================

        /// <summary>
        /// Log a sensor reading
        /// </summary>
        public void LogSensorReading(SensorReading reading)
        {
            if (!enableLogging) return;

            var entry = new SensorLogEntry
            {
                timestamp = reading.timestamp,
                sensorId = reading.sensorId,
                sensorType = reading.sensorType.ToString(),
                value = reading.value,
                status = reading.status.ToString(),
                unit = reading.unit,
                vectorValue = reading.vectorValue
            };

            AddToBuffer(entry);
        }

        /// <summary>
        /// Log a machine state
        /// </summary>
        public void LogMachineState(string machineId, Vector3 position, float feedRate, float spindleRpm, string status)
        {
            if (!enableLogging) return;

            // Log position
            AddToBuffer(new SensorLogEntry
            {
                timestamp = DateTime.UtcNow,
                sensorId = $"{machineId}_position",
                sensorType = "Position",
                value = position.magnitude,
                vectorValue = position,
                machineId = machineId,
                metadata = $"x={position.x:F3},y={position.y:F3},z={position.z:F3}"
            });

            // Log feed rate
            AddToBuffer(new SensorLogEntry
            {
                timestamp = DateTime.UtcNow,
                sensorId = $"{machineId}_feedrate",
                sensorType = "FeedRate",
                value = feedRate,
                unit = "mm/min",
                machineId = machineId
            });

            // Log spindle
            AddToBuffer(new SensorLogEntry
            {
                timestamp = DateTime.UtcNow,
                sensorId = $"{machineId}_spindle",
                sensorType = "SpindleSpeed",
                value = spindleRpm,
                unit = "RPM",
                machineId = machineId
            });

            // Log status
            AddToBuffer(new SensorLogEntry
            {
                timestamp = DateTime.UtcNow,
                sensorId = $"{machineId}_status",
                sensorType = "Status",
                value = 0,
                status = status,
                machineId = machineId
            });
        }

        /// <summary>
        /// Log an alert event
        /// </summary>
        public void LogAlert(SensorAlert alert)
        {
            if (!enableLogging) return;

            var entry = new SensorLogEntry
            {
                timestamp = alert.timestamp,
                sensorId = alert.sensorId,
                sensorType = "Alert",
                value = alert.value,
                status = alert.alertLevel.ToString(),
                metadata = alert.message
            };

            AddToBuffer(entry);

            // Immediately flush alerts
            FlushBuffer();
        }

        /// <summary>
        /// Log a custom event
        /// </summary>
        public void LogEvent(string eventType, string message, Dictionary<string, object> data = null)
        {
            if (!enableLogging) return;

            string metadata = message;
            if (data != null)
            {
                var parts = new List<string>();
                foreach (var kvp in data)
                {
                    parts.Add($"{kvp.Key}={kvp.Value}");
                }
                metadata += " | " + string.Join(",", parts);
            }

            var entry = new SensorLogEntry
            {
                timestamp = DateTime.UtcNow,
                sensorId = "system",
                sensorType = eventType,
                value = 0,
                metadata = metadata
            };

            AddToBuffer(entry);
        }

        private void AddToBuffer(SensorLogEntry entry)
        {
            lock (logBuffer)
            {
                if (logBuffer.Count >= bufferSize * 2)
                {
                    // Buffer overflow - drop oldest
                    logBuffer.Dequeue();
                    recordsDropped++;
                }
                logBuffer.Enqueue(entry);
            }
        }

        // =========================================================================
        // Logging Loop
        // =========================================================================

        private IEnumerator LoggingLoop()
        {
            while (enableLogging)
            {
                yield return new WaitForSeconds(logInterval);

                // Check if we need to rotate log file
                if (currentLogFile != null)
                {
                    var fileInfo = new FileInfo(currentLogFilePath);
                    if (fileInfo.Exists && fileInfo.Length >= maxFileSize)
                    {
                        CreateNewLogFile();
                    }
                }

                // Flush buffer
                FlushBuffer();
            }
        }

        private void FlushBuffer()
        {
            List<SensorLogEntry> entriesToFlush;

            lock (logBuffer)
            {
                if (logBuffer.Count == 0) return;

                entriesToFlush = new List<SensorLogEntry>(logBuffer);
                logBuffer.Clear();
            }

            // Write to local file
            if (loggingMode == LoggingMode.Local || loggingMode == LoggingMode.LocalAndRemote)
            {
                WriteToLocalFile(entriesToFlush);
            }

            // Send to remote
            if (loggingMode == LoggingMode.Remote || loggingMode == LoggingMode.LocalAndRemote)
            {
                if (enableFlaskLogging)
                {
                    StartCoroutine(SendToFlask(entriesToFlush));
                }
                if (enableInfluxDb)
                {
                    StartCoroutine(SendToInfluxDb(entriesToFlush));
                }
            }

            recordsLogged += entriesToFlush.Count;
            lastLogTime = DateTime.UtcNow.ToString("HH:mm:ss");
        }

        // =========================================================================
        // Local File Writing
        // =========================================================================

        private void WriteToLocalFile(List<SensorLogEntry> entries)
        {
            if (currentLogFile == null) return;

            try
            {
                foreach (var entry in entries)
                {
                    string line = FormatCsvLine(entry);
                    currentLogFile.WriteLine(line);
                }
                currentLogFile.Flush();
            }
            catch (Exception e)
            {
                Debug.LogError($"[DataLogger] Error writing to file: {e.Message}");
            }
        }

        private string FormatCsvLine(SensorLogEntry entry)
        {
            // Escape any commas in metadata
            string metadata = entry.metadata?.Replace(",", ";") ?? "";

            return $"{entry.timestamp:yyyy-MM-ddTHH:mm:ss.fffZ}," +
                   $"{entry.sensorId}," +
                   $"{entry.sensorType}," +
                   $"{entry.value:F4}," +
                   $"{entry.status}," +
                   $"{entry.unit}," +
                   $"{entry.machineId}," +
                   $"\"{metadata}\"";
        }

        // =========================================================================
        // Remote Logging - Flask
        // =========================================================================

        private IEnumerator SendToFlask(List<SensorLogEntry> entries)
        {
            var payload = new FlaskSensorPayload
            {
                entries = entries.ToArray(),
                timestamp = DateTime.UtcNow.ToString("o"),
                source = "unity_digital_twin"
            };

            string json = JsonUtility.ToJson(payload);

            using (UnityWebRequest request = UnityWebRequest.Post(flaskEndpoint, json, "application/json"))
            {
                request.timeout = 5;
                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogWarning($"[DataLogger] Flask logging failed: {request.error}");
                }
            }
        }

        // =========================================================================
        // Remote Logging - InfluxDB
        // =========================================================================

        private IEnumerator SendToInfluxDb(List<SensorLogEntry> entries)
        {
            if (string.IsNullOrEmpty(influxDbToken))
            {
                Debug.LogWarning("[DataLogger] InfluxDB token not configured");
                yield break;
            }

            // Build InfluxDB line protocol
            StringBuilder lineProtocol = new StringBuilder();

            foreach (var entry in entries)
            {
                // Format: measurement,tag1=value1 field1=value1 timestamp
                long timestampNs = ((DateTimeOffset)entry.timestamp).ToUnixTimeMilliseconds() * 1000000;

                string tags = $"sensor_id={entry.sensorId}";
                if (!string.IsNullOrEmpty(entry.machineId))
                {
                    tags += $",machine_id={entry.machineId}";
                }
                if (!string.IsNullOrEmpty(entry.sensorType))
                {
                    tags += $",type={entry.sensorType}";
                }

                string fields = $"value={entry.value}";
                if (!string.IsNullOrEmpty(entry.status))
                {
                    fields += $",status=\"{entry.status}\"";
                }

                lineProtocol.AppendLine($"sensor_data,{tags} {fields} {timestampNs}");
            }

            string url = $"{influxDbUrl}/api/v2/write?org={influxDbOrg}&bucket={influxDbBucket}&precision=ns";

            using (UnityWebRequest request = UnityWebRequest.Post(url, lineProtocol.ToString(), "text/plain"))
            {
                request.SetRequestHeader("Authorization", $"Token {influxDbToken}");
                request.timeout = 5;
                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogWarning($"[DataLogger] InfluxDB logging failed: {request.error}");
                }
            }
        }

        // =========================================================================
        // Log File Management
        // =========================================================================

        private void CleanupOldLogFiles()
        {
            string fullPath = Path.Combine(Application.persistentDataPath, localLogDirectory);
            if (!Directory.Exists(fullPath)) return;

            var files = new DirectoryInfo(fullPath).GetFiles("sensor_log_*.csv");
            Array.Sort(files, (a, b) => b.CreationTime.CompareTo(a.CreationTime));

            // Delete old files
            DateTime cutoffDate = DateTime.UtcNow.AddDays(-retentionDays);

            for (int i = 0; i < files.Length; i++)
            {
                if (i >= maxLogFiles || files[i].CreationTime < cutoffDate)
                {
                    if (files[i].FullName != currentLogFilePath)
                    {
                        try
                        {
                            files[i].Delete();
                            Debug.Log($"[DataLogger] Deleted old log file: {files[i].Name}");
                        }
                        catch (Exception e)
                        {
                            Debug.LogWarning($"[DataLogger] Failed to delete log file: {e.Message}");
                        }
                    }
                }
            }
        }

        /// <summary>
        /// Export data for a time range
        /// </summary>
        public string ExportData(DateTime startTime, DateTime endTime, ExportFormat format = ExportFormat.CSV)
        {
            string fullPath = Path.Combine(Application.persistentDataPath, localLogDirectory);
            string exportPath = Path.Combine(fullPath, $"export_{DateTime.UtcNow:yyyyMMdd_HHmmss}.{format.ToString().ToLower()}");

            // Read all log files and filter by time range
            var entries = new List<SensorLogEntry>();

            var files = Directory.GetFiles(fullPath, "sensor_log_*.csv");
            foreach (var file in files)
            {
                // Skip current file if it's being written
                if (file == currentLogFilePath)
                {
                    currentLogFile?.Flush();
                }

                try
                {
                    using (var reader = new StreamReader(file))
                    {
                        reader.ReadLine(); // Skip header

                        string line;
                        while ((line = reader.ReadLine()) != null)
                        {
                            var entry = ParseCsvLine(line);
                            if (entry != null && entry.timestamp >= startTime && entry.timestamp <= endTime)
                            {
                                entries.Add(entry);
                            }
                        }
                    }
                }
                catch (Exception e)
                {
                    Debug.LogWarning($"[DataLogger] Error reading log file: {e.Message}");
                }
            }

            // Write export file
            using (var writer = new StreamWriter(exportPath))
            {
                if (format == ExportFormat.CSV)
                {
                    writer.WriteLine("timestamp,sensor_id,sensor_type,value,status,unit,machine_id,metadata");
                    foreach (var entry in entries)
                    {
                        writer.WriteLine(FormatCsvLine(entry));
                    }
                }
                else if (format == ExportFormat.JSON)
                {
                    writer.Write(JsonUtility.ToJson(new ExportContainer { entries = entries.ToArray() }, true));
                }
            }

            Debug.Log($"[DataLogger] Exported {entries.Count} records to {exportPath}");
            return exportPath;
        }

        private SensorLogEntry ParseCsvLine(string line)
        {
            try
            {
                var parts = line.Split(',');
                if (parts.Length < 7) return null;

                return new SensorLogEntry
                {
                    timestamp = DateTime.Parse(parts[0]),
                    sensorId = parts[1],
                    sensorType = parts[2],
                    value = float.Parse(parts[3]),
                    status = parts[4],
                    unit = parts[5],
                    machineId = parts[6],
                    metadata = parts.Length > 7 ? parts[7].Trim('"') : ""
                };
            }
            catch
            {
                return null;
            }
        }

        /// <summary>
        /// Get logging statistics
        /// </summary>
        public LoggingStats GetStats()
        {
            return new LoggingStats
            {
                recordsLogged = recordsLogged,
                recordsDropped = recordsDropped,
                bufferSize = logBuffer.Count,
                lastLogTime = lastLogTime,
                currentLogFile = currentLogFilePath,
                isEnabled = enableLogging
            };
        }

        // Properties
        public int RecordsLogged => recordsLogged;
        public int RecordsDropped => recordsDropped;
        public int BufferCount => logBuffer.Count;
    }

    // =========================================================================
    // Data Classes
    // =========================================================================

    public enum LoggingMode
    {
        Local,
        Remote,
        LocalAndRemote
    }

    public enum ExportFormat
    {
        CSV,
        JSON
    }

    [Serializable]
    public class SensorLogEntry
    {
        public DateTime timestamp;
        public string sensorId;
        public string sensorType;
        public float value;
        public Vector3 vectorValue;
        public string status;
        public string unit;
        public string machineId;
        public string metadata;
    }

    [Serializable]
    public class FlaskSensorPayload
    {
        public SensorLogEntry[] entries;
        public string timestamp;
        public string source;
    }

    [Serializable]
    public class ExportContainer
    {
        public SensorLogEntry[] entries;
    }

    [Serializable]
    public class LoggingStats
    {
        public int recordsLogged;
        public int recordsDropped;
        public int bufferSize;
        public string lastLogTime;
        public string currentLogFile;
        public bool isEnabled;
    }
}
