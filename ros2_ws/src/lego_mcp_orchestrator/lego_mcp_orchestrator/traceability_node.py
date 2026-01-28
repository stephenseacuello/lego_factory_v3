#!/usr/bin/env python3
"""
Traceability / Digital Thread Node

Maintains complete manufacturing traceability for every part produced.
Records design, manufacturing, quality, and assembly history.

Features:
- Full part genealogy tracking
- Manufacturing event recording
- Quality inspection history
- Tamper-evident audit trail (hash chain)
- Serialization management
- Recall capability
- Regulatory compliance support (FDA 21 CFR Part 11, EU MDR)

LEGO MCP Manufacturing System v7.0
"""

import json
import hashlib
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from collections import defaultdict

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String
from std_srvs.srv import Trigger

try:
    from lego_mcp_msgs.msg import QualityEvent, DefectDetection
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class EventType(Enum):
    """Traceability event types."""
    PART_CREATED = 'part_created'
    DESIGN_LINKED = 'design_linked'
    MATERIAL_ADDED = 'material_added'
    OPERATION_START = 'operation_start'
    OPERATION_END = 'operation_end'
    QUALITY_CHECK = 'quality_check'
    DEFECT_FOUND = 'defect_found'
    REWORK = 'rework'
    INSPECTION_PASS = 'inspection_pass'
    INSPECTION_FAIL = 'inspection_fail'
    ASSEMBLY_START = 'assembly_start'
    ASSEMBLY_END = 'assembly_end'
    PACKAGING = 'packaging'
    SHIPMENT = 'shipment'
    RECALL = 'recall'
    DISPOSITION = 'disposition'


