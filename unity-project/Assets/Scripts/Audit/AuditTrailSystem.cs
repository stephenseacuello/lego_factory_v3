using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Security.Cryptography;
using UnityEngine;

namespace CNC_SCADA.DigitalTwin.Audit
{
    /// <summary>
    /// Comprehensive audit trail system for regulatory compliance (FDA 21 CFR Part 11)
    /// Tracks all user actions, system changes, and provides tamper-evident logging
    /// </summary>
    public class AuditTrailSystem : MonoBehaviour
    {
        public static AuditTrailSystem Instance { get; private set; }

        [Header("Configuration")]
        [SerializeField] private int maxInMemoryRecords = 10000;
        [SerializeField] private bool enableSignatureVerification = true;
        [SerializeField] private bool enableRealTimeSync = true;
        [SerializeField] private float syncIntervalSeconds = 5f;

        [Header("Retention")]
        [SerializeField] private int retentionDays = 365 * 7; // 7 years for FDA compliance

        // Events
        public event Action<AuditRecord> OnAuditRecordCreated;
        public event Action<List<AuditRecord>> OnAuditBatchSynced;
        public event Action<AuditAlert> OnAuditAlertRaised;
        public event Action<string> OnIntegrityViolationDetected;

        // Storage
        private List<AuditRecord> auditLog = new List<AuditRecord>();
        private Queue<AuditRecord> pendingSyncQueue = new Queue<AuditRecord>();
        private Dictionary<string, UserSession> activeSessions = new Dictionary<string, UserSession>();
        private string lastRecordHash = "";

        // Statistics
        private int totalRecordsCreated = 0;
        private int totalRecordsSynced = 0;
        private DateTime systemStartTime;

