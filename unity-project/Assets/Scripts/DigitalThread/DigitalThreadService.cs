using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

namespace CNCDigitalTwin.DigitalThread
{
    /// <summary>
    /// Digital Thread Service for complete product lifecycle traceability
    /// Tracks product from design through manufacturing to end-of-life
    /// Implements blockchain-inspired immutable audit trail
    /// </summary>
    public class DigitalThreadService : MonoBehaviour
    {
        public static DigitalThreadService Instance { get; private set; }

        [Header("Configuration")]
        [SerializeField] private bool enableBlockchainVerification = true;
        [SerializeField] private bool enableAutoSync = true;
        [SerializeField] private float syncInterval = 30f;
        [SerializeField] private int maxThreadEvents = 100000;

        // Product threads
        private Dictionary<string, ProductThread> productThreads = new Dictionary<string, ProductThread>();
        private Dictionary<string, PartThread> partThreads = new Dictionary<string, PartThread>();
        private Dictionary<string, ProcessThread> processThreads = new Dictionary<string, ProcessThread>();

        // Design data
        private Dictionary<string, DesignRevision> designRevisions = new Dictionary<string, DesignRevision>();
        private Dictionary<string, BillOfMaterials> billsOfMaterials = new Dictionary<string, BillOfMaterials>();

        // Manufacturing records
        private Dictionary<string, ManufacturingRecord> manufacturingRecords = new Dictionary<string, ManufacturingRecord>();
        private Dictionary<string, QualityRecord> qualityRecords = new Dictionary<string, QualityRecord>();

        // Blockchain-style ledger
        private List<ThreadBlock> ledger = new List<ThreadBlock>();
        private string lastBlockHash = "GENESIS";

        // Events
        public event Action<ProductThread> OnProductThreadCreated;
        public event Action<ThreadEvent> OnThreadEventAdded;
        public event Action<ProductThread> OnProductStateChanged;
        public event Action<QualityRecord> OnQualityRecordAdded;
        public event Action<NonConformance> OnNonConformanceRaised;
        public event Action<string> OnTraceabilityAlert;

        private Coroutine syncCoroutine;

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
            InitializeGenesisBlock();

            if (enableAutoSync)
            {
                syncCoroutine = StartCoroutine(SyncLoop());
            }
        }

        void OnDestroy()
        {
            if (syncCoroutine != null)
                StopCoroutine(syncCoroutine);
        }

        #region Initialization

        private void InitializeGenesisBlock()
        {
            var genesisBlock = new ThreadBlock
            {
                BlockIndex = 0,
                Timestamp = DateTime.UtcNow,
                PreviousHash = "0",
                Events = new List<ThreadEvent>(),
                Nonce = 0
            };

            genesisBlock.Hash = CalculateBlockHash(genesisBlock);
            ledger.Add(genesisBlock);
            lastBlockHash = genesisBlock.Hash;

            Debug.Log("[DigitalThread] Genesis block created");
        }

        #endregion

        #region Product Thread Management

        public ProductThread CreateProductThread(ProductThreadConfig config)
        {
            var thread = new ProductThread
            {
                ProductId = config.ProductId ?? Guid.NewGuid().ToString(),
                SerialNumber = config.SerialNumber ?? GenerateSerialNumber(config.ProductType),
                ProductType = config.ProductType,
                ProductName = config.ProductName,
                DesignRevision = config.DesignRevision,
                BOMRevision = config.BOMRevision,
                CreatedAt = DateTime.UtcNow,
                State = ProductState.Created,
                CurrentPhase = ProductPhase.Design,
                Events = new List<ThreadEvent>(),
                LinkedParts = new List<string>(),
                QualityRecords = new List<string>(),
                Certifications = new List<Certification>()
            };

            // Link to design
            if (!string.IsNullOrEmpty(config.DesignRevision))
            {
                thread.DesignData = designRevisions.GetValueOrDefault(config.DesignRevision);
            }

            // Link to BOM
            if (!string.IsNullOrEmpty(config.BOMRevision))
            {
                thread.BOM = billsOfMaterials.GetValueOrDefault(config.BOMRevision);
            }

            productThreads[thread.ProductId] = thread;

            // Create initial event
            AddThreadEvent(thread.ProductId, new ThreadEvent
            {
                EventType = ThreadEventType.ProductCreated,
                Description = $"Product thread created: {config.ProductName}",
                Data = new Dictionary<string, object>
                {
                    { "productType", config.ProductType },
                    { "serialNumber", thread.SerialNumber }
                }
            });

            OnProductThreadCreated?.Invoke(thread);
            Debug.Log($"[DigitalThread] Created product thread: {thread.SerialNumber}");

            return thread;
        }

