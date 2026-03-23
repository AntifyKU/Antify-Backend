"""
Test harness: Firebase import guards, shared Firestore fake wiring, and factories.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

patch("firebase_admin.get_app", return_value=MagicMock()).start()
patch("firebase_admin.storage.bucket", return_value=MagicMock()).start()
patch("pyrebase.initialize_app", return_value=MagicMock()).start()
patch("firebase_admin.firestore.client", return_value=MagicMock()).start()

from fastapi.testclient import TestClient  # noqa: E402

from app.dependencies.auth import get_current_user  # noqa: E402
from app.main import app as combined_asgi_app  # noqa: E402

from tests.fake_firestore import InMemoryFirestore  # noqa: E402

# Socket.IO wraps FastAPI; overrides must target the inner application.
fastapi_app = combined_asgi_app.other_asgi_app


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def species_document(
    *,
    doc_id: str,
    name: str = "Weaver Ant",
    scientific_name: str = "Oecophylla smaragdina",
    **extra: Any,
) -> tuple[str, dict]:
    """Return (id, firestore_dict) satisfying SpeciesSchema for list/get responses."""
    now = _utcnow()
    data = {
        "name": name,
        "scientific_name": scientific_name,
        "classification": {
            "family": "Formicidae",
            "subfamily": "Formicinae",
            "genus": scientific_name.split()[0],
        },
        "tags": ["Tree-dwelling"],
        "about": "About text",
        "characteristics": "Small workers",
        "colors": ["Orange"],
        "habitat": ["Trees"],
        "distribution": ["Central"],
        "behavior": "Social",
        "ecological_role": "Predator",
        "image": "https://example.com/ant.jpg",
        "created_at": now,
        "updated_at": None,
        "distribution_v2": {"provinces": ["Bangkok"]},
    }
    data.update(extra)
    return doc_id, data


def user_document(
    *,
    uid: str,
    username: str = "alice",
    email: str = "alice@example.com",
    role: str = "user",
    **extra: Any,
) -> dict:
    return {
        "user_id": uid,
        "username": username,
        "email": email,
        "role": role,
        "profile_picture": None,
        "is_active": True,
        "created_at": _utcnow(),
        "lasted_login": None,
        "lasted_update": None,
        "preferences": {"language": "english"},
        **extra,
    }


@pytest.fixture
def firestore_db() -> InMemoryFirestore:
    return InMemoryFirestore()


@pytest.fixture
def client(monkeypatch, firestore_db: InMemoryFirestore) -> Generator[TestClient, None, None]:
    monkeypatch.setattr("app.api.user.db", firestore_db)
    monkeypatch.setattr("app.api.species.db", firestore_db)
    monkeypatch.setattr("app.api.collection.db", firestore_db)
    monkeypatch.setattr("app.api.feedback.db", firestore_db)
    monkeypatch.setattr("firebase_admin.firestore.client", lambda: firestore_db)

    fastapi_app.dependency_overrides.clear()
    with TestClient(combined_asgi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def override_user_uid(client, firestore_db: InMemoryFirestore):
    """Register current user in Firestore and override get_current_user."""
    uid = "user-1"

    def _user() -> dict:
        return {"uid": uid, "email": "user@example.com"}

    fastapi_app.dependency_overrides[get_current_user] = _user
    firestore_db.collection("users").document(uid).set(user_document(uid=uid))
    return uid


@pytest.fixture
def override_admin_uid(client, firestore_db: InMemoryFirestore):
    uid = "admin-1"
    fastapi_app.dependency_overrides[get_current_user] = lambda: {"uid": uid, "email": "admin@example.com"}
    firestore_db.collection("users").document(uid).set(user_document(uid=uid, role="admin"))
    return uid


@pytest.fixture
def fake_pyrebase_login(monkeypatch) -> MagicMock:
    fb = MagicMock()
    fb.auth.return_value.sign_in_with_email_and_password.return_value = {
        "idToken": "id-token",
        "refreshToken": "refresh-token",
        "expiresIn": "3600",
    }
    monkeypatch.setattr("app.api.user.firebase", fb)
    return fb
