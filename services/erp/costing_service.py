"""
LEGO Factory v3 - Costing Service
==================================
Product cost calculation and analysis.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func

from config.database import get_db_session

logger = logging.getLogger(__name__)

# Default labor rate per minute
DEFAULT_LABOR_RATE = 0.50  # $0.50 per minute
# Default overhead rate as percentage of labor
DEFAULT_OVERHEAD_RATE = 0.25  # 25% of labor


class CostingService:
    """Service for calculating and managing product costs."""

    def __init__(self, session: Session):
        self.session = session

    def get_product_costs(
        self,
        search: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get product cost breakdown for all products.

        Returns:
            Dictionary with products list, summary, and variance alerts
        """
        try:
            from models.lego.parts_catalog import LegoProduct

            query = self.session.query(LegoProduct).filter(
                LegoProduct.is_deleted == False
            )

            if search:
                query = query.filter(
                    (LegoProduct.sku.ilike(f'%{search}%'))
                )

            products = query.offset(offset).limit(limit).all()

            product_costs = []
            total_material = 0
            total_labor = 0
            total_overhead = 0
            variance_alerts = []

            for product in products:
                cost_data = self._calculate_product_cost(product)
                product_costs.append(cost_data)

                total_material += cost_data['material_cost']
                total_labor += cost_data['labor_cost']
                total_overhead += cost_data['overhead_cost']

                # Check for variance > 5%
                if abs(cost_data['variance']) > 5:
                    variance_alerts.append({
                        'sku': cost_data['sku'],
                        'name': cost_data['name'],
                        'variance': cost_data['variance'],
                        'message': 'Cost variance exceeds 5% threshold'
                    })

            count = len(product_costs)
            summary = {
                'avg_material': total_material / count if count > 0 else 0,
                'avg_labor': total_labor / count if count > 0 else 0,
                'avg_overhead': total_overhead / count if count > 0 else 0,
                'variance_count': len(variance_alerts)
            }

            return {
                'products': product_costs,
                'count': count,
                'summary': summary,
                'variance_alerts': variance_alerts
            }

        except Exception as e:
            logger.error(f"Error fetching product costs: {e}", exc_info=True)
            return {'products': [], 'count': 0, 'summary': {}, 'variance_alerts': []}

    def _calculate_product_cost(self, product) -> Dict[str, Any]:
        """Calculate cost breakdown for a single product."""
        # Get material cost from product or calculate from weight
        material_cost = float(product.material_cost or 0)
        if material_cost == 0 and product.weight_grams:
            # Estimate based on weight (average material cost per gram)
            material_cost = float(product.weight_grams) * 0.02  # $0.02/gram default

        # Get labor cost from product or calculate from routing
        labor_cost = float(product.labor_cost or 0)
        if labor_cost == 0:
            labor_cost = self._calculate_labor_from_routing(product.routing_id)

        # Get overhead cost from product or calculate as percentage of labor
        overhead_cost = float(product.overhead_cost or 0)
        if overhead_cost == 0:
            overhead_cost = labor_cost * DEFAULT_OVERHEAD_RATE

        total_cost = material_cost + labor_cost + overhead_cost
        list_price = float(product.list_price or 0)

        # Calculate variance (difference from standard cost if available)
        standard_cost = float(product.total_cost or total_cost)
        variance = 0
        if standard_cost > 0:
            variance = ((total_cost - standard_cost) / standard_cost) * 100

        part_name = ''
        if product.part:
            part_name = product.part.name

        return {
            'sku': product.sku,
            'name': part_name or product.sku,
            'material_cost': material_cost,
            'labor_cost': labor_cost,
            'overhead_cost': overhead_cost,
            'total_cost': total_cost,
            'list_price': list_price,
            'variance': variance
        }

    def _calculate_labor_from_routing(self, routing_id: str) -> float:
        """Calculate labor cost from routing operations."""
        if not routing_id:
            return 0.05  # Default labor cost

        try:
            from models.lego.parts_catalog import LegoRoutingOperation

            operations = self.session.query(LegoRoutingOperation).filter(
                LegoRoutingOperation.routing_id == routing_id
            ).all()

            total_minutes = sum(
                (op.setup_time_min or 0) + (op.run_time_min or 0)
                for op in operations
            )

            return total_minutes * DEFAULT_LABOR_RATE

        except Exception as e:
            logger.debug(f"Error calculating labor from routing: {e}")
            return 0.05

    def get_product_cost_detail(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed cost breakdown for a specific product.

        Returns:
            Dictionary with BOM costs, routing costs, and totals
        """
        try:
            from models.lego.parts_catalog import LegoProduct

            product = self.session.query(LegoProduct).filter(
                LegoProduct.sku == sku
            ).first()

            if not product:
                return None

            cost_data = self._calculate_product_cost(product)

            # Get BOM breakdown
            bom_costs = self._get_bom_costs(product)

            # Get routing breakdown
            routing_costs = self._get_routing_costs(product.routing_id)

            return {
                **cost_data,
                'bom_costs': bom_costs,
                'routing_costs': routing_costs
            }

        except Exception as e:
            logger.error(f"Error fetching product cost detail: {e}", exc_info=True)
            return None

    def _get_bom_costs(self, product) -> List[Dict[str, Any]]:
        """Get BOM component costs for a product."""
        bom_costs = []

        # Material component
        if product.weight_grams:
            material_name = 'ABS Plastic'
            if product.material:
                material_name = product.material.name

            unit_cost = 0.02  # Default cost per gram
            if product.material and product.material.cost_per_gram:
                unit_cost = float(product.material.cost_per_gram)

            bom_costs.append({
                'component': f'Raw Material - {material_name}',
                'quantity': float(product.weight_grams),
                'unit': 'g',
                'unit_cost': unit_cost,
                'extended_cost': float(product.weight_grams) * unit_cost
            })

        # Color/additive component
        if product.color:
            bom_costs.append({
                'component': f'Colorant - {product.color.name}',
                'quantity': float(product.weight_grams or 0) * 0.05,  # 5% colorant
                'unit': 'g',
                'unit_cost': 0.08,
                'extended_cost': float(product.weight_grams or 0) * 0.05 * 0.08
            })

        return bom_costs

    def _get_routing_costs(self, routing_id: str) -> List[Dict[str, Any]]:
        """Get routing operation costs."""
        if not routing_id:
            return []

        try:
            from models.lego.parts_catalog import LegoRoutingOperation

            operations = self.session.query(LegoRoutingOperation).filter(
                LegoRoutingOperation.routing_id == routing_id
            ).order_by(LegoRoutingOperation.sequence).all()

            routing_costs = []
            for op in operations:
                setup_min = op.setup_time_min or 0
                run_min = op.run_time_min or 0
                total_min = setup_min + run_min
                labor_cost = total_min * DEFAULT_LABOR_RATE

                routing_costs.append({
                    'sequence': op.sequence,
                    'operation': op.name,
                    'work_center': op.work_center_id or op.machine_id or 'General',
                    'setup_min': setup_min,
                    'run_min': run_min,
                    'labor_cost': labor_cost
                })

            return routing_costs

        except Exception as e:
            logger.debug(f"Error getting routing costs: {e}")
            return []

    def run_cost_rollup(self, product_ids: List[str] = None) -> Dict[str, Any]:
        """
        Run cost rollup to recalculate and update product costs.

        Args:
            product_ids: Optional list of specific product SKUs to update.
                         If None, updates all products.

        Returns:
            Summary of rollup results
        """
        try:
            from models.lego.parts_catalog import LegoProduct

            query = self.session.query(LegoProduct).filter(
                LegoProduct.is_deleted == False
            )

            if product_ids:
                query = query.filter(LegoProduct.sku.in_(product_ids))

            products = query.all()
            updated = 0
            errors = []

            for product in products:
                try:
                    cost_data = self._calculate_product_cost(product)

                    product.material_cost = cost_data['material_cost']
                    product.labor_cost = cost_data['labor_cost']
                    product.overhead_cost = cost_data['overhead_cost']
                    product.total_cost = cost_data['total_cost']

                    updated += 1

                except Exception as e:
                    errors.append({'sku': product.sku, 'error': str(e)})

            self.session.flush()

            return {
                'updated': updated,
                'errors': errors,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error running cost rollup: {e}", exc_info=True)
            return {'updated': 0, 'errors': [{'error': str(e)}]}

    def get_cost_variance_report(
        self,
        threshold: float = 5.0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get products with cost variance exceeding threshold.

        Args:
            threshold: Variance percentage threshold
            limit: Maximum results

        Returns:
            List of products with variance details
        """
        try:
            from models.lego.parts_catalog import LegoProduct

            products = self.session.query(LegoProduct).filter(
                LegoProduct.is_deleted == False
            ).all()

            variance_items = []
            for product in products:
                cost_data = self._calculate_product_cost(product)

                if abs(cost_data['variance']) >= threshold:
                    variance_items.append({
                        'sku': cost_data['sku'],
                        'name': cost_data['name'],
                        'standard_cost': float(product.total_cost or 0),
                        'actual_cost': cost_data['total_cost'],
                        'variance': cost_data['variance'],
                        'variance_amount': cost_data['total_cost'] - float(product.total_cost or 0)
                    })

            # Sort by absolute variance
            variance_items.sort(key=lambda x: abs(x['variance']), reverse=True)

            return variance_items[:limit]

        except Exception as e:
            logger.error(f"Error getting variance report: {e}", exc_info=True)
            return []


def get_costing_service(session: Session = None) -> CostingService:
    """Get costing service instance."""
    if session:
        return CostingService(session)
    with get_db_session() as session:
        return CostingService(session)