        public ProductThread GetProductThread(string productId)
        {
            return productThreads.TryGetValue(productId, out var thread) ? thread : null;
        }

        public ProductThread GetProductBySerialNumber(string serialNumber)
        {
            return productThreads.Values.FirstOrDefault(p => p.SerialNumber == serialNumber);
        }

        public void UpdateProductState(string productId, ProductState newState, string reason = null)
        {
            if (!productThreads.TryGetValue(productId, out var thread))
                return;

            var oldState = thread.State;
            thread.State = newState;
            thread.LastUpdated = DateTime.UtcNow;

            AddThreadEvent(productId, new ThreadEvent
            {
                EventType = ThreadEventType.StateChanged,
                Description = $"State changed: {oldState} -> {newState}",
                Data = new Dictionary<string, object>
                {
                    { "previousState", oldState.ToString() },
                    { "newState", newState.ToString() },
                    { "reason", reason ?? "" }
                }
            });

            OnProductStateChanged?.Invoke(thread);
        }

        public void UpdateProductPhase(string productId, ProductPhase newPhase)
        {
            if (!productThreads.TryGetValue(productId, out var thread))
                return;

            var oldPhase = thread.CurrentPhase;
            thread.CurrentPhase = newPhase;
            thread.LastUpdated = DateTime.UtcNow;

            AddThreadEvent(productId, new ThreadEvent
            {
                EventType = ThreadEventType.PhaseChanged,
                Description = $"Phase changed: {oldPhase} -> {newPhase}"
            });
        }

        private string GenerateSerialNumber(string productType)
        {
            string prefix = productType?.Substring(0, Math.Min(3, productType.Length)).ToUpper() ?? "PRD";
            string timestamp = DateTime.UtcNow.ToString("yyMMdd");
            string random = UnityEngine.Random.Range(1000, 9999).ToString();
            return $"{prefix}-{timestamp}-{random}";
        }

        #endregion

        #region Part Thread Management

        public PartThread CreatePartThread(PartThreadConfig config)
        {
            var thread = new PartThread
            {
                PartId = config.PartId ?? Guid.NewGuid().ToString(),
                PartNumber = config.PartNumber,
                LotNumber = config.LotNumber,
                PartName = config.PartName,
                Material = config.Material,
                Supplier = config.Supplier,
                ReceivedDate = config.ReceivedDate ?? DateTime.UtcNow,
                ExpirationDate = config.ExpirationDate,
                Quantity = config.Quantity,
                UnitOfMeasure = config.UnitOfMeasure,
                State = PartState.Received,
                Events = new List<ThreadEvent>(),
                Certifications = config.Certifications ?? new List<string>(),
                TestResults = new List<TestResult>()
            };

            partThreads[thread.PartId] = thread;

            AddPartEvent(thread.PartId, new ThreadEvent
            {
                EventType = ThreadEventType.PartReceived,
                Description = $"Part received: {config.PartNumber} (Lot: {config.LotNumber})",
                Data = new Dictionary<string, object>
                {
                    { "supplier", config.Supplier },
                    { "quantity", config.Quantity }
                }
            });

            return thread;
        }

        public PartThread GetPartThread(string partId)
        {
            return partThreads.TryGetValue(partId, out var thread) ? thread : null;
        }

        public void LinkPartToProduct(string partId, string productId, string location = null)
        {
            if (!partThreads.TryGetValue(partId, out var part) ||
                !productThreads.TryGetValue(productId, out var product))
            {
                return;
            }

            part.UsedInProducts.Add(productId);
            part.State = PartState.InUse;
            product.LinkedParts.Add(partId);

            AddThreadEvent(productId, new ThreadEvent
            {
                EventType = ThreadEventType.PartLinked,
                Description = $"Part linked: {part.PartNumber}",
                Data = new Dictionary<string, object>
                {
                    { "partId", partId },
                    { "partNumber", part.PartNumber },
                    { "location", location ?? "" }
                }
            });

            AddPartEvent(partId, new ThreadEvent
            {
                EventType = ThreadEventType.PartConsumed,
                Description = $"Part consumed by product: {product.SerialNumber}",
                Data = new Dictionary<string, object>
                {
                    { "productId", productId },
                    { "serialNumber", product.SerialNumber }
                }
            });
        }

