"""
LEGO Factory v3 - Consolidated Demo Data
=========================================

This module contains all demo/mock data for development and testing purposes.
It should ONLY be imported when DEMO_MODE is explicitly enabled.

WARNING: This data is fake and should NEVER be returned in production.
Always check is_demo_mode_enabled() before using any data from this module.

Usage:
    from config.demo_mode import is_demo_mode_enabled

    if is_demo_mode_enabled():
        from api.routes.demo_data import get_demo_alarms
        return get_demo_alarms()
    else:
        return jsonify({'error': 'Service unavailable'}), 503
"""

from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional


# =============================================================================
# SCADA Demo Data
# =============================================================================

def get_demo_alarms() -> List[Dict[str, Any]]:
    """Return demo alarm data for SCADA."""
    return [
        {
            'alarm_id': 'ALM-001',
            'tag_name': 'ROBOT_XARM.TORQUE_J3',
            'priority': 'critical',
            'state': 'active_unack',
            'source': 'xArm Lite 6',
            'message': 'Joint 3 torque exceeded limit (15.2 Nm > 12.0 Nm)',
            'timestamp': '2024-01-15 14:32:15',
            'value': 15.2,
            'setpoint': 12.0,
            'engineering_unit': 'Nm',
        },
        {
            'alarm_id': 'ALM-002',
            'tag_name': 'PRINTER_01.TEMP_BED',
            'priority': 'critical',
            'state': 'active_unack',
            'source': 'Prusa MK4 #1',
            'message': 'Bed temperature runaway detected',
            'timestamp': '2024-01-15 14:28:42',
            'value': 125,
            'setpoint': 60,
            'engineering_unit': 'C',
        },
        {
            'alarm_id': 'ALM-003',
            'tag_name': 'PRINTER_01.FILAMENT',
            'priority': 'high',
            'state': 'active_ack',
            'source': 'Prusa MK4 #1',
            'message': 'Filament runout sensor triggered',
            'timestamp': '2024-01-15 14:15:33',
            'acknowledged_at': '2024-01-15 14:16:00',
            'acknowledged_by': 'operator',
        },
        {
            'alarm_id': 'ALM-004',
            'tag_name': 'CONVEYOR_A.BELT',
            'priority': 'high',
            'state': 'active_unack',
            'source': 'Conveyor-A',
            'message': 'Belt tension below threshold',
            'timestamp': '2024-01-15 13:45:21',
            'value': 45,
            'setpoint': 60,
            'engineering_unit': 'N',
        },
        {
            'alarm_id': 'ALM-005',
            'tag_name': 'PRINTER_02.TEMP_NOZZLE',
            'priority': 'medium',
            'state': 'active_ack',
            'source': 'Prusa MK4 #2',
            'message': 'Nozzle temperature deviation > 5C',
            'timestamp': '2024-01-15 12:30:00',
            'value': 215,
            'setpoint': 210,
            'engineering_unit': 'C',
            'acknowledged_at': '2024-01-15 12:32:00',
            'acknowledged_by': 'technician',
        },
    ]


# =============================================================================
# MES Demo Data
# =============================================================================

def get_demo_work_orders() -> Dict[str, Any]:
    """Return demo work orders for MES."""
    return {
        'work_orders': [
            {
                'id': '1',
                'work_order_id': 'WO-20240115-001',
                'description': 'Produce 500x 2x4 Red Bricks',
                'product_id': 'brick_2x4_red',
                'quantity_ordered': 500,
                'quantity_completed': 335,
                'status': 'in_progress',
                'priority': 3,
                'due_date': (datetime.utcnow() + timedelta(days=2)).isoformat(),
                'customer_id': 'CUST001',
            },
            {
                'id': '2',
                'work_order_id': 'WO-20240115-002',
                'description': 'Produce 1000x 2x2 Blue Bricks',
                'product_id': 'brick_2x2_blue',
                'quantity_ordered': 1000,
                'quantity_completed': 1000,
                'status': 'completed',
                'priority': 5,
                'due_date': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'customer_id': 'CUST002',
            },
            {
                'id': '3',
                'work_order_id': 'WO-20240116-001',
                'description': 'Produce 50x Custom Technic Gear 24T',
                'product_id': 'gear_24t',
                'quantity_ordered': 50,
                'quantity_completed': 0,
                'status': 'planned',
                'priority': 7,
                'due_date': (datetime.utcnow() + timedelta(days=5)).isoformat(),
                'customer_id': 'CUST001',
            },
        ],
        'count': 3,
    }


