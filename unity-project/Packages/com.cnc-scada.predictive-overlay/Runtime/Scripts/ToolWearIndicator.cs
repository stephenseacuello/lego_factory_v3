using UnityEngine;
using System;
using System.Collections.Generic;
using System.Net.Http;
using Newtonsoft.Json;

namespace CNCScada.Predictive
{
    /// <summary>
    /// Visualizes tool wear and RUL predictions
    /// Shows real-time wear progression, remaining useful life, and replacement recommendations
    /// </summary>
    public class ToolWearIndicator : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";

        [Header("Visual Settings")]
        [SerializeField] private Transform toolTransform;
        [SerializeField] private Material wearMaterial;
        [SerializeField] private Gradient wearGradient;
        [SerializeField] private bool showRULLabel = true;
        [SerializeField] private bool showWearHeatmap = true;

        [Header("Thresholds")]
        [SerializeField] private float warningThreshold = 70f; // % wear
        [SerializeField] private float criticalThreshold = 90f; // % wear
        [SerializeField] private float minRULHours = 8f; // Alert if RUL < 8 hours

        [Header("Update Settings")]
        [SerializeField] private float updateInterval = 5f;
        [SerializeField] private bool autoRefresh = true;

        #endregion

        #region Private Fields

        private HttpClient _httpClient;
        private ToolWearData _currentWear;
        private List<ToolWearHistory> _wearHistory;
        private Renderer _toolRenderer;
        private LineRenderer _wearGraphRenderer;
        private float _lastUpdateTime;

        #endregion

        #region Events

        public event Action<ToolWearData> OnWearUpdate;
        public event Action<float> OnWarningThresholdExceeded;
        public event Action<float> OnCriticalThresholdExceeded;
        public event Action<float> OnLowRUL;
        public event Action<string> OnError;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(5);
            _wearHistory = new List<ToolWearHistory>();

            if (toolTransform != null)
            {
                _toolRenderer = toolTransform.GetComponent<Renderer>();
            }

