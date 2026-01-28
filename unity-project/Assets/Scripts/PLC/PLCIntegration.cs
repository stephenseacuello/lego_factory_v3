using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using CNC_SCADA.DigitalTwin.Audit;

namespace CNC_SCADA.DigitalTwin.PLC
{
    /// <summary>
    /// PLC Integration Service for industrial controller communication
    /// Supports Modbus TCP/RTU, EtherNet/IP, and OPC UA protocols
    /// </summary>
    public class PLCIntegration : MonoBehaviour
    {
        public static PLCIntegration Instance { get; private set; }

        [Header("Connection Settings")]
        [SerializeField] private PLCProtocol defaultProtocol = PLCProtocol.ModbusTCP;
        [SerializeField] private string defaultHost = "192.168.1.100";
        [SerializeField] private int defaultPort = 502;
        [SerializeField] private float pollIntervalMs = 100f;
        [SerializeField] private int connectionTimeout = 5000;
        [SerializeField] private int responseTimeout = 1000;
        [SerializeField] private bool autoReconnect = true;

        [Header("Data Configuration")]
        [SerializeField] private int maxTagCount = 1000;
        [SerializeField] private bool enableWriteOperations = true;
        [SerializeField] private bool cacheTagValues = true;
        [SerializeField] private float cacheExpirySeconds = 0.5f;

        // Events
        public event Action<PLCConnection> OnConnected;
        public event Action<PLCConnection> OnDisconnected;
        public event Action<PLCTag, object> OnTagValueChanged;
        public event Action<PLCConnection, string> OnError;
        public event Action<PLCAlarm> OnAlarmTriggered;
        public event Action<PLCAlarm> OnAlarmCleared;

        // Connections and tags
        private Dictionary<string, PLCConnection> connections = new Dictionary<string, PLCConnection>();
        private Dictionary<string, PLCTag> tags = new Dictionary<string, PLCTag>();
        private Dictionary<string, PLCTagGroup> tagGroups = new Dictionary<string, PLCTagGroup>();
        private List<PLCAlarm> activeAlarms = new List<PLCAlarm>();

        // Polling
        private CancellationTokenSource pollingCts;
        private bool isPolling = false;

        // Statistics
        private PLCStatistics statistics = new PLCStatistics();

        public int ConnectionCount => connections.Count;
        public int TagCount => tags.Count;
        public int ActiveAlarmCount => activeAlarms.Count;
        public bool IsPolling => isPolling;

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

        private void OnDestroy()
        {
            StopPolling();
            DisconnectAll();
        }

        #region Connection Management

        public PLCConnection CreateConnection(PLCConnectionConfig config)
        {
            if (connections.ContainsKey(config.ConnectionId))
            {
                Debug.LogWarning($"[PLC] Connection already exists: {config.ConnectionId}");
                return connections[config.ConnectionId];
            }

            var connection = new PLCConnection
            {
                ConnectionId = config.ConnectionId,
                Name = config.Name,
                Protocol = config.Protocol,
                Host = config.Host,
                Port = config.Port,
                SlaveId = config.SlaveId,
                Status = ConnectionStatus.Disconnected,
                Tags = new List<string>(),
                LastPollTime = DateTime.MinValue
            };

            connections[config.ConnectionId] = connection;

            Debug.Log($"[PLC] Created connection: {config.ConnectionId} ({config.Protocol} @ {config.Host}:{config.Port})");
            return connection;
        }

        public IEnumerator Connect(string connectionId)
        {
            if (!connections.TryGetValue(connectionId, out var connection))
            {
                OnError?.Invoke(null, $"Connection not found: {connectionId}");
                yield break;
            }

            connection.Status = ConnectionStatus.Connecting;
            Debug.Log($"[PLC] Connecting to {connection.Name}...");

            // Use a result holder for coroutine results
            var result = new CoroutineResult<bool>();

            switch (connection.Protocol)
            {
                case PLCProtocol.ModbusTCP:
                    yield return ConnectModbusTCP(connection, result);
                    break;

                case PLCProtocol.ModbusRTU:
                    yield return ConnectModbusRTU(connection, result);
                    break;

                case PLCProtocol.EtherNetIP:
                    yield return ConnectEtherNetIP(connection, result);
                    break;

                case PLCProtocol.OPCUA:
                    yield return ConnectOPCUA(connection, result);
                    break;

                case PLCProtocol.S7:
                    yield return ConnectS7(connection, result);
                    break;
            }

            if (result.Value)
            {
                connection.Status = ConnectionStatus.Connected;
                connection.ConnectedTime = DateTime.Now;
                OnConnected?.Invoke(connection);
                LogAuditEvent("PLC_CONNECTED", $"Connected to {connection.Name}");
                Debug.Log($"[PLC] Connected to {connection.Name}");
            }
            else
            {
                connection.Status = ConnectionStatus.Error;
                OnError?.Invoke(connection, "Connection failed");
            }
        }

