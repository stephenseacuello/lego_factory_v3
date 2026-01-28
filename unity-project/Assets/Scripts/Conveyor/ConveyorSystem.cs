using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using CNC_SCADA.DigitalTwin.Audit;

namespace CNC_SCADA.DigitalTwin.Conveyor
{
    /// <summary>
    /// Conveyor System for material handling and factory automation
    /// Supports belt, roller, chain, and pneumatic conveyors with routing logic
    /// </summary>
    public class ConveyorSystem : MonoBehaviour
    {
        public static ConveyorSystem Instance { get; private set; }

        [Header("System Configuration")]
        [SerializeField] private float defaultSpeed = 0.5f; // m/s
        [SerializeField] private float physicsUpdateRate = 50f;
        [SerializeField] private bool enableCollisionDetection = true;
        [SerializeField] private LayerMask itemLayer;

        // Events
        public event Action<ConveyorSegment, ConveyorItem> OnItemEntered;
        public event Action<ConveyorSegment, ConveyorItem> OnItemExited;
        public event Action<ConveyorSegment, ConveyorItem> OnItemAtStation;
        public event Action<ConveyorSegment> OnConveyorStarted;
        public event Action<ConveyorSegment> OnConveyorStopped;
        public event Action<ConveyorSegment, string> OnConveyorFault;
        public event Action<RoutingDecision> OnRoutingDecision;

        // Conveyor network
        private Dictionary<string, ConveyorSegment> segments = new Dictionary<string, ConveyorSegment>();
        private Dictionary<string, ConveyorItem> trackedItems = new Dictionary<string, ConveyorItem>();
        private Dictionary<string, ConveyorStation> stations = new Dictionary<string, ConveyorStation>();
        private Dictionary<string, ConveyorJunction> junctions = new Dictionary<string, ConveyorJunction>();

        // Statistics
        private ConveyorStatistics statistics = new ConveyorStatistics();

        public int SegmentCount => segments.Count;
        public int TrackedItemCount => trackedItems.Count;
        public int ActiveFaults => segments.Values.Count(s => s.HasFault);

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
            InvokeRepeating(nameof(UpdateConveyors), 0f, 1f / physicsUpdateRate);
        }

        #region Segment Management

        public ConveyorSegment CreateSegment(ConveyorConfig config)
        {
            if (segments.ContainsKey(config.SegmentId))
            {
                Debug.LogWarning($"[Conveyor] Segment already exists: {config.SegmentId}");
                return segments[config.SegmentId];
            }

            var segmentObj = new GameObject($"Conveyor_{config.SegmentId}");
            segmentObj.transform.SetParent(transform);
            segmentObj.transform.position = config.StartPosition;

            var segment = new ConveyorSegment
            {
                SegmentId = config.SegmentId,
                Name = config.Name,
                Type = config.Type,
                GameObject = segmentObj,
                StartPosition = config.StartPosition,
                EndPosition = config.EndPosition,
                Length = Vector3.Distance(config.StartPosition, config.EndPosition),
                Width = config.Width,
                Speed = config.Speed > 0 ? config.Speed : defaultSpeed,
                Direction = (config.EndPosition - config.StartPosition).normalized,
                IsRunning = false,
                IsBidirectional = config.IsBidirectional,
                ItemsOnSegment = new List<string>(),
                SensorPositions = config.SensorPositions ?? new List<float>()
            };

            // Create visual representation
            CreateSegmentVisual(segment, config);

            // Create collision trigger
            if (enableCollisionDetection)
            {
                CreateSegmentCollider(segment);
            }

            segments[config.SegmentId] = segment;

            Debug.Log($"[Conveyor] Created segment: {config.SegmentId} ({config.Type})");
            return segment;
        }

        private void CreateSegmentVisual(ConveyorSegment segment, ConveyorConfig config)
        {
            // Create belt/roller visual
            var visual = GameObject.CreatePrimitive(PrimitiveType.Cube);
            visual.name = "Visual";
            visual.transform.SetParent(segment.GameObject.transform);

            Vector3 midpoint = (config.StartPosition + config.EndPosition) / 2f;
            visual.transform.position = midpoint;
            visual.transform.localScale = new Vector3(config.Width, 0.1f, segment.Length);
            visual.transform.LookAt(config.EndPosition);
            visual.transform.Rotate(0, 90, 0);

            // Remove default collider
            var collider = visual.GetComponent<Collider>();
            if (collider != null) Destroy(collider);

            // Apply material based on type
            var renderer = visual.GetComponent<Renderer>();
            if (renderer != null)
            {
                var mat = new Material(Shader.Find("Standard"));
                mat.color = config.Type switch
                {
                    ConveyorType.Belt => new Color(0.2f, 0.2f, 0.2f),
                    ConveyorType.Roller => new Color(0.5f, 0.5f, 0.5f),
                    ConveyorType.Chain => new Color(0.3f, 0.3f, 0.4f),
                    ConveyorType.Pneumatic => new Color(0.4f, 0.4f, 0.5f),
                    _ => Color.gray
                };
                renderer.material = mat;
            }

            segment.VisualObject = visual;
        }

