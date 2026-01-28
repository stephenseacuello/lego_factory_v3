using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Machining
{
    /// <summary>
    /// Calculates chip load (feed per tooth) for machining operations.
    /// Chip load = Feed Rate / (Spindle Speed × Number of Flutes)
    /// Part of Feature 2.2: Chip Load Heatmaps (MEDIUM PRIORITY)
    /// </summary>
    public class ChipLoadCalculator : MonoBehaviour
    {
        [Header("Cutting Parameters")]
        [SerializeField] private float feedRate = 1000f; // mm/min
        [SerializeField] private float spindleSpeed = 12000f; // RPM
        [SerializeField] private int numberOfFlutes = 4;
        [SerializeField] private float toolDiameter = 6f; // mm

        [Header("Material Properties")]
        [SerializeField] private MaterialType materialType = MaterialType.Aluminum;
        [SerializeField] private float hardness = 50f; // HRC or similar

        [Header("Calculation Settings")]
        [SerializeField] private bool autoUpdate = true;
        [SerializeField] private float updateInterval = 0.1f;

        // Calculated values
        private float currentChipLoad = 0f;
        private float currentChipThickness = 0f;
        private float currentMaterialRemovalRate = 0f;
        private float updateTimer = 0f;

        // Optimal chip load ranges (mm/tooth) by material
        private Dictionary<MaterialType, Vector2> optimalChipLoadRanges = new Dictionary<MaterialType, Vector2>
        {
            { MaterialType.Aluminum, new Vector2(0.05f, 0.15f) },
            { MaterialType.Steel, new Vector2(0.03f, 0.10f) },
            { MaterialType.Stainless, new Vector2(0.025f, 0.08f) },
            { MaterialType.Titanium, new Vector2(0.02f, 0.06f) },
            { MaterialType.Plastic, new Vector2(0.08f, 0.20f) },
            { MaterialType.Wood, new Vector2(0.10f, 0.25f) }
        };

        // Events
        public event Action<ChipLoadData> OnChipLoadUpdated;
        public event Action<ChipLoadWarning> OnChipLoadWarning;

        // Statistics
        private float minChipLoad = float.MaxValue;
        private float maxChipLoad = float.MinValue;
        private float avgChipLoad = 0f;
        private int totalCalculations = 0;

        void Start()
        {
            CalculateChipLoad();
        }

        void Update()
        {
            if (!autoUpdate) return;

            updateTimer += Time.deltaTime;
            if (updateTimer >= updateInterval)
            {
                CalculateChipLoad();
                updateTimer = 0f;
            }
        }

        /// <summary>
        /// Calculate chip load and related parameters
        /// </summary>
        public void CalculateChipLoad()
        {
            if (spindleSpeed <= 0 || numberOfFlutes <= 0)
            {
                Debug.LogWarning("[ChipLoad] Invalid parameters for chip load calculation");
                return;
            }

            // Calculate chip load (feed per tooth)
            // Formula: Chip Load = Feed Rate / (Spindle Speed × Number of Flutes)
            currentChipLoad = feedRate / (spindleSpeed * numberOfFlutes);

            // Calculate chip thickness (simplified - assumes full engagement)
            // Actual chip thickness varies with depth of cut and radial engagement
            currentChipThickness = currentChipLoad;

            // Calculate material removal rate (MRR)
            // MRR = Feed Rate × Depth of Cut × Width of Cut
            // For simplification, we estimate based on feed rate and tool diameter
            float estimatedDepthOfCut = toolDiameter * 0.1f; // 10% of diameter (conservative)
            float estimatedWidthOfCut = toolDiameter * 0.5f; // 50% engagement
            currentMaterialRemovalRate = feedRate * estimatedDepthOfCut * estimatedWidthOfCut;

            // Update statistics
            minChipLoad = Mathf.Min(minChipLoad, currentChipLoad);
            maxChipLoad = Mathf.Max(maxChipLoad, currentChipLoad);
            totalCalculations++;
            avgChipLoad = ((avgChipLoad * (totalCalculations - 1)) + currentChipLoad) / totalCalculations;

            // Check for warnings
            CheckChipLoadWarnings();

            // Trigger event
            var chipLoadData = new ChipLoadData
            {
                ChipLoad = currentChipLoad,
                ChipThickness = currentChipThickness,
                MaterialRemovalRate = currentMaterialRemovalRate,
                FeedRate = feedRate,
                SpindleSpeed = spindleSpeed,
                NumberOfFlutes = numberOfFlutes,
                ToolDiameter = toolDiameter,
                IsOptimal = IsChipLoadOptimal(),
                OptimalRange = GetOptimalRange(),
                Timestamp = DateTime.UtcNow
            };

            OnChipLoadUpdated?.Invoke(chipLoadData);
        }

        /// <summary>
        /// Check if current chip load is within optimal range
        /// </summary>
        private bool IsChipLoadOptimal()
        {
            if (!optimalChipLoadRanges.ContainsKey(materialType))
                return false;

            var range = optimalChipLoadRanges[materialType];
            return currentChipLoad >= range.x && currentChipLoad <= range.y;
        }

        /// <summary>
        /// Get optimal chip load range for current material
        /// </summary>
        private Vector2 GetOptimalRange()
        {
            if (optimalChipLoadRanges.ContainsKey(materialType))
                return optimalChipLoadRanges[materialType];

            return new Vector2(0.03f, 0.10f); // Default range
        }

        /// <summary>
        /// Check for chip load warnings and trigger events
        /// </summary>
        private void CheckChipLoadWarnings()
        {
            var optimalRange = GetOptimalRange();

            if (currentChipLoad < optimalRange.x)
            {
                // Chip load too low - risk of rubbing and built-up edge
                OnChipLoadWarning?.Invoke(new ChipLoadWarning
                {
                    WarningType = ChipLoadWarningType.TooLow,
                    CurrentValue = currentChipLoad,
                    OptimalRange = optimalRange,
                    Message = "Chip load too low. Risk of rubbing and tool wear.",
                    Severity = ChipLoadSeverity.Medium,
                    Recommendation = "Increase feed rate or decrease spindle speed."
                });
            }
            else if (currentChipLoad > optimalRange.y)
            {
                // Chip load too high - risk of tool breakage
                OnChipLoadWarning?.Invoke(new ChipLoadWarning
                {
                    WarningType = ChipLoadWarningType.TooHigh,
                    CurrentValue = currentChipLoad,
                    OptimalRange = optimalRange,
                    Message = "Chip load too high. Risk of tool breakage.",
                    Severity = ChipLoadSeverity.High,
                    Recommendation = "Decrease feed rate or increase spindle speed."
                });
            }

            // Check for extreme values
            if (currentChipLoad > optimalRange.y * 1.5f)
            {
                OnChipLoadWarning?.Invoke(new ChipLoadWarning
                {
                    WarningType = ChipLoadWarningType.Critical,
                    CurrentValue = currentChipLoad,
                    OptimalRange = optimalRange,
                    Message = "CRITICAL: Chip load extremely high. Stop machining immediately!",
                    Severity = ChipLoadSeverity.Critical,
                    Recommendation = "Emergency stop recommended. Reduce feed rate significantly."
                });
            }
        }

        /// <summary>
        /// Update cutting parameters from external source
        /// </summary>
        public void UpdateParameters(float newFeedRate, float newSpindleSpeed, int newFlutes)
        {
            feedRate = newFeedRate;
            spindleSpeed = newSpindleSpeed;
            numberOfFlutes = newFlutes;
            CalculateChipLoad();
        }

        /// <summary>
        /// Set material type
        /// </summary>
        public void SetMaterial(MaterialType material, float materialHardness)
        {
            materialType = material;
            hardness = materialHardness;
            CalculateChipLoad();
        }

        /// <summary>
        /// Calculate recommended feed rate for optimal chip load
        /// </summary>
        public float CalculateRecommendedFeedRate(float targetChipLoad)
        {
            // Feed Rate = Chip Load × Spindle Speed × Number of Flutes
            return targetChipLoad * spindleSpeed * numberOfFlutes;
        }

        /// <summary>
        /// Calculate recommended spindle speed for optimal chip load
        /// </summary>
        public float CalculateRecommendedSpindleSpeed(float targetChipLoad)
        {
            // Spindle Speed = Feed Rate / (Chip Load × Number of Flutes)
            if (targetChipLoad <= 0 || numberOfFlutes <= 0)
                return spindleSpeed;

            return feedRate / (targetChipLoad * numberOfFlutes);
        }

        /// <summary>
        /// Get chip load distribution across flutes
        /// </summary>
        public float[] GetChipLoadDistribution()
        {
            float[] distribution = new float[numberOfFlutes];

            // In ideal conditions, chip load is evenly distributed
            // In practice, tool runout and deflection can cause variation
            float runoutFactor = 0.05f; // 5% variation due to runout

            for (int i = 0; i < numberOfFlutes; i++)
            {
                // Add small variation to simulate real-world conditions
                float variation = UnityEngine.Random.Range(-runoutFactor, runoutFactor);
                distribution[i] = currentChipLoad * (1f + variation);
            }

            return distribution;
        }

        /// <summary>
        /// Get chip load statistics
        /// </summary>
        public ChipLoadStatistics GetStatistics()
        {
            return new ChipLoadStatistics
            {
                CurrentChipLoad = currentChipLoad,
                MinChipLoad = minChipLoad,
                MaxChipLoad = maxChipLoad,
                AvgChipLoad = avgChipLoad,
                TotalCalculations = totalCalculations,
                IsOptimal = IsChipLoadOptimal(),
                OptimalRange = GetOptimalRange(),
                MaterialType = materialType.ToString(),
                MaterialRemovalRate = currentMaterialRemovalRate
            };
        }

        /// <summary>
        /// Reset statistics
        /// </summary>
        public void ResetStatistics()
        {
            minChipLoad = float.MaxValue;
            maxChipLoad = float.MinValue;
            avgChipLoad = 0f;
            totalCalculations = 0;
        }

        #region Public Properties

        public float CurrentChipLoad => currentChipLoad;
        public float CurrentChipThickness => currentChipThickness;
        public float MaterialRemovalRate => currentMaterialRemovalRate;
        public float FeedRate { get => feedRate; set { feedRate = value; CalculateChipLoad(); } }
        public float SpindleSpeed { get => spindleSpeed; set { spindleSpeed = value; CalculateChipLoad(); } }
        public int NumberOfFlutes { get => numberOfFlutes; set { numberOfFlutes = value; CalculateChipLoad(); } }
        public MaterialType Material => materialType;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Material types for chip load calculation
    /// </summary>
    public enum MaterialType
    {
        Aluminum,
        Steel,
        Stainless,
        Titanium,
        Plastic,
        Wood,
        Composite,
        Brass,
        Copper
    }

    /// <summary>
    /// Chip load data
    /// </summary>
    [Serializable]
    public struct ChipLoadData
    {
        public float ChipLoad;
        public float ChipThickness;
        public float MaterialRemovalRate;
        public float FeedRate;
        public float SpindleSpeed;
        public int NumberOfFlutes;
        public float ToolDiameter;
        public bool IsOptimal;
        public Vector2 OptimalRange;
        public DateTime Timestamp;
    }

    /// <summary>
    /// Chip load warning types
    /// </summary>
    public enum ChipLoadWarningType
    {
        TooLow,
        TooHigh,
        Critical,
        Optimal
    }

    /// <summary>
    /// Warning severity levels
    /// </summary>
    public enum ChipLoadSeverity
    {
        Low,
        Medium,
        High,
        Critical
    }

    /// <summary>
    /// Chip load warning
    /// </summary>
    [Serializable]
    public struct ChipLoadWarning
    {
        public ChipLoadWarningType WarningType;
        public float CurrentValue;
        public Vector2 OptimalRange;
        public string Message;
        public ChipLoadSeverity Severity;
        public string Recommendation;
    }

    /// <summary>
    /// Chip load statistics
    /// </summary>
    [Serializable]
    public struct ChipLoadStatistics
    {
        public float CurrentChipLoad;
        public float MinChipLoad;
        public float MaxChipLoad;
        public float AvgChipLoad;
        public int TotalCalculations;
        public bool IsOptimal;
        public Vector2 OptimalRange;
        public string MaterialType;
        public float MaterialRemovalRate;
    }

    #endregion
}
