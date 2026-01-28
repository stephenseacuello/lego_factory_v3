using UnityEngine;
using System;
using System.Collections.Generic;

namespace CNCScada.DigitalTwin
{
    /// <summary>
    /// Toolpath Visualizer for G-code Path Rendering
    /// Renders 3D toolpaths with motion types, feedrates, and progress tracking
    /// Part of Phase 2: Real-Time Visualization (60Hz)
    /// </summary>
    public class ToolpathVisualizer : MonoBehaviour
    {
        [Header("State Handler Reference")]
        [SerializeField] private ISO23247StateHandler stateHandler;

        [Header("Rendering Settings")]
        [SerializeField] private Material lineMaterial;
        [SerializeField] private float lineWidth = 0.002f;
        [SerializeField] private float positionScale = 0.001f; // mm to Unity units
        [SerializeField] private int maxPathSegments = 10000;

        [Header("Motion Type Colors")]
        [SerializeField] private Color rapidColor = new Color(1f, 0.5f, 0f); // Orange for G0
        [SerializeField] private Color linearColor = Color.cyan; // Cyan for G1
        [SerializeField] private Color arcCWColor = Color.green; // Green for G2
        [SerializeField] private Color arcCCWColor = Color.yellow; // Yellow for G3
        [SerializeField] private Color completedColor = new Color(0.5f, 0.5f, 0.5f, 0.5f); // Gray for completed

        [Header("Progress Visualization")]
        [SerializeField] private bool showProgress = true;
        [SerializeField] private Color progressColor = Color.magenta;
        [SerializeField] private float progressMarkerSize = 0.01f;
        [SerializeField] private bool showToolPosition = true;
        [SerializeField] private GameObject toolMarkerPrefab;

        [Header("Performance")]
        [SerializeField] private bool enableLOD = true;
        [SerializeField] private float lodDistance1 = 5f;
        [SerializeField] private float lodDistance2 = 10f;
        [SerializeField] private bool enableCulling = true;
        [SerializeField] private float cullingRadius = 20f;

        [Header("Feedrate Visualization")]
        [SerializeField] private bool colorByFeedrate = false;
        [SerializeField] private float minFeedrate = 100f; // mm/min
        [SerializeField] private float maxFeedrate = 3000f; // mm/min
        [SerializeField] private Gradient feedrateGradient;

        // Toolpath data
        private List<PathSegment> pathSegments = new List<PathSegment>();
        private int currentSegmentIndex = 0;
        private LineRenderer lineRenderer;
        private GameObject toolMarker;

        // Rendering optimization
        private int visibleSegmentStart = 0;
        private int visibleSegmentEnd = 0;
        private Camera mainCamera;

        // Statistics
        private int totalSegments = 0;
        private float totalPathLength = 0f;
        private float completedPathLength = 0f;

        // Events
        public event Action<int, int> OnProgressChanged;
        public event Action OnPathCompleted;

        [Serializable]
        public class PathSegment
        {
            public Vector3 startPoint;
            public Vector3 endPoint;
            public string motionType; // G0, G1, G2, G3
            public float feedRate;
            public int lineNumber;
            public bool completed;
            public float length;
        }

        void Start()
        {
            if (stateHandler == null)
            {
                stateHandler = FindObjectOfType<ISO23247StateHandler>();
            }

            if (stateHandler != null)
            {
                stateHandler.OnStateUpdated += OnStateUpdated;
            }

            mainCamera = Camera.main;
            SetupLineRenderer();
            CreateToolMarker();

            // Initialize feedrate gradient if not set
            if (feedrateGradient == null)
            {
                feedrateGradient = new Gradient();
                GradientColorKey[] colorKeys = new GradientColorKey[3];
                colorKeys[0] = new GradientColorKey(Color.blue, 0f);
                colorKeys[1] = new GradientColorKey(Color.green, 0.5f);
                colorKeys[2] = new GradientColorKey(Color.red, 1f);
                GradientAlphaKey[] alphaKeys = new GradientAlphaKey[2];
                alphaKeys[0] = new GradientAlphaKey(1f, 0f);
                alphaKeys[1] = new GradientAlphaKey(1f, 1f);
                feedrateGradient.SetKeys(colorKeys, alphaKeys);
            }

            Debug.Log("[ToolpathVisualizer] Initialized");
        }

        void SetupLineRenderer()
        {
            GameObject lineObj = new GameObject("ToolpathLine");
            lineObj.transform.SetParent(transform);
            lineObj.transform.localPosition = Vector3.zero;

            lineRenderer = lineObj.AddComponent<LineRenderer>();
            lineRenderer.startWidth = lineWidth;
            lineRenderer.endWidth = lineWidth;
            lineRenderer.positionCount = 0;
            lineRenderer.useWorldSpace = true;

            if (lineMaterial != null)
            {
                lineRenderer.material = lineMaterial;
            }
            else
            {
                lineRenderer.material = new Material(Shader.Find("Sprites/Default"));
            }
        }

