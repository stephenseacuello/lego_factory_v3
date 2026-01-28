using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Safety
{
    /// <summary>
    /// Visualizes collisions and proximity warnings with highlights and overlays.
    /// Part of Feature 1.2: Collision Detection (HIGH PRIORITY)
    /// </summary>
    public class CollisionVisualizer : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private CollisionDetector collisionDetector;
        [SerializeField] private Material highlightMaterial;
        [SerializeField] private Material proximityMaterial;

        [Header("Visual Settings")]
        [SerializeField] private Color collisionColor = new Color(1f, 0f, 0f, 0.5f);
        [SerializeField] private Color proximityColor = new Color(1f, 1f, 0f, 0.3f);
        [SerializeField] private float pulseSpeed = 2f;
        [SerializeField] private bool enablePulse = true;

        [Header("Highlight Settings")]
        [SerializeField] private bool highlightColliders = true;
        [SerializeField] private float highlightDuration = 0.5f;
        [SerializeField] private LayerMask visualizationLayers;

        // State
        private Dictionary<GameObject, HighlightState> highlightedObjects = new Dictionary<GameObject, HighlightState>();
        private List<GameObject> objectsToRemove = new List<GameObject>();
        private float pulseTimer = 0f;

        private class HighlightState
        {
            public GameObject gameObject;
            public Renderer[] renderers;
            public Material[] originalMaterials;
            public Material[] highlightMaterials;
            public float startTime;
            public bool isCollision;
        }

        void Start()
        {
            if (collisionDetector == null)
            {
                collisionDetector = GetComponent<CollisionDetector>();
            }

            if (collisionDetector != null)
            {
                collisionDetector.OnCollisionDetected += HandleCollisionVisualization;
                collisionDetector.OnCollisionCleared += HandleCollisionCleared;
                collisionDetector.OnProximityWarning += HandleProximityVisualization;
                collisionDetector.OnProximityClear += HandleProximityCleared;
            }

            // Create default materials if not assigned
            if (highlightMaterial == null)
            {
                highlightMaterial = CreateHighlightMaterial(collisionColor);
            }
            if (proximityMaterial == null)
            {
                proximityMaterial = CreateHighlightMaterial(proximityColor);
            }
        }

        void OnDestroy()
        {
            if (collisionDetector != null)
            {
                collisionDetector.OnCollisionDetected -= HandleCollisionVisualization;
                collisionDetector.OnCollisionCleared -= HandleCollisionCleared;
                collisionDetector.OnProximityWarning -= HandleProximityVisualization;
                collisionDetector.OnProximityClear -= HandleProximityCleared;
            }

            ClearAllHighlights();
        }

        void Update()
        {
            // Update pulse effect
            if (enablePulse)
            {
                pulseTimer += Time.deltaTime * pulseSpeed;
                float pulseValue = (Mathf.Sin(pulseTimer) + 1f) * 0.5f;

                foreach (var kvp in highlightedObjects)
                {
                    UpdateHighlightPulse(kvp.Value, pulseValue);
                }
            }

            // Remove expired highlights
            objectsToRemove.Clear();
            foreach (var kvp in highlightedObjects)
            {
                if (Time.time - kvp.Value.startTime > highlightDuration)
                {
                    objectsToRemove.Add(kvp.Key);
                }
            }

            foreach (var obj in objectsToRemove)
            {
                RemoveHighlight(obj);
            }
        }

        /// <summary>
        /// Handle collision visualization
        /// </summary>
        private void HandleCollisionVisualization(CollisionEvent collisionEvent)
        {
            if (!highlightColliders) return;

            GameObject collidingObject = collisionEvent.CollidingObject;
            if (collidingObject != null)
            {
                HighlightObject(collidingObject, true);
                Debug.Log($"[CollisionVisualizer] Highlighting collision with {collidingObject.name}");
            }
        }

        /// <summary>
        /// Handle collision cleared
        /// </summary>
        private void HandleCollisionCleared()
        {
            // Remove collision highlights (but keep proximity highlights)
            objectsToRemove.Clear();
            foreach (var kvp in highlightedObjects)
            {
                if (kvp.Value.isCollision)
                {
                    objectsToRemove.Add(kvp.Key);
                }
            }

            foreach (var obj in objectsToRemove)
            {
                RemoveHighlight(obj);
            }
        }

        /// <summary>
        /// Handle proximity warning visualization
        /// </summary>
        private void HandleProximityVisualization(ProximityWarning warning)
        {
            if (!highlightColliders) return;

            GameObject nearbyObject = warning.NearbyObject;
            if (nearbyObject != null)
            {
                HighlightObject(nearbyObject, false);
            }
        }

        /// <summary>
        /// Handle proximity cleared
        /// </summary>
        private void HandleProximityCleared()
        {
            // Remove proximity highlights (but keep collision highlights)
            objectsToRemove.Clear();
            foreach (var kvp in highlightedObjects)
            {
                if (!kvp.Value.isCollision)
                {
                    objectsToRemove.Add(kvp.Key);
                }
            }

            foreach (var obj in objectsToRemove)
            {
                RemoveHighlight(obj);
            }
        }

        /// <summary>
        /// Highlight an object with collision or proximity material
        /// </summary>
        private void HighlightObject(GameObject obj, bool isCollision)
        {
            if (obj == null) return;

            // If already highlighted, update state
            if (highlightedObjects.ContainsKey(obj))
            {
                highlightedObjects[obj].startTime = Time.time;
                highlightedObjects[obj].isCollision = isCollision;
                return;
            }

            // Get all renderers
            Renderer[] renderers = obj.GetComponentsInChildren<Renderer>();
            if (renderers.Length == 0) return;

            // Store original materials
            var state = new HighlightState
            {
                gameObject = obj,
                renderers = renderers,
                originalMaterials = new Material[renderers.Length],
                highlightMaterials = new Material[renderers.Length],
                startTime = Time.time,
                isCollision = isCollision
            };

            // Replace materials
            Material highlightMat = isCollision ? highlightMaterial : proximityMaterial;
            for (int i = 0; i < renderers.Length; i++)
            {
                state.originalMaterials[i] = renderers[i].material;
                state.highlightMaterials[i] = highlightMat;
                renderers[i].material = highlightMat;
            }

            highlightedObjects[obj] = state;
        }

        /// <summary>
        /// Remove highlight from object
        /// </summary>
        private void RemoveHighlight(GameObject obj)
        {
            if (!highlightedObjects.ContainsKey(obj)) return;

            var state = highlightedObjects[obj];

            // Restore original materials
            for (int i = 0; i < state.renderers.Length; i++)
            {
                if (state.renderers[i] != null && state.originalMaterials[i] != null)
                {
                    state.renderers[i].material = state.originalMaterials[i];
                }
            }

            highlightedObjects.Remove(obj);
        }

        /// <summary>
        /// Clear all highlights
        /// </summary>
        private void ClearAllHighlights()
        {
            foreach (var kvp in highlightedObjects)
            {
                RemoveHighlight(kvp.Key);
            }
            highlightedObjects.Clear();
        }

        /// <summary>
        /// Update highlight pulse effect
        /// </summary>
        private void UpdateHighlightPulse(HighlightState state, float pulseValue)
        {
            if (state.renderers == null) return;

            Color baseColor = state.isCollision ? collisionColor : proximityColor;
            Color pulsedColor = baseColor * (0.5f + pulseValue * 0.5f);

            for (int i = 0; i < state.renderers.Length; i++)
            {
                if (state.renderers[i] != null && state.highlightMaterials[i] != null)
                {
                    state.renderers[i].material.color = pulsedColor;
                }
            }
        }

        /// <summary>
        /// Create highlight material
        /// </summary>
        private Material CreateHighlightMaterial(Color color)
        {
            Material mat = new Material(Shader.Find("Standard"));
            mat.SetFloat("_Mode", 3); // Transparent mode
            mat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            mat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            mat.SetInt("_ZWrite", 0);
            mat.DisableKeyword("_ALPHATEST_ON");
            mat.EnableKeyword("_ALPHABLEND_ON");
            mat.DisableKeyword("_ALPHAPREMULTIPLY_ON");
            mat.renderQueue = 3000;
            mat.color = color;
            return mat;
        }

        /// <summary>
        /// Enable or disable visualization
        /// </summary>
        public void SetVisualizationEnabled(bool enabled)
        {
            highlightColliders = enabled;
            if (!enabled)
            {
                ClearAllHighlights();
            }
        }

        /// <summary>
        /// Set collision color
        /// </summary>
        public void SetCollisionColor(Color color)
        {
            collisionColor = color;
            highlightMaterial = CreateHighlightMaterial(color);
        }

        /// <summary>
        /// Set proximity color
        /// </summary>
        public void SetProximityColor(Color color)
        {
            proximityColor = color;
            proximityMaterial = CreateHighlightMaterial(color);
        }
    }
}

