using UnityEngine;
using UnityEngine.UI;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using Newtonsoft.Json;

namespace CNCScada.Scheduling
{
    /// <summary>
    /// Schedule Optimizer with OR-Tools Integration
    /// Triggers backend optimization algorithms and displays results
    /// Part of Phase 3: Production Scheduling
    /// </summary>
    public class ScheduleOptimizer : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private float optimizationTimeout = 300f; // seconds

        [Header("UI References")]
        [SerializeField] private Button optimizeButton;
        [SerializeField] private Dropdown algorithmDropdown;
        [SerializeField] private Dropdown objectiveDropdown;
        [SerializeField] private Slider timeLimitSlider;
        [SerializeField] private Text timeLimitText;
        [SerializeField] private Toggle advancedOptionsToggle;
        [SerializeField] private GameObject advancedOptionsPanel;
        [SerializeField] private Text statusText;
        [SerializeField] private Slider progressBar;
        [SerializeField] private Text resultSummaryText;

        [Header("Algorithm Options")]
        [SerializeField] private List<string> availableAlgorithms = new List<string>
        {
            "or_tools_cp",
            "or_tools_sat",
            "genetic_algorithm",
            "simulated_annealing",
            "greedy",
            "priority_based"
        };

        [Header("Optimization Objectives")]
        [SerializeField] private List<string> availableObjectives = new List<string>
        {
            "minimize_makespan",
            "minimize_tardiness",
            "maximize_utilization",
            "minimize_setup_time",
            "balance_load"
        };

        [Header("Advanced Settings")]
        [SerializeField] private bool enableConstraints = true;
        [SerializeField] private bool respectDependencies = true;
        [SerializeField] private bool respectSkills = true;
        [SerializeField] private bool allowMachineChange = true;
        [SerializeField] private bool allowJobSplitting = false;

        // State
        private HttpClient httpClient;
        private bool isOptimizing = false;
        private float optimizationStartTime = 0f;
        private string currentAlgorithm = "or_tools_cp";
        private string currentObjective = "minimize_makespan";
        private float timeLimit = 60f; // seconds

        // Results
        private OptimizationResult lastResult;

        // Statistics
        private int totalOptimizations = 0;
        private int successfulOptimizations = 0;
        private int failedOptimizations = 0;
        private float averageOptimizationTime = 0f;
        private List<float> optimizationTimes = new List<float>();

        // Events
        public event Action OnOptimizationStarted;
        public event Action<OptimizationResult> OnOptimizationCompleted;
        public event Action<string> OnOptimizationFailed;

        [Serializable]
        public class OptimizationRequest
        {
            public string algorithm;
            public string objective;
            public float time_limit_seconds;
            public OptimizationConstraints constraints;
            public Dictionary<string, object> advanced_options;
        }

        [Serializable]
        public class OptimizationConstraints
        {
            public bool respect_dependencies;
            public bool respect_skills;
            public bool allow_machine_change;
            public bool allow_job_splitting;
            public List<string> required_machines;
            public List<string> excluded_machines;
        }

        [Serializable]
        public class OptimizationResult
        {
            public bool success;
            public string algorithm_used;
            public string objective;
            public float computation_time_seconds;
            public int iterations;
            public float objective_value;
            public float improvement_percent;
            public OptimizationMetrics metrics;
            public string error;
        }

        [Serializable]
        public class OptimizationMetrics
        {
            public float makespan_hours;
            public float total_tardiness_hours;
            public float average_utilization_percent;
            public float total_setup_time_hours;
            public float load_balance_score;
            public int jobs_rescheduled;
            public int machines_affected;
        }

        void Start()
        {
            httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(optimizationTimeout);

            SetupUI();
            Debug.Log("[ScheduleOptimizer] Initialized");
        }

