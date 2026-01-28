"""
LEGO Factory v3 - LEGO Models Unit Tests
========================================
"""

import pytest


class TestBrickDesignModel:
    """Tests for BrickDesign model."""

    def test_create_brick_design(self, db_session, sample_brick_design_data):
        """Test creating a brick design."""
        from models.lego.brick_designs import BrickDesign

        brick = BrickDesign(**sample_brick_design_data)
        db_session.add(brick)
        db_session.flush()

        assert brick.id is not None
        assert brick.design_id == 'BRICK-TEST-001'
        assert brick.studs_x == 2
        assert brick.studs_y == 4

    def test_brick_design_to_dict(self, db_session, sample_brick_design_data):
        """Test brick design serialization."""
        from models.lego.brick_designs import BrickDesign

        brick = BrickDesign(**sample_brick_design_data)
        db_session.add(brick)
        db_session.flush()

        data = brick.to_dict()

        assert 'design_id' in data
        assert 'studs_x' in data
        assert 'studs_y' in data
        assert 'dimensions' in data
        assert 'color' in data

    def test_brick_design_versioning(self, db_session, sample_brick_design_data):
        """Test brick design versioning (optimistic locking)."""
        from models.lego.brick_designs import BrickDesign

        brick = BrickDesign(**sample_brick_design_data)
        db_session.add(brick)
        db_session.flush()

        initial_version = brick.version
        brick.name = 'Updated Name'
        db_session.flush()

        assert brick.version == initial_version + 1


class TestBrickExportJobModel:
    """Tests for BrickExportJob model."""

    def test_create_export_job(self, db_session, sample_brick_design_data):
        """Test creating an export job."""
        from models.lego.brick_designs import BrickDesign, BrickExportJob, ExportFormat, ExportStatus

        brick = BrickDesign(**sample_brick_design_data)
        db_session.add(brick)
        db_session.flush()

        job = BrickExportJob(
            job_id='EXP-TEST-001',
            design_id=brick.id,
            export_format=ExportFormat.STL,
            status=ExportStatus.PENDING,
        )
        db_session.add(job)
        db_session.flush()

        assert job.id is not None
        assert job.job_id == 'EXP-TEST-001'
        assert job.status == ExportStatus.PENDING

    def test_export_job_with_slicing(self, db_session, sample_brick_design_data):
        """Test export job with slicing parameters."""
        from models.lego.brick_designs import BrickDesign, BrickExportJob, ExportFormat, PrinterType

        brick = BrickDesign(**sample_brick_design_data)
        db_session.add(brick)
        db_session.flush()

        job = BrickExportJob(
            job_id='EXP-TEST-002',
            design_id=brick.id,
            export_format=ExportFormat.GCODE,
            printer_type=PrinterType.PRUSA_MK4,
            layer_height=0.2,
            infill_percent=20,
            supports_enabled=False,
        )
        db_session.add(job)
        db_session.flush()

        assert job.layer_height == 0.2
        assert job.infill_percent == 20


class TestBrickColorModel:
    """Tests for BrickColor model."""

    def test_create_brick_color(self, db_session):
        """Test creating a brick color."""
        from models.lego.brick_designs import BrickColor

        color = BrickColor(
            color_id=999,
            name='Test Red',
            hex_code='#FF0000',
            rgb_r=255,
            rgb_g=0,
            rgb_b=0,
            is_current=True,
        )
        db_session.add(color)
        db_session.flush()

        assert color.id is not None
        assert color.name == 'Test Red'
        assert color.hex_code == '#FF0000'

    def test_brick_color_to_dict(self, db_session):
        """Test brick color serialization."""
        from models.lego.brick_designs import BrickColor

        color = BrickColor(
            color_id=998,
            name='Test Blue',
            hex_code='#0000FF',
            rgb_r=0,
            rgb_g=0,
            rgb_b=255,
        )
        db_session.add(color)
        db_session.flush()

        data = color.to_dict()

        assert 'color_id' in data
        assert 'name' in data
        assert 'hex' in data
        assert 'rgb' in data
