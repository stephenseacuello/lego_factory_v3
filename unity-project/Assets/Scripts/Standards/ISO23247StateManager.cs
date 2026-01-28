using System;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json;

namespace CNCScada.Standards
{
    /// <summary>
    /// Manages ISO 23247 compliant digital twin state representation.
    /// Implements ISO 23247-3 (Digital representation of manufacturing elements)
    /// and ISO 23247-4 (Information exchange).
    /// Part of Feature 1.4: ISO 23247 Compliance (MEDIUM PRIORITY)
    /// </summary>
    public class ISO23247StateManager : MonoBehaviour
    {
        [Header("ISO 23247 Configuration")]
        [SerializeField] private string entityId = "CNC-001";
        [SerializeField] private string entityType = "MachineToolResource";
        [SerializeField] private string manufacturingSite = "Plant-A";
        [SerializeField] private float updateInterval = 0.1f; // 10Hz state updates

        [Header("State Synchronization")]
        [SerializeField] private bool autoSync = true;
        [SerializeField] private bool logStateChanges = true;

        // Current state
        private ISO23247State currentState;
        private ISO23247State previousState;
        private float updateTimer = 0f;

        // State change tracking
        private Dictionary<string, object> stateChanges = new Dictionary<string, object>();
        private int stateVersion = 0;

        // Events
        public event Action<ISO23247State> OnStateUpdated;
        public event Action<ISO23247StateChange> OnStateChanged;

        // Statistics
        private int totalUpdates = 0;
        private int totalChanges = 0;
        private DateTime lastSyncTime;

        void Start()
        {
            InitializeState();
            lastSyncTime = DateTime.UtcNow;
        }

        void Update()
        {
            if (!autoSync) return;

            updateTimer += Time.deltaTime;
            if (updateTimer >= updateInterval)
            {
                UpdateState();
                updateTimer = 0f;
            }
        }

        /// <summary>
        /// Initialize ISO 23247 compliant state
        /// </summary>
        private void InitializeState()
        {
            currentState = new ISO23247State
            {
                EntityIdentification = new EntityIdentification
                {
                    EntityId = entityId,
                    EntityType = entityType,
                    ManufacturingSite = manufacturingSite,
                    Timestamp = DateTime.UtcNow
                },
                ObservableInformation = new ObservableInformation
                {
                    Position = new Position3D(),
                    Orientation = new Orientation3D(),
                    Velocity = new Velocity3D(),
                    Status = "Idle"
                },
                CapabilityInformation = new CapabilityInformation
                {
                    AvailableCapabilities = new List<string>
                    {
                        "3-axis-milling",
                        "tool-change",
                        "workpiece-probing"
                    },
                    MaxFeedRate = 5000f, // mm/min
                    MaxSpindleSpeed = 24000f, // RPM
                    WorkspaceVolume = new WorkspaceVolume
                    {
                        XMin = -200f,
                        XMax = 200f,
                        YMin = -150f,
                        YMax = 150f,
                        ZMin = 0f,
                        ZMax = 300f
                    }
                },
                StateVersion = stateVersion
            };

            previousState = CloneState(currentState);

            Debug.Log($"[ISO23247] State initialized for entity {entityId}");
        }

        /// <summary>
        /// Update state from current machine data
        /// </summary>
        public void UpdateState()
        {
            previousState = CloneState(currentState);

            // Update timestamp
            currentState.EntityIdentification.Timestamp = DateTime.UtcNow;

            // Update observable information (position, velocity, etc.)
            UpdateObservableInformation();

            // Increment version
            stateVersion++;
            currentState.StateVersion = stateVersion;
            totalUpdates++;

            // Detect changes
            DetectStateChanges();

            // Trigger events
            OnStateUpdated?.Invoke(currentState);

            lastSyncTime = DateTime.UtcNow;

            if (logStateChanges && stateChanges.Count > 0)
            {
                Debug.Log($"[ISO23247] State updated (v{stateVersion}): {stateChanges.Count} changes");
            }
        }

