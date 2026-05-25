# Spec: Date Filter for Profile Page

## 1. Overview

This feature adds a date-range filter to the `/profile` page so users can scope all displayed data — summary stats, recent transactions, and category breakdown — to a chosen time window (e.g. "Last 30 Days", "Last 3 Months", "This Year", or a custom start/end date). Currently the profile page always shows lifetime aggregate data; adding filters makes the page actionable for month-over-month review and sets the foundation for future reporting features.

---

## 2. Depends on

- `01-DB-setup.md` — `expenses` table with a `date` column (`TEXT`, `YYYY-MM-DD`) must exist
- `02-user-registration.md` — real user rows must be creatable
- `03-login-logout.md` — `session["user_id"]` must be set on login
- `04-profile-page.md` — `templates/profile.html` layout with four sections must exist
- `05-backend-routes-for-profile-page.md` — `get_profile_stats`, `get_recent_transactions`, `get_category_breakdown` must accept date-range parameters

---

## 3. Routes

- `GET /profile` — **modified**; now accepts optional query parameters:
  - `?preset=last30` | `last90` | `last365` | `all` (default: `all`)
  - `?start=YYYY-MM-DD&end=YYYY-MM-DD` — custom date range (overrides `preset` if both provided)

No new routes are added. Filtering is handled entirely via query-string parameters on the existing route.

---

## 4. Database Schema

No schema changes. The existing `expenses.date` column (`TEXT`, `YYYY-MM-DD`) is sufficient for `BETWEEN` range filtering.

---

## 5. Functions / Logic to Implement

### `parse_date_filter(args: dict) -> tuple[str | None, str | None]`

**Location:** `app.py` (module-level helper, not a route)

**Signature:**
```python
def parse_date_filter(args: dict) -> tuple[str | None, str | None]:
```

**Responsibility:** Parse the incoming query-string into a `(start_date, end_date)` tuple of `YYYY-MM-DD` strings, or `(None, None)` for "all time".

**Key logic steps:**
1. Check for `start` and `end` params first. If both are present and both parse successfully via `datetime.strptime(v, "%Y-%m-%d")`, return them as-is.
2. If only `start` or only `end` is present (but not both), ignore the partial custom range and fall through to preset logic.
3. Check `preset` param:
   - `"last30"` → `end = today`, `start = today - timedelta(days=30)`
   - `"last90"` → `end = today`, `start = today - timedelta(days=90)`
   - `"last365"` → `end = today`, `start = today - timedelta(days=365)`
   - `"all"` or absent → return `(None, None)`
4. Return start/end as `YYYY-MM-DD` strings (`date.strftime("%Y-%m-%d")`).
5. On any parse error, return `(None, None)` (graceful fallback to all-time).

---

### `get_profile_stats(user_id: int, start: str | None = None, end: str | None = None) -> dict`

**Location:** `database/db.py` — **modify signature** to accept optional date bounds.

**Signature:**
```python
def get_profile_stats(user_id: int, start: str | None = None, end: str | None = None) -> dict:
```

**Responsibility:** Return aggregate stats scoped to the optional date range.

**Key logic steps:**
1. Build the `WHERE` clause dynamically:
   - Always: `user_id = ?`
   - If `start` is not None: append `AND date >= ?`
   - If `end` is not None: append `AND date <= ?`
   - Collect params in a list in the same order.
2. Run the `SUM`/`COUNT` query and the top-category query, both with the same dynamic `WHERE` clause.
3. Return the existing dict shape unchanged — no new keys needed.

---

### `get_recent_transactions(user_id: int, limit: int = 6, start: str | None = None, end: str | None = None) -> list[dict]`

**Location:** `database/db.py` — **modify signature**.

**Signature:**
```python
def get_recent_transactions(user_id: int, limit: int = 6, start: str | None = None, end: str | None = None) -> list[dict]:
```

**Responsibility:** Return the N most recent expenses within the optional date range.

**Key logic steps:**
1. Build `WHERE` clause dynamically (same pattern as `get_profile_stats`).
2. Append `ORDER BY date DESC, id DESC LIMIT ?` — `limit` is always the last param.
3. Return the existing list-of-dicts shape unchanged.

---

### `get_category_breakdown(user_id: int, start: str | None = None, end: str | None = None) -> list[dict]`

**Location:** `database/db.py` — **modify signature**.

**Signature:**
```python
def get_category_breakdown(user_id: int, start: str | None = None, end: str | None = None) -> list[dict]:
```

**Responsibility:** Return per-category totals within the optional date range.

**Key logic steps:**
1. Build `WHERE` clause dynamically (same pattern as above).
2. Apply to both the grand-total query and the per-category query.
3. Return the existing list-of-dicts shape unchanged.

---

### `profile()` view function (modified)

**Location:** `app.py`

**Signature:**
```python
@app.route("/profile")
@login_required
def profile() -> str:
```

**Key logic steps:**
1. Call `parse_date_filter(request.args)` → `(start_date, end_date)`.
2. Determine `active_preset`: re-read `request.args.get("preset", "all")` for use in the template to highlight the active filter button.
3. Pass `start_date` and `end_date` into all three DB calls: `get_profile_stats`, `get_recent_transactions`, `get_category_breakdown`.
4. Pass `active_preset`, `start_date`, `end_date` to the template for rendering the filter bar.

---

## 6. Templates / UI

### `templates/profile.html` — **modify**

Add a **filter bar** section between the user-info card (Section 1) and the stats row (Section 2). The filter bar contains:

1. **Preset buttons** — four `<a>` tags linking to `?preset=last30`, `?preset=last90`, `?preset=last365`, `?preset=all`. The active preset gets a `filter-btn--active` CSS class, determined by `{{ active_preset }}`.
2. **Custom range form** — a `<form method="GET" action="{{ url_for('profile') }}">` with:
   - `<input type="date" name="start" value="{{ start_date or '' }}">` 
   - `<input type="date" name="end" value="{{ end_date or '' }}">`
   - A submit `<button>` labelled "Apply"
3. An **active filter label** shown only when a non-"all" filter is active, e.g. "Showing: Last 30 Days" or "Showing: May 1 – May 25, 2026". Use a `{% if active_preset != 'all' or start_date %}` guard.

The four existing sections (user card, stats row, transactions, categories) are **not restructured** — only the filter bar is inserted.

---

## 7. Files to Change

- `app.py` → add `parse_date_filter` helper; update `profile()` to call it and pass date args to DB functions; import `date` / `timedelta` from `datetime` if not already imported.
- `database/db.py` → add optional `start` / `end` params to `get_profile_stats`, `get_recent_transactions`, `get_category_breakdown`; build `WHERE` clauses dynamically using parameterised queries.
- `templates/profile.html` → insert filter bar between Section 1 and Section 2; add `filter-bar` CSS classes.
- `static/css/style.css` → add styles for `.filter-bar`, `.filter-btn`, `.filter-btn--active`, `.filter-label`.

---

## 8. Files to Create

None.

---

## 9. Dependencies

None. `datetime.date`, `datetime.timedelta`, and `datetime.datetime` are all part of the Python standard library and are already imported (or can be imported) from `datetime`.

---

## 10. Rules for Implementation

- **Raw SQL only** — no SQLAlchemy, no ORM.
- **Parameterised queries only** — `WHERE` clauses must be built by appending `?` placeholders and collecting values in a params list; never use f-strings or `%` formatting in SQL.
- **`session["user_id"]` is the single source of truth** — date params come from `request.args`, never from `request.form` on a GET request, and never trusted without parsing.
- **Graceful degradation** — any malformed or partial date input falls back to "all time" silently (no 400 error, no flash message).
- **Backward-compatible signatures** — all three DB functions must keep their existing keyword arguments as optional with `None` defaults so callers that don't pass dates continue to work unchanged (existing tests must still pass).
- **No inline styles, no hex colour literals** — use CSS variables; filter buttons styled via classes only.
- **Type annotations** — all new and modified function signatures must include parameter and return types.
- **`black` + `ruff`** — format and lint after changes.
- **`date` inputs must validate as `YYYY-MM-DD`** — `datetime.strptime(v, "%Y-%m-%d")` is the canonical validator; wrap in try/except.

---

## 11. Expected Behavior

1. User visits `/profile` with no query params → page loads with all-time data; "All Time" preset button is highlighted.
2. User clicks "Last 30 Days" → browser navigates to `/profile?preset=last30`; all three data sections (stats, transactions, categories) reflect only expenses from the last 30 calendar days; "Last 30 Days" button is highlighted.
3. User enters a custom date range (`start=2026-01-01`, `end=2026-03-31`) and clicks Apply → page reloads with `/profile?start=2026-01-01&end=2026-03-31`; data is scoped to that window; a label reads "Showing: January 1, 2026 – March 31, 2026".
4. User visits `/profile?preset=last30` with no expenses in that window → stats show `$0.00`, `0` transactions, empty top category, empty transaction table, empty category breakdown; the page renders without errors.
5. User visits `/profile?start=bad-date` → falls back to all-time; no error is shown.

---

## 12. Error Handling Expectations

| Failure Case | Expected Behavior |
|---|---|
| `start` or `end` param is not a valid `YYYY-MM-DD` string | `parse_date_filter` returns `(None, None)`; page renders with all-time data |
| Only `start` provided (no `end`) | Treated as incomplete custom range; falls through to preset logic or all-time |
| `start` is after `end` | Passed as-is to SQL (`BETWEEN` returns zero rows); page renders empty state gracefully |
| `preset` is an unrecognised string | Falls through to `(None, None)` — all-time data |
| No expenses exist in the selected range | All DB helpers return zeros/empty lists; template renders empty state, not a crash |
| DB file missing or corrupt | Flask default 500 handler (no special handling needed at this step) |

---

## 13. Definition of Done

- [ ] `parse_date_filter(args)` is implemented in `app.py` and correctly maps presets and custom date strings to `(start, end)` tuples
- [ ] `GET /profile?preset=last30` returns HTTP 200 and shows only expenses from the last 30 days
- [ ] `GET /profile?preset=last90` returns HTTP 200 and shows only expenses from the last 90 days
- [ ] `GET /profile?preset=last365` returns HTTP 200 and shows only expenses from the last 365 days
- [ ] `GET /profile?preset=all` (and no params) returns HTTP 200 and shows all-time data
- [ ] `GET /profile?start=YYYY-MM-DD&end=YYYY-MM-DD` returns HTTP 200 and shows data in that range
- [ ] Malformed date params silently fall back to all-time data (no 500, no 400)
- [ ] The active preset button has the `filter-btn--active` CSS class in the rendered HTML
- [ ] A "Showing: …" label appears when a non-all-time filter is active
- [ ] All three DB functions (`get_profile_stats`, `get_recent_transactions`, `get_category_breakdown`) accept `start` / `end` kwargs and apply them via parameterised `WHERE` clauses
- [ ] Existing callers of the three DB functions that omit `start`/`end` continue to work unchanged
- [ ] All existing tests in `tests/test_profile.py`, `tests/test_auth.py`, and `tests/test_registration.py` continue to pass
- [ ] No hex colour literals appear in the rendered HTML
- [ ] All new and modified functions have PEP 8-compliant signatures with type annotations
- [ ] `black` and `ruff` report no issues on changed files