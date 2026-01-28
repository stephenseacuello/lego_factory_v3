using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Networking;

namespace CNCScada.WorkOrder
{
    /// <summary>
    /// Work order management system for production scheduling and tracking.
    /// Integrates with Flask backend for order management and machine assignment.
    /// Supports priority scheduling, dependencies, and real-time status updates.
    /// </summary>
    public class WorkOrderManager : MonoBehaviour
    {
        [Header("Connection")]
        [SerializeField] private string backendUrl = "http://localhost:5001/api/workorders";
        [SerializeField] private bool syncWithBackend = true;
        [SerializeField] private float syncInterval = 30f;

        [Header("Queue Settings")]
        [SerializeField] private int maxQueueSize = 100;
        [SerializeField] private bool autoAssignMachines = true;
        [SerializeField] private SchedulingMode schedulingMode = SchedulingMode.Priority;

        [Header("Current Status")]
        [SerializeField] private List<WorkOrder> activeOrders = new List<WorkOrder>();
        [SerializeField] private List<WorkOrder> queuedOrders = new List<WorkOrder>();
        [SerializeField] private List<WorkOrder> completedOrders = new List<WorkOrder>();

        [Header("Statistics")]
        [SerializeField] private int totalOrdersProcessed;
        [SerializeField] private int ordersInProgress;
        [SerializeField] private float averageCompletionTimeMinutes;
        [SerializeField] private float onTimeDeliveryRate;

        // Machine assignments
        private Dictionary<string, string> machineAssignments = new Dictionary<string, string>();
        private Dictionary<string, WorkOrder> orderLookup = new Dictionary<string, WorkOrder>();

        // Events
        public event Action<WorkOrder> OnOrderCreated;
        public event Action<WorkOrder> OnOrderStarted;
        public event Action<WorkOrder> OnOrderCompleted;
        public event Action<WorkOrder> OnOrderCancelled;
        public event Action<WorkOrder, WorkOrderStatus> OnOrderStatusChanged;
        public event Action<string, string> OnMachineAssigned;

        // Singleton
        public static WorkOrderManager Instance { get; private set; }

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
        }

        private void Start()
        {
            if (syncWithBackend)
            {
                StartCoroutine(SyncLoop());
            }

            // Create some demo orders
            CreateDemoOrders();
        }

