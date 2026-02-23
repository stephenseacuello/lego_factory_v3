"""
Tests for New MES & ERP Services
=================================
Comprehensive tests for all newly created services.
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# MES Machine Feedback Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMachineFeedbackService:
    """Tests for MES Machine Feedback Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.mes.machine_feedback_service import (
            MachineFeedbackService,
            MachineEventType,
            process_machine_event,
            get_pending_completions
        )
        assert MachineFeedbackService is not None
        assert MachineEventType is not None

    def test_event_types_enum(self):
        """Test event types are defined."""
        from services.mes.machine_feedback_service import MachineEventType

        assert MachineEventType.JOB_COMPLETE == 'job_complete'
        assert MachineEventType.JOB_STARTED == 'job_started'
        assert MachineEventType.PARTIAL_COMPLETE == 'partial_complete'
        assert MachineEventType.SCRAP_REPORTED == 'scrap_reported'
        assert MachineEventType.MACHINE_FAULT == 'machine_fault'

    def test_service_init(self):
        """Test service initialization."""
        from services.mes.machine_feedback_service import MachineFeedbackService

        mock_session = Mock()
        service = MachineFeedbackService(mock_session)
        assert service.session == mock_session

    def test_process_event_requires_machine_id(self):
        """Test that machine_id is required."""
        from services.mes.machine_feedback_service import MachineFeedbackService

        mock_session = Mock()
        service = MachineFeedbackService(mock_session)

        result = service.process_machine_event({})
        assert result['success'] is False
        assert 'machine_id' in result['error']


# ─────────────────────────────────────────────────────────────────────────────
# MES Scheduling Service Tests (Skill-Based)
# ─────────────────────────────────────────────────────────────────────────────

class TestSchedulingServiceSkills:
    """Tests for skill-based scheduling constraints."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.mes.scheduling_service import (
            SchedulingService,
            ScheduleJob,
            Worker,
            Machine,
            ScheduledJob
        )
        assert SchedulingService is not None
        assert Worker is not None

    def test_schedule_job_dataclass(self):
        """Test ScheduleJob has skill fields."""
        from services.mes.scheduling_service import ScheduleJob

        job = ScheduleJob(
            job_id='JOB-001',
            work_order_id='WO-001',
            duration_minutes=60,
            required_skill='CNC_OPERATION',
            required_skill_level=3
        )
        assert job.required_skill == 'CNC_OPERATION'
        assert job.required_skill_level == 3

    def test_worker_dataclass(self):
        """Test Worker dataclass."""
        from services.mes.scheduling_service import Worker

        worker = Worker(
            worker_id='W001',
            name='John Smith',
            skills={'CNC_OPERATION': 4, 'WELDING': 2},
            efficiency=0.95
        )
        assert worker.skills['CNC_OPERATION'] == 4
        assert worker.efficiency == 0.95

    def test_get_eligible_workers(self):
        """Test _get_eligible_workers method."""
        from services.mes.scheduling_service import SchedulingService, Worker

        service = SchedulingService()
        workers = [
            Worker(worker_id='W1', name='Alice', skills={'CNC': 4, 'FDM': 2}),
            Worker(worker_id='W2', name='Bob', skills={'CNC': 2, 'WELDING': 5}),
            Worker(worker_id='W3', name='Carol', skills={'FDM': 5}),
        ]

        eligible = service._get_eligible_workers(workers, 'CNC', required_level=3)
        assert len(eligible) == 1
        assert eligible[0].worker_id == 'W1'

    def test_scheduled_job_has_worker_id(self):
        """Test ScheduledJob has worker_id field."""
        from services.mes.scheduling_service import ScheduledJob

        sj = ScheduledJob(
            job_id='JOB-001',
            machine_id='M001',
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            worker_id='W001'
        )
        assert sj.worker_id == 'W001'


# ─────────────────────────────────────────────────────────────────────────────
# MES Dispatch Service Tests (Rule Engine)
# ─────────────────────────────────────────────────────────────────────────────

class TestDispatchRuleEngine:
    """Tests for configurable dispatch rules."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.mes.dispatch_service import (
            DispatchService,
            DispatchRuleConfig,
            DispatchResult
        )
        assert DispatchService is not None
        assert DispatchRuleConfig is not None

    def test_dispatch_rule_config(self):
        """Test DispatchRuleConfig defaults."""
        from services.mes.dispatch_service import DispatchRuleConfig

        assert DispatchRuleConfig.DEFAULT_RULES['_default'] == 'wspt'
        assert DispatchRuleConfig.DEFAULT_RULES['fdm'] == 'setup_min'
        assert 'balanced' in DispatchRuleConfig.COMPOSITE_CONFIGS

    def test_get_machine_type(self):
        """Test _get_machine_type method."""
        from services.mes.dispatch_service import DispatchService

        mock_session = Mock()
        service = DispatchService(mock_session)

        assert service._get_machine_type('bambu-ps1') == 'fdm'
        assert service._get_machine_type('creality-cr30') == 'fdm'
        assert service._get_machine_type('bantam-cnc') == 'cnc'
        assert service._get_machine_type('unknown-machine') == '_default'

    def test_set_machine_dispatch_rule(self):
        """Test set_machine_dispatch_rule method."""
        from services.mes.dispatch_service import DispatchService

        mock_session = Mock()
        service = DispatchService(mock_session)

        result = service.set_machine_dispatch_rule('test-machine', 'edd')
        assert result['success'] is True
        assert result['rule_name'] == 'edd'

        # Verify rule is cached
        assert service._rule_cache['test-machine'] == 'edd'

    def test_invalid_rule_rejected(self):
        """Test that invalid rules are rejected."""
        from services.mes.dispatch_service import DispatchService

        mock_session = Mock()
        service = DispatchService(mock_session)

        result = service.set_machine_dispatch_rule('test-machine', 'invalid_rule')
        assert result['success'] is False
        assert 'Invalid rule' in result['error']


# ─────────────────────────────────────────────────────────────────────────────
# OEE Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOEEService:
    """Tests for OEE Service enhancements."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.mes.oee_service import (
            OEEService,
            SixBigLosses,
            OEEWaterfall,
            RealTimeOEE
        )
        assert OEEService is not None
        assert SixBigLosses.EQUIPMENT_FAILURE.value == 'equipment_failure'

    def test_six_big_losses_enum(self):
        """Test six big losses enum values."""
        from services.mes.oee_service import SixBigLosses

        assert SixBigLosses.EQUIPMENT_FAILURE.value == 'equipment_failure'
        assert SixBigLosses.SETUP_ADJUSTMENT.value == 'setup_adjustment'
        assert SixBigLosses.IDLING_MINOR_STOPS.value == 'idling_minor_stops'
        assert SixBigLosses.REDUCED_SPEED.value == 'reduced_speed'
        assert SixBigLosses.PROCESS_DEFECTS.value == 'process_defects'
        assert SixBigLosses.STARTUP_REJECTS.value == 'startup_rejects'

    def test_oee_waterfall_dataclass(self):
        """Test OEE waterfall dataclass."""
        from services.mes.oee_service import OEEWaterfall

        waterfall = OEEWaterfall(
            scheduled_time=480,
            planned_downtime=30,
            available_time=450,
            equipment_failure_loss=20,
            setup_loss=15,
            operating_time=415,
            idling_stops_loss=10,
            speed_loss=5,
            net_operating_time=400,
            defect_loss=8,
            startup_loss=2,
            value_operating_time=390,
            availability=0.92,
            performance=0.96,
            quality=0.98,
            oee=0.86
        )

        result = waterfall.to_dict()
        assert result['scheduled_time'] == 480
        assert result['availability'] == 0.92
        assert result['losses']['equipment_failure'] == 20

    def test_realtime_oee_dataclass(self):
        """Test real-time OEE dataclass."""
        from services.mes.oee_service import RealTimeOEE

        now = datetime.utcnow()
        rt_oee = RealTimeOEE(
            machine_id='MACHINE-001',
            timestamp=now,
            period_start=now - timedelta(hours=1),
            period_end=now,
            availability=0.95,
            performance=0.90,
            quality=0.99,
            oee=0.846,
            total_count=100,
            good_count=99,
            reject_count=1,
            scheduled_time=60,
            operating_time=57,
            downtime=3,
            actual_cycle_time=34.2,
            ideal_cycle_time=30,
            is_running=True,
            current_state='running'
        )

        result = rt_oee.to_dict()
        assert result['machine_id'] == 'MACHINE-001'
        assert result['oee'] == 0.846
        assert result['is_running'] is True


# ─────────────────────────────────────────────────────────────────────────────
# MES Material Planner Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMaterialPlannerService:
    """Tests for Material Shortage Resolution Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.mes.material_planner_service import (
            MaterialPlannerService,
            ShortageStatus,
            ResolutionType,
            MaterialShortage,
            AlternativeMaterial
        )
        assert MaterialPlannerService is not None
        assert ShortageStatus.DETECTED == 'detected'

    def test_service_init(self):
        """Test service initialization."""
        from services.mes.material_planner_service import MaterialPlannerService

        service = MaterialPlannerService()
        assert service._shortages == {}
        assert service._compatibility_map is not None

    def test_compatibility_map(self):
        """Test material compatibility map."""
        from services.mes.material_planner_service import MaterialPlannerService

        service = MaterialPlannerService()

        # PLA should have alternatives
        assert 'PLA' in service._compatibility_map
        alternatives = service._compatibility_map['PLA']
        assert len(alternatives) > 0

    def test_suggest_alternatives(self):
        """Test suggest_alternatives method."""
        from services.mes.material_planner_service import MaterialPlannerService

        service = MaterialPlannerService()
        alternatives = service.suggest_alternatives('PLA', 100)

        # Should return list of alternatives
        assert isinstance(alternatives, list)

    def test_check_material_availability(self):
        """Test check_material_availability method."""
        from services.mes.material_planner_service import MaterialPlannerService

        service = MaterialPlannerService()

        # PLA has demo inventory of 50
        result = service.check_material_availability('PLA', 30)
        assert result['available'] is True

        # Request more than available
        result = service.check_material_availability('PLA', 100)
        assert result['available'] is False
        assert 'shortage' in result

    def test_generate_recommendations(self):
        """Test that recommendations are generated."""
        from services.mes.material_planner_service import MaterialPlannerService, MaterialShortage, ShortageStatus
        from decimal import Decimal

        service = MaterialPlannerService()
        shortage = MaterialShortage(
            shortage_id='TEST-001',
            material_id='PLA',
            material_name='PLA Filament',
            required_quantity=Decimal('100'),
            available_quantity=Decimal('50'),
            shortage_quantity=Decimal('50'),
            job_id='JOB-001',
            work_order_id='WO-001',
            required_date=date.today()
        )

        alternatives = service.suggest_alternatives('PLA', 50)
        recommendations = service._generate_recommendations(shortage, alternatives, None)

        assert isinstance(recommendations, list)


