"""
Unit tests for app/services/auth.py

These tests exercise hashing, token creation, and the get_current_user
dependency in isolation — no HTTP layer involved.
"""
from datetime import datetime, timedelta

import pytest
from jose import jwt

from app.config import settings
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

class TestHashPassword:
    def test_returns_string(self):
        result = hash_password("mypassword")
        assert isinstance(result, str)

    def test_hash_is_not_plaintext(self):
        assert hash_password("mypassword") != "mypassword"

    def test_different_calls_produce_different_hashes(self):
        # bcrypt uses random salts
        h1 = hash_password("mypassword")
        h2 = hash_password("mypassword")
        assert h1 != h2

    def test_hash_is_long_enough(self):
        # bcrypt hashes are at least 60 chars
        assert len(hash_password("x")) >= 60


class TestVerifyPassword:
    def test_correct_password_returns_true(self):
        hashed = hash_password("correct")
        assert verify_password("correct", hashed) is True

    def test_wrong_password_returns_false(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_empty_password_vs_hash(self):
        hashed = hash_password("nonempty")
        assert verify_password("", hashed) is False

    def test_case_sensitive(self):
        hashed = hash_password("Password")
        assert verify_password("password", hashed) is False
        assert verify_password("Password", hashed) is True


# ---------------------------------------------------------------------------
# JWT creation
# ---------------------------------------------------------------------------

class TestCreateAccessToken:
    def test_returns_string(self):
        token = create_access_token(42)
        assert isinstance(token, str)

    def test_contains_user_id_as_sub(self):
        token = create_access_token(99)
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "99"

    def test_token_expires_in_future(self):
        token = create_access_token(1)
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        exp = datetime.utcfromtimestamp(payload["exp"])
        assert exp > datetime.utcnow()

    def test_expiry_roughly_matches_setting(self):
        before = datetime.utcnow()
        token = create_access_token(1)
        after = datetime.utcnow()
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        exp = datetime.utcfromtimestamp(payload["exp"])
        expected_min = before + timedelta(minutes=settings.access_token_expire_minutes - 1)
        expected_max = after  + timedelta(minutes=settings.access_token_expire_minutes + 1)
        assert expected_min <= exp <= expected_max

    def test_different_user_ids_produce_different_tokens(self):
        assert create_access_token(1) != create_access_token(2)

    def test_token_signed_with_correct_algorithm(self):
        token = create_access_token(5)
        header = jwt.get_unverified_header(token)
        assert header["alg"] == settings.jwt_algorithm

    def test_invalid_secret_raises(self):
        from jose import JWTError
        token = create_access_token(1)
        with pytest.raises(JWTError):
            jwt.decode(token, "wrong-secret", algorithms=[settings.jwt_algorithm])
