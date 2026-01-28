#!/usr/bin/env python3
"""
Backup and Recovery Procedures for LEGO Factory.

Provides comprehensive backup and restore functionality for:
- PostgreSQL/TimescaleDB database
- Configuration files
- ML models
- Historian data exports
"""

import os
import sys
import json
import shutil
import logging
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
import tarfile
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BackupManager:
    """Manages backup and restore operations."""

    def __init__(self, backup_dir: str = "/var/backups/lego-factory"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Configuration
        self.db_host = os.getenv("DATABASE_HOST", "localhost")
        self.db_port = os.getenv("DATABASE_PORT", "5432")
        self.db_name = os.getenv("DATABASE_NAME", "lego_factory")
        self.db_user = os.getenv("DATABASE_USER", "lego_factory_user")
        self.db_password = os.getenv("DATABASE_PASSWORD", "")

        self.retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

    def create_backup(self, backup_type: str = "full") -> Optional[str]:
        """
        Create a backup of the specified type.

        Args:
            backup_type: Type of backup ('full', 'database', 'config', 'models')

        Returns:
            Path to the created backup file, or None on failure
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"lego_factory_{backup_type}_{timestamp}"
        backup_path = self.backup_dir / backup_name

        logger.info(f"Starting {backup_type} backup: {backup_name}")

        try:
            backup_path.mkdir(parents=True, exist_ok=True)
            manifest = {
                "backup_name": backup_name,
                "backup_type": backup_type,
                "timestamp": timestamp,
                "created_at": datetime.utcnow().isoformat(),
                "components": []
            }

            if backup_type in ("full", "database"):
                if self._backup_database(backup_path):
                    manifest["components"].append("database")

            if backup_type in ("full", "config"):
                if self._backup_config(backup_path):
                    manifest["components"].append("config")

            if backup_type in ("full", "models"):
                if self._backup_models(backup_path):
                    manifest["components"].append("models")

            # Save manifest
            manifest_path = backup_path / "manifest.json"
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)

            # Create tarball
            tarball_path = self._create_tarball(backup_path)

            # Clean up temporary directory
            shutil.rmtree(backup_path)

            # Verify backup
            if self._verify_backup(tarball_path):
                logger.info(f"Backup created successfully: {tarball_path}")
                return str(tarball_path)
            else:
                logger.error("Backup verification failed")
                return None

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            if backup_path.exists():
                shutil.rmtree(backup_path)
            return None

    def _backup_database(self, backup_path: Path) -> bool:
        """Backup PostgreSQL/TimescaleDB database."""
        logger.info("Backing up database...")

        dump_file = backup_path / "database.sql"

        env = os.environ.copy()
        env["PGPASSWORD"] = self.db_password

        try:
            # Use pg_dump for database backup
            cmd = [
                "pg_dump",
                "-h", self.db_host,
                "-p", self.db_port,
                "-U", self.db_user,
                "-d", self.db_name,
                "-F", "c",  # Custom format for compression
                "-b",  # Include large objects
                "-v",  # Verbose
                "-f", str(dump_file)
            ]

            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            if result.returncode != 0:
                logger.error(f"pg_dump failed: {result.stderr}")
                return False

            # Calculate checksum
            checksum = self._calculate_checksum(dump_file)
            with open(backup_path / "database.sha256", "w") as f:
                f.write(f"{checksum}  database.sql\n")

            logger.info(f"Database backup complete: {dump_file.stat().st_size / 1024 / 1024:.2f} MB")
            return True

        except subprocess.TimeoutExpired:
            logger.error("Database backup timed out")
            return False
        except FileNotFoundError:
            logger.error("pg_dump not found - ensure PostgreSQL client is installed")
            return False
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return False

    def _backup_config(self, backup_path: Path) -> bool:
        """Backup configuration files."""
        logger.info("Backing up configuration...")

        config_backup_dir = backup_path / "config"
        config_backup_dir.mkdir(parents=True, exist_ok=True)

        config_paths = [
            "config/",
            ".env",
            "docker-compose.yml",
            "docker-compose.prod.yml",
            "k8s/",
        ]

        project_root = Path(__file__).parent.parent

        for config_path in config_paths:
            src = project_root / config_path
            if src.exists():
                if src.is_dir():
                    dst = config_backup_dir / config_path
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, config_backup_dir / config_path)
                logger.info(f"  Backed up: {config_path}")

        return True

    def _backup_models(self, backup_path: Path) -> bool:
        """Backup ML models."""
        logger.info("Backing up ML models...")

        models_backup_dir = backup_path / "models"
        models_backup_dir.mkdir(parents=True, exist_ok=True)

        project_root = Path(__file__).parent.parent
        models_dir = project_root / "models"

        if models_dir.exists():
            for model_file in models_dir.glob("**/*.pt"):
                rel_path = model_file.relative_to(models_dir)
                dst = models_backup_dir / rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(model_file, dst)
                logger.info(f"  Backed up model: {rel_path}")

            for config_file in models_dir.glob("**/*.json"):
                rel_path = config_file.relative_to(models_dir)
                dst = models_backup_dir / rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(config_file, dst)

        return True

    def _create_tarball(self, backup_path: Path) -> Path:
        """Create a compressed tarball of the backup."""
        tarball_path = backup_path.with_suffix(".tar.gz")

        with tarfile.open(tarball_path, "w:gz") as tar:
            tar.add(backup_path, arcname=backup_path.name)

        return tarball_path

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _verify_backup(self, tarball_path: Path) -> bool:
        """Verify backup integrity."""
        logger.info("Verifying backup integrity...")

        try:
            with tarfile.open(tarball_path, "r:gz") as tar:
                # Check manifest exists
                members = tar.getnames()
                manifest_found = any("manifest.json" in m for m in members)
                if not manifest_found:
                    logger.error("Manifest not found in backup")
                    return False

            logger.info("Backup verification passed")
            return True

        except tarfile.TarError as e:
            logger.error(f"Backup verification failed: {e}")
            return False

    def restore_backup(self, backup_path: str, components: List[str] = None) -> bool:
        """
        Restore from a backup.

        Args:
            backup_path: Path to the backup tarball
            components: List of components to restore (default: all)

        Returns:
            True if restore succeeded
        """
        backup_path = Path(backup_path)

        if not backup_path.exists():
            logger.error(f"Backup not found: {backup_path}")
            return False

        logger.info(f"Starting restore from: {backup_path}")

        # Extract to temporary directory
        temp_dir = self.backup_dir / "temp_restore"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(temp_dir)

            # Find extracted backup directory
            extracted_dirs = list(temp_dir.iterdir())
            if not extracted_dirs:
                logger.error("No content in backup archive")
                return False

            backup_dir = extracted_dirs[0]

            # Load manifest
            manifest_path = backup_dir / "manifest.json"
            if not manifest_path.exists():
                logger.error("Manifest not found")
                return False

            with open(manifest_path) as f:
                manifest = json.load(f)

            logger.info(f"Restoring backup: {manifest['backup_name']}")
            logger.info(f"Created: {manifest['created_at']}")
            logger.info(f"Components: {manifest['components']}")

            # Determine components to restore
            if components is None:
                components = manifest["components"]

            # Restore each component
            success = True

            if "database" in components and "database" in manifest["components"]:
                if not self._restore_database(backup_dir):
                    success = False

            if "config" in components and "config" in manifest["components"]:
                if not self._restore_config(backup_dir):
                    success = False

            if "models" in components and "models" in manifest["components"]:
                if not self._restore_models(backup_dir):
                    success = False

            return success

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

        finally:
            # Clean up
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def _restore_database(self, backup_dir: Path) -> bool:
        """Restore database from backup."""
        logger.info("Restoring database...")

        dump_file = backup_dir / "database.sql"
        if not dump_file.exists():
            logger.error("Database dump not found")
            return False

        # Verify checksum
        checksum_file = backup_dir / "database.sha256"
        if checksum_file.exists():
            with open(checksum_file) as f:
                expected_checksum = f.read().split()[0]
            actual_checksum = self._calculate_checksum(dump_file)
            if expected_checksum != actual_checksum:
                logger.error("Database dump checksum mismatch")
                return False

        env = os.environ.copy()
        env["PGPASSWORD"] = self.db_password

        try:
            # Use pg_restore for database restore
            cmd = [
                "pg_restore",
                "-h", self.db_host,
                "-p", self.db_port,
                "-U", self.db_user,
                "-d", self.db_name,
                "-c",  # Clean (drop) before restore
                "-v",  # Verbose
                str(dump_file)
            ]

            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600
            )

            if result.returncode != 0:
                # pg_restore may return non-zero even on partial success
                logger.warning(f"pg_restore warnings: {result.stderr}")

            logger.info("Database restore complete")
            return True

        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            return False

    def _restore_config(self, backup_dir: Path) -> bool:
        """Restore configuration files."""
        logger.info("Restoring configuration...")

        config_backup_dir = backup_dir / "config"
        if not config_backup_dir.exists():
            logger.warning("Config backup directory not found")
            return True

        project_root = Path(__file__).parent.parent

        for item in config_backup_dir.iterdir():
            dst = project_root / item.name
            if item.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)
            logger.info(f"  Restored: {item.name}")

        return True

    def _restore_models(self, backup_dir: Path) -> bool:
        """Restore ML models."""
        logger.info("Restoring ML models...")

        models_backup_dir = backup_dir / "models"
        if not models_backup_dir.exists():
            logger.warning("Models backup directory not found")
            return True

        project_root = Path(__file__).parent.parent
        models_dir = project_root / "models"
        models_dir.mkdir(parents=True, exist_ok=True)

        for item in models_backup_dir.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(models_backup_dir)
                dst = models_dir / rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dst)
                logger.info(f"  Restored: {rel_path}")

        return True

    def cleanup_old_backups(self) -> int:
        """
        Remove backups older than retention period.

        Returns:
            Number of backups removed
        """
        logger.info(f"Cleaning up backups older than {self.retention_days} days...")

        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        removed_count = 0

        for backup_file in self.backup_dir.glob("lego_factory_*.tar.gz"):
            try:
                # Parse timestamp from filename
                parts = backup_file.stem.split("_")
                if len(parts) >= 4:
                    timestamp_str = f"{parts[-2]}_{parts[-1]}"
                    backup_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                    if backup_date < cutoff_date:
                        backup_file.unlink()
                        logger.info(f"  Removed: {backup_file.name}")
                        removed_count += 1
            except (ValueError, IndexError):
                continue

        logger.info(f"Cleanup complete: {removed_count} backups removed")
        return removed_count

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        backups = []

        for backup_file in sorted(self.backup_dir.glob("lego_factory_*.tar.gz"), reverse=True):
            try:
                stat = backup_file.stat()
                parts = backup_file.stem.split("_")
                backup_type = parts[2] if len(parts) >= 4 else "unknown"

                backups.append({
                    "filename": backup_file.name,
                    "path": str(backup_file),
                    "type": backup_type,
                    "size_mb": stat.st_size / 1024 / 1024,
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except Exception:
                continue

        return backups


def main():
    parser = argparse.ArgumentParser(
        description="LEGO Factory Backup and Recovery Tool"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Create a backup")
    backup_parser.add_argument(
        "--type",
        choices=["full", "database", "config", "models"],
        default="full",
        help="Type of backup to create"
    )
    backup_parser.add_argument(
        "--backup-dir",
        default="/var/backups/lego-factory",
        help="Backup directory"
    )

    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore from backup")
    restore_parser.add_argument(
        "backup_path",
        help="Path to backup file"
    )
    restore_parser.add_argument(
        "--components",
        nargs="+",
        choices=["database", "config", "models"],
        help="Components to restore (default: all)"
    )
    restore_parser.add_argument(
        "--backup-dir",
        default="/var/backups/lego-factory",
        help="Backup directory"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List available backups")
    list_parser.add_argument(
        "--backup-dir",
        default="/var/backups/lego-factory",
        help="Backup directory"
    )

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Remove old backups")
    cleanup_parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Days to retain backups"
    )
    cleanup_parser.add_argument(
        "--backup-dir",
        default="/var/backups/lego-factory",
        help="Backup directory"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    backup_dir = getattr(args, "backup_dir", "/var/backups/lego-factory")
    manager = BackupManager(backup_dir)

    if args.command == "backup":
        result = manager.create_backup(args.type)
        return 0 if result else 1

    elif args.command == "restore":
        result = manager.restore_backup(args.backup_path, args.components)
        return 0 if result else 1

    elif args.command == "list":
        backups = manager.list_backups()
        if not backups:
            print("No backups found")
            return 0

        print(f"\n{'Filename':<50} {'Type':<10} {'Size (MB)':<12} {'Created'}")
        print("-" * 90)
        for backup in backups:
            print(f"{backup['filename']:<50} {backup['type']:<10} {backup['size_mb']:<12.2f} {backup['created']}")
        print(f"\nTotal: {len(backups)} backup(s)")
        return 0

    elif args.command == "cleanup":
        if args.retention_days:
            manager.retention_days = args.retention_days
        manager.cleanup_old_backups()
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
