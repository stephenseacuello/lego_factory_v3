using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;

namespace CNCScada.Simulation
{
    /// <summary>
    /// Generates mesh visualization from voxel grid for material removal simulation.
    /// Uses marching cubes algorithm for smooth surface generation.
    /// Part of Feature 1.1: Material Removal Simulation (MEDIUM PRIORITY)
    /// </summary>
    public class MaterialRemovalVisualizer : MonoBehaviour
    {
        [Header("Visualization Settings")]
        [SerializeField] private Material workpieceMaterial;
        [SerializeField] private bool smoothShading = true;
        [SerializeField] private bool showWireframe = false;

        [Header("Performance")]
        [SerializeField] private bool useAsyncGeneration = false;
        [SerializeField] private int maxVerticesPerMesh = 65000;

        // Mesh components
        private GameObject meshObject;
        private MeshFilter meshFilter;
        private MeshRenderer meshRenderer;
        private Mesh currentMesh;

        // Statistics
        private int lastVertexCount = 0;
        private int lastTriangleCount = 0;
        private float lastGenerationTime = 0f;

        void Start()
        {
            InitializeMeshObject();
        }

        /// <summary>
        /// Initialize mesh object for rendering
        /// </summary>
        private void InitializeMeshObject()
        {
            // Create mesh object
            meshObject = new GameObject("WorkpieceMesh");
            meshObject.transform.SetParent(transform);
            meshObject.transform.localPosition = Vector3.zero;

            // Add mesh components
            meshFilter = meshObject.AddComponent<MeshFilter>();
            meshRenderer = meshObject.AddComponent<MeshRenderer>();

            // Set material
            if (workpieceMaterial != null)
            {
                meshRenderer.material = workpieceMaterial;
            }
            else
            {
                // Create default material
                workpieceMaterial = new Material(Shader.Find("Standard"));
                workpieceMaterial.color = new Color(0.7f, 0.7f, 0.7f);
                meshRenderer.material = workpieceMaterial;
            }

            currentMesh = new Mesh();
            currentMesh.name = "WorkpieceMesh";
            meshFilter.mesh = currentMesh;
        }

        /// <summary>
        /// Update mesh from voxel grid
        /// </summary>
        public void UpdateMesh(bool[,,] voxelGrid, Vector3Int gridDimensions,
                              float voxelSize, Vector3 workpiecePosition)
        {
            if (voxelGrid == null) return;

            float startTime = Time.realtimeSinceStartup;

            if (useAsyncGeneration)
            {
                GenerateMeshAsync(voxelGrid, gridDimensions, voxelSize, workpiecePosition);
            }
            else
            {
                GenerateMeshSync(voxelGrid, gridDimensions, voxelSize, workpiecePosition);
            }

            lastGenerationTime = (Time.realtimeSinceStartup - startTime) * 1000f; // ms
        }

        /// <summary>
        /// Generate mesh asynchronously to avoid blocking the main thread
        /// </summary>
        private async void GenerateMeshAsync(bool[,,] voxelGrid, Vector3Int gridDimensions,
                                             float voxelSize, Vector3 workpiecePosition)
        {
            // Copy voxel data for thread safety
            bool[,,] voxelCopy = (bool[,,])voxelGrid.Clone();

            // Generate mesh data on background thread
            var meshData = await Task.Run(() =>
            {
                return GenerateMeshData(voxelCopy, gridDimensions, voxelSize, workpiecePosition);
            });

            // Apply mesh on main thread
            ApplyMeshData(meshData);
        }

        /// <summary>
        /// Container for mesh generation results
        /// </summary>
        private struct MeshData
        {
            public List<Vector3> Vertices;
            public List<int> Triangles;
            public List<Vector3> Normals;
        }