        private void CreateSegmentCollider(ConveyorSegment segment)
        {
            var triggerObj = new GameObject("Trigger");
            triggerObj.transform.SetParent(segment.GameObject.transform);

            Vector3 midpoint = (segment.StartPosition + segment.EndPosition) / 2f;
            triggerObj.transform.position = midpoint;
            triggerObj.transform.localScale = new Vector3(segment.Width, 0.5f, segment.Length);
            triggerObj.transform.LookAt(segment.EndPosition);
            triggerObj.transform.Rotate(0, 90, 0);

            var boxCollider = triggerObj.AddComponent<BoxCollider>();
            boxCollider.isTrigger = true;

            var handler = triggerObj.AddComponent<ConveyorTriggerHandler>();
            handler.Initialize(this, segment);
        }

        public void RemoveSegment(string segmentId)
        {
            if (segments.TryGetValue(segmentId, out var segment))
            {
                if (segment.GameObject != null)
                {
                    Destroy(segment.GameObject);
                }
                segments.Remove(segmentId);
                Debug.Log($"[Conveyor] Removed segment: {segmentId}");
            }
        }

        public ConveyorSegment GetSegment(string segmentId)
        {
            return segments.TryGetValue(segmentId, out var segment) ? segment : null;
        }

        #endregion

        #region Conveyor Control

        public void StartConveyor(string segmentId)
        {
            if (segments.TryGetValue(segmentId, out var segment))
            {
                if (segment.HasFault)
                {
                    Debug.LogWarning($"[Conveyor] Cannot start {segmentId} - has fault");
                    return;
                }

                segment.IsRunning = true;
                OnConveyorStarted?.Invoke(segment);

                LogAuditEvent("CONVEYOR_START", $"Started conveyor {segmentId}");
                Debug.Log($"[Conveyor] Started: {segmentId}");
            }
        }

        public void StopConveyor(string segmentId)
        {
            if (segments.TryGetValue(segmentId, out var segment))
            {
                segment.IsRunning = false;
                OnConveyorStopped?.Invoke(segment);

                LogAuditEvent("CONVEYOR_STOP", $"Stopped conveyor {segmentId}");
                Debug.Log($"[Conveyor] Stopped: {segmentId}");
            }
        }

        public void SetSpeed(string segmentId, float speed)
        {
            if (segments.TryGetValue(segmentId, out var segment))
            {
                segment.Speed = Mathf.Max(0, speed);
                Debug.Log($"[Conveyor] {segmentId} speed set to {speed} m/s");
            }
        }

        public void ReverseDirection(string segmentId)
        {
            if (segments.TryGetValue(segmentId, out var segment))
            {
                if (!segment.IsBidirectional)
                {
                    Debug.LogWarning($"[Conveyor] {segmentId} is not bidirectional");
                    return;
                }

                segment.Direction = -segment.Direction;
                var temp = segment.StartPosition;
                segment.StartPosition = segment.EndPosition;
                segment.EndPosition = temp;

                Debug.Log($"[Conveyor] {segmentId} direction reversed");
            }
        }

        public void StartAll()
        {
            foreach (var segment in segments.Values)
            {
                if (!segment.HasFault)
                {
                    segment.IsRunning = true;
                }
            }
            Debug.Log("[Conveyor] All conveyors started");
        }

        public void StopAll()
        {
            foreach (var segment in segments.Values)
            {
                segment.IsRunning = false;
            }
            Debug.Log("[Conveyor] All conveyors stopped");
        }

        public void EmergencyStop()
        {
            StopAll();
            LogAuditEvent("CONVEYOR_ESTOP", "Emergency stop activated", AuditSeverity.Critical);
            Debug.LogWarning("[Conveyor] EMERGENCY STOP");
        }

        #endregion

        #region Item Tracking

