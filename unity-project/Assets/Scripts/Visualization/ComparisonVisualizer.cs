using System;
using System.Collections.Generic;
using UnityEngine;
using CNCScada.Analytics;

namespace CNCScada.Visualization
{
    /// <summary>
    /// Visualizes comparative analysis data side-by-side.
    /// Part of Feature 2.4: Comparative Analysis (MEDIUM PRIORITY)
    /// </summary>
    public class ComparisonVisualizer : MonoBehaviour
    {
        [Header("Visualization Settings")]
        [SerializeField] private bool enableVisualization = true;
        [SerializeField] private float chartHeight = 2f;
        [SerializeField] private float chartWidth = 4f;
        [SerializeField] private Vector3 chartOffset = Vector3.zero;

        [Header("Colors")]
        [SerializeField] private Color run1Color = Color.blue;
        [SerializeField] private Color run2Color = Color.green;
        [SerializeField] private Color trendLineColor = Color.yellow;
        [SerializeField] private Color anomalyColor = Color.red;

        private ComparativeAnalyzer analyzer;
        private List<Vector3> run1Points = new List<Vector3>();
        private List<Vector3> run2Points = new List<Vector3>();

        void Start()
        {
            analyzer = GetComponent<ComparativeAnalyzer>();
            if (analyzer != null)
            {
                analyzer.OnComparisonCompleted += OnComparisonUpdated;
                analyzer.OnTrendDetected += OnTrendDetected;
                analyzer.OnAnomalyDetected += OnAnomalyDetected;
            }
        }

        void OnDrawGizmos()
        {
            if (!enableVisualization) return;
            DrawComparisonChart();
        }

        private void DrawComparisonChart()
        {
            if (run1Points.Count == 0 && run2Points.Count == 0) return;

            // Draw run 1 data
            Gizmos.color = run1Color;
            for (int i = 0; i < run1Points.Count - 1; i++)
            {
                Vector3 start = transform.TransformPoint(run1Points[i] + chartOffset);
                Vector3 end = transform.TransformPoint(run1Points[i + 1] + chartOffset);
                Gizmos.DrawLine(start, end);
            }

            // Draw run 2 data
            Gizmos.color = run2Color;
            for (int i = 0; i < run2Points.Count - 1; i++)
            {
                Vector3 start = transform.TransformPoint(run2Points[i] + chartOffset);
                Vector3 end = transform.TransformPoint(run2Points[i + 1] + chartOffset);
                Gizmos.DrawLine(start, end);
            }
        }

        private void OnComparisonUpdated(RunComparison comparison)
        {
            UpdateChartData(comparison);
        }

        private void OnTrendDetected(TrendAnalysis trend)
        {
            Debug.Log($"[ComparisonVisualizer] Trend detected: {trend.MetricName} - {trend.Direction}");
        }

        private void OnAnomalyDetected(AnomalyDetection anomaly)
        {
            Debug.LogWarning($"[ComparisonVisualizer] Anomaly detected: {anomaly.MetricName} - {anomaly.Severity}");
        }

        private void UpdateChartData(RunComparison comparison)
        {
            run1Points.Clear();
            run2Points.Clear();

            int metricIndex = 0;
            float xStep = chartWidth / comparison.Metrics.Count;

            foreach (var metric in comparison.Metrics)
            {
                float x = metricIndex * xStep;
                float y1 = Mathf.Clamp(metric.Value.Run1Avg / 100f, 0f, chartHeight);
                float y2 = Mathf.Clamp(metric.Value.Run2Avg / 100f, 0f, chartHeight);

                run1Points.Add(new Vector3(x, y1, 0));
                run2Points.Add(new Vector3(x, y2, 0));

                metricIndex++;
            }
        }

        void OnDestroy()
        {
            if (analyzer != null)
            {
                analyzer.OnComparisonCompleted -= OnComparisonUpdated;
                analyzer.OnTrendDetected -= OnTrendDetected;
                analyzer.OnAnomalyDetected -= OnAnomalyDetected;
            }
        }
    }
}
