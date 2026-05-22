import database.db as db_module


def _register(client, name="Alice Smith", email="alice@example.com", password="securepass"):
    return client.post(
        "/register",
        data={"name": name, "email": email, "password": password},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------

def test_register_get(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Create your account" in response.data


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_register_happy_path(client):
    # Act
    response = _register(client)

    # Assert — redirect to /login
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

    # Assert — user row exists in DB
    conn = db_module.get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", ("alice@example.com",)).fetchone()
    conn.close()
    assert user is not None
    assert user["name"] == "Alice Smith"
    assert user["password_hash"] != "securepass"  # must be hashed


# ---------------------------------------------------------------------------
# Duplicate email
# ---------------------------------------------------------------------------

def test_register_duplicate_email(client):
    _register(client)  # first registration

    response = _register(client)  # same email

    assert response.status_code == 200
    assert b"already exists" in response.data


# ---------------------------------------------------------------------------
# Validation — empty / invalid fields
# ---------------------------------------------------------------------------

def test_register_empty_name(client):
    response = _register(client, name="   ")
    assert response.status_code == 200
    assert b"Full name is required" in response.data


def test_register_invalid_email(client):
    response = _register(client, email="not-an-email")
    assert response.status_code == 200
    assert b"valid email address" in response.data


def test_register_short_password(client):
    response = _register(client, password="short")
    assert response.status_code == 200
    assert b"at least 8 characters" in response.data


# ---------------------------------------------------------------------------
# Field preservation on error
# ---------------------------------------------------------------------------

def test_register_preserves_fields_on_error(client):
    response = _register(client, password="short")
    body = response.data.decode()
    assert "alice@example.com" in body
    assert "Alice Smith" in body