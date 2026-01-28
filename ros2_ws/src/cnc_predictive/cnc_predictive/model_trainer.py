#!/usr/bin/env python3
"""
Model Trainer Action Server - Train ML models for predictive maintenance

Implements the TrainModel action for training various predictive models
using historical data from ROS bag files.
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
import json
import os
import time
from typing import Dict, List, Optional
import numpy as np

from cnc_interfaces.action import TrainModel


class ModelTrainerNode(Node):
    """Action server for ML model training"""

    def __init__(self):
        super().__init__('model_trainer')

        # Parameters
        self.declare_parameter('model_output_dir', '/tmp/cnc_models')
        self.declare_parameter('default_epochs', 100)
        self.declare_parameter('default_validation_split', 0.2)

        self.model_dir = self.get_parameter('model_output_dir').value
        self.default_epochs = self.get_parameter('default_epochs').value
        self.default_val_split = self.get_parameter('default_validation_split').value

        # Ensure output directory exists
        os.makedirs(self.model_dir, exist_ok=True)

        # Callback group for concurrent operations
        self.cb_group = ReentrantCallbackGroup()

        # Action server
        self.action_server = ActionServer(
            self,
            TrainModel,
            '/predictive/train_model',
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.cb_group
        )

        # Training state
        self.current_goal = None
        self.is_training = False

        self.get_logger().info('Model Trainer action server started')

    def goal_callback(self, goal_request):
        """Accept or reject training goal"""
        if self.is_training:
            self.get_logger().warn('Training already in progress, rejecting goal')
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle):
        """Handle cancellation request"""
        self.get_logger().info('Received cancel request')
        return CancelResponse.ACCEPT

    async def execute_callback(self, goal_handle):
        """Execute model training"""
        self.get_logger().info('Starting model training')
        self.is_training = True
        self.current_goal = goal_handle

        request = goal_handle.request
        result = TrainModel.Result()
        feedback = TrainModel.Feedback()

        try:
            # Parse hyperparameters
            hyperparams = {}
            if request.hyperparameters_json:
                hyperparams = json.loads(request.hyperparameters_json)

            epochs = request.epochs if request.epochs > 0 else self.default_epochs
            val_split = request.validation_split if request.validation_split > 0 else self.default_val_split

            # Load training data from bags
            self.get_logger().info(f'Loading data from {len(request.training_bag_paths)} bag files')

            feedback.status_message = "Loading training data..."
            feedback.progress = 0.1
            goal_handle.publish_feedback(feedback)

            # Simulate data loading (in production, use rosbag2_py)
            training_data = self.load_training_data(
                request.training_bag_paths,
                request.model_type,
                request.machine_id
            )

            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                result.success = False
                result.message = "Training cancelled"
                return result

            # Train model based on type
            feedback.status_message = "Training model..."
            feedback.progress = 0.2
            goal_handle.publish_feedback(feedback)

            start_time = time.time()
            model_result = await self.train_model(
                request.model_type,
                training_data,
                epochs,
                val_split,
                hyperparams,
                goal_handle,
                feedback
            )

            training_time = time.time() - start_time

            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                result.success = False
                result.message = "Training cancelled"
                return result

            # Save model
            model_id = f"{request.model_type}_{request.machine_id}_{int(time.time())}"
            model_path = os.path.join(self.model_dir, f"{model_id}.pkl")

            # In production, save actual model with joblib
            with open(model_path, 'w') as f:
                json.dump({'model_id': model_id, 'type': request.model_type}, f)

            # Prepare result
            result.success = True
            result.message = f"Model trained successfully"
            result.model_id = model_id
            result.model_path = model_path
            result.accuracy = model_result.get('accuracy', 0.85)
            result.precision = model_result.get('precision', 0.82)
            result.recall = model_result.get('recall', 0.88)
            result.f1_score = model_result.get('f1_score', 0.85)
            result.training_time = training_time
            result.metrics_json = json.dumps(model_result)

            goal_handle.succeed()
            self.get_logger().info(f'Training complete: {model_id}')

        except Exception as e:
            self.get_logger().error(f'Training failed: {e}')
            result.success = False
            result.message = str(e)
            goal_handle.abort()

        finally:
            self.is_training = False
            self.current_goal = None

        return result

    def load_training_data(self, bag_paths: List[str], model_type: str,
                           machine_id: str) -> Dict:
        """Load and preprocess training data from bag files"""
        # In production, use rosbag2_py to read bags
        # For now, generate synthetic data

        n_samples = 1000

        if model_type == 'tool_wear':
            # Features: spindle_load, vibration_rms, temperature, feed_rate
            X = np.random.randn(n_samples, 4)
            # Target: wear_rate
            y = 0.3 * X[:, 0] + 0.4 * X[:, 1] + 0.2 * X[:, 2] + np.random.randn(n_samples) * 0.1

        elif model_type == 'bearing':
            # Features: vibration_x, vibration_y, vibration_z, temperature
            X = np.random.randn(n_samples, 4)
            # Target: degradation_score
            y = np.sqrt(np.sum(X[:, :3]**2, axis=1)) + 0.1 * X[:, 3]

        elif model_type == 'anomaly':
            # Features: all sensor values
            X = np.random.randn(n_samples, 10)
            # Target: is_anomaly (binary)
            y = (np.sum(np.abs(X), axis=1) > 15).astype(float)

        else:  # thermal
            # Features: ambient_temp, spindle_speed, cutting_time
            X = np.random.randn(n_samples, 3)
            # Target: temperature_drift
            y = 0.5 * X[:, 0] + 0.3 * X[:, 1] * 0.01 + 0.2 * X[:, 2]

        return {'X': X, 'y': y, 'n_samples': n_samples}

    async def train_model(self, model_type: str, data: Dict, epochs: int,
                          val_split: float, hyperparams: Dict,
                          goal_handle, feedback) -> Dict:
        """Train the specified model type"""

        X, y = data['X'], data['y']
        n_samples = data['n_samples']

        # Split data
        split_idx = int(n_samples * (1 - val_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        # Simulate training epochs
        best_val_loss = float('inf')
        history = {'train_loss': [], 'val_loss': [], 'accuracy': []}

        for epoch in range(epochs):
            # Check for cancellation
            if goal_handle.is_cancel_requested:
                break

            # Simulate training step
            train_loss = 1.0 / (epoch + 1) + np.random.randn() * 0.1
            val_loss = 1.2 / (epoch + 1) + np.random.randn() * 0.15
            accuracy = min(0.95, 0.5 + epoch * 0.005 + np.random.randn() * 0.02)

            history['train_loss'].append(train_loss)
            history['val_loss'].append(val_loss)
            history['accuracy'].append(accuracy)

            if val_loss < best_val_loss:
                best_val_loss = val_loss

            # Publish feedback
            feedback.current_epoch = epoch + 1
            feedback.total_epochs = epochs
            feedback.progress = 0.2 + 0.7 * (epoch + 1) / epochs
            feedback.current_loss = float(train_loss)
            feedback.current_accuracy = float(accuracy)
            feedback.validation_loss = float(val_loss)
            feedback.validation_accuracy = float(accuracy - 0.02)
            feedback.status_message = f"Epoch {epoch + 1}/{epochs}, loss: {train_loss:.4f}"

            goal_handle.publish_feedback(feedback)

            # Small delay to simulate computation
            await self.sleep_async(0.05)

        # Final metrics
        final_accuracy = history['accuracy'][-1] if history['accuracy'] else 0.8

        return {
            'accuracy': final_accuracy,
            'precision': final_accuracy - 0.03,
            'recall': final_accuracy + 0.03,
            'f1_score': final_accuracy,
            'best_val_loss': best_val_loss,
            'epochs_trained': len(history['train_loss']),
            'history': history
        }

    async def sleep_async(self, seconds: float):
        """Async sleep helper"""
        import asyncio
        await asyncio.sleep(seconds)


def main(args=None):
    rclpy.init(args=args)
    node = ModelTrainerNode()

    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
