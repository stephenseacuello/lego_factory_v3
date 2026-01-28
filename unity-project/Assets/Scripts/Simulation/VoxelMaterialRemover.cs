using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Simulation
{
    /// <summary>
    /// Voxel-based material removal simulation.
    /// Discretizes workpiece into 3D voxel grid and removes material as tool passes through.
    /// Part of Feature 1.1: Material Removal Simulation (MEDIUM PRIORITY)
    /// </summary>
    public class VoxelMaterialRemover : MonoBehaviour
    {
        [Header("Voxel Grid Configuration")]
        [SerializeField] private Vector3 workpieceSize = new Vector3(0.1f, 0.05f, 0.1f); // 100x50x100mm
        [SerializeField] private float voxelSize = 0.001f; // 1mm voxels
        [SerializeField] private Vector3 workpiecePosition = Vector3.zero;

        [Header("Material Properties")]
        [SerializeField] private Material workpieceMaterial;
        [SerializeField] private Color removedMaterialColor = new Color(0.5f, 0.5f, 0.5f, 0.3f);
        [SerializeField] private float materialDensity = 2700f; // kg/m³ (aluminum)

        [Header("Tool Configuration")]
        [SerializeField] private Transform toolTransform;
        [SerializeField] private float toolRadius = 0.003f; // 3mm
        [SerializeField] private float toolLength = 0.05f; // 50mm

        [Header("Simulation Settings")]
        [SerializeField] private bool enableSimulation = true;
        [SerializeField] private float updateInterval = 0.05f; // Update every 50ms
        [SerializeField] private bool visualizeVoxels = false;

        // Voxel grid
        private bool[,,] voxelGrid;
        private Vector3Int gridDimensions;
        private float updateTimer = 0f;

        // Statistics
        private int totalVoxels = 0;
        private int removedVoxels = 0;
        private float volumeRemoved = 0f; // cubic meters
        private float massRemoved = 0f; // kg
        private DateTime startTime;

        // Mesh generation
        private MaterialRemovalVisualizer visualizer;

        // Events
        public event Action<MaterialRemovalEvent> OnMaterialRemoved;
        public event Action<VoxelStatistics> OnStatisticsUpdated;

        void Start()
        {
            InitializeVoxelGrid();

            // Find or create visualizer
            visualizer = GetComponent<MaterialRemovalVisualizer>();
            if (visualizer == null)
            {
                visualizer = gameObject.AddComponent<MaterialRemovalVisualizer>();
            }

            startTime = DateTime.UtcNow;
            Debug.Log($"[VoxelMaterialRemover] Initialized with {totalVoxels:N0} voxels ({gridDimensions})");
        }

        void Update()
        {
            if (!enableSimulation || toolTransform == null) return;

            updateTimer += Time.deltaTime;
            if (updateTimer >= updateInterval)
            {
                RemoveMaterial(toolTransform.position);
                updateTimer = 0f;
            }
        }

        void OnDrawGizmos()
        {
            if (!visualizeVoxels || voxelGrid == null) return;

            // Draw voxel grid (sample every Nth voxel to avoid performance issues)
            int sampleRate = Mathf.Max(1, gridDimensions.x / 20);

            Gizmos.color = Color.cyan;
            for (int x = 0; x < gridDimensions.x; x += sampleRate)
            {
                for (int y = 0; y < gridDimensions.y; y += sampleRate)
                {
                    for (int z = 0; z < gridDimensions.z; z += sampleRate)
                    {
                        if (voxelGrid[x, y, z])
                        {
                            Vector3 voxelWorldPos = VoxelToWorldPosition(new Vector3Int(x, y, z));
                            Gizmos.DrawWireCube(voxelWorldPos, Vector3.one * voxelSize);
                        }
                    }
                }
            }
        }

        /// <summary>
        /// Initialize voxel grid based on workpiece size
        /// </summary>
        private void InitializeVoxelGrid()
        {
            // Calculate grid dimensions
            gridDimensions = new Vector3Int(
                Mathf.CeilToInt(workpieceSize.x / voxelSize),
                Mathf.CeilToInt(workpieceSize.y / voxelSize),
                Mathf.CeilToInt(workpieceSize.z / voxelSize)
            );

            // Initialize all voxels as filled (true = material present)
            voxelGrid = new bool[gridDimensions.x, gridDimensions.y, gridDimensions.z];
            for (int x = 0; x < gridDimensions.x; x++)
            {
                for (int y = 0; y < gridDimensions.y; y++)
                {
                    for (int z = 0; z < gridDimensions.z; z++)
                    {
                        voxelGrid[x, y, z] = true;
                    }
                }
            }

            totalVoxels = gridDimensions.x * gridDimensions.y * gridDimensions.z;
            removedVoxels = 0;
        }

        /// <summary>
        /// Remove material at tool position
        /// </summary>
        public void RemoveMaterial(Vector3 toolPosition)
        {
            // Get tool path cylinder
            Vector3 toolStart = toolPosition;
            Vector3 toolEnd = toolPosition + toolTransform.up * toolLength;

            int voxelsRemovedThisFrame = 0;

            // Check all voxels within tool radius
            Vector3Int minVoxel = WorldToVoxelPosition(toolStart - Vector3.one * toolRadius);
            Vector3Int maxVoxel = WorldToVoxelPosition(toolEnd + Vector3.one * toolRadius);

            // Clamp to grid bounds
            minVoxel = ClampVoxelPosition(minVoxel);
            maxVoxel = ClampVoxelPosition(maxVoxel);

            for (int x = minVoxel.x; x <= maxVoxel.x; x++)
            {
                for (int y = minVoxel.y; y <= maxVoxel.y; y++)
                {
                    for (int z = minVoxel.z; z <= maxVoxel.z; z++)
                    {
                        if (!voxelGrid[x, y, z]) continue; // Already removed

                        Vector3 voxelWorldPos = VoxelToWorldPosition(new Vector3Int(x, y, z));

                        // Check if voxel center is within tool cylinder
                        if (IsPointInCylinder(voxelWorldPos, toolStart, toolEnd, toolRadius))
                        {
                            voxelGrid[x, y, z] = false;
                            removedVoxels++;
                            voxelsRemovedThisFrame++;
                        }
                    }
                }
            }

            if (voxelsRemovedThisFrame > 0)
            {
                // Update volume and mass removed
                float voxelVolume = voxelSize * voxelSize * voxelSize; // m³
                volumeRemoved = removedVoxels * voxelVolume;
                massRemoved = volumeRemoved * materialDensity;

                // Trigger event
                var removalEvent = new MaterialRemovalEvent
                {
                    Timestamp = DateTime.UtcNow,
                    ToolPosition = toolPosition,
                    VoxelsRemoved = voxelsRemovedThisFrame,
                    VolumeRemoved = voxelsRemovedThisFrame * voxelVolume,
                    MassRemoved = voxelsRemovedThisFrame * voxelVolume * materialDensity
                };

                OnMaterialRemoved?.Invoke(removalEvent);

                // Update visualizer
                if (visualizer != null)
                {
                    visualizer.UpdateMesh(voxelGrid, gridDimensions, voxelSize, workpiecePosition);
                }
            }
        }

        /// <summary>
        /// Check if point is inside tool cylinder
        /// </summary>
        private bool IsPointInCylinder(Vector3 point, Vector3 start, Vector3 end, float radius)
        {
            Vector3 axis = (end - start).normalized;
            Vector3 toPoint = point - start;

            // Project point onto cylinder axis
            float projection = Vector3.Dot(toPoint, axis);

            // Check if within cylinder length
            float cylinderLength = Vector3.Distance(start, end);
            if (projection < 0 || projection > cylinderLength)
                return false;

            // Check if within cylinder radius
            Vector3 projectedPoint = start + axis * projection;
            float distanceFromAxis = Vector3.Distance(point, projectedPoint);

            return distanceFromAxis <= radius;
        }

        /// <summary>
        /// Convert world position to voxel grid indices
        /// </summary>
        private Vector3Int WorldToVoxelPosition(Vector3 worldPos)
        {
            Vector3 localPos = worldPos - workpiecePosition + workpieceSize / 2f;

            return new Vector3Int(
                Mathf.FloorToInt(localPos.x / voxelSize),
                Mathf.FloorToInt(localPos.y / voxelSize),
                Mathf.FloorToInt(localPos.z / voxelSize)
            );
        }

        /// <summary>
        /// Convert voxel grid indices to world position
        /// </summary>
        private Vector3 VoxelToWorldPosition(Vector3Int voxelPos)
        {
            Vector3 localPos = new Vector3(
                voxelPos.x * voxelSize,
                voxelPos.y * voxelSize,
                voxelPos.z * voxelSize
            );

            return localPos + workpiecePosition - workpieceSize / 2f + Vector3.one * (voxelSize / 2f);
        }

        /// <summary>
        /// Clamp voxel position to grid bounds
        /// </summary>
        private Vector3Int ClampVoxelPosition(Vector3Int voxelPos)
        {
            return new Vector3Int(
                Mathf.Clamp(voxelPos.x, 0, gridDimensions.x - 1),
                Mathf.Clamp(voxelPos.y, 0, gridDimensions.y - 1),
                Mathf.Clamp(voxelPos.z, 0, gridDimensions.z - 1)
            );
        }

        /// <summary>
        /// Reset workpiece to full material
        /// </summary>
        public void ResetWorkpiece()
        {
            for (int x = 0; x < gridDimensions.x; x++)
            {
                for (int y = 0; y < gridDimensions.y; y++)
                {
                    for (int z = 0; z < gridDimensions.z; z++)
                    {
                        voxelGrid[x, y, z] = true;
                    }
                }
            }

            removedVoxels = 0;
            volumeRemoved = 0f;
            massRemoved = 0f;

            if (visualizer != null)
            {
                visualizer.UpdateMesh(voxelGrid, gridDimensions, voxelSize, workpiecePosition);
            }

            Debug.Log("[VoxelMaterialRemover] Workpiece reset");
        }

        /// <summary>
        /// Set workpiece dimensions
        /// </summary>
        public void SetWorkpieceDimensions(Vector3 size)
        {
            workpieceSize = size;
            InitializeVoxelGrid();

            if (visualizer != null)
            {
                visualizer.UpdateMesh(voxelGrid, gridDimensions, voxelSize, workpiecePosition);
            }

            Debug.Log($"[VoxelMaterialRemover] Workpiece dimensions set: {size}");
        }

        /// <summary>
        /// Set voxel resolution
        /// </summary>
        public void SetVoxelSize(float size)
        {
            voxelSize = Mathf.Max(0.0001f, size); // Minimum 0.1mm
            InitializeVoxelGrid();

            if (visualizer != null)
            {
                visualizer.UpdateMesh(voxelGrid, gridDimensions, voxelSize, workpiecePosition);
            }

            Debug.Log($"[VoxelMaterialRemover] Voxel size set: {size}m");
        }

        /// <summary>
        /// Get current removal statistics
        /// </summary>
        public VoxelStatistics GetStatistics()
        {
            float removalPercentage = (removedVoxels / (float)totalVoxels) * 100f;
            TimeSpan elapsed = DateTime.UtcNow - startTime;

            return new VoxelStatistics
            {
                TotalVoxels = totalVoxels,
                RemovedVoxels = removedVoxels,
                RemainingVoxels = totalVoxels - removedVoxels,
                RemovalPercentage = removalPercentage,
                VolumeRemoved = volumeRemoved,
                MassRemoved = massRemoved,
                GridDimensions = gridDimensions,
                VoxelSize = voxelSize,
                ElapsedTime = elapsed
            };
        }

        /// <summary>
        /// Enable or disable simulation
        /// </summary>
        public void SetSimulationEnabled(bool enabled)
        {
            enableSimulation = enabled;
            Debug.Log($"[VoxelMaterialRemover] Simulation {(enabled ? "enabled" : "disabled")}");
        }

        #region Public Properties

        public int TotalVoxels => totalVoxels;
        public int RemovedVoxels => removedVoxels;
        public float RemovalPercentage => (removedVoxels / (float)totalVoxels) * 100f;
        public float VolumeRemoved => volumeRemoved;
        public float MassRemoved => massRemoved;
        public Vector3Int GridDimensions => gridDimensions;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Material removal event data
    /// </summary>
    [Serializable]
    public struct MaterialRemovalEvent
    {
        public DateTime Timestamp;
        public Vector3 ToolPosition;
        public int VoxelsRemoved;
        public float VolumeRemoved; // m³
        public float MassRemoved; // kg
    }

    /// <summary>
    /// Voxel statistics
    /// </summary>
    [Serializable]
    public struct VoxelStatistics
    {
        public int TotalVoxels;
        public int RemovedVoxels;
        public int RemainingVoxels;
        public float RemovalPercentage;
        public float VolumeRemoved; // m³
        public float MassRemoved; // kg
        public Vector3Int GridDimensions;
        public float VoxelSize;
        public TimeSpan ElapsedTime;
    }

    #endregion
}

