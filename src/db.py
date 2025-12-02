from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent / "reactor.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS kinetic_coeffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_type_id INTEGER NOT NULL,
                k1 REAL NOT NULL,
                k2 REAL NOT NULL,
                Vr REAL NOT NULL,
                Q_min REAL NOT NULL,
                Q_max REAL NOT NULL,
                dQ REAL NOT NULL,
                CAin_min REAL NOT NULL,
                CAin_max REAL NOT NULL,
                dCAin REAL NOT NULL,
                FOREIGN KEY (raw_type_id) REFERENCES raw_types(id)
            )
            """
        )

        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            cur.executemany(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                [("admin", "admin", "admin"), ("user", "user", "user")],
            )

        cur.execute("SELECT COUNT(*) FROM raw_types")
        if cur.fetchone()[0] == 0:
            defaults = [
                ("Сырьё A", dict(k1=0.1, k2=0.2, Vr=10, Q_min=1, Q_max=10, dQ=1,
                                CAin_min=0.1, CAin_max=1.0, dCAin=0.1)),
                ("Сырьё B", dict(k1=0.05, k2=0.15, Vr=8, Q_min=1, Q_max=8, dQ=1,
                                CAin_min=0.1, CAin_max=0.8, dCAin=0.1)),
            ]
            for name, coeffs in defaults:
                raw_id = add_raw_type(name)
                update_coeffs(raw_id, coeffs)


def authenticate(username: str, password: str) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password),
        ).fetchone()


def get_raw_types() -> List[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM raw_types ORDER BY name").fetchall()


def get_coeffs(raw_type_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM kinetic_coeffs WHERE raw_type_id=?",
            (raw_type_id,),
        ).fetchone()


_COEFF_ORDER = ["k1", "k2", "Vr", "Q_min", "Q_max", "dQ", "CAin_min", "CAin_max", "dCAin"]


def update_coeffs(raw_type_id: int, coeffs: Dict[str, float]) -> None:
    values = [float(coeffs[k]) for k in _COEFF_ORDER]

    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM kinetic_coeffs WHERE raw_type_id=?",
            (raw_type_id,),
        ).fetchone()

        if exists:
            conn.execute(
                """
                UPDATE kinetic_coeffs SET
                    k1=?, k2=?, Vr=?,
                    Q_min=?, Q_max=?, dQ=?,
                    CAin_min=?, CAin_max=?, dCAin=?
                WHERE raw_type_id=?
                """,
                (*values, raw_type_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO kinetic_coeffs (
                    raw_type_id, k1, k2, Vr,
                    Q_min, Q_max, dQ,
                    CAin_min, CAin_max, dCAin
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (raw_type_id, *values),
            )


def add_raw_type(name: str) -> int:
    with get_connection() as conn:
        cur = conn.execute("INSERT INTO raw_types (name) VALUES (?)", (name,))
        return int(cur.lastrowid)