        public ConveyorItem TrackItem(GameObject itemObject, string itemId = null)
        {
            itemId = itemId ?? Guid.NewGuid().ToString().Substring(0, 8);

            if (trackedItems.ContainsKey(itemId))
            {
                Debug.LogWarning($"[Conveyor] Item already tracked: {itemId}");
                return trackedItems[itemId];
            }

            var item = new ConveyorItem
            {
                ItemId = itemId,
                GameObject = itemObject,
                CurrentSegmentId = null,
                PositionOnSegment = 0f,
                EntryTime = DateTime.Now,
                Status = ItemStatus.OnConveyor,
                Route = new List<string>(),
                Properties = new Dictionary<string, object>()
            };

            trackedItems[itemId] = item;
            statistics.TotalItemsTracked++;

            Debug.Log($"[Conveyor] Tracking item: {itemId}");
            return item;
        }

        public void UntrackItem(string itemId)
        {
            if (trackedItems.TryGetValue(itemId, out var item))
            {
                // Remove from segment
                if (!string.IsNullOrEmpty(item.CurrentSegmentId) &&
                    segments.TryGetValue(item.CurrentSegmentId, out var segment))
                {
                    segment.ItemsOnSegment.Remove(itemId);
                }

                trackedItems.Remove(itemId);
                Debug.Log($"[Conveyor] Untracked item: {itemId}");
            }
        }

        public ConveyorItem GetItem(string itemId)
        {
            return trackedItems.TryGetValue(itemId, out var item) ? item : null;
        }

        public void SetItemProperty(string itemId, string key, object value)
        {
            if (trackedItems.TryGetValue(itemId, out var item))
            {
                item.Properties[key] = value;
            }
        }

        public T GetItemProperty<T>(string itemId, string key)
        {
            if (trackedItems.TryGetValue(itemId, out var item) &&
                item.Properties.TryGetValue(key, out var value))
            {
                return (T)value;
            }
            return default;
        }

        internal void OnItemEnteredSegment(ConveyorSegment segment, GameObject itemObj)
        {
            var item = trackedItems.Values.FirstOrDefault(i => i.GameObject == itemObj);
            if (item == null)
            {
                item = TrackItem(itemObj);
            }

            // Remove from previous segment
            if (!string.IsNullOrEmpty(item.CurrentSegmentId) &&
                segments.TryGetValue(item.CurrentSegmentId, out var prevSegment))
            {
                prevSegment.ItemsOnSegment.Remove(item.ItemId);
                OnItemExited?.Invoke(prevSegment, item);
            }

            // Add to new segment
            item.CurrentSegmentId = segment.SegmentId;
            item.PositionOnSegment = 0f;
            item.Route.Add(segment.SegmentId);
            segment.ItemsOnSegment.Add(item.ItemId);

            statistics.ItemTransfers++;
            OnItemEntered?.Invoke(segment, item);
        }

        internal void OnItemExitedSegment(ConveyorSegment segment, GameObject itemObj)
        {
            var item = trackedItems.Values.FirstOrDefault(i => i.GameObject == itemObj);
            if (item != null && item.CurrentSegmentId == segment.SegmentId)
            {
                segment.ItemsOnSegment.Remove(item.ItemId);
                item.CurrentSegmentId = null;
                OnItemExited?.Invoke(segment, item);
            }
        }

        #endregion

        #region Stations

        public ConveyorStation CreateStation(StationConfig config)
        {
            var station = new ConveyorStation
            {
                StationId = config.StationId,
                Name = config.Name,
                Type = config.Type,
                SegmentId = config.SegmentId,
                PositionOnSegment = config.PositionOnSegment,
                ProcessTime = config.ProcessTime,
                IsOccupied = false,
                Queue = new Queue<string>()
            };

            stations[config.StationId] = station;

            // Add sensor at station position
            if (segments.TryGetValue(config.SegmentId, out var segment))
            {
                if (!segment.SensorPositions.Contains(config.PositionOnSegment))
                {
                    segment.SensorPositions.Add(config.PositionOnSegment);
                }
            }

            Debug.Log($"[Conveyor] Created station: {config.StationId} ({config.Type})");
            return station;
        }

        public void ProcessAtStation(string stationId, string itemId)
        {
            if (!stations.TryGetValue(stationId, out var station)) return;
            if (!trackedItems.TryGetValue(itemId, out var item)) return;

            station.IsOccupied = true;
            station.CurrentItemId = itemId;
            item.Status = ItemStatus.AtStation;

            StartCoroutine(ProcessStationCoroutine(station, item));
        }

