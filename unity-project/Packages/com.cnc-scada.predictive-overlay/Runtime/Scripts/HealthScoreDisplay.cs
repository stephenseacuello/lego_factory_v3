using UnityEngine;
using UnityEngine.UI;
using System;
using System.Collections.Generic;
using System.Net.Http;
using Newtonsoft.Json;

namespace CNCScada.Predictive
{
    /// <summary>
    /// Multi-factor machine health score display
    /// Combines vibration, temperature, tool wear, and performance metrics
    /// </summary>
    public class HealthScoreDisplay : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";

        [Header("UI References")]
        [SerializeField] private Image healthScoreGauge;
        [SerializeField] private Text healthScoreText;
        [SerializeField] private Text statusText;
        [SerializeField] private Image[] factorBars; // Individual health factors
        [SerializeField] private Text[] factorLabels;

        [Header("Visual Settings")]
        [SerializeField] private Gradient healthGradient;
        [SerializeField] private bool animateTransitions = true;
        [SerializeField] private float transitionSpeed = 2f;

        [Header("Thresholds")]
        [SerializeField] private float goodThreshold = 80f;
        [SerializeField] private float warningThreshold = 60f;
        [SerializeField] private float criticalThreshold = 40f;

        [Header("Update Settings")]
        [SerializeField] private float updateInterval = 5f;
        [SerializeField] private bool autoRefresh = true;

        #endregion

        #region Private Fields

        private HttpClient _httpClient;
        private HealthScore _currentScore;
        private List<HealthHistory> _scoreHistory;
        private float _displayedScore;
        private float _targetScore;
        private float _lastUpdateTime;

        #endregion

        #region Events

        public event Action<HealthScore> OnHealthUpdate;
        public event Action<HealthStatus> OnStatusChanged;
        public event Action<string> OnError;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(5);
            _scoreHistory = new List<HealthHistory>();

