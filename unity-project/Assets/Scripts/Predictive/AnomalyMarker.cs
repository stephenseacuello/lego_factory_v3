using UnityEngine;
using UnityEngine.UI;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Net.Http;
using Newtonsoft.Json;

namespace CNCScada.Predictive
{
    /// <summary>
    /// 3D Anomaly Marker System
    /// Visualizes detected anomalies with 3D markers and severity indicators
    /// Part of Phase 4: Predictive Maintenance
    /// </summary>
    public class AnomalyMarker : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";
        [SerializeField] private float updateInterval = 3f;

        [Header("Machine References")]
        [SerializeField] private Transform machineTransform;
        [SerializeField] private List<Transform> sensorLocations = new List<Transform>();

        [Header("Marker Prefabs")]
        [SerializeField] private GameObject lowSeverityMarkerPrefab;
        [SerializeField] private GameObject mediumSeverityMarkerPrefab;
        [SerializeField] private GameObject highSeverityMarkerPrefab;
        [SerializeField] private GameObject criticalSeverityMarkerPrefab;

        [Header("Visual Settings")]
        [SerializeField] private Color lowSeverityColor = Color.green;
        [SerializeField] private Color mediumSeverityColor = Color.yellow;
        [SerializeField] private Color highSeverityColor = new Color(1f, 0.5f, 0f); // Orange
        [SerializeField] private Color criticalSeverityColor = Color.red;
        [SerializeField] private float markerScale = 0.1f;
        [SerializeField] private bool enablePulsing = true;
        [SerializeField] private bool showLabels = true;

        [Header("Anomaly Types")]
        [SerializeField] private bool showVibrationAnomalies = true;
        [SerializeField] private bool showTemperatureAnomalies = true;
        [SerializeField] private bool showForceAnomalies = true;
        [SerializeField] private bool showQualityAnomalies = true;
        [SerializeField] private bool showPredictedAnomalies = true;

        [Header("Detection Settings")]
        [SerializeField] private float anomalyScoreThreshold = 0.7f;
        [SerializeField] private bool autoAcknowledge = false;
        [SerializeField] private float autoAcknowledgeDelay = 300f; // seconds

        // Data
        private HttpClient httpClient;
        private List<AnomalyData> activeAnomalies = new List<AnomalyData>();
        private Dictionary<string, GameObject> anomalyMarkers = new Dictionary<string, GameObject>();
        private Dictionary<string, float> anomalyTimestamps = new Dictionary<string, float>();

        // State
        private float lastUpdateTime = 0f;

        // Statistics
        private int totalAnomaliesDetected = 0;
        private int activeAnomalyCount = 0;
        private int acknowledgedAnomalies = 0;
        private Dictionary<string, int> anomaliesByType = new Dictionary<string, int>();

        // Events
        public event Action<AnomalyData> OnAnomalyDetected;
        public event Action<AnomalyData> OnCriticalAnomalyDetected;
        public event Action<string> OnAnomalyAcknowledged;

        [Serializable]
        public class AnomalyResponse
        {
            public bool success;
            public List<AnomalyData> anomalies;
            public AnomalySummary summary;
            public string error;
        }

        [Serializable]
        public class AnomalyData
        {
            public string anomaly_id;
            public string machine_id;
            public string anomaly_type; // vibration, temperature, force, quality, predicted
            public string severity; // low, medium, high, critical
            public float anomaly_score;
            public DateTime detected_time;
            public Vector3 location;
            public string description;
            public string sensor_id;
            public float confidence;
            public bool acknowledged;
            public List<string> affected_components;
            public string recommended_action;
        }

        [Serializable]
        public class AnomalySummary
        {
            public int total_active;
            public int low_severity;
            public int medium_severity;
            public int high_severity;
            public int critical_severity;
            public Dictionary<string, int> by_type;
        }

        void Start()
        {
            httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(10);

            StartCoroutine(UpdateAnomaliesPeriodically());

            Debug.Log("[AnomalyMarker] Initialized for machine: " + machineId);
        }