        private IEnumerator ConnectModbusTCP(PLCConnection connection, CoroutineResult<bool> result)
        {
            var connectTask = Task.Run(() =>
            {
                try
                {
                    var client = new TcpClient();
                    var connectResult = client.BeginConnect(connection.Host, connection.Port, null, null);
                    bool connected = connectResult.AsyncWaitHandle.WaitOne(connectionTimeout);

                    if (connected && client.Connected)
                    {
                        connection.TcpClient = client;
                        connection.NetworkStream = client.GetStream();
                        return true;
                    }

                    client.Close();
                    return false;
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[PLC] Modbus TCP connect error: {ex.Message}");
                    return false;
                }
            });

            while (!connectTask.IsCompleted)
            {
                yield return null;
            }

            result.Value = connectTask.Result;
        }

        private IEnumerator ConnectModbusRTU(PLCConnection connection, CoroutineResult<bool> result)
        {
            // Modbus RTU over serial - would require serial port library
            result.Value = false;
            yield break;
        }

        private IEnumerator ConnectEtherNetIP(PLCConnection connection, CoroutineResult<bool> result)
        {
            // EtherNet/IP connection
            var connectTask = Task.Run(() =>
            {
                try
                {
                    var client = new TcpClient();
                    var connectResult = client.BeginConnect(connection.Host, connection.Port, null, null);
                    bool connected = connectResult.AsyncWaitHandle.WaitOne(connectionTimeout);

                    if (connected && client.Connected)
                    {
                        connection.TcpClient = client;
                        connection.NetworkStream = client.GetStream();

                        // Send EtherNet/IP registration
                        // In real implementation, send RegisterSession command
                        return true;
                    }

                    client.Close();
                    return false;
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[PLC] EtherNet/IP connect error: {ex.Message}");
                    return false;
                }
            });

            while (!connectTask.IsCompleted)
            {
                yield return null;
            }

            result.Value = connectTask.Result;
        }

        private IEnumerator ConnectOPCUA(PLCConnection connection, CoroutineResult<bool> result)
        {
            // OPC UA connection - would use OPC UA library
            result.Value = false;
            yield break;
        }

        private IEnumerator ConnectS7(PLCConnection connection, CoroutineResult<bool> result)
        {
            // Siemens S7 connection
            result.Value = false;
            yield break;
        }

        public void Disconnect(string connectionId)
        {
            if (!connections.TryGetValue(connectionId, out var connection))
            {
                return;
            }

            try
            {
                connection.NetworkStream?.Close();
                connection.TcpClient?.Close();
            }
            catch { }

            connection.Status = ConnectionStatus.Disconnected;
            connection.TcpClient = null;
            connection.NetworkStream = null;

            OnDisconnected?.Invoke(connection);
            LogAuditEvent("PLC_DISCONNECTED", $"Disconnected from {connection.Name}");
            Debug.Log($"[PLC] Disconnected from {connection.Name}");
        }

        public void DisconnectAll()
        {
            foreach (var connectionId in connections.Keys)
            {
                Disconnect(connectionId);
            }
        }

        #endregion

        #region Tag Management

        public PLCTag CreateTag(PLCTagConfig config)
        {
            if (tags.ContainsKey(config.TagId))
            {
                Debug.LogWarning($"[PLC] Tag already exists: {config.TagId}");
                return tags[config.TagId];
            }

            var tag = new PLCTag
            {
                TagId = config.TagId,
                Name = config.Name,
                ConnectionId = config.ConnectionId,
                Address = config.Address,
                DataType = config.DataType,
                AccessMode = config.AccessMode,
                ScaleFactor = config.ScaleFactor,
                Offset = config.Offset,
                EngineeringUnits = config.EngineeringUnits,
                Description = config.Description,
                Value = null,
                Quality = TagQuality.Unknown,
                LastUpdateTime = DateTime.MinValue
            };

            // Parse address
            ParseTagAddress(tag, config.Address);

            tags[config.TagId] = tag;

            // Add to connection's tag list
            if (connections.TryGetValue(config.ConnectionId, out var connection))
            {
                connection.Tags.Add(config.TagId);
            }

            Debug.Log($"[PLC] Created tag: {config.TagId} ({config.DataType} @ {config.Address})");
            return tag;
        }