        private void CreateDemoOrders()
        {
            // Create sample work orders for demonstration
            CreateWorkOrder(new WorkOrderRequest
            {
                partNumber = "BRACKET-001",
                partName = "Mounting Bracket",
                quantity = 10,
                priority = OrderPriority.Normal,
                dueDate = DateTime.Now.AddHours(8),
                requiredMachine = "BantamCNC",
                estimatedCycleTimeMinutes = 15,
                gcodeFile = "bracket_001.nc"
            });

            CreateWorkOrder(new WorkOrderRequest
            {
                partNumber = "SHAFT-002",
                partName = "Drive Shaft",
                quantity = 5,
                priority = OrderPriority.High,
                dueDate = DateTime.Now.AddHours(4),
                requiredMachine = "BantamCNC",
                estimatedCycleTimeMinutes = 25,
                gcodeFile = "shaft_002.nc"
            });

            CreateWorkOrder(new WorkOrderRequest
            {
                partNumber = "PLATE-003",
                partName = "Base Plate",
                quantity = 20,
                priority = OrderPriority.Low,
                dueDate = DateTime.Now.AddDays(1),
                requiredMachine = "BantamCNC",
                estimatedCycleTimeMinutes = 8,
                gcodeFile = "plate_003.nc"
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
            // Fetch orders from backend
            using (UnityWebRequest webRequest = UnityWebRequest.Get(backendUrl))
            {
                webRequest.timeout = 10;
                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    try
                    {
                        var response = JsonUtility.FromJson<WorkOrderListResponse>(webRequest.downloadHandler.text);

                        // Merge with local orders
                        foreach (var order in response.orders)
                        {
                            if (!orderLookup.ContainsKey(order.orderId))
                            {
                                AddOrder(order);
                            }
                            else
                            {
                                UpdateOrder(order);
                            }
                        }

                        Debug.Log($"[WorkOrderManager] Synced {response.orders.Length} orders from backend");
                    }
                    catch (Exception ex)
                    {
                        Debug.LogWarning($"[WorkOrderManager] Sync parse error: {ex.Message}");
                    }
                }
            }
        }

        // =========================================================================
        // Order Management
        // =========================================================================

        /// <summary>
        /// Create a new work order
        /// </summary>
        public WorkOrder CreateWorkOrder(WorkOrderRequest request)
        {
            var order = new WorkOrder
            {
                orderId = $"WO-{DateTime.Now:yyyyMMdd}-{totalOrdersProcessed + 1:D4}",
                partNumber = request.partNumber,
                partName = request.partName,
                quantity = request.quantity,
                completedQuantity = 0,
                priority = request.priority,
                status = WorkOrderStatus.Queued,
                createdTime = DateTime.Now,
                dueDate = request.dueDate,
                requiredMachine = request.requiredMachine,
                assignedMachine = null,
                estimatedCycleTimeMinutes = request.estimatedCycleTimeMinutes,
                gcodeFile = request.gcodeFile,
                customerInfo = request.customerInfo,
                notes = request.notes
            };

            AddOrder(order);
            SortQueue();

            OnOrderCreated?.Invoke(order);

            Debug.Log($"[WorkOrderManager] Created order {order.orderId}: {order.partName} x{order.quantity}");

            // Auto-assign machine if enabled
            if (autoAssignMachines && !string.IsNullOrEmpty(order.requiredMachine))
            {
                AssignMachine(order.orderId, order.requiredMachine);
            }

            return order;
        }

        private void AddOrder(WorkOrder order)
        {
            orderLookup[order.orderId] = order;

            switch (order.status)
            {
                case WorkOrderStatus.Queued:
                case WorkOrderStatus.Scheduled:
                    if (!queuedOrders.Contains(order))
                        queuedOrders.Add(order);
                    break;
                case WorkOrderStatus.InProgress:
                case WorkOrderStatus.Paused:
                    if (!activeOrders.Contains(order))
                        activeOrders.Add(order);
                    break;
                case WorkOrderStatus.Completed:
                case WorkOrderStatus.Cancelled:
                    if (!completedOrders.Contains(order))
                        completedOrders.Add(order);
                    break;
            }
        }

        private void UpdateOrder(WorkOrder updatedOrder)
        {
            if (orderLookup.TryGetValue(updatedOrder.orderId, out var existingOrder))
            {
                // Update fields
                existingOrder.status = updatedOrder.status;
                existingOrder.completedQuantity = updatedOrder.completedQuantity;
                existingOrder.assignedMachine = updatedOrder.assignedMachine;
                existingOrder.startTime = updatedOrder.startTime;
                existingOrder.endTime = updatedOrder.endTime;
            }
        }

        /// <summary>
        /// Start a work order
        /// </summary>
        public bool StartOrder(string orderId)
        {
            if (!orderLookup.TryGetValue(orderId, out var order))
            {
                Debug.LogWarning($"[WorkOrderManager] Order not found: {orderId}");
                return false;
            }

            if (order.status != WorkOrderStatus.Queued && order.status != WorkOrderStatus.Scheduled)
            {
                Debug.LogWarning($"[WorkOrderManager] Cannot start order in status: {order.status}");
                return false;
            }

            // Move from queued to active
            queuedOrders.Remove(order);
            activeOrders.Add(order);

            order.status = WorkOrderStatus.InProgress;
            order.startTime = DateTime.Now;
            ordersInProgress++;

            OnOrderStarted?.Invoke(order);
            OnOrderStatusChanged?.Invoke(order, WorkOrderStatus.InProgress);

            Debug.Log($"[WorkOrderManager] Started order {orderId}");

            // Notify production analytics
            var analytics = FindObjectOfType<CNCScada.Analytics.ProductionAnalytics>();
            analytics?.RecordCycleStart(order.assignedMachine ?? order.requiredMachine);

            return true;
        }

        /// <summary>
        /// Record part completion
        /// </summary>
        public void RecordPartComplete(string orderId, bool isGood = true)
        {
            if (!orderLookup.TryGetValue(orderId, out var order))
            {
                return;
            }

            order.completedQuantity++;

            if (isGood)
            {
                order.goodCount++;
            }
            else
            {
                order.scrapCount++;
            }

            // Notify production analytics
            var analytics = FindObjectOfType<CNCScada.Analytics.ProductionAnalytics>();
            analytics?.RecordPartProduced(order.assignedMachine ?? order.requiredMachine, isGood);

            // Check if order is complete
            if (order.completedQuantity >= order.quantity)
            {
                CompleteOrder(orderId);
            }

            Debug.Log($"[WorkOrderManager] Order {orderId}: {order.completedQuantity}/{order.quantity} complete");
        }

        /// <summary>
        /// Complete a work order
        /// </summary>
        public void CompleteOrder(string orderId)
        {
            if (!orderLookup.TryGetValue(orderId, out var order))
            {
                return;
            }

            activeOrders.Remove(order);
            completedOrders.Add(order);

            order.status = WorkOrderStatus.Completed;
            order.endTime = DateTime.Now;
            ordersInProgress--;
            totalOrdersProcessed++;

            // Calculate statistics
            UpdateStatistics();

            // Release machine assignment
            if (!string.IsNullOrEmpty(order.assignedMachine))
            {
                machineAssignments.Remove(order.assignedMachine);
            }

            OnOrderCompleted?.Invoke(order);
            OnOrderStatusChanged?.Invoke(order, WorkOrderStatus.Completed);

            Debug.Log($"[WorkOrderManager] Completed order {orderId} in {order.ActualDuration.TotalMinutes:F1} minutes");

            // Start next queued order for this machine
            if (autoAssignMachines)
            {
                StartNextQueuedOrder(order.assignedMachine ?? order.requiredMachine);
            }
        }

        /// <summary>
        /// Cancel a work order
        /// </summary>
        public void CancelOrder(string orderId, string reason = "")
        {
            if (!orderLookup.TryGetValue(orderId, out var order))
            {
                return;
            }

            queuedOrders.Remove(order);
            activeOrders.Remove(order);
            completedOrders.Add(order);

            order.status = WorkOrderStatus.Cancelled;
            order.endTime = DateTime.Now;
            order.notes += $"\nCancelled: {reason}";

            if (order.status == WorkOrderStatus.InProgress)
            {
                ordersInProgress--;
            }

            // Release machine assignment
            if (!string.IsNullOrEmpty(order.assignedMachine))
            {
                machineAssignments.Remove(order.assignedMachine);
            }

            OnOrderCancelled?.Invoke(order);
            OnOrderStatusChanged?.Invoke(order, WorkOrderStatus.Cancelled);

            Debug.Log($"[WorkOrderManager] Cancelled order {orderId}: {reason}");
        }

        /// <summary>
        /// Pause a work order
        /// </summary>
        public void PauseOrder(string orderId)
        {
            if (!orderLookup.TryGetValue(orderId, out var order))
            {
                return;
            }

            if (order.status == WorkOrderStatus.InProgress)
            {
                order.status = WorkOrderStatus.Paused;
                OnOrderStatusChanged?.Invoke(order, WorkOrderStatus.Paused);
                Debug.Log($"[WorkOrderManager] Paused order {orderId}");
            }
        }

        /// <summary>
        /// Resume a paused order
        /// </summary>
        public void ResumeOrder(string orderId)
        {
            if (!orderLookup.TryGetValue(orderId, out var order))
            {
                return;
            }

            if (order.status == WorkOrderStatus.Paused)
            {
                order.status = WorkOrderStatus.InProgress;
                OnOrderStatusChanged?.Invoke(order, WorkOrderStatus.InProgress);
                Debug.Log($"[WorkOrderManager] Resumed order {orderId}");
            }
        }

        // =========================================================================
        // Machine Assignment
        // =========================================================================

        /// <summary>
        /// Assign a machine to an order
        /// </summary>
        public bool AssignMachine(string orderId, string machineId)
        {
            if (!orderLookup.TryGetValue(orderId, out var order))
            {
                return false;
            }

            // Check if machine is already assigned
            if (machineAssignments.TryGetValue(machineId, out var existingOrderId))
            {
                if (existingOrderId != orderId)
                {
                    Debug.LogWarning($"[WorkOrderManager] Machine {machineId} is assigned to order {existingOrderId}");
                    return false;
                }
            }

            order.assignedMachine = machineId;
            order.status = WorkOrderStatus.Scheduled;
            machineAssignments[machineId] = orderId;

            OnMachineAssigned?.Invoke(orderId, machineId);
            OnOrderStatusChanged?.Invoke(order, WorkOrderStatus.Scheduled);

            Debug.Log($"[WorkOrderManager] Assigned {machineId} to order {orderId}");

            return true;
        }

        /// <summary>
        /// Start next queued order for a machine
        /// </summary>
        private void StartNextQueuedOrder(string machineId)
        {
            var nextOrder = queuedOrders
                .Where(o => o.requiredMachine == machineId || string.IsNullOrEmpty(o.requiredMachine))
                .OrderByDescending(o => o.priority)
                .ThenBy(o => o.dueDate)
                .FirstOrDefault();

            if (nextOrder != null)
            {
                AssignMachine(nextOrder.orderId, machineId);
                StartOrder(nextOrder.orderId);
            }
        }

        // =========================================================================
        // Queue Management
        // =========================================================================

        private void SortQueue()
        {
            switch (schedulingMode)
            {
                case SchedulingMode.Priority:
                    queuedOrders = queuedOrders
                        .OrderByDescending(o => o.priority)
                        .ThenBy(o => o.dueDate)
                        .ThenBy(o => o.createdTime)
                        .ToList();
                    break;

                case SchedulingMode.FIFO:
                    queuedOrders = queuedOrders
                        .OrderBy(o => o.createdTime)
                        .ToList();
                    break;

                case SchedulingMode.EarliestDueDate:
                    queuedOrders = queuedOrders
                        .OrderBy(o => o.dueDate)
                        .ThenByDescending(o => o.priority)
                        .ToList();
                    break;

                case SchedulingMode.ShortestProcessingTime:
                    queuedOrders = queuedOrders
                        .OrderBy(o => o.estimatedCycleTimeMinutes * o.quantity)
                        .ToList();
                    break;
            }
        }

        /// <summary>
        /// Change order priority
        /// </summary>
        public void SetOrderPriority(string orderId, OrderPriority priority)
        {
            if (orderLookup.TryGetValue(orderId, out var order))
            {
                order.priority = priority;
                SortQueue();
                Debug.Log($"[WorkOrderManager] Order {orderId} priority changed to {priority}");
            }
        }

        /// <summary>
        /// Move order to front of queue
        /// </summary>
        public void RushOrder(string orderId)
        {
            if (orderLookup.TryGetValue(orderId, out var order))
            {
                order.priority = OrderPriority.Rush;
                SortQueue();
                Debug.Log($"[WorkOrderManager] Order {orderId} rushed to front of queue");
            }
        }

        // =========================================================================
        // Query Methods
        // =========================================================================

        /// <summary>
        /// Get order by ID
        /// </summary>
        public WorkOrder GetOrder(string orderId)
        {
            return orderLookup.TryGetValue(orderId, out var order) ? order : null;
        }

        /// <summary>
        /// Get all active orders
        /// </summary>
        public List<WorkOrder> GetActiveOrders()
        {
            return new List<WorkOrder>(activeOrders);
        }

        /// <summary>
        /// Get queued orders
        /// </summary>
        public List<WorkOrder> GetQueuedOrders()
        {
            return new List<WorkOrder>(queuedOrders);
        }

        /// <summary>
        /// Get completed orders
        /// </summary>
        public List<WorkOrder> GetCompletedOrders(int limit = 50)
        {
            return completedOrders.TakeLast(limit).ToList();
        }

        /// <summary>
        /// Get orders for a specific machine
        /// </summary>
        public List<WorkOrder> GetOrdersForMachine(string machineId)
        {
            return orderLookup.Values
                .Where(o => o.requiredMachine == machineId || o.assignedMachine == machineId)
                .ToList();
        }

        /// <summary>
        /// Get current order for a machine
        /// </summary>
        public WorkOrder GetCurrentOrderForMachine(string machineId)
        {
            return activeOrders.FirstOrDefault(o => o.assignedMachine == machineId);
        }

        /// <summary>
        /// Get overdue orders
        /// </summary>
        public List<WorkOrder> GetOverdueOrders()
        {
            var now = DateTime.Now;
            return orderLookup.Values
                .Where(o => o.status != WorkOrderStatus.Completed &&
                           o.status != WorkOrderStatus.Cancelled &&
                           o.dueDate < now)
                .ToList();
        }

        // =========================================================================
        // Statistics
        // =========================================================================

        private void UpdateStatistics()
        {
            if (completedOrders.Count == 0)
            {
                return;
            }

            // Average completion time
            var completedWithTimes = completedOrders
                .Where(o => o.startTime != default && o.endTime != default)
                .ToList();

            if (completedWithTimes.Count > 0)
            {
                averageCompletionTimeMinutes = (float)completedWithTimes
                    .Average(o => o.ActualDuration.TotalMinutes);
            }

            // On-time delivery rate
            var ordersWithDueDate = completedOrders
                .Where(o => o.dueDate != default)
                .ToList();

            if (ordersWithDueDate.Count > 0)
            {
                int onTime = ordersWithDueDate.Count(o => o.endTime <= o.dueDate);
                onTimeDeliveryRate = (float)onTime / ordersWithDueDate.Count * 100f;
            }
        }

        /// <summary>
        /// Get production summary
        /// </summary>
        public WorkOrderSummary GetSummary()
        {
            return new WorkOrderSummary
            {
                totalOrdersProcessed = totalOrdersProcessed,
                ordersInProgress = ordersInProgress,
                ordersQueued = queuedOrders.Count,
                overdueOrders = GetOverdueOrders().Count,
                averageCompletionTimeMinutes = averageCompletionTimeMinutes,
                onTimeDeliveryRate = onTimeDeliveryRate,
                totalPartsProduced = completedOrders.Sum(o => o.goodCount),
                totalScrap = completedOrders.Sum(o => o.scrapCount)
            };
        }

        // Properties
        public int TotalOrdersProcessed => totalOrdersProcessed;
        public int OrdersInProgress => ordersInProgress;
        public int QueuedOrderCount => queuedOrders.Count;
        public float AverageCompletionTime => averageCompletionTimeMinutes;
        public float OnTimeDeliveryRate => onTimeDeliveryRate;
    }