        /// <summary>
        /// Generate mesh data (can run on background thread)
        /// </summary>
        private MeshData GenerateMeshData(bool[,,] voxelGrid, Vector3Int gridDimensions,
                                          float voxelSize, Vector3 workpiecePosition)
        {
            var data = new MeshData
            {
                Vertices = new List<Vector3>(),
                Triangles = new List<int>(),
                Normals = new List<Vector3>()
            };

            Vector3 halfSize = new Vector3(
                gridDimensions.x * voxelSize / 2f,
                gridDimensions.y * voxelSize / 2f,
                gridDimensions.z * voxelSize / 2f
            );

            // Generate mesh data using the same algorithm as sync version
            for (int x = 0; x < gridDimensions.x; x++)
            {
                for (int y = 0; y < gridDimensions.y; y++)
                {
                    for (int z = 0; z < gridDimensions.z; z++)
                    {
                        if (!voxelGrid[x, y, z]) continue;

                        Vector3 voxelPos = new Vector3(x, y, z) * voxelSize;
                        voxelPos += workpiecePosition - halfSize;

                        // Check each face
                        if (x == 0 || !voxelGrid[x - 1, y, z])
                            AddQuad(data.Vertices, data.Triangles, data.Normals, voxelPos,
                                Vector3.right, Vector3.up, Vector3.left, voxelSize);

                        if (x == gridDimensions.x - 1 || !voxelGrid[x + 1, y, z])
                            AddQuad(data.Vertices, data.Triangles, data.Normals,
                                voxelPos + Vector3.right * voxelSize,
                                Vector3.right, Vector3.up, Vector3.right, voxelSize);

                        if (y == 0 || !voxelGrid[x, y - 1, z])
                            AddQuad(data.Vertices, data.Triangles, data.Normals, voxelPos,
                                Vector3.right, Vector3.forward, Vector3.down, voxelSize);

                        if (y == gridDimensions.y - 1 || !voxelGrid[x, y + 1, z])
                            AddQuad(data.Vertices, data.Triangles, data.Normals,
                                voxelPos + Vector3.up * voxelSize,
                                Vector3.right, Vector3.forward, Vector3.up, voxelSize);

                        if (z == 0 || !voxelGrid[x, y, z - 1])
                            AddQuad(data.Vertices, data.Triangles, data.Normals, voxelPos,
                                Vector3.right, Vector3.up, Vector3.back, voxelSize);

                        if (z == gridDimensions.z - 1 || !voxelGrid[x, y, z + 1])
                            AddQuad(data.Vertices, data.Triangles, data.Normals,
                                voxelPos + Vector3.forward * voxelSize,
                                Vector3.right, Vector3.up, Vector3.forward, voxelSize);
                    }
                }
            }

            return data;
        }

        /// <summary>
        /// Apply mesh data to the current mesh (must run on main thread)
        /// </summary>
        private void ApplyMeshData(MeshData data)
        {
            currentMesh.Clear();

            if (data.Vertices.Count > maxVerticesPerMesh)
            {
                Debug.LogWarning($"[MaterialRemovalVisualizer] Vertex count ({data.Vertices.Count}) exceeds limit. Splitting mesh.");
                ApplySplitMeshData(data);
                return;
            }

            currentMesh.SetVertices(data.Vertices);
            currentMesh.SetTriangles(data.Triangles, 0);

            if (smoothShading)
            {
                currentMesh.RecalculateNormals();
            }
            else
            {
                currentMesh.SetNormals(data.Normals);
            }

            currentMesh.RecalculateBounds();

            lastVertexCount = data.Vertices.Count;
            lastTriangleCount = data.Triangles.Count / 3;
        }

