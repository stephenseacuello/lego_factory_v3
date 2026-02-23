"""
ERP Bank Reconciliation Service
================================
Handles bank statement import, auto-matching, and reconciliation.

Features:
- Bank statement import (CSV, OFX, QFX)
- Auto-matching rules (amount, reference, date)
- Outstanding check tracking
- Reconciliation status tracking
- Bank feed integration capability
"""

import logging
import csv
import re
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from enum import Enum
import uuid

from sqlalchemy.orm import Session

from models.erp.bank_reconciliation import (
    BankTransaction,
    ReconciliationSession,
    OutstandingCheck,
)

logger = logging.getLogger(__name__)


class TransactionType(str, Enum):
    """Bank transaction type."""
    DEPOSIT = 'deposit'
    WITHDRAWAL = 'withdrawal'
    CHECK = 'check'
    TRANSFER = 'transfer'
    FEE = 'fee'
    INTEREST = 'interest'
    OTHER = 'other'


class MatchStatus(str, Enum):
    """Transaction match status."""
    UNMATCHED = 'unmatched'
    AUTO_MATCHED = 'auto_matched'
    MANUAL_MATCHED = 'manual_matched'
    RECONCILED = 'reconciled'
    EXCLUDED = 'excluded'


class ReconciliationStatus(str, Enum):
    """Bank reconciliation status."""
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    APPROVED = 'approved'


@dataclass
class MatchRule:
    """Auto-matching rule."""
    rule_id: str
    name: str
    priority: int
    # Match criteria
    amount_tolerance: Decimal = Decimal('0.01')
    date_tolerance_days: int = 3
    reference_pattern: str = None
    description_pattern: str = None
    transaction_type: TransactionType = None
    # Target GL
    default_gl_account: str = None
    default_category: str = None
    is_active: bool = True


