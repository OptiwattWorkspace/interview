"""Task storage.

A task is exactly four fields: title, status, due date, owner. The store
also keeps a tiny key/value table so the poller can remember which
iMessage row it last processed.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

OPEN = "open"
DOING = "doing"
DONE = "done"
STATUSES = (OPEN, DOING, DONE)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title  TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    due    TEXT,
    owner  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class Task:
    """One task. Four fields, nothing more."""

    id: int
    title: str
    status: str
    due: date | None
    owner: str

    def format(self) -> str:
        """Render as a single line: ``3. Pay bill | open | Aug 22 | casey``."""
        due = self.due.strftime("%b %-d") if self.due else "—"
        return f"{self.id}. {self.title} | {self.status} | {due} | {self.owner}"


class Store:
    """SQLite-backed task list."""

    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- tasks ---------------------------------------------------------

    def add(self, title: str, owner: str, due: date | None = None) -> Task:
        cur = self._conn.execute(
            "INSERT INTO tasks (title, status, due, owner) VALUES (?, ?, ?, ?)",
            (title, OPEN, due.isoformat() if due else None, owner),
        )
        self._conn.commit()
        return Task(cur.lastrowid, title, OPEN, due, owner)

    def get(self, task_id: int) -> Task | None:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return _to_task(row) if row else None

    def list(
        self, owner: str | None = None, include_done: bool = False
    ) -> list[Task]:
        """List tasks, soonest due first, undated last."""
        sql = "SELECT * FROM tasks"
        clauses, params = [], []
        if owner:
            clauses.append("owner = ?")
            params.append(owner)
        if not include_done:
            clauses.append("status != ?")
            params.append(DONE)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        # NULL dues sort last, then by date, then by insertion order.
        sql += " ORDER BY due IS NULL, due, id"
        rows = self._conn.execute(sql, params).fetchall()
        return [_to_task(r) for r in rows]

    def set_status(self, task_id: int, status: str) -> Task | None:
        if status not in STATUSES:
            raise ValueError(f"unknown status: {status}")
        cur = self._conn.execute(
            "UPDATE tasks SET status = ? WHERE id = ?", (status, task_id)
        )
        self._conn.commit()
        return self.get(task_id) if cur.rowcount else None

    def delete(self, task_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # -- poller bookmark -----------------------------------------------

    def get_state(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_state(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        self._conn.commit()


def _to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        status=row["status"],
        due=date.fromisoformat(row["due"]) if row["due"] else None,
        owner=row["owner"],
    )
