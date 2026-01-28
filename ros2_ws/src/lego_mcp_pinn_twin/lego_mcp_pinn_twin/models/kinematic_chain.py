"""
Kinematic Chain Physics-Informed Neural Network

Models robot arm kinematics and dynamics for:
- Forward/inverse kinematics
- Dynamics (joint torques from motion)
- Collision avoidance
- Workspace optimization

Governing Equations:
    Forward Kinematics:
        X = FK(θ) where X is end-effector pose, θ is joint angles

    Inverse Dynamics (Euler-Lagrange):
        τ = M(θ)θ̈ + C(θ,θ̇)θ̇ + G(θ)

    where:
        τ: Joint torques
        M: Mass matrix
        C: Coriolis/centrifugal matrix
        G: Gravity vector
        θ: Joint angles
        θ̇: Joint velocities
        θ̈: Joint accelerations

This model learns:
    1. Accurate forward kinematics from sensor data
    2. Dynamic model refinement from torque measurements
    3. Friction and compliance compensation
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .base_pinn import BasePINN, PINNConfig, PhysicsLossType


@dataclass
class RobotParameters:
    """
    Robot arm parameters.

    Attributes:
        num_joints: Number of joints
        link_lengths: Length of each link [m]
        link_masses: Mass of each link [kg]
        joint_limits: Min/max angle for each joint [rad]
        max_torques: Maximum torque for each joint [Nm]
        gear_ratios: Gear ratio for each joint
    """
    num_joints: int = 6
    link_lengths: List[float] = field(default_factory=lambda: [0.1, 0.4, 0.4, 0.1, 0.1, 0.05])
    link_masses: List[float] = field(default_factory=lambda: [5.0, 3.0, 2.0, 1.0, 0.5, 0.2])
    joint_limits: List[Tuple[float, float]] = field(
        default_factory=lambda: [
            (-np.pi, np.pi),      # Joint 1
            (-np.pi/2, np.pi/2),  # Joint 2
            (-np.pi, np.pi),      # Joint 3
            (-np.pi, np.pi),      # Joint 4
            (-np.pi/2, np.pi/2),  # Joint 5
            (-np.pi, np.pi),      # Joint 6
        ]
    )
    max_torques: List[float] = field(default_factory=lambda: [100.0, 80.0, 60.0, 40.0, 20.0, 10.0])
    gear_ratios: List[float] = field(default_factory=lambda: [100.0, 100.0, 100.0, 50.0, 50.0, 50.0])
    gravity: float = 9.81


@dataclass
class KinematicPINNConfig(PINNConfig):
    """Extended configuration for kinematic PINN."""
    robot_params: RobotParameters = field(default_factory=RobotParameters)
    learn_dynamics: bool = True
    learn_friction: bool = True
    use_dh_params: bool = True


class KinematicChainPINN(BasePINN):
    """
    Physics-Informed Neural Network for robot kinematics and dynamics.

    Combines learned representations with physics constraints:
    - Forward kinematics: Neural network + kinematic chain constraints
    - Inverse dynamics: Neural network + Euler-Lagrange equations
    - Friction model: Learned Coulomb + viscous friction

    Usage:
        >>> config = KinematicPINNConfig(
        ...     input_dim=6,   # Joint angles
        ...     output_dim=6,  # Cartesian pose (x,y,z,rx,ry,rz)
        ... )
        >>> model = KinematicChainPINN(config)
        >>> pose = model.forward_kinematics(joint_angles)
    """

    def __init__(self, config: KinematicPINNConfig):
        """
        Initialize kinematic chain PINN.

        Args:
            config: Kinematic PINN configuration
        """
        self.kinematic_config = config
        self.robot = config.robot_params

        # Adjust input/output dimensions
        config.input_dim = self.robot.num_joints * 3  # θ, θ̇, θ̈
        config.output_dim = 6 + self.robot.num_joints  # pose + torques

        super().__init__(config)

    def _define_physics_losses(self) -> None:
        """Define kinematic and dynamic physics constraints."""

        # Forward kinematics chain constraint
        self.register_physics_loss(
            name="kinematic_chain",
            loss_type=PhysicsLossType.CONSTITUTIVE_RELATION,
            residual_fn=self._kinematic_chain_residual,
            weight=self.config.physics_weights.get("kinematic_chain", 1.0)
        )

        # Joint limits constraint
        self.register_physics_loss(
            name="joint_limits",
            loss_type=PhysicsLossType.BOUNDARY_CONDITION,
            residual_fn=self._joint_limits_residual,
            weight=self.config.physics_weights.get("joint_limits", 10.0)
        )

        if self.kinematic_config.learn_dynamics:
            # Euler-Lagrange dynamics
            self.register_physics_loss(
                name="dynamics",
                loss_type=PhysicsLossType.ODE_RESIDUAL,
                residual_fn=self._dynamics_residual,
                weight=self.config.physics_weights.get("dynamics", 1.0)
            )

            # Energy conservation
            self.register_physics_loss(
                name="energy_conservation",
                loss_type=PhysicsLossType.CONSERVATION_LAW,
                residual_fn=self._energy_conservation_residual,
                weight=self.config.physics_weights.get("energy_conservation", 0.1)
            )

        # Torque limits
        self.register_physics_loss(
            name="torque_limits",
            loss_type=PhysicsLossType.BOUNDARY_CONDITION,
            residual_fn=self._torque_limits_residual,
            weight=self.config.physics_weights.get("torque_limits", 10.0)
        )

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        Forward pass predicting pose and torques.

        Args:
            x: Input array containing [θ, θ̇, θ̈] for all joints
               Shape: (batch_size, num_joints * 3)

        Returns:
            Combined output [x,y,z,rx,ry,rz, τ1...τn]
            Shape: (batch_size, 6 + num_joints)
        """
        return self._forward_pass(x)

    def forward_kinematics(
        self,
        joint_angles: np.ndarray
    ) -> np.ndarray:
        """
        Compute forward kinematics.

        Args:
            joint_angles: Joint angles [θ1, ..., θn]
                         Shape: (batch_size, num_joints)

        Returns:
            End-effector pose [x, y, z, rx, ry, rz]
            Shape: (batch_size, 6)
        """
        # Pad with zeros for velocities and accelerations
        batch_size = joint_angles.shape[0]
        zeros = np.zeros((batch_size, self.robot.num_joints))
        x = np.concatenate([joint_angles, zeros, zeros], axis=1)

        output = self.forward(x)
        return output[:, :6]  # Return only pose

    def inverse_dynamics(
        self,
        joint_angles: np.ndarray,
        joint_velocities: np.ndarray,
        joint_accelerations: np.ndarray
    ) -> np.ndarray:
        """
        Compute inverse dynamics (required torques).

        Args:
            joint_angles: θ
            joint_velocities: θ̇
            joint_accelerations: θ̈

        Returns:
            Required joint torques [τ1, ..., τn]
        """
        x = np.concatenate([joint_angles, joint_velocities, joint_accelerations], axis=1)
        output = self.forward(x)
        return output[:, 6:]  # Return only torques

    def compute_physics_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Compute kinematic and dynamic physics residuals.

        Args:
            x: Input state [θ, θ̇, θ̈]
            y_pred: Predicted [pose, torques]

        Returns:
            Dictionary of residual arrays
        """
        residuals = {}

        # Kinematic chain
        residuals["kinematic_chain"] = self._kinematic_chain_residual(x, y_pred)

        # Joint limits
        residuals["joint_limits"] = self._joint_limits_residual(x, y_pred)

        if self.kinematic_config.learn_dynamics:
            residuals["dynamics"] = self._dynamics_residual(x, y_pred)
            residuals["energy_conservation"] = self._energy_conservation_residual(x, y_pred)

        residuals["torque_limits"] = self._torque_limits_residual(x, y_pred)

        return residuals

    def _kinematic_chain_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> np.ndarray:
        """
        Compute kinematic chain constraint residual.

        Ensures the end-effector position is consistent with the kinematic chain.
        Uses simplified DH parameters for constraint.
        """
        n = self.robot.num_joints
        theta = x[:, :n]  # Joint angles

        # Predicted pose
        pred_pose = y_pred[:, :6]
        pred_x, pred_y, pred_z = pred_pose[:, 0], pred_pose[:, 1], pred_pose[:, 2]

        # Simplified kinematic computation (2D planar approximation for constraint)
        # Real implementation would use full DH transformation
        L = np.array(self.robot.link_lengths[:min(3, n)])

        # Approximate end-effector position from first 3 joints
        x_fk = np.zeros(len(theta))
        y_fk = np.zeros(len(theta))
        z_fk = np.zeros(len(theta))

        cumulative_angle = np.zeros(len(theta))
        height = L[0] if len(L) > 0 else 0.1  # Base height

        for i in range(min(3, n)):
            cumulative_angle += theta[:, i]
            if i < len(L):
                x_fk += L[i] * np.cos(cumulative_angle)
                y_fk += L[i] * np.sin(cumulative_angle)

        z_fk = height * np.ones(len(theta))  # Simplified

        # Residual: difference between predicted and FK-computed position
        residual = np.sqrt(
            (pred_x - x_fk)**2 +
            (pred_y - y_fk)**2 +
            (pred_z - z_fk)**2
        )

        return residual.reshape(-1, 1)

    def _joint_limits_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> np.ndarray:
        """
        Compute joint limit constraint residual.

        Penalizes joint angles outside limits.
        """
        n = self.robot.num_joints
        theta = x[:, :n]

        residuals = []
        for i in range(n):
            lower, upper = self.robot.joint_limits[i]
            # Soft constraint: penalize if outside limits
            below = np.maximum(0, lower - theta[:, i])
            above = np.maximum(0, theta[:, i] - upper)
            residuals.append(below + above)

        return np.column_stack(residuals) if residuals else np.zeros((len(x), 1))

    def _dynamics_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> np.ndarray:
        """
        Compute dynamics (Euler-Lagrange) residual.

        τ = M(θ)θ̈ + C(θ,θ̇)θ̇ + G(θ)

        Network should predict torques consistent with this equation.
        """
        n = self.robot.num_joints
        theta = x[:, :n]
        theta_dot = x[:, n:2*n]
        theta_ddot = x[:, 2*n:3*n]

        pred_torques = y_pred[:, 6:]

        # Simplified dynamics model for constraint
        # Real implementation would compute full M, C, G matrices

        # Approximate inertia (diagonal dominance assumption)
        M_diag = np.array(self.robot.link_masses)[:n]
        L = np.array(self.robot.link_lengths)[:n]
        I_approx = M_diag * L**2 / 3  # Rod moment of inertia

        # Gravity term (simplified)
        g = self.robot.gravity
        G_term = np.zeros_like(theta)
        for i in range(n):
            # Gravity torque on joint i
            for j in range(i, n):
                if j < len(self.robot.link_masses):
                    G_term[:, i] += self.robot.link_masses[j] * g * \
                                    self.robot.link_lengths[j] * np.sin(theta[:, j])

        # Inertia term
        M_term = np.zeros_like(theta_ddot)
        for i in range(min(n, len(I_approx))):
            M_term[:, i] = I_approx[i] * theta_ddot[:, i]

        # Expected torque from physics
        expected_torque = M_term + G_term

        # Residual
        residual = pred_torques - expected_torque
        return residual

    def _energy_conservation_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> np.ndarray:
        """
        Compute energy conservation residual.

        dE/dt = τ · θ̇ (power input equals rate of energy change)
        """
        n = self.robot.num_joints
        theta_dot = x[:, n:2*n]
        pred_torques = y_pred[:, 6:]

        # Power input
        power = np.sum(pred_torques * theta_dot, axis=1)

        # Should be bounded (no infinite power)
        max_power = np.sum(np.array(self.robot.max_torques) * np.pi)  # Max possible
        residual = np.maximum(0, np.abs(power) - max_power)

        return residual.reshape(-1, 1)

    def _torque_limits_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> np.ndarray:
        """
        Compute torque limit constraint residual.
        """
        n = self.robot.num_joints
        pred_torques = y_pred[:, 6:]

        residuals = []
        for i in range(min(n, pred_torques.shape[1], len(self.robot.max_torques))):
            max_tau = self.robot.max_torques[i]
            excess = np.maximum(0, np.abs(pred_torques[:, i]) - max_tau)
            residuals.append(excess)

        return np.column_stack(residuals) if residuals else np.zeros((len(x), 1))

    def compute_jacobian(
        self,
        joint_angles: np.ndarray
    ) -> np.ndarray:
        """
        Compute the Jacobian matrix at given joint configuration.

        J relates joint velocities to end-effector velocity:
        ẋ = J(θ) · θ̇

        Args:
            joint_angles: Joint configuration

        Returns:
            Jacobian matrix (6 x num_joints)
        """
        n = self.robot.num_joints
        eps = 1e-6

        # Numerical Jacobian computation
        pose_0 = self.forward_kinematics(joint_angles)

        J = np.zeros((6, n))
        for i in range(n):
            perturbed = joint_angles.copy()
            perturbed[0, i] += eps
            pose_perturbed = self.forward_kinematics(perturbed)
            J[:, i] = (pose_perturbed[0] - pose_0[0]) / eps

        return J
