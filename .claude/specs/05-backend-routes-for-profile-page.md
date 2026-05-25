# Spec: Backend Routes for Profile Page

## 1. Overview

This feature replaces the hardcoded, static data on the `/profile` page with real data sourced from the database for the currently logged-in user. It wires up the existing `users` and `expenses` tables to compute live stats (total spent, transaction count, top category), fetch recent transactions, and build a per-category spending breakdown — all scoped to the authenticated user's session. This unblocks any subsequent CRUD steps (add/edit/delete expense) by establishing the live data layer the profile page depends on.

---

## 2. Depends on

- `01-DB-setup.md` — `users` and `expenses` tables must exist; `get_db()` must be available
- `02-user-registration.md` — real user rows must be creatable
- `03-login-logout.md` — `session["user_id"]` is set on login and cleared on logout
- `04-profile-page.md` — `templates/profile.html` must exist with the established layout and all four sections

---

## 3. Routes

- `GET /profile` — modified; replaces hardcoded context with live DB queries scoped to `session["user_id"]`

No new routes are added in this step.

---

## 4. Database Schema

No schema changes. The existing tables are sufficient:

**users**
| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| name | TEXT | NOT NULL |
| email | TEXT | UNIQUE NOT NULL |
| password_hash | TEXT | NOT NULL |
| created_at | TEXT | DEFAULT (datetime('now')) |

**expenses**
| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| user_id | INTEGER | NOT NULL, FOREIGN KEY → users(id) |
| amount | REAL | NOT NULL |
| category | TEXT | NOT NULL |
| date | TEXT | NOT NULL |
| description | TEXT | — |
| created_at | TEXT | DEFAULT (datetime('now')) |

---

## 5. Functions / Logic to Implement

### `get_profile_stats(user_id: int) -> dict`

**Location:** `database/db.py`

**Signature:**
```python
def get_profile_stats(user_id: int) -> dict:
```

**Responsibility:** Return a dict with aggregate stats for the given user.

**Key logic steps:**
1. Open a DB connection via `get_db()`.
2. Run a single SQL query:
   ```sql
   SELECT
     COALESCE(SUM(amount), 0)  AS total_spent,
     COUNT(*)                   AS transaction_count
   FROM expenses
   WHERE user_id = ?
   ```
3. Run a second query to find the top category:
   ```sql
   SELECT category, SUM(amount) AS cat_total
   FROM expenses
   WHERE user_id = ?
   GROUP BY category
   ORDER BY cat_total DESC
   LIMIT 1
   ```
4. Return a dict:
   ```python
   {
     "total_spent": "$2,840.50",   # formatted as currency string
     "transaction_count": 24,
     "top_category": "Food",       # empty string "" if no expenses
   }
   ```
5. Format `total_spent` as `"${:,.2f}".format(value)`.
6. Close the connection in a `finally` block.

---

### `get_recent_transactions(user_id: int, limit: int = 6) -> list[dict]`

**Location:** `database/db.py`

**Signature:**
```python
def get_recent_transactions(user_id: int, limit: int = 6) -> list[dict]:
```

**Responsibility:** Return the N most recent expense rows for the user, formatted for the template.

**Key logic steps:**
1. Open a DB connection via `get_db()`.
2. Query:
   ```sql
   SELECT date, description, category, amount
   FROM expenses
   WHERE user_id = ?
   ORDER BY date DESC, id DESC
   LIMIT ?
   ```
3. Convert each `sqlite3.Row` to a plain dict with:
   - `date` — reformatted from `YYYY-MM-DD` to `"May 20, 2025"` using `datetime.strptime` + `strftime`
   - `description` — raw string
   - `category` — raw string (lowercased for CSS class use)
   - `amount` — formatted as `"$87.40"`
4. Return the list (empty list `[]` if no rows).
5. Close the connection in a `finally` block.

---

### `get_category_breakdown(user_id: int) -> list[dict]`

**Location:** `database/db.py`

**Signature:**
```python
def get_category_breakdown(user_id: int) -> list[dict]:
```

**Responsibility:** Return per-category spending totals with a percentage bar value, sorted by total descending.

