"""
tests/test_08-edit-expense.py
==============================
Pytest test suite for the Edit Expense feature (Step 8).

Spec under test
---------------
- GET  /expenses/<int:id>/edit — render pre-populated edit form for owner.
- POST /expenses/<int:id>/edit — validate, update DB row, redirect to /profile.
- @login_required enforced on both GET and POST.
- abort(404) when expense id does not exist.
- abort(403) when expense belongs to a different user.
- Server-side validation mirrors the add_expense rules:
    amount  → required, must be float, must be > 0
    category → must be in _VALID_CATEGORIES
    date    → required, must parse as YYYY-MM-DD
    description → optional
- On validation failure: re-render edit_expense.html (200) with the error
  message and re-populated submitted values.
- On success: update_expense_in_db(), flash "Expense updated successfully.",
  redirect to /profile.
"""

import sqlite3

import pytest
from werkzeug.security import generate_password_hash

import database.db as db_module
from app import app as flask_app
from database.db import init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app(tmp_path):
    """Flask app configured with an isolated on-disk SQLite DB per test.

    database/db.py reads _DB_PATH from the module so we monkey-patch it to a
    tmp_path file, ensuring every test gets a clean, independent database.
    """
    db_file = str(tmp_path / "test_expense_tracker.db")
    original_db_path = db_module._DB_PATH
    db_module._DB_PATH = db_file

    flask_app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with flask_app.app_context():
        init_db()
        yield flask_app

    # Restore original path so other test modules are not affected.
    db_module._DB_PATH = original_db_path


@pytest.fixture
def client(app):
    """Unauthenticated test client."""
    return app.test_client()


@pytest.fixture
def seed_user(app):
    """Insert one user into the test DB and return their user_id."""
    conn = sqlite3.connect(db_module._DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Test User", "test@example.com", generate_password_hash("password123")),
    )
    conn.commit()
    user_id = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("test@example.com",)
    ).fetchone()["id"]
    conn.close()
    return user_id


@pytest.fixture
def second_user(app):
    """Insert a second, different user and return their user_id."""
    conn = sqlite3.connect(db_module._DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Other User", "other@example.com", generate_password_hash("otherpass99")),
    )
    conn.commit()
    user_id = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("other@example.com",)
    ).fetchone()["id"]
    conn.close()
    return user_id


@pytest.fixture
def seed_expense(app, seed_user):
    """Insert one expense for seed_user and return its id."""
    conn = sqlite3.connect(db_module._DB_PATH)
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (seed_user, 45.50, "Food", "2026-05-01", "Grocery shopping"),
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id


@pytest.fixture
def logged_in_client(client, seed_user):
    """Test client with an active session for seed_user."""
    with client.session_transaction() as sess:
        sess["user_id"] = seed_user
        sess["user_name"] = "Test User"
    return client


# ---------------------------------------------------------------------------
# Helper: fetch the raw expense row directly from the DB (no ORM layer)
# ---------------------------------------------------------------------------


