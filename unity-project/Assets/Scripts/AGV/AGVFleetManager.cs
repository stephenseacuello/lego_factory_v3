using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.AI;

namespace CNCDigitalTwin.AGV
{
    /// <summary>
    /// AGV/AMR Fleet Manager for autonomous mobile robot coordination
    /// Handles fleet management, task assignment, path planning, and traffic control
    /// </summary>
    public class AGVFleetManager : MonoBehaviour
    {
        public static AGVFleetManager Instance { get; private set; }

        [Header("Fleet Configuration")]
        [SerializeField] private int maxFleetSize = 20;
        [SerializeField] private float taskAssignmentInterval = 1.0f;
        [SerializeField] private float statusUpdateInterval = 0.5f;

        [Header("Traffic Control")]
        [SerializeField] private float collisionAvoidanceDistance = 2.0f;
        [SerializeField] private float intersectionClearTime = 5.0f;
        [SerializeField] private bool enableTrafficControl = true;

        [Header("Charging")]
        [SerializeField] private float lowBatteryThreshold = 20f;
        [SerializeField] private float criticalBatteryThreshold = 10f;
        [SerializeField] private float chargeStartThreshold = 30f;

        // Fleet registry
        private Dictionary<string, AGVUnit> fleet = new Dictionary<string, AGVUnit>();
        private Dictionary<string, ChargingStation> chargingStations = new Dictionary<string, ChargingStation>();
        private Dictionary<string, AGVZone> zones = new Dictionary<string, AGVZone>();
        private Dictionary<string, Waypoint> waypoints = new Dictionary<string, Waypoint>();

        // Task management
        private Queue<TransportTask> taskQueue = new Queue<TransportTask>();
        private Dictionary<string, TransportTask> activeTasks = new Dictionary<string, TransportTask>();
        private List<TransportTask> completedTasks = new List<TransportTask>();

        // Traffic control
        private Dictionary<string, IntersectionLock> intersectionLocks = new Dictionary<string, IntersectionLock>();
        private List<TrafficIncident> trafficIncidents = new List<TrafficIncident>();

        // Events
        public event Action<AGVUnit> OnAGVRegistered;
        public event Action<AGVUnit> OnAGVStatusChanged;
        public event Action<TransportTask> OnTaskCreated;
        public event Action<TransportTask> OnTaskAssigned;
        public event Action<TransportTask> OnTaskCompleted;
        public event Action<AGVUnit, AGVAlert> OnAGVAlert;
        public event Action<TrafficIncident> OnTrafficIncident;

        private Coroutine taskAssignmentCoroutine;
        private Coroutine statusUpdateCoroutine;

