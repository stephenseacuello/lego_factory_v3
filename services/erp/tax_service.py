"""
ERP Tax Management Service
==========================
Tax calculation engine supporting multiple tax types, jurisdictions, and rates.

Features:
- Tax jurisdiction definitions (countries, states, cities)
- Tax rate tables by item/customer/location
- Automatic tax calculation on invoices
- Support for sales tax, VAT, withholding tax
- Tax exemption handling
- Tax reporting by jurisdiction
"""

import logging
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, field

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from config.database import get_db_session
from models.erp.tax import TaxJurisdiction, TaxRate, TaxExemption

logger = logging.getLogger(__name__)


class TaxType(str, Enum):
    """Types of taxes supported."""
    SALES_TAX = 'sales_tax'
    VAT = 'vat'
    GST = 'gst'
    WITHHOLDING = 'withholding'
    EXCISE = 'excise'
    IMPORT_DUTY = 'import_duty'


class TaxCategory(str, Enum):
    """Tax categories for items."""
    STANDARD = 'standard'
    REDUCED = 'reduced'
    ZERO_RATED = 'zero_rated'
    EXEMPT = 'exempt'
    REVERSE_CHARGE = 'reverse_charge'


@dataclass
class TaxLineResult:
    """Result of tax calculation for a line item."""
    jurisdiction_code: str
    tax_type: TaxType
    tax_category: TaxCategory
    taxable_amount: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    description: str


@dataclass
class TaxCalculationResult:
    """Complete tax calculation result."""
    subtotal: Decimal
    total_tax: Decimal
    total_with_tax: Decimal
    tax_lines: List[TaxLineResult]
    exemptions_applied: List[str]


