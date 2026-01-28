using UnityEngine;
using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using Newtonsoft.Json;

namespace CNCScada.DigitalTwin
{
    /// <summary>
    /// Visualizes CNC toolpaths with dynamic LOD
    /// Supports progress tracking, segment highlighting, and performance optimization
    /// </summary>
    public class ToolpathVisualizer : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string programId = "";

        [Header("Visual Settings")]
        [SerializeField] private Material pathMaterial;
        [SerializeField] private Material completedMaterial;
        [SerializeField] private Material currentMaterial;
        [SerializeField] private float lineWidth = 1.0f;
        [SerializeField] private Color pathColor = Color.white;
        [SerializeField] private Color completedColor = Color.green;
        [SerializeField] private Color currentColor = Color.yellow;

        [Header("LOD Settings")]
        [SerializeField] private bool enableLOD = true;
        [SerializeField] private float highDetailDistance = 50f;
        [SerializeField] private float mediumDetailDistance = 150f;
        [SerializeField] private float lowDetailDistance = 300f;
        [SerializeField] private int maxSegments = 10000;

        [Header("Performance")]
        [SerializeField] private bool enableFrustumCulling = true;
        [SerializeField] private bool enableOcclusion = false;
        [SerializeField] private int segmentsPerFrame = 100;

        #endregion

        #region Private Fields

        private HttpClient _httpClient;
        private List<ToolpathSegment> _segments;
        private List<LineRenderer> _lineRenderers;
        private int _currentSegmentIndex;
        private float _totalPathLength;
        private Camera _mainCamera;
        private Plane[] _frustumPlanes;

        #endregion

        #region Events

