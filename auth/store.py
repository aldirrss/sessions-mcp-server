"""
Auth store — user CRUD, token generation/validation, OAuth code management.

Token design:
  - Raw token  : secrets.token_urlsafe(32)  — shown to user ONCE, never stored
  - token_hash : hashlib.sha256(raw).hexdigest() — stored in DB for lookup

Password design:
  - passlib bcrypt — slow intentionally, safe for credentials
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from passlib.hash import bcrypt

import db

_logger = logging.getLogger("lm-mcp-ai.auth")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _user_row(row) -> dict:
    return {
        "id": str(row["id"]),
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "is_active": row["is_active"],
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def _token_row(row) -> dict:
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "name": row["name"],
        "last_used_at": str(row["last_used_at"]) if row["last_used_at"] else None,
        "expires_at": str(row["expires_at"]) if row["expires_at"] else None,
        "revoked": row["revoked"],
        "created_at": str(row["created_at"]),
    }


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

async def register_user(username: str, email: str, password: str) -> dict:
    """Create a new user. Raises ValueError on duplicate username/email."""
    password_hash = bcrypt.hash(password)
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES ($1, $2, $3)
                RETURNING id, username, email, role, is_active, created_at, updated_at
                """,
                username.strip().lower(),
                email.strip().lower(),
                password_hash,
            )
        except Exception as exc:
            msg = str(exc)
            if "username" in msg and "unique" in msg.lower():
                raise ValueError(f"Username '{username}' is already taken.")
            if "email" in msg and "unique" in msg.lower():
                raise ValueError(f"Email '{email}' is already registered.")
            raise
    return _user_row(row)


async def authenticate_user(username_or_email: str, password: str) -> Optional[dict]:
    """Verify credentials. Returns user dict on success, None on failure."""
    val = username_or_email.strip().lower()
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE (username = $1 OR email = $1) AND is_active = true",
            val,
        )
    if row is None:
        return None
    if not bcrypt.verify(password, row["password_hash"]):
        return None
    return _user_row(row)


async def get_user(user_id: str) -> Optional[dict]:
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, email, role, is_active, created_at, updated_at FROM users WHERE id = $1",
            user_id,
        )
    return _user_row(row) if row else None


async def list_users() -> list[dict]:
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, username, email, role, is_active, created_at, updated_at FROM users ORDER BY created_at DESC"
        )
    return [_user_row(r) for r in rows]


async def set_user_role(user_id: str, role: str) -> bool:
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET role = $1 WHERE id = $2", role, user_id
        )
    return result != "UPDATE 0"


async def set_user_active(user_id: str, active: bool) -> bool:
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET is_active = $1 WHERE id = $2", active, user_id
        )
    return result != "UPDATE 0"


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

async def create_token(
    user_id: str,
    name: str,
    expires_days: Optional[int] = None,
) -> tuple[str, dict]:
    """Create a new PAT. Returns (raw_token, record). Raw token shown once."""
    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=expires_days)
        if expires_days
        else None
    )
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO user_tokens (user_id, token_hash, name, expires_at)
            VALUES ($1, $2, $3, $4)
            RETURNING id, user_id, name, last_used_at, expires_at, revoked, created_at
            """,
            user_id,
            token_hash,
            name,
            expires_at,
        )
    return raw, _token_row(row)


async def validate_token(raw: str) -> Optional[dict]:
    """Validate a raw token. Returns user dict on success, None on failure."""
    token_hash = _hash_token(raw)
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.username, u.email, u.role, u.is_active,
                   t.id AS token_id, t.revoked, t.expires_at
            FROM user_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token_hash = $1
            """,
            token_hash,
        )
        if row is None:
            return None
        if row["revoked"] or not row["is_active"]:
            return None
        if row["expires_at"] and row["expires_at"] < datetime.now(timezone.utc):
            return None
        await conn.execute(
            "UPDATE user_tokens SET last_used_at = NOW() WHERE id = $1",
            row["token_id"],
        )
    return {
        "id": str(row["id"]),
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
    }


async def list_tokens(user_id: str) -> list[dict]:
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_id, name, last_used_at, expires_at, revoked, created_at
            FROM user_tokens WHERE user_id = $1 ORDER BY created_at DESC
            """,
            user_id,
        )
    return [_token_row(r) for r in rows]


async def revoke_token(token_id: str, user_id: Optional[str] = None) -> bool:
    """Revoke a token. If user_id is given, only revoke if it belongs to that user."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        if user_id:
            result = await conn.execute(
                "UPDATE user_tokens SET revoked = true WHERE id = $1 AND user_id = $2",
                token_id, user_id,
            )
        else:
            result = await conn.execute(
                "UPDATE user_tokens SET revoked = true WHERE id = $1", token_id
            )
    return result != "UPDATE 0"


# ---------------------------------------------------------------------------
# OAuth PKCE codes
# ---------------------------------------------------------------------------

async def create_oauth_code(
    user_id: str, client_id: str, redirect_uri: str, code_challenge: str
) -> str:
    """Create a single-use auth code. Expires in 10 minutes."""
    code = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO oauth_codes (code, user_id, client_id, redirect_uri, code_challenge, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            code, user_id, client_id, redirect_uri, code_challenge, expires_at,
        )
    return code


async def exchange_oauth_code(
    code: str, client_id: str, redirect_uri: str, code_verifier: str
) -> Optional[dict]:
    """
    Validate and exchange an auth code for a user.
    Verifies PKCE S256 challenge. Marks code as used. Returns user dict or None.
    """
    import base64, hashlib as _hl

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT oc.user_id, oc.code_challenge, oc.expires_at, oc.used,
                   oc.client_id, oc.redirect_uri
            FROM oauth_codes oc
            WHERE oc.code = $1
            """,
            code,
        )
        if row is None or row["used"]:
            return None
        if row["expires_at"] < datetime.now(timezone.utc):
            return None
        if row["client_id"] != client_id or row["redirect_uri"] != redirect_uri:
            return None

        # PKCE S256 verification
        digest = _hl.sha256(code_verifier.encode()).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        if expected != row["code_challenge"]:
            return None

        await conn.execute("UPDATE oauth_codes SET used = true WHERE code = $1", code)
        user_row = await conn.fetchrow(
            "SELECT id, username, email, role, is_active FROM users WHERE id = $1",
            row["user_id"],
        )

    if not user_row or not user_row["is_active"]:
        return None
    return {
        "id": str(user_row["id"]),
        "username": user_row["username"],
        "email": user_row["email"],
        "role": user_row["role"],
    }
