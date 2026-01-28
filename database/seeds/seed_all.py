"""
LEGO Factory v3 - Comprehensive Database Seeder
================================================
Seeds all modules with demo data for development and testing.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
import random

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from models.base import Base


def get_engine():
    """Get database engine."""
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is required. "
            "Example: postgresql://user:password@localhost:5432/lego_factory"
        )
    return create_engine(url)


def create_tables(engine):
    """Create all tables (if they don't exist)."""
    try:
        # Try to create tables, but ignore errors if they already exist
        Base.metadata.create_all(engine, checkfirst=True)
        print("✓ Tables created/verified")
    except Exception as e:
        # Tables likely already exist from Flask app startup
        print(f"✓ Tables already exist (skipping creation): {type(e).__name__}")


def seed_scada_machines(session):
    """Seed machine data."""
    from models.scada.machines import Machine, MachineType, ControllerType, ConnectionType, MachineState

    machines = [
        {
            'machine_id': 'prusa_mk4_1',
            'name': 'Prusa MK4 #1',
            'description': 'High-precision FDM 3D printer for LEGO brick production',
            'machine_type': MachineType.PRINTER_3D,
            'controller_type': ControllerType.MARLIN,
            'connection_type': ConnectionType.SERIAL,
            'connection_config': {'port': '/dev/ttyUSB0', 'baud': 115200},
            'axes': 3,
            'has_spindle': False,
            'work_envelope_x': 250,
            'work_envelope_y': 210,
            'work_envelope_z': 210,
            'area': 'printing_cell_1',
            'current_state': MachineState.IDLE,
            'enabled': True,
        },
        {
            'machine_id': 'prusa_mk4_2',
            'name': 'Prusa MK4 #2',
            'description': 'High-precision FDM 3D printer for LEGO brick production',
            'machine_type': MachineType.PRINTER_3D,
            'controller_type': ControllerType.MARLIN,
            'connection_type': ConnectionType.SERIAL,
            'connection_config': {'port': '/dev/ttyUSB1', 'baud': 115200},
            'axes': 3,
            'has_spindle': False,
            'work_envelope_x': 250,
            'work_envelope_y': 210,
            'work_envelope_z': 210,
            'area': 'printing_cell_1',
            'current_state': MachineState.RUNNING,
            'enabled': True,
        },
        {
            'machine_id': 'bambu_x1c_1',
            'name': 'Bambu X1 Carbon',
            'description': 'High-speed multi-color FDM printer',
            'machine_type': MachineType.PRINTER_3D,
            'controller_type': ControllerType.SIMULATION,
            'connection_type': ConnectionType.MQTT,
            'connection_config': {'host': 'bambu_x1c_1.local', 'topic': 'device/001'},
            'axes': 3,
            'has_spindle': False,
            'work_envelope_x': 256,
            'work_envelope_y': 256,
            'work_envelope_z': 256,
            'area': 'printing_cell_2',
            'current_state': MachineState.IDLE,
            'enabled': True,
        },
        {
            'machine_id': 'cnc_mill_1',
            'name': 'CNC Mill #1',
            'description': 'Precision CNC milling machine for molds',
            'machine_type': MachineType.CNC_MILL,
            'controller_type': ControllerType.GRBL,
            'connection_type': ConnectionType.SERIAL,
            'connection_config': {'port': '/dev/ttyUSB2', 'baud': 115200},
            'axes': 3,
            'has_spindle': True,
            'has_coolant': True,
            'max_spindle_rpm': 24000,
            'max_feed_rate': 5000,
            'work_envelope_x': 400,
            'work_envelope_y': 300,
            'work_envelope_z': 150,
            'area': 'machining_cell',
            'current_state': MachineState.IDLE,
            'enabled': True,
        },
        {
            'machine_id': 'niryo_ned2_1',
            'name': 'Niryo Ned2 #1',
            'description': '6-axis collaborative robot for assembly',
            'machine_type': MachineType.ROBOT_ARM,
            'controller_type': ControllerType.ROS2,
            'connection_type': ConnectionType.ROS2,
            'connection_config': {'namespace': '/niryo_ned2_1', 'action_server': 'niryo_robot_arm_commander'},
            'axes': 6,
            'has_spindle': False,
            'work_envelope_x': 440,
            'work_envelope_y': 440,
            'work_envelope_z': 400,
            'area': 'assembly_cell',
            'current_state': MachineState.IDLE,
            'enabled': True,
        },
        {
            'machine_id': 'xarm_lite6_1',
            'name': 'xArm Lite 6',
            'description': '6-axis robot arm for pick and place',
            'machine_type': MachineType.ROBOT_ARM,
            'controller_type': ControllerType.ROS2,
            'connection_type': ConnectionType.ROS2,
            'connection_config': {'namespace': '/xarm', 'ip': '192.168.1.100'},
            'axes': 6,
            'has_spindle': False,
            'work_envelope_x': 700,
            'work_envelope_y': 700,
            'work_envelope_z': 500,
            'area': 'assembly_cell',
            'current_state': MachineState.IDLE,
            'enabled': True,
        },
        {
            'machine_id': 'conveyor_1',
            'name': 'Main Conveyor',
            'description': 'Main production line conveyor',
            'machine_type': MachineType.CONVEYOR,
            'controller_type': ControllerType.SIMULATION,
            'connection_type': ConnectionType.SIMULATION,
            'connection_config': {},
            'axes': 1,
            'has_spindle': False,
            'area': 'production_line',
            'current_state': MachineState.RUNNING,
            'enabled': True,
        },
    ]

    for m_data in machines:
        existing = session.query(Machine).filter_by(machine_id=m_data['machine_id']).first()
        if not existing:
            machine = Machine(**m_data)
            session.add(machine)

    session.commit()
    print(f"✓ Seeded {len(machines)} machines")


def seed_scada_tags(session):
    """Seed tag data."""
    from models.scada.tags import Tag, TagDataType, TagCategory

    tags = [
        # Prusa MK4 #1 tags
        {'tag_id': 'prusa_mk4_1.hotend_temp', 'name': 'Hotend Temperature', 'equipment': 'prusa_mk4_1', 'data_type': TagDataType.FLOAT32, 'category': TagCategory.ANALOG_INPUT, 'eng_units': '°C', 'eng_low': 0, 'eng_high': 300},
        {'tag_id': 'prusa_mk4_1.bed_temp', 'name': 'Bed Temperature', 'equipment': 'prusa_mk4_1', 'data_type': TagDataType.FLOAT32, 'category': TagCategory.ANALOG_INPUT, 'eng_units': '°C', 'eng_low': 0, 'eng_high': 120},
        {'tag_id': 'prusa_mk4_1.position_x', 'name': 'X Position', 'equipment': 'prusa_mk4_1', 'data_type': TagDataType.FLOAT32, 'category': TagCategory.ANALOG_INPUT, 'eng_units': 'mm'},
        {'tag_id': 'prusa_mk4_1.position_y', 'name': 'Y Position', 'equipment': 'prusa_mk4_1', 'data_type': TagDataType.FLOAT32, 'category': TagCategory.ANALOG_INPUT, 'eng_units': 'mm'},
        {'tag_id': 'prusa_mk4_1.position_z', 'name': 'Z Position', 'equipment': 'prusa_mk4_1', 'data_type': TagDataType.FLOAT32, 'category': TagCategory.ANALOG_INPUT, 'eng_units': 'mm'},
        {'tag_id': 'prusa_mk4_1.print_progress', 'name': 'Print Progress', 'equipment': 'prusa_mk4_1', 'data_type': TagDataType.FLOAT32, 'category': TagCategory.ANALOG_INPUT, 'eng_units': '%'},
        {'tag_id': 'prusa_mk4_1.is_printing', 'name': 'Is Printing', 'equipment': 'prusa_mk4_1', 'data_type': TagDataType.BOOLEAN, 'category': TagCategory.DIGITAL_INPUT},

        # CNC Mill tags
        {'tag_id': 'cnc_mill_1.spindle_rpm', 'name': 'Spindle RPM', 'equipment': 'cnc_mill_1', 'data_type': TagDataType.FLOAT32, 'category': TagCategory.ANALOG_INPUT, 'eng_units': 'RPM', 'eng_high': 24000},
        {'tag_id': 'cnc_mill_1.spindle_load', 'name': 'Spindle Load', 'equipment': 'cnc_mill_1', 'data_type': TagDataType.FLOAT32, 'category': TagCategory.ANALOG_INPUT, 'eng_units': '%'},
        {'tag_id': 'cnc_mill_1.feed_rate', 'name': 'Feed Rate', 'equipment': 'cnc_mill_1', 'data_type': TagDataType.FLOAT32, 'category': TagCategory.ANALOG_INPUT, 'eng_units': 'mm/min'},
        {'tag_id': 'cnc_mill_1.coolant_on', 'name': 'Coolant On', 'equipment': 'cnc_mill_1', 'data_type': TagDataType.BOOLEAN, 'category': TagCategory.DIGITAL_INPUT},
        {'tag_id': 'cnc_mill_1.vibration_x', 'name': 'X Vibration', 'equipment': 'cnc_mill_1', 'data_type': TagDataType.FLOAT32, 'category': TagCategory.ANALOG_INPUT, 'eng_units': 'g'},
        {'tag_id': 'cnc_mill_1.vibration_y', 'name': 'Y Vibration', 'equipment': 'cnc_mill_1', 'data_type': TagDataType.FLOAT32, 'category': TagCategory.ANALOG_INPUT, 'eng_units': 'g'},

        # Robot tags
        {'tag_id': 'niryo_ned2_1.joint_1', 'name': 'Joint 1 Angle', 'equipment': 'niryo_ned2_1', 'data_type': TagDataType.FLOAT32, 'category': TagCategory.ANALOG_INPUT, 'eng_units': 'deg'},
        {'tag_id': 'niryo_ned2_1.gripper_state', 'name': 'Gripper State', 'equipment': 'niryo_ned2_1', 'data_type': TagDataType.STRING, 'category': TagCategory.STATUS},
        {'tag_id': 'niryo_ned2_1.is_moving', 'name': 'Is Moving', 'equipment': 'niryo_ned2_1', 'data_type': TagDataType.BOOLEAN, 'category': TagCategory.DIGITAL_INPUT},
    ]

    for t_data in tags:
        existing = session.query(Tag).filter_by(tag_id=t_data['tag_id']).first()
        if not existing:
            tag = Tag(**t_data)
            session.add(tag)

    session.commit()
    print(f"✓ Seeded {len(tags)} tags")


def seed_scada_alarms(session):
    """Seed alarm definitions."""
    from models.scada.alarms import AlarmDefinition, AlarmPriority, AlarmClass, AlarmType
    from models.scada.tags import Tag

    # Define alarms with tag_id string references
    alarms = [
        {'alarm_id': 'ALM-001', 'name': 'Hotend Over Temperature', 'tag_ref': 'prusa_mk4_1.hotend_temp', 'alarm_type': AlarmType.HIGH, 'priority': AlarmPriority.HIGH, 'alarm_class': AlarmClass.PROCESS, 'setpoint': 260, 'description': 'Hotend temperature exceeded safe limit'},
        {'alarm_id': 'ALM-002', 'name': 'Hotend Under Temperature', 'tag_ref': 'prusa_mk4_1.hotend_temp', 'alarm_type': AlarmType.LOW, 'priority': AlarmPriority.MEDIUM, 'alarm_class': AlarmClass.PROCESS, 'setpoint': 180, 'description': 'Hotend temperature below printing threshold'},
        {'alarm_id': 'ALM-003', 'name': 'Spindle Overload', 'tag_ref': 'cnc_mill_1.spindle_load', 'alarm_type': AlarmType.HIGH, 'priority': AlarmPriority.EMERGENCY, 'alarm_class': AlarmClass.SAFETY, 'setpoint': 90, 'description': 'Spindle load exceeded safe limit'},
        {'alarm_id': 'ALM-004', 'name': 'High Vibration X', 'tag_ref': 'cnc_mill_1.vibration_x', 'alarm_type': AlarmType.HIGH, 'priority': AlarmPriority.MEDIUM, 'alarm_class': AlarmClass.DIAGNOSTIC, 'setpoint': 0.5, 'description': 'Excessive vibration detected on X axis'},
        {'alarm_id': 'ALM-005', 'name': 'Bed Over Temperature', 'tag_ref': 'prusa_mk4_1.bed_temp', 'alarm_type': AlarmType.HIGH, 'priority': AlarmPriority.MEDIUM, 'alarm_class': AlarmClass.PROCESS, 'setpoint': 100, 'description': 'Bed temperature exceeded limit'},
    ]

    count = 0
    for a_data in alarms:
        existing = session.query(AlarmDefinition).filter_by(alarm_id=a_data['alarm_id']).first()
        if not existing:
            # Look up the actual tag UUID by its tag_id string
            tag_ref = a_data.pop('tag_ref')
            tag = session.query(Tag).filter_by(tag_id=tag_ref).first()
            if tag:
                a_data['tag_id'] = tag.id
                alarm = AlarmDefinition(**a_data)
                session.add(alarm)
                count += 1
            else:
                print(f"  Warning: Tag '{tag_ref}' not found for alarm '{a_data['alarm_id']}'")

    session.commit()
    print(f"✓ Seeded {count} alarm definitions")


def seed_scada_recipes(session):
    """Seed recipe data."""
    from models.scada.recipes import MasterRecipe, RecipeStatus, RecipeType

    recipes = [
        {
            'recipe_id': 'RCP-001',
            'name': '2x4 Standard Brick',
            'description': 'Standard 2x4 LEGO brick production recipe',
            'product_id': 'brick_2x4',
            'recipe_type': RecipeType.MASTER,
            'recipe_version': '1.0',
            'status': RecipeStatus.APPROVED,
            'parameters': {
                'layer_height': 0.2,
                'infill': 20,
                'print_speed': 60,
                'hotend_temp': 215,
                'bed_temp': 60,
                'material': 'PLA',
            },
            'print_profile': {
                'layer_height': 0.2,
                'infill_percent': 20,
                'supports': False,
            },
        },
        {
            'recipe_id': 'RCP-002',
            'name': '2x2 Standard Brick',
            'description': 'Standard 2x2 LEGO brick production recipe',
            'product_id': 'brick_2x2',
            'recipe_type': RecipeType.MASTER,
            'recipe_version': '1.0',
            'status': RecipeStatus.APPROVED,
            'parameters': {
                'layer_height': 0.2,
                'infill': 20,
                'print_speed': 60,
                'hotend_temp': 215,
                'bed_temp': 60,
                'material': 'PLA',
            },
            'print_profile': {
                'layer_height': 0.2,
                'infill_percent': 20,
                'supports': False,
            },
        },
        {
            'recipe_id': 'RCP-003',
            'name': '1x4 Plate',
            'description': 'Standard 1x4 LEGO plate production recipe',
            'product_id': 'plate_1x4',
            'recipe_type': RecipeType.MASTER,
            'recipe_version': '1.0',
            'status': RecipeStatus.APPROVED,
            'parameters': {
                'layer_height': 0.15,
                'infill': 15,
                'print_speed': 50,
                'hotend_temp': 210,
                'bed_temp': 55,
                'material': 'PLA',
            },
            'print_profile': {
                'layer_height': 0.15,
                'infill_percent': 15,
                'supports': False,
            },
        },
    ]

    for r_data in recipes:
        existing = session.query(MasterRecipe).filter_by(recipe_id=r_data['recipe_id']).first()
        if not existing:
            recipe = MasterRecipe(**r_data)
            session.add(recipe)

    session.commit()
    print(f"✓ Seeded {len(recipes)} recipes")


def seed_mes_work_orders(session):
    """Seed work order data."""
    from models.mes.work_orders import WorkOrder, Operation, Job, WorkOrderStatus, JobStatus, OperationType

    work_orders = [
        {
            'work_order_id': 'WO-2026-001',
            'description': 'Production run for red 2x4 bricks',
            'product_id': 'brick_2x4_red',
            'recipe_id': 'RCP-001',
            'quantity_ordered': 100,
            'quantity_completed': 45,
            'status': WorkOrderStatus.IN_PROGRESS,
            'priority': 2,
            'planned_start': datetime.now() - timedelta(days=1),
            'due_date': datetime.now() + timedelta(days=3),
            'customer_id': 'CUST001',
        },
        {
            'work_order_id': 'WO-2026-002',
            'description': 'Production run for blue 2x2 bricks',
            'product_id': 'brick_2x2_blue',
            'recipe_id': 'RCP-002',
            'quantity_ordered': 200,
            'quantity_completed': 0,
            'status': WorkOrderStatus.PLANNED,
            'priority': 3,
            'planned_start': datetime.now() + timedelta(days=1),
            'due_date': datetime.now() + timedelta(days=5),
            'customer_id': 'CUST002',
        },
        {
            'work_order_id': 'WO-2026-003',
            'description': 'Custom yellow brick order',
            'product_id': 'brick_2x4_yellow',
            'recipe_id': 'RCP-001',
            'quantity_ordered': 50,
            'quantity_completed': 50,
            'status': WorkOrderStatus.COMPLETED,
            'priority': 1,
            'planned_start': datetime.now() - timedelta(days=3),
            'actual_start': datetime.now() - timedelta(days=3),
            'actual_end': datetime.now() - timedelta(days=1),
            'due_date': datetime.now(),
            'customer_id': 'CUST001',
        },
    ]

    for wo_data in work_orders:
        existing = session.query(WorkOrder).filter_by(work_order_id=wo_data['work_order_id']).first()
        if not existing:
            wo = WorkOrder(**wo_data)
            session.add(wo)
            session.flush()

            # Add operations
            ops = [
                {'operation_id': f"{wo.work_order_id}-OP10", 'sequence': 10, 'operation_type': OperationType.DESIGN, 'name': 'Design Review', 'run_time': 30},
                {'operation_id': f"{wo.work_order_id}-OP20", 'sequence': 20, 'operation_type': OperationType.PRINTING_FDM, 'name': 'Print Bricks', 'run_time': 180},
                {'operation_id': f"{wo.work_order_id}-OP30", 'sequence': 30, 'operation_type': OperationType.INSPECTION, 'name': 'Quality Check', 'run_time': 15},
            ]
            for op_data in ops:
                op = Operation(work_order_id=wo.id, **op_data)
                session.add(op)

    session.commit()
    print(f"✓ Seeded {len(work_orders)} work orders")


def seed_mes_workers(session):
    """Seed worker data."""
    from models.mes.labor import Worker, Skill, WorkerStatus, SkillLevel

    workers = [
        {'employee_id': 'EMP001', 'first_name': 'John', 'last_name': 'Smith', 'email': 'john.smith@legofactory.com', 'department': 'Production', 'status': WorkerStatus.ACTIVE},
        {'employee_id': 'EMP002', 'first_name': 'Sarah', 'last_name': 'Johnson', 'email': 'sarah.j@legofactory.com', 'department': 'Quality', 'status': WorkerStatus.ACTIVE},
        {'employee_id': 'EMP003', 'first_name': 'Mike', 'last_name': 'Chen', 'email': 'mike.chen@legofactory.com', 'department': 'Maintenance', 'status': WorkerStatus.ACTIVE},
        {'employee_id': 'EMP004', 'first_name': 'Emily', 'last_name': 'Davis', 'email': 'emily.d@legofactory.com', 'department': 'Production', 'status': WorkerStatus.ACTIVE},
    ]

    for w_data in workers:
        existing = session.query(Worker).filter_by(employee_id=w_data['employee_id']).first()
        if not existing:
            worker = Worker(**w_data)
            session.add(worker)

    session.commit()
    print(f"✓ Seeded {len(workers)} workers")


def seed_erp_partners(session):
    """Seed customer and vendor data."""
    from models.erp.partners import Partner, PartnerType, PartnerStatus

    partners = [
        {'partner_id': 'CUST001', 'name': 'Brick Builders Inc', 'partner_type': PartnerType.CUSTOMER, 'email': 'orders@brickbuilders.com', 'phone': '555-0101', 'status': PartnerStatus.ACTIVE, 'credit_limit': 50000},
        {'partner_id': 'CUST002', 'name': 'LEGO World Shop', 'partner_type': PartnerType.CUSTOMER, 'email': 'purchasing@legoworld.com', 'phone': '555-0102', 'status': PartnerStatus.ACTIVE, 'credit_limit': 100000},
        {'partner_id': 'CUST003', 'name': 'Creative Blocks LLC', 'partner_type': PartnerType.CUSTOMER, 'email': 'orders@creativeblocks.com', 'phone': '555-0103', 'status': PartnerStatus.ACTIVE, 'credit_limit': 25000},
        {'partner_id': 'VEND001', 'name': 'Filament Supply Co', 'partner_type': PartnerType.VENDOR, 'email': 'sales@filamentsupply.com', 'phone': '555-0201', 'status': PartnerStatus.ACTIVE},
        {'partner_id': 'VEND002', 'name': 'Industrial Plastics Ltd', 'partner_type': PartnerType.VENDOR, 'email': 'orders@indplastics.com', 'phone': '555-0202', 'status': PartnerStatus.ACTIVE},
    ]

    for p_data in partners:
        existing = session.query(Partner).filter_by(partner_id=p_data['partner_id']).first()
        if not existing:
            partner = Partner(**p_data)
            session.add(partner)

    session.commit()
    print(f"✓ Seeded {len(partners)} partners")


def seed_erp_items(session):
    """Seed inventory items."""
    from models.erp.items import Item, ItemCategory, ItemType, ItemStatus

    # Seed categories first
    categories = [
        {'code': 'CAT-BRICK', 'name': 'Standard Bricks', 'description': 'Standard LEGO-compatible bricks'},
        {'code': 'CAT-PLATE', 'name': 'Plates', 'description': 'Flat plate elements'},
        {'code': 'CAT-TILE', 'name': 'Tiles', 'description': 'Smooth top tiles'},
        {'code': 'CAT-RAW', 'name': 'Raw Materials', 'description': 'Filament and raw materials'},
    ]

    cat_map = {}
    for c_data in categories:
        existing = session.query(ItemCategory).filter_by(code=c_data['code']).first()
        if not existing:
            cat = ItemCategory(**c_data)
            session.add(cat)
            session.flush()
            cat_map[c_data['code']] = cat.id
        else:
            cat_map[c_data['code']] = existing.id

    items = [
        {'item_id': 'brick_2x4_red', 'name': '2x4 Brick Red', 'cat_code': 'CAT-BRICK', 'item_type': ItemType.FINISHED_GOOD, 'status': ItemStatus.ACTIVE, 'standard_cost': 0.15, 'list_price': 0.35, 'reorder_point': 100, 'reorder_quantity': 500},
        {'item_id': 'brick_2x4_blue', 'name': '2x4 Brick Blue', 'cat_code': 'CAT-BRICK', 'item_type': ItemType.FINISHED_GOOD, 'status': ItemStatus.ACTIVE, 'standard_cost': 0.15, 'list_price': 0.35, 'reorder_point': 100, 'reorder_quantity': 500},
        {'item_id': 'brick_2x4_yellow', 'name': '2x4 Brick Yellow', 'cat_code': 'CAT-BRICK', 'item_type': ItemType.FINISHED_GOOD, 'status': ItemStatus.ACTIVE, 'standard_cost': 0.15, 'list_price': 0.35, 'reorder_point': 100, 'reorder_quantity': 500},
        {'item_id': 'brick_2x4_white', 'name': '2x4 Brick White', 'cat_code': 'CAT-BRICK', 'item_type': ItemType.FINISHED_GOOD, 'status': ItemStatus.ACTIVE, 'standard_cost': 0.15, 'list_price': 0.35, 'reorder_point': 100, 'reorder_quantity': 500},
        {'item_id': 'brick_2x2_red', 'name': '2x2 Brick Red', 'cat_code': 'CAT-BRICK', 'item_type': ItemType.FINISHED_GOOD, 'status': ItemStatus.ACTIVE, 'standard_cost': 0.08, 'list_price': 0.25, 'reorder_point': 200, 'reorder_quantity': 1000},
        {'item_id': 'brick_2x2_blue', 'name': '2x2 Brick Blue', 'cat_code': 'CAT-BRICK', 'item_type': ItemType.FINISHED_GOOD, 'status': ItemStatus.ACTIVE, 'standard_cost': 0.08, 'list_price': 0.25, 'reorder_point': 200, 'reorder_quantity': 1000},
        {'item_id': 'plate_1x4_white', 'name': '1x4 Plate White', 'cat_code': 'CAT-PLATE', 'item_type': ItemType.FINISHED_GOOD, 'status': ItemStatus.ACTIVE, 'standard_cost': 0.05, 'list_price': 0.15, 'reorder_point': 300, 'reorder_quantity': 1500},
        {'item_id': 'filament_pla_red', 'name': 'PLA Filament Red 1kg', 'cat_code': 'CAT-RAW', 'item_type': ItemType.RAW_MATERIAL, 'status': ItemStatus.ACTIVE, 'standard_cost': 18.00, 'list_price': 0, 'reorder_point': 10, 'reorder_quantity': 50},
        {'item_id': 'filament_pla_blue', 'name': 'PLA Filament Blue 1kg', 'cat_code': 'CAT-RAW', 'item_type': ItemType.RAW_MATERIAL, 'status': ItemStatus.ACTIVE, 'standard_cost': 18.00, 'list_price': 0, 'reorder_point': 10, 'reorder_quantity': 50},
        {'item_id': 'filament_pla_yellow', 'name': 'PLA Filament Yellow 1kg', 'cat_code': 'CAT-RAW', 'item_type': ItemType.RAW_MATERIAL, 'status': ItemStatus.ACTIVE, 'standard_cost': 18.00, 'list_price': 0, 'reorder_point': 10, 'reorder_quantity': 50},
        {'item_id': 'filament_pla_white', 'name': 'PLA Filament White 1kg', 'cat_code': 'CAT-RAW', 'item_type': ItemType.RAW_MATERIAL, 'status': ItemStatus.ACTIVE, 'standard_cost': 18.00, 'list_price': 0, 'reorder_point': 10, 'reorder_quantity': 50},
    ]

    for i_data in items:
        existing = session.query(Item).filter_by(item_id=i_data['item_id']).first()
        if not existing:
            cat_code = i_data.pop('cat_code')
            i_data['category_id'] = cat_map.get(cat_code)
            item = Item(**i_data)
            session.add(item)

    session.commit()
    print(f"✓ Seeded {len(items)} items")


def seed_erp_sales_orders(session):
    """Seed sales order data."""
    from models.erp.sales import SalesOrder, SalesOrderLine, SalesOrderStatus
    from models.erp.partners import Partner
    from models.erp.items import Item

    # Look up customer UUIDs
    cust_map = {}
    for partner in session.query(Partner).filter(Partner.partner_id.like('CUST%')).all():
        cust_map[partner.partner_id] = partner.id

    # Look up item UUIDs
    item_map = {}
    for item in session.query(Item).all():
        item_map[item.item_id] = item.id

    orders = [
        {
            'order_number': 'SO-2026-001',
            'cust_ref': 'CUST001',
            'status': SalesOrderStatus.RELEASED,
            'order_date': (datetime.now() - timedelta(days=2)).date(),
            'requested_date': (datetime.now() + timedelta(days=5)).date(),
            'lines': [
                {'item_ref': 'brick_2x4_red', 'quantity_ordered': 100, 'unit_price': 0.35},
                {'item_ref': 'brick_2x2_blue', 'quantity_ordered': 200, 'unit_price': 0.25},
            ],
        },
        {
            'order_number': 'SO-2026-002',
            'cust_ref': 'CUST002',
            'status': SalesOrderStatus.APPROVED,
            'order_date': (datetime.now() - timedelta(days=1)).date(),
            'requested_date': (datetime.now() + timedelta(days=7)).date(),
            'lines': [
                {'item_ref': 'brick_2x4_yellow', 'quantity_ordered': 500, 'unit_price': 0.35},
                {'item_ref': 'plate_1x4_white', 'quantity_ordered': 300, 'unit_price': 0.15},
            ],
        },
        {
            'order_number': 'SO-2026-003',
            'cust_ref': 'CUST003',
            'status': SalesOrderStatus.DRAFT,
            'order_date': datetime.now().date(),
            'requested_date': (datetime.now() + timedelta(days=10)).date(),
            'lines': [
                {'item_ref': 'brick_2x4_white', 'quantity_ordered': 1000, 'unit_price': 0.35},
            ],
        },
    ]

    count = 0
    for so_data in orders:
        existing = session.query(SalesOrder).filter_by(order_number=so_data['order_number']).first()
        if not existing:
            lines = so_data.pop('lines')
            cust_ref = so_data.pop('cust_ref')
            so_data['customer_id'] = cust_map.get(cust_ref)
            if so_data['customer_id']:
                so = SalesOrder(**so_data)
                session.add(so)
                session.flush()
                count += 1

                for idx, line_data in enumerate(lines, 1):
                    item_ref = line_data.pop('item_ref')
                    line_data['item_id'] = item_map.get(item_ref)
                    if line_data['item_id']:
                        sol = SalesOrderLine(
                            order_id=so.id,
                            line_number=idx * 10,
                            **line_data
                        )
                        session.add(sol)

    session.commit()
    print(f"✓ Seeded {count} sales orders")


def seed_qms_documents(session):
    """Seed QMS document data."""
    from models.qms.documents import Document, DocumentType, DocumentStatus

    documents = [
        {'document_number': 'SOP-001', 'title': '3D Printer Operation Procedure', 'document_type': DocumentType.PROCEDURE, 'status': DocumentStatus.APPROVED, 'revision': 'A', 'department': 'Production'},
        {'document_number': 'SOP-002', 'title': 'Quality Inspection Procedure', 'document_type': DocumentType.PROCEDURE, 'status': DocumentStatus.APPROVED, 'revision': 'B', 'department': 'Quality'},
        {'document_number': 'WI-001', 'title': 'Brick Dimension Measurement', 'document_type': DocumentType.PROCEDURE, 'status': DocumentStatus.APPROVED, 'revision': 'A', 'department': 'Quality'},
        {'document_number': 'SPEC-001', 'title': 'LEGO Brick Specifications', 'document_type': DocumentType.SPECIFICATION, 'status': DocumentStatus.APPROVED, 'revision': 'C', 'department': 'Engineering'},
        {'document_number': 'FORM-001', 'title': 'Inspection Checklist', 'document_type': DocumentType.FORM, 'status': DocumentStatus.APPROVED, 'revision': 'A', 'department': 'Quality'},
    ]

    for d_data in documents:
        existing = session.query(Document).filter_by(document_number=d_data['document_number']).first()
        if not existing:
            doc = Document(**d_data)
            session.add(doc)

    session.commit()
    print(f"✓ Seeded {len(documents)} documents")


def seed_qms_ncrs(session):
    """Seed NCR data."""
    from models.qms.ncr_capa import NonConformanceReport, NCRStatus, NCRType, Severity

    ncrs = [
        {'ncr_number': 'NCR-2026-001', 'title': 'Dimensional variance on 2x4 bricks', 'description': 'Studs measuring 4.82mm instead of 4.8mm on batch B2026-01', 'ncr_type': NCRType.INTERNAL, 'severity': Severity.MINOR, 'status': NCRStatus.SUBMITTED, 'detected_by': 'QC Inspector', 'detection_stage': 'in_process', 'item_id': 'brick_2x4_red', 'quantity_affected': 50},
        {'ncr_number': 'NCR-2026-002', 'title': 'Color variation in yellow bricks', 'description': 'Slight color variation between batches', 'ncr_type': NCRType.CUSTOMER_COMPLAINT, 'severity': Severity.MINOR, 'status': NCRStatus.UNDER_INVESTIGATION, 'detected_by': 'Customer Service', 'detection_stage': 'customer', 'item_id': 'brick_2x4_yellow', 'quantity_affected': 100},
        {'ncr_number': 'NCR-2026-003', 'title': 'Surface finish defect', 'description': 'Visible layer lines exceeding acceptable limits', 'ncr_type': NCRType.PRODUCT, 'severity': Severity.MAJOR, 'status': NCRStatus.CLOSED, 'detected_by': 'QC Inspector', 'detection_stage': 'final', 'item_id': 'brick_2x2_blue', 'quantity_affected': 25},
    ]

    for n_data in ncrs:
        existing = session.query(NonConformanceReport).filter_by(ncr_number=n_data['ncr_number']).first()
        if not existing:
            ncr = NonConformanceReport(**n_data)
            session.add(ncr)

    session.commit()
    print(f"✓ Seeded {len(ncrs)} NCRs")


def seed_cmms_assets(session):
    """Seed asset data."""
    from models.cmms.assets import Asset, AssetClass, AssetStatus, AssetCriticality

    # Seed asset classes
    classes = [
        {'code': 'CLS-3DPRINTER', 'name': '3D Printers', 'description': 'FDM and SLA 3D printers'},
        {'code': 'CLS-CNC', 'name': 'CNC Machines', 'description': 'CNC mills and lathes'},
        {'code': 'CLS-ROBOT', 'name': 'Robots', 'description': 'Industrial and collaborative robots'},
        {'code': 'CLS-CONVEYOR', 'name': 'Conveyors', 'description': 'Material handling conveyors'},
    ]

    class_map = {}
    for c_data in classes:
        existing = session.query(AssetClass).filter_by(code=c_data['code']).first()
        if not existing:
            ac = AssetClass(**c_data)
            session.add(ac)
            session.flush()
            class_map[c_data['code']] = ac.id
        else:
            class_map[c_data['code']] = existing.id

    assets = [
        {'asset_id': 'AST-PRUSA-001', 'name': 'Prusa MK4 #1', 'class_ref': 'CLS-3DPRINTER', 'serial_number': 'PRUSA-MK4-2024-001', 'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.ESSENTIAL, 'location_description': 'Building A, Cell 1', 'purchase_date': datetime(2024, 1, 15).date(), 'warranty_expiry': datetime(2026, 1, 15).date(), 'purchase_cost': 999.00},
        {'asset_id': 'AST-PRUSA-002', 'name': 'Prusa MK4 #2', 'class_ref': 'CLS-3DPRINTER', 'serial_number': 'PRUSA-MK4-2024-002', 'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.ESSENTIAL, 'location_description': 'Building A, Cell 1', 'purchase_date': datetime(2024, 2, 1).date(), 'warranty_expiry': datetime(2026, 2, 1).date(), 'purchase_cost': 999.00},
        {'asset_id': 'AST-BAMBU-001', 'name': 'Bambu X1 Carbon', 'class_ref': 'CLS-3DPRINTER', 'serial_number': 'BBL-X1C-2024-001', 'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.ESSENTIAL, 'location_description': 'Building A, Cell 2', 'purchase_date': datetime(2024, 3, 1).date(), 'warranty_expiry': datetime(2025, 3, 1).date(), 'purchase_cost': 1449.00},
        {'asset_id': 'AST-CNC-001', 'name': 'CNC Mill #1', 'class_ref': 'CLS-CNC', 'serial_number': 'CNC-2023-001', 'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.CRITICAL, 'location_description': 'Building B, Machining', 'purchase_date': datetime(2023, 6, 1).date(), 'warranty_expiry': datetime(2025, 6, 1).date(), 'purchase_cost': 15000.00},
        {'asset_id': 'AST-NIRYO-001', 'name': 'Niryo Ned2 #1', 'class_ref': 'CLS-ROBOT', 'serial_number': 'NIRYO-NED2-2024-001', 'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.IMPORTANT, 'location_description': 'Building A, Assembly', 'purchase_date': datetime(2024, 4, 1).date(), 'warranty_expiry': datetime(2026, 4, 1).date(), 'purchase_cost': 3990.00},
    ]

    for a_data in assets:
        existing = session.query(Asset).filter_by(asset_id=a_data['asset_id']).first()
        if not existing:
            class_ref = a_data.pop('class_ref')
            a_data['asset_class_id'] = class_map.get(class_ref)
            asset = Asset(**a_data)
            session.add(asset)

    session.commit()
    print(f"✓ Seeded {len(assets)} assets")


def seed_lego_colors(session):
    """Seed LEGO colors."""
    from models.lego.brick_designs import BrickColor

    colors = [
        {'color_id': 1, 'name': 'White', 'hex_code': '#FFFFFF', 'rgb_r': 255, 'rgb_g': 255, 'rgb_b': 255, 'ldraw_id': 15, 'is_current': True},
        {'color_id': 5, 'name': 'Brick Yellow', 'hex_code': '#D9BB7B', 'rgb_r': 217, 'rgb_g': 187, 'rgb_b': 123, 'ldraw_id': 19, 'is_current': True},
        {'color_id': 21, 'name': 'Bright Red', 'hex_code': '#C91A09', 'rgb_r': 201, 'rgb_g': 26, 'rgb_b': 9, 'ldraw_id': 4, 'is_current': True},
        {'color_id': 23, 'name': 'Bright Blue', 'hex_code': '#0055BF', 'rgb_r': 0, 'rgb_g': 85, 'rgb_b': 191, 'ldraw_id': 1, 'is_current': True},
        {'color_id': 24, 'name': 'Bright Yellow', 'hex_code': '#F2CD37', 'rgb_r': 242, 'rgb_g': 205, 'rgb_b': 55, 'ldraw_id': 14, 'is_current': True},
        {'color_id': 26, 'name': 'Black', 'hex_code': '#05131D', 'rgb_r': 5, 'rgb_g': 19, 'rgb_b': 29, 'ldraw_id': 0, 'is_current': True},
        {'color_id': 28, 'name': 'Dark Green', 'hex_code': '#237841', 'rgb_r': 35, 'rgb_g': 120, 'rgb_b': 65, 'ldraw_id': 2, 'is_current': True},
        {'color_id': 37, 'name': 'Bright Green', 'hex_code': '#4B9F4A', 'rgb_r': 75, 'rgb_g': 159, 'rgb_b': 74, 'ldraw_id': 10, 'is_current': True},
        {'color_id': 102, 'name': 'Medium Blue', 'hex_code': '#5A93DB', 'rgb_r': 90, 'rgb_g': 147, 'rgb_b': 219, 'ldraw_id': 42, 'is_current': True},
        {'color_id': 106, 'name': 'Bright Orange', 'hex_code': '#E76318', 'rgb_r': 231, 'rgb_g': 99, 'rgb_b': 24, 'ldraw_id': 25, 'is_current': True},
        {'color_id': 119, 'name': 'Bright Yellowish Green', 'hex_code': '#95B90B', 'rgb_r': 149, 'rgb_g': 185, 'rgb_b': 11, 'ldraw_id': 27, 'is_current': True},
        {'color_id': 124, 'name': 'Bright Reddish Violet', 'hex_code': '#923978', 'rgb_r': 146, 'rgb_g': 57, 'rgb_b': 120, 'ldraw_id': 5, 'is_current': True},
        {'color_id': 192, 'name': 'Reddish Brown', 'hex_code': '#582A12', 'rgb_r': 88, 'rgb_g': 42, 'rgb_b': 18, 'ldraw_id': 70, 'is_current': True},
        {'color_id': 194, 'name': 'Medium Stone Grey', 'hex_code': '#A0A5A9', 'rgb_r': 160, 'rgb_g': 165, 'rgb_b': 169, 'ldraw_id': 71, 'is_current': True},
        {'color_id': 199, 'name': 'Dark Stone Grey', 'hex_code': '#6C6E68', 'rgb_r': 108, 'rgb_g': 110, 'rgb_b': 104, 'ldraw_id': 72, 'is_current': True},
    ]

    for c_data in colors:
        existing = session.query(BrickColor).filter_by(color_id=c_data['color_id']).first()
        if not existing:
            color = BrickColor(**c_data)
            session.add(color)

    session.commit()
    print(f"✓ Seeded {len(colors)} LEGO colors")


def seed_ml_models(session):
    """Seed ML model data."""
    from models.ml.ml_models import MLModel, ModelType, ModelStatus

    models = [
        {
            'model_id': 'mm-dtae-lstm-v1',
            'name': 'MM-DTAE-LSTM Fingerprinter',
            'description': 'Multimodal Deep Transformer Autoencoder with LSTM for G-code fingerprinting',
            'model_type': ModelType.MM_DTAE_LSTM,
            'model_version': '1.0.0',
            'status': ModelStatus.READY,
            'hyperparameters': {
                'embedding_dim': 256,
                'num_heads': 8,
                'num_layers': 4,
                'lstm_hidden': 128,
                'dropout': 0.1,
            },
            'input_shape': [1, 512, 668],
            'output_shape': [1, 256],
            'training_samples': 50000,
            'metrics': {'accuracy': 0.90, 'loss': 0.15},
        },
        {
            'model_id': 'anomaly-detector-v1',
            'name': 'Sensor Anomaly Detector',
            'description': 'Detects anomalies in sensor readings',
            'model_type': ModelType.ANOMALY_DETECTOR,
            'model_version': '1.0.0',
            'status': ModelStatus.READY,
            'hyperparameters': {
                'threshold': 0.5,
                'window_size': 100,
            },
            'input_shape': [1, 100, 6],
            'output_shape': [1, 1],
            'training_samples': 100000,
            'metrics': {'precision': 0.92, 'recall': 0.88, 'f1': 0.90},
        },
        {
            'model_id': 'tool-wear-v1',
            'name': 'Tool Wear Predictor',
            'description': 'Predicts remaining tool life based on sensor data',
            'model_type': ModelType.TOOL_WEAR_PREDICTOR,
            'model_version': '1.0.0',
            'status': ModelStatus.READY,
            'hyperparameters': {
                'prediction_horizon': 60,
            },
            'input_shape': [1, 50, 8],
            'output_shape': [1, 1],
            'training_samples': 25000,
            'metrics': {'mae': 5.2, 'rmse': 7.8},
        },
    ]

    for m_data in models:
        existing = session.query(MLModel).filter_by(model_id=m_data['model_id']).first()
        if not existing:
            model = MLModel(**m_data)
            session.add(model)

    session.commit()
    print(f"✓ Seeded {len(models)} ML models")


def main():
    """Run all seeders."""
    print("\n" + "="*50)
    print("LEGO Factory v3 - Database Seeder")
    print("="*50 + "\n")

    engine = get_engine()

    # Create tables
    create_tables(engine)

    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Seed all modules
        seed_scada_machines(session)
        seed_scada_tags(session)
        seed_scada_alarms(session)
        seed_scada_recipes(session)

        seed_mes_work_orders(session)
        seed_mes_workers(session)

        seed_erp_partners(session)
        seed_erp_items(session)
        seed_erp_sales_orders(session)

        seed_qms_documents(session)
        seed_qms_ncrs(session)

        seed_cmms_assets(session)

        seed_lego_colors(session)
        seed_ml_models(session)

        print("\n" + "="*50)
        print("✓ All seed data loaded successfully!")
        print("="*50 + "\n")

    except Exception as e:
        session.rollback()
        print(f"\n✗ Error seeding database: {e}")
        raise
    finally:
        session.close()


if __name__ == '__main__':
    main()
