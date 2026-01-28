#!/usr/bin/env python3
"""
Lifecycle Base Class for LEGO MCP Nodes

Provides abstract base class and mixin for ROS2 Lifecycle node implementation.
Enables graceful state management with configure/activate/deactivate/cleanup callbacks.

Industry 4.0/5.0 Architecture - ISA-95 Levels 1-2
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable
from datetime import datetime
import traceback

import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.lifecycle import LifecycleState
from std_msgs.msg import String
from diagnostic_msgs.msg import DiagnosticStatus, DiagnosticArray, KeyValue


class LifecycleNodeBase(LifecycleNode, ABC):
    """
    Abstract base class for LEGO MCP Lifecycle Nodes.

    Provides:
    - Standard lifecycle callbacks with error handling
    - Diagnostic publishing
    - State tracking
    - Graceful degradation support

    Usage:
        class MyNode(LifecycleNodeBase):
            def do_configure(self) -> bool:
                # Your configuration logic
                return True

            def do_activate(self) -> bool:
                # Your activation logic
                return True
    """

    def __init__(self, node_name: str, **kwargs):
        """
        Initialize lifecycle node.

        Args:
            node_name: ROS2 node name
            **kwargs: Additional arguments passed to LifecycleNode
        """
        super().__init__(node_name, **kwargs)

        # State tracking
        self._configured = False
        self._active = False
        self._error_count = 0
        self._last_error: Optional[str] = None
        self._state_history: list = []

        # Diagnostic publisher
        self._diag_pub = self.create_publisher(
            DiagnosticArray,
            '/diagnostics',
            10
        )

        # State publisher
        self._state_pub = self.create_publisher(
            String,
            f'/lego_mcp/{node_name}/lifecycle_state',
            10
        )

        self.get_logger().info(f'{node_name} lifecycle node initialized')

    # ===================
    # Abstract Methods (implement in subclass)
    # ===================

    @abstractmethod
    def do_configure(self) -> bool:
        """
        Perform node configuration.

        Called during configure transition. Initialize resources,
        load parameters, create publishers/subscribers.

        Returns:
            True if configuration successful, False otherwise
        """
        pass

    @abstractmethod
    def do_activate(self) -> bool:
        """
        Activate the node.

        Called during activate transition. Start processing,
        enable hardware, begin publishing.

        Returns:
            True if activation successful, False otherwise
        """
        pass

    def do_deactivate(self) -> bool:
        """
        Deactivate the node.

        Called during deactivate transition. Stop processing,
        disable hardware, stop publishing.

        Returns:
            True if deactivation successful, False otherwise
        """
        return True

    def do_cleanup(self) -> bool:
        """
        Clean up node resources.

        Called during cleanup transition. Release resources,
        close connections, deallocate memory.

        Returns:
            True if cleanup successful, False otherwise
        """
        return True

    def do_shutdown(self) -> bool:
        """
        Shutdown the node.

        Called during shutdown transition. Final cleanup before
        node destruction.

        Returns:
            True if shutdown successful, False otherwise
        """
        return True

    def do_error_recovery(self) -> bool:
        """
        Attempt to recover from error state.

        Called when transitioning out of error state.

        Returns:
            True if recovery successful, False otherwise
        """
        return True

    # ===================
    # Lifecycle Callbacks
    # ===================

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Handle configure transition."""
        self.get_logger().info(f'Configuring from state: {state.label}')
        self._record_state_change('configuring')

        try:
            if self.do_configure():
                self._configured = True
                self._publish_diagnostic(DiagnosticStatus.OK, 'Configured')
                self._publish_state('inactive')
                self.get_logger().info('Configuration successful')
                return TransitionCallbackReturn.SUCCESS
            else:
                self._record_error('Configuration returned False')
                self._publish_diagnostic(DiagnosticStatus.ERROR, 'Configuration failed')
                return TransitionCallbackReturn.FAILURE

        except Exception as e:
            self._record_error(f'Configuration exception: {e}')
            self.get_logger().error(f'Configuration error: {e}\n{traceback.format_exc()}')
            self._publish_diagnostic(DiagnosticStatus.ERROR, str(e))
            return TransitionCallbackReturn.FAILURE

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Handle activate transition."""
        self.get_logger().info(f'Activating from state: {state.label}')
        self._record_state_change('activating')

        try:
            if self.do_activate():
                self._active = True
                self._publish_diagnostic(DiagnosticStatus.OK, 'Active')
                self._publish_state('active')
                self.get_logger().info('Activation successful')
                return TransitionCallbackReturn.SUCCESS
            else:
                self._record_error('Activation returned False')
                self._publish_diagnostic(DiagnosticStatus.WARN, 'Activation failed')
                return TransitionCallbackReturn.FAILURE

        except Exception as e:
            self._record_error(f'Activation exception: {e}')
            self.get_logger().error(f'Activation error: {e}\n{traceback.format_exc()}')
            self._publish_diagnostic(DiagnosticStatus.ERROR, str(e))
            return TransitionCallbackReturn.FAILURE

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Handle deactivate transition."""
        self.get_logger().info(f'Deactivating from state: {state.label}')
        self._record_state_change('deactivating')

        try:
            if self.do_deactivate():
                self._active = False
                self._publish_diagnostic(DiagnosticStatus.OK, 'Inactive')
                self._publish_state('inactive')
                self.get_logger().info('Deactivation successful')
                return TransitionCallbackReturn.SUCCESS
            else:
                self._record_error('Deactivation returned False')
                return TransitionCallbackReturn.FAILURE

        except Exception as e:
            self._record_error(f'Deactivation exception: {e}')
            self.get_logger().error(f'Deactivation error: {e}')
            return TransitionCallbackReturn.FAILURE

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Handle cleanup transition."""
        self.get_logger().info(f'Cleaning up from state: {state.label}')
        self._record_state_change('cleaning_up')

        try:
            if self.do_cleanup():
                self._configured = False
                self._publish_diagnostic(DiagnosticStatus.OK, 'Unconfigured')
                self._publish_state('unconfigured')
                self.get_logger().info('Cleanup successful')
                return TransitionCallbackReturn.SUCCESS
            else:
                return TransitionCallbackReturn.FAILURE

        except Exception as e:
            self.get_logger().error(f'Cleanup error: {e}')
            return TransitionCallbackReturn.FAILURE

    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Handle shutdown transition."""
        self.get_logger().info(f'Shutting down from state: {state.label}')
        self._record_state_change('shutting_down')

        try:
            self.do_shutdown()
            self._publish_state('finalized')
            self.get_logger().info('Shutdown complete')
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f'Shutdown error: {e}')
            return TransitionCallbackReturn.SUCCESS  # Always succeed on shutdown

    def on_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Handle error state entry."""
        self.get_logger().error(f'Error state from: {state.label}')
        self._record_state_change('error')
        self._publish_diagnostic(DiagnosticStatus.ERROR, self._last_error or 'Unknown error')
        self._publish_state('error')

        try:
            if self.do_error_recovery():
                self.get_logger().info('Error recovery successful')
                return TransitionCallbackReturn.SUCCESS
            else:
                return TransitionCallbackReturn.FAILURE

        except Exception as e:
            self.get_logger().error(f'Error recovery failed: {e}')
            return TransitionCallbackReturn.FAILURE

    # ===================
    # Helper Methods
    # ===================

    def _record_state_change(self, new_state: str):
        """Record state transition for history."""
        self._state_history.append({
            'state': new_state,
            'timestamp': datetime.now().isoformat(),
        })
        # Keep last 100 transitions
        if len(self._state_history) > 100:
            self._state_history = self._state_history[-100:]

    def _record_error(self, error_msg: str):
        """Record an error."""
        self._error_count += 1
        self._last_error = error_msg
        self.get_logger().error(error_msg)

    def _publish_diagnostic(self, level: int, message: str):
        """Publish diagnostic status."""
        msg = DiagnosticArray()
        msg.header.stamp = self.get_clock().now().to_msg()

        status = DiagnosticStatus()
        status.level = level
        status.name = self.get_name()
        status.message = message
        status.hardware_id = f'lego_mcp/{self.get_name()}'

        status.values = [
            KeyValue(key='configured', value=str(self._configured)),
            KeyValue(key='active', value=str(self._active)),
            KeyValue(key='error_count', value=str(self._error_count)),
        ]

        if self._last_error:
            status.values.append(KeyValue(key='last_error', value=self._last_error))

        msg.status.append(status)
        self._diag_pub.publish(msg)

    def _publish_state(self, state: str):
        """Publish current lifecycle state."""
        msg = String()
        msg.data = state
        self._state_pub.publish(msg)

    @property
    def is_configured(self) -> bool:
        """Check if node is configured."""
        return self._configured

    @property
    def is_active(self) -> bool:
        """Check if node is active."""
        return self._active

    def get_state_history(self) -> list:
        """Get state transition history."""
        return self._state_history.copy()


class LifecycleMixin:
    """
    Mixin class to add lifecycle capabilities to existing nodes.

    Use this when you need to add lifecycle behavior to a node
    that already inherits from another class.

    Usage:
        class MyExistingNode(SomeBaseClass, LifecycleMixin):
            def __init__(self):
                super().__init__()
                self.init_lifecycle_mixin()
    """

    def init_lifecycle_mixin(self):
        """Initialize lifecycle mixin state."""
        self._lc_configured = False
        self._lc_active = False
        self._lc_error_count = 0

    def lifecycle_configure(self) -> bool:
        """Override in subclass for configuration."""
        return True

    def lifecycle_activate(self) -> bool:
        """Override in subclass for activation."""
        return True

    def lifecycle_deactivate(self) -> bool:
        """Override in subclass for deactivation."""
        return True

    def lifecycle_cleanup(self) -> bool:
        """Override in subclass for cleanup."""
        return True

    @property
    def lc_is_active(self) -> bool:
        """Check if lifecycle is active."""
        return getattr(self, '_lc_active', False)


def create_lifecycle_wrapper(
    original_class: type,
    node_name: str,
) -> type:
    """
    Factory function to create a lifecycle wrapper for an existing node class.

    Args:
        original_class: The original node class to wrap
        node_name: Name for the lifecycle node

    Returns:
        A new class that wraps the original with lifecycle support
    """

    class LifecycleWrapper(LifecycleNodeBase):
        """Dynamically generated lifecycle wrapper."""

        def __init__(self, **kwargs):
            super().__init__(node_name, **kwargs)
            self._wrapped_instance: Optional[Any] = None

        def do_configure(self) -> bool:
            try:
                self._wrapped_instance = original_class()
                return True
            except Exception as e:
                self.get_logger().error(f'Failed to create wrapped instance: {e}')
                return False

        def do_activate(self) -> bool:
            if self._wrapped_instance is None:
                return False
            # If wrapped class has an activate method, call it
            if hasattr(self._wrapped_instance, 'activate'):
                return self._wrapped_instance.activate()
            return True

        def do_deactivate(self) -> bool:
            if self._wrapped_instance and hasattr(self._wrapped_instance, 'deactivate'):
                return self._wrapped_instance.deactivate()
            return True

        def do_cleanup(self) -> bool:
            if self._wrapped_instance and hasattr(self._wrapped_instance, 'cleanup'):
                self._wrapped_instance.cleanup()
            self._wrapped_instance = None
            return True

    LifecycleWrapper.__name__ = f'{original_class.__name__}Lifecycle'
    return LifecycleWrapper
