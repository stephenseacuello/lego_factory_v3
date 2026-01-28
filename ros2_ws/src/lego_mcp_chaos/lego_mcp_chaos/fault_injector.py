#!/usr/bin/env python3
"""
Fault Injector for LEGO MCP Chaos Testing

Implements fault injection patterns for ROS2:
- Node crash injection
- Network partition simulation
- Message delay injection
- Resource exhaustion
- Clock skew simulation

Industry 4.0/5.0 Architecture - Chaos Engineering
"""

import os
import signal
import subprocess
import threading
import time
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set


class FaultType(Enum):
    """Types of faults that can be injected."""
    NODE_CRASH = auto()          # Kill a node process
    NODE_HANG = auto()           # Make node unresponsive
    MESSAGE_DELAY = auto()       # Add latency to messages
    MESSAGE_DROP = auto()        # Drop messages
    MESSAGE_CORRUPT = auto()     # Corrupt message data
    NETWORK_PARTITION = auto()   # Isolate nodes from each other
    RESOURCE_EXHAUSTION = auto() # CPU/memory pressure
    CLOCK_SKEW = auto()          # Time synchronization issues
    DDS_FAILURE = auto()         # DDS middleware issues


@dataclass
class FaultInjection:
    """Record of an injected fault."""
    injection_id: str
    fault_type: FaultType
    target: str
    parameters: Dict = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    active: bool = True
    outcome: Optional[str] = None


