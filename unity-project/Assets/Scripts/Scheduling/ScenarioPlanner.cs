using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCScada.Scheduling
{
    /// <summary>
    /// Production scenario planning and "what-if" analysis.
    /// Allows creating, comparing, and evaluating different production scenarios.
    /// Part of Feature 4.2: Scenario Planning (MEDIUM PRIORITY - Phase 4)
    /// </summary>
    public class ScenarioPlanner : MonoBehaviour
    {
        [Header("Scenario Configuration")]
        [SerializeField] private int maxScenariosPerSession = 5;
        [SerializeField] private bool enableParallelEvaluation = true;

        [Header("Evaluation Metrics")]
        [SerializeField] private bool evaluateCost = true;
        [SerializeField] private bool evaluateLeadTime = true;
        [SerializeField] private bool evaluateQuality = true;
        [SerializeField] private bool evaluateResourceUtilization = true;

        // Scenario storage
        private List<ProductionScenario> scenarios = new List<ProductionScenario>();
        private ProductionScenario baselineScenario;
        private ProductionScenario currentScenario;

        // Events
        public event Action<ProductionScenario> OnScenarioCreated;
        public event Action<ProductionScenario> OnScenarioEvaluated;
        public event Action<ScenarioComparison> OnScenariosCompared;

        // Statistics
        private int totalScenariosCreated = 0;
        private int totalComparisons = 0;

        void Start()
        {
            InitializePlanner();
        }

        /// <summary>
        /// Initialize scenario planner
        /// </summary>
        private void InitializePlanner()
        {
            Debug.Log("[ScenarioPlanner] Initialized");
        }

        /// <summary>
        /// Create a new production scenario
        /// </summary>
        public ProductionScenario CreateScenario(string scenarioName, string description)
        {
            if (scenarios.Count >= maxScenariosPerSession)
            {
                Debug.LogWarning($"[ScenarioPlanner] Maximum scenarios reached ({maxScenariosPerSession})");
                return null;
            }

            var scenario = new ProductionScenario
            {
                ScenarioId = Guid.NewGuid().ToString(),
                Name = scenarioName,
                Description = description,
                CreatedTime = DateTime.UtcNow,
                Status = ScenarioStatus.Draft,
                Parameters = new ScenarioParameters(),
                Results = new ScenarioResults()
            };

            scenarios.Add(scenario);
            totalScenariosCreated++;

            OnScenarioCreated?.Invoke(scenario);

            Debug.Log($"[ScenarioPlanner] Scenario created: {scenarioName}");
            return scenario;
        }

        /// <summary>
        /// Set scenario as baseline for comparison
        /// </summary>
        public void SetBaselineScenario(string scenarioId)
        {
            var scenario = scenarios.Find(s => s.ScenarioId == scenarioId);
            if (scenario != null)
            {
                baselineScenario = scenario;
                scenario.IsBaseline = true;
                Debug.Log($"[ScenarioPlanner] Baseline scenario set: {scenario.Name}");
            }
        }

        /// <summary>
        /// Configure scenario parameters
        /// </summary>
        public void ConfigureScenario(string scenarioId, ScenarioParameters parameters)
        {
            var scenario = scenarios.Find(s => s.ScenarioId == scenarioId);
            if (scenario != null)
            {
                scenario.Parameters = parameters;
                scenario.Status = ScenarioStatus.Configured;
                Debug.Log($"[ScenarioPlanner] Scenario configured: {scenario.Name}");
            }
        }

        /// <summary>
        /// Add production jobs to scenario
        /// </summary>
        public void AddJobsToScenario(string scenarioId, List<ScenarioJob> jobs)
        {
            var scenario = scenarios.Find(s => s.ScenarioId == scenarioId);
            if (scenario != null)
            {
                scenario.Jobs = jobs;
                Debug.Log($"[ScenarioPlanner] Added {jobs.Count} jobs to scenario: {scenario.Name}");
            }
        }

        /// <summary>
        /// Add machine configuration to scenario
        /// </summary>
        public void AddMachinesToScenario(string scenarioId, List<ScenarioMachine> machines)
        {
            var scenario = scenarios.Find(s => s.ScenarioId == scenarioId);
            if (scenario != null)
            {
                scenario.Machines = machines;
                Debug.Log($"[ScenarioPlanner] Added {machines.Count} machines to scenario: {scenario.Name}");
            }
        }

        /// <summary>
        /// Evaluate a production scenario
        /// </summary>
        public void EvaluateScenario(string scenarioId)
        {
            var scenario = scenarios.Find(s => s.ScenarioId == scenarioId);
            if (scenario == null)
            {
                Debug.LogError($"[ScenarioPlanner] Scenario not found: {scenarioId}");
                return;
            }

            var startTime = Time.realtimeSinceStartup;

            // Calculate metrics
            scenario.Results = new ScenarioResults();

            if (evaluateCost)
            {
                scenario.Results.TotalCost = CalculateTotalCost(scenario);
                scenario.Results.BreakdownCosts = CalculateCostBreakdown(scenario);
            }

            if (evaluateLeadTime)
            {
                scenario.Results.TotalLeadTime = CalculateTotalLeadTime(scenario);
                scenario.Results.MaxLeadTime = CalculateMaxLeadTime(scenario);
                scenario.Results.AverageLeadTime = CalculateAverageLeadTime(scenario);
            }

            if (evaluateQuality)
            {
                scenario.Results.ExpectedYield = CalculateExpectedYield(scenario);
                scenario.Results.QualityScore = CalculateQualityScore(scenario);
            }

            if (evaluateResourceUtilization)
            {
                scenario.Results.MachineUtilization = CalculateMachineUtilization(scenario);
                scenario.Results.LaborUtilization = CalculateLaborUtilization(scenario);
            }

            // Additional metrics
            scenario.Results.Makespan = CalculateMakespan(scenario);
            scenario.Results.ThroughputRate = CalculateThroughput(scenario);
            scenario.Results.BottleneckMachine = IdentifyBottleneck(scenario);

            scenario.Status = ScenarioStatus.Evaluated;
            scenario.EvaluatedTime = DateTime.UtcNow;

            var evaluationTime = (Time.realtimeSinceStartup - startTime) * 1000f;

            OnScenarioEvaluated?.Invoke(scenario);

            Debug.Log($"[ScenarioPlanner] Scenario evaluated: {scenario.Name}, " +
                     $"Cost: ${scenario.Results.TotalCost:F2}, " +
                     $"Lead Time: {scenario.Results.TotalLeadTime:F1}h, " +
                     $"Evaluation time: {evaluationTime:F1}ms");
        }

        /// <summary>
        /// Compare two scenarios
        /// </summary>
        public ScenarioComparison CompareScenarios(string scenarioId1, string scenarioId2)
        {
            var scenario1 = scenarios.Find(s => s.ScenarioId == scenarioId1);
            var scenario2 = scenarios.Find(s => s.ScenarioId == scenarioId2);

            if (scenario1 == null || scenario2 == null)
            {
                Debug.LogError("[ScenarioPlanner] Invalid scenario IDs for comparison");
                return null;
            }

            if (scenario1.Status != ScenarioStatus.Evaluated || scenario2.Status != ScenarioStatus.Evaluated)
            {
                Debug.LogWarning("[ScenarioPlanner] Both scenarios must be evaluated before comparison");
                return null;
            }

            var comparison = new ScenarioComparison
            {
                ComparisonId = Guid.NewGuid().ToString(),
                Scenario1Id = scenarioId1,
                Scenario2Id = scenarioId2,
                Scenario1Name = scenario1.Name,
                Scenario2Name = scenario2.Name,
                ComparisonTime = DateTime.UtcNow
            };

            // Cost comparison
            comparison.CostDelta = scenario2.Results.TotalCost - scenario1.Results.TotalCost;
            comparison.CostChangePercent = (comparison.CostDelta / scenario1.Results.TotalCost) * 100f;

            // Lead time comparison
            comparison.LeadTimeDelta = scenario2.Results.TotalLeadTime - scenario1.Results.TotalLeadTime;
            comparison.LeadTimeChangePercent = (comparison.LeadTimeDelta / scenario1.Results.TotalLeadTime) * 100f;

            // Quality comparison
            comparison.YieldDelta = scenario2.Results.ExpectedYield - scenario1.Results.ExpectedYield;

            // Utilization comparison
            comparison.UtilizationDelta = scenario2.Results.MachineUtilization - scenario1.Results.MachineUtilization;

            // Identify trade-offs
            comparison.TradeOffs = IdentifyTradeOffs(scenario1, scenario2);

            // Overall recommendation
            comparison.RecommendedScenario = DetermineRecommendedScenario(scenario1, scenario2);

            totalComparisons++;
            OnScenariosCompared?.Invoke(comparison);

            Debug.Log($"[ScenarioPlanner] Scenarios compared: {scenario1.Name} vs {scenario2.Name}");
            return comparison;
        }

        /// <summary>
        /// Compare all scenarios against baseline
        /// </summary>
        public List<ScenarioComparison> CompareAgainstBaseline()
        {
            if (baselineScenario == null)
            {
                Debug.LogWarning("[ScenarioPlanner] No baseline scenario set");
                return new List<ScenarioComparison>();
            }

            var comparisons = new List<ScenarioComparison>();

            foreach (var scenario in scenarios)
            {
                if (scenario.ScenarioId != baselineScenario.ScenarioId &&
                    scenario.Status == ScenarioStatus.Evaluated)
                {
                    var comparison = CompareScenarios(baselineScenario.ScenarioId, scenario.ScenarioId);
                    if (comparison != null)
                    {
                        comparisons.Add(comparison);
                    }
                }
            }

            return comparisons;
        }

        #region Calculation Methods

        private float CalculateTotalCost(ProductionScenario scenario)
        {
            float cost = 0f;

            // Material cost
            foreach (var job in scenario.Jobs)
            {
                cost += job.MaterialCostPerUnit * job.Quantity;
            }

            // Labor cost
            float totalHours = scenario.Results.TotalLeadTime;
            cost += totalHours * scenario.Parameters.LaborCostPerHour;

            // Machine cost
            foreach (var machine in scenario.Machines)
            {
                cost += machine.OperatingCostPerHour * totalHours / scenario.Machines.Count;
            }

            return cost;
        }

        private Dictionary<string, float> CalculateCostBreakdown(ProductionScenario scenario)
        {
            var breakdown = new Dictionary<string, float>();

            breakdown["material"] = scenario.Jobs.Sum(j => j.MaterialCostPerUnit * j.Quantity);
            breakdown["labor"] = scenario.Results.TotalLeadTime * scenario.Parameters.LaborCostPerHour;
            breakdown["machine"] = scenario.Machines.Sum(m => m.OperatingCostPerHour * scenario.Results.TotalLeadTime / scenario.Machines.Count);
            breakdown["overhead"] = scenario.Results.TotalCost * 0.15f; // 15% overhead

            return breakdown;
        }

        private float CalculateTotalLeadTime(ProductionScenario scenario)
        {
            float totalTime = 0f;

            foreach (var job in scenario.Jobs)
            {
                totalTime += job.CycleTimeMinutes * job.Quantity / 60f; // Convert to hours
            }

            // Factor in machine availability
            totalTime /= Mathf.Max(scenario.Parameters.MachineAvailability, 0.1f);

            return totalTime;
        }

        private float CalculateMaxLeadTime(ProductionScenario scenario)
        {
            if (scenario.Jobs.Count == 0) return 0f;
            return scenario.Jobs.Max(j => j.CycleTimeMinutes * j.Quantity / 60f);
        }

        private float CalculateAverageLeadTime(ProductionScenario scenario)
        {
            if (scenario.Jobs.Count == 0) return 0f;
            return scenario.Jobs.Average(j => j.CycleTimeMinutes * j.Quantity / 60f);
        }

        private float CalculateExpectedYield(ProductionScenario scenario)
        {
            if (scenario.Jobs.Count == 0) return 1.0f;
            return scenario.Jobs.Average(j => j.ExpectedYield);
        }

        private float CalculateQualityScore(ProductionScenario scenario)
        {
            return scenario.Results.ExpectedYield * scenario.Parameters.QualityStandard;
        }

        private float CalculateMachineUtilization(ProductionScenario scenario)
        {
            return scenario.Parameters.MachineAvailability *
                   Mathf.Clamp01(scenario.Results.TotalLeadTime / (scenario.Machines.Count * 40f)); // 40h work week
        }

        private float CalculateLaborUtilization(ProductionScenario scenario)
        {
            return scenario.Parameters.LaborEfficiency;
        }

        private float CalculateMakespan(ProductionScenario scenario)
        {
            return scenario.Results.TotalLeadTime;
        }

        private float CalculateThroughput(ProductionScenario scenario)
        {
            int totalParts = scenario.Jobs.Sum(j => j.Quantity);
            return totalParts / Mathf.Max(scenario.Results.TotalLeadTime, 0.1f);
        }

        private string IdentifyBottleneck(ProductionScenario scenario)
        {
            if (scenario.Machines.Count == 0) return "None";

            var bottleneck = scenario.Machines.OrderByDescending(m => m.OperatingCostPerHour).First();
            return bottleneck.MachineId;
        }

        private List<string> IdentifyTradeOffs(ProductionScenario scenario1, ProductionScenario scenario2)
        {
            var tradeoffs = new List<string>();

            // Cost vs Speed
            if (scenario2.Results.TotalCost < scenario1.Results.TotalCost &&
                scenario2.Results.TotalLeadTime > scenario1.Results.TotalLeadTime)
            {
                tradeoffs.Add("Lower cost but longer lead time");
            }
            else if (scenario2.Results.TotalCost > scenario1.Results.TotalCost &&
                     scenario2.Results.TotalLeadTime < scenario1.Results.TotalLeadTime)
            {
                tradeoffs.Add("Higher cost but faster delivery");
            }

            // Quality vs Cost
            if (scenario2.Results.ExpectedYield > scenario1.Results.ExpectedYield &&
                scenario2.Results.TotalCost > scenario1.Results.TotalCost)
            {
                tradeoffs.Add("Higher quality but increased cost");
            }

            // Utilization vs Flexibility
            if (scenario2.Results.MachineUtilization > scenario1.Results.MachineUtilization * 1.1f)
            {
                tradeoffs.Add("Higher utilization may reduce scheduling flexibility");
            }

            return tradeoffs;
        }

        private string DetermineRecommendedScenario(ProductionScenario scenario1, ProductionScenario scenario2)
        {
            // Simple scoring system (customizable)
            float score1 = 0f;
            float score2 = 0f;

            // Cost factor (lower is better)
            score1 += (1f / scenario1.Results.TotalCost) * 100f;
            score2 += (1f / scenario2.Results.TotalCost) * 100f;

            // Lead time factor (lower is better)
            score1 += (1f / scenario1.Results.TotalLeadTime) * 50f;
            score2 += (1f / scenario2.Results.TotalLeadTime) * 50f;

            // Quality factor (higher is better)
            score1 += scenario1.Results.ExpectedYield * 30f;
            score2 += scenario2.Results.ExpectedYield * 30f;

            // Utilization factor (higher is better)
            score1 += scenario1.Results.MachineUtilization * 20f;
            score2 += scenario2.Results.MachineUtilization * 20f;

            return score2 > score1 ? scenario2.ScenarioId : scenario1.ScenarioId;
        }

        #endregion

        /// <summary>
        /// Delete scenario
        /// </summary>
        public void DeleteScenario(string scenarioId)
        {
            var scenario = scenarios.Find(s => s.ScenarioId == scenarioId);
            if (scenario != null)
            {
                scenarios.Remove(scenario);
                Debug.Log($"[ScenarioPlanner] Scenario deleted: {scenario.Name}");
            }
        }

        /// <summary>
        /// Get scenario statistics
        /// </summary>
        public PlannerStatistics GetStatistics()
        {
            return new PlannerStatistics
            {
                TotalScenariosCreated = totalScenariosCreated,
                ActiveScenarios = scenarios.Count,
                EvaluatedScenarios = scenarios.Count(s => s.Status == ScenarioStatus.Evaluated),
                TotalComparisons = totalComparisons,
                HasBaseline = baselineScenario != null
            };
        }

        #region Public Properties

        public int ScenarioCount => scenarios.Count;
        public List<ProductionScenario> AllScenarios => new List<ProductionScenario>(scenarios);
        public ProductionScenario BaselineScenario => baselineScenario;

        #endregion
    }

    #region Data Structures

    [Serializable]
    public class ProductionScenario
    {
        public string ScenarioId;
        public string Name;
        public string Description;
        public DateTime CreatedTime;
        public DateTime? EvaluatedTime;
        public ScenarioStatus Status;
        public bool IsBaseline;
        public ScenarioParameters Parameters;
        public List<ScenarioJob> Jobs;
        public List<ScenarioMachine> Machines;
        public ScenarioResults Results;
    }

    [Serializable]
    public class ScenarioParameters
    {
        public float MachineAvailability = 0.95f;
        public float LaborEfficiency = 0.85f;
        public float QualityStandard = 0.99f;
        public float LaborCostPerHour = 35f;
        public int WorkingHoursPerDay = 8;
        public int WorkingDaysPerWeek = 5;
    }

    [Serializable]
    public class ScenarioJob
    {
        public string JobId;
        public string PartNumber;
        public int Quantity;
        public float CycleTimeMinutes;
        public float MaterialCostPerUnit;
        public float ExpectedYield = 0.98f;
    }

    [Serializable]
    public class ScenarioMachine
    {
        public string MachineId;
        public string MachineType;
        public float OperatingCostPerHour;
        public List<string> Capabilities;
    }

    [Serializable]
    public class ScenarioResults
    {
        public float TotalCost;
        public Dictionary<string, float> BreakdownCosts;
        public float TotalLeadTime;
        public float MaxLeadTime;
        public float AverageLeadTime;
        public float ExpectedYield;
        public float QualityScore;
        public float MachineUtilization;
        public float LaborUtilization;
        public float Makespan;
        public float ThroughputRate;
        public string BottleneckMachine;
    }

    [Serializable]
    public class ScenarioComparison
    {
        public string ComparisonId;
        public string Scenario1Id;
        public string Scenario2Id;
        public string Scenario1Name;
        public string Scenario2Name;
        public DateTime ComparisonTime;
        public float CostDelta;
        public float CostChangePercent;
        public float LeadTimeDelta;
        public float LeadTimeChangePercent;
        public float YieldDelta;
        public float UtilizationDelta;
        public List<string> TradeOffs;
        public string RecommendedScenario;
    }

    [Serializable]
    public struct PlannerStatistics
    {
        public int TotalScenariosCreated;
        public int ActiveScenarios;
        public int EvaluatedScenarios;
        public int TotalComparisons;
        public bool HasBaseline;
    }

    public enum ScenarioStatus
    {
        Draft,
        Configured,
        Evaluated,
        Archived
    }

    #endregion
}