        /// <summary>
        /// Update observable information from machine
        /// </summary>
        private void UpdateObservableInformation()
        {
            // Update position from transform
            currentState.ObservableInformation.Position = new Position3D
            {
                X = transform.position.x,
                Y = transform.position.y,
                Z = transform.position.z
            };

            // Update orientation
            var euler = transform.rotation.eulerAngles;
            currentState.ObservableInformation.Orientation = new Orientation3D
            {
                Roll = euler.x,
                Pitch = euler.y,
                Yaw = euler.z
            };

            // Calculate velocity (simple finite difference)
            if (previousState != null)
            {
                float dt = (float)(currentState.EntityIdentification.Timestamp -
                                  previousState.EntityIdentification.Timestamp).TotalSeconds;
                if (dt > 0)
                {
                    currentState.ObservableInformation.Velocity = new Velocity3D
                    {
                        VX = (currentState.ObservableInformation.Position.X -
                              previousState.ObservableInformation.Position.X) / dt,
                        VY = (currentState.ObservableInformation.Position.Y -
                              previousState.ObservableInformation.Position.Y) / dt,
                        VZ = (currentState.ObservableInformation.Position.Z -
                              previousState.ObservableInformation.Position.Z) / dt
                    };
                }
            }
        }

        /// <summary>
        /// Detect changes between current and previous state
        /// </summary>
        private void DetectStateChanges()
        {
            stateChanges.Clear();

            if (previousState == null) return;

            // Check position changes
            var posDelta = Vector3.Distance(
                new Vector3(
                    (float)currentState.ObservableInformation.Position.X,
                    (float)currentState.ObservableInformation.Position.Y,
                    (float)currentState.ObservableInformation.Position.Z
                ),
                new Vector3(
                    (float)previousState.ObservableInformation.Position.X,
                    (float)previousState.ObservableInformation.Position.Y,
                    (float)previousState.ObservableInformation.Position.Z
                )
            );

            if (posDelta > 0.001f) // 1mm threshold
            {
                stateChanges["position"] = currentState.ObservableInformation.Position;
                totalChanges++;
            }

            // Check status changes
            if (currentState.ObservableInformation.Status != previousState.ObservableInformation.Status)
            {
                stateChanges["status"] = currentState.ObservableInformation.Status;
                totalChanges++;

                // Trigger change event
                var change = new ISO23247StateChange
                {
                    Timestamp = DateTime.UtcNow,
                    PropertyName = "status",
                    OldValue = previousState.ObservableInformation.Status,
                    NewValue = currentState.ObservableInformation.Status,
                    StateVersion = stateVersion
                };
                OnStateChanged?.Invoke(change);
            }
        }

        /// <summary>
        /// Deep clone state object
        /// </summary>
        private ISO23247State CloneState(ISO23247State state)
        {
            // Use JSON serialization for deep clone
            string json = JsonConvert.SerializeObject(state);
            return JsonConvert.DeserializeObject<ISO23247State>(json);
        }

        /// <summary>
        /// Set machine status (ISO 23247 compliant)
        /// </summary>
        public void SetStatus(string status)
        {
            currentState.ObservableInformation.Status = status;
            UpdateState();
        }

        /// <summary>
        /// Update capability information
        /// </summary>
        public void UpdateCapabilities(List<string> capabilities)
        {
            currentState.CapabilityInformation.AvailableCapabilities = capabilities;
            stateVersion++;
            currentState.StateVersion = stateVersion;
            OnStateUpdated?.Invoke(currentState);
        }

        /// <summary>
        /// Get current ISO 23247 state as JSON
        /// </summary>
        public string GetStateJson()
        {
            return JsonConvert.SerializeObject(currentState, Formatting.Indented);
        }

        /// <summary>
        /// Apply state from JSON (ISO 23247-4: Information exchange)
        /// </summary>
        public bool ApplyStateJson(string json)
        {
            try
            {
                var newState = JsonConvert.DeserializeObject<ISO23247State>(json);
                if (newState != null && newState.EntityIdentification.EntityId == entityId)
                {
                    previousState = currentState;
                    currentState = newState;
                    stateVersion = currentState.StateVersion;
                    OnStateUpdated?.Invoke(currentState);
                    return true;
                }
                return false;
            }
            catch (Exception e)
            {
                Debug.LogError($"[ISO23247] Failed to apply state JSON: {e.Message}");
                return false;
            }
        }

