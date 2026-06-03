import pytest

from app import create_app, normalize_dna_sequence, is_valid_dna_sequence


@pytest.fixture
def app(tmp_path):
    test_database = tmp_path / "test_dna_sequences.db"

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "DATABASE": str(test_database),
        }
    )

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def signup(client, username="researcher", password="password123"):
    return client.post(
        "/signup",
        data={
            "username": username,
            "password": password,
        },
        follow_redirects=True,
    )


def login(client, username="researcher", password="password123"):
    return client.post(
        "/login",
        data={
            "username": username,
            "password": password,
        },
        follow_redirects=True,
    )


def test_homepage_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Welcome" in response.data


def test_user_can_signup_and_login(client):
    response = signup(client)
    assert response.status_code == 200
    assert b"Signup successful" in response.data

    response = login(client)
    assert response.status_code == 200
    assert b"Logged in successfully" in response.data


def test_login_required_for_upload_page(client):
    response = client.get("/upload", follow_redirects=True)
    assert response.status_code == 200
    assert b"Please log in first" in response.data


def test_user_can_upload_and_list_sequence(client):
    signup(client)
    login(client)

    response = client.post(
        "/upload",
        data={
            "title": "Example cancer sample",
            "sequence_text": "ACGT NNACGT",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"DNA sequence uploaded successfully" in response.data
    assert b"Example cancer sample" in response.data
    assert b"ACGTNNACGT" in response.data


def test_invalid_sequence_is_rejected(client):
    signup(client)
    login(client)

    response = client.post(
        "/upload",
        data={
            "title": "Invalid sample",
            "sequence_text": "ACGTXYZ",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Invalid DNA sequence" in response.data


def test_sequence_helpers():
    assert normalize_dna_sequence("acg t\nNN") == "ACGTNN"
    assert is_valid_dna_sequence("ACGTNN") is True
    assert is_valid_dna_sequence("ACGTXYZ") is False