        private void AddPartEvent(string partId, ThreadEvent evt)
        {
            if (!partThreads.TryGetValue(partId, out var part))
                return;

            evt.EventId = Guid.NewGuid().ToString();
            evt.Timestamp = DateTime.UtcNow;
            evt.EntityId = partId;
            evt.EntityType = "Part";

            part.Events.Add(evt);
            AddToLedger(evt);
        }

        #endregion

        #region Design Management

        public DesignRevision RegisterDesignRevision(DesignRevisionConfig config)
        {
            var revision = new DesignRevision
            {
                RevisionId = config.RevisionId ?? Guid.NewGuid().ToString(),
                DesignId = config.DesignId,
                Version = config.Version,
                RevisionDate = config.RevisionDate ?? DateTime.UtcNow,
                Author = config.Author,
                Description = config.Description,
                CADFiles = config.CADFiles ?? new List<CADFile>(),
                Drawings = config.Drawings ?? new List<Drawing>(),
                Specifications = config.Specifications ?? new Dictionary<string, string>(),
                ApprovalStatus = ApprovalStatus.Draft,
                ChangeNotes = config.ChangeNotes
            };

            designRevisions[revision.RevisionId] = revision;
            Debug.Log($"[DigitalThread] Registered design revision: {config.DesignId} v{config.Version}");

            return revision;
        }

        public void ApproveDesignRevision(string revisionId, string approvedBy)
        {
            if (!designRevisions.TryGetValue(revisionId, out var revision))
                return;

            revision.ApprovalStatus = ApprovalStatus.Approved;
            revision.ApprovedBy = approvedBy;
            revision.ApprovedDate = DateTime.UtcNow;

            Debug.Log($"[DigitalThread] Design revision approved: {revision.DesignId} v{revision.Version}");
        }

        #endregion

        #region BOM Management

        public BillOfMaterials CreateBOM(BOMConfig config)
        {
            var bom = new BillOfMaterials
            {
                BOMId = config.BOMId ?? Guid.NewGuid().ToString(),
                ProductId = config.ProductId,
                Version = config.Version,
                EffectiveDate = config.EffectiveDate ?? DateTime.UtcNow,
                Status = BOMStatus.Draft,
                Items = config.Items ?? new List<BOMItem>()
            };

            billsOfMaterials[bom.BOMId] = bom;
            Debug.Log($"[DigitalThread] Created BOM: {bom.BOMId}");

            return bom;
        }

        public void AddBOMItem(string bomId, BOMItem item)
        {
            if (!billsOfMaterials.TryGetValue(bomId, out var bom))
                return;

            item.ItemId = item.ItemId ?? Guid.NewGuid().ToString();
            bom.Items.Add(item);
        }

        #endregion

        #region Manufacturing Records

        public ManufacturingRecord CreateManufacturingRecord(string productId, ManufacturingOperation operation)
        {
            if (!productThreads.TryGetValue(productId, out var product))
                return null;

            var record = new ManufacturingRecord
            {
                RecordId = Guid.NewGuid().ToString(),
                ProductId = productId,
                Operation = operation,
                StartTime = DateTime.UtcNow,
                Status = OperationStatus.InProgress,
                Parameters = new Dictionary<string, object>(),
                Measurements = new List<ProcessMeasurement>()
            };

            manufacturingRecords[record.RecordId] = record;
            product.ManufacturingRecords.Add(record.RecordId);

            AddThreadEvent(productId, new ThreadEvent
            {
                EventType = ThreadEventType.OperationStarted,
                Description = $"Operation started: {operation.OperationName}",
                Data = new Dictionary<string, object>
                {
                    { "operation", operation.OperationId },
                    { "machine", operation.MachineId ?? "" },
                    { "program", operation.ProgramId ?? "" }
                }
            });

            return record;
        }

        public void RecordProcessParameter(string recordId, string parameterName, object value)
        {
            if (!manufacturingRecords.TryGetValue(recordId, out var record))
                return;

            record.Parameters[parameterName] = value;
        }

        public void RecordMeasurement(string recordId, ProcessMeasurement measurement)
        {
            if (!manufacturingRecords.TryGetValue(recordId, out var record))
                return;

            measurement.MeasurementId = Guid.NewGuid().ToString();
            measurement.Timestamp = DateTime.UtcNow;
            record.Measurements.Add(measurement);

            // Check tolerance
            if (measurement.Nominal > 0 && measurement.Tolerance > 0)
            {
                float deviation = Mathf.Abs(measurement.Value - measurement.Nominal);
                measurement.IsInTolerance = deviation <= measurement.Tolerance;

                if (!measurement.IsInTolerance)
                {
                    RaiseNonConformance(record.ProductId, NonConformanceType.OutOfTolerance,
                        $"Measurement out of tolerance: {measurement.ParameterName} = {measurement.Value} " +
                        $"(Nominal: {measurement.Nominal} ±{measurement.Tolerance})");
                }
            }
        }

