"""
Migration Manager - Database Schema Migrations.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Platform Infrastructure

Provides database migration management for schema evolution.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum
import hashlib
import logging
import uuid

logger = logging.getLogger(__name__)


class MigrationStatus(Enum):
    """Migration execution status."""
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class MigrationDirection(Enum):
    """Migration direction."""
    UP = "up"
    DOWN = "down"


@dataclass
class Migration:
    """A database migration."""
    migration_id: str
    version: str
    name: str
    description: str
    up_sql: str
    down_sql: str
    status: MigrationStatus
    created_at: datetime
    applied_at: Optional[datetime] = None
    applied_by: Optional[str] = None
    execution_time_ms: Optional[int] = None
    checksum: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "migration_id": self.migration_id,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "up_sql": self.up_sql,
            "down_sql": self.down_sql,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "applied_by": self.applied_by,
            "execution_time_ms": self.execution_time_ms,
            "checksum": self.checksum,
            "dependencies": self.dependencies,
        }

    def compute_checksum(self) -> str:
        """Compute checksum of migration SQL."""
        content = f"{self.up_sql}{self.down_sql}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class MigrationManager:
    """
    Manages database schema migrations.

    Features:
    - Version-based migration ordering
    - Up and down migrations (rollback)
    - Checksum verification
    - Dependency management
    - Migration history tracking
    - Dry-run support
    """

    def __init__(self, migrations_path: str = "/migrations"):
        self.migrations_path = migrations_path
        self.migrations: Dict[str, Migration] = {}
        self.applied_order: List[str] = []
        self._initialize_sample_migrations()

    def _initialize_sample_migrations(self):
        """Initialize with sample migrations."""
        migrations = [
            Migration(
                migration_id=str(uuid.uuid4()),
                version="001",
                name="create_experiments_table",
                description="Create experiments table for ML experiment tracking",
                up_sql="""
                CREATE TABLE experiments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    status VARCHAR(50) DEFAULT 'created',
                    params JSONB DEFAULT '{}',
                    metrics JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                CREATE INDEX idx_experiments_status ON experiments(status);
                CREATE INDEX idx_experiments_created_at ON experiments(created_at);
                """,
                down_sql="""
                DROP TABLE IF EXISTS experiments;
                """,
                status=MigrationStatus.APPLIED,
                created_at=datetime(2024, 1, 1),
                applied_at=datetime(2024, 1, 1),
                applied_by="system",
                execution_time_ms=45,
            ),
            Migration(
                migration_id=str(uuid.uuid4()),
                version="002",
                name="create_model_registry_table",
                description="Create model registry for versioned model storage",
                up_sql="""
                CREATE TABLE models (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    version VARCHAR(50) NOT NULL,
                    stage VARCHAR(50) DEFAULT 'staging',
                    artifact_path VARCHAR(500),
                    metrics JSONB DEFAULT '{}',
                    experiment_id UUID REFERENCES experiments(id),
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(name, version)
                );
                CREATE INDEX idx_models_name ON models(name);
                CREATE INDEX idx_models_stage ON models(stage);
                """,
                down_sql="""
                DROP TABLE IF EXISTS models;
                """,
                status=MigrationStatus.APPLIED,
                created_at=datetime(2024, 1, 2),
                applied_at=datetime(2024, 1, 2),
                applied_by="system",
                execution_time_ms=32,
                dependencies=["001"],
            ),
            Migration(
                migration_id=str(uuid.uuid4()),
                version="003",
                name="create_causal_graphs_table",
                description="Create table for storing causal graph structures",
                up_sql="""
                CREATE TABLE causal_graphs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    domain VARCHAR(100) NOT NULL,
                    graph_data JSONB NOT NULL,
                    nodes JSONB DEFAULT '[]',
                    edges JSONB DEFAULT '[]',
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                CREATE INDEX idx_causal_graphs_domain ON causal_graphs(domain);
                """,
                down_sql="""
                DROP TABLE IF EXISTS causal_graphs;
                """,
                status=MigrationStatus.APPLIED,
                created_at=datetime(2024, 1, 3),
                applied_at=datetime(2024, 1, 3),
                applied_by="system",
                execution_time_ms=28,
            ),
            Migration(
                migration_id=str(uuid.uuid4()),
                version="004",
                name="create_action_audit_table",
                description="Create audit trail for AI action approvals",
                up_sql="""
                CREATE TABLE action_audit (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    action_type VARCHAR(100) NOT NULL,
                    action_data JSONB NOT NULL,
                    source_agent VARCHAR(100),
                    status VARCHAR(50) DEFAULT 'pending',
                    risk_level VARCHAR(20),
                    approved_by VARCHAR(100),
                    approved_at TIMESTAMP,
                    executed_at TIMESTAMP,
                    result JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE INDEX idx_action_audit_status ON action_audit(status);
                CREATE INDEX idx_action_audit_created_at ON action_audit(created_at);
                """,
                down_sql="""
                DROP TABLE IF EXISTS action_audit;
                """,
                status=MigrationStatus.PENDING,
                created_at=datetime(2024, 1, 4),
            ),
            Migration(
                migration_id=str(uuid.uuid4()),
                version="005",
                name="add_experiment_artifacts",
                description="Add artifacts table linked to experiments",
                up_sql="""
                CREATE TABLE artifacts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    experiment_id UUID REFERENCES experiments(id),
                    name VARCHAR(255) NOT NULL,
                    artifact_type VARCHAR(50) NOT NULL,
                    path VARCHAR(500) NOT NULL,
                    size_bytes BIGINT,
                    checksum VARCHAR(64),
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE INDEX idx_artifacts_experiment ON artifacts(experiment_id);
                CREATE INDEX idx_artifacts_type ON artifacts(artifact_type);
                """,
                down_sql="""
                DROP TABLE IF EXISTS artifacts;
                """,
                status=MigrationStatus.PENDING,
                created_at=datetime(2024, 1, 5),
                dependencies=["001"],
            ),
        ]

        for m in migrations:
            m.checksum = m.compute_checksum()
            self.migrations[m.version] = m
            if m.status == MigrationStatus.APPLIED:
                self.applied_order.append(m.version)

    def add_migration(
        self,
        version: str,
        name: str,
        description: str,
        up_sql: str,
        down_sql: str,
        dependencies: Optional[List[str]] = None,
    ) -> Migration:
        """Add a new migration."""
        if version in self.migrations:
            raise ValueError(f"Migration version already exists: {version}")

        migration = Migration(
            migration_id=str(uuid.uuid4()),
            version=version,
            name=name,
            description=description,
            up_sql=up_sql,
            down_sql=down_sql,
            status=MigrationStatus.PENDING,
            created_at=datetime.now(),
            dependencies=dependencies or [],
        )
        migration.checksum = migration.compute_checksum()

        self.migrations[version] = migration
        logger.info(f"Added migration: {version} - {name}")

        return migration

    def get_pending_migrations(self) -> List[Migration]:
        """Get all pending migrations in order."""
        pending = [
            m for m in self.migrations.values()
            if m.status == MigrationStatus.PENDING
        ]
        return sorted(pending, key=lambda m: m.version)

    def get_applied_migrations(self) -> List[Migration]:
        """Get all applied migrations in order."""
        return [
            self.migrations[v] for v in self.applied_order
            if v in self.migrations
        ]

    def migrate(
        self,
        target_version: Optional[str] = None,
        dry_run: bool = False,
    ) -> List[Dict[str, Any]]:
        """Run pending migrations up to target version."""
        pending = self.get_pending_migrations()

        if target_version:
            pending = [m for m in pending if m.version <= target_version]

        results = []
        for migration in pending:
            # Check dependencies
            for dep in migration.dependencies:
                if dep not in self.applied_order:
                    raise ValueError(
                        f"Migration {migration.version} depends on {dep} which is not applied"
                    )

            result = self._apply_migration(migration, dry_run)
            results.append(result)

            if result.get("error"):
                break

        return results

    def rollback(
        self,
        steps: int = 1,
        dry_run: bool = False,
    ) -> List[Dict[str, Any]]:
        """Rollback applied migrations."""
        if not self.applied_order:
            return []

        to_rollback = list(reversed(self.applied_order[-steps:]))
        results = []

        for version in to_rollback:
            migration = self.migrations.get(version)
            if migration:
                result = self._rollback_migration(migration, dry_run)
                results.append(result)

        return results

    def _apply_migration(
        self,
        migration: Migration,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Apply a single migration."""
        start_time = datetime.now()

        logger.info(f"Applying migration: {migration.version} - {migration.name}")

        if dry_run:
            return {
                "version": migration.version,
                "name": migration.name,
                "action": "apply",
                "dry_run": True,
                "sql": migration.up_sql,
            }

        try:
            # Simulate execution
            execution_time = 50  # ms

            migration.status = MigrationStatus.APPLIED
            migration.applied_at = datetime.now()
            migration.applied_by = "migration_manager"
            migration.execution_time_ms = execution_time

            self.applied_order.append(migration.version)

            logger.info(f"Applied migration: {migration.version} in {execution_time}ms")

            return {
                "version": migration.version,
                "name": migration.name,
                "action": "apply",
                "status": "success",
                "execution_time_ms": execution_time,
            }

        except Exception as e:
            migration.status = MigrationStatus.FAILED
            logger.error(f"Migration failed: {migration.version} - {e}")

            return {
                "version": migration.version,
                "name": migration.name,
                "action": "apply",
                "status": "failed",
                "error": str(e),
            }

    def _rollback_migration(
        self,
        migration: Migration,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Rollback a single migration."""
        logger.info(f"Rolling back migration: {migration.version} - {migration.name}")

        if dry_run:
            return {
                "version": migration.version,
                "name": migration.name,
                "action": "rollback",
                "dry_run": True,
                "sql": migration.down_sql,
            }

        try:
            # Simulate execution
            execution_time = 30  # ms

            migration.status = MigrationStatus.ROLLED_BACK
            migration.applied_at = None
            migration.applied_by = None

            if migration.version in self.applied_order:
                self.applied_order.remove(migration.version)

            logger.info(f"Rolled back migration: {migration.version}")

            return {
                "version": migration.version,
                "name": migration.name,
                "action": "rollback",
                "status": "success",
                "execution_time_ms": execution_time,
            }

        except Exception as e:
            logger.error(f"Rollback failed: {migration.version} - {e}")

            return {
                "version": migration.version,
                "name": migration.name,
                "action": "rollback",
                "status": "failed",
                "error": str(e),
            }

    def get_status(self) -> Dict[str, Any]:
        """Get migration status summary."""
        pending = len([m for m in self.migrations.values() if m.status == MigrationStatus.PENDING])
        applied = len([m for m in self.migrations.values() if m.status == MigrationStatus.APPLIED])
        failed = len([m for m in self.migrations.values() if m.status == MigrationStatus.FAILED])

        return {
            "total_migrations": len(self.migrations),
            "pending": pending,
            "applied": applied,
            "failed": failed,
            "current_version": self.applied_order[-1] if self.applied_order else None,
            "pending_migrations": [
                {"version": m.version, "name": m.name}
                for m in self.get_pending_migrations()
            ],
        }

    def verify_checksums(self) -> List[Dict[str, Any]]:
        """Verify migration checksums for applied migrations."""
        issues = []

        for version in self.applied_order:
            migration = self.migrations.get(version)
            if migration:
                current_checksum = migration.compute_checksum()
                if migration.checksum != current_checksum:
                    issues.append({
                        "version": version,
                        "name": migration.name,
                        "expected_checksum": migration.checksum,
                        "current_checksum": current_checksum,
                        "issue": "checksum_mismatch",
                    })

        return issues
