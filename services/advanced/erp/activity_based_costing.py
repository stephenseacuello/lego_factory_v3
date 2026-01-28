"""
Activity-Based Costing (ABC) Service

LegoMCP World-Class Manufacturing System v5.0
Phase 16: Quality Costing

Activity-Based Costing for manufacturing and quality activities:
- Activity definition and cost driver identification
- Cost pool management
- Activity rate calculation
- Product/part costing with activity consumption
- Quality activity costing

References:
- Cooper & Kaplan ABC methodology
- CAM-I Activity-Based Management
- ISO 10014
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
import uuid


class ActivityType(Enum):
    """Types of manufacturing activities."""
    # Unit-level (per unit produced)
    PRINTING = "printing"
    ASSEMBLY = "assembly"
    INSPECTION = "inspection"
    TESTING = "testing"
    PACKAGING = "packaging"

    # Batch-level (per batch/setup)
    SETUP = "setup"
    MATERIAL_HANDLING = "material_handling"
    FIRST_ARTICLE = "first_article"
    TOOL_CHANGE = "tool_change"

    # Product-level (per product type)
    ENGINEERING = "engineering"
    PROCESS_DESIGN = "process_design"
    QUALITY_PLANNING = "quality_planning"
    FMEA = "fmea"

    # Facility-level (sustaining)
    MAINTENANCE = "maintenance"
    SUPERVISION = "supervision"
    UTILITIES = "utilities"
    DEPRECIATION = "depreciation"


class CostDriver(Enum):
    """Activity cost drivers."""
    MACHINE_HOURS = "machine_hours"
    LABOR_HOURS = "labor_hours"
    SETUP_HOURS = "setup_hours"
    UNITS_PRODUCED = "units_produced"
    BATCHES = "batches"
    INSPECTIONS = "inspections"
    TESTS = "tests"
    MATERIAL_MOVES = "material_moves"
    ENGINEERING_HOURS = "engineering_hours"
    SQUARE_FOOTAGE = "square_footage"


@dataclass
class Activity:
    """An activity in the ABC model."""
    activity_id: str
    name: str
    activity_type: ActivityType
    cost_driver: CostDriver
    description: str = ""
    cost_pool: Decimal = Decimal('0')
    driver_quantity: float = 0
    rate: Decimal = Decimal('0')  # Cost per driver unit
    is_quality_activity: bool = False


@dataclass
class ActivityConsumption:
    """Record of activity consumption."""
    consumption_id: str
    timestamp: datetime
    activity_id: str
    part_id: Optional[str]
    work_order_id: Optional[str]
    driver_quantity: float
    calculated_cost: Decimal


@dataclass
class ProductCost:
    """ABC-calculated product cost."""
    part_id: str
    direct_materials: Decimal
    direct_labor: Decimal
    activity_costs: Dict[str, Decimal]
    total_cost: Decimal
    cost_breakdown: List[Dict[str, Any]]


class ActivityBasedCostingService:
    """
    Activity-Based Costing Service.

    Provides ABC costing for manufacturing operations:
    - Define activities and cost drivers
    - Allocate costs to cost pools
    - Calculate activity rates
    - Assign costs to products based on activity consumption
    """

    def __init__(self):
        self._activities: Dict[str, Activity] = {}
        self._consumptions: List[ActivityConsumption] = []
        self._setup_default_activities()

    def _setup_default_activities(self):
        """Set up default manufacturing activities."""
        defaults = [
            # Unit-level activities
            Activity(
                activity_id="ACT-PRINT",
                name="3D Printing",
                activity_type=ActivityType.PRINTING,
                cost_driver=CostDriver.MACHINE_HOURS,
                description="FDM 3D printing operations",
                cost_pool=Decimal('5000'),
                driver_quantity=200,  # hours/month
            ),
            Activity(
                activity_id="ACT-ASSEMBLY",
                name="Assembly",
                activity_type=ActivityType.ASSEMBLY,
                cost_driver=CostDriver.LABOR_HOURS,
                description="Manual assembly operations",
                cost_pool=Decimal('3000'),
                driver_quantity=150,
            ),
            Activity(
                activity_id="ACT-INSPECT",
                name="Quality Inspection",
                activity_type=ActivityType.INSPECTION,
                cost_driver=CostDriver.INSPECTIONS,
                description="In-process and final inspection",
                cost_pool=Decimal('2000'),
                driver_quantity=500,
                is_quality_activity=True,
            ),
            Activity(
                activity_id="ACT-TEST",
                name="LEGO Compatibility Testing",
                activity_type=ActivityType.TESTING,
                cost_driver=CostDriver.TESTS,
                description="Clutch power and dimensional testing",
                cost_pool=Decimal('1500'),
                driver_quantity=200,
                is_quality_activity=True,
            ),

            # Batch-level activities
            Activity(
                activity_id="ACT-SETUP",
                name="Machine Setup",
                activity_type=ActivityType.SETUP,
                cost_driver=CostDriver.SETUP_HOURS,
                description="Print job setup and calibration",
                cost_pool=Decimal('2500'),
                driver_quantity=50,
            ),
            Activity(
                activity_id="ACT-MATL",
                name="Material Handling",
                activity_type=ActivityType.MATERIAL_HANDLING,
                cost_driver=CostDriver.MATERIAL_MOVES,
                description="Material movement and staging",
                cost_pool=Decimal('1000'),
                driver_quantity=100,
            ),

            # Product-level activities
            Activity(
                activity_id="ACT-ENG",
                name="Engineering",
                activity_type=ActivityType.ENGINEERING,
                cost_driver=CostDriver.ENGINEERING_HOURS,
                description="Product engineering and design",
                cost_pool=Decimal('4000'),
                driver_quantity=80,
            ),
            Activity(
                activity_id="ACT-FMEA",
                name="FMEA Analysis",
                activity_type=ActivityType.FMEA,
                cost_driver=CostDriver.ENGINEERING_HOURS,
                description="Failure mode and effects analysis",
                cost_pool=Decimal('1200'),
                driver_quantity=30,
                is_quality_activity=True,
            ),

            # Facility-level
            Activity(
                activity_id="ACT-MAINT",
                name="Maintenance",
                activity_type=ActivityType.MAINTENANCE,
                cost_driver=CostDriver.MACHINE_HOURS,
                description="Equipment maintenance",
                cost_pool=Decimal('3000'),
                driver_quantity=200,
            ),
        ]

        for activity in defaults:
            activity.rate = self._calculate_rate(activity)
            self._activities[activity.activity_id] = activity

    def _calculate_rate(self, activity: Activity) -> Decimal:
        """Calculate activity rate from cost pool and driver quantity."""
        if activity.driver_quantity > 0:
            return activity.cost_pool / Decimal(str(activity.driver_quantity))
        return Decimal('0')

    def define_activity(
        self,
        name: str,
        activity_type: ActivityType,
        cost_driver: CostDriver,
        cost_pool: float,
        driver_quantity: float,
        description: str = "",
        is_quality_activity: bool = False
    ) -> Activity:
        """
        Define a new activity.

        Args:
            name: Activity name
            activity_type: Type of activity
            cost_driver: Cost driver for allocation
            cost_pool: Total cost pool for the activity
            driver_quantity: Expected quantity of cost driver
            description: Activity description
            is_quality_activity: Whether this is a quality-related activity

        Returns:
            Created activity
        """
        activity_id = f"ACT-{name.upper().replace(' ', '-')[:10]}"

        activity = Activity(
            activity_id=activity_id,
            name=name,
            activity_type=activity_type,
            cost_driver=cost_driver,
            description=description,
            cost_pool=Decimal(str(cost_pool)),
            driver_quantity=driver_quantity,
            is_quality_activity=is_quality_activity,
        )

        activity.rate = self._calculate_rate(activity)
        self._activities[activity_id] = activity

        return activity

    def update_cost_pool(
        self,
        activity_id: str,
        cost_pool: float,
        driver_quantity: Optional[float] = None
    ) -> Activity:
        """Update activity cost pool and recalculate rate."""
        if activity_id not in self._activities:
            raise ValueError(f"Activity {activity_id} not found")

        activity = self._activities[activity_id]
        activity.cost_pool = Decimal(str(cost_pool))

        if driver_quantity is not None:
            activity.driver_quantity = driver_quantity

        activity.rate = self._calculate_rate(activity)
        return activity

    def get_activity(self, activity_id: str) -> Optional[Activity]:
        """Get activity by ID."""
        return self._activities.get(activity_id)

    def get_all_activities(self) -> List[Activity]:
        """Get all defined activities."""
        return list(self._activities.values())

    def get_quality_activities(self) -> List[Activity]:
        """Get only quality-related activities."""
        return [a for a in self._activities.values() if a.is_quality_activity]

    def record_consumption(
        self,
        activity_id: str,
        driver_quantity: float,
        part_id: Optional[str] = None,
        work_order_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> ActivityConsumption:
        """
        Record activity consumption.

        Args:
            activity_id: Activity being consumed
            driver_quantity: Quantity of cost driver used
            part_id: Part consuming the activity
            work_order_id: Work order consuming the activity
            timestamp: When consumption occurred

        Returns:
            Consumption record
        """
        if activity_id not in self._activities:
            raise ValueError(f"Activity {activity_id} not found")

        activity = self._activities[activity_id]
        cost = activity.rate * Decimal(str(driver_quantity))

        consumption = ActivityConsumption(
            consumption_id=str(uuid.uuid4()),
            timestamp=timestamp or datetime.utcnow(),
            activity_id=activity_id,
            part_id=part_id,
            work_order_id=work_order_id,
            driver_quantity=driver_quantity,
            calculated_cost=cost,
        )

        self._consumptions.append(consumption)
        return consumption

    def calculate_part_cost(
        self,
        part_id: str,
        direct_materials: float = 0,
        direct_labor: float = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> ProductCost:
        """
        Calculate full product cost including activity costs.

        Args:
            part_id: Part to cost
            direct_materials: Direct material cost
            direct_labor: Direct labor cost
            start_date: Period start (optional)
            end_date: Period end (optional)

        Returns:
            Complete product cost breakdown
        """
        # Filter consumptions for this part
        consumptions = [
            c for c in self._consumptions
            if c.part_id == part_id
        ]

        if start_date:
            consumptions = [c for c in consumptions if c.timestamp >= start_date]
        if end_date:
            consumptions = [c for c in consumptions if c.timestamp < end_date]

        # Sum by activity
        activity_costs = {}
        breakdown = []

        for consumption in consumptions:
            activity = self._activities.get(consumption.activity_id)
            if activity:
                if activity.activity_id not in activity_costs:
                    activity_costs[activity.activity_id] = Decimal('0')
                activity_costs[activity.activity_id] += consumption.calculated_cost

                breakdown.append({
                    'activity': activity.name,
                    'activity_type': activity.activity_type.value,
                    'driver': activity.cost_driver.value,
                    'driver_quantity': consumption.driver_quantity,
                    'rate': float(activity.rate),
                    'cost': float(consumption.calculated_cost),
                    'is_quality': activity.is_quality_activity,
                })

        total_activity_cost = sum(activity_costs.values())
        total_cost = (
            Decimal(str(direct_materials)) +
            Decimal(str(direct_labor)) +
            total_activity_cost
        )

        return ProductCost(
            part_id=part_id,
            direct_materials=Decimal(str(direct_materials)),
            direct_labor=Decimal(str(direct_labor)),
            activity_costs={k: v for k, v in activity_costs.items()},
            total_cost=total_cost,
            cost_breakdown=breakdown,
        )

    def calculate_work_order_cost(
        self,
        work_order_id: str,
        direct_materials: float = 0,
        direct_labor: float = 0
    ) -> Dict[str, Any]:
        """
        Calculate work order cost using ABC.

        Args:
            work_order_id: Work order to cost
            direct_materials: Direct material cost
            direct_labor: Direct labor cost

        Returns:
            Work order cost breakdown
        """
        consumptions = [
            c for c in self._consumptions
            if c.work_order_id == work_order_id
        ]

        activity_costs = {}
        quality_costs = Decimal('0')
        non_quality_costs = Decimal('0')

        for consumption in consumptions:
            activity = self._activities.get(consumption.activity_id)
            if activity:
                if activity.activity_id not in activity_costs:
                    activity_costs[activity.activity_id] = {
                        'name': activity.name,
                        'cost': Decimal('0'),
                        'is_quality': activity.is_quality_activity,
                    }
                activity_costs[activity.activity_id]['cost'] += consumption.calculated_cost

                if activity.is_quality_activity:
                    quality_costs += consumption.calculated_cost
                else:
                    non_quality_costs += consumption.calculated_cost

        total_activity = quality_costs + non_quality_costs
        total_cost = (
            Decimal(str(direct_materials)) +
            Decimal(str(direct_labor)) +
            total_activity
        )

        return {
            'work_order_id': work_order_id,
            'direct_materials': float(Decimal(str(direct_materials))),
            'direct_labor': float(Decimal(str(direct_labor))),
            'activity_costs': {
                k: {'name': v['name'], 'cost': float(v['cost']), 'is_quality': v['is_quality']}
                for k, v in activity_costs.items()
            },
            'quality_activity_cost': float(quality_costs),
            'non_quality_activity_cost': float(non_quality_costs),
            'total_overhead': float(total_activity),
            'total_cost': float(total_cost),
            'quality_cost_percentage': float(quality_costs / total_cost * 100) if total_cost else 0,
        }

    def get_activity_summary(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get summary of activity consumption for a period.

        Returns cost and volume by activity.
        """
        period_consumptions = [
            c for c in self._consumptions
            if start_date <= c.timestamp < end_date
        ]

        summary = {}
        total_cost = Decimal('0')

        for activity_id, activity in self._activities.items():
            activity_consumptions = [
                c for c in period_consumptions
                if c.activity_id == activity_id
            ]

            if activity_consumptions:
                activity_cost = sum(c.calculated_cost for c in activity_consumptions)
                total_cost += activity_cost

                summary[activity_id] = {
                    'name': activity.name,
                    'type': activity.activity_type.value,
                    'driver': activity.cost_driver.value,
                    'rate': float(activity.rate),
                    'consumption_count': len(activity_consumptions),
                    'total_driver_quantity': sum(c.driver_quantity for c in activity_consumptions),
                    'total_cost': float(activity_cost),
                    'is_quality': activity.is_quality_activity,
                }

        # Add percentages
        for activity_id in summary:
            if total_cost > 0:
                summary[activity_id]['percentage'] = float(
                    Decimal(str(summary[activity_id]['total_cost'])) / total_cost * 100
                )
            else:
                summary[activity_id]['percentage'] = 0

        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
            },
            'activities': summary,
            'total_cost': float(total_cost),
            'quality_cost': float(sum(
                Decimal(str(s['total_cost'])) for s in summary.values() if s['is_quality']
            )),
        }

    def identify_cost_reduction_opportunities(self) -> List[Dict[str, Any]]:
        """
        Identify opportunities to reduce costs through activity analysis.

        Returns prioritized list of opportunities.
        """
        opportunities = []

        # Get recent data
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        summary = self.get_activity_summary(start_date, end_date)

        # Find high-cost, low-value activities
        for activity_id, data in summary.get('activities', {}).items():
            activity = self._activities.get(activity_id)
            if not activity:
                continue

            # Check for batch-level activities with high cost
            if (activity.activity_type == ActivityType.SETUP and
                data['total_cost'] > 500):
                opportunities.append({
                    'priority': 'medium',
                    'activity': activity.name,
                    'finding': f"High setup costs: ${data['total_cost']:.2f}/month",
                    'recommendation': "Consider batch consolidation or SMED implementation",
                    'potential_savings': data['total_cost'] * 0.20,
                })

            # Check for quality activities that might be reduced
            if activity.is_quality_activity and data['percentage'] > 20:
                opportunities.append({
                    'priority': 'low',
                    'activity': activity.name,
                    'finding': f"Quality activity is {data['percentage']:.1f}% of total overhead",
                    'recommendation': "Review inspection frequency - consider SPC or sampling",
                    'potential_savings': data['total_cost'] * 0.10,
                })

        # Sort by potential savings
        opportunities.sort(key=lambda x: x['potential_savings'], reverse=True)
        return opportunities

    def calculate_activity_rates_for_pricing(
        self,
        part_id: str,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """
        Calculate activity-based costs for pricing decisions.

        Args:
            part_id: Part to price
            quantity: Order quantity

        Returns:
            Pricing data with activity breakdown
        """
        # Get historical consumption for this part
        part_consumptions = [
            c for c in self._consumptions
            if c.part_id == part_id
        ]

        if not part_consumptions:
            # Estimate based on part type
            return {
                'part_id': part_id,
                'estimated': True,
                'unit_activity_cost': 0.50,  # Default estimate
                'quantity': quantity,
                'total_activity_cost': 0.50 * quantity,
            }

        # Calculate average activity cost per unit
        total_cost = sum(c.calculated_cost for c in part_consumptions)
        total_units = len(set(c.work_order_id for c in part_consumptions if c.work_order_id))
        if total_units == 0:
            total_units = 1

        avg_cost_per_unit = total_cost / Decimal(str(total_units))

        return {
            'part_id': part_id,
            'estimated': False,
            'unit_activity_cost': float(avg_cost_per_unit),
            'quantity': quantity,
            'total_activity_cost': float(avg_cost_per_unit * quantity),
            'historical_samples': len(part_consumptions),
        }


# Global instance
_abc_service: Optional[ActivityBasedCostingService] = None


def get_abc_service() -> ActivityBasedCostingService:
    """Get or create ABC Service instance."""
    global _abc_service
    if _abc_service is None:
        _abc_service = ActivityBasedCostingService()
    return _abc_service