        public void CompleteManufacturingRecord(string recordId, bool success, string notes = null)
        {
            if (!manufacturingRecords.TryGetValue(recordId, out var record))
                return;

            record.EndTime = DateTime.UtcNow;
            record.Duration = (float)(record.EndTime.Value - record.StartTime).TotalSeconds;
            record.Status = success ? OperationStatus.Completed : OperationStatus.Failed;
            record.Notes = notes;

            AddThreadEvent(record.ProductId, new ThreadEvent
            {
                EventType = success ? ThreadEventType.OperationCompleted : ThreadEventType.OperationFailed,
                Description = $"Operation {(success ? "completed" : "failed")}: {record.Operation.OperationName}",
                Data = new Dictionary<string, object>
                {
                    { "duration", record.Duration },
                    { "measurementCount", record.Measurements.Count }
                }
            });
        }

        #endregion

        #region Quality Records

        public QualityRecord CreateQualityRecord(string productId, QualityRecordConfig config)
        {
            if (!productThreads.TryGetValue(productId, out var product))
                return null;

            var record = new QualityRecord
            {
                RecordId = Guid.NewGuid().ToString(),
                ProductId = productId,
                RecordType = config.RecordType,
                InspectionDate = DateTime.UtcNow,
                Inspector = config.Inspector,
                Result = QualityResult.Pending,
                Measurements = new List<QualityMeasurement>(),
                NonConformances = new List<NonConformance>(),
                Notes = config.Notes
            };

            qualityRecords[record.RecordId] = record;
            product.QualityRecords.Add(record.RecordId);

            return record;
        }

        public void RecordQualityMeasurement(string recordId, QualityMeasurement measurement)
        {
            if (!qualityRecords.TryGetValue(recordId, out var record))
                return;

            measurement.MeasurementId = Guid.NewGuid().ToString();
            measurement.Timestamp = DateTime.UtcNow;

            // Check specification limits
            if (measurement.LSL > 0 || measurement.USL > 0)
            {
                measurement.IsConforming = measurement.Value >= measurement.LSL &&
                                           measurement.Value <= measurement.USL;

                if (!measurement.IsConforming)
                {
                    var nc = RaiseNonConformance(record.ProductId, NonConformanceType.Specification,
                        $"Quality measurement non-conforming: {measurement.Characteristic} = {measurement.Value}");

                    if (nc != null)
                    {
                        record.NonConformances.Add(nc);
                    }
                }
            }

            record.Measurements.Add(measurement);
        }

        public void CompleteQualityRecord(string recordId, QualityResult result, string disposition = null)
        {
            if (!qualityRecords.TryGetValue(recordId, out var record))
                return;

            record.Result = result;
            record.CompletedDate = DateTime.UtcNow;
            record.Disposition = disposition;

            // Update product state based on result
            if (productThreads.TryGetValue(record.ProductId, out var product))
            {
                if (result == QualityResult.Pass)
                {
                    product.QualityStatus = QualityStatus.Approved;
                }
                else if (result == QualityResult.Fail)
                {
                    product.QualityStatus = QualityStatus.Rejected;
                    UpdateProductState(product.ProductId, ProductState.OnHold, "Quality inspection failed");
                }
            }

            AddThreadEvent(record.ProductId, new ThreadEvent
            {
                EventType = ThreadEventType.QualityRecorded,
                Description = $"Quality inspection: {result}",
                Data = new Dictionary<string, object>
                {
                    { "recordType", record.RecordType.ToString() },
                    { "result", result.ToString() },
                    { "measurementCount", record.Measurements.Count },
                    { "nonConformanceCount", record.NonConformances.Count }
                }
            });

            OnQualityRecordAdded?.Invoke(record);
        }

        #endregion

        #region Non-Conformance Management

        public NonConformance RaiseNonConformance(string productId, NonConformanceType type, string description)
        {
            var nc = new NonConformance
            {
                NCId = Guid.NewGuid().ToString(),
                ProductId = productId,
                Type = type,
                Description = description,
                RaisedDate = DateTime.UtcNow,
                Status = NCStatus.Open,
                Severity = DetermineNCSeverity(type)
            };

            AddThreadEvent(productId, new ThreadEvent
            {
                EventType = ThreadEventType.NonConformanceRaised,
                Description = $"Non-conformance raised: {type}",
                Data = new Dictionary<string, object>
                {
                    { "ncId", nc.NCId },
                    { "type", type.ToString() },
                    { "severity", nc.Severity.ToString() }
                }
            });

            OnNonConformanceRaised?.Invoke(nc);
            OnTraceabilityAlert?.Invoke($"NC-{nc.NCId}: {description}");

            return nc;
        }

