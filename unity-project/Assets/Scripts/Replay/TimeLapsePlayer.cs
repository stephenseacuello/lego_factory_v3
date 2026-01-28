using System;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json;

namespace CNCScada.Replay
{
    /// <summary>
    /// Plays back time-lapse recordings with variable speed and timeline control.
    /// Supports slow-motion, normal speed, fast-forward, and timeline scrubbing.
    /// Part of Feature 2.3: Time-Lapse Replay (MEDIUM PRIORITY)
    /// </summary>
    public class TimeLapsePlayer : MonoBehaviour
    {
        [Header("Playback Configuration")]
        [SerializeField] private float playbackSpeed = 1f;
        [SerializeField] private bool loop = false;
        [SerializeField] private bool autoPlay = false;

        [Header("Speed Presets")]
        [SerializeField] private float slowMotionSpeed = 0.25f;
        [SerializeField] private float normalSpeed = 1f;
        [SerializeField] private float fastForwardSpeed = 4f;

        [Header("Interpolation")]
        [SerializeField] private bool interpolatePosition = true;
        [SerializeField] private bool interpolateForces = true;
        [SerializeField] private float interpolationSmoothing = 5f;

        [Header("Visualization")]
        [SerializeField] private bool showTimeline = true;
        [SerializeField] private bool showPlaybackMarker = true;

        // Playback state
        private TimeLapseRecording currentRecording;
        private bool isPlaying = false;
        private bool isPaused = false;
        private float currentTime = 0f;
        private int currentSnapshotIndex = 0;

        // Interpolation state
        private TimeLapseSnapshot currentSnapshot;
        private TimeLapseSnapshot nextSnapshot;
        private float snapshotLerpTime = 0f;

        // Events
        public event Action<TimeLapseRecording> OnRecordingLoaded;
        public event Action OnPlaybackStarted;
        public event Action OnPlaybackStopped;
        public event Action OnPlaybackPaused;
        public event Action OnPlaybackResumed;
        public event Action<float> OnTimeChanged;
        public event Action<TimeLapseSnapshot> OnSnapshotApplied;

        // Playback statistics
        private int totalFramesPlayed = 0;
        private float playbackStartTime = 0f;

        void Start()
        {
            if (autoPlay && currentRecording != null)
            {
                Play();
            }
        }

        void Update()
        {
            if (!isPlaying || isPaused || currentRecording == null) return;

            UpdatePlayback(Time.deltaTime * playbackSpeed);
        }

        /// <summary>
        /// Load a recording for playback
        /// </summary>
        public bool LoadRecording(TimeLapseRecording recording)
        {
            if (recording == null || recording.Snapshots == null || recording.Snapshots.Length == 0)
            {
                Debug.LogError("[TimeLapse] Invalid recording data");
                return false;
            }

            currentRecording = recording;
            currentTime = 0f;
            currentSnapshotIndex = 0;
            totalFramesPlayed = 0;

            if (currentRecording.Snapshots.Length > 0)
            {
                currentSnapshot = currentRecording.Snapshots[0];
                nextSnapshot = currentRecording.Snapshots.Length > 1 ?
                    currentRecording.Snapshots[1] : currentSnapshot;
            }

            Debug.Log($"[TimeLapse] Recording loaded: {recording.RecordingId}, Duration: {recording.Duration:F2}s, Snapshots: {recording.SnapshotCount}");

            OnRecordingLoaded?.Invoke(recording);
            return true;
        }

        /// <summary>
        /// Load recording from JSON string
        /// </summary>
        public bool LoadRecordingFromJson(string json)
        {
            try
            {
                var recording = JsonConvert.DeserializeObject<TimeLapseRecording>(json);
                return LoadRecording(recording);
            }
            catch (Exception e)
            {
                Debug.LogError($"[TimeLapse] Failed to load recording from JSON: {e.Message}");
                return false;
            }
        }

