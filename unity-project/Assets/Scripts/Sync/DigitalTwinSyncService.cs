using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using CNC_SCADA.DigitalTwin.ROS2;

namespace CNC_SCADA.DigitalTwin.Sync
{
    /// <summary>
    /// Digital Twin Synchronization Service
    /// Provides real-time bidirectional sync between physical and virtual twins
    /// Includes latency compensation, delta compression, and state prediction
    /// </summary>
    public class DigitalTwinSyncService : MonoBehaviour
    {
        public static DigitalTwinSyncService Instance { get; private set; }

        [Header("Sync Configuration")]
        [SerializeField] private SyncMode syncMode = SyncMode.Bidirectional;
        [SerializeField] private float syncRateHz = 60f;
        [SerializeField] private bool enableLatencyCompensation = true;
        [SerializeField] private bool enableDeltaCompression = true;
        [SerializeField] private bool enableStatePrediction = true;

        [Header("Network Settings")]
        [SerializeField] private float maxLatencyMs = 100f;
        [SerializeField] private int bufferSize = 30;
        [SerializeField] private float interpolationDelay = 0.1f;

        [Header("Compression Settings")]
        [SerializeField] private float positionThreshold = 0.0001f;
        [SerializeField] private float rotationThreshold = 0.01f;
        [SerializeField] private float velocityThreshold = 0.001f;

        // Events
        public event Action<SyncState> OnStateReceived;
        public event Action<SyncState> OnStateSent;
        public event Action<float> OnLatencyUpdated;
        public event Action<SyncConflict> OnConflictDetected;
        public event Action<SyncStatus> OnSyncStatusChanged;

        // State management
        private Dictionary<string, TwinEntity> trackedEntities = new Dictionary<string, TwinEntity>();
        private CircularBuffer<SyncState> stateHistory;
        private CircularBuffer<SyncState> remoteStateBuffer;
        private SyncState lastSentState;
        private SyncState lastReceivedState;

        // Timing and latency
        private float currentLatency = 0f;
        private float averageLatency = 0f;
        private float jitter = 0f;
        private Queue<float> latencySamples = new Queue<float>();
        private float lastSyncTime = 0f;
        private long sequenceNumber = 0;

        // Statistics
        private SyncStatistics statistics = new SyncStatistics();
        private SyncStatus currentStatus = SyncStatus.Disconnected;