        /// <summary>
        /// Split large mesh into multiple sub-meshes
        /// </summary>
        private void ApplySplitMeshData(MeshData data)
        {
            // Calculate number of meshes needed
            int numMeshes = (data.Vertices.Count + maxVerticesPerMesh - 1) / maxVerticesPerMesh;

            // Clear existing sub-mesh objects
            for (int i = meshObject.transform.childCount - 1; i >= 0; i--)
            {
                Destroy(meshObject.transform.GetChild(i).gameObject);
            }

            int vertexOffset = 0;
            int triangleOffset = 0;

            for (int meshIndex = 0; meshIndex < numMeshes; meshIndex++)
            {
                // Calculate vertices for this sub-mesh
                int verticesInThisMesh = Math.Min(maxVerticesPerMesh, data.Vertices.Count - vertexOffset);
                // Round down to multiple of 4 (vertices per quad) to avoid orphaned triangles
                verticesInThisMesh = (verticesInThisMesh / 4) * 4;

                if (verticesInThisMesh <= 0) break;

                // Create sub-mesh object
                GameObject subMeshObj = new GameObject($"SubMesh_{meshIndex}");
                subMeshObj.transform.SetParent(meshObject.transform);
                subMeshObj.transform.localPosition = Vector3.zero;

                MeshFilter subFilter = subMeshObj.AddComponent<MeshFilter>();
                MeshRenderer subRenderer = subMeshObj.AddComponent<MeshRenderer>();
                subRenderer.material = workpieceMaterial;

                Mesh subMesh = new Mesh();
                subMesh.name = $"WorkpieceMesh_Sub{meshIndex}";

                // Extract vertex range
                var subVertices = data.Vertices.GetRange(vertexOffset, verticesInThisMesh);
                var subNormals = data.Normals.GetRange(vertexOffset, verticesInThisMesh);

                // Calculate triangles for this range
                int trianglesInThisMesh = (verticesInThisMesh / 4) * 6; // 6 triangle indices per quad
                var subTriangles = new List<int>();

                for (int i = 0; i < trianglesInThisMesh && triangleOffset + i < data.Triangles.Count; i++)
                {
                    // Adjust triangle indices to be relative to this sub-mesh
                    int originalIndex = data.Triangles[triangleOffset + i];
                    subTriangles.Add(originalIndex - vertexOffset);
                }

                subMesh.SetVertices(subVertices);
                subMesh.SetTriangles(subTriangles, 0);

                if (smoothShading)
                {
                    subMesh.RecalculateNormals();
                }
                else
                {
                    subMesh.SetNormals(subNormals);
                }

                subMesh.RecalculateBounds();
                subFilter.mesh = subMesh;

                vertexOffset += verticesInThisMesh;
                triangleOffset += trianglesInThisMesh;
            }

            // Clear main mesh as we're using sub-meshes
            currentMesh.Clear();

            lastVertexCount = data.Vertices.Count;
            lastTriangleCount = data.Triangles.Count / 3;

            Debug.Log($"[MaterialRemovalVisualizer] Split mesh into {numMeshes} sub-meshes");
        }