        /// <summary>
        /// Start playback
        /// </summary>
        public void Play()
        {
            if (currentRecording == null)
            {
                Debug.LogWarning("[TimeLapse] No recording loaded");
                return;
            }

            if (isPlaying && !isPaused)
            {
                Debug.LogWarning("[TimeLapse] Already playing");
                return;
            }

            if (!isPlaying)
            {
                playbackStartTime = Time.time;
                isPlaying = true;
                isPaused = false;
                OnPlaybackStarted?.Invoke();
                Debug.Log("[TimeLapse] Playback started");
            }
            else
            {
                isPaused = false;
                OnPlaybackResumed?.Invoke();
                Debug.Log("[TimeLapse] Playback resumed");
            }
        }

        /// <summary>
        /// Stop playback
        /// </summary>
        public void Stop()
        {
            if (!isPlaying)
            {
                return;
            }

            isPlaying = false;
            isPaused = false;
            currentTime = 0f;
            currentSnapshotIndex = 0;
            snapshotLerpTime = 0f;

            OnPlaybackStopped?.Invoke();
            Debug.Log("[TimeLapse] Playback stopped");
        }

        /// <summary>
        /// Pause playback
        /// </summary>
        public void Pause()
        {
            if (!isPlaying || isPaused)
            {
                return;
            }

            isPaused = true;
            OnPlaybackPaused?.Invoke();
            Debug.Log("[TimeLapse] Playback paused");
        }

        /// <summary>
        /// Toggle pause
        /// </summary>
        public void TogglePause()
        {
            if (isPaused)
            {
                Play();
            }
            else
            {
                Pause();
            }
        }

        /// <summary>
        /// Update playback state
        /// </summary>
        private void UpdatePlayback(float deltaTime)
        {
            currentTime += deltaTime;

            // Check if playback finished
            if (currentTime >= currentRecording.Duration)
            {
                if (loop)
                {
                    currentTime = 0f;
                    currentSnapshotIndex = 0;
                    snapshotLerpTime = 0f;
                }
                else
                {
                    Stop();
                    return;
                }
            }

            // Find appropriate snapshot based on current time
            UpdateSnapshotIndices();

            // Apply snapshot to machine state
            ApplySnapshot();

            OnTimeChanged?.Invoke(currentTime);
        }

        /// <summary>
        /// Update current and next snapshot indices based on time
        /// </summary>
        private void UpdateSnapshotIndices()
        {
            // Find the snapshot that matches current time
            while (currentSnapshotIndex < currentRecording.Snapshots.Length - 1 &&
                   currentRecording.Snapshots[currentSnapshotIndex + 1].TimeOffset <= currentTime)
            {
                currentSnapshotIndex++;
                totalFramesPlayed++;
            }

            if (currentSnapshotIndex < currentRecording.Snapshots.Length)
            {
                currentSnapshot = currentRecording.Snapshots[currentSnapshotIndex];

                if (currentSnapshotIndex + 1 < currentRecording.Snapshots.Length)
                {
                    nextSnapshot = currentRecording.Snapshots[currentSnapshotIndex + 1];

                    // Calculate interpolation factor
                    float timeBetweenSnapshots = nextSnapshot.TimeOffset - currentSnapshot.TimeOffset;
                    if (timeBetweenSnapshots > 0)
                    {
                        snapshotLerpTime = (currentTime - currentSnapshot.TimeOffset) / timeBetweenSnapshots;
                        snapshotLerpTime = Mathf.Clamp01(snapshotLerpTime);
                    }
                }
                else
                {
                    nextSnapshot = currentSnapshot;
                    snapshotLerpTime = 0f;
                }
            }
        }

        /// <summary>
        /// Apply snapshot data to machine state
        /// </summary>
        private void ApplySnapshot()
        {
            if (currentSnapshot.Position != null)
            {
                ApplyPosition();
            }

            if (currentSnapshot.Forces != null)
            {
                ApplyForces();
            }

            if (currentSnapshot.Vibration != null)
            {
                ApplyVibration();
            }

            if (currentSnapshot.ChipLoad != null)
            {
                ApplyChipLoad();
            }

            OnSnapshotApplied?.Invoke(currentSnapshot);
        }

