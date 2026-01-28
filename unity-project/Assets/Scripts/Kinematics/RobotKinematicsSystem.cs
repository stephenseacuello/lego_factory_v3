using System;
using System.Collections.Generic;
using UnityEngine;
using CNC_SCADA.DigitalTwin.ROS2;

namespace CNC_SCADA.DigitalTwin.Kinematics
{
    /// <summary>
    /// Robot Kinematics System for Forward/Inverse Kinematics calculations
    /// Supports DH parameters, joint limits, workspace analysis, and trajectory planning
    /// </summary>
    public class RobotKinematicsSystem : MonoBehaviour
    {
        public static RobotKinematicsSystem Instance { get; private set; }

        [Header("Robot Configuration")]
        [SerializeField] private RobotType robotType = RobotType.SixAxisArm;
        [SerializeField] private string robotName = "robot_arm";
        [SerializeField] private int numJoints = 6;

        [Header("Kinematics Settings")]
        [SerializeField] private float ikTolerance = 0.001f;
        [SerializeField] private int ikMaxIterations = 100;
        [SerializeField] private float ikDampingFactor = 0.5f;
        [SerializeField] private IKSolver ikSolverType = IKSolver.DampedLeastSquares;

        [Header("Collision Detection")]
        [SerializeField] private bool enableSelfCollision = true;
        [SerializeField] private bool enableEnvironmentCollision = true;
        [SerializeField] private LayerMask collisionLayers;

        // Events
        public event Action<JointConfiguration> OnJointConfigurationChanged;
        public event Action<CartesianPose> OnEndEffectorPoseChanged;
        public event Action<CollisionEvent> OnCollisionDetected;
        public event Action<bool> OnIKSolutionFound;

        // Robot model
        private DHParameters[] dhParams;
        private JointLimits[] jointLimits;
        private JointConfiguration currentConfig;
        private CartesianPose currentPose;
        private Matrix4x4[] jointTransforms;
        private Transform[] jointTransformRefs;

        // Jacobian
        private float[,] jacobian;
        private float[,] jacobianPseudoInverse;

        // Statistics
        private int ikSolveCount = 0;
        private int ikSuccessCount = 0;
        private float averageIKTime = 0f;

        public JointConfiguration CurrentConfiguration => currentConfig;
        public CartesianPose CurrentPose => currentPose;
        public float IKSuccessRate => ikSolveCount > 0 ? (float)ikSuccessCount / ikSolveCount : 0f;

        private void Awake()
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

        private void Start()
        {
            InitializeRobotModel();
        }

        private void InitializeRobotModel()
        {
            // Initialize arrays
            dhParams = new DHParameters[numJoints];
            jointLimits = new JointLimits[numJoints];
            jointTransforms = new Matrix4x4[numJoints + 1];
            jacobian = new float[6, numJoints];
            jacobianPseudoInverse = new float[numJoints, 6];

            currentConfig = new JointConfiguration
            {
                JointAngles = new float[numJoints],
                JointVelocities = new float[numJoints],
                JointTorques = new float[numJoints]
            };

            // Initialize with default 6-DOF robot parameters (similar to UR5)
            InitializeDefaultDHParameters();
            InitializeDefaultJointLimits();

            // Calculate initial pose
            UpdateForwardKinematics();

            Debug.Log($"[Kinematics] Initialized {robotType} with {numJoints} joints");
        }

        private void InitializeDefaultDHParameters()
        {
            // Default DH parameters for 6-axis robot (UR5-like)
            // DH Convention: a (link length), d (link offset), alpha (link twist), theta (joint angle)
            dhParams[0] = new DHParameters { A = 0f, D = 0.089159f, Alpha = Mathf.PI / 2, ThetaOffset = 0f };
            dhParams[1] = new DHParameters { A = -0.425f, D = 0f, Alpha = 0f, ThetaOffset = 0f };
            dhParams[2] = new DHParameters { A = -0.39225f, D = 0f, Alpha = 0f, ThetaOffset = 0f };
            dhParams[3] = new DHParameters { A = 0f, D = 0.10915f, Alpha = Mathf.PI / 2, ThetaOffset = 0f };
            dhParams[4] = new DHParameters { A = 0f, D = 0.09465f, Alpha = -Mathf.PI / 2, ThetaOffset = 0f };
            dhParams[5] = new DHParameters { A = 0f, D = 0.0823f, Alpha = 0f, ThetaOffset = 0f };
        }