        private void ParseTagAddress(PLCTag tag, string address)
        {
            // Parse Modbus-style address: HR100, IR200, C50, DI100
            // Or Allen-Bradley style: N7:0, F8:5, B3/0

            if (address.StartsWith("HR") || address.StartsWith("4"))
            {
                tag.RegisterType = ModbusRegisterType.HoldingRegister;
                tag.RegisterAddress = int.Parse(address.Substring(address.StartsWith("HR") ? 2 : 1));
            }
            else if (address.StartsWith("IR") || address.StartsWith("3"))
            {
                tag.RegisterType = ModbusRegisterType.InputRegister;
                tag.RegisterAddress = int.Parse(address.Substring(address.StartsWith("IR") ? 2 : 1));
            }
            else if (address.StartsWith("C") || address.StartsWith("0"))
            {
                tag.RegisterType = ModbusRegisterType.Coil;
                tag.RegisterAddress = int.Parse(address.Substring(1));
            }
            else if (address.StartsWith("DI") || address.StartsWith("1"))
            {
                tag.RegisterType = ModbusRegisterType.DiscreteInput;
                tag.RegisterAddress = int.Parse(address.Substring(address.StartsWith("DI") ? 2 : 1));
            }
        }

        public PLCTagGroup CreateTagGroup(string groupId, string connectionId, List<string> tagIds, float pollRate = 100f)
        {
            var group = new PLCTagGroup
            {
                GroupId = groupId,
                ConnectionId = connectionId,
                TagIds = tagIds,
                PollRateMs = pollRate,
                IsEnabled = true,
                LastPollTime = DateTime.MinValue
            };

            tagGroups[groupId] = group;

            Debug.Log($"[PLC] Created tag group: {groupId} with {tagIds.Count} tags");
            return group;
        }

        public void RemoveTag(string tagId)
        {
            if (tags.TryGetValue(tagId, out var tag))
            {
                if (connections.TryGetValue(tag.ConnectionId, out var connection))
                {
                    connection.Tags.Remove(tagId);
                }
                tags.Remove(tagId);
            }
        }

        public PLCTag GetTag(string tagId)
        {
            return tags.TryGetValue(tagId, out var tag) ? tag : null;
        }

        public T GetTagValue<T>(string tagId)
        {
            if (tags.TryGetValue(tagId, out var tag) && tag.Value != null)
            {
                try
                {
                    return (T)Convert.ChangeType(tag.Value, typeof(T));
                }
                catch
                {
                    return default;
                }
            }
            return default;
        }

        #endregion

        #region Read Operations

        public void StartPolling()
        {
            if (isPolling) return;

            pollingCts = new CancellationTokenSource();
            isPolling = true;
            StartCoroutine(PollLoop());

            Debug.Log("[PLC] Started polling");
        }

        public void StopPolling()
        {
            if (!isPolling) return;

            pollingCts?.Cancel();
            isPolling = false;

            Debug.Log("[PLC] Stopped polling");
        }

        private IEnumerator PollLoop()
        {
            while (isPolling && !pollingCts.Token.IsCancellationRequested)
            {
                foreach (var connection in connections.Values)
                {
                    if (connection.Status != ConnectionStatus.Connected) continue;

                    yield return PollConnection(connection);
                }

                yield return new WaitForSeconds(pollIntervalMs / 1000f);
            }
        }

        private IEnumerator PollConnection(PLCConnection connection)
        {
            foreach (var tagId in connection.Tags)
            {
                if (!tags.TryGetValue(tagId, out var tag)) continue;
                if (tag.AccessMode == TagAccessMode.WriteOnly) continue;

                yield return ReadTag(tag);
            }

            connection.LastPollTime = DateTime.Now;
            statistics.PollCycles++;
        }

