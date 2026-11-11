"""Everything that talks to PostgreSQL lives here.

Values are always passed as query parameters (%s), never pasted into the SQL text,
so a food name can never change what a query does (no SQL injection).
"""

from pathlib import Path

import psycopg
from psycopg.rows import dict_row

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"

# Short, so a missing database gives a quick "not ready" instead of a hang.
CONNECT_TIMEOUT_SECONDS = 2

COLUMNS = (
    "id, name, quantity, location, label_date, date_type, status, created_at, closed_at"
)


def connect(database_url):
    return psycopg.connect(
        database_url, connect_timeout=CONNECT_TIMEOUT_SECONDS, row_factory=dict_row
    )


def ensure_schema(database_url):
    """Create the items table if it is missing. Safe to run more than once."""
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    with connect(database_url) as conn:
        conn.execute(sql)


def create_item(database_url, item):
    """Save a validated new item and return it as stored."""
    with connect(database_url) as conn:
        return conn.execute(
            f"""
            INSERT INTO items (name, quantity, location, label_date, date_type)
            VALUES (%(name)s, %(quantity)s, %(location)s, %(label_date)s, %(date_type)s)
            RETURNING {COLUMNS}
            """,  # nosec B608 - COLUMNS is a fixed constant; values are parameters
            item,
        ).fetchone()


def list_active_items(database_url):
    """Active items, soonest label date first. Same date: oldest entry first."""
    with connect(database_url) as conn:
        return conn.execute(
            f"""
            SELECT {COLUMNS} FROM items
            WHERE status = 'active'
            ORDER BY label_date, id
            """  # nosec B608 - COLUMNS is a fixed constant
        ).fetchall()


def list_closed_items(database_url, limit=100):
    """Used and discarded items, most recently closed first (the trial record)."""
    with connect(database_url) as conn:
        return conn.execute(
            f"""
            SELECT {COLUMNS} FROM items
            WHERE status <> 'active'
            ORDER BY closed_at DESC, id DESC
            LIMIT %s
            """,  # nosec B608 - COLUMNS is a fixed constant; values are parameters
            (limit,),
        ).fetchall()


def get_item(database_url, item_id):
    """One item by id, active or closed. None if there is no such item."""
    with connect(database_url) as conn:
        return conn.execute(
            f"SELECT {COLUMNS} FROM items WHERE id = %s",  # nosec B608
            (item_id,),
        ).fetchone()


def update_item(database_url, item_id, item):
    """Change the details of an active item. Status and dates stay as they are.

    Closed items are trial records, so they are never changed.
    Returns (outcome, item):
      ("updated", item)    it was active and now has the new details
      ("closed", item)     it is used or discarded; nothing changed
      ("not_found", None)  there is no item with this id
    """
    with connect(database_url) as conn:
        updated = conn.execute(
            f"""
            UPDATE items
            SET name = %(name)s, quantity = %(quantity)s, location = %(location)s,
                label_date = %(label_date)s, date_type = %(date_type)s
            WHERE id = %(id)s AND status = 'active'
            RETURNING {COLUMNS}
            """,  # nosec B608 - COLUMNS is a fixed constant; values are parameters
            {**item, "id": item_id},
        ).fetchone()
        if updated is not None:
            return "updated", updated

        existing = conn.execute(
            f"SELECT {COLUMNS} FROM items WHERE id = %s",  # nosec B608
            (item_id,),
        ).fetchone()
        if existing is None:
            return "not_found", None
        return "closed", existing


def close_item(database_url, item_id, status):
    """Mark an active item used or discarded. The row is kept, never deleted.

    Returns (outcome, item):
      ("closed", item)          it was active and is now closed
      ("already_closed", item)  it was closed before; nothing changed
      ("not_found", None)       there is no item with this id
    """
    with connect(database_url) as conn:
        item = conn.execute(
            f"""
            UPDATE items SET status = %s, closed_at = now()
            WHERE id = %s AND status = 'active'
            RETURNING {COLUMNS}
            """,  # nosec B608 - COLUMNS is a fixed constant; values are parameters
            (status, item_id),
        ).fetchone()
        if item is not None:
            return "closed", item

        existing = conn.execute(
            f"SELECT {COLUMNS} FROM items WHERE id = %s",  # nosec B608
            (item_id,),
        ).fetchone()
        if existing is None:
            return "not_found", None
        return "already_closed", existing