# ─────────────────────────────────────────────────────────────────────────────
# MES SPC Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSPCService:
    """Tests for Statistical Process Control Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.mes.spc_service import (
            SPCService,
            ChartType,
            AlertLevel,
            ViolationType,
            CHART_CONSTANTS
        )
        assert SPCService is not None
        assert ChartType.XBAR_R == 'xbar_r'
        assert CHART_CONSTANTS is not None

    def test_chart_constants(self):
        """Test chart constants are defined."""
        from services.mes.spc_service import CHART_CONSTANTS

        # Constants for n=5 should exist
        assert 5 in CHART_CONSTANTS
        constants = CHART_CONSTANTS[5]
        assert 'd2' in constants
        assert 'A2' in constants
        assert 'D3' in constants
        assert 'D4' in constants

    def test_record_measurement(self):
        """Test recording SPC measurements."""
        from services.mes.spc_service import SPCService

        service = SPCService()
        result = service.record_measurement(
            characteristic_id='CHAR-001',
            values=[10.1, 10.2, 10.0, 10.3, 10.1],
            machine_id='M001'
        )

        assert 'point_id' in result
        assert 'mean' in result
        assert result['mean'] is not None

    def test_set_specification_limits(self):
        """Test setting specification limits."""
        from services.mes.spc_service import SPCService

        service = SPCService()
        result = service.set_specification_limits(
            characteristic_id='CHAR-001',
            usl=10.5,
            target=10.0,
            lsl=9.5
        )

        assert result['usl'] == 10.5
        assert result['target'] == 10.0
        assert result['lsl'] == 9.5

    def test_calculate_capability_insufficient_data(self):
        """Test capability calculation with insufficient data."""
        from services.mes.spc_service import SPCService

        service = SPCService()
        service.set_specification_limits('CHAR-001', usl=10.5, target=10.0, lsl=9.5)

        # Only a few points
        for i in range(5):
            service.record_measurement('CHAR-001', [10.0 + i * 0.01], 'M001')

        result = service.calculate_capability('CHAR-001', min_points=30)
        assert 'error' in result
        assert 'Insufficient' in result['error']

    def test_western_electric_rules(self):
        """Test violation types are defined."""
        from services.mes.spc_service import ViolationType

        assert ViolationType.BEYOND_3SIGMA == 'beyond_3sigma'
        assert ViolationType.EIGHT_CONSECUTIVE_ONE_SIDE == 'eight_consecutive'

    def test_service_with_load_from_db_flag(self):
        """Test service initialization with database flag."""
        from services.mes.spc_service import SPCService

        # Without session, should still work
        service = SPCService(session=None, load_from_db=False)
        assert service._data == {}

    def test_get_control_chart_data(self):
        """Test getting control chart data."""
        from services.mes.spc_service import SPCService

        service = SPCService()

        # Record enough data
        for i in range(25):
            service.record_measurement(
                characteristic_id='CHAR-002',
                values=[10.0 + (i % 5) * 0.1],
                machine_id='M001'
            )

        result = service.get_control_chart_data('CHAR-002')

        assert 'points' in result
        assert result['point_count'] == 25

    def test_load_historical_data_no_session(self):
        """Test load_historical_data returns empty without session."""
        from services.mes.spc_service import SPCService

        service = SPCService(session=None)
        result = service.load_historical_data('CHAR-001')
        assert result == []

    def test_get_capability_trend_no_session(self):
        """Test get_capability_trend returns error without session."""
        from services.mes.spc_service import SPCService

        service = SPCService(session=None)
        result = service.get_capability_trend('CHAR-001')
        assert 'error' in result

    def test_get_charts_no_session(self):
        """Test get_charts returns empty without session."""
        from services.mes.spc_service import SPCService

        service = SPCService(session=None)
        result = service.get_charts()
        assert result == []

    def test_create_chart_no_session(self):
        """Test create_chart returns error without session."""
        from services.mes.spc_service import SPCService

        service = SPCService(session=None)
        result = service.create_chart(
            chart_id='TEST-001',
            name='Test Chart',
            characteristic='dimension_x'
        )
        assert 'error' in result


# ─────────────────────────────────────────────────────────────────────────────
# ERP Tax Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTaxService:
    """Tests for ERP Tax Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.erp.tax_service import (
            TaxService,
            TaxType,
            TaxCategory,
            TaxJurisdiction,
            TaxRate
        )
        assert TaxService is not None
        assert TaxType.SALES_TAX == 'sales_tax'

    def test_default_jurisdictions(self):
        """Test default jurisdictions are loaded."""
        from services.erp.tax_service import TaxService

        service = TaxService()
        # Should have US states
        assert len(service._jurisdictions) > 0

    def test_get_applicable_rate(self):
        """Test get_applicable_rate method."""
        from services.erp.tax_service import TaxService, TaxType, TaxCategory

        service = TaxService()
        rate = service.get_applicable_rate(
            jurisdiction_code='US-CA',
            tax_type=TaxType.SALES_TAX,
            tax_category=TaxCategory.STANDARD
        )

        assert rate is not None
        assert rate.rate == Decimal('7.25')

    def test_calculate_tax(self):
        """Test tax calculation."""
        from services.erp.tax_service import TaxService

        service = TaxService()
        result = service.calculate_tax(
            line_items=[{'amount': 100.0}],
            ship_to_jurisdiction='US-CA',
            customer_id='CUST001'
        )

        assert result.total_tax > 0
        assert len(result.tax_lines) > 0
        assert result.subtotal == Decimal('100.0')

    def test_tax_exemption(self):
        """Test customer tax exemption."""
        from services.erp.tax_service import TaxService, TaxExemption, TaxType

        service = TaxService()

        # Add exemption using the actual API
        exemption = TaxExemption(
            entity_id='CUST-EXEMPT',
            entity_type='customer',
            jurisdiction_code='US-CA',
            tax_type=TaxType.SALES_TAX,
            exemption_number='EX-12345',
            effective_date=date.today(),
            expiry_date=date(2027, 12, 31),
            reason='resale'
        )
        result = service.add_exemption(exemption)

        assert result['success'] is True

        # Verify exemption check returns the exemption
        found = service.check_exemption('CUST-EXEMPT', 'customer', 'US-CA', TaxType.SALES_TAX)
        assert found is not None
        assert found.exemption_number == 'EX-12345'


