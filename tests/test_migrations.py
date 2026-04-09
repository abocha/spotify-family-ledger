from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_alembic(database_path: Path, revision: str) -> None:
    env = os.environ.copy()
    env["TURSO_URL"] = f"sqlite:///{database_path}"
    env["TURSO_KEY"] = ""

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", revision],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _table_names(database_path: Path) -> set[str]:
    connection = sqlite3.connect(database_path)
    try:
        cursor = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
        return {row[0] for row in cursor.fetchall()}
    finally:
        connection.close()


def test_alembic_can_upgrade_from_old_head_to_v2_head(tmp_path):
    database_path = tmp_path / "migration-smoke.db"

    _run_alembic(database_path, "82e7e89440fa")
    old_tables = _table_names(database_path)
    assert "charge_cycles" in old_tables
    assert "billing_cycles" not in old_tables

    _run_alembic(database_path, "head")
    new_tables = _table_names(database_path)
    assert "billing_cycles" in new_tables
    assert "opening_balances" in new_tables
    assert "reconciliation_runs" in new_tables
    assert "charge_cycles" not in new_tables