        private void InitializeDefaultJointLimits()
        {
            // Default joint limits (radians)
            for (int i = 0; i < numJoints; i++)
            {
                jointLimits[i] = new JointLimits
                {
                    MinAngle = -2f * Mathf.PI,
                    MaxAngle = 2f * Mathf.PI,
                    MaxVelocity = 3.14f, // rad/s
                    MaxAcceleration = 10f, // rad/s^2
                    MaxTorque = 150f // Nm
                };
            }
        }

        public void SetDHParameters(DHParameters[] parameters)
        {
            if (parameters.Length == numJoints)
            {
                dhParams = parameters;
                UpdateForwardKinematics();
            }
        }

        public void SetJointLimits(JointLimits[] limits)
        {
            if (limits.Length == numJoints)
            {
                jointLimits = limits;
            }
        }

        #region Forward Kinematics

        public CartesianPose CalculateForwardKinematics(float[] jointAngles)
        {
            if (jointAngles.Length != numJoints)
            {
                Debug.LogError($"[Kinematics] Expected {numJoints} joint angles, got {jointAngles.Length}");
                return null;
            }

            // Calculate transformation matrices
            Matrix4x4 T = Matrix4x4.identity;

            for (int i = 0; i < numJoints; i++)
            {
                float theta = jointAngles[i] + dhParams[i].ThetaOffset;
                Matrix4x4 Ti = CalculateDHTransform(dhParams[i], theta);
                T = T * Ti;
                jointTransforms[i] = T;
            }

            jointTransforms[numJoints] = T; // End effector transform

            // Extract position and orientation
            var pose = new CartesianPose
            {
                Position = new Vector3(T.m03, T.m13, T.m23),
                Rotation = T.rotation,
                TransformMatrix = T
            };

            return pose;
        }

        private Matrix4x4 CalculateDHTransform(DHParameters dh, float theta)
        {
            float ct = Mathf.Cos(theta);
            float st = Mathf.Sin(theta);
            float ca = Mathf.Cos(dh.Alpha);
            float sa = Mathf.Sin(dh.Alpha);

            Matrix4x4 T = new Matrix4x4();
            T.m00 = ct; T.m01 = -st * ca; T.m02 = st * sa; T.m03 = dh.A * ct;
            T.m10 = st; T.m11 = ct * ca; T.m12 = -ct * sa; T.m13 = dh.A * st;
            T.m20 = 0; T.m21 = sa; T.m22 = ca; T.m23 = dh.D;
            T.m30 = 0; T.m31 = 0; T.m32 = 0; T.m33 = 1;

            return T;
        }

        public void UpdateForwardKinematics()
        {
            currentPose = CalculateForwardKinematics(currentConfig.JointAngles);
            OnEndEffectorPoseChanged?.Invoke(currentPose);
        }

        #endregion

        #region Inverse Kinematics

        public IKResult SolveInverseKinematics(CartesianPose targetPose, float[] seedAngles = null)
        {
            var startTime = DateTime.Now;
            ikSolveCount++;

            float[] solution = seedAngles ?? (float[])currentConfig.JointAngles.Clone();
            IKResult result = new IKResult
            {
                TargetPose = targetPose,
                Success = false
            };

            switch (ikSolverType)
            {
                case IKSolver.DampedLeastSquares:
                    result = SolveDampedLeastSquares(targetPose, solution);
                    break;

                case IKSolver.JacobianTranspose:
                    result = SolveJacobianTranspose(targetPose, solution);
                    break;

                case IKSolver.FABRIK:
                    result = SolveFABRIK(targetPose, solution);
                    break;

                case IKSolver.Analytical:
                    result = SolveAnalytical(targetPose);
                    break;
            }

            result.SolveTime = (float)(DateTime.Now - startTime).TotalMilliseconds;

            if (result.Success)
            {
                ikSuccessCount++;
                averageIKTime = (averageIKTime * (ikSuccessCount - 1) + result.SolveTime) / ikSuccessCount;
            }

            OnIKSolutionFound?.Invoke(result.Success);
            return result;
        }