# ─────────────────────────────────────────────────────────────────────────────
# ERP Currency Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCurrencyService:
    """Tests for ERP Multi-Currency Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.erp.currency_service import (
            CurrencyService,
            CurrencyCode,
            ExchangeRateType,
            ConversionResult
        )
        assert CurrencyService is not None
        assert CurrencyCode.USD == 'USD'

    def test_default_rates(self):
        """Test default exchange rates exist."""
        from services.erp.currency_service import CurrencyService

        service = CurrencyService()
        assert 'USD' in service._default_rates
        assert 'EUR' in service._default_rates
        assert service._default_rates['USD'] == Decimal('1.0000')

    def test_same_currency_conversion(self):
        """Test converting same currency."""
        from services.erp.currency_service import CurrencyService

        service = CurrencyService()
        result = service.convert(
            amount=Decimal('100'),
            from_currency='USD',
            to_currency='USD'
        )

        assert result.converted_amount == Decimal('100')
        assert result.exchange_rate == Decimal('1.0000')

    def test_usd_to_eur_conversion(self):
        """Test USD to EUR conversion."""
        from services.erp.currency_service import CurrencyService

        service = CurrencyService()
        result = service.convert(
            amount=Decimal('100'),
            from_currency='USD',
            to_currency='EUR'
        )

        assert result.converted_amount > 0
        assert result.target_currency == 'EUR'

    def test_cross_rate_calculation(self):
        """Test cross rate calculation."""
        from services.erp.currency_service import CurrencyService

        service = CurrencyService()
        rate = service._calculate_cross_rate('EUR', 'GBP')

        assert rate is not None
        assert rate > 0

    def test_gain_loss_calculation(self):
        """Test currency gain/loss calculation."""
        from services.erp.currency_service import CurrencyService

        service = CurrencyService()
        entry = service.calculate_gain_loss(
            transaction_id='TXN-001',
            original_amount=Decimal('1000'),
            original_currency='EUR',
            transaction_date=date.today() - timedelta(days=30),
            settlement_date=date.today()
        )

        assert entry.transaction_id == 'TXN-001'
        assert entry.original_amount == Decimal('1000')


# ─────────────────────────────────────────────────────────────────────────────
# ERP Depreciation Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDepreciationService:
    """Tests for ERP Fixed Asset/Depreciation Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.erp.depreciation_service import (
            DepreciationService,
            DepreciationMethod,
            AssetStatus,
            AssetCategory,
            FixedAsset
        )
        assert DepreciationService is not None
        assert DepreciationMethod.STRAIGHT_LINE == 'straight_line'

    def test_register_asset(self):
        """Test asset registration."""
        from services.erp.depreciation_service import DepreciationService

        service = DepreciationService()
        asset = service.register_asset(
            name='CNC Machine',
            acquisition_cost=50000.0,
            acquisition_date='2024-01-15',
            useful_life_months=60,
            salvage_value=5000.0,
            method='straight_line',
            category='machinery'
        )

        assert asset['asset_id'] is not None
        assert asset['name'] == 'CNC Machine'
        assert asset['acquisition_cost'] == 50000.0

    def test_straight_line_depreciation(self):
        """Test straight-line depreciation calculation."""
        from services.erp.depreciation_service import DepreciationService

        service = DepreciationService()
        asset = service.register_asset(
            name='Test Asset',
            acquisition_cost=12000.0,
            acquisition_date='2024-01-01',
            useful_life_months=12,
            salvage_value=0.0,
            method='straight_line'
        )

        result = service.calculate_monthly_depreciation(asset['asset_id'])

        assert result['monthly_depreciation'] == 1000.0  # 12000 / 12 months

    def test_declining_balance_depreciation(self):
        """Test declining balance depreciation."""
        from services.erp.depreciation_service import DepreciationService

        service = DepreciationService()
        asset = service.register_asset(
            name='Test Asset DB',
            acquisition_cost=10000.0,
            acquisition_date='2024-01-01',
            useful_life_months=60,
            salvage_value=1000.0,
            method='declining_balance'
        )

        result = service.calculate_monthly_depreciation(asset['asset_id'])

        assert result['monthly_depreciation'] > 0
        assert result['method'] == 'declining_balance'

    def test_run_depreciation(self):
        """Test running depreciation for all assets."""
        from services.erp.depreciation_service import DepreciationService

        service = DepreciationService()
        service.register_asset(
            name='Asset 1',
            acquisition_cost=10000.0,
            acquisition_date='2024-01-01',
            useful_life_months=60,
            salvage_value=0.0
        )
        service.register_asset(
            name='Asset 2',
            acquisition_cost=5000.0,
            acquisition_date='2024-01-01',
            useful_life_months=36,
            salvage_value=500.0
        )

        result = service.run_depreciation()

        assert result['assets_processed'] == 2
        assert result['total_depreciation'] > 0
        assert 'journal_entry' in result

    def test_dispose_asset(self):
        """Test asset disposal."""
        from services.erp.depreciation_service import DepreciationService

        service = DepreciationService()
        asset = service.register_asset(
            name='Asset to Dispose',
            acquisition_cost=10000.0,
            acquisition_date='2024-01-01',
            useful_life_months=60,
            salvage_value=1000.0
        )

        result = service.dispose_asset(
            asset_id=asset['asset_id'],
            disposal_date='2024-06-01',
            disposal_type='sale',
            proceeds=8000.0
        )

        assert 'gain_loss' in result
        assert result['disposal_type'] == 'sale'

    def test_asset_impairment(self):
        """Test recording asset impairment."""
        from services.erp.depreciation_service import DepreciationService

        service = DepreciationService()
        asset = service.register_asset(
            name='Impaired Asset',
            acquisition_cost=20000.0,
            acquisition_date='2024-01-01',
            useful_life_months=60,
            salvage_value=2000.0
        )

        result = service.record_impairment(
            asset_id=asset['asset_id'],
            impairment_amount=5000.0,
            reason='Market value decline'
        )

        assert result['impairment_amount'] == 5000.0
        assert result['nbv_after'] < result['nbv_before']


# ─────────────────────────────────────────────────────────────────────────────
# ERP Bank Reconciliation Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBankReconciliationService:
    """Tests for ERP Bank Reconciliation Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.erp.bank_reconciliation_service import (
            BankReconciliationService,
            TransactionType,
            MatchStatus,
            ReconciliationStatus,
            BankTransaction,
            MatchRule
        )
        assert BankReconciliationService is not None
        assert TransactionType.DEPOSIT == 'deposit'

    def test_default_match_rules(self):
        """Test default matching rules exist."""
        from services.erp.bank_reconciliation_service import BankReconciliationService

        service = BankReconciliationService()
        assert len(service._match_rules) > 0

    def test_parse_date_formats(self):
        """Test date parsing with various formats."""
        from services.erp.bank_reconciliation_service import BankReconciliationService

        service = BankReconciliationService()

        # YYYY-MM-DD
        assert service._parse_date('2024-01-15') == date(2024, 1, 15)
        # MM/DD/YYYY
        assert service._parse_date('01/15/2024') == date(2024, 1, 15)
        # MM/DD/YY
        assert service._parse_date('01/15/24') == date(2024, 1, 15)

    def test_parse_amount(self):
        """Test amount parsing."""
        from services.erp.bank_reconciliation_service import BankReconciliationService

        service = BankReconciliationService()

        assert service._parse_amount('100.00') == Decimal('100.00')
        assert service._parse_amount('$1,234.56') == Decimal('1234.56')
        assert service._parse_amount('(500.00)') == Decimal('-500.00')

    def test_import_csv_statement(self):
        """Test CSV statement import."""
        from services.erp.bank_reconciliation_service import BankReconciliationService

        service = BankReconciliationService()

        csv_content = """Date,Description,Amount,Reference
2024-01-15,DEPOSIT,1000.00,DEP001
2024-01-16,CHECK WITHDRAWAL,-500.00,CHK001
2024-01-17,BANK FEE,-25.00,FEE001"""

        result = service.import_csv_statement('BANK-001', csv_content)

        assert result['success'] is True
        assert result['transactions_imported'] == 3

    def test_start_reconciliation(self):
        """Test starting a reconciliation session."""
        from services.erp.bank_reconciliation_service import BankReconciliationService

        service = BankReconciliationService()

        result = service.start_reconciliation(
            bank_account_id='BANK-001',
            statement_date='2024-01-31',
            statement_ending_balance=50000.0
        )

        assert 'session_id' in result
        assert result['status'] == 'in_progress'

    def test_add_outstanding_check(self):
        """Test adding outstanding check."""
        from services.erp.bank_reconciliation_service import BankReconciliationService

        service = BankReconciliationService()

        result = service.add_outstanding_check(
            bank_account_id='BANK-001',
            check_number='1001',
            amount=500.0,
            date_issued='2024-01-20',
            payee='Supplier ABC'
        )

        assert result['check_number'] == '1001'
        assert result['status'] == 'outstanding'

    def test_get_outstanding_checks(self):
        """Test getting outstanding checks."""
        from services.erp.bank_reconciliation_service import BankReconciliationService

        service = BankReconciliationService()

        service.add_outstanding_check('BANK-001', '1001', 500.0, '2024-01-20', 'Payee 1')
        service.add_outstanding_check('BANK-001', '1002', 750.0, '2024-01-21', 'Payee 2')

        checks = service.get_outstanding_checks('BANK-001')

        assert len(checks) == 2

    def test_add_match_rule(self):
        """Test adding custom match rule."""
        from services.erp.bank_reconciliation_service import BankReconciliationService

        service = BankReconciliationService()
        initial_count = len(service._match_rules)

        result = service.add_match_rule(
            name='Custom Rule',
            priority=1,
            amount_tolerance=0.05,
            description_pattern='PAYROLL'
        )

        assert result['rule_id'] is not None
        assert len(service._match_rules) == initial_count + 1


# ─────────────────────────────────────────────────────────────────────────────
# Predictive Alarm Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPredictiveAlarmService:
    """Tests for Predictive Alarm Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.scada.alarm_management.predictive_alarm_service import (
            PredictiveAlarmService,
            TrendDirection,
            AlertSeverity,
            RollingStatistics,
            DynamicThreshold,
            TrendAlert,
            predictive_alarm_service,
        )
        assert PredictiveAlarmService is not None
        assert predictive_alarm_service is not None

    def test_trend_direction_enum(self):
        """Test trend direction enum values."""
        from services.scada.alarm_management.predictive_alarm_service import TrendDirection

        assert TrendDirection.STABLE.value == 'stable'
        assert TrendDirection.INCREASING.value == 'increasing'
        assert TrendDirection.DECREASING.value == 'decreasing'
        assert TrendDirection.RAPIDLY_INCREASING.value == 'rapidly_increasing'
        assert TrendDirection.RAPIDLY_DECREASING.value == 'rapidly_decreasing'

    def test_alert_severity_enum(self):
        """Test alert severity enum values."""
        from services.scada.alarm_management.predictive_alarm_service import AlertSeverity

        assert AlertSeverity.INFO.value == 'info'
        assert AlertSeverity.WARNING.value == 'warning'
        assert AlertSeverity.CRITICAL.value == 'critical'

    def test_rolling_statistics_calculation(self):
        """Test rolling statistics calculation."""
        from services.scada.alarm_management.predictive_alarm_service import RollingStatistics

        stats = RollingStatistics(tag_id='TEST-001')

        # Add values
        base_time = datetime.utcnow()
        for i in range(10):
            stats.add_value(100 + i, base_time + timedelta(minutes=i))

        assert stats.mean == pytest.approx(104.5, rel=0.01)
        assert stats.min_value == 100
        assert stats.max_value == 109
        assert len(stats.values) == 10

    def test_process_sensor_value(self):
        """Test processing sensor values."""
        from services.scada.alarm_management.predictive_alarm_service import (
            PredictiveAlarmService
        )

        service = PredictiveAlarmService()
        service._tag_stats.clear()  # Reset state

        result = service.process_sensor_value(
            tag_id='TEMP-001',
            tag_name='Temperature Sensor 1',
            value=75.0,
            alarm_thresholds={'high': 100, 'low': 50}
        )

        assert result['tag_id'] == 'TEMP-001'
        assert result['current_value'] == 75.0
        assert 'statistics' in result
        assert result['statistics']['sample_count'] == 1

    def test_dynamic_threshold_calculation(self):
        """Test dynamic threshold is calculated after enough samples."""
        from services.scada.alarm_management.predictive_alarm_service import (
            PredictiveAlarmService
        )

        service = PredictiveAlarmService()
        service._tag_stats.clear()
        service._dynamic_thresholds.clear()

        # Add enough samples for dynamic threshold calculation
        base_time = datetime.utcnow()
        for i in range(25):
            service.process_sensor_value(
                tag_id='PRES-001',
                tag_name='Pressure Sensor',
                value=50 + (i % 5),  # Values between 50-54
                timestamp=base_time + timedelta(minutes=i),
                alarm_thresholds={'high': 80, 'low': 20}
            )

        result = service.process_sensor_value(
            tag_id='PRES-001',
            tag_name='Pressure Sensor',
            value=52,
            timestamp=base_time + timedelta(minutes=25),
            alarm_thresholds={'high': 80, 'low': 20}
        )

        # Should have dynamic thresholds now
        assert 'dynamic_thresholds' in result
        # The dynamic threshold should exist
        threshold = service.get_dynamic_threshold('PRES-001', 'high')
        assert threshold is not None

    def test_configure_service(self):
        """Test service configuration."""
        from services.scada.alarm_management.predictive_alarm_service import (
            PredictiveAlarmService
        )

        service = PredictiveAlarmService()
        original_sigma = service._config['sigma_multiplier']

        service.configure({'sigma_multiplier': 2.5})

        assert service._config['sigma_multiplier'] == 2.5
        # Reset for other tests
        service.configure({'sigma_multiplier': original_sigma})

    def test_correlation_rule_registration(self):
        """Test alarm correlation rule registration."""
        from services.scada.alarm_management.predictive_alarm_service import (
            PredictiveAlarmService
        )

        service = PredictiveAlarmService()
        service._correlation_rules.clear()

        service.register_correlation_rule(
            primary_tag_id='MOTOR-001-TEMP',
            related_tag_ids=['MOTOR-001-VIB', 'MOTOR-001-AMP'],
            name='Motor 1 Correlation'
        )

        assert 'MOTOR-001-TEMP' in service._correlation_rules
        assert 'MOTOR-001-VIB' in service._correlation_rules['MOTOR-001-TEMP']

    def test_get_tag_statistics(self):
        """Test retrieving tag statistics."""
        from services.scada.alarm_management.predictive_alarm_service import (
            PredictiveAlarmService
        )

        service = PredictiveAlarmService()
        service._tag_stats.clear()

        # Process some values
        for i in range(5):
            service.process_sensor_value(
                tag_id='FLOW-001',
                tag_name='Flow Sensor',
                value=100 + i
            )

        stats = service.get_tag_statistics('FLOW-001')

        assert stats is not None
        assert stats['tag_id'] == 'FLOW-001'
        assert stats['sample_count'] == 5

    def test_get_nonexistent_statistics(self):
        """Test getting stats for unknown tag returns None."""
        from services.scada.alarm_management.predictive_alarm_service import (
            PredictiveAlarmService
        )

        service = PredictiveAlarmService()
        stats = service.get_tag_statistics('UNKNOWN-TAG')
        assert stats is None


