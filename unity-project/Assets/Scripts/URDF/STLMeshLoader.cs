using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

namespace CNC_SCADA.DigitalTwin.URDF
{
    /// <summary>
    /// Runtime STL (Stereolithography) mesh loader for Unity.
    /// Supports both ASCII and Binary STL formats.
    /// </summary>
    public static class STLMeshLoader
    {
        /// <summary>
        /// Load an STL mesh from file path
        /// </summary>
        public static Mesh LoadMesh(string filePath)
        {
            if (!File.Exists(filePath))
            {
                Debug.LogError($"[STLMeshLoader] File not found: {filePath}");
                return null;
            }

            byte[] fileBytes = File.ReadAllBytes(filePath);
            return LoadMeshFromBytes(fileBytes, Path.GetFileNameWithoutExtension(filePath));
        }

        /// <summary>
        /// Load an STL mesh from byte array
        /// </summary>
        public static Mesh LoadMeshFromBytes(byte[] data, string meshName = "STL_Mesh")
        {
            if (data == null || data.Length < 84)
            {
                Debug.LogError("[STLMeshLoader] Invalid STL data");
                return null;
            }

            // Check if ASCII or Binary
            bool isAscii = IsAsciiSTL(data);

            List<Vector3> vertices;
            List<Vector3> normals;
            List<int> triangles;

            if (isAscii)
            {
                ParseAsciiSTL(Encoding.ASCII.GetString(data), out vertices, out normals, out triangles);
            }
            else
            {
                ParseBinarySTL(data, out vertices, out normals, out triangles);
            }

            if (vertices == null || vertices.Count == 0)
            {
                Debug.LogError("[STLMeshLoader] No vertices parsed from STL");
                return null;
            }

            // Create Unity mesh
            Mesh mesh = new Mesh();
            mesh.name = meshName;

            // Unity has a 65535 vertex limit per mesh without 32-bit indices
            if (vertices.Count > 65535)
            {
                mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            }

            mesh.SetVertices(vertices);
            mesh.SetNormals(normals);
            mesh.SetTriangles(triangles, 0);

            // Recalculate bounds and normals if needed
            mesh.RecalculateBounds();
            if (normals.Count == 0 || normals[0] == Vector3.zero)
            {
                mesh.RecalculateNormals();
            }

            Debug.Log($"[STLMeshLoader] Loaded mesh: {meshName} ({vertices.Count} vertices, {triangles.Count / 3} triangles)");

            return mesh;
        }

        /// <summary>
        /// Check if STL data is ASCII format
        /// </summary>
        private static bool IsAsciiSTL(byte[] data)
        {
            // ASCII STL starts with "solid "
            if (data.Length < 6) return false;

            string header = Encoding.ASCII.GetString(data, 0, 6);
            if (!header.StartsWith("solid")) return false;

            // Additional check: look for "facet normal" in first 1000 bytes
            int checkLength = Math.Min(data.Length, 1000);
            string sample = Encoding.ASCII.GetString(data, 0, checkLength);
            return sample.Contains("facet normal");
        }

        /// <summary>
        /// Parse ASCII STL format
        /// </summary>
        private static void ParseAsciiSTL(string content, out List<Vector3> vertices,
            out List<Vector3> normals, out List<int> triangles)
        {
            vertices = new List<Vector3>();
            normals = new List<Vector3>();
            triangles = new List<int>();

            string[] lines = content.Split('\n');
            Vector3 currentNormal = Vector3.up;
            int vertexIndex = 0;

            foreach (string rawLine in lines)
            {
                string line = rawLine.Trim();

                if (line.StartsWith("facet normal"))
                {
                    currentNormal = ParseVector3FromLine(line, "facet normal");
                }
                else if (line.StartsWith("vertex"))
                {
                    // STL uses (X, Y, Z) - Unity uses (X, Y, Z) but with different handedness
                    // Convert from ROS/STL coordinate system to Unity
                    Vector3 v = ParseVector3FromLine(line, "vertex");
                    vertices.Add(ConvertSTLToUnityCoordinates(v));
                    normals.Add(ConvertSTLToUnityNormal(currentNormal));
                    triangles.Add(vertexIndex++);
                }
            }
        }

