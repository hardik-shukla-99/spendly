"""Tests for the /profile route (Step 4 — static UI, hardcoded data)."""


def test_profile_redirects_when_not_logged_in(client):
    """Unauthenticated request must redirect to /login."""
    rv = client.get("/profile", follow_redirects=False)
    assert rv.status_code == 302
    assert "/login" in rv.headers["Location"]


def test_profile_renders_when_logged_in(client):
    """Authenticated request returns 200 with all four sections present."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
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
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_name"] = "Test User"

    rv = client.get("/profile")
    assert rv.status_code == 200
    assert b"Alex Rivera" in rv.data
    assert b"alex@example.com" in rv.data
    assert b"January 2024" in rv.data


def test_profile_shows_transaction_rows(client):
    """Transaction table contains at least three hardcoded rows."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_name"] = "Test User"

    rv = client.get("/profile")
    assert rv.status_code == 200
    assert b"Grocery run" in rv.data
    assert b"Monthly gym" in rv.data
    assert b"Electricity bill" in rv.data


def test_profile_shows_category_breakdown(client):
    """Category breakdown contains at least three categories."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_name"] = "Test User"

    rv = client.get("/profile")
    assert rv.status_code == 200
    assert b"Food &amp; Dining" in rv.data
    assert b"Utilities" in rv.data
    assert b"Health" in rv.data


def test_profile_no_hex_colours(client):
    """profile.html must not contain raw hex colour literals."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
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