        private IEnumerator ProcessStationCoroutine(ConveyorStation station, ConveyorItem item)
        {
            yield return new WaitForSeconds(station.ProcessTime);

            station.IsOccupied = false;
            station.CurrentItemId = null;
            item.Status = ItemStatus.OnConveyor;
            station.ItemsProcessed++;

            Debug.Log($"[Conveyor] Station {station.StationId} processed item {item.ItemId}");
        }

        public void ReleaseFromStation(string stationId)
        {
            if (stations.TryGetValue(stationId, out var station))
            {
                station.IsOccupied = false;
                station.CurrentItemId = null;
            }
        }

        #endregion

        #region Junctions & Routing

        public ConveyorJunction CreateJunction(JunctionConfig config)
        {
            var junction = new ConveyorJunction
            {
                JunctionId = config.JunctionId,
                Name = config.Name,
                Type = config.Type,
                Position = config.Position,
                InputSegments = config.InputSegments,
                OutputSegments = config.OutputSegments,
                RoutingRules = config.RoutingRules ?? new List<RoutingRule>(),
                DefaultOutput = config.DefaultOutput
            };

            junctions[config.JunctionId] = junction;

            Debug.Log($"[Conveyor] Created junction: {config.JunctionId} ({config.Type})");
            return junction;
        }

        public string RouteItem(string junctionId, ConveyorItem item)
        {
            if (!junctions.TryGetValue(junctionId, out var junction))
            {
                return null;
            }

            string selectedOutput = junction.DefaultOutput;

            // Evaluate routing rules
            foreach (var rule in junction.RoutingRules)
            {
                if (EvaluateRoutingRule(rule, item))
                {
                    selectedOutput = rule.OutputSegmentId;
                    break;
                }
            }

            var decision = new RoutingDecision
            {
                JunctionId = junctionId,
                ItemId = item.ItemId,
                SelectedOutput = selectedOutput,
                Timestamp = DateTime.Now
            };

            OnRoutingDecision?.Invoke(decision);
            statistics.RoutingDecisions++;

            return selectedOutput;
        }

        private bool EvaluateRoutingRule(RoutingRule rule, ConveyorItem item)
        {
            // Check property condition
            if (!string.IsNullOrEmpty(rule.PropertyName))
            {
                if (!item.Properties.TryGetValue(rule.PropertyName, out var value))
                {
                    return false;
                }

                switch (rule.Operator)
                {
                    case RuleOperator.Equals:
                        return value?.ToString() == rule.Value?.ToString();
                    case RuleOperator.NotEquals:
                        return value?.ToString() != rule.Value?.ToString();
                    case RuleOperator.Contains:
                        return value?.ToString()?.Contains(rule.Value?.ToString() ?? "") ?? false;
                    case RuleOperator.GreaterThan:
                        return Convert.ToDouble(value) > Convert.ToDouble(rule.Value);
                    case RuleOperator.LessThan:
                        return Convert.ToDouble(value) < Convert.ToDouble(rule.Value);
                }
            }

            return true;
        }

        #endregion

        #region Faults

        public void SetFault(string segmentId, string faultCode, string message)
        {
            if (segments.TryGetValue(segmentId, out var segment))
            {
                segment.HasFault = true;
                segment.FaultCode = faultCode;
                segment.FaultMessage = message;
                segment.IsRunning = false;

                OnConveyorFault?.Invoke(segment, faultCode);
                LogAuditEvent("CONVEYOR_FAULT", $"{segmentId}: {faultCode} - {message}", AuditSeverity.Warning);
                Debug.LogWarning($"[Conveyor] Fault on {segmentId}: {faultCode}");
            }
        }

        public void ClearFault(string segmentId)
        {
            if (segments.TryGetValue(segmentId, out var segment))
            {
                segment.HasFault = false;
                segment.FaultCode = null;
                segment.FaultMessage = null;

                LogAuditEvent("CONVEYOR_FAULT_CLEAR", $"Fault cleared on {segmentId}");
                Debug.Log($"[Conveyor] Fault cleared on {segmentId}");
            }
        }

        #endregion

        #region Physics Update

