using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCDigitalTwin.ToolManagement
{
    /// <summary>
    /// Comprehensive Tool Management System for CNC machining
    /// Handles tool tracking, wear monitoring, life prediction, and crib management
    /// </summary>
    public class ToolManagementSystem : MonoBehaviour
    {
        public static ToolManagementSystem Instance { get; private set; }

        [Header("Configuration")]
        [SerializeField] private float wearUpdateInterval = 1.0f;
        [SerializeField] private float lifePredictionThreshold = 0.2f; // 20% remaining
        [SerializeField] private bool enableAutoReplacement = false;
        [SerializeField] private int maxToolHistoryEntries = 10000;

        [Header("Wear Calculation")]
        [SerializeField] private float baseWearRate = 0.001f; // Per cut
        [SerializeField] private float hardnessMultiplier = 1.5f;
        [SerializeField] private float speedMultiplier = 0.5f;
        [SerializeField] private float temperatureMultiplier = 0.3f;

        // Tool inventory
        private Dictionary<string, Tool> tools = new Dictionary<string, Tool>();
        private Dictionary<string, ToolHolder> toolHolders = new Dictionary<string, ToolHolder>();
        private Dictionary<string, ToolCrib> toolCribs = new Dictionary<string, ToolCrib>();

        // Active tool tracking
        private Dictionary<string, string> machineActiveTool = new Dictionary<string, string>(); // machineId -> toolId
        private Dictionary<string, ToolUsageSession> activeSessions = new Dictionary<string, ToolUsageSession>();

        // Tool library (tool definitions)
        private Dictionary<string, ToolDefinition> toolLibrary = new Dictionary<string, ToolDefinition>();

        // History and analytics
        private List<ToolHistoryEntry> toolHistory = new List<ToolHistoryEntry>();
        private Dictionary<string, ToolLifeStats> lifeStats = new Dictionary<string, ToolLifeStats>();

        // Pending replacements
        private Queue<ToolReplacementRequest> replacementQueue = new Queue<ToolReplacementRequest>();

        // Events
        public event Action<Tool> OnToolRegistered;
        public event Action<Tool> OnToolLoaded;
        public event Action<Tool> OnToolUnloaded;
        public event Action<Tool, float> OnWearUpdated;
        public event Action<Tool> OnToolWornOut;
        public event Action<Tool> OnToolBroken;
        public event Action<ToolReplacementRequest> OnReplacementNeeded;
        public event Action<Tool> OnToolReplaced;
        public event Action<ToolAlert> OnToolAlert;

        private Coroutine wearUpdateCoroutine;

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
            InitializeToolLibrary();
            InitializeDefaultCribs();
            wearUpdateCoroutine = StartCoroutine(WearUpdateLoop());
        }

        void OnDestroy()
        {
            if (wearUpdateCoroutine != null)
                StopCoroutine(wearUpdateCoroutine);
        }

        #region Initialization

        private void InitializeToolLibrary()
        {
            // End Mills
            DefineToolType(new ToolDefinition
            {
                ToolTypeId = "ENDMILL_4F_6MM",
                Name = "4-Flute End Mill 6mm",
                Category = ToolCategory.EndMill,
                Diameter = 6.0f,
                Length = 57.0f,
                FluteCount = 4,
                Material = ToolMaterial.Carbide,
                Coating = ToolCoating.TiAlN,
                ExpectedLife = 3600, // seconds of cut time
                MaxRPM = 24000,
                MaxFeedRate = 3000f,
                CoolantRequired = true
            });

            DefineToolType(new ToolDefinition
            {
                ToolTypeId = "ENDMILL_2F_3MM",
                Name = "2-Flute End Mill 3mm",
                Category = ToolCategory.EndMill,
                Diameter = 3.0f,
                Length = 38.0f,
                FluteCount = 2,
                Material = ToolMaterial.Carbide,
                Coating = ToolCoating.DLC,
                ExpectedLife = 2400,
                MaxRPM = 30000,
                MaxFeedRate = 2000f,
                CoolantRequired = true
            });

            // Ball End Mills
            DefineToolType(new ToolDefinition
            {
                ToolTypeId = "BALLMILL_4MM",
                Name = "Ball End Mill 4mm",
                Category = ToolCategory.BallEndMill,
                Diameter = 4.0f,
                Length = 50.0f,
                FluteCount = 2,
                Material = ToolMaterial.Carbide,
                Coating = ToolCoating.TiAlN,
                ExpectedLife = 2700,
                MaxRPM = 28000
            });

            // Drills
            DefineToolType(new ToolDefinition
            {
                ToolTypeId = "DRILL_5MM",
                Name = "Carbide Drill 5mm",
                Category = ToolCategory.Drill,
                Diameter = 5.0f,
                Length = 62.0f,
                FluteCount = 2,
                Material = ToolMaterial.Carbide,
                Coating = ToolCoating.TiN,
                ExpectedLife = 4000,
                MaxRPM = 8000,
                PointAngle = 140f,
                CoolantRequired = true
            });

            // Taps
            DefineToolType(new ToolDefinition
            {
                ToolTypeId = "TAP_M6",
                Name = "M6 x 1.0 Tap",
                Category = ToolCategory.Tap,
                Diameter = 6.0f,
                Length = 72.0f,
                FluteCount = 3,
                Material = ToolMaterial.HSS,
                Coating = ToolCoating.TiN,
                ExpectedLife = 1800,
                MaxRPM = 500,
                ThreadPitch = 1.0f
            });

            // Face Mills
            DefineToolType(new ToolDefinition
            {
                ToolTypeId = "FACEMILL_50MM",
                Name = "Face Mill 50mm",
                Category = ToolCategory.FaceMill,
                Diameter = 50.0f,
                Length = 45.0f,
                FluteCount = 5,
                Material = ToolMaterial.Carbide,
                Coating = ToolCoating.TiAlN,
                ExpectedLife = 7200,
                MaxRPM = 6000,
                InsertCount = 5
            });

            // Reamers
            DefineToolType(new ToolDefinition
            {
                ToolTypeId = "REAMER_8MM",
                Name = "Reamer 8mm H7",
                Category = ToolCategory.Reamer,
                Diameter = 8.0f,
                Length = 90.0f,
                FluteCount = 6,
                Material = ToolMaterial.Carbide,
                Coating = ToolCoating.None,
                ExpectedLife = 5000,
                MaxRPM = 3000,
                ToleranceClass = "H7"
            });

            Debug.Log($"[ToolMgmt] Initialized {toolLibrary.Count} tool definitions");
        }

        private void InitializeDefaultCribs()
        {
            // Main tool crib
            CreateToolCrib(new ToolCribConfig
            {
                CribId = "MAIN_CRIB",
                Name = "Main Tool Crib",
                Location = "Shop Floor A",
                Capacity = 500,
                IsAutomated = false
            });

            // Automated tool dispenser
            CreateToolCrib(new ToolCribConfig
            {
                CribId = "AUTO_DISPENSER",
                Name = "Automated Dispenser",
                Location = "Cell 1",
                Capacity = 100,
                IsAutomated = true
            });
        }

        #endregion

        #region Tool Definition Management

        public void DefineToolType(ToolDefinition definition)
        {
            toolLibrary[definition.ToolTypeId] = definition;
        }

        public ToolDefinition GetToolDefinition(string toolTypeId)
        {
            return toolLibrary.TryGetValue(toolTypeId, out var def) ? def : null;
        }

        public List<ToolDefinition> GetToolsByCategory(ToolCategory category)
        {
            return toolLibrary.Values.Where(t => t.Category == category).ToList();
        }

        #endregion

        #region Tool Instance Management

        public Tool RegisterTool(ToolRegistration registration)
        {
            var definition = GetToolDefinition(registration.ToolTypeId);
            if (definition == null)
            {
                Debug.LogWarning($"[ToolMgmt] Unknown tool type: {registration.ToolTypeId}");
                return null;
            }

            var tool = new Tool
            {
                ToolId = registration.ToolId ?? Guid.NewGuid().ToString(),
                Definition = definition,
                SerialNumber = registration.SerialNumber,
                Manufacturer = registration.Manufacturer,
                PurchaseDate = registration.PurchaseDate,
                Status = ToolStatus.Available,
                Condition = ToolCondition.New,
                WearLevel = 0f,
                RemainingLife = definition.ExpectedLife,
                TotalCutTime = 0f,
                TotalCuts = 0,
                CribId = registration.CribId,
                Location = registration.Location
            };

            tools[tool.ToolId] = tool;

            // Initialize life stats
            lifeStats[tool.ToolId] = new ToolLifeStats
            {
                ToolId = tool.ToolId,
                ExpectedLife = definition.ExpectedLife
            };

            LogHistory(tool, ToolEvent.Registered, "Tool registered");
            OnToolRegistered?.Invoke(tool);

            Debug.Log($"[ToolMgmt] Registered tool: {definition.Name} ({tool.ToolId})");
            return tool;
        }

        public Tool GetTool(string toolId)
        {
            return tools.TryGetValue(toolId, out var tool) ? tool : null;
        }

        public List<Tool> GetToolsByType(string toolTypeId)
        {
            return tools.Values.Where(t => t.Definition.ToolTypeId == toolTypeId).ToList();
        }

        public List<Tool> GetAvailableTools(string toolTypeId = null)
        {
            var query = tools.Values.Where(t => t.Status == ToolStatus.Available);
            if (!string.IsNullOrEmpty(toolTypeId))
            {
                query = query.Where(t => t.Definition.ToolTypeId == toolTypeId);
            }
            return query.OrderByDescending(t => t.RemainingLife).ToList();
        }

        #endregion

        #region Tool Holder Management

        public ToolHolder CreateToolHolder(ToolHolderConfig config)
        {
            var holder = new ToolHolder
            {
                HolderId = config.HolderId,
                Name = config.Name,
                Type = config.Type,
                TaperType = config.TaperType,
                Collet = config.Collet,
                GaugeLength = config.GaugeLength,
                MaxRPM = config.MaxRPM,
                Runout = config.Runout,
                Status = HolderStatus.Available
            };

            toolHolders[holder.HolderId] = holder;
            Debug.Log($"[ToolMgmt] Created tool holder: {config.Name}");
            return holder;
        }

        public bool AssembleTool(string toolId, string holderId)
        {
            if (!tools.TryGetValue(toolId, out var tool) ||
                !toolHolders.TryGetValue(holderId, out var holder))
            {
                return false;
            }

            if (tool.Status != ToolStatus.Available || holder.Status != HolderStatus.Available)
            {
                Debug.LogWarning("[ToolMgmt] Tool or holder not available for assembly");
                return false;
            }

            tool.HolderId = holderId;
            tool.Status = ToolStatus.Assembled;
            holder.InstalledToolId = toolId;
            holder.Status = HolderStatus.Loaded;

            // Calculate total tool length
            tool.TotalLength = tool.Definition.Length + holder.GaugeLength;

            LogHistory(tool, ToolEvent.Assembled, $"Assembled in holder {holder.Name}");
            return true;
        }

        public bool DisassembleTool(string toolId)
        {
            if (!tools.TryGetValue(toolId, out var tool) || string.IsNullOrEmpty(tool.HolderId))
            {
                return false;
            }

            if (toolHolders.TryGetValue(tool.HolderId, out var holder))
            {
                holder.InstalledToolId = null;
                holder.Status = HolderStatus.Available;
            }

            tool.HolderId = null;
            tool.Status = ToolStatus.Available;
            tool.TotalLength = tool.Definition.Length;

            LogHistory(tool, ToolEvent.Disassembled, "Disassembled from holder");
            return true;
        }

        #endregion

        #region Tool Loading/Unloading

        public bool LoadToolToMachine(string machineId, string toolId, int pocketNumber)
        {
            if (!tools.TryGetValue(toolId, out var tool))
            {
                Debug.LogWarning($"[ToolMgmt] Tool not found: {toolId}");
                return false;
            }

            if (tool.Status != ToolStatus.Assembled && tool.Status != ToolStatus.Available)
            {
                Debug.LogWarning($"[ToolMgmt] Tool not available for loading: {tool.Status}");
                return false;
            }

            tool.MachineId = machineId;
            tool.PocketNumber = pocketNumber;
            tool.Status = ToolStatus.Loaded;
            tool.LoadedAt = DateTime.UtcNow;

            LogHistory(tool, ToolEvent.Loaded, $"Loaded to {machineId} pocket {pocketNumber}");
            OnToolLoaded?.Invoke(tool);

            Debug.Log($"[ToolMgmt] Tool {tool.Definition.Name} loaded to {machineId} pocket {pocketNumber}");
            return true;
        }

        public bool UnloadToolFromMachine(string machineId, string toolId)
        {
            if (!tools.TryGetValue(toolId, out var tool))
            {
                return false;
            }

            // End any active session
            EndUsageSession(toolId);

            tool.MachineId = null;
            tool.PocketNumber = null;
            tool.Status = string.IsNullOrEmpty(tool.HolderId) ? ToolStatus.Available : ToolStatus.Assembled;

            LogHistory(tool, ToolEvent.Unloaded, $"Unloaded from {machineId}");
            OnToolUnloaded?.Invoke(tool);

            return true;
        }

        public bool SelectTool(string machineId, string toolId)
        {
            if (!tools.TryGetValue(toolId, out var tool) || tool.MachineId != machineId)
            {
                return false;
            }

            // Deselect previous tool
            if (machineActiveTool.TryGetValue(machineId, out var previousToolId) && previousToolId != toolId)
            {
                EndUsageSession(previousToolId);
            }

            machineActiveTool[machineId] = toolId;
            tool.Status = ToolStatus.InUse;

            // Start usage session
            StartUsageSession(toolId, machineId);

            LogHistory(tool, ToolEvent.Selected, $"Selected on {machineId}");
            return true;
        }

        public string GetActiveTool(string machineId)
        {
            return machineActiveTool.TryGetValue(machineId, out var toolId) ? toolId : null;
        }

        #endregion

        #region Usage Tracking

        private void StartUsageSession(string toolId, string machineId)
        {
            var session = new ToolUsageSession
            {
                SessionId = Guid.NewGuid().ToString(),
                ToolId = toolId,
                MachineId = machineId,
                StartTime = DateTime.UtcNow,
                StartWearLevel = tools[toolId].WearLevel
            };

            activeSessions[toolId] = session;
        }

        private void EndUsageSession(string toolId)
        {
            if (!activeSessions.TryGetValue(toolId, out var session))
                return;

            session.EndTime = DateTime.UtcNow;
            session.Duration = (float)(session.EndTime - session.StartTime).TotalSeconds;

            if (tools.TryGetValue(toolId, out var tool))
            {
                session.EndWearLevel = tool.WearLevel;
                session.WearAccumulated = session.EndWearLevel - session.StartWearLevel;
                tool.Status = ToolStatus.Loaded;
            }

            activeSessions.Remove(toolId);

            // Update life stats
            UpdateLifeStats(toolId, session);
        }

        public void RecordCut(string toolId, CutParameters parameters)
        {
            if (!tools.TryGetValue(toolId, out var tool))
                return;

            // Calculate wear based on cutting parameters
            float wearIncrement = CalculateWearIncrement(tool, parameters);

            tool.WearLevel = Mathf.Min(1f, tool.WearLevel + wearIncrement);
            tool.TotalCutTime += parameters.CutTime;
            tool.TotalCuts++;
            tool.RemainingLife = CalculateRemainingLife(tool);

            // Update active session
            if (activeSessions.TryGetValue(toolId, out var session))
            {
                session.CutCount++;
                session.TotalCutTime += parameters.CutTime;
                session.MaterialRemoved += parameters.MaterialRemoved;
            }

            OnWearUpdated?.Invoke(tool, tool.WearLevel);

            // Check for alerts
            CheckToolCondition(tool);
        }

        private float CalculateWearIncrement(Tool tool, CutParameters parameters)
        {
            float increment = baseWearRate;

            // Material hardness factor
            increment *= 1f + (parameters.MaterialHardness / 100f) * hardnessMultiplier;

            // Speed factor (higher speed = more wear)
            float speedRatio = parameters.SpindleSpeed / tool.Definition.MaxRPM;
            increment *= 1f + speedRatio * speedMultiplier;

            // Temperature factor
            if (parameters.CuttingTemperature > 0)
            {
                float tempRatio = parameters.CuttingTemperature / 500f; // Normalize to 500C
                increment *= 1f + tempRatio * temperatureMultiplier;
            }

            // Coolant reduces wear
            if (parameters.CoolantActive)
            {
                increment *= 0.7f;
            }

            // Coating effectiveness
            float coatingFactor = GetCoatingFactor(tool.Definition.Coating);
            increment *= coatingFactor;

            return increment * parameters.CutTime;
        }

        private float GetCoatingFactor(ToolCoating coating)
        {
            return coating switch
            {
                ToolCoating.None => 1.0f,
                ToolCoating.TiN => 0.85f,
                ToolCoating.TiAlN => 0.75f,
                ToolCoating.AlTiN => 0.7f,
                ToolCoating.DLC => 0.65f,
                ToolCoating.Diamond => 0.5f,
                _ => 1.0f
            };
        }

        private float CalculateRemainingLife(Tool tool)
        {
            // Estimate remaining life based on current wear rate
            if (tool.TotalCutTime <= 0) return tool.Definition.ExpectedLife;

            float wearRate = tool.WearLevel / tool.TotalCutTime;
            float remainingWear = 1f - tool.WearLevel;

            if (wearRate <= 0) return tool.Definition.ExpectedLife;
            return remainingWear / wearRate;
        }

        private void UpdateLifeStats(string toolId, ToolUsageSession session)
        {
            if (!lifeStats.TryGetValue(toolId, out var stats))
                return;

            stats.TotalSessions++;
            stats.TotalRunTime += session.Duration;
            stats.TotalCuts += session.CutCount;
            stats.AverageWearPerSession = stats.TotalWear / stats.TotalSessions;

            // Update wear trend
            stats.WearTrend.Add(new WearDataPoint
            {
                Timestamp = DateTime.UtcNow,
                WearLevel = tools[toolId].WearLevel,
                CumulativeCutTime = tools[toolId].TotalCutTime
            });
        }

        #endregion

        #region Wear Monitoring & Alerts

        private IEnumerator WearUpdateLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(wearUpdateInterval);

                foreach (var kvp in activeSessions.ToList())
                {
                    if (tools.TryGetValue(kvp.Key, out var tool))
                    {
                        // Passive wear while tool is selected (idle wear)
                        if (tool.Status == ToolStatus.InUse)
                        {
                            // Minimal idle wear
                            tool.WearLevel += 0.00001f;
                        }
                    }
                }
            }
        }

        private void CheckToolCondition(Tool tool)
        {
            var previousCondition = tool.Condition;

            // Update condition based on wear
            if (tool.WearLevel >= 1.0f)
            {
                tool.Condition = ToolCondition.WornOut;
                tool.Status = ToolStatus.WornOut;
                OnToolWornOut?.Invoke(tool);
                RequestReplacement(tool, "Tool worn out");
            }
            else if (tool.WearLevel >= 0.8f)
            {
                tool.Condition = ToolCondition.Critical;
                if (previousCondition != ToolCondition.Critical)
                {
                    RaiseAlert(tool, ToolAlertType.CriticalWear, $"Critical wear: {tool.WearLevel:P0}");
                    RequestReplacement(tool, "Critical wear level");
                }
            }
            else if (tool.WearLevel >= 0.6f)
            {
                tool.Condition = ToolCondition.Warning;
                if (previousCondition != ToolCondition.Warning)
                {
                    RaiseAlert(tool, ToolAlertType.WearWarning, $"High wear: {tool.WearLevel:P0}");
                }
            }
            else if (tool.WearLevel >= 0.3f)
            {
                tool.Condition = ToolCondition.Used;
            }

            // Check remaining life threshold
            float lifeRatio = tool.RemainingLife / tool.Definition.ExpectedLife;
            if (lifeRatio < lifePredictionThreshold && tool.Condition != ToolCondition.WornOut)
            {
                RaiseAlert(tool, ToolAlertType.LowLife, $"Low remaining life: {tool.RemainingLife:F0}s");
            }
        }

        public void ReportToolBreakage(string toolId, string description = "")
        {
            if (!tools.TryGetValue(toolId, out var tool))
                return;

            tool.Condition = ToolCondition.Broken;
            tool.Status = ToolStatus.Broken;

            EndUsageSession(toolId);
            LogHistory(tool, ToolEvent.Broken, description);
            OnToolBroken?.Invoke(tool);

            RaiseAlert(tool, ToolAlertType.Breakage, $"Tool broken: {description}");
            RequestReplacement(tool, "Tool breakage", true);
        }

        private void RaiseAlert(Tool tool, ToolAlertType alertType, string message)
        {
            var alert = new ToolAlert
            {
                AlertId = Guid.NewGuid().ToString(),
                ToolId = tool.ToolId,
                AlertType = alertType,
                Message = message,
                Timestamp = DateTime.UtcNow,
                MachineId = tool.MachineId
            };

            OnToolAlert?.Invoke(alert);
            Debug.LogWarning($"[ToolMgmt] Alert: {message}");
        }

        #endregion

        #region Tool Replacement

        private void RequestReplacement(Tool tool, string reason, bool urgent = false)
        {
            var request = new ToolReplacementRequest
            {
                RequestId = Guid.NewGuid().ToString(),
                ToolId = tool.ToolId,
                ToolTypeId = tool.Definition.ToolTypeId,
                MachineId = tool.MachineId,
                PocketNumber = tool.PocketNumber,
                Reason = reason,
                IsUrgent = urgent,
                RequestTime = DateTime.UtcNow
            };

            // Find replacement tool
            var replacement = FindReplacementTool(tool.Definition.ToolTypeId, tool.CribId);
            if (replacement != null)
            {
                request.ReplacementToolId = replacement.ToolId;
                request.Status = ReplacementStatus.Pending;
            }
            else
            {
                request.Status = ReplacementStatus.NoStock;
                RaiseAlert(tool, ToolAlertType.NoReplacement, $"No replacement available for {tool.Definition.Name}");
            }

            replacementQueue.Enqueue(request);
            OnReplacementNeeded?.Invoke(request);

            if (enableAutoReplacement && request.Status == ReplacementStatus.Pending)
            {
                StartCoroutine(AutoReplaceTool(request));
            }
        }

        private Tool FindReplacementTool(string toolTypeId, string preferredCrib)
        {
            // First check preferred crib
            var available = GetAvailableTools(toolTypeId)
                .Where(t => t.CribId == preferredCrib)
                .FirstOrDefault();

            if (available != null) return available;

            // Check any crib
            return GetAvailableTools(toolTypeId).FirstOrDefault();
        }

        private IEnumerator AutoReplaceTool(ToolReplacementRequest request)
        {
            Debug.Log($"[ToolMgmt] Auto-replacing tool: {request.ToolId}");

            yield return new WaitForSeconds(2f); // Simulate replacement time

            if (ExecuteReplacement(request))
            {
                request.Status = ReplacementStatus.Completed;
                request.CompletedTime = DateTime.UtcNow;
                Debug.Log($"[ToolMgmt] Tool replaced successfully");
            }
            else
            {
                request.Status = ReplacementStatus.Failed;
                Debug.LogWarning($"[ToolMgmt] Tool replacement failed");
            }
        }

        public bool ExecuteReplacement(ToolReplacementRequest request)
        {
            if (string.IsNullOrEmpty(request.ReplacementToolId))
                return false;

            var oldTool = GetTool(request.ToolId);
            var newTool = GetTool(request.ReplacementToolId);

            if (oldTool == null || newTool == null)
                return false;

            // Unload old tool
            if (!string.IsNullOrEmpty(oldTool.MachineId) && request.PocketNumber.HasValue)
            {
                UnloadToolFromMachine(oldTool.MachineId, oldTool.ToolId);
            }

            // Load new tool
            if (!string.IsNullOrEmpty(request.MachineId) && request.PocketNumber.HasValue)
            {
                LoadToolToMachine(request.MachineId, newTool.ToolId, request.PocketNumber.Value);
            }

            // Update old tool status
            if (oldTool.Condition == ToolCondition.WornOut || oldTool.Condition == ToolCondition.Broken)
            {
                oldTool.Status = ToolStatus.Scrapped;
                LogHistory(oldTool, ToolEvent.Scrapped, "Replaced due to wear/damage");
            }
            else
            {
                oldTool.Status = ToolStatus.Available;
            }

            OnToolReplaced?.Invoke(newTool);
            return true;
        }

        public List<ToolReplacementRequest> GetPendingReplacements()
        {
            return replacementQueue.Where(r => r.Status == ReplacementStatus.Pending).ToList();
        }

        #endregion

        #region Tool Crib Management

        public ToolCrib CreateToolCrib(ToolCribConfig config)
        {
            var crib = new ToolCrib
            {
                CribId = config.CribId,
                Name = config.Name,
                Location = config.Location,
                Capacity = config.Capacity,
                IsAutomated = config.IsAutomated,
                ToolIds = new List<string>()
            };

            toolCribs[crib.CribId] = crib;
            Debug.Log($"[ToolMgmt] Created tool crib: {config.Name}");
            return crib;
        }

        public bool TransferTool(string toolId, string targetCribId)
        {
            if (!tools.TryGetValue(toolId, out var tool) ||
                !toolCribs.TryGetValue(targetCribId, out var targetCrib))
            {
                return false;
            }

            if (tool.Status != ToolStatus.Available)
            {
                Debug.LogWarning("[ToolMgmt] Tool must be available for transfer");
                return false;
            }

            // Remove from current crib
            if (!string.IsNullOrEmpty(tool.CribId) && toolCribs.TryGetValue(tool.CribId, out var sourceCrib))
            {
                sourceCrib.ToolIds.Remove(toolId);
            }

            // Add to target crib
            tool.CribId = targetCribId;
            targetCrib.ToolIds.Add(toolId);

            LogHistory(tool, ToolEvent.Transferred, $"Transferred to {targetCrib.Name}");
            return true;
        }

        public ToolCribInventory GetCribInventory(string cribId)
        {
            if (!toolCribs.TryGetValue(cribId, out var crib))
                return null;

            var inventory = new ToolCribInventory
            {
                CribId = cribId,
                CribName = crib.Name,
                TotalTools = crib.ToolIds.Count,
                Capacity = crib.Capacity,
                ToolsByType = new Dictionary<string, int>(),
                ToolsByCondition = new Dictionary<ToolCondition, int>()
            };

            foreach (var toolId in crib.ToolIds)
            {
                if (tools.TryGetValue(toolId, out var tool))
                {
                    // By type
                    if (!inventory.ToolsByType.ContainsKey(tool.Definition.ToolTypeId))
                        inventory.ToolsByType[tool.Definition.ToolTypeId] = 0;
                    inventory.ToolsByType[tool.Definition.ToolTypeId]++;

                    // By condition
                    if (!inventory.ToolsByCondition.ContainsKey(tool.Condition))
                        inventory.ToolsByCondition[tool.Condition] = 0;
                    inventory.ToolsByCondition[tool.Condition]++;
                }
            }

            return inventory;
        }

        #endregion

        #region History & Reporting

        private void LogHistory(Tool tool, ToolEvent eventType, string description)
        {
            var entry = new ToolHistoryEntry
            {
                EntryId = Guid.NewGuid().ToString(),
                ToolId = tool.ToolId,
                Timestamp = DateTime.UtcNow,
                Event = eventType,
                Description = description,
                WearLevel = tool.WearLevel,
                TotalCutTime = tool.TotalCutTime,
                MachineId = tool.MachineId
            };

            toolHistory.Add(entry);

            // Trim history
            if (toolHistory.Count > maxToolHistoryEntries)
            {
                toolHistory.RemoveRange(0, toolHistory.Count - maxToolHistoryEntries);
            }
        }

        public List<ToolHistoryEntry> GetToolHistory(string toolId, int limit = 100)
        {
            return toolHistory
                .Where(h => h.ToolId == toolId)
                .OrderByDescending(h => h.Timestamp)
                .Take(limit)
                .ToList();
        }

        public ToolLifeReport GenerateLifeReport(string toolTypeId = null)
        {
            var query = tools.Values.AsEnumerable();
            if (!string.IsNullOrEmpty(toolTypeId))
            {
                query = query.Where(t => t.Definition.ToolTypeId == toolTypeId);
            }

            var toolsList = query.ToList();

            return new ToolLifeReport
            {
                GeneratedAt = DateTime.UtcNow,
                ToolTypeId = toolTypeId,
                TotalTools = toolsList.Count,
                AverageWearLevel = toolsList.Average(t => t.WearLevel),
                AverageLife = toolsList.Average(t => t.TotalCutTime),
                ExpectedLife = toolsList.FirstOrDefault()?.Definition.ExpectedLife ?? 0,
                ToolsNearEndOfLife = toolsList.Count(t => t.Condition == ToolCondition.Critical || t.Condition == ToolCondition.Warning),
                BrokenTools = toolsList.Count(t => t.Condition == ToolCondition.Broken),
                WornOutTools = toolsList.Count(t => t.Condition == ToolCondition.WornOut)
            };
        }

        #endregion

        #region Statistics

        public ToolManagementStats GetStatistics()
        {
            return new ToolManagementStats
            {
                TotalTools = tools.Count,
                AvailableTools = tools.Values.Count(t => t.Status == ToolStatus.Available),
                LoadedTools = tools.Values.Count(t => t.Status == ToolStatus.Loaded),
                InUseTools = tools.Values.Count(t => t.Status == ToolStatus.InUse),
                WornOutTools = tools.Values.Count(t => t.Condition == ToolCondition.WornOut),
                BrokenTools = tools.Values.Count(t => t.Condition == ToolCondition.Broken),
                ToolTypes = toolLibrary.Count,
                ToolCribs = toolCribs.Count,
                PendingReplacements = replacementQueue.Count(r => r.Status == ReplacementStatus.Pending),
                ActiveSessions = activeSessions.Count
            };
        }

        public int ToolCount => tools.Count;

        #endregion
    }

    #region Enums

    public enum ToolCategory
    {
        EndMill,
        BallEndMill,
        FaceMill,
        Drill,
        Tap,
        Reamer,
        Boring,
        Chamfer,
        ThreadMill,
        SlotDrill,
        TSlotCutter,
        Engraver,
        Custom
    }

    public enum ToolMaterial
    {
        HSS,
        Carbide,
        Cermet,
        Ceramic,
        CBN,
        PCD
    }

    public enum ToolCoating
    {
        None,
        TiN,
        TiCN,
        TiAlN,
        AlTiN,
        DLC,
        Diamond,
        ZrN
    }

    public enum ToolStatus
    {
        Available,
        Assembled,
        Loaded,
        InUse,
        WornOut,
        Broken,
        InRepair,
        Scrapped
    }

    public enum ToolCondition
    {
        New,
        Used,
        Warning,
        Critical,
        WornOut,
        Broken
    }

    public enum HolderStatus
    {
        Available,
        Loaded,
        InUse,
        Damaged
    }

    public enum ToolEvent
    {
        Registered,
        Assembled,
        Disassembled,
        Loaded,
        Unloaded,
        Selected,
        Deselected,
        WearUpdated,
        Broken,
        Replaced,
        Transferred,
        Scrapped
    }

    public enum ToolAlertType
    {
        WearWarning,
        CriticalWear,
        LowLife,
        Breakage,
        NoReplacement,
        MaintenanceDue
    }

    public enum ReplacementStatus
    {
        Pending,
        InProgress,
        Completed,
        Failed,
        Cancelled,
        NoStock
    }

    #endregion

    #region Data Classes

    [System.Serializable]
    public class ToolDefinition
    {
        public string ToolTypeId;
        public string Name;
        public ToolCategory Category;
        public float Diameter;
        public float Length;
        public int FluteCount;
        public ToolMaterial Material;
        public ToolCoating Coating;
        public float ExpectedLife; // seconds
        public float MaxRPM;
        public float MaxFeedRate;
        public bool CoolantRequired;
        public float PointAngle;
        public float ThreadPitch;
        public int InsertCount;
        public string ToleranceClass;
    }

    [System.Serializable]
    public class Tool
    {
        public string ToolId;
        public ToolDefinition Definition;
        public string SerialNumber;
        public string Manufacturer;
        public DateTime PurchaseDate;
        public ToolStatus Status;
        public ToolCondition Condition;
        public float WearLevel; // 0 to 1
        public float RemainingLife;
        public float TotalCutTime;
        public int TotalCuts;
        public string CribId;
        public string Location;
        public string HolderId;
        public string MachineId;
        public int? PocketNumber;
        public float TotalLength;
        public DateTime? LoadedAt;
        public float MeasuredDiameter;
        public float MeasuredLength;
        public DateTime? LastMeasurement;
    }

    [System.Serializable]
    public class ToolRegistration
    {
        public string ToolId;
        public string ToolTypeId;
        public string SerialNumber;
        public string Manufacturer;
        public DateTime PurchaseDate;
        public string CribId;
        public string Location;
    }

    [System.Serializable]
    public class ToolHolder
    {
        public string HolderId;
        public string Name;
        public string Type;
        public string TaperType;
        public string Collet;
        public float GaugeLength;
        public float MaxRPM;
        public float Runout;
        public HolderStatus Status;
        public string InstalledToolId;
    }

    [System.Serializable]
    public class ToolHolderConfig
    {
        public string HolderId;
        public string Name;
        public string Type;
        public string TaperType;
        public string Collet;
        public float GaugeLength;
        public float MaxRPM;
        public float Runout;
    }

    [System.Serializable]
    public class ToolCrib
    {
        public string CribId;
        public string Name;
        public string Location;
        public int Capacity;
        public bool IsAutomated;
        public List<string> ToolIds;
    }

    [System.Serializable]
    public class ToolCribConfig
    {
        public string CribId;
        public string Name;
        public string Location;
        public int Capacity;
        public bool IsAutomated;
    }

    [System.Serializable]
    public class ToolCribInventory
    {
        public string CribId;
        public string CribName;
        public int TotalTools;
        public int Capacity;
        public Dictionary<string, int> ToolsByType;
        public Dictionary<ToolCondition, int> ToolsByCondition;
    }

    [System.Serializable]
    public class CutParameters
    {
        public float CutTime;
        public float SpindleSpeed;
        public float FeedRate;
        public float DepthOfCut;
        public float MaterialHardness;
        public float CuttingTemperature;
        public bool CoolantActive;
        public float MaterialRemoved;
    }

    [System.Serializable]
    public class ToolUsageSession
    {
        public string SessionId;
        public string ToolId;
        public string MachineId;
        public DateTime StartTime;
        public DateTime EndTime;
        public float Duration;
        public float StartWearLevel;
        public float EndWearLevel;
        public float WearAccumulated;
        public int CutCount;
        public float TotalCutTime;
        public float MaterialRemoved;
    }

    [System.Serializable]
    public class ToolHistoryEntry
    {
        public string EntryId;
        public string ToolId;
        public DateTime Timestamp;
        public ToolEvent Event;
        public string Description;
        public float WearLevel;
        public float TotalCutTime;
        public string MachineId;
    }

    [System.Serializable]
    public class ToolLifeStats
    {
        public string ToolId;
        public float ExpectedLife;
        public int TotalSessions;
        public float TotalRunTime;
        public int TotalCuts;
        public float TotalWear;
        public float AverageWearPerSession;
        public List<WearDataPoint> WearTrend = new List<WearDataPoint>();
    }

    [System.Serializable]
    public class WearDataPoint
    {
        public DateTime Timestamp;
        public float WearLevel;
        public float CumulativeCutTime;
    }

    [System.Serializable]
    public class ToolAlert
    {
        public string AlertId;
        public string ToolId;
        public ToolAlertType AlertType;
        public string Message;
        public DateTime Timestamp;
        public string MachineId;
    }

    [System.Serializable]
    public class ToolReplacementRequest
    {
        public string RequestId;
        public string ToolId;
        public string ToolTypeId;
        public string MachineId;
        public int? PocketNumber;
        public string Reason;
        public bool IsUrgent;
        public DateTime RequestTime;
        public DateTime? CompletedTime;
        public string ReplacementToolId;
        public ReplacementStatus Status;
    }

    [System.Serializable]
    public class ToolLifeReport
    {
        public DateTime GeneratedAt;
        public string ToolTypeId;
        public int TotalTools;
        public float AverageWearLevel;
        public float AverageLife;
        public float ExpectedLife;
        public int ToolsNearEndOfLife;
        public int BrokenTools;
        public int WornOutTools;
    }

    [System.Serializable]
    public class ToolManagementStats
    {
        public int TotalTools;
        public int AvailableTools;
        public int LoadedTools;
        public int InUseTools;
        public int WornOutTools;
        public int BrokenTools;
        public int ToolTypes;
        public int ToolCribs;
        public int PendingReplacements;
        public int ActiveSessions;
    }

    #endregion
}