class TestAnomalyDetectionService:
    """Tests for Anomaly Detection Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.scada.alarm_management.anomaly_detection_service import (
            AnomalyDetectionService,
            AnomalyType,
            AnomalyDetection,
            SensorProfile,
            anomaly_detection_service,
        )
        assert AnomalyDetectionService is not None
        assert anomaly_detection_service is not None

    def test_anomaly_type_enum(self):
        """Test anomaly type enum values."""
        from services.scada.alarm_management.anomaly_detection_service import AnomalyType

        assert AnomalyType.POINT_ANOMALY.value == 'point_anomaly'
        assert AnomalyType.LEVEL_SHIFT.value == 'level_shift'
        assert AnomalyType.VARIANCE_CHANGE.value == 'variance_change'
        assert AnomalyType.COLLECTIVE_ANOMALY.value == 'collective_anomaly'

    def test_service_configuration(self):
        """Test service configuration."""
        from services.scada.alarm_management.anomaly_detection_service import (
            AnomalyDetectionService
        )

        service = AnomalyDetectionService()
        original = service._config['z_score_threshold']

        service.configure({'z_score_threshold': 2.5})
        assert service._config['z_score_threshold'] == 2.5

        # Reset
        service.configure({'z_score_threshold': original})

    def test_analyze_builds_profile(self):
        """Test that analyze builds sensor profile."""
        from services.scada.alarm_management.anomaly_detection_service import (
            AnomalyDetectionService
        )

        service = AnomalyDetectionService()
        service._profiles.clear()

        # Not enough samples for anomaly detection yet
        for i in range(10):
            service.analyze(
                tag_id='SENSOR-001',
                tag_name='Test Sensor',
                value=100 + (i % 3)
            )

        profile = service.get_sensor_profile('SENSOR-001')
        assert profile is not None
        assert profile['tag_id'] == 'SENSOR-001'
        assert profile['training_samples'] == 10

    def test_profile_training_completion(self):
        """Test that profile becomes trained after enough samples."""
        from services.scada.alarm_management.anomaly_detection_service import (
            AnomalyDetectionService
        )

        service = AnomalyDetectionService()
        service._profiles.clear()

        # Add minimum training samples
        for i in range(100):
            service.analyze(
                tag_id='SENSOR-002',
                tag_name='Test Sensor 2',
                value=50 + (i % 10)
            )

        profile = service.get_sensor_profile('SENSOR-002')
        assert profile['is_trained'] is True
        assert profile['long_term_mean'] > 0
        assert profile['long_term_std'] > 0

    def test_detect_point_anomaly(self):
        """Test detection of point anomalies."""
        from services.scada.alarm_management.anomaly_detection_service import (
            AnomalyDetectionService,
            AnomalyType
        )

        service = AnomalyDetectionService()
        service._profiles.clear()
        service._active_anomalies.clear()

        # Train with normal values (mean ~100, low variance)
        for i in range(100):
            service.analyze(
                tag_id='SENSOR-003',
                tag_name='Test Sensor 3',
                value=100 + (i % 2)  # Values 100-101
            )

        # Now inject an extreme value
        anomalies = service.analyze(
            tag_id='SENSOR-003',
            tag_name='Test Sensor 3',
            value=200  # Way outside normal range
        )

        # Should detect a point anomaly
        assert len(anomalies) > 0
        point_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.POINT_ANOMALY]
        assert len(point_anomalies) > 0

    def test_get_active_anomalies(self):
        """Test getting active anomalies."""
        from services.scada.alarm_management.anomaly_detection_service import (
            AnomalyDetectionService
        )

        service = AnomalyDetectionService()

        # Get active anomalies (may be empty or have some from previous tests)
        anomalies = service.get_active_anomalies()
        assert isinstance(anomalies, list)

    def test_clear_anomaly(self):
        """Test clearing an anomaly."""
        from services.scada.alarm_management.anomaly_detection_service import (
            AnomalyDetectionService,
            AnomalyDetection,
            AnomalyType
        )

        service = AnomalyDetectionService()

        # Add a test anomaly
        test_anomaly = AnomalyDetection(
            anomaly_id='test_anomaly_123',
            tag_id='TEST-001',
            tag_name='Test',
            anomaly_type=AnomalyType.POINT_ANOMALY,
            score=0.9,
            confidence=0.8,
            value=100,
            expected_value=50,
            deviation=5.0,
            timestamp=datetime.utcnow()
        )
        service._active_anomalies['test_anomaly_123'] = test_anomaly

        # Clear it
        service.clear_anomaly('test_anomaly_123')
        assert 'test_anomaly_123' not in service._active_anomalies

    def test_reset_sensor_profile(self):
        """Test resetting a sensor profile."""
        from services.scada.alarm_management.anomaly_detection_service import (
            AnomalyDetectionService
        )

        service = AnomalyDetectionService()

        # Create a profile
        service.analyze('SENSOR-RESET', 'Reset Test', 100)
        assert 'SENSOR-RESET' in service._profiles

        # Reset it
        service.reset_sensor_profile('SENSOR-RESET')
        assert 'SENSOR-RESET' not in service._profiles


# ─────────────────────────────────────────────────────────────────────────────
# Reliability Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestReliabilityService:
    """Tests for CMMS Reliability Service enhancements."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.cmms.reliability_service import (
            ReliabilityService,
            WeibullParameters,
            FMEAItem,
            MaintenanceCostBenefit,
            FMEASeverity,
            FMEAOccurrence,
            FMEADetection
        )
        assert ReliabilityService is not None
        assert WeibullParameters is not None

    def test_weibull_parameters(self):
        """Test Weibull parameter calculations."""
        from services.cmms.reliability_service import WeibullParameters

        # Beta=2 (Weibull wear-out), Eta=1000 hours
        params = WeibullParameters(beta=2.0, eta=1000, gamma=0)

        # Test mean life calculation
        mttf = params.mean_life()
        assert mttf > 800 and mttf < 900  # Should be around 886

        # Test B10 life
        b10 = params.b_life(10)
        assert b10 > 300 and b10 < 350  # Should be around 324

        # Test reliability at time
        r_500 = params.reliability_at_time(500)
        assert r_500 > 0.7 and r_500 < 0.8  # Should be ~0.78

    def test_weibull_beta_interpretation(self):
        """Test Weibull beta interpretation."""
        from services.cmms.reliability_service import WeibullParameters

        # Infant mortality
        infant = WeibullParameters(beta=0.5, eta=1000)
        assert 'infant' in infant._interpret_beta().lower()

        # Random failures
        random = WeibullParameters(beta=1.0, eta=1000)
        assert 'random' in random._interpret_beta().lower()

        # Wear-out
        wearout = WeibullParameters(beta=3.0, eta=1000)
        assert 'wear' in wearout._interpret_beta().lower()

    def test_fmea_item_rpn_calculation(self):
        """Test FMEA RPN calculation."""
        from services.cmms.reliability_service import FMEAItem

        item = FMEAItem(
            item_id='TEST-001',
            machine_id='M1',
            component='Motor',
            failure_mode='Bearing wear',
            failure_effect='Machine stops',
            severity=8,
            occurrence=5,
            detection=6
        )

        # RPN = S * O * D = 8 * 5 * 6 = 240
        assert item.rpn == 240
        assert item._categorize_rpn() == 'critical'  # >= 200

    def test_fmea_rpn_categories(self):
        """Test FMEA RPN categorization."""
        from services.cmms.reliability_service import FMEAItem

        # Low RPN
        low = FMEAItem('1', 'M1', 'C', 'FM', 'FE', 2, 2, 2)
        assert low._categorize_rpn() == 'low'  # 8

        # Medium RPN
        medium = FMEAItem('2', 'M1', 'C', 'FM', 'FE', 5, 4, 5)
        assert medium._categorize_rpn() == 'medium'  # 100

        # High RPN
        high = FMEAItem('3', 'M1', 'C', 'FM', 'FE', 6, 5, 5)
        assert high._categorize_rpn() == 'high'  # 150

        # Critical RPN
        critical = FMEAItem('4', 'M1', 'C', 'FM', 'FE', 8, 5, 6)
        assert critical._categorize_rpn() == 'critical'  # 240

    def test_maintenance_cost_benefit(self):
        """Test maintenance cost-benefit calculation."""
        from services.cmms.reliability_service import MaintenanceCostBenefit

        analysis = MaintenanceCostBenefit(
            machine_id='M1',
            strategy='preventive',
            analysis_period_months=12
        )
        analysis.preventive_cost = 6000
        analysis.corrective_cost = 2000
        analysis.downtime_cost = 1000
        analysis.labor_cost = 3000

        analysis.downtime_savings = 8000
        analysis.failure_prevention_savings = 4000

        analysis.calculate_totals()

        assert analysis.total_cost == 12000
        assert analysis.total_benefit == 12000
        assert analysis.roi == 0  # Break even

    def test_cost_benefit_positive_roi(self):
        """Test positive ROI calculation."""
        from services.cmms.reliability_service import MaintenanceCostBenefit

        analysis = MaintenanceCostBenefit(
            machine_id='M1',
            strategy='predictive',
            analysis_period_months=12
        )
        analysis.preventive_cost = 5000
        analysis.total_cost = 8000  # Set directly for test

        analysis.downtime_savings = 10000
        analysis.failure_prevention_savings = 6000
        analysis.total_benefit = 16000

        # ROI = (16000 - 8000) / 8000 * 100 = 100%
        analysis.roi = (analysis.total_benefit - analysis.total_cost) / analysis.total_cost * 100

        result = analysis.to_dict()
        assert result['metrics']['roi_percent'] == 100.0
        assert result['metrics']['net_benefit'] == 8000


