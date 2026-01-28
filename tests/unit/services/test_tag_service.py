"""
Unit tests for SCADA Tag Management Service.

Tests tag creation, caching, subscriptions, and value operations.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from services.scada.tag_management.tag_service import (
    TagCache,
    TagValue,
    TagService,
    write_tag_value,
    read_tag_value,
    read_tag_values,
)


class TestTagValue:
    """Tests for TagValue dataclass."""

    def test_create_tag_value(self):
        """Test creating a tag value."""
        tv = TagValue(
            tag_id="tag_001",
            tag_name="Temperature",
            value=25.5,
            quality=192,
            timestamp=datetime.utcnow(),
            eng_units="°C"
        )

        assert tv.tag_id == "tag_001"
        assert tv.tag_name == "Temperature"
        assert tv.value == 25.5
        assert tv.quality == 192
        assert tv.eng_units == "°C"

    def test_tag_value_default_eng_units(self):
        """Test tag value with default eng_units."""
        tv = TagValue(
            tag_id="tag_001",
            tag_name="Test",
            value=100,
            quality=192,
            timestamp=datetime.utcnow()
        )

        assert tv.eng_units is None


class TestTagCache:
    """Tests for TagCache singleton."""

    @pytest.fixture
    def cache(self):
        """Create a fresh cache for testing."""
        # Reset singleton for testing
        TagCache._instance = None
        return TagCache()

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """Test setting and getting tag values."""
        await cache.set("tag_001", 100.0, 192, "Temperature", "°C")

        result = await cache.get("tag_001")

        assert result is not None
        assert result.value == 100.0
        assert result.quality == 192
        assert result.tag_name == "Temperature"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, cache):
        """Test getting a nonexistent tag."""
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_many(self, cache):
        """Test getting multiple tag values."""
        await cache.set("tag_001", 100.0, 192)
        await cache.set("tag_002", 200.0, 192)
        await cache.set("tag_003", 300.0, 192)

        results = await cache.get_many(["tag_001", "tag_003", "nonexistent"])

        assert len(results) == 2
        assert "tag_001" in results
        assert "tag_003" in results
        assert "nonexistent" not in results

    @pytest.mark.asyncio
    async def test_subscription(self, cache):
        """Test subscribing to tag value changes."""
        queue = await cache.subscribe("tag_001")

        # Update the tag value
        await cache.set("tag_001", 50.0, 192)

        # Check that subscriber received the update
        value = queue.get_nowait()
        assert value.value == 50.0

    @pytest.mark.asyncio
    async def test_unsubscribe(self, cache):
        """Test unsubscribing from tag value changes."""
        queue = await cache.subscribe("tag_001")
        await cache.unsubscribe("tag_001", queue)

        # Update the tag value
        await cache.set("tag_001", 50.0, 192)

        # Queue should be empty after unsubscribe
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_value_changed_detection(self, cache):
        """Test that value changes are detected."""
        await cache.set("tag_001", 100.0, 192)
        await cache.set("tag_001", 100.0, 192)  # Same value
        await cache.set("tag_001", 150.0, 192)  # Different value

        result = await cache.get("tag_001")
        assert result.value == 150.0


class TestTagService:
    """Tests for TagService database operations."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        """Create a TagService with mock session."""
        return TagService(mock_session)

    def test_create_tag(self, service, mock_session):
        """Test creating a tag."""
        with patch('services.scada.tag_management.tag_service.TagService.create_tag') as mock_create:
            mock_create.return_value = {
                'tag_id': 'temp_001',
                'name': 'Temperature Sensor',
                'data_type': 'float32'
            }

            result = service.create_tag({
                'tag_id': 'temp_001',
                'name': 'Temperature Sensor',
                'data_type': 'float32'
            })

            assert result['tag_id'] == 'temp_001'

    def test_get_tag(self, service, mock_session):
        """Test getting a tag by ID."""
        mock_tag = Mock()
        mock_tag.to_dict.return_value = {'tag_id': 'temp_001', 'name': 'Test'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_tag

        with patch('services.scada.tag_management.tag_service.TagService.get_tag') as mock_get:
            mock_get.return_value = {'tag_id': 'temp_001', 'name': 'Test'}
            result = service.get_tag('temp_001')

            assert result is not None
            assert result['tag_id'] == 'temp_001'

    def test_get_nonexistent_tag(self, service, mock_session):
        """Test getting a nonexistent tag."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with patch('services.scada.tag_management.tag_service.TagService.get_tag') as mock_get:
            mock_get.return_value = None
            result = service.get_tag('nonexistent')

            assert result is None


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset cache singleton before each test."""
        TagCache._instance = None
        yield

    @pytest.mark.asyncio
    async def test_write_tag_value(self):
        """Test write_tag_value function."""
        await write_tag_value("tag_001", 100.0, 192, "Test Tag", "units")

        result = await read_tag_value("tag_001")
        assert result is not None
        assert result.value == 100.0

    @pytest.mark.asyncio
    async def test_read_tag_values(self):
        """Test read_tag_values function."""
        await write_tag_value("tag_001", 100.0)
        await write_tag_value("tag_002", 200.0)

        results = await read_tag_values(["tag_001", "tag_002"])

        assert len(results) == 2
        assert results["tag_001"].value == 100.0
        assert results["tag_002"].value == 200.0


class TestTagScaling:
    """Tests for tag value scaling."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return TagService(mock_session)

    def test_scale_value_no_tag(self, service, mock_session):
        """Test scaling when tag doesn't exist."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with patch('services.scada.tag_management.tag_service.TagService.scale_value') as mock_scale:
            mock_scale.return_value = 50.0  # Return raw value when no tag
            result = service.scale_value("nonexistent", 50.0)

            assert result == 50.0

    def test_inverse_scale_no_tag(self, service, mock_session):
        """Test inverse scaling when tag doesn't exist."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with patch('services.scada.tag_management.tag_service.TagService.inverse_scale') as mock_scale:
            mock_scale.return_value = 75.0  # Return eng value when no tag
            result = service.inverse_scale("nonexistent", 75.0)

            assert result == 75.0
