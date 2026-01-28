using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.DigitalTwin
{
    /// <summary>
    /// Controller for CNC machine visualization.
    /// Handles axis movement, spindle animation, and state visualization.
    /// </summary>
    public class MachineController : MonoBehaviour
    {
        [Header("Machine Info")]
        [SerializeField] private string machineId;
        [SerializeField] private MachineType machineType;

        [Header("Axis References")]
        [SerializeField] private Transform xAxis;
        [SerializeField] private Transform yAxis;
        [SerializeField] private Transform zAxis;
        [SerializeField] private Transform spindle;

        [Header("Motion Settings")]
        [SerializeField] private float positionSmoothTime = 0.05f;
        [SerializeField] private float maxSpindleRPM = 10000f;

        [Header("Visual Indicators")]
        [SerializeField] private Renderer statusLED;
        [SerializeField] private Material idleMaterial;
        [SerializeField] private Material runningMaterial;
        [SerializeField] private Material alarmMaterial;

        // State
        private Vector3 currentPosition;
        private Vector3 targetPosition;
        private Vector3 positionVelocity;
        private float spindleSpeed = 0f;
        private float currentSpindleAngle = 0f;
        private int machineStatus = 0;

        // Work envelope (mm)
        private Vector3 minPosition = Vector3.zero;
        private Vector3 maxPosition = new Vector3(140, 102, 152); // Bantam Explorer

        public string MachineId => machineId;
        public MachineType Type => machineType;
        public Vector3 CurrentPosition => currentPosition;

        /// <summary>
        /// Initialize the machine controller
        /// </summary>
        public void Initialize(string id, MachineType type)
        {
            machineId = id;
            machineType = type;

            // Set work envelope based on machine type
            switch (type)
            {
                case MachineType.BantamCNC:
                    minPosition = Vector3.zero;
                    maxPosition = new Vector3(140, 102, 152); // mm
                    break;
                default:
                    maxPosition = new Vector3(300, 300, 300);
                    break;
            }

            // Find axis transforms if not assigned
            if (xAxis == null) xAxis = transform.Find("XAxis");
            if (yAxis == null) yAxis = transform.Find("YAxis");
            if (zAxis == null) zAxis = transform.Find("ZAxis");
            if (spindle == null) spindle = transform.Find("Spindle");

            Debug.Log($"[MachineController] Initialized {machineId} as {machineType}");
        }

        private void Update()
        {
            UpdateAxisPositions();
            UpdateSpindleRotation();
        }

        /// <summary>
        /// Set the target position for smooth interpolation
        /// </summary>
        public void UpdateTargetPosition(Vector3 position)
        {
            // Position comes in meters from DigitalTwinController
            targetPosition = position;
        }

        /// <summary>
        /// Set machine state from TinyG status
        /// </summary>
        public void SetMachineState(int status, float feed, float spindleRPM)
        {
            machineStatus = status;
            spindleSpeed = spindleRPM;

            UpdateStatusIndicator();
        }

        private void UpdateAxisPositions()
        {
            // Smooth interpolation to target position
            currentPosition = Vector3.SmoothDamp(
                currentPosition,
                targetPosition,
                ref positionVelocity,
                positionSmoothTime
            );

            // Apply to axis transforms (if available)
            if (xAxis != null)
            {
                var pos = xAxis.localPosition;
                pos.x = currentPosition.x;
                xAxis.localPosition = pos;
            }

            if (yAxis != null)
            {
                var pos = yAxis.localPosition;
                pos.z = currentPosition.z; // Y axis moves in Z direction in Unity
                yAxis.localPosition = pos;
            }

            if (zAxis != null)
            {
                var pos = zAxis.localPosition;
                pos.y = currentPosition.y;
                zAxis.localPosition = pos;
            }
        }

        private void UpdateSpindleRotation()
        {
            if (spindle == null || spindleSpeed <= 0) return;

            // Rotate spindle based on RPM
            float degreesPerSecond = (spindleSpeed / 60f) * 360f;
            currentSpindleAngle += degreesPerSecond * Time.deltaTime;
            currentSpindleAngle %= 360f;

            spindle.localRotation = Quaternion.Euler(0, currentSpindleAngle, 0);
        }

        private void UpdateStatusIndicator()
        {
            if (statusLED == null) return;

            Material mat = machineStatus switch
            {
                2 => alarmMaterial,  // Alarm
                5 => runningMaterial, // Running
                _ => idleMaterial     // Idle/Ready
            };

            if (mat != null)
            {
                statusLED.material = mat;
            }
        }

        /// <summary>
        /// Get position in work coordinates (mm)
        /// </summary>
        public Vector3 GetWorkPosition()
        {
            return currentPosition * 1000f; // Convert meters to mm
        }

        /// <summary>
        /// Check if position is within work envelope
        /// </summary>
        public bool IsWithinWorkEnvelope(Vector3 positionMM)
        {
            return positionMM.x >= minPosition.x && positionMM.x <= maxPosition.x &&
                   positionMM.y >= minPosition.y && positionMM.y <= maxPosition.y &&
                   positionMM.z >= minPosition.z && positionMM.z <= maxPosition.z;
        }

        /// <summary>
        /// Home the machine (visual only - sends command via SocketIO)
        /// </summary>
        public void Home()
        {
            Debug.Log($"[MachineController] Homing {machineId}");
            // Actual homing is done via DigitalTwinController.SendGCode("G28")
        }

        /// <summary>
        /// Set spindle speed (visual only)
        /// </summary>
        public void SetSpindleSpeed(float rpm)
        {
            spindleSpeed = Mathf.Clamp(rpm, 0, maxSpindleRPM);
        }

        /// <summary>
        /// Highlight the machine (for selection)
        /// </summary>
        public void SetHighlighted(bool highlighted)
        {
            // Could add outline effect or change material
            var renderers = GetComponentsInChildren<Renderer>();
            foreach (var r in renderers)
            {
                if (highlighted)
                {
                    // Add highlight
                    r.material.SetFloat("_OutlineWidth", 0.01f);
                }
                else
                {
                    r.material.SetFloat("_OutlineWidth", 0f);
                }
            }
        }
    }
}