# ─────────────────────────────────────────────────────────────────────────────
# Takt Time Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTaktService:
    """Tests for Takt Time & Line Balancing Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.mes.takt_service import (
            TaktService,
            TaktAlertLevel,
            BottleneckSeverity,
            TaktStatus,
            LineBalanceRecommendation,
            BottleneckAnalysis,
            TaktPerformanceTrend
        )
        assert TaktService is not None
        assert TaktAlertLevel.CRITICAL.value == 'critical'

    def test_calculate_takt_time(self):
        """Test basic takt time calculation."""
        from services.mes.takt_service import TaktService

        service = TaktService(None)
        result = service.calculate_takt_time(demand_qty=480, available_hours=8)

        assert result['takt_time_seconds'] == 60.0
        assert result['units_per_hour'] == 60.0

    def test_calculate_takt_time_invalid(self):
        """Test takt time with invalid demand."""
        from services.mes.takt_service import TaktService

        service = TaktService(None)
        result = service.calculate_takt_time(demand_qty=0, available_hours=8)

        assert 'error' in result

    def test_record_cycle_time(self):
        """Test recording cycle time."""
        from services.mes.takt_service import TaktService

        service = TaktService(None)
        result = service.record_cycle_time(
            work_center_id='WC-001',
            cycle_seconds=55.0,
            takt_target_seconds=60.0,
            job_id='JOB-001'
        )

        assert result['status'] == 'recorded'
        assert result['record']['on_takt'] is True

    def test_record_cycle_time_triggers_alert(self):
        """Test that exceeding takt triggers alert."""
        from services.mes.takt_service import TaktService, TaktAlertLevel

        service = TaktService(None)
        # Record cycle time 25% over takt (critical threshold)
        result = service.record_cycle_time(
            work_center_id='WC-002',
            cycle_seconds=75.0,
            takt_target_seconds=60.0
        )

        assert result['alert'] is not None
        assert result['alert']['level'] == TaktAlertLevel.CRITICAL.value

    def test_realtime_takt_status(self):
        """Test real-time takt status calculation."""
        from services.mes.takt_service import TaktService, TaktAlertLevel

        service = TaktService(None)

        # Record several cycle times
        for i in range(10):
            service.record_cycle_time('WC-003', 62.0, 60.0)

        status = service.get_realtime_takt_status('WC-003', 60.0)

        assert status.work_center_id == 'WC-003'
        assert status.actual_cycle_seconds > 0
        assert status.alert_level == TaktAlertLevel.NORMAL  # 3.3% over is normal

    def test_line_balance_analysis(self):
        """Test line balance analysis."""
        from services.mes.takt_service import TaktService

        service = TaktService(None)
        operations = [
            {'name': 'Op1', 'cycle_seconds': 50},
            {'name': 'Op2', 'cycle_seconds': 55},
            {'name': 'Op3', 'cycle_seconds': 60},
            {'name': 'Op4', 'cycle_seconds': 45},
        ]

        result = service.line_balance_analysis(operations, takt_seconds=60)

        assert result['bottleneck'] == 'Op3'
        assert result['bottleneck_cycle'] == 60
        assert result['balance_efficiency_pct'] > 80

    def test_line_balance_recommendations(self):
        """Test line balance recommendations."""
        from services.mes.takt_service import TaktService

        service = TaktService(None)
        operations = [
            {'name': 'Op1', 'cycle_seconds': 30},  # Underutilized
            {'name': 'Op2', 'cycle_seconds': 65},  # Exceeds takt
            {'name': 'Op3', 'cycle_seconds': 55},
        ]

        recommendations = service.get_line_balance_recommendations(operations, 60)

        assert len(recommendations) > 0
        # Should recommend reducing bottleneck
        assert any(r.action == 'reduce_bottleneck_cycle' for r in recommendations)

    def test_bottleneck_analysis(self):
        """Test detailed bottleneck analysis."""
        from services.mes.takt_service import TaktService, BottleneckSeverity

        service = TaktService(None)
        operations = [
            {'name': 'Op1', 'cycle_seconds': 40},
            {'name': 'Op2', 'cycle_seconds': 100},  # Severe bottleneck (>1.5x avg)
            {'name': 'Op3', 'cycle_seconds': 45},
        ]

        analysis = service.analyze_bottleneck(operations, cost_per_hour=100.0)

        assert analysis.bottleneck_station == 'Op2'
        assert analysis.severity == BottleneckSeverity.SEVERE
        assert len(analysis.stations_starved) == 1  # Op3 is downstream

    def test_takt_performance_trend(self):
        """Test takt performance trending."""
        from services.mes.takt_service import TaktService
        from datetime import datetime, timedelta

        service = TaktService(None)
        base_time = datetime.utcnow()

        # Record cycles across multiple hours
        for i in range(50):
            service._cycle_history['WC-004'].append({
                'work_center_id': 'WC-004',
                'cycle_seconds': 58 + (i % 5),
                'takt_target_seconds': 60,
                'timestamp': (base_time - timedelta(hours=i // 5)).isoformat(),
                'on_takt': True,
            })

        trends = service.get_takt_performance_trend('WC-004', 60, periods=12, period_type='hourly')

        assert len(trends) > 0
        assert all(t.takt_target_seconds == 60 for t in trends)


# ─────────────────────────────────────────────────────────────────────────────
# Setup Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSetupService:
    """Tests for Setup Time Reduction (SMED) Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.mes.setup_service import (
            SetupService,
            SetupType,
            SetupPhase,
            SetupStatus,
            SetupStep,
            SetupProcedure,
            ActiveSetup,
            SetupBenchmark,
            SMEDImprovement
        )
        assert SetupService is not None
        assert SetupType.INTERNAL.value == 'internal'

    def test_record_setup_legacy(self):
        """Test legacy setup recording."""
        from services.mes.setup_service import SetupService

        service = SetupService(None)
        result = service.record_setup(
            machine_id='M001',
            job_id='JOB-001',
            duration_minutes=15.0,
            from_material='PLA',
            to_material='PETG',
            setup_type='internal'
        )

        assert result['status'] == 'recorded'
        assert result['event']['duration_minutes'] == 15.0

    def test_start_and_complete_setup(self):
        """Test starting and completing a setup."""
        from services.mes.setup_service import SetupService, SetupStatus

        service = SetupService(None)

        # Start setup
        active = service.start_setup(
            machine_id='M002',
            job_id='JOB-002',
            from_product='A',
            to_product='B',
            operator_id='OP-001'
        )

        assert active.status == SetupStatus.IN_PROGRESS
        assert active.setup_id.startswith('SETUP-')

        # Complete setup
        import time
        time.sleep(0.1)  # Small delay to ensure duration > 0
        result = service.complete_setup(active.setup_id)

        assert result['status'] == 'completed'
        assert result['duration_minutes'] >= 0

    def test_pause_and_resume_setup(self):
        """Test pausing and resuming a setup."""
        from services.mes.setup_service import SetupService, SetupStatus

        service = SetupService(None)

        active = service.start_setup('M003', 'JOB-003')

        # Pause
        result = service.pause_setup(active.setup_id, reason='Waiting for parts')
        assert result['status'] == 'paused'

        # Resume
        import time
        time.sleep(0.1)
        result = service.resume_setup(active.setup_id)
        assert result['status'] == 'resumed'
        assert result['total_pause_minutes'] >= 0

    def test_create_procedure(self):
        """Test creating a setup procedure checklist."""
        from services.mes.setup_service import SetupService, SetupType, SetupPhase

        service = SetupService(None)
        procedure = service.create_procedure(
            name='FDM Filament Change',
            machine_id='bambu-ps1',
            from_product='PLA',
            to_product='PETG',
            steps=[
                {'description': 'Heat nozzle to 240C', 'setup_type': 'internal', 'phase': 'preparation', 'estimated_minutes': 2},
                {'description': 'Retract filament', 'setup_type': 'internal', 'phase': 'removal', 'estimated_minutes': 1},
                {'description': 'Load new filament', 'setup_type': 'internal', 'phase': 'installation', 'estimated_minutes': 2},
                {'description': 'Purge extruder', 'setup_type': 'internal', 'phase': 'adjustment', 'estimated_minutes': 1},
            ]
        )

        assert procedure.procedure_id.startswith('PROC-')
        assert len(procedure.steps) == 4
        assert procedure.total_estimated_minutes == 6.0

    def test_setup_benchmarks(self):
        """Test setup benchmark tracking."""
        from services.mes.setup_service import SetupService

        service = SetupService(None)

        # Record several setups
        for duration in [15, 12, 18, 14, 16]:
            service.record_setup('M004', f'JOB-{duration}', duration, 'A', 'B')

        benchmarks = service.get_benchmarks('M004')

        assert len(benchmarks) > 0
        benchmark = benchmarks[0]
        assert benchmark.best_time_minutes == 12
        assert benchmark.worst_time_minutes == 18

    def test_compare_to_benchmark(self):
        """Test comparing setup to benchmark."""
        from services.mes.setup_service import SetupService

        service = SetupService(None)

        # Establish benchmark
        for duration in [15, 12, 18]:
            service.record_setup('M005', f'JOB-{duration}', duration, 'X', 'Y')

        # Compare a new setup
        result = service.compare_to_benchmark('M005', 'X', 'Y', 13.0)

        assert result['has_benchmark'] is True
        assert result['performance'] == 'good'  # Better than average

    def test_smed_project(self):
        """Test SMED improvement project tracking."""
        from services.mes.setup_service import SetupService

        service = SetupService(None)

        # Establish baseline
        for duration in [20, 22, 19]:
            service.record_setup('M006', f'JOB-{duration}', duration, 'P', 'Q')

        # Create SMED project
        project = service.create_smed_project('M006', 'P', 'Q', target_minutes=12)

        assert project.project_id.startswith('SMED-')
        assert project.baseline_minutes > 0
        assert project.target_minutes == 12

        # Update progress
        result = service.update_smed_progress(
            project.project_id,
            current_minutes=15,
            converted_steps=['Tool staging'],
            streamlined_steps=['Reduced adjustment time']
        )

        assert result['improvement_pct'] > 0
        assert result['target_achieved'] is False

    def test_setup_trends(self):
        """Test setup time trends."""
        from services.mes.setup_service import SetupService

        service = SetupService(None)

        # Record setups
        for i in range(10):
            service.record_setup('M007', f'JOB-{i}', 15 - i * 0.5, 'A', 'B')

        result = service.get_setup_trends('M007')

        assert result['count'] == 10
        assert result['trend_direction'] in ['improving', 'stable', 'degrading']


