import database.db as db_module
from app import app as flask_app


def _register_user(email: str = "alice@example.com", password: str = "securepass") -> None:
    db_module.register_user("Alice Smith", email, password)


def _login(client, email: str = "alice@example.com", password: str = "securepass"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------

def test_login_get(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Sign in" in response.data


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_login_happy_path(client):
    _register_user()

    response = _login(client)

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess["user_id"] is not None
        assert sess["user_name"] == "Alice Smith"


# ---------------------------------------------------------------------------
# Wrong credentials
# ---------------------------------------------------------------------------

def test_login_wrong_password(client):
    _register_user()

    response = _login(client, password="wrongpass")

    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_login_unknown_email(client):
    response = _login(client, email="nobody@example.com")

    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


# ---------------------------------------------------------------------------
# Empty fields
# ---------------------------------------------------------------------------

def test_login_empty_email(client):
    response = _login(client, email="", password="securepass")
    assert response.status_code == 200
    assert b"Email and password are required" in response.data


def test_login_empty_password(client):
    response = _login(client, email="alice@example.com", password="")
    assert response.status_code == 200
    assert b"Email and password are required" in response.data


# ---------------------------------------------------------------------------
# Email preservation on error
# ---------------------------------------------------------------------------

def test_login_preserves_email_on_error(client):
    response = _login(client, email="alice@example.com", password="wrongpass")
    assert b"alice@example.com" in response.data


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def test_logout_clears_session(client):
    _register_user()
    _login(client)

    response = client.get("/logout", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_logout_flash_message(client):
    _register_user()
    _login(client)

    response = client.get("/logout", follow_redirects=True)

    assert b"logged out" in response.data


# ---------------------------------------------------------------------------
# login_required guard
# ---------------------------------------------------------------------------

def test_login_required_redirects_unauthenticated(client):
    # /profile is an existing stub — apply login_required to its view function
    # directly and invoke it via a request context to test the guard logic.
    from app import login_required
    from flask import request as flask_request

    with flask_app.test_request_context("/profile"):
        guarded = login_required(lambda: "ok")
        response = guarded()

    # login_required returns a redirect Response when unauthenticated
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# Already-logged-in redirects
# ---------------------------------------------------------------------------

def test_login_page_redirects_when_already_authenticated(client):
    _register_user()
    _login(client)

    response = client.get("/login", follow_redirects=False)

    assert response.status_code == 302
    assert "/" in response.headers["Location"]


def test_register_page_redirects_when_already_authenticated(client):
    _register_user()
    _login(client)

    response = client.get("/register", follow_redirects=False)

    assert response.status_code == 302
    assert "/" in response.headers["Location"]