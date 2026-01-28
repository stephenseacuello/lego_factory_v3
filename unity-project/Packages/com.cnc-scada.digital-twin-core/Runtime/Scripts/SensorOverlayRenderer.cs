using UnityEngine;
using System;
using System.Collections.Generic;
using System.Net.Http;
using Newtonsoft.Json;

namespace CNCScada.DigitalTwin
{
    /// <summary>
    /// Renders sensor data overlays (temperature, vibration, stress)
    /// Supports heatmaps, 3D markers, and real-time data visualization
    /// </summary>
    public class SensorOverlayRenderer : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";

        [Header("Overlay Types")]
        [SerializeField] private bool showTemperature = true;
        [SerializeField] private bool showVibration = true;
        [SerializeField] private bool showStress = false;
        [SerializeField] private bool showToolWear = true;

        [Header("Heatmap Settings")]
        [SerializeField] private Gradient temperatureGradient;
        [SerializeField] private Gradient vibrationGradient;
        [SerializeField] private float heatmapAlpha = 0.7f;
        [SerializeField] private float heatmapResolution = 10f; // points per 100mm

        [Header("Marker Settings")]
        [SerializeField] private GameObject sensorMarkerPrefab;
        [SerializeField] private float markerScale = 1.0f;
        [SerializeField] private bool showLabels = true;
        [SerializeField] private Font labelFont;

        [Header("Update Settings")]
        [SerializeField] private float updateInterval = 1.0f;
        [SerializeField] private int maxDataPoints = 100;

        [Header("Thresholds")]
        [SerializeField] private float temperatureWarning = 60f; // °C
        [SerializeField] private float temperatureCritical = 80f; // °C
        [SerializeField] private float vibrationWarning = 0.5f; // g
        [SerializeField] private float vibrationCritical = 1.0f; // g

        #endregion

        #region Private Fields

        private HttpClient _httpClient;
        private List<SensorDataPoint> _sensorData;
        private Dictionary<string, GameObject> _sensorMarkers;
        private Material _heatmapMaterial;
        private Texture2D _heatmapTexture;
        private MeshRenderer _meshRenderer;
        private float _lastUpdateTime;

        #endregion

        #region Events

        public event Action<SensorDataPoint> OnSensorUpdate;
        public event Action<string, float> OnThresholdExceeded;
        public event Action<string> OnError;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(5);
            _sensorData = new List<SensorDataPoint>();
            _sensorMarkers = new Dictionary<string, GameObject>();

            InitializeGradients();
            InitializeHeatmap();

