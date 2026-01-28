using UnityEngine;
using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Linq;
using Newtonsoft.Json;

namespace CNCScada.Scheduling
{
    /// <summary>
    /// Interactive Gantt chart controller for production scheduling
    /// Supports drag-drop rescheduling, multi-machine view, and optimization
    /// </summary>
    public class GanttChartController : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";

        [Header("View Settings")]
        [SerializeField] private int scheduleHorizonDays = 7;
        [SerializeField] private float pixelsPerHour = 50f;
        [SerializeField] private float rowHeight = 40f;
        [SerializeField] private bool showWeekends = true;
        [SerializeField] private bool showShiftBoundaries = true;

        [Header("Job Colors")]
        [SerializeField] private Color scheduledColor = Color.green;
        [SerializeField] private Color runningColor = Color.yellow;
        [SerializeField] private Color completedColor = Color.gray;
        [SerializeField] private Color delayedColor = Color.red;
        [SerializeField] private Color setupColor = Color.cyan;

        [Header("UI References")]
        [SerializeField] private RectTransform chartContainer;
        [SerializeField] private GameObject jobBarPrefab;
        [SerializeField] private GameObject machineRowPrefab;

        [Header("Auto-refresh")]
        [SerializeField] private bool autoRefresh = true;
        [SerializeField] private float refreshInterval = 30f;

        #endregion

        #region Private Fields

        private HttpClient _httpClient;
        private List<ScheduledJob> _jobs;
        private List<MachineRow> _machineRows;
        private Dictionary<string, GameObject> _jobBars;
        private DateTime _scheduleStart;
        private DateTime _scheduleEnd;
        private float _lastRefreshTime;

        #endregion

        #region Events

        public event Action<ScheduledJob> OnJobClicked;
        public event Action<ScheduledJob, DateTime> OnJobRescheduled;
        public event Action<string> OnMachineClicked;
        public event Action<string> OnError;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(10);
            _jobs = new List<ScheduledJob>();
            _machineRows = new List<MachineRow>();
            _jobBars = new Dictionary<string, GameObject>();

            _scheduleStart = DateTime.Now.Date;
            _scheduleEnd = _scheduleStart.AddDays(scheduleHorizonDays);

