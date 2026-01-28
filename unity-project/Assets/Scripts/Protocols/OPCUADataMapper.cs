using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Protocols
{
    /// <summary>
    /// Maps OPC UA variables to Unity digital twin entities.
    /// Provides bi-directional data mapping between OPC UA address space and Unity objects.
    /// Part of Feature 1.5: OPC UA Integration (HIGH PRIORITY)
    /// </summary>
    public class OPCUADataMapper : MonoBehaviour
    {
        [Header("Mapper Configuration")]
        [SerializeField] private bool autoUpdate = true;
        [SerializeField] private float updateInterval = 0.1f; // 10Hz
        [SerializeField] private Transform machineTransform;

        [Header("Node Mappings")]
        [SerializeField] private List<NodeMapping> positionMappings = new List<NodeMapping>();
        [SerializeField] private List<NodeMapping> statusMappings = new List<NodeMapping>();
        [SerializeField] private List<NodeMapping> parameterMappings = new List<NodeMapping>();

        // OPC UA client reference
        private OPCUAClient opcuaClient;

        // Mapping state
        private float updateTimer = 0f;
        private Dictionary<string, MappedValue> mappedValues = new Dictionary<string, MappedValue>();

        // Statistics
        private int totalMappings = 0;
        private int activeMappings = 0;
        private int failedMappings = 0;
        private DateTime lastUpdate;

        // Events
        public event Action<string, object> OnMappedValueUpdated;

        void Start()
        {
            opcuaClient = GetComponent<OPCUAClient>();
            if (opcuaClient == null)
            {
                Debug.LogError("[OPCUAMapper] OPCUAClient not found!");
                return;
            }

            // Subscribe to client events
            opcuaClient.OnConnected += HandleConnected;
            opcuaClient.OnNodeValueChanged += HandleNodeValueChanged;

            InitializeMappings();
        }

        void Update()
        {
            if (!autoUpdate || !opcuaClient.IsConnected) return;

            updateTimer += Time.deltaTime;
            if (updateTimer >= updateInterval)
            {
                UpdateMappedValues();
                updateTimer = 0f;
            }
        }

        /// <summary>
        /// Initialize node mappings
        /// </summary>
        private void InitializeMappings()
        {
            // Default position mappings
            if (positionMappings.Count == 0)
            {
                positionMappings.Add(new NodeMapping
                {
                    NodeId = "ns=2;s=Machine.Position.X",
                    TargetProperty = "Position.x",
                    MappingType = MappingType.Float,
                    ScaleFactor = 1f,
                    Unit = "m"
                });

                positionMappings.Add(new NodeMapping
                {
                    NodeId = "ns=2;s=Machine.Position.Y",
                    TargetProperty = "Position.y",
                    MappingType = MappingType.Float,
                    ScaleFactor = 1f,
                    Unit = "m"
                });

                positionMappings.Add(new NodeMapping
                {
                    NodeId = "ns=2;s=Machine.Position.Z",
                    TargetProperty = "Position.z",
                    MappingType = MappingType.Float,
                    ScaleFactor = 1f,
                    Unit = "m"
                });
            }

            // Default status mappings
            if (statusMappings.Count == 0)
            {
                statusMappings.Add(new NodeMapping
                {
                    NodeId = "ns=2;s=Machine.Status",
                    TargetProperty = "Status",
                    MappingType = MappingType.String,
                    Unit = ""
                });

                statusMappings.Add(new NodeMapping
                {
                    NodeId = "ns=2;s=Machine.Spindle.Speed",
                    TargetProperty = "SpindleSpeed",
                    MappingType = MappingType.Float,
                    ScaleFactor = 1f,
                    Unit = "RPM"
                });
            }

            totalMappings = positionMappings.Count + statusMappings.Count + parameterMappings.Count;
            Debug.Log($"[OPCUAMapper] Initialized {totalMappings} node mappings");
        }

        /// <summary>
        /// Handle OPC UA client connected event
        /// </summary>
        private void HandleConnected()
        {
            Debug.Log("[OPCUAMapper] Client connected, subscribing to mapped nodes...");

            // Subscribe to all mapped nodes
            foreach (var mapping in positionMappings)
            {
                opcuaClient.SubscribeToNode(mapping.NodeId, mapping.TargetProperty);
            }

            foreach (var mapping in statusMappings)
            {
                opcuaClient.SubscribeToNode(mapping.NodeId, mapping.TargetProperty);
            }

            foreach (var mapping in parameterMappings)
            {
                opcuaClient.SubscribeToNode(mapping.NodeId, mapping.TargetProperty);
            }
        }

        /// <summary>
        /// Handle node value changed event
        /// </summary>
        private void HandleNodeValueChanged(string nodeId, object value)
        {
            // Find mapping for this node
            NodeMapping? mapping = FindMapping(nodeId);

            if (mapping.HasValue)
            {
                // Apply mapping
                ApplyMapping(mapping.Value, value);
            }
        }

        /// <summary>
        /// Find mapping for node ID
        /// </summary>
        private NodeMapping? FindMapping(string nodeId)
        {
            foreach (var mapping in positionMappings)
            {
                if (mapping.NodeId == nodeId)
                    return mapping;
            }

            foreach (var mapping in statusMappings)
            {
                if (mapping.NodeId == nodeId)
                    return mapping;
            }

            foreach (var mapping in parameterMappings)
            {
                if (mapping.NodeId == nodeId)
                    return mapping;
            }

            return null;
        }

        /// <summary>
        /// Apply mapping to Unity object
        /// </summary>
        private void ApplyMapping(NodeMapping mapping, object value)
        {
            try
            {
                object mappedValue = ConvertValue(value, mapping.MappingType, mapping.ScaleFactor);

                // Apply to target property
                if (machineTransform != null && mapping.TargetProperty.StartsWith("Position"))
                {
                    ApplyPositionMapping(mapping.TargetProperty, mappedValue);
                }

                // Store mapped value
                mappedValues[mapping.NodeId] = new MappedValue
                {
                    NodeId = mapping.NodeId,
                    TargetProperty = mapping.TargetProperty,
                    Value = mappedValue,
                    Timestamp = DateTime.UtcNow,
                    Unit = mapping.Unit
                };

                activeMappings++;
                lastUpdate = DateTime.UtcNow;

                OnMappedValueUpdated?.Invoke(mapping.TargetProperty, mappedValue);
            }
            catch (Exception e)
            {
                Debug.LogError($"[OPCUAMapper] Error applying mapping {mapping.TargetProperty}: {e.Message}");
                failedMappings++;
            }
        }

        /// <summary>
        /// Convert OPC UA value to target type
        /// </summary>
        private object ConvertValue(object value, MappingType targetType, float scaleFactor)
        {
            if (value == null) return null;

            switch (targetType)
            {
                case MappingType.Float:
                    return Convert.ToSingle(value) * scaleFactor;

                case MappingType.Int:
                    return Convert.ToInt32(value);

                case MappingType.Bool:
                    return Convert.ToBoolean(value);

                case MappingType.String:
                    return value.ToString();

                case MappingType.Vector3:
                    // Assume value is array or comma-separated string
                    if (value is float[] floatArray && floatArray.Length >= 3)
                    {
                        return new Vector3(floatArray[0], floatArray[1], floatArray[2]) * scaleFactor;
                    }
                    break;

                default:
                    return value;
            }

            return value;
        }

        /// <summary>
        /// Apply position mapping to machine transform
        /// </summary>
        private void ApplyPositionMapping(string property, object value)
        {
            if (machineTransform == null || !(value is float floatValue))
                return;

            Vector3 currentPos = machineTransform.position;

            if (property.EndsWith(".x"))
            {
                currentPos.x = floatValue;
            }
            else if (property.EndsWith(".y"))
            {
                currentPos.y = floatValue;
            }
            else if (property.EndsWith(".z"))
            {
                currentPos.z = floatValue;
            }

            machineTransform.position = currentPos;
        }

        /// <summary>
        /// Update all mapped values
        /// </summary>
        private void UpdateMappedValues()
        {
            if (!opcuaClient.IsConnected) return;

            // Read current values for all mappings
            foreach (var mapping in positionMappings)
            {
                object value = opcuaClient.GetNodeValue(mapping.NodeId);
                if (value != null)
                {
                    ApplyMapping(mapping, value);
                }
            }
        }

        /// <summary>
        /// Write value to OPC UA node
        /// </summary>
        public bool WriteToNode(string targetProperty, object value)
        {
            // Find node for this property
            string nodeId = FindNodeIdForProperty(targetProperty);

            if (!string.IsNullOrEmpty(nodeId))
            {
                return opcuaClient.WriteNode(nodeId, value);
            }

            Debug.LogWarning($"[OPCUAMapper] No mapping found for property: {targetProperty}");
            return false;
        }

        /// <summary>
        /// Find node ID for target property
        /// </summary>
        private string FindNodeIdForProperty(string targetProperty)
        {
            foreach (var mapping in positionMappings)
            {
                if (mapping.TargetProperty == targetProperty)
                    return mapping.NodeId;
            }

            foreach (var mapping in statusMappings)
            {
                if (mapping.TargetProperty == targetProperty)
                    return mapping.NodeId;
            }

            foreach (var mapping in parameterMappings)
            {
                if (mapping.TargetProperty == targetProperty)
                    return mapping.NodeId;
            }

            return null;
        }

        /// <summary>
        /// Get mapped value for property
        /// </summary>
        public object GetMappedValue(string targetProperty)
        {
            foreach (var kvp in mappedValues.Values)
            {
                if (kvp.TargetProperty == targetProperty)
                {
                    return kvp.Value;
                }
            }

            return null;
        }

        /// <summary>
        /// Get mapper statistics
        /// </summary>
        public MapperStatistics GetStatistics()
        {
            return new MapperStatistics
            {
                TotalMappings = totalMappings,
                ActiveMappings = activeMappings,
                FailedMappings = failedMappings,
                MappedValues = mappedValues.Count,
                LastUpdate = lastUpdate,
                UpdateInterval = updateInterval
            };
        }

        void OnDestroy()
        {
            if (opcuaClient != null)
            {
                opcuaClient.OnConnected -= HandleConnected;
                opcuaClient.OnNodeValueChanged -= HandleNodeValueChanged;
            }
        }

        #region Public Properties

        public int TotalMappings => totalMappings;
        public int ActiveMappings => activeMappings;
        public bool IsAutoUpdate => autoUpdate;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Node mapping configuration
    /// </summary>
    [Serializable]
    public struct NodeMapping
    {
        public string NodeId;
        public string TargetProperty;
        public MappingType MappingType;
        public float ScaleFactor;
        public string Unit;
    }

    /// <summary>
    /// Mapping type enumeration
    /// </summary>
    public enum MappingType
    {
        Float,
        Int,
        Bool,
        String,
        Vector3,
        Quaternion
    }

    /// <summary>
    /// Mapped value storage
    /// </summary>
    public struct MappedValue
    {
        public string NodeId;
        public string TargetProperty;
        public object Value;
        public DateTime Timestamp;
        public string Unit;
    }

    /// <summary>
    /// Mapper statistics
    /// </summary>
    [Serializable]
    public struct MapperStatistics
    {
        public int TotalMappings;
        public int ActiveMappings;
        public int FailedMappings;
        public int MappedValues;
        public DateTime LastUpdate;
        public float UpdateInterval;
    }

    #endregion
}