        IEnumerator UpdateAnomaliesPeriodically()
        {
            while (true)
            {
                yield return new WaitForSeconds(updateInterval);
                FetchAnomalies();

                // Auto-acknowledge old anomalies
                if (autoAcknowledge)
                {
                    CheckAutoAcknowledge();
                }
            }
        }

        void FetchAnomalies()
        {
            StartCoroutine(FetchAnomaliesAsync());
        }

        IEnumerator FetchAnomaliesAsync()
        {
            string url = $"{flaskServerUrl}/api/v1/predictive/anomalies?machine_id={machineId}&threshold={anomalyScoreThreshold}";

            using (var request = new HttpRequestMessage(HttpMethod.Get, url))
            {
                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    Debug.LogError("[AnomalyMarker] Failed to fetch anomaly data");
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                try
                {
                    AnomalyResponse response = JsonConvert.DeserializeObject<AnomalyResponse>(readTask.Result);

                    if (response.success)
                    {
                        UpdateAnomalyDisplay(response);
                    }
                    else
                    {
                        Debug.LogError($"[AnomalyMarker] Error: {response.error}");
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"[AnomalyMarker] Parse error: {e.Message}");
                }
            }

            lastUpdateTime = Time.time;
        }

        void UpdateAnomalyDisplay(AnomalyResponse response)
        {
            // Remove markers for resolved anomalies
            List<string> activeIds = new List<string>();
            foreach (var anomaly in response.anomalies)
            {
                activeIds.Add(anomaly.anomaly_id);
            }

            List<string> toRemove = new List<string>();
            foreach (var kvp in anomalyMarkers)
            {
                if (!activeIds.Contains(kvp.Key))
                {
                    toRemove.Add(kvp.Key);
                }
            }

            foreach (var id in toRemove)
            {
                RemoveAnomalyMarker(id);
            }

            // Update or create markers
            foreach (var anomaly in response.anomalies)
            {
                // Filter by type
                if (!ShouldDisplayAnomalyType(anomaly.anomaly_type))
                {
                    continue;
                }

                // Skip acknowledged unless we're tracking them
                if (anomaly.acknowledged && autoAcknowledge)
                {
                    continue;
                }

                // Check if it's a new anomaly
                bool isNew = !anomalyMarkers.ContainsKey(anomaly.anomaly_id);

                if (isNew)
                {
                    CreateAnomalyMarker(anomaly);
                    OnAnomalyDetected?.Invoke(anomaly);
                    totalAnomaliesDetected++;

                    // Track timestamp
                    anomalyTimestamps[anomaly.anomaly_id] = Time.time;

                    // Alert for critical
                    if (anomaly.severity == "critical")
                    {
                        OnCriticalAnomalyDetected?.Invoke(anomaly);
                        Debug.LogWarning($"[AnomalyMarker] CRITICAL ANOMALY: {anomaly.description}");
                    }
                }
                else
                {
                    UpdateAnomalyMarker(anomaly);
                }
            }

            // Update statistics
            activeAnomalies = response.anomalies;
            activeAnomalyCount = activeAnomalies.Count;

            if (response.summary != null)
            {
                anomaliesByType = response.summary.by_type;
            }
        }

        bool ShouldDisplayAnomalyType(string type)
        {
            switch (type)
            {
                case "vibration": return showVibrationAnomalies;
                case "temperature": return showTemperatureAnomalies;
                case "force": return showForceAnomalies;
                case "quality": return showQualityAnomalies;
                case "predicted": return showPredictedAnomalies;
                default: return true;
            }
        }

        void CreateAnomalyMarker(AnomalyData anomaly)
        {
            GameObject markerPrefab = GetMarkerPrefab(anomaly.severity);
            if (markerPrefab == null) return;

            // Calculate world position
            Vector3 worldPosition = CalculateMarkerPosition(anomaly);

            // Instantiate marker
            GameObject marker = Instantiate(markerPrefab, worldPosition, Quaternion.identity);
            marker.transform.SetParent(transform);
            marker.transform.localScale = Vector3.one * markerScale;

            // Setup marker components
            SetupMarkerComponents(marker, anomaly);

            // Store marker
            anomalyMarkers[anomaly.anomaly_id] = marker;

            Debug.Log($"[AnomalyMarker] Created marker for {anomaly.anomaly_type} anomaly (severity: {anomaly.severity})");
        }

