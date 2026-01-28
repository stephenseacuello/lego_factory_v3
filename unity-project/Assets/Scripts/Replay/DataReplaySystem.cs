using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;

namespace CNCScada.Replay
{
    /// <summary>
    /// Historical data replay system for reviewing past machine operations.
    /// Records machine states, sensor data, and events for later playback.
    /// Supports variable playback speed, seeking, and export.
    /// </summary>
    public class DataReplaySystem : MonoBehaviour
    {
        [Header("Recording Settings")]
        [SerializeField] private bool isRecording = false;
        [SerializeField] private float recordInterval = 0.1f;
        [SerializeField] private int maxRecordingFrames = 36000; // 1 hour at 10 fps
        [SerializeField] private string recordingsPath = "Recordings";

        [Header("Playback Settings")]
        [SerializeField] private bool isPlaying = false;
        [SerializeField] private float playbackSpeed = 1f;
        [SerializeField] private bool loopPlayback = false;

        [Header("Current State")]
        [SerializeField] private int currentFrame = 0;
        [SerializeField] private int totalFrames = 0;
        [SerializeField] private float recordingDuration = 0;
        [SerializeField] private string currentRecordingName = "";

        [Header("Status")]
        [SerializeField] private ReplayMode mode = ReplayMode.Idle;
        [SerializeField] private float playbackProgress = 0f;

        // Recording data
        private List<RecordedFrame> recordedFrames = new List<RecordedFrame>();
        private RecordingMetadata currentMetadata;
        private float lastRecordTime;
        private Coroutine playbackCoroutine;

        // Machine state cache for interpolation
        private Dictionary<string, MachineStateSnapshot> machineStates = new Dictionary<string, MachineStateSnapshot>();

        // Events
        public event Action OnRecordingStarted;
        public event Action OnRecordingStopped;
        public event Action<RecordingMetadata> OnRecordingSaved;
        public event Action<RecordingMetadata> OnPlaybackStarted;
        public event Action OnPlaybackStopped;
        public event Action OnPlaybackPaused;
        public event Action<int, int> OnFrameChanged;
        public event Action<RecordedFrame> OnFramePlayback;

        // Singleton
        public static DataReplaySystem Instance { get; private set; }

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
                return;
            }