        private void UpdateConveyors()
        {
            float dt = 1f / physicsUpdateRate;

            foreach (var segment in segments.Values)
            {
                if (!segment.IsRunning) continue;

                // Move items on this segment
                foreach (var itemId in segment.ItemsOnSegment.ToList())
                {
                    if (!trackedItems.TryGetValue(itemId, out var item)) continue;
                    if (item.Status != ItemStatus.OnConveyor) continue;

                    // Update position
                    item.PositionOnSegment += segment.Speed * dt;

                    // Check for station triggers
                    foreach (var sensorPos in segment.SensorPositions)
                    {
                        if (item.PositionOnSegment >= sensorPos &&
                            item.PositionOnSegment - segment.Speed * dt < sensorPos)
                        {
                            // Item passed sensor
                            CheckStationTrigger(segment.SegmentId, sensorPos, item);
                        }
                    }

                    // Move physical object
                    if (item.GameObject != null)
                    {
                        Vector3 targetPos = Vector3.Lerp(
                            segment.StartPosition,
                            segment.EndPosition,
                            item.PositionOnSegment / segment.Length
                        );
                        targetPos.y = item.GameObject.transform.position.y;
                        item.GameObject.transform.position = targetPos;
                    }

                    // Check for junction
                    if (item.PositionOnSegment >= segment.Length)
                    {
                        HandleSegmentExit(segment, item);
                    }
                }

                // Update belt animation
                UpdateBeltAnimation(segment, dt);
            }
        }

        private void CheckStationTrigger(string segmentId, float position, ConveyorItem item)
        {
            var station = stations.Values.FirstOrDefault(s =>
                s.SegmentId == segmentId &&
                Mathf.Approximately(s.PositionOnSegment, position));

            if (station != null)
            {
                OnItemAtStation?.Invoke(segments[segmentId], item);

                if (station.AutoProcess && !station.IsOccupied)
                {
                    ProcessAtStation(station.StationId, item.ItemId);
                }
            }
        }

        private void HandleSegmentExit(ConveyorSegment segment, ConveyorItem item)
        {
            // Find connected junction or segment
            var junction = junctions.Values.FirstOrDefault(j =>
                j.InputSegments.Contains(segment.SegmentId));

            if (junction != null)
            {
                string nextSegmentId = RouteItem(junction.JunctionId, item);
                if (!string.IsNullOrEmpty(nextSegmentId) && segments.TryGetValue(nextSegmentId, out var nextSegment))
                {
                    TransferItemToSegment(item, segment, nextSegment);
                }
            }
            else
            {
                // End of line - untrack or recirculate
                item.Status = ItemStatus.Completed;
                segment.ItemsOnSegment.Remove(item.ItemId);
                statistics.ItemsCompleted++;
            }
        }

        private void TransferItemToSegment(ConveyorItem item, ConveyorSegment from, ConveyorSegment to)
        {
            from.ItemsOnSegment.Remove(item.ItemId);
            to.ItemsOnSegment.Add(item.ItemId);
            item.CurrentSegmentId = to.SegmentId;
            item.PositionOnSegment = 0f;
            item.Route.Add(to.SegmentId);

            OnItemExited?.Invoke(from, item);
            OnItemEntered?.Invoke(to, item);
        }

        private void UpdateBeltAnimation(ConveyorSegment segment, float dt)
        {
            // Scroll texture to simulate belt movement
            if (segment.VisualObject != null)
            {
                var renderer = segment.VisualObject.GetComponent<Renderer>();
                if (renderer != null && renderer.material != null)
                {
                    Vector2 offset = renderer.material.mainTextureOffset;
                    offset.y += segment.Speed * dt * 0.5f;
                    renderer.material.mainTextureOffset = offset;
                }
            }
        }

        #endregion

        #region Statistics

        public ConveyorStatistics GetStatistics()
        {
            statistics.TotalSegments = segments.Count;
            statistics.ActiveSegments = segments.Values.Count(s => s.IsRunning);
            statistics.TotalStations = stations.Count;
            statistics.OccupiedStations = stations.Values.Count(s => s.IsOccupied);
            statistics.ItemsInSystem = trackedItems.Count;
            statistics.FaultedSegments = segments.Values.Count(s => s.HasFault);
            return statistics;
        }

        #endregion

        #region Audit

        private void LogAuditEvent(string action, string description, AuditSeverity severity = AuditSeverity.Info)
        {
            if (AuditTrailSystem.Instance != null)
            {
                AuditTrailSystem.Instance.LogSystemEvent(action, description, severity);
            }
        }

