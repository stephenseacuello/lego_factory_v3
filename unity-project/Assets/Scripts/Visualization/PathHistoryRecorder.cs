using System;
using System.Collections;
using UnityEngine;
using UnityEngine.Networking;

namespace CNCScada.Visualization
{
    /// <summary>
    /// Records machine position history and feeds it to trail renderers.
    /// Interfaces with backend path_history_service for persistence.
    /// Part of Feature 1.3: Machine Trail Visualization
    /// </summary>
    public class PathHistoryRecorder : MonoBehaviour
    {
        [Header("Recording Settings")]
        [SerializeField] private Transform targetTransform;
        [SerializeField] private string machineId = "machine_01";
        [SerializeField] private bool recordOnStart = true;
        [SerializeField] private float recordInterval = 0.1f; // seconds

        [Header("Trail Renderer")]
        [SerializeField] private MachineTrailRenderer trailRenderer;

        [Header("Backend Integration")]
        [SerializeField] private string backendUrl = "http://localhost:5000";
        [SerializeField] private bool syncWithBackend = true;
        [SerializeField] private float backendSyncInterval = 5f; // seconds

        private bool isRecording = false;
        private float recordTimer = 0f;
        private float syncTimer = 0f;
        private Vector3 lastPosition;
        private float currentSpeed = 0f;

        // Statistics
        private int totalPointsRecorded = 0;
        private int pointsSyncedToBackend = 0;
        private DateTime recordingStartTime;

        void Start()
        {
            // Auto-find trail renderer if not assigned
            if (trailRenderer == null)
            {
                trailRenderer = GetComponent<MachineTrailRenderer>();
                if (trailRenderer == null)
                {
                    Debug.LogWarning("[PathRecorder] MachineTrailRenderer not found, creating one");
                    trailRenderer = gameObject.AddComponent<MachineTrailRenderer>();
                }
            }

            // Auto-find target transform if not assigned
            if (targetTransform == null)
            {
                targetTransform = transform;
            }

            lastPosition = targetTransform.position;

            if (recordOnStart)
            {
                StartRecording();
            }
        }

        void Update()
        {
            if (!isRecording) return;

            recordTimer += Time.deltaTime;
            syncTimer += Time.deltaTime;

            // Record position at interval
            if (recordTimer >= recordInterval)
            {
                RecordCurrentPosition();
                recordTimer = 0f;
            }

            // Sync with backend at interval
            if (syncWithBackend && syncTimer >= backendSyncInterval)
            {
                StartCoroutine(SyncTrailToBackend());
                syncTimer = 0f;
            }
        }

        /// <summary>
        /// Start recording machine path
        /// </summary>
        public void StartRecording()
        {
            if (isRecording)
            {
                Debug.LogWarning("[PathRecorder] Already recording");
                return;
            }

            isRecording = true;
            recordingStartTime = DateTime.UtcNow;
            totalPointsRecorded = 0;
            pointsSyncedToBackend = 0;
            lastPosition = targetTransform.position;

            Debug.Log($"[PathRecorder] Started recording for machine: {machineId}");
        }

        /// <summary>
        /// Stop recording machine path
        /// </summary>
        public void StopRecording()
        {
            if (!isRecording)
            {
                Debug.LogWarning("[PathRecorder] Not currently recording");
                return;
            }

            isRecording = false;

            // Final sync to backend
            if (syncWithBackend)
            {
                StartCoroutine(SyncTrailToBackend());
            }

            TimeSpan duration = DateTime.UtcNow - recordingStartTime;
            Debug.Log($"[PathRecorder] Stopped recording. Duration: {duration.TotalMinutes:F2} min, Points: {totalPointsRecorded}");
        }

        /// <summary>
        /// Pause recording temporarily
        /// </summary>
        public void PauseRecording()
        {
            isRecording = false;
            Debug.Log("[PathRecorder] Recording paused");
        }

        /// <summary>
        /// Resume recording
        /// </summary>
        public void ResumeRecording()
        {
            isRecording = true;
            lastPosition = targetTransform.position;
            Debug.Log("[PathRecorder] Recording resumed");
        }

        /// <summary>
        /// Clear recorded trail
        /// </summary>
        public void ClearTrail()
        {
            if (trailRenderer != null)
            {
                trailRenderer.ClearTrail();
            }

            totalPointsRecorded = 0;
            pointsSyncedToBackend = 0;

            // Send clear command to backend
            if (syncWithBackend)
            {
                StartCoroutine(ClearBackendTrail());
            }

            Debug.Log("[PathRecorder] Trail cleared");
        }

        /// <summary>
        /// Load trail from backend
        /// </summary>
        public void LoadTrailFromBackend()
        {
            StartCoroutine(LoadTrailCoroutine());
        }