class TaxService:
    """
    Tax calculation and management service.

    Handles:
    - Jurisdiction and rate management
    - Automatic tax calculation
    - Exemption processing
    - Multi-jurisdiction scenarios (nexus)
    """

    def __init__(self, session: Session = None):
        self.session = session
        self._ensure_defaults()

    # ------------------------------------------------------------------
    # Default data seeding
    # ------------------------------------------------------------------

    def _ensure_defaults(self):
        """Populate default jurisdictions, rates, and exemptions if the DB is empty."""
        if self.session is None:
            return

        existing = self.session.query(TaxJurisdiction).first()
        if existing is not None:
            return

        today = date.today()

        # --- Jurisdictions ---------------------------------------------------
        jurisdictions = [
            TaxJurisdiction(
                code='US',
                name='United States',
                country='US',
                tax_types=[TaxType.EXCISE.value, TaxType.IMPORT_DUTY.value],
            ),
            TaxJurisdiction(
                code='US-CA',
                name='California',
                country='US',
                state='CA',
                tax_types=[TaxType.SALES_TAX.value],
            ),
            TaxJurisdiction(
                code='US-TX',
                name='Texas',
                country='US',
                state='TX',
                tax_types=[TaxType.SALES_TAX.value],
            ),
            TaxJurisdiction(
                code='US-NY',
                name='New York',
                country='US',
                state='NY',
                tax_types=[TaxType.SALES_TAX.value],
            ),
            TaxJurisdiction(
                code='DE',
                name='Germany',
                country='DE',
                tax_types=[TaxType.VAT.value],
            ),
        ]
        for j in jurisdictions:
            self.session.add(j)

        # --- Rates -----------------------------------------------------------
        rates = [
            TaxRate(
                jurisdiction_code='US-CA',
                tax_type=TaxType.SALES_TAX.value,
                rate=7.25,
                effective_date=today,
                category=TaxCategory.STANDARD.value,
            ),
            TaxRate(
                jurisdiction_code='US-TX',
                tax_type=TaxType.SALES_TAX.value,
                rate=6.25,
                effective_date=today,
                category=TaxCategory.STANDARD.value,
            ),
            TaxRate(
                jurisdiction_code='US-NY',
                tax_type=TaxType.SALES_TAX.value,
                rate=8.0,
                effective_date=today,
                category=TaxCategory.STANDARD.value,
            ),
            TaxRate(
                jurisdiction_code='DE',
                tax_type=TaxType.VAT.value,
                rate=19.0,
                effective_date=today,
                category=TaxCategory.STANDARD.value,
            ),
            TaxRate(
                jurisdiction_code='DE',
                tax_type=TaxType.VAT.value,
                rate=7.0,
                effective_date=today,
                category=TaxCategory.REDUCED.value,
            ),
        ]
        for r in rates:
            self.session.add(r)

        self.session.flush()
        logger.info("Seeded default tax jurisdictions and rates")

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------

    def add_jurisdiction(self, jurisdiction_data) -> Dict[str, Any]:
        """Add a tax jurisdiction.

        Accepts either a dict-like object / old-style dataclass or a raw dict
        with keys: code, name, country, state (optional), tax_types (list of str).
        """
        if isinstance(jurisdiction_data, dict):
            code = jurisdiction_data['code']
            name = jurisdiction_data['name']
            country = jurisdiction_data['country']
            state = jurisdiction_data.get('state')
            tax_types = jurisdiction_data.get('tax_types', [])
        else:
            # Legacy dataclass-style object
            code = jurisdiction_data.code
            name = jurisdiction_data.name
            country = jurisdiction_data.country
            state = getattr(jurisdiction_data, 'state', None)
            raw_types = getattr(jurisdiction_data, 'tax_types', [])
            tax_types = [t.value if isinstance(t, TaxType) else t for t in raw_types]

        # Normalise tax_types to plain strings for JSON storage
        tax_types = [t.value if isinstance(t, TaxType) else t for t in tax_types]

        db_obj = TaxJurisdiction(
            code=code,
            name=name,
            country=country,
            state=state,
            tax_types=tax_types,
        )
        self.session.add(db_obj)
        self.session.flush()
        return {'success': True, 'jurisdiction_code': code}

    def add_rate(self, rate_data) -> Dict[str, Any]:
        """Add a tax rate.

        Accepts either a dict or an old-style dataclass with fields:
        jurisdiction_code, tax_type, rate, effective_date, expiry_date,
        tax_category / category, item_category (optional).
        """
        if isinstance(rate_data, dict):
            jurisdiction_code = rate_data['jurisdiction_code']
            tax_type = rate_data['tax_type']
            rate_val = rate_data['rate']
            effective_date = rate_data['effective_date']
            expiry_date = rate_data.get('expiry_date')
            category = rate_data.get('category') or rate_data.get('tax_category')
        else:
            jurisdiction_code = rate_data.jurisdiction_code
            tax_type = rate_data.tax_type
            rate_val = rate_data.rate
            effective_date = rate_data.effective_date
            expiry_date = getattr(rate_data, 'expiry_date', None)
            category = getattr(rate_data, 'tax_category', None) or getattr(rate_data, 'category', None)

        # Normalise enums to strings
        if isinstance(tax_type, TaxType):
            tax_type = tax_type.value
        if isinstance(category, TaxCategory):
            category = category.value
        if isinstance(rate_val, Decimal):
            rate_val = float(rate_val)

        db_obj = TaxRate(
            jurisdiction_code=jurisdiction_code,
            tax_type=tax_type,
            rate=rate_val,
            effective_date=effective_date,
            expiry_date=expiry_date,
            category=category,
        )
        self.session.add(db_obj)
        self.session.flush()
        return {'success': True, 'rate_added': True}

    def add_exemption(self, exemption_data) -> Dict[str, Any]:
        """Add a tax exemption.

        Accepts either a dict or an old-style dataclass with fields:
        entity_id, entity_type, jurisdiction_code, tax_type,
        exemption_number / certificate_number, effective_date / start_date,
        expiry_date / end_date.
        """
        if isinstance(exemption_data, dict):
            entity_id = exemption_data['entity_id']
            entity_type = exemption_data['entity_type']
            jurisdiction_code = exemption_data['jurisdiction_code']
            tax_type = exemption_data['tax_type']
            certificate_number = (
                exemption_data.get('certificate_number')
                or exemption_data.get('exemption_number')
            )
            start_date = exemption_data.get('start_date') or exemption_data.get('effective_date')
            end_date = exemption_data.get('end_date') or exemption_data.get('expiry_date')
        else:
            entity_id = exemption_data.entity_id
            entity_type = exemption_data.entity_type
            jurisdiction_code = exemption_data.jurisdiction_code
            tax_type = exemption_data.tax_type
            certificate_number = (
                getattr(exemption_data, 'certificate_number', None)
                or getattr(exemption_data, 'exemption_number', None)
            )
            start_date = (
                getattr(exemption_data, 'start_date', None)
                or getattr(exemption_data, 'effective_date', None)
            )
            end_date = (
                getattr(exemption_data, 'end_date', None)
                or getattr(exemption_data, 'expiry_date', None)
            )

        if isinstance(tax_type, TaxType):
            tax_type = tax_type.value

        db_obj = TaxExemption(
            entity_id=entity_id,
            entity_type=entity_type,
            jurisdiction_code=jurisdiction_code,
            tax_type=tax_type,
            start_date=start_date,
            end_date=end_date,
            certificate_number=certificate_number,
        )
        self.session.add(db_obj)
        self.session.flush()
        return {'success': True, 'exemption_number': certificate_number}

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def _get_jurisdiction(self, code: str) -> Optional[TaxJurisdiction]:
        """Load a single jurisdiction by code from the DB."""
        return self.session.query(TaxJurisdiction).filter(
            TaxJurisdiction.code == code
        ).first()

    def get_applicable_rate(
        self,
        jurisdiction_code: str,
        tax_type: TaxType,
        tax_category: TaxCategory = TaxCategory.STANDARD,
        as_of_date: date = None,
        item_category: str = None
    ) -> Optional[TaxRate]:
        """Get the applicable tax rate for given criteria.

        Returns a TaxRate DB row or None.  The caller can read ``.rate``
        (a float) to get the percentage value.
        """
        if as_of_date is None:
            as_of_date = date.today()

        tax_type_str = tax_type.value if isinstance(tax_type, TaxType) else tax_type
        category_str = tax_category.value if isinstance(tax_category, TaxCategory) else tax_category

        base_filters = [
            TaxRate.jurisdiction_code == jurisdiction_code,
            TaxRate.tax_type == tax_type_str,
            TaxRate.effective_date <= as_of_date,
            or_(TaxRate.expiry_date.is_(None), TaxRate.expiry_date > as_of_date),
        ]

        # Try item-specific rate first (category stores tax_category normally,
        # but item_category overrides can also be stored here)
        if item_category:
            item_specific = self.session.query(TaxRate).filter(
                and_(*base_filters, TaxRate.category == item_category)
            ).first()
            if item_specific:
                return item_specific

        # Fall back to the standard category rate
        rate = self.session.query(TaxRate).filter(
            and_(*base_filters, TaxRate.category == category_str)
        ).first()

        if rate:
            return rate

        # Last resort: any rate with a null category
        return self.session.query(TaxRate).filter(
            and_(*base_filters, TaxRate.category.is_(None))
        ).first()

    def check_exemption(
        self,
        entity_id: str,
        entity_type: str,
        jurisdiction_code: str,
        tax_type: TaxType,
        as_of_date: date = None
    ) -> Optional[TaxExemption]:
        """Check if an entity has a valid tax exemption."""
        if as_of_date is None:
            as_of_date = date.today()

        tax_type_str = tax_type.value if isinstance(tax_type, TaxType) else tax_type

        return self.session.query(TaxExemption).filter(
            and_(
                TaxExemption.entity_id == entity_id,
                TaxExemption.entity_type == entity_type,
                TaxExemption.jurisdiction_code == jurisdiction_code,
                TaxExemption.tax_type == tax_type_str,
                TaxExemption.start_date <= as_of_date,
                or_(TaxExemption.end_date.is_(None), TaxExemption.end_date > as_of_date),
            )
        ).first()

    # ------------------------------------------------------------------
    # Tax calculation
    # ------------------------------------------------------------------

    def calculate_tax(
        self,
        line_items: List[Dict[str, Any]],
        ship_to_jurisdiction: str,
        customer_id: str = None,
        as_of_date: date = None,
        tax_included: bool = False
    ) -> TaxCalculationResult:
        """
        Calculate taxes for a list of line items.

        Args:
            line_items: List of {
                'amount': Decimal,
                'item_category': str (optional),
                'tax_category': TaxCategory (optional, default STANDARD),
                'description': str (optional)
            }
            ship_to_jurisdiction: Tax jurisdiction code (e.g., 'US-CA')
            customer_id: Customer ID for exemption checking
            as_of_date: Date for rate lookup
            tax_included: Whether amounts already include tax

        Returns:
            TaxCalculationResult with all tax details
        """
        if as_of_date is None:
            as_of_date = date.today()

        jurisdiction = self._get_jurisdiction(ship_to_jurisdiction)
        if not jurisdiction:
            # No jurisdiction found, return zero tax
            subtotal = sum(Decimal(str(item.get('amount', 0))) for item in line_items)
            return TaxCalculationResult(
                subtotal=subtotal,
                total_tax=Decimal('0'),
                total_with_tax=subtotal,
                tax_lines=[],
                exemptions_applied=[]
            )

        # Resolve tax_types from JSON list of strings to TaxType enums
        jurisdiction_tax_types = []
        for t in (jurisdiction.tax_types or []):
            try:
                jurisdiction_tax_types.append(TaxType(t))
            except ValueError:
                logger.warning("Unknown tax type '%s' in jurisdiction %s", t, jurisdiction.code)

        subtotal = Decimal('0')
        tax_lines: List[TaxLineResult] = []
        exemptions_applied: List[str] = []

        # Process each line item
        for item in line_items:
            amount = Decimal(str(item.get('amount', 0)))
            item_category = item.get('item_category')
            tax_category = item.get('tax_category', TaxCategory.STANDARD)

            if isinstance(tax_category, str):
                tax_category = TaxCategory(tax_category)

            # Skip exempt items
            if tax_category == TaxCategory.EXEMPT:
                subtotal += amount
                continue

            # Calculate tax for each applicable tax type in jurisdiction
            for tax_type in jurisdiction_tax_types:
                # Check for customer exemption
                if customer_id:
                    exemption = self.check_exemption(
                        customer_id, 'customer', ship_to_jurisdiction, tax_type, as_of_date
                    )
                    if exemption:
                        exemptions_applied.append(
                            f"{tax_type.value}: {exemption.certificate_number}"
                        )
                        continue

                # Get applicable rate
                rate = self.get_applicable_rate(
                    ship_to_jurisdiction, tax_type, tax_category, as_of_date, item_category
                )

                if rate and rate.rate > 0:
                    rate_decimal = Decimal(str(rate.rate))
                    if tax_included:
                        # Extract tax from amount
                        taxable_amount = amount / (1 + rate_decimal / 100)
                        tax_amount = amount - taxable_amount
                    else:
                        taxable_amount = amount
                        tax_amount = (amount * rate_decimal / 100).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )

                    description = f"{tax_type.value} @ {rate.rate}%"

                    tax_lines.append(TaxLineResult(
                        jurisdiction_code=ship_to_jurisdiction,
                        tax_type=tax_type,
                        tax_category=tax_category,
                        taxable_amount=taxable_amount,
                        tax_rate=rate_decimal,
                        tax_amount=tax_amount,
                        description=description,
                    ))

            subtotal += amount

        # Aggregate results
        total_tax = sum(tl.tax_amount for tl in tax_lines)

        if tax_included:
            total_with_tax = subtotal
            subtotal = subtotal - total_tax
        else:
            total_with_tax = subtotal + total_tax

        return TaxCalculationResult(
            subtotal=subtotal,
            total_tax=total_tax,
            total_with_tax=total_with_tax,
            tax_lines=tax_lines,
            exemptions_applied=exemptions_applied
        )

    def calculate_invoice_tax(
        self,
        invoice_id: str,
        ship_to_jurisdiction: str = None
    ) -> Dict[str, Any]:
        """
        Calculate tax for an existing invoice.

        Args:
            invoice_id: AR Invoice ID
            ship_to_jurisdiction: Override jurisdiction (uses customer default if not provided)

        Returns:
            Tax calculation result with invoice update
        """
        from models.erp.financial import ARInvoice, ARInvoiceLine

        invoice = self.session.query(ARInvoice).filter(
            ARInvoice.id == invoice_id
        ).first()

        if not invoice:
            return {'error': f'Invoice {invoice_id} not found'}

        # Get jurisdiction from customer or parameter
        jurisdiction = ship_to_jurisdiction
        if not jurisdiction and invoice.customer:
            # Would look up customer's default tax jurisdiction
            jurisdiction = 'US-CA'  # Default fallback

        # Build line items from invoice
        line_items = []
        for line in invoice.lines:
            line_items.append({
                'amount': line.extended_amount,
                'item_category': line.item.category.name if line.item and line.item.category else None,
                'tax_category': TaxCategory.STANDARD,
                'description': line.description
            })

        # Calculate tax
        result = self.calculate_tax(
            line_items=line_items,
            ship_to_jurisdiction=jurisdiction,
            customer_id=str(invoice.customer_id) if invoice.customer_id else None
        )

        # Update invoice
        invoice.tax_amount = result.total_tax
        invoice.total_amount = result.total_with_tax
        self.session.flush()

        return {
            'invoice_id': str(invoice.id),
            'subtotal': float(result.subtotal),
            'tax_amount': float(result.total_tax),
            'total_amount': float(result.total_with_tax),
            'tax_lines': [
                {
                    'jurisdiction': tl.jurisdiction_code,
                    'tax_type': tl.tax_type.value,
                    'rate': float(tl.tax_rate),
                    'amount': float(tl.tax_amount)
                }
                for tl in result.tax_lines
            ],
            'exemptions': result.exemptions_applied
        }

    def get_tax_summary_by_jurisdiction(
        self,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Get tax summary grouped by jurisdiction for reporting.

        Returns tax collected/owed by jurisdiction and tax type.
        """
        # This would query actual invoice tax data from database
        # For now, return structure
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'by_jurisdiction': {
                'US-CA': {
                    'sales_tax': {
                        'taxable_amount': 0,
                        'tax_collected': 0,
                        'rate': 7.25
                    }
                },
                'US-TX': {
                    'sales_tax': {
                        'taxable_amount': 0,
                        'tax_collected': 0,
                        'rate': 6.25
                    }
                }
            },
            'total_tax_collected': 0
        }

    def get_jurisdictions(self) -> List[Dict[str, Any]]:
        """List all tax jurisdictions."""
        rows = self.session.query(TaxJurisdiction).all()
        return [
            {
                'code': j.code,
                'name': j.name,
                'country': j.country,
                'state': j.state,
                'tax_types': j.tax_types or [],
            }
            for j in rows
        ]

    def get_rates(self, jurisdiction_code: str = None) -> List[Dict[str, Any]]:
        """List tax rates, optionally filtered by jurisdiction."""
        query = self.session.query(TaxRate)
        if jurisdiction_code:
            query = query.filter(TaxRate.jurisdiction_code == jurisdiction_code)

        rows = query.all()
        return [
            {
                'jurisdiction_code': r.jurisdiction_code,
                'tax_type': r.tax_type,
                'tax_category': r.category,
                'rate': float(r.rate),
                'effective_date': r.effective_date.isoformat() if r.effective_date else None,
                'expiry_date': r.expiry_date.isoformat() if r.expiry_date else None,
            }
            for r in rows
        ]


# Convenience functions
def calculate_tax(
    line_items: List[Dict[str, Any]],
    ship_to_jurisdiction: str,
    customer_id: str = None
) -> Dict[str, Any]:
    """Calculate tax for line items (standalone function)."""
    service = TaxService()
    result = service.calculate_tax(line_items, ship_to_jurisdiction, customer_id)
    return {
        'subtotal': float(result.subtotal),
        'total_tax': float(result.total_tax),
        'total_with_tax': float(result.total_with_tax),
        'tax_lines': [
            {
                'jurisdiction': tl.jurisdiction_code,
                'tax_type': tl.tax_type.value,
                'rate': float(tl.tax_rate),
                'amount': float(tl.tax_amount)
            }
            for tl in result.tax_lines
        ]
    }


def get_tax_rate(jurisdiction: str, tax_type: str = 'sales_tax') -> Optional[float]:
    """Get current tax rate for a jurisdiction."""
    service = TaxService()
    rate = service.get_applicable_rate(
        jurisdiction,
        TaxType(tax_type),
        TaxCategory.STANDARD
    )
    return float(rate.rate) if rate else None
