"""Unit tests for app.dependencies.auth."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from firebase_admin import auth as fa_auth
from tests.conftest import user_document

from app.dependencies.auth import (
    AUTHENTICATION_FAILED_DETAIL,
    INVALID_TOKEN_DETAIL,
    TOKEN_EXPIRED_DETAIL,
    TOKEN_REVOKED_DETAIL,
    get_optional_user,
    get_current_user,
    require_admin,
    verify_token,
    _verify_firebase_token,
)


def test_verify_token_missing_bearer():
    """Test that a missing bearer is rejected."""
    with pytest.raises(HTTPException) as exc:
        verify_token(authorization="Basic xxx")
    assert exc.value.status_code == 401
    assert exc.value.detail == INVALID_TOKEN_DETAIL


def test_get_current_user_missing_bearer():
    """Test that a missing bearer is rejected."""
    with pytest.raises(HTTPException) as exc:
        get_current_user(authorization="not-bearer")
    assert exc.value.status_code == 401


def test_verify_firebase_token_success(monkeypatch):
    """Test that a valid token is verified."""
    monkeypatch.setattr(
        "app.dependencies.auth.auth.verify_id_token",
        lambda token, clock_skew_seconds=0: {"uid": "u1", "email": "a@b.com"},
    )
    out = _verify_firebase_token("tok")
    assert out["uid"] == "u1"


def test_verify_firebase_token_expired(monkeypatch):
    """Test that a expired token is rejected."""

    monkeypatch.setattr(
        "app.dependencies.auth.auth.verify_id_token",
        MagicMock(side_effect=fa_auth.ExpiredIdTokenError("expired", None)),
    )
    with pytest.raises(HTTPException) as exc:
        _verify_firebase_token("x")
    assert exc.value.status_code == 401
    assert exc.value.detail == TOKEN_EXPIRED_DETAIL


def test_verify_firebase_token_revoked(monkeypatch):
    """Test that a revoked token is rejected."""

    monkeypatch.setattr(
        "app.dependencies.auth.auth.verify_id_token",
        MagicMock(side_effect=fa_auth.RevokedIdTokenError("revoked")),
    )
    with pytest.raises(HTTPException) as exc:
        _verify_firebase_token("x")
    assert exc.value.detail == TOKEN_REVOKED_DETAIL


def test_verify_firebase_token_invalid(monkeypatch):
    """Test that a invalid token is rejected."""

    monkeypatch.setattr(
        "app.dependencies.auth.auth.verify_id_token",
        MagicMock(side_effect=fa_auth.InvalidIdTokenError("invalid")),
    )
    with pytest.raises(HTTPException) as exc:
        _verify_firebase_token("x")
    assert exc.value.detail == INVALID_TOKEN_DETAIL


def test_verify_firebase_token_generic_error(monkeypatch):
    """Test that a generic error is rejected."""
    monkeypatch.setattr(
        "app.dependencies.auth.auth.verify_id_token",
        MagicMock(side_effect=RuntimeError("boom")),
    )
    with pytest.raises(HTTPException) as exc:
        _verify_firebase_token("x")
    assert exc.value.detail == AUTHENTICATION_FAILED_DETAIL


def test_get_optional_user_no_header():
    """Test that a no header is rejected."""
    assert get_optional_user(authorization=None) is None


def test_get_optional_user_invalid_header():
    """Test that a invalid header is rejected."""
    assert get_optional_user(authorization="nope") is None


def test_get_optional_user_invalid_token_swallowed(monkeypatch):
    """Test that a invalid token is swallowed."""
    monkeypatch.setattr(
        "app.dependencies.auth._verify_firebase_token",
        MagicMock(side_effect=HTTPException(status_code=401, detail="x")),
    )
    assert get_optional_user(authorization="Bearer bad") is None


def test_get_optional_user_valid(monkeypatch):
    """Test that a valid token is verified."""
    monkeypatch.setattr(
        "app.dependencies.auth._verify_firebase_token",
        lambda t: {"uid": "u1"},
    )
    assert get_optional_user(authorization="Bearer ok") == {"uid": "u1"}


def test_require_admin_success(monkeypatch, firestore_db):
    """Test that a user is verified as admin."""
    firestore_db.collection("users").document("adm").set(
        user_document(uid="adm", username="a", email="a@x.com", role="admin")
    )
    monkeypatch.setattr("app.dependencies.auth.firestore.client", lambda: firestore_db)
    out = require_admin({"uid": "adm", "email": "a@x.com"})
    assert out["uid"] == "adm"


def test_require_admin_user_missing(monkeypatch, firestore_db):
    """Test that a user not found is rejected."""
    monkeypatch.setattr("app.dependencies.auth.firestore.client", lambda: firestore_db)
    with pytest.raises(HTTPException) as exc:
        require_admin({"uid": "ghost", "email": "g@x.com"})
    assert exc.value.status_code == 404


def test_require_admin_forbidden(monkeypatch, firestore_db):
    """Test that a forbidden error is rejected."""

    firestore_db.collection("users").document("u").set(
        user_document(uid="u", username="u", email="u@x.com", role="user")
    )
    monkeypatch.setattr("app.dependencies.auth.firestore.client", lambda: firestore_db)
    with pytest.raises(HTTPException) as exc:
        require_admin({"uid": "u", "email": "u@x.com"})
    assert exc.value.status_code == 403


def test_require_admin_firestore_error(monkeypatch):
    """Test that a firestore error is rejected."""
    def failing_client():
        raise RuntimeError("db down")

    monkeypatch.setattr("app.dependencies.auth.firestore.client", failing_client)
    with pytest.raises(HTTPException) as exc:
        require_admin({"uid": "u", "email": "u@x.com"})
    assert exc.value.status_code == 500