        void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
            }
            else
            {
                Destroy(gameObject);
            }
        }

        void Start()
        {
            InitializeDefaultZones();
            taskAssignmentCoroutine = StartCoroutine(TaskAssignmentLoop());
            statusUpdateCoroutine = StartCoroutine(StatusUpdateLoop());
        }

        void OnDestroy()
        {
            if (taskAssignmentCoroutine != null)
                StopCoroutine(taskAssignmentCoroutine);
            if (statusUpdateCoroutine != null)
                StopCoroutine(statusUpdateCoroutine);
        }

        #region Initialization

        private void InitializeDefaultZones()
        {
            // Production zone
            CreateZone(new AGVZoneConfig
            {
                ZoneId = "PRODUCTION",
                Name = "Production Area",
                ZoneType = ZoneType.Production,
                MaxAGVs = 5,
                SpeedLimit = 1.5f
            });

            // Loading dock
            CreateZone(new AGVZoneConfig
            {
                ZoneId = "LOADING_DOCK",
                Name = "Loading Dock",
                ZoneType = ZoneType.LoadingDock,
                MaxAGVs = 3,
                SpeedLimit = 1.0f
            });

            // Storage area
            CreateZone(new AGVZoneConfig
            {
                ZoneId = "STORAGE",
                Name = "Storage Area",
                ZoneType = ZoneType.Storage,
                MaxAGVs = 8,
                SpeedLimit = 2.0f
            });

            // Charging area
            CreateZone(new AGVZoneConfig
            {
                ZoneId = "CHARGING",
                Name = "Charging Station Area",
                ZoneType = ZoneType.Charging,
                MaxAGVs = 4,
                SpeedLimit = 0.5f
            });

            // Initialize charging stations
            CreateChargingStation(new ChargingStationConfig
            {
                StationId = "CHARGER_01",
                Name = "Charger 1",
                Position = new Vector3(0, 0, -10),
                ChargingRate = 20f, // % per minute
                MaxVoltage = 48f,
                MaxCurrent = 30f
            });

            CreateChargingStation(new ChargingStationConfig
            {
                StationId = "CHARGER_02",
                Name = "Charger 2",
                Position = new Vector3(3, 0, -10),
                ChargingRate = 20f,
                MaxVoltage = 48f,
                MaxCurrent = 30f
            });
        }

        #endregion

        #region AGV Management

        public AGVUnit RegisterAGV(AGVConfig config)
        {
            if (fleet.Count >= maxFleetSize)
            {
                Debug.LogWarning("[AGV] Fleet at maximum capacity");
                return null;
            }

            var agv = new AGVUnit
            {
                AGVId = config.AGVId ?? Guid.NewGuid().ToString(),
                Name = config.Name,
                Type = config.Type,
                Model = config.Model,
                MaxPayload = config.MaxPayload,
                MaxSpeed = config.MaxSpeed,
                BatteryCapacity = config.BatteryCapacity,
                BatteryLevel = config.InitialBattery,
                Position = config.StartPosition,
                Rotation = Quaternion.identity,
                Status = AGVStatus.Idle,
                NavigationMode = config.NavigationMode,
                Dimensions = config.Dimensions,
                RegistrationTime = DateTime.UtcNow
            };

            fleet[agv.AGVId] = agv;

            // Create Unity GameObject if needed
            if (config.CreateGameObject)
            {
                CreateAGVGameObject(agv);
            }

            OnAGVRegistered?.Invoke(agv);
            Debug.Log($"[AGV] Registered AGV: {agv.Name} ({agv.Type})");

            return agv;
        }

        private void CreateAGVGameObject(AGVUnit agv)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = $"AGV_{agv.Name}";
            go.transform.position = agv.Position;
            go.transform.localScale = agv.Dimensions;

            // Add NavMeshAgent for pathfinding
            var navAgent = go.AddComponent<NavMeshAgent>();
            navAgent.speed = agv.MaxSpeed;
            navAgent.angularSpeed = 120f;
            navAgent.acceleration = 2f;
            navAgent.stoppingDistance = 0.5f;
            navAgent.radius = Mathf.Max(agv.Dimensions.x, agv.Dimensions.z) / 2f;

            agv.GameObject = go;
            agv.NavAgent = navAgent;
        }

        public void UnregisterAGV(string agvId)
        {
            if (fleet.TryGetValue(agvId, out var agv))
            {
                // Cancel any active tasks
                if (activeTasks.TryGetValue(agvId, out var task))
                {
                    CancelTask(task.TaskId, "AGV unregistered");
                }

                // Destroy GameObject
                if (agv.GameObject != null)
                {
                    Destroy(agv.GameObject);
                }

                fleet.Remove(agvId);
                Debug.Log($"[AGV] Unregistered AGV: {agv.Name}");
            }
        }

        public AGVUnit GetAGV(string agvId)
        {
            return fleet.TryGetValue(agvId, out var agv) ? agv : null;
        }

        public List<AGVUnit> GetAvailableAGVs(AGVType? type = null, float? minPayload = null)
        {
            var query = fleet.Values.Where(a =>
                a.Status == AGVStatus.Idle &&
                a.BatteryLevel > lowBatteryThreshold);

            if (type.HasValue)
                query = query.Where(a => a.Type == type.Value);

            if (minPayload.HasValue)
                query = query.Where(a => a.MaxPayload >= minPayload.Value);

            return query.OrderByDescending(a => a.BatteryLevel).ToList();
        }

        public void SetAGVStatus(string agvId, AGVStatus newStatus)
        {
            if (fleet.TryGetValue(agvId, out var agv))
            {
                var oldStatus = agv.Status;
                agv.Status = newStatus;

                if (oldStatus != newStatus)
                {
                    OnAGVStatusChanged?.Invoke(agv);
                }
            }
        }

        #endregion

        #region Zone Management

        public AGVZone CreateZone(AGVZoneConfig config)
        {
            var zone = new AGVZone
            {
                ZoneId = config.ZoneId,
                Name = config.Name,
                ZoneType = config.ZoneType,
                Bounds = config.Bounds,
                MaxAGVs = config.MaxAGVs,
                SpeedLimit = config.SpeedLimit,
                RequiresPermission = config.RequiresPermission,
                CurrentAGVs = new List<string>()
            };

            zones[zone.ZoneId] = zone;
            Debug.Log($"[AGV] Created zone: {config.Name}");
            return zone;
        }

        public bool RequestZoneEntry(string agvId, string zoneId)
        {
            if (!zones.TryGetValue(zoneId, out var zone))
                return false;

            if (zone.CurrentAGVs.Count >= zone.MaxAGVs)
            {
                Debug.Log($"[AGV] Zone {zone.Name} at capacity");
                return false;
            }

            if (zone.RequiresPermission)
            {
                // Would check permissions here
            }

            zone.CurrentAGVs.Add(agvId);

            if (fleet.TryGetValue(agvId, out var agv))
            {
                agv.CurrentZone = zoneId;

                // Apply speed limit
                if (agv.NavAgent != null && zone.SpeedLimit > 0)
                {
                    agv.NavAgent.speed = Mathf.Min(agv.MaxSpeed, zone.SpeedLimit);
                }
            }

            return true;
        }

        public void ExitZone(string agvId, string zoneId)
        {
            if (zones.TryGetValue(zoneId, out var zone))
            {
                zone.CurrentAGVs.Remove(agvId);
            }

            if (fleet.TryGetValue(agvId, out var agv) && agv.CurrentZone == zoneId)
            {
                agv.CurrentZone = null;

                // Restore speed
                if (agv.NavAgent != null)
                {
                    agv.NavAgent.speed = agv.MaxSpeed;
                }
            }
        }

        #endregion

        #region Waypoint Management

        public Waypoint CreateWaypoint(WaypointConfig config)
        {
            var waypoint = new Waypoint
            {
                WaypointId = config.WaypointId,
                Name = config.Name,
                Position = config.Position,
                WaypointType = config.WaypointType,
                ZoneId = config.ZoneId,
                ConnectedWaypoints = config.ConnectedWaypoints ?? new List<string>(),
                AllowedAGVTypes = config.AllowedAGVTypes ?? new List<AGVType>(),
                DockingAngle = config.DockingAngle,
                WaitTime = config.WaitTime
            };

            waypoints[waypoint.WaypointId] = waypoint;
            return waypoint;
        }

        public Waypoint GetWaypoint(string waypointId)
        {
            return waypoints.TryGetValue(waypointId, out var wp) ? wp : null;
        }

        public List<Waypoint> GetWaypointsByType(WaypointType type)
        {
            return waypoints.Values.Where(w => w.WaypointType == type).ToList();
        }

        #endregion

        #region Charging Station Management

        public ChargingStation CreateChargingStation(ChargingStationConfig config)
        {
            var station = new ChargingStation
            {
                StationId = config.StationId,
                Name = config.Name,
                Position = config.Position,
                ChargingRate = config.ChargingRate,
                MaxVoltage = config.MaxVoltage,
                MaxCurrent = config.MaxCurrent,
                Status = ChargingStationStatus.Available
            };

            chargingStations[station.StationId] = station;
            Debug.Log($"[AGV] Created charging station: {config.Name}");
            return station;
        }

        public ChargingStation FindAvailableCharger()
        {
            return chargingStations.Values
                .FirstOrDefault(s => s.Status == ChargingStationStatus.Available);
        }

        public bool AssignToCharger(string agvId, string stationId)
        {
            if (!fleet.TryGetValue(agvId, out var agv) ||
                !chargingStations.TryGetValue(stationId, out var station))
            {
                return false;
            }

            if (station.Status != ChargingStationStatus.Available)
            {
                return false;
            }

            station.Status = ChargingStationStatus.Occupied;
            station.CurrentAGV = agvId;
            station.ChargingStartTime = DateTime.UtcNow;

            agv.Status = AGVStatus.Charging;
            agv.ChargingStationId = stationId;

            StartCoroutine(ChargingProcess(agv, station));
            return true;
        }

        private IEnumerator ChargingProcess(AGVUnit agv, ChargingStation station)
        {
            while (agv.BatteryLevel < 100f && agv.Status == AGVStatus.Charging)
            {
                yield return new WaitForSeconds(1f);

                // Charge battery
                float chargeAmount = station.ChargingRate / 60f; // Per second
                agv.BatteryLevel = Mathf.Min(100f, agv.BatteryLevel + chargeAmount);

                // Update station
                station.EnergyDelivered += chargeAmount * agv.BatteryCapacity / 100f;
            }

            // Charging complete
            if (agv.BatteryLevel >= 100f)
            {
                agv.Status = AGVStatus.Idle;
                agv.ChargingStationId = null;
                station.Status = ChargingStationStatus.Available;
                station.CurrentAGV = null;

                Debug.Log($"[AGV] {agv.Name} fully charged");
            }
        }

        public void StopCharging(string agvId)
        {
            if (!fleet.TryGetValue(agvId, out var agv))
                return;

            if (!string.IsNullOrEmpty(agv.ChargingStationId) &&
                chargingStations.TryGetValue(agv.ChargingStationId, out var station))
            {
                station.Status = ChargingStationStatus.Available;
                station.CurrentAGV = null;
            }

            agv.Status = AGVStatus.Idle;
            agv.ChargingStationId = null;
        }

        #endregion

        #region Task Management

        public TransportTask CreateTask(TransportTaskConfig config)
        {
            var task = new TransportTask
            {
                TaskId = config.TaskId ?? Guid.NewGuid().ToString(),
                TaskType = config.TaskType,
                Priority = config.Priority,
                SourceLocation = config.SourceLocation,
                DestinationLocation = config.DestinationLocation,
                Payload = config.Payload,
                RequiredAGVType = config.RequiredAGVType,
                MinPayloadCapacity = config.MinPayloadCapacity,
                Deadline = config.Deadline,
                Status = TaskStatus.Pending,
                CreatedAt = DateTime.UtcNow
            };

            taskQueue.Enqueue(task);
            OnTaskCreated?.Invoke(task);

            Debug.Log($"[AGV] Task created: {task.TaskType} from {task.SourceLocation} to {task.DestinationLocation}");
            return task;
        }

        private IEnumerator TaskAssignmentLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(taskAssignmentInterval);
                ProcessTaskQueue();
                CheckBatteryLevels();
            }
        }

        private void ProcessTaskQueue()
        {
            if (taskQueue.Count == 0) return;

            // Get pending tasks sorted by priority
            var pendingTasks = taskQueue.ToList()
                .OrderByDescending(t => t.Priority)
                .ThenBy(t => t.CreatedAt)
                .ToList();

            taskQueue.Clear();

            foreach (var task in pendingTasks)
            {
                // Find suitable AGV
                var agv = FindBestAGVForTask(task);

                if (agv != null)
                {
                    AssignTaskToAGV(task, agv);
                }
                else
                {
                    // Re-queue for later
                    taskQueue.Enqueue(task);
                }
            }
        }

        private AGVUnit FindBestAGVForTask(TransportTask task)
        {
            var candidates = GetAvailableAGVs(task.RequiredAGVType, task.MinPayloadCapacity);

            if (candidates.Count == 0) return null;

            // Score candidates based on distance and battery
            AGVUnit bestAGV = null;
            float bestScore = float.MinValue;

            foreach (var agv in candidates)
            {
                float distance = Vector3.Distance(agv.Position, GetPositionFromLocation(task.SourceLocation));
                float batteryScore = agv.BatteryLevel;
                float distanceScore = 100f - Mathf.Min(distance, 100f);

                float score = batteryScore * 0.4f + distanceScore * 0.6f;

                if (score > bestScore)
                {
                    bestScore = score;
                    bestAGV = agv;
                }
            }

            return bestAGV;
        }

        private void AssignTaskToAGV(TransportTask task, AGVUnit agv)
        {
            task.AssignedAGV = agv.AGVId;
            task.Status = TaskStatus.Assigned;
            task.AssignedAt = DateTime.UtcNow;

            agv.Status = AGVStatus.EnRoute;
            agv.CurrentTask = task.TaskId;

            activeTasks[agv.AGVId] = task;

            OnTaskAssigned?.Invoke(task);
            Debug.Log($"[AGV] Task {task.TaskId} assigned to {agv.Name}");

            // Start navigation
            StartCoroutine(ExecuteTask(agv, task));
        }

        private IEnumerator ExecuteTask(AGVUnit agv, TransportTask task)
        {
            // Navigate to source
            task.Status = TaskStatus.EnRouteToSource;
            Vector3 sourcePos = GetPositionFromLocation(task.SourceLocation);

            yield return NavigateToPosition(agv, sourcePos);

            if (agv.Status == AGVStatus.Error)
            {
                task.Status = TaskStatus.Failed;
                task.ErrorMessage = "Navigation error to source";
                yield break;
            }

            // Pickup
            task.Status = TaskStatus.Pickup;
            agv.Status = AGVStatus.Loading;
            yield return new WaitForSeconds(task.Payload?.LoadTime ?? 5f);

            agv.CurrentPayload = task.Payload;

            // Navigate to destination
            task.Status = TaskStatus.EnRouteToDestination;
            agv.Status = AGVStatus.EnRoute;
            Vector3 destPos = GetPositionFromLocation(task.DestinationLocation);

            yield return NavigateToPosition(agv, destPos);

            if (agv.Status == AGVStatus.Error)
            {
                task.Status = TaskStatus.Failed;
                task.ErrorMessage = "Navigation error to destination";
                yield break;
            }

            // Dropoff
            task.Status = TaskStatus.Dropoff;
            agv.Status = AGVStatus.Unloading;
            yield return new WaitForSeconds(task.Payload?.UnloadTime ?? 5f);

            // Complete
            CompleteTask(task, agv);
        }

        private IEnumerator NavigateToPosition(AGVUnit agv, Vector3 targetPosition)
        {
            if (agv.NavAgent != null)
            {
                agv.NavAgent.SetDestination(targetPosition);

                while (agv.NavAgent.pathPending)
                {
                    yield return null;
                }

                if (agv.NavAgent.pathStatus == NavMeshPathStatus.PathInvalid)
                {
                    agv.Status = AGVStatus.Error;
                    RaiseAlert(agv, AGVAlertType.NavigationError, "Invalid path");
                    yield break;
                }

                while (agv.NavAgent.remainingDistance > agv.NavAgent.stoppingDistance)
                {
                    agv.Position = agv.NavAgent.transform.position;
                    agv.Rotation = agv.NavAgent.transform.rotation;

                    // Check for collisions with traffic control
                    if (enableTrafficControl)
                    {
                        yield return CheckTrafficControl(agv);
                    }

                    // Simulate battery drain
                    float drainRate = 0.001f * agv.NavAgent.speed; // Battery drain per frame
                    agv.BatteryLevel -= drainRate;

                    if (agv.BatteryLevel <= criticalBatteryThreshold)
                    {
                        agv.Status = AGVStatus.Error;
                        RaiseAlert(agv, AGVAlertType.CriticalBattery, "Critical battery level");
                        yield break;
                    }

                    yield return null;
                }
            }
            else
            {
                // Simple movement without NavMesh
                float speed = agv.MaxSpeed;
                while (Vector3.Distance(agv.Position, targetPosition) > 0.5f)
                {
                    Vector3 direction = (targetPosition - agv.Position).normalized;
                    agv.Position += direction * speed * Time.deltaTime;
                    agv.Rotation = Quaternion.LookRotation(direction);

                    agv.BatteryLevel -= 0.001f;
                    yield return null;
                }
            }
        }

        private IEnumerator CheckTrafficControl(AGVUnit agv)
        {
            // Check for nearby AGVs
            foreach (var other in fleet.Values)
            {
                if (other.AGVId == agv.AGVId || other.Status == AGVStatus.Idle)
                    continue;

                float distance = Vector3.Distance(agv.Position, other.Position);

                if (distance < collisionAvoidanceDistance)
                {
                    // Yield to higher priority or stop
                    if (other.Priority > agv.Priority ||
                        (other.Priority == agv.Priority && string.Compare(other.AGVId, agv.AGVId) < 0))
                    {
                        agv.Status = AGVStatus.Waiting;
                        if (agv.NavAgent != null)
                        {
                            agv.NavAgent.isStopped = true;
                        }

                        yield return new WaitForSeconds(1f);

                        if (agv.NavAgent != null)
                        {
                            agv.NavAgent.isStopped = false;
                        }
                        agv.Status = AGVStatus.EnRoute;
                    }
                }
            }
        }

        private void CompleteTask(TransportTask task, AGVUnit agv)
        {
            task.Status = TaskStatus.Completed;
            task.CompletedAt = DateTime.UtcNow;
            task.ActualDuration = (float)(task.CompletedAt.Value - task.AssignedAt.Value).TotalSeconds;

            agv.Status = AGVStatus.Idle;
            agv.CurrentTask = null;
            agv.CurrentPayload = null;
            agv.CompletedTasks++;
            agv.TotalDistanceTraveled += task.ActualDistance;

            activeTasks.Remove(agv.AGVId);
            completedTasks.Add(task);

            OnTaskCompleted?.Invoke(task);
            Debug.Log($"[AGV] Task {task.TaskId} completed by {agv.Name}");
        }

        public void CancelTask(string taskId, string reason)
        {
            var task = activeTasks.Values.FirstOrDefault(t => t.TaskId == taskId);
            if (task == null)
            {
                // Check pending queue
                var pendingList = taskQueue.ToList();
                task = pendingList.FirstOrDefault(t => t.TaskId == taskId);
                if (task != null)
                {
                    pendingList.Remove(task);
                    taskQueue.Clear();
                    foreach (var t in pendingList)
                        taskQueue.Enqueue(t);
                }
            }

            if (task != null)
            {
                task.Status = TaskStatus.Cancelled;
                task.ErrorMessage = reason;

                if (!string.IsNullOrEmpty(task.AssignedAGV) && fleet.TryGetValue(task.AssignedAGV, out var agv))
                {
                    agv.Status = AGVStatus.Idle;
                    agv.CurrentTask = null;
                    activeTasks.Remove(agv.AGVId);
                }

                Debug.Log($"[AGV] Task {taskId} cancelled: {reason}");
            }
        }

        private Vector3 GetPositionFromLocation(string location)
        {
            // Check waypoints
            if (waypoints.TryGetValue(location, out var waypoint))
            {
                return waypoint.Position;
            }

            // Check zones
            if (zones.TryGetValue(location, out var zone))
            {
                return zone.Bounds.center;
            }

            // Try to parse as position
            var parts = location.Split(',');
            if (parts.Length == 3 &&
                float.TryParse(parts[0], out float x) &&
                float.TryParse(parts[1], out float y) &&
                float.TryParse(parts[2], out float z))
            {
                return new Vector3(x, y, z);
            }

            return Vector3.zero;
        }

        #endregion

        #region Battery Management

        private void CheckBatteryLevels()
        {
            foreach (var agv in fleet.Values)
            {
                if (agv.Status == AGVStatus.Charging)
                    continue;

                if (agv.BatteryLevel <= criticalBatteryThreshold)
                {
                    RaiseAlert(agv, AGVAlertType.CriticalBattery, $"Critical battery: {agv.BatteryLevel:F1}%");

                    // Force stop and send to charger
                    if (agv.Status != AGVStatus.Error)
                    {
                        SendToCharge(agv.AGVId, true);
                    }
                }
                else if (agv.BatteryLevel <= lowBatteryThreshold)
                {
                    RaiseAlert(agv, AGVAlertType.LowBattery, $"Low battery: {agv.BatteryLevel:F1}%");

                    // Schedule charging after current task
                    agv.NeedsCharging = true;
                }
                else if (agv.BatteryLevel <= chargeStartThreshold && agv.Status == AGVStatus.Idle)
                {
                    // Send to charge if idle
                    SendToCharge(agv.AGVId, false);
                }
            }
        }

        public bool SendToCharge(string agvId, bool urgent = false)
        {
            if (!fleet.TryGetValue(agvId, out var agv))
                return false;

            // Find nearest available charger
            var charger = FindAvailableCharger();
            if (charger == null)
            {
                Debug.LogWarning($"[AGV] No charger available for {agv.Name}");
                return false;
            }

            // Cancel current task if urgent
            if (urgent && !string.IsNullOrEmpty(agv.CurrentTask))
            {
                CancelTask(agv.CurrentTask, "Emergency charging required");
            }

            // Navigate to charger
            StartCoroutine(NavigateToCharger(agv, charger));
            return true;
        }

        private IEnumerator NavigateToCharger(AGVUnit agv, ChargingStation charger)
        {
            agv.Status = AGVStatus.EnRoute;
            yield return NavigateToPosition(agv, charger.Position);

            if (agv.Status != AGVStatus.Error)
            {
                AssignToCharger(agv.AGVId, charger.StationId);
            }
        }

        #endregion

        #region Status Updates

        private IEnumerator StatusUpdateLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(statusUpdateInterval);

                foreach (var agv in fleet.Values)
                {
                    // Update position from NavAgent
                    if (agv.NavAgent != null)
                    {
                        agv.Position = agv.NavAgent.transform.position;
                        agv.Rotation = agv.NavAgent.transform.rotation;
                        agv.CurrentSpeed = agv.NavAgent.velocity.magnitude;
                    }

                    // Update odometry
                    if (agv.CurrentSpeed > 0.1f)
                    {
                        agv.TotalDistanceTraveled += agv.CurrentSpeed * statusUpdateInterval;
                        agv.TotalOperatingTime += statusUpdateInterval;
                    }
                }
            }
        }

        #endregion

        #region Alerts

        private void RaiseAlert(AGVUnit agv, AGVAlertType alertType, string message)
        {
            var alert = new AGVAlert
            {
                AlertId = Guid.NewGuid().ToString(),
                AGVId = agv.AGVId,
                AlertType = alertType,
                Message = message,
                Timestamp = DateTime.UtcNow,
                Position = agv.Position
            };

            OnAGVAlert?.Invoke(agv, alert);
            Debug.LogWarning($"[AGV] Alert for {agv.Name}: {message}");
        }

        #endregion

        #region Statistics

        public AGVFleetStats GetStatistics()
        {
            return new AGVFleetStats
            {
                TotalAGVs = fleet.Count,
                IdleAGVs = fleet.Values.Count(a => a.Status == AGVStatus.Idle),
                BusyAGVs = fleet.Values.Count(a => a.Status == AGVStatus.EnRoute ||
                    a.Status == AGVStatus.Loading || a.Status == AGVStatus.Unloading),
                ChargingAGVs = fleet.Values.Count(a => a.Status == AGVStatus.Charging),
                ErrorAGVs = fleet.Values.Count(a => a.Status == AGVStatus.Error),
                PendingTasks = taskQueue.Count,
                ActiveTasks = activeTasks.Count,
                CompletedTasks = completedTasks.Count,
                AverageTaskTime = completedTasks.Any() ?
                    completedTasks.Average(t => t.ActualDuration) : 0,
                AverageBatteryLevel = fleet.Values.Any() ?
                    fleet.Values.Average(a => a.BatteryLevel) : 0,
                TotalDistanceTraveled = fleet.Values.Sum(a => a.TotalDistanceTraveled),
                FleetUtilization = fleet.Count > 0 ?
                    (float)fleet.Values.Count(a => a.Status != AGVStatus.Idle && a.Status != AGVStatus.Charging) / fleet.Count * 100f : 0
            };
        }

        public int FleetSize => fleet.Count;
        public int PendingTaskCount => taskQueue.Count;

        #endregion
    }

    #region Enums

    public enum AGVType
    {
        Tugger,
        Forklift,
        UnitLoad,
        LightLoad,
        Custom
    }

    public enum AGVStatus
    {
        Idle,
        EnRoute,
        Loading,
        Unloading,
        Charging,
        Waiting,
        Maintenance,
        Error,
        Offline
    }

    public enum NavigationMode
    {
        Guided,         // Follow magnetic tape/wire
        Natural,        // SLAM-based natural navigation
        Hybrid,         // Combination
        Manual
    }

    public enum ZoneType
    {
        Production,
        Storage,
        LoadingDock,
        Charging,
        Maintenance,
        RestrictedArea
    }

    public enum WaypointType
    {
        Standard,
        Pickup,
        Dropoff,
        Charging,
        Intersection,
        WaitPoint
    }

    public enum TaskStatus
    {
        Pending,
        Assigned,
        EnRouteToSource,
        Pickup,
        EnRouteToDestination,
        Dropoff,
        Completed,
        Failed,
        Cancelled
    }

    public enum TaskPriority
    {
        Low = 0,
        Normal = 1,
        High = 2,
        Urgent = 3,
        Emergency = 4
    }

    public enum ChargingStationStatus
    {
        Available,
        Occupied,
        Maintenance,
        Error
    }

    public enum AGVAlertType
    {
        LowBattery,
        CriticalBattery,
        NavigationError,
        CollisionWarning,
        ObstacleDetected,
        TaskTimeout,
        CommunicationLost,
        Maintenance
    }

    #endregion

    #region Data Classes

    [System.Serializable]
    public class AGVUnit
    {
        public string AGVId;
        public string Name;
        public AGVType Type;
        public string Model;
        public float MaxPayload;
        public float MaxSpeed;
        public float BatteryCapacity;
        public float BatteryLevel;
        public Vector3 Position;
        public Quaternion Rotation;
        public Vector3 Dimensions;
        public AGVStatus Status;
        public NavigationMode NavigationMode;
        public string CurrentZone;
        public string CurrentTask;
        public PayloadInfo CurrentPayload;
        public string ChargingStationId;
        public bool NeedsCharging;
        public int Priority;
        public float CurrentSpeed;
        public int CompletedTasks;
        public float TotalDistanceTraveled;
        public float TotalOperatingTime;
        public DateTime RegistrationTime;
        public DateTime? LastMaintenance;
        public GameObject GameObject;
        public NavMeshAgent NavAgent;
    }

    [System.Serializable]
    public class AGVConfig
    {
        public string AGVId;
        public string Name;
        public AGVType Type;
        public string Model;
        public float MaxPayload;
        public float MaxSpeed;
        public float BatteryCapacity;
        public float InitialBattery;
        public Vector3 StartPosition;
        public Vector3 Dimensions;
        public NavigationMode NavigationMode;
        public bool CreateGameObject;
    }

    [System.Serializable]
    public class AGVZone
    {
        public string ZoneId;
        public string Name;
        public ZoneType ZoneType;
        public Bounds Bounds;
        public int MaxAGVs;
        public float SpeedLimit;
        public bool RequiresPermission;
        public List<string> CurrentAGVs;
    }

    [System.Serializable]
    public class AGVZoneConfig
    {
        public string ZoneId;
        public string Name;
        public ZoneType ZoneType;
        public Bounds Bounds;
        public int MaxAGVs;
        public float SpeedLimit;
        public bool RequiresPermission;
    }

    [System.Serializable]
    public class Waypoint
    {
        public string WaypointId;
        public string Name;
        public Vector3 Position;
        public WaypointType WaypointType;
        public string ZoneId;
        public List<string> ConnectedWaypoints;
        public List<AGVType> AllowedAGVTypes;
        public float DockingAngle;
        public float WaitTime;
    }

    [System.Serializable]
    public class WaypointConfig
    {
        public string WaypointId;
        public string Name;
        public Vector3 Position;
        public WaypointType WaypointType;
        public string ZoneId;
        public List<string> ConnectedWaypoints;
        public List<AGVType> AllowedAGVTypes;
        public float DockingAngle;
        public float WaitTime;
    }

    [System.Serializable]
    public class ChargingStation
    {
        public string StationId;
        public string Name;
        public Vector3 Position;
        public float ChargingRate;
        public float MaxVoltage;
        public float MaxCurrent;
        public ChargingStationStatus Status;
        public string CurrentAGV;
        public DateTime? ChargingStartTime;
        public float EnergyDelivered;
    }

    [System.Serializable]
    public class ChargingStationConfig
    {
        public string StationId;
        public string Name;
        public Vector3 Position;
        public float ChargingRate;
        public float MaxVoltage;
        public float MaxCurrent;
    }

    [System.Serializable]
    public class TransportTask
    {
        public string TaskId;
        public TransportTaskType TaskType;
        public TaskPriority Priority;
        public string SourceLocation;
        public string DestinationLocation;
        public PayloadInfo Payload;
        public AGVType? RequiredAGVType;
        public float MinPayloadCapacity;
        public DateTime? Deadline;
        public TaskStatus Status;
        public string AssignedAGV;
        public DateTime CreatedAt;
        public DateTime? AssignedAt;
        public DateTime? CompletedAt;
        public float ActualDuration;
        public float ActualDistance;
        public string ErrorMessage;
    }

    [System.Serializable]
    public class TransportTaskConfig
    {
        public string TaskId;
        public TransportTaskType TaskType;
        public TaskPriority Priority;
        public string SourceLocation;
        public string DestinationLocation;
        public PayloadInfo Payload;
        public AGVType? RequiredAGVType;
        public float MinPayloadCapacity;
        public DateTime? Deadline;
    }

    public enum TransportTaskType
    {
        PointToPoint,
        Pickup,
        Delivery,
        ReturnEmpty,
        Charging,
        Maintenance
    }

    [System.Serializable]
    public class PayloadInfo
    {
        public string PayloadId;
        public string Description;
        public float Weight;
        public Vector3 Dimensions;
        public float LoadTime;
        public float UnloadTime;
        public bool Fragile;
        public string MaterialType;
    }

    [System.Serializable]
    public class IntersectionLock
    {
        public string IntersectionId;
        public string LockedBy;
        public DateTime LockedAt;
        public DateTime ExpiresAt;
    }

    [System.Serializable]
    public class TrafficIncident
    {
        public string IncidentId;
        public string AGV1;
        public string AGV2;
        public string IncidentType;
        public Vector3 Location;
        public DateTime Timestamp;
        public string Resolution;
    }

    [System.Serializable]
    public class AGVAlert
    {
        public string AlertId;
        public string AGVId;
        public AGVAlertType AlertType;
        public string Message;
        public DateTime Timestamp;
        public Vector3 Position;
        public bool Acknowledged;
    }

    [System.Serializable]
    public class AGVFleetStats
    {
        public int TotalAGVs;
        public int IdleAGVs;
        public int BusyAGVs;
        public int ChargingAGVs;
        public int ErrorAGVs;
        public int PendingTasks;
        public int ActiveTasks;
        public int CompletedTasks;
        public float AverageTaskTime;
        public float AverageBatteryLevel;
        public float TotalDistanceTraveled;
        public float FleetUtilization;
    }

    #endregion
}