class FaultInjector:
    """
    Fault Injector for chaos testing.

    Provides controlled fault injection into the ROS2 system
    for resilience testing and validation.

    Usage:
        injector = FaultInjector()
        injection = injector.inject_node_crash("orchestrator_node")
        time.sleep(5)
        injector.stop_injection(injection.injection_id)
    """

    def __init__(self):
        """Initialize fault injector."""
        self._injections: Dict[str, FaultInjection] = {}
        self._lock = threading.RLock()
        self._injection_counter = 0

        # Message interceptors
        self._delay_interceptors: Dict[str, float] = {}  # topic -> delay_ms
        self._drop_interceptors: Dict[str, float] = {}   # topic -> drop_rate

        # Recovery handlers
        self._recovery_handlers: Dict[FaultType, Callable] = {}

    def _generate_id(self) -> str:
        """Generate unique injection ID."""
        self._injection_counter += 1
        return f"FAULT-{self._injection_counter:04d}"

    def inject_node_crash(
        self,
        node_name: str,
        signal_type: int = signal.SIGKILL,
    ) -> FaultInjection:
        """
        Inject a node crash by killing its process.

        Args:
            node_name: Name of the node to crash
            signal_type: Signal to send (SIGKILL, SIGTERM, etc.)

        Returns:
            FaultInjection record
        """
        injection_id = self._generate_id()

        injection = FaultInjection(
            injection_id=injection_id,
            fault_type=FaultType.NODE_CRASH,
            target=node_name,
            parameters={"signal": signal_type},
        )

        try:
            # Find and kill the node process
            result = subprocess.run(
                ["pkill", "-f", f"--ros-args.*{node_name}"],
                capture_output=True,
            )

            if result.returncode == 0:
                injection.outcome = "SUCCESS"
            else:
                # Try alternative method
                result = subprocess.run(
                    ["ros2", "node", "kill", node_name],
                    capture_output=True,
                )
                injection.outcome = "SUCCESS" if result.returncode == 0 else "FAILED"

        except Exception as e:
            injection.outcome = f"ERROR: {e}"
            injection.active = False

        with self._lock:
            self._injections[injection_id] = injection

        return injection

    def inject_node_hang(
        self,
        node_name: str,
        duration_seconds: float = 10.0,
    ) -> FaultInjection:
        """
        Inject a node hang by sending SIGSTOP.

        Args:
            node_name: Name of the node
            duration_seconds: How long to hang

        Returns:
            FaultInjection record
        """
        injection_id = self._generate_id()

        injection = FaultInjection(
            injection_id=injection_id,
            fault_type=FaultType.NODE_HANG,
            target=node_name,
            parameters={"duration": duration_seconds},
        )

        try:
            # Send SIGSTOP
            subprocess.run(
                ["pkill", "-STOP", "-f", f"--ros-args.*{node_name}"],
                capture_output=True,
            )
            injection.outcome = "STARTED"

            # Schedule SIGCONT
            def resume():
                time.sleep(duration_seconds)
                subprocess.run(
                    ["pkill", "-CONT", "-f", f"--ros-args.*{node_name}"],
                    capture_output=True,
                )
                with self._lock:
                    injection.active = False
                    injection.end_time = datetime.now()
                    injection.outcome = "COMPLETED"

            thread = threading.Thread(target=resume, daemon=True)
            thread.start()

        except Exception as e:
            injection.outcome = f"ERROR: {e}"
            injection.active = False

        with self._lock:
            self._injections[injection_id] = injection

        return injection

    def inject_message_delay(
        self,
        topic: str,
        delay_ms: float,
        duration_seconds: Optional[float] = None,
    ) -> FaultInjection:
        """
        Inject message delay on a topic.

        Note: Actual implementation requires middleware hooks.
        This records the intent for external implementation.

        Args:
            topic: Topic to delay
            delay_ms: Delay in milliseconds
            duration_seconds: Optional duration

        Returns:
            FaultInjection record
        """
        injection_id = self._generate_id()

        injection = FaultInjection(
            injection_id=injection_id,
            fault_type=FaultType.MESSAGE_DELAY,
            target=topic,
            parameters={"delay_ms": delay_ms, "duration": duration_seconds},
        )

        self._delay_interceptors[topic] = delay_ms

        if duration_seconds:
            def stop_delay():
                time.sleep(duration_seconds)
                if topic in self._delay_interceptors:
                    del self._delay_interceptors[topic]
                with self._lock:
                    injection.active = False
                    injection.end_time = datetime.now()
                    injection.outcome = "COMPLETED"

            thread = threading.Thread(target=stop_delay, daemon=True)
            thread.start()

        injection.outcome = "ACTIVE"

        with self._lock:
            self._injections[injection_id] = injection

        return injection

    def inject_message_drop(
        self,
        topic: str,
        drop_rate: float,  # 0.0 to 1.0
        duration_seconds: Optional[float] = None,
    ) -> FaultInjection:
        """
        Inject message drops on a topic.

        Args:
            topic: Topic to drop messages from
            drop_rate: Probability of dropping (0-1)
            duration_seconds: Optional duration

        Returns:
            FaultInjection record
        """
        injection_id = self._generate_id()

        injection = FaultInjection(
            injection_id=injection_id,
            fault_type=FaultType.MESSAGE_DROP,
            target=topic,
            parameters={"drop_rate": drop_rate, "duration": duration_seconds},
        )

        self._drop_interceptors[topic] = drop_rate

        if duration_seconds:
            def stop_drop():
                time.sleep(duration_seconds)
                if topic in self._drop_interceptors:
                    del self._drop_interceptors[topic]
                with self._lock:
                    injection.active = False
                    injection.end_time = datetime.now()

            thread = threading.Thread(target=stop_drop, daemon=True)
            thread.start()

        injection.outcome = "ACTIVE"

        with self._lock:
            self._injections[injection_id] = injection

        return injection

    def inject_resource_exhaustion(
        self,
        resource_type: str,  # "cpu", "memory"
        intensity: float,  # 0.0 to 1.0
        duration_seconds: float = 30.0,
    ) -> FaultInjection:
        """
        Inject resource exhaustion.

        Args:
            resource_type: "cpu" or "memory"
            intensity: 0-1 intensity level
            duration_seconds: Duration

        Returns:
            FaultInjection record
        """
        injection_id = self._generate_id()

        injection = FaultInjection(
            injection_id=injection_id,
            fault_type=FaultType.RESOURCE_EXHAUSTION,
            target=resource_type,
            parameters={"intensity": intensity, "duration": duration_seconds},
        )

        try:
            if resource_type == "cpu":
                # CPU stress using stress-ng if available
                cores = int(os.cpu_count() * intensity)
                subprocess.Popen(
                    ["stress-ng", "--cpu", str(max(1, cores)), "--timeout", f"{int(duration_seconds)}s"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                injection.outcome = "STARTED"

            elif resource_type == "memory":
                # Memory stress
                mb = int(1000 * intensity)  # Up to 1GB
                subprocess.Popen(
                    ["stress-ng", "--vm", "1", "--vm-bytes", f"{mb}M", "--timeout", f"{int(duration_seconds)}s"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                injection.outcome = "STARTED"

        except FileNotFoundError:
            injection.outcome = "FAILED: stress-ng not installed"
            injection.active = False
        except Exception as e:
            injection.outcome = f"ERROR: {e}"
            injection.active = False

        # Auto-deactivate after duration
        def deactivate():
            time.sleep(duration_seconds)
            with self._lock:
                injection.active = False
                injection.end_time = datetime.now()

        threading.Thread(target=deactivate, daemon=True).start()

        with self._lock:
            self._injections[injection_id] = injection

        return injection

    def inject_network_partition(
        self,
        node_a: str,
        node_b: str,
        duration_seconds: Optional[float] = None,
    ) -> FaultInjection:
        """
        Inject network partition between nodes.

        Note: Requires iptables/firewall access for real implementation.

        Args:
            node_a: First node
            node_b: Second node
            duration_seconds: Optional duration

        Returns:
            FaultInjection record
        """
        injection_id = self._generate_id()

        injection = FaultInjection(
            injection_id=injection_id,
            fault_type=FaultType.NETWORK_PARTITION,
            target=f"{node_a}<->{node_b}",
            parameters={"duration": duration_seconds},
        )

        # In a real implementation, this would use iptables or network namespaces
        # For now, record the intent
        injection.outcome = "SIMULATED"

        with self._lock:
            self._injections[injection_id] = injection

        return injection

    def stop_injection(self, injection_id: str) -> bool:
        """
        Stop an active fault injection.

        Args:
            injection_id: ID of the injection to stop

        Returns:
            True if stopped successfully
        """
        with self._lock:
            injection = self._injections.get(injection_id)
            if not injection or not injection.active:
                return False

            # Clean up based on fault type
            if injection.fault_type == FaultType.MESSAGE_DELAY:
                topic = injection.target
                if topic in self._delay_interceptors:
                    del self._delay_interceptors[topic]

            elif injection.fault_type == FaultType.MESSAGE_DROP:
                topic = injection.target
                if topic in self._drop_interceptors:
                    del self._drop_interceptors[topic]

            elif injection.fault_type == FaultType.NODE_HANG:
                # Resume the node
                subprocess.run(
                    ["pkill", "-CONT", "-f", f"--ros-args.*{injection.target}"],
                    capture_output=True,
                )

            injection.active = False
            injection.end_time = datetime.now()
            return True

    def stop_all_injections(self):
        """Stop all active fault injections."""
        with self._lock:
            for injection_id in list(self._injections.keys()):
                self.stop_injection(injection_id)

    def get_active_injections(self) -> List[FaultInjection]:
        """Get all active fault injections."""
        with self._lock:
            return [i for i in self._injections.values() if i.active]

    def get_injection(self, injection_id: str) -> Optional[FaultInjection]:
        """Get a specific injection record."""
        return self._injections.get(injection_id)

    def should_delay_message(self, topic: str) -> float:
        """Check if message should be delayed and by how much."""
        return self._delay_interceptors.get(topic, 0.0)

    def should_drop_message(self, topic: str) -> bool:
        """Check if message should be dropped."""
        rate = self._drop_interceptors.get(topic, 0.0)
        return random.random() < rate

    def get_statistics(self) -> Dict:
        """Get fault injection statistics."""
        with self._lock:
            active = [i for i in self._injections.values() if i.active]
            completed = [i for i in self._injections.values() if not i.active]

            by_type = {}
            for i in self._injections.values():
                by_type[i.fault_type.name] = by_type.get(i.fault_type.name, 0) + 1

            return {
                "total_injections": len(self._injections),
                "active_injections": len(active),
                "completed_injections": len(completed),
                "by_type": by_type,
            }
