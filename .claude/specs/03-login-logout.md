# Spec: Login and Logout

## 1. Overview

Implement the login and logout flows so registered users can authenticate into Spendly
and end their session. The `/login` route is currently a GET-only stub that renders the
template but never processes credentials. This step adds POST handling, credential
verification, Flask session management, and the `/logout` implementation. It also
introduces a login-required guard used by all future authenticated routes.

---

## 2. Depends on

- `01-DB-setup.md` — requires `users` table and `get_db()`.
- `02-user-registration.md` — requires `register_user()` and hashed passwords in DB.

---

## 3. Routes

- `GET /login` — render the login form (already exists; accept flash messages from registration)
- `POST /login` — validate credentials, set session, redirect to `/dashboard` or re-render with error
- `GET /logout` — clear session, redirect to `/login` (replaces stub)

---

## 4. Database Schema

No schema changes. Reads from the existing `users` table:

| Column        | Type    | Constraints               |
|---------------|---------|---------------------------|
| id            | INTEGER | PRIMARY KEY AUTOINCREMENT |
| email         | TEXT    | UNIQUE NOT NULL           |
| password_hash | TEXT    | NOT NULL                  |

---

## 5. Functions / Logic to Implement

### 5.1 `get_user_by_email(email)` in `database/db.py`

**Signature:**
```python
def get_user_by_email(email: str) -> sqlite3.Row | None:
```

**Responsibility:** Look up a user row by email; return `None` if not found.

**Key logic steps:**
1. Open a connection via `get_db()`.
2. Execute `SELECT id, name, email, password_hash FROM users WHERE email = ?` with a parameterized query.
3. Return `cursor.fetchone()` (a `sqlite3.Row` or `None`).
4. Close the connection in a `finally` block.

---

### 5.2 `POST /login` route handler in `app.py`

**Signature:**
```python
@app.route("/login", methods=["GET", "POST"])
def login() -> str | Response:
```

**Responsibility:** Authenticate the user and establish a session.

**Key logic steps:**
1. On `GET`: render `login.html`.
2. On `POST`:
   a. Strip and read `email` and `password` from `request.form`.
   b. Validate both fields are non-empty; re-render with error if blank.
   c. Call `get_user_by_email(email)`.
   d. If no user found, or `check_password_hash(user["password_hash"], password)` returns `False`: re-render with a generic error (`"Invalid email or password."`) — do not distinguish the two cases.
   e. On success: store `session["user_id"] = user["id"]` and `session["user_name"] = user["name"]`.
   f. Redirect to `url_for("dashboard")` (a future stub; for now redirect to `url_for("landing")`).

---

### 5.3 `GET /logout` route handler in `app.py`

**Signature:**
```python
@app.route("/logout")
def logout() -> Response:
```

**Responsibility:** Clear the session and send the user back to login.

**Key logic steps:**
1. Call `session.clear()`.
2. `flash("You have been logged out.")`.
3. `redirect(url_for("login"))`.

---

### 5.4 `login_required` decorator in `app.py`

**Signature:**
```python
def login_required(f: Callable) -> Callable:
```

**Responsibility:** Guard authenticated routes; redirect unauthenticated visitors to `/login`.

**Key logic steps:**
1. Check `session.get("user_id")`.
2. If absent: `flash("Please log in to continue.")` and `redirect(url_for("login"))`.
3. Otherwise call `f(*args, **kwargs)`.
4. Use `functools.wraps(f)` to preserve the wrapped function's metadata.

---

## 6. Templates / UI

- `templates/login.html` — **already exists**; ensure it:
  - Has a `<form method="POST">` that posts to `/login`
  - Renders `{{ error }}` for inline error messages
  - Renders `{% with messages = get_flashed_messages() %}` block for flash messages
  - Preserves the submitted `email` value in the input on re-render
- `templates/base.html` — update the **Logout** nav link `href` to `url_for("logout")` so it points to the real route instead of the stub.

---

## 7. Files to Change

- `app.py` →
  - Change `/login` to accept `GET` and `POST`; add POST handler
  - Replace `/logout` stub with real implementation
  - Add `login_required` decorator (import `functools` and `Callable` from `typing`)
  - Import `session`, `check_password_hash` (from `werkzeug.security`)
  - Import `get_user_by_email` from `database.db`
- `database/db.py` → add `get_user_by_email()` function
- `templates/login.html` → verify POST action, error display, flash block, and email value preservation
- `templates/base.html` → fix logout link href

---

## 8. Files to Create

- `tests/test_auth.py` — pytest tests covering login and logout flows.

---

## 9. Dependencies

None — `werkzeug.security` is already installed as part of Flask.

---

## 10. Rules for Implementation

- Raw SQL only — no SQLAlchemy or ORM.
- Parameterized queries exclusively — no string formatting in SQL.
- Use `werkzeug.security.check_password_hash` to verify passwords; never compare plaintext.
- Return the same error message for "user not found" and "wrong password" — do not distinguish them to avoid user enumeration.
- Store only `user_id` and `user_name` in the session — never store `password_hash` or sensitive data.
- `SECRET_KEY` must be set in `.env`; Flask sessions are cryptographically signed with it.
- `login_required` must use `functools.wraps` to preserve route function names (Flask uses `__name__` for endpoint registration — duplicated names cause `AssertionError`).
- Do not redirect to an arbitrary `next` URL without validating it is a local path (open-redirect risk); for now, always redirect to a fixed destination.
- PEP 8 + type annotations on all new function signatures.

---

## 11. Expected Behavior

A registered user navigates to `/login`, enters their email and password, and clicks
**Sign in**. The server looks up the user by email, verifies the password hash, stores
`user_id` and `user_name` in the Flask session, and redirects to the landing page (or
dashboard once implemented). When the user clicks **Logout** in the navbar, the session
is cleared and they are redirected to `/login` with a "You have been logged out." flash
message. Unauthenticated visitors who try to access a protected route are redirected to
`/login` with a "Please log in to continue." flash message.

---

## 12. Error Handling Expectations

| Failure case                        | Behaviour                                                                 |
|-------------------------------------|---------------------------------------------------------------------------|
| Email field is empty                | Re-render `login.html` with `error="Email and password are required."`    |
| Password field is empty             | Re-render `login.html` with `error="Email and password are required."`    |
| Email not found in DB               | Re-render `login.html` with `error="Invalid email or password."` (generic)|
| Password does not match hash        | Re-render `login.html` with `error="Invalid email or password."` (generic)|
| `SECRET_KEY` not set                | Flask raises `RuntimeError` — app startup already validates its presence  |
| DB error during lookup              | Let exception propagate; Flask debug mode surfaces it                     |
| Accessing protected route logged out| Redirect to `/login` with flash `"Please log in to continue."`           |

---

## 13. Definition of Done

- [ ] `POST /login` route validates credentials and sets `session["user_id"]`
- [ ] Successful login redirects away from the login page
- [ ] Failed login re-renders `login.html` with a generic inline error; submitted email is preserved
- [ ] `GET /logout` clears the session and redirects to `/login` with a flash message
- [ ] `get_user_by_email()` exists in `database/db.py` and uses a parameterized query
- [ ] Passwords are verified with `check_password_hash`; plaintext is never compared
- [ ] `login_required` decorator exists and guards future protected routes
- [ ] `templates/base.html` logout link points to `url_for("logout")`
- [ ] `tests/test_auth.py` covers: happy-path login, wrong password, unknown email, empty fields, logout clears session, protected route redirects
- [ ] All new functions have PEP 8 style and type annotations