        /// <summary>
        /// Generate mesh synchronously using greedy meshing algorithm
        /// </summary>
        private void GenerateMeshSync(bool[,,] voxelGrid, Vector3Int gridDimensions,
                                     float voxelSize, Vector3 workpiecePosition)
        {
            List<Vector3> vertices = new List<Vector3>();
            List<int> triangles = new List<int>();
            List<Vector3> normals = new List<Vector3>();

            Vector3 halfSize = new Vector3(
                gridDimensions.x * voxelSize / 2f,
                gridDimensions.y * voxelSize / 2f,
                gridDimensions.z * voxelSize / 2f
            );

            // Generate quads for each face
            // X-axis faces
            for (int x = 0; x < gridDimensions.x; x++)
            {
                for (int y = 0; y < gridDimensions.y; y++)
                {
                    for (int z = 0; z < gridDimensions.z; z++)
                    {
                        if (!voxelGrid[x, y, z]) continue;

                        Vector3 voxelPos = new Vector3(x, y, z) * voxelSize;
                        voxelPos += workpiecePosition - halfSize;

                        // Check each face
                        // -X face
                        if (x == 0 || !voxelGrid[x - 1, y, z])
                        {
                            AddQuad(vertices, triangles, normals,
                                voxelPos,
                                Vector3.right, Vector3.up, Vector3.left,
                                voxelSize);
                        }

                        // +X face
                        if (x == gridDimensions.x - 1 || !voxelGrid[x + 1, y, z])
                        {
                            AddQuad(vertices, triangles, normals,
                                voxelPos + Vector3.right * voxelSize,
                                Vector3.right, Vector3.up, Vector3.right,
                                voxelSize);
                        }

                        // -Y face
                        if (y == 0 || !voxelGrid[x, y - 1, z])
                        {
                            AddQuad(vertices, triangles, normals,
                                voxelPos,
                                Vector3.right, Vector3.forward, Vector3.down,
                                voxelSize);
                        }

                        // +Y face
                        if (y == gridDimensions.y - 1 || !voxelGrid[x, y + 1, z])
                        {
                            AddQuad(vertices, triangles, normals,
                                voxelPos + Vector3.up * voxelSize,
                                Vector3.right, Vector3.forward, Vector3.up,
                                voxelSize);
                        }

                        // -Z face
                        if (z == 0 || !voxelGrid[x, y, z - 1])
                        {
                            AddQuad(vertices, triangles, normals,
                                voxelPos,
                                Vector3.right, Vector3.up, Vector3.back,
                                voxelSize);
                        }

                        // +Z face
                        if (z == gridDimensions.z - 1 || !voxelGrid[x, y, z + 1])
                        {
                            AddQuad(vertices, triangles, normals,
                                voxelPos + Vector3.forward * voxelSize,
                                Vector3.right, Vector3.up, Vector3.forward,
                                voxelSize);
                        }
                    }
                }
            }

            // Update mesh
            currentMesh.Clear();

            if (vertices.Count > maxVerticesPerMesh)
            {
                Debug.LogWarning($"[MaterialRemovalVisualizer] Vertex count ({vertices.Count}) exceeds limit ({maxVerticesPerMesh}). Splitting mesh.");
                var meshData = new MeshData
                {
                    Vertices = vertices,
                    Triangles = triangles,
                    Normals = normals
                };
                ApplySplitMeshData(meshData);
                return;
            }

            currentMesh.SetVertices(vertices);
            currentMesh.SetTriangles(triangles, 0);

            if (smoothShading)
            {
                currentMesh.RecalculateNormals();
            }
            else
            {
                currentMesh.SetNormals(normals);
            }

            currentMesh.RecalculateBounds();

            lastVertexCount = vertices.Count;
            lastTriangleCount = triangles.Count / 3;
        }

        /// <summary>
        /// Add a quad to the mesh
        /// </summary>
        private void AddQuad(List<Vector3> vertices, List<int> triangles, List<Vector3> normals,
                            Vector3 origin, Vector3 right, Vector3 up, Vector3 normal, float size)
        {
            int vertexIndex = vertices.Count;

            // Add 4 vertices for the quad
            vertices.Add(origin);
            vertices.Add(origin + right * size);
            vertices.Add(origin + right * size + up * size);
            vertices.Add(origin + up * size);

            // Add normals
            for (int i = 0; i < 4; i++)
            {
                normals.Add(normal);
            }

            // Add two triangles (quad)
            triangles.Add(vertexIndex);
            triangles.Add(vertexIndex + 2);
            triangles.Add(vertexIndex + 1);

            triangles.Add(vertexIndex);
            triangles.Add(vertexIndex + 3);
            triangles.Add(vertexIndex + 2);
        }

        /// <summary>
        /// Get visualization statistics
        /// </summary>
        public MeshStatistics GetStatistics()
        {
            return new MeshStatistics
            {
                VertexCount = lastVertexCount,
                TriangleCount = lastTriangleCount,
                GenerationTimeMs = lastGenerationTime,
                SmoothShading = smoothShading
            };
        }

        /// <summary>
        /// Enable or disable smooth shading
        /// </summary>
        public void SetSmoothShading(bool smooth)
        {
            smoothShading = smooth;
        }

        /// <summary>
        /// Set workpiece material
        /// </summary>
        public void SetMaterial(Material material)
        {
            workpieceMaterial = material;
            if (meshRenderer != null)
            {
                meshRenderer.material = material;
            }
        }
    }

    /// <summary>
    /// Mesh generation statistics
    /// </summary>
    [Serializable]
    public struct MeshStatistics
    {
        public int VertexCount;
        public int TriangleCount;
        public float GenerationTimeMs;
        public bool SmoothShading;
    }
}
