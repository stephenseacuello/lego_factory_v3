"""
LEGO Factory v3 - Machine Seed Script
======================================
Seeds the database with configured machines.
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.base import Base
from models.scada.machines import Machine, MachineType, ControllerType, MachineState, ConnectionType


def load_machine_config():
    """Load machine configuration from JSON file."""
    config_path = Path(__file__).parent.parent.parent / 'config' / 'machines.json'
    with open(config_path, 'r') as f:
        return json.load(f)


def seed_machines(session):
    """Seed machines from configuration."""
    config = load_machine_config()

    machines_added = 0
    machines_updated = 0

    for machine_data in config.get('machines', []):
        # Check if machine already exists
        existing = session.query(Machine).filter_by(
            machine_id=machine_data['machine_id']
        ).first()

        # Map string types to enums
        machine_type = MachineType(machine_data['machine_type'])
        controller_type = ControllerType(machine_data['controller_type'])
        connection_type = ConnectionType(machine_data['connection_type'])

        if existing:
            # Update existing machine
            existing.name = machine_data['name']
            existing.description = machine_data.get('description')
            existing.machine_type = machine_type
            existing.controller_type = controller_type
            existing.connection_type = connection_type
            existing.connection_config = machine_data['connection_config']
            existing.area = machine_data.get('area')
            existing.cell = machine_data.get('cell')
            existing.axes = machine_data.get('axes', 3)
            existing.has_spindle = machine_data.get('has_spindle', False)
            existing.has_tool_changer = machine_data.get('has_tool_changer', False)
            existing.has_coolant = machine_data.get('has_coolant', False)
            existing.max_feed_rate = machine_data.get('max_feed_rate')
            existing.max_spindle_rpm = machine_data.get('max_spindle_rpm')
            existing.work_envelope_x = machine_data.get('work_envelope_x')
            existing.work_envelope_y = machine_data.get('work_envelope_y')
            existing.work_envelope_z = machine_data.get('work_envelope_z')
            existing.enabled = machine_data.get('enabled', True)
            machines_updated += 1
            print(f"  Updated: {machine_data['name']}")
        else:
            # Create new machine
            machine = Machine(
                machine_id=machine_data['machine_id'],
                name=machine_data['name'],
                description=machine_data.get('description'),
                machine_type=machine_type,
                controller_type=controller_type,
                connection_type=connection_type,
                connection_config=machine_data['connection_config'],
                area=machine_data.get('area'),
                cell=machine_data.get('cell'),
                axes=machine_data.get('axes', 3),
                has_spindle=machine_data.get('has_spindle', False),
                has_tool_changer=machine_data.get('has_tool_changer', False),
                has_coolant=machine_data.get('has_coolant', False),
                max_feed_rate=machine_data.get('max_feed_rate'),
                max_spindle_rpm=machine_data.get('max_spindle_rpm'),
                work_envelope_x=machine_data.get('work_envelope_x'),
                work_envelope_y=machine_data.get('work_envelope_y'),
                work_envelope_z=machine_data.get('work_envelope_z'),
                enabled=machine_data.get('enabled', True),
                current_state=MachineState.DISCONNECTED,
            )
            session.add(machine)
            machines_added += 1
            print(f"  Added: {machine_data['name']}")

    session.commit()
    print(f"\nMachines seeded: {machines_added} added, {machines_updated} updated")
    return machines_added, machines_updated


def main():
    """Main entry point."""
    # Database URL from environment (required)
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is required.")
        print("Set it in your .env file or export it before running this script.")
        print("Example: export DATABASE_URL=postgresql://lego:YOUR_PASSWORD@localhost:5434/lego_factory")
        sys.exit(1)

    print(f"Connecting to: {database_url.split('@')[1] if '@' in database_url else database_url}")

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("\nSeeding machines...")
        seed_machines(session)
        print("\nDone!")
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == '__main__':
    main()
