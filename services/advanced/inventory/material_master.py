"""
Material Master Service - 3D Printing Filament & Material Inventory Management.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Provides comprehensive material/filament tracking for LEGO brick production.

Features:
- Filament spool tracking (weight, remaining, usage history)
- Material property database (temperature, density, shrinkage)
- Lot/batch traceability
- Reorder point alerts
- Material consumption analytics
- LEGO-specific material profiles
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from collections import defaultdict
import json
import uuid
import logging
import math

logger = logging.getLogger(__name__)


# === Enums ===

class MaterialType(Enum):
    """Types of 3D printing materials."""
    PLA = "pla"
    PETG = "petg"
    ABS = "abs"
    ASA = "asa"
    TPU = "tpu"
    NYLON = "nylon"
    PC = "polycarbonate"
    PVA = "pva"  # Support material
    HIPS = "hips"  # Support material
    WOOD_FILL = "wood_fill"
    CARBON_FIBER = "carbon_fiber"
    METAL_FILL = "metal_fill"


class MaterialStatus(Enum):
    """Status of material/spool."""
    AVAILABLE = "available"
    IN_USE = "in_use"
    LOW_STOCK = "low_stock"
    EMPTY = "empty"
    EXPIRED = "expired"
    QUARANTINE = "quarantine"  # Quality hold
    RESERVED = "reserved"


class MaterialGrade(Enum):
    """Material quality grades."""
    PREMIUM = "premium"
    STANDARD = "standard"
    ECONOMY = "economy"
    ENGINEERING = "engineering"


class SpoolSize(Enum):
    """Standard spool sizes."""
    SMALL = 250  # 250g
    STANDARD = 1000  # 1kg
    LARGE = 2500  # 2.5kg
    BULK = 5000  # 5kg
    MASTER = 10000  # 10kg


# === Data Classes ===

@dataclass
class MaterialProperties:
    """Physical and printing properties of a material."""
    material_type: MaterialType
    density: float = 1.24  # g/cm³

    # Temperature settings (°C)
    print_temp_min: float = 190.0
    print_temp_max: float = 230.0
    print_temp_default: float = 210.0
    bed_temp_min: float = 50.0
    bed_temp_max: float = 70.0
    bed_temp_default: float = 60.0

    # Mechanical properties
    tensile_strength: float = 50.0  # MPa
    flexural_modulus: float = 3500.0  # MPa
    impact_strength: float = 5.0  # kJ/m²
    hardness: float = 80.0  # Shore D

    # Shrinkage and tolerances
    shrinkage_factor: float = 1.002
    moisture_sensitive: bool = False
    max_moisture_content: float = 0.05  # 0.05%

    # Printing characteristics
    requires_enclosure: bool = False
    requires_dry_box: bool = False
    print_speed_max: float = 100.0  # mm/s
    retraction_distance: float = 0.8  # mm

    # LEGO suitability
    lego_suitability: float = 0.85  # 0-1 score
    clutch_power_rating: str = "good"  # excellent, good, fair, poor

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['material_type'] = self.material_type.value
        return data


@dataclass
class FilamentSpool:
    """Individual filament spool tracking."""
    id: str
    material_type: MaterialType
    brand: str
    color: str
    color_code: str  # Hex color code

    # Weight tracking
    initial_weight_g: float  # Starting weight (e.g., 1000g)
    current_weight_g: float  # Current remaining weight
    spool_weight_g: float = 200.0  # Empty spool weight

    # Specifications
    diameter_mm: float = 1.75
    tolerance_mm: float = 0.02
    grade: MaterialGrade = MaterialGrade.STANDARD

    # Lot/batch tracking
    lot_number: str = ""
    batch_id: str = ""
    manufacture_date: Optional[str] = None
    expiry_date: Optional[str] = None

    # Location
    location: str = "filament_storage"
    printer_id: Optional[str] = None  # If loaded in printer

    # Status
    status: MaterialStatus = MaterialStatus.AVAILABLE
    opened_date: Optional[str] = None
    last_used: Optional[str] = None

    # Cost tracking
    unit_cost: float = 0.0  # Cost per kg
    currency: str = "USD"

    # Metadata
    supplier: str = ""
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def remaining_percentage(self) -> float:
        """Calculate remaining material percentage."""
        if self.initial_weight_g <= 0:
            return 0.0
        return (self.current_weight_g / self.initial_weight_g) * 100

    @property
    def used_weight_g(self) -> float:
        """Calculate used material weight."""
        return self.initial_weight_g - self.current_weight_g

    @property
    def remaining_length_m(self) -> float:
        """Estimate remaining filament length in meters."""
        # Length = weight / (density * π * (diameter/2)²)
        properties = MATERIAL_PROPERTIES.get(self.material_type)
        if not properties:
            density = 1.24
        else:
            density = properties.density

        radius_cm = (self.diameter_mm / 2) / 10  # Convert to cm
        cross_section_cm2 = math.pi * radius_cm ** 2
        length_cm = self.current_weight_g / (density * cross_section_cm2)
        return length_cm / 100  # Convert to meters

    @property
    def is_low_stock(self) -> bool:
        """Check if material is low."""
        return self.remaining_percentage < 20

    @property
    def is_expired(self) -> bool:
        """Check if material is expired."""
        if not self.expiry_date:
            return False
        try:
            expiry = datetime.fromisoformat(self.expiry_date)
            return datetime.now() > expiry
        except ValueError:
            return False

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['material_type'] = self.material_type.value
        data['grade'] = self.grade.value
        data['status'] = self.status.value
        data['remaining_percentage'] = self.remaining_percentage
        data['remaining_length_m'] = round(self.remaining_length_m, 1)
        data['is_low_stock'] = self.is_low_stock
        data['is_expired'] = self.is_expired
        return data


@dataclass
class MaterialTransaction:
    """Material movement/usage transaction."""
    id: str
    spool_id: str
    transaction_type: str  # receipt, issue, adjustment, scrap, return
    quantity_g: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Context
    work_order_id: Optional[str] = None
    print_job_id: Optional[str] = None
    printer_id: Optional[str] = None

    # Details
    reason: str = ""
    performed_by: str = ""
    notes: str = ""

    # Before/after weights
    weight_before: float = 0.0
    weight_after: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MaterialAlert:
    """Material-related alert."""
    id: str
    alert_type: str  # low_stock, expired, moisture, temperature
    severity: str  # critical, warning, info
    spool_id: Optional[str] = None
    message: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    acknowledged: bool = False
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# === Material Properties Database ===

MATERIAL_PROPERTIES: Dict[MaterialType, MaterialProperties] = {
    MaterialType.PLA: MaterialProperties(
        material_type=MaterialType.PLA,
        density=1.24,
        print_temp_min=190, print_temp_max=230, print_temp_default=210,
        bed_temp_min=50, bed_temp_max=70, bed_temp_default=60,
        tensile_strength=50, flexural_modulus=3500, impact_strength=5,
        shrinkage_factor=1.002,
        moisture_sensitive=True, max_moisture_content=0.05,
        print_speed_max=100, retraction_distance=0.8,
        lego_suitability=0.85, clutch_power_rating="good"
    ),
    MaterialType.PETG: MaterialProperties(
        material_type=MaterialType.PETG,
        density=1.27,
        print_temp_min=220, print_temp_max=260, print_temp_default=240,
        bed_temp_min=70, bed_temp_max=90, bed_temp_default=80,
        tensile_strength=53, flexural_modulus=2100, impact_strength=8,
        shrinkage_factor=1.003,
        moisture_sensitive=True, max_moisture_content=0.04,
        print_speed_max=80, retraction_distance=1.0,
        lego_suitability=0.95, clutch_power_rating="excellent"
    ),
    MaterialType.ABS: MaterialProperties(
        material_type=MaterialType.ABS,
        density=1.05,
        print_temp_min=220, print_temp_max=270, print_temp_default=245,
        bed_temp_min=90, bed_temp_max=110, bed_temp_default=100,
        tensile_strength=40, flexural_modulus=2300, impact_strength=20,
        shrinkage_factor=1.005,
        moisture_sensitive=True, max_moisture_content=0.03,
        requires_enclosure=True,
        print_speed_max=80, retraction_distance=0.6,
        lego_suitability=0.90, clutch_power_rating="excellent"
    ),
    MaterialType.ASA: MaterialProperties(
        material_type=MaterialType.ASA,
        density=1.07,
        print_temp_min=235, print_temp_max=280, print_temp_default=260,
        bed_temp_min=95, bed_temp_max=115, bed_temp_default=105,
        tensile_strength=42, flexural_modulus=2500, impact_strength=18,
        shrinkage_factor=1.005,
        moisture_sensitive=True, max_moisture_content=0.03,
        requires_enclosure=True,
        print_speed_max=70, retraction_distance=0.6,
        lego_suitability=0.88, clutch_power_rating="excellent"
    ),
    MaterialType.TPU: MaterialProperties(
        material_type=MaterialType.TPU,
        density=1.21,
        print_temp_min=210, print_temp_max=250, print_temp_default=230,
        bed_temp_min=40, bed_temp_max=60, bed_temp_default=50,
        tensile_strength=30, flexural_modulus=100, impact_strength=50,
        shrinkage_factor=1.001,
        moisture_sensitive=True, max_moisture_content=0.04,
        requires_dry_box=True,
        print_speed_max=40, retraction_distance=0.0,
        lego_suitability=0.60, clutch_power_rating="poor"
    ),
    MaterialType.NYLON: MaterialProperties(
        material_type=MaterialType.NYLON,
        density=1.14,
        print_temp_min=240, print_temp_max=280, print_temp_default=260,
        bed_temp_min=70, bed_temp_max=90, bed_temp_default=80,
        tensile_strength=75, flexural_modulus=2400, impact_strength=12,
        shrinkage_factor=1.015,
        moisture_sensitive=True, max_moisture_content=0.02,
        requires_enclosure=True, requires_dry_box=True,
        print_speed_max=60, retraction_distance=0.8,
        lego_suitability=0.70, clutch_power_rating="fair"
    ),
}


# === Material Master Service ===

class MaterialMasterService:
    """
    Material Master Service for 3D printing material management.

    Provides:
    - Filament spool CRUD operations
    - Material consumption tracking
    - Reorder point management
    - Usage analytics
    - LEGO-specific material recommendations
    """

    def __init__(self, storage_path: Optional[str] = None):
        self._spools: Dict[str, FilamentSpool] = {}
        self._transactions: List[MaterialTransaction] = []
        self._alerts: List[MaterialAlert] = []
        self._reorder_points: Dict[MaterialType, float] = {
            MaterialType.PLA: 1000,  # 1kg minimum
            MaterialType.PETG: 1000,
            MaterialType.ABS: 500,
            MaterialType.ASA: 500,
            MaterialType.TPU: 250,
        }
        logger.info("MaterialMasterService initialized")

    # === Spool Management ===

    def add_spool(self,
                  material_type: MaterialType,
                  brand: str,
                  color: str,
                  color_code: str = "#000000",
                  initial_weight_g: float = 1000.0,
                  diameter_mm: float = 1.75,
                  lot_number: str = "",
                  supplier: str = "",
                  unit_cost: float = 0.0,
                  **kwargs) -> FilamentSpool:
        """
        Add a new filament spool to inventory.

        Args:
            material_type: Type of material
            brand: Manufacturer/brand name
            color: Color name
            color_code: Hex color code
            initial_weight_g: Initial weight in grams
            diameter_mm: Filament diameter
            lot_number: Lot/batch number
            supplier: Supplier name
            unit_cost: Cost per kg

        Returns:
            Created FilamentSpool
        """
        spool_id = str(uuid.uuid4())[:8].upper()

        spool = FilamentSpool(
            id=spool_id,
            material_type=material_type,
            brand=brand,
            color=color,
            color_code=color_code,
            initial_weight_g=initial_weight_g,
            current_weight_g=initial_weight_g,
            diameter_mm=diameter_mm,
            lot_number=lot_number,
            supplier=supplier,
            unit_cost=unit_cost,
            **kwargs
        )

        self._spools[spool_id] = spool

        # Log transaction
        self._log_transaction(
            spool_id=spool_id,
            transaction_type="receipt",
            quantity_g=initial_weight_g,
            reason=f"New spool added: {brand} {color}",
            weight_after=initial_weight_g
        )

        logger.info(f"Added spool {spool_id}: {brand} {color} {material_type.value}")
        return spool

    def get_spool(self, spool_id: str) -> Optional[FilamentSpool]:
        """Get spool by ID."""
        return self._spools.get(spool_id)

    def get_all_spools(self,
                       material_type: Optional[MaterialType] = None,
                       status: Optional[MaterialStatus] = None,
                       color: Optional[str] = None,
                       brand: Optional[str] = None) -> List[FilamentSpool]:
        """
        Get all spools with optional filtering.

        Args:
            material_type: Filter by material type
            status: Filter by status
            color: Filter by color
            brand: Filter by brand

        Returns:
            List of matching spools
        """
        spools = list(self._spools.values())

        if material_type:
            spools = [s for s in spools if s.material_type == material_type]
        if status:
            spools = [s for s in spools if s.status == status]
        if color:
            spools = [s for s in spools if color.lower() in s.color.lower()]
        if brand:
            spools = [s for s in spools if brand.lower() in s.brand.lower()]

        return spools

    def update_spool(self, spool_id: str, **updates) -> Optional[FilamentSpool]:
        """Update spool properties."""
        spool = self._spools.get(spool_id)
        if not spool:
            return None

        for key, value in updates.items():
            if hasattr(spool, key):
                setattr(spool, key, value)

        spool.updated_at = datetime.now().isoformat()
        return spool

    def delete_spool(self, spool_id: str) -> bool:
        """Delete a spool from inventory."""
        if spool_id in self._spools:
            del self._spools[spool_id]
            logger.info(f"Deleted spool {spool_id}")
            return True
        return False

    # === Material Consumption ===

    def consume_material(self,
                        spool_id: str,
                        weight_g: float,
                        work_order_id: Optional[str] = None,
                        print_job_id: Optional[str] = None,
                        printer_id: Optional[str] = None,
                        reason: str = "") -> Optional[MaterialTransaction]:
        """
        Record material consumption from a spool.

        Args:
            spool_id: Spool ID
            weight_g: Weight consumed in grams
            work_order_id: Associated work order
            print_job_id: Associated print job
            printer_id: Printer that used the material
            reason: Reason for consumption

        Returns:
            Transaction record or None if insufficient material
        """
        spool = self._spools.get(spool_id)
        if not spool:
            logger.warning(f"Spool not found: {spool_id}")
            return None

        if spool.current_weight_g < weight_g:
            logger.warning(f"Insufficient material in spool {spool_id}")
            return None

        weight_before = spool.current_weight_g
        spool.current_weight_g -= weight_g
        spool.last_used = datetime.now().isoformat()
        spool.updated_at = datetime.now().isoformat()

        # Update status if low
        if spool.current_weight_g <= 0:
            spool.status = MaterialStatus.EMPTY
        elif spool.is_low_stock:
            spool.status = MaterialStatus.LOW_STOCK
            self._create_alert(
                alert_type="low_stock",
                severity="warning",
                spool_id=spool_id,
                message=f"Low stock alert: {spool.brand} {spool.color} ({spool.remaining_percentage:.1f}% remaining)"
            )

        transaction = self._log_transaction(
            spool_id=spool_id,
            transaction_type="issue",
            quantity_g=weight_g,
            work_order_id=work_order_id,
            print_job_id=print_job_id,
            printer_id=printer_id,
            reason=reason or "Material consumed",
            weight_before=weight_before,
            weight_after=spool.current_weight_g
        )

        logger.info(f"Consumed {weight_g}g from spool {spool_id}")
        return transaction

    def adjust_weight(self,
                     spool_id: str,
                     new_weight_g: float,
                     reason: str = "Manual adjustment") -> Optional[MaterialTransaction]:
        """
        Adjust spool weight (e.g., after weighing).

        Args:
            spool_id: Spool ID
            new_weight_g: New weight in grams
            reason: Reason for adjustment

        Returns:
            Transaction record
        """
        spool = self._spools.get(spool_id)
        if not spool:
            return None

        weight_before = spool.current_weight_g
        difference = new_weight_g - weight_before

        spool.current_weight_g = new_weight_g
        spool.updated_at = datetime.now().isoformat()

        # Update status
        if spool.current_weight_g <= 0:
            spool.status = MaterialStatus.EMPTY
        elif spool.is_low_stock:
            spool.status = MaterialStatus.LOW_STOCK
        else:
            spool.status = MaterialStatus.AVAILABLE

        return self._log_transaction(
            spool_id=spool_id,
            transaction_type="adjustment",
            quantity_g=abs(difference),
            reason=f"{reason}: {'added' if difference > 0 else 'removed'} {abs(difference):.1f}g",
            weight_before=weight_before,
            weight_after=new_weight_g
        )

    def load_spool(self, spool_id: str, printer_id: str) -> bool:
        """Mark spool as loaded in a printer."""
        spool = self._spools.get(spool_id)
        if not spool:
            return False

        spool.status = MaterialStatus.IN_USE
        spool.printer_id = printer_id
        spool.updated_at = datetime.now().isoformat()

        if not spool.opened_date:
            spool.opened_date = datetime.now().isoformat()

        logger.info(f"Loaded spool {spool_id} into printer {printer_id}")
        return True

    def unload_spool(self, spool_id: str) -> bool:
        """Mark spool as unloaded from printer."""
        spool = self._spools.get(spool_id)
        if not spool:
            return False

        spool.status = MaterialStatus.AVAILABLE if not spool.is_low_stock else MaterialStatus.LOW_STOCK
        spool.printer_id = None
        spool.updated_at = datetime.now().isoformat()

        logger.info(f"Unloaded spool {spool_id}")
        return True

    # === Analytics ===

    def get_inventory_summary(self) -> Dict[str, Any]:
        """
        Get inventory summary statistics.

        Returns:
            Dict with inventory metrics
        """
        spools = list(self._spools.values())

        if not spools:
            return {
                "total_spools": 0,
                "total_weight_kg": 0,
                "total_value": 0,
                "by_material": {},
                "by_status": {},
                "alerts": []
            }

        total_weight_g = sum(s.current_weight_g for s in spools)

        # By material type
        by_material: Dict[str, Dict[str, float]] = {}
        for spool in spools:
            mat = spool.material_type.value
            if mat not in by_material:
                by_material[mat] = {"count": 0, "weight_kg": 0, "value": 0}
            by_material[mat]["count"] += 1
            by_material[mat]["weight_kg"] += spool.current_weight_g / 1000
            by_material[mat]["value"] += (spool.current_weight_g / 1000) * spool.unit_cost

        # By status
        by_status = defaultdict(int)
        for spool in spools:
            by_status[spool.status.value] += 1

        # Total value
        total_value = sum(
            (s.current_weight_g / 1000) * s.unit_cost for s in spools
        )

        # Active alerts
        active_alerts = [a for a in self._alerts if not a.acknowledged]

        return {
            "total_spools": len(spools),
            "total_weight_kg": round(total_weight_g / 1000, 2),
            "total_value": round(total_value, 2),
            "currency": "USD",
            "by_material": by_material,
            "by_status": dict(by_status),
            "low_stock_count": sum(1 for s in spools if s.is_low_stock),
            "expired_count": sum(1 for s in spools if s.is_expired),
            "alerts_count": len(active_alerts),
            "alerts": [a.to_dict() for a in active_alerts[:5]]
        }

    def get_consumption_report(self,
                               days: int = 30,
                               material_type: Optional[MaterialType] = None) -> Dict[str, Any]:
        """
        Get material consumption report.

        Args:
            days: Number of days to analyze
            material_type: Filter by material type

        Returns:
            Consumption analytics
        """
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        # Filter transactions
        issues = [
            t for t in self._transactions
            if t.transaction_type == "issue" and t.timestamp >= cutoff_str
        ]

        if material_type:
            spool_ids = {
                s.id for s in self._spools.values()
                if s.material_type == material_type
            }
            issues = [t for t in issues if t.spool_id in spool_ids]

        if not issues:
            return {
                "period_days": days,
                "total_consumed_g": 0,
                "daily_average_g": 0,
                "by_material": {},
                "top_colors": [],
                "by_printer": {}
            }

        total_consumed = sum(t.quantity_g for t in issues)

        # By material
        by_material: Dict[str, float] = defaultdict(float)
        for t in issues:
            spool = self._spools.get(t.spool_id)
            if spool:
                by_material[spool.material_type.value] += t.quantity_g

        # By color
        by_color: Dict[str, float] = defaultdict(float)
        for t in issues:
            spool = self._spools.get(t.spool_id)
            if spool:
                by_color[spool.color] += t.quantity_g

        top_colors = sorted(by_color.items(), key=lambda x: x[1], reverse=True)[:10]

        # By printer
        by_printer: Dict[str, float] = defaultdict(float)
        for t in issues:
            if t.printer_id:
                by_printer[t.printer_id] += t.quantity_g

        return {
            "period_days": days,
            "total_consumed_g": round(total_consumed, 1),
            "total_consumed_kg": round(total_consumed / 1000, 2),
            "daily_average_g": round(total_consumed / days, 1),
            "by_material": {k: round(v, 1) for k, v in by_material.items()},
            "top_colors": [(c, round(w, 1)) for c, w in top_colors],
            "by_printer": {k: round(v, 1) for k, v in by_printer.items()},
            "transaction_count": len(issues)
        }

    def get_reorder_recommendations(self) -> List[Dict[str, Any]]:
        """
        Get materials that need reordering.

        Returns:
            List of reorder recommendations
        """
        recommendations = []

        for material_type, min_stock in self._reorder_points.items():
            spools = self.get_all_spools(material_type=material_type)
            total_available = sum(s.current_weight_g for s in spools if s.status != MaterialStatus.EMPTY)

            if total_available < min_stock:
                shortage = min_stock - total_available
                recommendations.append({
                    "material_type": material_type.value,
                    "current_stock_g": round(total_available, 1),
                    "min_stock_g": min_stock,
                    "shortage_g": round(shortage, 1),
                    "recommended_order_g": max(1000, shortage * 1.5),  # Order 1.5x shortage or 1kg minimum
                    "priority": "high" if total_available < min_stock * 0.5 else "medium"
                })

        return sorted(recommendations, key=lambda x: x["shortage_g"], reverse=True)

    # === LEGO-Specific Methods ===

    def get_lego_recommended_materials(self,
                                       outdoor_use: bool = False,
                                       high_strength: bool = False,
                                       flexible: bool = False) -> List[Dict[str, Any]]:
        """
        Get recommended materials for LEGO brick printing.

        Args:
            outdoor_use: Needs UV resistance
            high_strength: Needs high mechanical strength
            flexible: Needs flexibility

        Returns:
            List of recommended materials with scores
        """
        recommendations = []

        for material_type, props in MATERIAL_PROPERTIES.items():
            score = props.lego_suitability * 100

            # Adjust for requirements
            if outdoor_use:
                if material_type in [MaterialType.ASA, MaterialType.ABS]:
                    score += 20
                elif material_type == MaterialType.PLA:
                    score -= 30

            if high_strength:
                if material_type in [MaterialType.PETG, MaterialType.ABS, MaterialType.NYLON]:
                    score += 15

            if flexible:
                if material_type == MaterialType.TPU:
                    score += 50
                else:
                    score -= 20

            recommendations.append({
                "material_type": material_type.value,
                "name": material_type.name,
                "score": round(score, 1),
                "lego_suitability": props.lego_suitability,
                "clutch_power": props.clutch_power_rating,
                "print_temp_default": props.print_temp_default,
                "bed_temp_default": props.bed_temp_default,
                "requires_enclosure": props.requires_enclosure,
                "shrinkage_factor": props.shrinkage_factor,
                "available_stock_g": sum(
                    s.current_weight_g for s in self.get_all_spools(material_type=material_type)
                )
            })

        return sorted(recommendations, key=lambda x: x["score"], reverse=True)

    def estimate_print_material(self,
                                volume_mm3: float,
                                material_type: MaterialType,
                                infill_percent: float = 20.0,
                                waste_factor: float = 1.05) -> Dict[str, Any]:
        """
        Estimate material needed for a print.

        Args:
            volume_mm3: Part volume in cubic mm
            material_type: Material to use
            infill_percent: Infill percentage (0-100)
            waste_factor: Waste multiplier (default 5%)

        Returns:
            Material estimation
        """
        props = MATERIAL_PROPERTIES.get(material_type)
        if not props:
            return {"error": "Unknown material type"}

        # Estimate actual material volume (accounting for infill)
        # Rough estimate: walls + infill
        effective_volume_mm3 = volume_mm3 * (0.3 + (infill_percent / 100) * 0.7)

        # Convert to weight
        volume_cm3 = effective_volume_mm3 / 1000
        weight_g = volume_cm3 * props.density * waste_factor

        # Check available stock
        available_spools = [
            s for s in self.get_all_spools(material_type=material_type)
            if s.current_weight_g >= weight_g
        ]

        return {
            "material_type": material_type.value,
            "estimated_weight_g": round(weight_g, 1),
            "volume_mm3": volume_mm3,
            "infill_percent": infill_percent,
            "waste_factor": waste_factor,
            "available_spools": len(available_spools),
            "sufficient_stock": len(available_spools) > 0,
            "density_g_cm3": props.density
        }

    # === Internal Methods ===

    def _log_transaction(self, **kwargs) -> MaterialTransaction:
        """Log a material transaction."""
        transaction = MaterialTransaction(
            id=str(uuid.uuid4())[:8].upper(),
            **kwargs
        )
        self._transactions.append(transaction)
        return transaction

    def _create_alert(self,
                     alert_type: str,
                     severity: str,
                     spool_id: Optional[str],
                     message: str) -> MaterialAlert:
        """Create a new alert."""
        alert = MaterialAlert(
            id=str(uuid.uuid4())[:8].upper(),
            alert_type=alert_type,
            severity=severity,
            spool_id=spool_id,
            message=message
        )
        self._alerts.append(alert)
        return alert

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "") -> bool:
        """Acknowledge an alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now().isoformat()
                alert.acknowledged_by = acknowledged_by
                return True
        return False

    def get_alerts(self, include_acknowledged: bool = False) -> List[MaterialAlert]:
        """Get alerts."""
        if include_acknowledged:
            return self._alerts
        return [a for a in self._alerts if not a.acknowledged]

    def get_transactions(self,
                        spool_id: Optional[str] = None,
                        transaction_type: Optional[str] = None,
                        limit: int = 100) -> List[MaterialTransaction]:
        """Get transaction history."""
        transactions = self._transactions

        if spool_id:
            transactions = [t for t in transactions if t.spool_id == spool_id]
        if transaction_type:
            transactions = [t for t in transactions if t.transaction_type == transaction_type]

        return transactions[-limit:]

    def get_material_properties(self, material_type: MaterialType) -> Optional[MaterialProperties]:
        """Get properties for a material type."""
        return MATERIAL_PROPERTIES.get(material_type)


# === Singleton Instance ===

_material_master: Optional[MaterialMasterService] = None


def get_material_master() -> MaterialMasterService:
    """Get singleton MaterialMasterService instance."""
    global _material_master
    if _material_master is None:
        _material_master = MaterialMasterService()
    return _material_master


# === Module Exports ===

__all__ = [
    'MaterialMasterService',
    'get_material_master',
    'MaterialType',
    'MaterialStatus',
    'MaterialGrade',
    'SpoolSize',
    'FilamentSpool',
    'MaterialTransaction',
    'MaterialAlert',
    'MaterialProperties',
    'MATERIAL_PROPERTIES',
]