        /// <summary>
        /// Parse Binary STL format
        /// </summary>
        private static void ParseBinarySTL(byte[] data, out List<Vector3> vertices,
            out List<Vector3> normals, out List<int> triangles)
        {
            vertices = new List<Vector3>();
            normals = new List<Vector3>();
            triangles = new List<int>();

            // Binary STL format:
            // 80 bytes: Header
            // 4 bytes: Number of triangles (uint32)
            // For each triangle:
            //   12 bytes: Normal vector (3x float32)
            //   12 bytes: Vertex 1 (3x float32)
            //   12 bytes: Vertex 2 (3x float32)
            //   12 bytes: Vertex 3 (3x float32)
            //   2 bytes: Attribute byte count

            if (data.Length < 84)
            {
                Debug.LogError("[STLMeshLoader] Binary STL too short");
                return;
            }

            uint triangleCount = BitConverter.ToUInt32(data, 80);

            // Sanity check
            int expectedSize = 84 + (int)triangleCount * 50;
            if (data.Length < expectedSize)
            {
                Debug.LogWarning($"[STLMeshLoader] Binary STL size mismatch. Expected {expectedSize}, got {data.Length}");
                // Adjust triangle count based on actual size
                triangleCount = (uint)((data.Length - 84) / 50);
            }

            int offset = 84;
            int vertexIndex = 0;

            for (uint i = 0; i < triangleCount; i++)
            {
                // Normal
                float nx = BitConverter.ToSingle(data, offset);
                float ny = BitConverter.ToSingle(data, offset + 4);
                float nz = BitConverter.ToSingle(data, offset + 8);
                Vector3 normal = ConvertSTLToUnityNormal(new Vector3(nx, ny, nz));
                offset += 12;

                // Three vertices
                for (int v = 0; v < 3; v++)
                {
                    float vx = BitConverter.ToSingle(data, offset);
                    float vy = BitConverter.ToSingle(data, offset + 4);
                    float vz = BitConverter.ToSingle(data, offset + 8);
                    offset += 12;

                    Vector3 vertex = ConvertSTLToUnityCoordinates(new Vector3(vx, vy, vz));
                    vertices.Add(vertex);
                    normals.Add(normal);
                    triangles.Add(vertexIndex++);
                }

                // Skip attribute byte count
                offset += 2;
            }
        }

        /// <summary>
        /// Parse Vector3 from ASCII STL line
        /// </summary>
        private static Vector3 ParseVector3FromLine(string line, string prefix)
        {
            string values = line.Substring(prefix.Length).Trim();
            string[] parts = values.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);

            if (parts.Length >= 3)
            {
                if (float.TryParse(parts[0], System.Globalization.NumberStyles.Float,
                    System.Globalization.CultureInfo.InvariantCulture, out float x) &&
                    float.TryParse(parts[1], System.Globalization.NumberStyles.Float,
                    System.Globalization.CultureInfo.InvariantCulture, out float y) &&
                    float.TryParse(parts[2], System.Globalization.NumberStyles.Float,
                    System.Globalization.CultureInfo.InvariantCulture, out float z))
                {
                    return new Vector3(x, y, z);
                }
            }
            return Vector3.zero;
        }

        /// <summary>
        /// Convert STL coordinates to Unity coordinate system.
        /// STL/ROS uses X-forward, Y-left, Z-up.
        /// Unity uses X-right, Y-up, Z-forward.
        /// </summary>
        private static Vector3 ConvertSTLToUnityCoordinates(Vector3 stlCoord)
        {
            // Standard conversion: X -> -Y, Y -> Z, Z -> X (for ROS to Unity)
            // However, most STL files use Y-up already, so we may need to adjust
            // For now, use a simpler conversion that works for most robot URDFs
            return new Vector3(stlCoord.x, stlCoord.z, stlCoord.y);
        }

        /// <summary>
        /// Convert STL normal to Unity coordinate system.
        /// </summary>
        private static Vector3 ConvertSTLToUnityNormal(Vector3 stlNormal)
        {
            return new Vector3(stlNormal.x, stlNormal.z, stlNormal.y);
        }

        /// <summary>
        /// Create a GameObject with the loaded mesh
        /// </summary>
        public static GameObject CreateMeshGameObject(string filePath, string name = null, Material material = null)
        {
            Mesh mesh = LoadMesh(filePath);
            if (mesh == null) return null;

            GameObject obj = new GameObject(name ?? mesh.name);

            MeshFilter filter = obj.AddComponent<MeshFilter>();
            filter.mesh = mesh;

            MeshRenderer renderer = obj.AddComponent<MeshRenderer>();
            if (material != null)
            {
                renderer.material = material;
            }
            else
            {
                // Default material
                Material mat = new Material(Shader.Find("Standard"));
                mat.color = new Color(0.8f, 0.8f, 0.82f);
                mat.SetFloat("_Metallic", 0.3f);
                mat.SetFloat("_Glossiness", 0.5f);
                renderer.material = mat;
            }

            return obj;
        }

        /// <summary>
        /// Create a GameObject with mesh and optional collider
        /// </summary>
        public static GameObject CreateMeshWithCollider(string filePath, string name = null,
            Material material = null, bool addCollider = true)
        {
            GameObject obj = CreateMeshGameObject(filePath, name, material);
            if (obj == null) return null;

            if (addCollider)
            {
                MeshCollider collider = obj.AddComponent<MeshCollider>();
                collider.sharedMesh = obj.GetComponent<MeshFilter>().mesh;
                collider.convex = false;
            }

            return obj;
        }
    }
}
