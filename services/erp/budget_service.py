"""
Budget vs Actual Reporting Service
===================================
Budget creation and variance analysis against posted actuals.
"""
from datetime import date
from typing import Dict, Any, List
from decimal import Decimal

from sqlalchemy import func

from models.erp.financial import BudgetLine, GLAccount


class BudgetService:
    def __init__(self, session):
        self.session = session

    def create_budget(self, fiscal_year: int, lines: List[Dict[str, Any]]) -> Dict[str, Any]:
        fy_str = str(fiscal_year)

        # Delete existing budget lines for this fiscal year so create is idempotent
        self.session.query(BudgetLine).filter_by(fiscal_year=fy_str).delete()

        for line in lines:
            acct_number = line.get('account_number', '')
            amount = float(Decimal(str(line.get('amount', 0))))

            # Look up the GLAccount by account_number to get its UUID
            gl_account = self.session.query(GLAccount).filter_by(
                account_number=acct_number
            ).first()

            if gl_account is None:
                continue

            budget_line = BudgetLine(
                fiscal_year=fy_str,
                account_id=gl_account.id,
                amount=amount,
                notes=line.get('notes'),
            )
            self.session.add(budget_line)

        self.session.flush()
        return {'fiscal_year': fiscal_year, 'line_count': len(lines), 'status': 'created'}

    def get_budget_vs_actual(self, fiscal_year: int = None) -> Dict[str, Any]:
        fiscal_year = fiscal_year or date.today().year
        fy_str = str(fiscal_year)

        # Load budget totals per account_number from the database
        budget_rows = (
            self.session.query(
                GLAccount.account_number,
                func.sum(BudgetLine.amount).label('total_amount'),
            )
            .join(GLAccount, BudgetLine.account_id == GLAccount.id)
            .filter(BudgetLine.fiscal_year == fy_str)
            .group_by(GLAccount.account_number)
            .all()
        )
        budget_by_account = {
            row.account_number: Decimal(str(row.total_amount or 0))
            for row in budget_rows
        }

        from services.erp.financial_service import FinancialService
        fin_service = FinancialService(self.session)
        try:
            trial_balance = fin_service.get_trial_balance()
        except Exception:
            trial_balance = {'accounts': []}

        comparison = []
        for acct in trial_balance.get('accounts', []):
            acct_num = acct.get('account_number', '')
            actual = Decimal(str(acct.get('balance_debit', 0))) - Decimal(str(acct.get('balance_credit', 0)))
            budget = budget_by_account.get(acct_num, Decimal('0'))
            variance = actual - budget
            variance_pct = round(float(variance / budget * 100), 1) if budget else 0
            comparison.append({
                'account_number': acct_num,
                'account_name': acct.get('account_name', ''),
                'budget': float(budget), 'actual': float(actual),
                'variance': float(variance), 'variance_pct': variance_pct,
                'status': 'over' if variance > 0 else 'under' if variance < 0 else 'on_target',
            })

        total_budget_result = (
            self.session.query(func.sum(BudgetLine.amount))
            .filter(BudgetLine.fiscal_year == fy_str)
            .scalar()
        )
        total_budget = float(total_budget_result or 0)

        return {
            'fiscal_year': fiscal_year,
            'accounts': comparison,
            'total_budget': total_budget,
            'total_actual': float(sum(Decimal(str(a.get('actual', 0))) for a in comparison)),
        }
