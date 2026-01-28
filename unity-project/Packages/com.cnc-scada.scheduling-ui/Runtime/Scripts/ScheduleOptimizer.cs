using UnityEngine;
using System;
using System.Net.Http;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace CNCScada.Scheduling
{
    /// <summary>
    /// Triggers OR-Tools optimization on backend
    /// Supports multiple algorithms: CP-SAT, Genetic, Simulated Annealing
    /// </summary>
    public class ScheduleOptimizer : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";

        [Header("Optimization Settings")]
        [SerializeField] private OptimizationAlgorithm algorithm = OptimizationAlgorithm.CPSAT;
        [SerializeField] private OptimizationObjective objective = OptimizationObjective.MinimizeMakespan;
        [SerializeField] private int timeoutSeconds = 60;
        [SerializeField] private bool considerSetupTime = true;
        [SerializeField] private bool respectPriorities = true;

        #endregion

        #region Private Fields

        private HttpClient _httpClient;
        private bool _isOptimizing;
        private float _optimizationProgress;

        #endregion

        #region Events

        public event Action<ScheduleResponse> OnOptimizationComplete;
        public event Action<float> OnProgressUpdate;
        public event Action<string> OnError;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(timeoutSeconds + 10);
        }

        void OnDestroy()
        {
            _httpClient?.Dispose();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Trigger schedule optimization
        /// </summary>
        public void OptimizeSchedule()
        {
            if (_isOptimizing)
            {
                Debug.LogWarning("[Optimizer] Optimization already in progress");
                return;
            }

            StartCoroutine(RunOptimization());
        }

        /// <summary>
        /// Cancel ongoing optimization
        /// </summary>
        public void CancelOptimization()
        {
            _isOptimizing = false;
        }

        /// <summary>
        /// Get optimization progress
        /// </summary>
        public float GetProgress()
        {
            return _optimizationProgress;
        }

        #endregion

        #region Private Methods

        private System.Collections.IEnumerator RunOptimization()
        {
            _isOptimizing = true;
            _optimizationProgress = 0f;

            var url = $"{flaskServerUrl}/api/schedule/optimize";
            var request = new
            {
                algorithm = algorithm.ToString(),
                objective = objective.ToString(),
                timeout = timeoutSeconds,
                considerSetupTime,
                respectPriorities
            };

            var json = JsonConvert.SerializeObject(request);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            // Simulate progress (actual progress would need WebSocket or polling)
            float elapsed = 0f;
            while (!task.IsCompleted && elapsed < timeoutSeconds)
            {
                elapsed += Time.deltaTime;
                _optimizationProgress = Mathf.Clamp01(elapsed / timeoutSeconds);
                OnProgressUpdate?.Invoke(_optimizationProgress);
                yield return null;
            }

            if (task.IsFaulted)
            {
                Debug.LogError($"[Optimizer] Failed: {task.Exception?.Message}");
                OnError?.Invoke($"Optimization failed: {task.Exception?.Message}");
                _isOptimizing = false;
                yield break;
            }

            var response = task.Result;
            if (!response.IsSuccessStatusCode)
            {
                Debug.LogError($"[Optimizer] HTTP {response.StatusCode}");
                OnError?.Invoke($"HTTP error: {response.StatusCode}");
                _isOptimizing = false;
                yield break;
            }

            var readTask = response.Content.ReadAsStringAsync();
            while (!readTask.IsCompleted) yield return null;

            try
            {
                var result = JsonConvert.DeserializeObject<ScheduleResponse>(readTask.Result);
                _optimizationProgress = 1f;
                OnOptimizationComplete?.Invoke(result);
                Debug.Log($"[Optimizer] Complete - Makespan: {result.makespan}s, Improvement: {result.improvement}%");
            }
            catch (Exception e)
            {
                Debug.LogError($"[Optimizer] Parse error: {e.Message}");
                OnError?.Invoke($"Parse error: {e.Message}");
            }

            _isOptimizing = false;
        }

        #endregion
    }

    #region Enums

    public enum OptimizationAlgorithm
    {
        CPSAT,
        Genetic,
        SimulatedAnnealing
    }

    public enum OptimizationObjective
    {
        MinimizeMakespan,
        MinimizeLateness,
        MaximizeUtilization,
        MinimizeSetupTime
    }

    #endregion
}
