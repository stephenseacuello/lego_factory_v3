"""
Fixed Asset Register & Depreciation Service
=============================================
Comprehensive fixed asset management with database persistence.

Features:
- Database-backed asset register
- Multiple depreciation methods
- Asset disposal/retirement workflows
- Asset impairment handling
- Asset transfer between locations
- Depreciation schedules and journals
- Full audit trail
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from dataclasses import dataclass, field
import uuid

from sqlalchemy.orm import Session

from models.erp.fixed_assets import FixedAsset, DepreciationEntry, AssetDisposal

logger = logging.getLogger(__name__)


class DepreciationMethod(str, Enum):
    """Depreciation calculation methods."""
    STRAIGHT_LINE = 'straight_line'
    DECLINING_BALANCE = 'declining_balance'
    DOUBLE_DECLINING = 'double_declining'
    UNITS_OF_PRODUCTION = 'units_of_production'
    SUM_OF_YEARS = 'sum_of_years'


class AssetStatus(str, Enum):
    """Asset lifecycle status."""
    ACTIVE = 'active'
    DISPOSED = 'disposed'
    RETIRED = 'retired'
    TRANSFERRED = 'transferred'
    IMPAIRED = 'impaired'
    FULLY_DEPRECIATED = 'fully_depreciated'


class AssetCategory(str, Enum):
    """Fixed asset categories."""
    MACHINERY = 'machinery'
    EQUIPMENT = 'equipment'
    VEHICLES = 'vehicles'
    FURNITURE = 'furniture'
    COMPUTERS = 'computers'
    BUILDINGS = 'buildings'
    LAND = 'land'
    LEASEHOLD = 'leasehold_improvements'
    TOOLS = 'tools'
    OTHER = 'other'


class DepreciationService:
    """
    Comprehensive fixed asset and depreciation management service.

    Provides:
    - Asset registration and tracking
    - Multiple depreciation methods
    - Depreciation schedule generation
    - Asset disposal/retirement
    - Impairment handling
    - Location transfers
    - Journal entry generation
    """

    def __init__(self, session: Session = None):
        self.session = session

    # =========================================================================
    # Asset Registration
    # =========================================================================

    def register_asset(
        self,
        name: str,
        acquisition_cost: float,
        acquisition_date: str,
        useful_life_months: int = 60,
        salvage_value: float = 0,
        method: str = 'straight_line',
        category: str = 'equipment',
        asset_id: str = None,
        description: str = None,
        location_id: str = None,
        department_id: str = None,
        serial_number: str = None,
        vendor_id: str = None,
        warranty_expiry: str = None,
        total_units_capacity: int = None
    ) -> Dict[str, Any]:
        """
        Register a new fixed asset.

        Args:
            name: Asset name
            acquisition_cost: Original cost
            acquisition_date: Date acquired (YYYY-MM-DD)
            useful_life_months: Expected useful life
            salvage_value: Expected residual value
            method: Depreciation method
            category: Asset category
            asset_id: Optional custom ID
            description: Asset description
            location_id: Physical location
            department_id: Owning department
            serial_number: Serial/asset tag number
            vendor_id: Supplier/vendor ID
            warranty_expiry: Warranty end date
            total_units_capacity: For units-of-production method

        Returns:
            Created asset record
        """
        asset_id = asset_id or f"FA-{uuid.uuid4().hex[:8].upper()}"

        # Parse dates
        acq_date = date.fromisoformat(acquisition_date) if isinstance(acquisition_date, str) else acquisition_date
        warranty_date = date.fromisoformat(warranty_expiry) if warranty_expiry else None

        cost = float(acquisition_cost)
        sv = float(salvage_value)

        record = FixedAsset(
            asset_id=asset_id,
            name=name,
            description=description or name,
            category=category,
            acquisition_cost=cost,
            acquisition_date=acq_date,
            useful_life_months=useful_life_months,
            salvage_value=sv,
            depreciation_method=method,
            accumulated_depreciation=0.0,
            impairment_loss=0.0,
            net_book_value=cost - sv,
            status=AssetStatus.ACTIVE.value,
            location_id=location_id,
            department=department_id,
            serial_number=serial_number,
            vendor_id=vendor_id,
            warranty_expiry=warranty_date,
            total_units_capacity=total_units_capacity,
            units_produced=0,
        )

        self.session.add(record)
        self.session.flush()

        logger.info(f"Registered fixed asset: {asset_id} - {name}")

        return self._asset_to_dict(record)

    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Get asset by ID."""
        record = self._load_asset(asset_id)
        return self._asset_to_dict(record) if record else None

    def _load_asset(self, asset_id: str) -> Optional[FixedAsset]:
        """Load asset from database by business ID."""
        return self.session.query(FixedAsset).filter(
            FixedAsset.asset_id == asset_id
        ).first()

    # =========================================================================
    # Depreciation Calculations
    # =========================================================================

    def calculate_monthly_depreciation(
        self,
        asset_id: str,
        as_of_date: date = None
    ) -> Dict[str, Any]:
        """
        Calculate monthly depreciation for an asset.

        Args:
            asset_id: Asset ID
            as_of_date: Calculation date (default: today)

        Returns:
            Depreciation calculation result
        """
        asset = self._load_asset(asset_id)
        if not asset:
            return {'error': 'Asset not found', 'asset_id': asset_id}

        if asset.status in (AssetStatus.DISPOSED.value, AssetStatus.RETIRED.value):
            return {'error': 'Asset is disposed/retired', 'asset_id': asset_id}

        as_of_date = as_of_date or date.today()

        acq_cost = Decimal(str(asset.acquisition_cost))
        accum_dep = Decimal(str(asset.accumulated_depreciation or 0))
        impairment = Decimal(str(asset.impairment_loss or 0))
        salv_value = Decimal(str(asset.salvage_value or 0))

        # Calculate based on method
        if asset.depreciation_method == DepreciationMethod.STRAIGHT_LINE.value:
            depreciation = self._calc_straight_line(asset)
        elif asset.depreciation_method == DepreciationMethod.DECLINING_BALANCE.value:
            depreciation = self._calc_declining_balance(asset, rate=1.5)
        elif asset.depreciation_method == DepreciationMethod.DOUBLE_DECLINING.value:
            depreciation = self._calc_declining_balance(asset, rate=2.0)
        elif asset.depreciation_method == DepreciationMethod.SUM_OF_YEARS.value:
            depreciation = self._calc_sum_of_years(asset, as_of_date)
        elif asset.depreciation_method == DepreciationMethod.UNITS_OF_PRODUCTION.value:
            depreciation = self._calc_units_of_production(asset)
        else:
            depreciation = self._calc_straight_line(asset)

        net_book_value = acq_cost - accum_dep - impairment

        # Don't depreciate below salvage value
        max_depreciation = net_book_value - salv_value
        depreciation = min(depreciation, max(max_depreciation, Decimal('0')))

        return {
            'asset_id': asset_id,
            'asset_name': asset.name,
            'monthly_depreciation': float(depreciation.quantize(Decimal('0.01'))),
            'method': asset.depreciation_method,
            'acquisition_cost': float(acq_cost),
            'accumulated_depreciation': float(accum_dep),
            'impairment_loss': float(impairment),
            'net_book_value': float(net_book_value.quantize(Decimal('0.01'))),
            'salvage_value': float(salv_value),
            'remaining_life_months': self._get_remaining_life(asset, as_of_date),
            'is_fully_depreciated': net_book_value <= salv_value
        }

    def _calc_straight_line(self, asset: FixedAsset) -> Decimal:
        """Straight-line depreciation."""
        depreciable_amount = Decimal(str(asset.acquisition_cost)) - Decimal(str(asset.salvage_value or 0))
        months = max(asset.useful_life_months, 1)
        return depreciable_amount / months

    def _calc_declining_balance(self, asset: FixedAsset, rate: float = 1.5) -> Decimal:
        """Declining balance depreciation."""
        if asset.useful_life_months <= 0:
            return Decimal('0')

        annual_rate = Decimal(str(rate)) / Decimal(str(asset.useful_life_months / 12))
        monthly_rate = annual_rate / 12

        acq_cost = Decimal(str(asset.acquisition_cost))
        accum_dep = Decimal(str(asset.accumulated_depreciation or 0))
        impairment = Decimal(str(asset.impairment_loss or 0))
        salv_value = Decimal(str(asset.salvage_value or 0))

        nbv = acq_cost - accum_dep - impairment
        depreciation = nbv * monthly_rate

        # Cap at amount that would leave salvage value
        max_dep = nbv - salv_value
        return min(depreciation, max(max_dep, Decimal('0')))

    def _calc_sum_of_years(self, asset: FixedAsset, as_of_date: date) -> Decimal:
        """Sum-of-years-digits depreciation."""
        depreciable_amount = Decimal(str(asset.acquisition_cost)) - Decimal(str(asset.salvage_value or 0))
        years = asset.useful_life_months // 12
        sum_of_years = years * (years + 1) / 2

        # Calculate which year we're in
        months_since_acquisition = self._months_between(asset.acquisition_date, as_of_date)
        current_year = (months_since_acquisition // 12) + 1

        if current_year > years:
            return Decimal('0')

        remaining_years = years - current_year + 1
        annual_depreciation = depreciable_amount * Decimal(str(remaining_years)) / Decimal(str(sum_of_years))

        return annual_depreciation / 12

    def _calc_units_of_production(self, asset: FixedAsset) -> Decimal:
        """Units-of-production depreciation (requires units update)."""
        if not asset.total_units_capacity or asset.total_units_capacity <= 0:
            return self._calc_straight_line(asset)

        depreciable_amount = Decimal(str(asset.acquisition_cost)) - Decimal(str(asset.salvage_value or 0))
        rate_per_unit = depreciable_amount / asset.total_units_capacity

        # Default to average monthly units if not tracked
        monthly_units = asset.total_units_capacity / max(asset.useful_life_months, 1)
        return rate_per_unit * Decimal(str(monthly_units))

    def _get_remaining_life(self, asset: FixedAsset, as_of_date: date) -> int:
        """Get remaining useful life in months."""
        months_elapsed = self._months_between(asset.acquisition_date, as_of_date)
        return max(0, asset.useful_life_months - months_elapsed)

    def _months_between(self, start: date, end: date) -> int:
        """Calculate months between two dates."""
        return (end.year - start.year) * 12 + (end.month - start.month)

    # =========================================================================
    # Depreciation Run
    # =========================================================================

    def run_depreciation(
        self,
        period_end: date = None,
        asset_ids: List[str] = None
    ) -> Dict[str, Any]:
        """
        Run monthly depreciation for all or selected assets.

        Args:
            period_end: Period end date (default: today)
            asset_ids: Optional list of specific assets to process

        Returns:
            Depreciation run results
        """
        period_end = period_end or date.today()
        period_start = period_end.replace(day=1)

        assets = self._get_active_assets(asset_ids)
        entries = []
        total_depreciation = Decimal('0')

        for asset in assets:
            result = self.calculate_monthly_depreciation(asset.asset_id, period_end)

            if 'error' in result:
                continue

            depreciation = Decimal(str(result['monthly_depreciation']))
            if depreciation <= 0:
                continue

            # Update asset
            new_accum = float(Decimal(str(asset.accumulated_depreciation or 0)) + depreciation)
            asset.accumulated_depreciation = new_accum
            asset.last_depreciation_date = period_end
            asset.updated_at = datetime.utcnow()

            # Check if fully depreciated
            nbv = Decimal(str(asset.acquisition_cost)) - Decimal(str(new_accum)) - Decimal(str(asset.impairment_loss or 0))
            if nbv <= Decimal(str(asset.salvage_value or 0)):
                asset.status = AssetStatus.FULLY_DEPRECIATED.value

            asset.net_book_value = float(nbv)

            # Create entry
            entry_id = f"DEP-{uuid.uuid4().hex[:8].upper()}"
            dep_entry = DepreciationEntry(
                entry_id=entry_id,
                asset_id=asset.id,
                period_start=period_start,
                period_end=period_end,
                depreciation_amount=float(depreciation),
                accumulated_total=new_accum,
                net_book_value=float(nbv),
                method=asset.depreciation_method,
            )
            self.session.add(dep_entry)
            self.session.flush()

            entries.append({
                'asset_id': asset.asset_id,
                'asset_name': asset.name,
                'depreciation': float(depreciation),
                'accumulated': new_accum,
                'net_book_value': float(nbv),
                'status': asset.status
            })

            total_depreciation += depreciation

        self.session.flush()

        logger.info(
            f"Depreciation run complete: {len(entries)} assets, "
            f"total ${total_depreciation:,.2f}"
        )

        return {
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'assets_processed': len(entries),
            'total_depreciation': float(total_depreciation),
            'entries': entries,
            'journal_entry': self._create_journal_entry(entries, period_end)
        }

    def _get_active_assets(self, asset_ids: List[str] = None) -> List[FixedAsset]:
        """Get active assets from database."""
        query = self.session.query(FixedAsset).filter(
            FixedAsset.status.in_([
                AssetStatus.ACTIVE.value,
                AssetStatus.IMPAIRED.value
            ])
        )
        if asset_ids:
            query = query.filter(FixedAsset.asset_id.in_(asset_ids))

        return query.all()

    def _create_journal_entry(
        self,
        entries: List[Dict[str, Any]],
        period_end: date
    ) -> Dict[str, Any]:
        """Create depreciation journal entry."""
        total = sum(e['depreciation'] for e in entries)

        return {
            'entry_date': period_end.isoformat(),
            'description': f'Depreciation expense - {period_end.strftime("%B %Y")}',
            'debits': [{
                'account': '6100',  # Depreciation Expense
                'amount': round(total, 2)
            }],
            'credits': [{
                'account': '1599',  # Accumulated Depreciation
                'amount': round(total, 2)
            }]
        }

    # =========================================================================
    # Asset Disposal
    # =========================================================================

    def dispose_asset(
        self,
        asset_id: str,
        disposal_date: str,
        disposal_type: str = 'sale',
        proceeds: float = 0,
        buyer_info: str = None,
        reason: str = None
    ) -> Dict[str, Any]:
        """
        Dispose of an asset (sale, scrap, etc.).

        Args:
            asset_id: Asset to dispose
            disposal_date: Date of disposal
            disposal_type: Type ('sale', 'scrapped', 'trade_in', 'donation')
            proceeds: Sale proceeds
            buyer_info: Buyer information
            reason: Reason for disposal

        Returns:
            Disposal result with gain/loss
        """
        asset = self._load_asset(asset_id)
        if not asset:
            return {'error': 'Asset not found', 'asset_id': asset_id}

        if asset.status in (AssetStatus.DISPOSED.value, AssetStatus.RETIRED.value):
            return {'error': 'Asset already disposed/retired', 'asset_id': asset_id}

        disp_date = date.fromisoformat(disposal_date) if isinstance(disposal_date, str) else disposal_date
        proceeds_dec = Decimal(str(proceeds))

        # Calculate gain/loss
        acq_cost = Decimal(str(asset.acquisition_cost))
        accum_dep = Decimal(str(asset.accumulated_depreciation or 0))
        impairment = Decimal(str(asset.impairment_loss or 0))
        nbv = acq_cost - accum_dep - impairment
        gain_loss = proceeds_dec - nbv

        # Create disposal record
        disposal_id = f"DISP-{uuid.uuid4().hex[:8].upper()}"
        disposal = AssetDisposal(
            disposal_id=disposal_id,
            asset_id=asset.id,
            disposal_date=disp_date,
            disposal_method=disposal_type,
            sale_price=float(proceeds_dec),
            net_book_value_at_disposal=float(nbv),
            gain_loss=float(gain_loss),
            buyer_info=buyer_info,
            reason=reason,
        )
        self.session.add(disposal)

        # Update asset status
        asset.status = AssetStatus.DISPOSED.value
        asset.net_book_value = 0.0
        asset.updated_at = datetime.utcnow()

        self.session.flush()

        logger.info(f"Disposed asset {asset_id}: {disposal_type}, gain/loss ${gain_loss:,.2f}")

        return {
            'disposal_id': disposal_id,
            'asset_id': asset_id,
            'asset_name': asset.name,
            'disposal_date': disp_date.isoformat(),
            'disposal_type': disposal_type,
            'acquisition_cost': float(acq_cost),
            'accumulated_depreciation': float(accum_dep),
            'impairment_loss': float(impairment),
            'net_book_value': float(nbv),
            'proceeds': float(proceeds_dec),
            'gain_loss': float(gain_loss),
            'is_gain': gain_loss > 0,
            'journal_entry': self._create_disposal_journal(asset, disposal, acq_cost, accum_dep)
        }

    def _create_disposal_journal(
        self,
        asset: FixedAsset,
        disposal: AssetDisposal,
        acquisition_cost: Decimal,
        accumulated_depreciation: Decimal
    ) -> Dict[str, Any]:
        """Create disposal journal entry."""
        debits = []
        credits = []

        proceeds = Decimal(str(disposal.sale_price or 0))
        gain_loss = Decimal(str(disposal.gain_loss or 0))

        # Debit cash/receivable for proceeds
        if proceeds > 0:
            debits.append({
                'account': '1100',  # Cash
                'amount': float(proceeds)
            })

        # Debit accumulated depreciation
        debits.append({
            'account': '1599',  # Accumulated Depreciation
            'amount': float(accumulated_depreciation)
        })

        # Debit loss or credit gain
        if gain_loss < 0:
            debits.append({
                'account': '7500',  # Loss on Disposal
                'amount': float(abs(gain_loss))
            })
        elif gain_loss > 0:
            credits.append({
                'account': '7400',  # Gain on Disposal
                'amount': float(gain_loss)
            })

        # Credit fixed asset
        credits.append({
            'account': '1500',  # Fixed Assets
            'amount': float(acquisition_cost)
        })

        return {
            'entry_date': disposal.disposal_date.isoformat(),
            'description': f'Disposal of asset: {asset.name}',
            'debits': debits,
            'credits': credits
        }

    # =========================================================================
    # Asset Impairment
    # =========================================================================

    def record_impairment(
        self,
        asset_id: str,
        impairment_amount: float,
        impairment_date: str = None,
        reason: str = None
    ) -> Dict[str, Any]:
        """
        Record asset impairment loss.

        Args:
            asset_id: Asset ID
            impairment_amount: Impairment loss amount
            impairment_date: Date of impairment
            reason: Reason for impairment

        Returns:
            Impairment result
        """
        asset = self._load_asset(asset_id)
        if not asset:
            return {'error': 'Asset not found', 'asset_id': asset_id}

        imp_date = date.fromisoformat(impairment_date) if impairment_date else date.today()
        imp_amount = Decimal(str(impairment_amount))

        # Calculate current NBV
        acq_cost = Decimal(str(asset.acquisition_cost))
        accum_dep = Decimal(str(asset.accumulated_depreciation or 0))
        impairment = Decimal(str(asset.impairment_loss or 0))
        nbv_before = acq_cost - accum_dep - impairment

        # Validate impairment doesn't exceed NBV
        if imp_amount > nbv_before:
            return {
                'error': f'Impairment {imp_amount} exceeds NBV {nbv_before}',
                'asset_id': asset_id
            }

        # Update asset
        new_impairment = float(impairment + imp_amount)
        asset.impairment_loss = new_impairment
        asset.status = AssetStatus.IMPAIRED.value
        asset.updated_at = datetime.utcnow()

        nbv_after = acq_cost - accum_dep - Decimal(str(new_impairment))
        asset.net_book_value = float(nbv_after)

        self.session.flush()

        logger.info(f"Recorded impairment for {asset_id}: ${imp_amount:,.2f}")

        return {
            'asset_id': asset_id,
            'asset_name': asset.name,
            'impairment_date': imp_date.isoformat(),
            'impairment_amount': float(imp_amount),
            'total_impairment': new_impairment,
            'nbv_before': float(nbv_before),
            'nbv_after': float(nbv_after),
            'reason': reason,
            'journal_entry': {
                'entry_date': imp_date.isoformat(),
                'description': f'Impairment loss: {asset.name}',
                'debits': [{'account': '7600', 'amount': float(imp_amount)}],
                'credits': [{'account': '1590', 'amount': float(imp_amount)}]
            }
        }

    # =========================================================================
    # Asset Transfer
    # =========================================================================

    def transfer_asset(
        self,
        asset_id: str,
        new_location_id: str = None,
        new_department_id: str = None,
        transfer_date: str = None,
        reason: str = None
    ) -> Dict[str, Any]:
        """
        Transfer asset to new location or department.

        Args:
            asset_id: Asset ID
            new_location_id: New location
            new_department_id: New department
            transfer_date: Date of transfer
            reason: Reason for transfer

        Returns:
            Transfer result
        """
        asset = self._load_asset(asset_id)
        if not asset:
            return {'error': 'Asset not found', 'asset_id': asset_id}

        trans_date = date.fromisoformat(transfer_date) if transfer_date else date.today()

        old_location = asset.location_id
        old_department = asset.department

        if new_location_id:
            asset.location_id = new_location_id
        if new_department_id:
            asset.department = new_department_id

        asset.updated_at = datetime.utcnow()

        self.session.flush()

        logger.info(f"Transferred asset {asset_id} to {new_location_id or new_department_id}")

        return {
            'asset_id': asset_id,
            'asset_name': asset.name,
            'transfer_date': trans_date.isoformat(),
            'old_location': old_location,
            'new_location': asset.location_id,
            'old_department': old_department,
            'new_department': asset.department,
            'reason': reason
        }

    # =========================================================================
    # Reporting
    # =========================================================================

    def get_asset_register(
        self,
        category: str = None,
        location_id: str = None,
        status: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get fixed asset register with filters.

        Args:
            category: Filter by category
            location_id: Filter by location
            status: Filter by status

        Returns:
            List of asset records
        """
        query = self.session.query(FixedAsset)

        if category:
            query = query.filter(FixedAsset.category == category)
        if location_id:
            query = query.filter(FixedAsset.location_id == location_id)
        if status:
            query = query.filter(FixedAsset.status == status)

        return [self._asset_to_dict(record) for record in query.all()]

    def get_depreciation_schedule(
        self,
        asset_id: str,
        periods: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Generate depreciation schedule for an asset.

        Args:
            asset_id: Asset ID
            periods: Number of months to project

        Returns:
            List of projected depreciation entries
        """
        asset = self._load_asset(asset_id)
        if not asset:
            return []

        schedule = []
        current_date = date.today()
        accumulated = Decimal(str(asset.accumulated_depreciation or 0))
        acq_cost = Decimal(str(asset.acquisition_cost))
        impairment = Decimal(str(asset.impairment_loss or 0))
        salv_value = Decimal(str(asset.salvage_value or 0))
        nbv = acq_cost - accumulated - impairment

        for i in range(periods):
            period_date = date(
                current_date.year + (current_date.month + i - 1) // 12,
                (current_date.month + i - 1) % 12 + 1,
                1
            )

            if nbv <= salv_value:
                break

            result = self.calculate_monthly_depreciation(asset_id, period_date)
            if 'error' in result:
                break

            depreciation = Decimal(str(result['monthly_depreciation']))
            accumulated += depreciation
            nbv = acq_cost - accumulated - impairment

            schedule.append({
                'period': period_date.isoformat(),
                'depreciation': float(depreciation),
                'accumulated': float(accumulated),
                'net_book_value': float(nbv)
            })

        return schedule

    def get_summary_by_category(self) -> List[Dict[str, Any]]:
        """Get asset summary grouped by category."""
        summary = {}

        assets = self.session.query(FixedAsset).all()

        for asset in assets:
            cat = asset.category
            if cat not in summary:
                summary[cat] = {
                    'category': cat,
                    'count': 0,
                    'total_cost': Decimal('0'),
                    'total_depreciation': Decimal('0'),
                    'total_nbv': Decimal('0')
                }

            summary[cat]['count'] += 1
            summary[cat]['total_cost'] += Decimal(str(asset.acquisition_cost or 0))
            summary[cat]['total_depreciation'] += Decimal(str(asset.accumulated_depreciation or 0))
            nbv = (
                Decimal(str(asset.acquisition_cost or 0))
                - Decimal(str(asset.accumulated_depreciation or 0))
                - Decimal(str(asset.impairment_loss or 0))
            )
            summary[cat]['total_nbv'] += nbv

        return [
            {
                'category': v['category'],
                'count': v['count'],
                'total_cost': float(v['total_cost']),
                'total_depreciation': float(v['total_depreciation']),
                'total_nbv': float(v['total_nbv'])
            }
            for v in summary.values()
        ]

    def _asset_to_dict(self, asset: FixedAsset) -> Dict[str, Any]:
        """Convert asset DB record to dictionary."""
        acq_cost = Decimal(str(asset.acquisition_cost or 0))
        accum_dep = Decimal(str(asset.accumulated_depreciation or 0))
        impairment = Decimal(str(asset.impairment_loss or 0))
        nbv = acq_cost - accum_dep - impairment

        return {
            'asset_id': asset.asset_id,
            'name': asset.name,
            'description': asset.description,
            'category': asset.category,
            'acquisition_cost': float(acq_cost),
            'acquisition_date': asset.acquisition_date.isoformat() if asset.acquisition_date else None,
            'useful_life_months': asset.useful_life_months,
            'salvage_value': float(Decimal(str(asset.salvage_value or 0))),
            'depreciation_method': asset.depreciation_method,
            'location_id': asset.location_id,
            'department_id': asset.department,
            'status': asset.status,
            'accumulated_depreciation': float(accum_dep),
            'impairment_loss': float(impairment),
            'net_book_value': float(nbv),
            'depreciation_pct': float(accum_dep / acq_cost * 100) if acq_cost else 0,
            'serial_number': asset.serial_number,
            'vendor_id': asset.vendor_id,
            'warranty_expiry': asset.warranty_expiry.isoformat() if asset.warranty_expiry else None,
            'last_depreciation_date': asset.last_depreciation_date.isoformat() if asset.last_depreciation_date else None,
            'created_at': asset.created_at.isoformat() if asset.created_at else None
        }
