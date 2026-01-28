using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCScada.Analytics
{
    /// <summary>
    /// Automated root cause analysis for manufacturing issues.
    /// Analyzes patterns in historical data to identify likely causes of defects and failures.
    /// Part of Feature 3.2: Root Cause Analysis (MEDIUM PRIORITY - Phase 3)
    /// </summary>
    public class RootCauseAnalyzer : MonoBehaviour
    {
        [Header("Analysis Configuration")]
        [SerializeField] private bool enableAutomaticAnalysis = true;
        [SerializeField] private float analysisInterval = 300f; // 5 minutes
        [SerializeField] private int historicalWindowSize = 100; // Number of past events to analyze

        [Header("Detection Thresholds")]
        [SerializeField] private float correlationThreshold = 0.7f;
        [SerializeField] private float patternMatchThreshold = 0.8f;
        [SerializeField] private int minimumPatternOccurrences = 3;

        [Header("Issue Categories")]
        [SerializeField] private bool analyzeQualityIssues = true;
        [SerializeField] private bool analyzeToolFailures = true;
        [SerializeField] private bool analyzeProcessDeviations = true;
        [SerializeField] private bool analyzeDowntime = true;

        // Historical data storage
        private List<ManufacturingEvent> eventHistory = new List<ManufacturingEvent>();
        private List<QualityIssue> qualityIssues = new List<QualityIssue>();
        private List<RootCauseAnalysis> analysisResults = new List<RootCauseAnalysis>();

        // Analysis timing
        private float analysisTimer = 0f;

        // Pattern library
        private Dictionary<string, List<CausePattern>> knownPatterns = new Dictionary<string, List<CausePattern>>();

        // Events
        public event Action<RootCauseAnalysis> OnAnalysisCompleted;
        public event Action<CausePattern> OnPatternDetected;

        // Statistics
        private int totalAnalyses = 0;
        private int patternsDetected = 0;
        private int rootCausesIdentified = 0;

        void Start()
        {
            InitializeKnownPatterns();
        }

        void Update()
        {
            if (enableAutomaticAnalysis)
            {
                analysisTimer += Time.deltaTime;
                if (analysisTimer >= analysisInterval)
                {
                    PerformPeriodicAnalysis();
                    analysisTimer = 0f;
                }
            }
        }

        /// <summary>
        /// Initialize library of known cause patterns
        /// </summary>
        private void InitializeKnownPatterns()
        {
            // Quality issue patterns
            knownPatterns["dimensional_deviation"] = new List<CausePattern>
            {
                new CausePattern
                {
                    PatternName = "Tool Wear",
                    IndicatorEvents = new List<string> { "tool_age_high", "cutting_force_increase", "surface_finish_degradation" },
                    Confidence = 0.85f,
                    Recommendation = "Replace cutting tool and verify tool offset"
                },
                new CausePattern
                {
                    PatternName = "Thermal Expansion",
                    IndicatorEvents = new List<string> { "temperature_increase", "dimensional_drift", "time_correlation" },
                    Confidence = 0.75f,
                    Recommendation = "Implement thermal compensation or allow warmup time"
                },
                new CausePattern
                {
                    PatternName = "Workholding Issue",
                    IndicatorEvents = new List<string> { "vibration_increase", "positional_error", "random_pattern" },
                    Confidence = 0.70f,
                    Recommendation = "Check workpiece clamping and fixture integrity"
                }
            };

            // Tool failure patterns
            knownPatterns["tool_breakage"] = new List<CausePattern>
            {
                new CausePattern
                {
                    PatternName = "Excessive Feed Rate",
                    IndicatorEvents = new List<string> { "feed_rate_high", "cutting_force_spike", "sudden_failure" },
                    Confidence = 0.90f,
                    Recommendation = "Reduce feed rate and verify program parameters"
                },
                new CausePattern
                {
                    PatternName = "Material Hardness Variation",
                    IndicatorEvents = new List<string> { "force_variation", "spindle_load_spike", "inconsistent_cutting" },
                    Confidence = 0.80f,
                    Recommendation = "Verify material certification and adjust cutting parameters"
                },
                new CausePattern
                {
                    PatternName = "Coolant Issues",
                    IndicatorEvents = new List<string> { "temperature_spike", "built_up_edge", "chip_evacuation_poor" },
                    Confidence = 0.75f,
                    Recommendation = "Check coolant flow, concentration, and delivery"
                }
            };

            // Process deviation patterns
            knownPatterns["cycle_time_increase"] = new List<CausePattern>
            {
                new CausePattern
                {
                    PatternName = "Spindle Performance Degradation",
                    IndicatorEvents = new List<string> { "spindle_speed_deviation", "power_draw_increase", "gradual_slowdown" },
                    Confidence = 0.85f,
                    Recommendation = "Schedule spindle maintenance and bearing inspection"
                },
                new CausePattern
                {
                    PatternName = "Axis Servo Issues",
                    IndicatorEvents = new List<string> { "positioning_delay", "following_error", "vibration_low_frequency" },
                    Confidence = 0.80f,
                    Recommendation = "Check servo tuning and mechanical components"
                }
            };

            // Downtime patterns
            knownPatterns["unplanned_downtime"] = new List<CausePattern>
            {
                new CausePattern
                {
                    PatternName = "Preventive Maintenance Overdue",
                    IndicatorEvents = new List<string> { "operating_hours_high", "alarm_frequency_increase", "degrading_performance" },
                    Confidence = 0.75f,
                    Recommendation = "Execute scheduled maintenance tasks immediately"
                },
                new CausePattern
                {
                    PatternName = "Operator Error",
                    IndicatorEvents = new List<string> { "shift_correlation", "alarm_type_repetitive", "manual_intervention" },
                    Confidence = 0.70f,
                    Recommendation = "Provide additional operator training and review procedures"
                }
            };

            Debug.Log($"[RootCauseAnalyzer] Initialized with {knownPatterns.Count} pattern categories");
        }

        /// <summary>
        /// Record a manufacturing event for analysis
        /// </summary>
        public void RecordEvent(string eventType, string description, Dictionary<string, object> parameters)
        {
            var manufacturingEvent = new ManufacturingEvent
            {
                EventId = Guid.NewGuid().ToString(),
                EventType = eventType,
                Description = description,
                Timestamp = DateTime.UtcNow,
                Parameters = parameters ?? new Dictionary<string, object>()
            };

            eventHistory.Add(manufacturingEvent);

            // Enforce history limit
            if (eventHistory.Count > historicalWindowSize)
            {
                eventHistory.RemoveAt(0);
            }

            // Check for immediate pattern matches
            CheckForPatterns(manufacturingEvent);
        }

        /// <summary>
        /// Record a quality issue for root cause analysis
        /// </summary>
        public void RecordQualityIssue(string issueType, string description, float severity,
                                       Dictionary<string, float> measurements = null)
        {
            var issue = new QualityIssue
            {
                IssueId = Guid.NewGuid().ToString(),
                IssueType = issueType,
                Description = description,
                Severity = severity,
                Timestamp = DateTime.UtcNow,
                Measurements = measurements ?? new Dictionary<string, float>()
            };

            qualityIssues.Add(issue);

            // Trigger analysis for this issue
            if (analyzeQualityIssues)
            {
                AnalyzeQualityIssue(issue);
            }
        }

        /// <summary>
        /// Perform periodic analysis of all recent events
        /// </summary>
        private void PerformPeriodicAnalysis()
        {
            if (eventHistory.Count < 10) return; // Need minimum data

            // Analyze patterns in event history
            var recentEvents = eventHistory.Skip(Math.Max(0, eventHistory.Count - 50)).ToList();
            var patterns = DetectPatterns(recentEvents);

            foreach (var pattern in patterns)
            {
                OnPatternDetected?.Invoke(pattern);
                patternsDetected++;
            }

            totalAnalyses++;
            Debug.Log($"[RootCauseAnalyzer] Periodic analysis completed. Patterns detected: {patterns.Count}");
        }

        /// <summary>
        /// Analyze a specific quality issue
        /// </summary>
        private void AnalyzeQualityIssue(QualityIssue issue)
        {
            var analysis = new RootCauseAnalysis
            {
                AnalysisId = Guid.NewGuid().ToString(),
                IssueId = issue.IssueId,
                IssueType = issue.IssueType,
                Timestamp = DateTime.UtcNow,
                PotentialCauses = new List<PotentialCause>()
            };

            // Find matching patterns
            if (knownPatterns.ContainsKey(issue.IssueType))
            {
                var patterns = knownPatterns[issue.IssueType];
                var recentEvents = eventHistory.Skip(Math.Max(0, eventHistory.Count - 20)).ToList();

                foreach (var pattern in patterns)
                {
                    float matchScore = CalculatePatternMatch(pattern, recentEvents);

                    if (matchScore >= patternMatchThreshold)
                    {
                        analysis.PotentialCauses.Add(new PotentialCause
                        {
                            CauseName = pattern.PatternName,
                            Confidence = matchScore * pattern.Confidence,
                            SupportingEvidence = pattern.IndicatorEvents,
                            Recommendation = pattern.Recommendation
                        });
                    }
                }
            }

            // Sort causes by confidence
            analysis.PotentialCauses = analysis.PotentialCauses.OrderByDescending(c => c.Confidence).ToList();

            if (analysis.PotentialCauses.Count > 0)
            {
                analysis.PrimaryCause = analysis.PotentialCauses[0];
                rootCausesIdentified++;
            }

            analysisResults.Add(analysis);
            OnAnalysisCompleted?.Invoke(analysis);

            Debug.Log($"[RootCauseAnalyzer] Analysis completed for {issue.IssueType}. " +
                     $"Potential causes: {analysis.PotentialCauses.Count}");
        }

        /// <summary>
        /// Check for pattern matches after each event
        /// </summary>
        private void CheckForPatterns(ManufacturingEvent newEvent)
        {
            // Simple real-time pattern checking
            var recentEvents = eventHistory.Skip(Math.Max(0, eventHistory.Count - 10)).ToList();

            // Check for specific indicator sequences
            foreach (var patternCategory in knownPatterns.Values)
            {
                foreach (var pattern in patternCategory)
                {
                    if (pattern.IndicatorEvents.Contains(newEvent.EventType))
                    {
                        float matchScore = CalculatePatternMatch(pattern, recentEvents);
                        if (matchScore >= correlationThreshold)
                        {
                            OnPatternDetected?.Invoke(pattern);
                        }
                    }
                }
            }
        }

        /// <summary>
        /// Calculate pattern match score
        /// </summary>
        private float CalculatePatternMatch(CausePattern pattern, List<ManufacturingEvent> events)
        {
            if (events.Count == 0) return 0f;

            int matchCount = 0;
            var eventTypes = events.Select(e => e.EventType).ToList();

            foreach (var indicator in pattern.IndicatorEvents)
            {
                if (eventTypes.Contains(indicator))
                {
                    matchCount++;
                }
            }

            return (float)matchCount / pattern.IndicatorEvents.Count;
        }

        /// <summary>
        /// Detect patterns in event sequence
        /// </summary>
        private List<CausePattern> DetectPatterns(List<ManufacturingEvent> events)
        {
            var detectedPatterns = new List<CausePattern>();

            foreach (var patternCategory in knownPatterns.Values)
            {
                foreach (var pattern in patternCategory)
                {
                    float matchScore = CalculatePatternMatch(pattern, events);
                    if (matchScore >= patternMatchThreshold)
                    {
                        detectedPatterns.Add(pattern);
                    }
                }
            }

            return detectedPatterns;
        }

        /// <summary>
        /// Get most recent analysis results
        /// </summary>
        public List<RootCauseAnalysis> GetRecentAnalyses(int count = 10)
        {
            return analysisResults.Skip(Math.Max(0, analysisResults.Count - count)).ToList();
        }

        /// <summary>
        /// Get analysis statistics
        /// </summary>
        public AnalysisStatistics GetStatistics()
        {
            return new AnalysisStatistics
            {
                TotalAnalyses = totalAnalyses,
                PatternsDetected = patternsDetected,
                RootCausesIdentified = rootCausesIdentified,
                EventHistorySize = eventHistory.Count,
                QualityIssuesTracked = qualityIssues.Count,
                AverageConfidence = analysisResults.Count > 0 ?
                    analysisResults.Average(a => a.PrimaryCause?.Confidence ?? 0) : 0
            };
        }

        /// <summary>
        /// Clear historical data
        /// </summary>
        public void ClearHistory()
        {
            eventHistory.Clear();
            qualityIssues.Clear();
            analysisResults.Clear();
            Debug.Log("[RootCauseAnalyzer] History cleared");
        }

        #region Public Properties

        public int EventCount => eventHistory.Count;
        public int QualityIssueCount => qualityIssues.Count;
        public int AnalysisCount => analysisResults.Count;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Manufacturing event record
    /// </summary>
    [Serializable]
    public class ManufacturingEvent
    {
        public string EventId;
        public string EventType;
        public string Description;
        public DateTime Timestamp;
        public Dictionary<string, object> Parameters;
    }

    /// <summary>
    /// Quality issue record
    /// </summary>
    [Serializable]
    public class QualityIssue
    {
        public string IssueId;
        public string IssueType;
        public string Description;
        public float Severity;
        public DateTime Timestamp;
        public Dictionary<string, float> Measurements;
    }

    /// <summary>
    /// Root cause analysis result
    /// </summary>
    [Serializable]
    public class RootCauseAnalysis
    {
        public string AnalysisId;
        public string IssueId;
        public string IssueType;
        public DateTime Timestamp;
        public List<PotentialCause> PotentialCauses;
        public PotentialCause PrimaryCause;
    }

    /// <summary>
    /// Potential cause with confidence score
    /// </summary>
    [Serializable]
    public class PotentialCause
    {
        public string CauseName;
        public float Confidence;
        public List<string> SupportingEvidence;
        public string Recommendation;
    }

    /// <summary>
    /// Known cause pattern
    /// </summary>
    [Serializable]
    public class CausePattern
    {
        public string PatternName;
        public List<string> IndicatorEvents;
        public float Confidence;
        public string Recommendation;
    }

    /// <summary>
    /// Analysis statistics
    /// </summary>
    [Serializable]
    public struct AnalysisStatistics
    {
        public int TotalAnalyses;
        public int PatternsDetected;
        public int RootCausesIdentified;
        public int EventHistorySize;
        public int QualityIssuesTracked;
        public float AverageConfidence;
    }

    #endregion
}
