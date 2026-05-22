import os
import sqlite3

from werkzeug.security import generate_password_hash

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "expense_tracker.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT    NOT NULL,
                email        TEXT    UNIQUE NOT NULL,
                password_hash TEXT   NOT NULL,
                created_at   TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL    NOT NULL,
                category    TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                description TEXT,
                created_at  TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


def seed_db() -> None:
    conn = get_db()
    try:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count > 0:
            return

        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
        )
        conn.commit()

        user_id: int = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()[0]

        sample_expenses = [
            (user_id, 45.50,  "Food",          "2026-05-01", "Grocery shopping"),
            (user_id, 25.00,  "Transport",     "2026-05-03", "Monthly bus pass"),
            (user_id, 120.00, "Bills",         "2026-05-05", "Electricity bill"),
            (user_id, 60.00,  "Health",        "2026-05-08", "Pharmacy"),
            (user_id, 35.00,  "Entertainment", "2026-05-10", "Movie tickets"),
            (user_id, 89.99,  "Shopping",      "2026-05-12", "Clothes"),
            (user_id, 15.75,  "Other",         "2026-05-15", "Miscellaneous"),
            (user_id, 32.00,  "Food",          "2026-05-18", "Restaurant dinner"),
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            sample_expenses,
        )
        conn.commit()
    finally:
        conn.close()