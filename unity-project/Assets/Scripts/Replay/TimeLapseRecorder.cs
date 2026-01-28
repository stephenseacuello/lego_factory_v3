using System;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json;

namespace CNCScada.Replay
{
    /// <summary>
    /// Records machine state snapshots over time for time-lapse replay.
    /// Captures position, forces, vibrations, chip load, and other metrics.
    /// Part of Feature 2.3: Time-Lapse Replay (MEDIUM PRIORITY)
    /// </summary>
    public class TimeLapseRecorder : MonoBehaviour
    {
        [Header("Recording Configuration")]
        [SerializeField] private string recordingId;
        [SerializeField] private float captureInterval = 0.1f; // 10Hz default
        [SerializeField] private int maxSnapshots = 10000;
        [SerializeField] private bool autoGenerate RecordingId = true;

        [Header("Recording Control")]
        [SerializeField] private bool isRecording = false;
        [SerializeField] private bool pauseRecording = false;

        [Header("Data Capture")]
        [SerializeField] private bool capturePosition = true;
        [SerializeField] private bool captureForces = true;
        [SerializeField] private bool captureVibration = true;
        [SerializeField] private bool captureChipLoad = true;
        [SerializeField] private bool captureCustomData = true;

        // Recording data
        private List<TimeLapseSnapshot> snapshots = new List<TimeLapseSnapshot>();
        private float captureTimer = 0f;
        private DateTime recordingStartTime;
        private DateTime recordingEndTime;
        private int snapshotCount = 0;

        // Recording metadata
        private string machineName;
        private string operatorName;
        private string programName;
        private Dictionary<string, object> metadata = new Dictionary<string, object>();

        // Events
        public event Action<TimeLapseRecording> OnRecordingStarted;
        public event Action<TimeLapseRecording> OnRecordingStopped;
        public event Action<TimeLapseSnapshot> OnSnapshotCaptured;
        public event Action<string> OnRecordingError;

        // Statistics
        private long totalBytesRecorded = 0;
        private float averageSnapshotSize = 0f;

        void Start()
        {
            if (autoGenerateRecordingId && string.IsNullOrEmpty(recordingId))
            {
                recordingId = GenerateRecordingId();
            }

            machineName = gameObject.name;
        }

        void Update()
        {
            if (!isRecording || pauseRecording) return;

            captureTimer += Time.deltaTime;
            if (captureTimer >= captureInterval)
            {
                CaptureSnapshot();
                captureTimer = 0f;
            }
        }

        /// <summary>
        /// Start recording
        /// </summary>
        public void StartRecording(string operatorName = "", string programName = "")
        {
            if (isRecording)
            {
                Debug.LogWarning("[TimeLapse] Already recording");
                return;
            }

            // Initialize recording
            snapshots.Clear();
            snapshotCount = 0;
            recordingStartTime = DateTime.UtcNow;
            this.operatorName = operatorName;
            this.programName = programName;
            isRecording = true;
            pauseRecording = false;
            captureTimer = 0f;

            Debug.Log($"[TimeLapse] Recording started: {recordingId}");

            OnRecordingStarted?.Invoke(new TimeLapseRecording
            {
                RecordingId = recordingId,
                StartTime = recordingStartTime,
                MachineName = machineName,
                OperatorName = operatorName,
                ProgramName = programName,
                CaptureInterval = captureInterval
            });
        }

        /// <summary>
        /// Stop recording and finalize
        /// </summary>
        public TimeLapseRecording StopRecording()
        {
            if (!isRecording)
            {
                Debug.LogWarning("[TimeLapse] Not currently recording");
                return null;
            }

            recordingEndTime = DateTime.UtcNow;
            isRecording = false;
            pauseRecording = false;

            var duration = (recordingEndTime - recordingStartTime).TotalSeconds;

            var recording = new TimeLapseRecording
            {
                RecordingId = recordingId,
                MachineName = machineName,
                OperatorName = operatorName,
                ProgramName = programName,
                StartTime = recordingStartTime,
                EndTime = recordingEndTime,
                Duration = (float)duration,
                SnapshotCount = snapshotCount,
                CaptureInterval = captureInterval,
                Snapshots = snapshots.ToArray(),
                Metadata = metadata,
                TotalBytes = totalBytesRecorded
            };

            Debug.Log($"[TimeLapse] Recording stopped: {recordingId}, Duration: {duration:F2}s, Snapshots: {snapshotCount}");

            OnRecordingStopped?.Invoke(recording);

            return recording;
        }