        public float CurrentLatency => currentLatency;
        public float AverageLatency => averageLatency;
        public SyncStatus Status => currentStatus;
        public int TrackedEntityCount => trackedEntities.Count;

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
                Initialize();
            }
            else
            {
                Destroy(gameObject);
            }
        }

        private void Initialize()
        {
            stateHistory = new CircularBuffer<SyncState>(bufferSize);
            remoteStateBuffer = new CircularBuffer<SyncState>(bufferSize);

            // Subscribe to ROS2 bridge events
            if (ROS2UnityBridge.Instance != null)
            {
                ROS2UnityBridge.Instance.OnConnected += OnROS2Connected;
                ROS2UnityBridge.Instance.OnDisconnected += OnROS2Disconnected;
            }

            Debug.Log("[TwinSync] Initialized Digital Twin Sync Service");
        }

        private void FixedUpdate()
        {
            float syncInterval = 1f / syncRateHz;
            if (Time.fixedTime - lastSyncTime < syncInterval) return;

            lastSyncTime = Time.fixedTime;

            // Capture current state
            var currentState = CaptureState();

            // Apply interpolation/prediction to tracked entities
            if (enableStatePrediction)
            {
                ApplyStatePrediction();
            }

            // Send state if in appropriate mode
            if (syncMode == SyncMode.PrimaryToSecondary || syncMode == SyncMode.Bidirectional)
            {
                if (enableDeltaCompression)
                {
                    SendDeltaState(currentState);
                }
                else
                {
                    SendFullState(currentState);
                }
            }

            // Process received states
            ProcessReceivedStates();

            // Update statistics
            UpdateStatistics();
        }

        #region Entity Registration

        public void RegisterEntity(string entityId, Transform transform, TwinEntityType type, SyncPriority priority = SyncPriority.Normal)
        {
            if (trackedEntities.ContainsKey(entityId))
            {
                Debug.LogWarning($"[TwinSync] Entity already registered: {entityId}");
                return;
            }

            var entity = new TwinEntity
            {
                EntityId = entityId,
                Transform = transform,
                Type = type,
                Priority = priority,
                LastPosition = transform.position,
                LastRotation = transform.rotation,
                LastScale = transform.localScale,
                LastUpdateTime = Time.time,
                Predictor = new StatePredictor()
            };

            trackedEntities[entityId] = entity;
            Debug.Log($"[TwinSync] Registered entity: {entityId} ({type})");
        }

        public void UnregisterEntity(string entityId)
        {
            if (trackedEntities.ContainsKey(entityId))
            {
                trackedEntities.Remove(entityId);
                Debug.Log($"[TwinSync] Unregistered entity: {entityId}");
            }
        }

        public void RegisterMachine(string machineId, Transform machineTransform, Transform[] jointTransforms)
        {
            RegisterEntity(machineId, machineTransform, TwinEntityType.Machine, SyncPriority.High);

            // Register each joint
            for (int i = 0; i < jointTransforms.Length; i++)
            {
                string jointId = $"{machineId}_joint_{i}";
                RegisterEntity(jointId, jointTransforms[i], TwinEntityType.Joint, SyncPriority.High);
            }
        }

        public void RegisterRobot(string robotId, Transform robotTransform, Transform[] linkTransforms)
        {
            RegisterEntity(robotId, robotTransform, TwinEntityType.Robot, SyncPriority.Critical);

            for (int i = 0; i < linkTransforms.Length; i++)
            {
                string linkId = $"{robotId}_link_{i}";
                RegisterEntity(linkId, linkTransforms[i], TwinEntityType.RobotLink, SyncPriority.Critical);
            }
        }

        #endregion

        #region State Capture

        private SyncState CaptureState()
        {
            var state = new SyncState
            {
                SequenceNumber = sequenceNumber++,
                Timestamp = DateTime.UtcNow,
                LocalTime = Time.time,
                EntityStates = new Dictionary<string, EntityState>()
            };

            foreach (var kvp in trackedEntities)
            {
                var entity = kvp.Value;
                if (entity.Transform == null) continue;

                var entityState = new EntityState
                {
                    EntityId = entity.EntityId,
                    Position = entity.Transform.position,
                    Rotation = entity.Transform.rotation,
                    Scale = entity.Transform.localScale,
                    Velocity = (entity.Transform.position - entity.LastPosition) / Time.fixedDeltaTime,
                    AngularVelocity = GetAngularVelocity(entity.LastRotation, entity.Transform.rotation),
                    IsActive = entity.Transform.gameObject.activeInHierarchy
                };

                // Calculate delta from last state
                entityState.HasPositionChanged = Vector3.Distance(entityState.Position, entity.LastPosition) > positionThreshold;
                entityState.HasRotationChanged = Quaternion.Angle(entityState.Rotation, entity.LastRotation) > rotationThreshold;

                state.EntityStates[entity.EntityId] = entityState;

                // Update entity cache
                entity.LastPosition = entityState.Position;
                entity.LastRotation = entityState.Rotation;
                entity.LastScale = entityState.Scale;
                entity.LastUpdateTime = Time.time;
            }

            // Store in history
            stateHistory.Add(state);

            return state;
        }

        private Vector3 GetAngularVelocity(Quaternion from, Quaternion to)
        {
            Quaternion delta = to * Quaternion.Inverse(from);
            delta.ToAngleAxis(out float angle, out Vector3 axis);
            return axis * angle * Mathf.Deg2Rad / Time.fixedDeltaTime;
        }

        #endregion

        #region State Transmission

        private void SendFullState(SyncState state)
        {
            // Serialize and send full state
            var message = new SyncMessage
            {
                MessageType = SyncMessageType.FullState,
                Timestamp = state.Timestamp,
                SequenceNumber = state.SequenceNumber,
                Payload = SerializeState(state)
            };

            SendMessage(message);
            lastSentState = state;
            statistics.FullStatesSent++;
            OnStateSent?.Invoke(state);
        }

        private void SendDeltaState(SyncState state)
        {
            if (lastSentState == null)
            {
                SendFullState(state);
                return;
            }

            // Calculate delta
            var deltaState = new SyncState
            {
                SequenceNumber = state.SequenceNumber,
                Timestamp = state.Timestamp,
                LocalTime = state.LocalTime,
                EntityStates = new Dictionary<string, EntityState>(),
                IsDelta = true,
                BaseSequenceNumber = lastSentState.SequenceNumber
            };

            foreach (var kvp in state.EntityStates)
            {
                var entityState = kvp.Value;

                // Only include changed entities
                if (entityState.HasPositionChanged || entityState.HasRotationChanged)
                {
                    deltaState.EntityStates[kvp.Key] = entityState;
                }
            }

            // Send delta if there are changes, otherwise skip
            if (deltaState.EntityStates.Count > 0)
            {
                var message = new SyncMessage
                {
                    MessageType = SyncMessageType.DeltaState,
                    Timestamp = deltaState.Timestamp,
                    SequenceNumber = deltaState.SequenceNumber,
                    BaseSequenceNumber = deltaState.BaseSequenceNumber,
                    Payload = SerializeDeltaState(deltaState)
                };

                SendMessage(message);
                lastSentState = state;
                statistics.DeltaStatesSent++;
            }
            else
            {
                statistics.SkippedFrames++;
            }
        }

        private void SendMessage(SyncMessage message)
        {
            // Send via ROS2 or WebSocket
            if (ROS2UnityBridge.Instance != null && ROS2UnityBridge.Instance.IsConnected)
            {
                // Publish as ROS2 message
                // In real implementation, this would be a custom ROS2 message type
            }

            statistics.BytesSent += message.Payload?.Length ?? 0;
            statistics.MessagesSent++;
        }

        private byte[] SerializeState(SyncState state)
        {
            // JSON serialization for simplicity
            // In production, use binary serialization (FlatBuffers, Protobuf)
            string json = JsonUtility.ToJson(new SyncStateWrapper(state));
            return System.Text.Encoding.UTF8.GetBytes(json);
        }

        private byte[] SerializeDeltaState(SyncState state)
        {
            // Compressed delta serialization
            string json = JsonUtility.ToJson(new SyncStateWrapper(state));
            return System.Text.Encoding.UTF8.GetBytes(json);
        }

        #endregion

        #region State Reception

        public void ReceiveState(byte[] data, float networkLatency)
        {
            try
            {
                string json = System.Text.Encoding.UTF8.GetString(data);
                var wrapper = JsonUtility.FromJson<SyncStateWrapper>(json);
                var state = wrapper.ToSyncState();

                // Update latency tracking
                UpdateLatency(networkLatency);

                // Add to buffer for interpolation
                remoteStateBuffer.Add(state);

                lastReceivedState = state;
                statistics.MessagesReceived++;
                statistics.BytesReceived += data.Length;

                OnStateReceived?.Invoke(state);
            }
            catch (Exception ex)
            {
                Debug.LogError($"[TwinSync] Error receiving state: {ex.Message}");
                statistics.ErrorCount++;
            }
        }

        private void ProcessReceivedStates()
        {
            if (syncMode == SyncMode.SecondaryToPrimary || syncMode == SyncMode.Bidirectional)
            {
                // Get interpolated state based on buffer
                var targetState = GetInterpolatedState();
                if (targetState != null)
                {
                    ApplyState(targetState);
                }
            }
        }

        private SyncState GetInterpolatedState()
        {
            if (remoteStateBuffer.Count < 2) return null;

            // Find states to interpolate between
            float targetTime = Time.time - interpolationDelay;

            SyncState before = null;
            SyncState after = null;

            var states = remoteStateBuffer.GetAll();
            for (int i = 0; i < states.Count - 1; i++)
            {
                if (states[i].LocalTime <= targetTime && states[i + 1].LocalTime >= targetTime)
                {
                    before = states[i];
                    after = states[i + 1];
                    break;
                }
            }

            if (before == null || after == null) return null;

            // Interpolate
            float t = (targetTime - before.LocalTime) / (after.LocalTime - before.LocalTime);
            return InterpolateStates(before, after, t);
        }

        private SyncState InterpolateStates(SyncState a, SyncState b, float t)
        {
            var interpolated = new SyncState
            {
                SequenceNumber = b.SequenceNumber,
                Timestamp = DateTime.UtcNow,
                LocalTime = Time.time,
                EntityStates = new Dictionary<string, EntityState>()
            };

            foreach (var kvp in b.EntityStates)
            {
                var entityB = kvp.Value;
                EntityState entityA = null;
                a.EntityStates?.TryGetValue(kvp.Key, out entityA);

                var interpolatedEntity = new EntityState
                {
                    EntityId = entityB.EntityId,
                    IsActive = entityB.IsActive
                };

                if (entityA != null)
                {
                    interpolatedEntity.Position = Vector3.Lerp(entityA.Position, entityB.Position, t);
                    interpolatedEntity.Rotation = Quaternion.Slerp(entityA.Rotation, entityB.Rotation, t);
                    interpolatedEntity.Scale = Vector3.Lerp(entityA.Scale, entityB.Scale, t);
                    interpolatedEntity.Velocity = Vector3.Lerp(entityA.Velocity, entityB.Velocity, t);
                }
                else
                {
                    interpolatedEntity.Position = entityB.Position;
                    interpolatedEntity.Rotation = entityB.Rotation;
                    interpolatedEntity.Scale = entityB.Scale;
                    interpolatedEntity.Velocity = entityB.Velocity;
                }

                interpolated.EntityStates[kvp.Key] = interpolatedEntity;
            }

            return interpolated;
        }

        private void ApplyState(SyncState state)
        {
            foreach (var kvp in state.EntityStates)
            {
                if (trackedEntities.TryGetValue(kvp.Key, out var entity))
                {
                    if (entity.Transform == null) continue;

                    var entityState = kvp.Value;

                    // Check for conflicts
                    if (syncMode == SyncMode.Bidirectional)
                    {
                        var conflict = DetectConflict(entity, entityState);
                        if (conflict != null)
                        {
                            OnConflictDetected?.Invoke(conflict);
                            // Resolve conflict based on policy
                            if (!ResolveConflict(conflict))
                            {
                                continue; // Skip this update
                            }
                        }
                    }

                    // Apply state with smoothing
                    if (entity.Priority == SyncPriority.Critical)
                    {
                        // Immediate update for critical entities
                        entity.Transform.position = entityState.Position;
                        entity.Transform.rotation = entityState.Rotation;
                    }
                    else
                    {
                        // Smooth interpolation for other entities
                        entity.Transform.position = Vector3.Lerp(
                            entity.Transform.position,
                            entityState.Position,
                            0.5f
                        );
                        entity.Transform.rotation = Quaternion.Slerp(
                            entity.Transform.rotation,
                            entityState.Rotation,
                            0.5f
                        );
                    }

                    entity.Transform.localScale = entityState.Scale;
                    entity.Transform.gameObject.SetActive(entityState.IsActive);
                }
            }
        }

        #endregion

        #region State Prediction

        private void ApplyStatePrediction()
        {
            foreach (var entity in trackedEntities.Values)
            {
                if (entity.Transform == null) continue;

                // Predict position based on velocity
                entity.Predictor.UpdatePrediction(
                    entity.Transform.position,
                    (entity.Transform.position - entity.LastPosition) / Time.fixedDeltaTime,
                    Time.fixedDeltaTime
                );
            }
        }

        #endregion

        #region Conflict Detection & Resolution

        private SyncConflict DetectConflict(TwinEntity entity, EntityState remoteState)
        {
            // Compare local and remote state
            float positionDelta = Vector3.Distance(entity.Transform.position, remoteState.Position);
            float rotationDelta = Quaternion.Angle(entity.Transform.rotation, remoteState.Rotation);

            // Consider conflict if both sides have moved significantly
            float localMovement = Vector3.Distance(entity.Transform.position, entity.LastPosition);
            float remoteMovement = Vector3.Distance(remoteState.Position, entity.LastPosition);

            if (localMovement > positionThreshold && positionDelta > positionThreshold * 10)
            {
                return new SyncConflict
                {
                    EntityId = entity.EntityId,
                    Type = ConflictType.PositionMismatch,
                    LocalPosition = entity.Transform.position,
                    RemotePosition = remoteState.Position,
                    Magnitude = positionDelta,
                    Timestamp = DateTime.UtcNow
                };
            }

            return null;
        }

        private bool ResolveConflict(SyncConflict conflict)
        {
            switch (conflict.Type)
            {
                case ConflictType.PositionMismatch:
                    // Default: remote wins for now
                    // Could implement more sophisticated resolution
                    return true;

                case ConflictType.StateMismatch:
                    // Request full state resync
                    RequestResync();
                    return false;

                default:
                    return true;
            }
        }

        public void RequestResync()
        {
            var message = new SyncMessage
            {
                MessageType = SyncMessageType.ResyncRequest,
                Timestamp = DateTime.UtcNow,
                SequenceNumber = sequenceNumber
            };

            SendMessage(message);
            statistics.ResyncRequests++;
            Debug.Log("[TwinSync] Requested full resync");
        }

        #endregion

        #region Latency Management

        private void UpdateLatency(float latency)
        {
            currentLatency = latency;

            latencySamples.Enqueue(latency);
            if (latencySamples.Count > 100)
            {
                latencySamples.Dequeue();
            }

            // Calculate average and jitter
            averageLatency = latencySamples.Average();
            jitter = latencySamples.Max() - latencySamples.Min();

            OnLatencyUpdated?.Invoke(currentLatency);

            // Adjust interpolation delay based on jitter
            if (enableLatencyCompensation)
            {
                interpolationDelay = averageLatency / 1000f + jitter / 1000f * 2f;
            }
        }

        #endregion

        #region Connection Management

        private void OnROS2Connected()
        {
            SetStatus(SyncStatus.Connecting);

            // Send initial full state
            var state = CaptureState();
            SendFullState(state);

            SetStatus(SyncStatus.Synchronized);
        }

        private void OnROS2Disconnected()
        {
            SetStatus(SyncStatus.Disconnected);
        }

        private void SetStatus(SyncStatus status)
        {
            if (currentStatus != status)
            {
                currentStatus = status;
                OnSyncStatusChanged?.Invoke(status);
                Debug.Log($"[TwinSync] Status changed to: {status}");
            }
        }

        #endregion

        #region Statistics

        private void UpdateStatistics()
        {
            statistics.TrackedEntities = trackedEntities.Count;
            statistics.CurrentLatencyMs = currentLatency;
            statistics.AverageLatencyMs = averageLatency;
            statistics.JitterMs = jitter;
            statistics.BufferUtilization = (float)remoteStateBuffer.Count / bufferSize;
        }

        public SyncStatistics GetStatistics()
        {
            return statistics;
        }

        #endregion
    }

    #region Data Classes

    public enum SyncMode
    {
        PrimaryToSecondary, // Primary sends, secondary receives
        SecondaryToPrimary, // Secondary sends, primary receives
        Bidirectional,      // Both send and receive
        ReadOnly            // Only receives, never sends
    }

    public enum SyncPriority
    {
        Low,
        Normal,
        High,
        Critical
    }

    public enum TwinEntityType
    {
        Generic,
        Machine,
        Robot,
        RobotLink,
        Joint,
        Tool,
        Workpiece,
        Sensor,
        Conveyor,
        Environment
    }

    public enum SyncStatus
    {
        Disconnected,
        Connecting,
        Synchronized,
        Degraded,
        Error
    }

    public enum SyncMessageType
    {
        FullState,
        DeltaState,
        Heartbeat,
        ResyncRequest,
        Acknowledgment
    }

    public enum ConflictType
    {
        PositionMismatch,
        RotationMismatch,
        StateMismatch,
        SequenceGap
    }

    [Serializable]
    public class TwinEntity
    {
        public string EntityId;
        public Transform Transform;
        public TwinEntityType Type;
        public SyncPriority Priority;
        public Vector3 LastPosition;
        public Quaternion LastRotation;
        public Vector3 LastScale;
        public float LastUpdateTime;
        public StatePredictor Predictor;
    }

    [Serializable]
    public class SyncState
    {
        public long SequenceNumber;
        public DateTime Timestamp;
        public float LocalTime;
        public Dictionary<string, EntityState> EntityStates;
        public bool IsDelta;
        public long BaseSequenceNumber;
    }

    [Serializable]
    public class EntityState
    {
        public string EntityId;
        public Vector3 Position;
        public Quaternion Rotation;
        public Vector3 Scale;
        public Vector3 Velocity;
        public Vector3 AngularVelocity;
        public bool IsActive;
        public bool HasPositionChanged;
        public bool HasRotationChanged;
    }

    [Serializable]
    public class SyncMessage
    {
        public SyncMessageType MessageType;
        public DateTime Timestamp;
        public long SequenceNumber;
        public long BaseSequenceNumber;
        public byte[] Payload;
    }

    [Serializable]
    public class SyncConflict
    {
        public string EntityId;
        public ConflictType Type;
        public Vector3 LocalPosition;
        public Vector3 RemotePosition;
        public float Magnitude;
        public DateTime Timestamp;
    }

    [Serializable]
    public class SyncStatistics
    {
        public int TrackedEntities;
        public int MessagesSent;
        public int MessagesReceived;
        public long BytesSent;
        public long BytesReceived;
        public int FullStatesSent;
        public int DeltaStatesSent;
        public int SkippedFrames;
        public int ResyncRequests;
        public int ErrorCount;
        public float CurrentLatencyMs;
        public float AverageLatencyMs;
        public float JitterMs;
        public float BufferUtilization;
    }

    // Helper class for JSON serialization
    [Serializable]
    public class SyncStateWrapper
    {
        public long SequenceNumber;
        public string Timestamp;
        public float LocalTime;
        public List<EntityStateWrapper> Entities = new List<EntityStateWrapper>();

        public SyncStateWrapper() { }

        public SyncStateWrapper(SyncState state)
        {
            SequenceNumber = state.SequenceNumber;
            Timestamp = state.Timestamp.ToString("O");
            LocalTime = state.LocalTime;

            if (state.EntityStates != null)
            {
                foreach (var kvp in state.EntityStates)
                {
                    Entities.Add(new EntityStateWrapper(kvp.Value));
                }
            }
        }

        public SyncState ToSyncState()
        {
            var state = new SyncState
            {
                SequenceNumber = SequenceNumber,
                Timestamp = DateTime.Parse(Timestamp),
                LocalTime = LocalTime,
                EntityStates = new Dictionary<string, EntityState>()
            };

            foreach (var wrapper in Entities)
            {
                var entity = wrapper.ToEntityState();
                state.EntityStates[entity.EntityId] = entity;
            }

            return state;
        }
    }

    [Serializable]
    public class EntityStateWrapper
    {
        public string EntityId;
        public float[] Position = new float[3];
        public float[] Rotation = new float[4];
        public float[] Scale = new float[3];
        public float[] Velocity = new float[3];
        public bool IsActive;

        public EntityStateWrapper() { }

        public EntityStateWrapper(EntityState state)
        {
            EntityId = state.EntityId;
            Position[0] = state.Position.x;
            Position[1] = state.Position.y;
            Position[2] = state.Position.z;
            Rotation[0] = state.Rotation.x;
            Rotation[1] = state.Rotation.y;
            Rotation[2] = state.Rotation.z;
            Rotation[3] = state.Rotation.w;
            Scale[0] = state.Scale.x;
            Scale[1] = state.Scale.y;
            Scale[2] = state.Scale.z;
            Velocity[0] = state.Velocity.x;
            Velocity[1] = state.Velocity.y;
            Velocity[2] = state.Velocity.z;
            IsActive = state.IsActive;
        }

        public EntityState ToEntityState()
        {
            return new EntityState
            {
                EntityId = EntityId,
                Position = new Vector3(Position[0], Position[1], Position[2]),
                Rotation = new Quaternion(Rotation[0], Rotation[1], Rotation[2], Rotation[3]),
                Scale = new Vector3(Scale[0], Scale[1], Scale[2]),
                Velocity = new Vector3(Velocity[0], Velocity[1], Velocity[2]),
                IsActive = IsActive
            };
        }
    }

    // Circular buffer for state history
    public class CircularBuffer<T>
    {
        private T[] buffer;
        private int head;
        private int tail;
        private int count;

        public int Count => count;
        public int Capacity => buffer.Length;

        public CircularBuffer(int capacity)
        {
            buffer = new T[capacity];
            head = 0;
            tail = 0;
            count = 0;
        }

        public void Add(T item)
        {
            buffer[head] = item;
            head = (head + 1) % buffer.Length;

            if (count < buffer.Length)
            {
                count++;
            }
            else
            {
                tail = (tail + 1) % buffer.Length;
            }
        }

        public T Get(int index)
        {
            if (index >= count) throw new IndexOutOfRangeException();
            return buffer[(tail + index) % buffer.Length];
        }

        public List<T> GetAll()
        {
            var result = new List<T>(count);
            for (int i = 0; i < count; i++)
            {
                result.Add(Get(i));
            }
            return result;
        }
    }

    // State predictor for latency compensation
    public class StatePredictor
    {
        private Vector3 lastPosition;
        private Vector3 lastVelocity;
        private Vector3 predictedPosition;
        private float lastUpdateTime;

        public Vector3 PredictedPosition => predictedPosition;

        public void UpdatePrediction(Vector3 position, Vector3 velocity, float deltaTime)
        {
            // Simple linear prediction
            predictedPosition = position + velocity * deltaTime;

            lastPosition = position;
            lastVelocity = velocity;
            lastUpdateTime = Time.time;
        }

        public Vector3 GetPredictedPosition(float futureTime)
        {
            float dt = futureTime - lastUpdateTime;
            return lastPosition + lastVelocity * dt;
        }
    }

    #endregion
}
