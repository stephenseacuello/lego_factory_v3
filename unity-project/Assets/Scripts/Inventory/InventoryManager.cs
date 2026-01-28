using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Networking;

namespace CNCScada.Inventory
{
    /// <summary>
    /// Inventory and material tracking system for the Digital Twin.
    /// Tracks raw materials, work-in-progress, finished goods, and tools.
    /// Supports location tracking, reorder points, and material consumption.
    /// </summary>
    public class InventoryManager : MonoBehaviour
    {
        [Header("Configuration")]
        [SerializeField] private string backendUrl = "http://localhost:5001/api/inventory";
        [SerializeField] private bool syncWithBackend = true;
        [SerializeField] private float syncInterval = 60f;

        [Header("Storage Locations")]
        [SerializeField] private List<StorageLocation> storageLocations = new List<StorageLocation>();

        [Header("Inventory Items")]
        [SerializeField] private List<InventoryItem> rawMaterials = new List<InventoryItem>();
        [SerializeField] private List<InventoryItem> workInProgress = new List<InventoryItem>();
        [SerializeField] private List<InventoryItem> finishedGoods = new List<InventoryItem>();
        [SerializeField] private List<ToolInventoryItem> tools = new List<ToolInventoryItem>();

        [Header("Statistics")]
        [SerializeField] private int totalItemCount;
        [SerializeField] private int lowStockAlerts;
        [SerializeField] private float totalInventoryValue;

        // Lookup dictionaries
        private Dictionary<string, InventoryItem> itemLookup = new Dictionary<string, InventoryItem>();
        private Dictionary<string, StorageLocation> locationLookup = new Dictionary<string, StorageLocation>();

        // Transaction history
        private List<InventoryTransaction> transactionHistory = new List<InventoryTransaction>();
        private const int MaxTransactionHistory = 1000;

        // Events
        public event Action<InventoryItem> OnItemAdded;
        public event Action<InventoryItem> OnItemUpdated;
        public event Action<InventoryItem> OnItemRemoved;
        public event Action<InventoryItem> OnLowStockAlert;
        public event Action<InventoryTransaction> OnTransactionRecorded;

        // Singleton
        public static InventoryManager Instance { get; private set; }

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
                return;
            }

