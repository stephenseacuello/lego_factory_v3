using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using CNCScada.Machines;
using CNCScada.DigitalTwin;
using CNCScada.Connection;
using CNCScada.Sensors;

namespace CNCScada.Automation
{
    /// <summary>
    /// Automation controller for coordinating CNC machines and robot arms.
    /// Manages workflows, pick-and-place sequences, and machine-robot coordination.
    /// </summary>
    public class AutomationController : MonoBehaviour
    {
        [Header("Configuration")]
        public string cellId = "cell-001";
        public AutomationMode mode = AutomationMode.Manual;

        [Header("Machine References")]
        public BantamCNCController bantamCNC;
        public XArmLite6Controller xArmLite6;
        public NiryoNed2Controller niryoNed2;

        [Header("Workflow Settings")]
        public float sequenceDelay = 0.5f;
        public float safetyCheckInterval = 0.1f;
        public bool enableCollisionAvoidance = true;

        [Header("Positions")]
        public Vector3 partPickupPosition = new Vector3(0.4f, 0, 0.3f);
        public Vector3 partDropoffPosition = new Vector3(-0.4f, 0, 0.3f);
        public Vector3 cncLoadPosition = new Vector3(0, 0.36f, -0.3f);
        public Vector3 cncUnloadPosition = new Vector3(0.15f, 0.36f, -0.3f);

        [Header("Status")]
        [SerializeField] private CellStatus cellStatus = CellStatus.Idle;
        [SerializeField] private string currentWorkflow = "";
        [SerializeField] private int completedParts = 0;
        [SerializeField] private int failedParts = 0;

        // Events
        public event Action<CellStatus> OnStatusChanged;
        public event Action<WorkflowEvent> OnWorkflowEvent;
        public event Action<int> OnPartCompleted;
        public event Action<string> OnError;

        // Internal state
        private Queue<AutomationTask> taskQueue = new Queue<AutomationTask>();
        private AutomationTask currentTask;
        private Coroutine workflowCoroutine;
        private bool isEmergencyStopped = false;
        private Dictionary<string, Workflow> workflows = new Dictionary<string, Workflow>();

        // Singleton
        public static AutomationController Instance { get; private set; }

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
            }