        GameObject GetMarkerPrefab(string severity)
        {
            switch (severity)
            {
                case "low":
                    return lowSeverityMarkerPrefab ?? CreateDefaultMarker(lowSeverityColor);
                case "medium":
                    return mediumSeverityMarkerPrefab ?? CreateDefaultMarker(mediumSeverityColor);
                case "high":
                    return highSeverityMarkerPrefab ?? CreateDefaultMarker(highSeverityColor);
                case "critical":
                    return criticalSeverityMarkerPrefab ?? CreateDefaultMarker(criticalSeverityColor);
                default:
                    return CreateDefaultMarker(Color.gray);
            }
        }

        GameObject CreateDefaultMarker(Color color)
        {
            GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Cube);
            marker.transform.localScale = Vector3.one * 0.05f;

            Renderer renderer = marker.GetComponent<Renderer>();
            if (renderer != null)
            {
                renderer.material = new Material(Shader.Find("Standard"));
                renderer.material.color = color;
                renderer.material.SetFloat("_Metallic", 0.5f);
                renderer.material.SetFloat("_Glossiness", 0.8f);
            }

            Destroy(marker.GetComponent<Collider>());
            return marker;
        }

        Vector3 CalculateMarkerPosition(AnomalyData anomaly)
        {
            // Use specified location if available
            if (anomaly.location != Vector3.zero)
            {
                if (machineTransform != null)
                {
                    return machineTransform.TransformPoint(anomaly.location);
                }
                return anomaly.location;
            }

            // Try to find sensor location
            if (!string.IsNullOrEmpty(anomaly.sensor_id))
            {
                foreach (var sensor in sensorLocations)
                {
                    if (sensor.name.Contains(anomaly.sensor_id))
                    {
                        return sensor.position;
                    }
                }
            }

            // Default position
            if (machineTransform != null)
            {
                return machineTransform.position + Vector3.up * 0.5f;
            }

            return transform.position;
        }

        void SetupMarkerComponents(GameObject marker, AnomalyData anomaly)
        {
            // Add label
            if (showLabels)
            {
                CreateMarkerLabel(marker, anomaly);
            }

            // Add pulsing effect
            if (enablePulsing)
            {
                PulsingEffect pulseEffect = marker.AddComponent<PulsingEffect>();
                float pulseSpeed = anomaly.severity == "critical" ? 2f : 1f;
                pulseEffect.Initialize(1.3f, pulseSpeed);
            }

            // Add click handler
            AnomalyMarkerClickHandler clickHandler = marker.AddComponent<AnomalyMarkerClickHandler>();
            clickHandler.Initialize(anomaly, OnMarkerClicked);

            // Add rotation
            RotateEffect rotateEffect = marker.AddComponent<RotateEffect>();
            rotateEffect.Initialize(30f);
        }

        void CreateMarkerLabel(GameObject marker, AnomalyData anomaly)
        {
            GameObject labelObj = new GameObject("Label");
            labelObj.transform.SetParent(marker.transform);
            labelObj.transform.localPosition = Vector3.up * 0.1f;

            Canvas labelCanvas = labelObj.AddComponent<Canvas>();
            labelCanvas.renderMode = RenderMode.WorldSpace;

            RectTransform rect = labelObj.GetComponent<RectTransform>();
            rect.sizeDelta = new Vector2(0.4f, 0.15f);

            Text labelText = labelObj.AddComponent<Text>();
            labelText.text = $"{anomaly.anomaly_type}\n{anomaly.severity}\n{anomaly.anomaly_score:F2}";
            labelText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            labelText.fontSize = 20;
            labelText.color = Color.white;
            labelText.alignment = TextAnchor.MiddleCenter;

            Image background = labelObj.AddComponent<Image>();
            background.color = new Color(0, 0, 0, 0.8f);
        }

        void UpdateAnomalyMarker(AnomalyData anomaly)
        {
            if (!anomalyMarkers.ContainsKey(anomaly.anomaly_id)) return;

            GameObject marker = anomalyMarkers[anomaly.anomaly_id];

            // Update label if it exists
            Text label = marker.GetComponentInChildren<Text>();
            if (label != null)
            {
                label.text = $"{anomaly.anomaly_type}\n{anomaly.severity}\n{anomaly.anomaly_score:F2}";
            }

            // Fade if acknowledged
            if (anomaly.acknowledged)
            {
                Renderer renderer = marker.GetComponent<Renderer>();
                if (renderer != null)
                {
                    Color color = renderer.material.color;
                    color.a = 0.3f;
                    renderer.material.color = color;
                }
            }
        }

        void RemoveAnomalyMarker(string anomalyId)
        {
            if (anomalyMarkers.ContainsKey(anomalyId))
            {
                GameObject marker = anomalyMarkers[anomalyId];
                if (marker != null)
                {
                    Destroy(marker);
                }
                anomalyMarkers.Remove(anomalyId);
                anomalyTimestamps.Remove(anomalyId);
            }
        }

        void CheckAutoAcknowledge()
        {
            List<string> toAcknowledge = new List<string>();

            foreach (var kvp in anomalyTimestamps)
            {
                if (Time.time - kvp.Value > autoAcknowledgeDelay)
                {
                    toAcknowledge.Add(kvp.Key);
                }
            }

            foreach (var id in toAcknowledge)
            {
                AcknowledgeAnomaly(id);
            }
        }

        void OnMarkerClicked(AnomalyData anomaly)
        {
            ShowAnomalyDetails(anomaly);
            Debug.Log($"[AnomalyMarker] Clicked: {anomaly.description}");
        }

        void ShowAnomalyDetails(AnomalyData anomaly)
        {
            // Display detailed panel (implement in full system)
            string details = $"Anomaly: {anomaly.anomaly_type}\n";
            details += $"Severity: {anomaly.severity}\n";
            details += $"Score: {anomaly.anomaly_score:F2}\n";
            details += $"Description: {anomaly.description}\n";
            details += $"Recommendation: {anomaly.recommended_action}";

            Debug.Log(details);
        }

        /// <summary>
        /// Acknowledge an anomaly
        /// </summary>
        public void AcknowledgeAnomaly(string anomalyId)
        {
            StartCoroutine(AcknowledgeAnomalyAsync(anomalyId));
        }

        IEnumerator AcknowledgeAnomalyAsync(string anomalyId)
        {
            string url = $"{flaskServerUrl}/api/v1/predictive/anomalies/{anomalyId}/acknowledge";

            using (var request = new HttpRequestMessage(HttpMethod.Post, url))
            {
                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (!task.IsFaulted && task.Result != null && task.Result.IsSuccessStatusCode)
                {
                    acknowledgedAnomalies++;
                    OnAnomalyAcknowledged?.Invoke(anomalyId);
                    Debug.Log($"[AnomalyMarker] Acknowledged anomaly: {anomalyId}");
                }
            }
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_detected", totalAnomaliesDetected},
                {"active_anomalies", activeAnomalyCount},
                {"acknowledged_anomalies", acknowledgedAnomalies},
                {"anomalies_by_type", anomaliesByType},
                {"active_markers", anomalyMarkers.Count},
                {"last_update", lastUpdateTime}
            };
        }

        void OnDestroy()
        {
            if (httpClient != null) httpClient.Dispose();
        }
    }

    /// <summary>
    /// Click handler for anomaly markers
    /// </summary>
    public class AnomalyMarkerClickHandler : MonoBehaviour
    {
        private AnomalyMarker.AnomalyData anomalyData;
        private Action<AnomalyMarker.AnomalyData> clickCallback;

        public void Initialize(AnomalyMarker.AnomalyData data, Action<AnomalyMarker.AnomalyData> callback)
        {
            anomalyData = data;
            clickCallback = callback;
        }

        void OnMouseDown()
        {
            clickCallback?.Invoke(anomalyData);
        }
    }

    /// <summary>
    /// Rotation effect for markers
    /// </summary>
    public class RotateEffect : MonoBehaviour
    {
        private float rotationSpeed;

        public void Initialize(float speed)
        {
            rotationSpeed = speed;
        }

        void Update()
        {
            transform.Rotate(Vector3.up, rotationSpeed * Time.deltaTime);
        }
    }
}
