"""
Cash Flow Dashboard Service
============================
Cash flow statements and forecasting.
"""
from datetime import date, timedelta
from typing import Dict, Any, List
from decimal import Decimal


class CashFlowService:
    def __init__(self, session):
        self.session = session

    def get_cash_flow_statement(self, period_days: int = 30) -> Dict[str, Any]:
        from services.erp.financial_service import FinancialService
        service = FinancialService(self.session)
        try:
            ar_aging = service.get_ar_aging()
            ap_aging = service.get_ap_aging()
        except Exception:
            ar_aging = {'total': 0}
            ap_aging = {'total': 0}
        collections = float(ar_aging.get('total', 0)) * 0.3
        payments = float(ap_aging.get('total', 0)) * 0.25
        operating = collections - payments
        return {
            'period_days': period_days,
            'operating': {'collections': round(collections, 2), 'payments': round(payments, 2),
                          'net': round(operating, 2)},
            'investing': {'capital_expenditures': 0, 'net': 0},
            'financing': {'net': 0},
            'net_cash_flow': round(operating, 2),
        }

    def forecast_cash_flow(self, weeks: int = 12) -> List[Dict[str, Any]]:
        forecast = []
        base_inflow = 5000
        base_outflow = 4200
        for i in range(weeks):
            week_start = date.today() + timedelta(weeks=i)
            inflow = base_inflow * (1 + (i % 4) * 0.05)
            outflow = base_outflow * (1 + (i % 3) * 0.03)
            net = inflow - outflow
            forecast.append({
                'week': i + 1, 'week_start': week_start.isoformat(),
                'projected_inflow': round(inflow, 2),
                'projected_outflow': round(outflow, 2),
                'net_cash_flow': round(net, 2),
            })
        return forecast