def get_demo_work_order_detail(work_order_id: str) -> Dict[str, Any]:
    """Return demo work order detail for MES."""
    return {
        'id': '1',
        'work_order_id': work_order_id,
        'description': 'Produce 500x 2x4 Red Bricks',
        'product_id': 'brick_2x4_red',
        'quantity_ordered': 500,
        'quantity_completed': 335,
        'status': 'in_progress',
        'priority': 3,
        'operations': [
            {'id': '1', 'operation_id': 'OP-001', 'sequence': 10, 'name': 'Slice Model', 'operation_type': 'design', 'status': 'completed'},
            {'id': '2', 'operation_id': 'OP-002', 'sequence': 20, 'name': '3D Print', 'operation_type': 'printing_fdm', 'status': 'running'},
            {'id': '3', 'operation_id': 'OP-003', 'sequence': 30, 'name': 'Quality Check', 'operation_type': 'inspection', 'status': 'pending'},
            {'id': '4', 'operation_id': 'OP-004', 'sequence': 40, 'name': 'Packaging', 'operation_type': 'packaging', 'status': 'pending'},
        ],
        'jobs': [
            {'id': '1', 'job_id': 'JOB-20240115-001', 'machine_id': 'prusa_mk4_1', 'status': 'completed', 'quantity_completed': 200},
            {'id': '2', 'job_id': 'JOB-20240115-002', 'machine_id': 'prusa_mk4_2', 'status': 'running', 'quantity_completed': 135},
            {'id': '3', 'job_id': 'JOB-20240115-003', 'machine_id': 'bambu_x1c', 'status': 'queued', 'quantity_completed': 0},
        ],
    }


