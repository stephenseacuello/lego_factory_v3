using UnityEngine;
using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Linq;
using Newtonsoft.Json;

namespace CNCScada.Predictive
{
    /// <summary>
    /// AR maintenance calendar overlay
    /// Displays predicted maintenance events, RUL timelines, and scheduling
    /// </summary>
    public class MaintenanceCalendarAR : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";

        [Header("Prediction Settings")]
        [SerializeField] private int predictionHorizonDays = 30;
        [SerializeField] private float confidenceThreshold = 0.7f;
        [SerializeField] private bool showLowConfidence = false;

        [Header("AR Display")]
        [SerializeField] private Transform arAnchor;
        [SerializeField] private GameObject eventMarkerPrefab;
        [SerializeField] private float markerSpacing = 2f;
        [SerializeField] private float timelineHeight = 1.5f;

        [Header("Visual Settings")]
        [SerializeField] private Color criticalColor = Color.red;
        [SerializeField] private Color warningColor = Color.yellow;
        [SerializeField] private Color infoColor = Color.blue;
        [SerializeField] private bool showConnectionLines = true;

        [Header("Update Settings")]
        [SerializeField] private float updateInterval = 300f; // 5 minutes
        [SerializeField] private bool autoRefresh = true;

        #endregion

        #region Private Fields

        private HttpClient _httpClient;
        private List<MaintenanceEvent> _events;
        private Dictionary<string, GameObject> _eventMarkers;
        private LineRenderer _timelineRenderer;
        private float _lastUpdateTime;

        #endregion

        #region Events

        public event Action<MaintenanceEvent> OnEventClicked;
        public event Action<MaintenanceEvent> OnEventScheduled;
        public event Action<string> OnError;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(10);
            _events = new List<MaintenanceEvent>();
            _eventMarkers = new Dictionary<string, GameObject>();

            if (arAnchor == null)
            {
                arAnchor = transform;
            }