        void CreateToolMarker()
        {
            if (toolMarkerPrefab != null)
            {
                toolMarker = Instantiate(toolMarkerPrefab, transform);
            }
            else
            {
                toolMarker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                toolMarker.transform.SetParent(transform);
                toolMarker.transform.localScale = Vector3.one * progressMarkerSize;
                toolMarker.GetComponent<Renderer>().material.color = progressColor;
                Destroy(toolMarker.GetComponent<Collider>());
            }

            toolMarker.SetActive(showToolPosition);
        }

        void OnStateUpdated(ISO23247StateHandler.MachineState state)
        {
            if (state == null) return;

            // Update tool marker position
            if (showToolPosition && toolMarker != null)
            {
                Vector3 worldPos = transform.position + state.position * positionScale;
                toolMarker.transform.position = worldPos;
            }

            // Update progress based on current line
            if (state.current_line > 0 && state.current_line <= pathSegments.Count)
            {
                UpdateProgress(state.current_line);
            }
        }

        void Update()
        {
            if (enableCulling && mainCamera != null)
            {
                OptimizeVisibleSegments();
            }

            if (enableLOD && mainCamera != null)
            {
                UpdateLOD();
            }
        }

        void OptimizeVisibleSegments()
        {
            // Calculate visible range based on camera position
            Vector3 cameraPos = mainCamera.transform.position;
            float cullingRadiusSqr = cullingRadius * cullingRadius;

            visibleSegmentStart = 0;
            visibleSegmentEnd = pathSegments.Count;

            // Find first visible segment
            for (int i = 0; i < pathSegments.Count; i++)
            {
                Vector3 segmentMidpoint = (pathSegments[i].startPoint + pathSegments[i].endPoint) * 0.5f * positionScale;
                segmentMidpoint += transform.position;

                if ((segmentMidpoint - cameraPos).sqrMagnitude < cullingRadiusSqr)
                {
                    visibleSegmentStart = Mathf.Max(0, i - 100);
                    break;
                }
            }

            // Find last visible segment
            for (int i = pathSegments.Count - 1; i >= visibleSegmentStart; i--)
            {
                Vector3 segmentMidpoint = (pathSegments[i].startPoint + pathSegments[i].endPoint) * 0.5f * positionScale;
                segmentMidpoint += transform.position;

                if ((segmentMidpoint - cameraPos).sqrMagnitude < cullingRadiusSqr)
                {
                    visibleSegmentEnd = Mathf.Min(pathSegments.Count, i + 100);
                    break;
                }
            }
        }

        void UpdateLOD()
        {
            float distanceToCamera = Vector3.Distance(mainCamera.transform.position, transform.position);

            if (distanceToCamera > lodDistance2)
            {
                lineRenderer.startWidth = lineWidth * 3f;
                lineRenderer.endWidth = lineWidth * 3f;
            }
            else if (distanceToCamera > lodDistance1)
            {
                lineRenderer.startWidth = lineWidth * 2f;
                lineRenderer.endWidth = lineWidth * 2f;
            }
            else
            {
                lineRenderer.startWidth = lineWidth;
                lineRenderer.endWidth = lineWidth;
            }
        }

        /// <summary>
        /// Load toolpath from G-code segments
        /// </summary>
        public void LoadToolpath(List<PathSegment> segments)
        {
            pathSegments.Clear();
            pathSegments.AddRange(segments);
            totalSegments = pathSegments.Count;

            // Calculate total path length
            totalPathLength = 0f;
            foreach (var segment in pathSegments)
            {
                segment.length = Vector3.Distance(segment.startPoint, segment.endPoint);
                totalPathLength += segment.length;
            }

            currentSegmentIndex = 0;
            completedPathLength = 0f;

            RenderToolpath();
            Debug.Log($"[ToolpathVisualizer] Loaded {totalSegments} segments, total length: {totalPathLength:F2}mm");
        }

        void RenderToolpath()
        {
            if (pathSegments.Count == 0)
            {
                lineRenderer.positionCount = 0;
                return;
            }

            int startIdx = enableCulling ? visibleSegmentStart : 0;
            int endIdx = enableCulling ? visibleSegmentEnd : pathSegments.Count;
            endIdx = Mathf.Min(endIdx, pathSegments.Count);

            // Build line renderer positions
            List<Vector3> positions = new List<Vector3>();
            List<Color> colors = new List<Color>();

            for (int i = startIdx; i < endIdx; i++)
            {
                PathSegment segment = pathSegments[i];

                Vector3 worldStart = transform.position + segment.startPoint * positionScale;
                Vector3 worldEnd = transform.position + segment.endPoint * positionScale;

                positions.Add(worldStart);
                positions.Add(worldEnd);

                Color segmentColor = GetSegmentColor(segment);
                colors.Add(segmentColor);
                colors.Add(segmentColor);
            }

            lineRenderer.positionCount = positions.Count;
            lineRenderer.SetPositions(positions.ToArray());

            // Set colors (requires LineRenderer with vertex colors)
            if (lineRenderer.colorGradient != null)
            {
                GradientColorKey[] colorKeys = new GradientColorKey[colors.Count];
                for (int i = 0; i < colors.Count; i++)
                {
                    colorKeys[i] = new GradientColorKey(colors[i], (float)i / colors.Count);
                }
                GradientAlphaKey[] alphaKeys = new GradientAlphaKey[2];
                alphaKeys[0] = new GradientAlphaKey(1f, 0f);
                alphaKeys[1] = new GradientAlphaKey(1f, 1f);
                Gradient gradient = new Gradient();
                gradient.SetKeys(colorKeys, alphaKeys);
                lineRenderer.colorGradient = gradient;
            }
        }

