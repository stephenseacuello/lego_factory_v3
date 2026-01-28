#!/usr/bin/env python3
"""
LEGO Factory v3 - Migration Script for Factory Improvements
============================================================
Adds new columns and tables introduced by the factory improvements plan:
1. eligible_machines column on operations table
2. machine_availability table for scheduling

Usage:
    docker-compose exec app python scripts/migrate_v3_improvements.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_migration():
    print("=" * 60)
    print("  LEGO Factory v3 - Schema Migration")
    print("=" * 60)

    try:
        from config.database import get_engine
        from sqlalchemy import text

        engine = get_engine()

        with engine.connect() as conn:
            # 1. Add eligible_machines column to operations table
            print("\n1. Adding eligible_machines column to operations table...")
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = 'operations' AND column_name = 'eligible_machines'
                )
            """))
            has_column = result.scalar()

            if has_column:
                print("   Already exists, skipping.")
            else:
                conn.execute(text("""
                    ALTER TABLE operations
                    ADD COLUMN eligible_machines JSONB DEFAULT '[]'::jsonb
                """))
                print("   Added eligible_machines column.")

            # 2. Create machine_availability table
            print("\n2. Creating machine_availability table...")
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'machine_availability'
                )
            """))
            table_exists = result.scalar()

            if table_exists:
                print("   Already exists, skipping.")
            else:
                conn.execute(text("""
                    CREATE TABLE machine_availability (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        machine_id VARCHAR(50) NOT NULL,
                        availability_type VARCHAR(20) NOT NULL,
                        start_datetime TIMESTAMP NOT NULL,
                        end_datetime TIMESTAMP NOT NULL,
                        is_recurring BOOLEAN DEFAULT FALSE,
                        recurrence_pattern VARCHAR(50),
                        days_of_week JSONB,
                        capacity_percent INTEGER DEFAULT 100,
                        reason VARCHAR(200),
                        notes TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by VARCHAR(100),
                        updated_by VARCHAR(100),
                        is_deleted BOOLEAN DEFAULT FALSE,
                        deleted_at TIMESTAMP,
                        deleted_by VARCHAR(100)
                    )
                """))
                conn.execute(text("""
                    CREATE INDEX ix_machine_availability_machine_dates
                    ON machine_availability(machine_id, start_datetime, end_datetime)
                """))
                print("   Created machine_availability table with index.")

            conn.commit()

            print("\n" + "=" * 60)
            print("  Migration complete!")
            print("=" * 60)
            return 0

    except Exception as e:
        print(f"\nMigration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_migration())
