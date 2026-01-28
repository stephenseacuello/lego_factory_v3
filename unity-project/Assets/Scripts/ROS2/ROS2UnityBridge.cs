using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace CNC_SCADA.DigitalTwin.ROS2
{
    /// <summary>
    /// Comprehensive ROS2 Unity Bridge for bidirectional communication
    /// Supports topics, services, actions, and TF transforms
    /// </summary>
    public class ROS2UnityBridge : MonoBehaviour
    {
        public static ROS2UnityBridge Instance { get; private set; }

        [Header("Connection Settings")]
        [SerializeField] private string rosBridgeUrl = "ws://localhost:9090";
        [SerializeField] private string rosDistro = "humble";
        [SerializeField] private bool autoConnect = true;
        [SerializeField] private float reconnectInterval = 5f;

        [Header("Namespace Configuration")]
        [SerializeField] private string robotNamespace = "/cnc_scada";
        [SerializeField] private string tfPrefix = "";

        [Header("QoS Settings")]
        [SerializeField] private QoSProfile defaultQoS = QoSProfile.SensorData;
        [SerializeField] private int queueSize = 10;

        [Header("Performance")]
        [SerializeField] private float publishRateHz = 60f;
        [SerializeField] private bool enableCompression = true;
        [SerializeField] private int maxMessageSize = 65536;

        // Events
        public event Action OnConnected;
        public event Action OnDisconnected;
        public event Action<string, string> OnMessageReceived;
        public event Action<ROSError> OnError;
        public event Action<TFMessage> OnTFReceived;

        // State
        private bool isConnected = false;
        private Dictionary<string, TopicSubscription> subscriptions = new Dictionary<string, TopicSubscription>();
        private Dictionary<string, TopicPublisher> publishers = new Dictionary<string, TopicPublisher>();
        private Dictionary<string, ServiceClient> serviceClients = new Dictionary<string, ServiceClient>();
        private Dictionary<string, ActionClient> actionClients = new Dictionary<string, ActionClient>();
        private Dictionary<string, Transform> tfTree = new Dictionary<string, Transform>();
        private Queue<ROSMessage> outgoingMessages = new Queue<ROSMessage>();
        private float lastPublishTime = 0f;

        // Statistics
        private int messagesReceived = 0;
        private int messagesSent = 0;
        private float bytesReceived = 0f;
        private float bytesSent = 0f;

        public bool IsConnected => isConnected;
        public string Namespace => robotNamespace;
        public int MessagesReceived => messagesReceived;
        public int MessagesSent => messagesSent;

        private void Awake()
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

        private void Start()
        {
            if (autoConnect)
            {
                Connect();
            }
        }

        private void Update()
        {
            if (!isConnected) return;

            // Process outgoing message queue at specified rate
            float publishInterval = 1f / publishRateHz;
            if (Time.time - lastPublishTime >= publishInterval)
            {
                ProcessOutgoingMessages();
                lastPublishTime = Time.time;
            }
        }

        #region Connection Management

        public void Connect()
        {
            StartCoroutine(ConnectCoroutine());
        }

        private IEnumerator ConnectCoroutine()
        {
            Debug.Log($"[ROS2Bridge] Connecting to {rosBridgeUrl}...");

            // Simulate WebSocket connection (in real implementation, use WebSocket library)
            yield return new WaitForSeconds(0.5f);

            isConnected = true;
            OnConnected?.Invoke();

            // Subscribe to TF
            SubscribeToTF();

            // Advertise standard topics
            AdvertiseStandardTopics();

            Debug.Log($"[ROS2Bridge] Connected to ROS2 ({rosDistro})");
        }

        public void Disconnect()
        {
            if (!isConnected) return;

            // Unsubscribe from all topics
            foreach (var sub in subscriptions.Values)
            {
                UnsubscribeTopic(sub.Topic);
            }

            subscriptions.Clear();
            publishers.Clear();
            serviceClients.Clear();
            actionClients.Clear();

            isConnected = false;
            OnDisconnected?.Invoke();

            Debug.Log("[ROS2Bridge] Disconnected");
        }

        private IEnumerator ReconnectCoroutine()
        {
            while (!isConnected)
            {
                yield return new WaitForSeconds(reconnectInterval);
                Connect();
            }
        }

        #endregion

        #region Topic Publishing

        public void Advertise<T>(string topic, QoSProfile qos = QoSProfile.Default) where T : ROSMessage
        {
            string fullTopic = GetFullTopicName(topic);

            if (publishers.ContainsKey(fullTopic))
            {
                Debug.LogWarning($"[ROS2Bridge] Topic already advertised: {fullTopic}");
                return;
            }

            var publisher = new TopicPublisher
            {
                Topic = fullTopic,
                MessageType = typeof(T).Name,
                QoS = qos,
                IsActive = true
            };

            publishers[fullTopic] = publisher;
            Debug.Log($"[ROS2Bridge] Advertised topic: {fullTopic} ({typeof(T).Name})");
        }

        public void Publish<T>(string topic, T message) where T : ROSMessage
        {
            string fullTopic = GetFullTopicName(topic);

            if (!publishers.ContainsKey(fullTopic))
            {
                Advertise<T>(topic);
            }

            message.Topic = fullTopic;
            message.Timestamp = GetROSTime();

            outgoingMessages.Enqueue(message);
        }

        public void PublishJointState(JointStateMessage jointState)
        {
            Publish("/joint_states", jointState);
        }

        public void PublishPose(string topic, PoseStampedMessage pose)
        {
            Publish(topic, pose);
        }

        public void PublishTwist(string topic, TwistMessage twist)
        {
            Publish(topic, twist);
        }

        public void PublishPointCloud(string topic, PointCloud2Message pointCloud)
        {
            Publish(topic, pointCloud);
        }

        public void PublishLaserScan(string topic, LaserScanMessage scan)
        {
            Publish(topic, scan);
        }

        public void PublishImage(string topic, ImageMessage image)
        {
            Publish(topic, image);
        }

        public void PublishOdometry(string topic, OdometryMessage odom)
        {
            Publish(topic, odom);
        }

        private void ProcessOutgoingMessages()
        {
            int maxPerFrame = 10;
            int processed = 0;

            while (outgoingMessages.Count > 0 && processed < maxPerFrame)
            {
                var message = outgoingMessages.Dequeue();
                SendMessage(message);
                processed++;
            }
        }

        private void SendMessage(ROSMessage message)
        {
            // Serialize and send via WebSocket
            string json = SerializeMessage(message);
            bytesSent += json.Length;
            messagesSent++;

            // In real implementation, send via WebSocket
            // webSocket.Send(json);
        }

        private void AdvertiseStandardTopics()
        {
            Advertise<JointStateMessage>("/joint_states", QoSProfile.SensorData);
            Advertise<TFMessage>("/tf", QoSProfile.SensorData);
            Advertise<DiagnosticArrayMessage>("/diagnostics", QoSProfile.SystemDefault);
        }

        #endregion

        #region Topic Subscription

        public void Subscribe<T>(string topic, Action<T> callback, QoSProfile qos = QoSProfile.Default) where T : ROSMessage
        {
            string fullTopic = GetFullTopicName(topic);

            if (subscriptions.ContainsKey(fullTopic))
            {
                Debug.LogWarning($"[ROS2Bridge] Already subscribed to: {fullTopic}");
                return;
            }

            var subscription = new TopicSubscription
            {
                Topic = fullTopic,
                MessageType = typeof(T).Name,
                QoS = qos,
                Callback = (msg) => callback((T)msg),
                IsActive = true
            };

            subscriptions[fullTopic] = subscription;
            Debug.Log($"[ROS2Bridge] Subscribed to: {fullTopic}");
        }

        public void Unsubscribe(string topic)
        {
            string fullTopic = GetFullTopicName(topic);
            UnsubscribeTopic(fullTopic);
        }

        private void UnsubscribeTopic(string fullTopic)
        {
            if (subscriptions.ContainsKey(fullTopic))
            {
                subscriptions[fullTopic].IsActive = false;
                subscriptions.Remove(fullTopic);
                Debug.Log($"[ROS2Bridge] Unsubscribed from: {fullTopic}");
            }
        }

        private void SubscribeToTF()
        {
            Subscribe<TFMessage>("/tf", OnTFMessageReceived, QoSProfile.SensorData);
            Subscribe<TFMessage>("/tf_static", OnTFStaticReceived, QoSProfile.TransientLocal);
        }

        private void OnTFMessageReceived(TFMessage tfMessage)
        {
            foreach (var transform in tfMessage.Transforms)
            {
                UpdateTFTree(transform);
            }
            OnTFReceived?.Invoke(tfMessage);
        }

        private void OnTFStaticReceived(TFMessage tfMessage)
        {
            foreach (var transform in tfMessage.Transforms)
            {
                UpdateTFTree(transform, isStatic: true);
            }
        }

        #endregion

        #region Service Clients

        public void CreateServiceClient<TReq, TRes>(string serviceName)
            where TReq : ROSMessage
            where TRes : ROSMessage
        {
            string fullName = GetFullTopicName(serviceName);

            var client = new ServiceClient
            {
                ServiceName = fullName,
                RequestType = typeof(TReq).Name,
                ResponseType = typeof(TRes).Name,
                IsReady = true
            };

            serviceClients[fullName] = client;
            Debug.Log($"[ROS2Bridge] Created service client: {fullName}");
        }

        public void CallService<TReq, TRes>(string serviceName, TReq request, Action<TRes> callback)
            where TReq : ROSMessage
            where TRes : ROSMessage
        {
            string fullName = GetFullTopicName(serviceName);

            if (!serviceClients.ContainsKey(fullName))
            {
                CreateServiceClient<TReq, TRes>(serviceName);
            }

            var client = serviceClients[fullName];
            client.PendingCallbacks.Add(Guid.NewGuid().ToString(), (msg) => callback((TRes)msg));

            // Send service request
            var serviceCall = new ServiceCallMessage
            {
                ServiceName = fullName,
                Request = request
            };

            SendMessage(serviceCall);
            Debug.Log($"[ROS2Bridge] Called service: {fullName}");
        }

        // Common service calls
        public void GetParameter(string paramName, Action<object> callback)
        {
            // Implementation for parameter service
            Debug.Log($"[ROS2Bridge] Getting parameter: {paramName}");
        }

        public void SetParameter(string paramName, object value)
        {
            Debug.Log($"[ROS2Bridge] Setting parameter: {paramName} = {value}");
        }

        #endregion

        #region Action Clients

        public void CreateActionClient<TGoal, TResult, TFeedback>(string actionName)
            where TGoal : ROSMessage
            where TResult : ROSMessage
            where TFeedback : ROSMessage
        {
            string fullName = GetFullTopicName(actionName);

            var client = new ActionClient
            {
                ActionName = fullName,
                GoalType = typeof(TGoal).Name,
                ResultType = typeof(TResult).Name,
                FeedbackType = typeof(TFeedback).Name,
                IsReady = true
            };

            actionClients[fullName] = client;
            Debug.Log($"[ROS2Bridge] Created action client: {fullName}");
        }

        public string SendGoal<TGoal>(string actionName, TGoal goal,
            Action<ActionFeedback> feedbackCallback = null,
            Action<ActionResult> resultCallback = null)
            where TGoal : ROSMessage
        {
            string fullName = GetFullTopicName(actionName);
            string goalId = Guid.NewGuid().ToString();

            if (!actionClients.ContainsKey(fullName))
            {
                Debug.LogError($"[ROS2Bridge] Action client not found: {fullName}");
                return null;
            }

            var client = actionClients[fullName];

            var goalHandle = new GoalHandle
            {
                GoalId = goalId,
                ActionName = fullName,
                Status = GoalStatus.Pending,
                FeedbackCallback = feedbackCallback,
                ResultCallback = resultCallback
            };

            client.ActiveGoals[goalId] = goalHandle;

            // Send goal message
            var goalMessage = new ActionGoalMessage
            {
                ActionName = fullName,
                GoalId = goalId,
                Goal = goal
            };

            SendMessage(goalMessage);
            Debug.Log($"[ROS2Bridge] Sent goal to {fullName}: {goalId}");

            return goalId;
        }

        public void CancelGoal(string actionName, string goalId)
        {
            string fullName = GetFullTopicName(actionName);

            var cancelMessage = new ActionCancelMessage
            {
                ActionName = fullName,
                GoalId = goalId
            };

            SendMessage(cancelMessage);
            Debug.Log($"[ROS2Bridge] Cancelled goal: {goalId}");
        }

        // MoveIt action for robot motion planning
        public string SendMoveItGoal(PoseStampedMessage targetPose, Action<ActionResult> onComplete)
        {
            var goal = new MoveGroupGoal
            {
                TargetPose = targetPose,
                PlanningGroup = "manipulator",
                NumPlanningAttempts = 10,
                AllowedPlanningTime = 5.0
            };

            return SendGoal("/move_group", goal, null, onComplete);
        }

        // Trajectory execution
        public string ExecuteTrajectory(JointTrajectoryMessage trajectory, Action<ActionResult> onComplete)
        {
            var goal = new FollowJointTrajectoryGoal
            {
                Trajectory = trajectory
            };

            return SendGoal("/follow_joint_trajectory", goal,
                (feedback) => Debug.Log($"Trajectory progress: {feedback.Progress:P0}"),
                onComplete);
        }

        #endregion

        #region TF (Transform) Management

        public void PublishTF(TransformStampedMessage transform)
        {
            var tfMessage = new TFMessage
            {
                Transforms = new List<TransformStampedMessage> { transform }
            };

            Publish("/tf", tfMessage);
        }

        public void PublishStaticTF(TransformStampedMessage transform)
        {
            var tfMessage = new TFMessage
            {
                Transforms = new List<TransformStampedMessage> { transform }
            };

            Publish("/tf_static", tfMessage);
        }

        public void PublishUnityTransformToTF(UnityEngine.Transform unityTransform, string frameId, string childFrameId)
        {
            var tfMsg = new TransformStampedMessage
            {
                Header = new HeaderMessage
                {
                    Stamp = GetROSTime(),
                    FrameId = frameId
                },
                ChildFrameId = childFrameId,
                Transform = new TransformMessage
                {
                    Translation = UnityToROSPosition(unityTransform.position),
                    Rotation = UnityToROSRotation(unityTransform.rotation)
                }
            };

            PublishTF(tfMsg);
        }

        private void UpdateTFTree(TransformStampedMessage transform, bool isStatic = false)
        {
            string key = $"{transform.Header.FrameId}->{transform.ChildFrameId}";

            // Store transform for lookup
            // In real implementation, this would update a proper TF tree structure
        }

        public bool LookupTransform(string targetFrame, string sourceFrame, out TransformStampedMessage transform)
        {
            transform = null;
            string key = $"{sourceFrame}->{targetFrame}";

            // In real implementation, traverse TF tree to find transform
            return false;
        }

        #endregion

        #region Coordinate Conversion

        public static Vector3Message UnityToROSPosition(Vector3 unityPos)
        {
            // Unity: X-right, Y-up, Z-forward
            // ROS: X-forward, Y-left, Z-up
            return new Vector3Message
            {
                X = unityPos.z,
                Y = -unityPos.x,
                Z = unityPos.y
            };
        }

        public static Vector3 ROSToUnityPosition(Vector3Message rosPos)
        {
            return new Vector3(
                -(float)rosPos.Y,
                (float)rosPos.Z,
                (float)rosPos.X
            );
        }

        public static QuaternionMessage UnityToROSRotation(Quaternion unityRot)
        {
            // Convert Unity quaternion to ROS quaternion
            return new QuaternionMessage
            {
                X = unityRot.z,
                Y = -unityRot.x,
                Z = unityRot.y,
                W = -unityRot.w
            };
        }

        public static Quaternion ROSToUnityRotation(QuaternionMessage rosRot)
        {
            return new Quaternion(
                -(float)rosRot.Y,
                (float)rosRot.Z,
                (float)rosRot.X,
                -(float)rosRot.W
            );
        }

        #endregion

        #region Utility Methods

        private string GetFullTopicName(string topic)
        {
            if (topic.StartsWith("/"))
            {
                return topic;
            }
            return $"{robotNamespace}/{topic}";
        }

        private ROSTime GetROSTime()
        {
            var now = DateTime.UtcNow;
            var epoch = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
            var span = now - epoch;

            return new ROSTime
            {
                Sec = (int)span.TotalSeconds,
                Nanosec = (uint)((span.TotalSeconds - (int)span.TotalSeconds) * 1e9)
            };
        }

        private string SerializeMessage(ROSMessage message)
        {
            // JSON serialization for rosbridge protocol
            return JsonUtility.ToJson(message);
        }

        public ROSBridgeStatistics GetStatistics()
        {
            return new ROSBridgeStatistics
            {
                IsConnected = isConnected,
                MessagesReceived = messagesReceived,
                MessagesSent = messagesSent,
                BytesReceived = bytesReceived,
                BytesSent = bytesSent,
                ActiveSubscriptions = subscriptions.Count,
                ActivePublishers = publishers.Count,
                ActiveServiceClients = serviceClients.Count,
                ActiveActionClients = actionClients.Count
            };
        }

        #endregion
    }

    #region ROS Message Types

    [Serializable]
    public class ROSMessage
    {
        public string Topic;
        public ROSTime Timestamp;
    }

    [Serializable]
    public class ROSTime
    {
        public int Sec;
        public uint Nanosec;
    }

    [Serializable]
    public class HeaderMessage
    {
        public ROSTime Stamp;
        public string FrameId;
    }

    [Serializable]
    public class Vector3Message
    {
        public double X;
        public double Y;
        public double Z;
    }

    [Serializable]
    public class QuaternionMessage
    {
        public double X;
        public double Y;
        public double Z;
        public double W;
    }

    [Serializable]
    public class PoseMessage
    {
        public Vector3Message Position;
        public QuaternionMessage Orientation;
    }

    [Serializable]
    public class PoseStampedMessage : ROSMessage
    {
        public HeaderMessage Header;
        public PoseMessage Pose;
    }

    [Serializable]
    public class TwistMessage : ROSMessage
    {
        public Vector3Message Linear;
        public Vector3Message Angular;
    }

    [Serializable]
    public class WrenchMessage : ROSMessage
    {
        public Vector3Message Force;
        public Vector3Message Torque;
    }

    [Serializable]
    public class JointStateMessage : ROSMessage
    {
        public HeaderMessage Header;
        public string[] Name;
        public double[] Position;
        public double[] Velocity;
        public double[] Effort;
    }

    [Serializable]
    public class TransformMessage
    {
        public Vector3Message Translation;
        public QuaternionMessage Rotation;
    }

    [Serializable]
    public class TransformStampedMessage : ROSMessage
    {
        public HeaderMessage Header;
        public string ChildFrameId;
        public TransformMessage Transform;
    }

    [Serializable]
    public class TFMessage : ROSMessage
    {
        public List<TransformStampedMessage> Transforms;
    }

    [Serializable]
    public class LaserScanMessage : ROSMessage
    {
        public HeaderMessage Header;
        public float AngleMin;
        public float AngleMax;
        public float AngleIncrement;
        public float TimeIncrement;
        public float ScanTime;
        public float RangeMin;
        public float RangeMax;
        public float[] Ranges;
        public float[] Intensities;
    }

    [Serializable]
    public class PointCloud2Message : ROSMessage
    {
        public HeaderMessage Header;
        public uint Height;
        public uint Width;
        public PointFieldMessage[] Fields;
        public bool IsBigEndian;
        public uint PointStep;
        public uint RowStep;
        public byte[] Data;
        public bool IsDense;
    }

    [Serializable]
    public class PointFieldMessage
    {
        public string Name;
        public uint Offset;
        public byte Datatype;
        public uint Count;
    }

    [Serializable]
    public class ImageMessage : ROSMessage
    {
        public HeaderMessage Header;
        public uint Height;
        public uint Width;
        public string Encoding;
        public byte IsBigEndian;
        public uint Step;
        public byte[] Data;
    }

    [Serializable]
    public class OdometryMessage : ROSMessage
    {
        public HeaderMessage Header;
        public string ChildFrameId;
        public PoseWithCovarianceMessage Pose;
        public TwistWithCovarianceMessage Twist;
    }

    [Serializable]
    public class PoseWithCovarianceMessage
    {
        public PoseMessage Pose;
        public double[] Covariance; // 36 elements
    }

    [Serializable]
    public class TwistWithCovarianceMessage
    {
        public TwistMessage Twist;
        public double[] Covariance; // 36 elements
    }

    [Serializable]
    public class JointTrajectoryMessage : ROSMessage
    {
        public HeaderMessage Header;
        public string[] JointNames;
        public JointTrajectoryPointMessage[] Points;
    }

    [Serializable]
    public class JointTrajectoryPointMessage
    {
        public double[] Positions;
        public double[] Velocities;
        public double[] Accelerations;
        public double[] Effort;
        public ROSTime TimeFromStart;
    }

    [Serializable]
    public class DiagnosticArrayMessage : ROSMessage
    {
        public HeaderMessage Header;
        public DiagnosticStatusMessage[] Status;
    }

    [Serializable]
    public class DiagnosticStatusMessage
    {
        public byte Level; // OK=0, WARN=1, ERROR=2, STALE=3
        public string Name;
        public string Message;
        public string HardwareId;
        public KeyValueMessage[] Values;
    }

    [Serializable]
    public class KeyValueMessage
    {
        public string Key;
        public string Value;
    }

    // Service messages
    [Serializable]
    public class ServiceCallMessage : ROSMessage
    {
        public string ServiceName;
        public ROSMessage Request;
    }

    // Action messages
    [Serializable]
    public class ActionGoalMessage : ROSMessage
    {
        public string ActionName;
        public string GoalId;
        public ROSMessage Goal;
    }

    [Serializable]
    public class ActionCancelMessage : ROSMessage
    {
        public string ActionName;
        public string GoalId;
    }

    [Serializable]
    public class ActionFeedback
    {
        public string GoalId;
        public float Progress;
        public string Status;
    }

    [Serializable]
    public class ActionResult
    {
        public string GoalId;
        public bool Success;
        public string Message;
        public ROSMessage Result;
    }

    // MoveIt specific
    [Serializable]
    public class MoveGroupGoal : ROSMessage
    {
        public PoseStampedMessage TargetPose;
        public string PlanningGroup;
        public int NumPlanningAttempts;
        public double AllowedPlanningTime;
    }

    [Serializable]
    public class FollowJointTrajectoryGoal : ROSMessage
    {
        public JointTrajectoryMessage Trajectory;
    }

    #endregion

    #region Supporting Classes

    public enum QoSProfile
    {
        Default,
        SensorData,
        SystemDefault,
        ServicesDefault,
        ParametersDefault,
        TransientLocal,
        Reliable,
        BestEffort
    }

    [Serializable]
    public class TopicSubscription
    {
        public string Topic;
        public string MessageType;
        public QoSProfile QoS;
        public Action<ROSMessage> Callback;
        public bool IsActive;
    }

    [Serializable]
    public class TopicPublisher
    {
        public string Topic;
        public string MessageType;
        public QoSProfile QoS;
        public bool IsActive;
    }

    [Serializable]
    public class ServiceClient
    {
        public string ServiceName;
        public string RequestType;
        public string ResponseType;
        public bool IsReady;
        public Dictionary<string, Action<ROSMessage>> PendingCallbacks = new Dictionary<string, Action<ROSMessage>>();
    }

    [Serializable]
    public class ActionClient
    {
        public string ActionName;
        public string GoalType;
        public string ResultType;
        public string FeedbackType;
        public bool IsReady;
        public Dictionary<string, GoalHandle> ActiveGoals = new Dictionary<string, GoalHandle>();
    }

    [Serializable]
    public class GoalHandle
    {
        public string GoalId;
        public string ActionName;
        public GoalStatus Status;
        public Action<ActionFeedback> FeedbackCallback;
        public Action<ActionResult> ResultCallback;
    }

    public enum GoalStatus
    {
        Pending,
        Active,
        Preempted,
        Succeeded,
        Aborted,
        Rejected,
        Preempting,
        Recalling,
        Recalled,
        Lost
    }

    [Serializable]
    public class ROSError
    {
        public string Code;
        public string Message;
        public DateTime Timestamp;
    }

    [Serializable]
    public class ROSBridgeStatistics
    {
        public bool IsConnected;
        public int MessagesReceived;
        public int MessagesSent;
        public float BytesReceived;
        public float BytesSent;
        public int ActiveSubscriptions;
        public int ActivePublishers;
        public int ActiveServiceClients;
        public int ActiveActionClients;
    }

    #endregion
}