        private IKResult SolveDampedLeastSquares(CartesianPose targetPose, float[] solution)
        {
            var result = new IKResult { Success = false };

            for (int iter = 0; iter < ikMaxIterations; iter++)
            {
                // Calculate current pose
                var currentPose = CalculateForwardKinematics(solution);

                // Calculate error
                Vector3 posError = targetPose.Position - currentPose.Position;
                Quaternion rotError = targetPose.Rotation * Quaternion.Inverse(currentPose.Rotation);
                rotError.ToAngleAxis(out float angle, out Vector3 axis);
                Vector3 orientError = axis * angle * Mathf.Deg2Rad;

                float totalError = posError.magnitude + orientError.magnitude;

                if (totalError < ikTolerance)
                {
                    result.Success = true;
                    result.JointAngles = solution;
                    result.FinalPose = currentPose;
                    result.PositionError = posError.magnitude;
                    result.OrientationError = orientError.magnitude;
                    result.Iterations = iter;
                    return result;
                }

                // Calculate Jacobian
                CalculateJacobian(solution);

                // Damped least squares: dq = J^T * (J * J^T + lambda^2 * I)^-1 * e
                float[] error = new float[6];
                error[0] = posError.x;
                error[1] = posError.y;
                error[2] = posError.z;
                error[3] = orientError.x;
                error[4] = orientError.y;
                error[5] = orientError.z;

                float[] dq = CalculateDLSStep(error, ikDampingFactor);

                // Update joint angles
                for (int j = 0; j < numJoints; j++)
                {
                    solution[j] += dq[j];
                    // Apply joint limits
                    solution[j] = Mathf.Clamp(solution[j], jointLimits[j].MinAngle, jointLimits[j].MaxAngle);
                }
            }

            result.Iterations = ikMaxIterations;
            return result;
        }

        private IKResult SolveJacobianTranspose(CartesianPose targetPose, float[] solution)
        {
            var result = new IKResult { Success = false };
            float alpha = 0.1f; // Step size

            for (int iter = 0; iter < ikMaxIterations; iter++)
            {
                var currentPose = CalculateForwardKinematics(solution);

                Vector3 posError = targetPose.Position - currentPose.Position;
                float totalError = posError.magnitude;

                if (totalError < ikTolerance)
                {
                    result.Success = true;
                    result.JointAngles = solution;
                    result.FinalPose = currentPose;
                    result.PositionError = totalError;
                    result.Iterations = iter;
                    return result;
                }

                CalculateJacobian(solution);

                // dq = alpha * J^T * e
                for (int j = 0; j < numJoints; j++)
                {
                    float dq = 0;
                    dq += jacobian[0, j] * posError.x;
                    dq += jacobian[1, j] * posError.y;
                    dq += jacobian[2, j] * posError.z;
                    solution[j] += alpha * dq;
                    solution[j] = Mathf.Clamp(solution[j], jointLimits[j].MinAngle, jointLimits[j].MaxAngle);
                }
            }

            result.Iterations = ikMaxIterations;
            return result;
        }

