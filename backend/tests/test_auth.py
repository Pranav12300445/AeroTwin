"""Auth: password hashing (real bcrypt), JWT creation/decoding, current-user lookup, RBAC, seeding."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from jose import jwt

from app.auth import auth
from app.auth.auth import (
    create_access_token, decode_access_token, get_current_user,
    hash_password, require_role, seed_default_users, verify_password,
)
from app.config import Settings
from app.db.database import User
from app.models.schemas import UserRole


# ── password hashing ──

def test_hash_password_is_not_plaintext_and_is_salted():
    h1, h2 = hash_password("secret123"), hash_password("secret123")
    assert h1 != "secret123"
    assert h1 != h2  # random salt


def test_verify_password_accepts_correct_and_rejects_wrong(password_hashes):
    assert verify_password("admin123", password_hashes["admin"]) is True
    assert verify_password("admin124", password_hashes["admin"]) is False
    assert verify_password("", password_hashes["admin"]) is False


# ── JWT ──

def test_token_contains_subject_role_and_expiry():
    token = create_access_token("engineer", "maintenance_engineer")
    claims = decode_access_token(token)
    assert claims["sub"] == "engineer"
    assert claims["role"] == "maintenance_engineer"
    assert claims["exp"] > datetime.now(timezone.utc).timestamp()


def test_token_expiry_follows_settings(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: Settings(access_token_expire_minutes=5, _env_file=None))
    claims = decode_access_token(create_access_token("operator", "operator"))
    remaining = claims["exp"] - datetime.now(timezone.utc).timestamp()
    assert 4 * 60 < remaining <= 5 * 60


def test_expired_token_is_rejected(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: Settings(access_token_expire_minutes=-1, _env_file=None))
    assert decode_access_token(create_access_token("operator", "operator")) is None


def test_token_signed_with_other_secret_is_rejected():
    forged = jwt.encode(
        {"sub": "admin", "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "not-the-real-secret", algorithm="HS256",
    )
    assert decode_access_token(forged) is None


@pytest.mark.parametrize("bad", ["", "garbage", "a.b.c"])
def test_malformed_tokens_are_rejected(bad):
    assert decode_access_token(bad) is None


# ── get_current_user ──

async def test_get_current_user_returns_matching_user(seeded_db):
    async with seeded_db() as session:
        user = await get_current_user(create_access_token("engineer", "maintenance_engineer"), session)
    assert user.username == "engineer"
    assert user.role == "maintenance_engineer"


async def test_get_current_user_unknown_user_is_401(seeded_db):
    async with seeded_db() as session:
        with pytest.raises(HTTPException) as exc:
            await get_current_user(create_access_token("ghost", "admin"), session)
    assert exc.value.status_code == 401
    assert exc.value.headers == {"WWW-Authenticate": "Bearer"}


async def test_get_current_user_token_without_subject_is_401(seeded_db):
    token = jwt.encode({"role": "admin", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                       Settings(_env_file=None).jwt_secret_key, algorithm="HS256")
    async with seeded_db() as session:
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token, session)
    assert exc.value.status_code == 401


async def test_get_current_user_garbage_token_is_401(seeded_db):
    async with seeded_db() as session:
        with pytest.raises(HTTPException) as exc:
            await get_current_user("not-a-jwt", session)
    assert exc.value.status_code == 401


# ── RBAC ──

async def test_require_role_allows_listed_roles_and_returns_user():
    checker = require_role(UserRole.ADMIN, UserRole.MAINTENANCE_ENGINEER)
    user = SimpleNamespace(username="e", role="maintenance_engineer")
    assert await checker(user) is user


async def test_require_role_rejects_other_roles_with_403():
    checker = require_role(UserRole.ADMIN, UserRole.MAINTENANCE_ENGINEER)
    with pytest.raises(HTTPException) as exc:
        await checker(SimpleNamespace(username="o", role="operator"))
    assert exc.value.status_code == 403


# ── seeding ──

async def test_seed_default_users_creates_three_users_with_working_passwords(db):
    from sqlalchemy import select

    async with db() as session:
        await seed_default_users(session)
        users = {u.username: u for u in (await session.execute(select(User))).scalars()}

    assert {n: u.role for n, u in users.items()} == {
        "operator": "operator", "engineer": "maintenance_engineer", "admin": "admin",
    }
    assert verify_password("operator123", users["operator"].hashed_password)
    assert verify_password("engineer123", users["engineer"].hashed_password)
    assert verify_password("admin123", users["admin"].hashed_password)


async def test_seed_default_users_is_idempotent(db):
    from sqlalchemy import func, select

    async with db() as session:
        await seed_default_users(session)
        await seed_default_users(session)
        count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    assert count == 3


def test_user_role_enum_values():
    assert UserRole.OPERATOR == "operator"
    assert UserRole.MAINTENANCE_ENGINEER == "maintenance_engineer"
    assert UserRole.ADMIN == "admin"
