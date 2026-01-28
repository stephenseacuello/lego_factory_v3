"""
LEGO Factory v3 - Asset Service
================================
Asset management and meter tracking.
"""

import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import func

from config.database import get_db_session

logger = logging.getLogger(__name__)


class AssetService:
    """Service for managing factory assets."""

    def __init__(self, session: Session):
        self.session = session

    def create_asset(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new asset."""
        from models.cmms.assets import Asset, AssetStatus, AssetCriticality

        asset = Asset(
            asset_id=data.get('asset_id', f"AST-{uuid.uuid4().hex[:8].upper()}"),
            name=data['name'],
            description=data.get('description'),
            asset_class_id=data.get('asset_class_id'),
            status=AssetStatus(data.get('status', 'operational')),
            criticality=AssetCriticality(data.get('criticality', 'standard')),
            location_id=data.get('location_id'),
            location_description=data.get('location_description'),
            work_center_id=data.get('work_center_id'),
            serial_number=data.get('serial_number'),
            model_number=data.get('model_number'),
            manufacturer=data.get('manufacturer'),
            vendor_id=data.get('vendor_id'),
            purchase_date=data.get('purchase_date'),
            installation_date=data.get('installation_date'),
            warranty_expiry=data.get('warranty_expiry'),
            purchase_cost=data.get('purchase_cost'),
            replacement_cost=data.get('replacement_cost'),
            machine_id=data.get('machine_id'),
            parent_asset_id=data.get('parent_asset_id'),
            specifications=data.get('specifications', {}),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(asset)
        self.session.flush()

        logger.info(f"Created asset: {asset.asset_id}")
        return asset.to_dict()

    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Get an asset by ID."""
        from models.cmms.assets import Asset

        asset = self.session.query(Asset).filter(
            Asset.asset_id == asset_id
        ).first()
        return asset.to_dict() if asset else None

    def get_assets(
        self,
        status: str = None,
        criticality: str = None,
        asset_class_id: str = None,
        location_id: str = None,
        machine_id: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get assets with filtering."""
        from models.cmms.assets import Asset, AssetStatus, AssetCriticality

        query = self.session.query(Asset).filter(Asset.is_deleted == False)

        if status:
            query = query.filter(Asset.status == AssetStatus(status))
        if criticality:
            query = query.filter(Asset.criticality == AssetCriticality(criticality))
        if asset_class_id:
            query = query.filter(Asset.asset_class_id == asset_class_id)
        if location_id:
            query = query.filter(Asset.location_id == location_id)
        if machine_id:
            query = query.filter(Asset.machine_id == machine_id)

        assets = query.order_by(Asset.asset_id).offset(offset).limit(limit).all()
        return [a.to_dict() for a in assets]

    def update_asset(self, asset_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an asset."""
        from models.cmms.assets import Asset, AssetStatus, AssetCriticality

        asset = self.session.query(Asset).filter(
            Asset.asset_id == asset_id
        ).first()

        if not asset:
            return None

        for key, value in data.items():
            if hasattr(asset, key) and key not in ('id', 'asset_id', 'created_at'):
                if key == 'status' and isinstance(value, str):
                    value = AssetStatus(value)
                elif key == 'criticality' and isinstance(value, str):
                    value = AssetCriticality(value)
                setattr(asset, key, value)

        asset.updated_at = datetime.utcnow()
        asset.updated_by = data.get('updated_by', 'system')
        self.session.flush()

        logger.info(f"Updated asset: {asset_id}")
        return asset.to_dict()

    def update_status(self, asset_id: str, status: str, user_id: str = 'system') -> Optional[Dict[str, Any]]:
        """Update asset status."""
        from models.cmms.assets import AssetStatus
        return self.update_asset(asset_id, {
            'status': AssetStatus(status),
            'updated_by': user_id
        })

    def create_asset_class(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an asset class."""
        from models.cmms.assets import AssetClass

        asset_class = AssetClass(
            code=data['code'],
            name=data['name'],
            description=data.get('description'),
            parent_class_id=data.get('parent_class_id'),
            default_pm_interval_days=data.get('default_pm_interval_days'),
            default_pm_interval_hours=data.get('default_pm_interval_hours'),
            expected_lifespan_years=data.get('expected_lifespan_years'),
            spec_template=data.get('spec_template', {}),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(asset_class)
        self.session.flush()

        return asset_class.to_dict()

    def get_asset_classes(self) -> List[Dict[str, Any]]:
        """Get all asset classes."""
        from models.cmms.assets import AssetClass

        classes = self.session.query(AssetClass).filter(
            AssetClass.is_deleted == False
        ).order_by(AssetClass.code).all()
        return [c.to_dict() for c in classes]

    def create_meter(self, asset_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a meter for an asset."""
        from models.cmms.assets import Asset, Meter, MeterType

        asset = self.session.query(Asset).filter(Asset.asset_id == asset_id).first()
        if not asset:
            return None

        meter = Meter(
            meter_id=data.get('meter_id', f"MTR-{uuid.uuid4().hex[:8].upper()}"),
            asset_id=asset.id,
            name=data['name'],
            description=data.get('description'),
            meter_type=MeterType(data.get('meter_type', 'continuous')),
            unit_of_measure=data.get('unit_of_measure'),
            warning_threshold=data.get('warning_threshold'),
            critical_threshold=data.get('critical_threshold'),
            rollover_value=data.get('rollover_value'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(meter)
        self.session.flush()

        return meter.to_dict()

    def get_meters(self, asset_id: str) -> List[Dict[str, Any]]:
        """Get all meters for an asset."""
        from models.cmms.assets import Asset, Meter

        asset = self.session.query(Asset).filter(Asset.asset_id == asset_id).first()
        if not asset:
            return []

        meters = self.session.query(Meter).filter(
            Meter.asset_id == asset.id,
            Meter.is_deleted == False
        ).all()
        return [m.to_dict() for m in meters]

    def record_meter_reading(
        self,
        meter_id: str,
        reading_value: float,
        reading_date: datetime = None,
        source: str = 'manual',
        recorded_by: str = None
    ) -> Optional[Dict[str, Any]]:
        """Record a meter reading."""
        from models.cmms.assets import Meter, MeterReading

        meter = self.session.query(Meter).filter(Meter.meter_id == meter_id).first()
        if not meter:
            return None

        reading_date = reading_date or datetime.utcnow()

        # Calculate delta
        delta = None
        if meter.last_reading is not None:
            delta = reading_value - meter.last_reading
            # Handle rollover
            if meter.rollover_value and delta < 0:
                delta = reading_value + (meter.rollover_value - meter.last_reading)

        reading = MeterReading(
            meter_id=meter.id,
            reading_date=reading_date,
            reading_value=reading_value,
            delta=delta,
            source=source,
            recorded_by=recorded_by,
        )

        # Update meter's last reading
        meter.last_reading = reading_value
        meter.last_reading_date = reading_date

        self.session.add(reading)
        self.session.flush()

        # Check thresholds
        if meter.critical_threshold and reading_value >= meter.critical_threshold:
            logger.warning(f"Meter {meter_id} reading {reading_value} exceeds critical threshold {meter.critical_threshold}")
        elif meter.warning_threshold and reading_value >= meter.warning_threshold:
            logger.warning(f"Meter {meter_id} reading {reading_value} exceeds warning threshold {meter.warning_threshold}")

        return reading.to_dict()

    def get_meter_readings(
        self,
        meter_id: str,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get meter readings."""
        from models.cmms.assets import Meter, MeterReading

        meter = self.session.query(Meter).filter(Meter.meter_id == meter_id).first()
        if not meter:
            return []

        query = self.session.query(MeterReading).filter(MeterReading.meter_id == meter.id)

        if start_date:
            query = query.filter(MeterReading.reading_date >= start_date)
        if end_date:
            query = query.filter(MeterReading.reading_date <= end_date)

        readings = query.order_by(MeterReading.reading_date.desc()).limit(limit).all()
        return [r.to_dict() for r in readings]

    def get_asset_hierarchy(self, root_asset_id: str = None) -> List[Dict[str, Any]]:
        """Get asset hierarchy."""
        from models.cmms.assets import Asset

        if root_asset_id:
            root = self.session.query(Asset).filter(Asset.asset_id == root_asset_id).first()
            if not root:
                return []
            assets = [root] + list(root.child_assets)
        else:
            assets = self.session.query(Asset).filter(
                Asset.parent_asset_id == None,
                Asset.is_deleted == False
            ).all()

        def build_tree(asset):
            result = asset.to_dict()
            result['children'] = [build_tree(child) for child in asset.child_assets if not child.is_deleted]
            return result

        return [build_tree(a) for a in assets]

    def get_assets_by_status_summary(self) -> Dict[str, int]:
        """Get asset count by status."""
        from models.cmms.assets import Asset, AssetStatus

        results = self.session.query(
            Asset.status, func.count(Asset.id)
        ).filter(
            Asset.is_deleted == False
        ).group_by(Asset.status).all()

        return {r.status.value if r.status else 'unknown': r[1] for r in results}


def get_asset_service(session: Session = None) -> AssetService:
    """Get asset service instance."""
    if session:
        return AssetService(session)
    with get_db_session() as session:
        return AssetService(session)