        private IKResult SolveFABRIK(CartesianPose targetPose, float[] solution)
        {
            // Forward And Backward Reaching Inverse Kinematics
            var result = new IKResult { Success = false };

            // Get joint positions from current configuration
            Vector3[] jointPositions = new Vector3[numJoints + 1];
            float[] linkLengths = new float[numJoints];

            // Initialize positions from FK
            var pose = CalculateForwardKinematics(solution);
            for (int i = 0; i <= numJoints; i++)
            {
                jointPositions[i] = new Vector3(jointTransforms[i].m03, jointTransforms[i].m13, jointTransforms[i].m23);
            }

            // Calculate link lengths
            for (int i = 0; i < numJoints; i++)
            {
                linkLengths[i] = Vector3.Distance(jointPositions[i], jointPositions[i + 1]);
            }

            Vector3 basePos = jointPositions[0];

            for (int iter = 0; iter < ikMaxIterations; iter++)
            {
                float error = Vector3.Distance(jointPositions[numJoints], targetPose.Position);

                if (error < ikTolerance)
                {
                    result.Success = true;
                    result.PositionError = error;
                    result.Iterations = iter;
                    // Convert positions back to joint angles (simplified)
                    ConvertPositionsToAngles(jointPositions, solution);
                    result.JointAngles = solution;
                    result.FinalPose = CalculateForwardKinematics(solution);
                    return result;
                }

                // Backward reaching (from end effector to base)
                jointPositions[numJoints] = targetPose.Position;
                for (int i = numJoints - 1; i >= 0; i--)
                {
                    Vector3 dir = (jointPositions[i] - jointPositions[i + 1]).normalized;
                    jointPositions[i] = jointPositions[i + 1] + dir * linkLengths[i];
                }

                // Forward reaching (from base to end effector)
                jointPositions[0] = basePos;
                for (int i = 0; i < numJoints; i++)
                {
                    Vector3 dir = (jointPositions[i + 1] - jointPositions[i]).normalized;
                    jointPositions[i + 1] = jointPositions[i] + dir * linkLengths[i];
                }
            }

            result.Iterations = ikMaxIterations;
            return result;
        }

        private IKResult SolveAnalytical(CartesianPose targetPose)
        {
            // Analytical solution for 6-DOF robot (robot-specific)
            var result = new IKResult { Success = false };

            // This would contain robot-specific analytical IK
            // For general use, fall back to numerical method
            return SolveDampedLeastSquares(targetPose, (float[])currentConfig.JointAngles.Clone());
        }

        private void CalculateJacobian(float[] jointAngles)
        {
            // Numerical Jacobian calculation
            float delta = 0.0001f;

            var basePose = CalculateForwardKinematics(jointAngles);

            for (int j = 0; j < numJoints; j++)
            {
                float[] perturbedAngles = (float[])jointAngles.Clone();
                perturbedAngles[j] += delta;

                var perturbedPose = CalculateForwardKinematics(perturbedAngles);

                // Linear velocity columns
                jacobian[0, j] = (perturbedPose.Position.x - basePose.Position.x) / delta;
                jacobian[1, j] = (perturbedPose.Position.y - basePose.Position.y) / delta;
                jacobian[2, j] = (perturbedPose.Position.z - basePose.Position.z) / delta;

                // Angular velocity columns
                Quaternion dRot = perturbedPose.Rotation * Quaternion.Inverse(basePose.Rotation);
                dRot.ToAngleAxis(out float angle, out Vector3 axis);
                Vector3 angVel = axis * angle * Mathf.Deg2Rad / delta;

                jacobian[3, j] = angVel.x;
                jacobian[4, j] = angVel.y;
                jacobian[5, j] = angVel.z;
            }
        }

