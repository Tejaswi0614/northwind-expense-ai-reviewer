from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[1] / "northwind.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def setup_database() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT UNIQUE,
                name TEXT NOT NULL,
                grade INTEGER,
                department TEXT,
                manager TEXT,
                trip_purpose TEXT,
                trip_start TEXT,
                trip_end TEXT,
                raw_json TEXT
            );

            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'reviewed',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            );

            CREATE TABLE IF NOT EXISTS line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                vendor TEXT,
                category TEXT,
                amount REAL,
                verdict TEXT,
                confidence REAL,
                reasoning TEXT,
                policy_quotes TEXT,
                extracted_text TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(submission_id) REFERENCES submissions(id)
            );

            CREATE TABLE IF NOT EXISTS overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                line_item_id INTEGER NOT NULL,
                new_verdict TEXT NOT NULL,
                comment TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(line_item_id) REFERENCES line_items(id)
            );
            """
        )


def seed_employees(seed_root: Path) -> None:
    setup_database()
    with connect() as conn:
        for info_file in seed_root.glob("*/employee_info.json"):
            data = json.loads(info_file.read_text(encoding="utf-8"))
            employee_id = str(data.get("employee_id") or data.get("id") or info_file.parent.name)
            name = data.get("name") or data.get("employee_name") or "Unknown Employee"
            trip = data.get("trip") or data
            conn.execute(
                """
                INSERT OR IGNORE INTO employees
                (employee_id, name, grade, department, manager, trip_purpose, trip_start, trip_end, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    employee_id,
                    name,
                    int(data.get("grade") or data.get("employee_grade") or 0),
                    data.get("department", ""),
                    data.get("manager", ""),
                    data.get("trip_purpose") or trip.get("purpose", ""),
                    data.get("trip_start") or trip.get("start_date", ""),
                    data.get("trip_end") or trip.get("end_date", ""),
                    json.dumps(data),
                ),
            )


def rows(query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(query, params).fetchall()


def execute(query: str, params: tuple[Any, ...] = ()) -> int:
    with connect() as conn:
        cur = conn.execute(query, params)
        return int(cur.lastrowid)