    // =========================================================================
    // Data Types
    // =========================================================================

    public enum WorkOrderStatus
    {
        Queued,
        Scheduled,
        InProgress,
        Paused,
        Completed,
        Cancelled
    }

    public enum OrderPriority
    {
        Low = 0,
        Normal = 1,
        High = 2,
        Rush = 3,
        Emergency = 4
    }

    public enum SchedulingMode
    {
        Priority,
        FIFO,
        EarliestDueDate,
        ShortestProcessingTime
    }

    [Serializable]
    public class WorkOrder
    {
        public string orderId;
        public string partNumber;
        public string partName;
        public int quantity;
        public int completedQuantity;
        public int goodCount;
        public int scrapCount;
        public OrderPriority priority;
        public WorkOrderStatus status;
        public DateTime createdTime;
        public DateTime dueDate;
        public DateTime startTime;
        public DateTime endTime;
        public string requiredMachine;
        public string assignedMachine;
        public float estimatedCycleTimeMinutes;
        public string gcodeFile;
        public string customerInfo;
        public string notes;

        public TimeSpan ActualDuration => endTime != default ? endTime - startTime : DateTime.Now - startTime;
        public float Progress => quantity > 0 ? (float)completedQuantity / quantity * 100f : 0;
        public bool IsOverdue => dueDate != default && DateTime.Now > dueDate && status != WorkOrderStatus.Completed;
        public float ScrapRate => completedQuantity > 0 ? (float)scrapCount / completedQuantity * 100f : 0;
    }

    [Serializable]
    public class WorkOrderRequest
    {
        public string partNumber;
        public string partName;
        public int quantity;
        public OrderPriority priority;
        public DateTime dueDate;
        public string requiredMachine;
        public float estimatedCycleTimeMinutes;
        public string gcodeFile;
        public string customerInfo;
        public string notes;
    }

    [Serializable]
    public class WorkOrderListResponse
    {
        public WorkOrder[] orders;
    }

    [Serializable]
    public class WorkOrderSummary
    {
        public int totalOrdersProcessed;
        public int ordersInProgress;
        public int ordersQueued;
        public int overdueOrders;
        public float averageCompletionTimeMinutes;
        public float onTimeDeliveryRate;
        public int totalPartsProduced;
        public int totalScrap;
    }
}