**Key logic steps:**
1. Open a DB connection via `get_db()`.
2. Query total spend for the user (reuse or inline):
   ```sql
   SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?
   ```
3. Query per-category totals:
   ```sql
   SELECT category, SUM(amount) AS cat_total
   FROM expenses
   WHERE user_id = ?
   GROUP BY category
   ORDER BY cat_total DESC
   ```
4. For each row compute `pct = int(round(cat_total / grand_total * 100))` (guard against division by zero when `grand_total == 0`).
5. Return a list of dicts:
   ```python
   [
     {"name": "Food", "amount": "$620.00", "pct": 72},
     ...
   ]
   ```
6. Close the connection in a `finally` block.

---

### `get_user_by_id(user_id: int) -> sqlite3.Row | None`

**Location:** `database/db.py`

**Signature:**
```python
def get_user_by_id(user_id: int) -> sqlite3.Row | None:
```

**Responsibility:** Fetch a single user row by primary key (needed to display name, email, and `member_since` on the profile card).

**Key logic steps:**
1. Open a DB connection via `get_db()`.
2. Query:
   ```sql
   SELECT id, name, email, created_at FROM users WHERE id = ?
   ```
3. Return the `sqlite3.Row` or `None` if not found.
4. Format `created_at` (`YYYY-MM-DD HH:MM:SS`) into `"January 2024"` in the **view function** (not in `db.py`).
5. Close the connection in a `finally` block.

---

### `profile()` view function (modified)

**Location:** `app.py`

**Signature:**
```python
@app.route("/profile")
@login_required
def profile() -> str:
```

**Responsibility:** Fetch all live data for the logged-in user and render `profile.html`.

**Key logic steps:**
1. Read `user_id = session["user_id"]` (guaranteed present by `@login_required`).
2. Call `get_user_by_id(user_id)`. If `None`, clear session and redirect to `/login` with a flash message ("Session invalid — please log in again.").
3. Format `user["created_at"]` → `"January 2024"` using `datetime.strptime(user["created_at"], "%Y-%m-%d %H:%M:%S").strftime("%B %Y")`.
4. Build the `user` dict:
   ```python
   initials = "".join(w[0].upper() for w in user["name"].split()[:2])
   ```
5. Call `get_profile_stats(user_id)`.
6. Call `get_recent_transactions(user_id, limit=6)`.
7. Call `get_category_breakdown(user_id)`.
8. Render `profile.html` passing `user`, `stats`, `transactions`, `categories`.

---

## 6. Templates / UI

- **`templates/profile.html`** — **modify**, no structural changes required. Replace all hardcoded Python-dict values with Jinja2 template variables. The four-section layout (user card, stats row, transaction table, category breakdown) stays exactly as-is. Variable names must match those already used in the template:
  - `{{ user.name }}`, `{{ user.email }}`, `{{ user.initials }}`, `{{ user.member_since }}`
  - `{{ stats.total_spent }}`, `{{ stats.transaction_count }}`, `{{ stats.top_category }}`
  - `{% for t in transactions %}` → `{{ t.date }}`, `{{ t.description }}`, `{{ t.category }}`, `{{ t.amount }}`
  - `{% for c in categories %}` → `{{ c.name }}`, `{{ c.amount }}`, `{{ c.pct }}`

If any of the above variable names differ in the current template, update the template to align — **do not** rename the Python-side variables.

---

## 7. Files to Change

- `app.py` → replace hardcoded `user`, `stats`, `transactions`, `categories` dicts/lists in `profile()` with calls to the new `database/db.py` functions; import the four new functions.
- `database/db.py` → add four new functions: `get_user_by_id`, `get_profile_stats`, `get_recent_transactions`, `get_category_breakdown`.
- `templates/profile.html` → verify Jinja2 variable names match; update only if there is a mismatch.

---

## 8. Files to Create

None.

---

## 9. Dependencies

None. All required packages (`flask`, `werkzeug`, `python-dotenv`) are already in `requirements.txt`. `datetime` is part of the Python standard library.

---

## 10. Rules for Implementation