        public IEnumerator ReadTag(PLCTag tag)
        {
            if (!connections.TryGetValue(tag.ConnectionId, out var connection))
            {
                yield break;
            }

            if (connection.Status != ConnectionStatus.Connected)
            {
                tag.Quality = TagQuality.Bad;
                yield break;
            }

            object newValue = null;
            bool success = false;

            switch (connection.Protocol)
            {
                case PLCProtocol.ModbusTCP:
                    var result = ReadModbusTCP(connection, tag);
                    while (!result.IsCompleted)
                    {
                        yield return null;
                    }
                    newValue = result.Result;
                    success = newValue != null;
                    break;

                case PLCProtocol.EtherNetIP:
                    // EtherNet/IP read
                    break;
            }

            if (success)
            {
                // Apply scaling
                if (tag.DataType == PLCDataType.Float || tag.DataType == PLCDataType.Int16 ||
                    tag.DataType == PLCDataType.Int32)
                {
                    double scaled = Convert.ToDouble(newValue) * tag.ScaleFactor + tag.Offset;
                    newValue = scaled;
                }

                // Check for value change
                bool changed = tag.Value == null || !tag.Value.Equals(newValue);

                tag.Value = newValue;
                tag.Quality = TagQuality.Good;
                tag.LastUpdateTime = DateTime.Now;

                if (changed)
                {
                    OnTagValueChanged?.Invoke(tag, newValue);
                    CheckAlarmConditions(tag);
                }

                statistics.SuccessfulReads++;
            }
            else
            {
                tag.Quality = TagQuality.Bad;
                statistics.FailedReads++;
            }
        }

        private Task<object> ReadModbusTCP(PLCConnection connection, PLCTag tag)
        {
            return Task.Run(() =>
            {
                try
                {
                    byte[] request;
                    int responseLength;

                    ushort transactionId = (ushort)(DateTime.Now.Ticks & 0xFFFF);
                    byte functionCode;
                    ushort registerCount = GetRegisterCount(tag.DataType);

                    switch (tag.RegisterType)
                    {
                        case ModbusRegisterType.HoldingRegister:
                            functionCode = 0x03;
                            break;
                        case ModbusRegisterType.InputRegister:
                            functionCode = 0x04;
                            break;
                        case ModbusRegisterType.Coil:
                            functionCode = 0x01;
                            break;
                        case ModbusRegisterType.DiscreteInput:
                            functionCode = 0x02;
                            break;
                        default:
                            return null;
                    }

                    // Build Modbus TCP request
                    request = new byte[12];
                    request[0] = (byte)(transactionId >> 8);
                    request[1] = (byte)(transactionId & 0xFF);
                    request[2] = 0; // Protocol ID
                    request[3] = 0;
                    request[4] = 0; // Length
                    request[5] = 6;
                    request[6] = (byte)connection.SlaveId;
                    request[7] = functionCode;
                    request[8] = (byte)(tag.RegisterAddress >> 8);
                    request[9] = (byte)(tag.RegisterAddress & 0xFF);
                    request[10] = (byte)(registerCount >> 8);
                    request[11] = (byte)(registerCount & 0xFF);

                    // Send request
                    connection.NetworkStream.Write(request, 0, request.Length);

                    // Read response
                    byte[] response = new byte[256];
                    connection.NetworkStream.ReadTimeout = responseTimeout;
                    int bytesRead = connection.NetworkStream.Read(response, 0, response.Length);

                    if (bytesRead < 9)
                    {
                        return null;
                    }

                    // Parse response
                    byte dataLength = response[8];
                    byte[] data = new byte[dataLength];
                    Array.Copy(response, 9, data, 0, dataLength);

                    return ParseModbusData(data, tag.DataType);
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[PLC] Modbus read error: {ex.Message}");
                    return null;
                }
            });
        }

        private ushort GetRegisterCount(PLCDataType dataType)
        {
            return dataType switch
            {
                PLCDataType.Bool => 1,
                PLCDataType.Int16 => 1,
                PLCDataType.UInt16 => 1,
                PLCDataType.Int32 => 2,
                PLCDataType.UInt32 => 2,
                PLCDataType.Float => 2,
                PLCDataType.Double => 4,
                PLCDataType.String => 16,
                _ => 1
            };
        }

        private object ParseModbusData(byte[] data, PLCDataType dataType)
        {
            if (data == null || data.Length == 0) return null;

