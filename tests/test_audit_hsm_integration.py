"""
Tests for HSM-Signed Audit Trail Integration

Tests verify:
- Seal creation with HSM keys
- Seal verification
- Seal chain integrity
- Tamper detection
- Integration with DigitalThread
"""

import json
import os
import tempfile
from datetime import datetime, timedelta

import pytest

# Import HSM sealer
from dashboard.services.traceability.hsm_sealer import (
    HSMSealer,
    AuditSeal,
    SealType,
    SealStatus,
    SealVerificationResult,
)

# Import HSM key manager
from dashboard.services.security.hsm.key_manager import (
    KeyManager,
    KeyManagerConfig,
    KeyType,
    KeyUsage,
    KeyState,
)

# Import audit chain
from dashboard.services.traceability.audit_chain import DigitalThread
from dashboard.services.traceability.audit_event import EntityType


@pytest.fixture
def key_manager():
    """Create a KeyManager for testing."""
    config = KeyManagerConfig(
        require_hsm=False,  # Use software keys for testing
        audit_enabled=True,
    )
    return KeyManager(config=config)


@pytest.fixture
def hsm_sealer(key_manager):
    """Create an HSMSealer with test key manager."""
    return HSMSealer(
        key_manager=key_manager,
        auto_create_key=True,
    )


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def digital_thread(temp_db):
    """Create a DigitalThread with temporary database."""
    return DigitalThread(
        db_path=temp_db,
        auto_verify=False,
        verify_on_startup=False,
    )


class TestHSMSealerBasics:
    """Basic HSMSealer functionality tests."""

    def test_initialization(self, key_manager):
        """Test HSMSealer initializes correctly."""
        sealer = HSMSealer(key_manager=key_manager)
        assert sealer is not None
        assert sealer._seal_key_id is not None

    def test_initialization_without_key_manager(self):
        """Test initialization without key manager (fallback mode)."""
        sealer = HSMSealer(key_manager=None)
        assert sealer is not None
        # Should work but use fallback key

    def test_seal_key_created(self, key_manager):
        """Test that seal key is created automatically."""
        sealer = HSMSealer(key_manager=key_manager, auto_create_key=True)

        # Verify key was created
        key_metadata = key_manager.get_key_metadata(sealer._seal_key_id)
        assert key_metadata is not None
        assert key_metadata.key_type == KeyType.HMAC_SHA256
        assert KeyUsage.SIGN in key_metadata.usage
        assert KeyUsage.VERIFY in key_metadata.usage


class TestSealCreation:
    """Tests for seal creation."""

    def test_create_daily_seal(self, hsm_sealer):
        """Test creating a daily seal."""
        seal = hsm_sealer.create_seal(
            chain_hash="abc123def456",
            event_count=100,
            seal_type=SealType.DAILY,
        )

        assert seal is not None
        assert seal.seal_id.startswith("seal_daily_")
        assert seal.chain_hash == "abc123def456"
        assert seal.event_count == 100
        assert seal.seal_type == SealType.DAILY
        assert seal.signature is not None
        assert len(seal.signature) == 64  # SHA256 hex

    def test_create_checkpoint_seal(self, hsm_sealer):
        """Test creating a checkpoint seal."""
        seal = hsm_sealer.create_seal(
            chain_hash="xyz789",
            event_count=50,
            seal_type=SealType.CHECKPOINT,
        )

        assert seal.seal_type == SealType.CHECKPOINT
        assert seal.chain_hash == "xyz789"

    def test_seal_contains_timestamp(self, hsm_sealer):
        """Test that seal contains timestamp."""
        seal = hsm_sealer.create_seal(
            chain_hash="hash123",
            event_count=10,
        )

        assert seal.timestamp is not None
        assert isinstance(seal.timestamp, datetime)
        # Should be recent
        assert (datetime.utcnow() - seal.timestamp).total_seconds() < 60

    def test_seal_metadata(self, hsm_sealer):
        """Test seal with custom metadata."""
        metadata = {
            "operator": "test_user",
            "reason": "scheduled_seal",
            "location": "factory_1",
        }

        seal = hsm_sealer.create_seal(
            chain_hash="hash456",
            event_count=200,
            metadata=metadata,
        )

        assert seal.metadata == metadata

    def test_seal_chaining(self, hsm_sealer):
        """Test that seals are chained together."""
        # Create first seal
        seal1 = hsm_sealer.create_seal(
            chain_hash="hash1",
            event_count=100,
        )

        # Create second seal
        seal2 = hsm_sealer.create_seal(
            chain_hash="hash2",
            event_count=200,
        )

        # Second seal should reference first
        assert seal2.previous_seal_id == seal1.seal_id
        assert seal2.previous_seal_hash == seal1.compute_hash()


