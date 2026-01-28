using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCDigitalTwin.Analytics
{
    /// <summary>
    /// Production Analytics Engine for CNC Digital Twin
    /// Provides OEE calculation, performance metrics, production insights,
    /// trend analysis, and manufacturing intelligence
    /// </summary>
    public class ProductionAnalyticsEngine : MonoBehaviour
    {
        public static ProductionAnalyticsEngine Instance { get; private set; }

        [Header("Analytics Configuration")]
        [SerializeField] private float metricsUpdateInterval = 60f; // seconds
        [SerializeField] private float realTimeUpdateInterval = 5f; // seconds
        [SerializeField] private int trendHistoryDays = 30;
        [SerializeField] private bool enablePredictiveAnalytics = true;

        [Header("OEE Targets")]
        [SerializeField] private float targetOEE = 85f;
        [SerializeField] private float targetAvailability = 90f;
        [SerializeField] private float targetPerformance = 95f;
        [SerializeField] private float targetQuality = 99f;

        [Header("Shift Configuration")]
        [SerializeField] private int shiftStartHour = 6;
        [SerializeField] private int shiftDurationHours = 8;
        [SerializeField] private int plannedBreakMinutes = 30;

        // Events
        public event Action<OEEMetrics> OnOEEUpdated;
        public event Action<MachineMetrics> OnMachineMetricsUpdated;
        public event Action<ProductionSummary> OnProductionSummaryReady;
        public event Action<AnalyticsAlert> OnAlertGenerated;
        public event Action<TrendAnalysis> OnTrendAnalysisComplete;
        public event Action<PredictiveInsight> OnPredictiveInsight;

        // Data collections
        private Dictionary<string, MachineAnalytics> machineAnalytics = new Dictionary<string, MachineAnalytics>();
        private Dictionary<string, ProductAnalytics> productAnalytics = new Dictionary<string, ProductAnalytics>();
        private Dictionary<string, ShiftData> shiftData = new Dictionary<string, ShiftData>();
        private List<ProductionEvent> productionEvents = new List<ProductionEvent>();
        private List<DowntimeEvent> downtimeEvents = new List<DowntimeEvent>();
        private List<QualityEvent> qualityEvents = new List<QualityEvent>();

        // Current state
        private OEEMetrics currentOEE = new OEEMetrics();
        private ProductionSummary currentSummary = new ProductionSummary();

        // Statistics
        private AnalyticsStats stats = new AnalyticsStats();

        #region Data Structures

        public enum MachineState
        {
            Running,
            Idle,
            Setup,
            Breakdown,
            PlannedDowntime,
            UnplannedDowntime,
            Maintenance,
            Starved,
            Blocked,
            Offline
        }

        public enum DowntimeCategory
        {
            Planned_Maintenance,
            Planned_Break,
            Planned_Changeover,
            Unplanned_Breakdown,
            Unplanned_Material,
            Unplanned_Quality,
            Unplanned_Operator,
            Unplanned_External,
            Unknown
        }

        public enum QualityCategory
        {
            Good,
            Rework,
            Scrap,
            Hold,
            Unknown
        }

        public class OEEMetrics
        {
            public DateTime Timestamp { get; set; }
            public string MachineId { get; set; }
            public string ShiftId { get; set; }

            // Core OEE components
            public float Availability { get; set; } // %
            public float Performance { get; set; } // %
            public float Quality { get; set; } // %
            public float OEE => Availability * Performance * Quality / 10000f;

            // Time breakdown
            public TimeSpan PlannedProductionTime { get; set; }
            public TimeSpan RunTime { get; set; }
            public TimeSpan DownTime { get; set; }
            public TimeSpan IdleTime { get; set; }
            public TimeSpan SetupTime { get; set; }

            // Production counts
            public int TotalCount { get; set; }
            public int GoodCount { get; set; }
            public int RejectCount { get; set; }
            public int ReworkCount { get; set; }

            // Rates
            public float IdealCycleTime { get; set; } // seconds
            public float ActualCycleTime { get; set; } // seconds
            public float TheoreticalOutput { get; set; }
            public float ActualOutput { get; set; }

            // Losses
            public float AvailabilityLoss { get; set; } // pieces
            public float PerformanceLoss { get; set; } // pieces
            public float QualityLoss { get; set; } // pieces
        }

        public class MachineAnalytics
        {
            public string MachineId { get; set; }
            public string MachineName { get; set; }
            public MachineState CurrentState { get; set; }
            public DateTime StateStartTime { get; set; }
            public DateTime LastUpdateTime { get; set; }

            // Cumulative times
            public Dictionary<MachineState, TimeSpan> StateTimes { get; set; } = new Dictionary<MachineState, TimeSpan>();

            // Performance tracking
            public float CurrentCycleTime { get; set; }
            public List<float> CycleTimeHistory { get; set; } = new List<float>();
            public int PartCount { get; set; }
            public int GoodPartCount { get; set; }
            public int RejectCount { get; set; }

            // Current OEE
            public OEEMetrics CurrentOEE { get; set; } = new OEEMetrics();

            // Trend data
            public List<OEETrendPoint> OEEHistory { get; set; } = new List<OEETrendPoint>();
            public List<DowntimeEvent> DowntimeHistory { get; set; } = new List<DowntimeEvent>();
        }

        public class ProductAnalytics
        {
            public string ProductId { get; set; }
            public string ProductName { get; set; }
            public float StandardCycleTime { get; set; }
            public int TotalProduced { get; set; }
            public int GoodParts { get; set; }
            public int Rejects { get; set; }
            public float YieldRate => TotalProduced > 0 ? (float)GoodParts / TotalProduced * 100f : 0;
            public float AverageCycleTime { get; set; }
            public List<float> CycleTimeHistory { get; set; } = new List<float>();
            public Dictionary<string, int> DefectCounts { get; set; } = new Dictionary<string, int>();
        }

        public class ShiftData
        {
            public string ShiftId { get; set; }
            public string ShiftName { get; set; }
            public DateTime StartTime { get; set; }
            public DateTime EndTime { get; set; }
            public TimeSpan PlannedDuration { get; set; }
            public TimeSpan PlannedBreaks { get; set; }
            public TimeSpan ActualRunTime { get; set; }
            public int PlannedOutput { get; set; }
            public int ActualOutput { get; set; }
            public OEEMetrics ShiftOEE { get; set; } = new OEEMetrics();
            public List<string> Operators { get; set; } = new List<string>();
        }

        public class ProductionEvent
        {
            public string EventId { get; set; }
            public string MachineId { get; set; }
            public string ProductId { get; set; }
            public DateTime Timestamp { get; set; }
            public float CycleTime { get; set; }
            public QualityCategory Quality { get; set; }
            public string OperatorId { get; set; }
            public Dictionary<string, object> ProcessData { get; set; } = new Dictionary<string, object>();
        }

        public class DowntimeEvent
        {
            public string EventId { get; set; }
            public string MachineId { get; set; }
            public DateTime StartTime { get; set; }
            public DateTime? EndTime { get; set; }
            public TimeSpan Duration => EndTime.HasValue ? EndTime.Value - StartTime : DateTime.Now - StartTime;
            public DowntimeCategory Category { get; set; }
            public string ReasonCode { get; set; }
            public string Description { get; set; }
            public bool IsPlanned { get; set; }
            public string ResponsibleDepartment { get; set; }
        }

        public class QualityEvent
        {
            public string EventId { get; set; }
            public string MachineId { get; set; }
            public string ProductId { get; set; }
            public string PartId { get; set; }
            public DateTime Timestamp { get; set; }
            public QualityCategory Category { get; set; }
            public string DefectType { get; set; }
            public string DefectCode { get; set; }
            public float? MeasuredValue { get; set; }
            public float? SpecificationMin { get; set; }
            public float? SpecificationMax { get; set; }
            public string InspectionStation { get; set; }
        }

        public class OEETrendPoint
        {
            public DateTime Timestamp { get; set; }
            public float OEE { get; set; }
            public float Availability { get; set; }
            public float Performance { get; set; }
            public float Quality { get; set; }
        }

        public class TrendAnalysis
        {
            public string MetricName { get; set; }
            public DateTime AnalysisTime { get; set; }
            public float CurrentValue { get; set; }
            public float AverageValue { get; set; }
            public float TrendSlope { get; set; } // Positive = improving
            public float TrendConfidence { get; set; }
            public string TrendDirection { get; set; } // "Improving", "Declining", "Stable"
            public float PredictedNextValue { get; set; }
            public List<float> HistoricalValues { get; set; } = new List<float>();
        }

        public class PredictiveInsight
        {
            public string InsightId { get; set; }
            public string Category { get; set; }
            public string Title { get; set; }
            public string Description { get; set; }
            public float Confidence { get; set; }
            public float ImpactValue { get; set; }
            public string RecommendedAction { get; set; }
            public DateTime PredictedOccurrence { get; set; }
            public Dictionary<string, object> SupportingData { get; set; } = new Dictionary<string, object>();
        }

        public class ProductionSummary
        {
            public DateTime ReportTime { get; set; }
            public string Period { get; set; } // "Shift", "Day", "Week", "Month"
            public DateTime PeriodStart { get; set; }
            public DateTime PeriodEnd { get; set; }

            // Overall metrics
            public float OverallOEE { get; set; }
            public int TotalParts { get; set; }
            public int GoodParts { get; set; }
            public float YieldRate { get; set; }

            // Time analysis
            public TimeSpan TotalAvailableTime { get; set; }
            public TimeSpan TotalRunTime { get; set; }
            public TimeSpan TotalDownTime { get; set; }
            public float Utilization { get; set; }

            // Top issues
            public List<DowntimeSummary> TopDowntimeReasons { get; set; } = new List<DowntimeSummary>();
            public List<QualitySummary> TopQualityIssues { get; set; } = new List<QualitySummary>();
            public List<MachineSummary> MachinePerformance { get; set; } = new List<MachineSummary>();
        }

        public class DowntimeSummary
        {
            public string ReasonCode { get; set; }
            public DowntimeCategory Category { get; set; }
            public int Occurrences { get; set; }
            public TimeSpan TotalDuration { get; set; }
            public float PercentOfDowntime { get; set; }
        }

        public class QualitySummary
        {
            public string DefectType { get; set; }
            public int Count { get; set; }
            public float PercentOfRejects { get; set; }
            public string TopMachine { get; set; }
        }

        public class MachineSummary
        {
            public string MachineId { get; set; }
            public string MachineName { get; set; }
            public float OEE { get; set; }
            public float Availability { get; set; }
            public float Performance { get; set; }
            public float Quality { get; set; }
            public int PartsProduced { get; set; }
        }

        public class AnalyticsAlert
        {
            public string AlertId { get; set; }
            public string Category { get; set; }
            public AlertSeverity Severity { get; set; }
            public string Message { get; set; }
            public string MachineId { get; set; }
            public object CurrentValue { get; set; }
            public object Threshold { get; set; }
            public DateTime Timestamp { get; set; }
            public string RecommendedAction { get; set; }
        }

        public enum AlertSeverity
        {
            Info,
            Warning,
            Critical
        }

        public class AnalyticsStats
        {
            public DateTime StartTime { get; set; }
            public int MachinesTracked { get; set; }
            public int ProductsTracked { get; set; }
            public long EventsProcessed { get; set; }
            public int AlertsGenerated { get; set; }
            public int ReportsGenerated { get; set; }
        }

        #endregion

        #region Initialization

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
            }
            else
            {
                Destroy(gameObject);
                return;
            }

            stats.StartTime = DateTime.Now;
        }

        private void Start()
        {
            StartCoroutine(RealTimeMetricsLoop());
            StartCoroutine(PeriodicMetricsLoop());
            StartCoroutine(TrendAnalysisLoop());

            if (enablePredictiveAnalytics)
            {
                StartCoroutine(PredictiveAnalyticsLoop());
            }

            Debug.Log("[ProductionAnalytics] Engine initialized");
        }

        #endregion

        #region Machine Tracking

        public void RegisterMachine(string machineId, string machineName)
        {
            var analytics = new MachineAnalytics
            {
                MachineId = machineId,
                MachineName = machineName,
                CurrentState = MachineState.Offline,
                StateStartTime = DateTime.Now,
                LastUpdateTime = DateTime.Now
            };

            // Initialize state times
            foreach (MachineState state in Enum.GetValues(typeof(MachineState)))
            {
                analytics.StateTimes[state] = TimeSpan.Zero;
            }

            machineAnalytics[machineId] = analytics;
            stats.MachinesTracked++;

            Debug.Log($"[ProductionAnalytics] Registered machine: {machineId}");
        }

        public void UpdateMachineState(string machineId, MachineState newState)
        {
            if (!machineAnalytics.TryGetValue(machineId, out var analytics))
                return;

            var now = DateTime.Now;
            var duration = now - analytics.StateStartTime;

            // Accumulate time in previous state
            analytics.StateTimes[analytics.CurrentState] += duration;

            // Track downtime events
            if (IsDowntimeState(analytics.CurrentState) && !IsDowntimeState(newState))
            {
                // End downtime event
                var activeDowntime = downtimeEvents.LastOrDefault(d =>
                    d.MachineId == machineId && !d.EndTime.HasValue);
                if (activeDowntime != null)
                {
                    activeDowntime.EndTime = now;
                }
            }
            else if (!IsDowntimeState(analytics.CurrentState) && IsDowntimeState(newState))
            {
                // Start downtime event
                downtimeEvents.Add(new DowntimeEvent
                {
                    EventId = Guid.NewGuid().ToString(),
                    MachineId = machineId,
                    StartTime = now,
                    Category = MapStateToDowntimeCategory(newState),
                    IsPlanned = newState == MachineState.PlannedDowntime || newState == MachineState.Maintenance
                });
            }

            analytics.CurrentState = newState;
            analytics.StateStartTime = now;
            analytics.LastUpdateTime = now;
        }

        private bool IsDowntimeState(MachineState state)
        {
            return state == MachineState.Breakdown ||
                   state == MachineState.PlannedDowntime ||
                   state == MachineState.UnplannedDowntime ||
                   state == MachineState.Maintenance;
        }

        private DowntimeCategory MapStateToDowntimeCategory(MachineState state)
        {
            return state switch
            {
                MachineState.PlannedDowntime => DowntimeCategory.Planned_Maintenance,
                MachineState.Maintenance => DowntimeCategory.Planned_Maintenance,
                MachineState.Breakdown => DowntimeCategory.Unplanned_Breakdown,
                MachineState.UnplannedDowntime => DowntimeCategory.Unknown,
                _ => DowntimeCategory.Unknown
            };
        }

        #endregion

        #region Production Events

        public void RecordProduction(string machineId, string productId, float cycleTime,
            QualityCategory quality = QualityCategory.Good, Dictionary<string, object> processData = null)
        {
            var evt = new ProductionEvent
            {
                EventId = Guid.NewGuid().ToString(),
                MachineId = machineId,
                ProductId = productId,
                Timestamp = DateTime.Now,
                CycleTime = cycleTime,
                Quality = quality,
                ProcessData = processData ?? new Dictionary<string, object>()
            };

            productionEvents.Add(evt);
            stats.EventsProcessed++;

            // Update machine analytics
            if (machineAnalytics.TryGetValue(machineId, out var machine))
            {
                machine.PartCount++;
                machine.CurrentCycleTime = cycleTime;
                machine.CycleTimeHistory.Add(cycleTime);
                if (machine.CycleTimeHistory.Count > 100)
                    machine.CycleTimeHistory.RemoveAt(0);

                if (quality == QualityCategory.Good)
                    machine.GoodPartCount++;
                else
                    machine.RejectCount++;
            }

            // Update product analytics
            if (!productAnalytics.ContainsKey(productId))
            {
                productAnalytics[productId] = new ProductAnalytics
                {
                    ProductId = productId,
                    ProductName = productId
                };
                stats.ProductsTracked++;
            }

            var product = productAnalytics[productId];
            product.TotalProduced++;
            product.CycleTimeHistory.Add(cycleTime);
            if (product.CycleTimeHistory.Count > 100)
                product.CycleTimeHistory.RemoveAt(0);
            product.AverageCycleTime = product.CycleTimeHistory.Average();

            if (quality == QualityCategory.Good)
                product.GoodParts++;
            else
                product.Rejects++;

            // Quality event for non-good parts
            if (quality != QualityCategory.Good)
            {
                RecordQualityIssue(machineId, productId, quality, null);
            }
        }

        public void RecordQualityIssue(string machineId, string productId, QualityCategory category,
            string defectType, float? measuredValue = null, float? specMin = null, float? specMax = null)
        {
            var evt = new QualityEvent
            {
                EventId = Guid.NewGuid().ToString(),
                MachineId = machineId,
                ProductId = productId,
                Timestamp = DateTime.Now,
                Category = category,
                DefectType = defectType,
                MeasuredValue = measuredValue,
                SpecificationMin = specMin,
                SpecificationMax = specMax
            };

            qualityEvents.Add(evt);

            // Track defect types
            if (productAnalytics.TryGetValue(productId, out var product))
            {
                string defectKey = defectType ?? category.ToString();
                if (!product.DefectCounts.ContainsKey(defectKey))
                    product.DefectCounts[defectKey] = 0;
                product.DefectCounts[defectKey]++;
            }

            // Generate alert for quality issues
            if (category == QualityCategory.Scrap)
            {
                GenerateAlert("Quality", AlertSeverity.Warning,
                    $"Scrap part produced on {machineId}: {defectType ?? "Unknown defect"}",
                    machineId);
            }
        }

        public void RecordDowntime(string machineId, DowntimeCategory category, string reasonCode,
            string description = null, bool isPlanned = false)
        {
            var activeDowntime = downtimeEvents.LastOrDefault(d =>
                d.MachineId == machineId && !d.EndTime.HasValue);

            if (activeDowntime != null)
            {
                activeDowntime.Category = category;
                activeDowntime.ReasonCode = reasonCode;
                activeDowntime.Description = description;
                activeDowntime.IsPlanned = isPlanned;
            }
            else
            {
                downtimeEvents.Add(new DowntimeEvent
                {
                    EventId = Guid.NewGuid().ToString(),
                    MachineId = machineId,
                    StartTime = DateTime.Now,
                    Category = category,
                    ReasonCode = reasonCode,
                    Description = description,
                    IsPlanned = isPlanned
                });
            }
        }

        public void EndDowntime(string machineId)
        {
            var activeDowntime = downtimeEvents.LastOrDefault(d =>
                d.MachineId == machineId && !d.EndTime.HasValue);

            if (activeDowntime != null)
            {
                activeDowntime.EndTime = DateTime.Now;
            }
        }

        #endregion

        #region OEE Calculation

        public OEEMetrics CalculateOEE(string machineId, DateTime? startTime = null, DateTime? endTime = null)
        {
            if (!machineAnalytics.TryGetValue(machineId, out var analytics))
                return new OEEMetrics { MachineId = machineId };

            var start = startTime ?? GetShiftStart();
            var end = endTime ?? DateTime.Now;

            var oee = new OEEMetrics
            {
                Timestamp = DateTime.Now,
                MachineId = machineId
            };

            // Calculate planned production time
            TimeSpan plannedTime = end - start - TimeSpan.FromMinutes(plannedBreakMinutes);
            oee.PlannedProductionTime = plannedTime;

            // Get events in time range
            var events = productionEvents.Where(e =>
                e.MachineId == machineId &&
                e.Timestamp >= start && e.Timestamp <= end).ToList();

            var downtime = downtimeEvents.Where(d =>
                d.MachineId == machineId &&
                d.StartTime >= start &&
                (d.EndTime ?? DateTime.Now) <= end).ToList();

            // Calculate availability
            TimeSpan totalDowntime = TimeSpan.Zero;
            foreach (var dt in downtime.Where(d => !d.IsPlanned))
            {
                totalDowntime += dt.Duration;
            }
            oee.DownTime = totalDowntime;
            oee.RunTime = plannedTime - totalDowntime;
            oee.Availability = plannedTime.TotalMinutes > 0 ?
                (float)(oee.RunTime.TotalMinutes / plannedTime.TotalMinutes * 100) : 0;

            // Calculate performance
            oee.TotalCount = events.Count;
            oee.GoodCount = events.Count(e => e.Quality == QualityCategory.Good);
            oee.RejectCount = events.Count(e => e.Quality != QualityCategory.Good);

            // Get ideal cycle time from product or use average
            float idealCycleTime = events.Count > 0 ?
                events.Average(e => e.CycleTime) * 0.9f : // Assume ideal is 90% of average
                60f; // Default 60 seconds
            oee.IdealCycleTime = idealCycleTime;

            if (events.Count > 0)
                oee.ActualCycleTime = events.Average(e => e.CycleTime);

            oee.TheoreticalOutput = oee.RunTime.TotalSeconds > 0 ?
                (float)(oee.RunTime.TotalSeconds / idealCycleTime) : 0;
            oee.ActualOutput = oee.TotalCount;

            oee.Performance = oee.TheoreticalOutput > 0 ?
                Mathf.Min((oee.ActualOutput / oee.TheoreticalOutput) * 100f, 100f) : 0;

            // Calculate quality
            oee.Quality = oee.TotalCount > 0 ?
                (float)oee.GoodCount / oee.TotalCount * 100f : 100f;

            // Calculate losses
            oee.AvailabilityLoss = oee.TheoreticalOutput * (100f - oee.Availability) / 100f;
            oee.PerformanceLoss = (oee.TheoreticalOutput - oee.AvailabilityLoss) * (100f - oee.Performance) / 100f;
            oee.QualityLoss = oee.RejectCount;

            // Store in machine analytics
            analytics.CurrentOEE = oee;

            // Add to trend history
            analytics.OEEHistory.Add(new OEETrendPoint
            {
                Timestamp = DateTime.Now,
                OEE = oee.OEE,
                Availability = oee.Availability,
                Performance = oee.Performance,
                Quality = oee.Quality
            });

            // Trim history
            while (analytics.OEEHistory.Count > 24 * trendHistoryDays) // Hourly data for trend days
                analytics.OEEHistory.RemoveAt(0);

            // Check against targets
            CheckOEETargets(oee);

            return oee;
        }

        public OEEMetrics CalculateOverallOEE(DateTime? startTime = null, DateTime? endTime = null)
        {
            var start = startTime ?? GetShiftStart();
            var end = endTime ?? DateTime.Now;

            var overall = new OEEMetrics
            {
                Timestamp = DateTime.Now,
                MachineId = "ALL"
            };

            var machineOEEs = machineAnalytics.Keys.Select(id => CalculateOEE(id, start, end)).ToList();

            if (machineOEEs.Count == 0)
                return overall;

            // Weighted average by run time
            float totalRunTime = (float)machineOEEs.Sum(o => o.RunTime.TotalMinutes);

            if (totalRunTime > 0)
            {
                overall.Availability = machineOEEs.Sum(o => o.Availability * (float)o.RunTime.TotalMinutes) / totalRunTime;
                overall.Performance = machineOEEs.Sum(o => o.Performance * (float)o.RunTime.TotalMinutes) / totalRunTime;
                overall.Quality = machineOEEs.Sum(o => o.Quality * (float)o.RunTime.TotalMinutes) / totalRunTime;
            }

            overall.TotalCount = machineOEEs.Sum(o => o.TotalCount);
            overall.GoodCount = machineOEEs.Sum(o => o.GoodCount);
            overall.RejectCount = machineOEEs.Sum(o => o.RejectCount);
            overall.RunTime = TimeSpan.FromMinutes(totalRunTime);
            overall.DownTime = TimeSpan.FromMinutes(machineOEEs.Sum(o => o.DownTime.TotalMinutes));

            currentOEE = overall;
            OnOEEUpdated?.Invoke(overall);

            return overall;
        }

        private void CheckOEETargets(OEEMetrics oee)
        {
            if (oee.OEE < targetOEE * 0.8f) // Below 80% of target
            {
                GenerateAlert("OEE", AlertSeverity.Critical,
                    $"OEE critically low: {oee.OEE:F1}% (Target: {targetOEE}%)",
                    oee.MachineId, oee.OEE, targetOEE);
            }
            else if (oee.OEE < targetOEE)
            {
                GenerateAlert("OEE", AlertSeverity.Warning,
                    $"OEE below target: {oee.OEE:F1}% (Target: {targetOEE}%)",
                    oee.MachineId, oee.OEE, targetOEE);
            }

            if (oee.Availability < targetAvailability * 0.9f)
            {
                GenerateAlert("Availability", AlertSeverity.Warning,
                    $"Availability issue: {oee.Availability:F1}% (Target: {targetAvailability}%)",
                    oee.MachineId, oee.Availability, targetAvailability);
            }

            if (oee.Quality < targetQuality * 0.95f)
            {
                GenerateAlert("Quality", AlertSeverity.Warning,
                    $"Quality issue: {oee.Quality:F1}% (Target: {targetQuality}%)",
                    oee.MachineId, oee.Quality, targetQuality);
            }
        }

        private DateTime GetShiftStart()
        {
            var now = DateTime.Now;
            var shiftStart = new DateTime(now.Year, now.Month, now.Day, shiftStartHour, 0, 0);

            // Determine which shift we're in
            int hoursSinceShiftStart = (now.Hour - shiftStartHour + 24) % 24;
            int currentShift = hoursSinceShiftStart / shiftDurationHours;

            return shiftStart.AddHours(currentShift * shiftDurationHours);
        }

        #endregion

        #region Reporting

        public ProductionSummary GenerateSummary(string period = "Shift")
        {
            DateTime periodStart, periodEnd;

            switch (period.ToLower())
            {
                case "shift":
                    periodStart = GetShiftStart();
                    periodEnd = periodStart.AddHours(shiftDurationHours);
                    break;
                case "day":
                    periodStart = DateTime.Today;
                    periodEnd = DateTime.Today.AddDays(1);
                    break;
                case "week":
                    periodStart = DateTime.Today.AddDays(-(int)DateTime.Today.DayOfWeek);
                    periodEnd = periodStart.AddDays(7);
                    break;
                case "month":
                    periodStart = new DateTime(DateTime.Now.Year, DateTime.Now.Month, 1);
                    periodEnd = periodStart.AddMonths(1);
                    break;
                default:
                    periodStart = GetShiftStart();
                    periodEnd = DateTime.Now;
                    break;
            }

            var summary = new ProductionSummary
            {
                ReportTime = DateTime.Now,
                Period = period,
                PeriodStart = periodStart,
                PeriodEnd = periodEnd > DateTime.Now ? DateTime.Now : periodEnd
            };

            // Calculate overall OEE
            var oee = CalculateOverallOEE(periodStart, summary.PeriodEnd);
            summary.OverallOEE = oee.OEE;
            summary.TotalParts = oee.TotalCount;
            summary.GoodParts = oee.GoodCount;
            summary.YieldRate = oee.Quality;
            summary.TotalRunTime = oee.RunTime;
            summary.TotalDownTime = oee.DownTime;
            summary.TotalAvailableTime = oee.PlannedProductionTime;
            summary.Utilization = oee.Availability;

            // Top downtime reasons
            var downtimeInPeriod = downtimeEvents.Where(d =>
                d.StartTime >= periodStart && d.StartTime <= summary.PeriodEnd).ToList();

            summary.TopDowntimeReasons = downtimeInPeriod
                .GroupBy(d => d.ReasonCode ?? d.Category.ToString())
                .Select(g => new DowntimeSummary
                {
                    ReasonCode = g.Key,
                    Category = g.First().Category,
                    Occurrences = g.Count(),
                    TotalDuration = TimeSpan.FromTicks(g.Sum(d => d.Duration.Ticks)),
                    PercentOfDowntime = summary.TotalDownTime.TotalMinutes > 0 ?
                        (float)(TimeSpan.FromTicks(g.Sum(d => d.Duration.Ticks)).TotalMinutes / summary.TotalDownTime.TotalMinutes * 100) : 0
                })
                .OrderByDescending(s => s.TotalDuration)
                .Take(5)
                .ToList();

            // Top quality issues
            var qualityInPeriod = qualityEvents.Where(q =>
                q.Timestamp >= periodStart && q.Timestamp <= summary.PeriodEnd).ToList();

            int totalRejects = qualityInPeriod.Count;
            summary.TopQualityIssues = qualityInPeriod
                .GroupBy(q => q.DefectType ?? q.Category.ToString())
                .Select(g => new QualitySummary
                {
                    DefectType = g.Key,
                    Count = g.Count(),
                    PercentOfRejects = totalRejects > 0 ? (float)g.Count() / totalRejects * 100 : 0,
                    TopMachine = g.GroupBy(x => x.MachineId).OrderByDescending(x => x.Count()).First().Key
                })
                .OrderByDescending(s => s.Count)
                .Take(5)
                .ToList();

            // Machine performance
            summary.MachinePerformance = machineAnalytics.Values.Select(m =>
            {
                var machineOEE = CalculateOEE(m.MachineId, periodStart, summary.PeriodEnd);
                return new MachineSummary
                {
                    MachineId = m.MachineId,
                    MachineName = m.MachineName,
                    OEE = machineOEE.OEE,
                    Availability = machineOEE.Availability,
                    Performance = machineOEE.Performance,
                    Quality = machineOEE.Quality,
                    PartsProduced = machineOEE.TotalCount
                };
            })
            .OrderByDescending(m => m.OEE)
            .ToList();

            currentSummary = summary;
            stats.ReportsGenerated++;
            OnProductionSummaryReady?.Invoke(summary);

            return summary;
        }

        #endregion

        #region Trend Analysis

        private IEnumerator TrendAnalysisLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(300f); // Every 5 minutes

                foreach (var machine in machineAnalytics.Values)
                {
                    if (machine.OEEHistory.Count >= 10) // Need enough data
                    {
                        var trend = AnalyzeTrend("OEE", machine.OEEHistory.Select(h => h.OEE).ToList());
                        trend.MetricName = $"{machine.MachineId}_OEE";
                        OnTrendAnalysisComplete?.Invoke(trend);

                        // Alert on declining trends
                        if (trend.TrendDirection == "Declining" && trend.TrendConfidence > 70)
                        {
                            GenerateAlert("Trend", AlertSeverity.Warning,
                                $"OEE declining on {machine.MachineId}: {trend.TrendSlope:F2}% per hour",
                                machine.MachineId);
                        }
                    }
                }
            }
        }

        private TrendAnalysis AnalyzeTrend(string metricName, List<float> values)
        {
            var trend = new TrendAnalysis
            {
                MetricName = metricName,
                AnalysisTime = DateTime.Now,
                HistoricalValues = values,
                CurrentValue = values.LastOrDefault(),
                AverageValue = values.Average()
            };

            if (values.Count < 3)
            {
                trend.TrendDirection = "Insufficient Data";
                return trend;
            }

            // Linear regression
            int n = values.Count;
            float sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;

            for (int i = 0; i < n; i++)
            {
                sumX += i;
                sumY += values[i];
                sumXY += i * values[i];
                sumX2 += i * i;
            }

            trend.TrendSlope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
            float intercept = (sumY - trend.TrendSlope * sumX) / n;

            // Calculate R-squared for confidence
            float meanY = sumY / n;
            float ssTotal = 0, ssResidual = 0;

            for (int i = 0; i < n; i++)
            {
                float predicted = intercept + trend.TrendSlope * i;
                ssTotal += (values[i] - meanY) * (values[i] - meanY);
                ssResidual += (values[i] - predicted) * (values[i] - predicted);
            }

            float rSquared = 1 - (ssResidual / ssTotal);
            trend.TrendConfidence = rSquared * 100f;

            // Determine direction
            if (Mathf.Abs(trend.TrendSlope) < 0.1f)
                trend.TrendDirection = "Stable";
            else if (trend.TrendSlope > 0)
                trend.TrendDirection = "Improving";
            else
                trend.TrendDirection = "Declining";

            // Predict next value
            trend.PredictedNextValue = intercept + trend.TrendSlope * n;

            return trend;
        }

        #endregion

        #region Predictive Analytics

        private IEnumerator PredictiveAnalyticsLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(600f); // Every 10 minutes

                // Predict maintenance needs
                foreach (var machine in machineAnalytics.Values)
                {
                    PredictMaintenanceNeeds(machine);
                }

                // Predict quality issues
                PredictQualityIssues();

                // Predict capacity issues
                PredictCapacityIssues();
            }
        }

        private void PredictMaintenanceNeeds(MachineAnalytics machine)
        {
            // Check for increasing cycle times (potential maintenance need)
            if (machine.CycleTimeHistory.Count >= 20)
            {
                var recentCycleTimes = machine.CycleTimeHistory.Skip(machine.CycleTimeHistory.Count - 20).ToList();
                var trend = AnalyzeTrend("CycleTime", recentCycleTimes);

                if (trend.TrendDirection == "Declining" && trend.TrendSlope < -0.5f) // Getting slower
                {
                    var insight = new PredictiveInsight
                    {
                        InsightId = Guid.NewGuid().ToString(),
                        Category = "Maintenance",
                        Title = $"Potential maintenance needed on {machine.MachineId}",
                        Description = $"Cycle times increasing by {-trend.TrendSlope:F2}s per cycle. May indicate wear or maintenance need.",
                        Confidence = trend.TrendConfidence,
                        ImpactValue = -trend.TrendSlope * 100, // Estimated lost parts per 100 cycles
                        RecommendedAction = "Schedule preventive maintenance inspection",
                        PredictedOccurrence = DateTime.Now.AddHours(24),
                        SupportingData = new Dictionary<string, object>
                        {
                            ["trend_slope"] = trend.TrendSlope,
                            ["current_cycle_time"] = trend.CurrentValue,
                            ["average_cycle_time"] = trend.AverageValue
                        }
                    };

                    OnPredictiveInsight?.Invoke(insight);
                }
            }

            // Check for increasing downtime frequency
            var recentDowntime = machine.DowntimeHistory
                .Where(d => d.StartTime >= DateTime.Now.AddDays(-7))
                .ToList();

            if (recentDowntime.Count >= 3)
            {
                // Calculate MTBF (Mean Time Between Failures)
                var unplannedDowntime = recentDowntime.Where(d => !d.IsPlanned).OrderBy(d => d.StartTime).ToList();
                if (unplannedDowntime.Count >= 2)
                {
                    var intervals = new List<TimeSpan>();
                    for (int i = 1; i < unplannedDowntime.Count; i++)
                    {
                        intervals.Add(unplannedDowntime[i].StartTime - (unplannedDowntime[i - 1].EndTime ?? unplannedDowntime[i - 1].StartTime));
                    }

                    var avgMTBF = TimeSpan.FromTicks((long)intervals.Average(i => i.Ticks));

                    if (avgMTBF.TotalHours < 24) // Less than 24 hours between failures
                    {
                        var insight = new PredictiveInsight
                        {
                            InsightId = Guid.NewGuid().ToString(),
                            Category = "Reliability",
                            Title = $"Reliability concern on {machine.MachineId}",
                            Description = $"Average time between unplanned downtimes is {avgMTBF.TotalHours:F1} hours. Intervention recommended.",
                            Confidence = 80f,
                            ImpactValue = 24f / (float)avgMTBF.TotalHours, // Failures per day
                            RecommendedAction = "Perform root cause analysis and preventive maintenance",
                            PredictedOccurrence = DateTime.Now.Add(avgMTBF)
                        };

                        OnPredictiveInsight?.Invoke(insight);
                    }
                }
            }
        }

        private void PredictQualityIssues()
        {
            // Analyze quality trends by product
            foreach (var product in productAnalytics.Values)
            {
                if (product.TotalProduced < 50) continue;

                float rejectRate = (float)product.Rejects / product.TotalProduced * 100f;

                if (rejectRate > 5f) // More than 5% rejects
                {
                    var topDefect = product.DefectCounts.OrderByDescending(d => d.Value).FirstOrDefault();

                    var insight = new PredictiveInsight
                    {
                        InsightId = Guid.NewGuid().ToString(),
                        Category = "Quality",
                        Title = $"Quality issue with product {product.ProductId}",
                        Description = $"Reject rate at {rejectRate:F1}%. Top defect: {topDefect.Key} ({topDefect.Value} occurrences)",
                        Confidence = 90f,
                        ImpactValue = product.Rejects,
                        RecommendedAction = $"Investigate {topDefect.Key} defect cause. Review process parameters.",
                        PredictedOccurrence = DateTime.Now
                    };

                    OnPredictiveInsight?.Invoke(insight);
                }
            }
        }

        private void PredictCapacityIssues()
        {
            // Check if current production rate will meet targets
            if (currentSummary == null) return;

            float hoursRemaining = (float)(currentSummary.PeriodEnd - DateTime.Now).TotalHours;
            if (hoursRemaining <= 0) return;

            // Estimate parts remaining
            float avgPartsPerHour = currentSummary.TotalParts / (float)(DateTime.Now - currentSummary.PeriodStart).TotalHours;
            float predictedTotal = currentSummary.TotalParts + avgPartsPerHour * hoursRemaining;

            // If we have a target, check against it
            // (Assuming 100 parts/hour target for this example)
            float targetParts = 100f * (float)(currentSummary.PeriodEnd - currentSummary.PeriodStart).TotalHours;

            if (predictedTotal < targetParts * 0.9f)
            {
                var insight = new PredictiveInsight
                {
                    InsightId = Guid.NewGuid().ToString(),
                    Category = "Capacity",
                    Title = "Production target at risk",
                    Description = $"Predicted {predictedTotal:F0} parts vs target {targetParts:F0}. Shortfall: {targetParts - predictedTotal:F0} parts.",
                    Confidence = 75f,
                    ImpactValue = targetParts - predictedTotal,
                    RecommendedAction = "Consider overtime, additional resources, or target adjustment",
                    PredictedOccurrence = currentSummary.PeriodEnd
                };

                OnPredictiveInsight?.Invoke(insight);
            }
        }

        #endregion

        #region Processing Loops

        private IEnumerator RealTimeMetricsLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(realTimeUpdateInterval);

                // Update machine metrics
                foreach (var machine in machineAnalytics.Values)
                {
                    var oee = CalculateOEE(machine.MachineId);
                    var metrics = new MachineMetrics
                    {
                        MachineId = machine.MachineId,
                        CurrentState = machine.CurrentState,
                        CurrentOEE = oee.OEE,
                        PartsProduced = machine.PartCount,
                        CurrentCycleTime = machine.CurrentCycleTime
                    };

                    OnMachineMetricsUpdated?.Invoke(metrics);
                }
            }
        }

        private IEnumerator PeriodicMetricsLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(metricsUpdateInterval);

                // Generate shift summary
                GenerateSummary("Shift");

                // Clean up old events
                CleanupOldData();
            }
        }

        private void CleanupOldData()
        {
            var cutoff = DateTime.Now.AddDays(-trendHistoryDays);

            productionEvents.RemoveAll(e => e.Timestamp < cutoff);
            downtimeEvents.RemoveAll(d => (d.EndTime ?? DateTime.Now) < cutoff);
            qualityEvents.RemoveAll(q => q.Timestamp < cutoff);
        }

        #endregion

        #region Alerts

        private void GenerateAlert(string category, AlertSeverity severity, string message,
            string machineId = null, object currentValue = null, object threshold = null)
        {
            var alert = new AnalyticsAlert
            {
                AlertId = Guid.NewGuid().ToString(),
                Category = category,
                Severity = severity,
                Message = message,
                MachineId = machineId,
                CurrentValue = currentValue,
                Threshold = threshold,
                Timestamp = DateTime.Now
            };

            stats.AlertsGenerated++;
            OnAlertGenerated?.Invoke(alert);

            Debug.Log($"[ProductionAnalytics] ALERT [{severity}]: {message}");
        }

        #endregion

        #region Public API

        public class MachineMetrics
        {
            public string MachineId { get; set; }
            public MachineState CurrentState { get; set; }
            public float CurrentOEE { get; set; }
            public int PartsProduced { get; set; }
            public float CurrentCycleTime { get; set; }
        }

        public MachineAnalytics GetMachineAnalytics(string machineId)
        {
            return machineAnalytics.TryGetValue(machineId, out var analytics) ? analytics : null;
        }

        public List<MachineAnalytics> GetAllMachineAnalytics()
        {
            return machineAnalytics.Values.ToList();
        }

        public ProductAnalytics GetProductAnalytics(string productId)
        {
            return productAnalytics.TryGetValue(productId, out var analytics) ? analytics : null;
        }

        public List<ProductAnalytics> GetAllProductAnalytics()
        {
            return productAnalytics.Values.ToList();
        }

        public OEEMetrics GetCurrentOEE()
        {
            return currentOEE;
        }

        public ProductionSummary GetCurrentSummary()
        {
            return currentSummary;
        }

        public List<DowntimeEvent> GetDowntimeHistory(string machineId = null, int lastNDays = 7)
        {
            var cutoff = DateTime.Now.AddDays(-lastNDays);
            var query = downtimeEvents.Where(d => d.StartTime >= cutoff);

            if (!string.IsNullOrEmpty(machineId))
                query = query.Where(d => d.MachineId == machineId);

            return query.OrderByDescending(d => d.StartTime).ToList();
        }

        public List<QualityEvent> GetQualityHistory(string machineId = null, string productId = null, int lastNDays = 7)
        {
            var cutoff = DateTime.Now.AddDays(-lastNDays);
            var query = qualityEvents.Where(q => q.Timestamp >= cutoff);

            if (!string.IsNullOrEmpty(machineId))
                query = query.Where(q => q.MachineId == machineId);

            if (!string.IsNullOrEmpty(productId))
                query = query.Where(q => q.ProductId == productId);

            return query.OrderByDescending(q => q.Timestamp).ToList();
        }

        public AnalyticsStats GetStats()
        {
            return stats;
        }

        public void SetTargetOEE(float target)
        {
            targetOEE = Mathf.Clamp(target, 0, 100);
        }

        public void SetTargets(float availability, float performance, float quality)
        {
            targetAvailability = Mathf.Clamp(availability, 0, 100);
            targetPerformance = Mathf.Clamp(performance, 0, 100);
            targetQuality = Mathf.Clamp(quality, 0, 100);
        }

        #endregion
    }
}