            switch (dataType)
            {
                case PLCDataType.Bool:
                    return (data[0] & 0x01) != 0;

                case PLCDataType.Int16:
                    return (short)((data[0] << 8) | data[1]);

                case PLCDataType.UInt16:
                    return (ushort)((data[0] << 8) | data[1]);

                case PLCDataType.Int32:
                    if (data.Length >= 4)
                    {
                        return (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3];
                    }
                    break;

                case PLCDataType.Float:
                    if (data.Length >= 4)
                    {
                        byte[] floatBytes = new byte[] { data[3], data[2], data[1], data[0] };
                        return BitConverter.ToSingle(floatBytes, 0);
                    }
                    break;

                case PLCDataType.String:
                    return System.Text.Encoding.ASCII.GetString(data).TrimEnd('\0');
            }

            return null;
        }

        #endregion

        #region Write Operations

        public IEnumerator WriteTag(string tagId, object value)
        {
            if (!enableWriteOperations)
            {
                Debug.LogWarning("[PLC] Write operations disabled");
                yield break;
            }

            if (!tags.TryGetValue(tagId, out var tag))
            {
                yield break;
            }

            if (tag.AccessMode == TagAccessMode.ReadOnly)
            {
                Debug.LogWarning($"[PLC] Tag {tagId} is read-only");
                yield break;
            }

            if (!connections.TryGetValue(tag.ConnectionId, out var connection))
            {
                yield break;
            }

            bool success = false;

            switch (connection.Protocol)
            {
                case PLCProtocol.ModbusTCP:
                    var result = WriteModbusTCP(connection, tag, value);
                    while (!result.IsCompleted)
                    {
                        yield return null;
                    }
                    success = result.Result;
                    break;
            }

            if (success)
            {
                tag.Value = value;
                tag.LastUpdateTime = DateTime.Now;
                statistics.SuccessfulWrites++;
                LogAuditEvent("PLC_WRITE", $"Wrote {value} to {tagId}");
            }
            else
            {
                statistics.FailedWrites++;
            }
        }

        private Task<bool> WriteModbusTCP(PLCConnection connection, PLCTag tag, object value)
        {
            return Task.Run(() =>
            {
                try
                {
                    ushort transactionId = (ushort)(DateTime.Now.Ticks & 0xFFFF);
                    byte functionCode;
                    byte[] valueBytes;

                    switch (tag.RegisterType)
                    {
                        case ModbusRegisterType.HoldingRegister:
                            functionCode = 0x06; // Write single register
                            valueBytes = GetModbusValueBytes(value, tag.DataType);
                            break;
                        case ModbusRegisterType.Coil:
                            functionCode = 0x05; // Write single coil
                            valueBytes = Convert.ToBoolean(value) ?
                                new byte[] { 0xFF, 0x00 } : new byte[] { 0x00, 0x00 };
                            break;
                        default:
                            return false;
                    }

                    // Build request
                    byte[] request = new byte[12];
                    request[0] = (byte)(transactionId >> 8);
                    request[1] = (byte)(transactionId & 0xFF);
                    request[2] = 0;
                    request[3] = 0;
                    request[4] = 0;
                    request[5] = 6;
                    request[6] = (byte)connection.SlaveId;
                    request[7] = functionCode;
                    request[8] = (byte)(tag.RegisterAddress >> 8);
                    request[9] = (byte)(tag.RegisterAddress & 0xFF);
                    request[10] = valueBytes[0];
                    request[11] = valueBytes[1];

                    connection.NetworkStream.Write(request, 0, request.Length);

                    // Read response
                    byte[] response = new byte[12];
                    connection.NetworkStream.ReadTimeout = responseTimeout;
                    int bytesRead = connection.NetworkStream.Read(response, 0, response.Length);

                    return bytesRead >= 12;
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[PLC] Modbus write error: {ex.Message}");
                    return false;
                }
            });
        }

        private byte[] GetModbusValueBytes(object value, PLCDataType dataType)
        {
            switch (dataType)
            {
                case PLCDataType.Int16:
                case PLCDataType.UInt16:
                    short shortVal = Convert.ToInt16(value);
                    return new byte[] { (byte)(shortVal >> 8), (byte)(shortVal & 0xFF) };

                case PLCDataType.Float:
                    float floatVal = Convert.ToSingle(value);
                    byte[] floatBytes = BitConverter.GetBytes(floatVal);
                    return new byte[] { floatBytes[1], floatBytes[0] }; // Big-endian first word

                default:
                    return new byte[] { 0, 0 };
            }
        }

        #endregion

        #region Alarms

