using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Simulation
{
    /// <summary>
    /// Simulates chip generation and evacuation during machining.
    /// Visualizes chips as particles with physics-based behavior.
    /// Part of Feature 1.1: Material Removal Simulation (MEDIUM PRIORITY)
    /// </summary>
    public class ChipGenerationSimulator : MonoBehaviour
    {
        [Header("Chip Generation")]
        [SerializeField] private bool enableChipGeneration = true;
        [SerializeField] private float chipGenerationRate = 10f; // chips per second
        [SerializeField] private GameObject chipPrefab;

        [Header("Chip Properties")]
        [SerializeField] private float chipSize = 0.002f; // 2mm
        [SerializeField] private Color chipColor = new Color(0.6f, 0.6f, 0.6f);
        [SerializeField] private float chipLifetime = 5f; // seconds

        [Header("Physics")]
        [SerializeField] private float initialVelocity = 2f; // m/s
        [SerializeField] private float velocityVariation = 0.5f;
        [SerializeField] private bool useGravity = true;

        [Header("Particle System")]
        [SerializeField] private int maxChips = 1000;
        [SerializeField] private bool useParticleSystem = true;

        // Chip management
        private List<Chip> activeChips = new List<Chip>();
        private float chipTimer = 0f;
        private ParticleSystem chipParticleSystem;

        // Statistics
        private int totalChipsGenerated = 0;
        private float totalChipVolume = 0f;

        // Events
        public event Action<ChipData> OnChipGenerated;

        private class Chip
        {
            public GameObject gameObject;
            public float birthTime;
            public Vector3 velocity;
        }

        void Start()
        {
            InitializeChipSystem();
        }

        void Update()
        {
            if (!enableChipGeneration) return;

            chipTimer += Time.deltaTime;
            if (chipTimer >= 1f / chipGenerationRate)
            {
                GenerateChip();
                chipTimer = 0f;
            }

            UpdateChips();
        }

        /// <summary>
        /// Initialize chip generation system
        /// </summary>
        private void InitializeChipSystem()
        {
            if (useParticleSystem)
            {
                // Create particle system for chips
                var psObj = new GameObject("ChipParticles");
                psObj.transform.SetParent(transform);
                chipParticleSystem = psObj.AddComponent<ParticleSystem>();

                var main = chipParticleSystem.main;
                main.startLifetime = chipLifetime;
                main.startSize = chipSize;
                main.startColor = chipColor;
                main.maxParticles = maxChips;
                main.simulationSpace = ParticleSystemSimulationSpace.World;

                var emission = chipParticleSystem.emission;
                emission.rateOverTime = chipGenerationRate;

                var shape = chipParticleSystem.shape;
                shape.shapeType = ParticleSystemShapeType.Sphere;
                shape.radius = chipSize;
            }
        }

        /// <summary>
        /// Generate a chip at tool position
        /// </summary>
        public void GenerateChip()
        {
            if (useParticleSystem && chipParticleSystem != null)
            {
                // Particle system handles generation automatically
                totalChipsGenerated++;
                totalChipVolume += chipSize * chipSize * chipSize;
                return;
            }

            // Manual chip generation
            if (activeChips.Count >= maxChips)
            {
                // Remove oldest chip
                RemoveChip(activeChips[0]);
            }

            Vector3 position = transform.position;
            Vector3 velocity = CalculateChipVelocity();

            GameObject chipObj;
            if (chipPrefab != null)
            {
                chipObj = Instantiate(chipPrefab, position, Quaternion.identity);
            }
            else
            {
                chipObj = GameObject.CreatePrimitive(PrimitiveType.Cube);
                chipObj.transform.position = position;
                chipObj.transform.localScale = Vector3.one * chipSize;
                chipObj.GetComponent<Renderer>().material.color = chipColor;

                // Add physics
                var rb = chipObj.AddComponent<Rigidbody>();
                rb.mass = 0.001f; // 1 gram
                rb.useGravity = useGravity;
                rb.velocity = velocity;
            }

            var chip = new Chip
            {
                gameObject = chipObj,
                birthTime = Time.time,
                velocity = velocity
            };

            activeChips.Add(chip);
            totalChipsGenerated++;
            totalChipVolume += chipSize * chipSize * chipSize;

            var chipData = new ChipData
            {
                Timestamp = DateTime.UtcNow,
                Position = position,
                Velocity = velocity,
                Size = chipSize
            };

            OnChipGenerated?.Invoke(chipData);
        }

        /// <summary>
        /// Calculate chip ejection velocity
        /// </summary>
        private Vector3 CalculateChipVelocity()
        {
            // Base velocity in cutting direction
            Vector3 baseVelocity = transform.forward * initialVelocity;

            // Add random variation
            Vector3 variation = new Vector3(
                UnityEngine.Random.Range(-velocityVariation, velocityVariation),
                UnityEngine.Random.Range(0, velocityVariation),
                UnityEngine.Random.Range(-velocityVariation, velocityVariation)
            );

            return baseVelocity + variation;
        }

        /// <summary>
        /// Update active chips
        /// </summary>
        private void UpdateChips()
        {
            for (int i = activeChips.Count - 1; i >= 0; i--)
            {
                var chip = activeChips[i];

                // Check lifetime
                if (Time.time - chip.birthTime > chipLifetime)
                {
                    RemoveChip(chip);
                    activeChips.RemoveAt(i);
                }
            }
        }

        /// <summary>
        /// Remove a chip
        /// </summary>
        private void RemoveChip(Chip chip)
        {
            if (chip.gameObject != null)
            {
                Destroy(chip.gameObject);
            }
        }

        /// <summary>
        /// Enable or disable chip generation
        /// </summary>
        public void SetChipGeneration(bool enabled)
        {
            enableChipGeneration = enabled;
            if (chipParticleSystem != null)
            {
                if (enabled)
                    chipParticleSystem.Play();
                else
                    chipParticleSystem.Stop();
            }
        }

        /// <summary>
        /// Clear all chips
        /// </summary>
        public void ClearChips()
        {
            foreach (var chip in activeChips)
            {
                RemoveChip(chip);
            }
            activeChips.Clear();

            if (chipParticleSystem != null)
            {
                chipParticleSystem.Clear();
            }
        }

        /// <summary>
        /// Get chip generation statistics
        /// </summary>
        public ChipStatistics GetStatistics()
        {
            return new ChipStatistics
            {
                TotalChipsGenerated = totalChipsGenerated,
                ActiveChips = activeChips.Count,
                TotalChipVolume = totalChipVolume,
                ChipGenerationRate = chipGenerationRate
            };
        }

        void OnDestroy()
        {
            ClearChips();
        }

        #region Public Properties

        public int TotalChipsGenerated => totalChipsGenerated;
        public int ActiveChips => activeChips.Count;
        public bool IsGenerating => enableChipGeneration;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Chip generation data
    /// </summary>
    [Serializable]
    public struct ChipData
    {
        public DateTime Timestamp;
        public Vector3 Position;
        public Vector3 Velocity;
        public float Size;
    }

    /// <summary>
    /// Chip generation statistics
    /// </summary>
    [Serializable]
    public struct ChipStatistics
    {
        public int TotalChipsGenerated;
        public int ActiveChips;
        public float TotalChipVolume;
        public float ChipGenerationRate;
    }

    #endregion
}
