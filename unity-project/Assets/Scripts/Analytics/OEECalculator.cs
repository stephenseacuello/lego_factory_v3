using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Analytics
{
    /// <summary>
    /// Calculates Overall Equipment Effectiveness (OEE) metrics.
    /// OEE = Availability × Performance × Quality
    /// Part of Feature 3.4: OEE Breakdown (HIGH PRIORITY - Phase 3)
    /// </summary>
    public class OEECalculator : MonoBehaviour
    {
        [Header("OEE Configuration")]
        [SerializeField] private string machineId = "CNC-001";
        [SerializeField] private float updateInterval = 60f; // Update every minute
        [SerializeField] private bool enableRealTimeTracking = true;

        [Header("Shift Configuration")]
        [SerializeField] private float plannedProductionTime = 28800f; // 8 hours in seconds
        [SerializeField] private float idealCycleTime = 120f; // seconds per part
        [SerializeField] private int targetParts = 240; // Parts per shift

        [Header("Thresholds")]
        [SerializeField] private float goodOEEThreshold = 0.85f; // 85%
        [SerializeField] private float acceptableOEEThreshold = 0.65f; // 65%

        // OEE Components
        private float availability = 0f;
        private float performance = 0f;
        private float quality = 0f;
        private float oee = 0f;

        // Tracking data
        private float totalTime = 0f; // Planned production time
        private float runTime = 0f; // Actual operating time
        private float downtime = 0f; // Unplanned stops
        private int totalParts = 0; // Total parts produced
        private int goodParts = 0; // Quality parts
        private int rejectedParts = 0; // Rejected parts

        // Timing
        private float updateTimer = 0f;
        private DateTime shiftStartTime;
        private bool shiftActive = false;

        // Loss tracking
        private Dictionary<string, float> availabilityLosses = new Dictionary<string, float>();
        private Dictionary<string, float> performanceLosses = new Dictionary<string, float>();
        private Dictionary<string, int> qualityLosses = new Dictionary<string, int>();

        // Events
        public event Action<OEEMetrics> OnOEEUpdated;
        public event Action<OEEAlert> OnOEEAlert;

        // Statistics
        private int totalCalculations = 0;
        private float avgOEE = 0f;
        private float peakOEE = 0f;
        private float lowestOEE = 1f;

        void Start()
        {
            InitializeLossCategories();
        }

        void Update()
        {
            if (!enableRealTimeTracking || !shiftActive) return;

            updateTimer += Time.deltaTime;
            if (updateTimer >= updateInterval)
            {
                CalculateOEE();
                updateTimer = 0f;
            }
        }

        /// <summary>
        /// Initialize loss category tracking
        /// </summary>
        private void InitializeLossCategories()
        {
            // Availability losses
            availabilityLosses["breakdowns"] = 0f;
            availabilityLosses["setup_changeover"] = 0f;
            availabilityLosses["tool_changes"] = 0f;
            availabilityLosses["planned_maintenance"] = 0f;

            // Performance losses
            performanceLosses["reduced_speed"] = 0f;
            performanceLosses["minor_stops"] = 0f;
            performanceLosses["startup_slowdown"] = 0f;

            // Quality losses
            qualityLosses["scrap"] = 0;
            qualityLosses["rework"] = 0;
            qualityLosses["startup_rejects"] = 0;
        }

        /// <summary>
        /// Start a new shift
        /// </summary>
        public void StartShift(float plannedTime, float cycleTime, int targetCount)
        {
            shiftStartTime = DateTime.UtcNow;
            shiftActive = true;

            plannedProductionTime = plannedTime;
            idealCycleTime = cycleTime;
            targetParts = targetCount;

            // Reset metrics
            totalTime = plannedTime;
            runTime = 0f;
            downtime = 0f;
            totalParts = 0;
            goodParts = 0;
            rejectedParts = 0;

            // Reset losses
            foreach (var key in availabilityLosses.Keys)
                availabilityLosses[key] = 0f;
            foreach (var key in performanceLosses.Keys)
                performanceLosses[key] = 0f;
            foreach (var key in qualityLosses.Keys)
                qualityLosses[key] = 0;

            Debug.Log($"[OEE] Shift started: {plannedTime}s, target: {targetCount} parts");
        }

        /// <summary>
        /// End current shift
        /// </summary>
        public void EndShift()
        {
            if (!shiftActive) return;

            CalculateOEE();
            shiftActive = false;

            Debug.Log($"[OEE] Shift ended. Final OEE: {oee:P1}");
        }

        /// <summary>
        /// Calculate OEE metrics
        /// </summary>
        public void CalculateOEE()
        {
            if (!shiftActive || totalTime == 0) return;

            // Calculate Availability
            // Availability = Run Time / Planned Production Time
            availability = runTime / totalTime;
            availability = Mathf.Clamp01(availability);

            // Calculate Performance
            // Performance = (Ideal Cycle Time × Total Parts) / Run Time
            if (runTime > 0)
            {
                float idealTime = idealCycleTime * totalParts;
                performance = idealTime / runTime;
                performance = Mathf.Clamp01(performance);
            }
            else
            {
                performance = 0f;
            }

            // Calculate Quality
            // Quality = Good Parts / Total Parts
            if (totalParts > 0)
            {
                quality = (float)goodParts / totalParts;
                quality = Mathf.Clamp01(quality);
            }
            else
            {
                quality = 0f;
            }

            // Calculate OEE
            // OEE = Availability × Performance × Quality
            oee = availability * performance * quality;

            // Update statistics
            totalCalculations++;
            avgOEE = ((avgOEE * (totalCalculations - 1)) + oee) / totalCalculations;
            peakOEE = Mathf.Max(peakOEE, oee);
            lowestOEE = Mathf.Min(lowestOEE, oee);

            // Create metrics record
            var metrics = new OEEMetrics
            {
                MachineId = machineId,
                Timestamp = DateTime.UtcNow,
                OEE = oee,
                Availability = availability,
                Performance = performance,
                Quality = quality,
                TotalParts = totalParts,
                GoodParts = goodParts,
                RejectedParts = rejectedParts,
                RunTime = runTime,
                Downtime = downtime,
                PlannedProductionTime = totalTime
            };

            OnOEEUpdated?.Invoke(metrics);

            // Check for alerts
            CheckOEEAlerts(metrics);

            Debug.Log($"[OEE] OEE: {oee:P1} (A: {availability:P1}, P: {performance:P1}, Q: {quality:P1})");
        }

        /// <summary>
        /// Record machine running time
        /// </summary>
        public void RecordRunTime(float seconds)
        {
            runTime += seconds;
        }

        /// <summary>
        /// Record downtime event
        /// </summary>
        public void RecordDowntime(float seconds, string category)
        {
            downtime += seconds;

            if (availabilityLosses.ContainsKey(category))
            {
                availabilityLosses[category] += seconds;
            }
        }

        /// <summary>
        /// Record part production
        /// </summary>
        public void RecordPart(bool isGood)
        {
            totalParts++;

            if (isGood)
            {
                goodParts++;
            }
            else
            {
                rejectedParts++;
            }
        }

        /// <summary>
        /// Record quality loss
        /// </summary>
        public void RecordQualityLoss(int count, string category)
        {
            if (qualityLosses.ContainsKey(category))
            {
                qualityLosses[category] += count;
            }
        }

        /// <summary>
        /// Record performance loss
        /// </summary>
        public void RecordPerformanceLoss(float seconds, string category)
        {
            if (performanceLosses.ContainsKey(category))
            {
                performanceLosses[category] += seconds;
            }
        }

        /// <summary>
        /// Check for OEE alerts
        /// </summary>
        private void CheckOEEAlerts(OEEMetrics metrics)
        {
            if (metrics.OEE < acceptableOEEThreshold)
            {
                OnOEEAlert?.Invoke(new OEEAlert
                {
                    AlertType = OEEAlertType.LowOEE,
                    Severity = OEEAlertSeverity.Critical,
                    Message = $"Critical: OEE below acceptable threshold ({metrics.OEE:P1} < {acceptableOEEThreshold:P0})",
                    OEE = metrics.OEE,
                    Timestamp = DateTime.UtcNow
                });
            }
            else if (metrics.OEE < goodOEEThreshold)
            {
                OnOEEAlert?.Invoke(new OEEAlert
                {
                    AlertType = OEEAlertType.LowOEE,
                    Severity = OEEAlertSeverity.Warning,
                    Message = $"Warning: OEE below target ({metrics.OEE:P1} < {goodOEEThreshold:P0})",
                    OEE = metrics.OEE,
                    Timestamp = DateTime.UtcNow
                });
            }

            // Check individual components
            if (metrics.Availability < 0.90f)
            {
                OnOEEAlert?.Invoke(new OEEAlert
                {
                    AlertType = OEEAlertType.LowAvailability,
                    Severity = OEEAlertSeverity.Warning,
                    Message = $"Low availability: {metrics.Availability:P1}",
                    OEE = metrics.Availability,
                    Timestamp = DateTime.UtcNow
                });
            }

            if (metrics.Performance < 0.90f)
            {
                OnOEEAlert?.Invoke(new OEEAlert
                {
                    AlertType = OEEAlertType.LowPerformance,
                    Severity = OEEAlertSeverity.Warning,
                    Message = $"Low performance: {metrics.Performance:P1}",
                    OEE = metrics.Performance,
                    Timestamp = DateTime.UtcNow
                });
            }

            if (metrics.Quality < 0.95f)
            {
                OnOEEAlert?.Invoke(new OEEAlert
                {
                    AlertType = OEEAlertType.LowQuality,
                    Severity = OEEAlertSeverity.Warning,
                    Message = $"Low quality: {metrics.Quality:P1}",
                    OEE = metrics.Quality,
                    Timestamp = DateTime.UtcNow
                });
            }
        }

        /// <summary>
        /// Get OEE breakdown by loss category
        /// </summary>
        public OEEBreakdown GetBreakdown()
        {
            return new OEEBreakdown
            {
                OEE = oee,
                Availability = availability,
                Performance = performance,
                Quality = quality,
                AvailabilityLosses = new Dictionary<string, float>(availabilityLosses),
                PerformanceLosses = new Dictionary<string, float>(performanceLosses),
                QualityLosses = new Dictionary<string, int>(qualityLosses),
                TotalDowntime = downtime,
                TotalRejects = rejectedParts
            };
        }

        /// <summary>
        /// Get improvement opportunities
        /// </summary>
        public List<string> GetImprovementOpportunities()
        {
            var opportunities = new List<string>();

            // Analyze availability losses
            float maxAvailabilityLoss = 0f;
            string maxAvailabilityCategory = "";
            foreach (var loss in availabilityLosses)
            {
                if (loss.Value > maxAvailabilityLoss)
                {
                    maxAvailabilityLoss = loss.Value;
                    maxAvailabilityCategory = loss.Key;
                }
            }

            if (maxAvailabilityLoss > 0)
            {
                opportunities.Add($"Reduce {maxAvailabilityCategory} (current: {maxAvailabilityLoss / 60:F1} min)");
            }

            // Analyze performance losses
            if (performance < 0.90f)
            {
                opportunities.Add($"Improve cycle time efficiency (current: {performance:P1})");
            }

            // Analyze quality losses
            if (quality < 0.95f && totalParts > 0)
            {
                float rejectRate = (float)rejectedParts / totalParts;
                opportunities.Add($"Reduce defect rate (current: {rejectRate:P1})");
            }

            if (opportunities.Count == 0)
            {
                opportunities.Add("OEE is at world-class level (>85%)");
            }

            return opportunities;
        }

        /// <summary>
        /// Get OEE statistics
        /// </summary>
        public OEEStatistics GetStatistics()
        {
            return new OEEStatistics
            {
                CurrentOEE = oee,
                AverageOEE = avgOEE,
                PeakOEE = peakOEE,
                LowestOEE = lowestOEE,
                TotalCalculations = totalCalculations,
                ShiftActive = shiftActive,
                TotalParts = totalParts,
                GoodParts = goodParts,
                RejectedParts = rejectedParts
            };
        }

        #region Public Properties

        public float CurrentOEE => oee;
        public float Availability => availability;
        public float Performance => performance;
        public float Quality => quality;
        public bool IsShiftActive => shiftActive;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// OEE metrics record
    /// </summary>
    [Serializable]
    public struct OEEMetrics
    {
        public string MachineId;
        public DateTime Timestamp;
        public float OEE;
        public float Availability;
        public float Performance;
        public float Quality;
        public int TotalParts;
        public int GoodParts;
        public int RejectedParts;
        public float RunTime;
        public float Downtime;
        public float PlannedProductionTime;
    }

    /// <summary>
    /// OEE breakdown by loss categories
    /// </summary>
    [Serializable]
    public struct OEEBreakdown
    {
        public float OEE;
        public float Availability;
        public float Performance;
        public float Quality;
        public Dictionary<string, float> AvailabilityLosses;
        public Dictionary<string, float> PerformanceLosses;
        public Dictionary<string, int> QualityLosses;
        public float TotalDowntime;
        public int TotalRejects;
    }

    /// <summary>
    /// OEE alert
    /// </summary>
    [Serializable]
    public struct OEEAlert
    {
        public OEEAlertType AlertType;
        public OEEAlertSeverity Severity;
        public string Message;
        public float OEE;
        public DateTime Timestamp;
    }

    /// <summary>
    /// OEE statistics
    /// </summary>
    [Serializable]
    public struct OEEStatistics
    {
        public float CurrentOEE;
        public float AverageOEE;
        public float PeakOEE;
        public float LowestOEE;
        public int TotalCalculations;
        public bool ShiftActive;
        public int TotalParts;
        public int GoodParts;
        public int RejectedParts;
    }

    /// <summary>
    /// OEE alert types
    /// </summary>
    public enum OEEAlertType
    {
        LowOEE,
        LowAvailability,
        LowPerformance,
        LowQuality
    }

    /// <summary>
    /// OEE alert severity
    /// </summary>
    public enum OEEAlertSeverity
    {
        Info,
        Warning,
        Critical
    }

    #endregion
}
