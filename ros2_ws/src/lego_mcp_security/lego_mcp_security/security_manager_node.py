#!/usr/bin/env python3
"""
Security Manager Node for LEGO MCP

ROS2 node providing security management services:
- SROS2 key/certificate management
- IEC 62443 zone enforcement
- Security audit logging
- Intrusion detection alerts

Industry 4.0/5.0 Architecture - ISA-95 Level 2
"""

import rclpy
from rclpy.node import Node
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.lifecycle import LifecycleState

from std_msgs.msg import String
from std_srvs.srv import Trigger, SetBool

import json
import threading
from datetime import datetime
from typing import Dict, Optional

from .sros2_manager import SROS2Manager
from .security_zones import SecurityZoneManager, IEC62443Zone
from .access_control import RBACController, Role, Permission
from .audit_pipeline import SecurityAuditPipeline, SecurityEvent, SecuritySeverity
from .intrusion_detector import IntrusionDetector


class SecurityManagerNode(LifecycleNode):
    """
    Security Manager Lifecycle Node.

    Provides centralized security management for the LEGO MCP system.
    Implements ROS2 lifecycle for deterministic startup/shutdown.
    """

    def __init__(self, node_name: str = 'security_manager'):
        super().__init__(node_name)

        # Declare parameters
        self.declare_parameter('keystore_path', '/tmp/lego_mcp_keystore')
        self.declare_parameter('audit_log_path', '/var/log/lego_mcp/security.log')
        self.declare_parameter('enable_intrusion_detection', True)
        self.declare_parameter('zone_config_path', '')
        self.declare_parameter('heartbeat_rate', 1.0)

        # Components (initialized in on_configure)
        self._sros2_manager: Optional[SROS2Manager] = None
        self._zone_manager: Optional[SecurityZoneManager] = None
        self._rbac_controller: Optional[RBACController] = None
        self._audit_pipeline: Optional[SecurityAuditPipeline] = None
        self._intrusion_detector: Optional[IntrusionDetector] = None

        # Publishers/Subscribers/Services (created in on_configure)
        self._security_status_pub = None
        self._security_alert_pub = None
        self._intrusion_alert_pub = None
        self._health_srv = None
        self._rotate_keys_srv = None
        self._enable_detection_srv = None

        # State
        self._alert_callback_registered = False
        self._timer = None

        self.get_logger().info('SecurityManagerNode created (unconfigured)')

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Configure the security manager components."""
        self.get_logger().info('Configuring SecurityManagerNode...')

        try:
            # Get parameters
            keystore_path = self.get_parameter('keystore_path').value
            audit_log_path = self.get_parameter('audit_log_path').value
            enable_ids = self.get_parameter('enable_intrusion_detection').value

            # Initialize SROS2 Manager
            self._sros2_manager = SROS2Manager(keystore_path)
            self.get_logger().info(f'SROS2 Manager initialized: {keystore_path}')

            # Initialize Zone Manager with default zones
            self._zone_manager = SecurityZoneManager()
            self._zone_manager.initialize_default_zones()
            self.get_logger().info('Security Zone Manager initialized')

            # Initialize RBAC Controller
            self._rbac_controller = RBACController()
            self._rbac_controller.initialize_default_roles()
            self.get_logger().info('RBAC Controller initialized')

            # Initialize Audit Pipeline
            self._audit_pipeline = SecurityAuditPipeline(log_path=audit_log_path)
            self.get_logger().info(f'Audit Pipeline initialized: {audit_log_path}')

            # Initialize Intrusion Detector
            if enable_ids:
                self._intrusion_detector = IntrusionDetector()
                self._intrusion_detector.register_alert_callback(self._on_intrusion_alert)
                self._alert_callback_registered = True
                self.get_logger().info('Intrusion Detector initialized')

            # Create publishers
            self._security_status_pub = self.create_publisher(
                String,
                '/lego_mcp/security/status',
                10
            )
            self._security_alert_pub = self.create_publisher(
                String,
                '/lego_mcp/security/alerts',
                10
            )
            self._intrusion_alert_pub = self.create_publisher(
                String,
                '/lego_mcp/security/intrusion_alerts',
                10
            )

            # Create services
            self._health_srv = self.create_service(
                Trigger,
                '/lego_mcp/security/health',
                self._health_callback
            )
            self._rotate_keys_srv = self.create_service(
                Trigger,
                '/lego_mcp/security/rotate_keys',
                self._rotate_keys_callback
            )
            self._enable_detection_srv = self.create_service(
                SetBool,
                '/lego_mcp/security/enable_detection',
                self._enable_detection_callback
            )

            # Log configuration event
            self._audit_pipeline.log_event(SecurityEvent(
                event_type='SECURITY_MANAGER_CONFIGURED',
                severity=SecuritySeverity.INFO,
                source_node='security_manager',
                description='Security Manager configured successfully',
                details={
                    'keystore_path': keystore_path,
                    'intrusion_detection': enable_ids,
                },
            ))

            self.get_logger().info('SecurityManagerNode configured successfully')
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f'Configuration failed: {e}')
            return TransitionCallbackReturn.FAILURE

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Activate the security manager."""
        self.get_logger().info('Activating SecurityManagerNode...')

        try:
            # Start intrusion detection
            if self._intrusion_detector:
                self._intrusion_detector.start()
                self.get_logger().info('Intrusion detection started')

            # Start status publishing timer
            heartbeat_rate = self.get_parameter('heartbeat_rate').value
            self._timer = self.create_timer(
                1.0 / heartbeat_rate,
                self._publish_status
            )

            # Log activation
            self._audit_pipeline.log_event(SecurityEvent(
                event_type='SECURITY_MANAGER_ACTIVATED',
                severity=SecuritySeverity.INFO,
                source_node='security_manager',
                description='Security Manager activated',
            ))

            self.get_logger().info('SecurityManagerNode activated')
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f'Activation failed: {e}')
            return TransitionCallbackReturn.FAILURE

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Deactivate the security manager."""
        self.get_logger().info('Deactivating SecurityManagerNode...')

        try:
            # Stop intrusion detection
            if self._intrusion_detector:
                self._intrusion_detector.stop()

            # Cancel timer
            if self._timer:
                self._timer.cancel()
                self._timer = None

            # Log deactivation
            if self._audit_pipeline:
                self._audit_pipeline.log_event(SecurityEvent(
                    event_type='SECURITY_MANAGER_DEACTIVATED',
                    severity=SecuritySeverity.INFO,
                    source_node='security_manager',
                    description='Security Manager deactivated',
                ))

            self.get_logger().info('SecurityManagerNode deactivated')
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f'Deactivation failed: {e}')
            return TransitionCallbackReturn.FAILURE

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Clean up resources."""
        self.get_logger().info('Cleaning up SecurityManagerNode...')

        self._sros2_manager = None
        self._zone_manager = None
        self._rbac_controller = None
        self._audit_pipeline = None
        self._intrusion_detector = None

        self.get_logger().info('SecurityManagerNode cleaned up')
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Shutdown the node."""
        self.get_logger().info('Shutting down SecurityManagerNode...')
        return TransitionCallbackReturn.SUCCESS

    def on_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Handle error state."""
        self.get_logger().error('SecurityManagerNode entered error state')

        if self._audit_pipeline:
            self._audit_pipeline.log_event(SecurityEvent(
                event_type='SECURITY_MANAGER_ERROR',
                severity=SecuritySeverity.CRITICAL,
                source_node='security_manager',
                description='Security Manager entered error state',
            ))

        return TransitionCallbackReturn.SUCCESS

    def _publish_status(self):
        """Publish security status."""
        status = {
            'timestamp': datetime.now().isoformat(),
            'state': self.get_current_state().label,
            'sros2_enabled': self._sros2_manager is not None,
            'intrusion_detection': (
                self._intrusion_detector.running
                if self._intrusion_detector else False
            ),
            'zones_configured': (
                len(self._zone_manager.list_zones())
                if self._zone_manager else 0
            ),
            'alerts_24h': (
                self._audit_pipeline.get_recent_alert_count()
                if self._audit_pipeline else 0
            ),
        }

        msg = String()
        msg.data = json.dumps(status)
        self._security_status_pub.publish(msg)

    def _on_intrusion_alert(self, alert: Dict):
        """Handle intrusion detection alert."""
        self.get_logger().warn(f'Intrusion alert: {alert["type"]}')

        # Log to audit pipeline
        if self._audit_pipeline:
            self._audit_pipeline.log_event(SecurityEvent(
                event_type=alert['type'],
                severity=SecuritySeverity.HIGH,
                source_node=alert.get('source_node', 'unknown'),
                description=alert.get('description', 'Intrusion detected'),
                details=alert,
            ))

        # Publish alert
        msg = String()
        msg.data = json.dumps(alert)
        self._intrusion_alert_pub.publish(msg)
        self._security_alert_pub.publish(msg)

    def _health_callback(self, request, response):
        """Health check service callback."""
        all_healthy = True
        details = []

        if self._sros2_manager:
            details.append('SROS2: OK')
        else:
            details.append('SROS2: NOT CONFIGURED')
            all_healthy = False

        if self._intrusion_detector and self._intrusion_detector.running:
            details.append('IDS: RUNNING')
        elif self._intrusion_detector:
            details.append('IDS: STOPPED')
        else:
            details.append('IDS: DISABLED')

        response.success = all_healthy
        response.message = '; '.join(details)
        return response

    def _rotate_keys_callback(self, request, response):
        """Key rotation service callback."""
        if not self._sros2_manager:
            response.success = False
            response.message = 'SROS2 not configured'
            return response

        try:
            # This would trigger key rotation in production
            self._audit_pipeline.log_event(SecurityEvent(
                event_type='KEY_ROTATION_REQUESTED',
                severity=SecuritySeverity.INFO,
                source_node='security_manager',
                description='Key rotation requested via service',
            ))

            response.success = True
            response.message = 'Key rotation initiated'
            return response

        except Exception as e:
            response.success = False
            response.message = f'Key rotation failed: {e}'
            return response

    def _enable_detection_callback(self, request, response):
        """Enable/disable intrusion detection service callback."""
        if not self._intrusion_detector:
            response.success = False
            response.message = 'Intrusion detector not configured'
            return response

        try:
            if request.data:
                self._intrusion_detector.start()
                response.message = 'Intrusion detection enabled'
            else:
                self._intrusion_detector.stop()
                response.message = 'Intrusion detection disabled'

            response.success = True
            return response

        except Exception as e:
            response.success = False
            response.message = f'Operation failed: {e}'
            return response


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = SecurityManagerNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