            CreateTimeline();
            LoadMaintenanceEvents();
        }

        void Update()
        {
            if (autoRefresh && Time.time - _lastUpdateTime >= updateInterval)
            {
                LoadMaintenanceEvents();
                _lastUpdateTime = Time.time;
            }

            // Make markers face camera
            if (Camera.main != null)
            {
                foreach (var marker in _eventMarkers.Values)
                {
                    if (marker != null)
                    {
                        marker.transform.LookAt(Camera.main.transform);
                        marker.transform.Rotate(0, 180, 0);
                    }
                }
            }
        }

        void OnDestroy()
        {
            _httpClient?.Dispose();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Load maintenance predictions from backend
        /// </summary>
        public void LoadMaintenanceEvents()
        {
            StartCoroutine(FetchMaintenanceEvents());
        }

        /// <summary>
        /// Filter events by severity
        /// </summary>
        public void FilterBySeverity(MaintenanceSeverity severity)
        {
            foreach (var kvp in _eventMarkers)
            {
                var eventData = _events.FirstOrDefault(e => e.id == kvp.Key);
                bool visible = eventData != null && (severity == MaintenanceSeverity.All || eventData.severity == severity);
                kvp.Value.SetActive(visible);
            }
        }

        /// <summary>
        /// Get events within date range
        /// </summary>
        public List<MaintenanceEvent> GetEventsInRange(DateTime start, DateTime end)
        {
            return _events.Where(e => e.predictedDate >= start && e.predictedDate <= end).ToList();
        }

        /// <summary>
        /// Get critical events (high severity, high confidence)
        /// </summary>
        public List<MaintenanceEvent> GetCriticalEvents()
        {
            return _events.Where(e =>
                e.severity == MaintenanceSeverity.Critical &&
                e.confidence >= confidenceThreshold
            ).ToList();
        }

        /// <summary>
        /// Schedule maintenance event
        /// </summary>
        public void ScheduleEvent(string eventId, DateTime scheduledDate)
        {
            var evt = _events.FirstOrDefault(e => e.id == eventId);
            if (evt != null)
            {
                StartCoroutine(SendScheduleRequest(evt, scheduledDate));
            }
        }

        /// <summary>
        /// Highlight specific event
        /// </summary>
        public void HighlightEvent(string eventId, bool highlight)
        {
            if (_eventMarkers.TryGetValue(eventId, out GameObject marker))
            {
                var scale = highlight ? Vector3.one * 1.5f : Vector3.one;
                marker.transform.localScale = scale;
            }
        }

        #endregion

        #region Private Methods

        private void CreateTimeline()
        {
            var timelineObj = new GameObject("Timeline");
            timelineObj.transform.SetParent(arAnchor);
            timelineObj.transform.localPosition = Vector3.zero;

            _timelineRenderer = timelineObj.AddComponent<LineRenderer>();
            _timelineRenderer.material = new Material(Shader.Find("Sprites/Default"));
            _timelineRenderer.startColor = Color.white;
            _timelineRenderer.endColor = Color.white;
            _timelineRenderer.startWidth = 0.02f;
            _timelineRenderer.endWidth = 0.02f;
            _timelineRenderer.positionCount = 2;

            float timelineLength = predictionHorizonDays / 30f * 3f; // 3m per month
            _timelineRenderer.SetPosition(0, Vector3.zero);
            _timelineRenderer.SetPosition(1, new Vector3(timelineLength, 0, 0));
        }

        private System.Collections.IEnumerator FetchMaintenanceEvents()
        {
            var endDate = DateTime.Now.AddDays(predictionHorizonDays);
            var url = $"{flaskServerUrl}/api/predictive/maintenance?machine_id={machineId}&horizon_days={predictionHorizonDays}&confidence_threshold={confidenceThreshold}";

            var task = _httpClient.GetStringAsync(url);
            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted)
            {
                Debug.LogError($"[MaintenanceCalendar] Fetch failed: {task.Exception?.Message}");
                OnError?.Invoke($"Failed to load maintenance events: {task.Exception?.Message}");
                yield break;
            }

            try
            {
                var response = JsonConvert.DeserializeObject<MaintenanceResponse>(task.Result);
                _events = response.events ?? new List<MaintenanceEvent>();
                RefreshDisplay();
            }
            catch (Exception e)
            {
                Debug.LogError($"[MaintenanceCalendar] Parse error: {e.Message}");
                OnError?.Invoke($"Parse error: {e.Message}");
            }
        }

        private void RefreshDisplay()
        {
            ClearMarkers();

            foreach (var evt in _events)
            {
                if (!showLowConfidence && evt.confidence < confidenceThreshold)
                {
                    continue;
                }

                CreateEventMarker(evt);
            }

            Debug.Log($"[MaintenanceCalendar] Displaying {_eventMarkers.Count} maintenance events");
        }

        private void CreateEventMarker(MaintenanceEvent evt)
        {
            GameObject markerObj;
            if (eventMarkerPrefab != null)
            {
                markerObj = Instantiate(eventMarkerPrefab, arAnchor);
            }
            else
            {
                markerObj = CreateDefaultMarker(evt);
            }

            // Position on timeline
            var daysUntil = (evt.predictedDate - DateTime.Now).TotalDays;
            float xPos = (float)(daysUntil / predictionHorizonDays) * (predictionHorizonDays / 30f * 3f);
            markerObj.transform.localPosition = new Vector3(xPos, timelineHeight, 0);

            // Color based on severity
            var renderer = markerObj.GetComponent<Renderer>();
            if (renderer != null)
            {
                renderer.material.color = GetSeverityColor(evt.severity);
            }

            // Add click handler
            var clickHandler = markerObj.AddComponent<EventClickHandler>();
            clickHandler.Initialize(evt, () => OnEventClicked?.Invoke(evt));

            // Add label
            CreateEventLabel(markerObj, evt);

            // Add connection line
            if (showConnectionLines)
            {
                CreateConnectionLine(markerObj, evt);
            }

            _eventMarkers[evt.id] = markerObj;
        }

        private GameObject CreateDefaultMarker(MaintenanceEvent evt)
        {
            var markerObj = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            markerObj.name = $"Event_{evt.id}";
            markerObj.transform.SetParent(arAnchor);
            markerObj.transform.localScale = Vector3.one * 0.2f;
            return markerObj;
        }

        private void CreateEventLabel(GameObject marker, MaintenanceEvent evt)
        {
            var canvas = new GameObject("Canvas");
            canvas.transform.SetParent(marker.transform);
            canvas.transform.localPosition = Vector3.up * 0.3f;

            var canvasComponent = canvas.AddComponent<Canvas>();
            canvasComponent.renderMode = RenderMode.WorldSpace;

            var text = canvas.AddComponent<UnityEngine.UI.Text>();
            text.text = $"{evt.componentName}\n{evt.predictedDate:MM/dd}\n{evt.confidence:P0}";
            text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            text.fontSize = 24;
            text.alignment = TextAnchor.MiddleCenter;
            text.color = Color.white;

            var rectTransform = canvas.GetComponent<RectTransform>();
            rectTransform.sizeDelta = new Vector2(200, 100);
            rectTransform.localScale = Vector3.one * 0.01f;
        }

        private void CreateConnectionLine(GameObject marker, MaintenanceEvent evt)
        {
            var lineObj = new GameObject("ConnectionLine");
            lineObj.transform.SetParent(marker.transform);

            var lineRenderer = lineObj.AddComponent<LineRenderer>();
            lineRenderer.material = new Material(Shader.Find("Sprites/Default"));
            lineRenderer.startColor = GetSeverityColor(evt.severity);
            lineRenderer.endColor = GetSeverityColor(evt.severity);
            lineRenderer.startWidth = 0.01f;
            lineRenderer.endWidth = 0.01f;
            lineRenderer.positionCount = 2;

            lineRenderer.SetPosition(0, marker.transform.position);
            lineRenderer.SetPosition(1, marker.transform.position - new Vector3(0, timelineHeight, 0));
        }

        private Color GetSeverityColor(MaintenanceSeverity severity)
        {
            switch (severity)
            {
                case MaintenanceSeverity.Critical: return criticalColor;
                case MaintenanceSeverity.Warning: return warningColor;
                case MaintenanceSeverity.Info: return infoColor;
                default: return Color.white;
            }
        }

        private System.Collections.IEnumerator SendScheduleRequest(MaintenanceEvent evt, DateTime scheduledDate)
        {
            var url = $"{flaskServerUrl}/api/predictive/maintenance/schedule";
            var data = new
            {
                eventId = evt.id,
                machineId = machineId,
                scheduledDate = scheduledDate.ToString("yyyy-MM-ddTHH:mm:ss"),
                componentName = evt.componentName
            };

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                Debug.LogError("[MaintenanceCalendar] Schedule request failed");
                OnError?.Invoke("Failed to schedule maintenance event");
            }
            else
            {
                Debug.Log($"[MaintenanceCalendar] Event {evt.id} scheduled for {scheduledDate}");
                OnEventScheduled?.Invoke(evt);
            }
        }

        private void ClearMarkers()
        {
            foreach (var marker in _eventMarkers.Values)
            {
                if (marker != null)
                {
                    Destroy(marker);
                }
            }
            _eventMarkers.Clear();
        }

        #endregion
    }

    #region Helper Classes

    public class EventClickHandler : MonoBehaviour
    {
        private MaintenanceEvent _event;
        private Action _onClick;

        public void Initialize(MaintenanceEvent evt, Action onClick)
        {
            _event = evt;
            _onClick = onClick;
        }

        void OnMouseDown()
        {
            _onClick?.Invoke();
        }
    }

    #endregion

    #region Data Classes

    [Serializable]
    public class MaintenanceResponse
    {
        public string machineId;
        public List<MaintenanceEvent> events;
    }

    [Serializable]
    public class MaintenanceEvent
    {
        public string id;
        public string componentName;
        public DateTime predictedDate;
        public float confidence;
        public MaintenanceSeverity severity;
        public string maintenanceType; // preventive, corrective, predictive
        public float estimatedDowntimeHours;
        public string description;
        public bool isScheduled;
        public DateTime? scheduledDate;
    }

    public enum MaintenanceSeverity
    {
        All,
        Info,
        Warning,
        Critical
    }

    #endregion
}