        public int TotalRecords => auditLog.Count;
        public int PendingSyncCount => pendingSyncQueue.Count;

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
                systemStartTime = DateTime.UtcNow;
                InitializeAuditSystem();
            }
            else
            {
                Destroy(gameObject);
            }
        }

        private void Start()
        {
            if (enableRealTimeSync)
            {
                InvokeRepeating(nameof(SyncPendingRecords), syncIntervalSeconds, syncIntervalSeconds);
            }

            // Log system startup
            LogSystemEvent("SYSTEM_STARTUP", "Audit Trail System initialized", AuditSeverity.Info);
        }

        private void OnApplicationQuit()
        {
            LogSystemEvent("SYSTEM_SHUTDOWN", "Application shutting down", AuditSeverity.Info);
            SyncPendingRecords();
        }

        private void InitializeAuditSystem()
        {
            // Initialize with genesis record
            var genesisRecord = new AuditRecord
            {
                RecordId = "GENESIS",
                Timestamp = DateTime.UtcNow,
                Category = AuditCategory.System,
                Action = "SYSTEM_GENESIS",
                Description = "Audit trail genesis block",
                UserId = "SYSTEM",
                Severity = AuditSeverity.Info,
                PreviousHash = "0"
            };
            genesisRecord.RecordHash = CalculateRecordHash(genesisRecord);
            lastRecordHash = genesisRecord.RecordHash;
            auditLog.Add(genesisRecord);

            Debug.Log("[AuditTrail] System initialized with genesis record");
        }

        #region Record Creation

        /// <summary>
        /// Log a user action in the audit trail
        /// </summary>
        public AuditRecord LogUserAction(string userId, string action, string description,
            string targetEntity = null, string targetId = null, AuditSeverity severity = AuditSeverity.Info,
            Dictionary<string, string> metadata = null)
        {
            return CreateAuditRecord(new AuditRecordRequest
            {
                Category = AuditCategory.UserAction,
                Action = action,
                Description = description,
                UserId = userId,
                TargetEntity = targetEntity,
                TargetId = targetId,
                Severity = severity,
                Metadata = metadata
            });
        }

        /// <summary>
        /// Log a data change in the audit trail
        /// </summary>
        public AuditRecord LogDataChange(string userId, string entity, string entityId,
            string fieldName, string oldValue, string newValue, string reason = null)
        {
            var metadata = new Dictionary<string, string>
            {
                { "field", fieldName },
                { "old_value", oldValue ?? "null" },
                { "new_value", newValue ?? "null" }
            };

            if (!string.IsNullOrEmpty(reason))
            {
                metadata["reason"] = reason;
            }

            return CreateAuditRecord(new AuditRecordRequest
            {
                Category = AuditCategory.DataChange,
                Action = "DATA_MODIFIED",
                Description = $"Changed {fieldName} on {entity}",
                UserId = userId,
                TargetEntity = entity,
                TargetId = entityId,
                Severity = AuditSeverity.Info,
                Metadata = metadata
            });
        }

        /// <summary>
        /// Log a system event in the audit trail
        /// </summary>
        public AuditRecord LogSystemEvent(string eventCode, string description,
            AuditSeverity severity = AuditSeverity.Info, Dictionary<string, string> metadata = null)
        {
            return CreateAuditRecord(new AuditRecordRequest
            {
                Category = AuditCategory.System,
                Action = eventCode,
                Description = description,
                UserId = "SYSTEM",
                Severity = severity,
                Metadata = metadata
            });
        }

        /// <summary>
        /// Log a security event in the audit trail
        /// </summary>
        public AuditRecord LogSecurityEvent(string userId, string action, string description,
            AuditSeverity severity = AuditSeverity.Warning, string ipAddress = null)
        {
            var metadata = new Dictionary<string, string>();
            if (!string.IsNullOrEmpty(ipAddress))
            {
                metadata["ip_address"] = ipAddress;
            }

            return CreateAuditRecord(new AuditRecordRequest
            {
                Category = AuditCategory.Security,
                Action = action,
                Description = description,
                UserId = userId,
                Severity = severity,
                Metadata = metadata
            });
        }

        /// <summary>
        /// Log a machine control action
        /// </summary>
        public AuditRecord LogMachineControl(string userId, string machineId, string action,
            string description, Dictionary<string, string> parameters = null)
        {
            return CreateAuditRecord(new AuditRecordRequest
            {
                Category = AuditCategory.MachineControl,
                Action = action,
                Description = description,
                UserId = userId,
                TargetEntity = "Machine",
                TargetId = machineId,
                Severity = AuditSeverity.Info,
                Metadata = parameters
            });
        }

        /// <summary>
        /// Log a quality event
        /// </summary>
        public AuditRecord LogQualityEvent(string userId, string eventType, string partNumber,
            string description, QualityResult result, Dictionary<string, string> measurements = null)
        {
            var metadata = measurements ?? new Dictionary<string, string>();
            metadata["part_number"] = partNumber;
            metadata["result"] = result.ToString();

            return CreateAuditRecord(new AuditRecordRequest
            {
                Category = AuditCategory.Quality,
                Action = eventType,
                Description = description,
                UserId = userId,
                TargetEntity = "Part",
                TargetId = partNumber,
                Severity = result == QualityResult.Fail ? AuditSeverity.Warning : AuditSeverity.Info,
                Metadata = metadata
            });
        }

        /// <summary>
        /// Log a recipe/program change with electronic signature
        /// </summary>
        public AuditRecord LogRecipeChange(string userId, string recipeId, string action,
            string description, string signature = null, string signatureReason = null)
        {
            var metadata = new Dictionary<string, string>
            {
                { "recipe_id", recipeId }
            };

            var record = CreateAuditRecord(new AuditRecordRequest
            {
                Category = AuditCategory.RecipeChange,
                Action = action,
                Description = description,
                UserId = userId,
                TargetEntity = "Recipe",
                TargetId = recipeId,
                Severity = AuditSeverity.Info,
                Metadata = metadata,
                RequiresSignature = true
            });

            // Add electronic signature if provided
            if (!string.IsNullOrEmpty(signature))
            {
                AddElectronicSignature(record.RecordId, userId, signature, signatureReason);
            }

            return record;
        }

        private AuditRecord CreateAuditRecord(AuditRecordRequest request)
        {
            var record = new AuditRecord
            {
                RecordId = GenerateRecordId(),
                Timestamp = DateTime.UtcNow,
                Category = request.Category,
                Action = request.Action,
                Description = request.Description,
                UserId = request.UserId,
                TargetEntity = request.TargetEntity,
                TargetId = request.TargetId,
                Severity = request.Severity,
                Metadata = request.Metadata ?? new Dictionary<string, string>(),
                PreviousHash = lastRecordHash,
                RequiresSignature = request.RequiresSignature,
                SessionId = GetSessionId(request.UserId)
            };

            // Calculate tamper-evident hash
            record.RecordHash = CalculateRecordHash(record);
            lastRecordHash = record.RecordHash;

            // Add to log
            auditLog.Add(record);
            totalRecordsCreated++;

            // Queue for sync
            if (enableRealTimeSync)
            {
                pendingSyncQueue.Enqueue(record);
            }

            // Trim in-memory log if needed
            if (auditLog.Count > maxInMemoryRecords)
            {
                auditLog.RemoveAt(0);
            }

            // Raise events
            OnAuditRecordCreated?.Invoke(record);

            // Check for alerts
            CheckForAlerts(record);

            Debug.Log($"[AuditTrail] {record.Category}/{record.Action}: {record.Description}");

            return record;
        }

        private string GenerateRecordId()
        {
            return $"AUD-{DateTime.UtcNow:yyyyMMddHHmmss}-{totalRecordsCreated:D6}";
        }

        private string CalculateRecordHash(AuditRecord record)
        {
            var dataToHash = $"{record.RecordId}|{record.Timestamp:O}|{record.Category}|{record.Action}|" +
                           $"{record.Description}|{record.UserId}|{record.PreviousHash}";

            using (var sha256 = SHA256.Create())
            {
                var bytes = Encoding.UTF8.GetBytes(dataToHash);
                var hash = sha256.ComputeHash(bytes);
                return BitConverter.ToString(hash).Replace("-", "").ToLower();
            }
        }

        #endregion

        #region Electronic Signatures

        public void AddElectronicSignature(string recordId, string userId, string signature, string reason)
        {
            var record = auditLog.FirstOrDefault(r => r.RecordId == recordId);
            if (record == null)
            {
                Debug.LogWarning($"[AuditTrail] Record not found: {recordId}");
                return;
            }

            record.ElectronicSignature = new ElectronicSignature
            {
                SignatureId = $"SIG-{DateTime.UtcNow:yyyyMMddHHmmss}",
                UserId = userId,
                Timestamp = DateTime.UtcNow,
                SignatureHash = CalculateSignatureHash(userId, signature, record.RecordHash),
                Reason = reason,
                IsVerified = true
            };

            LogSystemEvent("SIGNATURE_APPLIED",
                $"Electronic signature applied to record {recordId} by {userId}",
                AuditSeverity.Info,
                new Dictionary<string, string> { { "record_id", recordId } });
        }

        private string CalculateSignatureHash(string userId, string signature, string recordHash)
        {
            var dataToHash = $"{userId}|{signature}|{recordHash}|{DateTime.UtcNow:O}";

            using (var sha256 = SHA256.Create())
            {
                var bytes = Encoding.UTF8.GetBytes(dataToHash);
                var hash = sha256.ComputeHash(bytes);
                return BitConverter.ToString(hash).Replace("-", "").ToLower();
            }
        }

        public bool VerifySignature(string recordId)
        {
            var record = auditLog.FirstOrDefault(r => r.RecordId == recordId);
            if (record?.ElectronicSignature == null)
            {
                return false;
            }

            // In a real system, this would verify against stored credentials
            return record.ElectronicSignature.IsVerified;
        }

        #endregion

        #region Session Management

        public string StartSession(string userId, string ipAddress = null, string userAgent = null)
        {
            var sessionId = $"SES-{DateTime.UtcNow:yyyyMMddHHmmss}-{Guid.NewGuid().ToString().Substring(0, 8)}";

            var session = new UserSession
            {
                SessionId = sessionId,
                UserId = userId,
                StartTime = DateTime.UtcNow,
                IpAddress = ipAddress,
                UserAgent = userAgent,
                IsActive = true
            };

            activeSessions[userId] = session;

            LogSecurityEvent(userId, "SESSION_START", $"User session started",
                AuditSeverity.Info, ipAddress);

            return sessionId;
        }

        public void EndSession(string userId)
        {
            if (activeSessions.TryGetValue(userId, out var session))
            {
                session.EndTime = DateTime.UtcNow;
                session.IsActive = false;

                LogSecurityEvent(userId, "SESSION_END",
                    $"User session ended. Duration: {(session.EndTime - session.StartTime).TotalMinutes:F1} minutes",
                    AuditSeverity.Info);

                activeSessions.Remove(userId);
            }
        }

        private string GetSessionId(string userId)
        {
            return activeSessions.TryGetValue(userId, out var session) ? session.SessionId : null;
        }

        #endregion

        #region Integrity Verification

        public IntegrityCheckResult VerifyChainIntegrity(int? lastNRecords = null)
        {
            var result = new IntegrityCheckResult
            {
                CheckTime = DateTime.UtcNow,
                TotalRecordsChecked = 0,
                IsValid = true,
                Violations = new List<IntegrityViolation>()
            };

            var recordsToCheck = lastNRecords.HasValue
                ? auditLog.TakeLast(lastNRecords.Value).ToList()
                : auditLog;

            string previousHash = recordsToCheck.Count > 0 ? recordsToCheck[0].PreviousHash : "0";

            for (int i = 0; i < recordsToCheck.Count; i++)
            {
                var record = recordsToCheck[i];
                result.TotalRecordsChecked++;

                // Verify previous hash chain
                if (i > 0 && record.PreviousHash != recordsToCheck[i - 1].RecordHash)
                {
                    result.IsValid = false;
                    result.Violations.Add(new IntegrityViolation
                    {
                        RecordId = record.RecordId,
                        ViolationType = "CHAIN_BREAK",
                        Description = "Previous hash does not match chain"
                    });
                }

                // Verify record hash
                var calculatedHash = CalculateRecordHash(record);
                if (calculatedHash != record.RecordHash)
                {
                    result.IsValid = false;
                    result.Violations.Add(new IntegrityViolation
                    {
                        RecordId = record.RecordId,
                        ViolationType = "HASH_MISMATCH",
                        Description = "Record hash does not match calculated hash"
                    });
                }
            }

            if (!result.IsValid)
            {
                OnIntegrityViolationDetected?.Invoke($"Chain integrity violation detected: {result.Violations.Count} issues found");

                // Log the integrity check failure
                LogSecurityEvent("SYSTEM", "INTEGRITY_VIOLATION",
                    $"Audit trail integrity check failed: {result.Violations.Count} violations",
                    AuditSeverity.Critical);
            }

            return result;
        }

        #endregion

        #region Querying

        public List<AuditRecord> Query(AuditQuery query)
        {
            var results = auditLog.AsEnumerable();

            if (query.StartTime.HasValue)
                results = results.Where(r => r.Timestamp >= query.StartTime.Value);

            if (query.EndTime.HasValue)
                results = results.Where(r => r.Timestamp <= query.EndTime.Value);

            if (!string.IsNullOrEmpty(query.UserId))
                results = results.Where(r => r.UserId == query.UserId);

            if (query.Categories != null && query.Categories.Any())
                results = results.Where(r => query.Categories.Contains(r.Category));

            if (query.Severities != null && query.Severities.Any())
                results = results.Where(r => query.Severities.Contains(r.Severity));

            if (!string.IsNullOrEmpty(query.Action))
                results = results.Where(r => r.Action.Contains(query.Action, StringComparison.OrdinalIgnoreCase));

            if (!string.IsNullOrEmpty(query.TargetEntity))
                results = results.Where(r => r.TargetEntity == query.TargetEntity);

            if (!string.IsNullOrEmpty(query.TargetId))
                results = results.Where(r => r.TargetId == query.TargetId);

            if (!string.IsNullOrEmpty(query.SearchText))
                results = results.Where(r =>
                    r.Description.Contains(query.SearchText, StringComparison.OrdinalIgnoreCase) ||
                    r.Action.Contains(query.SearchText, StringComparison.OrdinalIgnoreCase));

            // Apply ordering
            results = query.OrderDescending
                ? results.OrderByDescending(r => r.Timestamp)
                : results.OrderBy(r => r.Timestamp);

            // Apply pagination
            if (query.Skip > 0)
                results = results.Skip(query.Skip);

            if (query.Take > 0)
                results = results.Take(query.Take);

            return results.ToList();
        }

        public List<AuditRecord> GetRecentRecords(int count = 100)
        {
            return auditLog.TakeLast(count).Reverse().ToList();
        }

        public List<AuditRecord> GetRecordsByUser(string userId, int days = 7)
        {
            var cutoff = DateTime.UtcNow.AddDays(-days);
            return auditLog.Where(r => r.UserId == userId && r.Timestamp >= cutoff)
                          .OrderByDescending(r => r.Timestamp)
                          .ToList();
        }

        public List<AuditRecord> GetSecurityEvents(int days = 30)
        {
            var cutoff = DateTime.UtcNow.AddDays(-days);
            return auditLog.Where(r => r.Category == AuditCategory.Security && r.Timestamp >= cutoff)
                          .OrderByDescending(r => r.Timestamp)
                          .ToList();
        }

        #endregion

        #region Alerts

        private void CheckForAlerts(AuditRecord record)
        {
            // Critical severity alert
            if (record.Severity == AuditSeverity.Critical)
            {
                RaiseAlert(new AuditAlert
                {
                    AlertId = $"ALR-{DateTime.UtcNow:yyyyMMddHHmmss}",
                    Timestamp = DateTime.UtcNow,
                    Type = AlertType.CriticalEvent,
                    RecordId = record.RecordId,
                    Message = $"Critical event: {record.Description}",
                    Priority = AlertPriority.Critical
                });
            }

            // Failed login attempts
            if (record.Action == "LOGIN_FAILED")
            {
                var recentFailures = auditLog.Count(r =>
                    r.Action == "LOGIN_FAILED" &&
                    r.UserId == record.UserId &&
                    r.Timestamp >= DateTime.UtcNow.AddMinutes(-15));

                if (recentFailures >= 3)
                {
                    RaiseAlert(new AuditAlert
                    {
                        AlertId = $"ALR-{DateTime.UtcNow:yyyyMMddHHmmss}",
                        Timestamp = DateTime.UtcNow,
                        Type = AlertType.SecurityThreat,
                        RecordId = record.RecordId,
                        Message = $"Multiple failed login attempts for user {record.UserId}",
                        Priority = AlertPriority.High
                    });
                }
            }

            // Unusual activity hours
            var hour = record.Timestamp.Hour;
            if ((hour >= 0 && hour < 5) && record.Category == AuditCategory.MachineControl)
            {
                RaiseAlert(new AuditAlert
                {
                    AlertId = $"ALR-{DateTime.UtcNow:yyyyMMddHHmmss}",
                    Timestamp = DateTime.UtcNow,
                    Type = AlertType.UnusualActivity,
                    RecordId = record.RecordId,
                    Message = $"Machine control action during unusual hours by {record.UserId}",
                    Priority = AlertPriority.Medium
                });
            }
        }

        private void RaiseAlert(AuditAlert alert)
        {
            OnAuditAlertRaised?.Invoke(alert);
            Debug.LogWarning($"[AuditTrail] ALERT: {alert.Message}");
        }

        #endregion

        #region Export

        public string ExportToCSV(AuditQuery query = null)
        {
            var records = query != null ? Query(query) : auditLog;
            var sb = new StringBuilder();

            // Header
            sb.AppendLine("RecordId,Timestamp,Category,Action,Description,UserId,TargetEntity,TargetId,Severity,SessionId");

            foreach (var record in records)
            {
                sb.AppendLine($"\"{record.RecordId}\",\"{record.Timestamp:O}\",\"{record.Category}\"," +
                            $"\"{record.Action}\",\"{EscapeCsv(record.Description)}\",\"{record.UserId}\"," +
                            $"\"{record.TargetEntity}\",\"{record.TargetId}\",\"{record.Severity}\",\"{record.SessionId}\"");
            }

            return sb.ToString();
        }

        public string ExportToJson(AuditQuery query = null)
        {
            var records = query != null ? Query(query) : auditLog;
            return JsonUtility.ToJson(new AuditExport { Records = records }, true);
        }

        private string EscapeCsv(string value)
        {
            if (string.IsNullOrEmpty(value)) return "";
            return value.Replace("\"", "\"\"");
        }

        #endregion

        #region Sync

        private void SyncPendingRecords()
        {
            if (pendingSyncQueue.Count == 0) return;

            var batch = new List<AuditRecord>();
            while (pendingSyncQueue.Count > 0 && batch.Count < 100)
            {
                batch.Add(pendingSyncQueue.Dequeue());
            }

            // In a real system, this would sync to a backend service
            totalRecordsSynced += batch.Count;
            OnAuditBatchSynced?.Invoke(batch);

            Debug.Log($"[AuditTrail] Synced {batch.Count} records. Total synced: {totalRecordsSynced}");
        }

        #endregion

        #region Statistics

        public AuditStatistics GetStatistics(int days = 7)
        {
            var cutoff = DateTime.UtcNow.AddDays(-days);
            var recentRecords = auditLog.Where(r => r.Timestamp >= cutoff).ToList();

            return new AuditStatistics
            {
                TotalRecords = auditLog.Count,
                RecordsInPeriod = recentRecords.Count,
                RecordsByCategory = recentRecords.GroupBy(r => r.Category)
                    .ToDictionary(g => g.Key.ToString(), g => g.Count()),
                RecordsBySeverity = recentRecords.GroupBy(r => r.Severity)
                    .ToDictionary(g => g.Key.ToString(), g => g.Count()),
                UniqueUsers = recentRecords.Select(r => r.UserId).Distinct().Count(),
                SystemUptime = DateTime.UtcNow - systemStartTime,
                LastRecordTime = auditLog.LastOrDefault()?.Timestamp ?? DateTime.MinValue,
                ChainIntegrity = VerifyChainIntegrity(100).IsValid
            };
        }

        #endregion
    }

    #region Data Classes

    [Serializable]
    public class AuditRecord
    {
        public string RecordId;
        public DateTime Timestamp;
        public AuditCategory Category;
        public string Action;
        public string Description;
        public string UserId;
        public string TargetEntity;
        public string TargetId;
        public AuditSeverity Severity;
        public Dictionary<string, string> Metadata;
        public string SessionId;
        public string PreviousHash;
        public string RecordHash;
        public bool RequiresSignature;
        public ElectronicSignature ElectronicSignature;
    }

    public enum AuditCategory
    {
        System,
        UserAction,
        DataChange,
        Security,
        MachineControl,
        Quality,
        RecipeChange,
        Configuration,
        Alarm,
        Maintenance
    }

    public enum AuditSeverity
    {
        Debug,
        Info,
        Warning,
        Error,
        Critical
    }

    [Serializable]
    public class AuditRecordRequest
    {
        public AuditCategory Category;
        public string Action;
        public string Description;
        public string UserId;
        public string TargetEntity;
        public string TargetId;
        public AuditSeverity Severity;
        public Dictionary<string, string> Metadata;
        public bool RequiresSignature;
    }

    [Serializable]
    public class ElectronicSignature
    {
        public string SignatureId;
        public string UserId;
        public DateTime Timestamp;
        public string SignatureHash;
        public string Reason;
        public bool IsVerified;
    }

    [Serializable]
    public class UserSession
    {
        public string SessionId;
        public string UserId;
        public DateTime StartTime;
        public DateTime EndTime;
        public string IpAddress;
        public string UserAgent;
        public bool IsActive;
    }

    [Serializable]
    public class AuditQuery
    {
        public DateTime? StartTime;
        public DateTime? EndTime;
        public string UserId;
        public List<AuditCategory> Categories;
        public List<AuditSeverity> Severities;
        public string Action;
        public string TargetEntity;
        public string TargetId;
        public string SearchText;
        public bool OrderDescending = true;
        public int Skip = 0;
        public int Take = 100;
    }

    [Serializable]
    public class IntegrityCheckResult
    {
        public DateTime CheckTime;
        public int TotalRecordsChecked;
        public bool IsValid;
        public List<IntegrityViolation> Violations;
    }

    [Serializable]
    public class IntegrityViolation
    {
        public string RecordId;
        public string ViolationType;
        public string Description;
    }

    [Serializable]
    public class AuditAlert
    {
        public string AlertId;
        public DateTime Timestamp;
        public AlertType Type;
        public string RecordId;
        public string Message;
        public AlertPriority Priority;
    }

    public enum AlertType
    {
        CriticalEvent,
        SecurityThreat,
        UnusualActivity,
        PolicyViolation,
        SystemError
    }

    public enum AlertPriority
    {
        Low,
        Medium,
        High,
        Critical
    }

    public enum QualityResult
    {
        Pass,
        Fail,
        Rework,
        Scrap
    }

    [Serializable]
    public class AuditExport
    {
        public List<AuditRecord> Records;
    }

    [Serializable]
    public class AuditStatistics
    {
        public int TotalRecords;
        public int RecordsInPeriod;
        public Dictionary<string, int> RecordsByCategory;
        public Dictionary<string, int> RecordsBySeverity;
        public int UniqueUsers;
        public TimeSpan SystemUptime;
        public DateTime LastRecordTime;
        public bool ChainIntegrity;
    }

    #endregion
}
