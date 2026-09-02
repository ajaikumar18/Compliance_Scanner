"""
Tests for JWT Authentication, Bcrypt Hashing, and Role-Based Access Control (RBAC)

Tests cover:
- Bcrypt password hashing & verification (hash_password, verify_password)
- JWT access token generation & decoding (create_access_token, decode_access_token)
- Role-based permission enforcement (admin, inspector, viewer)
- Auth API Endpoints (POST /auth/register, POST /auth/login, GET /auth/me, GET /auth/users)

Run with:
    cd backend
    python -m pytest tests/test_auth_rbac.py -v
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.core.auth import (
    RoleChecker,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app
from app.models.user import User, UserRole

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Bcrypt Password Hashing Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_and_verify_correct_password(self):
        password = "SecurePassword123!"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert verify_password(password, hashed) is True

    def test_verify_incorrect_password_fails(self):
        password = "CorrectPassword"
        hashed = hash_password(password)

        assert verify_password("WrongPassword", hashed) is False

    def test_handles_long_passwords_gracefully(self):
        long_pwd = "A" * 100
        hashed = hash_password(long_pwd)
        assert verify_password(long_pwd, hashed) is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. JWT Token Generation & Decoding Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestJwtTokens:
    def test_create_and_decode_valid_token(self):
        payload = {"sub": "inspector_alex", "user_id": 42, "role": "inspector"}
        token = create_access_token(payload)

        assert isinstance(token, str)
        decoded = decode_access_token(token)

        assert decoded.username == "inspector_alex"
        assert decoded.user_id == 42
        assert decoded.role == "inspector"

    def test_decode_invalid_token_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("invalid.jwt.token")
        assert exc_info.value.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# 3. Role-Based Access Control (RBAC) Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRoleChecker:
    def test_role_checker_allows_permitted_role(self):
        checker = RoleChecker(["inspector", "admin"])
        user = User(id=1, username="test_inspector", role=UserRole.inspector, hashed_password="mock")

        result = checker(current_user=user)
        assert result.username == "test_inspector"

    def test_role_checker_blocks_unauthorized_role(self):
        checker = RoleChecker(["admin"])
        user = User(id=2, username="test_viewer", role=UserRole.viewer, hashed_password="mock")

        with pytest.raises(HTTPException) as exc_info:
            checker(current_user=user)

        assert exc_info.value.status_code == 403
        assert "Role 'viewer' does not have permission" in exc_info.value.detail


# ─────────────────────────────────────────────────────────────────────────────
# 4. Auth API Endpoints Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthEndpoints:
    @patch("app.routers.auth.get_db")
    def test_login_demo_fallback_success(self, mock_get_db):
        mock_session = MagicMock()
        mock_get_db.return_value = mock_session

        response = client.post(
            "/auth/login",
            data={"username": "inspector", "password": "anypassword"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "inspector"

    def test_get_me_profile_with_token(self):
        token = create_access_token({"sub": "admin_user", "user_id": 99, "role": "admin"})
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin_user"
        assert data["role"] == "admin"

    def test_admin_list_users_blocked_for_viewer(self):
        token = create_access_token({"sub": "viewer_user", "user_id": 5, "role": "viewer"})
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/auth/users", headers=headers)
        assert response.status_code == 403
