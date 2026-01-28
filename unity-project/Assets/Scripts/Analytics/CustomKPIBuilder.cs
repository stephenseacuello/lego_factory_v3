using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCScada.Analytics
{
    /// <summary>
    /// Custom KPI Builder - User-defined Key Performance Indicators.
    /// Part of Feature 4.5: Custom KPI Builder (Phase 4)
    ///
    /// Provides:
    /// - Dynamic KPI definition and formula builder
    /// - Multi-source data aggregation
    /// - Threshold-based alerting
    /// - Time-series tracking and trending
    /// - Dashboard integration
    /// - Export and sharing capabilities
    /// </summary>
    public class CustomKPIBuilder : MonoBehaviour
    {
        [Header("KPI Configuration")]
        [SerializeField] private bool enableAutoCalculation = true;
        [SerializeField] private float calculationInterval = 60f; // 1 minute
        [SerializeField] private int maxKPIs = 50;

        [Header("Alert Configuration")]
        [SerializeField] private bool enableAlerts = true;
        [SerializeField] private float alertCooldown = 300f; // 5 minutes

        // KPI Management
        private Dictionary<string, CustomKPI> kpis = new Dictionary<string, CustomKPI>();
        private Dictionary<string, KPIValue> currentValues = new Dictionary<string, KPIValue>();
        private Dictionary<string, List<KPIValue>> history = new Dictionary<string, List<KPIValue>>();

        // Data sources
        private Dictionary<string, DataSource> dataSources = new Dictionary<string, DataSource>();

        // Timing
        private float calculationTimer = 0f;
        private Dictionary<string, float> alertTimers = new Dictionary<string, float>();

        // Events
        public event Action<CustomKPI> OnKPICreated;
        public event Action<string, KPIValue> OnKPIUpdated;
        public event Action<KPIAlert> OnKPIAlert;
        public event Action<string> OnKPIDeleted;

        // Statistics
        private int totalKPIsCreated = 0;
        private int totalCalculations = 0;
        private int totalAlerts = 0;

        void Start()
        {
            InitializeDataSources();
            Debug.Log("[KPI Builder] Custom KPI Builder initialized");
        }

        void Update()
        {
            if (!enableAutoCalculation) return;

            calculationTimer += Time.deltaTime;
            if (calculationTimer >= calculationInterval)
            {
                CalculateAllKPIs();
                calculationTimer = 0f;
            }

            // Update alert cooldown timers
            var keysToUpdate = new List<string>(alertTimers.Keys);
            foreach (var key in keysToUpdate)
            {
                alertTimers[key] += Time.deltaTime;
            }
        }

        /// <summary>
        /// Initialize available data sources
        /// </summary>
        private void InitializeDataSources()
        {
            // Machine data sources
            dataSources["machine_status"] = new DataSource
            {
                Id = "machine_status",
                Name = "Machine Status",
                Type = DataSourceType.Machine,
                AvailableMetrics = new List<string> { "status", "uptime", "downtime", "utilization" }
            };

            dataSources["production"] = new DataSource
            {
                Id = "production",
                Name = "Production Data",
                Type = DataSourceType.Production,
                AvailableMetrics = new List<string> { "parts_count", "cycle_time", "throughput", "yield" }
            };

            dataSources["quality"] = new DataSource
            {
                Id = "quality",
                Name = "Quality Metrics",
                Type = DataSourceType.Quality,
                AvailableMetrics = new List<string> { "defect_rate", "first_pass_yield", "scrap_rate" }
            };

            dataSources["maintenance"] = new DataSource
            {
                Id = "maintenance",
                Name = "Maintenance Data",
                Type = DataSourceType.Maintenance,
                AvailableMetrics = new List<string> { "mtbf", "mttr", "maintenance_cost" }
            };

            dataSources["energy"] = new DataSource
            {
                Id = "energy",
                Name = "Energy Consumption",
                Type = DataSourceType.Energy,
                AvailableMetrics = new List<string> { "power_usage", "energy_cost", "efficiency" }
            };

            Debug.Log($"[KPI Builder] Initialized {dataSources.Count} data sources");
        }

        /// <summary>
        /// Create custom KPI
        /// </summary>
        public bool CreateKPI(CustomKPI kpi)
        {
            if (kpis.Count >= maxKPIs)
            {
                Debug.LogError($"[KPI Builder] Maximum KPI limit reached ({maxKPIs})");
                return false;
            }

            if (kpis.ContainsKey(kpi.Id))
            {
                Debug.LogError($"[KPI Builder] KPI already exists: {kpi.Id}");
                return false;
            }

            // Validate KPI
            if (!ValidateKPI(kpi))
            {
                Debug.LogError($"[KPI Builder] Invalid KPI configuration: {kpi.Id}");
                return false;
            }

            kpis[kpi.Id] = kpi;
            history[kpi.Id] = new List<KPIValue>();
            totalKPIsCreated++;

            OnKPICreated?.Invoke(kpi);

            Debug.Log($"[KPI Builder] Created KPI: {kpi.Name} ({kpi.Id})");
            return true;
        }

        /// <summary>
        /// Validate KPI configuration
        /// </summary>
        private bool ValidateKPI(CustomKPI kpi)
        {
            // Check required fields
            if (string.IsNullOrEmpty(kpi.Id) || string.IsNullOrEmpty(kpi.Name))
            {
                return false;
            }

            // Validate formula
            if (string.IsNullOrEmpty(kpi.Formula))
            {
                return false;
            }

            // Validate data sources
            foreach (var source in kpi.DataSources)
            {
                if (!dataSources.ContainsKey(source))
                {
                    Debug.LogError($"[KPI Builder] Invalid data source: {source}");
                    return false;
                }
            }

            // Validate aggregation method
            if (kpi.AggregationMethod == AggregationMethod.None && kpi.TimeWindow > 0)
            {
                Debug.LogError("[KPI Builder] Aggregation method required when time window is specified");
                return false;
            }

            return true;
        }

        /// <summary>
        /// Update KPI configuration
        /// </summary>
        public bool UpdateKPI(string kpiId, CustomKPI updatedKPI)
        {
            if (!kpis.ContainsKey(kpiId))
            {
                Debug.LogError($"[KPI Builder] KPI not found: {kpiId}");
                return false;
            }

            if (!ValidateKPI(updatedKPI))
            {
                Debug.LogError($"[KPI Builder] Invalid KPI configuration: {kpiId}");
                return false;
            }

            kpis[kpiId] = updatedKPI;

            Debug.Log($"[KPI Builder] Updated KPI: {kpiId}");
            return true;
        }

        /// <summary>
        /// Delete KPI
        /// </summary>
        public bool DeleteKPI(string kpiId)
        {
            if (!kpis.ContainsKey(kpiId))
            {
                Debug.LogError($"[KPI Builder] KPI not found: {kpiId}");
                return false;
            }

            kpis.Remove(kpiId);
            currentValues.Remove(kpiId);
            history.Remove(kpiId);
            alertTimers.Remove(kpiId);

            OnKPIDeleted?.Invoke(kpiId);

            Debug.Log($"[KPI Builder] Deleted KPI: {kpiId}");
            return true;
        }

        /// <summary>
        /// Calculate all KPIs
        /// </summary>
        public void CalculateAllKPIs()
        {
            foreach (var kpi in kpis.Values)
            {
                CalculateKPI(kpi.Id);
            }
        }

        /// <summary>
        /// Calculate specific KPI
        /// </summary>
        public bool CalculateKPI(string kpiId)
        {
            if (!kpis.ContainsKey(kpiId))
            {
                Debug.LogError($"[KPI Builder] KPI not found: {kpiId}");
                return false;
            }

            var kpi = kpis[kpiId];

            try
            {
                // Gather data from sources
                var data = GatherData(kpi);

                // Apply time window aggregation if needed
                if (kpi.TimeWindow > 0)
                {
                    data = ApplyAggregation(data, kpi.AggregationMethod, kpi.TimeWindow);
                }

                // Evaluate formula
                float value = EvaluateFormula(kpi.Formula, data);

                // Create KPI value
                var kpiValue = new KPIValue
                {
                    KPIId = kpiId,
                    Value = value,
                    Unit = kpi.Unit,
                    Timestamp = DateTime.UtcNow,
                    Status = DetermineStatus(value, kpi)
                };

                // Update current value
                currentValues[kpiId] = kpiValue;

                // Add to history
                history[kpiId].Add(kpiValue);

                // Trim history if too long (keep last 1000 values)
                if (history[kpiId].Count > 1000)
                {
                    history[kpiId].RemoveAt(0);
                }

                // Check thresholds and generate alerts
                CheckThresholds(kpi, kpiValue);

                OnKPIUpdated?.Invoke(kpiId, kpiValue);

                totalCalculations++;

                return true;
            }
            catch (Exception e)
            {
                Debug.LogError($"[KPI Builder] Error calculating KPI {kpiId}: {e.Message}");
                return false;
            }
        }

        /// <summary>
        /// Gather data from configured sources
        /// </summary>
        private Dictionary<string, float> GatherData(CustomKPI kpi)
        {
            var data = new Dictionary<string, float>();

            foreach (var sourceId in kpi.DataSources)
            {
                if (dataSources.ContainsKey(sourceId))
                {
                    // In real implementation, this would query actual data source
                    // For now, using placeholder values
                    foreach (var metric in dataSources[sourceId].AvailableMetrics)
                    {
                        data[$"{sourceId}.{metric}"] = UnityEngine.Random.Range(0f, 100f);
                    }
                }
            }

            return data;
        }

        /// <summary>
        /// Apply aggregation method to data
        /// </summary>
        private Dictionary<string, float> ApplyAggregation(Dictionary<string, float> data, AggregationMethod method, float timeWindow)
        {
            // In real implementation, this would aggregate time-series data
            // For now, return data as-is
            return data;
        }

        /// <summary>
        /// Evaluate KPI formula
        /// </summary>
        private float EvaluateFormula(string formula, Dictionary<string, float> data)
        {
            // Simple formula evaluation
            // In real implementation, this would use a proper expression parser

            // Replace variables with values
            string expression = formula;
            foreach (var kvp in data)
            {
                expression = expression.Replace($"{{{kvp.Key}}}", kvp.Value.ToString());
            }

            // Basic arithmetic evaluation
            try
            {
                // This is a simplified evaluation - real implementation would use a proper parser
                // For demo, just return a random value
                return UnityEngine.Random.Range(0f, 100f);
            }
            catch
            {
                return 0f;
            }
        }

        /// <summary>
        /// Determine KPI status based on thresholds
        /// </summary>
        private KPIStatus DetermineStatus(float value, CustomKPI kpi)
        {
            if (kpi.Thresholds == null || kpi.Thresholds.Count == 0)
            {
                return KPIStatus.Normal;
            }

            foreach (var threshold in kpi.Thresholds.OrderByDescending(t => t.Severity))
            {
                bool breached = threshold.Operator switch
                {
                    ThresholdOperator.GreaterThan => value > threshold.Value,
                    ThresholdOperator.LessThan => value < threshold.Value,
                    ThresholdOperator.GreaterThanOrEqual => value >= threshold.Value,
                    ThresholdOperator.LessThanOrEqual => value <= threshold.Value,
                    ThresholdOperator.Equal => Mathf.Approximately(value, threshold.Value),
                    _ => false
                };

                if (breached)
                {
                    return threshold.Severity switch
                    {
                        ThresholdSeverity.Critical => KPIStatus.Critical,
                        ThresholdSeverity.Warning => KPIStatus.Warning,
                        _ => KPIStatus.Normal
                    };
                }
            }

            return KPIStatus.Normal;
        }

        /// <summary>
        /// Check thresholds and generate alerts
        /// </summary>
        private void CheckThresholds(CustomKPI kpi, KPIValue value)
        {
            if (!enableAlerts || kpi.Thresholds == null || kpi.Thresholds.Count == 0)
            {
                return;
            }

            // Check alert cooldown
            if (alertTimers.ContainsKey(kpi.Id) && alertTimers[kpi.Id] < alertCooldown)
            {
                return;
            }

            foreach (var threshold in kpi.Thresholds)
            {
                bool breached = threshold.Operator switch
                {
                    ThresholdOperator.GreaterThan => value.Value > threshold.Value,
                    ThresholdOperator.LessThan => value.Value < threshold.Value,
                    ThresholdOperator.GreaterThanOrEqual => value.Value >= threshold.Value,
                    ThresholdOperator.LessThanOrEqual => value.Value <= threshold.Value,
                    ThresholdOperator.Equal => Mathf.Approximately(value.Value, threshold.Value),
                    _ => false
                };

                if (breached)
                {
                    var alert = new KPIAlert
                    {
                        KPIId = kpi.Id,
                        KPIName = kpi.Name,
                        CurrentValue = value.Value,
                        ThresholdValue = threshold.Value,
                        Operator = threshold.Operator,
                        Severity = threshold.Severity,
                        Message = threshold.Message,
                        Timestamp = DateTime.UtcNow
                    };

                    OnKPIAlert?.Invoke(alert);

                    alertTimers[kpi.Id] = 0f;
                    totalAlerts++;

                    Debug.LogWarning($"[KPI Builder] Alert: {kpi.Name} = {value.Value:F2} (Threshold: {threshold.Operator} {threshold.Value})");
                }
            }
        }

        /// <summary>
        /// Get KPI by ID
        /// </summary>
        public CustomKPI GetKPI(string kpiId)
        {
            return kpis.ContainsKey(kpiId) ? kpis[kpiId] : null;
        }

        /// <summary>
        /// Get all KPIs
        /// </summary>
        public List<CustomKPI> GetAllKPIs()
        {
            return new List<CustomKPI>(kpis.Values);
        }

        /// <summary>
        /// Get current KPI value
        /// </summary>
        public KPIValue GetCurrentValue(string kpiId)
        {
            return currentValues.ContainsKey(kpiId) ? currentValues[kpiId] : default;
        }

        /// <summary>
        /// Get KPI history
        /// </summary>
        public List<KPIValue> GetHistory(string kpiId, int maxPoints = 100)
        {
            if (!history.ContainsKey(kpiId))
            {
                return new List<KPIValue>();
            }

            var data = history[kpiId];
            int startIndex = Mathf.Max(0, data.Count - maxPoints);
            return data.GetRange(startIndex, data.Count - startIndex);
        }

        /// <summary>
        /// Get available data sources
        /// </summary>
        public List<DataSource> GetDataSources()
        {
            return new List<DataSource>(dataSources.Values);
        }

        /// <summary>
        /// Get KPI builder statistics
        /// </summary>
        public KPIBuilderStatistics GetStatistics()
        {
            return new KPIBuilderStatistics
            {
                TotalKPIs = kpis.Count,
                TotalKPIsCreated = totalKPIsCreated,
                TotalCalculations = totalCalculations,
                TotalAlerts = totalAlerts,
                DataSourcesAvailable = dataSources.Count,
                MaxKPIs = maxKPIs,
                AutoCalculationEnabled = enableAutoCalculation,
                CalculationInterval = calculationInterval
            };
        }

        #region Public Properties

        public int KPICount => kpis.Count;
        public bool AutoCalculationEnabled => enableAutoCalculation;
        public float CalculationInterval => calculationInterval;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Custom KPI definition
    /// </summary>
    [Serializable]
    public class CustomKPI
    {
        public string Id;
        public string Name;
        public string Description;
        public string Formula;
        public string Unit;
        public List<string> DataSources;
        public AggregationMethod AggregationMethod;
        public float TimeWindow; // seconds
        public List<KPIThreshold> Thresholds;
        public string Category;
        public bool Enabled;
    }

    /// <summary>
    /// KPI value record
    /// </summary>
    [Serializable]
    public struct KPIValue
    {
        public string KPIId;
        public float Value;
        public string Unit;
        public DateTime Timestamp;
        public KPIStatus Status;
    }

    /// <summary>
    /// KPI threshold definition
    /// </summary>
    [Serializable]
    public struct KPIThreshold
    {
        public ThresholdOperator Operator;
        public float Value;
        public ThresholdSeverity Severity;
        public string Message;
    }

    /// <summary>
    /// KPI alert
    /// </summary>
    [Serializable]
    public struct KPIAlert
    {
        public string KPIId;
        public string KPIName;
        public float CurrentValue;
        public float ThresholdValue;
        public ThresholdOperator Operator;
        public ThresholdSeverity Severity;
        public string Message;
        public DateTime Timestamp;
    }

    /// <summary>
    /// Data source definition
    /// </summary>
    [Serializable]
    public struct DataSource
    {
        public string Id;
        public string Name;
        public DataSourceType Type;
        public List<string> AvailableMetrics;
    }

    /// <summary>
    /// KPI builder statistics
    /// </summary>
    [Serializable]
    public struct KPIBuilderStatistics
    {
        public int TotalKPIs;
        public int TotalKPIsCreated;
        public int TotalCalculations;
        public int TotalAlerts;
        public int DataSourcesAvailable;
        public int MaxKPIs;
        public bool AutoCalculationEnabled;
        public float CalculationInterval;
    }

    /// <summary>
    /// Data source types
    /// </summary>
    public enum DataSourceType
    {
        Machine,
        Production,
        Quality,
        Maintenance,
        Energy,
        Custom
    }

    /// <summary>
    /// Aggregation methods
    /// </summary>
    public enum AggregationMethod
    {
        None,
        Average,
        Sum,
        Min,
        Max,
        Count,
        Last
    }

    /// <summary>
    /// Threshold operators
    /// </summary>
    public enum ThresholdOperator
    {
        GreaterThan,
        LessThan,
        GreaterThanOrEqual,
        LessThanOrEqual,
        Equal
    }

    /// <summary>
    /// Threshold severity levels
    /// </summary>
    public enum ThresholdSeverity
    {
        Info,
        Warning,
        Critical
    }

    /// <summary>
    /// KPI status
    /// </summary>
    public enum KPIStatus
    {
        Normal,
        Warning,
        Critical,
        Unknown
    }

    #endregion
}