        Color GetSegmentColor(PathSegment segment)
        {
            // Completed segments
            if (segment.completed)
            {
                return completedColor;
            }

            // Color by feedrate
            if (colorByFeedrate)
            {
                float t = Mathf.InverseLerp(minFeedrate, maxFeedrate, segment.feedRate);
                return feedrateGradient.Evaluate(t);
            }

            // Color by motion type
            switch (segment.motionType)
            {
                case "G0":
                    return rapidColor;
                case "G1":
                    return linearColor;
                case "G2":
                    return arcCWColor;
                case "G3":
                    return arcCCWColor;
                default:
                    return Color.white;
            }
        }

        void UpdateProgress(int lineNumber)
        {
            int previousIndex = currentSegmentIndex;

            // Mark segments as completed
            for (int i = 0; i < pathSegments.Count; i++)
            {
                if (pathSegments[i].lineNumber <= lineNumber)
                {
                    if (!pathSegments[i].completed)
                    {
                        pathSegments[i].completed = true;
                        completedPathLength += pathSegments[i].length;
                    }
                }
            }

            // Find current segment
            for (int i = 0; i < pathSegments.Count; i++)
            {
                if (pathSegments[i].lineNumber > lineNumber)
                {
                    currentSegmentIndex = i;
                    break;
                }
            }

            if (currentSegmentIndex != previousIndex)
            {
                RenderToolpath();
                OnProgressChanged?.Invoke(currentSegmentIndex, totalSegments);
            }

            // Check completion
            if (currentSegmentIndex >= totalSegments - 1)
            {
                OnPathCompleted?.Invoke();
            }
        }

        /// <summary>
        /// Clear all path segments
        /// </summary>
        public void ClearToolpath()
        {
            pathSegments.Clear();
            totalSegments = 0;
            totalPathLength = 0f;
            completedPathLength = 0f;
            currentSegmentIndex = 0;

            if (lineRenderer != null)
            {
                lineRenderer.positionCount = 0;
            }

            Debug.Log("[ToolpathVisualizer] Toolpath cleared");
        }

        /// <summary>
        /// Reset progress without clearing path
        /// </summary>
        public void ResetProgress()
        {
            foreach (var segment in pathSegments)
            {
                segment.completed = false;
            }
            currentSegmentIndex = 0;
            completedPathLength = 0f;
            RenderToolpath();
        }

        public float GetProgressPercent()
        {
            if (totalPathLength == 0f) return 0f;
            return (completedPathLength / totalPathLength) * 100f;
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_segments", totalSegments},
                {"current_segment", currentSegmentIndex},
                {"completed_segments", pathSegments.FindAll(s => s.completed).Count},
                {"total_path_length_mm", totalPathLength},
                {"completed_path_length_mm", completedPathLength},
                {"progress_percent", GetProgressPercent()},
                {"visible_segments", enableCulling ? (visibleSegmentEnd - visibleSegmentStart) : totalSegments}
            };
        }

        void OnDrawGizmos()
        {
            if (!Application.isPlaying || !showProgress) return;
            if (pathSegments.Count == 0) return;

            // Draw current segment marker
            if (currentSegmentIndex < pathSegments.Count)
            {
                PathSegment current = pathSegments[currentSegmentIndex];
                Vector3 worldPos = transform.position + current.startPoint * positionScale;

                Gizmos.color = progressColor;
                Gizmos.DrawWireSphere(worldPos, progressMarkerSize);
            }

            // Draw start and end markers
            if (pathSegments.Count > 0)
            {
                Vector3 startPos = transform.position + pathSegments[0].startPoint * positionScale;
                Vector3 endPos = transform.position + pathSegments[pathSegments.Count - 1].endPoint * positionScale;

                Gizmos.color = Color.green;
                Gizmos.DrawWireCube(startPos, Vector3.one * 0.02f);

                Gizmos.color = Color.red;
                Gizmos.DrawWireCube(endPos, Vector3.one * 0.02f);
            }
        }

        void OnDestroy()
        {
            if (stateHandler != null)
            {
                stateHandler.OnStateUpdated -= OnStateUpdated;
            }
        }
    }
}
