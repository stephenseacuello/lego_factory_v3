"""
Supplier Quality Scoring & Incoming Inspection Service
=======================================================
Calculates supplier quality scores and manages incoming inspections.

Uses database models (InspectionRecord, SupplierQualityRating, Partner)
instead of in-memory data structures.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List

import logging

logger = logging.getLogger(__name__)


class SupplierQualityService:
    def __init__(self, session):
        self.session = session

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_partner(self, supplier_id: str):
        """Look up a Partner by partner_id string. Returns the ORM object or None."""
        from models.erp.partners import Partner, PartnerType

        try:
            partner = (
                self.session.query(Partner)
                .filter(
                    Partner.partner_id == supplier_id,
                    Partner.partner_type.in_([PartnerType.VENDOR, PartnerType.BOTH]),
                    Partner.is_deleted == False,
                )
                .first()
            )
            return partner
        except Exception:
            logger.debug("Could not resolve partner for supplier_id=%s", supplier_id)
            return None

    @staticmethod
    def _grade_to_status(grade) -> str:
        """Map a SupplierGrade enum value to a human-readable status string."""
        from models.qms.supplier_quality import SupplierGrade

        mapping = {
            SupplierGrade.A_PREFERRED: 'preferred',
            SupplierGrade.B_APPROVED: 'approved',
            SupplierGrade.C_CONDITIONAL: 'conditional',
            SupplierGrade.D_PROBATION: 'at_risk',
            SupplierGrade.DISQUALIFIED: 'disqualified',
        }
        return mapping.get(grade, 'unknown')

    @staticmethod
    def _score_to_status(score: float) -> str:
        """Derive a status label from a numeric composite score."""
        if score >= 90:
            return 'preferred'
        if score >= 70:
            return 'approved'
        if score >= 50:
            return 'at_risk'
        return 'disqualified'

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_supplier_score(self, supplier_id: str, period_days: int = 90) -> Dict[str, Any]:
        """Calculate weighted composite supplier quality score.

        Strategy:
        1. If a ``SupplierQualityRating`` row exists for this vendor,
           return its persisted metrics directly.
        2. Otherwise, fall back to computing an ad-hoc score from
           ``InspectionRecord`` rows associated with the vendor.
        3. If neither data source has data, return a default score of 75.
        """
        from models.qms.supplier_quality import (
            InspectionRecord, InspectionResult, SupplierQualityRating,
        )

        default = {
            'supplier_id': supplier_id, 'score': 75, 'status': 'no_data',
            'components': {}, 'note': 'Default score - no inspection data',
        }

        try:
            partner = self._resolve_partner(supplier_id)
            if partner is None:
                return default

            # --- Path 1: use SupplierQualityRating if available -----------
            rating = (
                self.session.query(SupplierQualityRating)
                .filter(
                    SupplierQualityRating.vendor_id == partner.id,
                    SupplierQualityRating.is_deleted == False,
                )
                .order_by(SupplierQualityRating.period_end.desc())
                .first()
            )

            if rating is not None and rating.overall_score is not None:
                status = (
                    self._grade_to_status(rating.grade)
                    if rating.grade
                    else self._score_to_status(rating.overall_score)
                )
                quality_acceptance = rating.quality_score if rating.quality_score is not None else 0
                delivery_on_time = (
                    rating.on_time_delivery_percent
                    if rating.on_time_delivery_percent is not None
                    else (rating.delivery_score if rating.delivery_score is not None else 0)
                )
                total_lots = rating.total_lots_received or 0

                return {
                    'supplier_id': supplier_id,
                    'score': round(rating.overall_score, 1),
                    'status': status,
                    'components': {
                        'quality_acceptance': round(quality_acceptance, 1),
                        'delivery_on_time': round(delivery_on_time, 1),
                        'responsiveness': 80,  # not tracked in rating table
                        'price_competitiveness': 80,  # not tracked in rating table
                    },
                    'inspection_count': total_lots,
                    'period_days': period_days,
                    'rating_period': rating.rating_period,
                }

            # --- Path 2: compute from InspectionRecord rows ---------------
            cutoff = datetime.utcnow() - timedelta(days=period_days)

            inspections = (
                self.session.query(InspectionRecord)
                .filter(
                    InspectionRecord.vendor_id == partner.id,
                    InspectionRecord.inspection_date >= cutoff,
                    InspectionRecord.is_deleted == False,
                )
                .all()
            )

            if not inspections:
                return default

            total = len(inspections)

            # Quality acceptance rate (35% weight)
            accepted = sum(
                1 for i in inspections
                if i.disposition in (InspectionResult.ACCEPT, InspectionResult.USE_AS_IS)
            )
            quality_rate = accepted / total * 100

            # Delivery on-time (25% weight) -- not directly on the record;
            # approximate as 80 (neutral) when unavailable.
            delivery_rate = 80.0

            # Responsiveness (20% weight) -- placeholder
            responsiveness = 80.0

            # Price competitiveness (20% weight) -- placeholder
            price_score = 80.0

            composite = round(
                quality_rate * 0.35 +
                delivery_rate * 0.25 +
                responsiveness * 0.20 +
                price_score * 0.20, 1
            )

            status = self._score_to_status(composite)

            return {
                'supplier_id': supplier_id,
                'score': composite,
                'status': status,
                'components': {
                    'quality_acceptance': round(quality_rate, 1),
                    'delivery_on_time': round(delivery_rate, 1),
                    'responsiveness': round(responsiveness, 1),
                    'price_competitiveness': price_score,
                },
                'inspection_count': total,
                'period_days': period_days,
            }

        except Exception:
            logger.exception(
                "Error calculating supplier score for %s", supplier_id
            )
            return default

    def record_inspection(self, supplier_id: str, part_id: str, result: str,
                          on_time: bool = True, notes: str = None) -> Dict[str, Any]:
        """Record an incoming inspection result.

        Individual inspection records are created through the full QMS
        inspection workflow (``InspectionRecord`` linked to plans and
        work orders).  This lightweight convenience method is kept for
        backward compatibility but does **not** duplicate that work.
        """
        return {
            'status': 'recorded',
            'entry': {
                'supplier_id': supplier_id,
                'part_id': part_id,
                'result': result,
                'on_time': on_time,
                'notes': notes,
                'timestamp': datetime.utcnow().isoformat(),
            },
        }

    def get_supplier_rankings(self) -> List[Dict[str, Any]]:
        """Rank all suppliers by quality score.

        Prefers ``SupplierQualityRating`` rows. If no ratings exist at
        all, falls back to computing scores for every vendor-type
        partner.
        """
        from models.qms.supplier_quality import SupplierQualityRating
        from models.erp.partners import Partner, PartnerType
        from sqlalchemy import func

        try:
            # Attempt to build rankings from the ratings table, picking
            # the most recent rating per vendor.
            subq = (
                self.session.query(
                    SupplierQualityRating.vendor_id,
                    func.max(SupplierQualityRating.period_end).label('max_period_end'),
                )
                .filter(SupplierQualityRating.is_deleted == False)
                .group_by(SupplierQualityRating.vendor_id)
                .subquery()
            )

            ratings = (
                self.session.query(SupplierQualityRating, Partner)
                .join(subq, (
                    (SupplierQualityRating.vendor_id == subq.c.vendor_id) &
                    (SupplierQualityRating.period_end == subq.c.max_period_end)
                ))
                .join(Partner, Partner.id == SupplierQualityRating.vendor_id)
                .filter(
                    SupplierQualityRating.is_deleted == False,
                    Partner.is_deleted == False,
                )
                .all()
            )

            if ratings:
                rankings = []
                for rating, partner in ratings:
                    score = rating.overall_score if rating.overall_score is not None else 75
                    status = (
                        self._grade_to_status(rating.grade)
                        if rating.grade
                        else self._score_to_status(score)
                    )
                    rankings.append({
                        'supplier_id': partner.partner_id,
                        'supplier_name': partner.name,
                        'score': round(score, 1),
                        'status': status,
                        'components': {
                            'quality_acceptance': round(rating.quality_score or 0, 1),
                            'delivery_on_time': round(
                                rating.on_time_delivery_percent
                                if rating.on_time_delivery_percent is not None
                                else (rating.delivery_score or 0),
                                1,
                            ),
                            'responsiveness': 80,
                            'price_competitiveness': 80,
                        },
                        'inspection_count': rating.total_lots_received or 0,
                        'rating_period': rating.rating_period,
                    })
                return sorted(rankings, key=lambda x: x['score'], reverse=True)

            # Fallback: compute per-vendor scores from inspection records
            vendors = (
                self.session.query(Partner)
                .filter(
                    Partner.partner_type.in_([PartnerType.VENDOR, PartnerType.BOTH]),
                    Partner.is_deleted == False,
                )
                .all()
            )

            rankings = []
            for vendor in vendors:
                score_data = self.calculate_supplier_score(vendor.partner_id)
                score_data['supplier_name'] = vendor.name
                rankings.append(score_data)

            return sorted(rankings, key=lambda x: x['score'], reverse=True)

        except Exception:
            logger.exception("Error retrieving supplier rankings")
            return []

    def flag_at_risk_suppliers(self, threshold: float = 70) -> List[Dict[str, Any]]:
        """Flag suppliers with scores below *threshold*."""
        try:
            rankings = self.get_supplier_rankings()
            return [s for s in rankings if s['score'] < threshold]
        except Exception:
            logger.exception("Error flagging at-risk suppliers")
            return []
