using UnityEngine;
using System;
using System.Collections.Generic;
using System.Linq;

namespace CNCScada.Scheduling
{
    /// <summary>
    /// Visualizes machine capacity utilization over time
    /// Shows bottlenecks, idle time, and capacity constraints
    /// </summary>
    public class MachineCapacityView : MonoBehaviour
    {
        #region Serialized Fields

        [Header("View Settings")]
        [SerializeField] private float barWidth = 40f;
        [SerializeField] private float maxHeight = 200f;
        [SerializeField] private bool showPercentageLabels = true;

        [Header("Colors")]
        [SerializeField] private Color utilizationColor = Color.green;
        [SerializeField] private Color setupColor = Color.yellow;
        [SerializeField] private Color idleColor = Color.gray;
        [SerializeField] private Color overloadColor = Color.red;

        [Header("UI References")]
        [SerializeField] private RectTransform containerTransform;
        [SerializeField] private GameObject barPrefab;

        #endregion

        #region Private Fields

        private List<GameObject> _bars;
        private Dictionary<string, MachineCapacity> _capacityData;

        #endregion

        #region Events

        public event Action<string> OnMachineClicked;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _bars = new List<GameObject>();
            _capacityData = new Dictionary<string, MachineCapacity>();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Update capacity data for machines
        /// </summary>
        public void UpdateCapacity(List<ScheduledJob> jobs, DateTime startTime, DateTime endTime)
        {
            CalculateCapacity(jobs, startTime, endTime);
            RefreshView();
        }

        /// <summary>
        /// Get bottleneck machines (>90% utilization)
        /// </summary>
        public List<string> GetBottlenecks()
        {
            return _capacityData
                .Where(kvp => kvp.Value.utilizationPercent > 90f)
                .Select(kvp => kvp.Key)
                .ToList();
        }

        /// <summary>
        /// Get underutilized machines (<50% utilization)
        /// </summary>
        public List<string> GetUnderutilized()
        {
            return _capacityData
                .Where(kvp => kvp.Value.utilizationPercent < 50f)
                .Select(kvp => kvp.Key)
                .ToList();
        }

        #endregion

        #region Private Methods

        private void CalculateCapacity(List<ScheduledJob> jobs, DateTime start, DateTime end)
        {
            _capacityData.Clear();

            var totalHours = (end - start).TotalHours;
            var machineGroups = jobs.GroupBy(j => j.machineId);

            foreach (var group in machineGroups)
            {
                var capacity = new MachineCapacity
                {
                    machineId = group.Key,
                    totalHours = totalHours
                };

                foreach (var job in group)
                {
                    var duration = (job.endTime - job.startTime).TotalHours;
                    if (job.isSetup)
                    {
                        capacity.setupHours += duration;
                    }
                    else
                    {
                        capacity.productionHours += duration;
                    }
                }

                capacity.idleHours = totalHours - capacity.productionHours - capacity.setupHours;
                capacity.utilizationPercent = (float)((capacity.productionHours + capacity.setupHours) / totalHours * 100);

                _capacityData[group.Key] = capacity;
            }
        }

        private void RefreshView()
        {
            ClearBars();

            if (containerTransform == null) return;

            float xOffset = 0f;
            foreach (var kvp in _capacityData.OrderBy(k => k.Key))
            {
                CreateCapacityBar(kvp.Value, xOffset);
                xOffset += barWidth + 10f;
            }
        }

        private void CreateCapacityBar(MachineCapacity capacity, float xOffset)
        {
            GameObject barObj;
            if (barPrefab != null)
            {
                barObj = Instantiate(barPrefab, containerTransform);
            }
            else
            {
                barObj = new GameObject($"Bar_{capacity.machineId}");
                barObj.transform.SetParent(containerTransform);
            }

            var rectTransform = barObj.GetComponent<RectTransform>();
            if (rectTransform == null)
            {
                rectTransform = barObj.AddComponent<RectTransform>();
            }

            rectTransform.anchorMin = new Vector2(0, 0);
            rectTransform.anchorMax = new Vector2(0, 0);
            rectTransform.anchoredPosition = new Vector2(xOffset + barWidth / 2f, 0);

            // Create stacked segments
            CreateSegment(barObj, "Production", capacity.productionHours, capacity.totalHours, 0, utilizationColor);
            float setupOffset = (float)(capacity.productionHours / capacity.totalHours * maxHeight);
            CreateSegment(barObj, "Setup", capacity.setupHours, capacity.totalHours, setupOffset, setupColor);

            // Add label
            CreateLabel(barObj, capacity.machineId, capacity.utilizationPercent);

            _bars.Add(barObj);
        }

        private void CreateSegment(GameObject parent, string name, double hours, double totalHours, float yOffset, Color color)
        {
            if (hours <= 0) return;

            var segmentObj = new GameObject(name);
            segmentObj.transform.SetParent(parent.transform);

            var rect = segmentObj.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0.5f, 0);
            rect.anchorMax = new Vector2(0.5f, 0);
            rect.anchoredPosition = new Vector2(0, yOffset);

            float height = (float)(hours / totalHours * maxHeight);
            rect.sizeDelta = new Vector2(barWidth, height);

            var image = segmentObj.AddComponent<UnityEngine.UI.Image>();
            image.color = color;
        }

        private void CreateLabel(GameObject parent, string machineId, float utilPercent)
        {
            var labelObj = new GameObject("Label");
            labelObj.transform.SetParent(parent.transform);

            var rect = labelObj.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0.5f, 0);
            rect.anchorMax = new Vector2(0.5f, 0);
            rect.anchoredPosition = new Vector2(0, maxHeight + 10f);
            rect.sizeDelta = new Vector2(barWidth, 40f);

            var text = labelObj.AddComponent<UnityEngine.UI.Text>();
            text.text = showPercentageLabels ? $"{machineId}\n{utilPercent:F1}%" : machineId;
            text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            text.fontSize = 12;
            text.alignment = TextAnchor.UpperCenter;
            text.color = Color.white;
        }

        private void ClearBars()
        {
            foreach (var bar in _bars)
            {
                if (bar != null)
                {
                    Destroy(bar);
                }
            }
            _bars.Clear();
        }

        #endregion
    }

    #region Data Classes

    public class MachineCapacity
    {
        public string machineId;
        public double totalHours;
        public double productionHours;
        public double setupHours;
        public double idleHours;
        public float utilizationPercent;
    }

    #endregion
}
