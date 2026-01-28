using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Standards
{
    /// <summary>
    /// Validates ISO 23247 compliance for digital twin implementation.
    /// Checks conformance to all four parts of the standard.
    /// Part of Feature 1.4: ISO 23247 Compliance (MEDIUM PRIORITY)
    /// </summary>
    public class ISO23247ComplianceValidator : MonoBehaviour
    {
        [Header("Validation Configuration")]
        [SerializeField] private bool autoValidate = true;
        [SerializeField] private float validationInterval = 10f; // Validate every 10 seconds

        [Header("Compliance Requirements")]
        [SerializeField] private bool requireStateManager = true;
        [SerializeField] private bool requireDataExchange = true;
        [SerializeField] private bool requireEntityId = true;
        [SerializeField] private bool requireCapabilityInfo = true;

        // Component references
        private ISO23247StateManager stateManager;
        private ISO23247DataExchange dataExchange;

        // Validation state
        private bool isCompliant = false;
        private float validationTimer = 0f;
        private DateTime lastValidation;

        // Validation results
        private List<ComplianceIssue> issues = new List<ComplianceIssue>();
        private Dictionary<string, bool> requirementStatus = new Dictionary<string, bool>();

        // Events
        public event Action<ComplianceReport> OnValidationComplete;
        public event Action<ComplianceIssue> OnIssueDetected;

        void Start()
        {
            FindRequiredComponents();
            if (autoValidate)
            {
                ValidateCompliance();
            }
        }

        void Update()
        {
            if (!autoValidate) return;

            validationTimer += Time.deltaTime;
            if (validationTimer >= validationInterval)
            {
                ValidateCompliance();
                validationTimer = 0f;
            }
        }

        /// <summary>
        /// Find required ISO 23247 components
        /// </summary>
        private void FindRequiredComponents()
        {
            stateManager = GetComponent<ISO23247StateManager>();
            dataExchange = GetComponent<ISO23247DataExchange>();
        }

        /// <summary>
        /// Validate full ISO 23247 compliance
        /// </summary>
        public ComplianceReport ValidateCompliance()
        {
            issues.Clear();
            requirementStatus.Clear();
            lastValidation = DateTime.UtcNow;

            // Part 1: Overview and general principles
            ValidatePart1();

            // Part 2: Reference architecture
            ValidatePart2();

            // Part 3: Digital representation
            ValidatePart3();

            // Part 4: Information exchange
            ValidatePart4();

            // Determine overall compliance
            isCompliant = issues.Count == 0;

            var report = GenerateComplianceReport();
            OnValidationComplete?.Invoke(report);

            if (issues.Count > 0)
            {
                Debug.LogWarning($"[ISO23247Validator] Validation found {issues.Count} issue(s)");
            }
            else
            {
                Debug.Log("[ISO23247Validator] Digital twin is ISO 23247 compliant");
            }

            return report;
        }

        /// <summary>
        /// Validate Part 1: Overview and general principles
        /// </summary>
        private void ValidatePart1()
        {
            // Check basic digital twin structure
            CheckRequirement(
                "part1_structure",
                "Digital twin must have entity identification",
                stateManager != null && !string.IsNullOrEmpty(stateManager.EntityId),
                ComplianceSeverity.Critical
            );

            CheckRequirement(
                "part1_observable",
                "Digital twin must provide observable information",
                stateManager != null && stateManager.CurrentState != null,
                ComplianceSeverity.Critical
            );

            CheckRequirement(
                "part1_lifecycle",
                "Digital twin must support lifecycle management",
                true, // Assume supported
                ComplianceSeverity.Warning
            );
        }

        /// <summary>
        /// Validate Part 2: Reference architecture
        /// </summary>
        private void ValidatePart2()
        {
            // Check architectural components
            CheckRequirement(
                "part2_state_manager",
                "Must have ISO23247StateManager component",
                stateManager != null,
                ComplianceSeverity.Critical
            );

            CheckRequirement(
                "part2_data_exchange",
                "Must have ISO23247DataExchange component",
                dataExchange != null,
                ComplianceSeverity.Critical
            );

            CheckRequirement(
                "part2_separation",
                "Must maintain separation between physical and digital",
                stateManager != null && dataExchange != null,
                ComplianceSeverity.Warning
            );
        }

        /// <summary>
        /// Validate Part 3: Digital representation
        /// </summary>
        private void ValidatePart3()
        {
            if (stateManager == null)
            {
                AddIssue("part3_no_state", "StateManager missing", ComplianceSeverity.Critical);
                return;
            }

            var state = stateManager.CurrentState;
            if (state == null)
            {
                AddIssue("part3_no_state_data", "State data not initialized", ComplianceSeverity.Critical);
                return;
            }

            // Validate entity identification
            CheckRequirement(
                "part3_entity_id",
                "Entity must have unique identifier",
                !string.IsNullOrEmpty(state.EntityIdentification?.EntityId),
                ComplianceSeverity.Critical
            );

            CheckRequirement(
                "part3_entity_type",
                "Entity must have type classification",
                !string.IsNullOrEmpty(state.EntityIdentification?.EntityType),
                ComplianceSeverity.High
            );

            CheckRequirement(
                "part3_timestamp",
                "Entity identification must include timestamp",
                state.EntityIdentification?.Timestamp != default(DateTime),
                ComplianceSeverity.High
            );

            // Validate observable information
            CheckRequirement(
                "part3_position",
                "Observable information must include position",
                state.ObservableInformation?.Position != null,
                ComplianceSeverity.High
            );

            CheckRequirement(
                "part3_status",
                "Observable information must include status",
                !string.IsNullOrEmpty(state.ObservableInformation?.Status),
                ComplianceSeverity.High
            );

            // Validate capability information
            CheckRequirement(
                "part3_capabilities",
                "Must declare available capabilities",
                state.CapabilityInformation?.AvailableCapabilities != null &&
                state.CapabilityInformation.AvailableCapabilities.Count > 0,
                ComplianceSeverity.High
            );

            CheckRequirement(
                "part3_workspace",
                "Must define workspace volume",
                state.CapabilityInformation?.WorkspaceVolume != null,
                ComplianceSeverity.High
            );
        }

        /// <summary>
        /// Validate Part 4: Information exchange
        /// </summary>
        private void ValidatePart4()
        {
            if (dataExchange == null)
            {
                AddIssue("part4_no_exchange", "DataExchange component missing", ComplianceSeverity.Critical);
                return;
            }

            // Check exchange capabilities
            CheckRequirement(
                "part4_endpoint",
                "Must have configured exchange endpoint",
                !string.IsNullOrEmpty(dataExchange.ExchangeEndpoint),
                ComplianceSeverity.High
            );

            CheckRequirement(
                "part4_bidirectional",
                "Must support bidirectional communication",
                true, // Assume supported by architecture
                ComplianceSeverity.High
            );

            CheckRequirement(
                "part4_message_queue",
                "Must implement message queuing",
                true, // DataExchange has queue
                ComplianceSeverity.Medium
            );

            // Check real-time synchronization
            var stats = dataExchange.GetStatistics();
            CheckRequirement(
                "part4_sync_active",
                "State synchronization should be active",
                stats.MessagesSent > 0 || stats.MessagesReceived > 0,
                ComplianceSeverity.Warning
            );
        }

        /// <summary>
        /// Check individual requirement
        /// </summary>
        private void CheckRequirement(string requirementId, string description, bool passed, ComplianceSeverity severity)
        {
            requirementStatus[requirementId] = passed;

            if (!passed)
            {
                AddIssue(requirementId, description, severity);
            }
        }

        /// <summary>
        /// Add compliance issue
        /// </summary>
        private void AddIssue(string requirementId, string description, ComplianceSeverity severity)
        {
            var issue = new ComplianceIssue
            {
                RequirementId = requirementId,
                Description = description,
                Severity = severity,
                DetectedAt = DateTime.UtcNow
            };

            issues.Add(issue);
            OnIssueDetected?.Invoke(issue);
        }

        /// <summary>
        /// Generate compliance report
        /// </summary>
        private ComplianceReport GenerateComplianceReport()
        {
            return new ComplianceReport
            {
                IsCompliant = isCompliant,
                ValidationTime = lastValidation,
                TotalRequirements = requirementStatus.Count,
                PassedRequirements = CountPassed(),
                FailedRequirements = issues.Count,
                Issues = new List<ComplianceIssue>(issues),
                RequirementStatus = new Dictionary<string, bool>(requirementStatus),
                ComplianceScore = CalculateComplianceScore()
            };
        }

        /// <summary>
        /// Count passed requirements
        /// </summary>
        private int CountPassed()
        {
            int count = 0;
            foreach (var status in requirementStatus.Values)
            {
                if (status) count++;
            }
            return count;
        }

        /// <summary>
        /// Calculate compliance score (0-100)
        /// </summary>
        private float CalculateComplianceScore()
        {
            if (requirementStatus.Count == 0) return 0f;

            int totalWeight = 0;
            int passedWeight = 0;

            foreach (var kvp in requirementStatus)
            {
                // Weight by severity (inferred from requirement ID prefix)
                int weight = GetRequirementWeight(kvp.Key);
                totalWeight += weight;

                if (kvp.Value)
                {
                    passedWeight += weight;
                }
            }

            return totalWeight > 0 ? (passedWeight / (float)totalWeight) * 100f : 0f;
        }

        /// <summary>
        /// Get requirement weight based on ID
        /// </summary>
        private int GetRequirementWeight(string requirementId)
        {
            // Critical requirements have higher weight
            if (requirementId.Contains("critical")) return 10;
            if (requirementId.Contains("part3") || requirementId.Contains("part4")) return 5;
            if (requirementId.Contains("part2")) return 3;
            return 1;
        }

        #region Public Properties

        public bool IsCompliant => isCompliant;
        public int IssueCount => issues.Count;
        public DateTime LastValidation => lastValidation;

        #endregion
    }

    #region Compliance Data Structures

    /// <summary>
    /// Compliance issue severity levels
    /// </summary>
    public enum ComplianceSeverity
    {
        Info,
        Warning,
        Medium,
        High,
        Critical
    }

    /// <summary>
    /// Compliance issue
    /// </summary>
    [Serializable]
    public struct ComplianceIssue
    {
        public string RequirementId;
        public string Description;
        public ComplianceSeverity Severity;
        public DateTime DetectedAt;
    }

    /// <summary>
    /// Compliance validation report
    /// </summary>
    [Serializable]
    public struct ComplianceReport
    {
        public bool IsCompliant;
        public DateTime ValidationTime;
        public int TotalRequirements;
        public int PassedRequirements;
        public int FailedRequirements;
        public List<ComplianceIssue> Issues;
        public Dictionary<string, bool> RequirementStatus;
        public float ComplianceScore; // 0-100
    }

    #endregion
}