        /// <summary>
        /// Apply position from snapshot
        /// </summary>
        private void ApplyPosition()
        {
            Vector3 currentPos = new Vector3(
                currentSnapshot.Position.X,
                currentSnapshot.Position.Y,
                currentSnapshot.Position.Z
            );

            if (interpolatePosition && nextSnapshot.Position != null)
            {
                Vector3 nextPos = new Vector3(
                    nextSnapshot.Position.X,
                    nextSnapshot.Position.Y,
                    nextSnapshot.Position.Z
                );

                transform.position = Vector3.Lerp(currentPos, nextPos, snapshotLerpTime);
            }
            else
            {
                transform.position = currentPos;
            }

            // Apply rotation
            if (currentSnapshot.Rotation != null)
            {
                Vector3 currentRot = new Vector3(
                    currentSnapshot.Rotation.X,
                    currentSnapshot.Rotation.Y,
                    currentSnapshot.Rotation.Z
                );

                if (interpolatePosition && nextSnapshot.Rotation != null)
                {
                    Vector3 nextRot = new Vector3(
                        nextSnapshot.Rotation.X,
                        nextSnapshot.Rotation.Y,
                        nextSnapshot.Rotation.Z
                    );

                    Quaternion currentQuat = Quaternion.Euler(currentRot);
                    Quaternion nextQuat = Quaternion.Euler(nextRot);
                    transform.rotation = Quaternion.Slerp(currentQuat, nextQuat, snapshotLerpTime);
                }
                else
                {
                    transform.rotation = Quaternion.Euler(currentRot);
                }
            }
        }

        /// <summary>
        /// Apply forces from snapshot
        /// </summary>
        private void ApplyForces()
        {
            var forceViz = GetComponent<CNCScada.Visualization.ForceVisualization>();
            if (forceViz != null)
            {
                if (interpolateForces && nextSnapshot.Forces != null)
                {
                    float tangential = Mathf.Lerp(currentSnapshot.Forces.Tangential,
                        nextSnapshot.Forces.Tangential, snapshotLerpTime);
                    float radial = Mathf.Lerp(currentSnapshot.Forces.Radial,
                        nextSnapshot.Forces.Radial, snapshotLerpTime);
                    float axial = Mathf.Lerp(currentSnapshot.Forces.Axial,
                        nextSnapshot.Forces.Axial, snapshotLerpTime);

                    forceViz.UpdateForce(tangential, radial, axial);
                }
                else
                {
                    forceViz.UpdateForce(
                        currentSnapshot.Forces.Tangential,
                        currentSnapshot.Forces.Radial,
                        currentSnapshot.Forces.Axial
                    );
                }
            }
        }

        /// <summary>
        /// Apply vibration from snapshot
        /// </summary>
        private void ApplyVibration()
        {
            var vibViz = GetComponent<CNCScada.Visualization.VibrationVisualizer>();
            if (vibViz != null)
            {
                vibViz.UpdateVibration(
                    currentSnapshot.Vibration.X,
                    currentSnapshot.Vibration.Y,
                    currentSnapshot.Vibration.Z
                );
            }
        }

        /// <summary>
        /// Apply chip load from snapshot
        /// </summary>
        private void ApplyChipLoad()
        {
            var chipLoadCalc = GetComponent<CNCScada.Machining.ChipLoadCalculator>();
            if (chipLoadCalc != null)
            {
                chipLoadCalc.UpdateParameters(
                    currentSnapshot.ChipLoad.FeedRate,
                    currentSnapshot.ChipLoad.SpindleSpeed,
                    4  // Default number of flutes
                );
            }
        }

        /// <summary>
        /// Seek to specific time
        /// </summary>
        public void SeekTo(float time)
        {
            if (currentRecording == null)
            {
                Debug.LogWarning("[TimeLapse] No recording loaded");
                return;
            }

            currentTime = Mathf.Clamp(time, 0f, currentRecording.Duration);

            // Reset snapshot index and find appropriate snapshot
            currentSnapshotIndex = 0;
            UpdateSnapshotIndices();
            ApplySnapshot();

            OnTimeChanged?.Invoke(currentTime);
            Debug.Log($"[TimeLapse] Seeked to time: {currentTime:F2}s");
        }

