"""
ERP Multi-Currency Service
===========================
Handles foreign currency transactions, exchange rate management,
and currency gain/loss calculations for international operations.

Features:
- Exchange rate management with date ranges
- Automatic rate lookup on transactions
- Realized/unrealized gain/loss calculation
- Currency revaluation journals
- Multi-currency consolidation
"""

import logging
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CurrencyCode(str, Enum):
    """ISO 4217 currency codes."""
    USD = 'USD'  # US Dollar
    EUR = 'EUR'  # Euro
    GBP = 'GBP'  # British Pound
    JPY = 'JPY'  # Japanese Yen
    CNY = 'CNY'  # Chinese Yuan
    CAD = 'CAD'  # Canadian Dollar
    AUD = 'AUD'  # Australian Dollar
    CHF = 'CHF'  # Swiss Franc
    MXN = 'MXN'  # Mexican Peso
    INR = 'INR'  # Indian Rupee
    BRL = 'BRL'  # Brazilian Real
    KRW = 'KRW'  # South Korean Won
    SEK = 'SEK'  # Swedish Krona
    NOK = 'NOK'  # Norwegian Krone
    DKK = 'DKK'  # Danish Krone
    SGD = 'SGD'  # Singapore Dollar
    HKD = 'HKD'  # Hong Kong Dollar
    TWD = 'TWD'  # Taiwan Dollar


class ExchangeRateType(str, Enum):
    """Type of exchange rate."""
    SPOT = 'spot'           # Current market rate
    AVERAGE = 'average'     # Period average rate
    BUDGET = 'budget'       # Budgeted rate
    HISTORICAL = 'historical'  # Rate at transaction date


@dataclass
class ExchangeRate:
    """Exchange rate definition."""
    from_currency: str
    to_currency: str
    rate: Decimal
    effective_date: date
    expiry_date: Optional[date] = None
    rate_type: ExchangeRateType = ExchangeRateType.SPOT
    source: str = 'manual'  # 'manual', 'api', 'bank'


@dataclass
class CurrencyAmount:
    """Amount in a specific currency."""
    amount: Decimal
    currency: str

    def to_decimal(self) -> Decimal:
        return self.amount


@dataclass
class ConversionResult:
    """Result of currency conversion."""
    original_amount: Decimal
    original_currency: str
    converted_amount: Decimal
    target_currency: str
    exchange_rate: Decimal
    rate_date: date
    rate_type: ExchangeRateType


@dataclass
class GainLossEntry:
    """Currency gain/loss entry."""
    transaction_id: str
    original_amount: Decimal
    original_currency: str
    functional_amount_at_transaction: Decimal
    functional_amount_at_settlement: Decimal
    gain_loss: Decimal
    is_realized: bool
    transaction_date: date
    settlement_date: Optional[date]


