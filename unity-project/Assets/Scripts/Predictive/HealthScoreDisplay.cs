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
    /// Machine Health Score Display with Multi-Factor Gauges
    /// Displays overall health and individual subsystem scores
    /// Part of Phase 4: Predictive Maintenance
    /// </summary>
    public class HealthScoreDisplay : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";
        [SerializeField] private float updateInterval = 5f;

        [Header("UI References")]
        [SerializeField] private Image overallHealthFill;
        [SerializeField] private Text overallHealthText;
        [SerializeField] private Text overallHealthPercent;
        [SerializeField] private Image mechanicalHealthGauge;
        [SerializeField] private Image electricalHealthGauge;
        [SerializeField] private Image thermalHealthGauge;
        [SerializeField] private Image vibrationHealthGauge;
        [SerializeField] private Text mechanicalText;
        [SerializeField] private Text electricalText;
        [SerializeField] private Text thermalText;
        [SerializeField] private Text vibrationText;
        [SerializeField] private Text statusSummaryText;
        [SerializeField] private GameObject warningPanel;

        [Header("Gauge Settings")]
        [SerializeField] private Color excellentColor = Color.green;
        [SerializeField] private Color goodColor = Color.cyan;
        [SerializeField] private Color fairColor = Color.yellow;
        [SerializeField] private Color poorColor = new Color(1f, 0.5f, 0f); // Orange
        [SerializeField] private Color criticalColor = Color.red;
        [SerializeField] private float gaugeAnimationSpeed = 2f;
        [SerializeField] private bool enableSmoothTransitions = true;

        [Header("Health Thresholds")]
        [SerializeField] private float excellentThreshold = 0.9f;
        [SerializeField] private float goodThreshold = 0.75f;
        [SerializeField] private float fairThreshold = 0.5f;
        [SerializeField] private float poorThreshold = 0.25f;

        [Header("3D Visualization")]
        [SerializeField] private Transform machineTransform;
        [SerializeField] private bool enable3DHealthOverlay = true;
        [SerializeField] private Material healthOverlayMaterial;
        [SerializeField] private GameObject healthHologramPrefab;

        // Data
        private HttpClient httpClient;
        private HealthScoreData currentHealthData;
        private Dictionary<string, List<float>> healthHistory = new Dictionary<string, List<float>>();

        // Animated values
        private float targetOverallHealth = 1f;
        private float currentOverallHealth = 1f;
        private float targetMechanicalHealth = 1f;
        private float currentMechanicalHealth = 1f;
        private float targetElectricalHealth = 1f;
        private float currentElectricalHealth = 1f;
        private float targetThermalHealth = 1f;
        private float currentThermalHealth = 1f;
        private float targetVibrationHealth = 1f;
        private float currentVibrationHealth = 1f;

        // State
        private float lastUpdateTime = 0f;
        private GameObject healthHologram;

        // Statistics
        private float minHealthScore = 1f;
        private float maxHealthScore = 1f;
        private float averageHealthScore = 1f;
        private int healthUpdates = 0;

        // Events
        public event Action<HealthScoreData> OnHealthScoreUpdated;
        public event Action<string, float> OnSubsystemHealthCritical;

        [Serializable]
        public class HealthScoreResponse
        {
            public bool success;
            public HealthScoreData health_data;
            public List<HealthIssue> issues;
            public string error;
        }

        [Serializable]
        public class HealthScoreData
        {
            public string machine_id;
            public float overall_health_score;
            public SubsystemHealth mechanical;
            public SubsystemHealth electrical;
            public SubsystemHealth thermal;
            public SubsystemHealth vibration;
            public string health_status; // excellent, good, fair, poor, critical
            public DateTime timestamp;
            public float predicted_failure_probability;
            public int days_until_maintenance;
        }

        [Serializable]
        public class SubsystemHealth
        {
            public float score;
            public string status;
            public List<string> issues;
            public float trend; // positive, negative, stable
        }

        [Serializable]
        public class HealthIssue
        {
            public string subsystem;
            public string severity;
            public string description;
            public string recommendation;
        }

        void Start()
        {
            httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(10);

            InitializeHealthHistory();
            Setup3DVisualization();
            StartCoroutine(UpdateHealthScorePeriodically());

            Debug.Log("[HealthScoreDisplay] Initialized for machine: " + machineId);
        }

        void InitializeHealthHistory()
        {
            healthHistory["overall"] = new List<float>();
            healthHistory["mechanical"] = new List<float>();
            healthHistory["electrical"] = new List<float>();
            healthHistory["thermal"] = new List<float>();
            healthHistory["vibration"] = new List<float>();
        }

        void Setup3DVisualization()
        {
            if (enable3DHealthOverlay && machineTransform != null)
            {
                if (healthHologramPrefab != null)
                {
                    healthHologram = Instantiate(healthHologramPrefab, machineTransform);
                    healthHologram.transform.localPosition = Vector3.up * 0.5f;
                }
            }
        }

        IEnumerator UpdateHealthScorePeriodically()
        {
            while (true)
            {
                yield return new WaitForSeconds(updateInterval);
                FetchHealthScore();
            }
        }

        void FetchHealthScore()
        {
            StartCoroutine(FetchHealthScoreAsync());
        }

        IEnumerator FetchHealthScoreAsync()
        {
            string url = $"{flaskServerUrl}/api/v1/predictive/health-score?machine_id={machineId}";

            using (var request = new HttpRequestMessage(HttpMethod.Get, url))
            {
                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    Debug.LogError("[HealthScoreDisplay] Failed to fetch health score");
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                try
                {
                    HealthScoreResponse response = JsonConvert.DeserializeObject<HealthScoreResponse>(readTask.Result);

                    if (response.success)
                    {
                        UpdateHealthDisplay(response);
                    }
                    else
                    {
                        Debug.LogError($"[HealthScoreDisplay] Error: {response.error}");
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"[HealthScoreDisplay] Parse error: {e.Message}");
                }
            }

            lastUpdateTime = Time.time;
        }

        void UpdateHealthDisplay(HealthScoreResponse response)
        {
            currentHealthData = response.health_data;
            healthUpdates++;

            // Set target values for smooth animation
            targetOverallHealth = currentHealthData.overall_health_score;
            targetMechanicalHealth = currentHealthData.mechanical.score;
            targetElectricalHealth = currentHealthData.electrical.score;
            targetThermalHealth = currentHealthData.thermal.score;
            targetVibrationHealth = currentHealthData.vibration.score;

            // Record history
            RecordHealthHistory();

            // Update statistics
            UpdateStatistics();

            // Check for critical subsystems
            CheckCriticalSubsystems();

            // Update status text
            UpdateStatusSummary(response);

            OnHealthScoreUpdated?.Invoke(currentHealthData);
        }

        void Update()
        {
            if (!enableSmoothTransitions)
            {
                currentOverallHealth = targetOverallHealth;
                currentMechanicalHealth = targetMechanicalHealth;
                currentElectricalHealth = targetElectricalHealth;
                currentThermalHealth = targetThermalHealth;
                currentVibrationHealth = targetVibrationHealth;
            }
            else
            {
                // Smooth interpolation
                float t = gaugeAnimationSpeed * Time.deltaTime;
                currentOverallHealth = Mathf.Lerp(currentOverallHealth, targetOverallHealth, t);
                currentMechanicalHealth = Mathf.Lerp(currentMechanicalHealth, targetMechanicalHealth, t);
                currentElectricalHealth = Mathf.Lerp(currentElectricalHealth, targetElectricalHealth, t);
                currentThermalHealth = Mathf.Lerp(currentThermalHealth, targetThermalHealth, t);
                currentVibrationHealth = Mathf.Lerp(currentVibrationHealth, targetVibrationHealth, t);
            }

            // Update UI
            UpdateGaugeUI();
        }

        void UpdateGaugeUI()
        {
            // Overall health
            if (overallHealthFill != null)
            {
                overallHealthFill.fillAmount = currentOverallHealth;
                overallHealthFill.color = GetHealthColor(currentOverallHealth);
            }

            if (overallHealthPercent != null)
            {
                overallHealthPercent.text = $"{currentOverallHealth * 100f:F0}%";
            }

            if (overallHealthText != null)
            {
                overallHealthText.text = GetHealthStatusText(currentOverallHealth);
                overallHealthText.color = GetHealthColor(currentOverallHealth);
            }

            // Subsystem gauges
            UpdateSubsystemGauge(mechanicalHealthGauge, mechanicalText, currentMechanicalHealth, "Mechanical");
            UpdateSubsystemGauge(electricalHealthGauge, electricalText, currentElectricalHealth, "Electrical");
            UpdateSubsystemGauge(thermalHealthGauge, thermalText, currentThermalHealth, "Thermal");
            UpdateSubsystemGauge(vibrationHealthGauge, vibrationText, currentVibrationHealth, "Vibration");

            // 3D hologram
            if (healthHologram != null)
            {
                UpdateHealthHologram();
            }
        }

        void UpdateSubsystemGauge(Image gauge, Text text, float value, string label)
        {
            if (gauge != null)
            {
                gauge.fillAmount = value;
                gauge.color = GetHealthColor(value);
            }

            if (text != null)
            {
                text.text = $"{label}\n{value * 100f:F0}%";
            }
        }

        void UpdateHealthHologram()
        {
            // Scale hologram based on health
            healthHologram.transform.localScale = Vector3.one * (0.5f + currentOverallHealth * 0.5f);

            // Color based on health
            Renderer renderer = healthHologram.GetComponent<Renderer>();
            if (renderer != null)
            {
                renderer.material.color = GetHealthColor(currentOverallHealth);
            }

            // Rotate slowly
            healthHologram.transform.Rotate(Vector3.up, 20f * Time.deltaTime);
        }

        Color GetHealthColor(float healthScore)
        {
            if (healthScore >= excellentThreshold)
            {
                return excellentColor;
            }
            else if (healthScore >= goodThreshold)
            {
                float t = (healthScore - goodThreshold) / (excellentThreshold - goodThreshold);
                return Color.Lerp(goodColor, excellentColor, t);
            }
            else if (healthScore >= fairThreshold)
            {
                float t = (healthScore - fairThreshold) / (goodThreshold - fairThreshold);
                return Color.Lerp(fairColor, goodColor, t);
            }
            else if (healthScore >= poorThreshold)
            {
                float t = (healthScore - poorThreshold) / (fairThreshold - poorThreshold);
                return Color.Lerp(poorColor, fairColor, t);
            }
            else
            {
                float t = healthScore / poorThreshold;
                return Color.Lerp(criticalColor, poorColor, t);
            }
        }

        string GetHealthStatusText(float healthScore)
        {
            if (healthScore >= excellentThreshold) return "EXCELLENT";
            else if (healthScore >= goodThreshold) return "GOOD";
            else if (healthScore >= fairThreshold) return "FAIR";
            else if (healthScore >= poorThreshold) return "POOR";
            else return "CRITICAL";
        }

        void RecordHealthHistory()
        {
            RecordScore("overall", currentHealthData.overall_health_score);
            RecordScore("mechanical", currentHealthData.mechanical.score);
            RecordScore("electrical", currentHealthData.electrical.score);
            RecordScore("thermal", currentHealthData.thermal.score);
            RecordScore("vibration", currentHealthData.vibration.score);
        }

        void RecordScore(string key, float score)
        {
            healthHistory[key].Add(score);
            if (healthHistory[key].Count > 100)
            {
                healthHistory[key].RemoveAt(0);
            }
        }

        void UpdateStatistics()
        {
            minHealthScore = Mathf.Min(minHealthScore, currentHealthData.overall_health_score);
            maxHealthScore = Mathf.Max(maxHealthScore, currentHealthData.overall_health_score);

            float sum = 0f;
            foreach (float score in healthHistory["overall"])
            {
                sum += score;
            }
            averageHealthScore = healthHistory["overall"].Count > 0 ? sum / healthHistory["overall"].Count : 1f;
        }

        void CheckCriticalSubsystems()
        {
            CheckSubsystemHealth("mechanical", currentHealthData.mechanical.score);
            CheckSubsystemHealth("electrical", currentHealthData.electrical.score);
            CheckSubsystemHealth("thermal", currentHealthData.thermal.score);
            CheckSubsystemHealth("vibration", currentHealthData.vibration.score);
        }

        void CheckSubsystemHealth(string subsystem, float score)
        {
            if (score < poorThreshold)
            {
                OnSubsystemHealthCritical?.Invoke(subsystem, score);
                Debug.LogWarning($"[HealthScoreDisplay] {subsystem} subsystem health critical: {score:P0}");
            }
        }

        void UpdateStatusSummary(HealthScoreResponse response)
        {
            if (statusSummaryText == null) return;

            string summary = $"<b>Health Status: {currentHealthData.health_status.ToUpper()}</b>\n\n";
            summary += $"Overall: {currentHealthData.overall_health_score:P0}\n";
            summary += $"Failure Risk: {currentHealthData.predicted_failure_probability:P1}\n";
            summary += $"Next Maintenance: {currentHealthData.days_until_maintenance} days\n\n";

            if (response.issues != null && response.issues.Count > 0)
            {
                summary += "<b>Issues:</b>\n";
                foreach (var issue in response.issues)
                {
                    summary += $"• {issue.subsystem}: {issue.description}\n";
                }
            }

            statusSummaryText.text = summary;

            // Show warning panel if health is critical
            if (warningPanel != null)
            {
                warningPanel.SetActive(currentHealthData.overall_health_score < poorThreshold);
            }
        }

        /// <summary>
        /// Get health score history for a specific component
        /// </summary>
        public List<float> GetHealthHistory(string component)
        {
            if (healthHistory.ContainsKey(component))
            {
                return new List<float>(healthHistory[component]);
            }
            return new List<float>();
        }

        /// <summary>
        /// Get current health data
        /// </summary>
        public HealthScoreData GetCurrentHealthData()
        {
            return currentHealthData;
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"overall_health", currentHealthData?.overall_health_score ?? 0f},
                {"health_status", currentHealthData?.health_status ?? "unknown"},
                {"min_health_score", minHealthScore},
                {"max_health_score", maxHealthScore},
                {"average_health_score", averageHealthScore},
                {"health_updates", healthUpdates},
                {"mechanical_health", currentHealthData?.mechanical.score ?? 0f},
                {"electrical_health", currentHealthData?.electrical.score ?? 0f},
                {"thermal_health", currentHealthData?.thermal.score ?? 0f},
                {"vibration_health", currentHealthData?.vibration.score ?? 0f},
                {"last_update", lastUpdateTime}
            };
        }

        void OnDestroy()
        {
            if (httpClient != null) httpClient.Dispose();
        }

        void OnDrawGizmos()
        {
            if (!Application.isPlaying || machineTransform == null) return;

            if (currentHealthData != null)
            {
                // Draw health sphere around machine
                Gizmos.color = GetHealthColor(currentOverallHealth);
                Gizmos.DrawWireSphere(machineTransform.position, 0.5f);

                // Draw subsystem indicators
                Vector3 basePos = machineTransform.position;
                DrawSubsystemIndicator(basePos + Vector3.right * 0.7f, currentMechanicalHealth);
                DrawSubsystemIndicator(basePos + Vector3.left * 0.7f, currentElectricalHealth);
                DrawSubsystemIndicator(basePos + Vector3.forward * 0.7f, currentThermalHealth);
                DrawSubsystemIndicator(basePos + Vector3.back * 0.7f, currentVibrationHealth);
            }
        }

        void DrawSubsystemIndicator(Vector3 position, float health)
        {
            Gizmos.color = GetHealthColor(health);
            Gizmos.DrawSphere(position, 0.05f);
        }
    }
}
