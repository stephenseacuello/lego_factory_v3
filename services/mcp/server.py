"""
LEGO Factory v3 - Unified MCP Server
=====================================
Model Context Protocol server with 50+ tools across all domains.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """Tool categories."""
    SCADA = 'scada'
    MES = 'mes'
    ERP = 'erp'
    QMS = 'qms'
    CMMS = 'cmms'
    LEGO = 'lego'
    ML = 'ml'
    ROBOTICS = 'robotics'
    UNITY = 'unity'


@dataclass
class ToolDefinition:
    """MCP Tool definition."""
    name: str
    description: str
    category: ToolCategory
    parameters: Dict[str, Any]
    handler: callable


class MCPServer:
    """
    Unified MCP Server for LEGO Factory.

    Provides tools for:
    - SCADA: Machine control, alarms, historian
    - MES: Work orders, scheduling, OEE
    - ERP: Sales, purchasing, inventory
    - QMS: Documents, NCR/CAPA
    - CMMS: Assets, maintenance
    - LEGO: Brick design, slicing
    - ML: Fingerprinting, anomaly detection
    - Robotics: Robot control, coordination
    - Unity: Digital Twin
    """

    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self._register_all_tools()

    def _register_all_tools(self):
        """Register all available tools."""
        # SCADA Tools
        self._register_scada_tools()
        # MES Tools
        self._register_mes_tools()
        # ERP Tools
        self._register_erp_tools()
        # QMS Tools
        self._register_qms_tools()
        # CMMS Tools
        self._register_cmms_tools()
        # LEGO Tools
        self._register_lego_tools()
        # ML Tools
        self._register_ml_tools()
        # Robotics Tools
        self._register_robotics_tools()
        # Unity Tools
        self._register_unity_tools()

        logger.info(f"Registered {len(self.tools)} MCP tools")

    def _register_tool(self, tool: ToolDefinition):
        """Register a single tool."""
        self.tools[tool.name] = tool

    def _register_scada_tools(self):
        """Register SCADA tools."""
        self._register_tool(ToolDefinition(
            name='connect_machine',
            description='Connect to a CNC machine via serial port',
            category=ToolCategory.SCADA,
            parameters={
                'machine_id': {'type': 'string', 'required': True},
                'port': {'type': 'string', 'required': True},
                'controller_type': {'type': 'string', 'enum': ['tinyg', 'grbl']},
            },
            handler=self._handle_connect_machine,
        ))

        self._register_tool(ToolDefinition(
            name='disconnect_machine',
            description='Disconnect from a CNC machine',
            category=ToolCategory.SCADA,
            parameters={'machine_id': {'type': 'string', 'required': True}},
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='get_machine_status',
            description='Get current status of a connected machine',
            category=ToolCategory.SCADA,
            parameters={'machine_id': {'type': 'string', 'required': True}},
            handler=self._handle_get_machine_status,
        ))

        self._register_tool(ToolDefinition(
            name='list_machines',
            description='List all registered machines',
            category=ToolCategory.SCADA,
            parameters={},
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='send_gcode',
            description='Send G-code command to a machine',
            category=ToolCategory.SCADA,
            parameters={
                'machine_id': {'type': 'string', 'required': True},
                'gcode': {'type': 'string', 'required': True},
            },
            handler=self._handle_send_gcode,
        ))

        self._register_tool(ToolDefinition(
            name='start_job',
            description='Start a G-code job on a machine',
            category=ToolCategory.SCADA,
            parameters={
                'machine_id': {'type': 'string', 'required': True},
                'file_path': {'type': 'string', 'required': True},
            },
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='pause_job',
            description='Pause the current job on a machine',
            category=ToolCategory.SCADA,
            parameters={'machine_id': {'type': 'string', 'required': True}},
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='resume_job',
            description='Resume a paused job on a machine',
            category=ToolCategory.SCADA,
            parameters={'machine_id': {'type': 'string', 'required': True}},
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='emergency_stop',
            description='Trigger emergency stop on a machine',
            category=ToolCategory.SCADA,
            parameters={'machine_id': {'type': 'string', 'required': True}},
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='get_active_alarms',
            description='Get all active alarms in the system',
            category=ToolCategory.SCADA,
            parameters={
                'priority': {'type': 'string', 'enum': ['critical', 'high', 'medium', 'low']},
            },
            handler=self._handle_get_active_alarms,
        ))

        self._register_tool(ToolDefinition(
            name='acknowledge_alarm',
            description='Acknowledge an active alarm',
            category=ToolCategory.SCADA,
            parameters={
                'alarm_id': {'type': 'string', 'required': True},
                'user_id': {'type': 'string', 'required': True},
            },
            handler=self._handle_acknowledge_alarm,
        ))

        self._register_tool(ToolDefinition(
            name='shelve_alarm',
            description='Shelve an alarm temporarily',
            category=ToolCategory.SCADA,
            parameters={
                'alarm_id': {'type': 'string', 'required': True},
                'duration_hours': {'type': 'integer', 'required': True},
            },
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='query_historian',
            description='Query historical tag values',
            category=ToolCategory.SCADA,
            parameters={
                'tag_ids': {'type': 'array', 'required': True},
                'start_time': {'type': 'string', 'required': True},
                'end_time': {'type': 'string', 'required': True},
                'aggregation': {'type': 'string', 'enum': ['raw', 'avg', 'min', 'max']},
            },
            handler=self._handle_query_historian,
        ))

        self._register_tool(ToolDefinition(
            name='get_tag_value',
            description='Get current value of a tag',
            category=ToolCategory.SCADA,
            parameters={'tag_id': {'type': 'string', 'required': True}},
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='set_tag_value',
            description='Set value of a writable tag',
            category=ToolCategory.SCADA,
            parameters={
                'tag_id': {'type': 'string', 'required': True},
                'value': {'type': 'any', 'required': True},
            },
            handler=self._handle_placeholder,
        ))

    def _register_mes_tools(self):
        """Register MES tools."""
        self._register_tool(ToolDefinition(
            name='create_work_order',
            description='Create a new manufacturing work order',
            category=ToolCategory.MES,
            parameters={
                'product_id': {'type': 'string', 'required': True},
                'quantity': {'type': 'integer', 'required': True},
                'due_date': {'type': 'string'},
                'priority': {'type': 'integer'},
            },
            handler=self._handle_create_work_order,
        ))

        self._register_tool(ToolDefinition(
            name='get_work_order',
            description='Get work order details',
            category=ToolCategory.MES,
            parameters={'work_order_id': {'type': 'string', 'required': True}},
            handler=self._handle_get_work_order,
        ))

        self._register_tool(ToolDefinition(
            name='schedule_jobs',
            description='Run job scheduling optimization',
            category=ToolCategory.MES,
            parameters={
                'horizon_hours': {'type': 'integer'},
                'objective': {'type': 'string', 'enum': ['makespan', 'due_date']},
            },
            handler=self._handle_schedule_jobs,
        ))

        self._register_tool(ToolDefinition(
            name='get_oee_dashboard',
            description='Get OEE metrics dashboard',
            category=ToolCategory.MES,
            parameters={
                'machine_ids': {'type': 'array'},
                'days': {'type': 'integer'},
            },
            handler=self._handle_get_oee_dashboard,
        ))

        self._register_tool(ToolDefinition(
            name='update_work_order_status',
            description='Update work order status',
            category=ToolCategory.MES,
            parameters={
                'work_order_id': {'type': 'string', 'required': True},
                'status': {'type': 'string', 'required': True},
            },
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='report_production',
            description='Report production quantity',
            category=ToolCategory.MES,
            parameters={
                'work_order_id': {'type': 'string', 'required': True},
                'quantity': {'type': 'integer', 'required': True},
                'scrap': {'type': 'integer'},
            },
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='record_downtime',
            description='Record machine downtime event',
            category=ToolCategory.MES,
            parameters={
                'machine_id': {'type': 'string', 'required': True},
                'reason_code': {'type': 'string', 'required': True},
                'duration_minutes': {'type': 'integer'},
            },
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='get_recipe',
            description='Get manufacturing recipe',
            category=ToolCategory.MES,
            parameters={'recipe_id': {'type': 'string', 'required': True}},
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='download_recipe_to_machine',
            description='Download recipe to a machine controller',
            category=ToolCategory.MES,
            parameters={
                'recipe_id': {'type': 'string', 'required': True},
                'machine_id': {'type': 'string', 'required': True},
            },
            handler=self._handle_placeholder,
        ))

    def _register_erp_tools(self):
        """Register ERP tools."""
        self._register_tool(ToolDefinition(
            name='create_sales_order',
            description='Create a new sales order',
            category=ToolCategory.ERP,
            parameters={
                'customer_id': {'type': 'string', 'required': True},
                'lines': {'type': 'array', 'required': True},
            },
            handler=self._handle_create_sales_order,
        ))

        self._register_tool(ToolDefinition(
            name='create_purchase_order',
            description='Create a new purchase order',
            category=ToolCategory.ERP,
            parameters={
                'vendor_id': {'type': 'string', 'required': True},
                'lines': {'type': 'array', 'required': True},
            },
            handler=self._handle_create_purchase_order,
        ))

        self._register_tool(ToolDefinition(
            name='run_mrp',
            description='Run Material Requirements Planning',
            category=ToolCategory.ERP,
            parameters={
                'horizon_days': {'type': 'integer'},
                'include_forecasts': {'type': 'boolean'},
            },
            handler=self._handle_run_mrp,
        ))

        self._register_tool(ToolDefinition(
            name='get_inventory_balance',
            description='Get inventory balance for an item',
            category=ToolCategory.ERP,
            parameters={
                'item_id': {'type': 'string', 'required': True},
                'location_id': {'type': 'string'},
            },
            handler=self._handle_get_inventory_balance,
        ))

        self._register_tool(ToolDefinition(
            name='get_customer',
            description='Get customer details',
            category=ToolCategory.ERP,
            parameters={'customer_id': {'type': 'string', 'required': True}},
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='get_vendor',
            description='Get vendor details',
            category=ToolCategory.ERP,
            parameters={'vendor_id': {'type': 'string', 'required': True}},
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='get_bom',
            description='Get Bill of Materials for a product',
            category=ToolCategory.ERP,
            parameters={'product_id': {'type': 'string', 'required': True}},
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='create_inventory_transfer',
            description='Create inventory transfer between locations',
            category=ToolCategory.ERP,
            parameters={
                'item_id': {'type': 'string', 'required': True},
                'from_location': {'type': 'string', 'required': True},
                'to_location': {'type': 'string', 'required': True},
                'quantity': {'type': 'number', 'required': True},
            },
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='get_item',
            description='Get item master details',
            category=ToolCategory.ERP,
            parameters={'item_id': {'type': 'string', 'required': True}},
            handler=self._handle_placeholder,
        ))

    def _register_qms_tools(self):
        """Register QMS tools."""
        self._register_tool(ToolDefinition(
            name='create_ncr',
            description='Create a Non-Conformance Report',
            category=ToolCategory.QMS,
            parameters={
                'title': {'type': 'string', 'required': True},
                'description': {'type': 'string', 'required': True},
                'ncr_type': {'type': 'string', 'required': True},
                'severity': {'type': 'string'},
            },
            handler=self._handle_create_ncr,
        ))

        self._register_tool(ToolDefinition(
            name='create_capa',
            description='Create a Corrective/Preventive Action',
            category=ToolCategory.QMS,
            parameters={
                'title': {'type': 'string', 'required': True},
                'problem_statement': {'type': 'string', 'required': True},
                'ncr_number': {'type': 'string'},
            },
            handler=self._handle_create_capa,
        ))

        self._register_tool(ToolDefinition(
            name='get_document',
            description='Get controlled document',
            category=ToolCategory.QMS,
            parameters={'document_number': {'type': 'string', 'required': True}},
            handler=self._handle_get_document,
        ))

        self._register_tool(ToolDefinition(
            name='update_ncr_status',
            description='Update NCR status',
            category=ToolCategory.QMS,
            parameters={
                'ncr_number': {'type': 'string', 'required': True},
                'status': {'type': 'string', 'required': True},
            },
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='get_training_records',
            description='Get employee training records',
            category=ToolCategory.QMS,
            parameters={'employee_id': {'type': 'string', 'required': True}},
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='record_calibration',
            description='Record equipment calibration',
            category=ToolCategory.QMS,
            parameters={
                'equipment_id': {'type': 'string', 'required': True},
                'result': {'type': 'string', 'required': True},
            },
            handler=self._handle_placeholder,
        ))

    def _register_cmms_tools(self):
        """Register CMMS tools."""
        self._register_tool(ToolDefinition(
            name='create_maintenance_wo',
            description='Create a maintenance work order',
            category=ToolCategory.CMMS,
            parameters={
                'asset_id': {'type': 'string', 'required': True},
                'description': {'type': 'string', 'required': True},
                'wo_type': {'type': 'string'},
            },
            handler=self._handle_create_maintenance_wo,
        ))

        self._register_tool(ToolDefinition(
            name='get_asset',
            description='Get asset details',
            category=ToolCategory.CMMS,
            parameters={'asset_id': {'type': 'string', 'required': True}},
            handler=self._handle_get_asset,
        ))

        self._register_tool(ToolDefinition(
            name='generate_pm_work_orders',
            description='Generate preventive maintenance work orders',
            category=ToolCategory.CMMS,
            parameters={'days_ahead': {'type': 'integer'}},
            handler=self._handle_generate_pm_work_orders,
        ))

    def _register_lego_tools(self):
        """Register LEGO tools."""
        self._register_tool(ToolDefinition(
            name='get_brick_catalog',
            description='Get available LEGO brick types',
            category=ToolCategory.LEGO,
            parameters={
                'category': {'type': 'string'},
                'search': {'type': 'string'},
            },
            handler=self._handle_get_brick_catalog,
        ))

        self._register_tool(ToolDefinition(
            name='create_custom_brick',
            description='Create a custom LEGO brick design',
            category=ToolCategory.LEGO,
            parameters={
                'width_studs': {'type': 'integer', 'required': True},
                'length_studs': {'type': 'integer', 'required': True},
                'height_plates': {'type': 'integer'},
            },
            handler=self._handle_create_custom_brick,
        ))

        self._register_tool(ToolDefinition(
            name='slice_brick',
            description='Generate G-code for a brick design',
            category=ToolCategory.LEGO,
            parameters={
                'brick_id': {'type': 'string', 'required': True},
                'material': {'type': 'string'},
            },
            handler=self._handle_slice_brick,
        ))

        self._register_tool(ToolDefinition(
            name='get_brick_dimensions',
            description='Get precise dimensions for a brick type',
            category=ToolCategory.LEGO,
            parameters={'brick_type': {'type': 'string', 'required': True}},
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='export_brick_stl',
            description='Export brick design to STL format',
            category=ToolCategory.LEGO,
            parameters={'brick_id': {'type': 'string', 'required': True}},
            handler=self._handle_placeholder,
        ))

        self._register_tool(ToolDefinition(
            name='get_lego_colors',
            description='Get available LEGO colors',
            category=ToolCategory.LEGO,
            parameters={},
            handler=self._handle_placeholder,
        ))

    def _register_ml_tools(self):
        """Register ML tools."""
        self._register_tool(ToolDefinition(
            name='get_fingerprint',
            description='Get ML fingerprint for a G-code file',
            category=ToolCategory.ML,
            parameters={'gcode_file': {'type': 'string', 'required': True}},
            handler=self._handle_get_fingerprint,
        ))

        self._register_tool(ToolDefinition(
            name='detect_anomaly',
            description='Detect anomalies in sensor data',
            category=ToolCategory.ML,
            parameters={
                'machine_id': {'type': 'string', 'required': True},
                'start_time': {'type': 'string'},
                'end_time': {'type': 'string'},
            },
            handler=self._handle_detect_anomaly,
        ))

        self._register_tool(ToolDefinition(
            name='predict_tool_wear',
            description='Predict remaining tool life',
            category=ToolCategory.ML,
            parameters={'machine_id': {'type': 'string', 'required': True}},
            handler=self._handle_predict_tool_wear,
        ))

    def _register_robotics_tools(self):
        """Register robotics tools."""
        self._register_tool(ToolDefinition(
            name='get_robot_status',
            description='Get robot status',
            category=ToolCategory.ROBOTICS,
            parameters={'robot_id': {'type': 'string', 'required': True}},
            handler=self._handle_get_robot_status,
        ))

        self._register_tool(ToolDefinition(
            name='submit_robot_task',
            description='Submit a task to the cell orchestrator',
            category=ToolCategory.ROBOTICS,
            parameters={
                'task_type': {'type': 'string', 'required': True},
                'robot_id': {'type': 'string'},
                'parameters': {'type': 'object'},
            },
            handler=self._handle_submit_robot_task,
        ))

        self._register_tool(ToolDefinition(
            name='get_cell_status',
            description='Get work cell status',
            category=ToolCategory.ROBOTICS,
            parameters={'cell_id': {'type': 'string'}},
            handler=self._handle_get_cell_status,
        ))

    def _register_unity_tools(self):
        """Register Unity Digital Twin tools."""
        self._register_tool(ToolDefinition(
            name='get_scene_state',
            description='Get current Digital Twin scene state',
            category=ToolCategory.UNITY,
            parameters={'scene_id': {'type': 'string'}},
            handler=self._handle_get_scene_state,
        ))

        self._register_tool(ToolDefinition(
            name='update_entity',
            description='Update Digital Twin entity state',
            category=ToolCategory.UNITY,
            parameters={
                'entity_id': {'type': 'string', 'required': True},
                'state': {'type': 'object'},
                'transform': {'type': 'object'},
            },
            handler=self._handle_update_entity,
        ))

    # Tool Handlers
    def _handle_placeholder(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Placeholder handler for tools not yet implemented."""
        return {'message': 'Tool not yet implemented', 'params': params}

    def _handle_connect_machine(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.scada.machine_control import create_controller
        result = create_controller(
            params['machine_id'],
            params['port'],
            params.get('controller_type', 'tinyg')
        )
        return {'success': True, 'machine_id': params['machine_id']}

    def _handle_get_machine_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.scada.machine_control import get_controller
        controller = get_controller(params['machine_id'])
        if controller:
            return controller.get_status()
        return {'error': 'Machine not found'}

    def _handle_send_gcode(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.scada.machine_control import get_controller
        import asyncio
        controller = get_controller(params['machine_id'])
        if controller:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(controller.send_command(params['gcode']))
            loop.close()
            return {'success': True, 'response': result}
        return {'error': 'Machine not found'}

    def _handle_get_active_alarms(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.scada.alarm_management import get_alarm_processor
        processor = get_alarm_processor()
        alarms = processor.get_active_alarms(priority=params.get('priority'))
        return {'alarms': alarms, 'count': len(alarms)}

    def _handle_acknowledge_alarm(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.scada.alarm_management import get_alarm_processor
        processor = get_alarm_processor()
        result = processor.acknowledge_alarm(params['alarm_id'], params['user_id'])
        return {'success': result}

    def _handle_query_historian(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {'message': 'Historian query placeholder'}

    def _handle_create_work_order(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.mes.work_order_service import get_work_order_service
        from config.database import get_db_session
        with get_db_session() as session:
            service = get_work_order_service(session)
            result = service.create_work_order(params)
            return result

    def _handle_get_work_order(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.mes.work_order_service import get_work_order_service
        from config.database import get_db_session
        with get_db_session() as session:
            service = get_work_order_service(session)
            result = service.get_work_order(params['work_order_id'])
            return result or {'error': 'Work order not found'}

    def _handle_schedule_jobs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {'message': 'Scheduling placeholder'}

    def _handle_get_oee_dashboard(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.mes.oee_service import get_oee_dashboard
        return get_oee_dashboard(params.get('machine_ids'), params.get('days', 7))

    def _handle_create_sales_order(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.erp.sales_service import get_sales_service
        from config.database import get_db_session
        with get_db_session() as session:
            service = get_sales_service(session)
            result = service.create_order(params)
            return result

    def _handle_create_purchase_order(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.erp.purchasing_service import get_purchasing_service
        from config.database import get_db_session
        with get_db_session() as session:
            service = get_purchasing_service(session)
            result = service.create_purchase_order(params)
            return result

    def _handle_run_mrp(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.erp.mrp_service import get_mrp_service
        from config.database import get_db_session
        with get_db_session() as session:
            service = get_mrp_service(session)
            plan = service.run_mrp(
                params.get('horizon_days', 90),
                params.get('include_forecasts', True)
            )
            return {
                'planned_orders': plan.planned_orders,
                'action_messages': plan.action_messages,
            }

    def _handle_get_inventory_balance(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.erp.inventory_service import get_inventory_service
        from config.database import get_db_session
        with get_db_session() as session:
            service = get_inventory_service(session)
            return service.get_balance(params['item_id'], params.get('location_id'))

    def _handle_create_ncr(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.qms.ncr_service import get_ncr_service
        from config.database import get_db_session
        with get_db_session() as session:
            service = get_ncr_service(session)
            params['detected_by'] = params.get('detected_by', 'system')
            return service.create_ncr(params)

    def _handle_create_capa(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.qms.ncr_service import get_ncr_service
        from config.database import get_db_session
        with get_db_session() as session:
            service = get_ncr_service(session)
            params['owner_id'] = params.get('owner_id', 'system')
            return service.create_capa(params)

    def _handle_get_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.qms.document_service import get_document_service
        from config.database import get_db_session
        with get_db_session() as session:
            service = get_document_service(session)
            return service.get_document(params['document_number']) or {'error': 'Document not found'}

    def _handle_create_maintenance_wo(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.cmms.maintenance_service import get_maintenance_service
        from config.database import get_db_session
        with get_db_session() as session:
            service = get_maintenance_service(session)
            return service.create_work_order(params)

    def _handle_get_asset(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.cmms.asset_service import get_asset_service
        from config.database import get_db_session
        with get_db_session() as session:
            service = get_asset_service(session)
            return service.get_asset(params['asset_id']) or {'error': 'Asset not found'}

    def _handle_generate_pm_work_orders(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.cmms.maintenance_service import get_pm_service
        from config.database import get_db_session
        with get_db_session() as session:
            service = get_pm_service(session)
            return {'work_orders': service.generate_pm_work_orders(params.get('days_ahead', 7))}

    def _handle_get_brick_catalog(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.lego.brick_catalog import get_all_bricks, get_bricks_by_category
        if params.get('category'):
            return {'bricks': get_bricks_by_category(params['category'])}
        return {'bricks': get_all_bricks()}

    def _handle_create_custom_brick(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.lego.lego_specs import brick_dimensions
        dims = brick_dimensions(params['width_studs'], params['length_studs'], params.get('height_plates', 3))
        return {'dimensions': dims}

    def _handle_slice_brick(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {'message': 'Slicing placeholder', 'brick_id': params['brick_id']}

    def _handle_get_fingerprint(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {'message': 'Fingerprint placeholder', 'gcode_file': params['gcode_file']}

    def _handle_detect_anomaly(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {'anomalies': [], 'machine_id': params['machine_id']}

    def _handle_predict_tool_wear(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {'remaining_life_hours': 100, 'confidence': 0.85}

    def _handle_get_robot_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.robotics.ros2_bridge import get_ros2_bridge
        bridge = get_ros2_bridge()
        return bridge.get_robot_state(params['robot_id']) or {'error': 'Robot not found'}

    def _handle_submit_robot_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.robotics.cell_orchestrator import get_orchestrator
        orchestrator = get_orchestrator()
        task_id = orchestrator.submit_task(
            params['task_type'],
            params.get('robot_id'),
            params.get('parameters', {})
        )
        return {'task_id': task_id}

    def _handle_get_cell_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.robotics.cell_orchestrator import get_orchestrator
        orchestrator = get_orchestrator()
        return orchestrator.get_cell_status(params.get('cell_id', 'cell_1'))

    def _handle_get_scene_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.unity.unity_state_service import get_unity_service
        service = get_unity_service()
        return service.get_scene_state(params.get('scene_id'))

    def _handle_update_entity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from services.unity.unity_state_service import get_unity_service
        service = get_unity_service()
        success = service.update_entity(
            params['entity_id'],
            params.get('state'),
            params.get('transform')
        )
        return {'success': success}

    # MCP Protocol Methods
    def get_tools_list(self) -> List[Dict[str, Any]]:
        """Get list of available tools in MCP format."""
        return [
            {
                'name': tool.name,
                'description': tool.description,
                'inputSchema': {
                    'type': 'object',
                    'properties': tool.parameters,
                    'required': [k for k, v in tool.parameters.items() if v.get('required')],
                }
            }
            for tool in self.tools.values()
        ]

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name."""
        if name not in self.tools:
            return {'error': f'Unknown tool: {name}'}

        tool = self.tools[name]
        try:
            result = tool.handler(arguments)
            return {'result': result}
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {'error': str(e)}


# Global instance
_mcp_server: Optional[MCPServer] = None


def get_mcp_server() -> MCPServer:
    """Get MCP server instance."""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MCPServer()
    return _mcp_server
