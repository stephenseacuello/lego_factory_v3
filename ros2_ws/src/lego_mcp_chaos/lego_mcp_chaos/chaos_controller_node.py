#!/usr/bin/env python3
"""
Chaos Controller Node for LEGO MCP

ROS2 node providing chaos testing services:
- Fault injection control
- Scenario execution
- Resilience validation
- Recovery monitoring

Industry 4.0/5.0 Architecture - ISA-95 Level 2
Chaos Engineering for Manufacturing Systems
"""

import rclpy
from rclpy.node import Node
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.lifecycle import LifecycleState

from std_msgs.msg import String
from std_srvs.srv import Trigger, SetBool

import json
import yaml
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .fault_injector import FaultInjector, FaultType, FaultInjection
from .chaos_scenarios import (
    ChaosScenario,
    ChaosScenarioRunner,
    ScenarioOutcome,
    create_equipment_failure_scenario,
    create_safety_estop_scenario,
    create_cascade_failure_scenario,
    create_network_partition_scenario,
)
from .resilience_validator import (
    ResilienceValidator,
    ValidationLevel,
    ResilienceReport,
)


class ChaosControllerNode(LifecycleNode):
    """
    Chaos Controller Lifecycle Node.

    Provides controlled chaos testing capabilities for resilience validation.
    Implements ROS2 lifecycle for safe startup/shutdown during testing.

    SAFETY NOTE: This node should NEVER be deployed in production without
    proper safeguards. Chaos testing should only be performed in isolated
    test environments or with explicit safety zone exclusions.
    """

    def __init__(self, node_name: str = 'chaos_controller'):
        super().__init__(node_name)

        # Declare parameters
        self.declare_parameter('config_path', '')
        self.declare_parameter('enable_safety_zone_protection', True)
        self.declare_parameter('max_concurrent_faults', 2)
        self.declare_parameter('auto_cleanup_on_error', True)
        self.declare_parameter('status_rate', 1.0)

        # Components (initialized in on_configure)
        self._fault_injector: Optional[FaultInjector] = None
        self._scenario_runner: Optional[ChaosScenarioRunner] = None
        self._resilience_validator: Optional[ResilienceValidator] = None

        # Scenario storage
        self._loaded_scenarios: Dict[str, ChaosScenario] = {}
        self._scenario_history: List[Dict] = []

        # Publishers/Services (created in on_configure)
        self._status_pub = None
        self._result_pub = None
        self._health_srv = None
        self._run_scenario_srv = None
        self._stop_scenario_srv = None
        self._inject_fault_srv = None
        self._stop_all_srv = None
        self._validate_resilience_srv = None

        # State
        self._timer = None
        self._safety_protected = True

        self.get_logger().info('ChaosControllerNode created (unconfigured)')

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Configure the chaos controller components."""
        self.get_logger().info('Configuring ChaosControllerNode...')

        try:
            # Get parameters
            config_path = self.get_parameter('config_path').value
            self._safety_protected = self.get_parameter('enable_safety_zone_protection').value

            # Initialize Fault Injector
            self._fault_injector = FaultInjector()
            self.get_logger().info('Fault Injector initialized')

            # Initialize Scenario Runner
            self._scenario_runner = ChaosScenarioRunner(self._fault_injector)
            self.get_logger().info('Scenario Runner initialized')

            # Initialize Resilience Validator
            self._resilience_validator = ResilienceValidator()
            self.get_logger().info('Resilience Validator initialized')

            # Load predefined scenarios
            self._load_predefined_scenarios()

            # Load scenarios from config if provided
            if config_path:
                self._load_scenarios_from_config(config_path)

            # Create publishers
            self._status_pub = self.create_publisher(
                String,
                '/lego_mcp/chaos/status',
                10
            )
            self._result_pub = self.create_publisher(
                String,
                '/lego_mcp/chaos/results',
                10
            )

            # Create services
            self._health_srv = self.create_service(
                Trigger,
                '/lego_mcp/chaos/health',
                self._health_callback
            )
            self._run_scenario_srv = self.create_service(
                Trigger,
                '/lego_mcp/chaos/run_scenario',
                self._run_scenario_callback
            )
            self._stop_scenario_srv = self.create_service(
                Trigger,
                '/lego_mcp/chaos/stop_scenario',
                self._stop_scenario_callback
            )
            self._stop_all_srv = self.create_service(
                Trigger,
                '/lego_mcp/chaos/stop_all',
                self._stop_all_callback
            )
            self._validate_resilience_srv = self.create_service(
                Trigger,
                '/lego_mcp/chaos/validate_resilience',
                self._validate_resilience_callback
            )

            self.get_logger().info('ChaosControllerNode configured successfully')
            self.get_logger().warn(
                'CHAOS CONTROLLER CONFIGURED - Use only in test environments!'
            )
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f'Configuration failed: {e}')
            return TransitionCallbackReturn.FAILURE

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Activate the chaos controller."""
        self.get_logger().info('Activating ChaosControllerNode...')

        try:
            # Start status publishing timer
            status_rate = self.get_parameter('status_rate').value
            self._timer = self.create_timer(
                1.0 / status_rate,
                self._publish_status
            )

            self.get_logger().info('ChaosControllerNode activated')
            self.get_logger().warn(
                'CHAOS CONTROLLER ACTIVE - Fault injection enabled!'
            )
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f'Activation failed: {e}')
            return TransitionCallbackReturn.FAILURE

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Deactivate the chaos controller."""
        self.get_logger().info('Deactivating ChaosControllerNode...')

        try:
            # Stop all active injections
            if self._fault_injector:
                self._fault_injector.stop_all_injections()
                self.get_logger().info('Stopped all active fault injections')

            # Abort any running scenario
            if self._scenario_runner and self._scenario_runner.is_running():
                self._scenario_runner.abort_scenario()
                self.get_logger().info('Aborted running scenario')

            # Cancel timer
            if self._timer:
                self._timer.cancel()
                self._timer = None

            self.get_logger().info('ChaosControllerNode deactivated')
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f'Deactivation failed: {e}')
            return TransitionCallbackReturn.FAILURE

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Clean up resources."""
        self.get_logger().info('Cleaning up ChaosControllerNode...')

        # Ensure all injections stopped
        if self._fault_injector:
            self._fault_injector.stop_all_injections()

        self._fault_injector = None
        self._scenario_runner = None
        self._resilience_validator = None
        self._loaded_scenarios.clear()

        self.get_logger().info('ChaosControllerNode cleaned up')
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Shutdown the node."""
        self.get_logger().info('Shutting down ChaosControllerNode...')

        # Emergency cleanup
        if self._fault_injector:
            self._fault_injector.stop_all_injections()

        return TransitionCallbackReturn.SUCCESS

    def on_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Handle error state - ensure safe cleanup."""
        self.get_logger().error('ChaosControllerNode entered error state')

        # Emergency cleanup on error
        auto_cleanup = self.get_parameter('auto_cleanup_on_error').value
        if auto_cleanup and self._fault_injector:
            self._fault_injector.stop_all_injections()
            self.get_logger().info('Emergency cleanup: stopped all injections')

        return TransitionCallbackReturn.SUCCESS

    def _load_predefined_scenarios(self):
        """Load predefined chaos scenarios."""
        scenarios = [
            create_equipment_failure_scenario('grbl_node'),
            create_equipment_failure_scenario('formlabs_node'),
            create_safety_estop_scenario(),
            create_cascade_failure_scenario(),
            create_network_partition_scenario(),
        ]

        for scenario in scenarios:
            self._loaded_scenarios[scenario.scenario_id] = scenario
            self.get_logger().info(f'Loaded scenario: {scenario.name}')

    def _load_scenarios_from_config(self, config_path: str):
        """Load scenarios from YAML config file."""
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                self.get_logger().warn(f'Config file not found: {config_path}')
                return

            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)

            scenarios_config = config.get('scenarios', {})
            for scenario_id, scenario_data in scenarios_config.items():
                # Parse scenario from config
                # (simplified - full implementation would parse all fields)
                self.get_logger().info(f'Loaded config scenario: {scenario_id}')

        except Exception as e:
            self.get_logger().error(f'Failed to load config: {e}')

    def _publish_status(self):
        """Publish chaos controller status."""
        stats = self._fault_injector.get_statistics() if self._fault_injector else {}

        status = {
            'timestamp': datetime.now().isoformat(),
            'state': self.get_current_state().label,
            'safety_protected': self._safety_protected,
            'active_injections': stats.get('active_injections', 0),
            'total_injections': stats.get('total_injections', 0),
            'scenario_running': (
                self._scenario_runner.is_running()
                if self._scenario_runner else False
            ),
            'loaded_scenarios': list(self._loaded_scenarios.keys()),
            'scenarios_executed': len(self._scenario_history),
        }

        msg = String()
        msg.data = json.dumps(status)
        self._status_pub.publish(msg)

    def _health_callback(self, request, response):
        """Health check service callback."""
        response.success = True
        response.message = (
            f"Chaos Controller: "
            f"active_injections={len(self._fault_injector.get_active_injections()) if self._fault_injector else 0}, "
            f"scenarios_loaded={len(self._loaded_scenarios)}"
        )
        return response

    def _run_scenario_callback(self, request, response):
        """Run a chaos scenario."""
        # For a full implementation, this would accept scenario ID as parameter
        # Using trigger service for simplicity - real implementation would use custom service

        if not self._scenario_runner:
            response.success = False
            response.message = 'Scenario runner not configured'
            return response

        if self._scenario_runner.is_running():
            response.success = False
            response.message = 'A scenario is already running'
            return response

        # Run first available scenario as demo
        if self._loaded_scenarios:
            scenario_id = list(self._loaded_scenarios.keys())[0]
            scenario = self._loaded_scenarios[scenario_id]

            self.get_logger().info(f'Running scenario: {scenario.name}')

            # Run in background thread
            def run_async():
                result = self._scenario_runner.run_scenario(scenario)
                self._scenario_history.append({
                    'scenario_id': result.scenario_id,
                    'outcome': result.outcome.value,
                    'timestamp': datetime.now().isoformat(),
                })

                # Publish result
                result_msg = String()
                result_msg.data = json.dumps({
                    'scenario_id': result.scenario_id,
                    'outcome': result.outcome.value,
                    'steps_completed': result.steps_completed,
                    'steps_failed': result.steps_failed,
                })
                self._result_pub.publish(result_msg)

            thread = threading.Thread(target=run_async, daemon=True)
            thread.start()

            response.success = True
            response.message = f'Started scenario: {scenario.name}'
        else:
            response.success = False
            response.message = 'No scenarios loaded'

        return response

    def _stop_scenario_callback(self, request, response):
        """Stop running scenario."""
        if self._scenario_runner and self._scenario_runner.is_running():
            self._scenario_runner.abort_scenario()
            response.success = True
            response.message = 'Scenario aborted'
        else:
            response.success = False
            response.message = 'No scenario running'
        return response

    def _stop_all_callback(self, request, response):
        """Stop all fault injections."""
        if self._fault_injector:
            self._fault_injector.stop_all_injections()

        if self._scenario_runner and self._scenario_runner.is_running():
            self._scenario_runner.abort_scenario()

        response.success = True
        response.message = 'All injections and scenarios stopped'
        return response

    def _validate_resilience_callback(self, request, response):
        """Run resilience validation."""
        if not self._resilience_validator:
            response.success = False
            response.message = 'Resilience validator not configured'
            return response

        report = self._resilience_validator.validate_resilience()

        response.success = report.overall_passed
        response.message = (
            f"Resilience validation: "
            f"passed={report.overall_passed}, "
            f"availability={report.availability_percentage:.1f}%, "
            f"recovery_time={report.recovery_time_seconds:.2f}s"
        )

        # Publish detailed result
        result_msg = String()
        result_msg.data = json.dumps({
            'type': 'resilience_validation',
            'passed': report.overall_passed,
            'availability_pct': report.availability_percentage,
            'recovery_time_sec': report.recovery_time_seconds,
            'recommendations': report.recommendations,
        })
        self._result_pub.publish(result_msg)

        return response


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = ChaosControllerNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Ensure cleanup on exit
        if node._fault_injector:
            node._fault_injector.stop_all_injections()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