def _fetch_expense(expense_id: int) -> sqlite3.Row | None:
    """Query the DB directly and return the expense row (or None)."""
    conn = sqlite3.connect(db_module._DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, user_id, amount, category, date, description"
        " FROM expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()
    conn.close()
    return row


# ===========================================================================
# 1. Auth guard — unauthenticated access must redirect to /login
# ===========================================================================


class TestAuthGuard:
    def test_unauthenticated_get_redirects_to_login(self, client, seed_expense):
        """Unauthenticated GET /expenses/<id>/edit must return 302 to /login."""
        response = client.get(
            f"/expenses/{seed_expense}/edit", follow_redirects=False
        )
        assert response.status_code == 302, (
            "Unauthenticated GET must redirect (302)"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login for unauthenticated GET"
        )

    def test_unauthenticated_post_redirects_to_login(self, client, seed_expense):
        """Unauthenticated POST /expenses/<id>/edit must return 302 to /login."""
        response = client.post(
            f"/expenses/{seed_expense}/edit",
            data={
                "amount": "50.00",
                "category": "Food",
                "date": "2026-05-10",
                "description": "Attempt",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            "Unauthenticated POST must redirect (302)"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login for unauthenticated POST"
        )


# ===========================================================================
# 2. GET — edit form rendering
# ===========================================================================


class TestGetEditForm:
    def test_valid_owner_get_returns_200(self, logged_in_client, seed_expense):
        """Authenticated owner GET returns HTTP 200."""
        response = logged_in_client.get(f"/expenses/{seed_expense}/edit")
        assert response.status_code == 200, (
            "Owner GET /expenses/<id>/edit must return 200"
        )

    def test_form_prepopulated_with_amount(self, logged_in_client, seed_expense):
        """The current expense amount must appear in the response HTML."""
        response = logged_in_client.get(f"/expenses/{seed_expense}/edit")
        html = response.data.decode()
        # The original amount is 45.5; it may appear as "45.5" or "45.50"
        assert "45.5" in html, (
            "Pre-populated amount must be present in edit form HTML"
        )

    def test_form_prepopulated_with_category(self, logged_in_client, seed_expense):
        """The current expense category must appear in the response HTML."""
        response = logged_in_client.get(f"/expenses/{seed_expense}/edit")
        html = response.data.decode()
        assert "Food" in html, (
            "Pre-populated category must be present in edit form HTML"
        )

    def test_form_prepopulated_with_date(self, logged_in_client, seed_expense):
        """The current expense date must appear in the response HTML."""
        response = logged_in_client.get(f"/expenses/{seed_expense}/edit")
        html = response.data.decode()
        assert "2026-05-01" in html, (
            "Pre-populated date must be present in edit form HTML"
        )

    def test_form_prepopulated_with_description(self, logged_in_client, seed_expense):
        """The current expense description must appear in the response HTML."""
        response = logged_in_client.get(f"/expenses/{seed_expense}/edit")
        html = response.data.decode()
        assert "Grocery shopping" in html, (
            "Pre-populated description must be present in edit form HTML"
        )

    def test_nonexistent_expense_id_returns_404(self, logged_in_client):
        """GET with a non-existent expense id must return 404."""
        response = logged_in_client.get("/expenses/99999/edit")
        assert response.status_code == 404, (
            "GET with non-existent id must return 404"
        )

    def test_another_users_expense_returns_403(
        self, client, seed_user, second_user, app
    ):
        """GET targeting another user's expense must return 403."""
        # Insert an expense belonging to second_user
        conn = sqlite3.connect(db_module._DB_PATH)
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (second_user, 99.00, "Bills", "2026-04-01", "Other's bill"),
        )
        conn.commit()
        other_expense_id = cursor.lastrowid
        conn.close()

        # Log in as seed_user (not second_user)
        with client.session_transaction() as sess:
            sess["user_id"] = seed_user
            sess["user_name"] = "Test User"

        response = client.get(
            f"/expenses/{other_expense_id}/edit", follow_redirects=False
        )
        assert response.status_code == 403, (
            "GET on another user's expense must return 403"
        )

    def test_edit_form_contains_save_changes_button(
        self, logged_in_client, seed_expense
    ):
        """The edit form must have a 'Save Changes' submit button."""
        response = logged_in_client.get(f"/expenses/{seed_expense}/edit")
        html = response.data.decode()
        assert "Save Changes" in html, (
            "Edit form must contain a 'Save Changes' submit button"
        )

    def test_edit_form_contains_back_link_to_profile(
        self, logged_in_client, seed_expense
    ):
        """The edit form must contain a back link pointing to /profile."""
        response = logged_in_client.get(f"/expenses/{seed_expense}/edit")
        html = response.data.decode()
        assert "/profile" in html, (
            "Edit form must contain a back link to /profile"
        )


# ===========================================================================
# 3. POST — validation errors
# ===========================================================================


class TestPostValidation:
    """Each validation failure must: re-render the form (200) with the
    specific error message from the spec."""

    def _post(self, client, expense_id, **overrides):
        """Helper: POST to the edit URL with default valid data, overriding
        specific fields to trigger validation errors."""
        data = {
            "amount": "50.00",
            "category": "Food",
            "date": "2026-05-10",
            "description": "Test description",
        }
        data.update(overrides)
        return client.post(
            f"/expenses/{expense_id}/edit",
            data=data,
            follow_redirects=False,
        )

    def test_missing_amount_returns_200(self, logged_in_client, seed_expense):
        response = self._post(logged_in_client, seed_expense, amount="")
        assert response.status_code == 200, (
            "Missing amount must re-render the form (200)"
        )

    def test_missing_amount_shows_error_message(self, logged_in_client, seed_expense):
        response = self._post(logged_in_client, seed_expense, amount="")
        assert b"Amount is required." in response.data, (
            "Missing amount must show 'Amount is required.' error"
        )

    def test_nonnumeric_amount_returns_200(self, logged_in_client, seed_expense):
        response = self._post(logged_in_client, seed_expense, amount="abc")
        assert response.status_code == 200, (
            "Non-numeric amount must re-render the form (200)"
        )

    def test_nonnumeric_amount_shows_error_message(
        self, logged_in_client, seed_expense
    ):
        response = self._post(logged_in_client, seed_expense, amount="abc")
        assert b"Amount must be a valid number." in response.data, (
            "Non-numeric amount must show 'Amount must be a valid number.' error"
        )

    def test_zero_amount_returns_200(self, logged_in_client, seed_expense):
        response = self._post(logged_in_client, seed_expense, amount="0")
        assert response.status_code == 200, (
            "Zero amount must re-render the form (200)"
        )

    def test_zero_amount_shows_error_message(self, logged_in_client, seed_expense):
        response = self._post(logged_in_client, seed_expense, amount="0")
        assert b"Amount must be greater than zero." in response.data, (
            "Zero amount must show 'Amount must be greater than zero.' error"
        )

    def test_negative_amount_returns_200(self, logged_in_client, seed_expense):
        response = self._post(logged_in_client, seed_expense, amount="-10.00")
        assert response.status_code == 200, (
            "Negative amount must re-render the form (200)"
        )

    def test_negative_amount_shows_error_message(self, logged_in_client, seed_expense):
        response = self._post(logged_in_client, seed_expense, amount="-10.00")
        assert b"Amount must be greater than zero." in response.data, (
            "Negative amount must show 'Amount must be greater than zero.' error"
        )

    def test_invalid_category_returns_200(self, logged_in_client, seed_expense):
        response = self._post(
            logged_in_client, seed_expense, category="InvalidCat"
        )
        assert response.status_code == 200, (
            "Invalid category must re-render the form (200)"
        )

    def test_invalid_category_shows_error_message(
        self, logged_in_client, seed_expense
    ):
        response = self._post(
            logged_in_client, seed_expense, category="InvalidCat"
        )
        assert b"Please select a valid category." in response.data, (
            "Invalid category must show 'Please select a valid category.' error"
        )

    def test_missing_date_returns_200(self, logged_in_client, seed_expense):
        response = self._post(logged_in_client, seed_expense, date="")
        assert response.status_code == 200, (
            "Missing date must re-render the form (200)"
        )

    def test_missing_date_shows_error_message(self, logged_in_client, seed_expense):
        response = self._post(logged_in_client, seed_expense, date="")
        assert b"Date is required." in response.data, (
            "Missing date must show 'Date is required.' error"
        )

    def test_malformed_date_returns_200(self, logged_in_client, seed_expense):
        response = self._post(logged_in_client, seed_expense, date="not-a-date")
        assert response.status_code == 200, (
            "Malformed date must re-render the form (200)"
        )

    def test_malformed_date_shows_error_message(self, logged_in_client, seed_expense):
        response = self._post(logged_in_client, seed_expense, date="not-a-date")
        assert b"Please enter a valid date." in response.data, (
            "Malformed date must show 'Please enter a valid date.' error"
        )

    @pytest.mark.parametrize(
        "field,value,expected_error",
        [
            ("amount", "", b"Amount is required."),
            ("amount", "abc", b"Amount must be a valid number."),
            ("amount", "0", b"Amount must be greater than zero."),
            ("amount", "-5.00", b"Amount must be greater than zero."),
            ("category", "NotReal", b"Please select a valid category."),
            ("date", "", b"Date is required."),
            ("date", "31/12/2026", b"Please enter a valid date."),
        ],
    )
    def test_parametrized_validation_errors(
        self, logged_in_client, seed_expense, field, value, expected_error
    ):
        """Parametrized coverage: each invalid input re-renders with the right error."""
        response = self._post(logged_in_client, seed_expense, **{field: value})
        assert response.status_code == 200, (
            f"Field '{field}' value {value!r} must re-render the form (200)"
        )
        assert expected_error in response.data, (
            f"Field '{field}' value {value!r} must show error {expected_error!r}"
        )

    def test_validation_error_does_not_update_db(
        self, logged_in_client, seed_expense
    ):
        """On a validation error the DB row must remain unchanged."""
        original = _fetch_expense(seed_expense)
        self._post(logged_in_client, seed_expense, amount="")
        after = _fetch_expense(seed_expense)
        assert float(after["amount"]) == float(original["amount"]), (
            "DB row must not be modified when validation fails"
        )


# ===========================================================================
# 4. POST — successful update
# ===========================================================================


class TestPostSuccess:
    """A valid POST must update the DB, flash the message, and redirect."""

    _VALID_PAYLOAD = {
        "amount": "48.00",
        "category": "Transport",
        "date": "2026-05-20",
        "description": "Weekly train pass",
    }

    def test_valid_post_redirects_302(self, logged_in_client, seed_expense):
        """Valid POST must return 302."""
        response = logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data=self._VALID_PAYLOAD,
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            "Valid POST must redirect with 302"
        )

    def test_valid_post_redirects_to_profile(self, logged_in_client, seed_expense):
        """Valid POST must redirect to /profile."""
        response = logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data=self._VALID_PAYLOAD,
            follow_redirects=False,
        )
        assert "/profile" in response.headers["Location"], (
            "Valid POST must redirect to /profile"
        )

    def test_valid_post_updates_amount_in_db(self, logged_in_client, seed_expense):
        """After a valid POST the expense amount must be updated in the DB."""
        logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data=self._VALID_PAYLOAD,
            follow_redirects=False,
        )
        row = _fetch_expense(seed_expense)
        assert row is not None, "Expense row must still exist after update"
        assert float(row["amount"]) == pytest.approx(48.00), (
            "DB amount must be updated to 48.00 after valid POST"
        )

    def test_valid_post_updates_category_in_db(self, logged_in_client, seed_expense):
        """After a valid POST the expense category must be updated in the DB."""
        logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data=self._VALID_PAYLOAD,
            follow_redirects=False,
        )
        row = _fetch_expense(seed_expense)
        assert row["category"] == "Transport", (
            "DB category must be updated to 'Transport' after valid POST"
        )

    def test_valid_post_updates_date_in_db(self, logged_in_client, seed_expense):
        """After a valid POST the expense date must be updated in the DB."""
        logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data=self._VALID_PAYLOAD,
            follow_redirects=False,
        )
        row = _fetch_expense(seed_expense)
        assert row["date"] == "2026-05-20", (
            "DB date must be updated to '2026-05-20' after valid POST"
        )

    def test_valid_post_updates_description_in_db(
        self, logged_in_client, seed_expense
    ):
        """After a valid POST the expense description must be updated in the DB."""
        logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data=self._VALID_PAYLOAD,
            follow_redirects=False,
        )
        row = _fetch_expense(seed_expense)
        assert row["description"] == "Weekly train pass", (
            "DB description must be updated after valid POST"
        )

    def test_valid_post_flash_message_appears_after_redirect(
        self, logged_in_client, seed_expense
    ):
        """After a valid POST following the redirect must show the flash message."""
        response = logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data=self._VALID_PAYLOAD,
            follow_redirects=True,
        )
        assert b"Expense updated successfully." in response.data, (
            "Flash message 'Expense updated successfully.' must appear after redirect"
        )

    def test_valid_post_optional_description_can_be_empty(
        self, logged_in_client, seed_expense
    ):
        """A valid POST with an empty description must succeed (description is optional)."""
        payload = dict(self._VALID_PAYLOAD, description="")
        response = logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            "Empty description must not cause a validation error"
        )
        row = _fetch_expense(seed_expense)
        # Description should be empty string or None after the update
        assert row["description"] in ("", None), (
            "DB description must be empty/None when submitted as blank"
        )

    def test_valid_post_id_unchanged(self, logged_in_client, seed_expense):
        """The expense id must remain the same after a successful edit."""
        logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data=self._VALID_PAYLOAD,
            follow_redirects=False,
        )
        row = _fetch_expense(seed_expense)
        assert row is not None, "Expense row must still exist after update"
        assert row["id"] == seed_expense, (
            "Expense id must not change after a successful edit"
        )


