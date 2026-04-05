"""
Integration tests for /api/auth/* endpoints.

Covers: register, login, /me, token validation, duplicate detection.
"""
import pytest


REGISTER_URL = "/api/auth/register"
LOGIN_URL    = "/api/auth/login"
ME_URL       = "/api/auth/me"


# ---------------------------------------------------------------------------
# Health check (smoke test)
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_endpoint(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegister:
    def _payload(self, username="newuser", email="new@example.com", password="pass1234"):
        return {"username": username, "email": email, "password": password}

    def test_register_success(self, client):
        r = client.post(REGISTER_URL, json=self._payload())
        assert r.status_code == 201
        body = r.json()
        assert body["username"] == "newuser"
        assert body["email"] == "new@example.com"
        assert "id" in body
        # password must never be returned
        assert "password" not in body
        assert "password_hash" not in body

    def test_register_returns_id(self, client):
        r = client.post(REGISTER_URL, json=self._payload())
        assert isinstance(r.json()["id"], int)

    def test_duplicate_username(self, client, user_alice):
        r = client.post(REGISTER_URL, json=self._payload(username="alice", email="other@example.com"))
        assert r.status_code == 400
        assert "Username already taken" in r.json()["detail"]

    def test_duplicate_email(self, client, user_alice):
        r = client.post(REGISTER_URL, json=self._payload(username="newone", email="alice@example.com"))
        assert r.status_code == 400
        assert "Email already registered" in r.json()["detail"]

    def test_register_missing_username(self, client):
        r = client.post(REGISTER_URL, json={"email": "a@b.com", "password": "pw"})
        assert r.status_code == 422

    def test_register_missing_password(self, client):
        r = client.post(REGISTER_URL, json={"username": "u", "email": "u@b.com"})
        assert r.status_code == 422

    def test_register_missing_email(self, client):
        r = client.post(REGISTER_URL, json={"username": "u", "password": "pw"})
        assert r.status_code == 422

    def test_two_different_users_can_register(self, client):
        r1 = client.post(REGISTER_URL, json=self._payload("u1", "u1@test.com"))
        r2 = client.post(REGISTER_URL, json=self._payload("u2", "u2@test.com"))
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] != r2.json()["id"]


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login_success(self, client, user_alice):
        r = client.post(LOGIN_URL, json={"username": "alice", "password": "secret123"})
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert isinstance(body["access_token"], str)
        assert len(body["access_token"]) > 20

    def test_login_wrong_password(self, client, user_alice):
        r = client.post(LOGIN_URL, json={"username": "alice", "password": "wrongpass"})
        assert r.status_code == 401
        assert "Invalid" in r.json()["detail"]

    def test_login_nonexistent_user(self, client):
        r = client.post(LOGIN_URL, json={"username": "ghost", "password": "anything"})
        assert r.status_code == 401

    def test_login_empty_password(self, client, user_alice):
        r = client.post(LOGIN_URL, json={"username": "alice", "password": ""})
        assert r.status_code == 401

    def test_login_missing_fields(self, client):
        r = client.post(LOGIN_URL, json={"username": "alice"})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# /me — protected route
# ---------------------------------------------------------------------------

class TestMe:
    def test_me_with_valid_token(self, client, user_alice, auth_headers_alice):
        r = client.get(ME_URL, headers=auth_headers_alice)
        assert r.status_code == 200
        body = r.json()
        assert body["username"] == "alice"
        assert body["email"] == "alice@example.com"

    def test_me_without_token(self, client):
        r = client.get(ME_URL)
        assert r.status_code == 401

    def test_me_with_invalid_token(self, client):
        r = client.get(ME_URL, headers={"Authorization": "Bearer totallyinvalidtoken"})
        assert r.status_code == 401

    def test_me_with_tampered_token(self, client, alice_token):
        tampered = alice_token[:-5] + "XXXXX"
        r = client.get(ME_URL, headers={"Authorization": f"Bearer {tampered}"})
        assert r.status_code == 401

    def test_me_returns_correct_user_for_bob(self, client, user_bob, auth_headers_bob):
        r = client.get(ME_URL, headers=auth_headers_bob)
        assert r.status_code == 200
        assert r.json()["username"] == "bob"

    def test_me_does_not_expose_password_hash(self, client, auth_headers_alice):
        r = client.get(ME_URL, headers=auth_headers_alice)
        assert "password_hash" not in r.json()
        assert "password" not in r.json()

    def test_me_with_token_for_deleted_user(self, client):
        """A valid JWT referencing a non-existent user_id should return 401."""
        from app.services.auth import create_access_token

        token = create_access_token(999999)
        r = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