        private float[] CalculateDLSStep(float[] error, float lambda)
        {
            // Compute J * J^T + lambda^2 * I
            float[,] JJT = new float[6, 6];
            for (int i = 0; i < 6; i++)
            {
                for (int j = 0; j < 6; j++)
                {
                    JJT[i, j] = 0;
                    for (int k = 0; k < numJoints; k++)
                    {
                        JJT[i, j] += jacobian[i, k] * jacobian[j, k];
                    }
                    if (i == j) JJT[i, j] += lambda * lambda;
                }
            }

            // Invert JJT (simplified - use proper matrix inversion in production)
            float[,] JJTinv = InvertMatrix6x6(JJT);

            // Compute intermediate = JJT^-1 * error
            float[] intermediate = new float[6];
            for (int i = 0; i < 6; i++)
            {
                intermediate[i] = 0;
                for (int j = 0; j < 6; j++)
                {
                    intermediate[i] += JJTinv[i, j] * error[j];
                }
            }

            // Compute dq = J^T * intermediate
            float[] dq = new float[numJoints];
            for (int j = 0; j < numJoints; j++)
            {
                dq[j] = 0;
                for (int i = 0; i < 6; i++)
                {
                    dq[j] += jacobian[i, j] * intermediate[i];
                }
            }

            return dq;
        }

        private float[,] InvertMatrix6x6(float[,] m)
        {
            // Simplified Gauss-Jordan elimination for 6x6 matrix
            float[,] result = new float[6, 6];
            float[,] augmented = new float[6, 12];

            // Create augmented matrix [m | I]
            for (int i = 0; i < 6; i++)
            {
                for (int j = 0; j < 6; j++)
                {
                    augmented[i, j] = m[i, j];
                    augmented[i, j + 6] = (i == j) ? 1f : 0f;
                }
            }

            // Gauss-Jordan elimination
            for (int col = 0; col < 6; col++)
            {
                // Find pivot
                float maxVal = Mathf.Abs(augmented[col, col]);
                int maxRow = col;
                for (int row = col + 1; row < 6; row++)
                {
                    if (Mathf.Abs(augmented[row, col]) > maxVal)
                    {
                        maxVal = Mathf.Abs(augmented[row, col]);
                        maxRow = row;
                    }
                }

                // Swap rows
                for (int j = 0; j < 12; j++)
                {
                    float temp = augmented[col, j];
                    augmented[col, j] = augmented[maxRow, j];
                    augmented[maxRow, j] = temp;
                }

                // Scale pivot row
                float pivot = augmented[col, col];
                if (Mathf.Abs(pivot) < 1e-10f) continue;

                for (int j = 0; j < 12; j++)
                {
                    augmented[col, j] /= pivot;
                }

                // Eliminate column
                for (int row = 0; row < 6; row++)
                {
                    if (row != col)
                    {
                        float factor = augmented[row, col];
                        for (int j = 0; j < 12; j++)
                        {
                            augmented[row, j] -= factor * augmented[col, j];
                        }
                    }
                }
            }

            // Extract inverse
            for (int i = 0; i < 6; i++)
            {
                for (int j = 0; j < 6; j++)
                {
                    result[i, j] = augmented[i, j + 6];
                }
            }

            return result;
        }

        private void ConvertPositionsToAngles(Vector3[] positions, float[] angles)
        {
            // Simplified position to angle conversion
            // In practice, this requires proper geometric calculation
            for (int i = 0; i < numJoints - 1; i++)
            {
                Vector3 v1 = positions[i + 1] - positions[i];
                Vector3 v2 = positions[i + 2] - positions[i + 1];
                angles[i] = Vector3.SignedAngle(v1, v2, Vector3.up) * Mathf.Deg2Rad;
            }
        }

        #endregion

        #region Joint Configuration

        public void SetJointAngles(float[] angles, bool animate = false)
        {
            if (angles.Length != numJoints)
            {
                Debug.LogError($"[Kinematics] Expected {numJoints} angles");
                return;
            }

            // Check joint limits
            for (int i = 0; i < numJoints; i++)
            {
                angles[i] = Mathf.Clamp(angles[i], jointLimits[i].MinAngle, jointLimits[i].MaxAngle);
            }

            // Check for collisions if enabled
            if (enableSelfCollision || enableEnvironmentCollision)
            {
                var collision = CheckCollision(angles);
                if (collision != null)
                {
                    OnCollisionDetected?.Invoke(collision);
                    return;
                }
            }

            Array.Copy(angles, currentConfig.JointAngles, numJoints);
            UpdateForwardKinematics();
            OnJointConfigurationChanged?.Invoke(currentConfig);

            // Apply to Unity transforms
            ApplyToTransforms();
        }

