using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCScada.Training
{
    /// <summary>
    /// Operator Training Mode - Interactive simulation for operator skill development.
    /// Part of Feature 4.3: Operator Training Mode (Phase 4)
    ///
    /// Provides:
    /// - Guided training scenarios (setup, tooling, operations)
    /// - Real-time performance tracking
    /// - Step-by-step instructions with validation
    /// - Certification progress tracking
    /// - Safety protocol training
    /// </summary>
    public class OperatorTrainingMode : MonoBehaviour
    {
        [Header("Training Configuration")]
        [SerializeField] private string operatorId = "OP-001";
        [SerializeField] private bool enableGuidedMode = true;
        [SerializeField] private bool enableSafetyChecks = true;
        [SerializeField] private float timeoutSeconds = 300f; // 5 minutes per step

        [Header("Performance Thresholds")]
        [SerializeField] private float passingScore = 0.75f; // 75% to pass
        [SerializeField] private float excellentScore = 0.90f; // 90% for excellent
        [SerializeField] private int maxAttempts = 3;

        [Header("UI References")]
        [SerializeField] private GameObject trainingPanel;
        [SerializeField] private GameObject instructionPanel;
        [SerializeField] private GameObject feedbackPanel;

        // Training state
        private TrainingSession currentSession;
        private TrainingScenario currentScenario;
        private int currentStepIndex = 0;
        private bool sessionActive = false;
        private DateTime stepStartTime;
        private List<StepPerformance> stepPerformances = new List<StepPerformance>();

        // Available scenarios
        private Dictionary<string, TrainingScenario> scenarios = new Dictionary<string, TrainingScenario>();

        // Performance tracking
        private int totalSessions = 0;
        private int completedSessions = 0;
        private int failedSessions = 0;
        private float avgSessionScore = 0f;

        // Events
        public event Action<TrainingSession> OnSessionStarted;
        public event Action<TrainingSession> OnSessionCompleted;
        public event Action<StepPerformance> OnStepCompleted;
        public event Action<TrainingFeedback> OnFeedbackGenerated;

        void Start()
        {
            InitializeScenarios();
            Debug.Log("[Training] Operator Training Mode initialized");
        }

        /// <summary>
        /// Initialize available training scenarios
        /// </summary>
        private void InitializeScenarios()
        {
            // Scenario 1: Machine Setup
            scenarios["machine_setup"] = new TrainingScenario
            {
                ScenarioId = "machine_setup",
                Title = "CNC Machine Setup",
                Description = "Learn proper machine startup and configuration procedures",
                Difficulty = TrainingDifficulty.Beginner,
                EstimatedDuration = 600f, // 10 minutes
                Steps = new List<TrainingStep>
                {
                    new TrainingStep
                    {
                        StepId = "power_on",
                        Title = "Power On Machine",
                        Instruction = "Turn on main power switch and wait for system initialization",
                        ExpectedAction = "power_on",
                        TimeLimit = 60f,
                        Points = 10
                    },
                    new TrainingStep
                    {
                        StepId = "home_axes",
                        Title = "Home All Axes",
                        Instruction = "Execute homing sequence for X, Y, Z axes",
                        ExpectedAction = "home_all",
                        TimeLimit = 120f,
                        Points = 20
                    },
                    new TrainingStep
                    {
                        StepId = "load_tool",
                        Title = "Load Tool",
                        Instruction = "Install tool #1 in spindle and verify seating",
                        ExpectedAction = "tool_change",
                        TimeLimit = 180f,
                        Points = 30
                    },
                    new TrainingStep
                    {
                        StepId = "set_work_offset",
                        Title = "Set Work Offset",
                        Instruction = "Touch off workpiece and set G54 offset",
                        ExpectedAction = "set_offset",
                        TimeLimit = 240f,
                        Points = 40
                    }
                }
            };

            // Scenario 2: Tool Change Operations
            scenarios["tool_change"] = new TrainingScenario
            {
                ScenarioId = "tool_change",
                Title = "Tool Change Procedures",
                Description = "Master safe and efficient tool changing operations",
                Difficulty = TrainingDifficulty.Intermediate,
                EstimatedDuration = 480f, // 8 minutes
                Steps = new List<TrainingStep>
                {
                    new TrainingStep
                    {
                        StepId = "pause_program",
                        Title = "Pause Program",
                        Instruction = "Safely pause program execution",
                        ExpectedAction = "pause",
                        TimeLimit = 30f,
                        Points = 15
                    },
                    new TrainingStep
                    {
                        StepId = "retract_spindle",
                        Title = "Retract Spindle",
                        Instruction = "Raise spindle to safe height (Z+50mm)",
                        ExpectedAction = "jog_z",
                        TimeLimit = 60f,
                        Points = 20
                    },
                    new TrainingStep
                    {
                        StepId = "remove_tool",
                        Title = "Remove Current Tool",
                        Instruction = "Safely remove tool from spindle",
                        ExpectedAction = "tool_release",
                        TimeLimit = 120f,
                        Points = 30
                    },
                    new TrainingStep
                    {
                        StepId = "install_new_tool",
                        Title = "Install New Tool",
                        Instruction = "Install new tool and verify",
                        ExpectedAction = "tool_insert",
                        TimeLimit = 120f,
                        Points = 35
                    }
                }
            };

            // Scenario 3: Emergency Stop Procedures
            scenarios["emergency_stop"] = new TrainingScenario
            {
                ScenarioId = "emergency_stop",
                Title = "Emergency Stop Procedures",
                Description = "Critical safety training for emergency situations",
                Difficulty = TrainingDifficulty.Beginner,
                EstimatedDuration = 300f, // 5 minutes
                RequiresSafetyCertification = true,
                Steps = new List<TrainingStep>
                {
                    new TrainingStep
                    {
                        StepId = "recognize_hazard",
                        Title = "Recognize Hazard",
                        Instruction = "Identify potential safety hazard (collision, fire, etc.)",
                        ExpectedAction = "hazard_identify",
                        TimeLimit = 20f,
                        Points = 25
                    },
                    new TrainingStep
                    {
                        StepId = "activate_estop",
                        Title = "Activate E-Stop",
                        Instruction = "Immediately press emergency stop button",
                        ExpectedAction = "emergency_stop",
                        TimeLimit = 5f, // Must be fast!
                        Points = 50,
                        IsCritical = true
                    },
                    new TrainingStep
                    {
                        StepId = "secure_area",
                        Title = "Secure Area",
                        Instruction = "Clear personnel from machine area",
                        ExpectedAction = "area_secure",
                        TimeLimit = 30f,
                        Points = 25
                    }
                }
            };

            Debug.Log($"[Training] Initialized {scenarios.Count} training scenarios");
        }

        /// <summary>
        /// Start training session
        /// </summary>
        public void StartSession(string scenarioId, string operatorIdOverride = null)
        {
            if (sessionActive)
            {
                Debug.LogWarning("[Training] Session already active");
                return;
            }

            if (!scenarios.ContainsKey(scenarioId))
            {
                Debug.LogError($"[Training] Scenario not found: {scenarioId}");
                return;
            }

            currentScenario = scenarios[scenarioId];
            currentStepIndex = 0;
            stepPerformances.Clear();

            currentSession = new TrainingSession
            {
                SessionId = Guid.NewGuid().ToString(),
                OperatorId = operatorIdOverride ?? operatorId,
                ScenarioId = scenarioId,
                StartTime = DateTime.UtcNow,
                Difficulty = currentScenario.Difficulty,
                AttemptNumber = 1,
                GuidedMode = enableGuidedMode
            };

            sessionActive = true;
            totalSessions++;

            OnSessionStarted?.Invoke(currentSession);

            // Start first step
            StartStep(0);

            Debug.Log($"[Training] Session started: {scenarioId} for operator {currentSession.OperatorId}");
        }

        /// <summary>
        /// Start specific training step
        /// </summary>
        private void StartStep(int stepIndex)
        {
            if (stepIndex >= currentScenario.Steps.Count)
            {
                CompleteSession();
                return;
            }

            currentStepIndex = stepIndex;
            stepStartTime = DateTime.UtcNow;

            var step = currentScenario.Steps[stepIndex];
            Debug.Log($"[Training] Step {stepIndex + 1}/{currentScenario.Steps.Count}: {step.Title}");

            // Show instruction if guided mode enabled
            if (enableGuidedMode && instructionPanel != null)
            {
                // Display instruction to operator
                ShowInstruction(step);
            }
        }

        /// <summary>
        /// Record operator action for current step
        /// </summary>
        public void RecordAction(string action, bool isCorrect = true, Dictionary<string, float> metrics = null)
        {
            if (!sessionActive || currentStepIndex >= currentScenario.Steps.Count)
            {
                return;
            }

            var step = currentScenario.Steps[currentStepIndex];
            var completionTime = (float)(DateTime.UtcNow - stepStartTime).TotalSeconds;

            // Validate action
            bool actionCorrect = (action == step.ExpectedAction) && isCorrect;
            bool timedOut = completionTime > step.TimeLimit;

            // Calculate step score
            float timeScore = timedOut ? 0f : 1f - (completionTime / step.TimeLimit) * 0.3f; // 70% base + 30% time bonus
            float accuracyScore = actionCorrect ? 1f : 0f;
            float stepScore = (accuracyScore * 0.7f + timeScore * 0.3f) * step.Points;

            var performance = new StepPerformance
            {
                StepId = step.StepId,
                StepIndex = currentStepIndex,
                ActionTaken = action,
                IsCorrect = actionCorrect,
                TimedOut = timedOut,
                CompletionTime = completionTime,
                TimeLimit = step.TimeLimit,
                PointsEarned = actionCorrect ? stepScore : 0f,
                MaxPoints = step.Points,
                Accuracy = accuracyScore,
                Metrics = metrics
            };

            stepPerformances.Add(performance);
            OnStepCompleted?.Invoke(performance);

            // Provide feedback
            var feedback = GenerateFeedback(step, performance);
            OnFeedbackGenerated?.Invoke(feedback);

            if (feedbackPanel != null)
            {
                ShowFeedback(feedback);
            }

            // Check for critical failure
            if (step.IsCritical && !actionCorrect)
            {
                Debug.LogError($"[Training] Critical step failed: {step.Title}");
                FailSession("Critical safety step failed");
                return;
            }

            // Move to next step
            StartStep(currentStepIndex + 1);
        }

        /// <summary>
        /// Generate feedback for step performance
        /// </summary>
        private TrainingFeedback GenerateFeedback(TrainingStep step, StepPerformance performance)
        {
            var feedback = new TrainingFeedback
            {
                StepTitle = step.Title,
                IsCorrect = performance.IsCorrect,
                CompletionTime = performance.CompletionTime,
                ExpectedTime = step.TimeLimit
            };

            if (performance.IsCorrect)
            {
                if (performance.CompletionTime < step.TimeLimit * 0.5f)
                {
                    feedback.Rating = PerformanceRating.Excellent;
                    feedback.Message = "Excellent! Completed quickly and accurately.";
                    feedback.Tips = new List<string> { "Great speed and accuracy. Keep it up!" };
                }
                else if (performance.CompletionTime < step.TimeLimit * 0.8f)
                {
                    feedback.Rating = PerformanceRating.Good;
                    feedback.Message = "Good job! Completed correctly.";
                    feedback.Tips = new List<string> { "Try to improve your speed while maintaining accuracy." };
                }
                else
                {
                    feedback.Rating = PerformanceRating.Acceptable;
                    feedback.Message = "Acceptable. Completed correctly but could be faster.";
                    feedback.Tips = new List<string> { "Practice to improve your speed. Review the procedure." };
                }
            }
            else
            {
                feedback.Rating = PerformanceRating.NeedsImprovement;
                feedback.Message = performance.TimedOut ?
                    "Time limit exceeded. Review the procedure." :
                    "Incorrect action. Review the correct procedure.";
                feedback.Tips = new List<string>
                {
                    $"Expected action: {step.ExpectedAction}",
                    "Review training materials for this step",
                    "Try again and focus on the instructions"
                };
            }

            return feedback;
        }

        /// <summary>
        /// Complete training session
        /// </summary>
        private void CompleteSession()
        {
            if (!sessionActive) return;

            currentSession.EndTime = DateTime.UtcNow;
            currentSession.Duration = (float)(currentSession.EndTime - currentSession.StartTime).TotalSeconds;
            currentSession.StepsCompleted = stepPerformances.Count;
            currentSession.TotalSteps = currentScenario.Steps.Count;

            // Calculate scores
            float totalPointsEarned = stepPerformances.Sum(p => p.PointsEarned);
            float maxPossiblePoints = currentScenario.Steps.Sum(s => s.Points);
            currentSession.FinalScore = maxPossiblePoints > 0 ? totalPointsEarned / maxPossiblePoints : 0f;

            currentSession.Accuracy = stepPerformances.Count > 0 ?
                stepPerformances.Average(p => p.Accuracy) : 0f;

            currentSession.AvgStepTime = stepPerformances.Count > 0 ?
                stepPerformances.Average(p => p.CompletionTime) : 0f;

            // Determine pass/fail
            currentSession.Passed = currentSession.FinalScore >= passingScore;

            if (currentSession.Passed)
            {
                completedSessions++;
                if (currentSession.FinalScore >= excellentScore)
                {
                    currentSession.Rating = PerformanceRating.Excellent;
                    currentSession.CertificationEarned = currentScenario.RequiresSafetyCertification;
                }
                else
                {
                    currentSession.Rating = PerformanceRating.Good;
                }
            }
            else
            {
                failedSessions++;
                currentSession.Rating = PerformanceRating.NeedsImprovement;
            }

            // Update statistics
            avgSessionScore = ((avgSessionScore * (completedSessions + failedSessions - 1)) + currentSession.FinalScore) /
                             (completedSessions + failedSessions);

            sessionActive = false;

            OnSessionCompleted?.Invoke(currentSession);

            Debug.Log($"[Training] Session completed: Score {currentSession.FinalScore:P1}, " +
                     $"Passed: {currentSession.Passed}, Rating: {currentSession.Rating}");
        }

        /// <summary>
        /// Fail current session
        /// </summary>
        private void FailSession(string reason)
        {
            if (!sessionActive) return;

            currentSession.EndTime = DateTime.UtcNow;
            currentSession.Duration = (float)(currentSession.EndTime - currentSession.StartTime).TotalSeconds;
            currentSession.Passed = false;
            currentSession.Rating = PerformanceRating.NeedsImprovement;
            currentSession.FailureReason = reason;

            failedSessions++;
            sessionActive = false;

            OnSessionCompleted?.Invoke(currentSession);

            Debug.LogError($"[Training] Session failed: {reason}");
        }

        /// <summary>
        /// Get available scenarios
        /// </summary>
        public List<TrainingScenario> GetAvailableScenarios()
        {
            return new List<TrainingScenario>(scenarios.Values);
        }

        /// <summary>
        /// Get operator progress
        /// </summary>
        public OperatorProgress GetProgress(string operatorIdOverride = null)
        {
            string opId = operatorIdOverride ?? operatorId;

            return new OperatorProgress
            {
                OperatorId = opId,
                TotalSessions = totalSessions,
                CompletedSessions = completedSessions,
                FailedSessions = failedSessions,
                AverageScore = avgSessionScore,
                CompletionRate = totalSessions > 0 ? (float)completedSessions / totalSessions : 0f,
                CertificationsEarned = new List<string>() // Would track from completed sessions
            };
        }

        /// <summary>
        /// Get training statistics
        /// </summary>
        public TrainingStatistics GetStatistics()
        {
            return new TrainingStatistics
            {
                TotalSessions = totalSessions,
                CompletedSessions = completedSessions,
                FailedSessions = failedSessions,
                AverageScore = avgSessionScore,
                CompletionRate = totalSessions > 0 ? (float)completedSessions / totalSessions : 0f,
                SessionActive = sessionActive,
                CurrentScenarioId = sessionActive ? currentScenario?.ScenarioId : null,
                CurrentStep = sessionActive ? currentStepIndex + 1 : 0,
                TotalSteps = sessionActive ? currentScenario?.Steps.Count ?? 0 : 0
            };
        }

        // UI helper methods
        private void ShowInstruction(TrainingStep step)
        {
            // Implementation would update UI elements
            Debug.Log($"[Training] Instruction: {step.Instruction}");
        }

        private void ShowFeedback(TrainingFeedback feedback)
        {
            // Implementation would update UI elements
            Debug.Log($"[Training] Feedback: {feedback.Message} (Rating: {feedback.Rating})");
        }

        #region Public Properties

        public bool IsSessionActive => sessionActive;
        public string CurrentScenarioId => currentScenario?.ScenarioId;
        public int CurrentStepIndex => currentStepIndex;
        public float CurrentSessionScore => currentSession?.FinalScore ?? 0f;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Training scenario definition
    /// </summary>
    [Serializable]
    public class TrainingScenario
    {
        public string ScenarioId;
        public string Title;
        public string Description;
        public TrainingDifficulty Difficulty;
        public float EstimatedDuration;
        public bool RequiresSafetyCertification;
        public List<TrainingStep> Steps;
    }

    /// <summary>
    /// Individual training step
    /// </summary>
    [Serializable]
    public class TrainingStep
    {
        public string StepId;
        public string Title;
        public string Instruction;
        public string ExpectedAction;
        public float TimeLimit;
        public float Points;
        public bool IsCritical; // Failure means session fails
    }

    /// <summary>
    /// Training session record
    /// </summary>
    [Serializable]
    public class TrainingSession
    {
        public string SessionId;
        public string OperatorId;
        public string ScenarioId;
        public DateTime StartTime;
        public DateTime EndTime;
        public float Duration;
        public TrainingDifficulty Difficulty;
        public int AttemptNumber;
        public bool GuidedMode;
        public int StepsCompleted;
        public int TotalSteps;
        public float FinalScore;
        public float Accuracy;
        public float AvgStepTime;
        public bool Passed;
        public PerformanceRating Rating;
        public bool CertificationEarned;
        public string FailureReason;
    }

    /// <summary>
    /// Step performance metrics
    /// </summary>
    [Serializable]
    public struct StepPerformance
    {
        public string StepId;
        public int StepIndex;
        public string ActionTaken;
        public bool IsCorrect;
        public bool TimedOut;
        public float CompletionTime;
        public float TimeLimit;
        public float PointsEarned;
        public float MaxPoints;
        public float Accuracy;
        public Dictionary<string, float> Metrics;
    }

    /// <summary>
    /// Training feedback
    /// </summary>
    [Serializable]
    public struct TrainingFeedback
    {
        public string StepTitle;
        public bool IsCorrect;
        public float CompletionTime;
        public float ExpectedTime;
        public PerformanceRating Rating;
        public string Message;
        public List<string> Tips;
    }

    /// <summary>
    /// Operator progress tracking
    /// </summary>
    [Serializable]
    public struct OperatorProgress
    {
        public string OperatorId;
        public int TotalSessions;
        public int CompletedSessions;
        public int FailedSessions;
        public float AverageScore;
        public float CompletionRate;
        public List<string> CertificationsEarned;
    }

    /// <summary>
    /// Training statistics
    /// </summary>
    [Serializable]
    public struct TrainingStatistics
    {
        public int TotalSessions;
        public int CompletedSessions;
        public int FailedSessions;
        public float AverageScore;
        public float CompletionRate;
        public bool SessionActive;
        public string CurrentScenarioId;
        public int CurrentStep;
        public int TotalSteps;
    }

    /// <summary>
    /// Training difficulty levels
    /// </summary>
    public enum TrainingDifficulty
    {
        Beginner,
        Intermediate,
        Advanced,
        Expert
    }

    /// <summary>
    /// Performance rating levels
    /// </summary>
    public enum PerformanceRating
    {
        NeedsImprovement,
        Acceptable,
        Good,
        Excellent
    }

    #endregion
}
