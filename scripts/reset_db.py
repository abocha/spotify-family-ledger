#!/usr/bin/env python3
"""Hard reset the database and recreate the v2 schema."""

from __future__ import annotations

import os
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import text

sys.path.insert(0, os.getcwd())

from ledger.database import get_engine


def _quote_identifier(name: str) -> str:
    return f'"{name.replace("\"", "\"\"")}"'


def _drop_all_sqlite_objects(connection) -> None:
    connection.execute(text("PRAGMA foreign_keys=OFF"))

    object_names = [
        row[0]
        for row in connection.execute(
            text(
                """
                SELECT name
                FROM sqlite_master
                WHERE type IN ('table', 'view')
                  AND name NOT LIKE 'sqlite_%'
                """
            )
        )
    ]

    for object_name in object_names:
        quoted = _quote_identifier(object_name)
        connection.execute(text(f"DROP VIEW IF EXISTS {quoted}"))
        connection.execute(text(f"DROP TABLE IF EXISTS {quoted}"))

    connection.execute(text("PRAGMA foreign_keys=ON"))


def main() -> None:
    engine = get_engine()
    with engine.begin() as connection:
        _drop_all_sqlite_objects(connection)

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print("Database reset complete. V2 schema is now installed.")


if __name__ == "__main__":
    main()