        public bool MoveToTarget(CartesianPose targetPose)
        {
            var result = SolveInverseKinematics(targetPose);

            if (result.Success)
            {
                SetJointAngles(result.JointAngles);
                return true;
            }

            return false;
        }

        public void SetJointTransformReferences(Transform[] transforms)
        {
            jointTransformRefs = transforms;
        }

        private void ApplyToTransforms()
        {
            if (jointTransformRefs == null || jointTransformRefs.Length != numJoints) return;

            for (int i = 0; i < numJoints; i++)
            {
                if (jointTransformRefs[i] != null)
                {
                    // Apply rotation around local axis (typically Z for revolute joints)
                    jointTransformRefs[i].localRotation = Quaternion.Euler(0, 0, currentConfig.JointAngles[i] * Mathf.Rad2Deg);
                }
            }
        }

        #endregion

        #region Collision Detection

        public CollisionEvent CheckCollision(float[] jointAngles)
        {
            // Calculate all joint positions
            var pose = CalculateForwardKinematics(jointAngles);

            // Self-collision check
            if (enableSelfCollision)
            {
                for (int i = 0; i < numJoints - 2; i++)
                {
                    for (int j = i + 2; j < numJoints; j++)
                    {
                        Vector3 pi = new Vector3(jointTransforms[i].m03, jointTransforms[i].m13, jointTransforms[i].m23);
                        Vector3 pj = new Vector3(jointTransforms[j].m03, jointTransforms[j].m13, jointTransforms[j].m23);

                        float minDistance = 0.05f; // Minimum link clearance
                        if (Vector3.Distance(pi, pj) < minDistance)
                        {
                            return new CollisionEvent
                            {
                                Type = CollisionType.SelfCollision,
                                Link1Index = i,
                                Link2Index = j,
                                CollisionPoint = (pi + pj) / 2f,
                                PenetrationDepth = minDistance - Vector3.Distance(pi, pj)
                            };
                        }
                    }
                }
            }

            // Environment collision check
            if (enableEnvironmentCollision)
            {
                for (int i = 0; i <= numJoints; i++)
                {
                    Vector3 pos = new Vector3(jointTransforms[i].m03, jointTransforms[i].m13, jointTransforms[i].m23);
                    Collider[] hits = Physics.OverlapSphere(transform.TransformPoint(pos), 0.05f, collisionLayers);

                    if (hits.Length > 0)
                    {
                        return new CollisionEvent
                        {
                            Type = CollisionType.EnvironmentCollision,
                            Link1Index = i,
                            CollidedObject = hits[0].gameObject.name,
                            CollisionPoint = pos
                        };
                    }
                }
            }

            return null;
        }

        #endregion

        #region Workspace Analysis

        public WorkspaceInfo AnalyzeWorkspace(int samples = 1000)
        {
            var info = new WorkspaceInfo
            {
                MinBounds = Vector3.positiveInfinity,
                MaxBounds = Vector3.negativeInfinity,
                ReachablePoints = new List<Vector3>()
            };

            System.Random rand = new System.Random();

            for (int s = 0; s < samples; s++)
            {
                float[] randomAngles = new float[numJoints];
                for (int j = 0; j < numJoints; j++)
                {
                    randomAngles[j] = jointLimits[j].MinAngle +
                        (float)rand.NextDouble() * (jointLimits[j].MaxAngle - jointLimits[j].MinAngle);
                }

                var pose = CalculateForwardKinematics(randomAngles);
                var collision = CheckCollision(randomAngles);

                if (collision == null)
                {
                    info.ReachablePoints.Add(pose.Position);
                    info.MinBounds = Vector3.Min(info.MinBounds, pose.Position);
                    info.MaxBounds = Vector3.Max(info.MaxBounds, pose.Position);
                }
            }

            // Calculate approximate reach
            info.MaxReach = Vector3.Distance(Vector3.zero, info.MaxBounds);
            info.MinReach = info.MinBounds.magnitude;

            return info;
        }

