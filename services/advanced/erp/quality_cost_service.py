"""
Quality Cost Service - Cost of Quality (COQ) Management

LegoMCP World-Class Manufacturing System v5.0
Phase 16: Quality Costing

Implements ASQ/Juran Cost of Quality model:
- Prevention Costs: Training, process improvement, quality planning
- Appraisal Costs: Inspection, testing, audits
- Internal Failure Costs: Scrap, rework, retest
- External Failure Costs: Returns, warranty, recalls, reputation

References:
- ASQ Cost of Quality guidelines
- ISO 10014: Quality management - Guidelines for realizing financial benefits
- Juran's Quality Handbook (7th ed)
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
import uuid


class CostCategory(Enum):
    """Cost of Quality categories."""
    PREVENTION = "prevention"
    APPRAISAL = "appraisal"
    INTERNAL_FAILURE = "internal_failure"
    EXTERNAL_FAILURE = "external_failure"


class CostElement(Enum):
    """Detailed cost elements within each category."""
    # Prevention
    QUALITY_PLANNING = "quality_planning"
    TRAINING = "training"
    PROCESS_CONTROL = "process_control"
    SUPPLIER_QUALITY = "supplier_quality"
    DESIGN_REVIEW = "design_review"
    FMEA = "fmea"
    SPC_IMPLEMENTATION = "spc_implementation"

    # Appraisal
    INSPECTION = "inspection"
    TESTING = "testing"
    MEASUREMENT = "measurement"
    AUDIT = "audit"
    CALIBRATION = "calibration"
    SUPPLIER_AUDIT = "supplier_audit"
    LEGO_COMPATIBILITY_TEST = "lego_compatibility_test"

    # Internal Failure
    SCRAP = "scrap"
    REWORK = "rework"
    RETEST = "retest"
    DOWNGRADE = "downgrade"
    MACHINE_DOWNTIME = "machine_downtime"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"

    # External Failure
    WARRANTY = "warranty"
    RETURNS = "returns"
    COMPLAINTS = "complaints"
    RECALL = "recall"
    LIABILITY = "liability"
    REPUTATION_LOSS = "reputation_loss"
    CUSTOMER_COMPENSATION = "customer_compensation"


# Mapping elements to categories
ELEMENT_CATEGORY_MAP = {
    # Prevention
    CostElement.QUALITY_PLANNING: CostCategory.PREVENTION,
    CostElement.TRAINING: CostCategory.PREVENTION,
    CostElement.PROCESS_CONTROL: CostCategory.PREVENTION,
    CostElement.SUPPLIER_QUALITY: CostCategory.PREVENTION,
    CostElement.DESIGN_REVIEW: CostCategory.PREVENTION,
    CostElement.FMEA: CostCategory.PREVENTION,
    CostElement.SPC_IMPLEMENTATION: CostCategory.PREVENTION,

    # Appraisal
    CostElement.INSPECTION: CostCategory.APPRAISAL,
    CostElement.TESTING: CostCategory.APPRAISAL,
    CostElement.MEASUREMENT: CostCategory.APPRAISAL,
    CostElement.AUDIT: CostCategory.APPRAISAL,
    CostElement.CALIBRATION: CostCategory.APPRAISAL,
    CostElement.SUPPLIER_AUDIT: CostCategory.APPRAISAL,
    CostElement.LEGO_COMPATIBILITY_TEST: CostCategory.APPRAISAL,

    # Internal Failure
    CostElement.SCRAP: CostCategory.INTERNAL_FAILURE,
    CostElement.REWORK: CostCategory.INTERNAL_FAILURE,
    CostElement.RETEST: CostCategory.INTERNAL_FAILURE,
    CostElement.DOWNGRADE: CostCategory.INTERNAL_FAILURE,
    CostElement.MACHINE_DOWNTIME: CostCategory.INTERNAL_FAILURE,
    CostElement.ROOT_CAUSE_ANALYSIS: CostCategory.INTERNAL_FAILURE,

    # External Failure
    CostElement.WARRANTY: CostCategory.EXTERNAL_FAILURE,
    CostElement.RETURNS: CostCategory.EXTERNAL_FAILURE,
    CostElement.COMPLAINTS: CostCategory.EXTERNAL_FAILURE,
    CostElement.RECALL: CostCategory.EXTERNAL_FAILURE,
    CostElement.LIABILITY: CostCategory.EXTERNAL_FAILURE,
    CostElement.REPUTATION_LOSS: CostCategory.EXTERNAL_FAILURE,
    CostElement.CUSTOMER_COMPENSATION: CostCategory.EXTERNAL_FAILURE,
}


@dataclass
class QualityCostEntry:
    """A single quality cost entry."""
    entry_id: str
    timestamp: datetime
    category: CostCategory
    element: CostElement
    amount: Decimal
    description: str
    work_order_id: Optional[str] = None
    part_id: Optional[str] = None
    defect_id: Optional[str] = None
    quantity: float = 1.0
    unit: str = "each"
    recorded_by: Optional[str] = None
    cost_center: Optional[str] = None


@dataclass
class COQSummary:
    """Cost of Quality summary."""
    period_start: datetime
    period_end: datetime
    prevention_costs: Decimal
    appraisal_costs: Decimal
    internal_failure_costs: Decimal
    external_failure_costs: Decimal
    total_coq: Decimal
    revenue: Decimal
    coq_percentage: float
    conformance_cost: Decimal  # Prevention + Appraisal
    nonconformance_cost: Decimal  # Internal + External Failure
    ratio: float  # Conformance / Nonconformance


class QualityCostService:
    """
    Quality Cost Service - Tracks and analyzes Cost of Quality.

    Implements the ASQ/Juran COQ model to:
    - Track quality-related costs by category
    - Calculate COQ as percentage of revenue
    - Identify opportunities for quality investment
    - Support quality improvement ROI analysis
    """

    def __init__(self):
        self._entries: List[QualityCostEntry] = []
        self._revenue_by_period: Dict[str, Decimal] = {}
        self._targets = {
            'coq_percentage': 10.0,  # Target: 10% of revenue
            'prevention_percentage': 30.0,  # Prevention should be 30% of COQ
            'conformance_ratio': 1.5,  # Conformance should be 1.5x nonconformance
        }

    def record_cost(
        self,
        element: CostElement,
        amount: float,
        description: str,
        work_order_id: Optional[str] = None,
        part_id: Optional[str] = None,
        defect_id: Optional[str] = None,
        quantity: float = 1.0,
        recorded_by: Optional[str] = None,
        cost_center: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> QualityCostEntry:
        """
        Record a quality cost.

        Args:
            element: Cost element type
            amount: Cost amount in dollars
            description: Description of the cost
            work_order_id: Related work order
            part_id: Related part
            defect_id: Related defect/NCR
            quantity: Quantity (for per-unit costs)
            recorded_by: Person recording the cost
            cost_center: Cost center for accounting

        Returns:
            Created cost entry
        """
        category = ELEMENT_CATEGORY_MAP.get(element, CostCategory.INTERNAL_FAILURE)

        entry = QualityCostEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=timestamp or datetime.utcnow(),
            category=category,
            element=element,
            amount=Decimal(str(amount)),
            description=description,
            work_order_id=work_order_id,
            part_id=part_id,
            defect_id=defect_id,
            quantity=quantity,
            recorded_by=recorded_by,
            cost_center=cost_center,
        )

        self._entries.append(entry)
        return entry

    def record_scrap_cost(
        self,
        work_order_id: str,
        part_id: str,
        quantity: int,
        unit_cost: float,
        reason: str,
        defect_id: Optional[str] = None
    ) -> QualityCostEntry:
        """Record scrap cost from rejected parts."""
        total_cost = quantity * unit_cost
        return self.record_cost(
            element=CostElement.SCRAP,
            amount=total_cost,
            description=f"Scrap: {quantity} units - {reason}",
            work_order_id=work_order_id,
            part_id=part_id,
            defect_id=defect_id,
            quantity=quantity,
        )

    def record_rework_cost(
        self,
        work_order_id: str,
        part_id: str,
        labor_hours: float,
        labor_rate: float,
        material_cost: float,
        reason: str
    ) -> QualityCostEntry:
        """Record rework cost."""
        total_cost = (labor_hours * labor_rate) + material_cost
        return self.record_cost(
            element=CostElement.REWORK,
            amount=total_cost,
            description=f"Rework: {labor_hours:.1f}hrs - {reason}",
            work_order_id=work_order_id,
            part_id=part_id,
            quantity=labor_hours,
            unit="hours",
        )

    def record_inspection_cost(
        self,
        work_order_id: Optional[str],
        inspector_hours: float,
        inspector_rate: float,
        equipment_cost: float = 0,
        inspection_type: str = "standard"
    ) -> QualityCostEntry:
        """Record inspection/appraisal cost."""
        total_cost = (inspector_hours * inspector_rate) + equipment_cost
        return self.record_cost(
            element=CostElement.INSPECTION,
            amount=total_cost,
            description=f"{inspection_type} inspection: {inspector_hours:.1f}hrs",
            work_order_id=work_order_id,
            quantity=inspector_hours,
            unit="hours",
        )

    def record_warranty_cost(
        self,
        customer_order_id: str,
        repair_cost: float,
        shipping_cost: float,
        replacement_cost: float,
        part_id: Optional[str] = None,
        description: str = "Warranty claim"
    ) -> QualityCostEntry:
        """Record warranty/external failure cost."""
        total_cost = repair_cost + shipping_cost + replacement_cost
        return self.record_cost(
            element=CostElement.WARRANTY,
            amount=total_cost,
            description=f"Warranty: {description}",
            part_id=part_id,
        )

    def record_training_cost(
        self,
        training_type: str,
        attendee_count: int,
        hours: float,
        cost_per_hour: float,
        materials_cost: float = 0
    ) -> QualityCostEntry:
        """Record quality training cost (prevention)."""
        labor_cost = attendee_count * hours * cost_per_hour
        total_cost = labor_cost + materials_cost
        return self.record_cost(
            element=CostElement.TRAINING,
            amount=total_cost,
            description=f"Training: {training_type} ({attendee_count} attendees)",
            quantity=hours * attendee_count,
            unit="person-hours",
        )

    def set_period_revenue(
        self,
        period_key: str,
        revenue: float
    ) -> None:
        """Set revenue for a period (for COQ % calculation)."""
        self._revenue_by_period[period_key] = Decimal(str(revenue))

    def get_period_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        revenue: Optional[float] = None
    ) -> COQSummary:
        """
        Get Cost of Quality summary for a period.

        Args:
            start_date: Period start
            end_date: Period end
            revenue: Revenue for the period (for COQ %)

        Returns:
            COQ summary with category breakdowns
        """
        period_entries = [
            e for e in self._entries
            if start_date <= e.timestamp < end_date
        ]

        # Sum by category
        prevention = sum(
            e.amount for e in period_entries
            if e.category == CostCategory.PREVENTION
        )
        appraisal = sum(
            e.amount for e in period_entries
            if e.category == CostCategory.APPRAISAL
        )
        internal = sum(
            e.amount for e in period_entries
            if e.category == CostCategory.INTERNAL_FAILURE
        )
        external = sum(
            e.amount for e in period_entries
            if e.category == CostCategory.EXTERNAL_FAILURE
        )

        total_coq = prevention + appraisal + internal + external
        conformance = prevention + appraisal
        nonconformance = internal + external

        # Get revenue
        if revenue:
            period_revenue = Decimal(str(revenue))
        else:
            period_key = f"{start_date.year}-{start_date.month:02d}"
            period_revenue = self._revenue_by_period.get(period_key, Decimal('100000'))

        coq_percentage = float(total_coq / period_revenue * 100) if period_revenue else 0
        ratio = float(conformance / nonconformance) if nonconformance else float('inf')

        return COQSummary(
            period_start=start_date,
            period_end=end_date,
            prevention_costs=prevention,
            appraisal_costs=appraisal,
            internal_failure_costs=internal,
            external_failure_costs=external,
            total_coq=total_coq,
            revenue=period_revenue,
            coq_percentage=coq_percentage,
            conformance_cost=conformance,
            nonconformance_cost=nonconformance,
            ratio=ratio,
        )

    def get_element_breakdown(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Dict[str, Any]]:
        """Get detailed cost breakdown by element."""
        period_entries = [
            e for e in self._entries
            if start_date <= e.timestamp < end_date
        ]

        breakdown = {}
        for element in CostElement:
            element_entries = [e for e in period_entries if e.element == element]
            if element_entries:
                breakdown[element.value] = {
                    'category': ELEMENT_CATEGORY_MAP[element].value,
                    'count': len(element_entries),
                    'total_cost': float(sum(e.amount for e in element_entries)),
                    'avg_cost': float(sum(e.amount for e in element_entries) / len(element_entries)),
                }

        return breakdown

    def get_trend(
        self,
        months: int = 12
    ) -> List[Dict[str, Any]]:
        """Get monthly COQ trend."""
        trends = []
        now = datetime.utcnow()

        for i in range(months - 1, -1, -1):
            # Calculate month boundaries
            month_start = datetime(
                year=(now.year if now.month > i else now.year - 1),
                month=((now.month - i - 1) % 12) + 1,
                day=1
            )

            if month_start.month == 12:
                month_end = datetime(month_start.year + 1, 1, 1)
            else:
                month_end = datetime(month_start.year, month_start.month + 1, 1)

            summary = self.get_period_summary(month_start, month_end)

            trends.append({
                'period': month_start.strftime('%Y-%m'),
                'prevention': float(summary.prevention_costs),
                'appraisal': float(summary.appraisal_costs),
                'internal_failure': float(summary.internal_failure_costs),
                'external_failure': float(summary.external_failure_costs),
                'total_coq': float(summary.total_coq),
                'coq_percentage': summary.coq_percentage,
            })

        return trends

    def get_improvement_opportunities(self) -> List[Dict[str, Any]]:
        """
        Identify quality improvement opportunities based on COQ data.

        Returns prioritized list of improvement opportunities.
        """
        # Get last 3 months of data
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)

        summary = self.get_period_summary(start_date, end_date)
        breakdown = self.get_element_breakdown(start_date, end_date)

        opportunities = []

        # Check prevention investment ratio
        if summary.total_coq > 0:
            prevention_ratio = float(summary.prevention_costs / summary.total_coq)
            if prevention_ratio < 0.25:
                opportunities.append({
                    'priority': 'high',
                    'area': 'Prevention Investment',
                    'finding': f'Prevention costs are only {prevention_ratio*100:.1f}% of total COQ (target: 25-30%)',
                    'recommendation': 'Increase investment in training, process control, and FMEA',
                    'potential_savings': float(summary.nonconformance_cost * Decimal('0.15')),
                })

        # Check conformance/nonconformance ratio
        if summary.ratio < 1.0:
            opportunities.append({
                'priority': 'high',
                'area': 'Failure Cost Reduction',
                'finding': f'Nonconformance costs ({float(summary.nonconformance_cost):.2f}) exceed conformance costs',
                'recommendation': 'Focus on defect prevention to reduce failure costs',
                'potential_savings': float(summary.nonconformance_cost * Decimal('0.20')),
            })

        # Identify top cost drivers
        sorted_elements = sorted(
            breakdown.items(),
            key=lambda x: x[1]['total_cost'],
            reverse=True
        )

        for element_name, data in sorted_elements[:3]:
            if data['category'] in ['internal_failure', 'external_failure']:
                opportunities.append({
                    'priority': 'medium',
                    'area': f"{element_name.replace('_', ' ').title()}",
                    'finding': f"High {element_name} costs: ${data['total_cost']:.2f} ({data['count']} occurrences)",
                    'recommendation': f"Investigate root causes and implement preventive measures",
                    'potential_savings': data['total_cost'] * 0.30,
                })

        # Check overall COQ percentage
        if summary.coq_percentage > 15:
            opportunities.append({
                'priority': 'critical',
                'area': 'Overall Quality Costs',
                'finding': f"COQ is {summary.coq_percentage:.1f}% of revenue (target: <10%)",
                'recommendation': 'Implement comprehensive quality improvement program',
                'potential_savings': float(summary.total_coq * Decimal('0.25')),
            })

        return sorted(opportunities, key=lambda x: {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}[x['priority']])

    def calculate_quality_roi(
        self,
        prevention_investment: float,
        expected_failure_reduction: float = 0.20
    ) -> Dict[str, Any]:
        """
        Calculate ROI for a quality improvement investment.

        Args:
            prevention_investment: Proposed investment amount
            expected_failure_reduction: Expected reduction in failure costs (0-1)

        Returns:
            ROI analysis
        """
        # Get current failure costs
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=365)
        summary = self.get_period_summary(start_date, end_date)

        current_failure_costs = float(summary.nonconformance_cost)
        expected_savings = current_failure_costs * expected_failure_reduction

        net_benefit = expected_savings - prevention_investment
        roi = (net_benefit / prevention_investment * 100) if prevention_investment else 0
        payback_months = (prevention_investment / (expected_savings / 12)) if expected_savings else float('inf')

        return {
            'investment': prevention_investment,
            'current_annual_failure_costs': current_failure_costs,
            'expected_reduction_rate': expected_failure_reduction,
            'expected_annual_savings': expected_savings,
            'net_annual_benefit': net_benefit,
            'roi_percentage': roi,
            'payback_months': payback_months,
            'recommendation': 'Invest' if roi > 50 else 'Consider' if roi > 0 else 'Review',
        }

    def get_pareto_analysis(
        self,
        start_date: datetime,
        end_date: datetime,
        by: str = 'element'
    ) -> Dict[str, Any]:
        """
        Get Pareto analysis of quality costs.

        Args:
            start_date: Analysis start
            end_date: Analysis end
            by: Group by 'element', 'part_id', or 'defect_id'

        Returns:
            Pareto analysis with cumulative percentages
        """
        period_entries = [
            e for e in self._entries
            if start_date <= e.timestamp < end_date
        ]

        # Group by dimension
        groups = {}
        for entry in period_entries:
            if by == 'element':
                key = entry.element.value
            elif by == 'part_id':
                key = entry.part_id or 'unknown'
            elif by == 'defect_id':
                key = entry.defect_id or 'unknown'
            else:
                key = entry.element.value

            if key not in groups:
                groups[key] = Decimal('0')
            groups[key] += entry.amount

        # Sort descending
        sorted_groups = sorted(groups.items(), key=lambda x: x[1], reverse=True)

        # Calculate cumulative percentages
        total = sum(groups.values())
        cumulative = Decimal('0')
        pareto_items = []

        for name, amount in sorted_groups:
            cumulative += amount
            pareto_items.append({
                'name': name,
                'cost': float(amount),
                'percentage': float(amount / total * 100) if total else 0,
                'cumulative_percentage': float(cumulative / total * 100) if total else 0,
            })

        # Find 80% threshold
        threshold_index = next(
            (i for i, item in enumerate(pareto_items) if item['cumulative_percentage'] >= 80),
            len(pareto_items) - 1
        )

        return {
            'items': pareto_items,
            'total_cost': float(total),
            'vital_few': pareto_items[:threshold_index + 1],
            'vital_few_percentage': pareto_items[threshold_index]['cumulative_percentage'] if pareto_items else 0,
            'trivial_many_count': len(pareto_items) - threshold_index - 1,
        }


# Global instance
_quality_cost_service: Optional[QualityCostService] = None


def get_quality_cost_service() -> QualityCostService:
    """Get or create Quality Cost Service instance."""
    global _quality_cost_service
    if _quality_cost_service is None:
        _quality_cost_service = QualityCostService()
    return _quality_cost_service
