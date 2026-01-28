using UnityEngine;
using UnityEngine.EventSystems;
using System;

namespace CNCScada.Scheduling
{
    /// <summary>
    /// Handles drag and drop for job rescheduling in Gantt chart
    /// Supports snap-to-grid, constraint validation, and visual feedback
    /// </summary>
    [RequireComponent(typeof(RectTransform))]
    public class JobDragDropHandler : MonoBehaviour, IBeginDragHandler, IDragHandler, IEndDragHandler
    {
        #region Private Fields

        private RectTransform _rectTransform;
        private Canvas _canvas;
        private CanvasGroup _canvasGroup;
        private Vector2 _originalPosition;
        private GanttChartController _ganttController;
        private ScheduledJob _job;
        private bool _isDragging;

        [SerializeField] private float snapToGridMinutes = 15f;
        [SerializeField] private bool validateConstraints = true;
        [SerializeField] private Color dragColor = new Color(1f, 1f, 1f, 0.6f);

        #endregion

        #region Events

        public event Action<DateTime> OnJobDropped;
        public event Action OnDragStarted;
        public event Action OnDragCancelled;

        #endregion

        #region Lifecycle

        void Awake()
        {
            _rectTransform = GetComponent<RectTransform>();
            _canvas = GetComponentInParent<Canvas>();

            _canvasGroup = GetComponent<CanvasGroup>();
            if (_canvasGroup == null)
            {
                _canvasGroup = gameObject.AddComponent<CanvasGroup>();
            }
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Initialize drag handler with job data
        /// </summary>
        public void Initialize(GanttChartController controller, ScheduledJob job)
        {
            _ganttController = controller;
            _job = job;
        }

        #endregion

        #region Drag Handlers

        public void OnBeginDrag(PointerEventData eventData)
        {
            _originalPosition = _rectTransform.anchoredPosition;
            _isDragging = true;

            _canvasGroup.alpha = 0.6f;
            _canvasGroup.blocksRaycasts = false;

            OnDragStarted?.Invoke();
        }

        public void OnDrag(PointerEventData eventData)
        {
            if (!_isDragging) return;

            Vector2 localPoint;
            RectTransformUtility.ScreenPointToLocalPointInRectangle(
                _rectTransform.parent as RectTransform,
                eventData.position,
                eventData.pressEventCamera,
                out localPoint
            );

            _rectTransform.anchoredPosition = new Vector2(localPoint.x, _originalPosition.y);
        }

        public void OnEndDrag(PointerEventData eventData)
        {
            _isDragging = false;
            _canvasGroup.alpha = 1f;
            _canvasGroup.blocksRaycasts = true;

            // Calculate new start time based on position
            DateTime newStartTime = CalculateTimeFromPosition(_rectTransform.anchoredPosition.x);

            // Snap to grid
            if (snapToGridMinutes > 0)
            {
                newStartTime = SnapToGrid(newStartTime, snapToGridMinutes);
            }

            // Validate constraints
            if (validateConstraints && !IsValidTime(newStartTime))
            {
                // Revert to original position
                _rectTransform.anchoredPosition = _originalPosition;
                OnDragCancelled?.Invoke();
                return;
            }

            // Accept the drop
            OnJobDropped?.Invoke(newStartTime);
        }

        #endregion

        #region Private Methods

        private DateTime CalculateTimeFromPosition(float xPosition)
        {
            // Get chart settings from controller
            float pixelsPerHour = _ganttController != null ?
                _ganttController.GetType().GetField("pixelsPerHour", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)?.GetValue(_ganttController) as float? ?? 50f : 50f;

            float labelOffset = 150f; // Offset for machine labels
            float hours = (xPosition - labelOffset) / pixelsPerHour;

            DateTime scheduleStart = DateTime.Now.Date; // Should get from controller
            return scheduleStart.AddHours(hours);
        }

        private DateTime SnapToGrid(DateTime time, float intervalMinutes)
        {
            long ticks = time.Ticks;
            long intervalTicks = (long)(intervalMinutes * TimeSpan.TicksPerMinute);
            long snappedTicks = (ticks / intervalTicks) * intervalTicks;
            return new DateTime(snappedTicks);
        }

        private bool IsValidTime(DateTime newTime)
        {
            // Check if time is within business hours
            if (newTime.Hour < 6 || newTime.Hour >= 22)
            {
                return false;
            }

            // Check if time is on weekend (optional)
            if (newTime.DayOfWeek == DayOfWeek.Saturday || newTime.DayOfWeek == DayOfWeek.Sunday)
            {
                return false;
            }

            return true;
        }

        #endregion
    }
}