        public bool IsReachable(Vector3 position)
        {
            float distance = position.magnitude;
            float maxReach = 0;

            for (int i = 0; i < numJoints; i++)
            {
                maxReach += Mathf.Abs(dhParams[i].A) + dhParams[i].D;
            }

            if (distance > maxReach) return false;

            // Try to solve IK
            var result = SolveInverseKinematics(new CartesianPose { Position = position, Rotation = Quaternion.identity });
            return result.Success;
        }

        #endregion

        #region Trajectory Planning

        public JointTrajectory PlanTrajectory(float[] targetAngles, float duration, TrajectoryProfile profile = TrajectoryProfile.Trapezoidal)
        {
            var trajectory = new JointTrajectory
            {
                JointNames = new string[numJoints],
                Points = new List<TrajectoryPoint>()
            };

            for (int i = 0; i < numJoints; i++)
            {
                trajectory.JointNames[i] = $"joint_{i + 1}";
            }

            float[] startAngles = (float[])currentConfig.JointAngles.Clone();
            int numPoints = Mathf.CeilToInt(duration * 100); // 100 Hz

            for (int p = 0; p <= numPoints; p++)
            {
                float t = (float)p / numPoints;
                float s = 0; // Normalized position
                float sd = 0; // Normalized velocity
                float sdd = 0; // Normalized acceleration

                switch (profile)
                {
                    case TrajectoryProfile.Linear:
                        s = t;
                        sd = 1f / duration;
                        sdd = 0;
                        break;

                    case TrajectoryProfile.Trapezoidal:
                        // Trapezoidal velocity profile
                        float accelTime = 0.25f;
                        if (t < accelTime)
                        {
                            s = 2 * t * t / (accelTime * (2 - accelTime));
                            sd = 4 * t / (accelTime * (2 - accelTime));
                        }
                        else if (t < 1 - accelTime)
                        {
                            s = (2 * t - accelTime) / (2 - accelTime);
                            sd = 2 / (2 - accelTime);
                        }
                        else
                        {
                            float tr = 1 - t;
                            s = 1 - 2 * tr * tr / (accelTime * (2 - accelTime));
                            sd = 4 * tr / (accelTime * (2 - accelTime));
                        }
                        break;

                    case TrajectoryProfile.SCurve:
                        // S-curve (quintic polynomial)
                        s = 10 * t * t * t - 15 * t * t * t * t + 6 * t * t * t * t * t;
                        sd = (30 * t * t - 60 * t * t * t + 30 * t * t * t * t) / duration;
                        sdd = (60 * t - 180 * t * t + 120 * t * t * t) / (duration * duration);
                        break;
                }

                var point = new TrajectoryPoint
                {
                    TimeFromStart = t * duration,
                    Positions = new float[numJoints],
                    Velocities = new float[numJoints],
                    Accelerations = new float[numJoints]
                };

                for (int j = 0; j < numJoints; j++)
                {
                    float delta = targetAngles[j] - startAngles[j];
                    point.Positions[j] = startAngles[j] + s * delta;
                    point.Velocities[j] = sd * delta;
                    point.Accelerations[j] = sdd * delta;
                }

                trajectory.Points.Add(point);
            }

            return trajectory;
        }

        public CartesianTrajectory PlanCartesianPath(CartesianPose[] waypoints, float maxVelocity = 0.1f)
        {
            var trajectory = new CartesianTrajectory
            {
                Waypoints = new List<CartesianWaypoint>()
            };

            float totalDistance = 0;
            for (int i = 1; i < waypoints.Length; i++)
            {
                totalDistance += Vector3.Distance(waypoints[i - 1].Position, waypoints[i].Position);
            }

            float time = 0;
            for (int i = 0; i < waypoints.Length; i++)
            {
                float segmentDistance = i > 0 ?
                    Vector3.Distance(waypoints[i - 1].Position, waypoints[i].Position) : 0;

                time += segmentDistance / maxVelocity;

                trajectory.Waypoints.Add(new CartesianWaypoint
                {
                    Pose = waypoints[i],
                    TimeFromStart = time
                });
            }

            return trajectory;
        }