class CurrencyService:
    """
    Multi-currency management service.

    Handles:
    - Exchange rate tables with date ranges
    - Automatic rate lookup on transactions
    - Realized/unrealized gain/loss calculation
    - Currency revaluation journals
    - Multi-currency consolidation
    """

    def __init__(self, session: Session = None, functional_currency: str = 'USD'):
        self.session = session
        self.functional_currency = functional_currency
        self._rate_cache: Dict[Tuple[str, str, date], ExchangeRate] = {}

        # Default exchange rates (relative to USD)
        # In production, these would come from database or API
        self._default_rates: Dict[str, Decimal] = {
            'USD': Decimal('1.0000'),
            'EUR': Decimal('0.9250'),
            'GBP': Decimal('0.7900'),
            'JPY': Decimal('149.50'),
            'CNY': Decimal('7.2500'),
            'CAD': Decimal('1.3600'),
            'AUD': Decimal('1.5400'),
            'CHF': Decimal('0.8850'),
            'MXN': Decimal('17.15'),
            'INR': Decimal('83.10'),
            'BRL': Decimal('4.9700'),
            'KRW': Decimal('1335.00'),
            'SEK': Decimal('10.45'),
            'NOK': Decimal('10.65'),
            'DKK': Decimal('6.90'),
            'SGD': Decimal('1.3450'),
            'HKD': Decimal('7.8200'),
            'TWD': Decimal('31.50'),
        }

        # Currency precision (decimal places)
        self._currency_precision: Dict[str, int] = {
            'USD': 2, 'EUR': 2, 'GBP': 2, 'JPY': 0, 'CNY': 2,
            'CAD': 2, 'AUD': 2, 'CHF': 2, 'MXN': 2, 'INR': 2,
            'BRL': 2, 'KRW': 0, 'SEK': 2, 'NOK': 2, 'DKK': 2,
            'SGD': 2, 'HKD': 2, 'TWD': 0,
        }

    def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date = None,
        rate_type: ExchangeRateType = ExchangeRateType.SPOT
    ) -> Optional[ExchangeRate]:
        """
        Get exchange rate between two currencies.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            rate_date: Date for the rate (default: today)
            rate_type: Type of rate to retrieve

        Returns:
            ExchangeRate or None if not found
        """
        rate_date = rate_date or date.today()
        cache_key = (from_currency, to_currency, rate_date)

        if cache_key in self._rate_cache:
            return self._rate_cache[cache_key]

        # Try database first
        if self.session:
            rate = self._get_rate_from_db(from_currency, to_currency, rate_date, rate_type)
            if rate:
                self._rate_cache[cache_key] = rate
                return rate

        # Fall back to default rates via USD
        rate = self._calculate_cross_rate(from_currency, to_currency)
        if rate:
            exchange_rate = ExchangeRate(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=rate,
                effective_date=rate_date,
                rate_type=rate_type,
                source='default'
            )
            self._rate_cache[cache_key] = exchange_rate
            return exchange_rate

        return None

    def _get_rate_from_db(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date,
        rate_type: ExchangeRateType
    ) -> Optional[ExchangeRate]:
        """Query database for exchange rate."""
        try:
            from models.erp.currency import ExchangeRateRecord

            record = self.session.query(ExchangeRateRecord).filter(
                ExchangeRateRecord.from_currency == from_currency,
                ExchangeRateRecord.to_currency == to_currency,
                ExchangeRateRecord.rate_type == rate_type.value,
                ExchangeRateRecord.effective_date <= rate_date,
                (ExchangeRateRecord.expiry_date.is_(None) |
                 (ExchangeRateRecord.expiry_date >= rate_date))
            ).order_by(
                ExchangeRateRecord.effective_date.desc()
            ).first()

            if record:
                return ExchangeRate(
                    from_currency=record.from_currency,
                    to_currency=record.to_currency,
                    rate=Decimal(str(record.rate)),
                    effective_date=record.effective_date,
                    expiry_date=record.expiry_date,
                    rate_type=ExchangeRateType(record.rate_type),
                    source='database'
                )
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Failed to get rate from DB: {e}")

        return None

    def _calculate_cross_rate(
        self,
        from_currency: str,
        to_currency: str
    ) -> Optional[Decimal]:
        """Calculate cross rate using USD as intermediary."""
        if from_currency == to_currency:
            return Decimal('1.0000')

        from_usd_rate = self._default_rates.get(from_currency)
        to_usd_rate = self._default_rates.get(to_currency)

        if from_usd_rate is None or to_usd_rate is None:
            return None

        # Rate: 1 from_currency = X to_currency
        # via USD: from_currency -> USD -> to_currency
        # from_usd_rate = how many USD per 1 from_currency (inverse for non-USD)
        # to_usd_rate = how many to_currency per 1 USD

        if from_currency == 'USD':
            return to_usd_rate
        elif to_currency == 'USD':
            return Decimal('1') / from_usd_rate
        else:
            # Cross rate through USD
            usd_amount = Decimal('1') / from_usd_rate
            return usd_amount * to_usd_rate

    def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        rate_date: date = None,
        rate_type: ExchangeRateType = ExchangeRateType.SPOT
    ) -> ConversionResult:
        """
        Convert amount from one currency to another.

        Args:
            amount: Amount to convert
            from_currency: Source currency
            to_currency: Target currency
            rate_date: Date for exchange rate
            rate_type: Type of rate to use

        Returns:
            ConversionResult with conversion details
        """
        rate_date = rate_date or date.today()

        if from_currency == to_currency:
            return ConversionResult(
                original_amount=amount,
                original_currency=from_currency,
                converted_amount=amount,
                target_currency=to_currency,
                exchange_rate=Decimal('1.0000'),
                rate_date=rate_date,
                rate_type=rate_type
            )

        exchange_rate = self.get_exchange_rate(from_currency, to_currency, rate_date, rate_type)

        if not exchange_rate:
            raise ValueError(f"No exchange rate found for {from_currency}/{to_currency}")

        converted = amount * exchange_rate.rate
        precision = self._currency_precision.get(to_currency, 2)
        converted = converted.quantize(Decimal(f'0.{"0" * precision}'), rounding=ROUND_HALF_UP)

        return ConversionResult(
            original_amount=amount,
            original_currency=from_currency,
            converted_amount=converted,
            target_currency=to_currency,
            exchange_rate=exchange_rate.rate,
            rate_date=rate_date,
            rate_type=rate_type
        )

    def convert_to_functional(
        self,
        amount: Decimal,
        currency: str,
        rate_date: date = None
    ) -> ConversionResult:
        """Convert amount to functional (base) currency."""
        return self.convert(
            amount=amount,
            from_currency=currency,
            to_currency=self.functional_currency,
            rate_date=rate_date
        )

    def set_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate: Decimal,
        effective_date: date = None,
        expiry_date: date = None,
        rate_type: ExchangeRateType = ExchangeRateType.SPOT,
        source: str = 'manual'
    ) -> Dict[str, Any]:
        """
        Set or update an exchange rate.

        Args:
            from_currency: Source currency
            to_currency: Target currency
            rate: Exchange rate
            effective_date: When rate becomes effective
            expiry_date: When rate expires (None = indefinite)
            rate_type: Type of rate
            source: Source of rate data

        Returns:
            Created/updated rate record
        """
        effective_date = effective_date or date.today()

        # Clear cache for this pair
        cache_keys_to_remove = [
            k for k in self._rate_cache
            if k[0] == from_currency and k[1] == to_currency
        ]
        for key in cache_keys_to_remove:
            del self._rate_cache[key]

        if self.session:
            try:
                from models.erp.currency import ExchangeRateRecord

                # Expire any overlapping rates
                self.session.query(ExchangeRateRecord).filter(
                    ExchangeRateRecord.from_currency == from_currency,
                    ExchangeRateRecord.to_currency == to_currency,
                    ExchangeRateRecord.rate_type == rate_type.value,
                    ExchangeRateRecord.expiry_date.is_(None),
                    ExchangeRateRecord.effective_date < effective_date
                ).update({'expiry_date': effective_date - timedelta(days=1)})

                # Create new rate
                record = ExchangeRateRecord(
                    from_currency=from_currency,
                    to_currency=to_currency,
                    rate=float(rate),
                    effective_date=effective_date,
                    expiry_date=expiry_date,
                    rate_type=rate_type.value,
                    source=source,
                    created_at=datetime.utcnow()
                )
                self.session.add(record)
                self.session.flush()

                logger.info(f"Set exchange rate {from_currency}/{to_currency} = {rate}")

                return {
                    'id': record.id,
                    'from_currency': from_currency,
                    'to_currency': to_currency,
                    'rate': str(rate),
                    'effective_date': effective_date.isoformat(),
                    'expiry_date': expiry_date.isoformat() if expiry_date else None,
                    'rate_type': rate_type.value
                }
            except ImportError:
                pass

        # Store in memory
        exchange_rate = ExchangeRate(
            from_currency=from_currency,
            to_currency=to_currency,
            rate=rate,
            effective_date=effective_date,
            expiry_date=expiry_date,
            rate_type=rate_type,
            source=source
        )
        self._rate_cache[(from_currency, to_currency, effective_date)] = exchange_rate

        return {
            'from_currency': from_currency,
            'to_currency': to_currency,
            'rate': str(rate),
            'effective_date': effective_date.isoformat(),
            'rate_type': rate_type.value
        }

    def calculate_gain_loss(
        self,
        transaction_id: str,
        original_amount: Decimal,
        original_currency: str,
        transaction_date: date,
        settlement_date: date = None,
        is_realized: bool = False
    ) -> GainLossEntry:
        """
        Calculate currency gain or loss on a transaction.

        For unrealized: compares transaction date rate to current rate.
        For realized: compares transaction date rate to settlement date rate.

        Args:
            transaction_id: Reference to original transaction
            original_amount: Amount in original currency
            original_currency: Currency of transaction
            transaction_date: Date of original transaction
            settlement_date: Date of settlement (for realized)
            is_realized: Whether this is realized or unrealized

        Returns:
            GainLossEntry with calculated gain/loss
        """
        settlement_date = settlement_date or date.today()

        # Get rate at transaction date
        result_at_transaction = self.convert_to_functional(
            amount=original_amount,
            currency=original_currency,
            rate_date=transaction_date
        )

        # Get rate at settlement/current date
        result_at_settlement = self.convert_to_functional(
            amount=original_amount,
            currency=original_currency,
            rate_date=settlement_date
        )

        gain_loss = result_at_settlement.converted_amount - result_at_transaction.converted_amount

        return GainLossEntry(
            transaction_id=transaction_id,
            original_amount=original_amount,
            original_currency=original_currency,
            functional_amount_at_transaction=result_at_transaction.converted_amount,
            functional_amount_at_settlement=result_at_settlement.converted_amount,
            gain_loss=gain_loss,
            is_realized=is_realized,
            transaction_date=transaction_date,
            settlement_date=settlement_date if is_realized else None
        )

    def revalue_open_balances(
        self,
        as_of_date: date = None
    ) -> List[Dict[str, Any]]:
        """
        Revalue all open foreign currency balances.

        Creates revaluation entries for unrealized gains/losses.

        Args:
            as_of_date: Date for revaluation (default: today)

        Returns:
            List of revaluation entries
        """
        as_of_date = as_of_date or date.today()
        revaluations = []

        if not self.session:
            return revaluations

        # Get open AR balances by currency
        ar_balances = self._get_open_ar_by_currency()
        for currency, balance_info in ar_balances.items():
            if currency != self.functional_currency:
                entry = self.calculate_gain_loss(
                    transaction_id=f'AR_REVAL_{currency}_{as_of_date}',
                    original_amount=balance_info['amount'],
                    original_currency=currency,
                    transaction_date=balance_info['avg_date'],
                    settlement_date=as_of_date,
                    is_realized=False
                )
                if entry.gain_loss != 0:
                    revaluations.append({
                        'type': 'AR',
                        'currency': currency,
                        'original_amount': str(entry.original_amount),
                        'functional_original': str(entry.functional_amount_at_transaction),
                        'functional_current': str(entry.functional_amount_at_settlement),
                        'unrealized_gain_loss': str(entry.gain_loss),
                        'revaluation_date': as_of_date.isoformat()
                    })

        # Get open AP balances by currency
        ap_balances = self._get_open_ap_by_currency()
        for currency, balance_info in ap_balances.items():
            if currency != self.functional_currency:
                entry = self.calculate_gain_loss(
                    transaction_id=f'AP_REVAL_{currency}_{as_of_date}',
                    original_amount=balance_info['amount'],
                    original_currency=currency,
                    transaction_date=balance_info['avg_date'],
                    settlement_date=as_of_date,
                    is_realized=False
                )
                if entry.gain_loss != 0:
                    revaluations.append({
                        'type': 'AP',
                        'currency': currency,
                        'original_amount': str(entry.original_amount),
                        'functional_original': str(entry.functional_amount_at_transaction),
                        'functional_current': str(entry.functional_amount_at_settlement),
                        'unrealized_gain_loss': str(entry.gain_loss),
                        'revaluation_date': as_of_date.isoformat()
                    })

        logger.info(f"Generated {len(revaluations)} currency revaluation entries")
        return revaluations

    def _get_open_ar_by_currency(self) -> Dict[str, Dict[str, Any]]:
        """Get open AR balances grouped by currency."""
        # In production, would query actual AR table
        # For demo, return empty
        return {}

    def _get_open_ap_by_currency(self) -> Dict[str, Dict[str, Any]]:
        """Get open AP balances grouped by currency."""
        return {}

    def get_supported_currencies(self) -> List[Dict[str, Any]]:
        """Get list of supported currencies with details."""
        currencies = []
        for code in CurrencyCode:
            currencies.append({
                'code': code.value,
                'precision': self._currency_precision.get(code.value, 2),
                'default_rate_to_usd': str(self._default_rates.get(code.value, Decimal('1'))),
                'is_functional': code.value == self.functional_currency
            })
        return currencies

    def get_exchange_rate_history(
        self,
        from_currency: str,
        to_currency: str,
        start_date: date,
        end_date: date = None
    ) -> List[Dict[str, Any]]:
        """
        Get exchange rate history for a currency pair.

        Args:
            from_currency: Source currency
            to_currency: Target currency
            start_date: Start of date range
            end_date: End of date range (default: today)

        Returns:
            List of rate records
        """
        end_date = end_date or date.today()
        history = []

        if self.session:
            try:
                from models.erp.currency import ExchangeRateRecord

                records = self.session.query(ExchangeRateRecord).filter(
                    ExchangeRateRecord.from_currency == from_currency,
                    ExchangeRateRecord.to_currency == to_currency,
                    ExchangeRateRecord.effective_date >= start_date,
                    ExchangeRateRecord.effective_date <= end_date
                ).order_by(ExchangeRateRecord.effective_date).all()

                for record in records:
                    history.append({
                        'date': record.effective_date.isoformat(),
                        'rate': str(record.rate),
                        'rate_type': record.rate_type,
                        'source': record.source
                    })
            except ImportError:
                pass

        return history

    def create_multi_currency_invoice(
        self,
        customer_id: str,
        lines: List[Dict[str, Any]],
        currency: str,
        invoice_date: date = None
    ) -> Dict[str, Any]:
        """
        Create an invoice in a foreign currency.

        Args:
            customer_id: Customer ID
            lines: Invoice line items
            currency: Invoice currency
            invoice_date: Invoice date

        Returns:
            Invoice with amounts in both currencies
        """
        invoice_date = invoice_date or date.today()

        # Calculate totals in invoice currency
        subtotal = sum(Decimal(str(line.get('amount', 0))) for line in lines)

        # Convert to functional currency
        conversion = self.convert_to_functional(
            amount=subtotal,
            currency=currency,
            rate_date=invoice_date
        )

        return {
            'customer_id': customer_id,
            'invoice_date': invoice_date.isoformat(),
            'currency': currency,
            'subtotal': str(subtotal),
            'functional_currency': self.functional_currency,
            'functional_subtotal': str(conversion.converted_amount),
            'exchange_rate': str(conversion.exchange_rate),
            'rate_date': conversion.rate_date.isoformat(),
            'lines': lines
        }

    def consolidate_subsidiary(
        self,
        subsidiary_balances: List[Dict[str, Any]],
        subsidiary_currency: str,
        consolidation_date: date = None,
        rate_type: ExchangeRateType = ExchangeRateType.AVERAGE
    ) -> Dict[str, Any]:
        """
        Consolidate subsidiary balances into parent currency.

        Uses average rate for income statement items and
        spot rate for balance sheet items.

        Args:
            subsidiary_balances: List of account balances
            subsidiary_currency: Currency of subsidiary
            consolidation_date: Date for consolidation
            rate_type: Rate type to use

        Returns:
            Consolidated balances with translation adjustments
        """
        consolidation_date = consolidation_date or date.today()

        consolidated = []
        translation_adjustment = Decimal('0')

        for balance in subsidiary_balances:
            account_type = balance.get('account_type', 'asset')
            original_amount = Decimal(str(balance.get('amount', 0)))

            # Use spot rate for balance sheet, average for P&L
            if account_type in ('revenue', 'expense'):
                use_rate_type = ExchangeRateType.AVERAGE
            else:
                use_rate_type = ExchangeRateType.SPOT

            conversion = self.convert(
                amount=original_amount,
                from_currency=subsidiary_currency,
                to_currency=self.functional_currency,
                rate_date=consolidation_date,
                rate_type=use_rate_type
            )

            consolidated.append({
                'account_id': balance.get('account_id'),
                'account_name': balance.get('account_name'),
                'account_type': account_type,
                'original_currency': subsidiary_currency,
                'original_amount': str(original_amount),
                'functional_amount': str(conversion.converted_amount),
                'exchange_rate': str(conversion.exchange_rate),
                'rate_type': use_rate_type.value
            })

        return {
            'subsidiary_currency': subsidiary_currency,
            'functional_currency': self.functional_currency,
            'consolidation_date': consolidation_date.isoformat(),
            'balances': consolidated,
            'translation_adjustment': str(translation_adjustment)
        }


# Convenience functions for API usage
def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    rate_date: date = None
) -> Dict[str, Any]:
    """Convert currency amount."""
    service = CurrencyService()
    result = service.convert(
        amount=Decimal(str(amount)),
        from_currency=from_currency,
        to_currency=to_currency,
        rate_date=rate_date
    )
    return {
        'original_amount': str(result.original_amount),
        'original_currency': result.original_currency,
        'converted_amount': str(result.converted_amount),
        'target_currency': result.target_currency,
        'exchange_rate': str(result.exchange_rate),
        'rate_date': result.rate_date.isoformat()
    }


def get_exchange_rate(
    from_currency: str,
    to_currency: str,
    rate_date: date = None
) -> Optional[Dict[str, Any]]:
    """Get exchange rate between currencies."""
    service = CurrencyService()
    rate = service.get_exchange_rate(from_currency, to_currency, rate_date)
    if rate:
        return {
            'from_currency': rate.from_currency,
            'to_currency': rate.to_currency,
            'rate': str(rate.rate),
            'effective_date': rate.effective_date.isoformat(),
            'rate_type': rate.rate_type.value,
            'source': rate.source
        }
    return None
