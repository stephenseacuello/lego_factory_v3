using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCScada.Analytics
{
    /// <summary>
    /// Analyzes and compares multiple machining runs for performance comparison.
    /// Identifies trends, anomalies, and performance differences.
    /// Part of Feature 2.4: Comparative Analysis (MEDIUM PRIORITY)
    /// </summary>
    public class ComparativeAnalyzer : MonoBehaviour
    {
        [Header("Analysis Configuration")]
        [SerializeField] private int maxRuns = 10;
        [SerializeField] private bool autoAnalyze = true;
        [SerializeField] private float analysisInterval = 5f;

        [Header("Comparison Metrics")]
        [SerializeField] private bool compareForces = true;
        [SerializeField] private bool compareVibration = true;
        [SerializeField] private bool compareChipLoad = true;
        [SerializeField] private bool compareCycleTime = true;
        [SerializeField] private bool compareMaterialRemoval = true;

        // Stored run data
        private List<MachiningRun> runs = new List<MachiningRun>();
        private Dictionary<string, RunComparison> comparisons = new Dictionary<string, RunComparison>();
        private float analysisTimer = 0f;

        // Current run being tracked
        private MachiningRun currentRun;
        private bool isTrackingRun = false;
        private DateTime runStartTime;

        // Events
        public event Action<RunComparison> OnComparisonCompleted;
        public event Action<TrendAnalysis> OnTrendDetected;
        public event Action<AnomalyDetection> OnAnomalyDetected;

        // Statistics
        private int totalComparisons = 0;
        private int anomaliesDetected = 0;

        void Start()
        {
            InitializeAnalyzer();
        }

        void Update()
        {
            if (isTrackingRun)
            {
                UpdateCurrentRun();
            }

            if (autoAnalyze && runs.Count >= 2)
            {
                analysisTimer += Time.deltaTime;
                if (analysisTimer >= analysisInterval)
                {
                    AnalyzeAllRuns();
                    analysisTimer = 0f;
                }
            }
        }

        /// <summary>
        /// Initialize analyzer
        /// </summary>
        private void InitializeAnalyzer()
        {
            Debug.Log("[ComparativeAnalyzer] Initialized");
        }

        /// <summary>
        /// Start tracking a new run
        /// </summary>
        public void StartRun(string runId, string programName = "", Dictionary<string, object> metadata = null)
        {
            if (isTrackingRun)
            {
                Debug.LogWarning("[ComparativeAnalyzer] Already tracking a run");
                return;
            }

            currentRun = new MachiningRun
            {
                RunId = runId,
                ProgramName = programName,
                StartTime = DateTime.UtcNow,
                Metadata = metadata ?? new Dictionary<string, object>(),
                ForceData = new List<float>(),
                VibrationData = new List<float>(),
                ChipLoadData = new List<float>(),
                MaterialRemovalData = new List<float>()
            };

            isTrackingRun = true;
            runStartTime = DateTime.UtcNow;

            Debug.Log($"[ComparativeAnalyzer] Started tracking run: {runId}");
        }

        /// <summary>
        /// Stop tracking current run
        /// </summary>
        public MachiningRun StopRun()
        {
            if (!isTrackingRun)
            {
                Debug.LogWarning("[ComparativeAnalyzer] No run being tracked");
                return null;
            }

            currentRun.EndTime = DateTime.UtcNow;
            currentRun.CycleTime = (float)(currentRun.EndTime - currentRun.StartTime).TotalSeconds;
            currentRun.IsComplete = true;

            // Calculate statistics
            CalculateRunStatistics(currentRun);

            // Add to runs list
            if (runs.Count >= maxRuns)
            {
                runs.RemoveAt(0); // Remove oldest run
            }
            runs.Add(currentRun);

            isTrackingRun = false;

            Debug.Log($"[ComparativeAnalyzer] Completed run: {currentRun.RunId}, Cycle Time: {currentRun.CycleTime:F2}s");

            return currentRun;
        }

        /// <summary>
        /// Update current run with latest data
        /// </summary>
        private void UpdateCurrentRun()
        {
            // Collect force data
            if (compareForces)
            {
                var forceViz = GetComponent<CNCScada.Visualization.ForceVisualization>();
                if (forceViz != null)
                {
                    currentRun.ForceData.Add(forceViz.CurrentForceMagnitude);
                }
            }

            // Collect vibration data
            if (compareVibration)
            {
                var vibViz = GetComponent<CNCScada.Visualization.VibrationVisualizer>();
                if (vibViz != null)
                {
                    currentRun.VibrationData.Add(vibViz.VibrationMagnitude);
                }
            }

            // Collect chip load data
            if (compareChipLoad)
            {
                var chipLoadCalc = GetComponent<CNCScada.Machining.ChipLoadCalculator>();
                if (chipLoadCalc != null)
                {
                    currentRun.ChipLoadData.Add(chipLoadCalc.CurrentChipLoad);
                }
            }
        }

        /// <summary>
        /// Calculate statistics for a run
        /// </summary>
        private void CalculateRunStatistics(MachiningRun run)
        {
            run.Statistics = new RunStatistics
            {
                AvgForce = run.ForceData.Count > 0 ? run.ForceData.Average() : 0f,
                MaxForce = run.ForceData.Count > 0 ? run.ForceData.Max() : 0f,
                MinForce = run.ForceData.Count > 0 ? run.ForceData.Min() : 0f,

                AvgVibration = run.VibrationData.Count > 0 ? run.VibrationData.Average() : 0f,
                MaxVibration = run.VibrationData.Count > 0 ? run.VibrationData.Max() : 0f,

                AvgChipLoad = run.ChipLoadData.Count > 0 ? run.ChipLoadData.Average() : 0f,
                MaxChipLoad = run.ChipLoadData.Count > 0 ? run.ChipLoadData.Max() : 0f,

                CycleTime = run.CycleTime
            };
        }

        /// <summary>
        /// Compare two runs
        /// </summary>
        public RunComparison CompareRuns(string runId1, string runId2)
        {
            var run1 = runs.FirstOrDefault(r => r.RunId == runId1);
            var run2 = runs.FirstOrDefault(r => r.RunId == runId2);

            if (run1 == null || run2 == null)
            {
                Debug.LogWarning($"[ComparativeAnalyzer] One or both runs not found");
                return null;
            }

            var comparison = new RunComparison
            {
                Run1Id = runId1,
                Run2Id = runId2,
                ComparisonTime = DateTime.UtcNow,
                Metrics = new Dictionary<string, MetricComparison>()
            };

            // Compare forces
            if (compareForces && run1.ForceData.Count > 0 && run2.ForceData.Count > 0)
            {
                comparison.Metrics["force"] = new MetricComparison
                {
                    Run1Avg = run1.Statistics.AvgForce,
                    Run2Avg = run2.Statistics.AvgForce,
                    DifferencePercent = CalculatePercentageDifference(
                        run1.Statistics.AvgForce, run2.Statistics.AvgForce),
                    ImprovementDirection = run1.Statistics.AvgForce < run2.Statistics.AvgForce ? -1 : 1
                };
            }

            // Compare vibration
            if (compareVibration && run1.VibrationData.Count > 0 && run2.VibrationData.Count > 0)
            {
                comparison.Metrics["vibration"] = new MetricComparison
                {
                    Run1Avg = run1.Statistics.AvgVibration,
                    Run2Avg = run2.Statistics.AvgVibration,
                    DifferencePercent = CalculatePercentageDifference(
                        run1.Statistics.AvgVibration, run2.Statistics.AvgVibration),
                    ImprovementDirection = run1.Statistics.AvgVibration < run2.Statistics.AvgVibration ? -1 : 1
                };
            }

            // Compare chip load
            if (compareChipLoad && run1.ChipLoadData.Count > 0 && run2.ChipLoadData.Count > 0)
            {
                comparison.Metrics["chip_load"] = new MetricComparison
                {
                    Run1Avg = run1.Statistics.AvgChipLoad,
                    Run2Avg = run2.Statistics.AvgChipLoad,
                    DifferencePercent = CalculatePercentageDifference(
                        run1.Statistics.AvgChipLoad, run2.Statistics.AvgChipLoad),
                    ImprovementDirection = 0  // Neutral (depends on optimal range)
                };
            }

            // Compare cycle time
            if (compareCycleTime)
            {
                comparison.Metrics["cycle_time"] = new MetricComparison
                {
                    Run1Avg = run1.CycleTime,
                    Run2Avg = run2.CycleTime,
                    DifferencePercent = CalculatePercentageDifference(
                        run1.CycleTime, run2.CycleTime),
                    ImprovementDirection = run1.CycleTime < run2.CycleTime ? 1 : -1
                };
            }

            // Determine overall winner
            int improvementCount = comparison.Metrics.Values.Count(m => m.ImprovementDirection > 0);
            int degradationCount = comparison.Metrics.Values.Count(m => m.ImprovementDirection < 0);
            comparison.OverallWinner = improvementCount > degradationCount ? runId1 : runId2;

            totalComparisons++;
            string comparisonKey = $"{runId1}_vs_{runId2}";
            comparisons[comparisonKey] = comparison;

            OnComparisonCompleted?.Invoke(comparison);

            return comparison;
        }

        /// <summary>
        /// Analyze all runs for trends
        /// </summary>
        public void AnalyzeAllRuns()
        {
            if (runs.Count < 3)
            {
                return; // Need at least 3 runs for trend analysis
            }

            // Analyze force trends
            if (compareForces)
            {
                var forceTrend = AnalyzeTrend("force", runs.Select(r => r.Statistics.AvgForce).ToList());
                if (forceTrend != null)
                {
                    OnTrendDetected?.Invoke(forceTrend);
                }
            }

            // Analyze vibration trends
            if (compareVibration)
            {
                var vibrationTrend = AnalyzeTrend("vibration", runs.Select(r => r.Statistics.AvgVibration).ToList());
                if (vibrationTrend != null)
                {
                    OnTrendDetected?.Invoke(vibrationTrend);
                }
            }

            // Analyze cycle time trends
            if (compareCycleTime)
            {
                var cycleTimeTrend = AnalyzeTrend("cycle_time", runs.Select(r => r.CycleTime).ToList());
                if (cycleTimeTrend != null)
                {
                    OnTrendDetected?.Invoke(cycleTimeTrend);
                }
            }

            // Detect anomalies
            DetectAnomalies();
        }

        /// <summary>
        /// Analyze trend for a specific metric
        /// </summary>
        private TrendAnalysis AnalyzeTrend(string metricName, List<float> values)
        {
            if (values.Count < 3)
            {
                return null;
            }

            // Calculate simple linear regression
            float n = values.Count;
            float sumX = 0f;
            float sumY = 0f;
            float sumXY = 0f;
            float sumX2 = 0f;

            for (int i = 0; i < values.Count; i++)
            {
                float x = i;
                float y = values[i];
                sumX += x;
                sumY += y;
                sumXY += x * y;
                sumX2 += x * x;
            }

            float slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
            float intercept = (sumY - slope * sumX) / n;

            // Determine trend direction
            TrendDirection direction = TrendDirection.Stable;
            if (Mathf.Abs(slope) > 0.01f)
            {
                direction = slope > 0 ? TrendDirection.Increasing : TrendDirection.Decreasing;
            }

            // Calculate R-squared (goodness of fit)
            float meanY = sumY / n;
            float ssTotal = 0f;
            float ssResidual = 0f;

            for (int i = 0; i < values.Count; i++)
            {
                float predicted = slope * i + intercept;
                ssTotal += Mathf.Pow(values[i] - meanY, 2);
                ssResidual += Mathf.Pow(values[i] - predicted, 2);
            }

            float rSquared = 1f - (ssResidual / ssTotal);

            return new TrendAnalysis
            {
                MetricName = metricName,
                Direction = direction,
                Slope = slope,
                Confidence = rSquared,
                DataPoints = values.Count,
                IsSignificant = rSquared > 0.5f && Mathf.Abs(slope) > 0.05f
            };
        }

        /// <summary>
        /// Detect anomalies in run data
        /// </summary>
        private void DetectAnomalies()
        {
            if (runs.Count < 3)
            {
                return;
            }

            // Check for force anomalies
            if (compareForces)
            {
                var forceValues = runs.Select(r => r.Statistics.AvgForce).ToList();
                var forceAnomaly = DetectOutliers("force", forceValues);
                if (forceAnomaly != null)
                {
                    anomaliesDetected++;
                    OnAnomalyDetected?.Invoke(forceAnomaly);
                }
            }

            // Check for vibration anomalies
            if (compareVibration)
            {
                var vibrationValues = runs.Select(r => r.Statistics.AvgVibration).ToList();
                var vibrationAnomaly = DetectOutliers("vibration", vibrationValues);
                if (vibrationAnomaly != null)
                {
                    anomaliesDetected++;
                    OnAnomalyDetected?.Invoke(vibrationAnomaly);
                }
            }
        }

        /// <summary>
        /// Detect outliers using modified Z-score
        /// </summary>
        private AnomalyDetection DetectOutliers(string metricName, List<float> values)
        {
            if (values.Count < 3)
            {
                return null;
            }

            float mean = values.Average();
            float stdDev = CalculateStandardDeviation(values, mean);

            List<int> anomalyIndices = new List<int>();

            for (int i = 0; i < values.Count; i++)
            {
                float zScore = Mathf.Abs((values[i] - mean) / stdDev);
                if (zScore > 2.5f) // Threshold for anomaly
                {
                    anomalyIndices.Add(i);
                }
            }

            if (anomalyIndices.Count > 0)
            {
                return new AnomalyDetection
                {
                    MetricName = metricName,
                    AnomalyIndices = anomalyIndices,
                    AffectedRuns = anomalyIndices.Select(i => runs[i].RunId).ToList(),
                    Mean = mean,
                    StandardDeviation = stdDev,
                    Severity = anomalyIndices.Count >= values.Count * 0.3f ?
                        AnomalySeverity.High : AnomalySeverity.Medium
                };
            }

            return null;
        }

        /// <summary>
        /// Calculate percentage difference between two values
        /// </summary>
        private float CalculatePercentageDifference(float value1, float value2)
        {
            if (value1 == 0f)
            {
                return value2 == 0f ? 0f : 100f;
            }
            return ((value2 - value1) / value1) * 100f;
        }

        /// <summary>
        /// Calculate standard deviation
        /// </summary>
        private float CalculateStandardDeviation(List<float> values, float mean)
        {
            float sumSquaredDiff = values.Sum(v => Mathf.Pow(v - mean, 2));
            return Mathf.Sqrt(sumSquaredDiff / values.Count);
        }

        /// <summary>
        /// Get comparison summary
        /// </summary>
        public ComparisonSummary GetComparisonSummary()
        {
            return new ComparisonSummary
            {
                TotalRuns = runs.Count,
                TotalComparisons = totalComparisons,
                AnomaliesDetected = anomaliesDetected,
                LatestRun = runs.Count > 0 ? runs[runs.Count - 1].RunId : "",
                BestCycleTime = runs.Count > 0 ? runs.Min(r => r.CycleTime) : 0f,
                WorstCycleTime = runs.Count > 0 ? runs.Max(r => r.CycleTime) : 0f
            };
        }

        #region Public Properties

        public int RunCount => runs.Count;
        public bool IsTrackingRun => isTrackingRun;
        public List<MachiningRun> Runs => runs;
        public Dictionary<string, RunComparison> Comparisons => comparisons;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Machining run data
    /// </summary>
    [Serializable]
    public class MachiningRun
    {
        public string RunId;
        public string ProgramName;
        public DateTime StartTime;
        public DateTime EndTime;
        public float CycleTime;
        public bool IsComplete;
        public Dictionary<string, object> Metadata;
        public List<float> ForceData;
        public List<float> VibrationData;
        public List<float> ChipLoadData;
        public List<float> MaterialRemovalData;
        public RunStatistics Statistics;
    }

    /// <summary>
    /// Run statistics
    /// </summary>
    [Serializable]
    public struct RunStatistics
    {
        public float AvgForce;
        public float MaxForce;
        public float MinForce;
        public float AvgVibration;
        public float MaxVibration;
        public float AvgChipLoad;
        public float MaxChipLoad;
        public float CycleTime;
    }

    /// <summary>
    /// Run comparison
    /// </summary>
    [Serializable]
    public class RunComparison
    {
        public string Run1Id;
        public string Run2Id;
        public DateTime ComparisonTime;
        public Dictionary<string, MetricComparison> Metrics;
        public string OverallWinner;
    }

    /// <summary>
    /// Metric comparison
    /// </summary>
    [Serializable]
    public struct MetricComparison
    {
        public float Run1Avg;
        public float Run2Avg;
        public float DifferencePercent;
        public int ImprovementDirection; // 1 = Run1 better, -1 = Run2 better, 0 = neutral
    }

    /// <summary>
    /// Trend analysis
    /// </summary>
    [Serializable]
    public struct TrendAnalysis
    {
        public string MetricName;
        public TrendDirection Direction;
        public float Slope;
        public float Confidence;
        public int DataPoints;
        public bool IsSignificant;
    }

    /// <summary>
    /// Trend direction
    /// </summary>
    public enum TrendDirection
    {
        Increasing,
        Decreasing,
        Stable
    }

    /// <summary>
    /// Anomaly detection
    /// </summary>
    [Serializable]
    public struct AnomalyDetection
    {
        public string MetricName;
        public List<int> AnomalyIndices;
        public List<string> AffectedRuns;
        public float Mean;
        public float StandardDeviation;
        public AnomalySeverity Severity;
    }

    /// <summary>
    /// Anomaly severity
    /// </summary>
    public enum AnomalySeverity
    {
        Low,
        Medium,
        High,
        Critical
    }

    /// <summary>
    /// Comparison summary
    /// </summary>
    [Serializable]
    public struct ComparisonSummary
    {
        public int TotalRuns;
        public int TotalComparisons;
        public int AnomaliesDetected;
        public string LatestRun;
        public float BestCycleTime;
        public float WorstCycleTime;
    }

    #endregion
}
