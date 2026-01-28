"""
REST API MES/ERP Adapter.

Adapter for integrating with MES/ERP systems that expose REST APIs.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base_adapter import (
    BaseMesAdapter,
    AdapterError,
    ConnectionError,
    SyncError,
    WorkOrder,
    WorkOrderStatus,
    Operation,
    OperationStatus,
    ProductionReport,
    InspectionResult,
    MaterialStock,
)

logger = logging.getLogger(__name__)


class RestMesAdapter(BaseMesAdapter):
    """
    REST API adapter for MES/ERP integration.

    Configuration options:
        base_url: Base URL of the MES API
        api_key: API key for authentication (optional)
        username: Username for basic auth (optional)
        password: Password for basic auth (optional)
        timeout: Request timeout in seconds (default: 30)
        verify_ssl: Verify SSL certificates (default: True)
        retry_count: Number of retries for failed requests (default: 3)
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        self.base_url = config.get('base_url', '').rstrip('/')
        self.api_key = config.get('api_key')
        self.username = config.get('username')
        self.password = config.get('password')
        self.timeout = config.get('timeout', 30)
        self.verify_ssl = config.get('verify_ssl', True)
        self.retry_count = config.get('retry_count', 3)

        self.session: Optional[requests.Session] = None

    def connect(self) -> bool:
        """Establish connection to REST API."""
        try:
            self.session = requests.Session()

            # Configure retries
            retry_strategy = Retry(
                total=self.retry_count,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

            # Set authentication
            if self.api_key:
                self.session.headers['Authorization'] = f'Bearer {self.api_key}'
                self.session.headers['X-API-Key'] = self.api_key
            elif self.username and self.password:
                self.session.auth = (self.username, self.password)

            self.session.headers['Content-Type'] = 'application/json'
            self.session.headers['Accept'] = 'application/json'

            # Test connection
            health = self.health_check()
            self._connected = health.get('status') == 'ok'

            if self._connected:
                logger.info(f"Connected to MES API at {self.base_url}")
            else:
                logger.warning(f"MES API health check failed: {health}")

            return self._connected

        except Exception as e:
            logger.error(f"Failed to connect to MES API: {e}")
            raise ConnectionError(f"Connection failed: {e}")

    def disconnect(self) -> None:
        """Close connection."""
        if self.session:
            self.session.close()
            self.session = None
        self._connected = False
        logger.info("Disconnected from MES API")

    def health_check(self) -> Dict[str, Any]:
        """Check API health."""
        try:
            response = self._get('/health')
            return {'status': 'ok', 'response': response}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Make GET request."""
        if not self.session:
            raise ConnectionError("Not connected")

        url = f"{self.base_url}{endpoint}"
        response = self.session.get(
            url,
            params=params,
            timeout=self.timeout,
            verify=self.verify_ssl
        )
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, data: Dict) -> Any:
        """Make POST request."""
        if not self.session:
            raise ConnectionError("Not connected")

        url = f"{self.base_url}{endpoint}"
        response = self.session.post(
            url,
            json=data,
            timeout=self.timeout,
            verify=self.verify_ssl
        )
        response.raise_for_status()
        return response.json()

    def _put(self, endpoint: str, data: Dict) -> Any:
        """Make PUT request."""
        if not self.session:
            raise ConnectionError("Not connected")

        url = f"{self.base_url}{endpoint}"
        response = self.session.put(
            url,
            json=data,
            timeout=self.timeout,
            verify=self.verify_ssl
        )
        response.raise_for_status()
        return response.json()

    def _parse_work_order(self, data: Dict) -> WorkOrder:
        """Parse work order from API response."""
        operations = [
            Operation(
                operation_id=op.get('id', ''),
                operation_number=op.get('number', 0),
                operation_name=op.get('name', ''),
                work_center=op.get('work_center', ''),
                machine_id=op.get('machine_id', ''),
                setup_time_minutes=op.get('setup_time', 0),
                run_time_minutes=op.get('run_time', 0),
                required_capabilities=op.get('capabilities', []),
                status=OperationStatus(op.get('status', 'pending')),
                program_id=op.get('program_id', ''),
                instructions=op.get('instructions', ''),
            )
            for op in data.get('operations', [])
        ]

        return WorkOrder(
            work_order_id=data.get('id', ''),
            part_number=data.get('part_number', ''),
            part_description=data.get('part_description', ''),
            quantity=data.get('quantity', 1),
            due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None,
            priority=data.get('priority', 1),
            status=WorkOrderStatus(data.get('status', 'pending')),
            customer_id=data.get('customer_id', ''),
            customer_name=data.get('customer_name', ''),
            routing_id=data.get('routing_id', ''),
            operations=operations,
            material_lots=data.get('material_lots', []),
            notes=data.get('notes', ''),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None,
        )

    def get_pending_work_orders(
        self,
        machine_id: Optional[str] = None,
        limit: int = 100
    ) -> List[WorkOrder]:
        """Fetch pending work orders."""
        try:
            params = {
                'status': 'pending,released',
                'limit': limit,
            }
            if machine_id:
                params['machine_id'] = machine_id

            response = self._get('/work-orders', params)
            work_orders = response.get('data', response) if isinstance(response, dict) else response

            return [self._parse_work_order(wo) for wo in work_orders]

        except Exception as e:
            logger.error(f"Failed to fetch work orders: {e}")
            raise SyncError(f"Failed to fetch work orders: {e}")

    def get_work_order(self, work_order_id: str) -> Optional[WorkOrder]:
        """Fetch specific work order."""
        try:
            response = self._get(f'/work-orders/{work_order_id}')
            return self._parse_work_order(response)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise SyncError(f"Failed to fetch work order: {e}")
        except Exception as e:
            logger.error(f"Failed to fetch work order {work_order_id}: {e}")
            raise SyncError(f"Failed to fetch work order: {e}")

    def update_work_order_status(
        self,
        work_order_id: str,
        status: WorkOrderStatus,
        notes: str = ""
    ) -> bool:
        """Update work order status."""
        try:
            data = {
                'status': status.value,
                'notes': notes,
                'updated_at': datetime.utcnow().isoformat(),
            }
            self._put(f'/work-orders/{work_order_id}/status', data)
            logger.info(f"Updated work order {work_order_id} status to {status.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to update work order status: {e}")
            return False

    def update_operation_status(
        self,
        work_order_id: str,
        operation_id: str,
        status: OperationStatus,
        machine_id: str = "",
        notes: str = ""
    ) -> bool:
        """Update operation status."""
        try:
            data = {
                'status': status.value,
                'machine_id': machine_id,
                'notes': notes,
                'updated_at': datetime.utcnow().isoformat(),
            }
            self._put(f'/work-orders/{work_order_id}/operations/{operation_id}/status', data)
            logger.info(f"Updated operation {operation_id} status to {status.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to update operation status: {e}")
            return False

    def submit_production_report(self, report: ProductionReport) -> bool:
        """Submit production report."""
        try:
            data = self.to_dict(report)
            self._post('/production-reports', data)
            logger.info(f"Submitted production report for WO {report.work_order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to submit production report: {e}")
            return False

    def submit_inspection_result(self, result: InspectionResult) -> bool:
        """Submit inspection result."""
        try:
            data = self.to_dict(result)
            self._post('/inspections', data)
            logger.info(f"Submitted inspection result {result.inspection_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to submit inspection result: {e}")
            return False

    def get_material_stock(
        self,
        material_id: str,
        location: Optional[str] = None
    ) -> List[MaterialStock]:
        """Get material inventory."""
        try:
            params = {'material_id': material_id}
            if location:
                params['location'] = location

            response = self._get('/materials/stock', params)
            stock_data = response.get('data', response) if isinstance(response, dict) else response

            return [
                MaterialStock(
                    material_id=s.get('material_id', material_id),
                    material_name=s.get('material_name', ''),
                    lot_number=s.get('lot_number', ''),
                    quantity_available=s.get('quantity_available', 0),
                    quantity_reserved=s.get('quantity_reserved', 0),
                    unit=s.get('unit', 'ea'),
                    location=s.get('location', ''),
                    supplier_id=s.get('supplier_id', ''),
                )
                for s in stock_data
            ]
        except Exception as e:
            logger.error(f"Failed to get material stock: {e}")
            return []

    def consume_material(
        self,
        material_id: str,
        lot_number: str,
        quantity: float,
        work_order_id: str
    ) -> bool:
        """Record material consumption."""
        try:
            data = {
                'material_id': material_id,
                'lot_number': lot_number,
                'quantity': quantity,
                'work_order_id': work_order_id,
                'consumed_at': datetime.utcnow().isoformat(),
            }
            self._post('/materials/consume', data)
            logger.info(f"Consumed {quantity} of {material_id} lot {lot_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to consume material: {e}")
            return False
