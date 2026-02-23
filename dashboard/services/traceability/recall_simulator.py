"""
Recall Simulator - Product Recall Impact Analysis

LegoMCP World-Class Manufacturing System v5.0
Phase 15: Digital Thread & Traceability

Provides recall simulation capabilities:
- Impact assessment for potential recalls
- Affected batch identification
- Customer notification planning
- Cost and timeline estimation
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from enum import Enum
import uuid


class RecallSeverity(Enum):
    """Severity levels for recalls."""
    CRITICAL = "critical"    # Safety issue - immediate action required
    MAJOR = "major"          # Significant defect - customer notification
    MINOR = "minor"          # Quality issue - replacement offered
    PRECAUTIONARY = "precautionary"  # No confirmed issue - proactive


class RecallScope(Enum):
    """Scope of recall."""
    FULL = "full"            # All products in range
    PARTIAL = "partial"      # Specific batches only
    TARGETED = "targeted"    # Specific serial numbers


@dataclass
class AffectedProduct:
    """Information about an affected product."""
    serial_number: str
    part_id: str
    work_order_id: str
    batch_id: str
    production_date: datetime
    ship_date: Optional[datetime]
    customer_id: Optional[str]
    location: str  # 'inventory', 'shipped', 'installed'


@dataclass
class RecallSimulationResult:
    """Complete recall simulation result."""
    simulation_id: str
    recall_reason: str
    severity: RecallSeverity
    scope: RecallScope
    trigger_date: datetime
    affected_products: List[AffectedProduct]
    summary: Dict[str, int]
    customer_impact: Dict[str, int]
    cost_estimate: Dict[str, float]
    timeline_estimate: Dict[str, datetime]
    action_plan: List[str]
    notification_templates: Dict[str, str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RecallSimulator:
    """
    Simulates product recalls to assess impact and plan response.

    Uses digital thread data to trace affected products through
    the supply chain and estimate recall costs and timelines.
    """

    def __init__(self):
        self.simulation_history: Dict[str, RecallSimulationResult] = {}
        self.cost_factors = {
            'notification_per_customer': 5.00,
            'shipping_per_unit': 8.50,
            'replacement_labor_per_unit': 15.00,
            'admin_overhead_rate': 0.15,
            'regulatory_reporting': 2500.00,
            'customer_goodwill_per_unit': 10.00,
        }

    def simulate_recall(
        self,
        reason: str,
        severity: RecallSeverity,
        batch_ids: Optional[List[str]] = None,
        serial_numbers: Optional[List[str]] = None,
        date_range: Optional[tuple] = None,
        part_ids: Optional[List[str]] = None
    ) -> RecallSimulationResult:
        """
        Simulate a product recall scenario.

        Args:
            reason: Reason for the recall
            severity: Severity level
            batch_ids: Specific batches to recall (optional)
            serial_numbers: Specific serial numbers (optional)
            date_range: Production date range (optional)
            part_ids: Specific part types (optional)

        Returns:
            Complete recall simulation result
        """
        # Determine scope
        if serial_numbers:
            scope = RecallScope.TARGETED
        elif batch_ids:
            scope = RecallScope.PARTIAL
        else:
            scope = RecallScope.FULL

        # Identify affected products
        affected = self._identify_affected_products(
            batch_ids, serial_numbers, date_range, part_ids
        )

        # Calculate summary statistics
        summary = self._calculate_summary(affected)

        # Analyze customer impact
        customer_impact = self._analyze_customer_impact(affected)

        # Estimate costs
        cost_estimate = self._estimate_costs(affected, severity)

        # Estimate timeline
        timeline = self._estimate_timeline(affected, severity)

        # Generate action plan
        action_plan = self._generate_action_plan(severity, scope, len(affected))

        # Create notification templates
        templates = self._create_notification_templates(reason, severity)

        result = RecallSimulationResult(
            simulation_id=str(uuid.uuid4()),
            recall_reason=reason,
            severity=severity,
            scope=scope,
            trigger_date=datetime.utcnow(),
            affected_products=affected,
            summary=summary,
            customer_impact=customer_impact,
            cost_estimate=cost_estimate,
            timeline_estimate=timeline,
            action_plan=action_plan,
            notification_templates=templates,
        )

        self.simulation_history[result.simulation_id] = result
        return result

    def _identify_affected_products(
        self,
        batch_ids: Optional[List[str]],
        serial_numbers: Optional[List[str]],
        date_range: Optional[tuple],
        part_ids: Optional[List[str]]
    ) -> List[AffectedProduct]:
        """Identify all affected products based on criteria."""
        import random

        # Simulate product lookup - in production would query digital thread
        affected = []
        num_products = random.randint(50, 500)

        for i in range(num_products):
            prod_date = datetime.utcnow() - timedelta(days=random.randint(1, 90))

            # Determine location
            days_since_production = (datetime.utcnow() - prod_date).days
            if days_since_production < 3:
                location = 'inventory'
                ship_date = None
                customer_id = None
            elif days_since_production < 14:
                location = 'shipped'
                ship_date = prod_date + timedelta(days=2)
                customer_id = f"CUST-{random.randint(1000, 9999)}"
            else:
                location = 'installed'
                ship_date = prod_date + timedelta(days=2)
                customer_id = f"CUST-{random.randint(1000, 9999)}"

            affected.append(AffectedProduct(
                serial_number=f"SN-{uuid.uuid4().hex[:8].upper()}",
                part_id=part_ids[0] if part_ids else f"PART-{random.randint(100, 999)}",
                work_order_id=f"WO-{random.randint(1000, 9999)}",
                batch_id=batch_ids[0] if batch_ids else f"BATCH-{random.randint(100, 999)}",
                production_date=prod_date,
                ship_date=ship_date,
                customer_id=customer_id,
                location=location,
            ))

        return affected

    def _calculate_summary(self, affected: List[AffectedProduct]) -> Dict[str, int]:
        """Calculate summary statistics."""
        locations = {'inventory': 0, 'shipped': 0, 'installed': 0}
        for product in affected:
            locations[product.location] = locations.get(product.location, 0) + 1

        batches = set(p.batch_id for p in affected)
        work_orders = set(p.work_order_id for p in affected)

        return {
            'total_affected': len(affected),
            'in_inventory': locations['inventory'],
            'in_transit': locations['shipped'],
            'at_customers': locations['installed'],
            'unique_batches': len(batches),
            'work_orders_affected': len(work_orders),
        }

    def _analyze_customer_impact(self, affected: List[AffectedProduct]) -> Dict[str, int]:
        """Analyze impact on customers."""
        customers: Set[str] = set()
        for product in affected:
            if product.customer_id:
                customers.add(product.customer_id)

        # Group by region (simulated)
        import random
        regions = {
            'north_america': int(len(customers) * 0.4),
            'europe': int(len(customers) * 0.3),
            'asia_pacific': int(len(customers) * 0.2),
            'other': int(len(customers) * 0.1),
        }

        return {
            'total_customers': len(customers),
            'units_at_customers': sum(
                1 for p in affected if p.location in ['shipped', 'installed']
            ),
            **regions,
        }

    def _estimate_costs(
        self,
        affected: List[AffectedProduct],
        severity: RecallSeverity
    ) -> Dict[str, float]:
        """Estimate recall costs."""
        summary = self._calculate_summary(affected)
        customer_impact = self._analyze_customer_impact(affected)

        # Base costs
        notification_cost = (
            customer_impact['total_customers'] *
            self.cost_factors['notification_per_customer']
        )

        units_to_retrieve = summary['in_transit'] + summary['at_customers']
        shipping_cost = units_to_retrieve * self.cost_factors['shipping_per_unit']

        replacement_cost = (
            len(affected) * self.cost_factors['replacement_labor_per_unit']
        )

        goodwill_cost = (
            customer_impact['units_at_customers'] *
            self.cost_factors['customer_goodwill_per_unit']
        )

        # Severity multipliers
        severity_multipliers = {
            RecallSeverity.CRITICAL: 2.0,
            RecallSeverity.MAJOR: 1.5,
            RecallSeverity.MINOR: 1.0,
            RecallSeverity.PRECAUTIONARY: 0.8,
        }
        multiplier = severity_multipliers[severity]

        subtotal = (
            notification_cost + shipping_cost + replacement_cost + goodwill_cost
        ) * multiplier

        regulatory_cost = (
            self.cost_factors['regulatory_reporting']
            if severity in [RecallSeverity.CRITICAL, RecallSeverity.MAJOR]
            else 0
        )

        overhead = subtotal * self.cost_factors['admin_overhead_rate']

        return {
            'notification': notification_cost,
            'shipping': shipping_cost * multiplier,
            'replacement': replacement_cost * multiplier,
            'goodwill': goodwill_cost,
            'regulatory': regulatory_cost,
            'overhead': overhead,
            'total_estimated': subtotal + regulatory_cost + overhead,
        }

    def _estimate_timeline(
        self,
        affected: List[AffectedProduct],
        severity: RecallSeverity
    ) -> Dict[str, datetime]:
        """Estimate recall timeline."""
        now = datetime.utcnow()

        # Timeline varies by severity
        if severity == RecallSeverity.CRITICAL:
            notification_days = 1
            collection_days = 14
            resolution_days = 30
        elif severity == RecallSeverity.MAJOR:
            notification_days = 3
            collection_days = 30
            resolution_days = 60
        else:
            notification_days = 7
            collection_days = 45
            resolution_days = 90

        return {
            'initiation': now,
            'customer_notification': now + timedelta(days=notification_days),
            'inventory_quarantine': now + timedelta(days=1),
            'collection_complete': now + timedelta(days=collection_days),
            'replacements_shipped': now + timedelta(days=collection_days + 7),
            'case_closure': now + timedelta(days=resolution_days),
        }

    def _generate_action_plan(
        self,
        severity: RecallSeverity,
        scope: RecallScope,
        affected_count: int
    ) -> List[str]:
        """Generate step-by-step action plan."""
        plan = [
            "1. Immediate: Quarantine all inventory matching recall criteria",
            "2. Immediate: Stop shipment of affected products",
            "3. Day 1: Notify regulatory authorities (if applicable)",
            "4. Day 1-2: Prepare customer notification communications",
            f"5. Day 2-3: Contact {affected_count} affected customers",
            "6. Day 3-7: Set up return/replacement logistics",
            "7. Ongoing: Track returns and replacements",
            "8. Weekly: Report progress to management",
            "9. Completion: Document lessons learned",
            "10. Post-recall: Implement corrective actions",
        ]

        if severity == RecallSeverity.CRITICAL:
            plan.insert(0, "URGENT: Activate crisis management team")
            plan.insert(1, "URGENT: Prepare public statement")

        return plan

    def _create_notification_templates(
        self,
        reason: str,
        severity: RecallSeverity
    ) -> Dict[str, str]:
        """Create notification templates."""
        urgency = "URGENT: " if severity == RecallSeverity.CRITICAL else ""

        return {
            'email_subject': f"{urgency}Product Recall Notice - Action Required",
            'email_body': f"""
