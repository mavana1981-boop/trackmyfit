#!/usr/bin/env python
"""
Release-phase script: creates tables and seeds initial data.
Run once before the web process starts (Railway release command).
Safe to re-run — seed_data() is idempotent.
"""
import os
import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)


def main(retries=10, delay=3):
    from app import create_app, db
    from models import seed_data

    app = create_app()

    for attempt in range(1, retries + 1):
        try:
            with app.app_context():
                db.create_all()
                log.info('Tables created.')
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
