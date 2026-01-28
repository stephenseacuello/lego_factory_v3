using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNC_SCADA.DigitalTwin.Shifts
{
    /// <summary>
    /// Manages operator shifts, handoffs, breaks, and production tracking
    /// </summary>
    public class ShiftManagementSystem : MonoBehaviour
    {
        public static ShiftManagementSystem Instance { get; private set; }

        [Header("Shift Configuration")]
        [SerializeField] private int shiftDurationHours = 8;
        [SerializeField] private int breakDurationMinutes = 30;
        [SerializeField] private int handoffDurationMinutes = 15;
        [SerializeField] private bool autoRotateShifts = true;

        // Events
        public event Action<Shift> OnShiftStarted;
        public event Action<Shift> OnShiftEnded;
        public event Action<ShiftHandoff> OnHandoffStarted;
        public event Action<ShiftHandoff> OnHandoffCompleted;
        public event Action<Operator> OnOperatorClockedIn;
        public event Action<Operator> OnOperatorClockedOut;
        public event Action<Break> OnBreakStarted;
        public event Action<Break> OnBreakEnded;
        public event Action<string> OnAlertRaised;

        // Data storage
        private Dictionary<string, ShiftTemplate> shiftTemplates = new Dictionary<string, ShiftTemplate>();
        private Dictionary<string, Operator> operators = new Dictionary<string, Operator>();
        private Dictionary<string, Shift> activeShifts = new Dictionary<string, Shift>();
        private List<Shift> shiftHistory = new List<Shift>();
        private ShiftHandoff activeHandoff;

        // Current state
        public Shift CurrentShift { get; private set; }
        public List<Operator> ActiveOperators => operators.Values.Where(o => o.IsClockedIn).ToList();
        public bool IsHandoffInProgress => activeHandoff != null && !activeHandoff.IsCompleted;

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
                InitializeDefaultShiftTemplates();
                InitializeDemoOperators();
            }
            else
            {
                Destroy(gameObject);
            }
        }

        private void InitializeDefaultShiftTemplates()
        {
            // Day shift: 6 AM - 2 PM
            shiftTemplates["DAY"] = new ShiftTemplate
            {
                TemplateId = "DAY",
                Name = "Day Shift",
                StartTime = new TimeSpan(6, 0, 0),
                EndTime = new TimeSpan(14, 0, 0),
                BreakTimes = new List<TimeSpan>
                {
                    new TimeSpan(10, 0, 0) // 10 AM break
                },
                BreakDurationMinutes = breakDurationMinutes,
                MinOperators = 2,
                TargetOEE = 85f
            };

            // Swing shift: 2 PM - 10 PM
            shiftTemplates["SWING"] = new ShiftTemplate
            {
                TemplateId = "SWING",
                Name = "Swing Shift",
                StartTime = new TimeSpan(14, 0, 0),
                EndTime = new TimeSpan(22, 0, 0),
                BreakTimes = new List<TimeSpan>
                {
                    new TimeSpan(18, 0, 0) // 6 PM break
                },
                BreakDurationMinutes = breakDurationMinutes,
                MinOperators = 2,
                TargetOEE = 85f
            };

            // Night shift: 10 PM - 6 AM
            shiftTemplates["NIGHT"] = new ShiftTemplate
            {
                TemplateId = "NIGHT",
                Name = "Night Shift",
                StartTime = new TimeSpan(22, 0, 0),
                EndTime = new TimeSpan(6, 0, 0),
                BreakTimes = new List<TimeSpan>
                {
                    new TimeSpan(2, 0, 0) // 2 AM break
                },
                BreakDurationMinutes = breakDurationMinutes,
                MinOperators = 1,
                TargetOEE = 80f
            };

            Debug.Log($"[ShiftManagement] Initialized {shiftTemplates.Count} shift templates");
        }

        private void InitializeDemoOperators()
        {
            // Create demo operators with various certifications
            RegisterOperator(new Operator
            {
                OperatorId = "OP001",
                Name = "John Smith",
                BadgeNumber = "B001",
                Email = "john.smith@company.com",
                Phone = "+1-555-0101",
                HireDate = DateTime.Now.AddYears(-5),
                Certifications = new List<Certification>
                {
                    new Certification { Name = "CNC Mill Operation", Level = CertificationLevel.Expert, ExpiryDate = DateTime.Now.AddYears(1) },
                    new Certification { Name = "CNC Lathe Operation", Level = CertificationLevel.Advanced, ExpiryDate = DateTime.Now.AddYears(1) },
                    new Certification { Name = "Safety Training", Level = CertificationLevel.Expert, ExpiryDate = DateTime.Now.AddMonths(6) }
                },
                PreferredShift = "DAY",
                MaxHoursPerWeek = 40
            });

            RegisterOperator(new Operator
            {
                OperatorId = "OP002",
                Name = "Maria Garcia",
                BadgeNumber = "B002",
                Email = "maria.garcia@company.com",
                Phone = "+1-555-0102",
                HireDate = DateTime.Now.AddYears(-3),
                Certifications = new List<Certification>
                {
                    new Certification { Name = "CNC Mill Operation", Level = CertificationLevel.Advanced, ExpiryDate = DateTime.Now.AddYears(1) },
                    new Certification { Name = "Quality Inspection", Level = CertificationLevel.Expert, ExpiryDate = DateTime.Now.AddYears(2) },
                    new Certification { Name = "Safety Training", Level = CertificationLevel.Expert, ExpiryDate = DateTime.Now.AddMonths(8) }
                },
                PreferredShift = "DAY",
                MaxHoursPerWeek = 40
            });

            RegisterOperator(new Operator
            {
                OperatorId = "OP003",
                Name = "Robert Chen",
                BadgeNumber = "B003",
                Email = "robert.chen@company.com",
                Phone = "+1-555-0103",
                HireDate = DateTime.Now.AddYears(-7),
                Certifications = new List<Certification>
                {
                    new Certification { Name = "CNC Mill Operation", Level = CertificationLevel.Expert, ExpiryDate = DateTime.Now.AddYears(1) },
                    new Certification { Name = "CNC Lathe Operation", Level = CertificationLevel.Expert, ExpiryDate = DateTime.Now.AddYears(1) },
                    new Certification { Name = "Robot Programming", Level = CertificationLevel.Advanced, ExpiryDate = DateTime.Now.AddYears(1) },
                    new Certification { Name = "Safety Training", Level = CertificationLevel.Expert, ExpiryDate = DateTime.Now.AddMonths(4) }
                },
                PreferredShift = "SWING",
                MaxHoursPerWeek = 48
            });

            Debug.Log($"[ShiftManagement] Registered {operators.Count} demo operators");
        }

        #region Operator Management

        public void RegisterOperator(Operator op)
        {
            if (!operators.ContainsKey(op.OperatorId))
            {
                operators[op.OperatorId] = op;
                Debug.Log($"[ShiftManagement] Registered operator: {op.Name} ({op.OperatorId})");
            }
        }

        public Operator GetOperator(string operatorId)
        {
            return operators.TryGetValue(operatorId, out var op) ? op : null;
        }

        public List<Operator> GetQualifiedOperators(string certificationName, CertificationLevel minLevel = CertificationLevel.Basic)
        {
            return operators.Values.Where(op =>
                op.Certifications.Any(c =>
                    c.Name == certificationName &&
                    c.Level >= minLevel &&
                    c.ExpiryDate > DateTime.Now
                )).ToList();
        }

        public bool ClockIn(string operatorId, string machineId = null)
        {
            if (!operators.TryGetValue(operatorId, out var op))
            {
                Debug.LogWarning($"[ShiftManagement] Unknown operator: {operatorId}");
                return false;
            }

            if (op.IsClockedIn)
            {
                Debug.LogWarning($"[ShiftManagement] Operator {op.Name} already clocked in");
                return false;
            }

            op.IsClockedIn = true;
            op.ClockInTime = DateTime.Now;
            op.AssignedMachineId = machineId;
            op.CurrentShiftId = CurrentShift?.ShiftId;

            if (CurrentShift != null && !CurrentShift.AssignedOperators.Contains(operatorId))
            {
                CurrentShift.AssignedOperators.Add(operatorId);
            }

            OnOperatorClockedIn?.Invoke(op);
            Debug.Log($"[ShiftManagement] {op.Name} clocked in at {op.ClockInTime:HH:mm:ss}");

            return true;
        }

        public bool ClockOut(string operatorId)
        {
            if (!operators.TryGetValue(operatorId, out var op))
            {
                return false;
            }

            if (!op.IsClockedIn)
            {
                Debug.LogWarning($"[ShiftManagement] Operator {op.Name} not clocked in");
                return false;
            }

            var hoursWorked = (DateTime.Now - op.ClockInTime).TotalHours;
            op.TotalHoursThisWeek += (float)hoursWorked;

            op.IsClockedIn = false;
            op.ClockInTime = DateTime.MinValue;
            op.AssignedMachineId = null;

            OnOperatorClockedOut?.Invoke(op);
            Debug.Log($"[ShiftManagement] {op.Name} clocked out. Hours this shift: {hoursWorked:F2}");

            return true;
        }

        public bool AssignToMachine(string operatorId, string machineId)
        {
            if (!operators.TryGetValue(operatorId, out var op))
            {
                return false;
            }

            op.AssignedMachineId = machineId;
            Debug.Log($"[ShiftManagement] Assigned {op.Name} to machine {machineId}");
            return true;
        }

        #endregion

        #region Shift Management

        public Shift StartShift(string templateId)
        {
            if (!shiftTemplates.TryGetValue(templateId, out var template))
            {
                Debug.LogError($"[ShiftManagement] Unknown shift template: {templateId}");
                return null;
            }

            // End current shift if one is active
            if (CurrentShift != null && !CurrentShift.IsCompleted)
            {
                EndShift(CurrentShift.ShiftId);
            }

            var shift = new Shift
            {
                ShiftId = $"SHIFT-{DateTime.Now:yyyyMMdd-HHmmss}",
                TemplateId = templateId,
                Name = template.Name,
                PlannedStartTime = DateTime.Today.Add(template.StartTime),
                ActualStartTime = DateTime.Now,
                PlannedEndTime = DateTime.Today.Add(template.EndTime),
                TargetOEE = template.TargetOEE,
                Status = ShiftStatus.Active,
                ProductionTargets = new Dictionary<string, int>(),
                ProductionActuals = new Dictionary<string, int>(),
                AssignedOperators = new List<string>(),
                Notes = new List<ShiftNote>()
            };

            // Handle overnight shifts
            if (template.EndTime < template.StartTime)
            {
                shift.PlannedEndTime = shift.PlannedEndTime.AddDays(1);
            }

            activeShifts[shift.ShiftId] = shift;
            CurrentShift = shift;

            OnShiftStarted?.Invoke(shift);
            Debug.Log($"[ShiftManagement] Started {shift.Name} - ID: {shift.ShiftId}");

            // Check minimum operators
            if (ActiveOperators.Count < template.MinOperators)
            {
                OnAlertRaised?.Invoke($"Warning: {shift.Name} started with {ActiveOperators.Count}/{template.MinOperators} operators");
            }

            return shift;
        }

        public void EndShift(string shiftId)
        {
            if (!activeShifts.TryGetValue(shiftId, out var shift))
            {
                Debug.LogWarning($"[ShiftManagement] Unknown shift: {shiftId}");
                return;
            }

            shift.ActualEndTime = DateTime.Now;
            shift.Status = ShiftStatus.Completed;
            shift.IsCompleted = true;

            // Calculate shift metrics
            CalculateShiftMetrics(shift);

            shiftHistory.Add(shift);
            activeShifts.Remove(shiftId);

            if (CurrentShift?.ShiftId == shiftId)
            {
                CurrentShift = null;
            }

            OnShiftEnded?.Invoke(shift);
            Debug.Log($"[ShiftManagement] Ended {shift.Name} - Duration: {(shift.ActualEndTime - shift.ActualStartTime).TotalHours:F2}h, OEE: {shift.ActualOEE:F1}%");
        }

        private void CalculateShiftMetrics(Shift shift)
        {
            // Calculate total production vs targets
            int totalTarget = shift.ProductionTargets.Values.Sum();
            int totalActual = shift.ProductionActuals.Values.Sum();

            shift.ProductionEfficiency = totalTarget > 0 ? (float)totalActual / totalTarget * 100f : 0f;

            // Placeholder OEE calculation (would integrate with OEE analytics in real system)
            shift.ActualOEE = shift.ProductionEfficiency * 0.95f; // Simulated
        }

        public void SetProductionTarget(string shiftId, string partNumber, int quantity)
        {
            if (activeShifts.TryGetValue(shiftId, out var shift))
            {
                shift.ProductionTargets[partNumber] = quantity;
                Debug.Log($"[ShiftManagement] Set target for {partNumber}: {quantity} units");
            }
        }

        public void RecordProduction(string partNumber, int quantity)
        {
            if (CurrentShift != null)
            {
                if (!CurrentShift.ProductionActuals.ContainsKey(partNumber))
                {
                    CurrentShift.ProductionActuals[partNumber] = 0;
                }
                CurrentShift.ProductionActuals[partNumber] += quantity;
                Debug.Log($"[ShiftManagement] Recorded {quantity} {partNumber} - Total: {CurrentShift.ProductionActuals[partNumber]}");
            }
        }

        public void AddShiftNote(string shiftId, string operatorId, string note, ShiftNoteCategory category = ShiftNoteCategory.General)
        {
            if (activeShifts.TryGetValue(shiftId, out var shift))
            {
                shift.Notes.Add(new ShiftNote
                {
                    Timestamp = DateTime.Now,
                    OperatorId = operatorId,
                    Content = note,
                    Category = category
                });
                Debug.Log($"[ShiftManagement] Added note to shift: {note}");
            }
        }

        #endregion

        #region Break Management

        public Break StartBreak(string operatorId, BreakType breakType = BreakType.Scheduled)
        {
            if (!operators.TryGetValue(operatorId, out var op))
            {
                return null;
            }

            if (op.CurrentBreak != null && !op.CurrentBreak.IsCompleted)
            {
                Debug.LogWarning($"[ShiftManagement] {op.Name} already on break");
                return null;
            }

            var breakRecord = new Break
            {
                BreakId = $"BRK-{DateTime.Now:yyyyMMddHHmmss}",
                OperatorId = operatorId,
                Type = breakType,
                StartTime = DateTime.Now,
                PlannedDurationMinutes = breakDurationMinutes
            };

            op.CurrentBreak = breakRecord;
            op.Breaks.Add(breakRecord);

            OnBreakStarted?.Invoke(breakRecord);
            Debug.Log($"[ShiftManagement] {op.Name} started {breakType} break");

            return breakRecord;
        }

        public void EndBreak(string operatorId)
        {
            if (!operators.TryGetValue(operatorId, out var op))
            {
                return;
            }

            if (op.CurrentBreak == null || op.CurrentBreak.IsCompleted)
            {
                Debug.LogWarning($"[ShiftManagement] {op.Name} not on break");
                return;
            }

            op.CurrentBreak.EndTime = DateTime.Now;
            op.CurrentBreak.IsCompleted = true;
            op.CurrentBreak.ActualDurationMinutes = (int)(op.CurrentBreak.EndTime - op.CurrentBreak.StartTime).TotalMinutes;

            OnBreakEnded?.Invoke(op.CurrentBreak);

            var overtime = op.CurrentBreak.ActualDurationMinutes - op.CurrentBreak.PlannedDurationMinutes;
            if (overtime > 5)
            {
                OnAlertRaised?.Invoke($"{op.Name} break ran {overtime} minutes over scheduled time");
            }

            Debug.Log($"[ShiftManagement] {op.Name} ended break - Duration: {op.CurrentBreak.ActualDurationMinutes} min");
            op.CurrentBreak = null;
        }

        #endregion

        #region Handoff Management

        public ShiftHandoff InitiateHandoff(string outgoingShiftId, string incomingShiftTemplateId)
        {
            if (!activeShifts.TryGetValue(outgoingShiftId, out var outgoingShift))
            {
                Debug.LogError($"[ShiftManagement] Cannot handoff - unknown shift: {outgoingShiftId}");
                return null;
            }

            activeHandoff = new ShiftHandoff
            {
                HandoffId = $"HO-{DateTime.Now:yyyyMMddHHmmss}",
                OutgoingShiftId = outgoingShiftId,
                IncomingShiftTemplateId = incomingShiftTemplateId,
                StartTime = DateTime.Now,
                PlannedDurationMinutes = handoffDurationMinutes,
                Status = HandoffStatus.InProgress,
                Items = new List<HandoffItem>(),
                OutgoingOperators = new List<string>(outgoingShift.AssignedOperators),
                IncomingOperators = new List<string>()
            };

            // Auto-populate handoff items
            PopulateHandoffItems(activeHandoff, outgoingShift);

            OnHandoffStarted?.Invoke(activeHandoff);
            Debug.Log($"[ShiftManagement] Initiated handoff from {outgoingShift.Name}");

            return activeHandoff;
        }

        private void PopulateHandoffItems(ShiftHandoff handoff, Shift outgoingShift)
        {
            // Add production summary
            foreach (var kvp in outgoingShift.ProductionActuals)
            {
                int target = outgoingShift.ProductionTargets.TryGetValue(kvp.Key, out var t) ? t : 0;
                handoff.Items.Add(new HandoffItem
                {
                    Category = HandoffCategory.Production,
                    Title = $"{kvp.Key} Production",
                    Description = $"Completed {kvp.Value}/{target} units",
                    Priority = kvp.Value < target ? HandoffPriority.High : HandoffPriority.Normal,
                    IsAcknowledged = false
                });
            }

            // Add any shift notes as handoff items
            foreach (var note in outgoingShift.Notes.Where(n => n.Category == ShiftNoteCategory.HandoffRequired))
            {
                handoff.Items.Add(new HandoffItem
                {
                    Category = HandoffCategory.Issue,
                    Title = "Handoff Note",
                    Description = note.Content,
                    Priority = HandoffPriority.High,
                    IsAcknowledged = false
                });
            }
        }

        public void AddHandoffItem(string handoffId, HandoffItem item)
        {
            if (activeHandoff?.HandoffId == handoffId)
            {
                activeHandoff.Items.Add(item);
                Debug.Log($"[ShiftManagement] Added handoff item: {item.Title}");
            }
        }

        public void AcknowledgeHandoffItem(string handoffId, int itemIndex, string operatorId)
        {
            if (activeHandoff?.HandoffId == handoffId && itemIndex < activeHandoff.Items.Count)
            {
                activeHandoff.Items[itemIndex].IsAcknowledged = true;
                activeHandoff.Items[itemIndex].AcknowledgedBy = operatorId;
                activeHandoff.Items[itemIndex].AcknowledgedAt = DateTime.Now;
                Debug.Log($"[ShiftManagement] Item acknowledged by {operatorId}");
            }
        }

        public void CompleteHandoff(string handoffId)
        {
            if (activeHandoff?.HandoffId != handoffId)
            {
                Debug.LogWarning($"[ShiftManagement] Unknown handoff: {handoffId}");
                return;
            }

            // Check all items acknowledged
            var unacknowledged = activeHandoff.Items.Count(i => !i.IsAcknowledged);
            if (unacknowledged > 0)
            {
                OnAlertRaised?.Invoke($"Warning: {unacknowledged} handoff items not acknowledged");
            }

            activeHandoff.EndTime = DateTime.Now;
            activeHandoff.Status = HandoffStatus.Completed;
            activeHandoff.IsCompleted = true;

            // End outgoing shift
            EndShift(activeHandoff.OutgoingShiftId);

            // Start incoming shift
            var newShift = StartShift(activeHandoff.IncomingShiftTemplateId);

            OnHandoffCompleted?.Invoke(activeHandoff);
            Debug.Log($"[ShiftManagement] Handoff completed - New shift: {newShift?.Name}");

            activeHandoff = null;
        }

        #endregion

        #region Reporting

        public ShiftSummary GetShiftSummary(string shiftId)
        {
            Shift shift = null;
            if (!activeShifts.TryGetValue(shiftId, out shift))
            {
                shift = shiftHistory.FirstOrDefault(s => s.ShiftId == shiftId);
            }

            if (shift == null) return null;

            return new ShiftSummary
            {
                ShiftId = shift.ShiftId,
                Name = shift.Name,
                StartTime = shift.ActualStartTime,
                EndTime = shift.IsCompleted ? shift.ActualEndTime : DateTime.Now,
                Duration = (shift.IsCompleted ? shift.ActualEndTime : DateTime.Now) - shift.ActualStartTime,
                OperatorCount = shift.AssignedOperators.Count,
                TotalPartsProduced = shift.ProductionActuals.Values.Sum(),
                TotalPartsTarget = shift.ProductionTargets.Values.Sum(),
                OEE = shift.ActualOEE,
                NoteCount = shift.Notes.Count,
                IsActive = !shift.IsCompleted
            };
        }

        public List<ShiftSummary> GetShiftHistory(int days = 7)
        {
            var cutoff = DateTime.Now.AddDays(-days);
            return shiftHistory
                .Where(s => s.ActualStartTime >= cutoff)
                .Select(s => GetShiftSummary(s.ShiftId))
                .OrderByDescending(s => s.StartTime)
                .ToList();
        }

        public OperatorPerformance GetOperatorPerformance(string operatorId, int days = 30)
        {
            if (!operators.TryGetValue(operatorId, out var op))
            {
                return null;
            }

            var cutoff = DateTime.Now.AddDays(-days);
            var relevantShifts = shiftHistory.Where(s =>
                s.AssignedOperators.Contains(operatorId) &&
                s.ActualStartTime >= cutoff).ToList();

            return new OperatorPerformance
            {
                OperatorId = operatorId,
                Name = op.Name,
                TotalShifts = relevantShifts.Count,
                TotalHours = op.TotalHoursThisWeek,
                AverageOEE = relevantShifts.Any() ? relevantShifts.Average(s => s.ActualOEE) : 0f,
                CertificationCount = op.Certifications.Count(c => c.ExpiryDate > DateTime.Now),
                ExpiringSoonCertifications = op.Certifications.Count(c =>
                    c.ExpiryDate > DateTime.Now && c.ExpiryDate < DateTime.Now.AddDays(30))
            };
        }

        #endregion
    }

    #region Data Classes

    [Serializable]
    public class ShiftTemplate
    {
        public string TemplateId;
        public string Name;
        public TimeSpan StartTime;
        public TimeSpan EndTime;
        public List<TimeSpan> BreakTimes;
        public int BreakDurationMinutes;
        public int MinOperators;
        public float TargetOEE;
    }

    [Serializable]
    public class Shift
    {
        public string ShiftId;
        public string TemplateId;
        public string Name;
        public DateTime PlannedStartTime;
        public DateTime ActualStartTime;
        public DateTime PlannedEndTime;
        public DateTime ActualEndTime;
        public ShiftStatus Status;
        public bool IsCompleted;
        public float TargetOEE;
        public float ActualOEE;
        public float ProductionEfficiency;
        public Dictionary<string, int> ProductionTargets;
        public Dictionary<string, int> ProductionActuals;
        public List<string> AssignedOperators;
        public List<ShiftNote> Notes;
    }

    public enum ShiftStatus
    {
        Scheduled,
        Active,
        Handoff,
        Completed,
        Cancelled
    }

    [Serializable]
    public class ShiftNote
    {
        public DateTime Timestamp;
        public string OperatorId;
        public string Content;
        public ShiftNoteCategory Category;
    }

    public enum ShiftNoteCategory
    {
        General,
        Safety,
        Quality,
        Maintenance,
        HandoffRequired
    }

    [Serializable]
    public class Operator
    {
        public string OperatorId;
        public string Name;
        public string BadgeNumber;
        public string Email;
        public string Phone;
        public DateTime HireDate;
        public List<Certification> Certifications = new List<Certification>();
        public string PreferredShift;
        public float MaxHoursPerWeek;
        public float TotalHoursThisWeek;

        // Runtime state
        public bool IsClockedIn;
        public DateTime ClockInTime;
        public string AssignedMachineId;
        public string CurrentShiftId;
        public Break CurrentBreak;
        public List<Break> Breaks = new List<Break>();
    }

    [Serializable]
    public class Certification
    {
        public string Name;
        public CertificationLevel Level;
        public DateTime IssueDate;
        public DateTime ExpiryDate;
        public string IssuedBy;
    }

    public enum CertificationLevel
    {
        Basic,
        Intermediate,
        Advanced,
        Expert
    }

    [Serializable]
    public class Break
    {
        public string BreakId;
        public string OperatorId;
        public BreakType Type;
        public DateTime StartTime;
        public DateTime EndTime;
        public int PlannedDurationMinutes;
        public int ActualDurationMinutes;
        public bool IsCompleted;
    }

    public enum BreakType
    {
        Scheduled,
        Lunch,
        Personal,
        Emergency
    }

    [Serializable]
    public class ShiftHandoff
    {
        public string HandoffId;
        public string OutgoingShiftId;
        public string IncomingShiftTemplateId;
        public DateTime StartTime;
        public DateTime EndTime;
        public int PlannedDurationMinutes;
        public HandoffStatus Status;
        public bool IsCompleted;
        public List<HandoffItem> Items;
        public List<string> OutgoingOperators;
        public List<string> IncomingOperators;
    }

    public enum HandoffStatus
    {
        Pending,
        InProgress,
        Completed,
        Cancelled
    }

    [Serializable]
    public class HandoffItem
    {
        public HandoffCategory Category;
        public string Title;
        public string Description;
        public HandoffPriority Priority;
        public bool IsAcknowledged;
        public string AcknowledgedBy;
        public DateTime AcknowledgedAt;
    }

    public enum HandoffCategory
    {
        Production,
        Quality,
        Maintenance,
        Safety,
        Issue,
        Information
    }

    public enum HandoffPriority
    {
        Low,
        Normal,
        High,
        Critical
    }

    [Serializable]
    public class ShiftSummary
    {
        public string ShiftId;
        public string Name;
        public DateTime StartTime;
        public DateTime EndTime;
        public TimeSpan Duration;
        public int OperatorCount;
        public int TotalPartsProduced;
        public int TotalPartsTarget;
        public float OEE;
        public int NoteCount;
        public bool IsActive;
    }

    [Serializable]
    public class OperatorPerformance
    {
        public string OperatorId;
        public string Name;
        public int TotalShifts;
        public float TotalHours;
        public float AverageOEE;
        public int CertificationCount;
        public int ExpiringSoonCertifications;
    }

    #endregion
}
