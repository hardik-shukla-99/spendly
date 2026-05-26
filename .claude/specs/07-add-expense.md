# Spec: Add Expense

## 1. Overview

This feature replaces the `/expenses/add` stub route with a fully functional form that lets a logged-in user record a new expense (amount, category, date, optional description). On successful submission the expense is saved to the `expenses` table and the user is redirected to their profile page with a confirmation flash message. This is the first write operation in the app beyond registration, and it directly feeds the stats, transactions, and category breakdown on the profile page.

---

## 2. Depends on

- `01-DB-setup.md` — `expenses` table must exist with columns `user_id`, `amount`, `category`, `date`, `description`
- `02-user-registration.md` — real user rows must be creatable
- `03-login-logout.md` — `session["user_id"]` must be set; `@login_required` decorator must be available
- `04-profile-page.md` — `/profile` is the redirect target after a successful add

---

## 3. Routes

- `GET /expenses/add` — renders the Add Expense form (protected by `@login_required`)
- `POST /expenses/add` — validates and saves a new expense row, then redirects to `/profile`

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

### `add_expense_to_db(user_id: int, amount: float, category: str, date: str, description: str) -> int`

**Location:** `database/db.py`

**Signature:**
```python
def add_expense_to_db(
    user_id: int,
    amount: float,
    category: str,
    date: str,
    description: str,
) -> int:
```

**Responsibility:** Insert a validated expense row for the given user and return the new row's `id`.

**Key logic steps:**
1. Open a DB connection via `get_db()`.
2. Execute a parameterised `INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)`.
3. `conn.commit()`.
4. Return `cursor.lastrowid`.
5. Always close the connection in a `finally` block.

---

### `add_expense()` view function (modified stub)

**Location:** `app.py`

**Signature:**
```python
@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense() -> str | Response:
```

**Responsibility:** Render the form on GET; validate, save, and redirect on POST.

**Key logic steps (GET):**
1. Render `templates/add_expense.html` with the category list and today's date pre-filled.

**Key logic steps (POST):**
1. Read `amount`, `category`, `date`, `description` from `request.form`.
2. Strip whitespace from all string fields; treat blank `description` as `""`.
3. Validate:
   - `amount`: must be present and parseable as a positive `float` greater than 0.
   - `category`: must be one of the allowed category values (see Section 6).
   - `date`: must be present and match `YYYY-MM-DD` format via `datetime.strptime`.
   - `description`: optional; no length limit enforced beyond DB column type.
4. On any validation failure: re-render `add_expense.html` with an `error` message and re-populate form fields.
5. On success: call `add_expense_to_db(...)`, flash `"Expense added successfully."`, redirect to `url_for("profile")`.

---

## 6. Templates / UI

### `templates/add_expense.html` — **create**

Extends `base.html`. Renders a form with:

- **Amount** — `<input type="number" name="amount" step="0.01" min="0.01" required>` pre-filled with submitted value on error.
- **Category** — `<select name="category">` with the seven fixed options: Food, Transport, Bills, Health, Entertainment, Shopping, Other. Preserves selected value on error.
- **Date** — `<input type="date" name="date">` defaulting to today's date (`date.today().isoformat()`). Pre-filled with submitted value on error.
- **Description** — `<textarea name="description" rows="3">` optional. Pre-filled with submitted value on error.
- **Submit button** — labelled "Add Expense".
- **Error banner** — shown only when `{{ error }}` is set; styled with `.alert-error` CSS class (already used in login/register templates).
- **Back link** — `<a href="{{ url_for('profile') }}">← Back to Profile</a>` below the form.

---

## 7. Files to Change

- `app.py` → replace stub `add_expense()` with real `GET`/`POST` handler; add `@login_required`; import `add_expense_to_db` from `database.db`.
- `database/db.py` → add `add_expense_to_db` function; add it to the module's exports (no `__all__` exists, but update the import in `app.py`).

---

## 8. Files to Create

- `templates/add_expense.html` — the Add Expense form page.

---