        #endregion
    }

    #region Trigger Handler

    public class ConveyorTriggerHandler : MonoBehaviour
    {
        private ConveyorSystem system;
        private ConveyorSegment segment;

        public void Initialize(ConveyorSystem conveyorSystem, ConveyorSegment conveyorSegment)
        {
            system = conveyorSystem;
            segment = conveyorSegment;
        }

        private void OnTriggerEnter(Collider other)
        {
            system?.OnItemEnteredSegment(segment, other.gameObject);
        }

        private void OnTriggerExit(Collider other)
        {
            system?.OnItemExitedSegment(segment, other.gameObject);
        }
    }

    #endregion

    #region Data Classes

    [Serializable]
    public class ConveyorConfig
    {
        public string SegmentId;
        public string Name;
        public ConveyorType Type = ConveyorType.Belt;
        public Vector3 StartPosition;
        public Vector3 EndPosition;
        public float Width = 0.5f;
        public float Speed;
        public bool IsBidirectional;
        public List<float> SensorPositions;
    }

    public enum ConveyorType
    {
        Belt,
        Roller,
        Chain,
        Pneumatic,
        Gravity
    }

    [Serializable]
    public class ConveyorSegment
    {
        public string SegmentId;
        public string Name;
        public ConveyorType Type;
        public GameObject GameObject;
        public GameObject VisualObject;
        public Vector3 StartPosition;
        public Vector3 EndPosition;
        public Vector3 Direction;
        public float Length;
        public float Width;
        public float Speed;
        public bool IsRunning;
        public bool IsBidirectional;
        public bool HasFault;
        public string FaultCode;
        public string FaultMessage;
        public List<string> ItemsOnSegment;
        public List<float> SensorPositions;
    }

    [Serializable]
    public class ConveyorItem
    {
        public string ItemId;
        public GameObject GameObject;
        public string CurrentSegmentId;
        public float PositionOnSegment;
        public DateTime EntryTime;
        public ItemStatus Status;
        public List<string> Route;
        public Dictionary<string, object> Properties;
    }

    public enum ItemStatus
    {
        OnConveyor,
        AtStation,
        Waiting,
        Processing,
        Completed,
        Rejected
    }

    [Serializable]
    public class StationConfig
    {
        public string StationId;
        public string Name;
        public StationType Type;
        public string SegmentId;
        public float PositionOnSegment;
        public float ProcessTime = 1f;
        public bool AutoProcess = true;
    }

    public enum StationType
    {
        Pickup,
        Dropoff,
        Inspection,
        Processing,
        Labeling,
        Weighing,
        Sorting
    }

    [Serializable]
    public class ConveyorStation
    {
        public string StationId;
        public string Name;
        public StationType Type;
        public string SegmentId;
        public float PositionOnSegment;
        public float ProcessTime;
        public bool AutoProcess;
        public bool IsOccupied;
        public string CurrentItemId;
        public Queue<string> Queue;
        public int ItemsProcessed;
    }

    [Serializable]
    public class JunctionConfig
    {
        public string JunctionId;
        public string Name;
        public JunctionType Type;
        public Vector3 Position;
        public List<string> InputSegments;
        public List<string> OutputSegments;
        public List<RoutingRule> RoutingRules;
        public string DefaultOutput;
    }

    public enum JunctionType
    {
        Merge,
        Split,
        Diverter,
        Turntable,
        Transfer
    }

    [Serializable]
    public class ConveyorJunction
    {
        public string JunctionId;
        public string Name;
        public JunctionType Type;
        public Vector3 Position;
        public List<string> InputSegments;
        public List<string> OutputSegments;
        public List<RoutingRule> RoutingRules;
        public string DefaultOutput;
        public string CurrentOutput;
    }

    [Serializable]
    public class RoutingRule
    {
        public string RuleName;
        public int Priority;
        public string PropertyName;
        public RuleOperator Operator;
        public object Value;
        public string OutputSegmentId;
    }

    public enum RuleOperator
    {
        Equals,
        NotEquals,
        Contains,
        GreaterThan,
        LessThan
    }

    [Serializable]
    public class RoutingDecision
    {
        public string JunctionId;
        public string ItemId;
        public string SelectedOutput;
        public DateTime Timestamp;
    }

    [Serializable]
    public class ConveyorStatistics
    {
        public int TotalSegments;
        public int ActiveSegments;
        public int FaultedSegments;
        public int TotalStations;
        public int OccupiedStations;
        public int ItemsInSystem;
        public int TotalItemsTracked;
        public int ItemsCompleted;
        public int ItemTransfers;
        public int RoutingDecisions;
    }

    #endregion
}
