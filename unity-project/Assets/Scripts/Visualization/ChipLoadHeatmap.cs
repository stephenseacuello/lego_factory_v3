using System;
using System.Collections.Generic;
using UnityEngine;
using CNCScada.Machining;

namespace CNCScada.Visualization
{
    /// <summary>
    /// Visualizes chip load distribution as a color-coded heatmap on the cutting tool.
    /// Provides real-time visual feedback on chip load intensity per flute.
    /// Part of Feature 2.2: Chip Load Heatmaps (MEDIUM PRIORITY)
    /// </summary>
    [RequireComponent(typeof(ChipLoadCalculator))]
    public class ChipLoadHeatmap : MonoBehaviour
    {
        [Header("Heatmap Configuration")]
        [SerializeField] private GameObject toolObject;
        [SerializeField] private bool enable3DHeatmap = true;
        [SerializeField] private bool enableGizmos = true;

        [Header("Color Mapping")]
        [SerializeField] private Gradient chipLoadGradient;
        [SerializeField] private Color optimalColor = Color.green;
        [SerializeField] private Color lowColor = Color.blue;
        [SerializeField] private Color highColor = Color.yellow;
        [SerializeField] private Color criticalColor = Color.red;

        [Header("Visualization Settings")]
        [SerializeField] private float heatmapIntensity = 1f;
        [SerializeField] private float updateRate = 10f; // Hz
        [SerializeField] private bool smoothTransitions = true;
        [SerializeField] private float transitionSpeed = 5f;

        [Header("Flute Visualization")]
        [SerializeField] private bool showPerFlute = true;
        [SerializeField] private float fluteAngleOffset = 0f;
        [SerializeField] private float fluteVisualizationRadius = 0.5f;

        // References
        private ChipLoadCalculator chipLoadCalculator;
        private Renderer toolRenderer;
        private Material heatmapMaterial;

        // Heatmap data
        private float[] fluteChipLoads;
        private Color[] fluteColors;
        private float currentHeatmapValue = 0f;
        private Color currentHeatmapColor = Color.green;
        private Color targetHeatmapColor = Color.green;

        // Update timing
        private float updateTimer = 0f;
        private float updateInterval = 0.1f;

        // Flute positions for visualization
        private Vector3[] flutePositions;
        private Quaternion[] fluteRotations;

        // Events
        public event Action<HeatmapData> OnHeatmapUpdated;

        // Statistics
        private int heatmapUpdates = 0;
        private Dictionary<string, int> colorZoneCount = new Dictionary<string, int>
        {
            { "optimal", 0 },
            { "low", 0 },
            { "high", 0 },
            { "critical", 0 }
        };

        void Start()
        {
            InitializeHeatmap();
        }

        void Update()
        {
            updateTimer += Time.deltaTime;
            if (updateTimer >= updateInterval)
            {
                UpdateHeatmap();
                updateTimer = 0f;
            }

            // Smooth color transitions
            if (smoothTransitions)
            {
                currentHeatmapColor = Color.Lerp(currentHeatmapColor, targetHeatmapColor,
                    Time.deltaTime * transitionSpeed);
                ApplyHeatmapColor();
            }
        }

        void OnDrawGizmos()
        {
            if (!enableGizmos || !Application.isPlaying) return;

            DrawFluteHeatmapGizmos();
        }

        /// <summary>
        /// Initialize heatmap system
        /// </summary>
        private void InitializeHeatmap()
        {
            // Get chip load calculator
            chipLoadCalculator = GetComponent<ChipLoadCalculator>();
            if (chipLoadCalculator == null)
            {
                Debug.LogError("[ChipLoadHeatmap] ChipLoadCalculator not found!");
                enabled = false;
                return;
            }

            // Subscribe to chip load updates
            chipLoadCalculator.OnChipLoadUpdated += OnChipLoadCalculated;

            // Get tool renderer
            if (toolObject != null)
            {
                toolRenderer = toolObject.GetComponent<Renderer>();
                if (toolRenderer != null)
                {
                    // Create instance material for heatmap
                    heatmapMaterial = new Material(toolRenderer.material);
                    toolRenderer.material = heatmapMaterial;
                }
            }

            // Initialize color gradient if not set
            if (chipLoadGradient == null)
            {
                chipLoadGradient = new Gradient();
                var colorKeys = new GradientColorKey[4];
                colorKeys[0] = new GradientColorKey(lowColor, 0f);
                colorKeys[1] = new GradientColorKey(optimalColor, 0.5f);
                colorKeys[2] = new GradientColorKey(highColor, 0.75f);
                colorKeys[3] = new GradientColorKey(criticalColor, 1f);

                var alphaKeys = new GradientAlphaKey[2];
                alphaKeys[0] = new GradientAlphaKey(1f, 0f);
                alphaKeys[1] = new GradientAlphaKey(1f, 1f);

                chipLoadGradient.SetKeys(colorKeys, alphaKeys);
            }

            // Calculate update interval from rate
            updateInterval = 1f / updateRate;

            // Initialize flute arrays
            int fluteCount = chipLoadCalculator.NumberOfFlutes;
            fluteChipLoads = new float[fluteCount];
            fluteColors = new Color[fluteCount];
            flutePositions = new Vector3[fluteCount];
            fluteRotations = new Quaternion[fluteCount];

            CalculateFlutePositions();

            Debug.Log($"[ChipLoadHeatmap] Initialized with {fluteCount} flutes");
        }