            LoadSchedule();
        }

        void Update()
        {
            if (autoRefresh && Time.time - _lastRefreshTime >= refreshInterval)
            {
                LoadSchedule();
                _lastRefreshTime = Time.time;
            }
        }

        void OnDestroy()
        {
            _httpClient?.Dispose();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Load schedule from backend
        /// </summary>
        public void LoadSchedule()
        {
            StartCoroutine(FetchSchedule());
        }

        /// <summary>
        /// Refresh the Gantt chart display
        /// </summary>
        public void RefreshChart()
        {
            ClearChart();
            BuildChart();
        }

        /// <summary>
        /// Set schedule time window
        /// </summary>
        public void SetTimeWindow(DateTime start, DateTime end)
        {
            _scheduleStart = start;
            _scheduleEnd = end;
            RefreshChart();
        }

        /// <summary>
        /// Zoom in/out on timeline
        /// </summary>
        public void SetZoom(float pixelsPerHour)
        {
            this.pixelsPerHour = Mathf.Clamp(pixelsPerHour, 10f, 200f);
            RefreshChart();
        }

        /// <summary>
        /// Scroll to specific job
        /// </summary>
        public void ScrollToJob(string jobId)
        {
            if (_jobBars.TryGetValue(jobId, out GameObject jobBar))
            {
                var scrollRect = GetComponentInParent<UnityEngine.UI.ScrollRect>();
                if (scrollRect != null)
                {
                    Canvas.ForceUpdateCanvases();
                    var targetPos = (Vector2)scrollRect.transform.InverseTransformPoint(jobBar.transform.position);
                    scrollRect.content.anchoredPosition = -targetPos;
                }
            }
        }

        /// <summary>
        /// Filter jobs by machine
        /// </summary>
        public void FilterByMachine(string machineId)
        {
            foreach (var row in _machineRows)
            {
                row.gameObject.SetActive(string.IsNullOrEmpty(machineId) || row.machineId == machineId);
            }
        }

        /// <summary>
        /// Get jobs for specific machine
        /// </summary>
        public List<ScheduledJob> GetJobsForMachine(string machineId)
        {
            return _jobs.Where(j => j.machineId == machineId).ToList();
        }

        /// <summary>
        /// Get critical path jobs
        /// </summary>
        public List<ScheduledJob> GetCriticalPath()
        {
            return _jobs.Where(j => j.isCriticalPath).ToList();
        }

        #endregion

        #region Private Methods

        private System.Collections.IEnumerator FetchSchedule()
        {
            var startStr = _scheduleStart.ToString("yyyy-MM-dd");
            var endStr = _scheduleEnd.ToString("yyyy-MM-dd");
            var url = $"{flaskServerUrl}/api/schedule?start={startStr}&end={endStr}";

            var task = _httpClient.GetStringAsync(url);
            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted)
            {
                Debug.LogError($"[GanttChart] Fetch failed: {task.Exception?.Message}");
                OnError?.Invoke($"Failed to load schedule: {task.Exception?.Message}");
                yield break;
            }

            try
            {
                var response = JsonConvert.DeserializeObject<ScheduleResponse>(task.Result);
                _jobs = response.jobs ?? new List<ScheduledJob>();
                RefreshChart();
            }
            catch (Exception e)
            {
                Debug.LogError($"[GanttChart] Parse error: {e.Message}");
                OnError?.Invoke($"Parse error: {e.Message}");
            }
        }

        private void BuildChart()
        {
            if (chartContainer == null)
            {
                Debug.LogWarning("[GanttChart] Chart container not assigned");
                return;
            }

            // Group jobs by machine
            var machineGroups = _jobs.GroupBy(j => j.machineId).OrderBy(g => g.Key);

            float yOffset = 0;
            foreach (var group in machineGroups)
            {
                var row = CreateMachineRow(group.Key, yOffset);
                _machineRows.Add(row);

                // Create job bars for this machine
                foreach (var job in group)
                {
                    CreateJobBar(job, row.transform, yOffset);
                }

                yOffset += rowHeight;
            }

            // Update container size
            var containerRect = chartContainer.GetComponent<RectTransform>();
            containerRect.sizeDelta = new Vector2(
                GetChartWidth(),
                yOffset
            );
        }

        private MachineRow CreateMachineRow(string machineId, float yOffset)
        {
            GameObject rowObj;
            if (machineRowPrefab != null)
            {
                rowObj = Instantiate(machineRowPrefab, chartContainer);
            }
            else
            {
                rowObj = new GameObject($"Row_{machineId}");
                rowObj.transform.SetParent(chartContainer);

                var rowImage = rowObj.AddComponent<UnityEngine.UI.Image>();
                rowImage.color = new Color(0.2f, 0.2f, 0.2f, 0.3f);
            }

            var rectTransform = rowObj.GetComponent<RectTransform>();
            rectTransform.anchorMin = new Vector2(0, 1);
            rectTransform.anchorMax = new Vector2(1, 1);
            rectTransform.anchoredPosition = new Vector2(0, -yOffset);
            rectTransform.sizeDelta = new Vector2(0, rowHeight);

            var row = rowObj.AddComponent<MachineRow>();
            row.machineId = machineId;
            row.OnClicked += () => OnMachineClicked?.Invoke(machineId);

            // Add label
            CreateRowLabel(rowObj, machineId);

            return row;
        }

        private void CreateRowLabel(GameObject rowObj, string machineId)
        {
            var labelObj = new GameObject("Label");
            labelObj.transform.SetParent(rowObj.transform);

            var labelRect = labelObj.AddComponent<RectTransform>();
            labelRect.anchorMin = new Vector2(0, 0);
            labelRect.anchorMax = new Vector2(0, 1);
            labelRect.anchoredPosition = new Vector2(60, 0);
            labelRect.sizeDelta = new Vector2(120, 0);

            var text = labelObj.AddComponent<UnityEngine.UI.Text>();
            text.text = machineId;
            text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            text.fontSize = 14;
            text.alignment = TextAnchor.MiddleLeft;
            text.color = Color.white;
        }

        private void CreateJobBar(ScheduledJob job, Transform parent, float yOffset)
        {
            GameObject barObj;
            if (jobBarPrefab != null)
            {
                barObj = Instantiate(jobBarPrefab, parent);
            }
            else
            {
                barObj = new GameObject($"Job_{job.jobId}");
                barObj.transform.SetParent(parent);

                var barImage = barObj.AddComponent<UnityEngine.UI.Image>();
                barImage.color = GetJobColor(job);

                var button = barObj.AddComponent<UnityEngine.UI.Button>();
                button.onClick.AddListener(() => OnJobClicked?.Invoke(job));
            }

            // Position and size based on time
            var rectTransform = barObj.GetComponent<RectTransform>();
            rectTransform.anchorMin = new Vector2(0, 0);
            rectTransform.anchorMax = new Vector2(0, 1);

            float xStart = GetTimePosition(job.startTime);
            float width = GetDurationWidth(job.startTime, job.endTime);

            rectTransform.anchoredPosition = new Vector2(xStart + width / 2f, 0);
            rectTransform.sizeDelta = new Vector2(width, rowHeight - 4);

            // Add job label
            CreateJobLabel(barObj, job);

            // Add drag handler
            var dragHandler = barObj.AddComponent<JobDragDropHandler>();
            dragHandler.Initialize(this, job);
            dragHandler.OnJobDropped += (newTime) => HandleJobRescheduled(job, newTime);

            _jobBars[job.jobId] = barObj;
        }

        private void CreateJobLabel(GameObject barObj, ScheduledJob job)
        {
            var labelObj = new GameObject("Label");
            labelObj.transform.SetParent(barObj.transform);

            var labelRect = labelObj.AddComponent<RectTransform>();
            labelRect.anchorMin = Vector2.zero;
            labelRect.anchorMax = Vector2.one;
            labelRect.offsetMin = new Vector2(4, 0);
            labelRect.offsetMax = new Vector2(-4, 0);

            var text = labelObj.AddComponent<UnityEngine.UI.Text>();
            text.text = job.jobName;
            text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            text.fontSize = 12;
            text.alignment = TextAnchor.MiddleLeft;
            text.color = Color.black;
            text.resizeTextForBestFit = true;
            text.resizeTextMinSize = 8;
            text.resizeTextMaxSize = 12;
        }

        private void HandleJobRescheduled(ScheduledJob job, DateTime newTime)
        {
            OnJobRescheduled?.Invoke(job, newTime);
            StartCoroutine(SendRescheduleRequest(job, newTime));
        }

        private System.Collections.IEnumerator SendRescheduleRequest(ScheduledJob job, DateTime newTime)
        {
            var url = $"{flaskServerUrl}/api/schedule/reschedule";
            var data = new
            {
                jobId = job.jobId,
                newStartTime = newTime.ToString("yyyy-MM-ddTHH:mm:ss"),
                machineId = job.machineId
            };

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                Debug.LogError($"[GanttChart] Reschedule failed");
                OnError?.Invoke("Failed to reschedule job");
                LoadSchedule(); // Reload to revert changes
            }
            else
            {
                Debug.Log($"[GanttChart] Job {job.jobId} rescheduled to {newTime}");
                LoadSchedule(); // Reload to get updated schedule
            }
        }

        private Color GetJobColor(ScheduledJob job)
        {
            if (job.status == "completed") return completedColor;
            if (job.status == "running") return runningColor;
            if (job.isDelayed) return delayedColor;
            if (job.isSetup) return setupColor;
            return scheduledColor;
        }

        private float GetTimePosition(DateTime time)
        {
            var duration = time - _scheduleStart;
            return (float)duration.TotalHours * pixelsPerHour + 150f; // 150px offset for labels
        }

        private float GetDurationWidth(DateTime start, DateTime end)
        {
            var duration = end - start;
            return (float)duration.TotalHours * pixelsPerHour;
        }

        private float GetChartWidth()
        {
            var duration = _scheduleEnd - _scheduleStart;
            return (float)duration.TotalHours * pixelsPerHour + 200f;
        }

        private void ClearChart()
        {
            foreach (var row in _machineRows)
            {
                if (row != null && row.gameObject != null)
                {
                    Destroy(row.gameObject);
                }
            }
            _machineRows.Clear();
            _jobBars.Clear();
        }

        #endregion
    }

    #region Helper Classes

    public class MachineRow : MonoBehaviour
    {
        public string machineId;
        public event Action OnClicked;

        public void OnPointerClick()
        {
            OnClicked?.Invoke();
        }
    }

    #endregion

    #region Data Classes

    [Serializable]
    public class ScheduleResponse
    {
        public List<ScheduledJob> jobs;
        public DateTime scheduleStart;
        public DateTime scheduleEnd;
    }

    [Serializable]
    public class ScheduledJob
    {
        public string jobId;
        public string jobName;
        public string machineId;
        public DateTime startTime;
        public DateTime endTime;
        public string status; // scheduled, running, completed
        public bool isDelayed;
        public bool isSetup;
        public bool isCriticalPath;
        public int priority;
        public Dictionary<string, object> metadata;
    }

    #endregion
}
