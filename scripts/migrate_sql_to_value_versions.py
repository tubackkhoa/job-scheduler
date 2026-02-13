"""
Data migration script: sql_versions -> value_versions and update jobs config

Usage:
    python scripts/migrate_sql_to_value_versions.py

1. Copy all sql_versions to value_versions with field_id = '1.sql_id'
2. Update jobs for plugin_id=1:
   - session_id=1 (staging): use sql with name "u5 - v2.6.1 - Cheat flip with voting (test)"
   - session_id=2 (production): use sql with name defined below
"""

import os
import msgspec
import msgspec.json as ms
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import dotenv

dotenv.load_dotenv()

# Configuration
PLUGIN_ID = 1
FIELD_ID = f"{PLUGIN_ID}.sql_id"

STAGING_SQL_NAME = "u5 - v2.6.5 Cheat flip fix gated_flag for workers"
PRODUCTION_SQL_NAME = "u5 v2.5.19 - Liquidation zone, adding micro-trend confirmation"


def main():
    db_connection = os.getenv("DB_CONNECTION")
    if not db_connection:
        raise ValueError("DB_CONNECTION environment variable is required")

    engine = create_engine(db_connection)

    with Session(engine) as session:
        # Step 1: Migrate sql_versions to value_versions
        sql_versions = session.execute(
            text(
                """
                SELECT id, name, description, sql_query, created_at, updated_at, is_active, tags
                FROM sql_versions
                ORDER BY id
            """
            )
        ).fetchall()

        print(f"Found {len(sql_versions)} sql_versions to migrate")

        for row in sql_versions:
            old_id, name, description, sql_query, created_at, updated_at, is_active, tags = row

            # Check if already exists
            existing = session.execute(
                text("SELECT id FROM value_versions WHERE field_id = :field_id AND name = :name"),
                {"field_id": FIELD_ID, "name": name},
            ).scalar()

            if existing:
                print(
                    f"  Skipping sql_version {old_id} ({name}) - already exists as value_version {existing}"
                )
                continue

            result = session.execute(
                text(
                    """
                    INSERT INTO value_versions (field_id, name, description, value, created_at, updated_at, is_active, tags)
                    VALUES (:field_id, :name, :description, :value, :created_at, :updated_at, :is_active, :tags)
                    RETURNING id
                """
                ),
                {
                    "field_id": FIELD_ID,
                    "name": name,
                    "description": description,
                    "value": sql_query,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "is_active": is_active,
                    "tags": tags,
                },
            )
            new_id = result.scalar()
            print(f"  Migrated sql_version {old_id} -> value_version {new_id} ({name})")

        # Step 2: Find the sql_id for each session based on name
        staging_sql = session.execute(
            text("SELECT id FROM value_versions WHERE field_id = :field_id AND name = :name"),
            {"field_id": FIELD_ID, "name": STAGING_SQL_NAME},
        ).scalar()

        production_sql = session.execute(
            text("SELECT id FROM value_versions WHERE field_id = :field_id AND name = :name"),
            {"field_id": FIELD_ID, "name": PRODUCTION_SQL_NAME},
        ).scalar()

        print(f"\nStaging SQL (session_id=1): {staging_sql} ({STAGING_SQL_NAME})")
        print(f"Production SQL (session_id=2): {production_sql} ({PRODUCTION_SQL_NAME})")

        # Step 3: Update jobs for plugin_id=1
        jobs = session.execute(
            text("SELECT id, session_id, config FROM jobs WHERE plugin_id = :plugin_id"),
            {"plugin_id": PLUGIN_ID},
        ).fetchall()

        print(f"\nFound {len(jobs)} jobs for plugin_id={PLUGIN_ID}")

        for job_id, session_id, config_str in jobs:
            try:
                config = ms.decode(config_str) if config_str else {}
            except msgspec.DecodeError:
                config = {}

            if session_id == 1:
                new_sql_id = staging_sql
            elif session_id == 2:
                new_sql_id = production_sql
            else:
                print(f"  Skipping job {job_id} (unknown session_id={session_id})")
                continue

            if new_sql_id is None:
                print(f"  Warning: No sql_id found for job {job_id} (session_id={session_id})")
                continue

            config["sql_id"] = new_sql_id
            new_config_str = ms.encode(config).decode()

            session.execute(
                text("UPDATE jobs SET config = :config WHERE id = :job_id"),
                {"config": new_config_str, "job_id": job_id},
            )
            print(f"  Updated job {job_id} (session_id={session_id}) with sql_id={new_sql_id}")

        session.commit()
        print("\nMigration complete!")


if __name__ == "__main__":
    main()
