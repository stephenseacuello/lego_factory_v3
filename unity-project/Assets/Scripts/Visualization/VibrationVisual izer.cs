using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Visualization
{
    /// <summary>
    /// Visualizes machine vibrations using color-coded heatmaps and displacement effects.
    /// Monitors X, Y, Z axis vibration and displays intensity on machine components.
    /// Part of Feature 2.1: Force/Vibration Visualization (Phase 2)
    /// </summary>
    public class VibrationVisualizer : MonoBehaviour
    {
        [Header("Visualization Mode")]
        [SerializeField] private VisualizationMode mode = VisualizationMode.Heatmap;
        [SerializeField] private bool enableVisualization = true;

        [Header("Heatmap Settings")]
        [SerializeField] private Color lowVibrationColor = Color.green;
        [SerializeField] private Color mediumVibrationColor = Color.yellow;
        [SerializeField] private Color highVibrationColor = Color.red;
        [SerializeField] private float heatmapIntensity = 1f;

        [Header("Displacement Settings")]
        [SerializeField] private bool showDisplacement = true;
        [SerializeField] private float displacementScale = 100f; // Amplify small vibrations
        [SerializeField] private float displacementSmoothing = 0.1f;

        [Header("Waveform Settings")]
        [SerializeField] private bool showWaveform = false;
        [SerializeField] private int waveformSamples = 100;
        [SerializeField] private float waveformHeight = 0.1f; // meters

        [Header("Component References")]
        [SerializeField] private List<Renderer> machineRenderers = new List<Renderer>();
        [SerializeField] private Transform machineBase;

        // Vibration state
        private Vector3 currentVibration = Vector3.zero;
        private Vector3 smoothedVibration = Vector3.zero;
        private float vibrationMagnitude = 0f;
        private float maxVibration = 0f;

        // Vibration history for waveform
        private Queue<Vector3> vibrationHistory = new Queue<Vector3>();

        // Original materials (for heatmap restoration)
        private Dictionary<Renderer, Material> originalMaterials = new Dictionary<Renderer, Material>();

        // Original position (for displacement restoration)
        private Vector3 originalPosition;

        // Frequency analysis
        private float dominantFrequency = 0f;
        private List<float> frequencySpectrum = new List<float>();

        // Statistics
        private int totalUpdates = 0;
        private DateTime lastUpdate;

        // Events
        public event Action<VibrationData> OnVibrationUpdated;

        void Start()
        {
            InitializeVisualization();
            if (machineBase != null)
            {
                originalPosition = machineBase.localPosition;
            }
        }

        void Update()
        {
            if (enableVisualization)
            {
                UpdateVisualization();
            }
        }

        /// <summary>
        /// Initialize visualization system
        /// </summary>
        private void InitializeVisualization()
        {
            // Store original materials
            foreach (var renderer in machineRenderers)
            {
                if (renderer != null && !originalMaterials.ContainsKey(renderer))
                {
                    originalMaterials[renderer] = renderer.material;
                }
            }

            Debug.Log($"[VibrationVisualizer] Initialized with {machineRenderers.Count} renderers");
        }

        /// <summary>
        /// Update vibration data
        /// </summary>
        public void UpdateVibration(float x, float y, float z)
        {
            currentVibration = new Vector3(x, y, z);
            vibrationMagnitude = currentVibration.magnitude;

            // Update max vibration
            maxVibration = Mathf.Max(maxVibration, vibrationMagnitude);

            // Smooth vibration for displacement
            smoothedVibration = Vector3.Lerp(smoothedVibration, currentVibration, displacementSmoothing);

            // Add to history
            vibrationHistory.Enqueue(currentVibration);
            if (vibrationHistory.Count > waveformSamples)
            {
                vibrationHistory.Dequeue();
            }

            // Update statistics
            totalUpdates++;
            lastUpdate = DateTime.UtcNow;

            // Trigger event
            var vibrationData = new VibrationData
            {
                Timestamp = DateTime.UtcNow,
                X = x,
                Y = y,
                Z = z,
                Magnitude = vibrationMagnitude,
                MaxMagnitude = maxVibration,
                DominantFrequency = dominantFrequency
            };

            OnVibrationUpdated?.Invoke(vibrationData);
        }

        /// <summary>
        /// Update visualization based on current mode
        /// </summary>
        private void UpdateVisualization()
        {
            switch (mode)
            {
                case VisualizationMode.Heatmap:
                    UpdateHeatmap();
                    break;

                case VisualizationMode.Displacement:
                    UpdateDisplacement();
                    break;

                case VisualizationMode.Both:
                    UpdateHeatmap();
                    UpdateDisplacement();
                    break;
            }
        }

        /// <summary>
        /// Update heatmap visualization
        /// </summary>
        private void UpdateHeatmap()
        {
            // Calculate intensity (0-1) based on vibration magnitude
            float intensity = Mathf.Clamp01(vibrationMagnitude / 0.01f); // 0.01m/s² = max

            // Interpolate color based on intensity
            Color heatmapColor;
            if (intensity < 0.5f)
            {
                // Green to Yellow
                heatmapColor = Color.Lerp(lowVibrationColor, mediumVibrationColor, intensity * 2);
            }
            else
            {
                // Yellow to Red
                heatmapColor = Color.Lerp(mediumVibrationColor, highVibrationColor, (intensity - 0.5f) * 2);
            }

            heatmapColor.a = heatmapIntensity;

            // Apply to all machine renderers
            foreach (var renderer in machineRenderers)
            {
                if (renderer != null)
                {
                    renderer.material.color = heatmapColor;
                }
            }
        }

        /// <summary>
        /// Update displacement visualization
        /// </summary>
        private void UpdateDisplacement()
        {
            if (!showDisplacement || machineBase == null) return;

            // Apply scaled vibration displacement
            Vector3 displacement = smoothedVibration * displacementScale;
            machineBase.localPosition = originalPosition + displacement;
        }

        /// <summary>
        /// Analyze vibration frequency spectrum
        /// </summary>
        public void AnalyzeFrequency()
        {
            if (vibrationHistory.Count < waveformSamples) return;

            // Convert vibration history to magnitude array
            float[] samples = new float[vibrationHistory.Count];
            int i = 0;
            foreach (var vib in vibrationHistory)
            {
                samples[i++] = vib.magnitude;
            }

            // Perform FFT (simplified - real implementation would use proper FFT)
            // This is a placeholder for frequency analysis
            frequencySpectrum.Clear();

            // Find dominant frequency (simplified peak detection)
            float maxPower = 0f;
            int maxIndex = 0;

            for (int f = 1; f < samples.Length / 2; f++)
            {
                float power = Mathf.Abs(samples[f]);
                frequencySpectrum.Add(power);

                if (power > maxPower)
                {
                    maxPower = power;
                    maxIndex = f;
                }
            }

            // Calculate dominant frequency (simplified)
            dominantFrequency = maxIndex * (1000f / waveformSamples); // Assuming 1000 Hz sampling

            Debug.Log($"[VibrationVisualizer] Dominant frequency: {dominantFrequency:F2} Hz");
        }

        /// <summary>
        /// Draw vibration waveform
        /// </summary>
        void OnDrawGizmos()
        {
            if (!showWaveform || vibrationHistory.Count < 2) return;

            Gizmos.color = Color.cyan;

            Vector3 basePos = transform.position + Vector3.up * 0.5f;
            Vector3[] points = new Vector3[vibrationHistory.Count];

            int i = 0;
            foreach (var vib in vibrationHistory)
            {
                float xOffset = (i / (float)waveformSamples) * 0.5f;
                float yOffset = vib.magnitude * waveformHeight;
                points[i] = basePos + new Vector3(xOffset, yOffset, 0);
                i++;
            }

            // Draw waveform lines
            for (i = 0; i < points.Length - 1; i++)
            {
                Gizmos.DrawLine(points[i], points[i + 1]);
            }
        }

        /// <summary>
        /// Get vibration statistics
        /// </summary>
        public VibrationStatistics GetStatistics()
        {
            float avgVibration = 0f;
            if (vibrationHistory.Count > 0)
            {
                foreach (var vib in vibrationHistory)
                {
                    avgVibration += vib.magnitude;
                }
                avgVibration /= vibrationHistory.Count;
            }

            return new VibrationStatistics
            {
                CurrentMagnitude = vibrationMagnitude,
                MaxMagnitude = maxVibration,
                AverageMagnitude = avgVibration,
                DominantFrequency = dominantFrequency,
                HistorySize = vibrationHistory.Count,
                TotalUpdates = totalUpdates,
                LastUpdate = lastUpdate
            };
        }

        /// <summary>
        /// Reset vibration visualization
        /// </summary>
        public void ResetVisualization()
        {
            currentVibration = Vector3.zero;
            smoothedVibration = Vector3.zero;
            vibrationMagnitude = 0f;
            maxVibration = 0f;
            vibrationHistory.Clear();
            frequencySpectrum.Clear();

            // Restore original materials
            foreach (var kvp in originalMaterials)
            {
                if (kvp.Key != null)
                {
                    kvp.Key.material = kvp.Value;
                }
            }

            // Restore original position
            if (machineBase != null)
            {
                machineBase.localPosition = originalPosition;
            }
        }

        /// <summary>
        /// Set visualization mode
        /// </summary>
        public void SetMode(VisualizationMode newMode)
        {
            mode = newMode;

            // Reset if switching modes
            if (mode == VisualizationMode.Heatmap)
            {
                // Restore original position
                if (machineBase != null)
                {
                    machineBase.localPosition = originalPosition;
                }
            }
            else if (mode == VisualizationMode.Displacement)
            {
                // Restore original materials
                foreach (var kvp in originalMaterials)
                {
                    if (kvp.Key != null)
                    {
                        kvp.Key.material = kvp.Value;
                    }
                }
            }
        }

        void OnDestroy()
        {
            ResetVisualization();
        }

        #region Public Properties

        public float CurrentVibrationMagnitude => vibrationMagnitude;
        public float MaxVibration => maxVibration;
        public float DominantFrequency => dominantFrequency;
        public VisualizationMode CurrentMode => mode;

        #endregion
    }

    #region Enumerations and Data Structures

    /// <summary>
    /// Vibration visualization mode
    /// </summary>
    public enum VisualizationMode
    {
        Heatmap,        // Color-coded intensity
        Displacement,   // Physical displacement
        Both            // Heatmap + Displacement
    }

    /// <summary>
    /// Vibration data event structure
    /// </summary>
    [Serializable]
    public struct VibrationData
    {
        public DateTime Timestamp;
        public float X; // m/s²
        public float Y; // m/s²
        public float Z; // m/s²
        public float Magnitude; // m/s²
        public float MaxMagnitude; // m/s²
        public float DominantFrequency; // Hz
    }

    /// <summary>
    /// Vibration statistics
    /// </summary>
    [Serializable]
    public struct VibrationStatistics
    {
        public float CurrentMagnitude;
        public float MaxMagnitude;
        public float AverageMagnitude;
        public float DominantFrequency;
        public int HistorySize;
        public int TotalUpdates;
        public DateTime LastUpdate;
    }

    #endregion
}