        /// <summary>
        /// Get recording statistics
        /// </summary>
        public RecordingStatistics GetStatistics()
        {
            TimeSpan duration = isRecording ? DateTime.UtcNow - recordingStartTime : TimeSpan.Zero;

            return new RecordingStatistics
            {
                IsRecording = isRecording,
                MachineId = machineId,
                TotalPointsRecorded = totalPointsRecorded,
                PointsSyncedToBackend = pointsSyncedToBackend,
                RecordingDuration = duration,
                CurrentSpeed = currentSpeed,
                TrailStats = trailRenderer != null ? trailRenderer.GetStatistics() : default
            };
        }

        private void RecordCurrentPosition()
        {
            Vector3 currentPosition = targetTransform.position;

            // Calculate speed (mm/s to mm/min)
            float distance = Vector3.Distance(currentPosition, lastPosition);
            currentSpeed = (distance / recordInterval) * 60f * 1000f; // convert m/s to mm/min

            // Add point to trail renderer
            if (trailRenderer != null)
            {
                trailRenderer.AddTrailPoint(currentPosition, currentSpeed);
            }

            lastPosition = currentPosition;
            totalPointsRecorded++;
        }

        private IEnumerator SyncTrailToBackend()
        {
            if (trailRenderer == null) yield break;

            var trailData = trailRenderer.ExportTrailData();
            if (trailData.Points == null || trailData.Points.Length == 0) yield break;

            // Prepare JSON payload
            var payload = new TrailSyncPayload
            {
                machine_id = machineId,
                points = trailData.Points,
                speeds = trailData.Speeds,
                timestamp = DateTime.UtcNow.ToString("o")
            };

            string jsonPayload = JsonUtility.ToJson(payload);
            byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonPayload);

            using (UnityWebRequest request = new UnityWebRequest($"{backendUrl}/api/v1/trails/{machineId}", "POST"))
            {
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");

                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    pointsSyncedToBackend = trailData.Points.Length;
                    Debug.Log($"[PathRecorder] Synced {pointsSyncedToBackend} points to backend");
                }
                else
                {
                    Debug.LogWarning($"[PathRecorder] Failed to sync trail: {request.error}");
                }
            }
        }

        private IEnumerator ClearBackendTrail()
        {
            using (UnityWebRequest request = UnityWebRequest.Delete($"{backendUrl}/api/v1/trails/{machineId}"))
            {
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    Debug.Log($"[PathRecorder] Cleared backend trail for {machineId}");
                }
                else
                {
                    Debug.LogWarning($"[PathRecorder] Failed to clear backend trail: {request.error}");
                }
            }
        }

        private IEnumerator LoadTrailCoroutine()
        {
            using (UnityWebRequest request = UnityWebRequest.Get($"{backendUrl}/api/v1/trails/{machineId}"))
            {
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    try
                    {
                        var response = JsonUtility.FromJson<TrailLoadResponse>(request.downloadHandler.text);
                        if (response != null && response.points != null && response.points.Length > 0)
                        {
                            var trailData = new TrailData
                            {
                                Points = response.points,
                                Speeds = response.speeds
                            };

                            if (trailRenderer != null)
                            {
                                trailRenderer.ImportTrailData(trailData);
                                Debug.Log($"[PathRecorder] Loaded {response.points.Length} points from backend");
                            }
                        }
                        else
                        {
                            Debug.LogWarning("[PathRecorder] No trail data found on backend");
                        }
                    }
                    catch (Exception ex)
                    {
                        Debug.LogError($"[PathRecorder] Failed to parse trail data: {ex.Message}");
                    }
                }
                else
                {
                    Debug.LogWarning($"[PathRecorder] Failed to load trail from backend: {request.error}");
                }
            }
        }

        #region Public Properties

        public bool IsRecording => isRecording;
        public string MachineId => machineId;
        public int TotalPointsRecorded => totalPointsRecorded;
        public float CurrentSpeed => currentSpeed;

        #endregion
    }

    /// <summary>
    /// Recording statistics
    /// </summary>
    [System.Serializable]
    public struct RecordingStatistics
    {
        public bool IsRecording;
        public string MachineId;
        public int TotalPointsRecorded;
        public int PointsSyncedToBackend;
        public TimeSpan RecordingDuration;
        public float CurrentSpeed;
        public TrailStatistics TrailStats;
    }

    /// <summary>
    /// Payload for syncing trail to backend
    /// </summary>
    [System.Serializable]
    private class TrailSyncPayload
    {
        public string machine_id;
        public Vector3[] points;
        public float[] speeds;
        public string timestamp;
    }

    /// <summary>
    /// Response from loading trail from backend
    /// </summary>
    [System.Serializable]
    private class TrailLoadResponse
    {
        public Vector3[] points;
        public float[] speeds;
        public string timestamp;
    }
}