        /// <summary>
        /// Calculate positions for flute visualization
        /// </summary>
        private void CalculateFlutePositions()
        {
            int fluteCount = fluteChipLoads.Length;
            float angleStep = 360f / fluteCount;

            for (int i = 0; i < fluteCount; i++)
            {
                float angle = (i * angleStep + fluteAngleOffset) * Mathf.Deg2Rad;
                flutePositions[i] = new Vector3(
                    Mathf.Cos(angle) * fluteVisualizationRadius,
                    0f,
                    Mathf.Sin(angle) * fluteVisualizationRadius
                );
                fluteRotations[i] = Quaternion.Euler(0, i * angleStep + fluteAngleOffset, 0);
            }
        }

        /// <summary>
        /// Update heatmap visualization
        /// </summary>
        private void UpdateHeatmap()
        {
            if (chipLoadCalculator == null) return;

            // Get chip load distribution
            fluteChipLoads = chipLoadCalculator.GetChipLoadDistribution();

            // Calculate colors for each flute
            var optimalRange = chipLoadCalculator.GetStatistics().OptimalRange;
            float totalChipLoad = 0f;

            for (int i = 0; i < fluteChipLoads.Length; i++)
            {
                float chipLoad = fluteChipLoads[i];
                totalChipLoad += chipLoad;

                // Calculate normalized value (0 = low, 0.5 = optimal, 1 = critical)
                float normalizedValue = CalculateNormalizedChipLoad(chipLoad, optimalRange);
                fluteColors[i] = chipLoadGradient.Evaluate(normalizedValue);

                // Update statistics
                UpdateColorZoneStats(chipLoad, optimalRange);
            }

            // Calculate average chip load for overall heatmap
            float avgChipLoad = totalChipLoad / fluteChipLoads.Length;
            currentHeatmapValue = CalculateNormalizedChipLoad(avgChipLoad, optimalRange);
            targetHeatmapColor = chipLoadGradient.Evaluate(currentHeatmapValue);

            if (!smoothTransitions)
            {
                currentHeatmapColor = targetHeatmapColor;
                ApplyHeatmapColor();
            }

            heatmapUpdates++;

            // Trigger event
            OnHeatmapUpdated?.Invoke(new HeatmapData
            {
                FluteChipLoads = fluteChipLoads,
                FluteColors = fluteColors,
                AverageChipLoad = avgChipLoad,
                NormalizedValue = currentHeatmapValue,
                CurrentColor = currentHeatmapColor,
                IsOptimal = chipLoadCalculator.GetStatistics().IsOptimal,
                Timestamp = DateTime.UtcNow
            });
        }

        /// <summary>
        /// Calculate normalized chip load value for color mapping
        /// </summary>
        private float CalculateNormalizedChipLoad(float chipLoad, Vector2 optimalRange)
        {
            float optimalMid = (optimalRange.x + optimalRange.y) / 2f;
            float optimalWidth = optimalRange.y - optimalRange.x;

            if (chipLoad < optimalRange.x)
            {
                // Below optimal - map to 0.0 to 0.5
                float deviation = (optimalRange.x - chipLoad) / optimalRange.x;
                return Mathf.Clamp01(0.5f - (deviation * 0.5f));
            }
            else if (chipLoad > optimalRange.y)
            {
                // Above optimal - map to 0.5 to 1.0
                float deviation = (chipLoad - optimalRange.y) / optimalRange.y;
                return Mathf.Clamp01(0.5f + (deviation * 0.5f));
            }
            else
            {
                // Within optimal range - map to around 0.5 (green zone)
                return 0.5f;
            }
        }

        /// <summary>
        /// Update color zone statistics
        /// </summary>
        private void UpdateColorZoneStats(float chipLoad, Vector2 optimalRange)
        {
            if (chipLoad < optimalRange.x * 0.5f)
            {
                colorZoneCount["critical"]++;
            }
            else if (chipLoad < optimalRange.x)
            {
                colorZoneCount["low"]++;
            }
            else if (chipLoad <= optimalRange.y)
            {
                colorZoneCount["optimal"]++;
            }
            else if (chipLoad <= optimalRange.y * 1.5f)
            {
                colorZoneCount["high"]++;
            }
            else
            {
                colorZoneCount["critical"]++;
            }
        }

