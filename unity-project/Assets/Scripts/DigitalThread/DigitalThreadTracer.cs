using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.DigitalThread
{
    /// <summary>
    /// Tracks product genealogy from raw material through all manufacturing operations.
    /// Implements ISO 23247 digital thread requirements for complete traceability.
    /// Part of Feature 3.1: Digital Thread Tracing (HIGH PRIORITY - Phase 3)
    /// </summary>
    public class DigitalThreadTracer : MonoBehaviour
    {
        [Header("Thread Configuration")]
        [SerializeField] private string threadId;
        [SerializeField] private string partNumber;
        [SerializeField] private string serialNumber;
        [SerializeField] private bool autoGenerateIds = true;

        [Header("Tracking Settings")]
        [SerializeField] private bool trackMaterialOrigin = true;
        [SerializeField] private bool trackOperations = true;
        [SerializeField] private bool trackQualityChecks = true;
        [SerializeField] private bool trackToolChanges = true;
        [SerializeField] private bool trackEnvironmentalConditions = true;

        [Header("Data Retention")]
        [SerializeField] private int maxOperations = 1000;
        [SerializeField] private int maxQualityChecks = 100;
        [SerializeField] private bool persistToBackend = true;
        [SerializeField] private float backendSyncInterval = 60f; // seconds

        // Digital thread data
        private DigitalThread currentThread;
        private List<Operation> operations = new List<Operation>();
        private List<QualityCheck> qualityChecks = new List<QualityCheck>();
        private List<ToolChange> toolChanges = new List<ToolChange>();
        private MaterialProvenance materialProvenance;

        // Timing
        private float syncTimer = 0f;
        private DateTime threadStartTime;

        // Events
        public event Action<DigitalThread> OnThreadCreated;
        public event Action<Operation> OnOperationRecorded;
        public event Action<QualityCheck> OnQualityCheckRecorded;
        public event Action<ToolChange> OnToolChangeRecorded;
        public event Action<DigitalThread> OnThreadCompleted;

        // Statistics
        private int totalOperations = 0;
        private int totalQualityChecks = 0;
        private int totalToolChanges = 0;
        private int threadsCompleted = 0;

        void Start()
        {
            InitializeThread();
        }

        void Update()
        {
            if (persistToBackend)
            {
                syncTimer += Time.deltaTime;
                if (syncTimer >= backendSyncInterval)
                {
                    SyncToBackend();
                    syncTimer = 0f;
                }
            }
        }

        /// <summary>
        /// Initialize a new digital thread
        /// </summary>
        private void InitializeThread()
        {
            if (autoGenerateIds)
            {
                threadId = GenerateThreadId();
                if (string.IsNullOrEmpty(serialNumber))
                {
                    serialNumber = GenerateSerialNumber();
                }
            }

            threadStartTime = DateTime.UtcNow;

            currentThread = new DigitalThread
            {
                ThreadId = threadId,
                PartNumber = partNumber,
                SerialNumber = serialNumber,
                StartTime = threadStartTime,
                Status = ThreadStatus.Active,
                MaterialProvenance = materialProvenance,
                Operations = operations,
                QualityChecks = qualityChecks,
                ToolChanges = toolChanges
            };

            OnThreadCreated?.Invoke(currentThread);
            Debug.Log($"[DigitalThread] Thread initialized: {threadId}");
        }

        /// <summary>
        /// Record a manufacturing operation
        /// </summary>
        public void RecordOperation(string operationName, string machineId, Dictionary<string, object> parameters)
        {
            var operation = new Operation
            {
                OperationId = Guid.NewGuid().ToString(),
                OperationName = operationName,
                MachineId = machineId,
                StartTime = DateTime.UtcNow,
                Parameters = parameters,
                Status = OperationStatus.InProgress
            };

            operations.Add(operation);
            totalOperations++;

            // Enforce max operations limit
            if (operations.Count > maxOperations)
            {
                operations.RemoveAt(0);
            }

            OnOperationRecorded?.Invoke(operation);
            Debug.Log($"[DigitalThread] Operation recorded: {operationName} on {machineId}");
        }

        /// <summary>
        /// Complete an operation
        /// </summary>
        public void CompleteOperation(string operationId, bool success, Dictionary<string, object> results)
        {
            var operation = operations.Find(op => op.OperationId == operationId);
            if (operation != null)
            {
                operation.EndTime = DateTime.UtcNow;
                operation.Duration = (operation.EndTime.Value - operation.StartTime).TotalSeconds;
                operation.Status = success ? OperationStatus.Completed : OperationStatus.Failed;
                operation.Results = results;

                Debug.Log($"[DigitalThread] Operation completed: {operation.OperationName} ({operation.Status})");
            }
        }

        /// <summary>
        /// Record a quality check
        /// </summary>
        public void RecordQualityCheck(string checkType, string inspectorId, Dictionary<string, float> measurements)
        {
            var qualityCheck = new QualityCheck
            {
                CheckId = Guid.NewGuid().ToString(),
                CheckType = checkType,
                InspectorId = inspectorId,
                Timestamp = DateTime.UtcNow,
                Measurements = measurements,
                Result = EvaluateQualityResult(measurements)
            };

            qualityChecks.Add(qualityCheck);
            totalQualityChecks++;

            // Enforce max quality checks limit
            if (qualityChecks.Count > maxQualityChecks)
            {
                qualityChecks.RemoveAt(0);
            }

            OnQualityCheckRecorded?.Invoke(qualityCheck);
            Debug.Log($"[DigitalThread] Quality check recorded: {checkType} - {qualityCheck.Result}");
        }

        /// <summary>
        /// Record a tool change event
        /// </summary>
        public void RecordToolChange(string oldToolId, string newToolId, string reason, int toolLife)
        {
            var toolChange = new ToolChange
            {
                ChangeId = Guid.NewGuid().ToString(),
                OldToolId = oldToolId,
                NewToolId = newToolId,
                Timestamp = DateTime.UtcNow,
                Reason = reason,
                ToolLifeRemaining = toolLife
            };

            toolChanges.Add(toolChange);
            totalToolChanges++;

            OnToolChangeRecorded?.Invoke(toolChange);
            Debug.Log($"[DigitalThread] Tool change recorded: {oldToolId} → {newToolId}");
        }

        /// <summary>
        /// Set material provenance information
        /// </summary>
        public void SetMaterialProvenance(string materialType, string lotNumber, string supplier,
                                          string certificationNumber, DateTime receiptDate)
        {
            materialProvenance = new MaterialProvenance
            {
                MaterialType = materialType,
                LotNumber = lotNumber,
                Supplier = supplier,
                CertificationNumber = certificationNumber,
                ReceiptDate = receiptDate,
                TraceabilityCode = GenerateTraceabilityCode(materialType, lotNumber, supplier)
            };

            if (currentThread != null)
            {
                currentThread.MaterialProvenance = materialProvenance;
            }

            Debug.Log($"[DigitalThread] Material provenance set: {materialType} from {supplier}");
        }

        /// <summary>
        /// Add environmental conditions at a specific point in time
        /// </summary>
        public void RecordEnvironmentalConditions(float temperature, float humidity, float ambientVibration)
        {
            var conditions = new EnvironmentalConditions
            {
                Timestamp = DateTime.UtcNow,
                Temperature = temperature,
                Humidity = humidity,
                AmbientVibration = ambientVibration
            };

            // Store in current operation if one is active
            var activeOperation = operations.FindLast(op => op.Status == OperationStatus.InProgress);
            if (activeOperation != null)
            {
                if (activeOperation.EnvironmentalConditions == null)
                {
                    activeOperation.EnvironmentalConditions = new List<EnvironmentalConditions>();
                }
                activeOperation.EnvironmentalConditions.Add(conditions);
            }
        }

        /// <summary>
        /// Complete the digital thread
        /// </summary>
        public void CompleteThread()
        {
            if (currentThread == null) return;

            currentThread.EndTime = DateTime.UtcNow;
            currentThread.Status = ThreadStatus.Completed;
            currentThread.TotalDuration = (currentThread.EndTime.Value - currentThread.StartTime).TotalSeconds;

            // Calculate statistics
            currentThread.TotalOperations = operations.Count;
            currentThread.SuccessfulOperations = operations.FindAll(op => op.Status == OperationStatus.Completed).Count;
            currentThread.FailedOperations = operations.FindAll(op => op.Status == OperationStatus.Failed).Count;
            currentThread.TotalQualityChecks = qualityChecks.Count;
            currentThread.PassedQualityChecks = qualityChecks.FindAll(qc => qc.Result == QualityResult.Pass).Count;

            threadsCompleted++;
            OnThreadCompleted?.Invoke(currentThread);

            Debug.Log($"[DigitalThread] Thread completed: {threadId} ({currentThread.TotalDuration}s)");

            // Sync final state to backend
            if (persistToBackend)
            {
                SyncToBackend();
            }
        }

        /// <summary>
        /// Generate unique thread ID
        /// </summary>
        private string GenerateThreadId()
        {
            return $"DT-{DateTime.UtcNow:yyyyMMdd-HHmmss}-{UnityEngine.Random.Range(1000, 9999)}";
        }

        /// <summary>
        /// Generate serial number
        /// </summary>
        private string GenerateSerialNumber()
        {
            return $"SN-{DateTime.UtcNow:yyyyMMdd}-{UnityEngine.Random.Range(100000, 999999)}";
        }

        /// <summary>
        /// Generate traceability code from material information
        /// </summary>
        private string GenerateTraceabilityCode(string materialType, string lotNumber, string supplier)
        {
            var hash = $"{materialType}-{lotNumber}-{supplier}".GetHashCode();
            return $"TC-{Math.Abs(hash):X8}";
        }

        /// <summary>
        /// Evaluate quality result from measurements
        /// </summary>
        private QualityResult EvaluateQualityResult(Dictionary<string, float> measurements)
        {
            // Simple evaluation - in production, this would use proper tolerances
            foreach (var measurement in measurements)
            {
                if (measurement.Value < 0 || measurement.Value > 100)
                {
                    return QualityResult.Fail;
                }
            }
            return QualityResult.Pass;
        }

        /// <summary>
        /// Sync digital thread to backend
        /// </summary>
        private void SyncToBackend()
        {
            if (currentThread == null) return;

            // In a real implementation, this would POST to the backend API
            Debug.Log($"[DigitalThread] Syncing thread to backend: {threadId} ({operations.Count} ops, {qualityChecks.Count} checks)");
        }

        /// <summary>
        /// Get complete digital thread
        /// </summary>
        public DigitalThread GetDigitalThread()
        {
            return currentThread;
        }

        /// <summary>
        /// Get thread statistics
        /// </summary>
        public ThreadStatistics GetStatistics()
        {
            return new ThreadStatistics
            {
                ThreadId = threadId,
                TotalOperations = totalOperations,
                TotalQualityChecks = totalQualityChecks,
                TotalToolChanges = totalToolChanges,
                ThreadsCompleted = threadsCompleted,
                CurrentThreadDuration = currentThread != null ?
                    (DateTime.UtcNow - currentThread.StartTime).TotalSeconds : 0,
                ActiveOperations = operations.FindAll(op => op.Status == OperationStatus.InProgress).Count
            };
        }

        /// <summary>
        /// Export thread to JSON
        /// </summary>
        public string ExportToJson()
        {
            if (currentThread == null) return "{}";
            return JsonUtility.ToJson(currentThread, true);
        }

        /// <summary>
        /// Get genealogy path (all operations in sequence)
        /// </summary>
        public List<string> GetGenealogyPath()
        {
            var path = new List<string>();

            if (materialProvenance != null)
            {
                path.Add($"Material: {materialProvenance.MaterialType} (Lot: {materialProvenance.LotNumber})");
            }

            foreach (var operation in operations)
            {
                path.Add($"{operation.OperationName} on {operation.MachineId} ({operation.Status})");
            }

            return path;
        }

        void OnDestroy()
        {
            // Final sync on destroy
            if (persistToBackend && currentThread != null && currentThread.Status == ThreadStatus.Active)
            {
                CompleteThread();
            }
        }

        #region Public Properties

        public string ThreadId => threadId;
        public string PartNumber => partNumber;
        public string SerialNumber => serialNumber;
        public int OperationCount => operations.Count;
        public int QualityCheckCount => qualityChecks.Count;
        public ThreadStatus Status => currentThread?.Status ?? ThreadStatus.Inactive;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Digital thread data structure
    /// </summary>
    [Serializable]
    public class DigitalThread
    {
        public string ThreadId;
        public string PartNumber;
        public string SerialNumber;
        public DateTime StartTime;
        public DateTime? EndTime;
        public double TotalDuration;
        public ThreadStatus Status;
        public MaterialProvenance MaterialProvenance;
        public List<Operation> Operations;
        public List<QualityCheck> QualityChecks;
        public List<ToolChange> ToolChanges;
        public int TotalOperations;
        public int SuccessfulOperations;
        public int FailedOperations;
        public int TotalQualityChecks;
        public int PassedQualityChecks;
    }

    /// <summary>
    /// Material provenance information
    /// </summary>
    [Serializable]
    public class MaterialProvenance
    {
        public string MaterialType;
        public string LotNumber;
        public string Supplier;
        public string CertificationNumber;
        public DateTime ReceiptDate;
        public string TraceabilityCode;
    }

    /// <summary>
    /// Manufacturing operation record
    /// </summary>
    [Serializable]
    public class Operation
    {
        public string OperationId;
        public string OperationName;
        public string MachineId;
        public DateTime StartTime;
        public DateTime? EndTime;
        public double Duration;
        public OperationStatus Status;
        public Dictionary<string, object> Parameters;
        public Dictionary<string, object> Results;
        public List<EnvironmentalConditions> EnvironmentalConditions;
    }

    /// <summary>
    /// Quality check record
    /// </summary>
    [Serializable]
    public class QualityCheck
    {
        public string CheckId;
        public string CheckType;
        public string InspectorId;
        public DateTime Timestamp;
        public Dictionary<string, float> Measurements;
        public QualityResult Result;
        public string Notes;
    }

    /// <summary>
    /// Tool change record
    /// </summary>
    [Serializable]
    public class ToolChange
    {
        public string ChangeId;
        public string OldToolId;
        public string NewToolId;
        public DateTime Timestamp;
        public string Reason;
        public int ToolLifeRemaining;
    }

    /// <summary>
    /// Environmental conditions snapshot
    /// </summary>
    [Serializable]
    public class EnvironmentalConditions
    {
        public DateTime Timestamp;
        public float Temperature;
        public float Humidity;
        public float AmbientVibration;
    }

    /// <summary>
    /// Thread statistics
    /// </summary>
    [Serializable]
    public struct ThreadStatistics
    {
        public string ThreadId;
        public int TotalOperations;
        public int TotalQualityChecks;
        public int TotalToolChanges;
        public int ThreadsCompleted;
        public double CurrentThreadDuration;
        public int ActiveOperations;
    }

    /// <summary>
    /// Thread status enumeration
    /// </summary>
    public enum ThreadStatus
    {
        Inactive,
        Active,
        Completed,
        Failed
    }

    /// <summary>
    /// Operation status enumeration
    /// </summary>
    public enum OperationStatus
    {
        Pending,
        InProgress,
        Completed,
        Failed,
        Cancelled
    }

    /// <summary>
    /// Quality check result enumeration
    /// </summary>
    public enum QualityResult
    {
        Pass,
        Fail,
        Conditional,
        Retest
    }

    #endregion
}