            InitializeGradient();
            LoadHealthScore();
        }

        void Update()
        {
            if (autoRefresh && Time.time - _lastUpdateTime >= updateInterval)
            {
                LoadHealthScore();
                _lastUpdateTime = Time.time;
            }

            if (animateTransitions)
            {
                AnimateScore();
            }

            UpdateDisplay();
        }

        void OnDestroy()
        {
            _httpClient?.Dispose();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Load health score from backend
        /// </summary>
        public void LoadHealthScore()
        {
            StartCoroutine(FetchHealthScore());
        }

        /// <summary>
        /// Get current overall health score (0-100)
        /// </summary>
        public float GetHealthScore()
        {
            return _currentScore?.overallScore ?? 0f;
        }

        /// <summary>
        /// Get health status
        /// </summary>
        public HealthStatus GetHealthStatus()
        {
            if (_currentScore == null) return HealthStatus.Unknown;

            float score = _currentScore.overallScore;
            if (score >= goodThreshold) return HealthStatus.Good;
            if (score >= warningThreshold) return HealthStatus.Warning;
            if (score >= criticalThreshold) return HealthStatus.Poor;
            return HealthStatus.Critical;
        }

        /// <summary>
        /// Get weakest health factor
        /// </summary>
        public string GetWeakestFactor()
        {
            if (_currentScore == null || _currentScore.factors == null) return "Unknown";

            float minScore = float.MaxValue;
            string weakest = "Unknown";

            foreach (var factor in _currentScore.factors)
            {
                if (factor.Value < minScore)
                {
                    minScore = factor.Value;
                    weakest = factor.Key;
                }
            }

            return weakest;
        }

        /// <summary>
        /// Get health trend (improving/declining)
        /// </summary>
        public float GetHealthTrend()
        {
            if (_scoreHistory.Count < 2) return 0f;

            var recent = _scoreHistory[_scoreHistory.Count - 1];
            var previous = _scoreHistory[_scoreHistory.Count - 2];

            var timeDiff = (recent.timestamp - previous.timestamp).TotalHours;
            if (timeDiff <= 0) return 0f;

            return (recent.score - previous.score) / (float)timeDiff;
        }

        /// <summary>
        /// Get predicted health score for future date
        /// </summary>
        public float GetPredictedScore(DateTime targetDate)
        {
            if (_currentScore == null) return 0f;

            var trend = GetHealthTrend();
            var hoursAhead = (targetDate - DateTime.Now).TotalHours;

            return Mathf.Clamp(_currentScore.overallScore + trend * (float)hoursAhead, 0f, 100f);
        }

        #endregion

        #region Private Methods

        private void InitializeGradient()
        {
            if (healthGradient == null || healthGradient.colorKeys.Length == 0)
            {
                healthGradient = new Gradient();
                healthGradient.colorKeys = new GradientColorKey[]
                {
                    new GradientColorKey(Color.red, 0.0f),      // 0-20: Critical
                    new GradientColorKey(new Color(1f, 0.5f, 0f), 0.4f), // 40: Poor
                    new GradientColorKey(Color.yellow, 0.6f),   // 60: Warning
                    new GradientColorKey(Color.green, 1.0f)     // 100: Good
                };
            }
        }

        private System.Collections.IEnumerator FetchHealthScore()
        {
            var url = $"{flaskServerUrl}/api/predictive/health?machine_id={machineId}";
            var task = _httpClient.GetStringAsync(url);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted)
            {
                Debug.LogWarning($"[HealthScore] Fetch failed: {task.Exception?.Message}");
                OnError?.Invoke($"Failed to load health score: {task.Exception?.Message}");
                yield break;
            }

            try
            {
                var response = JsonConvert.DeserializeObject<HealthScoreResponse>(task.Result);

                var previousStatus = GetHealthStatus();
                _currentScore = response.health;
                _targetScore = _currentScore.overallScore;

                // Add to history
                _scoreHistory.Add(new HealthHistory
                {
                    timestamp = DateTime.Now,
                    score = _currentScore.overallScore
                });

                // Limit history size
                while (_scoreHistory.Count > 100)
                {
                    _scoreHistory.RemoveAt(0);
                }

                OnHealthUpdate?.Invoke(_currentScore);

                var newStatus = GetHealthStatus();
                if (newStatus != previousStatus)
                {
                    OnStatusChanged?.Invoke(newStatus);
                }
            }
            catch (Exception e)
            {
                Debug.LogError($"[HealthScore] Parse error: {e.Message}");
                OnError?.Invoke($"Parse error: {e.Message}");
            }
        }

        private void AnimateScore()
        {
            _displayedScore = Mathf.Lerp(_displayedScore, _targetScore, Time.deltaTime * transitionSpeed);
        }

        private void UpdateDisplay()
        {
            if (_currentScore == null) return;

            float displayScore = animateTransitions ? _displayedScore : _targetScore;

            // Update gauge
            if (healthScoreGauge != null)
            {
                healthScoreGauge.fillAmount = displayScore / 100f;
                healthScoreGauge.color = healthGradient.Evaluate(displayScore / 100f);
            }

            // Update score text
            if (healthScoreText != null)
            {
                healthScoreText.text = $"{displayScore:F1}";
                healthScoreText.color = healthGradient.Evaluate(displayScore / 100f);
            }

            // Update status text
            if (statusText != null)
            {
                var status = GetHealthStatus();
                statusText.text = status.ToString().ToUpper();
                statusText.color = GetStatusColor(status);
            }

            // Update factor bars
            UpdateFactorBars();
        }

        private void UpdateFactorBars()
        {
            if (_currentScore?.factors == null || factorBars == null) return;

            int index = 0;
            foreach (var factor in _currentScore.factors)
            {
                if (index >= factorBars.Length) break;

                if (factorBars[index] != null)
                {
                    factorBars[index].fillAmount = factor.Value / 100f;
                    factorBars[index].color = healthGradient.Evaluate(factor.Value / 100f);
                }

                if (factorLabels != null && index < factorLabels.Length && factorLabels[index] != null)
                {
                    factorLabels[index].text = $"{factor.Key}: {factor.Value:F0}%";
                }

                index++;
            }
        }

        private Color GetStatusColor(HealthStatus status)
        {
            switch (status)
            {
                case HealthStatus.Good: return Color.green;
                case HealthStatus.Warning: return Color.yellow;
                case HealthStatus.Poor: return new Color(1f, 0.5f, 0f); // orange
                case HealthStatus.Critical: return Color.red;
                default: return Color.gray;
            }
        }

        #endregion

        #region Gizmos

        void OnDrawGizmos()
        {
            if (!Application.isPlaying || _currentScore == null) return;

            // Draw health score as colored sphere in scene
            Gizmos.color = healthGradient.Evaluate(_currentScore.overallScore / 100f);
            Gizmos.DrawWireSphere(transform.position, 0.5f);
        }

        #endregion
    }

    #region Data Classes

    [Serializable]
    public class HealthScoreResponse
    {
        public string machineId;
        public HealthScore health;
        public List<HealthPrediction> predictions;
    }

    [Serializable]
    public class HealthScore
    {
        public float overallScore; // 0-100
        public Dictionary<string, float> factors; // Individual factor scores
        public DateTime calculatedAt;
        public float confidence;
        public string primaryConcern;
        public List<string> recommendations;
    }

    [Serializable]
    public class HealthPrediction
    {
        public DateTime predictedDate;
        public float predictedScore;
        public float confidence;
    }

    public class HealthHistory
    {
        public DateTime timestamp;
        public float score;
    }

    public enum HealthStatus
    {
        Unknown,
        Good,
        Warning,
        Poor,
        Critical
    }

    #endregion
}
