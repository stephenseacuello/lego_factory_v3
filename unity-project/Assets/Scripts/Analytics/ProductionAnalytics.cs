using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCScada.Analytics
{
    /// <summary>
    /// Production analytics system for tracking OEE, cycle times, and production KPIs.
    /// Provides real-time metrics and historical analysis for manufacturing operations.
    /// </summary>
    public class ProductionAnalytics : MonoBehaviour
    {
        [Header("Settings")]
        [SerializeField] private float updateInterval = 5f;
        [SerializeField] private int historyRetentionHours = 24;

        [Header("Shift Configuration")]
        [SerializeField] private float plannedProductionHoursPerShift = 8f;
        [SerializeField] private float plannedBreakMinutes = 30f;
        [SerializeField] private int targetPartsPerHour = 10;

        [Header("Current OEE Metrics")]
        [SerializeField] private float availability = 100f;
        [SerializeField] private float performance = 100f;
        [SerializeField] private float quality = 100f;
        [SerializeField] private float oee = 100f;

        [Header("Production Counts")]
        [SerializeField] private int totalPartsProduced;
        [SerializeField] private int goodParts;
        [SerializeField] private int scrapParts;
        [SerializeField] private int currentShiftParts;

        [Header("Time Tracking")]
        [SerializeField] private float runTimeMinutes;
        [SerializeField] private float downTimeMinutes;
        [SerializeField] private float idleTimeMinutes;
        [SerializeField] private float averageCycleTimeSeconds;

        // Data collections
        private List<ProductionEvent> productionEvents = new List<ProductionEvent>();
        private List<CycleTimeRecord> cycleTimeHistory = new List<CycleTimeRecord>();
        private List<DowntimeEvent> downtimeEvents = new List<DowntimeEvent>();
        private Dictionary<string, MachineMetrics> machineMetrics = new Dictionary<string, MachineMetrics>();

        // Shift tracking
        private DateTime shiftStartTime;
        private DateTime lastPartProducedTime;
        private bool isInProduction;
        private Coroutine updateCoroutine;

        // Events
        public event Action<OEEMetrics> OnOEEUpdated;
        public event Action<ProductionEvent> OnPartProduced;
        public event Action<DowntimeEvent> OnDowntimeStarted;
        public event Action<DowntimeEvent> OnDowntimeEnded;
        public event Action<ProductionSummary> OnShiftSummary;

        // Singleton
        public static ProductionAnalytics Instance { get; private set; }

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
                return;
            }

            shiftStartTime = DateTime.Now;
            InitializeMachineMetrics();
        }

        private void Start()
        {
            updateCoroutine = StartCoroutine(PeriodicUpdate());
        }

        private void OnDestroy()
        {
            if (updateCoroutine != null)
            {
                StopCoroutine(updateCoroutine);
            }
        }

        private void InitializeMachineMetrics()
        {
            // Initialize metrics for known machines
            machineMetrics["BantamCNC"] = new MachineMetrics { machineId = "BantamCNC", machineName = "Bantam Desktop Explorer" };
            machineMetrics["xArm"] = new MachineMetrics { machineId = "xArm", machineName = "xArm Lite 6" };
            machineMetrics["Niryo"] = new MachineMetrics { machineId = "Niryo", machineName = "Niryo Ned2" };
        }

        private IEnumerator PeriodicUpdate()
        {
            while (true)
            {
                yield return new WaitForSeconds(updateInterval);
                CalculateOEE();
                CleanupOldData();
            }
        }

        // =========================================================================
        // Production Event Recording
        // =========================================================================

        /// <summary>
        /// Record a part being produced
        /// </summary>
        public void RecordPartProduced(string machineId, bool isGood = true, float cycleTimeSeconds = 0)
        {
            var productionEvent = new ProductionEvent
            {
                eventId = $"PROD_{DateTime.Now.Ticks}",
                machineId = machineId,
                timestamp = DateTime.Now,
                eventType = ProductionEventType.PartComplete,
                partQuality = isGood ? PartQuality.Good : PartQuality.Scrap,
                cycleTimeSeconds = cycleTimeSeconds
            };

            productionEvents.Add(productionEvent);
            totalPartsProduced++;
            currentShiftParts++;

            if (isGood)
            {
                goodParts++;
            }
            else
            {
                scrapParts++;
            }

            // Record cycle time
            if (cycleTimeSeconds > 0)
            {
                cycleTimeHistory.Add(new CycleTimeRecord
                {
                    machineId = machineId,
                    timestamp = DateTime.Now,
                    cycleTimeSeconds = cycleTimeSeconds
                });

                UpdateAverageCycleTime();
            }

            // Update machine metrics
            if (machineMetrics.TryGetValue(machineId, out MachineMetrics metrics))
            {
                metrics.partsProduced++;
                if (isGood) metrics.goodParts++;
                else metrics.scrapParts++;

                if (cycleTimeSeconds > 0)
                {
                    metrics.totalCycleTime += cycleTimeSeconds;
                    metrics.cycleCount++;
                }
            }

            lastPartProducedTime = DateTime.Now;
            OnPartProduced?.Invoke(productionEvent);

            Debug.Log($"[Analytics] Part produced on {machineId}: {(isGood ? "GOOD" : "SCRAP")} ({cycleTimeSeconds:F1}s)");
        }

        /// <summary>
        /// Record start of machine operation
        /// </summary>
        public void RecordCycleStart(string machineId)
        {
            if (machineMetrics.TryGetValue(machineId, out MachineMetrics metrics))
            {
                metrics.lastCycleStartTime = DateTime.Now;
                metrics.isRunning = true;
            }

            isInProduction = true;
        }

        /// <summary>
        /// Record end of machine operation and return cycle time
        /// </summary>
        public float RecordCycleEnd(string machineId, bool partProduced = true, bool isGood = true)
        {
            float cycleTime = 0;

            if (machineMetrics.TryGetValue(machineId, out MachineMetrics metrics))
            {
                if (metrics.lastCycleStartTime != default)
                {
                    cycleTime = (float)(DateTime.Now - metrics.lastCycleStartTime).TotalSeconds;
                }

                metrics.isRunning = false;
            }

            if (partProduced)
            {
                RecordPartProduced(machineId, isGood, cycleTime);
            }

            return cycleTime;
        }

        // =========================================================================
        // Downtime Tracking
        // =========================================================================

        /// <summary>
        /// Start recording a downtime event
        /// </summary>
        public DowntimeEvent StartDowntime(string machineId, DowntimeReason reason, string description = "")
        {
            var downtimeEvent = new DowntimeEvent
            {
                eventId = $"DT_{DateTime.Now.Ticks}",
                machineId = machineId,
                startTime = DateTime.Now,
                reason = reason,
                description = description,
                isOngoing = true
            };

            downtimeEvents.Add(downtimeEvent);

            if (machineMetrics.TryGetValue(machineId, out MachineMetrics metrics))
            {
                metrics.isRunning = false;
                metrics.currentDowntimeEvent = downtimeEvent;
            }

            OnDowntimeStarted?.Invoke(downtimeEvent);

            Debug.Log($"[Analytics] Downtime started on {machineId}: {reason}");

            return downtimeEvent;
        }

        /// <summary>
        /// End a downtime event
        /// </summary>
        public void EndDowntime(string eventId)
        {
            var downtimeEvent = downtimeEvents.Find(d => d.eventId == eventId && d.isOngoing);

            if (downtimeEvent != null)
            {
                downtimeEvent.endTime = DateTime.Now;
                downtimeEvent.isOngoing = false;

                if (machineMetrics.TryGetValue(downtimeEvent.machineId, out MachineMetrics metrics))
                {
                    metrics.totalDowntimeMinutes += (float)downtimeEvent.Duration.TotalMinutes;
                    metrics.currentDowntimeEvent = null;
                }

                OnDowntimeEnded?.Invoke(downtimeEvent);

                Debug.Log($"[Analytics] Downtime ended: {downtimeEvent.Duration.TotalMinutes:F1} minutes");
            }
        }

        /// <summary>
        /// End all ongoing downtimes for a machine
        /// </summary>
        public void EndAllDowntimes(string machineId)
        {
            var ongoingDowntimes = downtimeEvents.FindAll(d => d.machineId == machineId && d.isOngoing);

            foreach (var dt in ongoingDowntimes)
            {
                EndDowntime(dt.eventId);
            }
        }

        // =========================================================================
        // OEE Calculation
        // =========================================================================

        private void CalculateOEE()
        {
            TimeSpan shiftDuration = DateTime.Now - shiftStartTime;
            float plannedProductionMinutes = (plannedProductionHoursPerShift * 60f) - plannedBreakMinutes;
            float actualShiftMinutes = (float)shiftDuration.TotalMinutes;

            // Use smaller of actual or planned time
            float effectiveMinutes = Mathf.Min(actualShiftMinutes, plannedProductionMinutes);

            // Calculate run time (total time - downtime)
            float totalDowntime = downtimeEvents
                .Where(d => d.startTime >= shiftStartTime)
                .Sum(d => (float)d.Duration.TotalMinutes);

            runTimeMinutes = effectiveMinutes - totalDowntime;
            downTimeMinutes = totalDowntime;

            // Availability = Run Time / Planned Production Time
            availability = effectiveMinutes > 0 ? (runTimeMinutes / effectiveMinutes) * 100f : 0;
            availability = Mathf.Clamp(availability, 0, 100);

            // Performance = (Ideal Cycle Time × Total Count) / Run Time
            float targetParts = (runTimeMinutes / 60f) * targetPartsPerHour;
            performance = targetParts > 0 ? (currentShiftParts / targetParts) * 100f : 0;
            performance = Mathf.Clamp(performance, 0, 100);

            // Quality = Good Count / Total Count
            quality = currentShiftParts > 0 ? ((float)goodParts / currentShiftParts) * 100f : 100;
            quality = Mathf.Clamp(quality, 0, 100);

            // OEE = Availability × Performance × Quality
            oee = (availability / 100f) * (performance / 100f) * (quality / 100f) * 100f;

            var metrics = new OEEMetrics
            {
                availability = availability,
                performance = performance,
                quality = quality,
                oee = oee,
                timestamp = DateTime.Now
            };

            OnOEEUpdated?.Invoke(metrics);
        }

        private void UpdateAverageCycleTime()
        {
            if (cycleTimeHistory.Count == 0)
            {
                averageCycleTimeSeconds = 0;
                return;
            }

            // Calculate average from last hour
            var recentCycles = cycleTimeHistory
                .Where(c => c.timestamp > DateTime.Now.AddHours(-1))
                .ToList();

            if (recentCycles.Count > 0)
            {
                averageCycleTimeSeconds = recentCycles.Average(c => c.cycleTimeSeconds);
            }
        }

        private void CleanupOldData()
        {
            DateTime cutoff = DateTime.Now.AddHours(-historyRetentionHours);

            productionEvents.RemoveAll(e => e.timestamp < cutoff);
            cycleTimeHistory.RemoveAll(c => c.timestamp < cutoff);
            downtimeEvents.RemoveAll(d => d.endTime < cutoff && !d.isOngoing);
        }

        // =========================================================================
        // Shift Management
        // =========================================================================

        /// <summary>
        /// Start a new shift
        /// </summary>
        public ProductionSummary StartNewShift()
        {
            // Generate summary for previous shift
            var summary = GetShiftSummary();

            // Reset counters
            currentShiftParts = 0;
            goodParts = 0;
            scrapParts = 0;
            runTimeMinutes = 0;
            downTimeMinutes = 0;
            shiftStartTime = DateTime.Now;

            // Reset machine metrics
            foreach (var metrics in machineMetrics.Values)
            {
                metrics.ResetShiftData();
            }

            Debug.Log("[Analytics] New shift started");

            OnShiftSummary?.Invoke(summary);

            return summary;
        }

        /// <summary>
        /// Get summary for current shift
        /// </summary>
        public ProductionSummary GetShiftSummary()
        {
            CalculateOEE();

            var summary = new ProductionSummary
            {
                shiftStartTime = shiftStartTime,
                shiftEndTime = DateTime.Now,
                totalPartsProduced = currentShiftParts,
                goodParts = goodParts,
                scrapParts = scrapParts,
                oee = oee,
                availability = availability,
                performance = performance,
                quality = quality,
                runTimeMinutes = runTimeMinutes,
                downTimeMinutes = downTimeMinutes,
                averageCycleTimeSeconds = averageCycleTimeSeconds,
                downtimeBreakdown = GetDowntimeBreakdown(),
                machineMetrics = new List<MachineMetrics>(machineMetrics.Values)
            };

            return summary;
        }

        private Dictionary<DowntimeReason, float> GetDowntimeBreakdown()
        {
            var breakdown = new Dictionary<DowntimeReason, float>();
            var shiftDowntimes = downtimeEvents.Where(d => d.startTime >= shiftStartTime);

            foreach (DowntimeReason reason in Enum.GetValues(typeof(DowntimeReason)))
            {
                float minutes = shiftDowntimes
                    .Where(d => d.reason == reason)
                    .Sum(d => (float)d.Duration.TotalMinutes);

                if (minutes > 0)
                {
                    breakdown[reason] = minutes;
                }
            }

            return breakdown;
        }

        // =========================================================================
        // Query Methods
        // =========================================================================

        /// <summary>
        /// Get current OEE metrics
        /// </summary>
        public OEEMetrics GetCurrentOEE()
        {
            return new OEEMetrics
            {
                availability = availability,
                performance = performance,
                quality = quality,
                oee = oee,
                timestamp = DateTime.Now
            };
        }

        /// <summary>
        /// Get metrics for a specific machine
        /// </summary>
        public MachineMetrics GetMachineMetrics(string machineId)
        {
            return machineMetrics.TryGetValue(machineId, out MachineMetrics metrics) ? metrics : null;
        }

        /// <summary>
        /// Get all machine metrics
        /// </summary>
        public List<MachineMetrics> GetAllMachineMetrics()
        {
            return new List<MachineMetrics>(machineMetrics.Values);
        }

        /// <summary>
        /// Get production events within a time range
        /// </summary>
        public List<ProductionEvent> GetProductionEvents(DateTime start, DateTime end)
        {
            return productionEvents
                .Where(e => e.timestamp >= start && e.timestamp <= end)
                .ToList();
        }

        /// <summary>
        /// Get cycle time statistics
        /// </summary>
        public CycleTimeStats GetCycleTimeStats(string machineId = null)
        {
            var cycles = cycleTimeHistory
                .Where(c => string.IsNullOrEmpty(machineId) || c.machineId == machineId)
                .ToList();

            if (cycles.Count == 0)
            {
                return new CycleTimeStats();
            }

            var times = cycles.Select(c => c.cycleTimeSeconds).ToList();

            return new CycleTimeStats
            {
                count = times.Count,
                average = times.Average(),
                min = times.Min(),
                max = times.Max(),
                standardDeviation = CalculateStdDev(times)
            };
        }

        private float CalculateStdDev(List<float> values)
        {
            if (values.Count < 2) return 0;

            float avg = values.Average();
            float sumSquares = values.Sum(v => (v - avg) * (v - avg));
            return Mathf.Sqrt(sumSquares / (values.Count - 1));
        }

        /// <summary>
        /// Get parts per hour rate
        /// </summary>
        public float GetPartsPerHour(string machineId = null)
        {
            TimeSpan shiftDuration = DateTime.Now - shiftStartTime;
            float hours = (float)shiftDuration.TotalHours;

            if (hours < 0.1f) return 0;

            if (string.IsNullOrEmpty(machineId))
            {
                return currentShiftParts / hours;
            }

            if (machineMetrics.TryGetValue(machineId, out MachineMetrics metrics))
            {
                return metrics.partsProduced / hours;
            }

            return 0;
        }

        // Properties
        public float OEE => oee;
        public float Availability => availability;
        public float Performance => performance;
        public float Quality => quality;
        public int TotalPartsProduced => totalPartsProduced;
        public int GoodParts => goodParts;
        public int ScrapParts => scrapParts;
        public float AverageCycleTime => averageCycleTimeSeconds;
        public float RunTimeMinutes => runTimeMinutes;
        public float DownTimeMinutes => downTimeMinutes;
        public bool IsInProduction => isInProduction;
    }

    // =========================================================================
    // Data Types
    // =========================================================================

    public enum ProductionEventType
    {
        PartComplete,
        PartStarted,
        PartRejected,
        SetupComplete,
        ToolChange
    }

    public enum PartQuality
    {
        Good,
        Rework,
        Scrap
    }

    public enum DowntimeReason
    {
        PlannedMaintenance,
        UnplannedBreakdown,
        Setup,
        ToolChange,
        MaterialShortage,
        OperatorAbsence,
        QualityHold,
        NoOrders,
        Other
    }

    [Serializable]
    public class ProductionEvent
    {
        public string eventId;
        public string machineId;
        public DateTime timestamp;
        public ProductionEventType eventType;
        public PartQuality partQuality;
        public float cycleTimeSeconds;
        public string partNumber;
        public string workOrderId;
    }

    [Serializable]
    public class CycleTimeRecord
    {
        public string machineId;
        public DateTime timestamp;
        public float cycleTimeSeconds;
    }

    [Serializable]
    public class DowntimeEvent
    {
        public string eventId;
        public string machineId;
        public DateTime startTime;
        public DateTime endTime;
        public DowntimeReason reason;
        public string description;
        public bool isOngoing;

        public TimeSpan Duration => isOngoing ? DateTime.Now - startTime : endTime - startTime;
    }

    [Serializable]
    public class OEEMetrics
    {
        public float availability;
        public float performance;
        public float quality;
        public float oee;
        public DateTime timestamp;
    }

    [Serializable]
    public class MachineMetrics
    {
        public string machineId;
        public string machineName;
        public int partsProduced;
        public int goodParts;
        public int scrapParts;
        public float totalCycleTime;
        public int cycleCount;
        public float totalDowntimeMinutes;
        public bool isRunning;
        public DateTime lastCycleStartTime;
        public DowntimeEvent currentDowntimeEvent;

        public float AverageCycleTime => cycleCount > 0 ? totalCycleTime / cycleCount : 0;
        public float ScrapRate => partsProduced > 0 ? (float)scrapParts / partsProduced * 100f : 0;

        public void ResetShiftData()
        {
            partsProduced = 0;
            goodParts = 0;
            scrapParts = 0;
            totalCycleTime = 0;
            cycleCount = 0;
            totalDowntimeMinutes = 0;
        }
    }

    [Serializable]
    public class ProductionSummary
    {
        public DateTime shiftStartTime;
        public DateTime shiftEndTime;
        public int totalPartsProduced;
        public int goodParts;
        public int scrapParts;
        public float oee;
        public float availability;
        public float performance;
        public float quality;
        public float runTimeMinutes;
        public float downTimeMinutes;
        public float averageCycleTimeSeconds;
        public Dictionary<DowntimeReason, float> downtimeBreakdown;
        public List<MachineMetrics> machineMetrics;

        public TimeSpan ShiftDuration => shiftEndTime - shiftStartTime;
        public float ScrapRate => totalPartsProduced > 0 ? (float)scrapParts / totalPartsProduced * 100f : 0;
    }

    [Serializable]
    public class CycleTimeStats
    {
        public int count;
        public float average;
        public float min;
        public float max;
        public float standardDeviation;
    }
}