# ─────────────────────────────────────────────────────────────────────────────
# WIP Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWIPService:
    """Tests for WIP & Kanban Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.mes.wip_service import (
            WIPService,
            KanbanSignal,
            AgingCategory,
            ConstraintType,
            WIPItem,
            WorkCenterWIP,
            KanbanCard,
            WIPAgingReport,
            ConstraintAnalysis
        )
        assert WIPService is not None
        assert KanbanSignal.REPLENISH.value == 'replenish'

    def test_aging_category_enum(self):
        """Test aging category values."""
        from services.mes.wip_service import AgingCategory

        assert AgingCategory.FRESH.value == 'fresh'
        assert AgingCategory.NORMAL.value == 'normal'
        assert AgingCategory.AGING.value == 'aging'
        assert AgingCategory.STALE.value == 'stale'

    def test_set_unit_cost(self):
        """Test setting unit cost for WIP valuation."""
        from services.mes.wip_service import WIPService

        service = WIPService(None)
        service.set_unit_cost('PRODUCT-001', 25.50)

        assert service._unit_costs['PRODUCT-001'] == 25.50

    def test_set_work_center_mapping(self):
        """Test work center mapping."""
        from services.mes.wip_service import WIPService

        service = WIPService(None)
        service.set_work_center_mapping('bambu-ps1', 'FDM-CENTER')
        service.set_work_center_mapping('bambu-ps2', 'FDM-CENTER')

        assert service._work_center_map['bambu-ps1'] == 'FDM-CENTER'
        assert service._work_center_map['bambu-ps2'] == 'FDM-CENTER'

    def test_create_kanban_card(self):
        """Test creating a kanban card."""
        from services.mes.wip_service import WIPService, KanbanSignal

        service = WIPService(None)
        card = service.create_kanban_card(
            product_id='PROD-001',
            work_center_id='WC-001',
            target_qty=100,
            reorder_point=30
        )

        assert card.card_id.startswith('KB-')
        assert card.status == 'empty'
        assert card.signal == KanbanSignal.REPLENISH

    def test_update_kanban_card(self):
        """Test updating kanban card quantity."""
        from services.mes.wip_service import WIPService, KanbanSignal

        service = WIPService(None)
        card = service.create_kanban_card('PROD-002', 'WC-002', 100, 30)

        # Fill card
        result = service.update_kanban_card(card.card_id, 100)

        assert result['status'] == 'full'
        assert result['signal'] == KanbanSignal.NONE.value

        # Deplete below reorder point
        result = service.update_kanban_card(card.card_id, 25)

        assert result['status'] == 'empty'
        assert result['signal'] == KanbanSignal.REPLENISH.value

    def test_set_wip_limit(self):
        """Test setting WIP limit."""
        from services.mes.wip_service import WIPService

        service = WIPService(None)
        result = service.set_wip_limit('M001', 10)

        assert result['new_limit'] == 10
        assert service._wip_limits['M001'] == 10

    def test_record_wip_snapshot(self):
        """Test recording WIP snapshot."""
        from services.mes.wip_service import WIPService
        from unittest.mock import Mock, MagicMock

        # Create mock session
        mock_session = Mock()
        mock_query = MagicMock()
        mock_query.filter.return_value.group_by.return_value.all.return_value = [
            ('M001', 3),
            ('M002', 2),
        ]
        mock_session.query.return_value = mock_query

        service = WIPService(mock_session)
        service._wip_limits = {'default': 5}

        snapshot = service.record_wip_snapshot()

        assert 'timestamp' in snapshot
        assert 'total_wip' in snapshot
        assert snapshot['total_wip'] == 5

    def test_categorize_age(self):
        """Test WIP age categorization."""
        from services.mes.wip_service import WIPService, AgingCategory

        service = WIPService(None)

        assert service._categorize_age(12) == AgingCategory.FRESH
        assert service._categorize_age(48) == AgingCategory.NORMAL
        assert service._categorize_age(120) == AgingCategory.AGING
        assert service._categorize_age(200) == AgingCategory.STALE

    def test_constraint_type_enum(self):
        """Test constraint type values."""
        from services.mes.wip_service import ConstraintType

        assert ConstraintType.BOTTLENECK.value == 'bottleneck'
        assert ConstraintType.STARVED.value == 'starved'
        assert ConstraintType.BLOCKED.value == 'blocked'
        assert ConstraintType.BALANCED.value == 'balanced'

    def test_wip_item_dataclass(self):
        """Test WIPItem dataclass."""
        from services.mes.wip_service import WIPItem, AgingCategory
        from datetime import datetime

        item = WIPItem(
            job_id='JOB-001',
            work_order_id='WO-001',
            product_id='PROD-001',
            machine_id='M001',
            work_center_id='WC-001',
            quantity=50,
            entered_queue_at=datetime.utcnow(),
            age_hours=24,
            age_category=AgingCategory.NORMAL,
            unit_cost=10.0,
            total_value=500.0
        )

        assert item.total_value == 500.0
        assert item.age_category == AgingCategory.NORMAL


# ─────────────────────────────────────────────────────────────────────────────
# Time Clock Service Tests (Labor & Skill Management)
# ─────────────────────────────────────────────────────────────────────────────

class TestTimeClockService:
    """Tests for Time Clock & Labor Management Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.mes.time_clock_service import (
            TimeClockService,
            CertificationStatus,
            SkillLevel,
            Certification,
            WorkerSkill,
            WorkerProfile,
            TimeEntry,
            LaborEfficiency,
            CrossTrainingRecommendation
        )
        assert TimeClockService is not None
        assert SkillLevel.EXPERT.value == 5

    def test_clock_in_out(self):
        """Test basic clock in/out functionality."""
        from services.mes.time_clock_service import TimeClockService

        service = TimeClockService(None)

        # Clock in
        result = service.clock_in('W001', machine_id='M001', job_id='JOB-001')
        assert result['status'] == 'clocked_in'
        assert result['worker_id'] == 'W001'

        # Cannot clock in twice
        result = service.clock_in('W001')
        assert 'error' in result

        # Clock out
        import time
        time.sleep(0.1)
        result = service.clock_out('W001')
        assert result['status'] == 'clocked_out'
        assert result['total_hours'] >= 0

    def test_break_tracking(self):
        """Test break start/end tracking."""
        from services.mes.time_clock_service import TimeClockService

        service = TimeClockService(None)
        service.clock_in('W002')

        # Start break
        result = service.start_break('W002', 'lunch')
        assert result['status'] == 'break_started'

        # End break
        import time
        time.sleep(0.1)
        result = service.end_break('W002')
        assert result['status'] == 'break_ended'
        assert result['break_minutes'] >= 0

        service.clock_out('W002')

    def test_register_worker(self):
        """Test worker profile registration."""
        from services.mes.time_clock_service import TimeClockService

        service = TimeClockService(None)
        profile = service.register_worker(
            worker_id='W003',
            name='John Smith',
            department='Manufacturing',
            hire_date=date(2023, 1, 15),
            hourly_rate=28.50,
            primary_machines=['M001', 'M002']
        )

        assert profile.worker_id == 'W003'
        assert profile.name == 'John Smith'
        assert profile.hourly_rate == 28.50

    def test_add_skill(self):
        """Test adding skills to a worker."""
        from services.mes.time_clock_service import TimeClockService, SkillLevel

        service = TimeClockService(None)
        service.register_worker('W004', 'Jane Doe', 'Manufacturing', date(2023, 1, 1), 25.0)

        skill = service.add_skill(
            worker_id='W004',
            skill_id='CNC_OPERATION',
            skill_name='CNC Machine Operation',
            level=4,
            required_for_machines=['CNC-001']
        )

        assert skill.skill_id == 'CNC_OPERATION'
        assert skill.level == SkillLevel.PROFICIENT

    def test_add_certification(self):
        """Test adding certifications."""
        from services.mes.time_clock_service import TimeClockService, CertificationStatus

        service = TimeClockService(None)

        cert = service.add_certification(
            worker_id='W005',
            certification_type='safety',
            certification_name='Forklift Operator',
            issued_date=date(2025, 1, 1),
            expiry_date=date(2028, 1, 1),  # Future date
            issuing_authority='OSHA',
            credential_number='FLK-12345'
        )

        assert cert.cert_id.startswith('CERT-')
        assert cert.status == CertificationStatus.ACTIVE

    def test_expiring_certifications(self):
        """Test getting expiring certifications."""
        from services.mes.time_clock_service import TimeClockService

        service = TimeClockService(None)
        service.register_worker('W006', 'Bob Test', 'Production', date(2023, 1, 1), 25.0)

        # Add expiring cert
        service.add_certification(
            worker_id='W006',
            certification_type='safety',
            certification_name='Safety Training',
            issued_date=date(2024, 1, 1),
            expiry_date=date.today() + timedelta(days=15),
            issuing_authority='Internal'
        )

        expiring = service.get_expiring_certifications(days=30)
        assert len(expiring) > 0
        assert expiring[0]['days_until_expiry'] <= 30

    def test_skill_matrix(self):
        """Test skill matrix generation."""
        from services.mes.time_clock_service import TimeClockService

        service = TimeClockService(None)
        service.register_worker('W007', 'Alice', 'Dept1', date(2023, 1, 1), 25.0)
        service.register_worker('W008', 'Bob', 'Dept1', date(2023, 1, 1), 25.0)

        service.add_skill('W007', 'SKILL_A', 'Skill A', 4)
        service.add_skill('W007', 'SKILL_B', 'Skill B', 3)
        service.add_skill('W008', 'SKILL_A', 'Skill A', 2)

        matrix = service.get_skill_matrix('Dept1')

        assert len(matrix['skill_columns']) == 2
        assert len(matrix['workers']) == 2

    def test_cross_training_recommendations(self):
        """Test cross-training recommendation generation."""
        from services.mes.time_clock_service import TimeClockService

        service = TimeClockService(None)
        service.register_worker('W009', 'Worker 1', 'Production', date(2023, 1, 1), 25.0, ['M001'])
        service.register_worker('W010', 'Worker 2', 'Production', date(2023, 1, 1), 25.0, ['M001'])

        # Only W009 has the required skill
        service.add_skill('W009', 'MACHINE_OP', 'Machine Operation', 4)
        service.set_skill_requirement('M001', ['MACHINE_OP'])

        recommendations = service.get_cross_training_recommendations('Production')

        # Should recommend W010 learn MACHINE_OP
        assert len(recommendations) > 0

    def test_labor_summary(self):
        """Test labor summary report."""
        from services.mes.time_clock_service import TimeClockService

        service = TimeClockService(None)
        service.register_worker('W011', 'Worker', 'Dept', date(2023, 1, 1), 25.0)

        service.clock_in('W011', 'M001', 'JOB-001')
        import time
        time.sleep(0.1)
        service.clock_out('W011')

        summary = service.get_labor_summary()

        assert summary['entry_count'] >= 1
        assert 'by_department' in summary