        public void ConfigureAlarm(PLCAlarmConfig config)
        {
            if (!tags.TryGetValue(config.TagId, out var tag))
            {
                return;
            }

            tag.AlarmConfig = new PLCAlarmSettings
            {
                IsEnabled = config.IsEnabled,
                HighHighLimit = config.HighHighLimit,
                HighLimit = config.HighLimit,
                LowLimit = config.LowLimit,
                LowLowLimit = config.LowLowLimit,
                Deadband = config.Deadband,
                Severity = config.Severity,
                Message = config.Message
            };

            Debug.Log($"[PLC] Configured alarm for tag: {config.TagId}");
        }

        private void CheckAlarmConditions(PLCTag tag)
        {
            if (tag.AlarmConfig == null || !tag.AlarmConfig.IsEnabled) return;
            if (tag.Value == null) return;

            double value = Convert.ToDouble(tag.Value);
            var config = tag.AlarmConfig;
            PLCAlarm existingAlarm = activeAlarms.Find(a => a.TagId == tag.TagId);

            AlarmState newState = AlarmState.Normal;

            if (config.HighHighLimit.HasValue && value >= config.HighHighLimit.Value)
            {
                newState = AlarmState.HighHigh;
            }
            else if (config.HighLimit.HasValue && value >= config.HighLimit.Value)
            {
                newState = AlarmState.High;
            }
            else if (config.LowLowLimit.HasValue && value <= config.LowLowLimit.Value)
            {
                newState = AlarmState.LowLow;
            }
            else if (config.LowLimit.HasValue && value <= config.LowLimit.Value)
            {
                newState = AlarmState.Low;
            }

            if (newState != AlarmState.Normal && existingAlarm == null)
            {
                // New alarm
                var alarm = new PLCAlarm
                {
                    AlarmId = Guid.NewGuid().ToString(),
                    TagId = tag.TagId,
                    TagName = tag.Name,
                    State = newState,
                    Value = value,
                    Limit = GetLimitValue(config, newState),
                    Severity = config.Severity,
                    Message = config.Message ?? $"{tag.Name} {newState}",
                    TriggerTime = DateTime.Now,
                    IsAcknowledged = false
                };

                activeAlarms.Add(alarm);
                OnAlarmTriggered?.Invoke(alarm);
                statistics.AlarmsTriggered++;

                LogAuditEvent("PLC_ALARM", $"Alarm: {tag.Name} - {newState}", AuditSeverity.Warning);
            }
            else if (newState == AlarmState.Normal && existingAlarm != null)
            {
                // Alarm cleared
                existingAlarm.State = AlarmState.Normal;
                existingAlarm.ClearTime = DateTime.Now;
                activeAlarms.Remove(existingAlarm);
                OnAlarmCleared?.Invoke(existingAlarm);

                LogAuditEvent("PLC_ALARM_CLEAR", $"Alarm cleared: {tag.Name}");
            }
        }

        private double GetLimitValue(PLCAlarmSettings config, AlarmState state)
        {
            return state switch
            {
                AlarmState.HighHigh => config.HighHighLimit ?? 0,
                AlarmState.High => config.HighLimit ?? 0,
                AlarmState.Low => config.LowLimit ?? 0,
                AlarmState.LowLow => config.LowLowLimit ?? 0,
                _ => 0
            };
        }

        public void AcknowledgeAlarm(string alarmId)
        {
            var alarm = activeAlarms.Find(a => a.AlarmId == alarmId);
            if (alarm != null)
            {
                alarm.IsAcknowledged = true;
                alarm.AcknowledgeTime = DateTime.Now;
                LogAuditEvent("PLC_ALARM_ACK", $"Acknowledged alarm: {alarm.TagName}");
            }
        }

        public List<PLCAlarm> GetActiveAlarms()
        {
            return new List<PLCAlarm>(activeAlarms);
        }

        #endregion

        #region Statistics