Dear Valued Customer,

We are contacting you regarding a {severity.value} product recall.

Reason: {reason}

Action Required:
1. Stop using the affected product immediately
2. Contact our support team at [PHONE] or [EMAIL]
3. Await further instructions for return/replacement

We sincerely apologize for any inconvenience.

Best regards,
LegoMCP Quality Assurance Team
            """.strip(),
            'internal_memo': f"""
INTERNAL RECALL NOTICE

Severity: {severity.value.upper()}
Reason: {reason}

Immediate Actions:
- Quarantine all matching inventory
- Stop all shipments of affected products
- Await customer service script from QA team

Do NOT discuss with customers until official communications are approved.
            """.strip(),
        }

    def get_simulation_report(self, simulation_id: str) -> Optional[Dict]:
        """Get a formatted report of a simulation."""
        sim = self.simulation_history.get(simulation_id)
        if not sim:
            return None

        return {
            'simulation_id': sim.simulation_id,
            'recall_reason': sim.recall_reason,
            'severity': sim.severity.value,
            'scope': sim.scope.value,
            'summary': sim.summary,
            'total_cost': sim.cost_estimate['total_estimated'],
            'timeline_days': (
                sim.timeline_estimate['case_closure'] -
                sim.timeline_estimate['initiation']
            ).days,
            'action_items': len(sim.action_plan),
        }


# Singleton instance
_recall_simulator: Optional[RecallSimulator] = None


def get_recall_simulator() -> RecallSimulator:
    """Get or create the recall simulator instance."""
    global _recall_simulator
    if _recall_simulator is None:
        _recall_simulator = RecallSimulator()
    return _recall_simulator
