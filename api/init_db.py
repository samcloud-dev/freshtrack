"""Create the FreshTrack table. Run once before the api serves items:

    DATABASE_URL=postgresql://... python init_db.py

Safe to run again: it never removes data. Planned to run as a Kubernetes Job.
"""

import logging
import os
import sys

import db

log = logging.getLogger("init_db")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        log.error("DATABASE_URL is not set")
        return 1
    try:
        db.ensure_schema(database_url)
    except db.psycopg.Error as exc:
        # The class name only: the full message could include connection details.
        log.error("Schema setup failed: %s", exc.__class__.__name__)
        return 1
    log.info("Schema is ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
