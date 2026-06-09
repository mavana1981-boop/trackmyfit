#!/usr/bin/env python
"""
Boot-time DB init: creates tables, runs migrations, seeds data.
Safe to re-run — all operations are idempotent.
"""
import os, sys, time, logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

MIGRATIONS = [
    # Add custom_name column if missing
    "ALTER TABLE workout_sessions ADD COLUMN IF NOT EXISTS custom_name VARCHAR(150)",
    # Add session_muscle_groups junction table if missing
    """
    CREATE TABLE IF NOT EXISTS session_muscle_groups (
        session_id      INTEGER NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,
        muscle_group_id INTEGER NOT NULL REFERENCES muscle_groups(id)    ON DELETE CASCADE,
        PRIMARY KEY (session_id, muscle_group_id)
    )
    """,
]


def run_migrations(conn):
    for sql in MIGRATIONS:
        try:
            conn.execute(sql.strip())
            log.info('Migration OK: %s...', sql.strip()[:60])
        except Exception as e:
            log.warning('Migration skipped (%s): %s', sql.strip()[:40], e)


def main(retries=10, delay=3):
    from app import create_app, db
    from models import seed_data
    from sqlalchemy import text

    app = create_app()

    for attempt in range(1, retries + 1):
        try:
            with app.app_context():
                # 1. Create any missing tables (new installs)
                db.create_all()
                log.info('Tables created/verified.')

                # 2. Run column/table migrations (existing installs)
                with db.engine.connect() as conn:
                    for sql in MIGRATIONS:
                        try:
                            conn.execute(text(sql.strip()))
                            log.info('Migration OK: %s...', sql.strip()[:60])
                        except Exception as e:
                            log.warning('Migration skipped: %s', e)
                    conn.commit()
                log.info('Migrations complete.')

                # 3. Seed reference data
                seed_data()
                log.info('Seed data OK.')

            log.info('DB init complete.')
            return

        except Exception as exc:
            log.warning('Attempt %d/%d failed: %s', attempt, retries, exc)
            if attempt == retries:
                log.error('DB init failed after %d attempts — aborting.', retries)
                sys.exit(1)
            log.info('Retrying in %ds...', delay)
            time.sleep(delay)


if __name__ == '__main__':
    main()
