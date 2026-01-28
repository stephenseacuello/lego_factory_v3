using UnityEngine;

namespace CNCScada.Visualization
{
    /// <summary>
    /// Maps machining parameters (speed, feed, power) to trail colors.
    /// Provides preset color schemes for different visualization modes.
    /// Part of Feature 1.3: Machine Trail Visualization
    /// </summary>
    public class TrailColorMapper : MonoBehaviour
    {
        public enum ColorScheme
        {
            Speed,          // Blue (slow) -> Red (fast)
            FeedRate,       // Green (low) -> Yellow (high)
            SpindleLoad,    // Cyan (low) -> Magenta (high)
            Temperature,    // Blue (cold) -> Red (hot)
            Custom          // User-defined gradient
        }

        [Header("Color Scheme")]
        [SerializeField] private ColorScheme currentScheme = ColorScheme.Speed;
        [SerializeField] private Gradient customGradient;

        [Header("Value Ranges")]
        [SerializeField] private Vector2 speedRange = new Vector2(0f, 5000f);      // mm/min
        [SerializeField] private Vector2 feedRateRange = new Vector2(0f, 1000f);   // mm/min
        [SerializeField] private Vector2 spindleLoadRange = new Vector2(0f, 100f); // %
        [SerializeField] private Vector2 temperatureRange = new Vector2(20f, 80f); // °C

        private Gradient speedGradient;
        private Gradient feedRateGradient;
        private Gradient spindleLoadGradient;
        private Gradient temperatureGradient;

        void Awake()
        {
            InitializeGradients();
        }

        /// <summary>
        /// Get color for given speed value
        /// </summary>
        public Color GetColorForSpeed(float speed)
        {
            float normalized = Mathf.InverseLerp(speedRange.x, speedRange.y, speed);
            return speedGradient.Evaluate(normalized);
        }

        /// <summary>
        /// Get color for given feed rate
        /// </summary>
        public Color GetColorForFeedRate(float feedRate)
        {
            float normalized = Mathf.InverseLerp(feedRateRange.x, feedRateRange.y, feedRate);
            return feedRateGradient.Evaluate(normalized);
        }

        /// <summary>
        /// Get color for given spindle load
        /// </summary>
        public Color GetColorForSpindleLoad(float load)
        {
            float normalized = Mathf.InverseLerp(spindleLoadRange.x, spindleLoadRange.y, load);
            return spindleLoadGradient.Evaluate(normalized);
        }

        /// <summary>
        /// Get color for given temperature
        /// </summary>
        public Color GetColorForTemperature(float temperature)
        {
            float normalized = Mathf.InverseLerp(temperatureRange.x, temperatureRange.y, temperature);
            return temperatureGradient.Evaluate(normalized);
        }

        /// <summary>
        /// Get color based on current color scheme
        /// </summary>
        public Color GetColor(float value)
        {
            switch (currentScheme)
            {
                case ColorScheme.Speed:
                    return GetColorForSpeed(value);
                case ColorScheme.FeedRate:
                    return GetColorForFeedRate(value);
                case ColorScheme.SpindleLoad:
                    return GetColorForSpindleLoad(value);
                case ColorScheme.Temperature:
                    return GetColorForTemperature(value);
                case ColorScheme.Custom:
                    return GetCustomColor(value);
                default:
                    return Color.white;
            }
        }

        /// <summary>
        /// Get gradient for current color scheme
        /// </summary>
        public Gradient GetCurrentGradient()
        {
            switch (currentScheme)
            {
                case ColorScheme.Speed:
                    return speedGradient;
                case ColorScheme.FeedRate:
                    return feedRateGradient;
                case ColorScheme.SpindleLoad:
                    return spindleLoadGradient;
                case ColorScheme.Temperature:
                    return temperatureGradient;
                case ColorScheme.Custom:
                    return customGradient;
                default:
                    return speedGradient;
            }
        }

        /// <summary>
        /// Set color scheme
        /// </summary>
        public void SetColorScheme(ColorScheme scheme)
        {
            currentScheme = scheme;
            Debug.Log($"[ColorMapper] Color scheme changed to: {scheme}");
        }

        /// <summary>
        /// Set speed range
        /// </summary>
        public void SetSpeedRange(float min, float max)
        {
            speedRange = new Vector2(min, max);
        }

        /// <summary>
        /// Set feed rate range
        /// </summary>
        public void SetFeedRateRange(float min, float max)
        {
            feedRateRange = new Vector2(min, max);
        }

        /// <summary>
        /// Set spindle load range
        /// </summary>
        public void SetSpindleLoadRange(float min, float max)
        {
            spindleLoadRange = new Vector2(min, max);
        }

        /// <summary>
        /// Set temperature range
        /// </summary>
        public void SetTemperatureRange(float min, float max)
        {
            temperatureRange = new Vector2(min, max);
        }