        #endregion

        #region ROS2 Integration

        public void PublishJointStateToROS()
        {
            if (ROS2UnityBridge.Instance == null || !ROS2UnityBridge.Instance.IsConnected) return;

            var jointState = new JointStateMessage
            {
                Header = new HeaderMessage
                {
                    FrameId = "base_link",
                    Stamp = new ROSTime { Sec = (int)Time.time, Nanosec = 0 }
                },
                Name = new string[numJoints],
                Position = new double[numJoints],
                Velocity = new double[numJoints],
                Effort = new double[numJoints]
            };

            for (int i = 0; i < numJoints; i++)
            {
                jointState.Name[i] = $"joint_{i + 1}";
                jointState.Position[i] = currentConfig.JointAngles[i];
                jointState.Velocity[i] = currentConfig.JointVelocities[i];
                jointState.Effort[i] = currentConfig.JointTorques[i];
            }

            ROS2UnityBridge.Instance.PublishJointState(jointState);
        }

        #endregion
    }

    #region Data Classes

    public enum RobotType
    {
        SixAxisArm,
        SCARA,
        Delta,
        Cartesian,
        Custom
    }

    public enum IKSolver
    {
        DampedLeastSquares,
        JacobianTranspose,
        FABRIK,
        Analytical
    }

    public enum TrajectoryProfile
    {
        Linear,
        Trapezoidal,
        SCurve
    }

    [Serializable]
    public class DHParameters
    {
        public float A; // Link length
        public float D; // Link offset
        public float Alpha; // Link twist
        public float ThetaOffset; // Joint angle offset
    }

    [Serializable]
    public class JointLimits
    {
        public float MinAngle;
        public float MaxAngle;
        public float MaxVelocity;
        public float MaxAcceleration;
        public float MaxTorque;
    }

    [Serializable]
    public class JointConfiguration
    {
        public float[] JointAngles;
        public float[] JointVelocities;
        public float[] JointTorques;
    }

    [Serializable]
    public class CartesianPose
    {
        public Vector3 Position;
        public Quaternion Rotation;
        public Matrix4x4 TransformMatrix;
    }

    [Serializable]
    public class IKResult
    {
        public bool Success;
        public float[] JointAngles;
        public CartesianPose TargetPose;
        public CartesianPose FinalPose;
        public float PositionError;
        public float OrientationError;
        public int Iterations;
        public float SolveTime;
    }

    [Serializable]
    public class CollisionEvent
    {
        public CollisionType Type;
        public int Link1Index;
        public int Link2Index;
        public string CollidedObject;
        public Vector3 CollisionPoint;
        public float PenetrationDepth;
    }

    public enum CollisionType
    {
        SelfCollision,
        EnvironmentCollision,
        JointLimit
    }

    [Serializable]
    public class WorkspaceInfo
    {
        public Vector3 MinBounds;
        public Vector3 MaxBounds;
        public float MaxReach;
        public float MinReach;
        public List<Vector3> ReachablePoints;
    }

    [Serializable]
    public class JointTrajectory
    {
        public string[] JointNames;
        public List<TrajectoryPoint> Points;
    }

    [Serializable]
    public class TrajectoryPoint
    {
        public float TimeFromStart;
        public float[] Positions;
        public float[] Velocities;
        public float[] Accelerations;
    }

    [Serializable]
    public class CartesianTrajectory
    {
        public List<CartesianWaypoint> Waypoints;
    }

    [Serializable]
    public class CartesianWaypoint
    {
        public CartesianPose Pose;
        public float TimeFromStart;
    }

    #endregion
}