        private NCSeverity DetermineNCSeverity(NonConformanceType type)
        {
            return type switch
            {
                NonConformanceType.Safety => NCSeverity.Critical,
                NonConformanceType.Specification => NCSeverity.Major,
                NonConformanceType.OutOfTolerance => NCSeverity.Major,
                NonConformanceType.Cosmetic => NCSeverity.Minor,
                NonConformanceType.Documentation => NCSeverity.Minor,
                _ => NCSeverity.Minor
            };
        }

        #endregion

        #region Thread Events

        public void AddThreadEvent(string productId, ThreadEvent evt)
        {
            if (!productThreads.TryGetValue(productId, out var product))
                return;

            evt.EventId = Guid.NewGuid().ToString();
            evt.Timestamp = DateTime.UtcNow;
            evt.EntityId = productId;
            evt.EntityType = "Product";

            product.Events.Add(evt);
            product.LastUpdated = evt.Timestamp;

            AddToLedger(evt);
            OnThreadEventAdded?.Invoke(evt);
        }

        public void RecordCustomEvent(string productId, string eventType, string description,
            Dictionary<string, object> data = null)
        {
            AddThreadEvent(productId, new ThreadEvent
            {
                EventType = ThreadEventType.Custom,
                CustomEventType = eventType,
                Description = description,
                Data = data ?? new Dictionary<string, object>()
            });
        }

        #endregion

        #region Blockchain-style Ledger

        private void AddToLedger(ThreadEvent evt)
        {
            if (!enableBlockchainVerification)
                return;

            // Get or create current block
            var currentBlock = ledger.LastOrDefault();
            if (currentBlock == null || currentBlock.Events.Count >= 100)
            {
                // Create new block
                currentBlock = new ThreadBlock
                {
                    BlockIndex = ledger.Count,
                    Timestamp = DateTime.UtcNow,
                    PreviousHash = lastBlockHash,
                    Events = new List<ThreadEvent>()
                };
                ledger.Add(currentBlock);
            }

            // Add event to current block
            currentBlock.Events.Add(evt);

            // Update block hash
            currentBlock.Hash = CalculateBlockHash(currentBlock);
            lastBlockHash = currentBlock.Hash;
        }

        private string CalculateBlockHash(ThreadBlock block)
        {
            string data = $"{block.BlockIndex}{block.Timestamp:O}{block.PreviousHash}{block.Events.Count}{block.Nonce}";

            using (SHA256 sha = SHA256.Create())
            {
                byte[] hashBytes = sha.ComputeHash(Encoding.UTF8.GetBytes(data));
                return Convert.ToBase64String(hashBytes);
            }
        }

        public bool VerifyLedgerIntegrity()
        {
            if (ledger.Count < 2)
                return true;

            for (int i = 1; i < ledger.Count; i++)
            {
                var currentBlock = ledger[i];
                var previousBlock = ledger[i - 1];

                // Verify previous hash reference
                if (currentBlock.PreviousHash != previousBlock.Hash)
                {
                    Debug.LogError($"[DigitalThread] Ledger integrity violation at block {i}");
                    return false;
                }

                // Verify current block hash
                string calculatedHash = CalculateBlockHash(currentBlock);
                if (currentBlock.Hash != calculatedHash)
                {
                    Debug.LogError($"[DigitalThread] Block {i} hash mismatch");
                    return false;
                }
            }

            return true;
        }

        public ThreadBlock GetBlock(int index)
        {
            return index >= 0 && index < ledger.Count ? ledger[index] : null;
        }

        #endregion

        #region Traceability Queries

        public TraceabilityReport GenerateTraceabilityReport(string productId)
        {
            if (!productThreads.TryGetValue(productId, out var product))
                return null;

            var report = new TraceabilityReport
            {
                ProductId = productId,
                SerialNumber = product.SerialNumber,
                GeneratedAt = DateTime.UtcNow,
                ProductInfo = product,
                LinkedParts = product.LinkedParts
                    .Select(id => partThreads.GetValueOrDefault(id))
                    .Where(p => p != null)
                    .ToList(),
                ManufacturingHistory = product.ManufacturingRecords
                    .Select(id => manufacturingRecords.GetValueOrDefault(id))
                    .Where(r => r != null)
                    .ToList(),
                QualityHistory = product.QualityRecords
                    .Select(id => qualityRecords.GetValueOrDefault(id))
                    .Where(r => r != null)
                    .ToList(),
                EventHistory = product.Events.OrderByDescending(e => e.Timestamp).ToList()
            };

            // Calculate statistics
            report.TotalEvents = report.EventHistory.Count;
            report.TotalParts = report.LinkedParts.Count;
            report.TotalOperations = report.ManufacturingHistory.Count;
            report.NonConformanceCount = report.QualityHistory.Sum(q => q.NonConformances?.Count ?? 0);

            return report;
        }

