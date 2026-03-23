"""Unit tests for app.dependencies.auth."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

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
    with pytest.raises(HTTPException) as exc:
        verify_token(authorization="Basic xxx")
    assert exc.value.status_code == 401
    assert exc.value.detail == INVALID_TOKEN_DETAIL


def test_get_current_user_missing_bearer():
    with pytest.raises(HTTPException) as exc:
        get_current_user(authorization="not-bearer")
    assert exc.value.status_code == 401


def test_verify_firebase_token_success(monkeypatch):
    monkeypatch.setattr(
        "app.dependencies.auth.auth.verify_id_token",
        lambda token, clock_skew_seconds=0: {"uid": "u1", "email": "a@b.com"},
    )
    out = _verify_firebase_token("tok")
    assert out["uid"] == "u1"


def test_verify_firebase_token_expired(monkeypatch):
    from firebase_admin import auth as fa_auth

    monkeypatch.setattr(
        "app.dependencies.auth.auth.verify_id_token",
        MagicMock(side_effect=fa_auth.ExpiredIdTokenError("expired", None)),
    )
    with pytest.raises(HTTPException) as exc:
        _verify_firebase_token("x")
    assert exc.value.status_code == 401
    assert exc.value.detail == TOKEN_EXPIRED_DETAIL


def test_verify_firebase_token_revoked(monkeypatch):
    from firebase_admin import auth as fa_auth

    monkeypatch.setattr(
        "app.dependencies.auth.auth.verify_id_token",
        MagicMock(side_effect=fa_auth.RevokedIdTokenError("revoked")),
    )
    with pytest.raises(HTTPException) as exc:
        _verify_firebase_token("x")
    assert exc.value.detail == TOKEN_REVOKED_DETAIL


def test_verify_firebase_token_invalid(monkeypatch):
    from firebase_admin import auth as fa_auth

    monkeypatch.setattr(
        "app.dependencies.auth.auth.verify_id_token",
        MagicMock(side_effect=fa_auth.InvalidIdTokenError("invalid")),
    )
    with pytest.raises(HTTPException) as exc:
        _verify_firebase_token("x")
    assert exc.value.detail == INVALID_TOKEN_DETAIL


def test_verify_firebase_token_generic_error(monkeypatch):
    monkeypatch.setattr(
        "app.dependencies.auth.auth.verify_id_token",
        MagicMock(side_effect=RuntimeError("boom")),
    )
    with pytest.raises(HTTPException) as exc:
        _verify_firebase_token("x")
    assert exc.value.detail == AUTHENTICATION_FAILED_DETAIL


def test_get_optional_user_no_header():
    assert get_optional_user(authorization=None) is None


def test_get_optional_user_invalid_header():
    assert get_optional_user(authorization="nope") is None


def test_get_optional_user_invalid_token_swallowed(monkeypatch):
    monkeypatch.setattr(
        "app.dependencies.auth._verify_firebase_token",
        MagicMock(side_effect=HTTPException(status_code=401, detail="x")),
    )
    assert get_optional_user(authorization="Bearer bad") is None


def test_get_optional_user_valid(monkeypatch):
    monkeypatch.setattr(
        "app.dependencies.auth._verify_firebase_token",
        lambda t: {"uid": "u1"},
    )
    assert get_optional_user(authorization="Bearer ok") == {"uid": "u1"}


def test_require_admin_success(monkeypatch, firestore_db):
    from tests.conftest import user_document

    firestore_db.collection("users").document("adm").set(
        user_document(uid="adm", username="a", email="a@x.com", role="admin")
    )
    monkeypatch.setattr("app.dependencies.auth.firestore.client", lambda: firestore_db)
    out = require_admin({"uid": "adm", "email": "a@x.com"})
    assert out["uid"] == "adm"


def test_require_admin_user_missing(monkeypatch, firestore_db):
    monkeypatch.setattr("app.dependencies.auth.firestore.client", lambda: firestore_db)
    with pytest.raises(HTTPException) as exc:
        require_admin({"uid": "ghost", "email": "g@x.com"})
    assert exc.value.status_code == 404


def test_require_admin_forbidden(monkeypatch, firestore_db):
    from tests.conftest import user_document

    firestore_db.collection("users").document("u").set(
        user_document(uid="u", username="u", email="u@x.com", role="user")
    )
    monkeypatch.setattr("app.dependencies.auth.firestore.client", lambda: firestore_db)
    with pytest.raises(HTTPException) as exc:
        require_admin({"uid": "u", "email": "u@x.com"})
    assert exc.value.status_code == 403


def test_require_admin_firestore_error(monkeypatch):
    def failing_client():
        raise RuntimeError("db down")

    monkeypatch.setattr("app.dependencies.auth.firestore.client", failing_client)
    with pytest.raises(HTTPException) as exc:
        require_admin({"uid": "u", "email": "u@x.com"})
    assert exc.value.status_code == 500
