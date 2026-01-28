using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCDigitalTwin.Quality
{
    /// <summary>
    /// Quality SPC (Statistical Process Control) System for CNC Digital Twin
    /// Implements control charts, capability analysis, and real-time quality monitoring
    /// Supports ISO 9001 and IATF 16949 quality management requirements
    /// </summary>
    public class QualitySPCSystem : MonoBehaviour
    {
        public static QualitySPCSystem Instance { get; private set; }

        [Header("SPC Configuration")]
        [SerializeField] private int defaultSubgroupSize = 5;
        [SerializeField] private int controlChartPoints = 25;
        [SerializeField] private float sigmaMultiplier = 3f;
        [SerializeField] private bool enableWesternElectricRules = true;

        [Header("Capability Targets")]
        [SerializeField] private float targetCp = 1.33f;
        [SerializeField] private float targetCpk = 1.33f;
        [SerializeField] private float targetPpk = 1.67f;

        [Header("Inspection Settings")]
        [SerializeField] private float measurementUncertainty = 0.001f; // mm
        [SerializeField] private bool enableAutoCalibration = true;
        [SerializeField] private float calibrationIntervalHours = 8f;

        // Events
        public event Action<Characteristic, Measurement> OnMeasurementRecorded;
        public event Action<ControlChart, SPCViolation> OnControlViolation;
        public event Action<Characteristic, CapabilityResult> OnCapabilityCalculated;
        public event Action<InspectionResult> OnInspectionComplete;
        public event Action<QualityAlert> OnQualityAlert;
        public event Action<ProcessChange> OnProcessChange;

        // Data collections
        private Dictionary<string, Characteristic> characteristics = new Dictionary<string, Characteristic>();
        private Dictionary<string, ControlChart> controlCharts = new Dictionary<string, ControlChart>();
        private Dictionary<string, GageRR> gageStudies = new Dictionary<string, GageRR>();
        private Dictionary<string, InspectionPlan> inspectionPlans = new Dictionary<string, InspectionPlan>();
        private List<Measurement> measurementHistory = new List<Measurement>();

        // Current state
        private QualityState currentState = new QualityState();

        // Statistics
        private QualityStats stats = new QualityStats();

        #region Data Structures

        public enum CharacteristicType
        {
            Dimension,
            Position,
            Runout,
            Flatness,
            Perpendicularity,
            Parallelism,
            Angularity,
            Concentricity,
            Circularity,
            Cylindricity,
            SurfaceFinish,
            Hardness,
            Weight,
            Torque
        }

        public enum ControlChartType
        {
            XBar_R,      // Average and Range
            XBar_S,      // Average and Std Dev
            Individual_MR, // Individual and Moving Range
            P_Chart,     // Proportion defective
            NP_Chart,    // Number defective
            C_Chart,     // Count of defects
            U_Chart      // Defects per unit
        }

        public enum InspectionType
        {
            FirstArticle,
            InProcess,
            Final,
            Receiving,
            Audit,
            SPC
        }

        public enum ViolationType
        {
            OutOfControl,      // Point beyond control limits
            Rule2_9Points,     // 9 consecutive points on one side
            Rule3_6Points,     // 6 consecutive increasing/decreasing
            Rule4_14Points,    // 14 consecutive alternating
            Rule5_2of3,        // 2 of 3 beyond 2 sigma
            Rule6_4of5,        // 4 of 5 beyond 1 sigma
            Rule7_15Points,    // 15 consecutive within 1 sigma
            Rule8_8Points,     // 8 consecutive beyond 1 sigma
            Trend,
            Shift,
            Mixture,
            Stratification
        }

        public class Characteristic
        {
            public string CharId { get; set; }
            public string Name { get; set; }
            public string PartNumber { get; set; }
            public string Operation { get; set; }
            public CharacteristicType Type { get; set; }
            public float Nominal { get; set; }
            public float UpperSpec { get; set; }
            public float LowerSpec { get; set; }
            public float Tolerance => UpperSpec - LowerSpec;
            public string Units { get; set; }
            public bool IsCritical { get; set; }
            public bool IsKeyCharacteristic { get; set; }
            public string GageId { get; set; }
            public int DecimalPlaces { get; set; }
            public CapabilityResult CurrentCapability { get; set; }
            public List<Measurement> RecentMeasurements { get; set; } = new List<Measurement>();
        }

        public class Measurement
        {
            public string MeasurementId { get; set; }
            public string CharId { get; set; }
            public string PartId { get; set; }
            public DateTime Timestamp { get; set; }
            public float Value { get; set; }
            public float Nominal { get; set; }
            public float Deviation => Value - Nominal;
            public bool IsConforming { get; set; }
            public string OperatorId { get; set; }
            public string GageId { get; set; }
            public int SubgroupNumber { get; set; }
            public Dictionary<string, object> Metadata { get; set; } = new Dictionary<string, object>();
        }

        public class ControlChart
        {
            public string ChartId { get; set; }
            public string CharId { get; set; }
            public ControlChartType Type { get; set; }
            public int SubgroupSize { get; set; }

            // Control limits
            public float UCL { get; set; }  // Upper Control Limit
            public float CL { get; set; }   // Center Line
            public float LCL { get; set; }  // Lower Control Limit
            public float USL { get; set; }  // Upper Spec Limit
            public float LSL { get; set; }  // Lower Spec Limit

            // For range/std dev charts
            public float UCL_R { get; set; }
            public float CL_R { get; set; }
            public float LCL_R { get; set; }

            // Zone boundaries (1, 2, 3 sigma)
            public float Zone_A_Upper { get; set; }
            public float Zone_B_Upper { get; set; }
            public float Zone_B_Lower { get; set; }
            public float Zone_A_Lower { get; set; }

            // Data
            public List<SubgroupData> Subgroups { get; set; } = new List<SubgroupData>();
            public DateTime LastUpdate { get; set; }
            public bool IsInControl { get; set; }
            public int ConsecutiveViolations { get; set; }
        }

        public class SubgroupData
        {
            public int SubgroupNumber { get; set; }
            public DateTime Timestamp { get; set; }
            public List<float> Values { get; set; } = new List<float>();
            public float Mean { get; set; }
            public float Range { get; set; }
            public float StdDev { get; set; }
            public bool IsViolation { get; set; }
            public List<ViolationType> ViolationTypes { get; set; } = new List<ViolationType>();
        }

        public class SPCViolation
        {
            public string ViolationId { get; set; }
            public string ChartId { get; set; }
            public DateTime Timestamp { get; set; }
            public ViolationType Type { get; set; }
            public int SubgroupNumber { get; set; }
            public float Value { get; set; }
            public float ControlLimit { get; set; }
            public string Description { get; set; }
            public string RecommendedAction { get; set; }
            public bool Acknowledged { get; set; }
            public string RootCause { get; set; }
            public string CorrectiveAction { get; set; }
        }

        public class CapabilityResult
        {
            public string CharId { get; set; }
            public DateTime CalculatedTime { get; set; }
            public int SampleSize { get; set; }

            // Basic statistics
            public float Mean { get; set; }
            public float StdDev { get; set; }
            public float Min { get; set; }
            public float Max { get; set; }

            // Capability indices
            public float Cp { get; set; }    // Process capability
            public float Cpk { get; set; }   // Process capability index
            public float Cpm { get; set; }   // Taguchi capability
            public float Pp { get; set; }    // Process performance
            public float Ppk { get; set; }   // Process performance index

            // Sigma level
            public float SigmaLevel { get; set; }
            public float PPM_Expected { get; set; } // Parts per million defective
            public float Yield { get; set; }  // Expected yield %

            // Assessment
            public CapabilityRating Rating { get; set; }
            public bool MeetsTarget { get; set; }
        }

        public enum CapabilityRating
        {
            Excellent,    // Cpk >= 2.0
            Good,         // 1.67 <= Cpk < 2.0
            Acceptable,   // 1.33 <= Cpk < 1.67
            Marginal,     // 1.0 <= Cpk < 1.33
            Poor,         // 0.67 <= Cpk < 1.0
            Unacceptable  // Cpk < 0.67
        }

        public class InspectionPlan
        {
            public string PlanId { get; set; }
            public string PartNumber { get; set; }
            public string Operation { get; set; }
            public InspectionType Type { get; set; }
            public List<string> CharacteristicIds { get; set; } = new List<string>();
            public int SampleSize { get; set; }
            public float SamplingFrequency { get; set; } // parts per inspection
            public bool IsActive { get; set; }
            public AQL_Level AQL { get; set; }
        }

        public enum AQL_Level
        {
            Level_0_065,
            Level_0_10,
            Level_0_15,
            Level_0_25,
            Level_0_40,
            Level_0_65,
            Level_1_0,
            Level_1_5,
            Level_2_5,
            Level_4_0
        }

        public class InspectionResult
        {
            public string InspectionId { get; set; }
            public string PlanId { get; set; }
            public string PartId { get; set; }
            public DateTime Timestamp { get; set; }
            public string OperatorId { get; set; }
            public List<Measurement> Measurements { get; set; } = new List<Measurement>();
            public bool IsConforming { get; set; }
            public int ConformingCount { get; set; }
            public int NonConformingCount { get; set; }
            public string Disposition { get; set; }
            public List<string> NonConformanceIds { get; set; } = new List<string>();
        }

        public class GageRR
        {
            public string StudyId { get; set; }
            public string GageId { get; set; }
            public string CharId { get; set; }
            public DateTime StudyDate { get; set; }
            public int NumberOfParts { get; set; }
            public int NumberOfOperators { get; set; }
            public int NumberOfTrials { get; set; }

            // Results
            public float GRR_Percent { get; set; }    // % of tolerance
            public float Repeatability { get; set; }  // Equipment variation
            public float Reproducibility { get; set; }// Operator variation
            public float PartVariation { get; set; }
            public float TotalVariation { get; set; }
            public int NumberOfDistinctCategories { get; set; }

            public GageRRRating Rating { get; set; }
        }

        public enum GageRRRating
        {
            Excellent,   // < 10%
            Acceptable,  // 10-30%
            Marginal,    // 30-50%
            Unacceptable // > 50%
        }

        public class QualityAlert
        {
            public string AlertId { get; set; }
            public DateTime Timestamp { get; set; }
            public string Source { get; set; }
            public AlertSeverity Severity { get; set; }
            public string Message { get; set; }
            public string CharId { get; set; }
            public string PartId { get; set; }
            public bool RequiresAction { get; set; }
            public string RecommendedAction { get; set; }
        }

        public enum AlertSeverity
        {
            Info,
            Warning,
            Critical,
            Stop
        }

        public class ProcessChange
        {
            public string ChangeId { get; set; }
            public DateTime Timestamp { get; set; }
            public string CharId { get; set; }
            public ProcessChangeType Type { get; set; }
            public float BeforeValue { get; set; }
            public float AfterValue { get; set; }
            public float Magnitude { get; set; }
            public string DetectionMethod { get; set; }
        }

        public enum ProcessChangeType
        {
            MeanShift,
            VariationIncrease,
            VariationDecrease,
            Trend,
            CyclicPattern
        }

        public class QualityState
        {
            public DateTime Timestamp { get; set; }
            public int TotalCharacteristics { get; set; }
            public int InControlCharts { get; set; }
            public int OutOfControlCharts { get; set; }
            public float OverallYield { get; set; }
            public float AverageCpk { get; set; }
            public int ActiveAlerts { get; set; }
            public int PartsInspectedToday { get; set; }
            public int DefectsFoundToday { get; set; }
            public float FirstTimeYield { get; set; }
        }

        public class QualityStats
        {
            public DateTime StartTime { get; set; }
            public long TotalMeasurements { get; set; }
            public long TotalInspections { get; set; }
            public long TotalViolations { get; set; }
            public int CharacteristicsMonitored { get; set; }
            public int ActiveControlCharts { get; set; }
            public float OverallCpk { get; set; }
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
            InitializeDefaultConfiguration();
            StartCoroutine(SPCMonitorLoop());
            StartCoroutine(CapabilityAnalysisLoop());

            Debug.Log("[QualitySPC] System initialized");
        }

        private void InitializeDefaultConfiguration()
        {
            // Register sample characteristics
            RegisterCharacteristic("DIAM_001", "Bore Diameter", "PART-001", CharacteristicType.Dimension,
                nominal: 25.0f, upperSpec: 25.015f, lowerSpec: 24.985f, units: "mm", isCritical: true);

            RegisterCharacteristic("POS_001", "Hole Position X", "PART-001", CharacteristicType.Position,
                nominal: 50.0f, upperSpec: 50.05f, lowerSpec: 49.95f, units: "mm");

            RegisterCharacteristic("FLAT_001", "Surface Flatness", "PART-001", CharacteristicType.Flatness,
                nominal: 0f, upperSpec: 0.01f, lowerSpec: 0f, units: "mm");

            RegisterCharacteristic("RA_001", "Surface Finish", "PART-001", CharacteristicType.SurfaceFinish,
                nominal: 0.8f, upperSpec: 1.6f, lowerSpec: 0f, units: "µm Ra");

            // Create control charts
            CreateControlChart("DIAM_001", ControlChartType.XBar_R, defaultSubgroupSize);
            CreateControlChart("POS_001", ControlChartType.XBar_R, defaultSubgroupSize);
            CreateControlChart("FLAT_001", ControlChartType.Individual_MR, 1);
            CreateControlChart("RA_001", ControlChartType.XBar_R, defaultSubgroupSize);
        }

        #endregion

        #region Characteristic Management

        public Characteristic RegisterCharacteristic(string charId, string name, string partNumber,
            CharacteristicType type, float nominal, float upperSpec, float lowerSpec,
            string units = "mm", bool isCritical = false, bool isKeyChar = false)
        {
            var characteristic = new Characteristic
            {
                CharId = charId,
                Name = name,
                PartNumber = partNumber,
                Type = type,
                Nominal = nominal,
                UpperSpec = upperSpec,
                LowerSpec = lowerSpec,
                Units = units,
                IsCritical = isCritical,
                IsKeyCharacteristic = isKeyChar,
                DecimalPlaces = CalculateDecimalPlaces(upperSpec - lowerSpec)
            };

            characteristics[charId] = characteristic;
            stats.CharacteristicsMonitored++;

            Debug.Log($"[QualitySPC] Registered characteristic: {charId} ({name})");
            return characteristic;
        }

        private int CalculateDecimalPlaces(float tolerance)
        {
            // Rule of 10: measure to 1/10 of tolerance
            if (tolerance >= 1) return 2;
            if (tolerance >= 0.1) return 3;
            if (tolerance >= 0.01) return 4;
            return 5;
        }

        #endregion

        #region Control Charts

        public ControlChart CreateControlChart(string charId, ControlChartType type, int subgroupSize)
        {
            if (!characteristics.TryGetValue(charId, out var characteristic))
            {
                Debug.LogError($"[QualitySPC] Characteristic {charId} not found");
                return null;
            }

            var chart = new ControlChart
            {
                ChartId = $"CC_{charId}",
                CharId = charId,
                Type = type,
                SubgroupSize = subgroupSize,
                USL = characteristic.UpperSpec,
                LSL = characteristic.LowerSpec,
                IsInControl = true
            };

            controlCharts[chart.ChartId] = chart;
            stats.ActiveControlCharts++;

            Debug.Log($"[QualitySPC] Created {type} chart for {charId}");
            return chart;
        }

        public void RecordMeasurement(string charId, float value, string partId = null, string operatorId = null)
        {
            if (!characteristics.TryGetValue(charId, out var characteristic))
            {
                Debug.LogWarning($"[QualitySPC] Unknown characteristic: {charId}");
                return;
            }

            var measurement = new Measurement
            {
                MeasurementId = Guid.NewGuid().ToString(),
                CharId = charId,
                PartId = partId ?? Guid.NewGuid().ToString().Substring(0, 8),
                Timestamp = DateTime.Now,
                Value = value,
                IsConforming = value >= characteristic.LowerSpec && value <= characteristic.UpperSpec,
                OperatorId = operatorId
            };

            // Add to history
            measurementHistory.Add(measurement);
            characteristic.RecentMeasurements.Add(measurement);

            // Trim history
            while (characteristic.RecentMeasurements.Count > 1000)
                characteristic.RecentMeasurements.RemoveAt(0);

            stats.TotalMeasurements++;

            // Update control chart
            string chartId = $"CC_{charId}";
            if (controlCharts.TryGetValue(chartId, out var chart))
            {
                AddToControlChart(chart, measurement);
            }

            // Check for non-conformance
            if (!measurement.IsConforming)
            {
                GenerateAlert(AlertSeverity.Warning, charId,
                    $"Non-conforming measurement: {value:F4} {characteristic.Units} (Spec: {characteristic.LowerSpec:F4} - {characteristic.UpperSpec:F4})",
                    partId);
            }

            OnMeasurementRecorded?.Invoke(characteristic, measurement);
        }

        private void AddToControlChart(ControlChart chart, Measurement measurement)
        {
            // Get or create current subgroup
            SubgroupData currentSubgroup;

            if (chart.Subgroups.Count == 0 ||
                chart.Subgroups.Last().Values.Count >= chart.SubgroupSize)
            {
                // Create new subgroup
                currentSubgroup = new SubgroupData
                {
                    SubgroupNumber = chart.Subgroups.Count + 1,
                    Timestamp = DateTime.Now
                };
                chart.Subgroups.Add(currentSubgroup);
                measurement.SubgroupNumber = currentSubgroup.SubgroupNumber;
            }
            else
            {
                currentSubgroup = chart.Subgroups.Last();
                measurement.SubgroupNumber = currentSubgroup.SubgroupNumber;
            }

            currentSubgroup.Values.Add(measurement.Value);

            // If subgroup is complete, calculate statistics and check control
            if (currentSubgroup.Values.Count >= chart.SubgroupSize)
            {
                CalculateSubgroupStats(currentSubgroup);

                // Recalculate control limits if we have enough data
                if (chart.Subgroups.Count >= 20)
                {
                    RecalculateControlLimits(chart);
                }

                // Check for violations
                CheckControlChartViolations(chart, currentSubgroup);
            }

            chart.LastUpdate = DateTime.Now;

            // Trim old subgroups
            while (chart.Subgroups.Count > controlChartPoints)
                chart.Subgroups.RemoveAt(0);
        }

        private void CalculateSubgroupStats(SubgroupData subgroup)
        {
            if (subgroup.Values.Count == 0) return;

            subgroup.Mean = subgroup.Values.Average();
            subgroup.Range = subgroup.Values.Max() - subgroup.Values.Min();

            if (subgroup.Values.Count > 1)
            {
                float sumSqDiff = subgroup.Values.Sum(v => (v - subgroup.Mean) * (v - subgroup.Mean));
                subgroup.StdDev = Mathf.Sqrt(sumSqDiff / (subgroup.Values.Count - 1));
            }
        }

        private void RecalculateControlLimits(ControlChart chart)
        {
            var completeSubgroups = chart.Subgroups.Where(s => s.Values.Count >= chart.SubgroupSize).ToList();

            if (completeSubgroups.Count < 20) return;

            float xBarBar = completeSubgroups.Average(s => s.Mean);
            float rBar = completeSubgroups.Average(s => s.Range);

            // A2, D3, D4 constants depend on subgroup size
            float A2 = GetA2Constant(chart.SubgroupSize);
            float D3 = GetD3Constant(chart.SubgroupSize);
            float D4 = GetD4Constant(chart.SubgroupSize);

            // X-bar chart limits
            chart.CL = xBarBar;
            chart.UCL = xBarBar + A2 * rBar;
            chart.LCL = xBarBar - A2 * rBar;

            // R chart limits
            chart.CL_R = rBar;
            chart.UCL_R = D4 * rBar;
            chart.LCL_R = D3 * rBar;

            // Zone boundaries
            float oneThirdWidth = (chart.UCL - chart.CL) / 3f;
            chart.Zone_A_Upper = chart.CL + 2 * oneThirdWidth;
            chart.Zone_B_Upper = chart.CL + oneThirdWidth;
            chart.Zone_B_Lower = chart.CL - oneThirdWidth;
            chart.Zone_A_Lower = chart.CL - 2 * oneThirdWidth;
        }

        private float GetA2Constant(int n)
        {
            float[] A2 = { 0, 0, 1.880f, 1.023f, 0.729f, 0.577f, 0.483f, 0.419f, 0.373f, 0.337f, 0.308f };
            return n < A2.Length ? A2[n] : 0.308f;
        }

        private float GetD3Constant(int n)
        {
            float[] D3 = { 0, 0, 0, 0, 0, 0, 0, 0.076f, 0.136f, 0.184f, 0.223f };
            return n < D3.Length ? D3[n] : 0.223f;
        }

        private float GetD4Constant(int n)
        {
            float[] D4 = { 0, 0, 3.267f, 2.574f, 2.282f, 2.114f, 2.004f, 1.924f, 1.864f, 1.816f, 1.777f };
            return n < D4.Length ? D4[n] : 1.777f;
        }

        #endregion

        #region Control Chart Violation Detection

        private void CheckControlChartViolations(ControlChart chart, SubgroupData subgroup)
        {
            var violations = new List<ViolationType>();
            var recentSubgroups = chart.Subgroups.ToList();

            // Rule 1: Point beyond control limits
            if (subgroup.Mean > chart.UCL || subgroup.Mean < chart.LCL)
            {
                violations.Add(ViolationType.OutOfControl);
            }

            if (enableWesternElectricRules && recentSubgroups.Count >= 9)
            {
                // Rule 2: 9 consecutive points on one side of center
                var last9 = recentSubgroups.Skip(recentSubgroups.Count - 9).Take(9).ToList();
                if (last9.All(s => s.Mean > chart.CL) || last9.All(s => s.Mean < chart.CL))
                {
                    violations.Add(ViolationType.Rule2_9Points);
                }

                // Rule 3: 6 consecutive increasing or decreasing
                if (recentSubgroups.Count >= 6)
                {
                    var last6 = recentSubgroups.Skip(recentSubgroups.Count - 6).Take(6).ToList();
                    bool allIncreasing = true, allDecreasing = true;
                    for (int i = 1; i < 6; i++)
                    {
                        if (last6[i].Mean <= last6[i - 1].Mean) allIncreasing = false;
                        if (last6[i].Mean >= last6[i - 1].Mean) allDecreasing = false;
                    }
                    if (allIncreasing || allDecreasing)
                    {
                        violations.Add(ViolationType.Rule3_6Points);
                    }
                }

                // Rule 5: 2 of 3 points beyond 2 sigma
                if (recentSubgroups.Count >= 3)
                {
                    var last3 = recentSubgroups.Skip(recentSubgroups.Count - 3).Take(3).ToList();
                    int beyondUpperA = last3.Count(s => s.Mean > chart.Zone_A_Upper);
                    int beyondLowerA = last3.Count(s => s.Mean < chart.Zone_A_Lower);
                    if (beyondUpperA >= 2 || beyondLowerA >= 2)
                    {
                        violations.Add(ViolationType.Rule5_2of3);
                    }
                }

                // Rule 6: 4 of 5 points beyond 1 sigma
                if (recentSubgroups.Count >= 5)
                {
                    var last5 = recentSubgroups.Skip(recentSubgroups.Count - 5).Take(5).ToList();
                    int beyondUpperB = last5.Count(s => s.Mean > chart.Zone_B_Upper);
                    int beyondLowerB = last5.Count(s => s.Mean < chart.Zone_B_Lower);
                    if (beyondUpperB >= 4 || beyondLowerB >= 4)
                    {
                        violations.Add(ViolationType.Rule6_4of5);
                    }
                }
            }

            if (violations.Count > 0)
            {
                subgroup.IsViolation = true;
                subgroup.ViolationTypes = violations;
                chart.IsInControl = false;
                chart.ConsecutiveViolations++;
                stats.TotalViolations++;

                foreach (var violationType in violations)
                {
                    var violation = new SPCViolation
                    {
                        ViolationId = Guid.NewGuid().ToString(),
                        ChartId = chart.ChartId,
                        Timestamp = DateTime.Now,
                        Type = violationType,
                        SubgroupNumber = subgroup.SubgroupNumber,
                        Value = subgroup.Mean,
                        ControlLimit = violationType == ViolationType.OutOfControl ?
                            (subgroup.Mean > chart.CL ? chart.UCL : chart.LCL) : chart.CL,
                        Description = GetViolationDescription(violationType),
                        RecommendedAction = GetRecommendedAction(violationType)
                    };

                    OnControlViolation?.Invoke(chart, violation);
                    Debug.LogWarning($"[QualitySPC] Control violation: {chart.CharId} - {violationType}");
                }
            }
            else
            {
                chart.IsInControl = true;
                chart.ConsecutiveViolations = 0;
            }
        }

        private string GetViolationDescription(ViolationType type)
        {
            return type switch
            {
                ViolationType.OutOfControl => "Point beyond control limits",
                ViolationType.Rule2_9Points => "9 consecutive points on same side of center",
                ViolationType.Rule3_6Points => "6 consecutive increasing or decreasing points",
                ViolationType.Rule4_14Points => "14 consecutive alternating points",
                ViolationType.Rule5_2of3 => "2 of 3 points beyond 2 sigma",
                ViolationType.Rule6_4of5 => "4 of 5 points beyond 1 sigma",
                ViolationType.Rule7_15Points => "15 consecutive points within 1 sigma (stratification)",
                ViolationType.Rule8_8Points => "8 consecutive points beyond 1 sigma (mixture)",
                ViolationType.Trend => "Trending detected",
                ViolationType.Shift => "Process shift detected",
                _ => "Unknown violation"
            };
        }

        private string GetRecommendedAction(ViolationType type)
        {
            return type switch
            {
                ViolationType.OutOfControl => "Stop and investigate assignable cause",
                ViolationType.Rule2_9Points => "Check for process mean shift",
                ViolationType.Rule3_6Points => "Check for tool wear or drift",
                ViolationType.Rule5_2of3 => "Verify measurement system, check process",
                ViolationType.Rule6_4of5 => "Investigate process variation",
                ViolationType.Shift => "Identify and correct assignable cause",
                ViolationType.Trend => "Check for progressive deterioration",
                _ => "Investigate and document findings"
            };
        }

        #endregion

        #region Capability Analysis

        private IEnumerator CapabilityAnalysisLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(300f); // Every 5 minutes

                foreach (var charId in characteristics.Keys)
                {
                    CalculateCapability(charId);
                }
            }
        }

        public CapabilityResult CalculateCapability(string charId, int? sampleSize = null)
        {
            if (!characteristics.TryGetValue(charId, out var characteristic))
                return null;

            var measurements = characteristic.RecentMeasurements
                .OrderByDescending(m => m.Timestamp)
                .Take(sampleSize ?? 50)
                .Select(m => m.Value)
                .ToList();

            if (measurements.Count < 30)
            {
                Debug.LogWarning($"[QualitySPC] Insufficient data for capability: {charId} ({measurements.Count} samples)");
                return null;
            }

            var result = new CapabilityResult
            {
                CharId = charId,
                CalculatedTime = DateTime.Now,
                SampleSize = measurements.Count
            };

            // Basic statistics
            result.Mean = measurements.Average();
            result.Min = measurements.Min();
            result.Max = measurements.Max();

            float sumSqDiff = measurements.Sum(v => (v - result.Mean) * (v - result.Mean));
            result.StdDev = Mathf.Sqrt(sumSqDiff / (measurements.Count - 1));

            float tolerance = characteristic.UpperSpec - characteristic.LowerSpec;
            float sigma6 = 6 * result.StdDev;

            // Cp - Process Capability (potential)
            result.Cp = tolerance / sigma6;

            // Cpk - Process Capability Index (actual)
            float cpUpper = (characteristic.UpperSpec - result.Mean) / (3 * result.StdDev);
            float cpLower = (result.Mean - characteristic.LowerSpec) / (3 * result.StdDev);
            result.Cpk = Mathf.Min(cpUpper, cpLower);

            // Cpm - Taguchi Capability (considers target)
            float targetDeviation = result.Mean - characteristic.Nominal;
            float tau = Mathf.Sqrt(result.StdDev * result.StdDev + targetDeviation * targetDeviation);
            result.Cpm = tolerance / (6 * tau);

            // Pp and Ppk (performance - uses overall standard deviation)
            // For this simplified version, Pp ≈ Cp, Ppk ≈ Cpk
            result.Pp = result.Cp;
            result.Ppk = result.Cpk;

            // Sigma level
            result.SigmaLevel = result.Cpk * 3f;

            // Expected PPM (using normal distribution approximation)
            result.PPM_Expected = CalculatePPM(result.Cpk);
            result.Yield = (1 - result.PPM_Expected / 1000000f) * 100f;

            // Rating
            result.Rating = result.Cpk switch
            {
                >= 2.0f => CapabilityRating.Excellent,
                >= 1.67f => CapabilityRating.Good,
                >= 1.33f => CapabilityRating.Acceptable,
                >= 1.0f => CapabilityRating.Marginal,
                >= 0.67f => CapabilityRating.Poor,
                _ => CapabilityRating.Unacceptable
            };

            result.MeetsTarget = result.Cpk >= targetCpk;

            // Store result
            characteristic.CurrentCapability = result;

            OnCapabilityCalculated?.Invoke(characteristic, result);

            // Alert if capability is low
            if (result.Cpk < targetCpk)
            {
                GenerateAlert(AlertSeverity.Warning, charId,
                    $"Capability below target: Cpk = {result.Cpk:F2} (Target: {targetCpk:F2})",
                    null);
            }

            return result;
        }

        private float CalculatePPM(float cpk)
        {
            // Simplified PPM calculation using Cpk
            // PPM ≈ 2 * (1 - Φ(3*Cpk)) * 1,000,000
            // Using approximation for standard normal CDF

            float z = 3 * cpk;
            float phi = NormalCDF(z);
            return (1 - phi) * 2 * 1000000f;
        }

        private float NormalCDF(float z)
        {
            // Approximation of standard normal CDF
            float a1 = 0.254829592f;
            float a2 = -0.284496736f;
            float a3 = 1.421413741f;
            float a4 = -1.453152027f;
            float a5 = 1.061405429f;
            float p = 0.3275911f;

            int sign = z < 0 ? -1 : 1;
            z = Mathf.Abs(z) / Mathf.Sqrt(2f);

            float t = 1.0f / (1.0f + p * z);
            float y = 1.0f - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Mathf.Exp(-z * z);

            return 0.5f * (1.0f + sign * y);
        }

        #endregion

        #region SPC Monitoring

        private IEnumerator SPCMonitorLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(60f); // Every minute

                UpdateQualityState();

                // Simulate measurements for testing
                SimulateMeasurements();
            }
        }

        private void SimulateMeasurements()
        {
            foreach (var characteristic in characteristics.Values)
            {
                // Generate realistic measurement based on specs
                float midPoint = (characteristic.UpperSpec + characteristic.LowerSpec) / 2f;
                float halfTolerance = characteristic.Tolerance / 2f;

                // Normal distribution centered on nominal with some variation
                float value = characteristic.Nominal +
                             UnityEngine.Random.Range(-halfTolerance * 0.5f, halfTolerance * 0.5f) +
                             Mathf.Sin(Time.time * 0.1f) * halfTolerance * 0.1f; // Small drift

                RecordMeasurement(characteristic.CharId, value);
            }
        }

        private void UpdateQualityState()
        {
            currentState.Timestamp = DateTime.Now;
            currentState.TotalCharacteristics = characteristics.Count;
            currentState.InControlCharts = controlCharts.Values.Count(c => c.IsInControl);
            currentState.OutOfControlCharts = controlCharts.Values.Count(c => !c.IsInControl);

            // Calculate average Cpk
            var cpkValues = characteristics.Values
                .Where(c => c.CurrentCapability != null)
                .Select(c => c.CurrentCapability.Cpk)
                .ToList();

            currentState.AverageCpk = cpkValues.Count > 0 ? cpkValues.Average() : 0;

            // Calculate yield
            var todayMeasurements = measurementHistory.Where(m => m.Timestamp.Date == DateTime.Today).ToList();
            currentState.PartsInspectedToday = todayMeasurements.Select(m => m.PartId).Distinct().Count();
            currentState.DefectsFoundToday = todayMeasurements.Count(m => !m.IsConforming);

            currentState.FirstTimeYield = currentState.PartsInspectedToday > 0 ?
                (1 - (float)currentState.DefectsFoundToday / currentState.PartsInspectedToday) * 100f : 100f;
        }

        #endregion

        #region Alerts

        private void GenerateAlert(AlertSeverity severity, string charId, string message, string partId)
        {
            var alert = new QualityAlert
            {
                AlertId = Guid.NewGuid().ToString(),
                Timestamp = DateTime.Now,
                Severity = severity,
                Source = "SPC System",
                Message = message,
                CharId = charId,
                PartId = partId,
                RequiresAction = severity >= AlertSeverity.Warning
            };

            OnQualityAlert?.Invoke(alert);

            if (severity >= AlertSeverity.Critical)
            {
                Debug.LogError($"[QualitySPC] CRITICAL: {message}");
            }
            else if (severity >= AlertSeverity.Warning)
            {
                Debug.LogWarning($"[QualitySPC] WARNING: {message}");
            }
        }

        #endregion

        #region Public API

        public Characteristic GetCharacteristic(string charId)
        {
            return characteristics.TryGetValue(charId, out var c) ? c : null;
        }

        public List<Characteristic> GetAllCharacteristics()
        {
            return characteristics.Values.ToList();
        }

        public ControlChart GetControlChart(string charId)
        {
            string chartId = $"CC_{charId}";
            return controlCharts.TryGetValue(chartId, out var chart) ? chart : null;
        }

        public List<ControlChart> GetAllControlCharts()
        {
            return controlCharts.Values.ToList();
        }

        public QualityState GetCurrentState()
        {
            return currentState;
        }

        public List<Measurement> GetMeasurementHistory(string charId, int count = 100)
        {
            return measurementHistory
                .Where(m => m.CharId == charId)
                .OrderByDescending(m => m.Timestamp)
                .Take(count)
                .ToList();
        }

        public QualityStats GetStats()
        {
            stats.OverallCpk = currentState.AverageCpk;
            return stats;
        }

        public void RecordBatchMeasurements(string charId, float[] values, string partId = null)
        {
            foreach (var value in values)
            {
                RecordMeasurement(charId, value, partId);
            }
        }

        public InspectionResult PerformInspection(string planId, string partId, Dictionary<string, float> measurements)
        {
            if (!inspectionPlans.TryGetValue(planId, out var plan))
            {
                Debug.LogWarning($"[QualitySPC] Unknown inspection plan: {planId}");
                return null;
            }

            var result = new InspectionResult
            {
                InspectionId = Guid.NewGuid().ToString(),
                PlanId = planId,
                PartId = partId,
                Timestamp = DateTime.Now,
                IsConforming = true
            };

            foreach (var charId in plan.CharacteristicIds)
            {
                if (measurements.TryGetValue(charId, out var value))
                {
                    RecordMeasurement(charId, value, partId);

                    var characteristic = characteristics[charId];
                    bool conforming = value >= characteristic.LowerSpec && value <= characteristic.UpperSpec;

                    if (conforming)
                        result.ConformingCount++;
                    else
                    {
                        result.NonConformingCount++;
                        result.IsConforming = false;
                    }
                }
            }

            result.Disposition = result.IsConforming ? "Accept" : "Reject";
            stats.TotalInspections++;

            OnInspectionComplete?.Invoke(result);
            return result;
        }

        #endregion
    }
}