        public List<ProductThread> QueryProductsByPart(string partId)
        {
            if (!partThreads.TryGetValue(partId, out var part))
                return new List<ProductThread>();

            return part.UsedInProducts
                .Select(id => productThreads.GetValueOrDefault(id))
                .Where(p => p != null)
                .ToList();
        }

        public List<PartThread> QueryPartsBySupplier(string supplier)
        {
            return partThreads.Values
                .Where(p => p.Supplier == supplier)
                .ToList();
        }

        public List<ProductThread> QueryProductsByDateRange(DateTime start, DateTime end)
        {
            return productThreads.Values
                .Where(p => p.CreatedAt >= start && p.CreatedAt <= end)
                .ToList();
        }

        #endregion

        #region Synchronization

        private IEnumerator SyncLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(syncInterval);

                // Verify ledger integrity
                if (enableBlockchainVerification && !VerifyLedgerIntegrity())
                {
                    OnTraceabilityAlert?.Invoke("CRITICAL: Ledger integrity violation detected!");
                }

                // Trim old events if needed
                if (GetTotalEventCount() > maxThreadEvents)
                {
                    TrimOldEvents();
                }
            }
        }

        private int GetTotalEventCount()
        {
            return productThreads.Values.Sum(p => p.Events.Count) +
                   partThreads.Values.Sum(p => p.Events.Count);
        }

        private void TrimOldEvents()
        {
            // Keep most recent events for each thread
            int keepCount = maxThreadEvents / (productThreads.Count + partThreads.Count + 1);

            foreach (var product in productThreads.Values)
            {
                if (product.Events.Count > keepCount)
                {
                    product.Events = product.Events
                        .OrderByDescending(e => e.Timestamp)
                        .Take(keepCount)
                        .ToList();
                }
            }
        }

        #endregion

        #region Statistics

        public DigitalThreadStats GetStatistics()
        {
            return new DigitalThreadStats
            {
                TotalProducts = productThreads.Count,
                TotalParts = partThreads.Count,
                TotalEvents = GetTotalEventCount(),
                TotalDesignRevisions = designRevisions.Count,
                TotalBOMs = billsOfMaterials.Count,
                TotalManufacturingRecords = manufacturingRecords.Count,
                TotalQualityRecords = qualityRecords.Count,
                LedgerBlocks = ledger.Count,
                LedgerIntegrity = enableBlockchainVerification ? VerifyLedgerIntegrity() : true,
                ProductsByState = productThreads.Values
                    .GroupBy(p => p.State)
                    .ToDictionary(g => g.Key, g => g.Count()),
                ProductsByPhase = productThreads.Values
                    .GroupBy(p => p.CurrentPhase)
                    .ToDictionary(g => g.Key, g => g.Count())
            };
        }

        public int ProductCount => productThreads.Count;
        public int PartCount => partThreads.Count;

        #endregion
    }

    #region Enums

    public enum ProductState
    {
        Created,
        InProgress,
        Completed,
        Shipped,
        OnHold,
        Scrapped,
        Returned,
        EndOfLife
    }

    public enum ProductPhase
    {
        Design,
        Planning,
        MaterialProcurement,
        Manufacturing,
        Assembly,
        Testing,
        QualityInspection,
        Packaging,
        Shipping,
        InService,
        Maintenance,
        EndOfLife
    }

    public enum PartState
    {
        Received,
        InspectionPending,
        Approved,
        Quarantine,
        InUse,
        Consumed,
        Rejected,
        Expired
    }

    public enum ThreadEventType
    {
        ProductCreated,
        StateChanged,
        PhaseChanged,
        PartLinked,
        PartReceived,
        PartConsumed,
        OperationStarted,
        OperationCompleted,
        OperationFailed,
        QualityRecorded,
        NonConformanceRaised,
        NonConformanceResolved,
        CertificationAdded,
        ShipmentCreated,
        Custom
    }

    public enum ApprovalStatus
    {
        Draft,
        Review,
        Approved,
        Released,
        Obsolete
    }

    public enum BOMStatus
    {
        Draft,
        Released,
        Obsolete
    }

    public enum OperationStatus
    {
        Pending,
        InProgress,
        Completed,
        Failed,
        Cancelled
    }

    public enum QualityResult
    {
        Pending,
        Pass,
        Fail,
        ConditionalPass
    }

    public enum QualityStatus
    {
        Pending,
        Approved,
        Rejected,
        ConditionalApproval,
        Waived
    }

    public enum QualityRecordType
    {
        IncomingInspection,
        FirstArticle,
        InProcess,
        FinalInspection,
        Audit,
        CustomerReturn
    }

    public enum NonConformanceType
    {
        Specification,
        OutOfTolerance,
        Cosmetic,
        Documentation,
        Process,
        Material,
        Safety
    }

    public enum NCStatus
    {
        Open,
        UnderReview,
        Dispositioned,
        Closed
    }

    public enum NCSeverity
    {
        Minor,
        Major,
        Critical
    }

    #endregion

    #region Data Classes

    [System.Serializable]
    public class ProductThread
    {
        public string ProductId;
        public string SerialNumber;
        public string ProductType;
        public string ProductName;
        public string DesignRevision;
        public string BOMRevision;
        public DateTime CreatedAt;
        public DateTime LastUpdated;
        public ProductState State;
        public ProductPhase CurrentPhase;
        public QualityStatus QualityStatus;
        public DesignRevision DesignData;
        public BillOfMaterials BOM;
        public List<ThreadEvent> Events;
        public List<string> LinkedParts;
        public List<string> ManufacturingRecords = new List<string>();
        public List<string> QualityRecords;
        public List<Certification> Certifications;
        public Dictionary<string, object> CustomData = new Dictionary<string, object>();
    }

    [System.Serializable]
    public class ProductThreadConfig
    {
        public string ProductId;
        public string SerialNumber;
        public string ProductType;
        public string ProductName;
        public string DesignRevision;
        public string BOMRevision;
    }

    [System.Serializable]
    public class PartThread
    {
        public string PartId;
        public string PartNumber;
        public string LotNumber;
        public string PartName;
        public string Material;
        public string Supplier;
        public DateTime ReceivedDate;
        public DateTime? ExpirationDate;
        public float Quantity;
        public string UnitOfMeasure;
        public PartState State;
        public List<ThreadEvent> Events;
        public List<string> Certifications;
        public List<TestResult> TestResults;
        public List<string> UsedInProducts = new List<string>();
    }

    [System.Serializable]
    public class PartThreadConfig
    {
        public string PartId;
        public string PartNumber;
        public string LotNumber;
        public string PartName;
        public string Material;
        public string Supplier;
        public DateTime? ReceivedDate;
        public DateTime? ExpirationDate;
        public float Quantity;
        public string UnitOfMeasure;
        public List<string> Certifications;
    }

    [System.Serializable]
    public class ProcessThread
    {
        public string ProcessId;
        public string ProcessName;
        public List<ManufacturingOperation> Operations;
    }

    [System.Serializable]
    public class ThreadEvent
    {
        public string EventId;
        public string EntityId;
        public string EntityType;
        public DateTime Timestamp;
        public ThreadEventType EventType;
        public string CustomEventType;
        public string Description;
        public string UserId;
        public Dictionary<string, object> Data;
    }

    [System.Serializable]
    public class DesignRevision
    {
        public string RevisionId;
        public string DesignId;
        public string Version;
        public DateTime RevisionDate;
        public string Author;
        public string Description;
        public List<CADFile> CADFiles;
        public List<Drawing> Drawings;
        public Dictionary<string, string> Specifications;
        public ApprovalStatus ApprovalStatus;
        public string ApprovedBy;
        public DateTime? ApprovedDate;
        public string ChangeNotes;
    }

    [System.Serializable]
    public class DesignRevisionConfig
    {
        public string RevisionId;
        public string DesignId;
        public string Version;
        public DateTime? RevisionDate;
        public string Author;
        public string Description;
        public List<CADFile> CADFiles;
        public List<Drawing> Drawings;
        public Dictionary<string, string> Specifications;
        public string ChangeNotes;
    }

    [System.Serializable]
    public class CADFile
    {
        public string FileId;
        public string FileName;
        public string FileType;
        public string FilePath;
        public string Checksum;
    }

    [System.Serializable]
    public class Drawing
    {
        public string DrawingId;
        public string DrawingNumber;
        public string Revision;
        public string FilePath;
    }

    [System.Serializable]
    public class BillOfMaterials
    {
        public string BOMId;
        public string ProductId;
        public string Version;
        public DateTime EffectiveDate;
        public BOMStatus Status;
        public List<BOMItem> Items;
    }

    [System.Serializable]
    public class BOMConfig
    {
        public string BOMId;
        public string ProductId;
        public string Version;
        public DateTime? EffectiveDate;
        public List<BOMItem> Items;
    }

    [System.Serializable]
    public class BOMItem
    {
        public string ItemId;
        public string PartNumber;
        public string Description;
        public float Quantity;
        public string UnitOfMeasure;
        public int Level;
        public string ParentItemId;
        public bool IsCritical;
    }

    [System.Serializable]
    public class ManufacturingRecord
    {
        public string RecordId;
        public string ProductId;
        public ManufacturingOperation Operation;
        public DateTime StartTime;
        public DateTime? EndTime;
        public float Duration;
        public OperationStatus Status;
        public Dictionary<string, object> Parameters;
        public List<ProcessMeasurement> Measurements;
        public string Notes;
    }

    [System.Serializable]
    public class ManufacturingOperation
    {
        public string OperationId;
        public string OperationName;
        public int Sequence;
        public string MachineId;
        public string ProgramId;
        public float SetupTime;
        public float CycleTime;
    }

    [System.Serializable]
    public class ProcessMeasurement
    {
        public string MeasurementId;
        public DateTime Timestamp;
        public string ParameterName;
        public float Value;
        public string Unit;
        public float Nominal;
        public float Tolerance;
        public bool IsInTolerance;
    }

    [System.Serializable]
    public class QualityRecord
    {
        public string RecordId;
        public string ProductId;
        public QualityRecordType RecordType;
        public DateTime InspectionDate;
        public DateTime? CompletedDate;
        public string Inspector;
        public QualityResult Result;
        public List<QualityMeasurement> Measurements;
        public List<NonConformance> NonConformances;
        public string Disposition;
        public string Notes;
    }

    [System.Serializable]
    public class QualityRecordConfig
    {
        public QualityRecordType RecordType;
        public string Inspector;
        public string Notes;
    }

    [System.Serializable]
    public class QualityMeasurement
    {
        public string MeasurementId;
        public DateTime Timestamp;
        public string Characteristic;
        public float Value;
        public string Unit;
        public float LSL; // Lower Spec Limit
        public float USL; // Upper Spec Limit
        public bool IsConforming;
        public string Method;
        public string Equipment;
    }

    [System.Serializable]
    public class NonConformance
    {
        public string NCId;
        public string ProductId;
        public NonConformanceType Type;
        public string Description;
        public DateTime RaisedDate;
        public DateTime? ResolvedDate;
        public NCStatus Status;
        public NCSeverity Severity;
        public string RootCause;
        public string CorrectiveAction;
        public string Disposition;
    }

    [System.Serializable]
    public class Certification
    {
        public string CertificationId;
        public string CertificationType;
        public string IssuedBy;
        public DateTime IssuedDate;
        public DateTime? ExpirationDate;
        public string DocumentRef;
    }

    [System.Serializable]
    public class TestResult
    {
        public string TestId;
        public string TestName;
        public DateTime TestDate;
        public bool Passed;
        public Dictionary<string, object> Results;
    }

    [System.Serializable]
    public class ThreadBlock
    {
        public int BlockIndex;
        public DateTime Timestamp;
        public string PreviousHash;
        public string Hash;
        public List<ThreadEvent> Events;
        public int Nonce;
    }

    [System.Serializable]
    public class TraceabilityReport
    {
        public string ProductId;
        public string SerialNumber;
        public DateTime GeneratedAt;
        public ProductThread ProductInfo;
        public List<PartThread> LinkedParts;
        public List<ManufacturingRecord> ManufacturingHistory;
        public List<QualityRecord> QualityHistory;
        public List<ThreadEvent> EventHistory;
        public int TotalEvents;
        public int TotalParts;
        public int TotalOperations;
        public int NonConformanceCount;
    }

    [System.Serializable]
    public class DigitalThreadStats
    {
        public int TotalProducts;
        public int TotalParts;
        public int TotalEvents;
        public int TotalDesignRevisions;
        public int TotalBOMs;
        public int TotalManufacturingRecords;
        public int TotalQualityRecords;
        public int LedgerBlocks;
        public bool LedgerIntegrity;
        public Dictionary<ProductState, int> ProductsByState;
        public Dictionary<ProductPhase, int> ProductsByPhase;
    }

    #endregion
}
