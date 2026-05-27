# Spec: Edit Expense Details

## 1. Overview

This feature replaces the `/expenses/<int:id>/edit` stub route with a fully functional edit form that lets a logged-in user update the amount, category, date, and description of an existing expense. On a successful `GET` the form is pre-populated with the expense's current values; on a valid `POST` the expense row is updated in the database and the user is redirected to the profile page with a confirmation flash message. This unblocks users from correcting data-entry mistakes without having to delete and re-add an expense.

---

## 2. Depends on

- `01-DB-setup.md` — `expenses` table must exist with columns `id`, `user_id`, `amount`, `category`, `date`, `description`
- `03-login-logout.md` — `session["user_id"]` must be set; `@login_required` decorator must be available
- `04-profile-page.md` — `/profile` is the redirect target after a successful edit
- `07-add-expense.md` — defines `_VALID_CATEGORIES`, the shared validation rules, and the `add_expense.html` form pattern that this form mirrors

---

## 3. Routes

- `GET /expenses/<int:id>/edit` — render the Edit Expense form pre-populated with the existing row's values (protected by `@login_required`)
- `POST /expenses/<int:id>/edit` — validate the submitted data, update the expense row, and redirect to `/profile`

---

## 4. Database Schema

No schema changes. The existing `expenses` table is sufficient:

| Column      | Type    | Constraints                              |
|-------------|---------|------------------------------------------|
| id          | INTEGER | PRIMARY KEY AUTOINCREMENT                |
| user_id     | INTEGER | NOT NULL, FOREIGN KEY → users(id)        |
| amount      | REAL    | NOT NULL                                 |
| category    | TEXT    | NOT NULL                                 |
| date        | TEXT    | NOT NULL (`YYYY-MM-DD`)                  |
| description | TEXT    | nullable                                 |
| created_at  | TEXT    | DEFAULT (datetime('now'))                |

---

## 5. Functions / Logic to Implement

### `get_expense_by_id(expense_id: int) -> sqlite3.Row | None`

**Location:** `database/db.py`

**Signature:**
```python
def get_expense_by_id(expense_id: int) -> sqlite3.Row | None:
```

**Responsibility:** Fetch a single expense row by its primary key, or return `None` if it doesn't exist.

**Key logic steps:**
1. Open a DB connection via `get_db()`.
2. Execute `SELECT id, user_id, amount, category, date, description FROM expenses WHERE id = ?` with `expense_id` as the parameter.
3. Return `cursor.fetchone()` (may be `None`).
4. Always close the connection in a `finally` block.

---

### `update_expense_in_db(expense_id: int, amount: float, category: str, date: str, description: str) -> None`

**Location:** `database/db.py`

**Signature:**
```python
def update_expense_in_db(
    expense_id: int,
    amount: float,
    category: str,
    date: str,
    description: str,
) -> None:
```

**Responsibility:** Update all editable fields of an existing expense row.

**Key logic steps:**
1. Open a DB connection via `get_db()`.
2. Execute a parameterised `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? WHERE id = ?`.
3. `conn.commit()`.
4. Always close the connection in a `finally` block.

---

### `edit_expense()` view function (replaces stub)

**Location:** `app.py`

**Signature:**
```python
@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(id: int) -> str | Response:
```

**Responsibility:** Render the pre-populated form on GET; validate, update, and redirect on POST.

**Key logic steps (GET):**
1. Call `get_expense_by_id(id)`. If `None`, `abort(404)`.
2. Check that `expense["user_id"] == session["user_id"]`. If not, `abort(403)`.
3. Render `templates/edit_expense.html` passing the expense's current field values and the categories list.

**Key logic steps (POST):**
1. Call `get_expense_by_id(id)`. If `None`, `abort(404)`.
2. Check that `expense["user_id"] == session["user_id"]`. If not, `abort(403)`.
3. Read `amount`, `category`, `date`, `description` from `request.form`; strip whitespace.
4. Validate (same rules as `add_expense`):
   - `amount`: must be present, parseable as `float`, and greater than 0.
   - `category`: must be one of `_VALID_CATEGORIES`.
   - `date`: must be present and parse via `datetime.strptime(raw_date, "%Y-%m-%d")`.
   - `description`: optional.
5. On any validation failure: re-render `edit_expense.html` with an `error` message and re-populated field values.
6. On success: call `update_expense_in_db(id, amount, category, raw_date, description)`, flash `"Expense updated successfully."`, redirect to `url_for("profile")`.

---

## 6. Templates / UI

### `templates/edit_expense.html` — **create**

Extends `base.html`. Mirrors the layout of `add_expense.html` with these differences:

- **Page heading** — "Edit Expense" instead of "Add Expense".
- **Amount** — `<input type="number" name="amount" step="0.01" min="0.01" required>` pre-filled with the expense's current `amount`.
- **Category** — `<select name="category">` with the seven fixed options; the current category is pre-selected.
- **Date** — `<input type="date" name="date">` pre-filled with the expense's current `date` (stored as `YYYY-MM-DD`).
- **Description** — `<textarea name="description" rows="3">` pre-filled with the current description (or empty if `None`).
- **Submit button** — labelled "Save Changes".
- **Error banner** — shown only when `{{ error }}` is set; uses the same `.alert-error` CSS class.
- **Back link** — `<a href="{{ url_for('profile') }}">← Back to Profile</a>` below the form.

### `templates/profile.html` — **modify** (optional UX improvement)

Add an "Edit" link/button next to each transaction row in the recent transactions table that points to `url_for('edit_expense', id=transaction.id)`. This requires passing the expense `id` through `get_recent_transactions`.