        void SetupUI()
        {
            if (optimizeButton != null)
            {
                optimizeButton.onClick.AddListener(OnOptimizeButtonClicked);
            }

            if (algorithmDropdown != null)
            {
                algorithmDropdown.ClearOptions();
                algorithmDropdown.AddOptions(availableAlgorithms);
                algorithmDropdown.onValueChanged.AddListener(OnAlgorithmChanged);
                algorithmDropdown.value = 0;
            }

            if (objectiveDropdown != null)
            {
                objectiveDropdown.ClearOptions();
                objectiveDropdown.AddOptions(availableObjectives);
                objectiveDropdown.onValueChanged.AddListener(OnObjectiveChanged);
                objectiveDropdown.value = 0;
            }

            if (timeLimitSlider != null)
            {
                timeLimitSlider.minValue = 10f;
                timeLimitSlider.maxValue = 300f;
                timeLimitSlider.value = timeLimit;
                timeLimitSlider.onValueChanged.AddListener(OnTimeLimitChanged);
            }

            if (advancedOptionsToggle != null)
            {
                advancedOptionsToggle.onValueChanged.AddListener(OnAdvancedOptionsToggled);
            }

            if (advancedOptionsPanel != null)
            {
                advancedOptionsPanel.SetActive(false);
            }

            UpdateTimeLimitText();
        }

        void OnAlgorithmChanged(int index)
        {
            if (index >= 0 && index < availableAlgorithms.Count)
            {
                currentAlgorithm = availableAlgorithms[index];
                Debug.Log($"[ScheduleOptimizer] Algorithm changed to: {currentAlgorithm}");
            }
        }

        void OnObjectiveChanged(int index)
        {
            if (index >= 0 && index < availableObjectives.Count)
            {
                currentObjective = availableObjectives[index];
                Debug.Log($"[ScheduleOptimizer] Objective changed to: {currentObjective}");
            }
        }

        void OnTimeLimitChanged(float value)
        {
            timeLimit = value;
            UpdateTimeLimitText();
        }

        void OnAdvancedOptionsToggled(bool isOn)
        {
            if (advancedOptionsPanel != null)
            {
                advancedOptionsPanel.SetActive(isOn);
            }
        }

        void UpdateTimeLimitText()
        {
            if (timeLimitText != null)
            {
                timeLimitText.text = $"Time Limit: {timeLimit:F0}s";
            }
        }

        void OnOptimizeButtonClicked()
        {
            if (isOptimizing)
            {
                UpdateStatus("Optimization already running", true);
                return;
            }

            StartOptimization();
        }

        void StartOptimization()
        {
            isOptimizing = true;
            totalOptimizations++;
            optimizationStartTime = Time.time;

            UpdateStatus("Starting optimization...", false);
            SetButtonState(false);

            if (progressBar != null)
            {
                progressBar.value = 0f;
                StartCoroutine(AnimateProgressBar());
            }

            OnOptimizationStarted?.Invoke();

            StartCoroutine(RunOptimizationAsync());
        }

        IEnumerator AnimateProgressBar()
        {
            while (isOptimizing && progressBar != null)
            {
                float elapsed = Time.time - optimizationStartTime;
                float progress = Mathf.Clamp01(elapsed / timeLimit);
                progressBar.value = progress;
                yield return new WaitForSeconds(0.1f);
            }

            if (progressBar != null)
            {
                progressBar.value = 1f;
            }
        }

        IEnumerator RunOptimizationAsync()
        {
            string url = $"{flaskServerUrl}/api/v1/scheduler/optimize";

            OptimizationRequest request = new OptimizationRequest
            {
                algorithm = currentAlgorithm,
                objective = currentObjective,
                time_limit_seconds = timeLimit,
                constraints = new OptimizationConstraints
                {
                    respect_dependencies = respectDependencies,
                    respect_skills = respectSkills,
                    allow_machine_change = allowMachineChange,
                    allow_job_splitting = allowJobSplitting
                },
                advanced_options = new Dictionary<string, object>()
            };

            string jsonData = JsonConvert.SerializeObject(request);

            using (var httpRequest = new HttpRequestMessage(HttpMethod.Post, url))
            {
                httpRequest.Content = new StringContent(jsonData, Encoding.UTF8, "application/json");

                var task = httpClient.SendAsync(httpRequest);
                while (!task.IsCompleted) yield return null;

                float computationTime = Time.time - optimizationStartTime;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    HandleOptimizationFailure("Network error or server unavailable");
                    RecordOptimizationTime(computationTime);
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                try
                {
                    OptimizationResult result = JsonConvert.DeserializeObject<OptimizationResult>(readTask.Result);

                    if (result.success)
                    {
                        HandleOptimizationSuccess(result);
                    }
                    else
                    {
                        HandleOptimizationFailure(result.error);
                    }

                    RecordOptimizationTime(computationTime);
                }
                catch (Exception e)
                {
                    HandleOptimizationFailure($"Parse error: {e.Message}");
                    RecordOptimizationTime(computationTime);
                }
            }

            isOptimizing = false;
            SetButtonState(true);
        }

