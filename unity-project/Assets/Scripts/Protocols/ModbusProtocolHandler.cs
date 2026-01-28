using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace CNCDigitalTwin.Protocols
{
    /// <summary>
    /// Modbus TCP/RTU Protocol Handler for PLC Communication
    /// Implements Modbus protocol per IEC 61158 standard
    /// </summary>
    public class ModbusProtocolHandler : MonoBehaviour
    {
        public static ModbusProtocolHandler Instance { get; private set; }

        [Header("Connection Settings")]
        [SerializeField] private ConnectionMode connectionMode = ConnectionMode.TCP;
        [SerializeField] private string ipAddress = "192.168.1.100";
        [SerializeField] private int port = 502;
        [SerializeField] private string serialPort = "COM1";
        [SerializeField] private int baudRate = 9600;
        [SerializeField] private byte slaveAddress = 1;

        [Header("Communication Settings")]
        [SerializeField] private float pollInterval = 0.1f; // 100ms
        [SerializeField] private int timeout = 1000; // ms
        [SerializeField] private int maxRetries = 3;
        [SerializeField] private bool autoReconnect = true;

        // Connection state
        private TcpClient tcpClient;
        private NetworkStream networkStream;
        private bool isConnected = false;
        private ushort transactionId = 0;

        // Register maps
        private Dictionary<string, RegisterMap> registerMaps = new Dictionary<string, RegisterMap>();

        // Polling groups
        private Dictionary<string, PollingGroup> pollingGroups = new Dictionary<string, PollingGroup>();

        // Data cache
        private Dictionary<ushort, ushort> holdingRegisters = new Dictionary<ushort, ushort>();
        private Dictionary<ushort, ushort> inputRegisters = new Dictionary<ushort, ushort>();
        private Dictionary<ushort, bool> coils = new Dictionary<ushort, bool>();
        private Dictionary<ushort, bool> discreteInputs = new Dictionary<ushort, bool>();

        // Statistics
        private CommunicationStatistics statistics = new CommunicationStatistics();

        // Events
        public event Action<bool> OnConnectionStateChanged;
        public event Action<string, object> OnDataReceived;
        public event Action<ModbusException> OnError;
        public event Action<string, RegisterMap> OnRegisterUpdated;

        #region Data Structures

        public enum ConnectionMode
        {
            TCP,
            RTU,
            ASCII
        }

        public enum FunctionCode : byte
        {
            ReadCoils = 0x01,
            ReadDiscreteInputs = 0x02,
            ReadHoldingRegisters = 0x03,
            ReadInputRegisters = 0x04,
            WriteSingleCoil = 0x05,
            WriteSingleRegister = 0x06,
            WriteMultipleCoils = 0x0F,
            WriteMultipleRegisters = 0x10,
            ReadWriteMultipleRegisters = 0x17,
            MaskWriteRegister = 0x16,
            ReadFIFOQueue = 0x18,
            ReadDeviceIdentification = 0x2B
        }

        [System.Serializable]
        public class RegisterMap
        {
            public string name;
            public string description;
            public RegisterType registerType;
            public ushort address;
            public ushort quantity;
            public DataType dataType;
            public float scaleFactor;
            public float offset;
            public string unit;
            public bool isSigned;
            public ByteOrder byteOrder;
            public object currentValue;
            public DateTime lastUpdate;
            public bool isValid;
        }

        public enum RegisterType
        {
            Coil,
            DiscreteInput,
            HoldingRegister,
            InputRegister
        }

        public enum DataType
        {
            Bool,
            Int16,
            UInt16,
            Int32,
            UInt32,
            Float32,
            Float64,
            String
        }

        public enum ByteOrder
        {
            BigEndian,      // AB CD
            LittleEndian,   // DC BA
            BigEndianSwap,  // BA DC
            LittleEndianSwap // CD AB
        }

        [System.Serializable]
        public class PollingGroup
        {
            public string groupId;
            public string name;
            public float pollInterval;
            public List<string> registerNames;
            public bool isActive;
            public DateTime lastPoll;
            public int errorCount;
        }

        [System.Serializable]
        public class ModbusRequest
        {
            public ushort transactionId;
            public byte slaveAddress;
            public FunctionCode functionCode;
            public ushort startAddress;
            public ushort quantity;
            public byte[] data;
            public DateTime timestamp;
            public Action<ModbusResponse> callback;
        }

        [System.Serializable]
        public class ModbusResponse
        {
            public ushort transactionId;
            public byte slaveAddress;
            public FunctionCode functionCode;
            public byte[] data;
            public bool isError;
            public byte exceptionCode;
            public float responseTimeMs;
            public DateTime timestamp;
        }

        [System.Serializable]
        public class ModbusException
        {
            public byte exceptionCode;
            public string message;
            public DateTime timestamp;
            public ModbusRequest request;
        }

        [System.Serializable]
        public class CommunicationStatistics
        {
            public int totalRequests;
            public int successfulResponses;
            public int failedResponses;
            public int timeouts;
            public int crcErrors;
            public float averageResponseTimeMs;
            public float minResponseTimeMs;
            public float maxResponseTimeMs;
            public DateTime lastActivity;
            public int reconnectCount;
        }

        // Exception codes
        private static readonly Dictionary<byte, string> ExceptionMessages = new Dictionary<byte, string>
        {
            { 0x01, "Illegal Function" },
            { 0x02, "Illegal Data Address" },
            { 0x03, "Illegal Data Value" },
            { 0x04, "Slave Device Failure" },
            { 0x05, "Acknowledge" },
            { 0x06, "Slave Device Busy" },
            { 0x08, "Memory Parity Error" },
            { 0x0A, "Gateway Path Unavailable" },
            { 0x0B, "Gateway Target Device Failed to Respond" }
        };

        #endregion

        #region Unity Lifecycle

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
            InitializeHandler();
            CreateDefaultRegisterMaps();
        }

        private void OnDestroy()
        {
            Disconnect();
            StopAllCoroutines();
        }

        #endregion

        #region Initialization

        private void InitializeHandler()
        {
            Debug.Log("[Modbus] Initializing Modbus Protocol Handler");
            statistics = new CommunicationStatistics();
        }

        private void CreateDefaultRegisterMaps()
        {
            // Create common CNC machine register maps
            CreateRegisterMap("spindle_speed", "Spindle Speed", RegisterType.HoldingRegister,
                40001, 2, DataType.Float32, 1.0f, "RPM");
            CreateRegisterMap("spindle_load", "Spindle Load", RegisterType.InputRegister,
                30001, 1, DataType.UInt16, 0.1f, "%");
            CreateRegisterMap("feed_rate", "Feed Rate", RegisterType.HoldingRegister,
                40003, 2, DataType.Float32, 1.0f, "mm/min");
            CreateRegisterMap("axis_x_position", "X Axis Position", RegisterType.InputRegister,
                30003, 2, DataType.Float32, 0.001f, "mm");
            CreateRegisterMap("axis_y_position", "Y Axis Position", RegisterType.InputRegister,
                30005, 2, DataType.Float32, 0.001f, "mm");
            CreateRegisterMap("axis_z_position", "Z Axis Position", RegisterType.InputRegister,
                30007, 2, DataType.Float32, 0.001f, "mm");
            CreateRegisterMap("coolant_active", "Coolant Active", RegisterType.Coil,
                1, 1, DataType.Bool, 1.0f, "");
            CreateRegisterMap("spindle_running", "Spindle Running", RegisterType.DiscreteInput,
                10001, 1, DataType.Bool, 1.0f, "");
            CreateRegisterMap("program_number", "Program Number", RegisterType.HoldingRegister,
                40005, 1, DataType.UInt16, 1.0f, "");
            CreateRegisterMap("alarm_code", "Alarm Code", RegisterType.InputRegister,
                30009, 1, DataType.UInt16, 1.0f, "");
            CreateRegisterMap("machine_status", "Machine Status", RegisterType.InputRegister,
                30010, 1, DataType.UInt16, 1.0f, "");
            CreateRegisterMap("tool_number", "Tool Number", RegisterType.HoldingRegister,
                40006, 1, DataType.UInt16, 1.0f, "");
            CreateRegisterMap("part_count", "Part Count", RegisterType.InputRegister,
                30011, 2, DataType.UInt32, 1.0f, "");
            CreateRegisterMap("cycle_time", "Cycle Time", RegisterType.InputRegister,
                30013, 2, DataType.Float32, 1.0f, "sec");

            // Create default polling group
            CreatePollingGroup("realtime", "Real-time Data", 0.1f, new string[]
            {
                "spindle_speed", "spindle_load", "axis_x_position",
                "axis_y_position", "axis_z_position", "machine_status"
            });

            CreatePollingGroup("status", "Status Data", 1.0f, new string[]
            {
                "program_number", "tool_number", "alarm_code",
                "part_count", "cycle_time", "coolant_active", "spindle_running"
            });

            Debug.Log($"[Modbus] Created {registerMaps.Count} register maps and {pollingGroups.Count} polling groups");
        }

        #endregion

        #region Connection Management

        public void Connect()
        {
            if (isConnected)
            {
                Debug.LogWarning("[Modbus] Already connected");
                return;
            }

            StartCoroutine(ConnectAsync());
        }

        private IEnumerator ConnectAsync()
        {
            Debug.Log($"[Modbus] Connecting to {ipAddress}:{port}");

            bool success = false;
            bool hasError = false;
            string errorMessage = null;
            Task connectTask = null;

            if (connectionMode == ConnectionMode.TCP)
            {
                tcpClient = new TcpClient();
                connectTask = tcpClient.ConnectAsync(ipAddress, port);

                float startTime = Time.realtimeSinceStartup;
                while (connectTask != null && !connectTask.IsCompleted)
                {
                    if ((Time.realtimeSinceStartup - startTime) * 1000 > timeout)
                    {
                        hasError = true;
                        errorMessage = "Connection timeout";
                        break;
                    }
                    yield return null;
                }

                if (!hasError && connectTask != null && connectTask.IsFaulted)
                {
                    hasError = true;
                    errorMessage = connectTask.Exception?.InnerException?.Message ?? "Connection failed";
                }

                if (!hasError)
                {
                    try
                    {
                        networkStream = tcpClient.GetStream();
                        networkStream.ReadTimeout = timeout;
                        networkStream.WriteTimeout = timeout;
                        success = true;
                        Debug.Log("[Modbus] TCP connection established");
                    }
                    catch (Exception ex)
                    {
                        hasError = true;
                        errorMessage = ex.Message;
                    }
                }

                if (hasError)
                {
                    Debug.LogError($"[Modbus] Connection failed: {errorMessage}");
                    OnError?.Invoke(new ModbusException
                    {
                        exceptionCode = 0xFF,
                        message = errorMessage,
                        timestamp = DateTime.Now
                    });
                }
            }

            isConnected = success;
            OnConnectionStateChanged?.Invoke(success);

            if (success)
            {
                StartCoroutine(PollingLoop());
            }
            else if (autoReconnect)
            {
                yield return new WaitForSeconds(5f);
                StartCoroutine(ConnectAsync());
                statistics.reconnectCount++;
            }
        }

        public void Disconnect()
        {
            if (!isConnected)
                return;

            try
            {
                networkStream?.Close();
                tcpClient?.Close();
            }
            catch (Exception ex)
            {
                Debug.LogError($"[Modbus] Disconnect error: {ex.Message}");
            }

            isConnected = false;
            OnConnectionStateChanged?.Invoke(false);
            Debug.Log("[Modbus] Disconnected");
        }

        #endregion

        #region Register Map Management

        public void CreateRegisterMap(string name, string description, RegisterType type,
            ushort address, ushort quantity, DataType dataType, float scaleFactor, string unit,
            ByteOrder byteOrder = ByteOrder.BigEndian, bool isSigned = false)
        {
            var map = new RegisterMap
            {
                name = name,
                description = description,
                registerType = type,
                address = address,
                quantity = quantity,
                dataType = dataType,
                scaleFactor = scaleFactor,
                offset = 0,
                unit = unit,
                byteOrder = byteOrder,
                isSigned = isSigned,
                isValid = false
            };

            registerMaps[name] = map;
        }

        public RegisterMap GetRegisterMap(string name)
        {
            return registerMaps.TryGetValue(name, out var map) ? map : null;
        }

        public List<RegisterMap> GetAllRegisterMaps()
        {
            return registerMaps.Values.ToList();
        }

        #endregion

        #region Polling Groups

        public void CreatePollingGroup(string groupId, string name, float interval, string[] registers)
        {
            var group = new PollingGroup
            {
                groupId = groupId,
                name = name,
                pollInterval = interval,
                registerNames = registers.ToList(),
                isActive = true,
                lastPoll = DateTime.MinValue
            };

            pollingGroups[groupId] = group;
        }

        public void SetPollingGroupActive(string groupId, bool active)
        {
            if (pollingGroups.TryGetValue(groupId, out var group))
            {
                group.isActive = active;
            }
        }

        private IEnumerator PollingLoop()
        {
            while (isConnected)
            {
                foreach (var kvp in pollingGroups)
                {
                    var group = kvp.Value;

                    if (!group.isActive)
                        continue;

                    if ((DateTime.Now - group.lastPoll).TotalSeconds >= group.pollInterval)
                    {
                        yield return StartCoroutine(PollGroup(group));
                        group.lastPoll = DateTime.Now;
                    }
                }

                yield return new WaitForSeconds(pollInterval);
            }
        }

        private IEnumerator PollGroup(PollingGroup group)
        {
            foreach (var registerName in group.registerNames)
            {
                if (!registerMaps.TryGetValue(registerName, out var map))
                    continue;

                yield return StartCoroutine(ReadRegisterMapAsync(map));
            }
        }

        #endregion

        #region Read Operations

        public void ReadRegister(string name, Action<object> callback = null)
        {
            if (!registerMaps.TryGetValue(name, out var map))
            {
                Debug.LogWarning($"[Modbus] Register map not found: {name}");
                return;
            }

            StartCoroutine(ReadRegisterMapAsync(map, callback));
        }

        private IEnumerator ReadRegisterMapAsync(RegisterMap map, Action<object> callback = null)
        {
            FunctionCode functionCode;
            ushort baseAddress;

            switch (map.registerType)
            {
                case RegisterType.Coil:
                    functionCode = FunctionCode.ReadCoils;
                    baseAddress = map.address;
                    break;
                case RegisterType.DiscreteInput:
                    functionCode = FunctionCode.ReadDiscreteInputs;
                    baseAddress = (ushort)(map.address - 10000);
                    break;
                case RegisterType.InputRegister:
                    functionCode = FunctionCode.ReadInputRegisters;
                    baseAddress = (ushort)(map.address - 30000);
                    break;
                case RegisterType.HoldingRegister:
                default:
                    functionCode = FunctionCode.ReadHoldingRegisters;
                    baseAddress = (ushort)(map.address - 40000);
                    break;
            }

            ModbusResponse response = null;
            yield return StartCoroutine(SendRequestAsync(functionCode, baseAddress, map.quantity, null,
                r => response = r));

            if (response != null && !response.isError)
            {
                // Parse response data
                object value = ParseResponseData(response.data, map);
                map.currentValue = value;
                map.lastUpdate = DateTime.Now;
                map.isValid = true;

                // Cache data
                CacheRegisterData(map, response.data);

                callback?.Invoke(value);
                OnDataReceived?.Invoke(map.name, value);
                OnRegisterUpdated?.Invoke(map.name, map);
            }
            else if (response != null && response.isError)
            {
                map.isValid = false;
                Debug.LogWarning($"[Modbus] Read error for {map.name}: {GetExceptionMessage(response.exceptionCode)}");
            }
        }

        public bool[] ReadCoils(ushort startAddress, ushort quantity)
        {
            // Synchronous read for simple cases
            var request = CreateRequest(FunctionCode.ReadCoils, startAddress, quantity, null);
            var response = SendRequestSync(request);

            if (response != null && !response.isError && response.data != null)
            {
                var values = new bool[quantity];
                for (int i = 0; i < quantity; i++)
                {
                    int byteIndex = i / 8;
                    int bitIndex = i % 8;
                    if (byteIndex < response.data.Length)
                    {
                        values[i] = (response.data[byteIndex] & (1 << bitIndex)) != 0;
                    }
                }
                return values;
            }

            return null;
        }

        public ushort[] ReadHoldingRegisters(ushort startAddress, ushort quantity)
        {
            var request = CreateRequest(FunctionCode.ReadHoldingRegisters, startAddress, quantity, null);
            var response = SendRequestSync(request);

            if (response != null && !response.isError && response.data != null)
            {
                var values = new ushort[quantity];
                for (int i = 0; i < quantity && i * 2 + 1 < response.data.Length; i++)
                {
                    values[i] = (ushort)((response.data[i * 2] << 8) | response.data[i * 2 + 1]);
                }
                return values;
            }

            return null;
        }

        public ushort[] ReadInputRegisters(ushort startAddress, ushort quantity)
        {
            var request = CreateRequest(FunctionCode.ReadInputRegisters, startAddress, quantity, null);
            var response = SendRequestSync(request);

            if (response != null && !response.isError && response.data != null)
            {
                var values = new ushort[quantity];
                for (int i = 0; i < quantity && i * 2 + 1 < response.data.Length; i++)
                {
                    values[i] = (ushort)((response.data[i * 2] << 8) | response.data[i * 2 + 1]);
                }
                return values;
            }

            return null;
        }

        #endregion

        #region Write Operations

        public void WriteRegister(string name, object value, Action<bool> callback = null)
        {
            if (!registerMaps.TryGetValue(name, out var map))
            {
                Debug.LogWarning($"[Modbus] Register map not found: {name}");
                return;
            }

            StartCoroutine(WriteRegisterMapAsync(map, value, callback));
        }

        private IEnumerator WriteRegisterMapAsync(RegisterMap map, object value, Action<bool> callback = null)
        {
            FunctionCode functionCode;
            ushort baseAddress;
            byte[] data;

            switch (map.registerType)
            {
                case RegisterType.Coil:
                    functionCode = map.quantity == 1 ? FunctionCode.WriteSingleCoil : FunctionCode.WriteMultipleCoils;
                    baseAddress = map.address;
                    data = EncodeCoilValue(value, map.quantity);
                    break;
                case RegisterType.HoldingRegister:
                    functionCode = map.quantity == 1 ? FunctionCode.WriteSingleRegister : FunctionCode.WriteMultipleRegisters;
                    baseAddress = (ushort)(map.address - 40000);
                    data = EncodeRegisterValue(value, map);
                    break;
                default:
                    Debug.LogWarning($"[Modbus] Cannot write to {map.registerType}");
                    callback?.Invoke(false);
                    yield break;
            }

            ModbusResponse response = null;
            yield return StartCoroutine(SendRequestAsync(functionCode, baseAddress, map.quantity, data,
                r => response = r));

            bool success = response != null && !response.isError;
            callback?.Invoke(success);

            if (success)
            {
                map.currentValue = value;
                map.lastUpdate = DateTime.Now;
                Debug.Log($"[Modbus] Successfully wrote {value} to {map.name}");
            }
        }

        public bool WriteSingleCoil(ushort address, bool value)
        {
            byte[] data = value ? new byte[] { 0xFF, 0x00 } : new byte[] { 0x00, 0x00 };
            var request = CreateRequest(FunctionCode.WriteSingleCoil, address, 1, data);
            var response = SendRequestSync(request);
            return response != null && !response.isError;
        }

        public bool WriteSingleRegister(ushort address, ushort value)
        {
            byte[] data = new byte[] { (byte)(value >> 8), (byte)(value & 0xFF) };
            var request = CreateRequest(FunctionCode.WriteSingleRegister, address, 1, data);
            var response = SendRequestSync(request);
            return response != null && !response.isError;
        }

        public bool WriteMultipleRegisters(ushort startAddress, ushort[] values)
        {
            byte[] data = new byte[values.Length * 2];
            for (int i = 0; i < values.Length; i++)
            {
                data[i * 2] = (byte)(values[i] >> 8);
                data[i * 2 + 1] = (byte)(values[i] & 0xFF);
            }

            var request = CreateRequest(FunctionCode.WriteMultipleRegisters, startAddress, (ushort)values.Length, data);
            var response = SendRequestSync(request);
            return response != null && !response.isError;
        }

        #endregion

        #region Protocol Implementation

        private ModbusRequest CreateRequest(FunctionCode functionCode, ushort startAddress, ushort quantity, byte[] data)
        {
            return new ModbusRequest
            {
                transactionId = transactionId++,
                slaveAddress = slaveAddress,
                functionCode = functionCode,
                startAddress = startAddress,
                quantity = quantity,
                data = data,
                timestamp = DateTime.Now
            };
        }

        private IEnumerator SendRequestAsync(FunctionCode functionCode, ushort startAddress, ushort quantity,
            byte[] writeData, Action<ModbusResponse> callback)
        {
            if (!isConnected)
            {
                callback?.Invoke(null);
                yield break;
            }

            var request = CreateRequest(functionCode, startAddress, quantity, writeData);

            for (int retry = 0; retry < maxRetries; retry++)
            {
                var response = SendRequestSync(request);

                if (response != null)
                {
                    callback?.Invoke(response);
                    yield break;
                }

                yield return new WaitForSeconds(0.1f);
            }

            statistics.timeouts++;
            callback?.Invoke(null);
        }

        private ModbusResponse SendRequestSync(ModbusRequest request)
        {
            if (!isConnected || networkStream == null)
                return null;

            var startTime = DateTime.Now;
            statistics.totalRequests++;
            statistics.lastActivity = DateTime.Now;

            try
            {
                // Build request frame
                byte[] frame = BuildModbusTCPFrame(request);

                // Send request
                networkStream.Write(frame, 0, frame.Length);
                networkStream.Flush();

                // Read response
                byte[] responseHeader = new byte[7];
                int bytesRead = networkStream.Read(responseHeader, 0, 7);

                if (bytesRead < 7)
                {
                    statistics.failedResponses++;
                    return null;
                }

                // Parse MBAP header
                ushort responseTransactionId = (ushort)((responseHeader[0] << 8) | responseHeader[1]);
                ushort protocolId = (ushort)((responseHeader[2] << 8) | responseHeader[3]);
                ushort length = (ushort)((responseHeader[4] << 8) | responseHeader[5]);
                byte unitId = responseHeader[6];

                // Read remaining data
                byte[] pduData = new byte[length - 1];
                bytesRead = networkStream.Read(pduData, 0, pduData.Length);

                var response = new ModbusResponse
                {
                    transactionId = responseTransactionId,
                    slaveAddress = unitId,
                    functionCode = (FunctionCode)(pduData[0] & 0x7F),
                    isError = (pduData[0] & 0x80) != 0,
                    timestamp = DateTime.Now,
                    responseTimeMs = (float)(DateTime.Now - startTime).TotalMilliseconds
                };

                if (response.isError)
                {
                    response.exceptionCode = pduData.Length > 1 ? pduData[1] : (byte)0;
                    statistics.failedResponses++;

                    OnError?.Invoke(new ModbusException
                    {
                        exceptionCode = response.exceptionCode,
                        message = GetExceptionMessage(response.exceptionCode),
                        timestamp = DateTime.Now,
                        request = request
                    });
                }
                else
                {
                    // Extract data bytes (skip function code and byte count)
                    if (pduData.Length > 2)
                    {
                        int dataLength = pduData[1];
                        response.data = new byte[dataLength];
                        Array.Copy(pduData, 2, response.data, 0, Math.Min(dataLength, pduData.Length - 2));
                    }
                    else if (pduData.Length > 1)
                    {
                        response.data = new byte[pduData.Length - 1];
                        Array.Copy(pduData, 1, response.data, 0, pduData.Length - 1);
                    }

                    statistics.successfulResponses++;
                }

                // Update response time statistics
                UpdateResponseTimeStats(response.responseTimeMs);

                return response;
            }
            catch (Exception ex)
            {
                Debug.LogError($"[Modbus] Communication error: {ex.Message}");
                statistics.failedResponses++;

                if (autoReconnect)
                {
                    isConnected = false;
                    OnConnectionStateChanged?.Invoke(false);
                    StartCoroutine(ConnectAsync());
                }

                return null;
            }
        }

        private byte[] BuildModbusTCPFrame(ModbusRequest request)
        {
            // Build PDU
            List<byte> pdu = new List<byte>();
            pdu.Add((byte)request.functionCode);
            pdu.Add((byte)(request.startAddress >> 8));
            pdu.Add((byte)(request.startAddress & 0xFF));

            switch (request.functionCode)
            {
                case FunctionCode.ReadCoils:
                case FunctionCode.ReadDiscreteInputs:
                case FunctionCode.ReadHoldingRegisters:
                case FunctionCode.ReadInputRegisters:
                    pdu.Add((byte)(request.quantity >> 8));
                    pdu.Add((byte)(request.quantity & 0xFF));
                    break;

                case FunctionCode.WriteSingleCoil:
                case FunctionCode.WriteSingleRegister:
                    if (request.data != null)
                    {
                        pdu.AddRange(request.data);
                    }
                    break;

                case FunctionCode.WriteMultipleCoils:
                case FunctionCode.WriteMultipleRegisters:
                    pdu.Add((byte)(request.quantity >> 8));
                    pdu.Add((byte)(request.quantity & 0xFF));
                    if (request.data != null)
                    {
                        pdu.Add((byte)request.data.Length);
                        pdu.AddRange(request.data);
                    }
                    break;
            }

            // Build MBAP header
            ushort length = (ushort)(pdu.Count + 1);
            byte[] frame = new byte[7 + pdu.Count];

            // Transaction ID
            frame[0] = (byte)(request.transactionId >> 8);
            frame[1] = (byte)(request.transactionId & 0xFF);
            // Protocol ID (0 = Modbus)
            frame[2] = 0;
            frame[3] = 0;
            // Length
            frame[4] = (byte)(length >> 8);
            frame[5] = (byte)(length & 0xFF);
            // Unit ID
            frame[6] = request.slaveAddress;
            // PDU
            Array.Copy(pdu.ToArray(), 0, frame, 7, pdu.Count);

            return frame;
        }

        #endregion

        #region Data Conversion

        private object ParseResponseData(byte[] data, RegisterMap map)
        {
            if (data == null || data.Length == 0)
                return null;

            switch (map.dataType)
            {
                case DataType.Bool:
                    return (data[0] & 0x01) != 0;

                case DataType.UInt16:
                    return (ushort)(((data[0] << 8) | data[1]) * map.scaleFactor + map.offset);

                case DataType.Int16:
                    short signed = (short)((data[0] << 8) | data[1]);
                    return signed * map.scaleFactor + map.offset;

                case DataType.UInt32:
                    uint u32 = ConvertToUInt32(data, map.byteOrder);
                    return u32 * map.scaleFactor + map.offset;

                case DataType.Int32:
                    int i32 = (int)ConvertToUInt32(data, map.byteOrder);
                    return i32 * map.scaleFactor + map.offset;

                case DataType.Float32:
                    byte[] floatBytes = ReorderBytes(data, map.byteOrder, 4);
                    float f = BitConverter.ToSingle(floatBytes, 0);
                    return f * map.scaleFactor + map.offset;

                case DataType.Float64:
                    byte[] doubleBytes = ReorderBytes(data, map.byteOrder, 8);
                    double d = BitConverter.ToDouble(doubleBytes, 0);
                    return d * map.scaleFactor + map.offset;

                case DataType.String:
                    return System.Text.Encoding.ASCII.GetString(data).TrimEnd('\0');

                default:
                    return data;
            }
        }

        private uint ConvertToUInt32(byte[] data, ByteOrder byteOrder)
        {
            if (data.Length < 4)
                return 0;

            byte[] reordered = ReorderBytes(data, byteOrder, 4);
            return BitConverter.ToUInt32(reordered, 0);
        }

        private byte[] ReorderBytes(byte[] data, ByteOrder byteOrder, int length)
        {
            byte[] result = new byte[length];
            Array.Copy(data, result, Math.Min(data.Length, length));

            switch (byteOrder)
            {
                case ByteOrder.BigEndian:
                    // AB CD -> DC BA for little-endian system
                    if (BitConverter.IsLittleEndian)
                        Array.Reverse(result);
                    break;

                case ByteOrder.LittleEndian:
                    // DC BA -> DC BA on little-endian
                    if (!BitConverter.IsLittleEndian)
                        Array.Reverse(result);
                    break;

                case ByteOrder.BigEndianSwap:
                    // BA DC
                    for (int i = 0; i < result.Length - 1; i += 2)
                    {
                        byte temp = result[i];
                        result[i] = result[i + 1];
                        result[i + 1] = temp;
                    }
                    if (BitConverter.IsLittleEndian)
                        Array.Reverse(result);
                    break;

                case ByteOrder.LittleEndianSwap:
                    // CD AB
                    for (int i = 0; i < result.Length - 1; i += 2)
                    {
                        byte temp = result[i];
                        result[i] = result[i + 1];
                        result[i + 1] = temp;
                    }
                    if (!BitConverter.IsLittleEndian)
                        Array.Reverse(result);
                    break;
            }

            return result;
        }

        private byte[] EncodeCoilValue(object value, ushort quantity)
        {
            if (quantity == 1)
            {
                bool boolVal = Convert.ToBoolean(value);
                return boolVal ? new byte[] { 0xFF, 0x00 } : new byte[] { 0x00, 0x00 };
            }

            bool[] values = value as bool[];
            if (values == null)
                return new byte[] { 0x00, 0x00 };

            int byteCount = (values.Length + 7) / 8;
            byte[] data = new byte[byteCount];

            for (int i = 0; i < values.Length; i++)
            {
                if (values[i])
                {
                    data[i / 8] |= (byte)(1 << (i % 8));
                }
            }

            return data;
        }

        private byte[] EncodeRegisterValue(object value, RegisterMap map)
        {
            float scaledValue = (Convert.ToSingle(value) - map.offset) / map.scaleFactor;

            switch (map.dataType)
            {
                case DataType.UInt16:
                case DataType.Int16:
                    ushort u16 = (ushort)scaledValue;
                    return new byte[] { (byte)(u16 >> 8), (byte)(u16 & 0xFF) };

                case DataType.UInt32:
                case DataType.Int32:
                    uint u32 = (uint)scaledValue;
                    byte[] u32Bytes = BitConverter.GetBytes(u32);
                    if (BitConverter.IsLittleEndian)
                        Array.Reverse(u32Bytes);
                    return u32Bytes;

                case DataType.Float32:
                    byte[] floatBytes = BitConverter.GetBytes((float)scaledValue);
                    if (BitConverter.IsLittleEndian)
                        Array.Reverse(floatBytes);
                    return floatBytes;

                default:
                    return new byte[] { 0x00, 0x00 };
            }
        }

        private void CacheRegisterData(RegisterMap map, byte[] data)
        {
            if (map.registerType == RegisterType.HoldingRegister || map.registerType == RegisterType.InputRegister)
            {
                for (int i = 0; i < map.quantity && i * 2 + 1 < data.Length; i++)
                {
                    ushort value = (ushort)((data[i * 2] << 8) | data[i * 2 + 1]);
                    ushort address = (ushort)(map.address + i);

                    if (map.registerType == RegisterType.HoldingRegister)
                        holdingRegisters[address] = value;
                    else
                        inputRegisters[address] = value;
                }
            }
            else if (map.registerType == RegisterType.Coil || map.registerType == RegisterType.DiscreteInput)
            {
                for (int i = 0; i < map.quantity; i++)
                {
                    int byteIndex = i / 8;
                    int bitIndex = i % 8;
                    bool value = byteIndex < data.Length && (data[byteIndex] & (1 << bitIndex)) != 0;
                    ushort address = (ushort)(map.address + i);

                    if (map.registerType == RegisterType.Coil)
                        coils[address] = value;
                    else
                        discreteInputs[address] = value;
                }
            }
        }

        #endregion

        #region Utilities

        private string GetExceptionMessage(byte code)
        {
            return ExceptionMessages.TryGetValue(code, out var msg) ? msg : $"Unknown exception (0x{code:X2})";
        }

        private void UpdateResponseTimeStats(float responseTime)
        {
            if (statistics.minResponseTimeMs == 0 || responseTime < statistics.minResponseTimeMs)
                statistics.minResponseTimeMs = responseTime;
            if (responseTime > statistics.maxResponseTimeMs)
                statistics.maxResponseTimeMs = responseTime;

            // Running average
            int n = statistics.successfulResponses;
            statistics.averageResponseTimeMs = statistics.averageResponseTimeMs + (responseTime - statistics.averageResponseTimeMs) / n;
        }

        public object GetCachedValue(string registerName)
        {
            if (registerMaps.TryGetValue(registerName, out var map) && map.isValid)
            {
                return map.currentValue;
            }
            return null;
        }

        public CommunicationStatistics GetStatistics()
        {
            return statistics;
        }

        public bool IsConnected => isConnected;

        #endregion
    }
}
