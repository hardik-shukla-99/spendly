# Plan: 01 — Database Setup

## Context

The Spendly app has a stub `database/db.py` with no implementation. All future features (auth, profile, expense tracking) depend on a working SQLite data layer. This plan implements `get_db()`, `init_db()`, and `seed_db()` per spec `01-DB-setup.md`, then wires them into `app.py` startup.

---

## Files to Modify

| File | Change |
|------|--------|
| `database/db.py` | Implement all three functions (currently a stub) |
| `app.py` | Add imports + call `init_db()` / `seed_db()` on startup |

---

## Step 1 — `database/db.py`

### Imports

```python
import sqlite3
import os
from werkzeug.security import generate_password_hash
```

---

### `get_db() -> sqlite3.Connection`

- Resolve `expense_tracker.db` path relative to project root via `os.path.dirname(__file__)` (two levels up from `database/`)
- Set `conn.row_factory = sqlite3.Row` — dict-like row access
- Execute `PRAGMA foreign_keys = ON` — enforce FK constraints per connection
- Return open connection (caller closes it)

---

### `init_db() -> None`

- Call `get_db()` internally
- Run `CREATE TABLE IF NOT EXISTS` for both tables in a single `executescript`:

**users**

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| name | TEXT | NOT NULL |
| email | TEXT | UNIQUE NOT NULL |
| password_hash | TEXT | NOT NULL |
| created_at | TEXT | DEFAULT datetime('now') |

**expenses**

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| user_id | INTEGER | FK → users.id, NOT NULL |
| amount | REAL | NOT NULL |
| category | TEXT | NOT NULL |
| date | TEXT | NOT NULL (YYYY-MM-DD) |
| description | TEXT | Nullable |
| created_at | TEXT | DEFAULT datetime('now') |

- Commit and close
- Idempotent — safe to call multiple times

---

### `seed_db() -> None`

- Check `SELECT COUNT(*) FROM users` → return early if count > 0 (prevents duplicates)
- Insert demo user (parameterized):
  - name: `Demo User`, email: `demo@spendly.com`, password: `generate_password_hash("demo123")`
- Fetch the new user's `id`
- Insert 8 sample expenses via `executemany` — all 7 categories covered:

| amount | category | date | description |
|--------|----------|------|-------------|
| 45.50 | Food | 2026-05-01 | Grocery shopping |
| 25.00 | Transport | 2026-05-03 | Monthly bus pass |
| 120.00 | Bills | 2026-05-05 | Electricity bill |
| 60.00 | Health | 2026-05-08 | Pharmacy |
| 35.00 | Entertainment | 2026-05-10 | Movie tickets |
| 89.99 | Shopping | 2026-05-12 | Clothes |
| 15.75 | Other | 2026-05-15 | Miscellaneous |
| 32.00 | Food | 2026-05-18 | Restaurant dinner |

- All queries use `?` placeholders — no string formatting in SQL
- Commit and close

---

## Step 2 — `app.py`

Add import after existing Flask import:

```python
from database.db import get_db, init_db, seed_db
```

Add startup block after `app = Flask(__name__)`:

```python
with app.app_context():
    init_db()
    seed_db()
```

Do **not** touch or remove any existing route stubs.

---

## Constraints

- No ORM — raw `sqlite3` only
- Parameterized queries everywhere (`?` placeholders)
- `PRAGMA foreign_keys = ON` on every connection
- `amount` stored as REAL (not INTEGER)
- Passwords hashed via `werkzeug.security.generate_password_hash`
- Dates in YYYY-MM-DD format
- No new pip packages required

---

## Verification

```bash
# 1. Start the app
source venv/bin/activate && python app.py

# 2. Confirm DB file was created
ls expense_tracker.db

# 3. Inspect schema and data
sqlite3 expense_tracker.db ".tables"
sqlite3 expense_tracker.db "SELECT id, name, email FROM users;"
sqlite3 expense_tracker.db "SELECT COUNT(*) FROM expenses;"   # → 8

# 4. Restart app — confirm no duplicate seed data
python app.py
sqlite3 expense_tracker.db "SELECT COUNT(*) FROM users;"      # → still 1

# 5. Run tests
pytest
```