            // Ensure recordings directory exists
            string fullPath = Path.Combine(Application.persistentDataPath, recordingsPath);
            if (!Directory.Exists(fullPath))
            {
                Directory.CreateDirectory(fullPath);
            }
        }

        private void Update()
        {
            if (isRecording && Time.time - lastRecordTime >= recordInterval)
            {
                RecordFrame();
                lastRecordTime = Time.time;
            }
        }

        // =========================================================================
        // Recording
        // =========================================================================

        /// <summary>
        /// Start recording machine data
        /// </summary>
        public void StartRecording(string recordingName = "")
        {
            if (isRecording || isPlaying)
            {
                Debug.LogWarning("[DataReplay] Cannot start recording while already recording or playing");
                return;
            }

            // Clear previous recording
            recordedFrames.Clear();
            currentFrame = 0;
            totalFrames = 0;

            // Set recording name
            if (string.IsNullOrEmpty(recordingName))
            {
                recordingName = $"Recording_{DateTime.Now:yyyyMMdd_HHmmss}";
            }
            currentRecordingName = recordingName;

            // Create metadata
            currentMetadata = new RecordingMetadata
            {
                recordingId = Guid.NewGuid().ToString(),
                name = recordingName,
                startTime = DateTime.Now,
                recordInterval = recordInterval,
                version = "1.0"
            };

            isRecording = true;
            mode = ReplayMode.Recording;
            lastRecordTime = Time.time;

            OnRecordingStarted?.Invoke();

            Debug.Log($"[DataReplay] Recording started: {recordingName}");
        }

        /// <summary>
        /// Stop recording and optionally save
        /// </summary>
        public RecordingMetadata StopRecording(bool save = true)
        {
            if (!isRecording)
            {
                return null;
            }

            isRecording = false;
            mode = ReplayMode.Idle;

            // Finalize metadata
            currentMetadata.endTime = DateTime.Now;
            currentMetadata.totalFrames = recordedFrames.Count;
            currentMetadata.duration = (float)(currentMetadata.endTime - currentMetadata.startTime).TotalSeconds;

            totalFrames = recordedFrames.Count;
            recordingDuration = currentMetadata.duration;

            OnRecordingStopped?.Invoke();

            Debug.Log($"[DataReplay] Recording stopped: {totalFrames} frames, {recordingDuration:F1}s");

            if (save)
            {
                SaveRecording(currentRecordingName);
            }

            return currentMetadata;
        }

        private void RecordFrame()
        {
            if (recordedFrames.Count >= maxRecordingFrames)
            {
                Debug.LogWarning("[DataReplay] Maximum recording frames reached");
                StopRecording();
                return;
            }

            var frame = new RecordedFrame
            {
                frameIndex = recordedFrames.Count,
                timestamp = DateTime.Now,
                relativeTime = recordedFrames.Count * recordInterval,
                machineStates = new List<MachineStateSnapshot>(),
                sensorReadings = new List<SensorSnapshot>(),
                events = new List<RecordedEvent>()
            };

            // Record CNC state
            var cnc = FindObjectOfType<CNCScada.Machines.BantamCNCController>();
            if (cnc != null)
            {
                frame.machineStates.Add(new MachineStateSnapshot
                {
                    machineId = "BantamCNC",
                    machineType = "CNC",
                    position = cnc.Position,
                    spindleSpeed = cnc.SpindleSpeed,
                    feedRate = cnc.FeedRate,
                    isRunning = cnc.SpindleSpeed > 0
                });
            }

            // Record xArm state
            var xarm = FindObjectOfType<CNCScada.Machines.XArmLite6Controller>();
            if (xarm != null)
            {
                frame.machineStates.Add(new MachineStateSnapshot
                {
                    machineId = "xArm",
                    machineType = "Robot",
                    jointAngles = xarm.JointAngles,
                    gripperPosition = xarm.GripperState,
                    isRunning = true
                });
            }

            // Record Niryo state
            var niryo = FindObjectOfType<CNCScada.Machines.NiryoNed2Controller>();
            if (niryo != null)
            {
                frame.machineStates.Add(new MachineStateSnapshot
                {
                    machineId = "Niryo",
                    machineType = "Robot",
                    jointAngles = niryo.JointAngles,
                    gripperPosition = niryo.GripperState,
                    isRunning = true
                });
            }

            // Record sensor data
            var sensorSystem = FindObjectOfType<CNCScada.Sensors.SensorSystem>();
            if (sensorSystem != null)
            {
                var readings = sensorSystem.GetAllReadings();
                foreach (var reading in readings)
                {
                    frame.sensorReadings.Add(new SensorSnapshot
                    {
                        sensorId = reading.Value.sensorId,
                        sensorType = reading.Value.sensorType.ToString(),
                        value = reading.Value.value,
                        unit = reading.Value.unit
                    });
                }
            }

            // Record energy data
            var energySystem = FindObjectOfType<CNCScada.Energy.EnergyMonitoringSystem>();
            if (energySystem != null)
            {
                frame.energyReading = new EnergySnapshot
                {
                    totalPowerWatts = energySystem.TotalPowerWatts,
                    totalEnergyKWh = energySystem.TotalEnergyKWh,
                    powerFactor = energySystem.PowerFactor
                };
            }

            // Record analytics data
            var analytics = FindObjectOfType<CNCScada.Analytics.ProductionAnalytics>();
            if (analytics != null)
            {
                frame.analyticsSnapshot = new AnalyticsSnapshot
                {
                    oee = analytics.OEE,
                    availability = analytics.Availability,
                    performance = analytics.Performance,
                    quality = analytics.Quality,
                    partsProduced = analytics.TotalPartsProduced
                };
            }

            recordedFrames.Add(frame);
            totalFrames = recordedFrames.Count;
            currentFrame = totalFrames - 1;
        }

        // =========================================================================
        // Playback
        // =========================================================================

        /// <summary>
        /// Start playback of recorded data
        /// </summary>
        public void StartPlayback()
        {
            if (recordedFrames.Count == 0)
            {
                Debug.LogWarning("[DataReplay] No recording to play");
                return;
            }

            if (isRecording)
            {
                Debug.LogWarning("[DataReplay] Cannot play while recording");
                return;
            }

            isPlaying = true;
            mode = ReplayMode.Playing;
            currentFrame = 0;

            // Stop real-time updates on machines
            SetMachinesReplayMode(true);

            if (playbackCoroutine != null)
            {
                StopCoroutine(playbackCoroutine);
            }
            playbackCoroutine = StartCoroutine(PlaybackLoop());

            OnPlaybackStarted?.Invoke(currentMetadata);

            Debug.Log("[DataReplay] Playback started");
        }

        /// <summary>
        /// Stop playback
        /// </summary>
        public void StopPlayback()
        {
            if (!isPlaying)
            {
                return;
            }

            isPlaying = false;
            mode = ReplayMode.Idle;

            if (playbackCoroutine != null)
            {
                StopCoroutine(playbackCoroutine);
                playbackCoroutine = null;
            }

            // Resume real-time updates on machines
            SetMachinesReplayMode(false);

            OnPlaybackStopped?.Invoke();

            Debug.Log("[DataReplay] Playback stopped");
        }

        /// <summary>
        /// Pause playback
        /// </summary>
        public void PausePlayback()
        {
            if (isPlaying)
            {
                isPlaying = false;
                mode = ReplayMode.Paused;
                OnPlaybackPaused?.Invoke();
                Debug.Log("[DataReplay] Playback paused");
            }
        }

        /// <summary>
        /// Resume playback
        /// </summary>
        public void ResumePlayback()
        {
            if (mode == ReplayMode.Paused)
            {
                isPlaying = true;
                mode = ReplayMode.Playing;

                if (playbackCoroutine != null)
                {
                    StopCoroutine(playbackCoroutine);
                }
                playbackCoroutine = StartCoroutine(PlaybackLoop());

                Debug.Log("[DataReplay] Playback resumed");
            }
        }

        /// <summary>
        /// Seek to specific frame
        /// </summary>
        public void SeekToFrame(int frameIndex)
        {
            if (recordedFrames.Count == 0)
            {
                return;
            }

            frameIndex = Mathf.Clamp(frameIndex, 0, recordedFrames.Count - 1);
            currentFrame = frameIndex;

            ApplyFrame(recordedFrames[frameIndex]);

            playbackProgress = (float)currentFrame / (totalFrames - 1);
            OnFrameChanged?.Invoke(currentFrame, totalFrames);
        }

        /// <summary>
        /// Seek to specific time
        /// </summary>
        public void SeekToTime(float time)
        {
            if (recordedFrames.Count == 0)
            {
                return;
            }

            int frameIndex = Mathf.FloorToInt(time / recordInterval);
            SeekToFrame(frameIndex);
        }

        /// <summary>
        /// Set playback speed
        /// </summary>
        public void SetPlaybackSpeed(float speed)
        {
            playbackSpeed = Mathf.Clamp(speed, 0.1f, 10f);
            Debug.Log($"[DataReplay] Playback speed: {playbackSpeed}x");
        }

        private IEnumerator PlaybackLoop()
        {
            while (isPlaying && currentFrame < recordedFrames.Count)
            {
                var frame = recordedFrames[currentFrame];
                ApplyFrame(frame);

                OnFramePlayback?.Invoke(frame);
                OnFrameChanged?.Invoke(currentFrame, totalFrames);

                playbackProgress = (float)currentFrame / (totalFrames - 1);
                currentFrame++;

                yield return new WaitForSeconds(recordInterval / playbackSpeed);
            }

            if (currentFrame >= recordedFrames.Count)
            {
                if (loopPlayback)
                {
                    currentFrame = 0;
                    playbackCoroutine = StartCoroutine(PlaybackLoop());
                }
                else
                {
                    StopPlayback();
                }
            }
        }

        private void ApplyFrame(RecordedFrame frame)
        {
            // Apply CNC state
            var cncState = frame.machineStates.Find(s => s.machineId == "BantamCNC");
            if (cncState != null)
            {
                var cnc = FindObjectOfType<CNCScada.Machines.BantamCNCController>();
                if (cnc != null)
                {
                    cnc.SetTargetPosition(cncState.position.x, cncState.position.y, cncState.position.z);
                    cnc.SetSpindleSpeed(cncState.spindleSpeed);
                }
            }

            // Apply xArm state
            var xarmState = frame.machineStates.Find(s => s.machineId == "xArm");
            if (xarmState != null)
            {
                var xarm = FindObjectOfType<CNCScada.Machines.XArmLite6Controller>();
                if (xarm != null && xarmState.jointAngles != null)
                {
                    xarm.SetJointAngles(xarmState.jointAngles);
                    xarm.SetGripperPosition(xarmState.gripperPosition);
                }
            }

            // Apply Niryo state
            var niryoState = frame.machineStates.Find(s => s.machineId == "Niryo");
            if (niryoState != null)
            {
                var niryo = FindObjectOfType<CNCScada.Machines.NiryoNed2Controller>();
                if (niryo != null && niryoState.jointAngles != null)
                {
                    niryo.SetJointAngles(niryoState.jointAngles);
                    niryo.SetGripperPosition(niryoState.gripperPosition);
                }
            }
        }

        private void SetMachinesReplayMode(bool replay)
        {
            // Disable/enable real-time updates during replay
            var manager = FindObjectOfType<CNCScada.Core.DigitalTwinManager>();
            if (manager != null)
            {
                // In a full implementation, this would pause real-time data sync
            }
        }

        // =========================================================================
        // Save/Load
        // =========================================================================

        /// <summary>
        /// Save recording to file
        /// </summary>
        public void SaveRecording(string filename)
        {
            if (recordedFrames.Count == 0)
            {
                Debug.LogWarning("[DataReplay] No frames to save");
                return;
            }

            string fullPath = Path.Combine(Application.persistentDataPath, recordingsPath, $"{filename}.json");

            var recording = new RecordingData
            {
                metadata = currentMetadata,
                frames = recordedFrames.ToArray()
            };

            string json = JsonUtility.ToJson(recording, true);
            File.WriteAllText(fullPath, json);

            OnRecordingSaved?.Invoke(currentMetadata);

            Debug.Log($"[DataReplay] Recording saved: {fullPath}");
        }

        /// <summary>
        /// Load recording from file
        /// </summary>
        public bool LoadRecording(string filename)
        {
            string fullPath = Path.Combine(Application.persistentDataPath, recordingsPath, $"{filename}.json");

            if (!File.Exists(fullPath))
            {
                Debug.LogError($"[DataReplay] Recording file not found: {fullPath}");
                return false;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var recording = JsonUtility.FromJson<RecordingData>(json);

                currentMetadata = recording.metadata;
                recordedFrames = new List<RecordedFrame>(recording.frames);
                currentRecordingName = filename;
                totalFrames = recordedFrames.Count;
                recordingDuration = currentMetadata.duration;
                currentFrame = 0;

                Debug.Log($"[DataReplay] Recording loaded: {filename} ({totalFrames} frames)");
                return true;
            }
            catch (Exception ex)
            {
                Debug.LogError($"[DataReplay] Failed to load recording: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Get list of available recordings
        /// </summary>
        public List<string> GetAvailableRecordings()
        {
            string fullPath = Path.Combine(Application.persistentDataPath, recordingsPath);
            var files = Directory.GetFiles(fullPath, "*.json");

            return files.Select(f => Path.GetFileNameWithoutExtension(f)).ToList();
        }

        /// <summary>
        /// Delete a recording
        /// </summary>
        public bool DeleteRecording(string filename)
        {
            string fullPath = Path.Combine(Application.persistentDataPath, recordingsPath, $"{filename}.json");

            if (File.Exists(fullPath))
            {
                File.Delete(fullPath);
                Debug.Log($"[DataReplay] Recording deleted: {filename}");
                return true;
            }

            return false;
        }

        // =========================================================================
        // Export
        // =========================================================================

        /// <summary>
        /// Export recording to CSV
        /// </summary>
        public void ExportToCSV(string filename)
        {
            if (recordedFrames.Count == 0)
            {
                return;
            }

            string fullPath = Path.Combine(Application.persistentDataPath, recordingsPath, $"{filename}.csv");

            using (var writer = new StreamWriter(fullPath))
            {
                // Header
                writer.WriteLine("Frame,Time,CNC_X,CNC_Y,CNC_Z,Spindle_RPM,xArm_J1,xArm_J2,xArm_J3,xArm_J4,xArm_J5,xArm_J6,Power_W,OEE");

                foreach (var frame in recordedFrames)
                {
                    var cnc = frame.machineStates.Find(s => s.machineId == "BantamCNC");
                    var xarm = frame.machineStates.Find(s => s.machineId == "xArm");

                    string line = $"{frame.frameIndex},{frame.relativeTime:F2}," +
                                  $"{cnc?.position.x ?? 0:F3},{cnc?.position.y ?? 0:F3},{cnc?.position.z ?? 0:F3},{cnc?.spindleSpeed ?? 0:F0},";

                    if (xarm?.jointAngles != null && xarm.jointAngles.Length >= 6)
                    {
                        line += $"{xarm.jointAngles[0]:F1},{xarm.jointAngles[1]:F1},{xarm.jointAngles[2]:F1}," +
                                $"{xarm.jointAngles[3]:F1},{xarm.jointAngles[4]:F1},{xarm.jointAngles[5]:F1},";
                    }
                    else
                    {
                        line += "0,0,0,0,0,0,";
                    }

                    line += $"{frame.energyReading?.totalPowerWatts ?? 0:F1},{frame.analyticsSnapshot?.oee ?? 0:F1}";

                    writer.WriteLine(line);
                }
            }

            Debug.Log($"[DataReplay] Exported to CSV: {fullPath}");
        }

        // Properties
        public bool IsRecording => isRecording;
        public bool IsPlaying => isPlaying;
        public ReplayMode Mode => mode;
        public int CurrentFrame => currentFrame;
        public int TotalFrames => totalFrames;
        public float PlaybackProgress => playbackProgress;
        public float PlaybackSpeed => playbackSpeed;
        public float RecordingDuration => recordingDuration;
        public RecordingMetadata CurrentMetadata => currentMetadata;
    }

    // =========================================================================
    // Data Types
    // =========================================================================

    public enum ReplayMode
    {
        Idle,
        Recording,
        Playing,
        Paused
    }

    [Serializable]
    public class RecordingData
    {
        public RecordingMetadata metadata;
        public RecordedFrame[] frames;
    }

    [Serializable]
    public class RecordingMetadata
    {
        public string recordingId;
        public string name;
        public DateTime startTime;
        public DateTime endTime;
        public float duration;
        public int totalFrames;
        public float recordInterval;
        public string version;
        public string description;
    }

    [Serializable]
    public class RecordedFrame
    {
        public int frameIndex;
        public DateTime timestamp;
        public float relativeTime;
        public List<MachineStateSnapshot> machineStates;
        public List<SensorSnapshot> sensorReadings;
        public List<RecordedEvent> events;
        public EnergySnapshot energyReading;
        public AnalyticsSnapshot analyticsSnapshot;
    }

    [Serializable]
    public class MachineStateSnapshot
    {
        public string machineId;
        public string machineType;
        public Vector3 position;
        public float[] jointAngles;
        public float spindleSpeed;
        public float feedRate;
        public float gripperPosition;
        public bool isRunning;
        public string programName;
        public int lineNumber;
    }

    [Serializable]
    public class SensorSnapshot
    {
        public string sensorId;
        public string sensorType;
        public float value;
        public string unit;
    }

    [Serializable]
    public class EnergySnapshot
    {
        public float totalPowerWatts;
        public float totalEnergyKWh;
        public float powerFactor;
    }

    [Serializable]
    public class AnalyticsSnapshot
    {
        public float oee;
        public float availability;
        public float performance;
        public float quality;
        public int partsProduced;
    }

    [Serializable]
    public class RecordedEvent
    {
        public string eventType;
        public string eventData;
        public string source;
    }
}