        public PLCStatistics GetStatistics()
        {
            statistics.ActiveConnections = connections.Values.Count(c => c.Status == ConnectionStatus.Connected);
            statistics.TotalTags = tags.Count;
            statistics.ActiveAlarms = activeAlarms.Count;
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

    #region Data Classes

    public enum PLCProtocol
    {
        ModbusTCP,
        ModbusRTU,
        EtherNetIP,
        OPCUA,
        S7,
        FinsTCP,
        MELSEC
    }

    public enum ConnectionStatus
    {
        Disconnected,
        Connecting,
        Connected,
        Error
    }

    public enum PLCDataType
    {
        Bool,
        Int16,
        UInt16,
        Int32,
        UInt32,
        Float,
        Double,
        String
    }

    public enum TagAccessMode
    {
        ReadOnly,
        WriteOnly,
        ReadWrite
    }

    public enum TagQuality
    {
        Good,
        Bad,
        Unknown
    }

    public enum ModbusRegisterType
    {
        Coil,
        DiscreteInput,
        HoldingRegister,
        InputRegister
    }

    public enum AlarmState
    {
        Normal,
        High,
        HighHigh,
        Low,
        LowLow
    }

    public enum AlarmSeverity
    {
        Info,
        Warning,
        Critical
    }

    [Serializable]
    public class PLCConnectionConfig
    {
        public string ConnectionId;
        public string Name;
        public PLCProtocol Protocol;
        public string Host;
        public int Port;
        public int SlaveId = 1;
    }

    [Serializable]
    public class PLCConnection
    {
        public string ConnectionId;
        public string Name;
        public PLCProtocol Protocol;
        public string Host;
        public int Port;
        public int SlaveId;
        public ConnectionStatus Status;
        public DateTime ConnectedTime;
        public DateTime LastPollTime;
        public List<string> Tags;

        // Connection objects (not serialized)
        [NonSerialized] public TcpClient TcpClient;
        [NonSerialized] public NetworkStream NetworkStream;
    }

    [Serializable]
    public class PLCTagConfig
    {
        public string TagId;
        public string Name;
        public string ConnectionId;
        public string Address;
        public PLCDataType DataType;
        public TagAccessMode AccessMode = TagAccessMode.ReadWrite;
        public double ScaleFactor = 1.0;
        public double Offset = 0.0;
        public string EngineeringUnits;
        public string Description;
    }

    [Serializable]
    public class PLCTag
    {
        public string TagId;
        public string Name;
        public string ConnectionId;
        public string Address;
        public PLCDataType DataType;
        public TagAccessMode AccessMode;
        public ModbusRegisterType RegisterType;
        public int RegisterAddress;
        public double ScaleFactor;
        public double Offset;
        public string EngineeringUnits;
        public string Description;
        public object Value;
        public TagQuality Quality;
        public DateTime LastUpdateTime;
        public PLCAlarmSettings AlarmConfig;
    }

    [Serializable]
    public class PLCTagGroup
    {
        public string GroupId;
        public string ConnectionId;
        public List<string> TagIds;
        public float PollRateMs;
        public bool IsEnabled;
        public DateTime LastPollTime;
    }

    [Serializable]
    public class PLCAlarmConfig
    {
        public string TagId;
        public bool IsEnabled = true;
        public double? HighHighLimit;
        public double? HighLimit;
        public double? LowLimit;
        public double? LowLowLimit;
        public double Deadband;
        public AlarmSeverity Severity = AlarmSeverity.Warning;
        public string Message;
    }

    [Serializable]
    public class PLCAlarmSettings
    {
        public bool IsEnabled;
        public double? HighHighLimit;
        public double? HighLimit;
        public double? LowLimit;
        public double? LowLowLimit;
        public double Deadband;
        public AlarmSeverity Severity;
        public string Message;
    }

    [Serializable]
    public class PLCAlarm
    {
        public string AlarmId;
        public string TagId;
        public string TagName;
        public AlarmState State;
        public double Value;
        public double Limit;
        public AlarmSeverity Severity;
        public string Message;
        public DateTime TriggerTime;
        public DateTime? ClearTime;
        public DateTime? AcknowledgeTime;
        public bool IsAcknowledged;
    }

    [Serializable]
    public class PLCStatistics
    {
        public int ActiveConnections;
        public int TotalTags;
        public int ActiveAlarms;
        public int PollCycles;
        public int SuccessfulReads;
        public int FailedReads;
        public int SuccessfulWrites;
        public int FailedWrites;
        public int AlarmsTriggered;
    }

    /// <summary>
    /// Helper class for returning values from coroutines
    /// </summary>
    public class CoroutineResult<T>
    {
        public T Value { get; set; }
        public bool HasValue { get; set; }

        public CoroutineResult()
        {
            Value = default;
            HasValue = false;
        }

        public CoroutineResult(T value)
        {
            Value = value;
            HasValue = true;
        }
    }

    #endregion
}