            InitializeWorkflows();
        }

        private void Start()
        {
            FindMachines();
            SetStatus(CellStatus.Idle);
        }

        private void Update()
        {
            // Process task queue in automatic mode
            if (mode == AutomationMode.Automatic && !isEmergencyStopped)
            {
                if (currentTask == null && taskQueue.Count > 0)
                {
                    currentTask = taskQueue.Dequeue();
                    StartTask(currentTask);
                }
            }

            // Safety monitoring
            if (enableCollisionAvoidance)
            {
                CheckCollisionRisks();
            }
        }

        private void FindMachines()
        {
            if (bantamCNC == null)
            {
                bantamCNC = FindObjectOfType<BantamCNCController>();
            }
            if (xArmLite6 == null)
            {
                xArmLite6 = FindObjectOfType<XArmLite6Controller>();
            }
            if (niryoNed2 == null)
            {
                niryoNed2 = FindObjectOfType<NiryoNed2Controller>();
            }

            Debug.Log($"[Automation] Found machines - CNC: {bantamCNC != null}, xArm: {xArmLite6 != null}, Niryo: {niryoNed2 != null}");
        }

        // =========================================================================
        // Workflow Management
        // =========================================================================

        private void InitializeWorkflows()
        {
            // Define standard workflows
            workflows["pick_and_place"] = new Workflow
            {
                name = "Pick and Place",
                description = "Pick part from bin and place in fixture",
                steps = new List<WorkflowStep>
                {
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "xarm", target = "pickup_approach" },
                    new WorkflowStep { action = StepAction.OpenGripper, robotId = "xarm" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "xarm", target = "pickup" },
                    new WorkflowStep { action = StepAction.CloseGripper, robotId = "xarm" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "xarm", target = "pickup_approach" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "xarm", target = "place_approach" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "xarm", target = "place" },
                    new WorkflowStep { action = StepAction.OpenGripper, robotId = "xarm" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "xarm", target = "home" }
                }
            };

            workflows["cnc_cycle"] = new Workflow
            {
                name = "CNC Machining Cycle",
                description = "Complete CNC machining cycle with robot loading",
                steps = new List<WorkflowStep>
                {
                    // Load part
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "xarm", target = "bin_pickup" },
                    new WorkflowStep { action = StepAction.CloseGripper, robotId = "xarm" },
                    new WorkflowStep { action = StepAction.WaitForCNC, cncCondition = "idle" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "xarm", target = "cnc_load" },
                    new WorkflowStep { action = StepAction.OpenGripper, robotId = "xarm" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "xarm", target = "safe" },
                    // Run CNC
                    new WorkflowStep { action = StepAction.RunCNCProgram, program = "part001.nc" },
                    new WorkflowStep { action = StepAction.WaitForCNC, cncCondition = "complete" },
                    // Unload part
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "niryo", target = "cnc_unload" },
                    new WorkflowStep { action = StepAction.CloseGripper, robotId = "niryo" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "niryo", target = "bin_dropoff" },
                    new WorkflowStep { action = StepAction.OpenGripper, robotId = "niryo" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "niryo", target = "home" }
                }
            };

            workflows["dual_robot_handoff"] = new Workflow
            {
                name = "Dual Robot Handoff",
                description = "Transfer part between xArm and Niryo",
                steps = new List<WorkflowStep>
                {
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "xarm", target = "pickup" },
                    new WorkflowStep { action = StepAction.CloseGripper, robotId = "xarm" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "xarm", target = "handoff" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "niryo", target = "handoff_receive" },
                    new WorkflowStep { action = StepAction.CloseGripper, robotId = "niryo" },
                    new WorkflowStep { action = StepAction.OpenGripper, robotId = "xarm" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "xarm", target = "home" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "niryo", target = "dropoff" },
                    new WorkflowStep { action = StepAction.OpenGripper, robotId = "niryo" },
                    new WorkflowStep { action = StepAction.MoveRobot, robotId = "niryo", target = "home" }
                }
            };

            Debug.Log($"[Automation] Initialized {workflows.Count} workflows");
        }

        /// <summary>
        /// Start a predefined workflow
        /// </summary>
        public void StartWorkflow(string workflowName)
        {
            if (!workflows.TryGetValue(workflowName, out var workflow))
            {
                Debug.LogError($"[Automation] Workflow not found: {workflowName}");
                OnError?.Invoke($"Workflow not found: {workflowName}");
                return;
            }

            if (workflowCoroutine != null)
            {
                Debug.LogWarning("[Automation] Workflow already running, stopping current workflow");
                StopCoroutine(workflowCoroutine);
            }

            currentWorkflow = workflowName;
            SetStatus(CellStatus.Running);
            workflowCoroutine = StartCoroutine(ExecuteWorkflow(workflow));
        }

        /// <summary>
        /// Stop current workflow
        /// </summary>
        public void StopWorkflow()
        {
            if (workflowCoroutine != null)
            {
                StopCoroutine(workflowCoroutine);
                workflowCoroutine = null;
            }

            currentWorkflow = "";
            SetStatus(CellStatus.Stopped);

            // Move robots to safe positions
            xArmLite6?.MoveToHome();
            niryoNed2?.MoveToHome();
        }

        /// <summary>
        /// Emergency stop - immediate halt of all motion
        /// </summary>
        public void EmergencyStop()
        {
            isEmergencyStopped = true;
            StopWorkflow();
            SetStatus(CellStatus.EmergencyStop);

            // Send E-stop to all machines
            FlaskSocketIOClient.Instance?.EmergencyStop();

            Debug.LogWarning("[Automation] EMERGENCY STOP ACTIVATED");
            OnWorkflowEvent?.Invoke(new WorkflowEvent
            {
                eventType = WorkflowEventType.EmergencyStop,
                message = "Emergency stop activated",
                timestamp = DateTime.UtcNow
            });
        }

        /// <summary>
        /// Reset emergency stop state
        /// </summary>
        public void ResetEmergencyStop()
        {
            isEmergencyStopped = false;
            SetStatus(CellStatus.Idle);
            Debug.Log("[Automation] Emergency stop reset");
        }

        private IEnumerator ExecuteWorkflow(Workflow workflow)
        {
            OnWorkflowEvent?.Invoke(new WorkflowEvent
            {
                eventType = WorkflowEventType.WorkflowStarted,
                workflowName = workflow.name,
                message = $"Starting workflow: {workflow.name}",
                timestamp = DateTime.UtcNow
            });

            for (int i = 0; i < workflow.steps.Count; i++)
            {
                if (isEmergencyStopped)
                {
                    yield break;
                }

                var step = workflow.steps[i];

                OnWorkflowEvent?.Invoke(new WorkflowEvent
                {
                    eventType = WorkflowEventType.StepStarted,
                    workflowName = workflow.name,
                    stepIndex = i,
                    message = $"Step {i + 1}/{workflow.steps.Count}: {step.action}",
                    timestamp = DateTime.UtcNow
                });

                yield return ExecuteStep(step);

                yield return new WaitForSeconds(sequenceDelay);
            }

            completedParts++;
            OnPartCompleted?.Invoke(completedParts);

            OnWorkflowEvent?.Invoke(new WorkflowEvent
            {
                eventType = WorkflowEventType.WorkflowCompleted,
                workflowName = workflow.name,
                message = $"Workflow completed: {workflow.name}",
                timestamp = DateTime.UtcNow
            });

            currentWorkflow = "";
            SetStatus(CellStatus.Idle);
        }

        private IEnumerator ExecuteStep(WorkflowStep step)
        {
            switch (step.action)
            {
                case StepAction.MoveRobot:
                    yield return MoveRobotToPosition(step.robotId, step.target);
                    break;

                case StepAction.OpenGripper:
                    yield return OperateGripper(step.robotId, true);
                    break;

                case StepAction.CloseGripper:
                    yield return OperateGripper(step.robotId, false);
                    break;

                case StepAction.RunCNCProgram:
                    yield return RunCNCProgram(step.program);
                    break;

                case StepAction.WaitForCNC:
                    yield return WaitForCNCCondition(step.cncCondition);
                    break;

                case StepAction.Wait:
                    yield return new WaitForSeconds(step.waitTime);
                    break;

                case StepAction.SendGCode:
                    FlaskSocketIOClient.Instance?.SendGCode(step.gcode);
                    yield return new WaitForSeconds(0.1f);
                    break;

                case StepAction.CheckSensor:
                    yield return CheckSensorCondition(step.sensorId, step.sensorThreshold);
                    break;

                default:
                    Debug.LogWarning($"[Automation] Unknown step action: {step.action}");
                    break;
            }
        }

        private IEnumerator MoveRobotToPosition(string robotId, string targetName)
        {
            // Get target position from predefined positions
            Vector3 targetPos = GetNamedPosition(targetName);
            float[] jointAngles = null;

            if (robotId == "xarm" && xArmLite6 != null)
            {
                // Calculate inverse kinematics for target position
                // For now, use predefined joint angles for named positions
                jointAngles = GetPresetJointAngles(robotId, targetName);
                if (jointAngles != null)
                {
                    xArmLite6.SetTargetJointAngles(jointAngles);
                }

                // Wait for motion to complete
                yield return new WaitForSeconds(2f);
            }
            else if (robotId == "niryo" && niryoNed2 != null)
            {
                jointAngles = GetPresetJointAngles(robotId, targetName);
                if (jointAngles != null)
                {
                    niryoNed2.SetTargetJointAngles(jointAngles);
                }

                yield return new WaitForSeconds(2f);
            }
        }

        private IEnumerator OperateGripper(string robotId, bool open)
        {
            float opening = open ? 1f : 0f;

            if (robotId == "xarm" && xArmLite6 != null)
            {
                xArmLite6.SetGripperOpening(opening);
            }
            else if (robotId == "niryo" && niryoNed2 != null)
            {
                niryoNed2.SetGripperOpening(opening);
            }

            yield return new WaitForSeconds(0.5f);
        }

        private IEnumerator RunCNCProgram(string programName)
        {
            // Send command to run CNC program
            FlaskSocketIOClient.Instance?.SendGCode($"M98 P{programName}");

            yield return new WaitForSeconds(0.5f);
        }

        private IEnumerator WaitForCNCCondition(string condition)
        {
            float timeout = 300f; // 5 minute timeout
            float elapsed = 0f;

            while (elapsed < timeout && !isEmergencyStopped)
            {
                if (condition == "idle")
                {
                    if (bantamCNC != null && bantamCNC.Status == BantamCNCController.MachineStatus.Idle)
                    {
                        yield break;
                    }
                }
                else if (condition == "complete")
                {
                    if (bantamCNC != null && bantamCNC.Status == BantamCNCController.MachineStatus.Idle)
                    {
                        yield break;
                    }
                }

                yield return new WaitForSeconds(0.5f);
                elapsed += 0.5f;
            }

            Debug.LogWarning($"[Automation] Timeout waiting for CNC condition: {condition}");
        }

        private IEnumerator CheckSensorCondition(string sensorId, float threshold)
        {
            if (SensorSystem.Instance == null)
            {
                yield break;
            }

            var sensor = SensorSystem.Instance.GetSensor(sensorId);
            if (sensor == null)
            {
                Debug.LogWarning($"[Automation] Sensor not found: {sensorId}");
                yield break;
            }

            var reading = sensor.GetReading();
            if (reading.value > threshold)
            {
                Debug.LogWarning($"[Automation] Sensor threshold exceeded: {sensorId} = {reading.value} > {threshold}");
                // Could pause workflow or take corrective action
            }

            yield return null;
        }

        private Vector3 GetNamedPosition(string positionName)
        {
            return positionName switch
            {
                "pickup" => partPickupPosition,
                "pickup_approach" => partPickupPosition + Vector3.up * 0.1f,
                "dropoff" => partDropoffPosition,
                "place" => partDropoffPosition,
                "place_approach" => partDropoffPosition + Vector3.up * 0.1f,
                "cnc_load" => cncLoadPosition,
                "cnc_unload" => cncUnloadPosition,
                "handoff" => new Vector3(0, 0.3f, 0),
                "handoff_receive" => new Vector3(0.05f, 0.3f, 0),
                "safe" => new Vector3(0, 0.4f, 0.2f),
                "home" => Vector3.zero,
                _ => Vector3.zero
            };
        }

        private float[] GetPresetJointAngles(string robotId, string positionName)
        {
            // Predefined joint angles for common positions
            if (robotId == "xarm")
            {
                return positionName switch
                {
                    "home" => new float[] { 0, 0, 0, 0, 0, 0 },
                    "pickup" => new float[] { 45, -30, -60, 0, 90, 0 },
                    "pickup_approach" => new float[] { 45, -20, -50, 0, 70, 0 },
                    "cnc_load" => new float[] { 0, -40, -70, 0, 110, 0 },
                    "safe" => new float[] { 0, -45, -45, 0, 90, 0 },
                    "handoff" => new float[] { -90, -30, -60, 0, 90, 0 },
                    _ => new float[] { 0, 0, 0, 0, 0, 0 }
                };
            }
            else if (robotId == "niryo")
            {
                return positionName switch
                {
                    "home" => new float[] { 0, 0, 0, 0, 0, 0 },
                    "dropoff" => new float[] { -45, -20, 45, 0, 65, 0 },
                    "cnc_unload" => new float[] { 0, -30, 60, 0, 60, 0 },
                    "handoff_receive" => new float[] { 90, -20, 50, 0, 60, 0 },
                    "safe" => new float[] { 0, -30, 30, 0, 90, 0 },
                    _ => new float[] { 0, 0, 0, 0, 0, 0 }
                };
            }

            return null;
        }

        // =========================================================================
        // Task Queue Management
        // =========================================================================

        /// <summary>
        /// Add a task to the automation queue
        /// </summary>
        public void QueueTask(AutomationTask task)
        {
            taskQueue.Enqueue(task);
            Debug.Log($"[Automation] Task queued: {task.taskName} (queue size: {taskQueue.Count})");
        }

        /// <summary>
        /// Clear all queued tasks
        /// </summary>
        public void ClearTaskQueue()
        {
            taskQueue.Clear();
            Debug.Log("[Automation] Task queue cleared");
        }

        private void StartTask(AutomationTask task)
        {
            Debug.Log($"[Automation] Starting task: {task.taskName}");
            SetStatus(CellStatus.Running);

            if (!string.IsNullOrEmpty(task.workflowName))
            {
                StartWorkflow(task.workflowName);
            }
        }

        // =========================================================================
        // Safety and Monitoring
        // =========================================================================

        private void CheckCollisionRisks()
        {
            if (xArmLite6 == null || niryoNed2 == null) return;

            // Check end effector proximity
            Vector3 xArmEE = xArmLite6.transform.position; // Simplified - should use actual EE position
            Vector3 niryoEE = niryoNed2.transform.position;

            float distance = Vector3.Distance(xArmEE, niryoEE);

            if (distance < 0.1f) // 10cm minimum clearance
            {
                Debug.LogWarning($"[Automation] Collision risk! Robot clearance: {distance:F3}m");
                OnWorkflowEvent?.Invoke(new WorkflowEvent
                {
                    eventType = WorkflowEventType.Warning,
                    message = $"Collision risk detected. Clearance: {distance:F3}m",
                    timestamp = DateTime.UtcNow
                });
            }
        }

        private void SetStatus(CellStatus status)
        {
            if (cellStatus != status)
            {
                cellStatus = status;
                OnStatusChanged?.Invoke(status);
                Debug.Log($"[Automation] Cell status: {status}");
            }
        }

        // =========================================================================
        // Public Interface
        // =========================================================================

        /// <summary>
        /// Run a single part cycle
        /// </summary>
        public void RunSingleCycle()
        {
            StartWorkflow("cnc_cycle");
        }

        /// <summary>
        /// Start continuous production mode
        /// </summary>
        public void StartContinuousProduction(int partCount = -1)
        {
            mode = AutomationMode.Automatic;

            for (int i = 0; i < (partCount < 0 ? 1000 : partCount); i++)
            {
                QueueTask(new AutomationTask
                {
                    taskName = $"Part_{i + 1}",
                    workflowName = "cnc_cycle",
                    priority = 1
                });
            }

            Debug.Log($"[Automation] Starting continuous production ({partCount} parts)");
        }

        /// <summary>
        /// Get available workflows
        /// </summary>
        public string[] GetAvailableWorkflows()
        {
            var names = new List<string>();
            foreach (var kvp in workflows)
            {
                names.Add(kvp.Key);
            }
            return names.ToArray();
        }

        // Properties
        public CellStatus Status => cellStatus;
        public string CurrentWorkflow => currentWorkflow;
        public int CompletedParts => completedParts;
        public int FailedParts => failedParts;
        public int QueuedTasks => taskQueue.Count;
        public bool IsEmergencyStopped => isEmergencyStopped;
    }

    // =========================================================================
    // Enums and Data Classes
    // =========================================================================

    public enum AutomationMode
    {
        Manual,
        SemiAutomatic,
        Automatic
    }

    public enum CellStatus
    {
        Idle,
        Running,
        Paused,
        Stopped,
        Error,
        EmergencyStop,
        Maintenance
    }

    public enum StepAction
    {
        MoveRobot,
        OpenGripper,
        CloseGripper,
        RunCNCProgram,
        WaitForCNC,
        Wait,
        SendGCode,
        CheckSensor,
        Custom
    }

    public enum WorkflowEventType
    {
        WorkflowStarted,
        WorkflowCompleted,
        WorkflowFailed,
        StepStarted,
        StepCompleted,
        StepFailed,
        Warning,
        Error,
        EmergencyStop
    }

    [Serializable]
    public class Workflow
    {
        public string name;
        public string description;
        public List<WorkflowStep> steps;
    }

    [Serializable]
    public class WorkflowStep
    {
        public StepAction action;
        public string robotId;
        public string target;
        public string program;
        public string gcode;
        public string cncCondition;
        public string sensorId;
        public float sensorThreshold;
        public float waitTime;
        public Dictionary<string, object> customParams;
    }

    [Serializable]
    public class AutomationTask
    {
        public string taskName;
        public string workflowName;
        public int priority;
        public DateTime scheduledTime;
        public Dictionary<string, object> parameters;
    }

    [Serializable]
    public class WorkflowEvent
    {
        public WorkflowEventType eventType;
        public string workflowName;
        public int stepIndex;
        public string message;
        public DateTime timestamp;
    }
}