            InitializeDefaultLocations();
            InitializeDemoInventory();
        }

        private void Start()
        {
            if (syncWithBackend)
            {
                StartCoroutine(SyncLoop());
            }

            UpdateStatistics();
        }

        private void InitializeDefaultLocations()
        {
            // Raw material storage
            storageLocations.Add(new StorageLocation
            {
                locationId = "LOC_RAW_01",
                locationName = "Raw Material Rack A",
                locationType = LocationType.RawMaterial,
                position = new Vector3(-1f, 0, 0.5f),
                capacity = 100
            });

            storageLocations.Add(new StorageLocation
            {
                locationId = "LOC_RAW_02",
                locationName = "Raw Material Rack B",
                locationType = LocationType.RawMaterial,
                position = new Vector3(-1f, 0, -0.5f),
                capacity = 100
            });

            // WIP buffer
            storageLocations.Add(new StorageLocation
            {
                locationId = "LOC_WIP_01",
                locationName = "CNC Input Buffer",
                locationType = LocationType.WorkInProgress,
                position = new Vector3(0.3f, 0.36f, -0.1f),
                capacity = 20
            });

            storageLocations.Add(new StorageLocation
            {
                locationId = "LOC_WIP_02",
                locationName = "CNC Output Buffer",
                locationType = LocationType.WorkInProgress,
                position = new Vector3(-0.3f, 0.36f, -0.1f),
                capacity = 20
            });

            // Finished goods
            storageLocations.Add(new StorageLocation
            {
                locationId = "LOC_FG_01",
                locationName = "Finished Goods Bin 1",
                locationType = LocationType.FinishedGoods,
                position = new Vector3(0.4f, 0.1f, 0.3f),
                capacity = 50
            });

            storageLocations.Add(new StorageLocation
            {
                locationId = "LOC_FG_02",
                locationName = "Finished Goods Bin 2",
                locationType = LocationType.FinishedGoods,
                position = new Vector3(-0.4f, 0.1f, 0.3f),
                capacity = 50
            });

            // Tool storage
            storageLocations.Add(new StorageLocation
            {
                locationId = "LOC_TOOL_01",
                locationName = "Tool Crib",
                locationType = LocationType.ToolStorage,
                position = new Vector3(1f, 0.5f, 0),
                capacity = 50
            });

            // Build lookup
            foreach (var loc in storageLocations)
            {
                locationLookup[loc.locationId] = loc;
            }
        }

        private void InitializeDemoInventory()
        {
            // Raw materials
            AddItem(new InventoryItem
            {
                itemId = "MAT_AL6061_ROUND",
                itemName = "Aluminum 6061 Round Bar",
                itemType = ItemType.RawMaterial,
                category = "Aluminum",
                partNumber = "AL6061-R-1.0",
                description = "1 inch diameter aluminum round bar",
                quantity = 25,
                unit = "pieces",
                unitCost = 15.50f,
                reorderPoint = 10,
                reorderQuantity = 50,
                locationId = "LOC_RAW_01",
                dimensions = new Vector3(25.4f, 25.4f, 300f) // mm
            });

            AddItem(new InventoryItem
            {
                itemId = "MAT_AL6061_PLATE",
                itemName = "Aluminum 6061 Plate",
                itemType = ItemType.RawMaterial,
                category = "Aluminum",
                partNumber = "AL6061-P-0.5",
                description = "0.5 inch thick aluminum plate",
                quantity = 15,
                unit = "sheets",
                unitCost = 45.00f,
                reorderPoint = 5,
                reorderQuantity = 20,
                locationId = "LOC_RAW_01",
                dimensions = new Vector3(304.8f, 12.7f, 304.8f)
            });

            AddItem(new InventoryItem
            {
                itemId = "MAT_BRASS_ROUND",
                itemName = "Brass Round Bar",
                itemType = ItemType.RawMaterial,
                category = "Brass",
                partNumber = "BRASS-R-0.75",
                description = "0.75 inch diameter brass round bar",
                quantity = 30,
                unit = "pieces",
                unitCost = 22.00f,
                reorderPoint = 10,
                reorderQuantity = 40,
                locationId = "LOC_RAW_02"
            });

            AddItem(new InventoryItem
            {
                itemId = "MAT_ACETAL_ROUND",
                itemName = "Acetal Delrin Round",
                itemType = ItemType.RawMaterial,
                category = "Plastic",
                partNumber = "ACETAL-R-1.5",
                description = "1.5 inch diameter acetal rod",
                quantity = 20,
                unit = "pieces",
                unitCost = 18.00f,
                reorderPoint = 8,
                reorderQuantity = 30,
                locationId = "LOC_RAW_02"
            });

            // Tools
            AddTool(new ToolInventoryItem
            {
                itemId = "TOOL_EM_0125",
                itemName = "1/8\" End Mill",
                toolType = ToolType.EndMill,
                diameter = 3.175f,
                flutes = 2,
                material = "Carbide",
                coating = "TiAlN",
                quantity = 10,
                usedCount = 3,
                maxLifeMinutes = 120,
                currentLifeMinutes = 45,
                locationId = "LOC_TOOL_01",
                unitCost = 25.00f
            });

            AddTool(new ToolInventoryItem
            {
                itemId = "TOOL_EM_0250",
                itemName = "1/4\" End Mill",
                toolType = ToolType.EndMill,
                diameter = 6.35f,
                flutes = 4,
                material = "Carbide",
                coating = "TiAlN",
                quantity = 8,
                usedCount = 2,
                maxLifeMinutes = 180,
                currentLifeMinutes = 120,
                locationId = "LOC_TOOL_01",
                unitCost = 35.00f
            });

            AddTool(new ToolInventoryItem
            {
                itemId = "TOOL_DRILL_0125",
                itemName = "1/8\" Drill Bit",
                toolType = ToolType.DrillBit,
                diameter = 3.175f,
                flutes = 2,
                material = "HSS",
                coating = "TiN",
                quantity = 15,
                usedCount = 5,
                maxLifeMinutes = 60,
                currentLifeMinutes = 30,
                locationId = "LOC_TOOL_01",
                unitCost = 8.00f
            });
        }

        private IEnumerator SyncLoop()
        {
            while (true)
            {
                yield return StartCoroutine(SyncWithBackend());
                yield return new WaitForSeconds(syncInterval);
            }
        }

        private IEnumerator SyncWithBackend()
        {
            // Upload local changes
            // Download remote updates
            yield return null;
        }

        // =========================================================================
        // Item Management
        // =========================================================================

        /// <summary>
        /// Add a new inventory item
        /// </summary>
        public void AddItem(InventoryItem item)
        {
            if (string.IsNullOrEmpty(item.itemId))
            {
                item.itemId = $"ITEM_{DateTime.Now.Ticks}";
            }

            item.lastUpdated = DateTime.Now;
            itemLookup[item.itemId] = item;

            switch (item.itemType)
            {
                case ItemType.RawMaterial:
                    rawMaterials.Add(item);
                    break;
                case ItemType.WorkInProgress:
                    workInProgress.Add(item);
                    break;
                case ItemType.FinishedGood:
                    finishedGoods.Add(item);
                    break;
            }

            // Update location
            if (locationLookup.TryGetValue(item.locationId, out var location))
            {
                location.currentQuantity += item.quantity;
            }

            RecordTransaction(new InventoryTransaction
            {
                transactionType = TransactionType.Receipt,
                itemId = item.itemId,
                quantity = item.quantity,
                reason = "Initial stock"
            });

            UpdateStatistics();
            OnItemAdded?.Invoke(item);

            Debug.Log($"[Inventory] Added item: {item.itemName} x{item.quantity}");
        }

        /// <summary>
        /// Add a tool to inventory
        /// </summary>
        public void AddTool(ToolInventoryItem tool)
        {
            if (string.IsNullOrEmpty(tool.itemId))
            {
                tool.itemId = $"TOOL_{DateTime.Now.Ticks}";
            }

            tool.lastUpdated = DateTime.Now;
            tools.Add(tool);
            itemLookup[tool.itemId] = tool;

            UpdateStatistics();

            Debug.Log($"[Inventory] Added tool: {tool.itemName} x{tool.quantity}");
        }

        /// <summary>
        /// Update item quantity (add or remove)
        /// </summary>
        public bool UpdateQuantity(string itemId, int quantityChange, string reason = "")
        {
            if (!itemLookup.TryGetValue(itemId, out var item))
            {
                Debug.LogWarning($"[Inventory] Item not found: {itemId}");
                return false;
            }

            int newQuantity = item.quantity + quantityChange;

            if (newQuantity < 0)
            {
                Debug.LogWarning($"[Inventory] Insufficient stock for {item.itemName}");
                return false;
            }

            item.quantity = newQuantity;
            item.lastUpdated = DateTime.Now;

            // Update location
            if (locationLookup.TryGetValue(item.locationId, out var location))
            {
                location.currentQuantity += quantityChange;
            }

            // Record transaction
            RecordTransaction(new InventoryTransaction
            {
                transactionType = quantityChange > 0 ? TransactionType.Receipt : TransactionType.Issue,
                itemId = itemId,
                quantity = Math.Abs(quantityChange),
                reason = reason
            });

            // Check reorder point
            if (item.quantity <= item.reorderPoint && item.quantity > 0)
            {
                lowStockAlerts++;
                OnLowStockAlert?.Invoke(item);

                // Raise notification
                var notificationService = FindObjectOfType<CNCScada.Notifications.NotificationService>();
                notificationService?.Notify(
                    "Low Stock Alert",
                    $"{item.itemName} is below reorder point ({item.quantity}/{item.reorderPoint})",
                    CNCScada.Notifications.NotificationType.Warning
                );
            }

            UpdateStatistics();
            OnItemUpdated?.Invoke(item);

            Debug.Log($"[Inventory] Updated {item.itemName}: {quantityChange:+0;-0} -> {item.quantity}");

            return true;
        }

        /// <summary>
        /// Consume material for production
        /// </summary>
        public bool ConsumeMaterial(string itemId, int quantity, string workOrderId = "")
        {
            return UpdateQuantity(itemId, -quantity, $"Consumed for WO: {workOrderId}");
        }

        /// <summary>
        /// Receive material into inventory
        /// </summary>
        public bool ReceiveMaterial(string itemId, int quantity, string purchaseOrderId = "")
        {
            return UpdateQuantity(itemId, quantity, $"Received from PO: {purchaseOrderId}");
        }

        /// <summary>
        /// Transfer item between locations
        /// </summary>
        public bool TransferItem(string itemId, string fromLocationId, string toLocationId, int quantity)
        {
            if (!itemLookup.TryGetValue(itemId, out var item))
            {
                return false;
            }

            if (!locationLookup.TryGetValue(fromLocationId, out var fromLoc) ||
                !locationLookup.TryGetValue(toLocationId, out var toLoc))
            {
                return false;
            }

            if (item.locationId != fromLocationId)
            {
                Debug.LogWarning($"[Inventory] Item {itemId} is not at location {fromLocationId}");
                return false;
            }

            if (toLoc.currentQuantity + quantity > toLoc.capacity)
            {
                Debug.LogWarning($"[Inventory] Destination location {toLocationId} at capacity");
                return false;
            }

            fromLoc.currentQuantity -= quantity;
            toLoc.currentQuantity += quantity;
            item.locationId = toLocationId;
            item.lastUpdated = DateTime.Now;

            RecordTransaction(new InventoryTransaction
            {
                transactionType = TransactionType.Transfer,
                itemId = itemId,
                quantity = quantity,
                fromLocationId = fromLocationId,
                toLocationId = toLocationId,
                reason = "Location transfer"
            });

            OnItemUpdated?.Invoke(item);

            Debug.Log($"[Inventory] Transferred {item.itemName} x{quantity} from {fromLoc.locationName} to {toLoc.locationName}");

            return true;
        }

        /// <summary>
        /// Move item from WIP to finished goods
        /// </summary>
        public InventoryItem CompleteProduction(string wipItemId, string finishedPartNumber, int quantity)
        {
            // Consume WIP
            if (!ConsumeMaterial(wipItemId, quantity, "Production complete"))
            {
                return null;
            }

            // Create or update finished goods
            var existingFG = finishedGoods.Find(fg => fg.partNumber == finishedPartNumber);

            if (existingFG != null)
            {
                UpdateQuantity(existingFG.itemId, quantity, "Production complete");
                return existingFG;
            }

            var newFG = new InventoryItem
            {
                itemId = $"FG_{DateTime.Now.Ticks}",
                itemName = finishedPartNumber,
                itemType = ItemType.FinishedGood,
                partNumber = finishedPartNumber,
                quantity = quantity,
                unit = "pieces",
                locationId = "LOC_FG_01"
            };

            AddItem(newFG);

            return newFG;
        }

        /// <summary>
        /// Record tool usage
        /// </summary>
        public void RecordToolUsage(string toolId, float minutesUsed)
        {
            var tool = tools.Find(t => t.itemId == toolId);
            if (tool == null)
            {
                return;
            }

            tool.currentLifeMinutes += minutesUsed;
            tool.lastUpdated = DateTime.Now;

            // Check if tool needs replacement
            if (tool.currentLifeMinutes >= tool.maxLifeMinutes)
            {
                tool.usedCount++;
                tool.currentLifeMinutes = 0;

                if (tool.usedCount >= tool.quantity)
                {
                    // All tools used, need reorder
                    OnLowStockAlert?.Invoke(tool);

                    var notificationService = FindObjectOfType<CNCScada.Notifications.NotificationService>();
                    notificationService?.Notify(
                        "Tool Replacement Required",
                        $"{tool.itemName} has reached end of life",
                        CNCScada.Notifications.NotificationType.Warning
                    );
                }
            }

            Debug.Log($"[Inventory] Tool {tool.itemName} used: {minutesUsed:F1} min ({tool.currentLifeMinutes:F0}/{tool.maxLifeMinutes} min)");
        }

        // =========================================================================
        // Query Methods
        // =========================================================================

        public InventoryItem GetItem(string itemId)
        {
            return itemLookup.TryGetValue(itemId, out var item) ? item : null;
        }

        public List<InventoryItem> GetRawMaterials() => new List<InventoryItem>(rawMaterials);
        public List<InventoryItem> GetWorkInProgress() => new List<InventoryItem>(workInProgress);
        public List<InventoryItem> GetFinishedGoods() => new List<InventoryItem>(finishedGoods);
        public List<ToolInventoryItem> GetTools() => new List<ToolInventoryItem>(tools);

        public List<InventoryItem> GetLowStockItems()
        {
            var lowStock = new List<InventoryItem>();

            foreach (var item in itemLookup.Values)
            {
                if (item.quantity <= item.reorderPoint)
                {
                    lowStock.Add(item);
                }
            }

            return lowStock;
        }

        public List<InventoryItem> GetItemsByLocation(string locationId)
        {
            return itemLookup.Values.Where(i => i.locationId == locationId).ToList();
        }

        public List<InventoryItem> GetItemsByCategory(string category)
        {
            return itemLookup.Values.Where(i => i.category == category).ToList();
        }

        public StorageLocation GetLocation(string locationId)
        {
            return locationLookup.TryGetValue(locationId, out var loc) ? loc : null;
        }

        public List<StorageLocation> GetAllLocations() => new List<StorageLocation>(storageLocations);

        public List<InventoryTransaction> GetTransactionHistory(int count = 100)
        {
            return transactionHistory.TakeLast(count).Reverse().ToList();
        }

        // =========================================================================
        // Private Methods
        // =========================================================================

        private void RecordTransaction(InventoryTransaction transaction)
        {
            transaction.transactionId = $"TXN_{DateTime.Now.Ticks}";
            transaction.timestamp = DateTime.Now;

            transactionHistory.Add(transaction);

            while (transactionHistory.Count > MaxTransactionHistory)
            {
                transactionHistory.RemoveAt(0);
            }

            OnTransactionRecorded?.Invoke(transaction);
        }

        private void UpdateStatistics()
        {
            totalItemCount = itemLookup.Count;
            totalInventoryValue = itemLookup.Values.Sum(i => i.quantity * i.unitCost);
            lowStockAlerts = GetLowStockItems().Count;
        }

        // Properties
        public int TotalItemCount => totalItemCount;
        public int LowStockAlerts => lowStockAlerts;
        public float TotalInventoryValue => totalInventoryValue;
        public int RawMaterialCount => rawMaterials.Count;
        public int FinishedGoodsCount => finishedGoods.Count;
        public int ToolCount => tools.Count;
    }

    // =========================================================================
    // Data Types
    // =========================================================================

    public enum ItemType
    {
        RawMaterial,
        WorkInProgress,
        FinishedGood,
        Consumable,
        Tool
    }

    public enum LocationType
    {
        RawMaterial,
        WorkInProgress,
        FinishedGoods,
        ToolStorage,
        Staging,
        Shipping
    }

    public enum TransactionType
    {
        Receipt,
        Issue,
        Transfer,
        Adjustment,
        Scrap,
        Return
    }

    public enum ToolType
    {
        EndMill,
        DrillBit,
        FaceMill,
        BallMill,
        ThreadMill,
        Reamer,
        Tap,
        Insert
    }

    [Serializable]
    public class InventoryItem
    {
        public string itemId;
        public string itemName;
        public ItemType itemType;
        public string category;
        public string partNumber;
        public string description;
        public int quantity;
        public string unit;
        public float unitCost;
        public int reorderPoint;
        public int reorderQuantity;
        public string locationId;
        public Vector3 dimensions;
        public string supplier;
        public DateTime lastUpdated;
        public Dictionary<string, string> customAttributes;

        public float TotalValue => quantity * unitCost;
        public bool IsLowStock => quantity <= reorderPoint;
    }

    [Serializable]
    public class ToolInventoryItem : InventoryItem
    {
        public ToolType toolType;
        public float diameter;
        public int flutes;
        public string material;
        public string coating;
        public int usedCount;
        public float maxLifeMinutes;
        public float currentLifeMinutes;

        public float RemainingLifePercent => maxLifeMinutes > 0 ? (1 - currentLifeMinutes / maxLifeMinutes) * 100f : 0;
        public bool NeedsReplacement => currentLifeMinutes >= maxLifeMinutes * 0.9f;
    }

    [Serializable]
    public class StorageLocation
    {
        public string locationId;
        public string locationName;
        public LocationType locationType;
        public Vector3 position;
        public int capacity;
        public int currentQuantity;
        public bool isActive = true;

        public float UtilizationPercent => capacity > 0 ? (float)currentQuantity / capacity * 100f : 0;
        public bool IsFull => currentQuantity >= capacity;
    }

    [Serializable]
    public class InventoryTransaction
    {
        public string transactionId;
        public TransactionType transactionType;
        public string itemId;
        public int quantity;
        public string fromLocationId;
        public string toLocationId;
        public string reason;
        public string userId;
        public DateTime timestamp;
    }
}
