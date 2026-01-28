using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Toolpath
{
    /// <summary>
    /// Visualizes G-code toolpaths in Unity 3D space.
    /// Supports animation, highlighting, and progress tracking.
    /// </summary>
    public class ToolpathVisualizer : MonoBehaviour
    {
        [Header("Visualization Settings")]
        public Transform workpieceOrigin;
        public float scaleFactor = 0.001f; // mm to Unity units
        public bool showRapidMoves = true;
        public bool showFeedMoves = true;
        public bool showArcs = true;

        [Header("Line Settings")]
        public float rapidLineWidth = 0.001f;
        public float feedLineWidth = 0.002f;
        public Material rapidMaterial;
        public Material feedMaterial;
        public Material arcMaterial;
        public Material currentLineMaterial;

        [Header("Colors")]
        public Color rapidColor = new Color(1f, 1f, 0f, 0.5f);
        public Color feedColor = new Color(0f, 0.8f, 1f, 0.8f);
        public Color arcColor = new Color(0f, 1f, 0.5f, 0.8f);
        public Color currentColor = new Color(1f, 0.3f, 0f, 1f);
        public Color completedColor = new Color(0.3f, 0.3f, 0.3f, 0.5f);

        [Header("Animation")]
        public bool animateToolpath = false;
        public float animationSpeed = 1f;
        public Transform toolIndicator;

        [Header("Status")]
        [SerializeField] private int totalSegments;
        [SerializeField] private int currentSegment;
        [SerializeField] private float totalLength;
        [SerializeField] private float estimatedTime;

        // Internal state
        private GCodeParser parser;
        private List<ToolpathSegment> segments;
        private List<LineRenderer> lineRenderers = new List<LineRenderer>();
        private Coroutine animationCoroutine;
        private bool isAnimating;

        // Events
        public event Action<int, int> OnSegmentProgress;
        public event Action OnToolpathComplete;
        public event Action<ToolpathSegment> OnSegmentEnter;

        // Singleton
        public static ToolpathVisualizer Instance { get; private set; }

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
            }

            parser = new GCodeParser();
            CreateDefaultMaterials();
        }

        private void CreateDefaultMaterials()
        {
            if (rapidMaterial == null)
            {
                rapidMaterial = new Material(Shader.Find("Sprites/Default"));
                rapidMaterial.color = rapidColor;
            }

            if (feedMaterial == null)
            {
                feedMaterial = new Material(Shader.Find("Sprites/Default"));
                feedMaterial.color = feedColor;
            }

            if (arcMaterial == null)
            {
                arcMaterial = new Material(Shader.Find("Sprites/Default"));
                arcMaterial.color = arcColor;
            }

            if (currentLineMaterial == null)
            {
                currentLineMaterial = new Material(Shader.Find("Sprites/Default"));
                currentLineMaterial.color = currentColor;
            }
        }

        /// <summary>
        /// Load and visualize G-code from string
        /// </summary>
        public void LoadGCode(string gcode)
        {
            ClearVisualization();

            parser.OnProgressUpdated += (progress) =>
            {
                Debug.Log($"[ToolpathVisualizer] Parsing: {progress * 100:F1}%");
            };

            segments = parser.Parse(gcode);
            totalSegments = segments.Count;

            CalculateStatistics();
            CreateVisualization();

            Debug.Log($"[ToolpathVisualizer] Loaded {totalSegments} segments, " +
                      $"total length: {totalLength:F1}mm, estimated time: {estimatedTime:F1}s");
        }

        /// <summary>
        /// Load G-code from file
        /// </summary>
        public void LoadGCodeFile(string filePath)
        {
            ClearVisualization();
            segments = parser.ParseFile(filePath);
            totalSegments = segments.Count;

            CalculateStatistics();
            CreateVisualization();
        }

        /// <summary>
        /// Clear all visualization
        /// </summary>
        public void ClearVisualization()
        {
            StopAnimation();

            foreach (var lr in lineRenderers)
            {
                if (lr != null)
                {
                    Destroy(lr.gameObject);
                }
            }
            lineRenderers.Clear();

            segments?.Clear();
            totalSegments = 0;
            currentSegment = 0;
        }

        private void CalculateStatistics()
        {
            totalLength = 0;
            estimatedTime = 0;

            foreach (var segment in segments)
            {
                totalLength += segment.Length;
                estimatedTime += segment.EstimatedTime;
            }
        }

        private void CreateVisualization()
        {
            // Create parent object for toolpath
            var toolpathParent = new GameObject("Toolpath");
            if (workpieceOrigin != null)
            {
                toolpathParent.transform.SetParent(workpieceOrigin);
                toolpathParent.transform.localPosition = Vector3.zero;
            }
            else
            {
                toolpathParent.transform.SetParent(transform);
            }

            // Group segments by type for batching
            var rapidSegments = new List<ToolpathSegment>();
            var feedSegments = new List<ToolpathSegment>();
            var arcSegments = new List<ToolpathSegment>();

            foreach (var segment in segments)
            {
                switch (segment.motionType)
                {
                    case MotionType.Rapid:
                        if (showRapidMoves) rapidSegments.Add(segment);
                        break;
                    case MotionType.Linear:
                        if (showFeedMoves) feedSegments.Add(segment);
                        break;
                    case MotionType.ArcCW:
                    case MotionType.ArcCCW:
                        if (showArcs) arcSegments.Add(segment);
                        break;
                }
            }

            // Create line renderers for each type
            if (rapidSegments.Count > 0)
            {
                CreateSegmentLines(toolpathParent.transform, "Rapids", rapidSegments,
                    rapidMaterial, rapidLineWidth, true);
            }

            if (feedSegments.Count > 0)
            {
                CreateSegmentLines(toolpathParent.transform, "Feeds", feedSegments,
                    feedMaterial, feedLineWidth, false);
            }

            if (arcSegments.Count > 0)
            {
                CreateArcLines(toolpathParent.transform, "Arcs", arcSegments,
                    arcMaterial, feedLineWidth);
            }

            // Create tool indicator if needed
            if (toolIndicator == null && animateToolpath)
            {
                CreateToolIndicator(toolpathParent.transform);
            }
        }

        private void CreateSegmentLines(Transform parent, string name,
            List<ToolpathSegment> segmentList, Material material, float width, bool dashed)
        {
            var lineObj = new GameObject(name);
            lineObj.transform.SetParent(parent);
            lineObj.transform.localPosition = Vector3.zero;

            var lr = lineObj.AddComponent<LineRenderer>();
            lr.material = material;
            lr.startWidth = width;
            lr.endWidth = width;
            lr.useWorldSpace = false;

            // Build points list
            var points = new List<Vector3>();

            foreach (var segment in segmentList)
            {
                // Convert from G-code coordinates (mm) to Unity coordinates
                // G-code: X=right, Y=forward, Z=up
                // Unity: X=right, Y=up, Z=forward
                Vector3 start = ConvertCoordinates(segment.startPoint);
                Vector3 end = ConvertCoordinates(segment.endPoint);

                if (points.Count == 0 || Vector3.Distance(points[points.Count - 1], start) > 0.0001f)
                {
                    // Add a break in the line
                    if (points.Count > 0)
                    {
                        points.Add(points[points.Count - 1]); // Duplicate last point
                        points.Add(start); // Duplicate new start point
                    }
                    points.Add(start);
                }
                points.Add(end);
            }

            lr.positionCount = points.Count;
            lr.SetPositions(points.ToArray());

            lineRenderers.Add(lr);
        }

        private void CreateArcLines(Transform parent, string name,
            List<ToolpathSegment> arcSegments, Material material, float width)
        {
            foreach (var segment in arcSegments)
            {
                if (segment.arcPoints == null || segment.arcPoints.Length < 2)
                    continue;

                var arcObj = new GameObject($"Arc_{segment.lineNumber}");
                arcObj.transform.SetParent(parent);
                arcObj.transform.localPosition = Vector3.zero;

                var lr = arcObj.AddComponent<LineRenderer>();
                lr.material = material;
                lr.startWidth = width;
                lr.endWidth = width;
                lr.useWorldSpace = false;

                var points = new Vector3[segment.arcPoints.Length];
                for (int i = 0; i < segment.arcPoints.Length; i++)
                {
                    points[i] = ConvertCoordinates(segment.arcPoints[i]);
                }

                lr.positionCount = points.Length;
                lr.SetPositions(points);

                lineRenderers.Add(lr);
            }
        }

        private Vector3 ConvertCoordinates(Vector3 gcodePos)
        {
            // Convert G-code coordinates to Unity coordinates
            // G-code: X=right, Y=forward, Z=up
            // Unity: X=right, Y=up, Z=forward
            return new Vector3(
                gcodePos.x * scaleFactor,
                gcodePos.z * scaleFactor,  // Z in G-code becomes Y in Unity
                gcodePos.y * scaleFactor   // Y in G-code becomes Z in Unity
            );
        }

        private void CreateToolIndicator(Transform parent)
        {
            var indicator = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            indicator.name = "ToolIndicator";
            indicator.transform.SetParent(parent);
            indicator.transform.localScale = Vector3.one * 0.005f;

            var collider = indicator.GetComponent<Collider>();
            if (collider != null) Destroy(collider);

            var material = new Material(Shader.Find("Standard"));
            material.color = currentColor;
            material.EnableKeyword("_EMISSION");
            material.SetColor("_EmissionColor", currentColor * 2f);
            indicator.GetComponent<Renderer>().material = material;

            toolIndicator = indicator.transform;
        }

        // =========================================================================
        // Animation
        // =========================================================================

        /// <summary>
        /// Start toolpath animation
        /// </summary>
        public void StartAnimation()
        {
            if (segments == null || segments.Count == 0)
            {
                Debug.LogWarning("[ToolpathVisualizer] No toolpath loaded");
                return;
            }

            StopAnimation();
            animationCoroutine = StartCoroutine(AnimateToolpath());
        }

        /// <summary>
        /// Stop animation
        /// </summary>
        public void StopAnimation()
        {
            if (animationCoroutine != null)
            {
                StopCoroutine(animationCoroutine);
                animationCoroutine = null;
            }
            isAnimating = false;
        }

        /// <summary>
        /// Jump to specific segment
        /// </summary>
        public void JumpToSegment(int segmentIndex)
        {
            if (segments == null || segmentIndex < 0 || segmentIndex >= segments.Count)
                return;

            currentSegment = segmentIndex;
            var segment = segments[segmentIndex];

            if (toolIndicator != null)
            {
                toolIndicator.localPosition = ConvertCoordinates(segment.startPoint);
            }

            OnSegmentProgress?.Invoke(currentSegment, totalSegments);
        }

        private IEnumerator AnimateToolpath()
        {
            isAnimating = true;
            currentSegment = 0;

            foreach (var segment in segments)
            {
                OnSegmentEnter?.Invoke(segment);

                // Calculate animation duration based on feed rate
                float duration = segment.EstimatedTime / animationSpeed;
                duration = Mathf.Max(duration, 0.01f); // Minimum duration

                Vector3 startPos = ConvertCoordinates(segment.startPoint);
                Vector3 endPos = ConvertCoordinates(segment.endPoint);

                float elapsed = 0f;

                while (elapsed < duration)
                {
                    float t = elapsed / duration;

                    if (segment.motionType == MotionType.ArcCW || segment.motionType == MotionType.ArcCCW)
                    {
                        // Interpolate along arc
                        if (segment.arcPoints != null && segment.arcPoints.Length > 0)
                        {
                            int index = Mathf.FloorToInt(t * (segment.arcPoints.Length - 1));
                            index = Mathf.Clamp(index, 0, segment.arcPoints.Length - 1);
                            toolIndicator.localPosition = ConvertCoordinates(segment.arcPoints[index]);
                        }
                    }
                    else
                    {
                        // Linear interpolation
                        toolIndicator.localPosition = Vector3.Lerp(startPos, endPos, t);
                    }

                    elapsed += Time.deltaTime;
                    yield return null;
                }

                // Ensure we reach the end point
                toolIndicator.localPosition = endPos;

                currentSegment++;
                OnSegmentProgress?.Invoke(currentSegment, totalSegments);
            }

            isAnimating = false;
            OnToolpathComplete?.Invoke();
            Debug.Log("[ToolpathVisualizer] Animation complete");
        }

        // =========================================================================
        // Public API
        // =========================================================================

        /// <summary>
        /// Get bounding box of the toolpath
        /// </summary>
        public Bounds GetBounds()
        {
            if (segments == null || segments.Count == 0)
                return new Bounds(Vector3.zero, Vector3.zero);

            Vector3 min = Vector3.one * float.MaxValue;
            Vector3 max = Vector3.one * float.MinValue;

            foreach (var segment in segments)
            {
                min = Vector3.Min(min, segment.startPoint);
                min = Vector3.Min(min, segment.endPoint);
                max = Vector3.Max(max, segment.startPoint);
                max = Vector3.Max(max, segment.endPoint);
            }

            Vector3 center = ConvertCoordinates((min + max) / 2f);
            Vector3 size = ConvertCoordinates(max - min);

            return new Bounds(center, size);
        }

        /// <summary>
        /// Get segment at specific line number
        /// </summary>
        public ToolpathSegment GetSegmentAtLine(int lineNumber)
        {
            return segments?.Find(s => s.lineNumber == lineNumber);
        }

        /// <summary>
        /// Highlight specific line number
        /// </summary>
        public void HighlightLine(int lineNumber)
        {
            // Find and highlight the segment
            int index = segments?.FindIndex(s => s.lineNumber == lineNumber) ?? -1;
            if (index >= 0)
            {
                JumpToSegment(index);
            }
        }

        // Properties
        public int TotalSegments => totalSegments;
        public int CurrentSegment => currentSegment;
        public float TotalLength => totalLength;
        public float EstimatedTime => estimatedTime;
        public bool IsAnimating => isAnimating;
        public List<ToolpathSegment> Segments => segments;
    }
}