            InitializeGradient();
            LoadToolWear();
        }

        void Update()
        {
            if (autoRefresh && Time.time - _lastUpdateTime >= updateInterval)
            {
                LoadToolWear();
                _lastUpdateTime = Time.time;
            }

            UpdateVisualization();
        }

        void OnDestroy()
        {
            _httpClient?.Dispose();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Load current tool wear data
        /// </summary>
        public void LoadToolWear()
        {
            StartCoroutine(FetchToolWear());
        }

        /// <summary>
        /// Get current wear percentage
        /// </summary>
        public float GetWearPercent()
        {
            return _currentWear?.wearPercent ?? 0f;
        }

        /// <summary>
        /// Get remaining useful life in hours
        /// </summary>
        public float GetRemainingLife()
        {
            return _currentWear?.remainingLifeHours ?? 0f;
        }

        /// <summary>
        /// Check if tool needs replacement
        /// </summary>
        public bool NeedsReplacement()
        {
            if (_currentWear == null) return false;
            return _currentWear.wearPercent >= criticalThreshold ||
                   _currentWear.remainingLifeHours <= minRULHours;
        }

        /// <summary>
        /// Get tool wear status
        /// </summary>
        public ToolWearStatus GetStatus()
        {
            if (_currentWear == null) return ToolWearStatus.Unknown;
            if (_currentWear.wearPercent >= criticalThreshold) return ToolWearStatus.Critical;
            if (_currentWear.wearPercent >= warningThreshold) return ToolWearStatus.Warning;
            return ToolWearStatus.Good;
        }

        /// <summary>
        /// Get wear trend (increasing/decreasing rate)
        /// </summary>
        public float GetWearTrend()
        {
            if (_wearHistory.Count < 2) return 0f;

            var recent = _wearHistory[_wearHistory.Count - 1];
            var previous = _wearHistory[_wearHistory.Count - 2];

            var timeDiff = (recent.timestamp - previous.timestamp).TotalHours;
            if (timeDiff <= 0) return 0f;

            return (recent.wearPercent - previous.wearPercent) / (float)timeDiff;
        }

        #endregion

        #region Private Methods

        private void InitializeGradient()
        {
            if (wearGradient == null || wearGradient.colorKeys.Length == 0)
            {
                wearGradient = new Gradient();
                wearGradient.colorKeys = new GradientColorKey[]
                {
                    new GradientColorKey(Color.green, 0.0f),   // 0% wear
                    new GradientColorKey(Color.yellow, 0.5f),  // 50% wear
                    new GradientColorKey(Color.red, 1.0f)      // 100% wear
                };
            }
        }

        private System.Collections.IEnumerator FetchToolWear()
        {
            var url = $"{flaskServerUrl}/api/predictive/tool-wear?machine_id={machineId}";
            var task = _httpClient.GetStringAsync(url);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted)
            {
                Debug.LogWarning($"[ToolWear] Fetch failed: {task.Exception?.Message}");
                OnError?.Invoke($"Failed to load tool wear: {task.Exception?.Message}");
                yield break;
            }

            try
            {
                var response = JsonConvert.DeserializeObject<ToolWearResponse>(task.Result);
                _currentWear = response.currentWear;

                // Add to history
                _wearHistory.Add(new ToolWearHistory
                {
                    timestamp = DateTime.Now,
                    wearPercent = _currentWear.wearPercent,
                    remainingLifeHours = _currentWear.remainingLifeHours
                });

                // Limit history size
                while (_wearHistory.Count > 100)
                {
                    _wearHistory.RemoveAt(0);
                }

                CheckThresholds();
                OnWearUpdate?.Invoke(_currentWear);
            }
            catch (Exception e)
            {
                Debug.LogError($"[ToolWear] Parse error: {e.Message}");
                OnError?.Invoke($"Parse error: {e.Message}");
            }
        }

        private void UpdateVisualization()
        {
            if (_currentWear == null) return;

            // Update tool color based on wear
            if (_toolRenderer != null && showWearHeatmap)
            {
                float normalizedWear = _currentWear.wearPercent / 100f;
                Color wearColor = wearGradient.Evaluate(normalizedWear);

                if (wearMaterial != null)
                {
                    wearMaterial.color = wearColor;
                    _toolRenderer.material = wearMaterial;
                }
                else
                {
                    _toolRenderer.material.color = wearColor;
                }
            }

            // Update RUL label
            if (showRULLabel && toolTransform != null)
            {
                UpdateRULLabel();
            }
        }

        private void UpdateRULLabel()
        {
            var canvas = toolTransform.GetComponentInChildren<Canvas>();
            if (canvas == null)
            {
                canvas = CreateRULLabel();
            }

            var text = canvas.GetComponentInChildren<UnityEngine.UI.Text>();
            if (text != null)
            {
                text.text = $"Wear: {_currentWear.wearPercent:F1}%\nRUL: {_currentWear.remainingLifeHours:F1}h";
                text.color = GetStatusColor();
            }
        }

        private Canvas CreateRULLabel()
        {
            var labelObj = new GameObject("RUL_Label");
            labelObj.transform.SetParent(toolTransform);
            labelObj.transform.localPosition = Vector3.up * 0.5f;

            var canvas = labelObj.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;

            var text = labelObj.AddComponent<UnityEngine.UI.Text>();
            text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            text.fontSize = 20;
            text.alignment = TextAnchor.MiddleCenter;
            text.color = Color.white;

            var rectTransform = labelObj.GetComponent<RectTransform>();
            rectTransform.sizeDelta = new Vector2(150, 60);
            rectTransform.localScale = Vector3.one * 0.01f;

            // Make label face camera
            if (Camera.main != null)
            {
                labelObj.transform.LookAt(Camera.main.transform);
                labelObj.transform.Rotate(0, 180, 0);
            }

            return canvas;
        }

        private void CheckThresholds()
        {
            if (_currentWear == null) return;

            if (_currentWear.wearPercent >= criticalThreshold)
            {
                OnCriticalThresholdExceeded?.Invoke(_currentWear.wearPercent);
            }
            else if (_currentWear.wearPercent >= warningThreshold)
            {
                OnWarningThresholdExceeded?.Invoke(_currentWear.wearPercent);
            }

            if (_currentWear.remainingLifeHours <= minRULHours)
            {
                OnLowRUL?.Invoke(_currentWear.remainingLifeHours);
            }
        }

        private Color GetStatusColor()
        {
            switch (GetStatus())
            {
                case ToolWearStatus.Good: return Color.green;
                case ToolWearStatus.Warning: return Color.yellow;
                case ToolWearStatus.Critical: return Color.red;
                default: return Color.gray;
            }
        }

        #endregion

        #region Gizmos

        void OnDrawGizmos()
        {
            if (!Application.isPlaying || _currentWear == null || toolTransform == null) return;

            // Draw wear percentage as a sphere
            Gizmos.color = wearGradient.Evaluate(_currentWear.wearPercent / 100f);
            Gizmos.DrawWireSphere(toolTransform.position, 0.1f);
        }

        #endregion
    }

    #region Data Classes

    [Serializable]
    public class ToolWearResponse
    {
        public string machineId;
        public ToolWearData currentWear;
        public List<ToolWearPrediction> predictions;
    }

    [Serializable]
    public class ToolWearData
    {
        public string toolId;
        public string toolType;
        public float wearPercent;
        public float remainingLifeHours;
        public int cuttingTime; // seconds
        public float confidence;
        public DateTime lastMeasurement;
    }

    [Serializable]
    public class ToolWearPrediction
    {
        public DateTime predictedDate;
        public float predictedWear;
        public float confidence;
    }

    public class ToolWearHistory
    {
        public DateTime timestamp;
        public float wearPercent;
        public float remainingLifeHours;
    }

    public enum ToolWearStatus
    {
        Unknown,
        Good,
        Warning,
        Critical
    }

    #endregion
}