class TestSealVerification:
    """Tests for seal verification."""

    def test_verify_valid_seal(self, hsm_sealer):
        """Test verifying a valid seal."""
        seal = hsm_sealer.create_seal(
            chain_hash="valid_hash",
            event_count=100,
        )

        result = hsm_sealer.verify_seal(seal)

        assert result.is_valid is True
        assert result.status == SealStatus.VALID
        assert result.seal_id == seal.seal_id

    def test_detect_tampered_signature(self, hsm_sealer):
        """Test detection of tampered signature."""
        seal = hsm_sealer.create_seal(
            chain_hash="original_hash",
            event_count=100,
        )

        # Tamper with signature
        seal.signature = "tampered_signature_00000000000000000000000000000000"

        result = hsm_sealer.verify_seal(seal)

        assert result.is_valid is False
        assert result.status == SealStatus.TAMPERED
        assert "tampered" in result.error_message.lower()

    def test_detect_tampered_chain_hash(self, hsm_sealer):
        """Test detection of tampered chain hash."""
        seal = hsm_sealer.create_seal(
            chain_hash="original_hash",
            event_count=100,
        )

        original_signature = seal.signature

        # Tamper with chain hash (signature won't match)
        seal.chain_hash = "tampered_hash"

        result = hsm_sealer.verify_seal(seal)

        assert result.is_valid is False
        assert result.status == SealStatus.TAMPERED

    def test_detect_tampered_event_count(self, hsm_sealer):
        """Test detection of tampered event count."""
        seal = hsm_sealer.create_seal(
            chain_hash="hash123",
            event_count=100,
        )

        # Tamper with event count
        seal.event_count = 999

        result = hsm_sealer.verify_seal(seal)

        assert result.is_valid is False
        assert result.status == SealStatus.TAMPERED


class TestSealChainVerification:
    """Tests for seal chain verification."""

    def test_verify_valid_chain(self, hsm_sealer):
        """Test verifying a valid seal chain."""
        # Create chain of seals
        seals = []
        for i in range(5):
            seal = hsm_sealer.create_seal(
                chain_hash=f"hash_{i}",
                event_count=(i + 1) * 100,
            )
            seals.append(seal)

        # Verify chain
        all_valid, results = hsm_sealer.verify_seal_chain(seals)

        assert all_valid is True
        assert len(results) == 5
        assert all(r.is_valid for r in results)

    def test_detect_broken_chain(self, hsm_sealer):
        """Test detection of broken seal chain."""
        # Create seals
        seal1 = hsm_sealer.create_seal(chain_hash="h1", event_count=100)
        seal2 = hsm_sealer.create_seal(chain_hash="h2", event_count=200)
        seal3 = hsm_sealer.create_seal(chain_hash="h3", event_count=300)

        # Break the chain by modifying previous_seal_hash
        seal2.previous_seal_hash = "wrong_hash"

        seals = [seal1, seal2, seal3]
        all_valid, results = hsm_sealer.verify_seal_chain(seals)

        assert all_valid is False


class TestSealPersistence:
    """Tests for seal import/export."""

    def test_export_seals(self, hsm_sealer):
        """Test exporting seals to file."""
        # Create some seals
        hsm_sealer.create_seal(chain_hash="h1", event_count=100)
        hsm_sealer.create_seal(chain_hash="h2", event_count=200)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            export_path = f.name

        try:
            count = hsm_sealer.export_seals(export_path)
            assert count == 2

            # Verify file content
            with open(export_path, 'r') as f:
                data = json.load(f)

            assert data["seal_count"] == 2
            assert len(data["seals"]) == 2
        finally:
            os.unlink(export_path)

    def test_import_seals(self, key_manager):
        """Test importing seals from file."""
        # Create sealer and seals
        sealer1 = HSMSealer(key_manager=key_manager)
        seal1 = sealer1.create_seal(chain_hash="h1", event_count=100)
        seal2 = sealer1.create_seal(chain_hash="h2", event_count=200)

        # Export
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            export_path = f.name

        try:
            sealer1.export_seals(export_path)

            # Create new sealer and import
            sealer2 = HSMSealer(key_manager=key_manager)
            count = sealer2.import_seals(export_path)

            assert count == 2
            assert sealer2.get_seal(seal1.seal_id) is not None
            assert sealer2.get_seal(seal2.seal_id) is not None
        finally:
            os.unlink(export_path)

    def test_seal_serialization(self, hsm_sealer):
        """Test seal to_dict and from_dict."""
        seal = hsm_sealer.create_seal(
            chain_hash="test_hash",
            event_count=500,
            metadata={"test": "data"},
        )

        # Serialize
        seal_dict = seal.to_dict()

        # Deserialize
        restored = AuditSeal.from_dict(seal_dict)

        assert restored.seal_id == seal.seal_id
        assert restored.chain_hash == seal.chain_hash
        assert restored.event_count == seal.event_count
        assert restored.signature == seal.signature
        assert restored.metadata == seal.metadata


