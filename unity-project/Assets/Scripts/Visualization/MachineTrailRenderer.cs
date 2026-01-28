using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Visualization
{
    /// <summary>
    /// Efficient trail rendering for machine tool paths using LineRenderer.
    /// Trails show historical machine positions with color-coding by speed/feed.
    /// Part of Feature 1.3: Machine Trail Visualization
    /// </summary>
    public class MachineTrailRenderer : MonoBehaviour
    {
        [Header("Trail Settings")]
        [SerializeField] private int maxTrailPoints = 10000;
        [SerializeField] private float trailWidth = 0.005f;
        [SerializeField] private Material trailMaterial;
        [SerializeField] private bool enableTrail = true;

        [Header("Color Mapping")]
        [SerializeField] private Gradient speedGradient;
        [SerializeField] private float minSpeed = 0f;
        [SerializeField] private float maxSpeed = 5000f; // mm/min

        [Header("Performance")]
        [SerializeField] private int updateInterval = 1; // Update every N frames
        [SerializeField] private float minPointDistance = 0.001f; // meters

        private LineRenderer lineRenderer;
        private List<Vector3> trailPoints = new List<Vector3>();
        private List<float> trailSpeeds = new List<float>();
        private Vector3 lastRecordedPosition;
        private int frameCounter = 0;

        // Statistics
        private float totalTrailLength = 0f;
        private int pointsAdded = 0;
        private int pointsRemoved = 0;

        void Awake()
        {
            InitializeLineRenderer();
            InitializeDefaultGradient();
        }

        void Update()
        {
            frameCounter++;
            if (frameCounter >= updateInterval)
            {
                UpdateTrailVisuals();
                frameCounter = 0;
            }
        }

        /// <summary>
        /// Add a new point to the trail with speed information
        /// </summary>
        public void AddTrailPoint(Vector3 position, float speed)
        {
            if (!enableTrail) return;

            // Check if point is far enough from last point
            if (trailPoints.Count > 0)
            {
                float distance = Vector3.Distance(position, lastRecordedPosition);
                if (distance < minPointDistance) return;

                totalTrailLength += distance;
            }

            // Add new point
            trailPoints.Add(position);
            trailSpeeds.Add(speed);
            lastRecordedPosition = position;
            pointsAdded++;

            // Remove oldest points if exceeding max
            if (trailPoints.Count > maxTrailPoints)
            {
                float removedSegmentLength = Vector3.Distance(trailPoints[0], trailPoints[1]);
                totalTrailLength -= removedSegmentLength;

                trailPoints.RemoveAt(0);
                trailSpeeds.RemoveAt(0);
                pointsRemoved++;
            }
        }

        /// <summary>
        /// Clear all trail points
        /// </summary>
        public void ClearTrail()
        {
            trailPoints.Clear();
            trailSpeeds.Clear();
            totalTrailLength = 0f;
            pointsAdded = 0;
            pointsRemoved = 0;

            if (lineRenderer != null)
            {
                lineRenderer.positionCount = 0;
            }

            Debug.Log("[TrailRenderer] Trail cleared");
        }

        /// <summary>
        /// Set trail visibility
        /// </summary>
        public void SetTrailEnabled(bool enabled)
        {
            enableTrail = enabled;
            if (lineRenderer != null)
            {
                lineRenderer.enabled = enabled;
            }
        }

        /// <summary>
        /// Update trail width
        /// </summary>
        public void SetTrailWidth(float width)
        {
            trailWidth = width;
            if (lineRenderer != null)
            {
                lineRenderer.startWidth = width;
                lineRenderer.endWidth = width;
            }
        }

        /// <summary>
        /// Set speed range for color mapping
        /// </summary>
        public void SetSpeedRange(float min, float max)
        {
            minSpeed = min;
            maxSpeed = max;
        }

        /// <summary>
        /// Get trail statistics
        /// </summary>
        public TrailStatistics GetStatistics()
        {
            return new TrailStatistics
            {
                PointCount = trailPoints.Count,
                TotalLength = totalTrailLength,
                PointsAdded = pointsAdded,
                PointsRemoved = pointsRemoved,
                MemoryUsageMB = (trailPoints.Count * 16 + trailSpeeds.Count * 4) / (1024f * 1024f)
            };
        }

        /// <summary>
        /// Export trail points for serialization
        /// </summary>
        public TrailData ExportTrailData()
        {
            return new TrailData
            {
                Points = trailPoints.ToArray(),
                Speeds = trailSpeeds.ToArray()
            };
        }

        /// <summary>
        /// Import trail points from serialized data
        /// </summary>
        public void ImportTrailData(TrailData data)
        {
            ClearTrail();
            trailPoints.AddRange(data.Points);
            trailSpeeds.AddRange(data.Speeds);

            // Recalculate total length
            totalTrailLength = 0f;
            for (int i = 1; i < trailPoints.Count; i++)
            {
                totalTrailLength += Vector3.Distance(trailPoints[i - 1], trailPoints[i]);
            }

            UpdateTrailVisuals();
            Debug.Log($"[TrailRenderer] Imported {trailPoints.Count} trail points");
        }

        private void InitializeLineRenderer()
        {
            lineRenderer = GetComponent<LineRenderer>();
            if (lineRenderer == null)
            {
                lineRenderer = gameObject.AddComponent<LineRenderer>();
            }

            lineRenderer.startWidth = trailWidth;
            lineRenderer.endWidth = trailWidth;
            lineRenderer.positionCount = 0;
            lineRenderer.useWorldSpace = true;
            lineRenderer.numCornerVertices = 2;
            lineRenderer.numCapVertices = 2;

            // Use default material if not assigned
            if (trailMaterial == null)
            {
                trailMaterial = new Material(Shader.Find("Sprites/Default"));
                trailMaterial.color = Color.cyan;
            }
            lineRenderer.material = trailMaterial;
        }

        private void InitializeDefaultGradient()
        {
            if (speedGradient == null)
            {
                speedGradient = new Gradient();
                var colorKeys = new GradientColorKey[5];
                colorKeys[0] = new GradientColorKey(Color.blue, 0.0f);     // Slow (blue)
                colorKeys[1] = new GradientColorKey(Color.cyan, 0.25f);    //
                colorKeys[2] = new GradientColorKey(Color.green, 0.5f);    // Medium (green)
                colorKeys[3] = new GradientColorKey(Color.yellow, 0.75f);  //
                colorKeys[4] = new GradientColorKey(Color.red, 1.0f);      // Fast (red)

                var alphaKeys = new GradientAlphaKey[2];
                alphaKeys[0] = new GradientAlphaKey(1.0f, 0.0f);
                alphaKeys[1] = new GradientAlphaKey(1.0f, 1.0f);

                speedGradient.SetKeys(colorKeys, alphaKeys);
            }
        }

        private void UpdateTrailVisuals()
        {
            if (lineRenderer == null || trailPoints.Count < 2) return;

            // Update LineRenderer positions
            lineRenderer.positionCount = trailPoints.Count;
            lineRenderer.SetPositions(trailPoints.ToArray());

            // Update colors based on speed
            UpdateTrailColors();
        }

        private void UpdateTrailColors()
        {
            if (trailPoints.Count == 0) return;

            // Create color gradient for LineRenderer
            var colors = new Color[trailPoints.Count];
            for (int i = 0; i < trailSpeeds.Count; i++)
            {
                float normalizedSpeed = Mathf.InverseLerp(minSpeed, maxSpeed, trailSpeeds[i]);
                colors[i] = speedGradient.Evaluate(normalizedSpeed);
            }

            lineRenderer.colorGradient = CreateGradientFromColors(colors);
        }

        private Gradient CreateGradientFromColors(Color[] colors)
        {
            var gradient = new Gradient();
            int keyCount = Mathf.Min(8, colors.Length); // Unity max 8 gradient keys

            var colorKeys = new GradientColorKey[keyCount];
            var alphaKeys = new GradientAlphaKey[keyCount];

            for (int i = 0; i < keyCount; i++)
            {
                int index = (int)((float)i / (keyCount - 1) * (colors.Length - 1));
                float time = (float)i / (keyCount - 1);

                colorKeys[i] = new GradientColorKey(colors[index], time);
                alphaKeys[i] = new GradientAlphaKey(colors[index].a, time);
            }

            gradient.SetKeys(colorKeys, alphaKeys);
            return gradient;
        }

        #region Public Properties

        public int TrailPointCount => trailPoints.Count;
        public float TotalTrailLength => totalTrailLength;
        public bool IsTrailEnabled => enableTrail;
        public int MaxTrailPoints => maxTrailPoints;

        #endregion
    }

    /// <summary>
    /// Trail statistics data
    /// </summary>
    [System.Serializable]
    public struct TrailStatistics
    {
        public int PointCount;
        public float TotalLength;
        public int PointsAdded;
        public int PointsRemoved;
        public float MemoryUsageMB;
    }

    /// <summary>
    /// Serializable trail data
    /// </summary>
    [System.Serializable]
    public struct TrailData
    {
        public Vector3[] Points;
        public float[] Speeds;
    }
}