        void HandleOptimizationSuccess(OptimizationResult result)
        {
            successfulOptimizations++;
            lastResult = result;

            UpdateStatus("Optimization completed successfully", false);
            DisplayResults(result);

            OnOptimizationCompleted?.Invoke(result);
            Debug.Log($"[ScheduleOptimizer] Optimization completed - Improvement: {result.improvement_percent:F1}%");
        }

        void HandleOptimizationFailure(string error)
        {
            failedOptimizations++;
            UpdateStatus($"Optimization failed: {error}", true);
            OnOptimizationFailed?.Invoke(error);
            Debug.LogError($"[ScheduleOptimizer] Optimization failed: {error}");
        }

        void DisplayResults(OptimizationResult result)
        {
            if (resultSummaryText == null) return;

            string summary = $"<b>Optimization Results</b>\n\n";
            summary += $"Algorithm: {result.algorithm_used}\n";
            summary += $"Objective: {result.objective}\n";
            summary += $"Computation Time: {result.computation_time_seconds:F2}s\n";
            summary += $"Iterations: {result.iterations}\n";
            summary += $"Improvement: {result.improvement_percent:F1}%\n\n";

            if (result.metrics != null)
            {
                summary += $"<b>Metrics:</b>\n";
                summary += $"Makespan: {result.metrics.makespan_hours:F2} hours\n";
                summary += $"Total Tardiness: {result.metrics.total_tardiness_hours:F2} hours\n";
                summary += $"Avg Utilization: {result.metrics.average_utilization_percent:F1}%\n";
                summary += $"Setup Time: {result.metrics.total_setup_time_hours:F2} hours\n";
                summary += $"Load Balance: {result.metrics.load_balance_score:F2}\n";
                summary += $"Jobs Rescheduled: {result.metrics.jobs_rescheduled}\n";
                summary += $"Machines Affected: {result.metrics.machines_affected}\n";
            }

            resultSummaryText.text = summary;
        }

        void RecordOptimizationTime(float time)
        {
            optimizationTimes.Add(time);
            if (optimizationTimes.Count > 100)
            {
                optimizationTimes.RemoveAt(0);
            }

            float sum = 0f;
            foreach (float t in optimizationTimes)
            {
                sum += t;
            }
            averageOptimizationTime = sum / optimizationTimes.Count;
        }

        void UpdateStatus(string message, bool isError)
        {
            if (statusText != null)
            {
                statusText.text = message;
                statusText.color = isError ? Color.red : Color.white;
            }
        }

        void SetButtonState(bool enabled)
        {
            if (optimizeButton != null)
            {
                optimizeButton.interactable = enabled;
            }
        }

        /// <summary>
        /// Get the last optimization result
        /// </summary>
        public OptimizationResult GetLastResult()
        {
            return lastResult;
        }

        /// <summary>
        /// Check if optimization is currently running
        /// </summary>
        public bool IsOptimizing()
        {
            return isOptimizing;
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_optimizations", totalOptimizations},
                {"successful_optimizations", successfulOptimizations},
                {"failed_optimizations", failedOptimizations},
                {"success_rate", totalOptimizations > 0 ? (float)successfulOptimizations / totalOptimizations : 0f},
                {"average_optimization_time", averageOptimizationTime},
                {"current_algorithm", currentAlgorithm},
                {"current_objective", currentObjective},
                {"is_optimizing", isOptimizing}
            };
        }

        void OnDestroy()
        {
            if (httpClient != null) httpClient.Dispose();
        }
    }
}
