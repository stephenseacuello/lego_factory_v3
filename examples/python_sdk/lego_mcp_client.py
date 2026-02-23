"""
LEGO MCP v8.0 Python SDK Client

A comprehensive Python client for interacting with the LEGO MCP v8.0 API.
Supports all major features including manufacturing, digital twin, AI/ML, and compliance.

Usage:
    from lego_mcp_client import LegoMCPClient

    client = LegoMCPClient(
        base_url="https://api.lego-mcp.example.com",
        api_key="your-api-key"
    )

    # Get equipment status
    equipment = client.equipment.list()
    print(f"Found {len(equipment)} pieces of equipment")

    # Create manufacturing order
    order = client.manufacturing.create_order(
        product_spec={"brick_type": "2x4", "color": "red"},
        quantity=100
    )
    print(f"Created order: {order.order_number}")

Author: LEGO MCP Engineering
Version: 8.0.0
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, TypeVar, Generic
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =============================================================================
# Type Definitions
# =============================================================================

T = TypeVar('T')


class EquipmentStatus(Enum):
    """Equipment operational status."""
    OFFLINE = "offline"
    IDLE = "idle"
    RUNNING = "running"
    MAINTENANCE = "maintenance"
    FAILED = "failed"


class OrderStatus(Enum):
    """Manufacturing order status."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ActionStatus(Enum):
    """Command center action status."""
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Equipment:
    """Equipment entity."""
    id: str
    equipment_id: str
    name: str
    type: str
    status: EquipmentStatus
    health_score: float
    location: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> Equipment:
        return cls(
            id=data['id'],
            equipment_id=data['equipment_id'],
            name=data['name'],
            type=data['type'],
            status=EquipmentStatus(data['status']),
            health_score=data.get('health_score', 1.0),
            location=data.get('location'),
            manufacturer=data.get('manufacturer'),
            model=data.get('model'),
        )


@dataclass
class ManufacturingOrder:
    """Manufacturing order entity."""
    id: str
    order_number: str
    status: OrderStatus
    quantity: int
    completed_quantity: int
    product_spec: dict
    due_date: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> ManufacturingOrder:
        return cls(
            id=data['id'],
            order_number=data['order_number'],
            status=OrderStatus(data['status']),
            quantity=data['quantity'],
            completed_quantity=data.get('completed_quantity', 0),
            product_spec=data.get('product_spec', {}),
            due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None,
        )


