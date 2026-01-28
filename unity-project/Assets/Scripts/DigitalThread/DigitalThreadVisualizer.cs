using System.Collections.Generic;
using UnityEngine;
using CNCScada.DigitalThread;

namespace CNCScada.Visualization
{
    /// <summary>
    /// Visualizes digital thread genealogy with interactive timeline and flowchart.
    /// Part of Feature 3.1: Digital Thread Tracing (HIGH PRIORITY - Phase 3)
    /// </summary>
    [RequireComponent(typeof(DigitalThreadTracer))]
    public class DigitalThreadVisualizer : MonoBehaviour
    {
        [Header("Visualization Settings")]
        [SerializeField] private bool enableGizmos = true;
        [SerializeField] private bool showOperationFlow = true;
        [SerializeField] private bool showQualityChecks = true;
        [SerializeField] private bool showToolChanges = true;

        [Header("Display Configuration")]
        [SerializeField] private float nodeSpacing = 2f;
        [SerializeField] private float verticalOffset = 1f;
        [SerializeField] private float gizmoSize = 0.3f;

        [Header("Colors")]
        [SerializeField] private Color materialColor = Color.cyan;
        [SerializeField] private Color operationColor = Color.green;
        [SerializeField] private Color qualityPassColor = Color.blue;
        [SerializeField] private Color qualityFailColor = Color.red;
        [SerializeField] private Color toolChangeColor = Color.yellow;
        [SerializeField] private Color completedColor = Color.white;

        // References
        private DigitalThreadTracer tracer;

        // Visualization data
        private List<Vector3> operationPositions = new List<Vector3>();
        private List<Vector3> qualityCheckPositions = new List<Vector3>();
        private List<Vector3> toolChangePositions = new List<Vector3>();

        void Start()
        {
            tracer = GetComponent<DigitalThreadTracer>();
            if (tracer == null)
            {
                Debug.LogError("[DigitalThreadVisualizer] DigitalThreadTracer not found!");
                enabled = false;
                return;
            }

            // Subscribe to events
            tracer.OnOperationRecorded += OnOperationRecorded;
            tracer.OnQualityCheckRecorded += OnQualityCheckRecorded;
            tracer.OnToolChangeRecorded += OnToolChangeRecorded;
        }

        void OnDrawGizmos()
        {
            if (!enableGizmos || !Application.isPlaying) return;

            DrawDigitalThreadFlow();
        }

        /// <summary>
        /// Draw digital thread flowchart
        /// </summary>
        private void DrawDigitalThreadFlow()
        {
            var thread = tracer?.GetDigitalThread();
            if (thread == null) return;

            Vector3 startPos = transform.position;

            // Draw material origin
            if (thread.MaterialProvenance != null)
            {
                Gizmos.color = materialColor;
                Gizmos.DrawSphere(startPos, gizmoSize);

                #if UNITY_EDITOR
                UnityEditor.Handles.Label(startPos + Vector3.up * 0.5f,
                    $"Material: {thread.MaterialProvenance.MaterialType}");
                #endif
            }

            // Draw operations
            if (showOperationFlow && thread.Operations != null)
            {
                Vector3 currentPos = startPos;

                for (int i = 0; i < thread.Operations.Count; i++)
                {
                    var operation = thread.Operations[i];
                    currentPos += Vector3.right * nodeSpacing;

                    // Choose color based on status
                    Gizmos.color = operation.Status == OperationStatus.Completed ? operationColor :
                                   operation.Status == OperationStatus.Failed ? Color.red :
                                   Color.gray;

                    Gizmos.DrawCube(currentPos, Vector3.one * gizmoSize);

                    // Draw connection line
                    Vector3 prevPos = i == 0 ? startPos : currentPos - Vector3.right * nodeSpacing;
                    Gizmos.color = Color.white * 0.5f;
                    Gizmos.DrawLine(prevPos, currentPos);

                    #if UNITY_EDITOR
                    UnityEditor.Handles.Label(currentPos + Vector3.up * 0.5f,
                        $"{operation.OperationName}\n{operation.Status}");
                    #endif
                }
            }

            // Draw quality checks
            if (showQualityChecks && thread.QualityChecks != null)
            {
                for (int i = 0; i < thread.QualityChecks.Count; i++)
                {
                    var check = thread.QualityChecks[i];
                    Vector3 checkPos = startPos + Vector3.right * (i + 1) * nodeSpacing +
                                       Vector3.up * verticalOffset;

                    Gizmos.color = check.Result == QualityResult.Pass ? qualityPassColor : qualityFailColor;
                    Gizmos.DrawWireSphere(checkPos, gizmoSize * 0.8f);

                    #if UNITY_EDITOR
                    UnityEditor.Handles.Label(checkPos + Vector3.up * 0.3f,
                        $"QC: {check.CheckType}\n{check.Result}");
                    #endif
                }
            }

            // Draw tool changes
            if (showToolChanges && thread.ToolChanges != null)
            {
                for (int i = 0; i < thread.ToolChanges.Count; i++)
                {
                    var change = thread.ToolChanges[i];
                    Vector3 changePos = startPos + Vector3.right * (i + 1) * nodeSpacing -
                                        Vector3.up * verticalOffset;

                    Gizmos.color = toolChangeColor;
                    Gizmos.DrawWireCube(changePos, Vector3.one * gizmoSize * 0.6f);

                    #if UNITY_EDITOR
                    UnityEditor.Handles.Label(changePos - Vector3.up * 0.3f,
                        $"Tool: {change.NewToolId}");
                    #endif
                }
            }

            // Draw thread status indicator
            Vector3 statusPos = transform.position + Vector3.up * (verticalOffset * 2);
            Gizmos.color = thread.Status == ThreadStatus.Completed ? completedColor :
                           thread.Status == ThreadStatus.Active ? Color.green :
                           Color.gray;
            Gizmos.DrawWireSphere(statusPos, gizmoSize * 1.5f);

            #if UNITY_EDITOR
            UnityEditor.Handles.Label(statusPos + Vector3.up * 0.5f,
                $"Thread: {thread.ThreadId}\nStatus: {thread.Status}");
            #endif
        }

        /// <summary>
        /// Handle operation recorded event
        /// </summary>
        private void OnOperationRecorded(Operation operation)
        {
            Vector3 pos = transform.position + Vector3.right * nodeSpacing * operationPositions.Count;
            operationPositions.Add(pos);
        }

        /// <summary>
        /// Handle quality check recorded event
        /// </summary>
        private void OnQualityCheckRecorded(QualityCheck check)
        {
            Vector3 pos = transform.position +
                          Vector3.right * nodeSpacing * qualityCheckPositions.Count +
                          Vector3.up * verticalOffset;
            qualityCheckPositions.Add(pos);
        }

        /// <summary>
        /// Handle tool change recorded event
        /// </summary>
        private void OnToolChangeRecorded(ToolChange change)
        {
            Vector3 pos = transform.position +
                          Vector3.right * nodeSpacing * toolChangePositions.Count -
                          Vector3.up * verticalOffset;
            toolChangePositions.Add(pos);
        }

        void OnDestroy()
        {
            if (tracer != null)
            {
                tracer.OnOperationRecorded -= OnOperationRecorded;
                tracer.OnQualityCheckRecorded -= OnQualityCheckRecorded;
                tracer.OnToolChangeRecorded -= OnToolChangeRecorded;
            }
        }

        #region Public Properties

        public bool GizmosEnabled
        {
            get => enableGizmos;
            set => enableGizmos = value;
        }

        #endregion
    }
}
