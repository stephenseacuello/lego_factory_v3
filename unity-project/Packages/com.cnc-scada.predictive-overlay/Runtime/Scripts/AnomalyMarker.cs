using UnityEngine;
using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Linq;
using Newtonsoft.Json;

namespace CNCScada.Predictive
{
    /// <summary>
    /// 3D markers for detected anomalies
    /// Shows anomaly location, type, severity, and recommended actions
    /// </summary>
    public class AnomalyMarker : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";

        [Header("Marker Settings")]
        [SerializeField] private GameObject markerPrefab;
        [SerializeField] private float markerScale = 1.0f;
        [SerializeField] private bool animateMarkers = true;
        [SerializeField] private float animationSpeed = 2f;

        [Header("Colors by Severity")]
        [SerializeField] private Color lowSeverityColor = Color.yellow;
        [SerializeField] private Color mediumSeverityColor = new Color(1f, 0.5f, 0f); // orange
        [SerializeField] private Color highSeverityColor = Color.red;
        [SerializeField] private Color criticalSeverityColor = new Color(0.8f, 0f, 0f); // dark red

        [Header("Filtering")]
        [SerializeField] private float minConfidence = 0.6f;
        [SerializeField] private bool showResolvedAnomalies = false;
        [SerializeField] private int maxAnomalies = 50;

        [Header("Update Settings")]
        [SerializeField] private float updateInterval = 10f;
        [SerializeField] private bool autoRefresh = true;

        #endregion

        #region Private Fields

        private HttpClient _httpClient;
        private List<Anomaly> _anomalies;
        private Dictionary<string, GameObject> _markers;
        private float _lastUpdateTime;

        #endregion

        #region Events

        public event Action<Anomaly> OnAnomalyDetected;
        public event Action<Anomaly> OnAnomalyClicked;
        public event Action<Anomaly> OnAnomalyResolved;
        public event Action<string> OnError;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(10);
            _anomalies = new List<Anomaly>();
            _markers = new Dictionary<string, GameObject>();

