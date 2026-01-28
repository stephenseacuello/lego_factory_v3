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
    /// Tool Wear Indicator with Predictive Life Estimation
    /// Visualizes tool condition and predicts remaining useful life
    /// Part of Phase 4: Predictive Maintenance
    /// </summary>
    public class ToolWearIndicator : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";
        [SerializeField] private float updateInterval = 5f;

        [Header("3D Tool References")]
        [SerializeField] private Transform toolTransform;
        [SerializeField] private Transform toolHolderTransform;
        [SerializeField] private Material newToolMaterial;
        [SerializeField] private Material wornToolMaterial;

        [Header("UI References")]
        [SerializeField] private Slider wearLevelSlider;
        [SerializeField] private Text wearPercentText;
        [SerializeField] private Text remainingLifeText;
        [SerializeField] private Text toolNumberText;
        [SerializeField] private Text toolTypeText;
        [SerializeField] private Image statusIndicator;
        [SerializeField] private GameObject warningPanel;
        [SerializeField] private Text warningText;

        [Header("Visual Settings")]
        [SerializeField] private Color healthyColor = Color.green;
        [SerializeField] private Color cautionColor = Color.yellow;
        [SerializeField] private Color criticalColor = Color.red;
        [SerializeField] private float cautionThreshold = 0.7f;
        [SerializeField] private float criticalThreshold = 0.9f;

        [Header("Wear Visualization")]
        [SerializeField] private bool enable3DWearVisualization = true;
        [SerializeField] private GameObject wearParticlePrefab;
        [SerializeField] private float particleEmissionRate = 10f;
        [SerializeField] private bool showWearHeatmap = true;

        [Header("Prediction Settings")]
        [SerializeField] private bool enablePrediction = true;
        [SerializeField] private int predictionHorizonHours = 24;
        [SerializeField] private bool showConfidenceInterval = true;

        // Data
        private HttpClient httpClient;
        private ToolWearData currentToolData;
        private List<float> wearHistory = new List<float>();
        private ParticleSystem wearParticles;

        // State
        private float lastUpdateTime = 0f;
        private bool warningActive = false;

        // Statistics
        private int totalTools = 0;
        private int toolsNeedingReplacement = 0;
        private float averageToolLife = 0f;

        // Events
        public event Action<ToolWearData> OnToolWearUpdated;
        public event Action<ToolWearData> OnToolWarning;
        public event Action<ToolWearData> OnToolCritical;

        [Serializable]
        public class ToolWearResponse
        {
            public bool success;
            public ToolWearData tool_data;
            public ToolPrediction prediction;
            public string error;
        }

        [Serializable]
        public class ToolWearData
        {
            public int tool_number;
            public string tool_type;
            public float wear_percent;
            public float remaining_life_hours;
            public float cutting_time_hours;
            public float total_cuts;
            public string condition; // healthy, caution, critical
            public List<WearMeasurement> measurements;
            public DateTime last_changed;
            public DateTime predicted_replacement;
        }

        [Serializable]
        public class WearMeasurement
        {
            public string measurement_type; // flank_wear, crater_wear, edge_chipping
            public float value_mm;
            public float threshold_mm;
            public float percent_of_threshold;
        }

        [Serializable]
        public class ToolPrediction
        {
            public float predicted_remaining_hours;
            public float confidence;
            public string replacement_recommendation;
            public float lower_bound_hours;
            public float upper_bound_hours;
        }

        void Start()
        {
            httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(10);

            SetupWearVisualization();
            StartCoroutine(UpdateToolDataPeriodically());

            Debug.Log("[ToolWearIndicator] Initialized for machine: " + machineId);
        }

        void SetupWearVisualization()
        {
            if (enable3DWearVisualization && toolTransform != null)
            {
                // Setup particle system for wear visualization
                if (wearParticlePrefab != null)
                {
                    GameObject particlesObj = Instantiate(wearParticlePrefab, toolTransform);
                    wearParticles = particlesObj.GetComponent<ParticleSystem>();
                }
                else
                {
                    GameObject particlesObj = new GameObject("WearParticles");
                    particlesObj.transform.SetParent(toolTransform);
                    particlesObj.transform.localPosition = Vector3.zero;
                    wearParticles = particlesObj.AddComponent<ParticleSystem>();

                    var main = wearParticles.main;
                    main.startSize = 0.005f;
                    main.startLifetime = 1f;
                    main.maxParticles = 100;

                    var emission = wearParticles.emission;
                    emission.rateOverTime = particleEmissionRate;
                }
            }
        }

        IEnumerator UpdateToolDataPeriodically()
        {
            while (true)
            {
                yield return new WaitForSeconds(updateInterval);
                FetchToolWearData();
            }
        }

        void FetchToolWearData()
        {
            StartCoroutine(FetchToolWearAsync());
        }

        IEnumerator FetchToolWearAsync()
        {
            string url = $"{flaskServerUrl}/api/v1/predictive/tool-wear?machine_id={machineId}";

            using (var request = new HttpRequestMessage(HttpMethod.Get, url))
            {
                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    Debug.LogError("[ToolWearIndicator] Failed to fetch tool wear data");
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                try
                {
                    ToolWearResponse response = JsonConvert.DeserializeObject<ToolWearResponse>(readTask.Result);

                    if (response.success)
                    {
                        UpdateToolWearDisplay(response);
                    }
                    else
                    {
                        Debug.LogError($"[ToolWearIndicator] Error: {response.error}");
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"[ToolWearIndicator] Parse error: {e.Message}");
                }
            }

            lastUpdateTime = Time.time;
        }

        void UpdateToolWearDisplay(ToolWearResponse response)
        {
            currentToolData = response.tool_data;

            // Update wear history
            wearHistory.Add(currentToolData.wear_percent);
            if (wearHistory.Count > 100)
            {
                wearHistory.RemoveAt(0);
            }

            // Update UI
            UpdateWearUI();

            // Update 3D visualization
            if (enable3DWearVisualization)
            {
                Update3DWearVisualization();
            }

            // Check for warnings
            CheckWearThresholds();

            // Update prediction display
            if (enablePrediction && response.prediction != null)
            {
                UpdatePredictionDisplay(response.prediction);
            }

            OnToolWearUpdated?.Invoke(currentToolData);
        }

        void UpdateWearUI()
        {
            // Wear slider
            if (wearLevelSlider != null)
            {
                wearLevelSlider.value = currentToolData.wear_percent / 100f;

                // Color based on condition
                ColorBlock colors = wearLevelSlider.colors;
                colors.disabledColor = GetWearColor(currentToolData.wear_percent / 100f);
                wearLevelSlider.colors = colors;
            }

            // Wear percentage text
            if (wearPercentText != null)
            {
                wearPercentText.text = $"{currentToolData.wear_percent:F1}%";
                wearPercentText.color = GetWearColor(currentToolData.wear_percent / 100f);
            }

            // Remaining life
            if (remainingLifeText != null)
            {
                TimeSpan remaining = TimeSpan.FromHours(currentToolData.remaining_life_hours);
                remainingLifeText.text = $"Life: {remaining.TotalHours:F1}h";
            }

            // Tool info
            if (toolNumberText != null)
            {
                toolNumberText.text = $"T{currentToolData.tool_number}";
            }

            if (toolTypeText != null)
            {
                toolTypeText.text = currentToolData.tool_type;
            }

            // Status indicator
            if (statusIndicator != null)
            {
                statusIndicator.color = GetWearColor(currentToolData.wear_percent / 100f);
            }
        }

        void Update3DWearVisualization()
        {
            if (toolTransform == null) return;

            // Update tool material based on wear
            Renderer toolRenderer = toolTransform.GetComponent<Renderer>();
            if (toolRenderer != null && newToolMaterial != null && wornToolMaterial != null)
            {
                float t = currentToolData.wear_percent / 100f;
                toolRenderer.material.Lerp(newToolMaterial, wornToolMaterial, t);
            }

            // Update particle emission based on wear
            if (wearParticles != null)
            {
                var emission = wearParticles.emission;
                emission.rateOverTime = particleEmissionRate * (currentToolData.wear_percent / 100f);
            }

            // Scale tool slightly to show wear
            if (currentToolData.wear_percent > 50f)
            {
                float wearScale = 1f - (currentToolData.wear_percent / 100f) * 0.05f;
                toolTransform.localScale = Vector3.one * wearScale;
            }
        }

        void CheckWearThresholds()
        {
            float wearNormalized = currentToolData.wear_percent / 100f;

            if (wearNormalized >= criticalThreshold)
            {
                if (!warningActive || currentToolData.condition == "critical")
                {
                    ShowWarning($"CRITICAL: Tool {currentToolData.tool_number} needs immediate replacement!");
                    OnToolCritical?.Invoke(currentToolData);
                }
            }
            else if (wearNormalized >= cautionThreshold)
            {
                if (!warningActive || currentToolData.condition == "caution")
                {
                    ShowWarning($"CAUTION: Tool {currentToolData.tool_number} approaching end of life");
                    OnToolWarning?.Invoke(currentToolData);
                }
            }
            else
            {
                HideWarning();
            }
        }

        void ShowWarning(string message)
        {
            warningActive = true;

            if (warningPanel != null)
            {
                warningPanel.SetActive(true);
            }

            if (warningText != null)
            {
                warningText.text = message;
            }

            Debug.LogWarning($"[ToolWearIndicator] {message}");
        }

        void HideWarning()
        {
            warningActive = false;

            if (warningPanel != null)
            {
                warningPanel.SetActive(false);
            }
        }

        void UpdatePredictionDisplay(ToolPrediction prediction)
        {
            if (remainingLifeText != null && showConfidenceInterval)
            {
                string predictionText = $"Life: {prediction.predicted_remaining_hours:F1}h";

                if (showConfidenceInterval)
                {
                    predictionText += $"\n({prediction.lower_bound_hours:F1}-{prediction.upper_bound_hours:F1}h)";
                }

                predictionText += $"\nConfidence: {prediction.confidence:P0}";
                remainingLifeText.text = predictionText;
            }
        }

        Color GetWearColor(float wearNormalized)
        {
            if (wearNormalized >= criticalThreshold)
            {
                return criticalColor;
            }
            else if (wearNormalized >= cautionThreshold)
            {
                return Color.Lerp(cautionColor, criticalColor,
                    (wearNormalized - cautionThreshold) / (criticalThreshold - cautionThreshold));
            }
            else
            {
                return Color.Lerp(healthyColor, cautionColor,
                    wearNormalized / cautionThreshold);
            }
        }

        /// <summary>
        /// Get wear history for charting
        /// </summary>
        public List<float> GetWearHistory()
        {
            return new List<float>(wearHistory);
        }

        /// <summary>
        /// Manually trigger tool change
        /// </summary>
        public void TriggerToolChange()
        {
            StartCoroutine(TriggerToolChangeAsync());
        }

        IEnumerator TriggerToolChangeAsync()
        {
            string url = $"{flaskServerUrl}/api/v1/predictive/tool-change";

            var changeRequest = new
            {
                machine_id = machineId,
                tool_number = currentToolData?.tool_number ?? 0
            };

            string jsonData = JsonConvert.SerializeObject(changeRequest);

            using (var request = new HttpRequestMessage(HttpMethod.Post, url))
            {
                request.Content = new System.Net.Http.StringContent(jsonData, System.Text.Encoding.UTF8, "application/json");

                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    Debug.LogError("[ToolWearIndicator] Tool change request failed");
                }
                else
                {
                    Debug.Log("[ToolWearIndicator] Tool change scheduled");
                    HideWarning();
                }
            }
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"current_tool", currentToolData?.tool_number ?? 0},
                {"wear_percent", currentToolData?.wear_percent ?? 0f},
                {"remaining_life_hours", currentToolData?.remaining_life_hours ?? 0f},
                {"condition", currentToolData?.condition ?? "unknown"},
                {"warning_active", warningActive},
                {"wear_history_size", wearHistory.Count},
                {"last_update", lastUpdateTime}
            };
        }

        void OnDestroy()
        {
            if (httpClient != null) httpClient.Dispose();
        }

        void OnDrawGizmos()
        {
            if (!Application.isPlaying || toolTransform == null) return;

            // Draw wear level indicator
            if (currentToolData != null)
            {
                Gizmos.color = GetWearColor(currentToolData.wear_percent / 100f);
                Gizmos.DrawWireSphere(toolTransform.position, 0.05f);

                // Draw wear percentage arc
                float angle = (currentToolData.wear_percent / 100f) * 360f;
                Vector3 from = toolTransform.position + Vector3.forward * 0.1f;
                Vector3 to = Quaternion.Euler(0, angle, 0) * Vector3.forward * 0.1f + toolTransform.position;
                Gizmos.DrawLine(toolTransform.position, from);
                Gizmos.DrawLine(toolTransform.position, to);
            }
        }
    }
}
