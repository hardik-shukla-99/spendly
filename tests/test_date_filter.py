"""
tests/test_date_filter.py
=========================
Pytest test suite for the Date Filter feature on the /profile page (Step 6).

Spec under test
---------------
- GET /profile accepts ?preset= and ?start=&end= query params.
- parse_date_filter() maps those params to (start, end) YYYY-MM-DD tuples.
- get_profile_stats, get_recent_transactions, get_category_breakdown all accept
  optional start/end kwargs and scope their SQL queries accordingly.
- The profile template renders a filter-bar, active-button highlighting, and a
  "Showing: …" label for non-all-time filters.
"""

import os
import sqlite3
import tempfile
from datetime import date, timedelta

import pytest
from flask import url_for

# ---------------------------------------------------------------------------
# Imports from the application under test
# ---------------------------------------------------------------------------
from app import app as flask_app
from app import parse_date_filter
from database.db import (
    get_category_breakdown,
    get_db,
    get_profile_stats,
    get_recent_transactions,
    init_db,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app(tmp_path):
    """Flask app configured with an isolated on-disk SQLite DB per test.

    We use a real file (not :memory:) because database/db.py's get_db() reads
    _DB_PATH from the module.  We monkey-patch _DB_PATH on the db module so
    every call within the test uses the temp file.
    """
    import database.db as db_module

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

    # Restore the original DB path so other test modules are unaffected.
    db_module._DB_PATH = original_db_path


@pytest.fixture
def client(app):
    """Unauthenticated test client."""
    return app.test_client()


@pytest.fixture
def seed_user(app):
    """Insert a single user into the test DB and return their id."""
    import database.db as db_module

    conn = sqlite3.connect(db_module._DB_PATH)
    conn.row_factory = sqlite3.Row
    from werkzeug.security import generate_password_hash

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
def logged_in_client(client, seed_user):
    """Test client with an active session for seed_user."""
    with client.session_transaction() as sess:
        sess["user_id"] = seed_user
        sess["user_name"] = "Test User"
    return client


@pytest.fixture
def client_with_expenses(logged_in_client, seed_user, app):
    """logged_in_client whose DB also contains expenses at known dates.

    Dates chosen so that:
      - 2026-01-15  — older than 90 days from 2026-05-25
      - 2026-03-20  — within last 90 days but older than 30 days from 2026-05-25
      - 2026-05-01  — within last 30 days from 2026-05-25
      - 2026-05-20  — within last 30 days from 2026-05-25
    """
    import database.db as db_module

    conn = sqlite3.connect(db_module._DB_PATH)
    expenses = [
        (seed_user, 10.00, "Food", "2026-01-15", "January item"),
        (seed_user, 20.00, "Transport", "2026-03-20", "March item"),
        (seed_user, 30.00, "Bills", "2026-05-01", "May item 1"),
        (seed_user, 40.00, "Health", "2026-05-20", "May item 2"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()
    return logged_in_client


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _insert_expense(db_path, user_id, amount, category, expense_date, description=""):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, description),
    )
    conn.commit()
    conn.close()


# ===========================================================================
# 1. Auth guard
# ===========================================================================


class TestAuthGuard:
    def test_unauthenticated_profile_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, (
            "Unauthenticated GET /profile must redirect (302)"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login"
        )

    def test_unauthenticated_profile_with_preset_redirects_to_login(self, client):
        response = client.get("/profile?preset=last30")
        assert response.status_code == 302, (
            "Unauthenticated GET /profile?preset=last30 must redirect"
        )
        assert "/login" in response.headers["Location"]

    def test_unauthenticated_profile_with_custom_dates_redirects_to_login(
        self, client
    ):
        response = client.get("/profile?start=2026-01-01&end=2026-05-25")
        assert response.status_code == 302, (
            "Unauthenticated GET /profile with custom dates must redirect"
        )


# ===========================================================================
# 2. Default / all-time behaviour (no query params)
# ===========================================================================


class TestNoFilter:
    def test_no_params_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert response.status_code == 200, "GET /profile (no params) must return 200"

    def test_no_params_all_time_button_is_active(self, logged_in_client):
        response = logged_in_client.get("/profile")
        html = response.data.decode()
        # The "All Time" anchor must carry the active class
        assert "filter-btn--active" in html, (
            "filter-btn--active class must be present when no filter is set"
        )
        # Verify the active class is on the All Time button, not another one
        # Find the segment that contains "All Time"
        all_time_idx = html.find("All Time")
        assert all_time_idx != -1, "'All Time' text must appear in the page"
        # The active class should appear before "All Time" within the same tag
        snippet_before = html[max(0, all_time_idx - 200) : all_time_idx]
        assert "filter-btn--active" in snippet_before, (
            "'All Time' anchor must have filter-btn--active class"
        )

    def test_no_params_no_showing_label(self, logged_in_client):
        response = logged_in_client.get("/profile")
        html = response.data.decode()
        assert "Showing:" not in html, (
            "No 'Showing:' label should appear when no filter is active"
        )

    def test_preset_all_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=all")
        assert response.status_code == 200, "GET /profile?preset=all must return 200"

    def test_preset_all_all_time_button_is_active(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=all")
        html = response.data.decode()
        all_time_idx = html.find("All Time")
        assert all_time_idx != -1, "'All Time' text must appear"
        snippet_before = html[max(0, all_time_idx - 200) : all_time_idx]
        assert "filter-btn--active" in snippet_before, (
            "'All Time' button must be active for ?preset=all"
        )

    def test_preset_all_no_showing_label(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=all")
        html = response.data.decode()
        assert "Showing:" not in html, (
            "No 'Showing:' label should appear for ?preset=all"
        )


# ===========================================================================
# 3. Preset filter buttons
# ===========================================================================


class TestPresetFilters:
    def test_preset_last30_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=last30")
        assert response.status_code == 200, "?preset=last30 must return 200"

    def test_preset_last30_active_button(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=last30")
        html = response.data.decode()
        last30_idx = html.find("Last 30 Days")
        assert last30_idx != -1, "'Last 30 Days' text must appear"
        snippet_before = html[max(0, last30_idx - 200) : last30_idx]
        assert "filter-btn--active" in snippet_before, (
            "'Last 30 Days' button must have filter-btn--active for ?preset=last30"
        )

    def test_preset_last30_showing_label(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=last30")
        html = response.data.decode()
        assert "Showing: Last 30 Days" in html, (
            "'Showing: Last 30 Days' label must appear for ?preset=last30"
        )

    def test_preset_last90_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=last90")
        assert response.status_code == 200, "?preset=last90 must return 200"

    def test_preset_last90_active_button(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=last90")
        html = response.data.decode()
        last3m_idx = html.find("Last 3 Months")
        assert last3m_idx != -1, "'Last 3 Months' text must appear"
        snippet_before = html[max(0, last3m_idx - 200) : last3m_idx]
        assert "filter-btn--active" in snippet_before, (
            "'Last 3 Months' button must have filter-btn--active for ?preset=last90"
        )

    def test_preset_last90_showing_label(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=last90")
        html = response.data.decode()
        assert "Showing: Last 3 Months" in html, (
            "'Showing: Last 3 Months' label must appear for ?preset=last90"
        )

    def test_preset_last365_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=last365")
        assert response.status_code == 200, "?preset=last365 must return 200"

    def test_preset_last365_active_button(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=last365")
        html = response.data.decode()
        this_year_idx = html.find("This Year")
        assert this_year_idx != -1, "'This Year' text must appear"
        snippet_before = html[max(0, this_year_idx - 200) : this_year_idx]
        assert "filter-btn--active" in snippet_before, (
            "'This Year' button must have filter-btn--active for ?preset=last365"
        )

    def test_preset_last365_showing_label(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=last365")
        html = response.data.decode()
        assert "Showing: This Year" in html, (
            "'Showing: This Year' label must appear for ?preset=last365"
        )


# ===========================================================================
# 4. Custom date range
# ===========================================================================


class TestCustomDateRange:
    def test_custom_range_returns_200(self, logged_in_client):
        response = logged_in_client.get(
            "/profile?start=2026-01-01&end=2026-05-25"
        )
        assert response.status_code == 200, "Custom date range must return 200"

    def test_custom_range_showing_label_contains_dates(self, logged_in_client):
        response = logged_in_client.get(
            "/profile?start=2026-01-01&end=2026-05-25"
        )
        html = response.data.decode()
        assert "Showing:" in html, "Custom date range must show a 'Showing:' label"
        assert "2026-01-01" in html, "Start date must appear in the Showing label"
        assert "2026-05-25" in html, "End date must appear in the Showing label"

    def test_custom_range_showing_label_format(self, logged_in_client):
        """Verify the label reads 'Showing: START – END' in human-readable format."""
        response = logged_in_client.get(
            "/profile?start=2026-03-01&end=2026-03-31"
        )
        html = response.data.decode()
        # The view formats dates as "Month D, YYYY" (e.g. "March 1, 2026")
        assert "Showing:" in html, "Showing label must be present for custom range"
        assert "March 1, 2026" in html, (
            "Showing label must render start date in 'Month D, YYYY' format"
        )
        assert "March 31, 2026" in html, (
            "Showing label must render end date in 'Month D, YYYY' format"
        )


# ===========================================================================
# 5. Malformed / partial / unrecognised inputs
# ===========================================================================


class TestMalformedInputs:
    def test_malformed_both_dates_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?start=bad&end=bad")
        assert response.status_code == 200, "Malformed dates must not cause a 500"

    def test_malformed_both_dates_no_showing_label(self, logged_in_client):
        response = logged_in_client.get("/profile?start=bad&end=bad")
        html = response.data.decode()
        assert "Showing:" not in html, (
            "Malformed dates must fall back to all-time (no Showing: label)"
        )

    def test_only_start_provided_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?start=2026-01-01")
        assert response.status_code == 200, "Only start param must not cause a 500"

    def test_only_start_provided_no_showing_label(self, logged_in_client):
        response = logged_in_client.get("/profile?start=2026-01-01")
        html = response.data.decode()
        assert "Showing:" not in html, (
            "Only-start param must fall back to all-time (no Showing: label)"
        )

    def test_only_end_provided_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?end=2026-05-25")
        assert response.status_code == 200, "Only end param must not cause a 500"

    def test_only_end_provided_no_showing_label(self, logged_in_client):
        response = logged_in_client.get("/profile?end=2026-05-25")
        html = response.data.decode()
        assert "Showing:" not in html, (
            "Only-end param must fall back to all-time (no Showing: label)"
        )

    def test_unknown_preset_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=foo")
        assert response.status_code == 200, "Unrecognised preset must not cause a 500"

    def test_unknown_preset_no_showing_label(self, logged_in_client):
        response = logged_in_client.get("/profile?preset=foo")
        html = response.data.decode()
        assert "Showing:" not in html, (
            "Unrecognised preset must fall back to all-time (no Showing: label)"
        )

    def test_start_after_end_returns_200(self, logged_in_client):
        """start > end is a valid parse; SQL returns zero rows but page must not crash."""
        response = logged_in_client.get(
            "/profile?start=2026-12-31&end=2026-01-01"
        )
        assert response.status_code == 200, "start > end must not cause a 500"


# ===========================================================================
# 6. Filter bar HTML structure
# ===========================================================================


class TestFilterBarHTML:
    def test_filter_bar_section_present(self, logged_in_client):
        response = logged_in_client.get("/profile")
        html = response.data.decode()
        assert "filter-bar" in html, (
            "filter-bar CSS class / section must be present in profile HTML"
        )

    def test_four_preset_anchor_links_present(self, logged_in_client):
        response = logged_in_client.get("/profile")
        html = response.data.decode()
        assert "preset=all" in html, "Preset link ?preset=all must exist"
        assert "preset=last30" in html, "Preset link ?preset=last30 must exist"
        assert "preset=last90" in html, "Preset link ?preset=last90 must exist"
        assert "preset=last365" in html, "Preset link ?preset=last365 must exist"

    def test_custom_form_method_get_present(self, logged_in_client):
        response = logged_in_client.get("/profile")
        html = response.data.decode()
        assert 'method="GET"' in html or "method=GET" in html.upper(), (
            "Custom date range form must use GET method"
        )

    def test_custom_form_start_input_present(self, logged_in_client):
        response = logged_in_client.get("/profile")
        html = response.data.decode()
        assert 'name="start"' in html, (
            "Custom date form must have an input with name='start'"
        )

    def test_custom_form_end_input_present(self, logged_in_client):
        response = logged_in_client.get("/profile")
        html = response.data.decode()
        assert 'name="end"' in html, (
            "Custom date form must have an input with name='end'"
        )

    def test_apply_submit_button_present(self, logged_in_client):
        response = logged_in_client.get("/profile")
        html = response.data.decode()
        assert "Apply" in html, "Custom date form must have an Apply submit button"

    def test_all_preset_button_labels_present(self, logged_in_client):
        response = logged_in_client.get("/profile")
        html = response.data.decode()
        for label in ["All Time", "Last 30 Days", "Last 3 Months", "This Year"]:
            assert label in html, f"Preset button label '{label}' must appear in HTML"


# ===========================================================================
# 7. Empty state (no matching expenses in selected range)
# ===========================================================================


class TestEmptyState:
    def test_filter_with_no_expenses_returns_200(self, logged_in_client):
        """No expenses exist for this user; any filter must render without crashing."""
        response = logged_in_client.get("/profile?preset=last30")
        assert response.status_code == 200, (
            "Profile page must render 200 even when the filtered window has no expenses"
        )

    def test_filter_with_no_matching_expenses_shows_zero_total(
        self, logged_in_client
    ):
        response = logged_in_client.get("/profile?preset=last30")
        html = response.data.decode()
        assert "$0.00" in html, (
            "Total Spent must display $0.00 when no expenses match the filter"
        )

    def test_custom_range_far_past_returns_200(self, logged_in_client):
        response = logged_in_client.get(
            "/profile?start=2000-01-01&end=2000-12-31"
        )
        assert response.status_code == 200, (
            "Custom range with zero matching expenses must not crash"
        )


# ===========================================================================
# 8. parse_date_filter unit tests
# ===========================================================================


class TestParseDateFilter:
    """Unit tests for the parse_date_filter() helper in app.py."""

    def test_valid_start_and_end_returns_them(self):
        result = parse_date_filter({"start": "2026-01-01", "end": "2026-05-25"})
        assert result == ("2026-01-01", "2026-05-25"), (
            "Valid start+end must be returned as-is"
        )

    def test_only_start_returns_none_none(self):
        result = parse_date_filter({"start": "2026-01-01"})
        assert result == (None, None), (
            "Only start (no end) must return (None, None)"
        )

    def test_only_end_returns_none_none(self):
        result = parse_date_filter({"end": "2026-05-25"})
        assert result == (None, None), (
            "Only end (no start) must return (None, None)"
        )

    def test_invalid_start_invalid_end_returns_none_none(self):
        result = parse_date_filter({"start": "bad", "end": "also-bad"})
        assert result == (None, None), (
            "Invalid date strings must return (None, None)"
        )

    def test_invalid_start_valid_end_returns_none_none(self):
        result = parse_date_filter({"start": "not-a-date", "end": "2026-05-25"})
        assert result == (None, None), (
            "One invalid date must cause fallback to (None, None)"
        )

    def test_preset_all_returns_none_none(self):
        result = parse_date_filter({"preset": "all"})
        assert result == (None, None), "preset=all must return (None, None)"

    def test_no_params_returns_none_none(self):
        result = parse_date_filter({})
        assert result == (None, None), "Empty args must return (None, None)"

    def test_unknown_preset_returns_none_none(self):
        result = parse_date_filter({"preset": "weekly"})
        assert result == (None, None), "Unknown preset must return (None, None)"

    def test_preset_last30_returns_correct_range(self):
        today = date.today()
        expected_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        expected_end = today.strftime("%Y-%m-%d")
        start, end = parse_date_filter({"preset": "last30"})
        assert start == expected_start, "preset=last30 start must be today - 30 days"
        assert end == expected_end, "preset=last30 end must be today"

    def test_preset_last90_returns_correct_range(self):
        today = date.today()
        expected_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")
        expected_end = today.strftime("%Y-%m-%d")
        start, end = parse_date_filter({"preset": "last90"})
        assert start == expected_start, "preset=last90 start must be today - 90 days"
        assert end == expected_end, "preset=last90 end must be today"

    def test_preset_last365_returns_correct_range(self):
        today = date.today()
        expected_start = (today - timedelta(days=365)).strftime("%Y-%m-%d")
        expected_end = today.strftime("%Y-%m-%d")
        start, end = parse_date_filter({"preset": "last365"})
        assert start == expected_start, (
            "preset=last365 start must be today - 365 days"
        )
        assert end == expected_end, "preset=last365 end must be today"

    def test_custom_range_overrides_preset(self):
        """When both start+end AND preset are present, custom range wins."""
        result = parse_date_filter(
            {"start": "2026-01-01", "end": "2026-03-31", "preset": "last30"}
        )
        assert result == ("2026-01-01", "2026-03-31"), (
            "Custom start+end must override preset param"
        )

    def test_returns_string_tuple_not_date_objects(self):
        start, end = parse_date_filter({"preset": "last30"})
        assert isinstance(start, str), "parse_date_filter must return strings"
        assert isinstance(end, str), "parse_date_filter must return strings"

    @pytest.mark.parametrize(
        "start,end",
        [
            ("2026/01/01", "2026/05/25"),   # wrong separator
            ("01-01-2026", "05-25-2026"),   # wrong order
            ("2026-13-01", "2026-05-25"),   # invalid month
            ("2026-01-32", "2026-05-25"),   # invalid day
        ],
    )
    def test_various_malformed_dates_return_none_none(self, start, end):
        result = parse_date_filter({"start": start, "end": end})
        assert result == (None, None), (
            f"Malformed dates start={start!r} end={end!r} must return (None, None)"
        )


# ===========================================================================
# 9. DB function scoping tests
# ===========================================================================


class TestGetProfileStatsScoping:
    """get_profile_stats() must honour start/end date bounds."""

    def test_no_filter_returns_all_expenses(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 10.00, "Food", "2026-01-15")
        _insert_expense(db_module._DB_PATH, seed_user, 20.00, "Transport", "2026-05-01")

        stats = get_profile_stats(seed_user)
        assert stats["transaction_count"] == 2, (
            "No filter must return all expenses"
        )

    def test_start_end_filter_excludes_older_expenses(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 10.00, "Food", "2026-01-15")
        _insert_expense(db_module._DB_PATH, seed_user, 20.00, "Transport", "2026-05-01")

        stats = get_profile_stats(seed_user, start="2026-04-01", end="2026-05-31")
        assert stats["transaction_count"] == 1, (
            "Filter must exclude expenses before start date"
        )

    def test_start_end_filter_excludes_newer_expenses(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 10.00, "Food", "2026-01-15")
        _insert_expense(db_module._DB_PATH, seed_user, 20.00, "Transport", "2026-05-01")

        stats = get_profile_stats(seed_user, start="2026-01-01", end="2026-02-28")
        assert stats["transaction_count"] == 1, (
            "Filter must exclude expenses after end date"
        )

    def test_filter_returns_correct_total_spent(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 50.00, "Bills", "2026-01-15")
        _insert_expense(db_module._DB_PATH, seed_user, 25.00, "Food", "2026-05-01")

        stats = get_profile_stats(seed_user, start="2026-04-01", end="2026-05-31")
        assert stats["total_spent"] == "$25.00", (
            "total_spent must reflect only in-range expenses"
        )

    def test_filter_empty_range_returns_zero_total(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 50.00, "Bills", "2026-01-15")

        stats = get_profile_stats(seed_user, start="2026-06-01", end="2026-06-30")
        assert stats["total_spent"] == "$0.00", (
            "Empty filtered range must return $0.00"
        )
        assert stats["transaction_count"] == 0, (
            "Empty filtered range must return 0 transactions"
        )

    def test_filter_empty_range_top_category_is_empty_string(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 50.00, "Bills", "2026-01-15")

        stats = get_profile_stats(seed_user, start="2026-06-01", end="2026-06-30")
        assert stats["top_category"] == "", (
            "Empty filtered range must return empty string for top_category"
        )

    def test_backward_compat_no_date_args_works(self, app, seed_user):
        """Calling get_profile_stats without start/end must not raise."""
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 15.00, "Food", "2026-05-01")

        stats = get_profile_stats(seed_user)
        assert isinstance(stats, dict), "Must return a dict even without date params"
        assert "total_spent" in stats
        assert "transaction_count" in stats
        assert "top_category" in stats

    def test_isolates_to_requesting_user(self, app, seed_user):
        """Expenses of a different user must not bleed into the stats."""
        import database.db as db_module
        from werkzeug.security import generate_password_hash

        conn = sqlite3.connect(db_module._DB_PATH)
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Other User", "other@example.com", generate_password_hash("pw12345!")),
        )
        conn.commit()
        other_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("other@example.com",)
        ).fetchone()[0]
        conn.close()

        _insert_expense(db_module._DB_PATH, seed_user, 10.00, "Food", "2026-05-01")
        _insert_expense(db_module._DB_PATH, other_id, 999.00, "Luxury", "2026-05-01")

        stats = get_profile_stats(seed_user)
        assert stats["transaction_count"] == 1, (
            "Stats must be scoped to the requesting user only"
        )


class TestGetRecentTransactionsScoping:
    """get_recent_transactions() must honour start/end date bounds."""

    def test_no_filter_returns_all_transactions_up_to_limit(
        self, app, seed_user
    ):
        import database.db as db_module

        for i in range(3):
            _insert_expense(
                db_module._DB_PATH, seed_user, float(i + 1), "Food",
                f"2026-0{i+1}-01"
            )

        txns = get_recent_transactions(seed_user, limit=10)
        assert len(txns) == 3, "No filter must return all expenses up to limit"

    def test_start_filter_excludes_older_transactions(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 10.00, "Food", "2026-01-15")
        _insert_expense(db_module._DB_PATH, seed_user, 20.00, "Bills", "2026-05-01")

        txns = get_recent_transactions(seed_user, limit=10, start="2026-04-01")
        assert len(txns) == 1, "start filter must exclude older transactions"
        # category is lowercased by get_recent_transactions
        assert txns[0]["category"] == "bills", (
            "Returned transaction must be the one within the range"
        )

    def test_end_filter_excludes_newer_transactions(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 10.00, "Food", "2026-01-15")
        _insert_expense(db_module._DB_PATH, seed_user, 20.00, "Bills", "2026-05-01")

        txns = get_recent_transactions(seed_user, limit=10, end="2026-02-28")
        assert len(txns) == 1, "end filter must exclude newer transactions"
        # category is lowercased by get_recent_transactions
        assert txns[0]["category"] == "food", (
            "Returned transaction must be the one within the range"
        )

    def test_start_and_end_filter_returns_only_matching(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 10.00, "Food", "2026-01-15")
        _insert_expense(db_module._DB_PATH, seed_user, 20.00, "Transport", "2026-03-20")
        _insert_expense(db_module._DB_PATH, seed_user, 30.00, "Bills", "2026-05-01")

        txns = get_recent_transactions(
            seed_user, limit=10, start="2026-03-01", end="2026-04-30"
        )
        assert len(txns) == 1, "start+end filter must return only matching transactions"

    def test_empty_range_returns_empty_list(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 10.00, "Food", "2026-01-15")

        txns = get_recent_transactions(
            seed_user, limit=10, start="2026-06-01", end="2026-06-30"
        )
        assert txns == [], "Empty filtered range must return empty list"

    def test_returned_transactions_have_expected_keys(self, app, seed_user):
        import database.db as db_module

        _insert_expense(
            db_module._DB_PATH, seed_user, 10.00, "Food", "2026-05-01", "Groceries"
        )

        txns = get_recent_transactions(seed_user, limit=10)
        assert len(txns) == 1
        tx = txns[0]
        for key in ("date", "description", "category", "amount"):
            assert key in tx, f"Transaction dict must contain key '{key}'"

    def test_backward_compat_no_date_args_works(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 15.00, "Food", "2026-05-01")

        txns = get_recent_transactions(seed_user)
        assert isinstance(txns, list), "Must return a list even without date params"


class TestGetCategoryBreakdownScoping:
    """get_category_breakdown() must honour start/end date bounds."""

    def test_no_filter_returns_all_categories(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 10.00, "Food", "2026-01-15")
        _insert_expense(db_module._DB_PATH, seed_user, 20.00, "Transport", "2026-05-01")

        cats = get_category_breakdown(seed_user)
        names = [c["name"] for c in cats]
        assert "Food" in names, "No-filter breakdown must include all categories"
        assert "Transport" in names

    def test_date_filter_excludes_out_of_range_categories(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 10.00, "Food", "2026-01-15")
        _insert_expense(db_module._DB_PATH, seed_user, 20.00, "Transport", "2026-05-01")

        cats = get_category_breakdown(
            seed_user, start="2026-04-01", end="2026-05-31"
        )
        names = [c["name"] for c in cats]
        assert "Transport" in names, "In-range category must be included"
        assert "Food" not in names, "Out-of-range category must be excluded"

    def test_date_filter_returns_correct_amounts(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 30.00, "Bills", "2026-05-01")
        _insert_expense(db_module._DB_PATH, seed_user, 30.00, "Bills", "2026-01-15")

        cats = get_category_breakdown(
            seed_user, start="2026-04-01", end="2026-05-31"
        )
        assert len(cats) == 1, "Only the in-range category must appear"
        assert cats[0]["amount"] == "$30.00", (
            "Amount must reflect only the in-range expense"
        )

    def test_empty_range_returns_empty_list(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 10.00, "Food", "2026-01-15")

        cats = get_category_breakdown(
            seed_user, start="2026-06-01", end="2026-06-30"
        )
        assert cats == [], "Empty filtered range must return empty list"

    def test_returned_categories_have_expected_keys(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 50.00, "Health", "2026-05-01")

        cats = get_category_breakdown(seed_user)
        assert len(cats) == 1
        cat = cats[0]
        for key in ("name", "amount", "pct"):
            assert key in cat, f"Category dict must contain key '{key}'"

    def test_percentage_sums_to_100_for_single_category(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 100.00, "Shopping", "2026-05-01")

        cats = get_category_breakdown(seed_user)
        assert cats[0]["pct"] == 100, (
            "Single category must have 100% share"
        )

    def test_backward_compat_no_date_args_works(self, app, seed_user):
        import database.db as db_module

        _insert_expense(db_module._DB_PATH, seed_user, 15.00, "Food", "2026-05-01")

        cats = get_category_breakdown(seed_user)
        assert isinstance(cats, list), "Must return a list even without date params"


# ===========================================================================
# 10. Integration: profile page data is scoped by date filter
# ===========================================================================


class TestProfilePageDataScoping:
    """End-to-end: the profile route passes date bounds to DB functions and
    the rendered page reflects only the in-range data."""

    def test_preset_last30_only_shows_recent_transactions(
        self, client_with_expenses, app
    ):
        """With expenses on 2026-01-15, 2026-03-20, 2026-05-01, 2026-05-20
        and today = 2026-05-25, preset=last30 should exclude Jan and March items."""
        response = client_with_expenses.get("/profile?preset=last30")
        assert response.status_code == 200
        html = response.data.decode()
        # Jan and March descriptions must not appear in recent transactions
        assert "January item" not in html, (
            "January expense must be excluded by last-30-days filter"
        )
        assert "March item" not in html, (
            "March expense must be excluded by last-30-days filter"
        )

    def test_custom_range_scopes_data_correctly(self, client_with_expenses, app):
        """Custom range 2026-01-01 – 2026-02-28 must show only the January expense."""
        response = client_with_expenses.get(
            "/profile?start=2026-01-01&end=2026-02-28"
        )
        assert response.status_code == 200
        html = response.data.decode()
        assert "January item" in html, (
            "January expense must appear within its date range"
        )
        assert "March item" not in html, (
            "March expense must be outside the specified range"
        )
        assert "May item 1" not in html, (
            "May item 1 must be outside the specified range"
        )

    def test_no_filter_shows_all_expenses(self, client_with_expenses, app):
        """No filter must show all four inserted expenses."""
        response = client_with_expenses.get("/profile")
        assert response.status_code == 200
        html = response.data.decode()
        # All four descriptions must be present (limit=6, we only have 4)
        for desc in ["January item", "March item", "May item 1", "May item 2"]:
            assert desc in html, f"'{desc}' must appear when no date filter is active"