## 9. Dependencies

None. All required packages (`Flask`, `sqlite3`, `datetime`) are already in use.

---

## 10. Rules for Implementation

- **`@login_required` is mandatory** — the route must be protected; unauthenticated access redirects to `/login`.
- **Raw SQL only** — no SQLAlchemy or ORM.
- **Parameterised queries only** — `?` placeholders in SQL; never f-strings or `%` formatting.
- **`session["user_id"]` is the user identity** — never trust a hidden form field for `user_id`.
- **Server-side validation is authoritative** — HTML `required` / `min` attributes are UX hints only; the POST handler must re-validate everything.
- **Amount must be a positive float** — use `float(amount_str)` inside a `try/except ValueError`; reject `0` and negative values.
- **Category must be allowlisted** — only the seven fixed values are accepted; any other value returns a validation error.
- **Date must parse** — use `datetime.strptime(date_str, "%Y-%m-%d")`; wrap in `try/except ValueError`.
- **Flash messages** — use `flash()` only on success before redirect; validation errors go into the `error` template variable (not flash).
- **Type annotations** — all new and modified function signatures must include parameter and return types.
- **`black` + `ruff`** — format and lint after changes.
- **No inline styles** — use existing CSS classes from `style.css`; add new classes to `style.css` if needed.

---

## 11. Expected Behavior

1. Logged-in user clicks "Add Expense" (link to `/expenses/add`) on the profile page.
2. Browser loads the Add Expense form with today's date pre-filled and "Food" as the default category.
3. User enters amount `45.50`, selects "Food", leaves the date as today, adds description "Weekly groceries", and submits.
4. Server validates all fields, inserts a row into `expenses`, flashes "Expense added successfully.", and redirects to `/profile`.
5. Profile page reloads showing the flash message and the new expense reflected in stats and recent transactions.

---

## 12. Error Handling Expectations

| Failure Case | Expected Behavior |
|---|---|
| `amount` is empty | Re-render form with error "Amount is required." |
| `amount` is not a valid number (e.g. "abc") | Re-render form with error "Amount must be a valid number." |
| `amount` is zero or negative | Re-render form with error "Amount must be greater than zero." |
| `category` is missing or not in allowed list | Re-render form with error "Please select a valid category." |
| `date` is empty | Re-render form with error "Date is required." |
| `date` is not a valid `YYYY-MM-DD` string | Re-render form with error "Please enter a valid date." |
| Unauthenticated user accesses `/expenses/add` | `@login_required` redirects to `/login` with flash "Please log in to continue." |
| DB write fails (e.g. constraint violation) | Let the exception propagate to Flask's default 500 handler (no special handling at this step). |

---

## 13. Definition of Done

- [ ] `GET /expenses/add` returns HTTP 200 and renders the Add Expense form for a logged-in user
- [ ] `GET /expenses/add` redirects to `/login` for an unauthenticated user
- [ ] Form pre-fills today's date by default
- [ ] `POST /expenses/add` with valid data inserts a row in `expenses`, flashes success, and redirects to `/profile`
- [ ] `POST /expenses/add` with a missing or non-numeric `amount` re-renders the form with an error message
- [ ] `POST /expenses/add` with a zero or negative `amount` re-renders the form with an error message
- [ ] `POST /expenses/add` with an invalid category re-renders the form with an error message
- [ ] `POST /expenses/add` with a missing or malformed date re-renders the form with an error message
- [ ] All previously submitted valid field values are re-populated in the form on validation error
- [ ] `add_expense_to_db` is implemented in `database/db.py` and uses a parameterised INSERT
- [ ] `session["user_id"]` (not a form field) is used as the expense's `user_id`
- [ ] The new expense appears in recent transactions and affects stats on `/profile` after a successful add
- [ ] All existing tests (`tests/test_auth.py`, `tests/test_registration.py`, `tests/test_profile.py`) continue to pass
- [ ] New and modified functions have PEP 8-compliant type annotations
- [ ] `black` and `ruff` report no issues on changed files