        public event Action<int, int> OnProgressUpdate; // current, total
        public event Action OnPathCompleted;
        public event Action<string> OnError;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(10);
            _segments = new List<ToolpathSegment>();
            _lineRenderers = new List<LineRenderer>();
            _mainCamera = Camera.main;
        }

        void Update()
        {
            if (enableFrustumCulling && _mainCamera != null)
            {
                UpdateFrustumCulling();
            }

            UpdateLOD();
        }

        void OnDestroy()
        {
            _httpClient?.Dispose();
            ClearPath();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Load toolpath from G-code program
        /// </summary>
        public void LoadToolpath(string programId)
        {
            this.programId = programId;
            StartCoroutine(FetchToolpath());
        }

        /// <summary>
        /// Update current segment index (progress)
        /// </summary>
        public void UpdateProgress(int segmentIndex)
        {
            _currentSegmentIndex = segmentIndex;
            UpdateSegmentColors();
            OnProgressUpdate?.Invoke(segmentIndex, _segments.Count);

            if (segmentIndex >= _segments.Count - 1)
            {
                OnPathCompleted?.Invoke();
            }
        }

        /// <summary>
        /// Clear all toolpath visualization
        /// </summary>
        public void ClearPath()
        {
            foreach (var renderer in _lineRenderers)
            {
                if (renderer != null)
                {
                    Destroy(renderer.gameObject);
                }
            }
            _lineRenderers.Clear();
            _segments.Clear();
            _currentSegmentIndex = 0;
        }

        /// <summary>
        /// Get total path length
        /// </summary>
        public float GetTotalLength()
        {
            return _totalPathLength;
        }

        /// <summary>
        /// Get progress percentage
        /// </summary>
        public float GetProgressPercent()
        {
            if (_segments.Count == 0) return 0f;
            return (float)_currentSegmentIndex / _segments.Count * 100f;
        }

        /// <summary>
        /// Highlight specific segment
        /// </summary>
        public void HighlightSegment(int index, Color color)
        {
            if (index < 0 || index >= _lineRenderers.Count) return;
            _lineRenderers[index].startColor = color;
            _lineRenderers[index].endColor = color;
        }

        #endregion

        #region Private Methods

        private System.Collections.IEnumerator FetchToolpath()
        {
            var url = $"{flaskServerUrl}/api/gcode/toolpath?program_id={programId}";
            var task = _httpClient.GetStringAsync(url);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted)
            {
                Debug.LogError($"[Toolpath] Fetch failed: {task.Exception?.Message}");
                OnError?.Invoke($"Failed to load toolpath: {task.Exception?.Message}");
                yield break;
            }

            try
            {
                var response = JsonConvert.DeserializeObject<ToolpathResponse>(task.Result);
                ProcessToolpath(response);
            }
            catch (Exception e)
            {
                Debug.LogError($"[Toolpath] Parse error: {e.Message}");
                OnError?.Invoke($"Parse error: {e.Message}");
            }
        }

        private void ProcessToolpath(ToolpathResponse response)
        {
            ClearPath();

            if (response.segments == null || response.segments.Count == 0)
            {
                Debug.LogWarning("[Toolpath] No segments in response");
                return;
            }

            // Limit segments for performance
            int segmentCount = Mathf.Min(response.segments.Count, maxSegments);
            _segments = response.segments.GetRange(0, segmentCount);

            // Calculate total path length
            _totalPathLength = 0f;
            foreach (var segment in _segments)
            {
                _totalPathLength += segment.length;
            }

            // Create line renderers
            StartCoroutine(CreateLineRenderers());
        }

        private System.Collections.IEnumerator CreateLineRenderers()
        {
            int created = 0;
            foreach (var segment in _segments)
            {
                CreateSegmentRenderer(segment);
                created++;

                if (created % segmentsPerFrame == 0)
                {
                    yield return null; // Spread over multiple frames
                }
            }

            Debug.Log($"[Toolpath] Created {_segments.Count} segments, total length: {_totalPathLength:F2} mm");
        }

        private void CreateSegmentRenderer(ToolpathSegment segment)
        {
            var go = new GameObject($"Segment_{_lineRenderers.Count}");
            go.transform.SetParent(transform);

            var lr = go.AddComponent<LineRenderer>();
            lr.material = pathMaterial != null ? pathMaterial : new Material(Shader.Find("Sprites/Default"));
            lr.startColor = pathColor;
            lr.endColor = pathColor;
            lr.startWidth = lineWidth;
            lr.endWidth = lineWidth;
            lr.positionCount = 2;

            // Convert from machine coordinates to Unity coordinates (Y<->Z swap)
            var start = new Vector3(segment.start.x, segment.start.z, segment.start.y);
            var end = new Vector3(segment.end.x, segment.end.z, segment.end.y);

            lr.SetPosition(0, start);
            lr.SetPosition(1, end);

            lr.useWorldSpace = true;
            lr.alignment = LineAlignment.View;

            _lineRenderers.Add(lr);
        }

        private void UpdateSegmentColors()
        {
            for (int i = 0; i < _lineRenderers.Count; i++)
            {
                if (_lineRenderers[i] == null) continue;

                Color color;
                if (i < _currentSegmentIndex)
                {
                    color = completedColor; // Completed segments
                }
                else if (i == _currentSegmentIndex)
                {
                    color = currentColor; // Current segment
                }
                else
                {
                    color = pathColor; // Upcoming segments
                }

                _lineRenderers[i].startColor = color;
                _lineRenderers[i].endColor = color;
            }
        }

        private void UpdateLOD()
        {
            if (!enableLOD || _mainCamera == null) return;

            var camPos = _mainCamera.transform.position;

            for (int i = 0; i < _lineRenderers.Count; i++)
            {
                if (_lineRenderers[i] == null) continue;

                // Calculate distance to camera
                var segmentPos = _lineRenderers[i].transform.position;
                float distance = Vector3.Distance(camPos, segmentPos);

                // Adjust line width based on distance
                float width = lineWidth;
                if (distance > lowDetailDistance)
                {
                    width = lineWidth * 0.25f;
                }
                else if (distance > mediumDetailDistance)
                {
                    width = lineWidth * 0.5f;
                }
                else if (distance > highDetailDistance)
                {
                    width = lineWidth * 0.75f;
                }

                _lineRenderers[i].startWidth = width;
                _lineRenderers[i].endWidth = width;
            }
        }

        private void UpdateFrustumCulling()
        {
            _frustumPlanes = GeometryUtility.CalculateFrustumPlanes(_mainCamera);

            foreach (var lr in _lineRenderers)
            {
                if (lr == null) continue;

                var bounds = lr.bounds;
                bool visible = GeometryUtility.TestPlanesAABB(_frustumPlanes, bounds);
                lr.enabled = visible;
            }
        }

        #endregion

        #region Gizmos

        void OnDrawGizmos()
        {
            if (!Application.isPlaying || _segments == null) return;

            // Draw current segment in editor
            if (_currentSegmentIndex >= 0 && _currentSegmentIndex < _segments.Count)
            {
                var seg = _segments[_currentSegmentIndex];
                Gizmos.color = Color.cyan;
                Gizmos.DrawLine(
                    new Vector3(seg.start.x, seg.start.z, seg.start.y),
                    new Vector3(seg.end.x, seg.end.z, seg.end.y)
                );
            }
        }

        #endregion
    }

    #region Data Classes

    [Serializable]
    public class ToolpathResponse
    {
        public string programId;
        public List<ToolpathSegment> segments;
        public float totalLength;
        public float estimatedTime;
    }

    [Serializable]
    public class ToolpathSegment
    {
        public int index;
        public ToolpathPoint start;
        public ToolpathPoint end;
        public float length;
        public float feedRate;
        public string moveType; // G0, G1, G2, G3
        public int lineNumber;
    }

    [Serializable]
    public class ToolpathPoint
    {
        public float x;
        public float y;
        public float z;
    }

    #endregion
}
