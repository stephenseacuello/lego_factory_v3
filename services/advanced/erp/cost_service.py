"""
Cost Service

Standard and actual cost management:
- Standard cost calculation from BOM + routing
- Actual cost recording
- Variance analysis (Material, Labor, Overhead)
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Part, BOM, WorkOrder, WorkOrderOperation
from models.manufacturing import Routing
from models.analytics import CostLedger, CostType


class CostService:
    """
    Cost Service - Manufacturing cost management.

    Calculates and tracks standard costs, actual costs,
    and variances for manufacturing operations.
    """

    def __init__(self, session: Session):
        self.session = session

    def calculate_standard_cost(self, part_id: str) -> Dict[str, Any]:
        """
        Calculate standard manufacturing cost for a part.

        Cost components:
        - Material: BOM component costs
        - Labor: Routing labor time × labor rate
        - Machine: Routing machine time × machine rate
        - Overhead: Calculated as % of labor + machine

        Args:
            part_id: Part ID to cost

        Returns:
            Detailed cost breakdown
        """
        part = self.session.query(Part).filter(Part.id == part_id).first()
        if not part:
            raise ValueError(f"Part {part_id} not found")

        # Material cost from BOM
        material_cost = self._calculate_material_cost(part_id)

        # Labor and machine cost from routing
        labor_cost, machine_cost = self._calculate_routing_cost(part_id)

        # Overhead (typically 30-50% of conversion cost)
        conversion_cost = labor_cost + machine_cost
        overhead_rate = 0.35  # 35% overhead
        overhead_cost = conversion_cost * overhead_rate

        total_cost = material_cost + labor_cost + machine_cost + overhead_cost

        cost_breakdown = {
            'part_id': part_id,
            'part_number': part.part_number,
            'material_cost': round(material_cost, 4),
            'labor_cost': round(labor_cost, 4),
            'machine_cost': round(machine_cost, 4),
            'overhead_cost': round(overhead_cost, 4),
            'total_cost': round(total_cost, 4),
            'cost_per_component': self._get_material_cost_detail(part_id),
            'cost_per_operation': self._get_routing_cost_detail(part_id)
        }

        return cost_breakdown

    def _calculate_material_cost(self, part_id: str) -> float:
        """Calculate material cost from BOM."""
        bom_lines = self.session.query(BOM).filter(
            BOM.parent_part_id == part_id,
            BOM.bom_type == 'MBOM'
        ).all()

        total = 0.0
        for bom in bom_lines:
            child = bom.child_part
            child_cost = float(child.standard_cost or 0)

            # If child has its own BOM, use rolled-up cost
            if child.bom_as_parent:
                child_cost = self._calculate_material_cost(str(child.id))
                # Add child's routing cost
                labor, machine = self._calculate_routing_cost(str(child.id))
                child_cost += labor + machine

            total += child_cost * bom.quantity

        return total

    def _get_material_cost_detail(self, part_id: str) -> List[Dict[str, Any]]:
        """Get detailed material cost breakdown."""
        bom_lines = self.session.query(BOM).filter(
            BOM.parent_part_id == part_id,
            BOM.bom_type == 'MBOM'
        ).order_by(BOM.sequence).all()

        return [
            {
                'part_number': bom.child_part.part_number,
                'quantity': bom.quantity,
                'unit_cost': float(bom.child_part.standard_cost or 0),
                'extended_cost': float(bom.child_part.standard_cost or 0) * bom.quantity
            }
            for bom in bom_lines
        ]

    def _calculate_routing_cost(self, part_id: str) -> tuple:
        """Calculate labor and machine cost from routing."""
        routings = self.session.query(Routing).filter(
            Routing.part_id == part_id,
            Routing.is_active == True
        ).all()

        labor_cost = 0.0
        machine_cost = 0.0

        for routing in routings:
            # Labor cost
            labor_hours = (routing.labor_time_min or routing.run_time_min or 0) / 60
            labor_rate = 25.00  # Default $/hour
            labor_cost += labor_hours * labor_rate

            # Machine cost
            machine_hours = (routing.machine_time_min or routing.run_time_min or 0) / 60
            if routing.work_center:
                machine_rate = float(routing.work_center.hourly_rate or 30)
            else:
                machine_rate = 30.00  # Default $/hour
            machine_cost += machine_hours * machine_rate

        return labor_cost, machine_cost

    def _get_routing_cost_detail(self, part_id: str) -> List[Dict[str, Any]]:
        """Get detailed routing cost breakdown."""
        routings = self.session.query(Routing).filter(
            Routing.part_id == part_id,
            Routing.is_active == True
        ).order_by(Routing.operation_sequence).all()

        return [
            {
                'operation': routing.operation_code,
                'work_center': routing.work_center.code if routing.work_center else None,
                'setup_time_min': routing.setup_time_min,
                'run_time_min': routing.run_time_min,
                'standard_cost': float(routing.standard_cost or 0)
            }
            for routing in routings
        ]

    def update_standard_cost(self, part_id: str) -> Part:
        """
        Update standard cost on part master.

        Recalculates and stores the standard cost on the part.
        """
        cost_data = self.calculate_standard_cost(part_id)

        part = self.session.query(Part).filter(Part.id == part_id).first()
        part.standard_cost = Decimal(str(cost_data['total_cost']))

        self.session.commit()
        return part

    def roll_up_costs(self, part_id: str = None) -> int:
        """
        Roll up costs for all parts or a specific part and its parents.

        Updates standard costs starting from lowest level parts
        and working up through the BOM structure.

        Returns:
            Number of parts updated
        """
        if part_id:
            # Update specific part and its parents
            self.update_standard_cost(part_id)

            # Find and update parents
            parents = self.session.query(BOM).filter(
                BOM.child_part_id == part_id
            ).all()

            count = 1
            for bom in parents:
                count += self.roll_up_costs(str(bom.parent_part_id))

            return count
        else:
            # Update all parts - start with leaf nodes
            updated = 0

            # Get parts with no children (leaf nodes)
            leaf_parts = self.session.query(Part).filter(
                ~Part.id.in_(
                    self.session.query(BOM.parent_part_id).distinct()
                )
            ).all()

            # Update leaves first
            for part in leaf_parts:
                self.update_standard_cost(str(part.id))
                updated += 1

            # Then update parts with children in order of BOM depth
            remaining = self.session.query(Part).filter(
                Part.id.in_(
                    self.session.query(BOM.parent_part_id).distinct()
                )
            ).all()

            for part in remaining:
                self.update_standard_cost(str(part.id))
                updated += 1

            return updated

    # Actual Cost Recording

    def record_work_order_costs(
        self,
        work_order_id: str,
        material_costs: List[Dict[str, Any]] = None,
        labor_costs: List[Dict[str, Any]] = None,
        machine_costs: List[Dict[str, Any]] = None
    ) -> List[CostLedger]:
        """
        Record actual costs for a work order.

        Args:
            work_order_id: Work order ID
            material_costs: List of {part_id, quantity, unit_cost}
            labor_costs: List of {operation_id, hours, rate}
            machine_costs: List of {operation_id, hours, rate}

        Returns:
            List of created CostLedger entries
        """
        work_order = self.session.query(WorkOrder).filter(
            WorkOrder.id == work_order_id
        ).first()

        if not work_order:
            raise ValueError(f"Work order {work_order_id} not found")

        entries = []

        # Material costs
        if material_costs:
            for mat in material_costs:
                part = self.session.query(Part).filter(
                    Part.id == mat['part_id']
                ).first()

                entry = CostLedger.record_material_cost(
                    self.session,
                    work_order_id=work_order_id,
                    part_id=mat['part_id'],
                    quantity=mat['quantity'],
                    standard_unit=float(part.standard_cost or 0) if part else 0,
                    actual_unit=mat['unit_cost'],
                    lot_number=mat.get('lot_number')
                )
                entries.append(entry)

        # Labor costs
        if labor_costs:
            for labor in labor_costs:
                # Get standard rate from routing
                operation = self.session.query(WorkOrderOperation).filter(
                    WorkOrderOperation.id == labor['operation_id']
                ).first()

                std_rate = 25.00  # Default
                if operation and operation.routing:
                    std_time = operation.routing.labor_time_min or 0
                    if std_time > 0:
                        std_rate = float(operation.routing.standard_cost or 0) / (std_time / 60)

                entry = CostLedger.record_labor_cost(
                    self.session,
                    work_order_id=work_order_id,
                    operation_id=labor['operation_id'],
                    hours=labor['hours'],
                    standard_rate=std_rate,
                    actual_rate=labor['rate'],
                    operator_id=labor.get('operator_id')
                )
                entries.append(entry)

        # Machine costs
        if machine_costs:
            for machine in machine_costs:
                operation = self.session.query(WorkOrderOperation).filter(
                    WorkOrderOperation.id == machine['operation_id']
                ).first()

                std_rate = 30.00  # Default
                if operation and operation.work_center:
                    std_rate = float(operation.work_center.hourly_rate or 30)

                entry = CostLedger.record_machine_cost(
                    self.session,
                    work_order_id=work_order_id,
                    operation_id=machine['operation_id'],
                    hours=machine['hours'],
                    standard_rate=std_rate,
                    actual_rate=machine['rate'],
                    machine_id=str(operation.work_center_id) if operation else None
                )
                entries.append(entry)

        self.session.commit()
        return entries

    def auto_record_operation_costs(
        self,
        operation_id: str,
        operator_id: str = None
    ) -> List[CostLedger]:
        """
        Automatically record costs when an operation completes.

        Uses actual operation times and work center rates.
        """
        operation = self.session.query(WorkOrderOperation).filter(
            WorkOrderOperation.id == operation_id
        ).first()

        if not operation:
            raise ValueError(f"Operation {operation_id} not found")

        entries = []

        # Calculate actual hours
        actual_hours = (operation.run_time_actual_min or 0) / 60
        setup_hours = (operation.setup_time_actual_min or 0) / 60
        total_hours = actual_hours + setup_hours

        if total_hours > 0:
            # Labor cost
            labor_entry = CostLedger.record_labor_cost(
                self.session,
                work_order_id=str(operation.work_order_id),
                operation_id=operation_id,
                hours=total_hours,
                standard_rate=25.00,  # Could be from routing
                actual_rate=25.00,
                operator_id=operator_id or operation.operator_id
            )
            entries.append(labor_entry)

            # Machine cost
            if operation.work_center:
                machine_entry = CostLedger.record_machine_cost(
                    self.session,
                    work_order_id=str(operation.work_order_id),
                    operation_id=operation_id,
                    hours=total_hours,
                    standard_rate=float(operation.work_center.hourly_rate or 30),
                    actual_rate=float(operation.work_center.hourly_rate or 30),
                    machine_id=str(operation.work_center_id)
                )
                entries.append(machine_entry)

        self.session.commit()
        return entries

    # Variance Analysis

    def get_work_order_variance(self, work_order_id: str) -> Dict[str, Any]:
        """
        Get variance analysis for a completed work order.

        Returns:
            Variance breakdown by cost type
        """
        work_order = self.session.query(WorkOrder).filter(
            WorkOrder.id == work_order_id
        ).first()

        if not work_order:
            raise ValueError(f"Work order {work_order_id} not found")

        # Get standard cost for the part
        part = work_order.part
        std_cost = self.calculate_standard_cost(str(part.id))

        # Get actual costs from ledger
        variance_summary = CostLedger.get_variance_summary(
            self.session,
            work_order_id=work_order_id
        )

        # Calculate expected total based on quantity
        expected_total = std_cost['total_cost'] * work_order.quantity_completed

        actual_total = sum(
            v['actual'] for v in variance_summary.values()
        )

        return {
            'work_order_number': work_order.work_order_number,
            'part_number': part.part_number,
            'quantity_completed': work_order.quantity_completed,
            'standard_cost_per_unit': std_cost['total_cost'],
            'expected_total_cost': expected_total,
            'actual_total_cost': actual_total,
            'total_variance': actual_total - expected_total,
            'variance_percentage': (
                (actual_total - expected_total) / expected_total * 100
                if expected_total else 0
            ),
            'by_cost_type': variance_summary,
            'variance_details': self._get_variance_details(work_order_id)
        }

    def _get_variance_details(self, work_order_id: str) -> List[Dict[str, Any]]:
        """Get detailed variance by cost element."""
        entries = self.session.query(CostLedger).filter(
            CostLedger.work_order_id == work_order_id
        ).all()

        return [
            {
                'cost_type': entry.cost_type,
                'cost_element': entry.cost_element,
                'quantity': float(entry.quantity or 0),
                'standard_cost': float(entry.standard_cost or 0),
                'actual_cost': float(entry.actual_cost or 0),
                'variance': float(entry.variance or 0),
                'resource': entry.resource_id
            }
            for entry in entries
        ]

    def get_period_variance_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get variance report for a time period.

        Returns summary of all variances within the period.
        """
        variance_summary = CostLedger.get_variance_summary(
            self.session,
            start_date=start_date,
            end_date=end_date
        )

        # Get top variances
        top_variances = self.session.query(
            CostLedger.work_order_id,
            func.sum(CostLedger.variance).label('total_variance')
        ).filter(
            CostLedger.transaction_date >= start_date,
            CostLedger.transaction_date < end_date
        ).group_by(
            CostLedger.work_order_id
        ).order_by(
            func.abs(func.sum(CostLedger.variance)).desc()
        ).limit(10).all()

        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'summary': variance_summary,
            'total_standard': sum(v['standard'] for v in variance_summary.values()),
            'total_actual': sum(v['actual'] for v in variance_summary.values()),
            'total_variance': sum(v['variance'] for v in variance_summary.values()),
            'top_variances': [
                {
                    'work_order_id': str(woid),
                    'variance': float(var or 0)
                }
                for woid, var in top_variances
            ]
        }