        /// <summary>
        /// Get state statistics
        /// </summary>
        public ISO23247Statistics GetStatistics()
        {
            return new ISO23247Statistics
            {
                EntityId = entityId,
                StateVersion = stateVersion,
                TotalUpdates = totalUpdates,
                TotalChanges = totalChanges,
                LastSyncTime = lastSyncTime,
                UpdateInterval = updateInterval,
                IsCompliant = true
            };
        }

        #region Public Properties

        public ISO23247State CurrentState => currentState;
        public string EntityId => entityId;
        public int StateVersion => stateVersion;
        public bool IsAutoSync => autoSync;

        #endregion
    }

    #region ISO 23247 Data Structures

    /// <summary>
    /// ISO 23247 compliant state representation
    /// </summary>
    [Serializable]
    public class ISO23247State
    {
        public EntityIdentification EntityIdentification { get; set; }
        public ObservableInformation ObservableInformation { get; set; }
        public CapabilityInformation CapabilityInformation { get; set; }
        public int StateVersion { get; set; }
    }

    /// <summary>
    /// Entity identification (ISO 23247-3)
    /// </summary>
    [Serializable]
    public class EntityIdentification
    {
        public string EntityId { get; set; }
        public string EntityType { get; set; }
        public string ManufacturingSite { get; set; }
        public DateTime Timestamp { get; set; }
    }

    /// <summary>
    /// Observable information (ISO 23247-3)
    /// </summary>
    [Serializable]
    public class ObservableInformation
    {
        public Position3D Position { get; set; }
        public Orientation3D Orientation { get; set; }
        public Velocity3D Velocity { get; set; }
        public string Status { get; set; }
    }

    /// <summary>
    /// 3D Position
    /// </summary>
    [Serializable]
    public class Position3D
    {
        public double X { get; set; }
        public double Y { get; set; }
        public double Z { get; set; }
    }

    /// <summary>
    /// 3D Orientation (Euler angles)
    /// </summary>
    [Serializable]
    public class Orientation3D
    {
        public double Roll { get; set; }
        public double Pitch { get; set; }
        public double Yaw { get; set; }
    }

    /// <summary>
    /// 3D Velocity
    /// </summary>
    [Serializable]
    public class Velocity3D
    {
        public double VX { get; set; }
        public double VY { get; set; }
        public double VZ { get; set; }
    }

    /// <summary>
    /// Capability information (ISO 23247-3)
    /// </summary>
    [Serializable]
    public class CapabilityInformation
    {
        public List<string> AvailableCapabilities { get; set; }
        public float MaxFeedRate { get; set; }
        public float MaxSpindleSpeed { get; set; }
        public WorkspaceVolume WorkspaceVolume { get; set; }
    }

    /// <summary>
    /// Workspace volume definition
    /// </summary>
    [Serializable]
    public class WorkspaceVolume
    {
        public float XMin { get; set; }
        public float XMax { get; set; }
        public float YMin { get; set; }
        public float YMax { get; set; }
        public float ZMin { get; set; }
        public float ZMax { get; set; }
    }

    /// <summary>
    /// State change event
    /// </summary>
    [Serializable]
    public struct ISO23247StateChange
    {
        public DateTime Timestamp;
        public string PropertyName;
        public object OldValue;
        public object NewValue;
        public int StateVersion;
    }

    /// <summary>
    /// ISO 23247 compliance statistics
    /// </summary>
    [Serializable]
    public struct ISO23247Statistics
    {
        public string EntityId;
        public int StateVersion;
        public int TotalUpdates;
        public int TotalChanges;
        public DateTime LastSyncTime;
        public float UpdateInterval;
        public bool IsCompliant;
    }

    #endregion
}