class TestDigitalThreadIntegration:
    """Tests for integration with DigitalThread."""

    def test_seal_after_events(self, hsm_sealer, digital_thread):
        """Test creating seal after logging events."""
        # Log some events
        for i in range(10):
            digital_thread.log_work_order_event(
                entity_id=f"WO-{i:03d}",
                action="created",
                description=f"Work order {i}",
            )

        # Get chain statistics
        stats = digital_thread.get_chain_statistics()

        # Create seal
        seal = hsm_sealer.create_seal(
            chain_hash=digital_thread._last_hash,
            event_count=stats["total_events"],
        )

        assert seal.event_count == 10
        assert seal.chain_hash == digital_thread._last_hash

        # Verify seal
        result = hsm_sealer.verify_seal(seal)
        assert result.is_valid is True

    def test_tamper_detection_integration(self, hsm_sealer, digital_thread):
        """Test tamper detection with real events."""
        # Log events
        for i in range(5):
            digital_thread.log_equipment_event(
                entity_id=f"EQ-{i:03d}",
                action="started",
            )

        # Create seal with correct hash
        correct_hash = digital_thread._last_hash
        seal = hsm_sealer.create_seal(
            chain_hash=correct_hash,
            event_count=5,
        )

        # Verify - should pass
        result1 = hsm_sealer.verify_seal(seal)
        assert result1.is_valid is True

        # Now verify that if the chain_hash changed, we'd detect it
        # (simulating tamper detection in production)
        tampered_seal = AuditSeal(
            seal_id=seal.seal_id,
            seal_type=seal.seal_type,
            chain_hash="different_hash",  # Tampered
            event_count=seal.event_count,
            timestamp=seal.timestamp,
            previous_seal_id=seal.previous_seal_id,
            previous_seal_hash=seal.previous_seal_hash,
            signature=seal.signature,  # Original signature won't match
            key_id=seal.key_id,
        )

        result2 = hsm_sealer.verify_seal(tampered_seal)
        assert result2.is_valid is False


class TestSealStatistics:
    """Tests for seal statistics."""

    def test_get_statistics_empty(self, hsm_sealer):
        """Test statistics with no seals."""
        stats = hsm_sealer.get_statistics()

        assert stats["total_seals"] == 0
        assert stats["seals_by_type"] == {}
        assert stats["first_seal"] is None

    def test_get_statistics(self, hsm_sealer):
        """Test statistics with seals."""
        # Create various seals
        hsm_sealer.create_seal("h1", 100, SealType.DAILY)
        hsm_sealer.create_seal("h2", 200, SealType.DAILY)
        hsm_sealer.create_seal("h3", 300, SealType.CHECKPOINT)

        stats = hsm_sealer.get_statistics()

        assert stats["total_seals"] == 3
        assert stats["seals_by_type"]["daily"] == 2
        assert stats["seals_by_type"]["checkpoint"] == 1
        assert stats["first_seal"] is not None
        assert stats["last_seal"] is not None


class TestSealQueries:
    """Tests for seal query methods."""

    def test_get_seal(self, hsm_sealer):
        """Test getting seal by ID."""
        seal = hsm_sealer.create_seal("hash", 100)

        retrieved = hsm_sealer.get_seal(seal.seal_id)
        assert retrieved is not None
        assert retrieved.seal_id == seal.seal_id

    def test_get_nonexistent_seal(self, hsm_sealer):
        """Test getting nonexistent seal."""
        result = hsm_sealer.get_seal("nonexistent_seal")
        assert result is None

    def test_get_latest_seal(self, hsm_sealer):
        """Test getting latest seal."""
        seal1 = hsm_sealer.create_seal("h1", 100)
        seal2 = hsm_sealer.create_seal("h2", 200)
        seal3 = hsm_sealer.create_seal("h3", 300)

        latest = hsm_sealer.get_latest_seal()
        assert latest is not None
        assert latest.seal_id == seal3.seal_id

    def test_list_seals_by_type(self, hsm_sealer):
        """Test listing seals filtered by type."""
        hsm_sealer.create_seal("h1", 100, SealType.DAILY)
        hsm_sealer.create_seal("h2", 200, SealType.DAILY)
        hsm_sealer.create_seal("h3", 300, SealType.CHECKPOINT)

        daily_seals = hsm_sealer.list_seals(seal_type=SealType.DAILY)
        assert len(daily_seals) == 2

        checkpoint_seals = hsm_sealer.list_seals(seal_type=SealType.CHECKPOINT)
        assert len(checkpoint_seals) == 1