# ===========================================================================
# 5. Ownership enforcement on POST
# ===========================================================================


class TestOwnershipEnforcement:
    def test_post_another_users_expense_returns_403(
        self, client, seed_user, second_user, app
    ):
        """POST targeting another user's expense must return 403."""
        # Insert an expense belonging to second_user
        conn = sqlite3.connect(db_module._DB_PATH)
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (second_user, 99.00, "Bills", "2026-04-01", "Other's bill"),
        )
        conn.commit()
        other_expense_id = cursor.lastrowid
        conn.close()

        # Log in as seed_user (not second_user)
        with client.session_transaction() as sess:
            sess["user_id"] = seed_user
            sess["user_name"] = "Test User"

        response = client.post(
            f"/expenses/{other_expense_id}/edit",
            data={
                "amount": "50.00",
                "category": "Food",
                "date": "2026-05-10",
                "description": "Tampered",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403, (
            "POST on another user's expense must return 403"
        )

    def test_post_another_users_expense_db_row_unchanged(
        self, client, seed_user, second_user, app
    ):
        """When a 403 is returned the target expense row must remain unchanged."""
        conn = sqlite3.connect(db_module._DB_PATH)
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (second_user, 99.00, "Bills", "2026-04-01", "Other's bill"),
        )
        conn.commit()
        other_expense_id = cursor.lastrowid
        conn.close()

        original = _fetch_expense(other_expense_id)

        with client.session_transaction() as sess:
            sess["user_id"] = seed_user
            sess["user_name"] = "Test User"

        client.post(
            f"/expenses/{other_expense_id}/edit",
            data={
                "amount": "1.00",
                "category": "Food",
                "date": "2026-01-01",
                "description": "Tampered",
            },
            follow_redirects=False,
        )

        after = _fetch_expense(other_expense_id)
        assert float(after["amount"]) == float(original["amount"]), (
            "DB amount must not change after a 403-rejected POST"
        )
        assert after["category"] == original["category"], (
            "DB category must not change after a 403-rejected POST"
        )
        assert after["date"] == original["date"], (
            "DB date must not change after a 403-rejected POST"
        )

    def test_post_nonexistent_expense_returns_404(self, logged_in_client):
        """POST to a non-existent expense id must return 404."""
        response = logged_in_client.post(
            "/expenses/99999/edit",
            data={
                "amount": "50.00",
                "category": "Food",
                "date": "2026-05-10",
                "description": "Ghost",
            },
            follow_redirects=False,
        )
        assert response.status_code == 404, (
            "POST with non-existent id must return 404"
        )


# ===========================================================================
# 6. Field repopulation on validation error
# ===========================================================================


class TestFieldRepopulation:
    """When a POST fails validation the submitted (invalid) values must be
    echoed back in the rendered form so the user does not lose their input."""

    def test_submitted_amount_echoed_on_error(self, logged_in_client, seed_expense):
        """Submitted non-numeric amount must appear in the re-rendered form."""
        response = logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data={
                "amount": "not-a-number",
                "category": "Food",
                "date": "2026-05-10",
                "description": "Some description",
            },
            follow_redirects=False,
        )
        html = response.data.decode()
        assert "not-a-number" in html, (
            "Submitted invalid amount must be echoed back in the re-rendered form"
        )

    def test_submitted_category_echoed_on_error(self, logged_in_client, seed_expense):
        """When category is invalid the submitted value (or empty) must not cause
        a crash and the valid category options must still be rendered."""
        response = logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data={
                "amount": "",  # trigger a different error so form re-renders
                "category": "Food",
                "date": "2026-05-10",
                "description": "Check category",
            },
            follow_redirects=False,
        )
        html = response.data.decode()
        # The form must still list the valid categories
        assert "Food" in html, (
            "Valid categories must appear in the re-rendered form after a validation error"
        )

    def test_submitted_date_echoed_on_error(self, logged_in_client, seed_expense):
        """Submitted date must be echoed back when another field fails."""
        response = logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data={
                "amount": "",  # trigger amount error so we can check date echo
                "category": "Food",
                "date": "2026-07-15",
                "description": "Check date echo",
            },
            follow_redirects=False,
        )
        html = response.data.decode()
        assert "2026-07-15" in html, (
            "Submitted date must be echoed back in the re-rendered form on validation error"
        )

    def test_submitted_description_echoed_on_error(
        self, logged_in_client, seed_expense
    ):
        """Submitted description must be echoed back when another field fails."""
        response = logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data={
                "amount": "",  # trigger amount error
                "category": "Food",
                "date": "2026-05-10",
                "description": "My unique description text",
            },
            follow_redirects=False,
        )
        html = response.data.decode()
        assert "My unique description text" in html, (
            "Submitted description must be echoed back in the re-rendered form on error"
        )

    def test_invalid_amount_value_echoed_when_date_also_bad(
        self, logged_in_client, seed_expense
    ):
        """When amount fails first the submitted amount is echoed (not the original)."""
        response = logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data={
                "amount": "xyz",
                "category": "Health",
                "date": "2026-05-10",
                "description": "",
            },
            follow_redirects=False,
        )
        html = response.data.decode()
        assert "xyz" in html, (
            "The submitted bad amount 'xyz' must appear in the re-rendered form"
        )

    def test_error_banner_uses_alert_error_class(self, logged_in_client, seed_expense):
        """The error banner must use the '.alert-error' CSS class from the spec."""
        response = logged_in_client.post(
            f"/expenses/{seed_expense}/edit",
            data={
                "amount": "",
                "category": "Food",
                "date": "2026-05-10",
                "description": "",
            },
            follow_redirects=False,
        )
        html = response.data.decode()
        assert "alert-error" in html, (
            "Error banner must use the 'alert-error' CSS class when a validation error occurs"
        )