# ─────────────────────────────────────────────────────────────────────────────
# Genealogy Service Tests (Recall & Compliance)
# ─────────────────────────────────────────────────────────────────────────────

class TestGenealogyServiceEnhancements:
    """Tests for Genealogy Service enhancements."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.mes.genealogy_service import (
            GenealogyService,
            create_product_record,
            trace_forward,
            trace_backward
        )
        assert GenealogyService is not None

    def test_recall_actions_generation(self):
        """Test recall action generation logic."""
        from services.mes.genealogy_service import GenealogyService
        from unittest.mock import Mock

        mock_session = Mock()
        service = GenealogyService(mock_session)

        # Test critical severity with shipped products
        actions = service._generate_recall_actions(
            shipped_count=5,
            customer_count=3,
            severity='critical'
        )

        assert len(actions) > 0
        assert actions[0]['action'] == 'customer_notification'
        assert any(a['action'] == 'regulatory_notification' for a in actions)

    def test_compliance_assessment(self):
        """Test compliance assessment logic."""
        from services.mes.genealogy_service import GenealogyService
        from unittest.mock import Mock

        mock_session = Mock()
        service = GenealogyService(mock_session)

        # Test with compliant report
        report = {
            'traceability': {'full_traceability': True},
            'process_history': {'all_operations_documented': True},
            'quality_records': {'all_inspections_passed': True},
        }

        assessment = service._assess_compliance(report, 'ISO')

        assert assessment['compliant'] is True
        assert assessment['issue_count'] == 0

        # Test with non-compliant report
        report['traceability']['full_traceability'] = False

        assessment = service._assess_compliance(report, 'ISO')

        assert assessment['compliant'] is False
        assert assessment['issue_count'] > 0

    def test_as9100_section_generation(self):
        """Test AS9100 section generation."""
        from services.mes.genealogy_service import GenealogyService
        from unittest.mock import Mock, MagicMock

        mock_session = Mock()
        service = GenealogyService(mock_session)

        mock_genealogy = MagicMock()
        mock_genealogy.fai_complete = True
        mock_genealogy.fai_number = 'FAI-001'

        steps = [
            {'operation_name': 'Heat Treatment'},
            {'operation_name': 'Machining'},
        ]

        section = service._generate_as9100_section(mock_genealogy, steps)

        assert 'first_article_inspection' in section
        assert 'special_processes' in section
        assert 'Heat Treatment' in section['special_processes']['processes_identified']

    def test_fda_section_generation(self):
        """Test FDA section generation."""
        from services.mes.genealogy_service import GenealogyService
        from unittest.mock import Mock, MagicMock

        mock_session = Mock()
        service = GenealogyService(mock_session)

        mock_genealogy = MagicMock()
        mock_genealogy.serial_number = 'SN-001'
        mock_genealogy.batch_number = 'BATCH-001'
        mock_genealogy.started_at = datetime.utcnow()
        mock_genealogy.overall_quality = MagicMock(value='passed')

        steps = []

        section = service._generate_fda_section(mock_genealogy, steps)

        assert 'device_history_record' in section
        assert 'electronic_records' in section
        assert section['electronic_records']['part_11_compliant'] is True

    def test_iatf_section_generation(self):
        """Test IATF section generation."""
        from services.mes.genealogy_service import GenealogyService
        from unittest.mock import Mock, MagicMock

        mock_session = Mock()
        service = GenealogyService(mock_session)

        mock_genealogy = MagicMock()
        mock_genealogy.serial_number = 'SN-001'

        steps = [{'quality_result': 'passed'}]

        section = service._generate_iatf_section(mock_genealogy, steps)

        assert 'ppap_status' in section
        assert 'special_characteristics' in section
        assert section['ppap_status']['ppap_approved'] is True


# ─────────────────────────────────────────────────────────────────────────────
# Recipe Tracking Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRecipeTrackingService:
    """Tests for Recipe Version Control & Tracking Service."""

    def test_import_module(self):
        """Test that the module can be imported."""
        from services.mes.recipe_tracking_service import (
            RecipeTrackingService,
            RecipeStatus,
            LockStatus,
            Recipe,
            RecipeVersion,
            RecipeParameter,
            RecipeEffectiveness
        )
        assert RecipeTrackingService is not None
        assert RecipeStatus.ACTIVE.value == 'active'

    def test_create_recipe(self):
        """Test recipe creation."""
        from services.mes.recipe_tracking_service import RecipeTrackingService, RecipeStatus

        service = RecipeTrackingService()
        recipe = service.create_recipe(
            name='FDM Print Recipe',
            product_id='BRICK-001',
            machine_type='fdm',
            description='Standard PLA print settings',
            parameters=[
                {'name': 'nozzle_temp', 'value': 215, 'unit': 'C', 'is_critical': True},
                {'name': 'bed_temp', 'value': 60, 'unit': 'C'},
                {'name': 'print_speed', 'value': 50, 'unit': 'mm/s'},
            ],
            created_by='engineer_01'
        )

        assert recipe.recipe_id.startswith('RCP-')
        assert recipe.name == 'FDM Print Recipe'
        assert len(recipe.versions) == 1
        assert recipe.versions[1].status == RecipeStatus.DRAFT

    def test_create_new_version(self):
        """Test creating a new recipe version."""
        from services.mes.recipe_tracking_service import RecipeTrackingService

        service = RecipeTrackingService()
        recipe = service.create_recipe(
            name='Test Recipe',
            product_id='PROD-001',
            machine_type='cnc',
            description='Test',
            parameters=[
                {'name': 'speed', 'value': 1000, 'unit': 'rpm'},
            ],
            created_by='user1'
        )

        # Get the parameter ID
        param_id = list(recipe.versions[1].parameters.keys())[0]

        # Create new version with changed parameter
        new_version = service.create_new_version(
            recipe_id=recipe.recipe_id,
            parameter_changes={param_id: 1200},
            change_description='Increased speed',
            change_reason='Improved throughput',
            created_by='user2'
        )

        assert new_version.version_number == 2
        assert new_version.parameters[param_id].value == 1200

    def test_compare_versions(self):
        """Test version comparison."""
        from services.mes.recipe_tracking_service import RecipeTrackingService

        service = RecipeTrackingService()
        recipe = service.create_recipe(
            name='Compare Test',
            product_id='PROD-002',
            machine_type='fdm',
            description='Test',
            parameters=[
                {'name': 'temp', 'value': 200, 'unit': 'C', 'is_critical': True},
            ],
            created_by='user1'
        )

        param_id = list(recipe.versions[1].parameters.keys())[0]
        service.create_new_version(
            recipe.recipe_id, {param_id: 210}, 'Temp change', 'Testing', 'user2'
        )

        diff = service.compare_versions(recipe.recipe_id, 1, 2)

        assert diff['total_changes'] == 1
        assert diff['differences'][0]['old_value'] == 200
        assert diff['differences'][0]['new_value'] == 210

    def test_approval_workflow(self):
        """Test approval workflow."""
        from services.mes.recipe_tracking_service import RecipeTrackingService, RecipeStatus

        service = RecipeTrackingService()
        service._required_approvers = ['approver1', 'approver2']

        recipe = service.create_recipe(
            name='Approval Test',
            product_id='PROD-003',
            machine_type='fdm',
            description='Test',
            parameters=[{'name': 'param', 'value': 100, 'unit': 'x'}],
            created_by='creator'
        )

        # Submit for approval
        result = service.submit_for_approval(recipe.recipe_id, 1, 'creator')
        assert result['status'] == 'submitted'
        request_id = result['request_id']

        # First approver
        result = service.approve_version(request_id, 'approver1')
        assert result['status'] == 'partially_approved'

        # Second approver
        result = service.approve_version(request_id, 'approver2')
        assert result['status'] == 'fully_approved'

        # Check version status
        version = recipe.versions[1]
        assert version.status == RecipeStatus.APPROVED

    def test_activate_version(self):
        """Test activating an approved version."""
        from services.mes.recipe_tracking_service import RecipeTrackingService, RecipeStatus

        service = RecipeTrackingService()
        service._required_approvers = ['approver']

        recipe = service.create_recipe(
            name='Activate Test',
            product_id='PROD-004',
            machine_type='fdm',
            description='Test',
            parameters=[{'name': 'param', 'value': 100, 'unit': 'x'}],
            created_by='creator'
        )

        # Approve
        result = service.submit_for_approval(recipe.recipe_id, 1, 'creator', ['approver'])
        service.approve_version(result['request_id'], 'approver')

        # Activate
        result = service.activate_version(recipe.recipe_id, 1, 'activator')
        assert result['status'] == 'activated'
        assert recipe.current_version == 1
        assert recipe.versions[1].status == RecipeStatus.ACTIVE

    def test_production_lock(self):
        """Test recipe locking for production."""
        from services.mes.recipe_tracking_service import RecipeTrackingService, LockStatus

        service = RecipeTrackingService()
        service._required_approvers = ['approver']

        recipe = service.create_recipe(
            name='Lock Test',
            product_id='PROD-005',
            machine_type='fdm',
            description='Test',
            parameters=[{'name': 'param', 'value': 100, 'unit': 'x'}],
            created_by='creator'
        )

        # Approve and activate
        result = service.submit_for_approval(recipe.recipe_id, 1, 'creator', ['approver'])
        service.approve_version(result['request_id'], 'approver')
        service.activate_version(recipe.recipe_id, 1, 'activator')

        # Lock
        result = service.lock_for_production(recipe.recipe_id, 'JOB-001')
        assert result['status'] == 'locked'
        assert recipe.lock_status == LockStatus.LOCKED

        # Cannot lock again
        result = service.lock_for_production(recipe.recipe_id, 'JOB-002')
        assert 'error' in result

        # Unlock
        result = service.unlock_recipe(recipe.recipe_id, 'JOB-001')
        assert result['status'] == 'unlocked'

    def test_lot_linkage(self):
        """Test linking lots to recipes."""
        from services.mes.recipe_tracking_service import RecipeTrackingService

        service = RecipeTrackingService()
        service._required_approvers = ['approver']

        recipe = service.create_recipe(
            name='Lot Test',
            product_id='PROD-006',
            machine_type='fdm',
            description='Test',
            parameters=[{'name': 'temp', 'value': 200, 'unit': 'C'}],
            created_by='creator'
        )

        result = service.submit_for_approval(recipe.recipe_id, 1, 'creator', ['approver'])
        service.approve_version(result['request_id'], 'approver')
        service.activate_version(recipe.recipe_id, 1, 'activator')

        # Link lot
        link = service.link_lot_to_recipe('LOT-001', recipe.recipe_id, 'JOB-001', 100)
        assert link['lot_id'] == 'LOT-001'
        assert 'parameters_snapshot' in link

        # Retrieve
        info = service.get_lot_recipe_info('LOT-001')
        assert info['version_number'] == 1

    def test_effectiveness_tracking(self):
        """Test recipe effectiveness tracking."""
        from services.mes.recipe_tracking_service import RecipeTrackingService

        service = RecipeTrackingService()
        service._required_approvers = ['approver']

        recipe = service.create_recipe(
            name='Effectiveness Test',
            product_id='PROD-007',
            machine_type='fdm',
            description='Test',
            parameters=[{'name': 'param', 'value': 100, 'unit': 'x'}],
            created_by='creator'
        )

        result = service.submit_for_approval(recipe.recipe_id, 1, 'creator', ['approver'])
        service.approve_version(result['request_id'], 'approver')
        service.activate_version(recipe.recipe_id, 1, 'activator')

        # Link lot and record result
        service.link_lot_to_recipe('LOT-EFF-001', recipe.recipe_id, 'JOB-001', 100)
        service.record_production_result('LOT-EFF-001', 95, 5, 30.5, 98.5)

        # Get effectiveness
        eff = service.get_recipe_effectiveness(recipe.recipe_id, 1)
        assert eff.lots_produced == 1
        assert eff.yield_pct == 95.0
        assert eff.quality_score == 98.5

    def test_audit_trail(self):
        """Test audit trail generation."""
        from services.mes.recipe_tracking_service import RecipeTrackingService

        service = RecipeTrackingService()

        recipe = service.create_recipe(
            name='Audit Test',
            product_id='PROD-008',
            machine_type='fdm',
            description='Test',
            parameters=[{'name': 'param', 'value': 100, 'unit': 'x'}],
            created_by='creator'
        )

        # Get audit trail
        trail = service.get_audit_trail(recipe.recipe_id)
        assert len(trail) >= 1
        assert trail[0]['action'] == 'created'


class TestAlarmManagementPackage:
    """Tests for alarm management package exports."""

    def test_package_exports(self):
        """Test that all expected exports are available from package."""
        from services.scada.alarm_management import (
            # Core alarm service
            AlarmProcessor,
            AlarmService,
            AlarmEvent,
            AlarmSummary,
            AlarmPriority,
            AlarmStatus,
            alarm_processor,
            # Predictive alarm service
            PredictiveAlarmService,
            TrendDirection,
            AlertSeverity,
            predictive_alarm_service,
            # Anomaly detection
            AnomalyDetectionService,
            AnomalyType,
            anomaly_detection_service,
        )

        assert AlarmProcessor is not None
        assert PredictiveAlarmService is not None
        assert AnomalyDetectionService is not None


# ─────────────────────────────────────────────────────────────────────────────
# Run Tests
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