            LoadAnomalies();
        }

        void Update()
        {
            if (autoRefresh && Time.time - _lastUpdateTime >= updateInterval)
            {
                LoadAnomalies();
                _lastUpdateTime = Time.time;
            }

            if (animateMarkers)
            {
                AnimateMarkers();
            }
        }

        void OnDestroy()
        {
            _httpClient?.Dispose();
            ClearMarkers();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Load anomalies from backend
        /// </summary>
        public void LoadAnomalies()
        {
            StartCoroutine(FetchAnomalies());
        }

        /// <summary>
        /// Filter anomalies by type
        /// </summary>
        public void FilterByType(AnomalyType type)
        {
            foreach (var kvp in _markers)
            {
                var anomaly = _anomalies.FirstOrDefault(a => a.id == kvp.Key);
                bool visible = anomaly != null && (type == AnomalyType.All || anomaly.type == type);
                kvp.Value.SetActive(visible);
            }
        }

        /// <summary>
        /// Filter by severity
        /// </summary>
        public void FilterBySeverity(AnomalySeverity minSeverity)
        {
            foreach (var kvp in _markers)
            {
                var anomaly = _anomalies.FirstOrDefault(a => a.id == kvp.Key);
                bool visible = anomaly != null && anomaly.severity >= minSeverity;
                kvp.Value.SetActive(visible);
            }
        }

        /// <summary>
        /// Get active anomalies
        /// </summary>
        public List<Anomaly> GetActiveAnomalies()
        {
            return _anomalies.Where(a => !a.isResolved).ToList();
        }

        /// <summary>
        /// Get critical anomalies
        /// </summary>
        public List<Anomaly> GetCriticalAnomalies()
        {
            return _anomalies.Where(a => !a.isResolved && a.severity == AnomalySeverity.Critical).ToList();
        }

        /// <summary>
        /// Mark anomaly as resolved
        /// </summary>
        public void ResolveAnomaly(string anomalyId, string resolution)
        {
            StartCoroutine(SendResolveRequest(anomalyId, resolution));
        }

        /// <summary>
        /// Highlight specific anomaly
        /// </summary>
        public void HighlightAnomaly(string anomalyId, bool highlight)
        {
            if (_markers.TryGetValue(anomalyId, out GameObject marker))
            {
                var scale = highlight ? Vector3.one * markerScale * 1.5f : Vector3.one * markerScale;
                marker.transform.localScale = scale;
            }
        }

        #endregion

        #region Private Methods

        private System.Collections.IEnumerator FetchAnomalies()
        {
            var url = $"{flaskServerUrl}/api/predictive/anomalies?machine_id={machineId}&min_confidence={minConfidence}&include_resolved={showResolvedAnomalies}";
            var task = _httpClient.GetStringAsync(url);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted)
            {
                Debug.LogWarning($"[AnomalyMarker] Fetch failed: {task.Exception?.Message}");
                OnError?.Invoke($"Failed to load anomalies: {task.Exception?.Message}");
                yield break;
            }

            try
            {
                var response = JsonConvert.DeserializeObject<AnomalyResponse>(task.Result);
                var newAnomalies = response.anomalies ?? new List<Anomaly>();

                // Check for new anomalies
                foreach (var anomaly in newAnomalies)
                {
                    if (!_anomalies.Any(a => a.id == anomaly.id))
                    {
                        OnAnomalyDetected?.Invoke(anomaly);
                    }
                }

                _anomalies = newAnomalies.Take(maxAnomalies).ToList();
                RefreshMarkers();
            }
            catch (Exception e)
            {
                Debug.LogError($"[AnomalyMarker] Parse error: {e.Message}");
                OnError?.Invoke($"Parse error: {e.Message}");
            }
        }

        private void RefreshMarkers()
        {
            // Remove markers for anomalies that no longer exist
            var anomalyIds = new HashSet<string>(_anomalies.Select(a => a.id));
            var toRemove = _markers.Keys.Where(id => !anomalyIds.Contains(id)).ToList();
            foreach (var id in toRemove)
            {
                if (_markers[id] != null)
                {
                    Destroy(_markers[id]);
                }
                _markers.Remove(id);
            }

            // Create/update markers
            foreach (var anomaly in _anomalies)
            {
                if (_markers.ContainsKey(anomaly.id))
                {
                    UpdateMarker(anomaly);
                }
                else
                {
                    CreateMarker(anomaly);
                }
            }
        }

        private void CreateMarker(Anomaly anomaly)
        {
            GameObject markerObj;
            if (markerPrefab != null)
            {
                markerObj = Instantiate(markerPrefab, transform);
            }
            else
            {
                markerObj = CreateDefaultMarker(anomaly);
            }

            markerObj.name = $"Anomaly_{anomaly.id}";
            markerObj.transform.localPosition = anomaly.location;
            markerObj.transform.localScale = Vector3.one * markerScale;

            // Set color based on severity
            var renderer = markerObj.GetComponent<Renderer>();
            if (renderer != null)
            {
                renderer.material.color = GetSeverityColor(anomaly.severity);
            }

            // Add click handler
            var clickHandler = markerObj.AddComponent<AnomalyClickHandler>();
            clickHandler.Initialize(anomaly, () => OnAnomalyClicked?.Invoke(anomaly));

            // Add label
            CreateAnomalyLabel(markerObj, anomaly);

            // Add particle effect for critical anomalies
            if (anomaly.severity == AnomalySeverity.Critical)
            {
                AddParticleEffect(markerObj, GetSeverityColor(anomaly.severity));
            }

            _markers[anomaly.id] = markerObj;
        }

        private GameObject CreateDefaultMarker(Anomaly anomaly)
        {
            var markerObj = GameObject.CreatePrimitive(PrimitiveType.Cube);
            markerObj.transform.SetParent(transform);
            return markerObj;
        }

        private void UpdateMarker(Anomaly anomaly)
        {
            if (!_markers.TryGetValue(anomaly.id, out GameObject marker)) return;

            // Update color if severity changed
            var renderer = marker.GetComponent<Renderer>();
            if (renderer != null)
            {
                renderer.material.color = GetSeverityColor(anomaly.severity);
            }

            // Update label
            var canvas = marker.GetComponentInChildren<Canvas>();
            if (canvas != null)
            {
                var text = canvas.GetComponentInChildren<UnityEngine.UI.Text>();
                if (text != null)
                {
                    text.text = GetAnomalyLabelText(anomaly);
                }
            }

            // Hide if resolved
            if (anomaly.isResolved && !showResolvedAnomalies)
            {
                marker.SetActive(false);
            }
        }

        private void CreateAnomalyLabel(GameObject marker, Anomaly anomaly)
        {
            var canvas = new GameObject("Canvas");
            canvas.transform.SetParent(marker.transform);
            canvas.transform.localPosition = Vector3.up * 1.5f;

            var canvasComponent = canvas.AddComponent<Canvas>();
            canvasComponent.renderMode = RenderMode.WorldSpace;

            var text = canvas.AddComponent<UnityEngine.UI.Text>();
            text.text = GetAnomalyLabelText(anomaly);
            text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            text.fontSize = 18;
            text.alignment = TextAnchor.MiddleCenter;
            text.color = Color.white;

            var rectTransform = canvas.GetComponent<RectTransform>();
            rectTransform.sizeDelta = new Vector2(200, 80);
            rectTransform.localScale = Vector3.one * 0.01f;
        }

        private string GetAnomalyLabelText(Anomaly anomaly)
        {
            return $"{anomaly.type}\n{anomaly.severity}\n{anomaly.confidence:P0}";
        }

        private void AddParticleEffect(GameObject marker, Color color)
        {
            var particleObj = new GameObject("ParticleEffect");
            particleObj.transform.SetParent(marker.transform);
            particleObj.transform.localPosition = Vector3.zero;

            var particleSystem = particleObj.AddComponent<ParticleSystem>();
            var main = particleSystem.main;
            main.startColor = color;
            main.startSize = 0.2f;
            main.startLifetime = 1f;
            main.loop = true;

            var emission = particleSystem.emission;
            emission.rateOverTime = 10f;
        }

        private void AnimateMarkers()
        {
            float pulse = (Mathf.Sin(Time.time * animationSpeed) + 1f) / 2f;

            foreach (var kvp in _markers)
            {
                if (kvp.Value == null) continue;

                var anomaly = _anomalies.FirstOrDefault(a => a.id == kvp.Key);
                if (anomaly != null && !anomaly.isResolved)
                {
                    // Pulse scale for active anomalies
                    float scaleMultiplier = 1f + pulse * 0.2f;
                    kvp.Value.transform.localScale = Vector3.one * markerScale * scaleMultiplier;

                    // Rotate marker
                    kvp.Value.transform.Rotate(Vector3.up, animationSpeed * 20f * Time.deltaTime);
                }
            }
        }

        private Color GetSeverityColor(AnomalySeverity severity)
        {
            switch (severity)
            {
                case AnomalySeverity.Low: return lowSeverityColor;
                case AnomalySeverity.Medium: return mediumSeverityColor;
                case AnomalySeverity.High: return highSeverityColor;
                case AnomalySeverity.Critical: return criticalSeverityColor;
                default: return Color.gray;
            }
        }

        private System.Collections.IEnumerator SendResolveRequest(string anomalyId, string resolution)
        {
            var url = $"{flaskServerUrl}/api/predictive/anomalies/{anomalyId}/resolve";
            var data = new { resolution, resolvedBy = "Unity", resolvedAt = DateTime.UtcNow };

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                Debug.LogError("[AnomalyMarker] Resolve request failed");
                OnError?.Invoke("Failed to resolve anomaly");
            }
            else
            {
                Debug.Log($"[AnomalyMarker] Anomaly {anomalyId} resolved");
                var anomaly = _anomalies.FirstOrDefault(a => a.id == anomalyId);
                if (anomaly != null)
                {
                    anomaly.isResolved = true;
                    OnAnomalyResolved?.Invoke(anomaly);
                }
                LoadAnomalies(); // Refresh
            }
        }

        private void ClearMarkers()
        {
            foreach (var marker in _markers.Values)
            {
                if (marker != null)
                {
                    Destroy(marker);
                }
            }
            _markers.Clear();
        }

        #endregion
    }

    #region Helper Classes

    public class AnomalyClickHandler : MonoBehaviour
    {
        private Anomaly _anomaly;
        private Action _onClick;

        public void Initialize(Anomaly anomaly, Action onClick)
        {
            _anomaly = anomaly;
            _onClick = onClick;
        }

        void OnMouseDown()
        {
            _onClick?.Invoke();
        }
    }

    #endregion

    #region Data Classes

    [Serializable]
    public class AnomalyResponse
    {
        public string machineId;
        public List<Anomaly> anomalies;
    }

    [Serializable]
    public class Anomaly
    {
        public string id;
        public AnomalyType type;
        public AnomalySeverity severity;
        public Vector3 location;
        public float confidence;
        public DateTime detectedAt;
        public string description;
        public string recommendedAction;
        public bool isResolved;
        public DateTime? resolvedAt;
        public string resolution;
    }

    public enum AnomalyType
    {
        All,
        Vibration,
        Temperature,
        Power,
        Acoustic,
        ToolWear,
        PositionError,
        SpindleLoad
    }

    public enum AnomalySeverity
    {
        Low = 1,
        Medium = 2,
        High = 3,
        Critical = 4
    }

    #endregion
}
