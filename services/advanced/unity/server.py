"""
Unity WebSocket Server Entry Point

LegoMCP World-Class Manufacturing Platform v2.0
ISO 23247 Compliant Digital Twin Visualization

Standalone server for Unity client connections:
- WebSocket server for real-time updates
- REST API for scene data
- Multi-client support (WebGL, Desktop, VR, AR)

Usage:
    python -m dashboard.services.unity.server

Author: LegoMCP Team
Version: 2.0.0
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Dict, Set, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import required packages
try:
    import websockets
    from websockets.server import serve
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets package not installed. Install with: pip install websockets")

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning("aiohttp package not installed. Install with: pip install aiohttp")

# Import Unity services
try:
    from .bridge import UnityBridge, get_unity_bridge, MessageType, SubscriptionRoom
    from .scene_data import SceneDataService, get_scene_data_service
    UNITY_SERVICES_AVAILABLE = True
except ImportError as e:
    UNITY_SERVICES_AVAILABLE = False
    logger.warning(f"Unity services not available: {e}")


class UnityWebSocketServer:
    """
    WebSocket server for Unity clients.

    Handles:
    - Client connections and authentication
    - Real-time state streaming
    - Subscription management
    - Graceful shutdown
    """

    def __init__(
        self,
        ws_host: str = "0.0.0.0",
        ws_port: int = 8770,
        api_port: int = 8771
    ):
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.api_port = api_port

        # Connected clients
        self.clients: Set[Any] = set()
        self.client_info: Dict[str, Dict[str, Any]] = {}

        # Services
        self.bridge: Optional[UnityBridge] = None
        self.scene_service: Optional[SceneDataService] = None

        # Server state
        self.running = False
        self.ws_server = None
        self.api_app = None

        # Statistics
        self.stats = {
            "connections_total": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
            "start_time": None,
        }

    async def initialize(self) -> None:
        """Initialize services."""
        if UNITY_SERVICES_AVAILABLE:
            self.bridge = get_unity_bridge()
            self.scene_service = get_scene_data_service()
            logger.info("Unity services initialized")
        else:
            logger.warning("Running without Unity services")

    async def handle_client(self, websocket, path: str) -> None:
        """Handle a WebSocket client connection."""
        client_id = f"client_{len(self.clients)}_{datetime.utcnow().timestamp()}"

        try:
            # Register client
            self.clients.add(websocket)
            self.client_info[client_id] = {
                "websocket": websocket,
                "connected_at": datetime.utcnow().isoformat(),
                "subscriptions": [],
                "client_type": "unknown",
                "path": path,
            }
            self.stats["connections_total"] += 1

            logger.info(f"Client connected: {client_id} from {websocket.remote_address}")

            # Send welcome message
            await self.send_to_client(websocket, {
                "type": "connected",
                "client_id": client_id,
                "server_version": "2.0.0",
                "timestamp": datetime.utcnow().isoformat(),
            })

            # Handle messages
            async for message in websocket:
                await self.handle_message(client_id, websocket, message)

        except Exception as e:
            logger.error(f"Client error {client_id}: {e}")
            self.stats["errors"] += 1
        finally:
            # Cleanup
            self.clients.discard(websocket)
            if client_id in self.client_info:
                del self.client_info[client_id]
            logger.info(f"Client disconnected: {client_id}")

    async def handle_message(
        self,
        client_id: str,
        websocket: Any,
        message: str
    ) -> None:
        """Handle incoming message from client."""
        self.stats["messages_received"] += 1

        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")

            if msg_type == "subscribe":
                await self.handle_subscribe(client_id, websocket, data)
            elif msg_type == "unsubscribe":
                await self.handle_unsubscribe(client_id, data)
            elif msg_type == "get_scene":
                await self.handle_get_scene(websocket)
            elif msg_type == "get_equipment":
                await self.handle_get_equipment(websocket, data)
            elif msg_type == "command":
                await self.handle_command(client_id, websocket, data)
            elif msg_type == "ping":
                await self.send_to_client(websocket, {"type": "pong"})
            elif msg_type == "client_info":
                await self.handle_client_info(client_id, data)
            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from {client_id}")
            await self.send_to_client(websocket, {
                "type": "error",
                "message": "Invalid JSON"
            })

    async def handle_subscribe(
        self,
        client_id: str,
        websocket: Any,
        data: Dict[str, Any]
    ) -> None:
        """Handle subscription request."""
        room = data.get("room", "equipment_updates")

        if client_id in self.client_info:
            if room not in self.client_info[client_id]["subscriptions"]:
                self.client_info[client_id]["subscriptions"].append(room)

        await self.send_to_client(websocket, {
            "type": "subscribed",
            "room": room,
        })

        logger.info(f"Client {client_id} subscribed to {room}")

    async def handle_unsubscribe(
        self,
        client_id: str,
        data: Dict[str, Any]
    ) -> None:
        """Handle unsubscription request."""
        room = data.get("room")

        if client_id in self.client_info:
            subs = self.client_info[client_id]["subscriptions"]
            if room in subs:
                subs.remove(room)

    async def handle_get_scene(self, websocket: Any) -> None:
        """Handle scene data request."""
        if self.scene_service:
            scene_state = self.scene_service.get_full_scene()
        else:
            scene_state = {
                "equipment": [],
                "timestamp": datetime.utcnow().isoformat(),
            }

        await self.send_to_client(websocket, {
            "type": "scene_state",
            "data": scene_state,
        })

    async def handle_get_equipment(
        self,
        websocket: Any,
        data: Dict[str, Any]
    ) -> None:
        """Handle equipment data request."""
        equipment_id = data.get("equipment_id")

        if self.scene_service and equipment_id:
            equipment = self.scene_service.get_equipment_state(equipment_id)
            await self.send_to_client(websocket, {
                "type": "equipment_state",
                "equipment_id": equipment_id,
                "data": equipment,
            })
        else:
            await self.send_to_client(websocket, {
                "type": "error",
                "message": "Equipment not found",
            })

    async def handle_command(
        self,
        client_id: str,
        websocket: Any,
        data: Dict[str, Any]
    ) -> None:
        """Handle command from Unity client."""
        command = data.get("command")
        target = data.get("target")
        params = data.get("params", {})

        logger.info(f"Command from {client_id}: {command} -> {target}")

        # Acknowledge command
        await self.send_to_client(websocket, {
            "type": "command_ack",
            "command": command,
            "status": "received",
        })

    async def handle_client_info(
        self,
        client_id: str,
        data: Dict[str, Any]
    ) -> None:
        """Handle client info update."""
        if client_id in self.client_info:
            self.client_info[client_id]["client_type"] = data.get("client_type", "unknown")
            self.client_info[client_id]["platform"] = data.get("platform")
            self.client_info[client_id]["version"] = data.get("version")

    async def send_to_client(
        self,
        websocket: Any,
        data: Dict[str, Any]
    ) -> None:
        """Send message to a client."""
        try:
            await websocket.send(json.dumps(data))
            self.stats["messages_sent"] += 1
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    async def broadcast(
        self,
        data: Dict[str, Any],
        room: Optional[str] = None
    ) -> None:
        """Broadcast message to all or subscribed clients."""
        message = json.dumps(data)

        for client_id, info in self.client_info.items():
            if room is None or room in info.get("subscriptions", []):
                try:
                    await info["websocket"].send(message)
                    self.stats["messages_sent"] += 1
                except Exception as e:
                    logger.error(f"Broadcast error to {client_id}: {e}")

    async def start_update_loop(self) -> None:
        """Start the periodic update loop."""
        update_interval = float(os.getenv("TWIN_SYNC_INTERVAL_MS", "100")) / 1000.0

        while self.running:
            try:
                # Get current state
                if self.scene_service:
                    state = self.scene_service.get_full_scene()

                    # Broadcast to subscribed clients
                    await self.broadcast({
                        "type": "state_update",
                        "data": state,
                        "timestamp": datetime.utcnow().isoformat(),
                    }, room="equipment_updates")

                await asyncio.sleep(update_interval)

            except Exception as e:
                logger.error(f"Update loop error: {e}")
                await asyncio.sleep(1.0)

    def setup_api_routes(self) -> web.Application:
        """Setup REST API routes."""
        app = web.Application()

        # Health check
        async def health(request):
            return web.json_response({
                "status": "healthy",
                "version": "2.0.0",
                "timestamp": datetime.utcnow().isoformat(),
            })

        # Scene state
        async def get_scene(request):
            if self.scene_service:
                state = self.scene_service.get_full_scene()
            else:
                state = {"equipment": []}
            return web.json_response(state)

        # Statistics
        async def get_stats(request):
            return web.json_response({
                **self.stats,
                "connected_clients": len(self.clients),
                "uptime_seconds": (
                    (datetime.utcnow() - datetime.fromisoformat(self.stats["start_time"])).total_seconds()
                    if self.stats["start_time"] else 0
                ),
            })

        # Client list
        async def get_clients(request):
            clients = []
            for client_id, info in self.client_info.items():
                clients.append({
                    "client_id": client_id,
                    "connected_at": info.get("connected_at"),
                    "client_type": info.get("client_type"),
                    "subscriptions": info.get("subscriptions", []),
                })
            return web.json_response({"clients": clients})

        app.router.add_get("/health", health)
        app.router.add_get("/api/scene", get_scene)
        app.router.add_get("/api/stats", get_stats)
        app.router.add_get("/api/clients", get_clients)

        return app

    async def run(self) -> None:
        """Run the WebSocket and API servers."""
        self.running = True
        self.stats["start_time"] = datetime.utcnow().isoformat()

        await self.initialize()

        tasks = []

        # Start WebSocket server
        if WEBSOCKETS_AVAILABLE:
            self.ws_server = await serve(
                self.handle_client,
                self.ws_host,
                self.ws_port
            )
            logger.info(f"WebSocket server started on ws://{self.ws_host}:{self.ws_port}")
        else:
            logger.error("Cannot start WebSocket server: websockets not installed")

        # Start API server
        if AIOHTTP_AVAILABLE:
            self.api_app = self.setup_api_routes()
            runner = web.AppRunner(self.api_app)
            await runner.setup()
            site = web.TCPSite(runner, self.ws_host, self.api_port)
            await site.start()
            logger.info(f"REST API server started on http://{self.ws_host}:{self.api_port}")
        else:
            logger.warning("REST API not available: aiohttp not installed")

        # Start update loop
        update_task = asyncio.create_task(self.start_update_loop())
        tasks.append(update_task)

        logger.info("Unity server ready for connections")

        # Wait for shutdown
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("Shutting down Unity server...")
        self.running = False

        # Close all client connections
        for websocket in list(self.clients):
            try:
                await websocket.close()
            except Exception:
                pass

        # Close WebSocket server
        if self.ws_server:
            self.ws_server.close()
            await self.ws_server.wait_closed()

        logger.info("Unity server shutdown complete")


async def main():
    """Main entry point."""
    ws_host = os.getenv("UNITY_WS_HOST", "0.0.0.0")
    ws_port = int(os.getenv("UNITY_WS_PORT", "8770"))
    api_port = int(os.getenv("UNITY_API_PORT", "8771"))

    server = UnityWebSocketServer(
        ws_host=ws_host,
        ws_port=ws_port,
        api_port=api_port
    )

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        asyncio.create_task(server.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await server.run()
    except KeyboardInterrupt:
        await server.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
