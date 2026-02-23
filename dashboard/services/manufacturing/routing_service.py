"""
Routing Service

Manages manufacturing routings:
- Auto-generation from part type
- Operation sequence management
- Time standard calculation
- Work center assignment
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from models import Part, WorkCenter, Routing
from models.manufacturing import WorkCenterStatus


# Default routing templates by part type
ROUTING_TEMPLATES = {
    'standard': [
        {
            'sequence': 10,
            'operation_code': 'DESIGN',
            'description': 'CAD design and verification in Fusion 360',
            'work_center_type': 'DESIGN_WORKSTATION',
            'setup_time_min': 5,
            'run_time_min': 15,
        },
        {
            'sequence': 20,
            'operation_code': 'SLICE',
            'description': 'Generate G-code with optimized print settings',
            'work_center_type': 'DESIGN_WORKSTATION',
            'setup_time_min': 2,
            'run_time_min': 5,
        },
        {
            'sequence': 30,
            'operation_code': 'PRINT',
            'description': '3D print brick using FDM',
            'work_center_type': 'FDM_PRINTER',
            'setup_time_min': 10,
            'run_time_min': 60,  # Will be calculated per part
        },
        {
            'sequence': 40,
            'operation_code': 'INSPECT',
            'description': 'Quality inspection - dimensions and fit test',
            'work_center_type': 'INSPECTION_STATION',
            'setup_time_min': 1,
            'run_time_min': 5,
        },
    ],
    'technic': [
        {
            'sequence': 10,
            'operation_code': 'DESIGN',
            'description': 'CAD design with Technic features',
            'work_center_type': 'DESIGN_WORKSTATION',
            'setup_time_min': 5,
            'run_time_min': 20,
        },
        {
            'sequence': 20,
            'operation_code': 'SLICE',
            'description': 'Generate G-code with support structures',
            'work_center_type': 'DESIGN_WORKSTATION',
            'setup_time_min': 3,
            'run_time_min': 8,
        },
        {
            'sequence': 30,
            'operation_code': 'PRINT',
            'description': '3D print Technic part with supports',
            'work_center_type': 'FDM_PRINTER',
            'setup_time_min': 15,
            'run_time_min': 90,
        },
        {
            'sequence': 35,
            'operation_code': 'POST_PROCESS',
            'description': 'Remove supports and clean part',
            'work_center_type': 'FINISHING_STATION',
            'setup_time_min': 2,
            'run_time_min': 10,
        },
        {
            'sequence': 40,
            'operation_code': 'INSPECT',
            'description': 'Quality inspection - Technic fit test',
            'work_center_type': 'INSPECTION_STATION',
            'setup_time_min': 2,
            'run_time_min': 8,
        },
    ],
    'duplo': [
        {
            'sequence': 10,
            'operation_code': 'DESIGN',
            'description': 'CAD design with Duplo scaling',
            'work_center_type': 'DESIGN_WORKSTATION',
            'setup_time_min': 5,
            'run_time_min': 15,
        },
        {
            'sequence': 20,
            'operation_code': 'SLICE',
            'description': 'Generate G-code for large format',
            'work_center_type': 'DESIGN_WORKSTATION',
            'setup_time_min': 2,
            'run_time_min': 5,
        },
        {
            'sequence': 30,
            'operation_code': 'PRINT',
            'description': '3D print Duplo brick',
            'work_center_type': 'FDM_PRINTER',
            'setup_time_min': 10,
            'run_time_min': 120,  # Larger parts take longer
        },
        {
            'sequence': 40,
            'operation_code': 'INSPECT',
            'description': 'Quality inspection - Duplo compatibility',
            'work_center_type': 'INSPECTION_STATION',
            'setup_time_min': 1,
            'run_time_min': 5,
        },
    ],
    'minifig': [
        {
            'sequence': 10,
            'operation_code': 'DESIGN',
            'description': 'CAD design minifig component',
            'work_center_type': 'DESIGN_WORKSTATION',
            'setup_time_min': 5,
            'run_time_min': 25,
        },
        {
            'sequence': 20,
            'operation_code': 'SLICE',
            'description': 'Generate high-resolution G-code',
            'work_center_type': 'DESIGN_WORKSTATION',
            'setup_time_min': 3,
            'run_time_min': 10,
        },
        {
            'sequence': 30,
            'operation_code': 'PRINT_SLA',
            'description': 'SLA/Resin print for fine detail',
            'work_center_type': 'SLA_PRINTER',
            'setup_time_min': 15,
            'run_time_min': 45,
        },
        {
            'sequence': 35,
            'operation_code': 'CURE',
            'description': 'UV cure resin part',
            'work_center_type': 'CURING_STATION',
            'setup_time_min': 1,
            'run_time_min': 20,
        },
        {
            'sequence': 40,
            'operation_code': 'INSPECT',
            'description': 'Quality inspection - minifig articulation',
            'work_center_type': 'INSPECTION_STATION',
            'setup_time_min': 2,
            'run_time_min': 10,
        },
    ],
    'cnc_milled': [
        {
            'sequence': 10,
            'operation_code': 'CAM',
            'description': 'Generate CNC toolpaths',
            'work_center_type': 'DESIGN_WORKSTATION',
            'setup_time_min': 10,
            'run_time_min': 30,
        },
        {
            'sequence': 20,
            'operation_code': 'MILL_ROUGH',
            'description': 'CNC rough machining',
            'work_center_type': 'CNC_MILL',
            'setup_time_min': 20,
            'run_time_min': 45,
        },
        {
            'sequence': 30,
            'operation_code': 'MILL_FINISH',
            'description': 'CNC finish machining',
            'work_center_type': 'CNC_MILL',
            'setup_time_min': 5,
            'run_time_min': 30,
        },
        {
            'sequence': 40,
            'operation_code': 'DEBURR',
            'description': 'Remove burrs and clean part',
            'work_center_type': 'FINISHING_STATION',
            'setup_time_min': 2,
            'run_time_min': 15,
        },
        {
            'sequence': 50,
            'operation_code': 'INSPECT',
            'description': 'CMM dimensional inspection',
            'work_center_type': 'INSPECTION_STATION',
            'setup_time_min': 5,
            'run_time_min': 15,
        },
    ],
    'laser_engraved': [
        {
            'sequence': 10,
            'operation_code': 'PRINT',
            'description': '3D print base brick',
            'work_center_type': 'FDM_PRINTER',
            'setup_time_min': 10,
            'run_time_min': 60,
        },
        {
            'sequence': 20,
            'operation_code': 'LASER_SETUP',
            'description': 'Position part for laser engraving',
            'work_center_type': 'LASER_ENGRAVER',
            'setup_time_min': 5,
            'run_time_min': 2,
        },
        {
            'sequence': 30,
            'operation_code': 'LASER_ENGRAVE',
            'description': 'Laser engrave pattern/text',
            'work_center_type': 'LASER_ENGRAVER',
            'setup_time_min': 0,
            'run_time_min': 10,
        },
        {
            'sequence': 40,
            'operation_code': 'INSPECT',
            'description': 'Visual inspection of engraving',
            'work_center_type': 'INSPECTION_STATION',
            'setup_time_min': 1,
            'run_time_min': 3,
        },
    ],
}


class RoutingService:
    """
    Routing Service - Manufacturing process definition.

    Manages the sequence of operations required to manufacture
    a part, including work center assignments and time standards.
    """

    def __init__(self, session: Session):
        self.session = session

    def create_routing(
        self,
        part_id: str,
        operations: List[Dict[str, Any]]
    ) -> List[Routing]:
        """
        Create a routing for a part.

        Args:
            part_id: ID of the part
            operations: List of operation definitions

        Returns:
            List of created Routing instances
        """
        part = self.session.query(Part).filter(Part.id == part_id).first()
        if not part:
            raise ValueError(f"Part {part_id} not found")

        # Delete existing routing
        self.session.query(Routing).filter(Routing.part_id == part_id).delete()

        routings = []
        for op in operations:
            routing = Routing(
                part_id=part_id,
                operation_sequence=op['sequence'],
                operation_code=op['operation_code'],
                description=op.get('description'),
                work_center_id=op.get('work_center_id'),
                setup_time_min=op.get('setup_time_min', 0),
                run_time_min=op.get('run_time_min', 0),
                machine_time_min=op.get('machine_time_min', 0),
                labor_time_min=op.get('labor_time_min', 0),
                instructions=op.get('instructions'),
                tooling_required=op.get('tooling_required'),
                parameters=op.get('parameters'),
                is_active=True
            )
            self.session.add(routing)
            routings.append(routing)

        self.session.commit()
        return routings

    def auto_generate_routing(
        self,
        part_id: str,
        part_type: str = None
    ) -> List[Routing]:
        """
        Auto-generate routing based on part type.

        Uses routing templates to create standard routings
        for common part types. Automatically assigns work centers
        based on availability and capability.

        Args:
            part_id: ID of the part
            part_type: Type of part (standard, technic, duplo, etc.)

        Returns:
            List of created Routing instances
        """
        part = self.session.query(Part).filter(Part.id == part_id).first()
        if not part:
            raise ValueError(f"Part {part_id} not found")

        # Determine part type from part if not specified
        if not part_type:
            part_type = part.part_type or 'standard'

        # Get routing template
        template = ROUTING_TEMPLATES.get(part_type, ROUTING_TEMPLATES['standard'])

        # Build operations with work center assignments
        operations = []
        for op_template in template:
            op = dict(op_template)

            # Find appropriate work center
            wc = self._find_work_center(op_template['work_center_type'])
            if wc:
                op['work_center_id'] = wc.id

            # Calculate run time based on part volume
            if op['operation_code'] == 'PRINT' and part.volume_mm3:
                # Estimate print time: ~15mm³/min for FDM
                estimated_time = part.volume_mm3 / 15
                op['run_time_min'] = max(op['run_time_min'], estimated_time)
                op['machine_time_min'] = op['run_time_min']

            # Calculate standard cost
            op['standard_cost'] = self._calculate_operation_cost(op, wc)

            operations.append(op)

        return self.create_routing(part_id, operations)

    def _find_work_center(self, work_center_type: str) -> Optional[WorkCenter]:
        """Find an available work center of the specified type."""
        # First try to find an available one
        wc = self.session.query(WorkCenter).filter(
            WorkCenter.type == work_center_type,
            WorkCenter.status == WorkCenterStatus.AVAILABLE.value
        ).first()

        # If none available, just find any of that type
        if not wc:
            wc = self.session.query(WorkCenter).filter(
                WorkCenter.type == work_center_type
            ).first()

        return wc

    def _calculate_operation_cost(
        self,
        operation: Dict[str, Any],
        work_center: Optional[WorkCenter]
    ) -> float:
        """Calculate standard cost for an operation."""
        setup_time = operation.get('setup_time_min', 0)
        run_time = operation.get('run_time_min', 0)
        total_hours = (setup_time + run_time) / 60

        if work_center and work_center.hourly_rate:
            return float(work_center.hourly_rate) * total_hours

        # Default rates by operation type
        default_rates = {
            'DESIGN': 50,      # $/hour
            'SLICE': 30,
            'PRINT': 25,
            'PRINT_SLA': 35,
            'MILL_ROUGH': 75,
            'MILL_FINISH': 75,
            'LASER_ENGRAVE': 40,
            'INSPECT': 45,
            'POST_PROCESS': 20,
            'CURE': 15,
            'DEBURR': 25,
        }

        rate = default_rates.get(operation.get('operation_code', ''), 30)
        return rate * total_hours

    def get_routing(self, part_id: str) -> List[Routing]:
        """Get the active routing for a part."""
        return self.session.query(Routing).filter(
            Routing.part_id == part_id,
            Routing.is_active == True
        ).order_by(Routing.operation_sequence).all()

    def calculate_total_time(self, part_id: str, quantity: int = 1) -> Dict[str, float]:
        """
        Calculate total time for producing a quantity.

        Returns:
            Dictionary with setup_time, run_time, total_time in minutes
        """
        routings = self.get_routing(part_id)

        setup_time = sum(r.setup_time_min or 0 for r in routings)
        run_time_per_unit = sum(r.run_time_min or 0 for r in routings)

        return {
            'setup_time_min': setup_time,
            'run_time_per_unit_min': run_time_per_unit,
            'run_time_total_min': run_time_per_unit * quantity,
            'total_time_min': setup_time + (run_time_per_unit * quantity)
        }

    def calculate_standard_cost(self, part_id: str, quantity: int = 1) -> Dict[str, float]:
        """
        Calculate standard manufacturing cost.

        Returns:
            Dictionary with setup_cost, run_cost, total_cost
        """
        routings = self.get_routing(part_id)

        total_cost = sum(float(r.standard_cost or 0) for r in routings)

        return {
            'cost_per_unit': total_cost,
            'total_cost': total_cost * quantity,
            'operation_costs': {
                r.operation_code: float(r.standard_cost or 0)
                for r in routings
            }
        }

    def update_operation_time(
        self,
        routing_id: str,
        setup_time_min: float = None,
        run_time_min: float = None
    ) -> Routing:
        """Update time standards for a routing operation."""
        routing = self.session.query(Routing).filter(
            Routing.id == routing_id
        ).first()

        if not routing:
            raise ValueError(f"Routing {routing_id} not found")

        if setup_time_min is not None:
            routing.setup_time_min = setup_time_min
        if run_time_min is not None:
            routing.run_time_min = run_time_min

        # Recalculate standard cost
        wc = routing.work_center
        routing.standard_cost = self._calculate_operation_cost(
            {
                'setup_time_min': routing.setup_time_min,
                'run_time_min': routing.run_time_min,
                'operation_code': routing.operation_code
            },
            wc
        )

        self.session.commit()
        return routing
