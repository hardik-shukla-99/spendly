"""Tests for the /profile route (Step 5 — real-DB data)."""

import database.db as db_module


def test_profile_redirects_when_not_logged_in(client):
    """Unauthenticated request must redirect to /login."""
    rv = client.get("/profile", follow_redirects=False)
    assert rv.status_code == 302
    assert "/login" in rv.headers["Location"]


def test_profile_renders_when_logged_in(client):
    """Authenticated request returns 200 with all four sections present."""
    user_id = db_module.register_user("Test User", "test@example.com", "password123")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = "Test User"

    rv = client.get("/profile")
    assert rv.status_code == 200

    # Section 2 — stats
    assert b"Total Spent" in rv.data
    assert b"Transactions" in rv.data
    assert b"Top Category" in rv.data

    # Section 3 — transaction table
    assert b"Recent Transactions" in rv.data

    # Section 4 — category breakdown
    assert b"Spending by Category" in rv.data


def test_profile_shows_user_info_card(client):
    """Profile page renders name and email in the user info card."""
    user_id = db_module.register_user("Jane Doe", "jane@example.com", "password123")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = "Jane Doe"

    rv = client.get("/profile")
    assert rv.status_code == 200
    assert b"Jane Doe" in rv.data
    assert b"jane@example.com" in rv.data


def test_profile_shows_transaction_rows(client):
    """Transaction table contains rows from DB-inserted expenses."""
    user_id = db_module.register_user("Jane Doe", "jane@example.com", "password123")
    conn = db_module.get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [
            (user_id, 50.00, "Food", "2026-05-20", "Test grocery"),
            (user_id, 30.00, "Health", "2026-05-18", "Test gym"),
            (user_id, 100.00, "Bills", "2026-05-15", "Test electricity"),
        ],
    )
    conn.commit()
    conn.close()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    rv = client.get("/profile")
    assert rv.status_code == 200
    assert b"Test grocery" in rv.data
    assert b"Test gym" in rv.data
    assert b"Test electricity" in rv.data


def test_profile_shows_category_breakdown(client):
    """Category breakdown contains categories from DB-inserted expenses."""
    user_id = db_module.register_user("Jane Doe", "jane@example.com", "password123")
    conn = db_module.get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [
            (user_id, 50.00, "Food", "2026-05-20", "Test grocery"),
            (user_id, 30.00, "Health", "2026-05-18", "Test gym"),
            (user_id, 100.00, "Bills", "2026-05-15", "Test electricity"),
        ],
    )
    conn.commit()
    conn.close()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    rv = client.get("/profile")
    assert rv.status_code == 200
    assert b"Food" in rv.data
    assert b"Health" in rv.data
    assert b"Bills" in rv.data


def test_profile_no_hex_colours(client):
    """profile.html must not contain raw hex colour literals."""
    user_id = db_module.register_user("Test User", "test@example.com", "password123")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = "Test User"

    rv = client.get("/profile")
    html = rv.data.decode("utf-8")

    # Crude but effective: look for patterns like #1a472a or #fff inside
    # style attributes or style blocks originating from profile.html itself.
    # (The test only checks the rendered page — not CSS files served separately.)
    import re
    # Allow #id selectors (single word after #) but flag colour hex codes
    hex_colour_pattern = re.compile(r'(?<![&\w])#([0-9a-fA-F]{3,6})\b')
    matches = hex_colour_pattern.findall(html)
    assert matches == [], f"Hex colour values found in rendered HTML: {matches}"