---

## 7. Files to Change

- `app.py` → replace stub `edit_expense()` with the real `GET`/`POST` handler; add `GET` and `POST` to the route `methods`; import `get_expense_by_id` and `update_expense_in_db` from `database.db`; add `abort` import from `flask`.
- `database/db.py` → add `get_expense_by_id` and `update_expense_in_db` functions; update the import line in `app.py` accordingly.
- `templates/profile.html` → (optional) expose expense `id` in transactions loop and add an "Edit" link per row.
- `database/db.py` → update `get_recent_transactions` to include `id` in the `SELECT` clause so edit links can be rendered on the profile page.

---

## 8. Files to Create

- `templates/edit_expense.html` — the Edit Expense form page.

---

## 9. Dependencies

None. All required packages (`Flask`, `sqlite3`, `datetime`) are already in use.

---

## 10. Rules for Implementation

- **`@login_required` is mandatory** — unauthenticated access redirects to `/login`.
- **Ownership check is mandatory** — if `expense["user_id"] != session["user_id"]`, call `abort(403)`. Never allow one user to edit another user's expense.
- **404 on missing expense** — if `get_expense_by_id(id)` returns `None`, call `abort(404)`.
- **Raw SQL only** — no SQLAlchemy or ORM.
- **Parameterised queries only** — `?` placeholders in SQL; never f-strings or `%` formatting.
- **`session["user_id"]` is the identity source** — never trust a hidden form field for ownership.
- **Server-side validation is authoritative** — same validation rules as `add_expense`; HTML attributes are UX hints only.
- **Amount must be a positive float** — use `float()` inside `try/except ValueError`; reject `0` and negatives.
- **Category must be allowlisted** — use `_VALID_CATEGORIES` defined in `app.py`.
- **Date must parse** — use `datetime.strptime(date_str, "%Y-%m-%d")`; wrap in `try/except ValueError`.
- **Flash messages on success only** — validation errors go into the `error` template variable, not `flash()`.
- **Type annotations** — all new and modified function signatures must include parameter and return types.
- **`black` + `ruff`** — format and lint after changes.
- **No inline styles** — use existing CSS classes; add new classes to `style.css` if needed.

---

## 11. Expected Behavior

1. Logged-in user views the profile page and clicks "Edit" next to a transaction (or navigates directly to `/expenses/3/edit`).
2. Browser loads the Edit Expense form pre-filled with the expense's current amount, category, date, and description.
3. User changes the amount from `45.50` to `48.00`, updates the description to "Weekly groceries + extras", and clicks "Save Changes".
4. Server validates all fields, updates the row in `expenses`, flashes "Expense updated successfully.", and redirects to `/profile`.
5. Profile page reloads showing the flash message and the updated expense reflected in stats and recent transactions.

---

## 12. Error Handling Expectations

| Failure Case | Expected Behavior |
|---|---|
| `id` does not exist in `expenses` | `abort(404)` — Flask renders a 404 page |
| `expense.user_id != session["user_id"]` | `abort(403)` — Flask renders a 403 page |
| Unauthenticated user accesses the route | `@login_required` redirects to `/login` with flash "Please log in to continue." |
| `amount` is empty | Re-render form with error "Amount is required." |
| `amount` is not a valid number (e.g. "abc") | Re-render form with error "Amount must be a valid number." |
| `amount` is zero or negative | Re-render form with error "Amount must be greater than zero." |
| `category` is missing or not in allowed list | Re-render form with error "Please select a valid category." |
| `date` is empty | Re-render form with error "Date is required." |
| `date` is not a valid `YYYY-MM-DD` string | Re-render form with error "Please enter a valid date." |
| DB write fails (unexpected) | Let the exception propagate to Flask's default 500 handler |

---

## 13. Definition of Done

- [ ] `GET /expenses/<int:id>/edit` returns HTTP 200 and renders the Edit Expense form pre-populated with existing field values for the owning user
- [ ] `GET /expenses/<int:id>/edit` returns 404 for a non-existent expense id
- [ ] `GET /expenses/<int:id>/edit` returns 403 when the expense belongs to a different user
- [ ] `GET /expenses/<int:id>/edit` redirects to `/login` for an unauthenticated user
- [ ] `POST /expenses/<int:id>/edit` with valid data updates the row in `expenses`, flashes "Expense updated successfully.", and redirects to `/profile`
- [ ] `POST /expenses/<int:id>/edit` with a missing or non-numeric `amount` re-renders the form with an error message
- [ ] `POST /expenses/<int:id>/edit` with a zero or negative `amount` re-renders the form with an error message
- [ ] `POST /expenses/<int:id>/edit` with an invalid category re-renders the form with an error message
- [ ] `POST /expenses/<int:id>/edit` with a missing or malformed date re-renders the form with an error message
- [ ] All submitted valid field values are re-populated in the form on validation error
- [ ] A user cannot edit another user's expense (403 enforced)
- [ ] `get_expense_by_id` is implemented in `database/db.py` using a parameterised SELECT
- [ ] `update_expense_in_db` is implemented in `database/db.py` using a parameterised UPDATE
- [ ] `session["user_id"]` (not a form field) is used for ownership verification
- [ ] All existing tests (`tests/test_auth.py`, `tests/test_registration.py`, `tests/test_profile.py`, `tests/test_add_expense.py`) continue to pass
- [ ] New and modified functions have PEP 8-compliant type annotations
- [ ] `black` and `ruff` report no issues on changed files