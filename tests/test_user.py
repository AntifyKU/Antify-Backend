"""Tests for user models and authentication utilities."""
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.user import (
    ChangeEmailSchema,
    ChangePasswordSchema,
    LoginSchema,
    SignUpSchema,
    UpdateProfileSchema,
    UserSchema,
)
from app.dependencies.auth import require_admin, _verify_firebase_token, get_current_user

# Allow imports without Firebase init
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MOCK_CREDENTIAL = "pass123"
MOCK_NEW_CREDENTIAL = "strongpass456"


class TestSignUpSchema:
    """Tests for SignUpSchema."""

    def test_valid_signup(self):
        """Should create valid SignUpSchema."""
        user = SignUpSchema(
            username="alice",
            email="alice@example.com",
            password=MOCK_CREDENTIAL,
        )
        assert user.username == "alice"
        assert user.email == "alice@example.com"

    def test_invalid_email(self):
        """Should raise error for invalid email."""
        with pytest.raises(ValidationError):
            SignUpSchema(
                username="alice",
                email="invalid-email",
                password=MOCK_CREDENTIAL,
            )

    def test_missing_field(self):
        """Should raise error when required field is missing."""
        with pytest.raises(ValidationError):
            SignUpSchema(email="alice@example.com", password=MOCK_CREDENTIAL)


class TestLoginSchema:
    """Tests for LoginSchema."""

    def test_valid_login(self):
        """Should create valid LoginSchema."""
        schema = LoginSchema(
            email="alice@example.com",
            password=MOCK_CREDENTIAL,
        )
        assert schema.email == "alice@example.com"

    def test_missing_password(self):
        """Should raise error when password is missing."""
        with pytest.raises(ValidationError):
            LoginSchema(email="alice@example.com")


class TestUserSchema:
    """Tests for UserSchema."""

    BASE_DATA = {
        "user_id": "uid-001",
        "username": "alice",
        "email": "alice@example.com",
        "created_at": datetime(2026, 1, 1),
    }

    def test_default_values(self):
        """Should set default values correctly."""
        user = UserSchema(**self.BASE_DATA)
        assert user.role == "user"
        assert user.is_active is True
        assert user.profile_picture is None
        assert user.preferences == {"language": "english"}

    def test_custom_role(self):
        """Should allow custom role."""
        user = UserSchema(**{**self.BASE_DATA, "role": "admin"})
        assert user.role == "admin"

    def test_optional_fields(self):
        """Should accept optional fields."""
        user = UserSchema(
            **{
                **self.BASE_DATA,
                "lasted_login": datetime(2026, 2, 1),
                "lasted_update": datetime(2026, 2, 2),
                "profile_picture": "https://example.com/pic.jpg",
            }
        )
        assert user.lasted_login is not None
        assert user.profile_picture is not None

    def test_invalid_email(self):
        """Should raise error for invalid email."""
        with pytest.raises(ValidationError):
            UserSchema(**{**self.BASE_DATA, "email": "bad-email"})


class TestUpdateProfileSchema:
    """Tests for UpdateProfileSchema."""

    def test_all_none(self):
        """Should allow all fields to be None."""
        schema = UpdateProfileSchema()
        assert schema.username is None
        assert schema.profile_picture is None
        assert schema.preferences is None

    def test_partial_update(self):
        """Should allow partial update."""
        schema = UpdateProfileSchema(username="bob")
        assert schema.username == "bob"

    def test_with_preferences(self):
        """Should update preferences."""
        schema = UpdateProfileSchema(preferences={"language": "thai"})
        assert schema.preferences is not None
        assert schema.preferences.get("language") == "thai"


class TestChangeEmailSchema:
    """Tests for ChangeEmailSchema."""

    def test_valid_email(self):
        """Should accept valid email."""
        schema = ChangeEmailSchema(new_email="new@example.com")
        assert str(schema.new_email) == "new@example.com"

    def test_invalid_email(self):
        """Should reject invalid email."""
        with pytest.raises(ValidationError):
            ChangeEmailSchema(new_email="invalid-email")


class TestChangePasswordSchema:
    """Tests for ChangePasswordSchema."""

    def test_valid_password(self):
        """Should accept valid password."""
        schema = ChangePasswordSchema(new_password=MOCK_NEW_CREDENTIAL)
        assert schema.new_password == MOCK_NEW_CREDENTIAL

    def test_missing_password(self):
        """Should raise error if password missing."""
        with pytest.raises(ValidationError):
            ChangePasswordSchema()


class TestVerifyFirebaseToken:
    """Tests for _verify_firebase_token function."""

    def _import(self):
        """Import target function."""
        return _verify_firebase_token

    @patch("app.dependencies.auth.auth")
    def test_valid_token(self, mock_auth):
        """Should return decoded token for valid input."""
        mock_auth.verify_id_token.return_value = {"uid": "user-1"}
        result = self._import()("valid-token")
        assert result["uid"] == "user-1"

    @patch("app.dependencies.auth.auth")
    def test_expired_token(self, mock_auth):
        """Should raise 401 for expired token."""
        fb_auth = sys.modules["firebase_admin.auth"]
        mock_auth.ExpiredIdTokenError = fb_auth.ExpiredIdTokenError
        mock_auth.verify_id_token.side_effect = fb_auth.ExpiredIdTokenError(
            "expired", None, None
        )

        with pytest.raises(HTTPException) as exc:
            self._import()("expired-token")

        assert exc.value.status_code == 401

    @patch("app.dependencies.auth.auth")
    def test_invalid_token(self, mock_auth):
        """Should raise 401 for invalid token."""
        fb_auth = sys.modules["firebase_admin.auth"]
        mock_auth.InvalidIdTokenError = fb_auth.InvalidIdTokenError
        mock_auth.verify_id_token.side_effect = fb_auth.InvalidIdTokenError("invalid")

        with pytest.raises(HTTPException):
            self._import()("bad-token")


class TestGetCurrentUser:
    """Tests for get_current_user."""

    @patch("app.dependencies.auth._verify_firebase_token")
    def test_valid_bearer(self, mock_verify):
        """Should extract token and verify."""
        mock_verify.return_value = {"uid": "user-1"}
        result = get_current_user(authorization="Bearer valid-token")
        assert result["uid"] == "user-1"

    def test_invalid_header(self):
        """Should raise error for invalid header."""
        with pytest.raises(HTTPException):
            get_current_user(authorization="invalid-header")


class TestRequireAdmin:
    """Tests for require_admin."""

    @patch("app.dependencies.auth.firestore")
    def test_admin_pass(self, mock_firestore):
        """Admin user should pass."""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"role": "admin"}

        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )
        mock_firestore.client.return_value = mock_db
        result = require_admin(current_user={"uid": "admin-uid"})
        assert result["uid"] == "admin-uid"

    @patch("app.dependencies.auth.firestore")
    def test_non_admin(self, mock_firestore):
        """Non-admin should raise 403."""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"role": "user"}

        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )
        mock_firestore.client.return_value = mock_db

        with pytest.raises(HTTPException) as exc:
            require_admin(current_user={"uid": "user-uid"})

        assert exc.value.status_code == 403
