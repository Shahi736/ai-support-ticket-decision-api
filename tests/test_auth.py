import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.api import app
from src.database import Base, engine
from src.schemas import AIDecision

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """Wipes and recreates all tables before each test for isolation."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def mock_ai_decision():
    """
    Mocks the AI decision pipeline so ticket tests don't hit Gemini's
    real API (avoids rate limits and keeps tests fast/deterministic).
    """
    fake_decision = AIDecision(
        action="REQUEST_PHOTOS",
        confidence=0.9,
        reason="Test reason",
        sources=["damaged_goods.md"],
    )
    with patch("src.api.make_decision", return_value=fake_decision):
        yield


def register_and_login(email: str, password: str) -> str:
    """Helper: registers a user, logs in, returns their access token."""
    client.post("/register", json={"email": email, "password": password})
    response = client.post("/login", json={"email": email, "password": password})
    return response.json()["access_token"]


def test_register_creates_user():
    response = client.post(
        "/register", json={"email": "alice@example.com", "password": "AlicePass123!"}
    )
    assert response.status_code == 201
    assert response.json()["email"] == "alice@example.com"


def test_register_duplicate_email_fails():
    client.post("/register", json={"email": "alice@example.com", "password": "AlicePass123!"})
    response = client.post(
        "/register", json={"email": "alice@example.com", "password": "AlicePass123!"}
    )
    assert response.status_code == 400


def test_login_success_returns_token():
    client.post("/register", json={"email": "alice@example.com", "password": "AlicePass123!"})
    response = client.post(
        "/login", json={"email": "alice@example.com", "password": "AlicePass123!"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password_fails():
    client.post("/register", json={"email": "alice@example.com", "password": "AlicePass123!"})
    response = client.post(
        "/login", json={"email": "alice@example.com", "password": "WrongPassword"}
    )
    assert response.status_code == 401


def test_me_requires_auth():
    response = client.get("/me")
    assert response.status_code == 401


def test_me_returns_current_user():
    token = register_and_login("alice@example.com", "AlicePass123!")
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_alice_cannot_access_bobs_ticket():
    """
    Core authorization test: Alice's token must not allow her to retrieve
    a ticket that belongs to Bob, even though the ticket exists.
    """
    alice_token = register_and_login("alice@example.com", "AlicePass123!")
    bob_token = register_and_login("bob@example.com", "BobPass123!")

    ticket_response = client.post(
        "/tickets",
        json={"message": "My order arrived damaged. It cost 3000 rupees."},
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert ticket_response.status_code == 201
    bob_ticket_id = ticket_response.json()["id"]

    response = client.get(
        f"/tickets/{bob_ticket_id}",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert response.status_code == 404


def test_user_can_access_own_ticket():
    token = register_and_login("alice@example.com", "AlicePass123!")

    ticket_response = client.post(
        "/tickets",
        json={"message": "My order arrived damaged. It cost 3000 rupees."},
        headers={"Authorization": f"Bearer {token}"},
    )
    ticket_id = ticket_response.json()["id"]

    response = client.get(
        f"/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == ticket_id