class BankReconciliationService:
    """
    Bank reconciliation service.

    Provides:
    - Statement import (CSV, OFX)
    - Automatic transaction matching
    - Manual matching interface
    - Outstanding check tracking
    - Reconciliation completion and approval
    """

    def __init__(self, session: Session = None):
        self.session = session
        self._match_rules: List[MatchRule] = self._get_default_rules()

    def _get_default_rules(self) -> List[MatchRule]:
        """Get default matching rules."""
        return [
            MatchRule(
                rule_id='RULE-001',
                name='Exact Amount Match',
                priority=1,
                amount_tolerance=Decimal('0.00'),
                date_tolerance_days=0
            ),
            MatchRule(
                rule_id='RULE-002',
                name='Amount with Tolerance',
                priority=2,
                amount_tolerance=Decimal('0.01'),
                date_tolerance_days=2
            ),
            MatchRule(
                rule_id='RULE-003',
                name='Check Number Match',
                priority=1,
                amount_tolerance=Decimal('0.01'),
                date_tolerance_days=5,
                transaction_type=TransactionType.CHECK
            ),
            MatchRule(
                rule_id='RULE-004',
                name='Payroll Pattern',
                priority=3,
                description_pattern=r'(PAYROLL|SALARY|WAGE)',
                default_gl_account='5100',
                default_category='payroll'
            ),
            MatchRule(
                rule_id='RULE-005',
                name='Bank Fee',
                priority=2,
                description_pattern=r'(SERVICE CHARGE|BANK FEE|MONTHLY FEE)',
                transaction_type=TransactionType.FEE,
                default_gl_account='6500',
                default_category='bank_fees'
            ),
        ]

    # =========================================================================
    # Statement Import
    # =========================================================================

    def import_csv_statement(
        self,
        bank_account_id: str,
        csv_content: str,
        column_mapping: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Import bank statement from CSV content.

        Args:
            bank_account_id: Bank account ID
            csv_content: CSV file content
            column_mapping: Map of standard fields to CSV columns

        Returns:
            Import result with statistics
        """
        # Default column mapping
        mapping = column_mapping or {
            'date': 'Date',
            'description': 'Description',
            'amount': 'Amount',
            'reference': 'Reference',
            'check_number': 'Check Number',
            'type': 'Type'
        }

        transactions = []
        errors = []

        try:
            lines = csv_content.strip().split('\n')
            reader = csv.DictReader(lines)

            for row_num, row in enumerate(reader, start=2):
                try:
                    txn = self._parse_csv_row(row, mapping, bank_account_id)
                    if txn:
                        self.session.add(txn)
                        self.session.flush()
                        transactions.append(txn)
                except Exception as e:
                    errors.append({'row': row_num, 'error': str(e)})

        except Exception as e:
            return {'success': False, 'error': f'Failed to parse CSV: {e}'}

        # Run auto-matching
        matched_count = 0
        for txn in transactions:
            if self._auto_match_transaction(txn):
                matched_count += 1

        self.session.flush()

        logger.info(
            f"Imported {len(transactions)} transactions for account {bank_account_id}, "
            f"auto-matched {matched_count}"
        )

        return {
            'success': True,
            'bank_account_id': bank_account_id,
            'transactions_imported': len(transactions),
            'transactions_matched': matched_count,
            'transactions_unmatched': len(transactions) - matched_count,
            'errors': errors,
            'transaction_ids': [str(t.id) for t in transactions]
        }

    def _parse_csv_row(
        self,
        row: Dict[str, str],
        mapping: Dict[str, str],
        bank_account_id: str
    ) -> Optional[BankTransaction]:
        """Parse a CSV row into a bank transaction."""
        date_str = row.get(mapping.get('date', 'Date'), '').strip()
        if not date_str:
            return None

        # Parse date (handle multiple formats)
        txn_date = self._parse_date(date_str)
        if not txn_date:
            return None

        # Parse amount
        amount_str = row.get(mapping.get('amount', 'Amount'), '0').strip()
        amount = self._parse_amount(amount_str)

        # Determine transaction type
        type_str = row.get(mapping.get('type', 'Type'), '').strip().upper()
        check_num = row.get(mapping.get('check_number', 'Check Number'), '').strip()

        if check_num:
            txn_type = TransactionType.CHECK
        elif 'FEE' in type_str or 'CHARGE' in type_str:
            txn_type = TransactionType.FEE
        elif 'INTEREST' in type_str:
            txn_type = TransactionType.INTEREST
        elif 'TRANSFER' in type_str:
            txn_type = TransactionType.TRANSFER
        elif amount > 0:
            txn_type = TransactionType.DEPOSIT
        else:
            txn_type = TransactionType.WITHDRAWAL

        return BankTransaction(
            bank_account_id=bank_account_id,
            transaction_date=txn_date,
            post_date=txn_date,
            transaction_type=txn_type.value,
            amount=float(amount),
            description=row.get(mapping.get('description', 'Description'), '').strip(),
            reference=row.get(mapping.get('reference', 'Reference'), '').strip() or None,
            check_number=check_num or None,
            match_status=MatchStatus.UNMATCHED.value,
            imported_at=datetime.utcnow()
        )

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date from various formats."""
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%m/%d/%y',
            '%d/%m/%Y',
            '%Y/%m/%d',
            '%m-%d-%Y',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    def _parse_amount(self, amount_str: str) -> Decimal:
        """Parse amount string to Decimal."""
        # Remove currency symbols and commas
        cleaned = re.sub(r'[,$]', '', amount_str)
        # Handle parentheses for negative
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]
        try:
            return Decimal(cleaned).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except:
            return Decimal('0')

    def import_ofx_statement(
        self,
        bank_account_id: str,
        ofx_content: str
    ) -> Dict[str, Any]:
        """
        Import bank statement from OFX/QFX content.

        Args:
            bank_account_id: Bank account ID
            ofx_content: OFX file content

        Returns:
            Import result
        """
        # Simplified OFX parsing (production would use ofxparse library)
        transactions = []

        # Extract transactions using regex (simplified)
        txn_pattern = re.compile(
            r'<STMTTRN>.*?<TRNTYPE>(\w+).*?<DTPOSTED>(\d{8}).*?<TRNAMT>([-\d.]+).*?'
            r'(?:<NAME>([^<]*?))?.*?(?:<MEMO>([^<]*?))?.*?</STMTTRN>',
            re.DOTALL | re.IGNORECASE
        )

        for match in txn_pattern.finditer(ofx_content):
            txn_type_str = match.group(1).upper()
            date_str = match.group(2)
            amount_str = match.group(3)
            name = match.group(4) or ''
            memo = match.group(5) or ''

            # Parse date (YYYYMMDD format)
            try:
                txn_date = datetime.strptime(date_str[:8], '%Y%m%d').date()
            except:
                continue

            amount = self._parse_amount(amount_str)

            # Map OFX type
            type_map = {
                'CREDIT': TransactionType.DEPOSIT,
                'DEBIT': TransactionType.WITHDRAWAL,
                'CHECK': TransactionType.CHECK,
                'INT': TransactionType.INTEREST,
                'FEE': TransactionType.FEE,
                'XFER': TransactionType.TRANSFER,
            }
            txn_type = type_map.get(txn_type_str, TransactionType.OTHER)

            txn = BankTransaction(
                bank_account_id=bank_account_id,
                transaction_date=txn_date,
                post_date=txn_date,
                transaction_type=txn_type.value,
                amount=float(amount),
                description=f"{name} {memo}".strip(),
                match_status=MatchStatus.UNMATCHED.value,
                imported_at=datetime.utcnow()
            )
            self.session.add(txn)
            self.session.flush()
            transactions.append(txn)

        # Auto-match
        matched = sum(1 for t in transactions if self._auto_match_transaction(t))
        self.session.flush()

        return {
            'success': True,
            'bank_account_id': bank_account_id,
            'transactions_imported': len(transactions),
            'transactions_matched': matched,
            'transactions_unmatched': len(transactions) - matched
        }

    # =========================================================================
    # Auto-Matching
    # =========================================================================

    def _auto_match_transaction(self, txn: BankTransaction) -> bool:
        """
        Attempt to auto-match a bank transaction to GL entries.

        Returns True if matched.
        """
        # Get candidate GL entries
        candidates = self._get_gl_candidates(txn)

        if not candidates:
            return False

        # Try matching rules in priority order
        for rule in sorted(self._match_rules, key=lambda r: r.priority):
            if not rule.is_active:
                continue

            match = self._apply_rule(txn, candidates, rule)
            if match:
                txn.match_status = MatchStatus.AUTO_MATCHED.value
                txn.matched_gl_entry_id = match['gl_entry_id']
                txn.matched_at = datetime.utcnow()
                return True

        return False

    def _get_gl_candidates(self, txn: BankTransaction) -> List[Dict[str, Any]]:
        """Get candidate GL entries for matching."""
        if self.session:
            try:
                from models.erp.general_ledger import JournalEntry

                # Query GL entries within date range
                start_date = txn.transaction_date - timedelta(days=7)
                end_date = txn.transaction_date + timedelta(days=7)

                entries = self.session.query(JournalEntry).filter(
                    JournalEntry.entry_date >= start_date,
                    JournalEntry.entry_date <= end_date,
                    JournalEntry.is_reconciled == False
                ).all()

                return [{
                    'gl_entry_id': str(e.id),
                    'entry_date': e.entry_date,
                    'amount': Decimal(str(e.amount)),
                    'description': e.description,
                    'reference': e.reference
                } for e in entries]
            except ImportError:
                pass

        # Demo candidates
        return []

    def _apply_rule(
        self,
        txn: BankTransaction,
        candidates: List[Dict[str, Any]],
        rule: MatchRule
    ) -> Optional[Dict[str, Any]]:
        """Apply matching rule to find a match."""
        txn_amount = Decimal(str(txn.amount))
        txn_type = txn.transaction_type

        for candidate in candidates:
            # Check amount tolerance
            amount_diff = abs(txn_amount - candidate['amount'])
            if amount_diff > rule.amount_tolerance:
                continue

            # Check date tolerance
            date_diff = abs((txn.transaction_date - candidate['entry_date']).days)
            if date_diff > rule.date_tolerance_days:
                continue

            # Check reference pattern
            if rule.reference_pattern:
                if not re.search(rule.reference_pattern, txn.reference or '', re.IGNORECASE):
                    continue

            # Check description pattern
            if rule.description_pattern:
                if not re.search(rule.description_pattern, txn.description or '', re.IGNORECASE):
                    continue

            # Check transaction type
            if rule.transaction_type and txn_type != rule.transaction_type.value:
                continue

            # Match found
            return candidate

        return None

    def manual_match(
        self,
        transaction_id: str,
        gl_entry_id: str
    ) -> Dict[str, Any]:
        """
        Manually match a bank transaction to a GL entry.

        Args:
            transaction_id: Bank transaction ID
            gl_entry_id: GL entry ID

        Returns:
            Match result
        """
        txn = self.session.query(BankTransaction).filter_by(id=transaction_id).first()
        if not txn:
            return {'success': False, 'error': 'Transaction not found'}

        txn.match_status = MatchStatus.MANUAL_MATCHED.value
        txn.matched_gl_entry_id = gl_entry_id
        txn.matched_at = datetime.utcnow()
        self.session.flush()

        logger.info(f"Manually matched {transaction_id} to GL entry {gl_entry_id}")

        return {
            'success': True,
            'transaction_id': transaction_id,
            'gl_entry_id': gl_entry_id,
            'match_status': txn.match_status
        }

    def unmatch_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Unmatch a previously matched transaction."""
        txn = self.session.query(BankTransaction).filter_by(id=transaction_id).first()
        if not txn:
            return {'success': False, 'error': 'Transaction not found'}

        txn.match_status = MatchStatus.UNMATCHED.value
        txn.matched_gl_entry_id = None
        txn.matched_at = None
        self.session.flush()

        return {
            'success': True,
            'transaction_id': transaction_id,
            'match_status': txn.match_status
        }

    # =========================================================================
    # Outstanding Checks
    # =========================================================================

    def add_outstanding_check(
        self,
        bank_account_id: str,
        check_number: str,
        amount: float,
        date_issued: str,
        payee: str,
        gl_entry_id: str = None
    ) -> Dict[str, Any]:
        """
        Add an outstanding check.

        Args:
            bank_account_id: Bank account
            check_number: Check number
            amount: Check amount
            date_issued: Date check was issued
            payee: Payee name
            gl_entry_id: Associated GL entry

        Returns:
            Outstanding check record
        """
        issued = date.fromisoformat(date_issued) if isinstance(date_issued, str) else date_issued

        check = OutstandingCheck(
            bank_account_id=bank_account_id,
            check_number=check_number,
            amount=float(Decimal(str(amount))),
            issued_date=issued,
            payee=payee,
            gl_entry_id=gl_entry_id,
            status='outstanding',
        )
        self.session.add(check)
        self.session.flush()

        return {
            'check_id': str(check.id),
            'bank_account_id': check.bank_account_id,
            'check_number': check.check_number,
            'amount': check.amount,
            'date_issued': check.issued_date.isoformat() if check.issued_date else None,
            'payee': check.payee,
            'gl_entry_id': check.gl_entry_id,
            'status': check.status,
            'created_at': check.created_at.isoformat() if check.created_at else None,
        }

    def get_outstanding_checks(
        self,
        bank_account_id: str = None
    ) -> List[Dict[str, Any]]:
        """Get outstanding checks."""
        query = self.session.query(OutstandingCheck).filter(
            OutstandingCheck.status == 'outstanding'
        )
        if bank_account_id:
            query = query.filter(OutstandingCheck.bank_account_id == bank_account_id)

        checks = query.all()

        return [
            {
                'check_id': str(c.id),
                'bank_account_id': c.bank_account_id,
                'check_number': c.check_number,
                'amount': float(c.amount),
                'date_issued': c.issued_date.isoformat() if c.issued_date else None,
                'payee': c.payee,
                'gl_entry_id': c.gl_entry_id,
                'status': c.status,
                'days_outstanding': (date.today() - c.issued_date).days if c.issued_date else 0,
            }
            for c in checks
        ]

    def clear_check(
        self,
        check_number: str,
        bank_account_id: str,
        clear_date: str
    ) -> Dict[str, Any]:
        """Mark a check as cleared."""
        check = self.session.query(OutstandingCheck).filter_by(
            bank_account_id=bank_account_id,
            check_number=check_number,
        ).first()

        if not check:
            return {'success': False, 'error': 'Check not found'}

        check.status = 'cleared'
        check.cleared_date = date.fromisoformat(clear_date) if isinstance(clear_date, str) else clear_date
        self.session.flush()

        return {
            'success': True,
            'check_number': check_number,
            'amount': float(check.amount),
            'cleared_date': check.cleared_date.isoformat()
        }

    # =========================================================================
    # Reconciliation Session
    # =========================================================================

    def start_reconciliation(
        self,
        bank_account_id: str,
        statement_date: str,
        statement_ending_balance: float
    ) -> Dict[str, Any]:
        """
        Start a new reconciliation session.

        Args:
            bank_account_id: Bank account to reconcile
            statement_date: Statement date
            statement_ending_balance: Ending balance per statement

        Returns:
            Reconciliation session info
        """
        stmt_date = date.fromisoformat(statement_date) if isinstance(statement_date, str) else statement_date

        # Get book balance
        book_balance = self._get_book_balance(bank_account_id, stmt_date)

        recon = ReconciliationSession(
            bank_account_id=bank_account_id,
            statement_date=stmt_date,
            ending_balance=float(Decimal(str(statement_ending_balance))),
            book_balance=float(book_balance),
            status=ReconciliationStatus.IN_PROGRESS.value,
            adjustments=[],
        )
        self.session.add(recon)
        self.session.flush()

        logger.info(f"Started reconciliation {recon.id} for account {bank_account_id}")

        ending = Decimal(str(recon.ending_balance))
        return {
            'session_id': str(recon.id),
            'bank_account_id': bank_account_id,
            'statement_date': stmt_date.isoformat(),
            'statement_ending_balance': float(ending),
            'book_balance': float(book_balance),
            'difference': float(ending - book_balance),
            'status': recon.status
        }

    def _get_book_balance(self, bank_account_id: str, as_of_date: date) -> Decimal:
        """Get GL book balance for bank account."""
        if self.session:
            try:
                from models.erp.general_ledger import AccountBalance

                balance = self.session.query(AccountBalance).filter(
                    AccountBalance.account_id == bank_account_id
                ).first()

                if balance:
                    return Decimal(str(balance.balance))
            except ImportError:
                pass

        # Demo balance
        return Decimal('50000.00')

    def get_reconciliation_status(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """Get current reconciliation status and summary."""
        recon = self.session.query(ReconciliationSession).filter_by(id=session_id).first()
        if not recon:
            return {'error': 'Reconciliation session not found'}

        # Count transactions by match status for this bank account
        matched_statuses = [
            MatchStatus.AUTO_MATCHED.value,
            MatchStatus.MANUAL_MATCHED.value,
            MatchStatus.RECONCILED.value,
        ]
        matched = self.session.query(BankTransaction).filter(
            BankTransaction.bank_account_id == recon.bank_account_id,
            BankTransaction.match_status.in_(matched_statuses),
        ).count()

        unmatched = self.session.query(BankTransaction).filter(
            BankTransaction.bank_account_id == recon.bank_account_id,
            BankTransaction.match_status == MatchStatus.UNMATCHED.value,
        ).count()

        # Calculate outstanding checks total
        outstanding = self.get_outstanding_checks(recon.bank_account_id)
        outstanding_total = sum(c['amount'] for c in outstanding)

        # Calculate deposits in transit (placeholder)
        deposits_in_transit = Decimal('0')

        book_balance = Decimal(str(recon.book_balance)) if recon.book_balance is not None else Decimal('0')
        ending_balance = Decimal(str(recon.ending_balance))

        # Adjusted book balance
        adjusted_book = book_balance - Decimal(str(outstanding_total)) + deposits_in_transit

        return {
            'session_id': str(recon.id),
            'bank_account_id': recon.bank_account_id,
            'statement_date': recon.statement_date.isoformat(),
            'status': recon.status,
            'statement_ending_balance': float(ending_balance),
            'book_balance': float(book_balance),
            'outstanding_checks': float(outstanding_total),
            'outstanding_check_count': len(outstanding),
            'deposits_in_transit': float(deposits_in_transit),
            'adjusted_book_balance': float(adjusted_book),
            'difference': float(ending_balance - adjusted_book),
            'is_balanced': abs(ending_balance - adjusted_book) < Decimal('0.01'),
            'transactions_matched': matched,
            'transactions_unmatched': unmatched,
            'adjustments': recon.adjustments or []
        }

    def add_reconciliation_adjustment(
        self,
        session_id: str,
        adjustment_type: str,
        amount: float,
        description: str,
        gl_account: str = None
    ) -> Dict[str, Any]:
        """
        Add a reconciling adjustment.

        Args:
            session_id: Reconciliation session
            adjustment_type: Type (e.g., 'bank_error', 'timing', 'other')
            amount: Adjustment amount
            description: Description
            gl_account: GL account for journal entry

        Returns:
            Updated reconciliation
        """
        recon = self.session.query(ReconciliationSession).filter_by(id=session_id).first()
        if not recon:
            return {'error': 'Reconciliation session not found'}

        adjustment = {
            'id': f"ADJ-{uuid.uuid4().hex[:6].upper()}",
            'type': adjustment_type,
            'amount': float(amount),
            'description': description,
            'gl_account': gl_account,
            'created_at': datetime.utcnow().isoformat()
        }

        current_adjustments = list(recon.adjustments or [])
        current_adjustments.append(adjustment)
        recon.adjustments = current_adjustments
        self.session.flush()

        return {
            'success': True,
            'adjustment': adjustment,
            'total_adjustments': sum(a['amount'] for a in recon.adjustments)
        }

    def complete_reconciliation(
        self,
        session_id: str,
        approved_by: str = None
    ) -> Dict[str, Any]:
        """
        Complete and optionally approve reconciliation.

        Args:
            session_id: Reconciliation session
            approved_by: User ID approving reconciliation

        Returns:
            Completion result
        """
        recon = self.session.query(ReconciliationSession).filter_by(id=session_id).first()
        if not recon:
            return {'error': 'Reconciliation session not found'}

        status = self.get_reconciliation_status(session_id)

        if not status.get('is_balanced'):
            return {
                'success': False,
                'error': 'Reconciliation is not balanced',
                'difference': status.get('difference')
            }

        # Mark matched transactions as reconciled
        matched_statuses = [
            MatchStatus.AUTO_MATCHED.value,
            MatchStatus.MANUAL_MATCHED.value,
        ]
        matched_txns = self.session.query(BankTransaction).filter(
            BankTransaction.bank_account_id == recon.bank_account_id,
            BankTransaction.match_status.in_(matched_statuses),
        ).all()

        for txn in matched_txns:
            txn.match_status = MatchStatus.RECONCILED.value

        recon.status = ReconciliationStatus.COMPLETED.value
        recon.completed_at = datetime.utcnow()

        if approved_by:
            recon.status = ReconciliationStatus.APPROVED.value
            recon.approved_by = approved_by

        self.session.flush()

        logger.info(f"Completed reconciliation {session_id}")

        return {
            'success': True,
            'session_id': str(recon.id),
            'status': recon.status,
            'completed_at': recon.completed_at.isoformat(),
            'approved_by': approved_by
        }

    # =========================================================================
    # Queries
    # =========================================================================

    def get_unmatched_transactions(
        self,
        bank_account_id: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get unmatched bank transactions."""
        query = self.session.query(BankTransaction).filter(
            BankTransaction.match_status == MatchStatus.UNMATCHED.value
        )
        if bank_account_id:
            query = query.filter(BankTransaction.bank_account_id == bank_account_id)

        query = query.limit(limit)
        txns = query.all()

        return [
            {
                'transaction_id': str(txn.id),
                'bank_account_id': txn.bank_account_id,
                'transaction_date': txn.transaction_date.isoformat() if txn.transaction_date else None,
                'transaction_type': txn.transaction_type,
                'amount': float(txn.amount),
                'description': txn.description,
                'reference': txn.reference,
                'check_number': txn.check_number,
                'imported_at': txn.imported_at.isoformat() if txn.imported_at else None
            }
            for txn in txns
        ]

    def get_match_suggestions(
        self,
        transaction_id: str,
        max_suggestions: int = 5
    ) -> List[Dict[str, Any]]:
        """Get match suggestions for a transaction."""
        txn = self.session.query(BankTransaction).filter_by(id=transaction_id).first()
        if not txn:
            return []

        candidates = self._get_gl_candidates(txn)
        suggestions = []

        txn_amount = Decimal(str(txn.amount))

        for candidate in candidates[:max_suggestions]:
            amount_diff = abs(txn_amount - candidate['amount'])
            date_diff = abs((txn.transaction_date - candidate['entry_date']).days)

            score = 100 - (float(amount_diff) * 10) - (date_diff * 5)
            score = max(0, min(100, score))

            suggestions.append({
                'gl_entry_id': candidate['gl_entry_id'],
                'entry_date': candidate['entry_date'].isoformat(),
                'amount': float(candidate['amount']),
                'description': candidate['description'],
                'reference': candidate['reference'],
                'match_score': score,
                'amount_difference': float(amount_diff),
                'date_difference_days': date_diff
            })

        return sorted(suggestions, key=lambda x: -x['match_score'])

    def add_match_rule(
        self,
        name: str,
        priority: int = 5,
        amount_tolerance: float = 0.01,
        date_tolerance_days: int = 3,
        reference_pattern: str = None,
        description_pattern: str = None,
        default_gl_account: str = None
    ) -> Dict[str, Any]:
        """Add a custom matching rule."""
        rule = MatchRule(
            rule_id=f"RULE-{uuid.uuid4().hex[:6].upper()}",
            name=name,
            priority=priority,
            amount_tolerance=Decimal(str(amount_tolerance)),
            date_tolerance_days=date_tolerance_days,
            reference_pattern=reference_pattern,
            description_pattern=description_pattern,
            default_gl_account=default_gl_account
        )

        self._match_rules.append(rule)

        return {
            'rule_id': rule.rule_id,
            'name': rule.name,
            'priority': rule.priority
        }


# Convenience functions
def import_statement(
    session: Session,
    bank_account_id: str,
    content: str,
    format: str = 'csv'
) -> Dict[str, Any]:
    """Import bank statement."""
    service = BankReconciliationService(session)
    if format.lower() == 'ofx':
        return service.import_ofx_statement(bank_account_id, content)
    return service.import_csv_statement(bank_account_id, content)


def start_reconciliation(
    session: Session,
    bank_account_id: str,
    statement_date: str,
    ending_balance: float
) -> Dict[str, Any]:
    """Start bank reconciliation."""
    service = BankReconciliationService(session)
    return service.start_reconciliation(bank_account_id, statement_date, ending_balance)