        /// <summary>
        /// Seek to specific snapshot
        /// </summary>
        public void SeekToSnapshot(int snapshotIndex)
        {
            if (currentRecording == null || snapshotIndex < 0 ||
                snapshotIndex >= currentRecording.Snapshots.Length)
            {
                Debug.LogWarning("[TimeLapse] Invalid snapshot index");
                return;
            }

            currentSnapshotIndex = snapshotIndex;
            currentSnapshot = currentRecording.Snapshots[snapshotIndex];
            currentTime = currentSnapshot.TimeOffset;

            ApplySnapshot();
            OnTimeChanged?.Invoke(currentTime);
        }

        /// <summary>
        /// Set playback speed
        /// </summary>
        public void SetPlaybackSpeed(float speed)
        {
            playbackSpeed = Mathf.Clamp(speed, 0.1f, 10f);
            Debug.Log($"[TimeLapse] Playback speed set to: {playbackSpeed}x");
        }

        /// <summary>
        /// Set to slow motion
        /// </summary>
        public void SetSlowMotion()
        {
            SetPlaybackSpeed(slowMotionSpeed);
        }

        /// <summary>
        /// Set to normal speed
        /// </summary>
        public void SetNormalSpeed()
        {
            SetPlaybackSpeed(normalSpeed);
        }

        /// <summary>
        /// Set to fast forward
        /// </summary>
        public void SetFastForward()
        {
            SetPlaybackSpeed(fastForwardSpeed);
        }

        /// <summary>
        /// Step forward one snapshot
        /// </summary>
        public void StepForward()
        {
            if (currentRecording == null) return;

            int newIndex = Mathf.Min(currentSnapshotIndex + 1, currentRecording.Snapshots.Length - 1);
            SeekToSnapshot(newIndex);
        }

        /// <summary>
        /// Step backward one snapshot
        /// </summary>
        public void StepBackward()
        {
            if (currentRecording == null) return;

            int newIndex = Mathf.Max(currentSnapshotIndex - 1, 0);
            SeekToSnapshot(newIndex);
        }

        /// <summary>
        /// Get playback statistics
        /// </summary>
        public PlaybackStatistics GetStatistics()
        {
            float progress = currentRecording != null ?
                (currentTime / currentRecording.Duration) * 100f : 0f;

            float actualPlaybackTime = isPlaying ? (Time.time - playbackStartTime) : 0f;

            return new PlaybackStatistics
            {
                IsPlaying = isPlaying,
                IsPaused = isPaused,
                CurrentTime = currentTime,
                TotalDuration = currentRecording?.Duration ?? 0f,
                Progress = progress,
                CurrentSnapshotIndex = currentSnapshotIndex,
                TotalSnapshots = currentRecording?.SnapshotCount ?? 0,
                PlaybackSpeed = playbackSpeed,
                TotalFramesPlayed = totalFramesPlayed,
                ActualPlaybackTime = actualPlaybackTime
            };
        }

        #region Public Properties

        public bool IsPlaying => isPlaying;
        public bool IsPaused => isPaused;
        public float CurrentTime => currentTime;
        public float Duration => currentRecording?.Duration ?? 0f;
        public float PlaybackSpeed { get => playbackSpeed; set => SetPlaybackSpeed(value); }
        public bool Loop { get => loop; set => loop = value; }
        public TimeLapseRecording CurrentRecording => currentRecording;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Playback statistics
    /// </summary>
    [Serializable]
    public struct PlaybackStatistics
    {
        public bool IsPlaying;
        public bool IsPaused;
        public float CurrentTime;
        public float TotalDuration;
        public float Progress;
        public int CurrentSnapshotIndex;
        public int TotalSnapshots;
        public float PlaybackSpeed;
        public int TotalFramesPlayed;
        public float ActualPlaybackTime;
    }

    #endregion
}
