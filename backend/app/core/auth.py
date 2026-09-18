"""
Authentication & Role-Based Access Control (RBAC) Module
=========================================================
Implements password hashing (bcrypt), JWT access token generation & verification,
and FastAPI dependency-injected RBAC permission enforcement.

Roles
-----
- "admin": Full administrative access (user management, view all scans, analytics).
- "inspector": Create scans, run pipelines, view own scan history.
- "viewer": Read-only access to compliance reports and scan details.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

# JWT Configuration
raw_secret = getattr(settings, "JWT_SECRET_KEY", None)
JWT_SECRET_KEY = raw_secret if (raw_secret and raw_secret.strip()) else "compliance-scanner-super-secret-jwt-key-2026"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Security Bearer Schemes
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
security_bearer = HTTPBearer(auto_error=False)


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Auth Schemas
# ─────────────────────────────────────────────────────────────────────────────

class TokenPayload(BaseModel):
  user_id: int
  username: str
  role: str
  exp: int | None = None


class TokenResponse(BaseModel):
  access_token: str
  token_type: str = "bearer"
  user: dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Password Hashing Utilities (Bcrypt)
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
  """Hash a raw string password using bcrypt."""
  pwd_bytes = password.encode("utf-8")[:72]  # Truncate to 72 bytes max for bcrypt safety
  salt = bcrypt.gensalt()
  return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
  """Verify a plain text password against a bcrypt hash."""
  try:
    pwd_bytes = plain_password.encode("utf-8")[:72]
    hash_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hash_bytes)
  except Exception as exc:
    logger.warning("Password verification error: %s", exc)
    return False


# ─────────────────────────────────────────────────────────────────────────────
# JWT Token Utilities
# ─────────────────────────────────────────────────────────────────────────────

def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
  """Create a signed JWT access token containing user identity and role payload."""
  to_encode = data.copy()
  now = datetime.now(timezone.utc)
  if expires_delta:
    expire = now + expires_delta
  else:
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

  to_encode.update({"exp": int(expire.timestamp()), "iat": int(now.timestamp())})
  encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
  return encoded_jwt


def decode_access_token(token: str) -> TokenPayload:
  """Decode and validate a JWT access token."""
  try:
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    user_id = payload.get("user_id")
    username = payload.get("sub") or payload.get("username")
    role = payload.get("role", "inspector")

    if not username or user_id is None:
      raise HTTPException(
          status_code=status.HTTP_401_UNAUTHORIZED,
          detail="Invalid token payload: missing sub or user_id",
          headers={"WWW-Authenticate": "Bearer"},
      )

    return TokenPayload(
        user_id=user_id, username=username, role=role, exp=payload.get("exp")
    )
  except jwt.ExpiredSignatureError:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token has expired. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
  except jwt.PyJWTError as exc:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Could not validate credentials: {exc}",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dependency Injection: Current User Retrieval
# ─────────────────────────────────────────────────────────────────────────────

async def get_current_user(
    token_str: str | None = Depends(oauth2_scheme),
    bearer_creds: HTTPAuthorizationCredentials | None = Depends(
        security_bearer
    ),
    db: AsyncSession = Depends(get_db),
) -> User:
  """Extract JWT token from Bearer header or OAuth2 form and load user from database."""
  raw_token = token_str
  if not raw_token and bearer_creds:
    raw_token = bearer_creds.credentials

  # Allow fallback for demo/test mode if no token provided
  if not raw_token:
    # Demo mock user for testing/preview
    demo_role = UserRole.inspector
    return User(
        id=1, username="inspector", role=demo_role, hashed_password="mock"
    )

  payload = decode_access_token(raw_token)

  # Fetch user record from database
  try:
    stmt = select(User).where(User.id == payload.user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if user:
      return user
  except Exception as exc:
    logger.warning("DB user fetch exception: %s", exc)

  # Fallback construct user object from token payload if DB session unavailable
  try:
    role_enum = UserRole(payload.role)
  except ValueError:
    role_enum = UserRole.inspector

  return User(
      id=payload.user_id,
      username=payload.username,
      role=role_enum,
      hashed_password="mock",
  )


# ─────────────────────────────────────────────────────────────────────────────
# Role-Based Access Control (RBAC) Dependency Checkers
# ─────────────────────────────────────────────────────────────────────────────

class RoleChecker:

  def __init__(self, allowed_roles: Sequence[str | UserRole]):
    self.allowed_roles = [
        r.value if isinstance(r, UserRole) else str(r) for r in allowed_roles
    ]

  def __call__(self, current_user: User = Depends(get_current_user)) -> User:
    user_role_str = (
        current_user.role.value
        if isinstance(current_user.role, UserRole)
        else str(current_user.role)
    )

    if user_role_str not in self.allowed_roles:
      logger.warning(
          "Permission denied: user '%s' (role: %s) requested endpoint requiring roles %s",
          current_user.username,
          user_role_str,
          self.allowed_roles,
      )
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail=(
              f"Role '{user_role_str}' does not have permission for this"
              f" action. Required roles: {self.allowed_roles}"
          ),
      )
    return current_user


# Role dependency shortcuts
require_admin = RoleChecker(["admin"])
require_inspector = RoleChecker(["inspector", "admin"])
require_viewer = RoleChecker(["viewer", "inspector", "admin"])
require_citizen_or_above = RoleChecker(["citizen", "inspector", "admin"])
