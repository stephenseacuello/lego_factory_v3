"""
LEGO Factory v3 - FMEA Service Unit Tests
=========================================
Tests for Failure Mode and Effects Analysis service.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from services.advanced.quality.fmea_service import (
    FMEAService,
    DynamicFactors,
)


class TestDynamicFactors:
    """Test DynamicFactors dataclass."""

    def test_default_factors(self):
        """Test default factor values are 1.0."""
        factors = DynamicFactors()
        assert factors.machine_health == 1.0
        assert factors.operator_skill == 1.0
        assert factors.material_quality == 1.0
        assert factors.spc_trend == 1.0
        assert factors.environmental == 1.0

    def test_total_factor_default(self):
        """Test total factor with defaults equals 1.0."""
        factors = DynamicFactors()
        assert factors.total_factor() == 1.0

    def test_total_factor_custom(self):
        """Test total factor calculation with custom values."""
        factors = DynamicFactors(
            machine_health=1.2,
            operator_skill=1.5,
            material_quality=1.0,
            spc_trend=1.1,
            environmental=1.0,
        )
        # 1.2 * 1.5 * 1.0 * 1.1 * 1.0 = 1.98
        assert factors.total_factor() == pytest.approx(1.98, rel=1e-2)

    def test_total_factor_degraded(self):
        """Test total factor increases when conditions degrade."""
        normal = DynamicFactors()
        degraded = DynamicFactors(
            machine_health=1.5,
            operator_skill=1.2,
        )
        assert degraded.total_factor() > normal.total_factor()


class TestFMEAService:
    """Test FMEAService class."""

    @pytest.fixture
    def fmea_service(self):
        """Create an FMEA service instance."""
        return FMEAService()

    def test_service_initialization(self, fmea_service):
        """Test FMEA service initializes correctly."""
        assert fmea_service is not None
        assert len(fmea_service._fmeas) == 0
        assert len(fmea_service._failure_modes) == 0
        assert len(fmea_service._actions) == 0

    def test_rpn_thresholds(self, fmea_service):
        """Test RPN thresholds are defined correctly."""
        assert fmea_service.RPN_THRESHOLD_HIGH == 100
        assert fmea_service.RPN_THRESHOLD_CRITICAL == 200
        assert fmea_service.RPN_THRESHOLD_IMMEDIATE == 300

    def test_lego_failure_modes_defined(self, fmea_service):
        """Test LEGO-specific failure modes are defined."""
        modes = fmea_service.LEGO_FAILURE_MODES
        assert len(modes) > 0
        assert 'stud_undersized' in modes
        assert 'warping' in modes
        assert 'layer_adhesion' in modes

    def test_failure_mode_structure(self, fmea_service):
        """Test failure mode structure is correct."""
        mode = fmea_service.LEGO_FAILURE_MODES['stud_undersized']
        assert 'description' in mode
        assert 'effect' in mode
        assert 'cause' in mode
        assert 'severity' in mode
        assert 'occurrence' in mode
        assert 'detection' in mode

    def test_failure_mode_ratings_valid(self, fmea_service):
        """Test failure mode ratings are valid (1-10)."""
        for mode_name, mode in fmea_service.LEGO_FAILURE_MODES.items():
            assert 1 <= mode['severity'] <= 10, f"{mode_name} severity out of range"
            assert 1 <= mode['occurrence'] <= 10, f"{mode_name} occurrence out of range"
            assert 1 <= mode['detection'] <= 10, f"{mode_name} detection out of range"


class TestCreateFMEA:
    """Test FMEA creation."""

    @pytest.fixture
    def fmea_service(self):
        """Create an FMEA service instance."""
        return FMEAService()

    def test_create_fmea_basic(self, fmea_service):
        """Test creating a basic FMEA record."""
        fmea = fmea_service.create_fmea(
            part_id="part-001",
            part_name="2x4 Brick",
        )

        assert fmea is not None
        assert 'fmea_id' in fmea
        assert fmea['part_id'] == "part-001"
        assert fmea['part_name'] == "2x4 Brick"
        assert fmea['fmea_type'] == "process"
        assert fmea['status'] == "draft"

    def test_create_fmea_with_type(self, fmea_service):
        """Test creating FMEA with specific type."""
        fmea = fmea_service.create_fmea(
            part_id="part-002",
            part_name="Minifig Head",
            fmea_type="design",
        )

        assert fmea['fmea_type'] == "design"

    def test_create_fmea_stores_in_memory(self, fmea_service):
        """Test created FMEA is stored in memory."""
        fmea = fmea_service.create_fmea(
            part_id="part-003",
            part_name="Wheel",
        )

        assert fmea['fmea_id'] in fmea_service._fmeas

    def test_create_multiple_fmeas(self, fmea_service):
        """Test creating multiple FMEA records."""
        fmea1 = fmea_service.create_fmea(part_id="p1", part_name="Part 1")
        fmea2 = fmea_service.create_fmea(part_id="p2", part_name="Part 2")

        assert fmea1['fmea_id'] != fmea2['fmea_id']
        assert len(fmea_service._fmeas) == 2


class TestAddFailureMode:
    """Test adding failure modes to FMEA."""

    @pytest.fixture
    def fmea_service(self):
        """Create an FMEA service with an existing FMEA."""
        service = FMEAService()
        service.create_fmea(part_id="part-001", part_name="Test Part")
        return service

    @pytest.fixture
    def fmea_id(self, fmea_service):
        """Get the FMEA ID."""
        return list(fmea_service._fmeas.keys())[0]

    def test_add_failure_mode_basic(self, fmea_service, fmea_id):
        """Test adding a basic failure mode."""
        fm = fmea_service.add_failure_mode(
            fmea_id=fmea_id,
            description="Test failure mode",
            severity=5,
            occurrence=3,
            detection=4,
        )

        assert fm is not None
        assert fm['description'] == "Test failure mode"
        assert fm['severity'] == 5
        assert fm['occurrence'] == 3
        assert fm['detection'] == 4

    def test_add_failure_mode_calculates_rpn(self, fmea_service, fmea_id):
        """Test RPN is calculated correctly."""
        fm = fmea_service.add_failure_mode(
            fmea_id=fmea_id,
            description="Test failure",
            severity=8,
            occurrence=5,
            detection=6,
        )

        # RPN = Severity * Occurrence * Detection
        expected_rpn = 8 * 5 * 6  # 240
        assert fm['rpn'] == expected_rpn

    def test_add_failure_mode_with_details(self, fmea_service, fmea_id):
        """Test adding failure mode with full details."""
        fm = fmea_service.add_failure_mode(
            fmea_id=fmea_id,
            description="Part warping",
            severity=6,
            occurrence=4,
            detection=3,
            effect="Dimensional inaccuracy",
            cause="Uneven cooling",
            controls="Bed temperature monitoring",
            is_safety_critical=False,
        )

        assert fm['potential_effect'] == "Dimensional inaccuracy"
        assert fm['potential_cause'] == "Uneven cooling"
        assert fm['current_controls'] == "Bed temperature monitoring"
        assert fm['is_safety_critical'] is False

    def test_add_failure_mode_invalid_fmea(self, fmea_service):
        """Test adding failure mode to non-existent FMEA returns None."""
        fm = fmea_service.add_failure_mode(
            fmea_id="invalid-fmea-id",
            description="Test",
            severity=5,
            occurrence=5,
            detection=5,
        )

        assert fm is None

    def test_add_safety_critical_failure_mode(self, fmea_service, fmea_id):
        """Test adding a safety-critical failure mode."""
        fm = fmea_service.add_failure_mode(
            fmea_id=fmea_id,
            description="Structural failure",
            severity=10,
            occurrence=2,
            detection=5,
            is_safety_critical=True,
        )

        assert fm['is_safety_critical'] is True


class TestRPNCalculations:
    """Test RPN-related calculations."""

    @pytest.fixture
    def fmea_service(self):
        """Create an FMEA service."""
        return FMEAService()

    def test_rpn_minimum(self, fmea_service):
        """Test minimum RPN value."""
        fmea = fmea_service.create_fmea(part_id="p1", part_name="Test")
        fm = fmea_service.add_failure_mode(
            fmea_id=fmea['fmea_id'],
            description="Low risk",
            severity=1,
            occurrence=1,
            detection=1,
        )
        assert fm['rpn'] == 1

    def test_rpn_maximum(self, fmea_service):
        """Test maximum RPN value."""
        fmea = fmea_service.create_fmea(part_id="p1", part_name="Test")
        fm = fmea_service.add_failure_mode(
            fmea_id=fmea['fmea_id'],
            description="Extreme risk",
            severity=10,
            occurrence=10,
            detection=10,
        )
        assert fm['rpn'] == 1000

    def test_rpn_threshold_classification(self, fmea_service):
        """Test RPN threshold classifications."""
        fmea = fmea_service.create_fmea(part_id="p1", part_name="Test")

        # Below high threshold (RPN < 100)
        low = fmea_service.add_failure_mode(
            fmea_id=fmea['fmea_id'],
            description="Low",
            severity=3,
            occurrence=3,
            detection=3,  # RPN = 27
        )
        assert low['rpn'] < fmea_service.RPN_THRESHOLD_HIGH

        # High threshold (100 <= RPN < 200)
        high = fmea_service.add_failure_mode(
            fmea_id=fmea['fmea_id'],
            description="High",
            severity=5,
            occurrence=4,
            detection=6,  # RPN = 120
        )
        assert high['rpn'] >= fmea_service.RPN_THRESHOLD_HIGH
        assert high['rpn'] < fmea_service.RPN_THRESHOLD_CRITICAL

        # Critical threshold (200 <= RPN < 300)
        critical = fmea_service.add_failure_mode(
            fmea_id=fmea['fmea_id'],
            description="Critical",
            severity=7,
            occurrence=5,
            detection=6,  # RPN = 210
        )
        assert critical['rpn'] >= fmea_service.RPN_THRESHOLD_CRITICAL
        assert critical['rpn'] < fmea_service.RPN_THRESHOLD_IMMEDIATE


class TestDynamicFactorsIntegration:
    """Test dynamic factors with FMEA service."""

    @pytest.fixture
    def fmea_service(self):
        """Create an FMEA service with dynamic factors."""
        service = FMEAService()
        service._dynamic_factors["wc-001"] = DynamicFactors(
            machine_health=1.2,
            operator_skill=1.0,
        )
        return service

    def test_dynamic_factors_stored(self, fmea_service):
        """Test dynamic factors are stored by work center."""
        assert "wc-001" in fmea_service._dynamic_factors
        factors = fmea_service._dynamic_factors["wc-001"]
        assert factors.machine_health == 1.2

    def test_dynamic_factors_update(self, fmea_service):
        """Test updating dynamic factors."""
        fmea_service._dynamic_factors["wc-001"].spc_trend = 1.3
        factors = fmea_service._dynamic_factors["wc-001"]
        assert factors.spc_trend == 1.3
        assert factors.total_factor() == pytest.approx(1.56, rel=1e-2)  # 1.2 * 1.3


class TestLegoFailureModes:
    """Test LEGO-specific failure mode definitions."""

    @pytest.fixture
    def fmea_service(self):
        """Create an FMEA service."""
        return FMEAService()

    def test_stud_failure_modes(self, fmea_service):
        """Test stud-related failure modes."""
        assert 'stud_undersized' in fmea_service.LEGO_FAILURE_MODES
        assert 'stud_oversized' in fmea_service.LEGO_FAILURE_MODES

        undersized = fmea_service.LEGO_FAILURE_MODES['stud_undersized']
        assert undersized['severity'] > 5  # High severity for clutch issues

    def test_structural_failure_modes(self, fmea_service):
        """Test structural failure modes."""
        layer_adhesion = fmea_service.LEGO_FAILURE_MODES['layer_adhesion']
        assert layer_adhesion['severity'] >= 8  # High severity for structural weakness

    def test_cosmetic_failure_modes(self, fmea_service):
        """Test cosmetic failure modes have lower severity."""
        stringing = fmea_service.LEGO_FAILURE_MODES['stringing']
        assert stringing['severity'] < 5  # Lower severity for cosmetic issues

    def test_missing_feature_severity(self, fmea_service):
        """Test missing feature has high severity."""
        missing = fmea_service.LEGO_FAILURE_MODES['missing_feature']
        assert missing['severity'] >= 9  # Critical - part non-functional