- **Raw SQL only** — no SQLAlchemy, no ORM.
- **Parameterised queries only** — never use f-strings or `%` string formatting in SQL.
- **`get_db()` pattern** — open a connection, use a `try/finally` to close it; do not leave connections open.
- **`row_factory = sqlite3.Row`** — already set in `get_db()`; use column-name access (`row["amount"]`), not index access.
- **Foreign keys** — already enforced via `PRAGMA foreign_keys = ON` in `get_db()`.
- **Type annotations** — all function signatures must include parameter and return types (PEP 8 / project convention).
- **Currency formatting** — use `"${:,.2f}".format(value)` consistently; never return raw floats to the template.
- **Date formatting** — parse with `datetime.strptime`, format with `strftime`; do not rely on SQLite `strftime()` for display output.
- **CSS classes** — category values passed to the template must be lowercased strings suitable for CSS class names (e.g. `"food"`, `"transport"`).
- **No inline styles, no hex colour literals** — enforced by the existing test `test_profile_no_hex_colours`.
- **`session["user_id"]` is the single source of truth** — never trust user-supplied input for scoping DB queries.

---

## 11. Expected Behavior

1. User logs in → `session["user_id"]` is set.
2. User navigates to `/profile`.
3. `login_required` confirms the session is valid.
4. The view calls `get_user_by_id` → retrieves the real name, email, and join date.
5. The view calls `get_profile_stats` → computes total spent, transaction count, and top category from live `expenses` rows.
6. The view calls `get_recent_transactions(limit=6)` → returns the 6 most recent expenses, newest first, with dates formatted as "Month DD, YYYY" and amounts formatted as "$XX.XX".
7. The view calls `get_category_breakdown` → returns all categories sorted by total spend descending, each with a percentage for the progress bar.
8. `profile.html` renders with all four sections populated from real data.
9. If the user has no expenses, stats show `$0.00`, `0` transactions, an empty top category, an empty transaction table, and an empty category breakdown — the page renders without errors.

---

## 12. Error Handling Expectations

| Failure Case | Expected Behavior |
|---|---|
| `session["user_id"]` is set but the user row no longer exists in DB | Clear session, flash "Session invalid — please log in again.", redirect to `/login` |
| User has zero expenses | `get_profile_stats` returns `{"total_spent": "$0.00", "transaction_count": 0, "top_category": ""}`. Template must handle empty `transactions` and `categories` lists gracefully (empty state, not a crash) |
| DB file missing or corrupt | `sqlite3` raises an exception → Flask's default 500 error handler returns a 500 response (no special handling needed at this step) |
| `created_at` is `NULL` or malformed in DB | Fall back to `"Unknown"` for `member_since` using a try/except around the `strptime` call in the view |

---

## 13. Definition of Done

- [ ] `get_user_by_id(user_id)` is implemented in `database/db.py` and returns a `sqlite3.Row` with `id`, `name`, `email`, `created_at`
- [ ] `get_profile_stats(user_id)` is implemented and returns a dict with `total_spent` (currency string), `transaction_count` (int), `top_category` (string)
- [ ] `get_recent_transactions(user_id, limit=6)` is implemented and returns a list of dicts with `date` (formatted), `description`, `category` (lowercase), `amount` (currency string)
- [ ] `get_category_breakdown(user_id)` is implemented and returns a list of dicts with `name`, `amount` (currency string), `pct` (int 0–100)
- [ ] `profile()` view in `app.py` imports and calls all four new DB functions
- [ ] `/profile` returns HTTP 200 for a logged-in user with real data populated
- [ ] `/profile` redirects to `/login` for an unauthenticated request
- [ ] Profile page displays the real logged-in user's name and email (not "Alex Rivera")
- [ ] Profile page displays correct total spent and transaction count from the DB
- [ ] Profile page displays correct top-spending category
- [ ] Profile page displays up to 6 most recent transactions in descending date order
- [ ] Profile page displays all categories with correct amounts and percentage bars
- [ ] Page renders without errors when the user has zero expenses
- [ ] All existing tests in `tests/test_profile.py` pass (or are updated to reflect real-data assertions)
- [ ] All existing tests in `tests/test_auth.py` and `tests/test_registration.py` continue to pass
- [ ] No hex colour literals appear in the rendered HTML (existing test `test_profile_no_hex_colours` passes)
- [ ] All new functions have PEP 8-compliant signatures with type annotations