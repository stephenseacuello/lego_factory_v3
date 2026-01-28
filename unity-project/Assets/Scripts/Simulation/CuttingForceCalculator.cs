using System;
using UnityEngine;

namespace CNCScada.Simulation
{
    /// <summary>
    /// Calculates cutting forces based on material properties, tool geometry, and cutting parameters.
    /// Uses mechanistic cutting force model.
    /// Part of Feature 1.1: Material Removal Simulation (MEDIUM PRIORITY)
    /// </summary>
    public class CuttingForceCalculator : MonoBehaviour
    {
        [Header("Material Properties")]
        [SerializeField] private float materialHardness = 70f; // HB (Brinell)
        [SerializeField] private float specificCuttingForce = 2000f; // N/mm² (aluminum)
        [SerializeField] private string materialType = "Aluminum 6061";

        [Header("Tool Geometry")]
        [SerializeField] private float toolDiameter = 6f; // mm
        [SerializeField] private int numberOfFlutes = 2;
        [SerializeField] private float helix Angle = 30f; // degrees
        [SerializeField] private float rakeAngle = 10f; // degrees

        [Header("Cutting Parameters")]
        [SerializeField] private float spindleSpeed = 10000f; // RPM
        [SerializeField] private float feedRate = 500f; // mm/min
        [SerializeField] private float depthOfCut = 1f; // mm
        [SerializeField] private float widthOfCut = 3f; // mm

        // Force components
        private Vector3 currentForce = Vector3.zero;
        private float tangentialForce = 0f;
        private float radialForce = 0f;
        private float axialForce = 0f;

        // Statistics
        private float maxForce = 0f;
        private float avgForce = 0f;
        private int forceCalculations = 0;

        // Events
        public event Action<CuttingForceData> OnForceCalculated;

        /// <summary>
        /// Calculate cutting forces for current cutting conditions
        /// </summary>
        public CuttingForceData CalculateForces()
        {
            // Calculate chip load (feed per tooth)
            float feedPerTooth = feedRate / (spindleSpeed * numberOfFlutes); // mm/tooth

            // Calculate chip area
            float chipArea = feedPerTooth * depthOfCut; // mm²

            // Calculate tangential cutting force (primary cutting force)
            tangentialForce = specificCuttingForce * chipArea; // N

            // Calculate radial force (approximately 30-40% of tangential)
            radialForce = tangentialForce * 0.35f;

            // Calculate axial force (approximately 20-30% of tangential)
            axialForce = tangentialForce * 0.25f;

            // Apply geometry corrections
            ApplyGeometryCorrections();

            // Calculate resultant force magnitude
            float forceMagnitude = Mathf.Sqrt(
                tangentialForce * tangentialForce +
                radialForce * radialForce +
                axialForce * axialForce
            );

            // Update force vector (in tool coordinate system)
            currentForce = new Vector3(radialForce, axialForce, tangentialForce);

            // Update statistics
            maxForce = Mathf.Max(maxForce, forceMagnitude);
            avgForce = (avgForce * forceCalculations + forceMagnitude) / (forceCalculations + 1);
            forceCalculations++;

            var forceData = new CuttingForceData
            {
                Timestamp = DateTime.UtcNow,
                TangentialForce = tangentialForce,
                RadialForce = radialForce,
                AxialForce = axialForce,
                TotalForce = forceMagnitude,
                FeedPerTooth = feedPerTooth,
                ChipArea = chipArea,
                Power = CalculatePower(tangentialForce)
            };

            OnForceCalculated?.Invoke(forceData);

            return forceData;
        }

        /// <summary>
        /// Apply corrections based on tool geometry
        /// </summary>
        private void ApplyGeometryCorrections()
        {
            // Helix angle correction
            float helixFactor = Mathf.Cos(helixAngle * Mathf.Deg2Rad);
            tangentialForce *= helixFactor;

            // Rake angle correction
            float rakeFactor = 1f - (rakeAngle / 90f) * 0.2f;
            tangentialForce *= rakeFactor;

            // Tool wear factor (placeholder - would be updated based on tool wear)
            float wearFactor = 1.0f;
            tangentialForce *= wearFactor;
        }

        /// <summary>
        /// Calculate cutting power
        /// </summary>
        private float CalculatePower(float force)
        {
            // Cutting velocity (m/min)
            float cuttingVelocity = (Mathf.PI * toolDiameter * spindleSpeed) / 1000f;

            // Power (kW) = Force (N) * Velocity (m/min) / 60000
            return (force * cuttingVelocity) / 60000f;
        }

        /// <summary>
        /// Set material properties
        /// </summary>
        public void SetMaterial(string type, float hardness, float cuttingForce)
        {
            materialType = type;
            materialHardness = hardness;
            specificCuttingForce = cuttingForce;
            Debug.Log($"[CuttingForceCalculator] Material set: {type}, Hardness: {hardness} HB");
        }

        /// <summary>
        /// Set tool geometry
        /// </summary>
        public void SetToolGeometry(float diameter, int flutes, float helix, float rake)
        {
            toolDiameter = diameter;
            numberOfFlutes = flutes;
            helixAngle = helix;
            rakeAngle = rake;
            Debug.Log($"[CuttingForceCalculator] Tool geometry set: D={diameter}mm, Flutes={flutes}");
        }

        /// <summary>
        /// Set cutting parameters
        /// </summary>
        public void SetCuttingParameters(float rpm, float feed, float doc, float woc)
        {
            spindleSpeed = rpm;
            feedRate = feed;
            depthOfCut = doc;
            widthOfCut = woc;
        }

        /// <summary>
        /// Get force statistics
        /// </summary>
        public ForceStatistics GetStatistics()
        {
            return new ForceStatistics
            {
                CurrentForce = currentForce.magnitude,
                MaxForce = maxForce,
                AverageForce = avgForce,
                TotalCalculations = forceCalculations,
                CurrentPower = CalculatePower(tangentialForce)
            };
        }

        #region Public Properties

        public Vector3 CurrentForce => currentForce;
        public float TangentialForce => tangentialForce;
        public float RadialForce => radialForce;
        public float AxialForce => axialForce;
        public float MaxForce => maxForce;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Cutting force data
    /// </summary>
    [Serializable]
    public struct CuttingForceData
    {
        public DateTime Timestamp;
        public float TangentialForce; // N
        public float RadialForce; // N
        public float AxialForce; // N
        public float TotalForce; // N
        public float FeedPerTooth; // mm/tooth
        public float ChipArea; // mm²
        public float Power; // kW
    }

    /// <summary>
    /// Force statistics
    /// </summary>
    [Serializable]
    public struct ForceStatistics
    {
        public float CurrentForce;
        public float MaxForce;
        public float AverageForce;
        public int TotalCalculations;
        public float CurrentPower;
    }

    #endregion
}
