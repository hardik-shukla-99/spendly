# Spec: User Registration

## 1. Overview

Implement the user registration flow so new visitors can create a Spendly account.
The existing `GET /register` stub and `register.html` template are already in place;
this step adds form handling, server-side validation, password hashing, and database
insertion. A successful registration redirects the user to the login page. This
feature is the prerequisite for every authenticated route (profile, expenses).

---

## 2. Depends on

`01-DB-setup.md` — requires `users` table and `get_db()` to be working.

---

## 3. Routes

- `GET /register` — render the registration form (already exists; no change needed)
- `POST /register` — validate form data, create user, redirect or re-render with errors

---

## 4. Database Schema

No schema changes. Uses the existing `users` table:

| Column        | Type    | Constraints                   |
|---------------|---------|-------------------------------|
| id            | INTEGER | PRIMARY KEY AUTOINCREMENT     |
| name          | TEXT    | NOT NULL                      |
| email         | TEXT    | UNIQUE NOT NULL               |
| password_hash | TEXT    | NOT NULL                      |
| created_at    | TEXT    | DEFAULT datetime('now')       |

---

## 5. Functions / Logic to Implement

### 5.1 `register_user(name, email, password)` in `database/db.py`

**Signature:**
```python
def register_user(name: str, email: str, password: str) -> int:
```

**Responsibility:** Insert a new user record and return the new user's `id`.

**Key logic steps:**
1. Hash `password` with `werkzeug.security.generate_password_hash`.
2. Execute `INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)` using parameterized query.
3. Commit the connection.
4. Return `cursor.lastrowid`.
5. Let `sqlite3.IntegrityError` propagate — the route handler catches it to detect duplicate emails.

---

### 5.2 `POST /register` route handler in `app.py`

**Signature:**
```python
@app.route("/register", methods=["GET", "POST"])
def register() -> str | Response:
```

**Responsibility:** Handle form submission — validate, persist, redirect.

**Key logic steps:**
1. On `GET`: render `register.html` with no error.
2. On `POST`:
   a. Strip and read `name`, `email`, `password` from `request.form`.
   b. Run validation (see § 12); on failure re-render `register.html` with `error=<message>`.
   c. Call `register_user(name, email, password)`.
   d. On `sqlite3.IntegrityError` (duplicate email): re-render with `error="An account with that email already exists."`.
   e. On success: `flash("Account created — please sign in.")` and `redirect(url_for("login"))`.

---

## 6. Templates / UI

- `templates/register.html` — **already exists**; no structural changes needed.
  The template already renders `{{ error }}` and posts to `POST /register`.
- `templates/login.html` — add a flash message display block if not already present,
  so the success message from registration is visible after redirect.

---

## 7. Files to Change

- `app.py` → change `GET`-only `/register` route to accept `GET` and `POST`; add POST handler logic; import `sqlite3`, `request`, `redirect`, `url_for`, `flash` from flask.
- `database/db.py` → add `register_user()` function.
- `templates/login.html` → add flash message rendering block (one-time addition).

---

## 8. Files to Create

- `tests/test_registration.py` — pytest tests covering the registration flow.

---

## 9. Dependencies

None — `werkzeug.security` is already installed.

---

## 10. Rules for Implementation

- Raw SQL only — no SQLAlchemy or ORM.
- Parameterized queries exclusively — no string formatting in SQL.
- Hash passwords with `werkzeug.security.generate_password_hash`; never store plaintext.
- Minimum password length: 8 characters (validated server-side; the `placeholder` hint in the template already says "Min. 8 characters").
- Email must be non-empty and contain `@` (basic format check; full RFC validation is out of scope).
- Name must be non-empty after stripping whitespace.
- Do not leak whether an email is already registered via timing differences — use the same code path and only reveal it after the DB attempt fails.
- Use `flask.flash` for the success message so it persists across the redirect.
- `SECRET_KEY` must be set in `.env` for sessions/flash to work — document this in the error handling section.

---

## 11. Expected Behavior

A visitor navigates to `/register`, fills in their full name, email, and a password of
at least 8 characters, and clicks **Create account**. The server validates the inputs,
hashes the password, and inserts a new row into `users`. The user is redirected to
`/login` where a green flash banner reads "Account created — please sign in."
If any validation fails or the email is already taken, the registration form is
re-rendered with a clear inline error message and the submitted name and email values
are preserved in the form fields so the user does not have to retype them.

---

## 12. Error Handling Expectations

| Failure case                          | Behaviour                                                      |
|---------------------------------------|----------------------------------------------------------------|
| Name is empty or whitespace-only      | Re-render form with `error="Full name is required."`           |
| Email is empty or missing `@`         | Re-render form with `error="A valid email address is required."` |
| Password shorter than 8 characters   | Re-render form with `error="Password must be at least 8 characters."` |
| Email already registered (UNIQUE)     | Re-render form with `error="An account with that email already exists."` |
| `SECRET_KEY` not set                  | Flask raises `RuntimeError` on first `flash()` call — app startup should validate `SECRET_KEY` is present |
| Unexpected DB error                   | Let exception propagate (Flask's debug mode shows it); do not swallow silently |

---

## 13. Definition of Done

- [ ] `POST /register` route is wired and accepts form submissions
- [ ] `register_user()` function exists in `database/db.py`
- [ ] Passwords are stored hashed — never plaintext
- [ ] All three fields (name, email, password) are validated server-side
- [ ] Duplicate email returns a user-friendly inline error
- [ ] Successful registration redirects to `/login` with a flash message
- [ ] Form re-renders with error message on any validation failure
- [ ] `tests/test_registration.py` covers: happy path, duplicate email, empty fields, short password
- [ ] All queries use parameterized SQL
- [ ] App starts and registers a new user end-to-end without errors