        /// <summary>
        /// Apply heatmap color to tool material
        /// </summary>
        private void ApplyHeatmapColor()
        {
            if (heatmapMaterial != null && enable3DHeatmap)
            {
                Color emissionColor = currentHeatmapColor * heatmapIntensity;
                heatmapMaterial.SetColor("_EmissionColor", emissionColor);
                heatmapMaterial.EnableKeyword("_EMISSION");

                // Also apply to base color with reduced intensity
                Color baseColor = Color.Lerp(Color.white, currentHeatmapColor, 0.5f);
                heatmapMaterial.SetColor("_Color", baseColor);
            }
        }

        /// <summary>
        /// Draw flute heatmap gizmos
        /// </summary>
        private void DrawFluteHeatmapGizmos()
        {
            if (!showPerFlute || fluteChipLoads == null) return;

            for (int i = 0; i < fluteChipLoads.Length; i++)
            {
                Vector3 worldPos = transform.TransformPoint(flutePositions[i]);

                // Draw colored sphere for each flute
                Gizmos.color = fluteColors[i];
                Gizmos.DrawSphere(worldPos, 0.1f);

                // Draw line from center to flute position
                Gizmos.color = fluteColors[i] * 0.5f;
                Gizmos.DrawLine(transform.position, worldPos);

                // Draw flute number
                #if UNITY_EDITOR
                UnityEditor.Handles.Label(worldPos + Vector3.up * 0.2f,
                    $"F{i + 1}\n{fluteChipLoads[i]:F4}");
                #endif
            }

            // Draw center indicator
            Gizmos.color = currentHeatmapColor;
            Gizmos.DrawWireSphere(transform.position, fluteVisualizationRadius * 0.2f);
        }

        /// <summary>
        /// Handle chip load calculation updates
        /// </summary>
        private void OnChipLoadCalculated(ChipLoadData data)
        {
            // Additional processing can be done here if needed
        }

        /// <summary>
        /// Set heatmap intensity
        /// </summary>
        public void SetIntensity(float intensity)
        {
            heatmapIntensity = Mathf.Clamp01(intensity);
            ApplyHeatmapColor();
        }

        /// <summary>
        /// Enable/disable 3D heatmap
        /// </summary>
        public void SetHeatmapEnabled(bool enabled)
        {
            enable3DHeatmap = enabled;

            if (!enabled && heatmapMaterial != null)
            {
                // Reset material to default
                heatmapMaterial.SetColor("_Color", Color.white);
                heatmapMaterial.SetColor("_EmissionColor", Color.black);
            }
        }

        /// <summary>
        /// Get heatmap statistics
        /// </summary>
        public HeatmapStatistics GetStatistics()
        {
            return new HeatmapStatistics
            {
                TotalUpdates = heatmapUpdates,
                CurrentColor = currentHeatmapColor,
                CurrentValue = currentHeatmapValue,
                OptimalCount = colorZoneCount["optimal"],
                LowCount = colorZoneCount["low"],
                HighCount = colorZoneCount["high"],
                CriticalCount = colorZoneCount["critical"],
                UpdateRate = updateRate
            };
        }

        /// <summary>
        /// Reset heatmap statistics
        /// </summary>
        public void ResetStatistics()
        {
            heatmapUpdates = 0;
            foreach (var key in new List<string>(colorZoneCount.Keys))
            {
                colorZoneCount[key] = 0;
            }
        }

        void OnDestroy()
        {
            if (chipLoadCalculator != null)
            {
                chipLoadCalculator.OnChipLoadUpdated -= OnChipLoadCalculated;
            }

            if (heatmapMaterial != null)
            {
                Destroy(heatmapMaterial);
            }
        }

        #region Public Properties

        public float CurrentHeatmapValue => currentHeatmapValue;
        public Color CurrentHeatmapColor => currentHeatmapColor;
        public float[] FluteChipLoads => fluteChipLoads;
        public Color[] FluteColors => fluteColors;
        public bool IsEnabled => enable3DHeatmap;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Heatmap visualization data
    /// </summary>
    [Serializable]
    public struct HeatmapData
    {
        public float[] FluteChipLoads;
        public Color[] FluteColors;
        public float AverageChipLoad;
        public float NormalizedValue;
        public Color CurrentColor;
        public bool IsOptimal;
        public DateTime Timestamp;
    }

    /// <summary>
    /// Heatmap statistics
    /// </summary>
    [Serializable]
    public struct HeatmapStatistics
    {
        public int TotalUpdates;
        public Color CurrentColor;
        public float CurrentValue;
        public int OptimalCount;
        public int LowCount;
        public int HighCount;
        public int CriticalCount;
        public float UpdateRate;
    }

    #endregion
}