        /// <summary>
        /// Pause/Resume recording
        /// </summary>
        public void SetPause(bool pause)
        {
            pauseRecording = pause;
            Debug.Log($"[TimeLapse] Recording {(pause ? "paused" : "resumed")}");
        }

        /// <summary>
        /// Capture a snapshot of current state
        /// </summary>
        private void CaptureSnapshot()
        {
            try
            {
                if (snapshotCount >= maxSnapshots)
                {
                    Debug.LogWarning($"[TimeLapse] Max snapshots reached ({maxSnapshots})");
                    OnRecordingError?.Invoke("Max snapshots reached");
                    StopRecording();
                    return;
                }

                var snapshot = new TimeLapseSnapshot
                {
                    Timestamp = DateTime.UtcNow,
                    TimeOffset = (float)(DateTime.UtcNow - recordingStartTime).TotalSeconds,
                    SnapshotIndex = snapshotCount
                };

                // Capture position data
                if (capturePosition)
                {
                    snapshot.Position = new Vector3Data
                    {
                        X = transform.position.x,
                        Y = transform.position.y,
                        Z = transform.position.z
                    };

                    snapshot.Rotation = new Vector3Data
                    {
                        X = transform.rotation.eulerAngles.x,
                        Y = transform.rotation.eulerAngles.y,
                        Z = transform.rotation.eulerAngles.z
                    };
                }

                // Capture forces (if available)
                if (captureForces)
                {
                    var forceViz = GetComponent<CNCScada.Visualization.ForceVisualization>();
                    if (forceViz != null)
                    {
                        snapshot.Forces = new ForceData
                        {
                            Tangential = forceViz.TangentialForce,
                            Radial = forceViz.RadialForce,
                            Axial = forceViz.AxialForce,
                            Resultant = forceViz.CurrentForceMagnitude
                        };
                    }
                }

                // Capture vibration (if available)
                if (captureVibration)
                {
                    var vibViz = GetComponent<CNCScada.Visualization.VibrationVisualizer>();
                    if (vibViz != null)
                    {
                        snapshot.Vibration = new VibrationData
                        {
                            X = vibViz.VibrationX,
                            Y = vibViz.VibrationY,
                            Z = vibViz.VibrationZ,
                            Magnitude = vibViz.VibrationMagnitude
                        };
                    }
                }

                // Capture chip load (if available)
                if (captureChipLoad)
                {
                    var chipLoadCalc = GetComponent<CNCScada.Machining.ChipLoadCalculator>();
                    if (chipLoadCalc != null)
                    {
                        snapshot.ChipLoad = new ChipLoadData
                        {
                            ChipLoad = chipLoadCalc.CurrentChipLoad,
                            FeedRate = chipLoadCalc.FeedRate,
                            SpindleSpeed = chipLoadCalc.SpindleSpeed,
                            IsOptimal = chipLoadCalc.GetStatistics().IsOptimal
                        };
                    }
                }

                // Capture custom data
                if (captureCustomData && customDataCapture != null)
                {
                    snapshot.CustomData = customDataCapture();
                }

                snapshots.Add(snapshot);
                snapshotCount++;

                // Estimate snapshot size for statistics
                string json = JsonConvert.SerializeObject(snapshot);
                long snapshotSize = json.Length;
                totalBytesRecorded += snapshotSize;
                averageSnapshotSize = totalBytesRecorded / (float)snapshotCount;

                OnSnapshotCaptured?.Invoke(snapshot);
            }
            catch (Exception e)
            {
                Debug.LogError($"[TimeLapse] Error capturing snapshot: {e.Message}");
                OnRecordingError?.Invoke($"Snapshot capture error: {e.Message}");
            }
        }

        /// <summary>
        /// Custom data capture delegate
        /// </summary>
        private Func<Dictionary<string, object>> customDataCapture;

        /// <summary>
        /// Set custom data capture function
        /// </summary>
        public void SetCustomDataCapture(Func<Dictionary<string, object>> captureFunc)
        {
            customDataCapture = captureFunc;
        }