def get_demo_jobs() -> Dict[str, Any]:
    """Return demo jobs for MES."""
    return {
        'jobs': [
            {
                'id': '1',
                'job_id': 'JOB-20240115-001',
                'work_order_id': '1',
                'machine_id': 'prusa_mk4_1',
                'status': 'completed',
                'quantity_planned': 200,
                'quantity_completed': 200,
                'scheduled_start': (datetime.utcnow() - timedelta(hours=8)).isoformat(),
                'actual_end': (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            },
            {
                'id': '2',
                'job_id': 'JOB-20240115-002',
                'work_order_id': '1',
                'machine_id': 'prusa_mk4_2',
                'status': 'running',
                'quantity_planned': 150,
                'quantity_completed': 135,
                'scheduled_start': (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                'actual_start': (datetime.utcnow() - timedelta(hours=5.5)).isoformat(),
            },
            {
                'id': '3',
                'job_id': 'JOB-20240115-003',
                'work_order_id': '1',
                'machine_id': 'bambu_x1c',
                'status': 'queued',
                'quantity_planned': 150,
                'quantity_completed': 0,
                'scheduled_start': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            },
        ],
        'count': 3,
    }


def get_demo_dispatch_queue(machine_id: str) -> Dict[str, Any]:
    """Return demo dispatch queue for MES."""
    return {
        'machine_id': machine_id,
        'queue': [
            {'job_id': 'JOB-20240115-003', 'work_order_id': 'WO-20240115-001', 'priority_score': 85.5, 'quantity': 150},
            {'job_id': 'JOB-20240116-001', 'work_order_id': 'WO-20240116-001', 'priority_score': 72.0, 'quantity': 25},
        ],
        'count': 2,
    }


def get_demo_oee(machine_id: Optional[str] = None) -> Dict[str, Any]:
    """Return demo OEE metrics for MES."""
    if machine_id:
        return {
            'machine_id': machine_id,
            'period': {'start': (datetime.utcnow() - timedelta(days=7)).isoformat(), 'end': datetime.utcnow().isoformat()},
            'oee': 0.852,
            'availability': 0.92,
            'performance': 0.95,
            'quality': 0.975,
            'planned_production_time': 168,
            'actual_production_time': 154.56,
            'total_count': 4500,
            'good_count': 4387,
        }
    return get_demo_oee_summary()


def get_demo_oee_summary() -> Dict[str, Any]:
    """Return demo OEE summary for MES."""
    return {
        'period': {'start': (datetime.utcnow() - timedelta(days=7)).isoformat(), 'end': datetime.utcnow().isoformat()},
        'overall_oee': 0.847,
        'machines': [
            {'machine_id': 'prusa_mk4_1', 'name': 'Prusa MK4 #1', 'oee': 0.89, 'availability': 0.94, 'performance': 0.97, 'quality': 0.98},
            {'machine_id': 'prusa_mk4_2', 'name': 'Prusa MK4 #2', 'oee': 0.85, 'availability': 0.91, 'performance': 0.96, 'quality': 0.97},
            {'machine_id': 'bambu_x1c', 'name': 'Bambu X1C', 'oee': 0.91, 'availability': 0.95, 'performance': 0.98, 'quality': 0.98},
            {'machine_id': 'niryo_ned2', 'name': 'Niryo Ned2', 'oee': 0.78, 'availability': 0.85, 'performance': 0.94, 'quality': 0.98},
            {'machine_id': 'xarm_lite6', 'name': 'xArm Lite 6', 'oee': 0.82, 'availability': 0.88, 'performance': 0.95, 'quality': 0.98},
        ],
    }


# =============================================================================
# ERP Demo Data
# =============================================================================

def get_demo_chart_of_accounts() -> Dict[str, Any]:
    """Return demo chart of accounts for ERP."""
    return {
        'accounts': [
            {'account_number': '1000', 'name': 'Cash', 'account_type': 'asset', 'is_active': True},
            {'account_number': '1100', 'name': 'Accounts Receivable', 'account_type': 'asset', 'is_active': True},
            {'account_number': '1200', 'name': 'Inventory', 'account_type': 'asset', 'is_active': True},
            {'account_number': '1500', 'name': 'Equipment', 'account_type': 'asset', 'is_active': True},
            {'account_number': '2000', 'name': 'Accounts Payable', 'account_type': 'liability', 'is_active': True},
            {'account_number': '3000', 'name': 'Retained Earnings', 'account_type': 'equity', 'is_active': True},
            {'account_number': '4000', 'name': 'Sales Revenue', 'account_type': 'revenue', 'is_active': True},
            {'account_number': '5000', 'name': 'Cost of Goods Sold', 'account_type': 'expense', 'is_active': True},
            {'account_number': '6000', 'name': 'Operating Expenses', 'account_type': 'expense', 'is_active': True},
        ],
        'count': 9,
    }


def get_demo_account_balance(account_number: str) -> Dict[str, Any]:
    """Return demo account balance for ERP."""
    balances = {
        '1000': 125000.00,
        '1100': 45000.00,
        '1200': 78000.00,
        '2000': -32000.00,
        '4000': -185000.00,
        '5000': 92000.00,
    }
    return {
        'account_number': account_number,
        'account_name': f'Account {account_number}',
        'as_of_date': date.today().isoformat(),
        'balance': balances.get(account_number, 0),
    }


def get_demo_journal_entries() -> Dict[str, Any]:
    """Return demo journal entries for ERP."""
    return {
        'journal_entries': [
            {
                'journal_number': 'JE-20240115-001',
                'status': 'posted',
                'journal_date': (date.today() - timedelta(days=5)).isoformat(),
                'description': 'Sales revenue for work order WO-20240110-001',
                'total_debit': 5000.00,
                'total_credit': 5000.00,
            },
            {
                'journal_number': 'JE-20240112-001',
                'status': 'posted',
                'journal_date': (date.today() - timedelta(days=8)).isoformat(),
                'description': 'Raw material purchase',
                'total_debit': 2500.00,
                'total_credit': 2500.00,
            },
        ],
        'count': 2,
    }


def get_demo_ap_invoices() -> Dict[str, Any]:
    """Return demo AP invoices for ERP."""
    return {
        'invoices': [
            {
                'invoice_number': 'AP-20240115-001',
                'vendor_invoice_number': 'INV-12345',
                'vendor_id': 'V001',
                'status': 'approved',
                'invoice_date': (date.today() - timedelta(days=10)).isoformat(),
                'due_date': (date.today() + timedelta(days=20)).isoformat(),
                'total': 3500.00,
                'balance_due': 3500.00,
            },
            {
                'invoice_number': 'AP-20240110-001',
                'vendor_invoice_number': 'INV-12340',
                'vendor_id': 'V002',
                'status': 'paid',
                'invoice_date': (date.today() - timedelta(days=15)).isoformat(),
                'due_date': (date.today() + timedelta(days=15)).isoformat(),
                'total': 1200.00,
                'balance_due': 0.00,
            },
        ],
        'count': 2,
    }


def get_demo_ar_invoices() -> Dict[str, Any]:
    """Return demo AR invoices for ERP."""
    return {
        'invoices': [
            {
                'invoice_number': 'INV-20240115-001',
                'customer_id': 'C001',
                'status': 'sent',
                'invoice_date': (date.today() - timedelta(days=5)).isoformat(),
                'due_date': (date.today() + timedelta(days=25)).isoformat(),
                'total': 8500.00,
                'balance_due': 8500.00,
            },
            {
                'invoice_number': 'INV-20240108-001',
                'customer_id': 'C002',
                'status': 'partially_paid',
                'invoice_date': (date.today() - timedelta(days=12)).isoformat(),
                'due_date': (date.today() + timedelta(days=18)).isoformat(),
                'total': 5000.00,
                'balance_due': 2500.00,
            },
        ],
        'count': 2,
    }


def get_demo_ap_aging() -> Dict[str, Any]:
    """Return demo AP aging for ERP."""
    return {
        'current': 3500.00,
        '1_30': 2100.00,
        '31_60': 800.00,
        '61_90': 0.00,
        'over_90': 0.00,
        'total': 6400.00,
    }


def get_demo_ar_aging() -> Dict[str, Any]:
    """Return demo AR aging for ERP."""
    return {
        'current': 11000.00,
        '1_30': 4500.00,
        '31_60': 1200.00,
        '61_90': 500.00,
        'over_90': 0.00,
        'total': 17200.00,
    }


def get_demo_trial_balance() -> Dict[str, Any]:
    """Return demo trial balance for ERP."""
    return {
        'as_of_date': date.today().isoformat(),
        'accounts': [
            {'account_number': '1000', 'account_name': 'Cash', 'account_type': 'asset', 'debit_balance': 125000.00, 'credit_balance': 0.00},
            {'account_number': '1100', 'account_name': 'Accounts Receivable', 'account_type': 'asset', 'debit_balance': 45000.00, 'credit_balance': 0.00},
            {'account_number': '1200', 'account_name': 'Inventory', 'account_type': 'asset', 'debit_balance': 78000.00, 'credit_balance': 0.00},
            {'account_number': '1500', 'account_name': 'Equipment', 'account_type': 'asset', 'debit_balance': 50000.00, 'credit_balance': 0.00},
            {'account_number': '2000', 'account_name': 'Accounts Payable', 'account_type': 'liability', 'debit_balance': 0.00, 'credit_balance': 32000.00},
            {'account_number': '3000', 'account_name': 'Retained Earnings', 'account_type': 'equity', 'debit_balance': 0.00, 'credit_balance': 81000.00},
            {'account_number': '4000', 'account_name': 'Sales Revenue', 'account_type': 'revenue', 'debit_balance': 0.00, 'credit_balance': 185000.00},
            {'account_number': '5000', 'account_name': 'Cost of Goods Sold', 'account_type': 'expense', 'debit_balance': 0.00, 'credit_balance': 0.00},
            {'account_number': '6000', 'account_name': 'Operating Expenses', 'account_type': 'expense', 'debit_balance': 0.00, 'credit_balance': 0.00},
        ],
        'total_debit': 298000.00,
        'total_credit': 298000.00,
        'is_balanced': True,
    }


def get_demo_income_statement() -> Dict[str, Any]:
    """Return demo income statement for ERP."""
    today = date.today()
    return {
        'period': {
            'start_date': date(today.year, today.month, 1).isoformat(),
            'end_date': today.isoformat(),
        },
        'revenue': 185000.00,
        'cost_of_goods_sold': 92000.00,
        'gross_profit': 93000.00,
        'operating_expenses': 45000.00,
        'operating_income': 48000.00,
        'other_income': 500.00,
        'other_expenses': 1200.00,
        'net_income': 47300.00,
    }


def get_demo_financial_dashboard() -> Dict[str, Any]:
    """Return demo financial dashboard for ERP."""
    today = date.today()
    return {
        'period': today.strftime('%B %Y'),
        'summary': {
            'cash_balance': 125000.00,
            'ar_balance': 45000.00,
            'ap_balance': 32000.00,
            'net_working_capital': 138000.00,
        },
        'income': {
            'revenue_mtd': 185000.00,
            'revenue_ytd': 1450000.00,
            'gross_margin': 0.503,
            'net_income_mtd': 47300.00,
        },
        'ratios': {
            'current_ratio': 7.75,
            'quick_ratio': 5.31,
            'ar_turnover': 4.1,
            'ap_turnover': 5.8,
        },
        'trends': {
            'revenue_trend': [145000, 152000, 168000, 175000, 185000],
            'expense_trend': [72000, 76000, 84000, 87000, 93000],
            'months': ['Sep', 'Oct', 'Nov', 'Dec', 'Jan'],
        },
    }


def get_demo_partners() -> Dict[str, Any]:
    """Return demo partners for ERP."""
    return {
        'partners': [
            {'partner_id': 'CUST001', 'name': 'Brick Builders Inc', 'partner_type': 'customer', 'status': 'active'},
            {'partner_id': 'CUST002', 'name': 'LEGO World Shop', 'partner_type': 'customer', 'status': 'active'},
            {'partner_id': 'VEND001', 'name': 'Filament Supply Co', 'partner_type': 'vendor', 'status': 'active'},
        ],
        'count': 3
    }


# =============================================================================
# QMS Demo Data
# =============================================================================

def get_demo_documents() -> Dict[str, Any]:
    """Return demo documents for QMS."""
    return {
        'documents': [
            {
                'document_number': 'SOP-20240101-001',
                'title': 'Standard Operating Procedure: 3D Printer Setup',
                'document_type': 'procedure',
                'status': 'effective',
                'revision': 'B',
                'effective_date': (date.today() - timedelta(days=30)).isoformat(),
                'owner_id': 'W002',
            },
            {
                'document_number': 'SPEC-20240105-001',
                'title': 'Specification: LEGO Brick Dimensional Tolerances',
                'document_type': 'specification',
                'status': 'effective',
                'revision': 'A',
                'effective_date': (date.today() - timedelta(days=15)).isoformat(),
                'owner_id': 'W002',
            },
            {
                'document_number': 'FRM-20240110-001',
                'title': 'Form: Production Quality Checklist',
                'document_type': 'form',
                'status': 'pending_approval',
                'revision': 'A',
                'effective_date': None,
                'owner_id': 'W001',
            },
            {
                'document_number': 'WI-20240112-001',
                'title': 'Work Instruction: Printer Calibration',
                'document_type': 'procedure',
                'status': 'draft',
                'revision': 'A',
                'effective_date': None,
                'owner_id': 'W002',
            },
        ],
        'count': 4,
    }


def get_demo_document_detail(document_number: str) -> Dict[str, Any]:
    """Return demo document detail for QMS."""
    return {
        'document_number': document_number,
        'title': 'Standard Operating Procedure: 3D Printer Setup',
        'description': 'This SOP describes the standard procedure for setting up and initializing 3D printers.',
        'document_type': 'procedure',
        'status': 'effective',
        'revision': 'B',
        'effective_date': (date.today() - timedelta(days=30)).isoformat(),
        'author_id': 'W002',
        'owner_id': 'W002',
        'department': 'Production',
        'files': [
            {'filename': 'SOP_3D_Printer_Setup_v2.pdf', 'file_type': 'application/pdf', 'is_primary': True},
        ],
        'revisions': [
            {'revision': 'B', 'revision_date': (date.today() - timedelta(days=30)).isoformat(), 'change_summary': 'Added Bambu X1C setup procedure', 'revised_by': 'W002'},
            {'revision': 'A', 'revision_date': (date.today() - timedelta(days=90)).isoformat(), 'change_summary': 'Initial release', 'revised_by': 'W002'},
        ],
        'approvals': [
            {'approval_type': 'review', 'approver_id': 'W001', 'status': 'approved', 'completed_date': (date.today() - timedelta(days=32)).isoformat()},
            {'approval_type': 'approve', 'approver_id': 'W002', 'status': 'approved', 'completed_date': (date.today() - timedelta(days=31)).isoformat()},
        ],
    }


def get_demo_ncrs() -> Dict[str, Any]:
    """Return demo NCRs for QMS."""
    return {
        'ncrs': [
            {
                'ncr_number': 'NCR-20240115-001',
                'description': 'Dimensional variation in brick studs - out of tolerance',
                'severity': 'minor',
                'source': 'Production inspection',
                'status': 'under_investigation',
                'created_at': (datetime.utcnow() - timedelta(days=2)).isoformat(),
            },
            {
                'ncr_number': 'NCR-20240113-001',
                'description': 'Print layer adhesion failure',
                'severity': 'major',
                'source': 'Customer complaint',
                'status': 'closed',
                'created_at': (datetime.utcnow() - timedelta(days=4)).isoformat(),
            },
            {
                'ncr_number': 'NCR-20240110-001',
                'description': 'Incorrect color in finished batch',
                'severity': 'minor',
                'source': 'Final inspection',
                'status': 'closed',
                'created_at': (datetime.utcnow() - timedelta(days=7)).isoformat(),
            },
        ],
        'count': 3,
    }


def get_demo_capas() -> Dict[str, Any]:
    """Return demo CAPAs for QMS."""
    return {
        'capas': [
            {
                'capa_number': 'CAPA-20240114-001',
                'capa_type': 'corrective',
                'description': 'Improve printer calibration procedure',
                'source_ncr': 'NCR-20240113-001',
                'status': 'implementing',
                'due_date': (date.today() + timedelta(days=30)).isoformat(),
            },
            {
                'capa_number': 'CAPA-20240108-001',
                'capa_type': 'preventive',
                'description': 'Add color verification step to receiving inspection',
                'source_ncr': 'NCR-20240110-001',
                'status': 'effectiveness_check',
                'due_date': (date.today() + timedelta(days=15)).isoformat(),
            },
        ],
        'count': 2,
    }


# =============================================================================
# CMMS Demo Data
# =============================================================================

def get_demo_assets() -> Dict[str, Any]:
    """Return demo assets for CMMS."""
    return {
        'assets': [
            {
                'asset_id': 'PRINTER-001',
                'name': 'Prusa MK4 #1',
                'status': 'operational',
                'criticality': 'essential',
                'location_id': 'CELL-1',
                'manufacturer': 'Prusa Research',
                'serial_number': 'PRU2024001',
            },
            {
                'asset_id': 'PRINTER-002',
                'name': 'Prusa MK4 #2',
                'status': 'operational',
                'criticality': 'essential',
                'location_id': 'CELL-1',
                'manufacturer': 'Prusa Research',
                'serial_number': 'PRU2024002',
            },
            {
                'asset_id': 'ROBOT-001',
                'name': 'Niryo Ned2',
                'status': 'maintenance',
                'criticality': 'important',
                'location_id': 'CELL-1',
                'manufacturer': 'Niryo',
                'serial_number': 'NIR2024001',
            },
        ],
        'count': 3,
    }


def get_demo_asset(asset_id: str) -> Optional[Dict[str, Any]]:
    """Return demo asset for CMMS."""
    assets = {
        'PRINTER-001': {
            'asset_id': 'PRINTER-001',
            'name': 'Prusa MK4 #1',
            'description': '3D printer for LEGO brick production',
            'status': 'operational',
            'criticality': 'essential',
            'location_id': 'CELL-1',
            'manufacturer': 'Prusa Research',
            'model_number': 'MK4',
            'serial_number': 'PRU2024001',
            'installation_date': '2024-01-15',
        },
    }
    return assets.get(asset_id)


def get_demo_meters(asset_id: str) -> Dict[str, Any]:
    """Return demo meters for CMMS."""
    return {
        'asset_id': asset_id,
        'meters': [
            {
                'meter_id': f'{asset_id}-RUNTIME',
                'name': 'Runtime Hours',
                'meter_type': 'continuous',
                'unit_of_measure': 'hours',
                'last_reading': 1250.5,
                'last_reading_date': '2024-01-18T10:00:00Z',
            },
            {
                'meter_id': f'{asset_id}-CYCLES',
                'name': 'Print Cycles',
                'meter_type': 'continuous',
                'unit_of_measure': 'cycles',
                'last_reading': 432,
                'last_reading_date': '2024-01-18T10:00:00Z',
            },
        ],
        'count': 2,
    }


def get_demo_work_orders_cmms() -> Dict[str, Any]:
    """Return demo work orders for CMMS."""
    return {
        'work_orders': [
            {
                'wo_number': 'MWO-20240118-A1B2C3',
                'description': 'Replace extruder nozzle',
                'wo_type': 'preventive',
                'status': 'scheduled',
                'priority': 'medium',
                'asset_id': 'PRINTER-001',
                'estimated_hours': 1.5,
            },
            {
                'wo_number': 'MWO-20240117-D4E5F6',
                'description': 'Calibrate robot arm',
                'wo_type': 'corrective',
                'status': 'in_progress',
                'priority': 'high',
                'asset_id': 'ROBOT-001',
                'estimated_hours': 2.0,
            },
        ],
        'count': 2,
    }


def get_demo_work_order_cmms(wo_number: str) -> Optional[Dict[str, Any]]:
    """Return demo work order for CMMS."""
    work_orders = {
        'MWO-20240118-A1B2C3': {
            'wo_number': 'MWO-20240118-A1B2C3',
            'description': 'Replace extruder nozzle',
            'wo_type': 'preventive',
            'status': 'scheduled',
            'priority': 'medium',
            'asset_id': 'PRINTER-001',
            'asset_name': 'Prusa MK4 #1',
            'target_start': '2024-01-20T09:00:00Z',
            'target_completion': '2024-01-20T12:00:00Z',
            'estimated_hours': 1.5,
            'instructions': '1. Heat hotend to 260C\n2. Remove old nozzle\n3. Install new nozzle\n4. Perform calibration print',
        },
    }
    return work_orders.get(wo_number)


def get_demo_pm_schedules() -> Dict[str, Any]:
    """Return demo PM schedules for CMMS."""
    return {
        'pm_schedules': [
            {
                'pm_id': 'PM-PRINTER-NOZZLE',
                'name': 'Nozzle Replacement',
                'asset_id': 'PRINTER-001',
                'trigger_type': 'calendar',
                'frequency_days': 90,
                'next_due_date': '2024-01-20',
                'priority': 'medium',
                'is_active': True,
            },
            {
                'pm_id': 'PM-ROBOT-CALIBRATION',
                'name': 'Joint Calibration',
                'asset_id': 'ROBOT-001',
                'trigger_type': 'meter',
                'meter_interval': 500,
                'next_due_date': '2024-01-25',
                'priority': 'high',
                'is_active': True,
            },
        ],
        'count': 2,
    }


def get_demo_pm_compliance() -> Dict[str, Any]:
    """Return demo PM compliance for CMMS."""
    return {
        'period_days': 30,
        'total_due': 12,
        'completed_on_time': 10,
        'compliance_rate': 83.33,
    }


def get_demo_backlog() -> Dict[str, Any]:
    """Return demo backlog for CMMS."""
    return {
        'by_status': {
            'draft': 2,
            'approved': 3,
            'scheduled': 5,
            'in_progress': 2,
            'waiting_parts': 1,
        },
        'by_priority': {
            'critical': 1,
            'high': 3,
            'medium': 6,
            'low': 3,
        },
        'overdue_count': 2,
        'total_estimated_hours': 45.5,
        'total_work_orders': 13,
    }


def get_demo_spares() -> Dict[str, Any]:
    """Return demo spares for CMMS."""
    return {
        'spares': [
            {
                'spare_id': 'SPARE-NOZZLE-04',
                'name': '0.4mm Brass Nozzle',
                'quantity_on_hand': 15,
                'reorder_point': 5,
                'unit_cost': 8.50,
            },
            {
                'spare_id': 'SPARE-BELT-GT2',
                'name': 'GT2 Timing Belt (1m)',
                'quantity_on_hand': 8,
                'reorder_point': 3,
                'unit_cost': 12.00,
            },
        ],
        'count': 2,
    }
