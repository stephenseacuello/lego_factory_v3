#!/usr/bin/env python3
"""
LEGO MCP Formlabs SLA Printer Simulator

Simulates Formlabs SLA printer for testing without physical hardware.
Mimics PreFormServer Local API responses.

LEGO MCP Manufacturing System v7.0
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import asyncio
import random

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String


class PrinterState(Enum):
    """Formlabs printer states."""
    OFFLINE = "offline"
    IDLE = "idle"
    PRINTING = "printing"
    PAUSED = "paused"
    FINISHED = "finished"
    ERROR = "error"
    HEATING = "heating"
    FILLING = "filling"
    SELF_TEST = "self_test"


class PrintJobPhase(Enum):
    """Print job phases."""
    QUEUED = "queued"
    PREPARING = "preparing"
    HEATING = "heating"
    FILLING = "filling"
    PRINTING = "printing"
    SEPARATING = "separating"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class SimulatedResin:
    """Simulated resin cartridge."""
    material: str = "Grey_V5"
    volume_ml: float = 1000.0
    temperature_c: float = 31.0
    target_temperature_c: float = 31.0


@dataclass
class SimulatedTank:
    """Simulated resin tank."""
    serial: str = "SIM-TANK-001"
    material: str = "Grey_V5"
    lifetime_layers: int = 0
    max_layers: int = 75000


@dataclass
class SimulatedPrintJob:
    """Simulated print job."""
    job_id: str
    name: str
    form_file: str
    layer_count: int
    current_layer: int = 0
    phase: PrintJobPhase = PrintJobPhase.QUEUED
    estimated_print_time_s: int = 3600
    elapsed_time_s: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    volume_ml: float = 10.0


class FormlabsSimulatorNode(Node):
    """
    Simulates Formlabs SLA printer for testing.

    Features:
    - Simulates print job lifecycle
    - Mimics heating, filling, printing phases
    - Reports layer progress
    - Simulates resin consumption
    - Supports pause/resume/cancel
    """

    def __init__(self):
        super().__init__('formlabs_simulator')

        # Parameters
        self.declare_parameter('printer_name', 'formlabs_sim')
        self.declare_parameter('printer_model', 'Form 3+')
        self.declare_parameter('serial_number', 'SIM-FORM-001')
        self.declare_parameter('layer_time_s', 8.0)  # Simulated time per layer
        self.declare_parameter('heating_time_s', 300.0)  # 5 min heating
        self.declare_parameter('filling_time_s', 60.0)  # 1 min filling
        self.declare_parameter('status_rate', 1.0)  # Hz
        self.declare_parameter('simulate_failures', False)
        self.declare_parameter('failure_probability', 0.001)

        self._printer_name = self.get_parameter('printer_name').value
        self._printer_model = self.get_parameter('printer_model').value
        self._serial_number = self.get_parameter('serial_number').value
        self._layer_time = self.get_parameter('layer_time_s').value
        self._heating_time = self.get_parameter('heating_time_s').value
        self._filling_time = self.get_parameter('filling_time_s').value
        self._status_rate = self.get_parameter('status_rate').value
        self._simulate_failures = self.get_parameter('simulate_failures').value
        self._failure_probability = self.get_parameter('failure_probability').value

        # Printer state
        self._state = PrinterState.IDLE
        self._resin = SimulatedResin()
        self._tank = SimulatedTank()
        self._current_job: Optional[SimulatedPrintJob] = None
        self._job_queue: List[SimulatedPrintJob] = []
        self._job_history: List[SimulatedPrintJob] = []
        self._next_job_id = 1

        # Phase timing
        self._phase_start_time: Optional[datetime] = None
        self._phase_duration: float = 0.0

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Subscribers
        self.create_subscription(
            String,
            f'/{self._printer_name}/command',
            self._on_command,
            10,
            callback_group=self._cb_group
        )

        self.create_subscription(
            String,
            f'/{self._printer_name}/upload',
            self._on_upload,
            10,
            callback_group=self._cb_group
        )

        # Publishers
        self._status_pub = self.create_publisher(
            String,
            f'/{self._printer_name}/status',
            10
        )

        self._job_pub = self.create_publisher(
            String,
            f'/{self._printer_name}/job_status',
            10
        )

        self._event_pub = self.create_publisher(
            String,
            f'/{self._printer_name}/events',
            10
        )

        # Status timer
        self._status_timer = self.create_timer(
            1.0 / self._status_rate,
            self._publish_status,
            callback_group=self._cb_group
        )

        # Simulation timer (runs at 10Hz for smooth progress)
        self._sim_timer = self.create_timer(
            0.1,
            self._update_simulation,
            callback_group=self._cb_group
        )

        self.get_logger().info(
            f"Formlabs Simulator initialized: {self._printer_name} ({self._printer_model})"
        )

    def _on_command(self, msg: String):
        """Handle printer commands."""
        try:
            data = json.loads(msg.data)
            command = data.get('command', '')

            if command == 'print':
                job_id = data.get('job_id')
                self._start_print(job_id)

            elif command == 'pause':
                self._pause_print()

            elif command == 'resume':
                self._resume_print()

            elif command == 'cancel':
                self._cancel_print()

            elif command == 'status':
                self._publish_status()

            elif command == 'get_job':
                job_id = data.get('job_id')
                self._publish_job_status(job_id)

            elif command == 'list_jobs':
                self._publish_job_list()

            elif command == 'delete_job':
                job_id = data.get('job_id')
                self._delete_job(job_id)

            elif command == 'set_resin':
                material = data.get('material', 'Grey_V5')
                self._resin.material = material
                self._tank.material = material
                self._publish_event('resin_changed', {'material': material})

            else:
                self.get_logger().warn(f"Unknown command: {command}")

        except json.JSONDecodeError:
            self.get_logger().error(f"Invalid command JSON: {msg.data}")

    def _on_upload(self, msg: String):
        """Handle file upload (simulated)."""
        try:
            data = json.loads(msg.data)
            file_path = data.get('file_path', '')
            file_name = data.get('name', file_path.split('/')[-1])

            # Simulate file analysis
            job = SimulatedPrintJob(
                job_id=f"job_{self._next_job_id:04d}",
                name=file_name,
                form_file=file_path,
                layer_count=random.randint(100, 500),  # Simulated
                estimated_print_time_s=random.randint(1800, 14400),  # 30min - 4h
                volume_ml=random.uniform(5.0, 50.0),
            )
            self._next_job_id += 1

            self._job_queue.append(job)

            self._publish_event('job_uploaded', {
                'job_id': job.job_id,
                'name': job.name,
                'layers': job.layer_count,
                'estimated_time_s': job.estimated_print_time_s,
                'volume_ml': round(job.volume_ml, 2),
            })

            self.get_logger().info(f"Job uploaded: {job.job_id} - {job.name}")

        except json.JSONDecodeError:
            self.get_logger().error(f"Invalid upload JSON: {msg.data}")

    def _start_print(self, job_id: Optional[str] = None):
        """Start printing a job."""
        if self._state not in [PrinterState.IDLE, PrinterState.FINISHED]:
            self._publish_event('error', {'message': f"Cannot start print: printer is {self._state.value}"})
            return

        # Find job
        job = None
        if job_id:
            for j in self._job_queue:
                if j.job_id == job_id:
                    job = j
                    break
        elif self._job_queue:
            job = self._job_queue[0]

        if not job:
            self._publish_event('error', {'message': 'No job to print'})
            return

        # Remove from queue
        self._job_queue.remove(job)

        # Start job
        self._current_job = job
        self._current_job.started_at = datetime.now()
        self._current_job.phase = PrintJobPhase.PREPARING

        # Start heating phase
        self._state = PrinterState.HEATING
        self._phase_start_time = datetime.now()
        self._phase_duration = self._heating_time

        self._publish_event('print_started', {
            'job_id': job.job_id,
            'name': job.name,
        })

        self.get_logger().info(f"Started print: {job.job_id} - {job.name}")

    def _pause_print(self):
        """Pause current print."""
        if self._state != PrinterState.PRINTING:
            return

        self._state = PrinterState.PAUSED
        if self._current_job:
            self._current_job.phase = PrintJobPhase.SEPARATING

        self._publish_event('print_paused', {
            'job_id': self._current_job.job_id if self._current_job else None,
        })

    def _resume_print(self):
        """Resume paused print."""
        if self._state != PrinterState.PAUSED:
            return

        self._state = PrinterState.PRINTING
        if self._current_job:
            self._current_job.phase = PrintJobPhase.PRINTING

        self._publish_event('print_resumed', {
            'job_id': self._current_job.job_id if self._current_job else None,
        })

    def _cancel_print(self):
        """Cancel current print."""
        if self._current_job:
            self._current_job.phase = PrintJobPhase.CANCELLED
            self._current_job.finished_at = datetime.now()
            self._job_history.append(self._current_job)

            self._publish_event('print_cancelled', {
                'job_id': self._current_job.job_id,
                'layer': self._current_job.current_layer,
                'total_layers': self._current_job.layer_count,
            })

            self._current_job = None

        self._state = PrinterState.IDLE

    def _delete_job(self, job_id: str):
        """Delete a queued job."""
        for job in self._job_queue:
            if job.job_id == job_id:
                self._job_queue.remove(job)
                self._publish_event('job_deleted', {'job_id': job_id})
                return

        self._publish_event('error', {'message': f'Job not found: {job_id}'})

    def _update_simulation(self):
        """Update simulation state (called at 10Hz)."""
        if not self._current_job:
            return

        now = datetime.now()

        # Check for simulated failures
        if self._simulate_failures and self._state == PrinterState.PRINTING:
            if random.random() < self._failure_probability:
                self._simulate_failure()
                return

        # Heating phase
        if self._state == PrinterState.HEATING:
            elapsed = (now - self._phase_start_time).total_seconds()

            # Simulate temperature rise
            progress = min(1.0, elapsed / self._phase_duration)
            self._resin.temperature_c = 20.0 + (self._resin.target_temperature_c - 20.0) * progress

            if elapsed >= self._phase_duration:
                # Move to filling phase
                self._state = PrinterState.FILLING
                self._current_job.phase = PrintJobPhase.FILLING
                self._phase_start_time = now
                self._phase_duration = self._filling_time

                self._publish_event('heating_complete', {
                    'temperature_c': self._resin.temperature_c,
                })

        # Filling phase
        elif self._state == PrinterState.FILLING:
            elapsed = (now - self._phase_start_time).total_seconds()

            if elapsed >= self._phase_duration:
                # Start printing
                self._state = PrinterState.PRINTING
                self._current_job.phase = PrintJobPhase.PRINTING
                self._phase_start_time = now

                self._publish_event('filling_complete', {})

        # Printing phase
        elif self._state == PrinterState.PRINTING:
            # Update elapsed time
            if self._current_job.started_at:
                self._current_job.elapsed_time_s = int(
                    (now - self._current_job.started_at).total_seconds()
                )

            # Advance layers based on simulated layer time
            elapsed = (now - self._phase_start_time).total_seconds()
            expected_layer = int(elapsed / self._layer_time)

            if expected_layer > self._current_job.current_layer:
                self._current_job.current_layer = min(
                    expected_layer,
                    self._current_job.layer_count
                )

                # Consume resin
                resin_per_layer = self._current_job.volume_ml / self._current_job.layer_count
                self._resin.volume_ml -= resin_per_layer
                self._tank.lifetime_layers += 1

                # Publish layer progress
                if self._current_job.current_layer % 10 == 0:
                    self._publish_event('layer_complete', {
                        'layer': self._current_job.current_layer,
                        'total_layers': self._current_job.layer_count,
                        'progress': round(
                            self._current_job.current_layer / self._current_job.layer_count * 100,
                            1
                        ),
                    })

            # Check if print is complete
            if self._current_job.current_layer >= self._current_job.layer_count:
                self._complete_print()

    def _complete_print(self):
        """Complete the current print job."""
        if not self._current_job:
            return

        self._current_job.phase = PrintJobPhase.FINISHED
        self._current_job.finished_at = datetime.now()
        self._current_job.current_layer = self._current_job.layer_count

        self._job_history.append(self._current_job)

        self._publish_event('print_complete', {
            'job_id': self._current_job.job_id,
            'name': self._current_job.name,
            'layers': self._current_job.layer_count,
            'elapsed_time_s': self._current_job.elapsed_time_s,
        })

        self.get_logger().info(f"Print complete: {self._current_job.job_id}")

        self._current_job = None
        self._state = PrinterState.FINISHED

        # Auto-start next job if queued
        if self._job_queue:
            # Wait a bit before starting next job
            self.create_timer(
                5.0,
                lambda: self._start_print(),
                callback_group=self._cb_group
            )

    def _simulate_failure(self):
        """Simulate a random print failure."""
        failures = [
            ('resin_low', 'Resin level too low'),
            ('tank_expired', 'Resin tank needs replacement'),
            ('motor_error', 'Build platform motor error'),
            ('laser_error', 'Laser calibration error'),
            ('temperature_error', 'Temperature sensor error'),
        ]

        failure_type, message = random.choice(failures)

        self._state = PrinterState.ERROR
        if self._current_job:
            self._current_job.phase = PrintJobPhase.FAILED

        self._publish_event('print_failed', {
            'job_id': self._current_job.job_id if self._current_job else None,
            'error_type': failure_type,
            'message': message,
            'layer': self._current_job.current_layer if self._current_job else 0,
        })

        self.get_logger().error(f"Simulated failure: {failure_type} - {message}")

    def _publish_status(self):
        """Publish printer status."""
        status = {
            'printer': {
                'name': self._printer_name,
                'model': self._printer_model,
                'serial': self._serial_number,
                'state': self._state.value,
            },
            'resin': {
                'material': self._resin.material,
                'volume_ml': round(self._resin.volume_ml, 1),
                'temperature_c': round(self._resin.temperature_c, 1),
            },
            'tank': {
                'serial': self._tank.serial,
                'material': self._tank.material,
                'lifetime_layers': self._tank.lifetime_layers,
                'lifetime_percent': round(
                    self._tank.lifetime_layers / self._tank.max_layers * 100, 1
                ),
            },
            'job': None,
            'queue_length': len(self._job_queue),
            'timestamp': datetime.now().isoformat(),
        }

        if self._current_job:
            status['job'] = {
                'job_id': self._current_job.job_id,
                'name': self._current_job.name,
                'phase': self._current_job.phase.value,
                'layer': self._current_job.current_layer,
                'total_layers': self._current_job.layer_count,
                'progress': round(
                    self._current_job.current_layer / self._current_job.layer_count * 100,
                    1
                ) if self._current_job.layer_count > 0 else 0,
                'elapsed_time_s': self._current_job.elapsed_time_s,
                'estimated_time_s': self._current_job.estimated_print_time_s,
            }

        msg = String()
        msg.data = json.dumps(status)
        self._status_pub.publish(msg)

    def _publish_job_status(self, job_id: Optional[str] = None):
        """Publish status of a specific job."""
        job = None

        if job_id:
            # Check current job
            if self._current_job and self._current_job.job_id == job_id:
                job = self._current_job
            # Check queue
            for j in self._job_queue:
                if j.job_id == job_id:
                    job = j
                    break
            # Check history
            for j in self._job_history:
                if j.job_id == job_id:
                    job = j
                    break
        else:
            job = self._current_job

        if not job:
            self._publish_event('error', {'message': f'Job not found: {job_id}'})
            return

        status = {
            'job_id': job.job_id,
            'name': job.name,
            'phase': job.phase.value,
            'layer': job.current_layer,
            'total_layers': job.layer_count,
            'progress': round(job.current_layer / job.layer_count * 100, 1) if job.layer_count > 0 else 0,
            'elapsed_time_s': job.elapsed_time_s,
            'estimated_time_s': job.estimated_print_time_s,
            'volume_ml': round(job.volume_ml, 2),
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'finished_at': job.finished_at.isoformat() if job.finished_at else None,
        }

        msg = String()
        msg.data = json.dumps(status)
        self._job_pub.publish(msg)

    def _publish_job_list(self):
        """Publish list of all jobs."""
        jobs = []

        if self._current_job:
            jobs.append({
                'job_id': self._current_job.job_id,
                'name': self._current_job.name,
                'status': 'printing',
                'progress': round(
                    self._current_job.current_layer / self._current_job.layer_count * 100,
                    1
                ) if self._current_job.layer_count > 0 else 0,
            })

        for job in self._job_queue:
            jobs.append({
                'job_id': job.job_id,
                'name': job.name,
                'status': 'queued',
                'progress': 0,
            })

        for job in self._job_history[-10:]:  # Last 10 completed jobs
            jobs.append({
                'job_id': job.job_id,
                'name': job.name,
                'status': job.phase.value,
                'progress': 100 if job.phase == PrintJobPhase.FINISHED else 0,
            })

        msg = String()
        msg.data = json.dumps({'jobs': jobs})
        self._job_pub.publish(msg)

    def _publish_event(self, event_type: str, data: Dict[str, Any]):
        """Publish an event."""
        event = {
            'event': event_type,
            'data': data,
            'timestamp': datetime.now().isoformat(),
        }

        msg = String()
        msg.data = json.dumps(event)
        self._event_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = FormlabsSimulatorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
