"""
BOM Service

Bill of Materials management:
- EBOM: Engineering BOM (as-designed)
- MBOM: Manufacturing BOM (as-built)
- Multi-level explosion
- Where-used analysis
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from models import Part, BOM


class BOMService:
    """
    BOM Service - Bill of Materials management.

    Manages parent-child relationships between parts for
    material planning and costing.
    """

    def __init__(self, session: Session):
        self.session = session

    def create_bom_line(
        self,
        parent_part_id: str,
        child_part_id: str,
        quantity: float,
        bom_type: str = 'MBOM',
        sequence: int = None,
        unit: str = 'EA',
        notes: str = None,
        effective_date: date = None
    ) -> BOM:
        """
        Create a BOM relationship between parts.

        Args:
            parent_part_id: Parent (assembly) part ID
            child_part_id: Child (component) part ID
            quantity: Quantity required per parent
            bom_type: BOM type (EBOM, MBOM, SBOM)
            sequence: Assembly sequence number
            unit: Unit of measure
            notes: Additional notes
            effective_date: When BOM becomes effective

        Returns:
            Created BOM instance
        """
        # Validate parts exist
        parent = self.session.query(Part).filter(Part.id == parent_part_id).first()
        if not parent:
            raise ValueError(f"Parent part {parent_part_id} not found")

        child = self.session.query(Part).filter(Part.id == child_part_id).first()
        if not child:
            raise ValueError(f"Child part {child_part_id} not found")

        # Check for circular reference
        if self._would_create_cycle(parent_part_id, child_part_id):
            raise ValueError("BOM would create circular reference")

        # Check for duplicate
        existing = self.session.query(BOM).filter(
            BOM.parent_part_id == parent_part_id,
            BOM.child_part_id == child_part_id,
            BOM.bom_type == bom_type
        ).first()

        if existing:
            raise ValueError(f"BOM line already exists for this parent/child/type")

        # Auto-generate sequence if not provided
        if sequence is None:
            max_seq = self.session.query(BOM).filter(
                BOM.parent_part_id == parent_part_id,
                BOM.bom_type == bom_type
            ).count()
            sequence = (max_seq + 1) * 10

        bom = BOM(
            parent_part_id=parent_part_id,
            child_part_id=child_part_id,
            quantity=quantity,
            bom_type=bom_type,
            sequence=sequence,
            unit=unit,
            notes=notes,
            effective_date=effective_date or date.today()
        )

        self.session.add(bom)
        self.session.commit()
        return bom

    def _would_create_cycle(self, parent_id: str, child_id: str) -> bool:
        """Check if adding this BOM line would create a cycle."""
        if parent_id == child_id:
            return True

        # Check if child is an ancestor of parent
        ancestors = self._get_ancestors(parent_id)
        return child_id in ancestors

    def _get_ancestors(self, part_id: str, visited: set = None) -> set:
        """Get all ancestors of a part."""
        if visited is None:
            visited = set()

        if part_id in visited:
            return visited

        visited.add(part_id)

        parent_boms = self.session.query(BOM).filter(
            BOM.child_part_id == part_id
        ).all()

        for bom in parent_boms:
            self._get_ancestors(str(bom.parent_part_id), visited)

        return visited

    def get_bom(
        self,
        part_id: str,
        bom_type: str = 'MBOM',
        effective_date: date = None
    ) -> List[Dict[str, Any]]:
        """
        Get single-level BOM for a part.

        Args:
            part_id: Parent part ID
            bom_type: BOM type filter
            effective_date: Effective date filter

        Returns:
            List of BOM components with quantities
        """
        query = self.session.query(BOM).filter(
            BOM.parent_part_id == part_id,
            BOM.bom_type == bom_type
        )

        if effective_date:
            query = query.filter(
                (BOM.effective_date.is_(None)) |
                (BOM.effective_date <= effective_date),
                (BOM.obsolete_date.is_(None)) |
                (BOM.obsolete_date > effective_date)
            )

        bom_lines = query.order_by(BOM.sequence).all()

        return [
            {
                'id': str(b.id),
                'sequence': b.sequence,
                'child_part_id': str(b.child_part_id),
                'child_part_number': b.child_part.part_number,
                'child_part_name': b.child_part.name,
                'quantity': b.quantity,
                'unit': b.unit,
                'notes': b.notes
            }
            for b in bom_lines
        ]

    def explode_bom(
        self,
        part_id: str,
        quantity: float = 1.0,
        bom_type: str = 'MBOM',
        max_levels: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Multi-level BOM explosion.

        Recursively explodes the BOM to show all components
        at all levels with extended quantities.

        Args:
            part_id: Top-level part ID
            quantity: Quantity to explode for
            bom_type: BOM type
            max_levels: Maximum recursion depth

        Returns:
            Flattened list of all components with quantities
        """
        result = []
        self._explode_recursive(
            part_id, quantity, bom_type, 0, max_levels, result, []
        )
        return result

    def _explode_recursive(
        self,
        part_id: str,
        quantity: float,
        bom_type: str,
        level: int,
        max_levels: int,
        result: list,
        path: list
    ):
        """Recursive BOM explosion helper."""
        if level >= max_levels:
            return

        bom_lines = self.session.query(BOM).filter(
            BOM.parent_part_id == part_id,
            BOM.bom_type == bom_type
        ).order_by(BOM.sequence).all()

        for bom in bom_lines:
            child = bom.child_part
            extended_qty = quantity * bom.quantity

            current_path = path + [child.part_number]

            result.append({
                'level': level + 1,
                'path': ' > '.join(current_path),
                'part_id': str(child.id),
                'part_number': child.part_number,
                'part_name': child.name,
                'quantity_per': bom.quantity,
                'extended_quantity': extended_qty,
                'unit': bom.unit,
                'is_leaf': len(child.bom_as_parent) == 0
            })

            # Recurse if this part has children
            if child.bom_as_parent:
                self._explode_recursive(
                    str(child.id), extended_qty, bom_type,
                    level + 1, max_levels, result, current_path
                )

    def get_summarized_bom(
        self,
        part_id: str,
        quantity: float = 1.0,
        bom_type: str = 'MBOM'
    ) -> List[Dict[str, Any]]:
        """
        Get summarized (consolidated) BOM.

        Combines all occurrences of the same part across levels
        into a single line with total quantity.

        Args:
            part_id: Top-level part ID
            quantity: Quantity to calculate for
            bom_type: BOM type

        Returns:
            Consolidated list of all unique components
        """
        explosion = self.explode_bom(part_id, quantity, bom_type)

        # Consolidate by part
        consolidated = {}
        for item in explosion:
            pid = item['part_id']
            if pid in consolidated:
                consolidated[pid]['total_quantity'] += item['extended_quantity']
            else:
                consolidated[pid] = {
                    'part_id': pid,
                    'part_number': item['part_number'],
                    'part_name': item['part_name'],
                    'total_quantity': item['extended_quantity'],
                    'unit': item['unit']
                }

        return sorted(
            consolidated.values(),
            key=lambda x: x['part_number']
        )

    def where_used(
        self,
        part_id: str,
        bom_type: str = None,
        include_indirect: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Where-used analysis - find all parents using this part.

        Args:
            part_id: Part ID to search for
            bom_type: Optional BOM type filter
            include_indirect: Include indirect (grandparent) usage

        Returns:
            List of parent parts using this component
        """
        query = self.session.query(BOM).filter(
            BOM.child_part_id == part_id
        )

        if bom_type:
            query = query.filter(BOM.bom_type == bom_type)

        direct_usage = query.all()

        result = []
        for bom in direct_usage:
            parent = bom.parent_part
            result.append({
                'level': 1,
                'parent_part_id': str(parent.id),
                'parent_part_number': parent.part_number,
                'parent_part_name': parent.name,
                'quantity': bom.quantity,
                'bom_type': bom.bom_type,
                'is_direct': True
            })

        if include_indirect:
            for direct in list(result):
                indirect = self.where_used(
                    direct['parent_part_id'],
                    bom_type,
                    include_indirect=True
                )
                for item in indirect:
                    item['level'] += 1
                    item['is_direct'] = False
                    result.append(item)

        return result

    def copy_bom(
        self,
        from_part_id: str,
        to_part_id: str,
        from_type: str = 'EBOM',
        to_type: str = 'MBOM'
    ) -> List[BOM]:
        """
        Copy BOM from one type to another or between parts.

        Commonly used to create MBOM from EBOM.

        Args:
            from_part_id: Source part ID
            to_part_id: Target part ID
            from_type: Source BOM type
            to_type: Target BOM type

        Returns:
            List of created BOM lines
        """
        source_bom = self.session.query(BOM).filter(
            BOM.parent_part_id == from_part_id,
            BOM.bom_type == from_type
        ).all()

        new_bom = []
        for bom in source_bom:
            new_line = BOM(
                parent_part_id=to_part_id,
                child_part_id=bom.child_part_id,
                quantity=bom.quantity,
                bom_type=to_type,
                sequence=bom.sequence,
                unit=bom.unit,
                notes=f"Copied from {from_type}",
                effective_date=date.today()
            )
            self.session.add(new_line)
            new_bom.append(new_line)

        self.session.commit()
        return new_bom

    def update_bom_line(
        self,
        bom_id: str,
        quantity: float = None,
        sequence: int = None,
        notes: str = None,
        obsolete_date: date = None
    ) -> BOM:
        """Update an existing BOM line."""
        bom = self.session.query(BOM).filter(BOM.id == bom_id).first()
        if not bom:
            raise ValueError(f"BOM line {bom_id} not found")

        if quantity is not None:
            bom.quantity = quantity
        if sequence is not None:
            bom.sequence = sequence
        if notes is not None:
            bom.notes = notes
        if obsolete_date is not None:
            bom.obsolete_date = obsolete_date

        self.session.commit()
        return bom

    def delete_bom_line(self, bom_id: str) -> bool:
        """Delete a BOM line."""
        bom = self.session.query(BOM).filter(BOM.id == bom_id).first()
        if not bom:
            return False

        self.session.delete(bom)
        self.session.commit()
        return True

    def compare_boms(
        self,
        part_id: str,
        type_a: str = 'EBOM',
        type_b: str = 'MBOM'
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Compare two BOM types for the same part.

        Returns:
            Dictionary with 'only_in_a', 'only_in_b', 'different_qty'
        """
        bom_a = {
            str(b.child_part_id): b
            for b in self.session.query(BOM).filter(
                BOM.parent_part_id == part_id,
                BOM.bom_type == type_a
            ).all()
        }

        bom_b = {
            str(b.child_part_id): b
            for b in self.session.query(BOM).filter(
                BOM.parent_part_id == part_id,
                BOM.bom_type == type_b
            ).all()
        }

        only_in_a = []
        only_in_b = []
        different_qty = []

        for child_id, bom in bom_a.items():
            if child_id not in bom_b:
                only_in_a.append({
                    'part_number': bom.child_part.part_number,
                    'quantity': bom.quantity
                })
            elif bom.quantity != bom_b[child_id].quantity:
                different_qty.append({
                    'part_number': bom.child_part.part_number,
                    f'{type_a}_qty': bom.quantity,
                    f'{type_b}_qty': bom_b[child_id].quantity
                })

        for child_id, bom in bom_b.items():
            if child_id not in bom_a:
                only_in_b.append({
                    'part_number': bom.child_part.part_number,
                    'quantity': bom.quantity
                })

        return {
            f'only_in_{type_a}': only_in_a,
            f'only_in_{type_b}': only_in_b,
            'different_quantities': different_qty
        }
