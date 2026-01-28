using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCScada.Scheduling
{
    /// <summary>
    /// Dynamic production scheduler with real-time optimization.
    /// Adjusts job sequences based on machine availability, priority, and constraints.
    /// Part of Feature 4.1: Dynamic Scheduling (HIGH PRIORITY - Phase 4)
    /// </summary>
    public class DynamicScheduler : MonoBehaviour
    {
        [Header("Scheduling Configuration")]
        [SerializeField] private bool enableAutoScheduling = true;
        [SerializeField] private float schedulingInterval = 60f; // Re-optimize every minute
        [SerializeField] private int maxJobsPerMachine = 10;

        [Header("Optimization Strategy")]
        [SerializeField] private SchedulingStrategy strategy = SchedulingStrategy.MinimizeMakespan;
        [SerializeField] private bool considerSetupTime = true;
        [SerializeField] private bool considerToolAvailability = true;
        [SerializeField] private bool considerOperatorSkills = true;

        [Header("Constraints")]
        [SerializeField] private float maxMachineUtilization = 0.95f;
        [SerializeField] private float minBufferTime = 300f; // 5 minutes in seconds
        [SerializeField] private bool allowJobSplitting = false;

        // Job and machine tracking
        private List<Job> pendingJobs = new List<Job>();
        private List<Job> scheduledJobs = new List<Job>();
        private List<Job> completedJobs = new List<Job>();
        private Dictionary<string, MachineStatus> machineStatuses = new Dictionary<string, MachineStatus>();

        // Scheduling state
        private float schedulingTimer = 0f;
        private Schedule currentSchedule;
        private bool scheduleNeedsUpdate = false;

        // Events
        public event Action<Schedule> OnScheduleUpdated;
        public event Action<Job> OnJobStarted;
        public event Action<Job> OnJobCompleted;
        public event Action<Job> OnJobDelayed;
        public event Action<ScheduleConflict> OnConflictDetected;

        // Statistics
        private int totalJobsScheduled = 0;
        private int totalReschedulingEvents = 0;
        private float averageMakespan = 0f;
        private float averageUtilization = 0f;

        void Start()
        {
            InitializeScheduler();
        }

        void Update()
        {
            if (!enableAutoScheduling) return;

            schedulingTimer += Time.deltaTime;
            if (schedulingTimer >= schedulingInterval || scheduleNeedsUpdate)
            {
                OptimizeSchedule();
                schedulingTimer = 0f;
                scheduleNeedsUpdate = false;
            }
        }

        /// <summary>
        /// Initialize scheduler
        /// </summary>
        private void InitializeScheduler()
        {
            currentSchedule = new Schedule
            {
                ScheduleId = Guid.NewGuid().ToString(),
                CreationTime = DateTime.UtcNow,
                Jobs = new List<Job>(),
                Assignments = new List<JobAssignment>()
            };

            Debug.Log("[DynamicScheduler] Initialized with strategy: " + strategy);
        }

        /// <summary>
        /// Add a new job to the scheduling queue
        /// </summary>
        public void AddJob(string jobId, string partNumber, int quantity,
                          float estimatedCycleTime, JobPriority priority = JobPriority.Normal,
                          DateTime? dueDate = null)
        {
            var job = new Job
            {
                JobId = jobId,
                PartNumber = partNumber,
                Quantity = quantity,
                EstimatedCycleTime = estimatedCycleTime,
                Priority = priority,
                DueDate = dueDate ?? DateTime.UtcNow.AddDays(7),
                Status = JobStatus.Pending,
                CreatedTime = DateTime.UtcNow
            };

            pendingJobs.Add(job);
            scheduleNeedsUpdate = true;

            Debug.Log($"[DynamicScheduler] Job added: {jobId} ({quantity}x {partNumber})");
        }

        /// <summary>
        /// Register machine status
        /// </summary>
        public void UpdateMachineStatus(string machineId, bool available,
                                       float currentUtilization, List<string> capabilities)
        {
            if (!machineStatuses.ContainsKey(machineId))
            {
                machineStatuses[machineId] = new MachineStatus
                {
                    MachineId = machineId,
                    Capabilities = capabilities ?? new List<string>()
                };
            }

            var status = machineStatuses[machineId];
            status.Available = available;
            status.CurrentUtilization = currentUtilization;
            status.LastUpdate = DateTime.UtcNow;

            if (available && currentUtilization < maxMachineUtilization)
            {
                scheduleNeedsUpdate = true;
            }
        }

        /// <summary>
        /// Optimize production schedule
        /// </summary>
        public void OptimizeSchedule()
        {
            if (pendingJobs.Count == 0)
            {
                Debug.Log("[DynamicScheduler] No pending jobs to schedule");
                return;
            }

            var startTime = Time.realtimeSinceStartup;

            // Sort jobs by priority and due date
            var sortedJobs = SortJobsByStrategy(pendingJobs);

            // Clear previous assignments
            currentSchedule.Assignments.Clear();

            // Assign jobs to machines
            foreach (var job in sortedJobs)
            {
                var assignment = FindBestMachine(job);
                if (assignment != null)
                {
                    currentSchedule.Assignments.Add(assignment);
                    scheduledJobs.Add(job);
                    pendingJobs.Remove(job);
                    job.Status = JobStatus.Scheduled;
                }
            }

            // Calculate schedule metrics
            currentSchedule.Makespan = CalculateMakespan();
            currentSchedule.AverageUtilization = CalculateAverageUtilization();
            currentSchedule.TotalJobs = currentSchedule.Assignments.Count;
            currentSchedule.UpdateTime = DateTime.UtcNow;

            totalJobsScheduled += currentSchedule.Assignments.Count;
            totalReschedulingEvents++;

            var optimizationTime = (Time.realtimeSinceStartup - startTime) * 1000f;

            OnScheduleUpdated?.Invoke(currentSchedule);

            Debug.Log($"[DynamicScheduler] Schedule optimized: {currentSchedule.Assignments.Count} jobs assigned, " +
                     $"makespan: {currentSchedule.Makespan:F1}s, utilization: {currentSchedule.AverageUtilization:P1}, " +
                     $"optimization time: {optimizationTime:F1}ms");
        }

        /// <summary>
        /// Sort jobs based on scheduling strategy
        /// </summary>
        private List<Job> SortJobsByStrategy(List<Job> jobs)
        {
            switch (strategy)
            {
                case SchedulingStrategy.FIFO:
                    return jobs.OrderBy(j => j.CreatedTime).ToList();

                case SchedulingStrategy.EarliestDueDate:
                    return jobs.OrderBy(j => j.DueDate).ThenByDescending(j => j.Priority).ToList();

                case SchedulingStrategy.ShortestProcessingTime:
                    return jobs.OrderBy(j => j.EstimatedCycleTime * j.Quantity).ToList();

                case SchedulingStrategy.HighestPriority:
                    return jobs.OrderByDescending(j => j.Priority).ThenBy(j => j.DueDate).ToList();

                case SchedulingStrategy.MinimizeMakespan:
                    // Critical ratio: (Due Date - Now) / Processing Time
                    return jobs.OrderBy(j =>
                    {
                        float timeRemaining = (float)(j.DueDate - DateTime.UtcNow).TotalSeconds;
                        float processingTime = j.EstimatedCycleTime * j.Quantity;
                        return timeRemaining / processingTime;
                    }).ToList();

                default:
                    return jobs.OrderBy(j => j.CreatedTime).ToList();
            }
        }

        /// <summary>
        /// Find best machine for a job
        /// </summary>
        private JobAssignment FindBestMachine(Job job)
        {
            JobAssignment bestAssignment = null;
            float bestScore = float.MinValue;

            foreach (var machine in machineStatuses.Values)
            {
                if (!machine.Available) continue;
                if (machine.CurrentUtilization >= maxMachineUtilization) continue;

                // Check if machine has required capabilities
                if (job.RequiredCapabilities != null && job.RequiredCapabilities.Count > 0)
                {
                    bool hasCapabilities = job.RequiredCapabilities.All(c => machine.Capabilities.Contains(c));
                    if (!hasCapabilities) continue;
                }

                // Calculate assignment score
                float score = CalculateAssignmentScore(job, machine);

                if (score > bestScore)
                {
                    bestScore = score;
                    bestAssignment = new JobAssignment
                    {
                        JobId = job.JobId,
                        MachineId = machine.MachineId,
                        StartTime = DateTime.UtcNow.AddSeconds(minBufferTime),
                        EstimatedEndTime = DateTime.UtcNow.AddSeconds(minBufferTime + (job.EstimatedCycleTime * job.Quantity)),
                        Score = score
                    };
                }
            }

            return bestAssignment;
        }

        /// <summary>
        /// Calculate assignment score for machine selection
        /// </summary>
        private float CalculateAssignmentScore(Job job, MachineStatus machine)
        {
            float score = 0f;

            // Factor 1: Machine utilization (prefer balanced load)
            float utilizationScore = 1f - machine.CurrentUtilization;
            score += utilizationScore * 0.3f;

            // Factor 2: Setup time consideration
            if (considerSetupTime && machine.LastJobPart != null)
            {
                if (machine.LastJobPart == job.PartNumber)
                {
                    score += 0.3f; // Same part, minimal setup
                }
                else
                {
                    score -= 0.1f; // Different part, setup required
                }
            }

            // Factor 3: Due date urgency
            float timeToDeadline = (float)(job.DueDate - DateTime.UtcNow).TotalSeconds;
            float urgencyScore = Mathf.Clamp01(1f - (timeToDeadline / 86400f)); // Normalize to 1 day
            score += urgencyScore * 0.2f;

            // Factor 4: Job priority
            score += (int)job.Priority * 0.2f;

            return score;
        }

        /// <summary>
        /// Calculate total makespan
        /// </summary>
        private float CalculateMakespan()
        {
            if (currentSchedule.Assignments.Count == 0) return 0f;

            DateTime maxEndTime = currentSchedule.Assignments.Max(a => a.EstimatedEndTime);
            DateTime minStartTime = currentSchedule.Assignments.Min(a => a.StartTime);

            return (float)(maxEndTime - minStartTime).TotalSeconds;
        }

        /// <summary>
        /// Calculate average machine utilization
        /// </summary>
        private float CalculateAverageUtilization()
        {
            if (machineStatuses.Count == 0) return 0f;
            return machineStatuses.Values.Average(m => m.CurrentUtilization);
        }

        /// <summary>
        /// Mark job as started
        /// </summary>
        public void StartJob(string jobId)
        {
            var job = scheduledJobs.Find(j => j.JobId == jobId);
            if (job != null)
            {
                job.Status = JobStatus.InProgress;
                job.ActualStartTime = DateTime.UtcNow;
                OnJobStarted?.Invoke(job);
                Debug.Log($"[DynamicScheduler] Job started: {jobId}");
            }
        }

        /// <summary>
        /// Mark job as completed
        /// </summary>
        public void CompleteJob(string jobId)
        {
            var job = scheduledJobs.Find(j => j.JobId == jobId);
            if (job != null)
            {
                job.Status = JobStatus.Completed;
                job.ActualEndTime = DateTime.UtcNow;
                scheduledJobs.Remove(job);
                completedJobs.Add(job);
                OnJobCompleted?.Invoke(job);

                // Update statistics
                float actualMakespan = (float)(job.ActualEndTime.Value - job.ActualStartTime.Value).TotalSeconds;
                averageMakespan = (averageMakespan * (completedJobs.Count - 1) + actualMakespan) / completedJobs.Count;

                Debug.Log($"[DynamicScheduler] Job completed: {jobId}, makespan: {actualMakespan:F1}s");
            }
        }

        /// <summary>
        /// Detect scheduling conflicts
        /// </summary>
        public List<ScheduleConflict> DetectConflicts()
        {
            var conflicts = new List<ScheduleConflict>();

            // Check for overlapping assignments on same machine
            var machineGroups = currentSchedule.Assignments.GroupBy(a => a.MachineId);

            foreach (var group in machineGroups)
            {
                var assignments = group.OrderBy(a => a.StartTime).ToList();

                for (int i = 0; i < assignments.Count - 1; i++)
                {
                    if (assignments[i].EstimatedEndTime > assignments[i + 1].StartTime)
                    {
                        var conflict = new ScheduleConflict
                        {
                            ConflictType = ConflictType.OverlappingJobs,
                            MachineId = group.Key,
                            Job1Id = assignments[i].JobId,
                            Job2Id = assignments[i + 1].JobId,
                            ConflictTime = assignments[i].EstimatedEndTime
                        };

                        conflicts.Add(conflict);
                        OnConflictDetected?.Invoke(conflict);
                    }
                }
            }

            return conflicts;
        }

        /// <summary>
        /// Get schedule statistics
        /// </summary>
        public ScheduleStatistics GetStatistics()
        {
            return new ScheduleStatistics
            {
                TotalJobsScheduled = totalJobsScheduled,
                PendingJobs = pendingJobs.Count,
                ScheduledJobs = scheduledJobs.Count,
                CompletedJobs = completedJobs.Count,
                TotalReschedulingEvents = totalReschedulingEvents,
                AverageMakespan = averageMakespan,
                AverageUtilization = averageUtilization,
                CurrentMachines = machineStatuses.Count,
                SchedulingStrategy = strategy.ToString()
            };
        }

        /// <summary>
        /// Force immediate rescheduling
        /// </summary>
        public void ForceReschedule()
        {
            scheduleNeedsUpdate = true;
            schedulingTimer = schedulingInterval; // Trigger on next update
            Debug.Log("[DynamicScheduler] Forced reschedule requested");
        }

        #region Public Properties

        public Schedule CurrentSchedule => currentSchedule;
        public int PendingJobCount => pendingJobs.Count;
        public int ScheduledJobCount => scheduledJobs.Count;
        public int CompletedJobCount => completedJobs.Count;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Production job
    /// </summary>
    [Serializable]
    public class Job
    {
        public string JobId;
        public string PartNumber;
        public int Quantity;
        public float EstimatedCycleTime; // seconds per part
        public JobPriority Priority;
        public DateTime DueDate;
        public JobStatus Status;
        public DateTime CreatedTime;
        public DateTime? ActualStartTime;
        public DateTime? ActualEndTime;
        public List<string> RequiredCapabilities;
    }

    /// <summary>
    /// Job assignment to machine
    /// </summary>
    [Serializable]
    public class JobAssignment
    {
        public string JobId;
        public string MachineId;
        public DateTime StartTime;
        public DateTime EstimatedEndTime;
        public float Score;
    }

    /// <summary>
    /// Production schedule
    /// </summary>
    [Serializable]
    public class Schedule
    {
        public string ScheduleId;
        public DateTime CreationTime;
        public DateTime UpdateTime;
        public List<Job> Jobs;
        public List<JobAssignment> Assignments;
        public float Makespan; // Total time span
        public float AverageUtilization;
        public int TotalJobs;
    }

    /// <summary>
    /// Machine status
    /// </summary>
    [Serializable]
    public class MachineStatus
    {
        public string MachineId;
        public bool Available;
        public float CurrentUtilization; // 0-1
        public List<string> Capabilities;
        public string LastJobPart;
        public DateTime LastUpdate;
    }

    /// <summary>
    /// Schedule conflict
    /// </summary>
    [Serializable]
    public class ScheduleConflict
    {
        public ConflictType ConflictType;
        public string MachineId;
        public string Job1Id;
        public string Job2Id;
        public DateTime ConflictTime;
    }

    /// <summary>
    /// Schedule statistics
    /// </summary>
    [Serializable]
    public struct ScheduleStatistics
    {
        public int TotalJobsScheduled;
        public int PendingJobs;
        public int ScheduledJobs;
        public int CompletedJobs;
        public int TotalReschedulingEvents;
        public float AverageMakespan;
        public float AverageUtilization;
        public int CurrentMachines;
        public string SchedulingStrategy;
    }

    /// <summary>
    /// Scheduling strategies
    /// </summary>
    public enum SchedulingStrategy
    {
        FIFO,                       // First In First Out
        EarliestDueDate,           // Earliest due date first
        ShortestProcessingTime,    // Shortest job first
        HighestPriority,           // Priority-based
        MinimizeMakespan           // Critical ratio scheduling
    }

    /// <summary>
    /// Job status
    /// </summary>
    public enum JobStatus
    {
        Pending,
        Scheduled,
        InProgress,
        Completed,
        Cancelled,
        Delayed
    }

    /// <summary>
    /// Job priority
    /// </summary>
    public enum JobPriority
    {
        Low = 1,
        Normal = 2,
        High = 3,
        Critical = 4
    }

    /// <summary>
    /// Conflict types
    /// </summary>
    public enum ConflictType
    {
        OverlappingJobs,
        ResourceUnavailable,
        CapabilityMismatch,
        DeadlineMissed
    }

    #endregion
}
