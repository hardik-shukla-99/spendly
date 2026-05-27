import os
import sqlite3
from datetime import datetime

from werkzeug.security import generate_password_hash

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "expense_tracker.db"
)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_db()
    try:
        conn.executescript(
            """
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
        """
        )
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
            (user_id, 45.50, "Food", "2026-05-01", "Grocery shopping"),
            (user_id, 25.00, "Transport", "2026-05-03", "Monthly bus pass"),
            (user_id, 120.00, "Bills", "2026-05-05", "Electricity bill"),
            (user_id, 60.00, "Health", "2026-05-08", "Pharmacy"),
            (user_id, 35.00, "Entertainment", "2026-05-10", "Movie tickets"),
            (user_id, 89.99, "Shopping", "2026-05-12", "Clothes"),
            (user_id, 15.75, "Other", "2026-05-15", "Miscellaneous"),
            (user_id, 32.00, "Food", "2026-05-18", "Restaurant dinner"),
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            sample_expenses,
        )
        conn.commit()
    finally:
        conn.close()


def add_expense_to_db(
    user_id: int,
    amount: float,
    category: str,
    date: str,
    description: str,
) -> int:
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_expense_by_id(expense_id: int) -> sqlite3.Row | None:
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, user_id, amount, category, date, description"
            " FROM expenses WHERE id = ?",
            (expense_id,),
        ).fetchone()
    finally:
        conn.close()


def update_expense_in_db(
    expense_id: int,
    amount: float,
    category: str,
    date: str,
    description: str,
) -> None:
    conn = get_db()
    try:
        conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ?"
            " WHERE id = ?",
            (amount, category, date, description, expense_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email: str) -> sqlite3.Row | None:
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()


def register_user(name: str, email: str, password: str) -> int:
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def _build_date_where(
    user_id: int,
    start: str | None,
    end: str | None,
) -> tuple[str, list]:
    """Return a (where_clause, params) pair for date-scoped expense queries.

    The returned where_clause is a plain SQL string built from hardcoded
    literals only — no user input is ever interpolated into it.  All
    user-supplied values are collected in params as positional ? placeholders.
    """
    conditions = ["user_id = ?"]
    params: list = [user_id]
    if start:
        conditions.append("date >= ?")
        params.append(start)
    if end:
        conditions.append("date <= ?")
        params.append(end)
    return "WHERE " + " AND ".join(conditions), params


def get_recent_transactions(
    user_id: int,
    limit: int = 6,
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    conn = get_db()
    try:
        where_clause, params = _build_date_where(user_id, start, end)
        params.append(limit)
        sql = (
            "SELECT id, date, description, category, amount"
            " FROM expenses"
            " " + where_clause + " ORDER BY date DESC, id DESC"
            " LIMIT ?"
        )
        rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            try:
                fmt_date = datetime.strptime(row["date"], "%Y-%m-%d").strftime(
                    "%B %d, %Y"
                )
            except (ValueError, TypeError):
                fmt_date = row["date"]
            result.append(
                {
                    "id": row["id"],
                    "date": fmt_date,
                    "description": row["description"] or "",
                    "category": (row["category"] or "").lower(),
                    "amount": "${:,.2f}".format(row["amount"]),
                }
            )
        return result
    finally:
        conn.close()


def get_profile_stats(
    user_id: int,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    conn = get_db()
    try:
        where_clause, params = _build_date_where(user_id, start, end)

        row = conn.execute(
            "SELECT"
            " COALESCE(SUM(amount), 0) AS total_spent,"
            " COUNT(*) AS transaction_count"
            " FROM expenses"
            " " + where_clause,
            params,
        ).fetchone()
        total_spent = row["total_spent"]
        transaction_count = row["transaction_count"]

        top_row = conn.execute(
            "SELECT category"
            " FROM expenses"
            " " + where_clause + " GROUP BY category"
            " ORDER BY SUM(amount) DESC"
            " LIMIT 1",
            params,
        ).fetchone()
        top_category = top_row["category"] if top_row else ""

        return {
            "total_spent": "${:,.2f}".format(total_spent),
            "transaction_count": transaction_count,
            "top_category": top_category,
        }
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def get_category_breakdown(
    user_id: int,
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    conn = get_db()
    try:
        where_clause, params = _build_date_where(user_id, start, end)

        grand_total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses " + where_clause,
            params,
        ).fetchone()[0]

        rows = conn.execute(
            "SELECT category, SUM(amount) AS cat_total"
            " FROM expenses"
            " " + where_clause + " GROUP BY category"
            " ORDER BY cat_total DESC",
            params,
        ).fetchall()

        result = []
        for row in rows:
            pct = int(round(row["cat_total"] / grand_total * 100)) if grand_total else 0
            result.append(
                {
                    "name": row["category"],
                    "amount": "${:,.2f}".format(row["cat_total"]),
                    "pct": pct,
                }
            )
        return result
    finally:
        conn.close()
