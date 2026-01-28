"""
LEGO Factory v3 - ROS2 Bridge Service
=====================================
WebSocket bridge to communicate with ROS2 via rosbridge_suite.
"""

import json
import threading
import time
import logging
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import websocket, gracefully handle if not available
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logger.warning("websocket-client not installed. ROS2 bridge will run in simulation mode.")


class ConnectionState(Enum):
    DISCONNECTED = 'disconnected'
    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    ERROR = 'error'


@dataclass
class ROS2Topic:
    """ROS2 topic subscription"""
    name: str
    msg_type: str
    callback: Callable[[Dict], None]
    queue_size: int = 10


@dataclass
class ROS2Service:
    """ROS2 service"""
    name: str
    srv_type: str


class ROS2Bridge:
    """
    Bridge to ROS2 via rosbridge WebSocket.
    
    Connects to rosbridge_server running on the ROS2 side and provides
    methods to subscribe to topics, call services, and publish messages.
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, host: str = "localhost", port: int = 9090):
        if self._initialized:
            return
            
        self.host = host
        self.port = port
        self.url = f"ws://{host}:{port}"
        
        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._state = ConnectionState.DISCONNECTED
        self._lock = threading.Lock()
        
        self._subscriptions: Dict[str, ROS2Topic] = {}
        self._service_results: Dict[str, Any] = {}
        self._service_events: Dict[str, threading.Event] = {}
        self._message_id = 0
        
        self._status_callbacks: List[Callable[[ConnectionState], None]] = []
        self._simulation_mode = not WEBSOCKET_AVAILABLE
        
        self._initialized = True
        logger.info(f"ROS2Bridge initialized for {self.url}")
    
    @property
    def state(self) -> ConnectionState:
        return self._state
    
    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED
    
    def connect(self) -> bool:
        """Connect to rosbridge server."""
        if self._simulation_mode:
            logger.info("ROS2Bridge running in simulation mode")
            self._state = ConnectionState.CONNECTED
            self._notify_status()
            return True
            
        if self._state == ConnectionState.CONNECTED:
            return True
            
        self._state = ConnectionState.CONNECTING
        self._notify_status()
        
        try:
            self._ws = websocket.WebSocketApp(
                self.url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            self._ws_thread = threading.Thread(
                target=self._ws.run_forever,
                daemon=True
            )
            self._ws_thread.start()
            
            # Wait for connection
            timeout = 5.0
            start = time.time()
            while self._state == ConnectionState.CONNECTING and time.time() - start < timeout:
                time.sleep(0.1)
            
            return self._state == ConnectionState.CONNECTED
            
        except Exception as e:
            logger.error(f"Failed to connect to rosbridge: {e}")
            self._state = ConnectionState.ERROR
            self._notify_status()
            return False
    
    def disconnect(self):
        """Disconnect from rosbridge server."""
        if self._ws:
            self._ws.close()
        self._state = ConnectionState.DISCONNECTED
        self._notify_status()
    
    def subscribe(self, topic: str, msg_type: str, callback: Callable[[Dict], None], queue_size: int = 10):
        """Subscribe to a ROS2 topic."""
        with self._lock:
            self._subscriptions[topic] = ROS2Topic(topic, msg_type, callback, queue_size)
        
        if self.is_connected and not self._simulation_mode:
            self._send_subscribe(topic, msg_type, queue_size)
        
        logger.info(f"Subscribed to {topic}")
    
    def unsubscribe(self, topic: str):
        """Unsubscribe from a ROS2 topic."""
        with self._lock:
            if topic in self._subscriptions:
                del self._subscriptions[topic]
        
        if self.is_connected and not self._simulation_mode:
            msg = {
                "op": "unsubscribe",
                "topic": topic
            }
            self._send(msg)
        
        logger.info(f"Unsubscribed from {topic}")
    
    def publish(self, topic: str, msg_type: str, msg: Dict):
        """Publish a message to a ROS2 topic."""
        if self._simulation_mode:
            logger.debug(f"[SIM] Publishing to {topic}: {msg}")
            return
            
        if not self.is_connected:
            logger.warning(f"Cannot publish to {topic}: not connected")
            return
        
        message = {
            "op": "publish",
            "topic": topic,
            "type": msg_type,
            "msg": msg
        }
        self._send(message)
    
    def call_service(self, service: str, srv_type: str, args: Dict = None, timeout: float = 10.0) -> Optional[Dict]:
        """Call a ROS2 service and wait for response."""
        if self._simulation_mode:
            logger.debug(f"[SIM] Calling service {service} with {args}")
            # Return simulated success response
            return {"success": True, "message": "Simulation mode"}
            
        if not self.is_connected:
            logger.warning(f"Cannot call service {service}: not connected")
            return None
        
        with self._lock:
            self._message_id += 1
            msg_id = f"call_service:{self._message_id}"
        
        event = threading.Event()
        self._service_events[msg_id] = event
        
        message = {
            "op": "call_service",
            "id": msg_id,
            "service": service,
            "type": srv_type,
            "args": args or {}
        }
        self._send(message)
        
        # Wait for response
        if event.wait(timeout):
            result = self._service_results.pop(msg_id, None)
            del self._service_events[msg_id]
            return result
        else:
            logger.warning(f"Service call to {service} timed out")
            del self._service_events[msg_id]
            return None
    
    def on_status_change(self, callback: Callable[[ConnectionState], None]):
        """Register callback for connection status changes."""
        self._status_callbacks.append(callback)
    
    def _send(self, msg: Dict):
        """Send message to rosbridge."""
        if self._ws and self.is_connected:
            try:
                self._ws.send(json.dumps(msg))
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
    
    def _send_subscribe(self, topic: str, msg_type: str, queue_size: int):
        """Send subscribe message."""
        msg = {
            "op": "subscribe",
            "topic": topic,
            "type": msg_type,
            "queue_length": queue_size
        }
        self._send(msg)
    
    def _on_open(self, ws):
        """WebSocket opened callback."""
        logger.info(f"Connected to rosbridge at {self.url}")
        self._state = ConnectionState.CONNECTED
        self._notify_status()
        
        # Re-subscribe to topics
        with self._lock:
            for topic, sub in self._subscriptions.items():
                self._send_subscribe(topic, sub.msg_type, sub.queue_size)
    
    def _on_message(self, ws, message):
        """WebSocket message received callback."""
        try:
            data = json.loads(message)
            op = data.get("op")
            
            if op == "publish":
                # Topic message
                topic = data.get("topic")
                if topic in self._subscriptions:
                    self._subscriptions[topic].callback(data.get("msg", {}))
            
            elif op == "service_response":
                # Service response
                msg_id = data.get("id")
                if msg_id in self._service_events:
                    self._service_results[msg_id] = data.get("values")
                    self._service_events[msg_id].set()
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _on_error(self, ws, error):
        """WebSocket error callback."""
        logger.error(f"WebSocket error: {error}")
        self._state = ConnectionState.ERROR
        self._notify_status()
    
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket closed callback."""
        logger.info(f"Disconnected from rosbridge: {close_msg}")
        self._state = ConnectionState.DISCONNECTED
        self._notify_status()
    
    def _notify_status(self):
        """Notify status change callbacks."""
        for callback in self._status_callbacks:
            try:
                callback(self._state)
            except Exception as e:
                logger.error(f"Status callback error: {e}")

    def get_robot_state(self, robot_id: str) -> Optional[Dict]:
        """Get the current state of a robot."""
        if self._simulation_mode:
            # Return simulated state
            return {
                'robot_id': robot_id,
                'connected': True,
                'state': 'idle',
                'position': {'x': 0.0, 'y': 0.0, 'z': 0.0},
                'joints': [0.0] * 6,
                'gripper_open': True,
            }

        # Call ROS2 service to get robot state
        result = self.call_service(
            f'/robot/{robot_id}/get_state',
            'std_srvs/srv/Trigger',
            {}
        )
        return result


# Global instance
_ros2_bridge: Optional[ROS2Bridge] = None


def get_ros2_bridge(host: str = "localhost", port: int = 9090) -> ROS2Bridge:
    """Get the global ROS2Bridge instance."""
    global _ros2_bridge
    if _ros2_bridge is None:
        _ros2_bridge = ROS2Bridge(host, port)
    return _ros2_bridge
