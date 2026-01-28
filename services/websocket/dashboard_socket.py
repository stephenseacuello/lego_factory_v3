"""
LEGO Factory v3 - Dashboard WebSocket Namespace
================================================
Namespace handler for web dashboard real-time updates.

Events (Server -> Client):
- tag_value: Real-time tag value updates
- alarm_triggered: New alarm notification
- alarm_cleared: Alarm cleared notification
- work_order_update: Work order status change
- oee_update: OEE metrics update
- machine_status: Machine status change
- kpi_update: KPI dashboard updates

Events (Client -> Server):
- subscribe_tags: Subscribe to tag groups
- unsubscribe_tags: Unsubscribe from tag groups
- subscribe_machine: Subscribe to machine updates
- subscribe_area: Subscribe to area updates
- request_dashboard_data: Request dashboard initial data
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Set, List

from flask import request, session
from flask_socketio import Namespace, emit, join_room, leave_room

from services.websocket.socket_service import connection_manager

logger = logging.getLogger(__name__)


class DashboardNamespace(Namespace):
    """
    WebSocket namespace for web dashboard updates.

    Provides real-time updates for:
    - Tag values (grouped subscriptions)
    - Alarms
    - Work orders
    - OEE metrics
    - Machine status
    """

    def __init__(self, namespace: str = '/dashboard'):
        super().__init__(namespace)
        # Track tag subscriptions per client
        self._tag_subscriptions: Dict[str, Set[str]] = {}
        # Track area subscriptions per client
        self._area_subscriptions: Dict[str, Set[str]] = {}
        # Track machine subscriptions per client
        self._machine_subscriptions: Dict[str, Set[str]] = {}
        # Dashboard client metadata
        self._dashboard_clients: Dict[str, Dict[str, Any]] = {}

    def on_connect(self):
        """Handle dashboard client connection."""
        sid = request.sid
        user_id = session.get('user_id')
        user_role = session.get('role', 'viewer')

        # Register with connection manager
        connection_manager.register_client(
            sid=sid,
            namespace='/dashboard',
            user_id=user_id,
            metadata={
                'ip': request.remote_addr,
                'client_type': 'dashboard',
                'role': user_role,
            }
        )

        # Initialize subscriptions
        self._tag_subscriptions[sid] = set()
        self._area_subscriptions[sid] = set()
        self._machine_subscriptions[sid] = set()

        # Store dashboard-specific metadata
        self._dashboard_clients[sid] = {
            'user_id': user_id,
            'role': user_role,
            'connected_at': datetime.utcnow().isoformat(),
            'active_dashboard': None,
        }

        # Send connection acknowledgment
        emit('connection_ack', {
            'status': 'connected',
            'sid': sid,
            'namespace': '/dashboard',
            'role': user_role,
            'timestamp': datetime.utcnow().isoformat(),
        })

        # Auto-join dashboard room
        join_room('dashboard')
        connection_manager.join_room(sid, 'dashboard')

        # Auto-join role-based room
        if user_role:
            join_room(f"role:{user_role}")
            connection_manager.join_room(sid, f"role:{user_role}")

        logger.info(f"Dashboard client connected: {sid} (role: {user_role})")

    def on_disconnect(self):
        """Handle dashboard client disconnection."""
        sid = request.sid

        # Clean up subscriptions
        self._tag_subscriptions.pop(sid, None)
        self._area_subscriptions.pop(sid, None)
        self._machine_subscriptions.pop(sid, None)
        self._dashboard_clients.pop(sid, None)

        # Unregister from connection manager
        connection_manager.unregister_client(sid, '/dashboard')

        logger.info(f"Dashboard client disconnected: {sid}")

    def on_subscribe_tags(self, data: Dict[str, Any]):
        """
        Subscribe to tag value updates.

        Args:
            data: {
                'tag_ids': list of tag IDs,
                'tag_group': str (optional, predefined group name),
                'area': str (optional, subscribe to all tags in area),
                'update_interval': int (optional, ms between updates),
            }
        """
        sid = request.sid

        if sid not in self._tag_subscriptions:
            self._tag_subscriptions[sid] = set()

        tag_ids = data.get('tag_ids', [])
        tag_group = data.get('tag_group')
        area = data.get('area')

        # Handle predefined tag groups
        if tag_group:
            tag_ids.extend(self._get_tag_group(tag_group))

        # Handle area-based subscription
        if area:
            tag_ids.extend(self._get_area_tags(area))

        # Subscribe to tags
        for tag_id in tag_ids:
            self._tag_subscriptions[sid].add(tag_id)
            join_room(f"tag:{tag_id}")

        # Join group room if specified
        if tag_group:
            join_room(f"taggroup:{tag_group}")

        emit('subscribe_tags_ack', {
            'tag_ids': tag_ids,
            'tag_group': tag_group,
            'subscribed': True,
            'total_subscriptions': len(self._tag_subscriptions[sid]),
        })

        # Send current values for subscribed tags
        self._send_current_tag_values(sid, tag_ids)

        logger.debug(f"Client {sid} subscribed to {len(tag_ids)} tags")

    def on_unsubscribe_tags(self, data: Dict[str, Any]):
        """
        Unsubscribe from tag value updates.

        Args:
            data: {
                'tag_ids': list of tag IDs,
                'tag_group': str (optional),
                'all': bool (unsubscribe from all)
            }
        """
        sid = request.sid

        if sid not in self._tag_subscriptions:
            return

        if data.get('all'):
            # Unsubscribe from all tags
            for tag_id in self._tag_subscriptions[sid]:
                leave_room(f"tag:{tag_id}")
            self._tag_subscriptions[sid] = set()
        else:
            tag_ids = data.get('tag_ids', [])
            tag_group = data.get('tag_group')

            if tag_group:
                tag_ids.extend(self._get_tag_group(tag_group))
                leave_room(f"taggroup:{tag_group}")

            for tag_id in tag_ids:
                self._tag_subscriptions[sid].discard(tag_id)
                leave_room(f"tag:{tag_id}")

        emit('unsubscribe_tags_ack', {
            'subscribed': False,
            'total_subscriptions': len(self._tag_subscriptions[sid]),
        })

    def on_subscribe_machine(self, data: Dict[str, Any]):
        """
        Subscribe to machine status updates.

        Args:
            data: {
                'machine_id': str or list,
            }
        """
        sid = request.sid

        if sid not in self._machine_subscriptions:
            self._machine_subscriptions[sid] = set()

        machine_ids = data.get('machine_id', [])
        if isinstance(machine_ids, str):
            machine_ids = [machine_ids]

        for machine_id in machine_ids:
            self._machine_subscriptions[sid].add(machine_id)
            join_room(f"machine:{machine_id}")

        emit('subscribe_machine_ack', {
            'machine_ids': machine_ids,
            'subscribed': True,
        })

        logger.debug(f"Client {sid} subscribed to machines: {machine_ids}")

    def on_subscribe_area(self, data: Dict[str, Any]):
        """
        Subscribe to area updates (all machines and tags in area).

        Args:
            data: {
                'area': str,
            }
        """
        sid = request.sid
        area = data.get('area')

        if not area:
            emit('error', {'message': 'area required'})
            return

        if sid not in self._area_subscriptions:
            self._area_subscriptions[sid] = set()

        self._area_subscriptions[sid].add(area)
        join_room(f"area:{area}")

        emit('subscribe_area_ack', {
            'area': area,
            'subscribed': True,
        })

        logger.debug(f"Client {sid} subscribed to area: {area}")

    def on_request_dashboard_data(self, data: Dict[str, Any] = None):
        """
        Request initial dashboard data.

        Args:
            data: {
                'dashboard_type': str (scada, mes, oee, etc.),
                'area': str (optional),
            }
        """
        sid = request.sid
        data = data or {}
        dashboard_type = data.get('dashboard_type', 'overview')

        try:
            dashboard_data = self._get_dashboard_data(dashboard_type, data)

            emit('dashboard_data', {
                'dashboard_type': dashboard_type,
                'data': dashboard_data,
                'timestamp': datetime.utcnow().isoformat(),
            })

            # Update client metadata
            if sid in self._dashboard_clients:
                self._dashboard_clients[sid]['active_dashboard'] = dashboard_type

        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            emit('error', {
                'code': 'DATA_ERROR',
                'message': str(e),
            })

    def on_ping(self):
        """Handle ping request."""
        emit('pong', {
            'timestamp': datetime.utcnow().isoformat(),
            'namespace': '/dashboard',
        })

    # Helper methods

    def _get_tag_group(self, group_name: str) -> List[str]:
        """Get tag IDs for a predefined group."""
        # Predefined tag groups
        groups = {
            'printers': [
                'printer_1.temperature', 'printer_1.progress', 'printer_1.status',
                'printer_2.temperature', 'printer_2.progress', 'printer_2.status',
                'printer_3.temperature', 'printer_3.progress', 'printer_3.status',
            ],
            'robots': [
                'niryo_ned2.joint_1', 'niryo_ned2.joint_2', 'niryo_ned2.joint_3',
                'niryo_ned2.joint_4', 'niryo_ned2.joint_5', 'niryo_ned2.joint_6',
                'niryo_ned2.status', 'niryo_ned2.gripper',
            ],
            'environment': [
                'env.temperature', 'env.humidity', 'env.pressure',
            ],
            'production': [
                'production.count', 'production.reject_count', 'production.rate',
            ],
        }
        return groups.get(group_name, [])

    def _get_area_tags(self, area: str) -> List[str]:
        """Get all tag IDs for an area."""
        try:
            from services.scada.tag_management.tag_service import get_tag_service
            from config.database import get_db_session

            with get_db_session() as session:
                service = get_tag_service(session)
                tags = service.get_tags(area=area, limit=500)
                return [t['tag_id'] for t in tags]
        except Exception as e:
            logger.error(f"Error getting area tags: {e}")
            return []

    def _send_current_tag_values(self, sid: str, tag_ids: List[str]):
        """Send current values for subscribed tags."""
        try:
            from services.scada.tag_management.tag_service import tag_cache
            import asyncio

            # Get current values from cache
            loop = asyncio.new_event_loop()
            values = loop.run_until_complete(tag_cache.get_many(tag_ids))
            loop.close()

            if values:
                tag_values = {
                    tag_id: {
                        'value': tv.value,
                        'quality': tv.quality,
                        'timestamp': tv.timestamp.isoformat() if tv.timestamp else None,
                    }
                    for tag_id, tv in values.items()
                }

                emit('tag_values_initial', {
                    'values': tag_values,
                    'timestamp': datetime.utcnow().isoformat(),
                }, room=sid)

        except Exception as e:
            logger.error(f"Error sending initial tag values: {e}")

    def _get_dashboard_data(self, dashboard_type: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get initial data for a dashboard type."""
        data = {}

        try:
            if dashboard_type == 'overview':
                data = self._get_overview_data()
            elif dashboard_type == 'scada':
                data = self._get_scada_data(filters)
            elif dashboard_type == 'mes':
                data = self._get_mes_data(filters)
            elif dashboard_type == 'oee':
                data = self._get_oee_data(filters)
            elif dashboard_type == 'alarms':
                data = self._get_alarms_data(filters)
        except Exception as e:
            logger.error(f"Error getting {dashboard_type} data: {e}")

        return data

    def _get_overview_data(self) -> Dict[str, Any]:
        """Get factory overview data."""
        return {
            'machines': {'total': 5, 'running': 3, 'idle': 1, 'error': 1},
            'production': {'today': 150, 'target': 200, 'rate': 75.0},
            'alarms': {'active': 2, 'unacked': 1},
            'oee': {'availability': 85.0, 'performance': 92.0, 'quality': 98.5},
        }

    def _get_scada_data(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get SCADA dashboard data."""
        return {
            'tags_count': 50,
            'active_alarms': 2,
            'machines': [],
        }

    def _get_mes_data(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get MES dashboard data."""
        return {
            'work_orders': [],
            'production_summary': {},
        }

    def _get_oee_data(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get OEE dashboard data."""
        return {
            'oee': 78.3,
            'availability': 85.0,
            'performance': 92.0,
            'quality': 98.5,
            'trend': [],
        }

    def _get_alarms_data(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get alarms dashboard data."""
        try:
            from services.scada.alarm_management.alarm_service import get_alarm_service
            from config.database import get_db_session

            with get_db_session() as session:
                service = get_alarm_service(session)
                active = service.get_active_alarms()
                summary = service.get_alarm_summary()

                return {
                    'active_alarms': active,
                    'summary': {
                        'total_active': summary.total_active,
                        'unacknowledged': summary.unacknowledged,
                        'by_priority': summary.by_priority,
                    },
                }
        except Exception as e:
            logger.error(f"Error getting alarms data: {e}")
            return {}


# Global namespace instance
_dashboard_namespace: Optional[DashboardNamespace] = None


def get_dashboard_namespace() -> Optional[DashboardNamespace]:
    """Get dashboard namespace instance."""
    return _dashboard_namespace


def set_dashboard_namespace(namespace: DashboardNamespace):
    """Set dashboard namespace instance."""
    global _dashboard_namespace
    _dashboard_namespace = namespace


# Convenience functions for emitting events

def emit_tag_value(tag_id: str, value: Any, quality: int = 192, timestamp: datetime = None):
    """Emit tag value update to subscribed clients."""
    from services.websocket.socket_service import emit_to_room

    emit_to_room(
        'tag_value',
        {
            'tag_id': tag_id,
            'value': value,
            'quality': quality,
            'timestamp': (timestamp or datetime.utcnow()).isoformat(),
        },
        f"tag:{tag_id}",
        '/dashboard'
    )


def emit_alarm_triggered(alarm_data: Dict[str, Any]):
    """Emit alarm triggered notification to dashboard clients."""
    from services.websocket.socket_service import emit_to_room

    emit_to_room(
        'alarm_triggered',
        {
            **alarm_data,
            'timestamp': datetime.utcnow().isoformat(),
        },
        'dashboard',
        '/dashboard'
    )


def emit_alarm_cleared(alarm_data: Dict[str, Any]):
    """Emit alarm cleared notification to dashboard clients."""
    from services.websocket.socket_service import emit_to_room

    emit_to_room(
        'alarm_cleared',
        {
            **alarm_data,
            'timestamp': datetime.utcnow().isoformat(),
        },
        'dashboard',
        '/dashboard'
    )


def emit_work_order_update(work_order_data: Dict[str, Any]):
    """Emit work order update to dashboard clients."""
    from services.websocket.socket_service import emit_to_room

    emit_to_room(
        'work_order_update',
        {
            **work_order_data,
            'timestamp': datetime.utcnow().isoformat(),
        },
        'dashboard',
        '/dashboard'
    )


def emit_oee_update(oee_data: Dict[str, Any]):
    """Emit OEE metrics update to dashboard clients."""
    from services.websocket.socket_service import emit_to_room

    emit_to_room(
        'oee_update',
        {
            **oee_data,
            'timestamp': datetime.utcnow().isoformat(),
        },
        'dashboard',
        '/dashboard'
    )


def emit_machine_status(machine_id: str, status: str, details: Dict[str, Any] = None):
    """Emit machine status change to subscribed clients."""
    from services.websocket.socket_service import emit_to_room

    emit_to_room(
        'machine_status',
        {
            'machine_id': machine_id,
            'status': status,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat(),
        },
        f"machine:{machine_id}",
        '/dashboard'
    )

    # Also emit to general dashboard room
    emit_to_room(
        'machine_status',
        {
            'machine_id': machine_id,
            'status': status,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat(),
        },
        'dashboard',
        '/dashboard'
    )


def emit_kpi_update(kpi_data: Dict[str, Any]):
    """Emit KPI update to dashboard clients."""
    from services.websocket.socket_service import emit_to_room

    emit_to_room(
        'kpi_update',
        {
            **kpi_data,
            'timestamp': datetime.utcnow().isoformat(),
        },
        'dashboard',
        '/dashboard'
    )


def emit_to_area(area: str, event: str, data: Dict[str, Any]):
    """Emit event to all clients subscribed to an area."""
    from services.websocket.socket_service import emit_to_room

    emit_to_room(
        event,
        {
            'area': area,
            **data,
            'timestamp': datetime.utcnow().isoformat(),
        },
        f"area:{area}",
        '/dashboard'
    )