            StartCoroutine(UpdateSensorData());
        }

        void Update()
        {
            if (Time.time - _lastUpdateTime >= updateInterval)
            {
                UpdateVisualization();
                _lastUpdateTime = Time.time;
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
        /// Add sensor data point manually
        /// </summary>
        public void AddSensorData(SensorDataPoint dataPoint)
        {
            _sensorData.Add(dataPoint);

            // Limit data points for memory
            while (_sensorData.Count > maxDataPoints)
            {
                _sensorData.RemoveAt(0);
            }

            CheckThresholds(dataPoint);
            OnSensorUpdate?.Invoke(dataPoint);
        }

        /// <summary>
        /// Clear all sensor data and markers
        /// </summary>
        public void ClearData()
        {
            _sensorData.Clear();
            ClearMarkers();
            UpdateHeatmap();
        }

        /// <summary>
        /// Get latest sensor value for type
        /// </summary>
        public float GetLatestValue(string sensorType)
        {
            for (int i = _sensorData.Count - 1; i >= 0; i--)
            {
                if (_sensorData[i].type == sensorType)
                {
                    return _sensorData[i].value;
                }
            }
            return 0f;
        }

        /// <summary>
        /// Get average sensor value over time window
        /// </summary>
        public float GetAverageValue(string sensorType, float timeWindowSeconds)
        {
            float sum = 0f;
            int count = 0;
            long cutoffTime = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() - (long)(timeWindowSeconds * 1000);

            foreach (var point in _sensorData)
            {
                if (point.type == sensorType && point.timestamp >= cutoffTime)
                {
                    sum += point.value;
                    count++;
                }
            }

            return count > 0 ? sum / count : 0f;
        }

        /// <summary>
        /// Toggle overlay visibility
        /// </summary>
        public void SetOverlayVisible(string overlayType, bool visible)
        {
            switch (overlayType.ToLower())
            {
                case "temperature":
                    showTemperature = visible;
                    break;
                case "vibration":
                    showVibration = visible;
                    break;
                case "stress":
                    showStress = visible;
                    break;
                case "toolwear":
                    showToolWear = visible;
                    break;
            }
            UpdateVisualization();
        }

        #endregion

        #region Private Methods

        private void InitializeGradients()
        {
            // Default temperature gradient: blue -> green -> yellow -> red
            if (temperatureGradient == null || temperatureGradient.colorKeys.Length == 0)
            {
                temperatureGradient = new Gradient();
                temperatureGradient.colorKeys = new GradientColorKey[]
                {
                    new GradientColorKey(Color.blue, 0.0f),
                    new GradientColorKey(Color.green, 0.4f),
                    new GradientColorKey(Color.yellow, 0.7f),
                    new GradientColorKey(Color.red, 1.0f)
                };
            }

            // Default vibration gradient: green -> yellow -> orange -> red
            if (vibrationGradient == null || vibrationGradient.colorKeys.Length == 0)
            {
                vibrationGradient = new Gradient();
                vibrationGradient.colorKeys = new GradientColorKey[]
                {
                    new GradientColorKey(Color.green, 0.0f),
                    new GradientColorKey(Color.yellow, 0.5f),
                    new GradientColorKey(new Color(1f, 0.5f, 0f), 0.75f), // orange
                    new GradientColorKey(Color.red, 1.0f)
                };
            }
        }

        private void InitializeHeatmap()
        {
            _heatmapTexture = new Texture2D(256, 256, TextureFormat.RGBA32, false);
            _heatmapMaterial = new Material(Shader.Find("Standard"));
            _heatmapMaterial.SetTexture("_MainTex", _heatmapTexture);

            _meshRenderer = GetComponent<MeshRenderer>();
            if (_meshRenderer != null)
            {
                _meshRenderer.material = _heatmapMaterial;
            }
        }

        private System.Collections.IEnumerator UpdateSensorData()
        {
            while (true)
            {
                yield return new WaitForSeconds(updateInterval);

                var url = $"{flaskServerUrl}/api/sensors/latest?machine_id={machineId}";
                var task = _httpClient.GetStringAsync(url);

                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted)
                {
                    Debug.LogWarning($"[SensorOverlay] Fetch failed: {task.Exception?.Message}");
                    OnError?.Invoke($"Sensor fetch failed: {task.Exception?.Message}");
                    continue;
                }

                try
                {
                    var response = JsonConvert.DeserializeObject<SensorResponse>(task.Result);
                    if (response.sensors != null)
                    {
                        foreach (var sensor in response.sensors)
                        {
                            AddSensorData(sensor);
                        }
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"[SensorOverlay] Parse error: {e.Message}");
                    OnError?.Invoke($"Parse error: {e.Message}");
                }
            }
        }

        private void UpdateVisualization()
        {
            UpdateMarkers();
            UpdateHeatmap();
        }

        private void UpdateMarkers()
        {
            if (!showLabels) return;

            // Create/update markers for latest sensor values
            var sensorTypes = new HashSet<string>();
            foreach (var point in _sensorData)
            {
                sensorTypes.Add(point.type);
            }

            foreach (var sensorType in sensorTypes)
            {
                if (!ShouldShowSensor(sensorType)) continue;

                float value = GetLatestValue(sensorType);
                Vector3 position = GetSensorPosition(sensorType);

                UpdateMarker(sensorType, position, value);
            }
        }

        private void UpdateMarker(string sensorType, Vector3 position, float value)
        {
            GameObject marker;
            if (!_sensorMarkers.TryGetValue(sensorType, out marker))
            {
                // Create new marker
                if (sensorMarkerPrefab != null)
                {
                    marker = Instantiate(sensorMarkerPrefab, transform);
                }
                else
                {
                    marker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                    marker.transform.SetParent(transform);
                }

                marker.name = $"Sensor_{sensorType}";
                _sensorMarkers[sensorType] = marker;
            }

            marker.transform.localPosition = position;
            marker.transform.localScale = Vector3.one * markerScale;

            // Color based on sensor type and value
            var renderer = marker.GetComponent<Renderer>();
            if (renderer != null)
            {
                renderer.material.color = GetSensorColor(sensorType, value);
            }

            // Update label
            if (showLabels)
            {
                UpdateMarkerLabel(marker, sensorType, value);
            }
        }

        private void UpdateMarkerLabel(GameObject marker, string sensorType, float value)
        {
            var canvas = marker.GetComponentInChildren<Canvas>();
            if (canvas == null)
            {
                var labelObj = new GameObject("Label");
                labelObj.transform.SetParent(marker.transform);
                labelObj.transform.localPosition = Vector3.up * 2f;

                canvas = labelObj.AddComponent<Canvas>();
                canvas.renderMode = RenderMode.WorldSpace;

                var text = labelObj.AddComponent<UnityEngine.UI.Text>();
                text.font = labelFont != null ? labelFont : Resources.GetBuiltinResource<Font>("Arial.ttf");
                text.fontSize = 14;
                text.alignment = TextAnchor.MiddleCenter;
                text.color = Color.white;

                var rectTransform = labelObj.GetComponent<RectTransform>();
                rectTransform.sizeDelta = new Vector2(100, 30);
                rectTransform.localScale = Vector3.one * 0.1f;
            }

            var textComponent = canvas.GetComponentInChildren<UnityEngine.UI.Text>();
            if (textComponent != null)
            {
                string unit = GetSensorUnit(sensorType);
                textComponent.text = $"{sensorType}: {value:F1}{unit}";
            }
        }

        private void UpdateHeatmap()
        {
            if (!showTemperature && !showVibration) return;

            // Clear texture
            Color[] pixels = new Color[256 * 256];
            for (int i = 0; i < pixels.Length; i++)
            {
                pixels[i] = Color.clear;
            }

            // Render sensor data as heatmap
            foreach (var point in _sensorData)
            {
                if (!ShouldShowSensor(point.type)) continue;

                var normalizedPos = NormalizePosition(point.position);
                int x = Mathf.Clamp((int)(normalizedPos.x * 256), 0, 255);
                int y = Mathf.Clamp((int)(normalizedPos.y * 256), 0, 255);

                Color color = GetSensorColor(point.type, point.value);
                color.a = heatmapAlpha;

                // Apply with blur
                int radius = 3;
                for (int dx = -radius; dx <= radius; dx++)
                {
                    for (int dy = -radius; dy <= radius; dy++)
                    {
                        int px = Mathf.Clamp(x + dx, 0, 255);
                        int py = Mathf.Clamp(y + dy, 0, 255);
                        float dist = Mathf.Sqrt(dx * dx + dy * dy);
                        float weight = Mathf.Exp(-dist * dist / (2f * radius * radius));

                        pixels[py * 256 + px] = Color.Lerp(pixels[py * 256 + px], color, weight);
                    }
                }
            }

            _heatmapTexture.SetPixels(pixels);
            _heatmapTexture.Apply();
        }

        private void CheckThresholds(SensorDataPoint point)
        {
            if (point.type == "temperature")
            {
                if (point.value >= temperatureCritical)
                {
                    OnThresholdExceeded?.Invoke("temperature", point.value);
                }
                else if (point.value >= temperatureWarning)
                {
                    OnThresholdExceeded?.Invoke("temperature_warning", point.value);
                }
            }
            else if (point.type == "vibration")
            {
                if (point.value >= vibrationCritical)
                {
                    OnThresholdExceeded?.Invoke("vibration", point.value);
                }
                else if (point.value >= vibrationWarning)
                {
                    OnThresholdExceeded?.Invoke("vibration_warning", point.value);
                }
            }
        }

        private bool ShouldShowSensor(string sensorType)
        {
            switch (sensorType.ToLower())
            {
                case "temperature": return showTemperature;
                case "vibration": return showVibration;
                case "stress": return showStress;
                case "toolwear": return showToolWear;
                default: return true;
            }
        }

        private Color GetSensorColor(string sensorType, float value)
        {
            switch (sensorType.ToLower())
            {
                case "temperature":
                    float tempNorm = Mathf.Clamp01(value / 100f);
                    return temperatureGradient.Evaluate(tempNorm);
                case "vibration":
                    float vibNorm = Mathf.Clamp01(value / 2f);
                    return vibrationGradient.Evaluate(vibNorm);
                default:
                    return Color.gray;
            }
        }

        private Vector3 GetSensorPosition(string sensorType)
        {
            // Default positions - should be configured per machine
            switch (sensorType.ToLower())
            {
                case "temperature": return new Vector3(0, 10, 0);
                case "vibration": return new Vector3(0, 5, 0);
                case "toolwear": return new Vector3(0, 15, 0);
                default: return Vector3.zero;
            }
        }

        private Vector2 NormalizePosition(Vector3 position)
        {
            // Normalize to 0-1 range for heatmap
            return new Vector2(
                (position.x + 100) / 200f,
                (position.z + 100) / 200f
            );
        }

        private string GetSensorUnit(string sensorType)
        {
            switch (sensorType.ToLower())
            {
                case "temperature": return "°C";
                case "vibration": return "g";
                case "stress": return "MPa";
                case "toolwear": return "%";
                default: return "";
            }
        }

        private void ClearMarkers()
        {
            foreach (var marker in _sensorMarkers.Values)
            {
                if (marker != null)
                {
                    Destroy(marker);
                }
            }
            _sensorMarkers.Clear();
        }

        #endregion
    }

    #region Data Classes

    [Serializable]
    public class SensorResponse
    {
        public string machineId;
        public List<SensorDataPoint> sensors;
    }

    [Serializable]
    public class SensorDataPoint
    {
        public string type; // temperature, vibration, stress, etc.
        public float value;
        public Vector3 position;
        public long timestamp;
        public string unit;
    }

    #endregion
}