        /// <summary>
        /// Set custom gradient
        /// </summary>
        public void SetCustomGradient(Gradient gradient)
        {
            customGradient = gradient;
            currentScheme = ColorScheme.Custom;
        }

        private Color GetCustomColor(float value)
        {
            if (customGradient == null)
            {
                Debug.LogWarning("[ColorMapper] Custom gradient not set, using speed gradient");
                return GetColorForSpeed(value);
            }

            // Assume value is already normalized 0-1 for custom gradient
            return customGradient.Evaluate(Mathf.Clamp01(value));
        }

        private void InitializeGradients()
        {
            // Speed gradient: Blue (slow) -> Cyan -> Green -> Yellow -> Red (fast)
            speedGradient = new Gradient();
            speedGradient.SetKeys(
                new GradientColorKey[]
                {
                    new GradientColorKey(new Color(0.0f, 0.2f, 1.0f), 0.0f),  // Deep blue
                    new GradientColorKey(new Color(0.0f, 0.8f, 1.0f), 0.25f), // Cyan
                    new GradientColorKey(new Color(0.0f, 1.0f, 0.0f), 0.5f),  // Green
                    new GradientColorKey(new Color(1.0f, 0.9f, 0.0f), 0.75f), // Yellow
                    new GradientColorKey(new Color(1.0f, 0.0f, 0.0f), 1.0f)   // Red
                },
                new GradientAlphaKey[]
                {
                    new GradientAlphaKey(1.0f, 0.0f),
                    new GradientAlphaKey(1.0f, 1.0f)
                }
            );

            // Feed rate gradient: Green (low) -> Yellow (medium) -> Orange (high)
            feedRateGradient = new Gradient();
            feedRateGradient.SetKeys(
                new GradientColorKey[]
                {
                    new GradientColorKey(new Color(0.0f, 1.0f, 0.0f), 0.0f),  // Green
                    new GradientColorKey(new Color(0.5f, 1.0f, 0.0f), 0.33f), // Yellow-green
                    new GradientColorKey(new Color(1.0f, 1.0f, 0.0f), 0.66f), // Yellow
                    new GradientColorKey(new Color(1.0f, 0.5f, 0.0f), 1.0f)   // Orange
                },
                new GradientAlphaKey[]
                {
                    new GradientAlphaKey(1.0f, 0.0f),
                    new GradientAlphaKey(1.0f, 1.0f)
                }
            );

            // Spindle load gradient: Cyan (low) -> Purple (medium) -> Magenta (high)
            spindleLoadGradient = new Gradient();
            spindleLoadGradient.SetKeys(
                new GradientColorKey[]
                {
                    new GradientColorKey(new Color(0.0f, 1.0f, 1.0f), 0.0f),  // Cyan
                    new GradientColorKey(new Color(0.5f, 0.0f, 1.0f), 0.5f),  // Purple
                    new GradientColorKey(new Color(1.0f, 0.0f, 1.0f), 1.0f)   // Magenta
                },
                new GradientAlphaKey[]
                {
                    new GradientAlphaKey(1.0f, 0.0f),
                    new GradientAlphaKey(1.0f, 1.0f)
                }
            );

            // Temperature gradient: Blue (cold) -> White (warm) -> Red (hot)
            temperatureGradient = new Gradient();
            temperatureGradient.SetKeys(
                new GradientColorKey[]
                {
                    new GradientColorKey(new Color(0.0f, 0.2f, 1.0f), 0.0f),  // Cold blue
                    new GradientColorKey(new Color(0.5f, 0.7f, 1.0f), 0.33f), // Light blue
                    new GradientColorKey(new Color(1.0f, 1.0f, 1.0f), 0.5f),  // White
                    new GradientColorKey(new Color(1.0f, 0.5f, 0.0f), 0.75f), // Orange
                    new GradientColorKey(new Color(1.0f, 0.0f, 0.0f), 1.0f)   // Hot red
                },
                new GradientAlphaKey[]
                {
                    new GradientAlphaKey(1.0f, 0.0f),
                    new GradientAlphaKey(1.0f, 1.0f)
                }
            );

            // Initialize custom gradient if not set
            if (customGradient == null)
            {
                customGradient = new Gradient();
                customGradient.SetKeys(
                    new GradientColorKey[]
                    {
                        new GradientColorKey(Color.white, 0.0f),
                        new GradientColorKey(Color.white, 1.0f)
                    },
                    new GradientAlphaKey[]
                    {
                        new GradientAlphaKey(1.0f, 0.0f),
                        new GradientAlphaKey(1.0f, 1.0f)
                    }
                );
            }
        }

        #region Public Properties

        public ColorScheme CurrentScheme => currentScheme;
        public Vector2 SpeedRange => speedRange;
        public Vector2 FeedRateRange => feedRateRange;
        public Vector2 SpindleLoadRange => spindleLoadRange;
        public Vector2 TemperatureRange => temperatureRange;

        #endregion
    }
}