@dataclass
class TraceabilityEvent:
    """Single traceability event."""
    event_id: str
    serial_number: str
    event_type: EventType
    timestamp: float
    source_node: str
    data: Dict[str, Any] = field(default_factory=dict)
    previous_hash: str = ""
    event_hash: str = ""
    signature: str = ""  # Digital signature (optional HSM)

    def compute_hash(self) -> str:
        """Compute hash of this event."""
        content = json.dumps({
            'event_id': self.event_id,
            'serial_number': self.serial_number,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp,
            'source_node': self.source_node,
            'data': self.data,
            'previous_hash': self.previous_hash,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class PartRecord:
    """Complete part traceability record."""
    serial_number: str
    part_id: str
    work_order_id: str
    batch_id: str = ""

    # Design
    design_id: str = ""
    design_revision: str = ""
    cad_hash: str = ""

    # Material
    material_lot_numbers: List[str] = field(default_factory=list)
    material_types: List[str] = field(default_factory=list)

    # Manufacturing
    equipment_used: List[str] = field(default_factory=list)
    operations_performed: List[str] = field(default_factory=list)
    manufacturing_start: float = 0.0
    manufacturing_end: float = 0.0

    # Quality
    inspection_results: List[Dict] = field(default_factory=list)
    defects_found: List[Dict] = field(default_factory=list)
    quality_status: str = "pending"  # pending, pass, fail, rework

    # Assembly
    parent_assembly: str = ""
    child_components: List[str] = field(default_factory=list)

    # Chain
    event_chain: List[str] = field(default_factory=list)  # Event IDs
    chain_root_hash: str = ""
    chain_tip_hash: str = ""

    # Status
    status: str = "in_progress"  # in_progress, complete, shipped, recalled
    disposition: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class BatchRecord:
    """Batch traceability record."""
    batch_id: str
    work_order_id: str
    part_id: str
    serial_numbers: List[str] = field(default_factory=list)
    quantity_target: int = 0
    quantity_produced: int = 0
    quantity_passed: int = 0
    quantity_failed: int = 0
    batch_start: float = 0.0
    batch_end: float = 0.0
    status: str = "in_progress"


class TraceabilityNode(Node):
    """
    Traceability node for complete manufacturing history.

    Implements:
    - Part genealogy (forward/backward traceability)
    - Hash chain for tamper evidence
    - Event sourcing pattern
    - Recall support
    """

    def __init__(self):
        super().__init__('traceability')

        # Parameters
        self.declare_parameter('storage_backend', 'memory')  # memory, sqlite, postgresql
        self.declare_parameter('enable_hash_chain', True)
        self.declare_parameter('enable_signatures', False)
        self.declare_parameter('retention_days', 365 * 7)  # 7 year default
        self.declare_parameter('serial_prefix', 'LEGO-MCP')

        self._storage_backend = self.get_parameter('storage_backend').value
        self._enable_hash_chain = self.get_parameter('enable_hash_chain').value
        self._enable_signatures = self.get_parameter('enable_signatures').value
        self._serial_prefix = self.get_parameter('serial_prefix').value

        # Storage
        self._parts: Dict[str, PartRecord] = {}
        self._batches: Dict[str, BatchRecord] = {}
        self._events: Dict[str, TraceabilityEvent] = {}
        self._serial_index: Dict[str, str] = {}  # serial -> part_id mapping
        self._lock = threading.RLock()

        # Serial number counter
        self._serial_counter = 0

        # Callback groups
        self._srv_group = ReentrantCallbackGroup()
        self._sub_group = ReentrantCallbackGroup()

        # QoS
        reliable_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            depth=100
        )

        # Publishers
        self._events_pub = self.create_publisher(
            String,
            '/lego_mcp/traceability/events',
            reliable_qos
        )

        self._audit_pub = self.create_publisher(
            String,
            '/lego_mcp/traceability/audit',
            reliable_qos
        )

        # Subscribers
        self.create_subscription(
            String,
            '/lego_mcp/work_order/events',
            self._on_work_order_event,
            10,
            callback_group=self._sub_group
        )

        self.create_subscription(
            String,
            '/lego_mcp/inspection/results',
            self._on_inspection_result,
            reliable_qos,
            callback_group=self._sub_group
        )

        self.create_subscription(
            String,
            '/lego_mcp/inspection/defects',
            self._on_defect_detected,
            10,
            callback_group=self._sub_group
        )

        self.create_subscription(
            String,
            '/lego_mcp/scheduler/dispatch',
            self._on_job_dispatch,
            10,
            callback_group=self._sub_group
        )

        # Services
        self._create_part_srv = self.create_service(
            Trigger,
            '/lego_mcp/traceability/create_part',
            self._create_part_callback,
            callback_group=self._srv_group
        )

        self._get_part_srv = self.create_service(
            Trigger,
            '/lego_mcp/traceability/get_part',
            self._get_part_callback,
            callback_group=self._srv_group
        )

        self._get_history_srv = self.create_service(
            Trigger,
            '/lego_mcp/traceability/get_history',
            self._get_history_callback,
            callback_group=self._srv_group
        )

        self._verify_chain_srv = self.create_service(
            Trigger,
            '/lego_mcp/traceability/verify_chain',
            self._verify_chain_callback,
            callback_group=self._srv_group
        )

        self._trace_forward_srv = self.create_service(
            Trigger,
            '/lego_mcp/traceability/trace_forward',
            self._trace_forward_callback,
            callback_group=self._srv_group
        )

        self._trace_backward_srv = self.create_service(
            Trigger,
            '/lego_mcp/traceability/trace_backward',
            self._trace_backward_callback,
            callback_group=self._srv_group
        )

        self._initiate_recall_srv = self.create_service(
            Trigger,
            '/lego_mcp/traceability/initiate_recall',
            self._initiate_recall_callback,
            callback_group=self._srv_group
        )

        self._get_statistics_srv = self.create_service(
            Trigger,
            '/lego_mcp/traceability/statistics',
            self._get_statistics_callback,
            callback_group=self._srv_group
        )

        self.get_logger().info(
            f'Traceability node started - backend: {self._storage_backend}, '
            f'hash chain: {self._enable_hash_chain}'
        )

    def _generate_serial_number(self) -> str:
        """Generate unique serial number."""
        self._serial_counter += 1
        timestamp = datetime.now().strftime('%Y%m%d')
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"{self._serial_prefix}-{timestamp}-{self._serial_counter:06d}-{unique_id}"

    def _create_part(
        self,
        part_id: str,
        work_order_id: str,
        batch_id: str = "",
        design_id: str = "",
    ) -> PartRecord:
        """Create new part record."""
        serial_number = self._generate_serial_number()
        current_time = time.time()

        part = PartRecord(
            serial_number=serial_number,
            part_id=part_id,
            work_order_id=work_order_id,
            batch_id=batch_id,
            design_id=design_id,
            created_at=current_time,
            updated_at=current_time,
        )

        with self._lock:
            self._parts[serial_number] = part
            self._serial_index[serial_number] = part_id

        # Record creation event
        self._record_event(
            serial_number,
            EventType.PART_CREATED,
            {
                'part_id': part_id,
                'work_order_id': work_order_id,
                'batch_id': batch_id,
            }
        )

        return part

    def _record_event(
        self,
        serial_number: str,
        event_type: EventType,
        data: Dict[str, Any],
        source_node: str = ""
    ) -> TraceabilityEvent:
        """Record traceability event with hash chain."""
        event_id = str(uuid.uuid4())
        current_time = time.time()

        # Get previous hash
        previous_hash = ""
        if self._enable_hash_chain and serial_number in self._parts:
            part = self._parts[serial_number]
            if part.chain_tip_hash:
                previous_hash = part.chain_tip_hash

        event = TraceabilityEvent(
            event_id=event_id,
            serial_number=serial_number,
            event_type=event_type,
            timestamp=current_time,
            source_node=source_node or self.get_name(),
            data=data,
            previous_hash=previous_hash,
        )

        # Compute hash
        event.event_hash = event.compute_hash()

        with self._lock:
            self._events[event_id] = event

            # Update part record
            if serial_number in self._parts:
                part = self._parts[serial_number]
                part.event_chain.append(event_id)
                part.chain_tip_hash = event.event_hash
                if not part.chain_root_hash:
                    part.chain_root_hash = event.event_hash
                part.updated_at = current_time

        # Publish event
        self._publish_event(event)

        return event

    def _publish_event(self, event: TraceabilityEvent):
        """Publish traceability event."""
        event_data = {
            'event_id': event.event_id,
            'serial_number': event.serial_number,
            'event_type': event.event_type.value,
            'timestamp': event.timestamp,
            'data': event.data,
            'event_hash': event.event_hash,
        }

        msg = String()
        msg.data = json.dumps(event_data)
        self._events_pub.publish(msg)

    def _on_work_order_event(self, msg: String):
        """Handle work order events."""
        try:
            event = json.loads(msg.data)
            event_type = event.get('event_type', '')
            data = event.get('data', {})

            if event_type == 'work_order_started':
                # Create batch record
                wo_id = data.get('work_order_id', '')
                batch_id = f"BATCH-{wo_id}"

                with self._lock:
                    self._batches[batch_id] = BatchRecord(
                        batch_id=batch_id,
                        work_order_id=wo_id,
                        part_id=data.get('part_id', ''),
                        batch_start=time.time(),
                    )

            elif event_type == 'work_order_completed':
                wo_id = data.get('work_order_id', '')
                batch_id = f"BATCH-{wo_id}"

                with self._lock:
                    if batch_id in self._batches:
                        batch = self._batches[batch_id]
                        batch.batch_end = time.time()
                        batch.status = 'complete'

        except json.JSONDecodeError:
            pass

    def _on_inspection_result(self, msg: String):
        """Handle inspection results."""
        try:
            data = json.loads(msg.data)
            serial_number = data.get('serial_number', '')

            if not serial_number or serial_number not in self._parts:
                return

            with self._lock:
                part = self._parts[serial_number]
                part.inspection_results.append(data)

                if data.get('passed', True):
                    self._record_event(
                        serial_number,
                        EventType.INSPECTION_PASS,
                        data,
                        source_node='inspection_server'
                    )
                    part.quality_status = 'pass'
                else:
                    self._record_event(
                        serial_number,
                        EventType.INSPECTION_FAIL,
                        data,
                        source_node='inspection_server'
                    )
                    part.quality_status = 'fail'

        except json.JSONDecodeError:
            pass

    def _on_defect_detected(self, msg: String):
        """Handle defect detection."""
        try:
            data = json.loads(msg.data)
            serial_number = data.get('serial_number', '')

            if not serial_number or serial_number not in self._parts:
                return

            with self._lock:
                part = self._parts[serial_number]
                part.defects_found.append(data.get('defect', {}))

                self._record_event(
                    serial_number,
                    EventType.DEFECT_FOUND,
                    data,
                    source_node='inspection_server'
                )

        except json.JSONDecodeError:
            pass

    def _on_job_dispatch(self, msg: String):
        """Handle job dispatch - create part record if needed."""
        try:
            data = json.loads(msg.data)
            wo_id = data.get('work_order_id', '')
            part_id = data.get('part_id', '')
            equipment_id = data.get('equipment_id', '')

            # Create part record for each dispatched job
            batch_id = f"BATCH-{wo_id}"
            part = self._create_part(part_id, wo_id, batch_id)

            # Record operation start
            self._record_event(
                part.serial_number,
                EventType.OPERATION_START,
                {
                    'equipment_id': equipment_id,
                    'job_id': data.get('job_id', ''),
                }
            )

            with self._lock:
                part.equipment_used.append(equipment_id)
                part.manufacturing_start = time.time()

        except json.JSONDecodeError:
            pass

    def _verify_hash_chain(self, serial_number: str) -> Tuple[bool, str]:
        """Verify hash chain integrity for a part."""
        if serial_number not in self._parts:
            return False, "Part not found"

        part = self._parts[serial_number]

        if not part.event_chain:
            return True, "No events to verify"

        previous_hash = ""
        for event_id in part.event_chain:
            if event_id not in self._events:
                return False, f"Missing event: {event_id}"

            event = self._events[event_id]

            # Verify previous hash link
            if event.previous_hash != previous_hash:
                return False, f"Chain broken at {event_id}"

            # Verify event hash
            computed_hash = event.compute_hash()
            if computed_hash != event.event_hash:
                return False, f"Hash mismatch at {event_id}"

            previous_hash = event.event_hash

        return True, "Chain verified successfully"

    def _trace_forward(self, serial_number: str) -> List[str]:
        """Trace forward: where did this part go?"""
        result = []

        with self._lock:
            if serial_number not in self._parts:
                return result

            part = self._parts[serial_number]

            # Check if used in assembly
            if part.parent_assembly:
                result.append(part.parent_assembly)
                # Recursively trace forward
                result.extend(self._trace_forward(part.parent_assembly))

        return result

    def _trace_backward(self, serial_number: str) -> List[str]:
        """Trace backward: where did components come from?"""
        result = []

        with self._lock:
            if serial_number not in self._parts:
                return result

            part = self._parts[serial_number]

            # Get child components
            for child_sn in part.child_components:
                result.append(child_sn)
                # Recursively trace backward
                result.extend(self._trace_backward(child_sn))

        return result

    # Service callbacks

    def _create_part_callback(self, request, response):
        """Handle create part service request."""
        # Would parse part_id, work_order_id from request
        part = self._create_part(
            part_id="BRICK-2x4",
            work_order_id="WO-TEST",
        )

        response.success = True
        response.message = json.dumps({
            'serial_number': part.serial_number,
            'created': True,
        })
        return response

    def _get_part_callback(self, request, response):
        """Handle get part service request."""
        # Would parse serial_number from request
        # For demo, return first part
        with self._lock:
            if self._parts:
                part = next(iter(self._parts.values()))
                response.success = True
                response.message = json.dumps(asdict(part))
            else:
                response.success = False
                response.message = "No parts found"

        return response

    def _get_history_callback(self, request, response):
        """Handle get history service request."""
        # Would parse serial_number from request
        with self._lock:
            if self._parts:
                sn = next(iter(self._parts.keys()))
                part = self._parts[sn]

                history = []
                for event_id in part.event_chain:
                    if event_id in self._events:
                        event = self._events[event_id]
                        history.append({
                            'event_id': event.event_id,
                            'event_type': event.event_type.value,
                            'timestamp': event.timestamp,
                            'data': event.data,
                        })

                response.success = True
                response.message = json.dumps({
                    'serial_number': sn,
                    'event_count': len(history),
                    'events': history,
                })
            else:
                response.success = False
                response.message = "No parts found"

        return response

    def _verify_chain_callback(self, request, response):
        """Handle verify chain service request."""
        with self._lock:
            if self._parts:
                sn = next(iter(self._parts.keys()))
                valid, message = self._verify_hash_chain(sn)

                response.success = True
                response.message = json.dumps({
                    'serial_number': sn,
                    'valid': valid,
                    'message': message,
                })
            else:
                response.success = False
                response.message = "No parts to verify"

        return response

    def _trace_forward_callback(self, request, response):
        """Handle trace forward service request."""
        with self._lock:
            if self._parts:
                sn = next(iter(self._parts.keys()))
                trace = self._trace_forward(sn)

                response.success = True
                response.message = json.dumps({
                    'serial_number': sn,
                    'forward_trace': trace,
                })
            else:
                response.success = False
                response.message = "No parts found"

        return response

    def _trace_backward_callback(self, request, response):
        """Handle trace backward service request."""
        with self._lock:
            if self._parts:
                sn = next(iter(self._parts.keys()))
                trace = self._trace_backward(sn)

                response.success = True
                response.message = json.dumps({
                    'serial_number': sn,
                    'backward_trace': trace,
                })
            else:
                response.success = False
                response.message = "No parts found"

        return response

    def _initiate_recall_callback(self, request, response):
        """Handle recall initiation."""
        # Would parse affected serial numbers/batches
        # Mark affected parts and trace impact

        with self._lock:
            affected_count = 0
            for sn, part in self._parts.items():
                # In real implementation, would filter by criteria
                if part.status != 'recalled':
                    self._record_event(
                        sn,
                        EventType.RECALL,
                        {'reason': 'Service requested recall'},
                    )
                    part.status = 'recalled'
                    affected_count += 1

        response.success = True
        response.message = json.dumps({
            'recall_initiated': True,
            'affected_parts': affected_count,
        })
        return response

    def _get_statistics_callback(self, request, response):
        """Handle statistics request."""
        with self._lock:
            stats = {
                'total_parts': len(self._parts),
                'total_events': len(self._events),
                'total_batches': len(self._batches),
                'parts_by_status': defaultdict(int),
                'quality_status': defaultdict(int),
            }

            for part in self._parts.values():
                stats['parts_by_status'][part.status] += 1
                stats['quality_status'][part.quality_status] += 1

            # Convert defaultdict to regular dict for JSON
            stats['parts_by_status'] = dict(stats['parts_by_status'])
            stats['quality_status'] = dict(stats['quality_status'])

        response.success = True
        response.message = json.dumps(stats)
        return response


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = TraceabilityNode()

    executor = MultiThreadedExecutor(num_threads=4)
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