@dataclass
class DigitalTwinState:
    """Digital twin state snapshot."""
    equipment_id: str
    timestamp: datetime
    state_type: str
    predicted_values: dict
    actual_values: Optional[dict]
    uncertainty: Optional[dict]
    physics_residual: Optional[float]

    @classmethod
    def from_dict(cls, data: dict) -> DigitalTwinState:
        return cls(
            equipment_id=data['equipment_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            state_type=data['state_type'],
            predicted_values=data['predicted_values'],
            actual_values=data.get('actual_values'),
            uncertainty=data.get('uncertainty'),
            physics_residual=data.get('physics_residual'),
        )


@dataclass
class Action:
    """Command center action."""
    id: str
    action_type: str
    target_type: str
    status: ActionStatus
    parameters: dict
    confidence: Optional[float]
    requires_approval: bool

    @classmethod
    def from_dict(cls, data: dict) -> Action:
        return cls(
            id=data['id'],
            action_type=data['action_type'],
            target_type=data['target_type'],
            status=ActionStatus(data['status']),
            parameters=data.get('parameters', {}),
            confidence=data.get('confidence'),
            requires_approval=data.get('requires_approval', True),
        )


@dataclass
class APIResponse(Generic[T]):
    """Generic API response wrapper."""
    success: bool
    data: Optional[T]
    error: Optional[str] = None
    meta: dict = field(default_factory=dict)


# =============================================================================
# API Client
# =============================================================================

class LegoMCPClient:
    """
    LEGO MCP v8.0 API Client.

    Provides comprehensive access to all LEGO MCP API endpoints.

    Example:
        client = LegoMCPClient(
            base_url="https://api.lego-mcp.example.com",
            api_key="your-api-key"
        )

        # List equipment
        equipment = client.equipment.list()

        # Get digital twin state
        twin_state = client.digital_twin.get_state("cnc-001")
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 30,
        max_retries: int = 3,
        verify_ssl: bool = True,
    ):
        """
        Initialize the LEGO MCP client.

        Args:
            base_url: API base URL (e.g., https://api.lego-mcp.example.com)
            api_key: API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        # Configure session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Initialize sub-clients
        self.equipment = EquipmentAPI(self)
        self.manufacturing = ManufacturingAPI(self)
        self.digital_twin = DigitalTwinAPI(self)
        self.ai = AIAPI(self)
        self.command_center = CommandCenterAPI(self)
        self.compliance = ComplianceAPI(self)

    def _get_headers(self) -> dict:
        """Get default headers for API requests."""
        timestamp = str(int(time.time()))
        signature = self._sign_request(timestamp)

        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Request-Timestamp": timestamp,
            "X-Request-Signature": signature,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "lego-mcp-python-sdk/8.0.0",
        }

    def _sign_request(self, timestamp: str) -> str:
        """Sign request with HMAC-SHA256."""
        message = f"{timestamp}:{self.api_key}"
        signature = hmac.new(
            self.api_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
    ) -> APIResponse:
        """Make an API request."""
        url = urljoin(self.base_url, endpoint)

        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                params=params,
                json=json_data,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            response.raise_for_status()

            data = response.json()
            return APIResponse(
                success=True,
                data=data.get('data'),
                meta=data.get('meta', {}),
            )

        except requests.exceptions.HTTPError as e:
            error_message = str(e)
            if response.text:
                try:
                    error_data = response.json()
                    error_message = error_data.get('error', str(e))
                except json.JSONDecodeError:
                    pass
            return APIResponse(success=False, data=None, error=error_message)

        except requests.exceptions.RequestException as e:
            return APIResponse(success=False, data=None, error=str(e))

    def health_check(self) -> bool:
        """Check API health status."""
        response = self._request("GET", "/api/v8/health")
        return response.success


class EquipmentAPI:
    """Equipment management API."""

    def __init__(self, client: LegoMCPClient):
        self.client = client

    def list(
        self,
        status: Optional[EquipmentStatus] = None,
        equipment_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Equipment]:
        """
        List all equipment.

        Args:
            status: Filter by status
            equipment_type: Filter by type (cnc, 3d_printer, robot_arm, injection)
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of Equipment objects
        """
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status.value
        if equipment_type:
            params["type"] = equipment_type

        response = self.client._request("GET", "/api/v8/equipment", params=params)

        if response.success and response.data:
            return [Equipment.from_dict(e) for e in response.data]
        return []

    def get(self, equipment_id: str) -> Optional[Equipment]:
        """Get equipment by ID."""
        response = self.client._request("GET", f"/api/v8/equipment/{equipment_id}")

        if response.success and response.data:
            return Equipment.from_dict(response.data)
        return None

    def get_metrics(
        self,
        equipment_id: str,
        metric_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[dict]:
        """Get equipment metrics."""
        params = {}
        if metric_type:
            params["metric_type"] = metric_type
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()

        response = self.client._request(
            "GET",
            f"/api/v8/equipment/{equipment_id}/metrics",
            params=params
        )

        return response.data if response.success else []


class ManufacturingAPI:
    """Manufacturing orders and jobs API."""

    def __init__(self, client: LegoMCPClient):
        self.client = client

    def list_orders(
        self,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ManufacturingOrder]:
        """List manufacturing orders."""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status.value

        response = self.client._request("GET", "/api/v8/manufacturing/orders", params=params)

        if response.success and response.data:
            return [ManufacturingOrder.from_dict(o) for o in response.data]
        return []

    def create_order(
        self,
        product_spec: dict,
        quantity: int,
        priority: int = 5,
        due_date: Optional[datetime] = None,
    ) -> Optional[ManufacturingOrder]:
        """
        Create a new manufacturing order.

        Args:
            product_spec: Product specification (brick type, color, etc.)
            quantity: Number of units to produce
            priority: Priority level (1-10, lower is higher priority)
            due_date: Optional due date

        Returns:
            Created ManufacturingOrder or None on error
        """
        data = {
            "product_spec": product_spec,
            "quantity": quantity,
            "priority": priority,
        }
        if due_date:
            data["due_date"] = due_date.isoformat()

        response = self.client._request("POST", "/api/v8/manufacturing/orders", json_data=data)

        if response.success and response.data:
            return ManufacturingOrder.from_dict(response.data)
        return None

    def get_order(self, order_id: str) -> Optional[ManufacturingOrder]:
        """Get order by ID."""
        response = self.client._request("GET", f"/api/v8/manufacturing/orders/{order_id}")

        if response.success and response.data:
            return ManufacturingOrder.from_dict(response.data)
        return None


class DigitalTwinAPI:
    """Digital twin API."""

    def __init__(self, client: LegoMCPClient):
        self.client = client

    def get_state(
        self,
        equipment_id: str,
        state_type: str = "thermal",
    ) -> Optional[DigitalTwinState]:
        """
        Get current digital twin state for equipment.

        Args:
            equipment_id: Equipment identifier
            state_type: State type (thermal, structural, process)

        Returns:
            Current DigitalTwinState or None
        """
        params = {"state_type": state_type}
        response = self.client._request(
            "GET",
            f"/api/v8/digital-twin/{equipment_id}/state",
            params=params
        )

        if response.success and response.data:
            return DigitalTwinState.from_dict(response.data)
        return None

    def predict(
        self,
        equipment_id: str,
        state_type: str,
        horizon_seconds: int = 60,
    ) -> list[DigitalTwinState]:
        """
        Get predicted future states.

        Args:
            equipment_id: Equipment identifier
            state_type: State type to predict
            horizon_seconds: Prediction horizon

        Returns:
            List of predicted states
        """
        data = {
            "state_type": state_type,
            "horizon_seconds": horizon_seconds,
        }
        response = self.client._request(
            "POST",
            f"/api/v8/digital-twin/{equipment_id}/predict",
            json_data=data
        )

        if response.success and response.data:
            return [DigitalTwinState.from_dict(s) for s in response.data]
        return []


class AIAPI:
    """AI/ML services API."""

    def __init__(self, client: LegoMCPClient):
        self.client = client

    def get_prediction(
        self,
        equipment_id: str,
        prediction_type: str = "maintenance",
    ) -> dict:
        """
        Get AI prediction for equipment.

        Args:
            equipment_id: Equipment identifier
            prediction_type: Type of prediction (maintenance, quality, anomaly)

        Returns:
            Prediction result dict
        """
        params = {"prediction_type": prediction_type}
        response = self.client._request(
            "GET",
            f"/api/v8/ai/predictions/{equipment_id}",
            params=params
        )
        return response.data if response.success else {}

    def evaluate_guardrails(self, action: dict) -> dict:
        """
        Evaluate an action against AI guardrails.

        Args:
            action: Action to evaluate

        Returns:
            Guardrail evaluation result
        """
        response = self.client._request(
            "POST",
            "/api/v8/ai/guardrails/evaluate",
            json_data=action
        )
        return response.data if response.success else {}


class CommandCenterAPI:
    """Command center API."""

    def __init__(self, client: LegoMCPClient):
        self.client = client

    def list_actions(
        self,
        status: Optional[ActionStatus] = None,
        limit: int = 100,
    ) -> list[Action]:
        """List command center actions."""
        params = {"limit": limit}
        if status:
            params["status"] = status.value

        response = self.client._request("GET", "/api/v8/command-center/actions", params=params)

        if response.success and response.data:
            return [Action.from_dict(a) for a in response.data]
        return []

    def create_action(
        self,
        action_type: str,
        target_type: str,
        target_id: str,
        parameters: dict,
    ) -> Optional[Action]:
        """Create a new action."""
        data = {
            "action_type": action_type,
            "target_type": target_type,
            "target_id": target_id,
            "parameters": parameters,
        }
        response = self.client._request(
            "POST",
            "/api/v8/command-center/actions",
            json_data=data
        )

        if response.success and response.data:
            return Action.from_dict(response.data)
        return None

    def approve_action(self, action_id: str) -> bool:
        """Approve a pending action."""
        response = self.client._request(
            "POST",
            f"/api/v8/command-center/actions/{action_id}/approve"
        )
        return response.success

    def run_cosimulation(
        self,
        scenario_name: str,
        parameters: dict,
        monte_carlo_iterations: int = 100,
    ) -> dict:
        """
        Run a co-simulation scenario.

        Args:
            scenario_name: Name of the scenario
            parameters: Scenario parameters
            monte_carlo_iterations: Number of Monte Carlo iterations

        Returns:
            Simulation results
        """
        data = {
            "name": scenario_name,
            "parameters": parameters,
            "monte_carlo_iterations": monte_carlo_iterations,
        }
        response = self.client._request(
            "POST",
            "/api/v8/command-center/cosim/run",
            json_data=data
        )
        return response.data if response.success else {}


class ComplianceAPI:
    """Compliance and audit API."""

    def __init__(self, client: LegoMCPClient):
        self.client = client

    def get_cmmc_status(self) -> dict:
        """Get CMMC compliance status."""
        response = self.client._request("GET", "/api/v8/compliance/cmmc/status")
        return response.data if response.success else {}

    def get_audit_entries(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        resource_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get audit trail entries."""
        params = {"limit": limit}
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()
        if resource_type:
            params["resource_type"] = resource_type

        response = self.client._request("GET", "/api/v8/compliance/audit", params=params)
        return response.data if response.success else []

    def verify_audit_chain(self, date: str) -> dict:
        """Verify audit chain integrity for a date."""
        response = self.client._request(
            "POST",
            "/api/v8/compliance/audit/verify",
            json_data={"date": date}
        )
        return response.data if response.success else {}


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Example usage
    client = LegoMCPClient(
        base_url="https://api.lego-mcp.example.com",
        api_key="your-api-key-here"
    )

    # Check health
    print(f"API healthy: {client.health_check()}")

    # List equipment
    print("\n--- Equipment ---")
    equipment_list = client.equipment.list()
    for eq in equipment_list[:5]:
        print(f"  {eq.equipment_id}: {eq.name} ({eq.status.value})")

    # Get digital twin state
    print("\n--- Digital Twin ---")
    if equipment_list:
        twin_state = client.digital_twin.get_state(
            equipment_list[0].equipment_id,
            state_type="thermal"
        )
        if twin_state:
            print(f"  Equipment: {twin_state.equipment_id}")
            print(f"  Physics Residual: {twin_state.physics_residual}")

    # List pending actions
    print("\n--- Pending Actions ---")
    actions = client.command_center.list_actions(status=ActionStatus.PENDING)
    for action in actions[:5]:
        print(f"  {action.id}: {action.action_type} ({action.confidence:.2f} confidence)")

    # Get CMMC status
    print("\n--- Compliance ---")
    cmmc_status = client.compliance.get_cmmc_status()
    print(f"  CMMC Level: {cmmc_status.get('target_level', 'N/A')}")
    print(f"  Overall Score: {cmmc_status.get('overall_score', 'N/A')}%")
