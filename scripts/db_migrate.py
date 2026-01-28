#!/usr/bin/env python3
"""
LEGO Factory v3 - Database Migration Helper
============================================

This script provides safe database migration operations for production environments.

Usage:
    python scripts/db_migrate.py status          # Show current migration status
    python scripts/db_migrate.py upgrade         # Upgrade to latest
    python scripts/db_migrate.py downgrade       # Rollback one revision
    python scripts/db_migrate.py history         # Show migration history
    python scripts/db_migrate.py backup          # Create backup before migration
    python scripts/db_migrate.py restore <file>  # Restore from backup

Environment variables required:
    DATABASE_URL - PostgreSQL connection string
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_database_url():
    """Get database URL from environment."""
    url = os.environ.get('DATABASE_URL')
    if not url:
        print("ERROR: DATABASE_URL environment variable is required")
        print("Example: export DATABASE_URL=postgresql://user:pass@localhost:5432/lego_factory")
        sys.exit(1)
    return url


def run_alembic(*args):
    """Run alembic command."""
    cmd = ['alembic'] + list(args)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(result.returncode)
    return result


def show_status():
    """Show current migration status."""
    print("=" * 60)
    print("MIGRATION STATUS")
    print("=" * 60)
    run_alembic('current')
    print()
    run_alembic('heads')


def upgrade(revision='head'):
    """Upgrade database to specified revision (default: latest)."""
    print("=" * 60)
    print(f"UPGRADING DATABASE TO: {revision}")
    print("=" * 60)

    # Show current state
    print("\nCurrent state:")
    run_alembic('current')

    # Perform upgrade
    print(f"\nUpgrading to {revision}...")
    run_alembic('upgrade', revision)

    # Verify
    print("\nNew state:")
    run_alembic('current')
    print("\nUpgrade complete!")


def downgrade(revision='-1'):
    """Downgrade database by specified steps (default: 1)."""
    print("=" * 60)
    print(f"DOWNGRADING DATABASE BY: {revision}")
    print("=" * 60)

    # Show current state
    print("\nCurrent state:")
    run_alembic('current')

    # Confirm
    response = input("\nAre you sure you want to rollback? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        sys.exit(0)

    # Perform downgrade
    print(f"\nRolling back {revision}...")
    run_alembic('downgrade', revision)

    # Verify
    print("\nNew state:")
    run_alembic('current')
    print("\nDowngrade complete!")


def show_history():
    """Show migration history."""
    print("=" * 60)
    print("MIGRATION HISTORY")
    print("=" * 60)
    run_alembic('history', '--verbose')


def create_backup():
    """Create database backup using pg_dump."""
    db_url = get_database_url()

    # Parse connection info
    from urllib.parse import urlparse
    parsed = urlparse(db_url)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = PROJECT_ROOT / 'backups'
    backup_dir.mkdir(exist_ok=True)
    backup_file = backup_dir / f'lego_factory_{timestamp}.sql'

    print("=" * 60)
    print("CREATING DATABASE BACKUP")
    print("=" * 60)
    print(f"Output file: {backup_file}")

    # Set password environment variable for pg_dump
    env = os.environ.copy()
    env['PGPASSWORD'] = parsed.password

    cmd = [
        'pg_dump',
        '-h', parsed.hostname,
        '-p', str(parsed.port or 5432),
        '-U', parsed.username,
        '-d', parsed.path.lstrip('/'),
        '-f', str(backup_file),
        '--verbose',
    ]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"\nBackup created: {backup_file}")
        print(f"Size: {backup_file.stat().st_size / 1024 / 1024:.2f} MB")
    else:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)

    return backup_file


def restore_backup(backup_file):
    """Restore database from backup file."""
    db_url = get_database_url()

    if not os.path.exists(backup_file):
        print(f"ERROR: Backup file not found: {backup_file}")
        sys.exit(1)

    # Parse connection info
    from urllib.parse import urlparse
    parsed = urlparse(db_url)

    print("=" * 60)
    print("RESTORING DATABASE FROM BACKUP")
    print("=" * 60)
    print(f"Backup file: {backup_file}")

    # Confirm
    response = input("\nWARNING: This will overwrite the current database. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        sys.exit(0)

    # Set password environment variable for psql
    env = os.environ.copy()
    env['PGPASSWORD'] = parsed.password

    cmd = [
        'psql',
        '-h', parsed.hostname,
        '-p', str(parsed.port or 5432),
        '-U', parsed.username,
        '-d', parsed.path.lstrip('/'),
        '-f', backup_file,
    ]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode == 0:
        print("\nRestore complete!")
    else:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)


def print_usage():
    """Print usage information."""
    print(__doc__)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == 'status':
        show_status()
    elif command == 'upgrade':
        revision = sys.argv[2] if len(sys.argv) > 2 else 'head'
        upgrade(revision)
    elif command == 'downgrade':
        revision = sys.argv[2] if len(sys.argv) > 2 else '-1'
        downgrade(revision)
    elif command == 'history':
        show_history()
    elif command == 'backup':
        create_backup()
    elif command == 'restore':
        if len(sys.argv) < 3:
            print("ERROR: Backup file path required")
            print("Usage: python scripts/db_migrate.py restore <backup_file>")
            sys.exit(1)
        restore_backup(sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == '__main__':
    main()