        /// <summary>
        /// Add metadata to recording
        /// </summary>
        public void AddMetadata(string key, object value)
        {
            metadata[key] = value;
        }

        /// <summary>
        /// Generate unique recording ID
        /// </summary>
        private string GenerateRecordingId()
        {
            return $"{machineName}_{DateTime.UtcNow:yyyyMMdd_HHmmss}_{Guid.NewGuid().ToString().Substring(0, 8)}";
        }

        /// <summary>
        /// Export recording as JSON
        /// </summary>
        public string ExportRecordingJson()
        {
            var recording = StopRecording();
            if (recording != null)
            {
                return JsonConvert.SerializeObject(recording, Formatting.Indented);
            }
            return null;
        }

        /// <summary>
        /// Get recording statistics
        /// </summary>
        public RecordingStatistics GetStatistics()
        {
            float duration = isRecording ? (float)(DateTime.UtcNow - recordingStartTime).TotalSeconds : 0f;

            return new RecordingStatistics
            {
                RecordingId = recordingId,
                IsRecording = isRecording,
                IsPaused = pauseRecording,
                Duration = duration,
                SnapshotCount = snapshotCount,
                MaxSnapshots = maxSnapshots,
                CaptureInterval = captureInterval,
                TotalBytes = totalBytesRecorded,
                AverageSnapshotSize = averageSnapshotSize,
                EstimatedFinalSize = (long)(averageSnapshotSize * maxSnapshots)
            };
        }

        /// <summary>
        /// Clear recorded data
        /// </summary>
        public void ClearRecording()
        {
            snapshots.Clear();
            snapshotCount = 0;
            totalBytesRecorded = 0;
            averageSnapshotSize = 0f;
            Debug.Log("[TimeLapse] Recording data cleared");
        }

        #region Public Properties

        public bool IsRecording => isRecording;
        public bool IsPaused => pauseRecording;
        public int SnapshotCount => snapshotCount;
        public float CaptureInterval { get => captureInterval; set => captureInterval = value; }
        public string RecordingId => recordingId;
        public List<TimeLapseSnapshot> Snapshots => snapshots;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Complete time-lapse recording
    /// </summary>
    [Serializable]
    public class TimeLapseRecording
    {
        public string RecordingId;
        public string MachineName;
        public string OperatorName;
        public string ProgramName;
        public DateTime StartTime;
        public DateTime EndTime;
        public float Duration;
        public int SnapshotCount;
        public float CaptureInterval;
        public TimeLapseSnapshot[] Snapshots;
        public Dictionary<string, object> Metadata;
        public long TotalBytes;
    }

    /// <summary>
    /// Single snapshot of machine state
    /// </summary>
    [Serializable]
    public class TimeLapseSnapshot
    {
        public DateTime Timestamp;
        public float TimeOffset;
        public int SnapshotIndex;
        public Vector3Data Position;
        public Vector3Data Rotation;
        public ForceData Forces;
        public VibrationData Vibration;
        public ChipLoadData ChipLoad;
        public Dictionary<string, object> CustomData;
    }

    /// <summary>
    /// 3D vector data
    /// </summary>
    [Serializable]
    public struct Vector3Data
    {
        public float X;
        public float Y;
        public float Z;
    }

    /// <summary>
    /// Force data snapshot
    /// </summary>
    [Serializable]
    public struct ForceData
    {
        public float Tangential;
        public float Radial;
        public float Axial;
        public float Resultant;
    }

    /// <summary>
    /// Vibration data snapshot
    /// </summary>
    [Serializable]
    public struct VibrationData
    {
        public float X;
        public float Y;
        public float Z;
        public float Magnitude;
    }

    /// <summary>
    /// Chip load data snapshot
    /// </summary>
    [Serializable]
    public struct ChipLoadData
    {
        public float ChipLoad;
        public float FeedRate;
        public float SpindleSpeed;
        public bool IsOptimal;
    }

    /// <summary>
    /// Recording statistics
    /// </summary>
    [Serializable]
    public struct RecordingStatistics
    {
        public string RecordingId;
        public bool IsRecording;
        public bool IsPaused;
        public float Duration;
        public int SnapshotCount;
        public int MaxSnapshots;
        public float CaptureInterval;
        public long TotalBytes;
        public float AverageSnapshotSize;
        public long EstimatedFinalSize;
    }

    #endregion
}
