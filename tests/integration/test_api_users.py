"""Integration: user routes with mocked Firebase Auth / Pyrebase / Cloudinary."""

from __future__ import annotations

from types import SimpleNamespace
import requests
from firebase_admin import auth as firebase_auth

from app.dependencies.auth import get_current_user

from tests.conftest import fastapi_app, user_document


def test_signup_creates_user(client, firestore_db, monkeypatch):
    monkeypatch.setattr(
        "app.api.user.auth.create_user",
        lambda **kw: SimpleNamespace(uid="new-user-uid"),
    )
    monkeypatch.setattr("app.api.user.auth.delete_user", lambda uid: None)

    r = client.post(
        "/api/auth/signup",
        json={
            "username": "newbie",
            "email": "newbie@example.com",
            "password": "secret12345",
        },
    )
    assert r.status_code == 201
    doc = firestore_db.collection("users").document("new-user-uid").get()
    assert doc.exists
    assert doc.to_dict()["username"] == "newbie"


def test_signup_duplicate_username(client, firestore_db, monkeypatch):
    firestore_db.collection("users").document("u1").set(
        user_document(uid="u1", username="taken", email="a@example.com")
    )

    monkeypatch.setattr(
        "app.api.user.auth.create_user",
        lambda **kw: SimpleNamespace(uid="x"),
    )
    r = client.post(
        "/api/auth/signup",
        json={"username": "taken", "email": "other@example.com", "password": "x" * 12},
    )
    assert r.status_code == 400
    assert "Username" in r.json()["detail"]


def test_signup_email_already_exists(client, firestore_db, monkeypatch):
    def boom(**kw):
        raise firebase_auth.EmailAlreadyExistsError("x", None, None)

    monkeypatch.setattr("app.api.user.auth.create_user", boom)
    r = client.post(
        "/api/auth/signup",
        json={"username": "u2", "email": "dup@example.com", "password": "x" * 12},
    )
    assert r.status_code == 400
    assert "Email" in r.json()["detail"]


def test_login_with_email(client, firestore_db, fake_pyrebase_login, monkeypatch):
    firestore_db.collection("users").document("uid-1").set(
        user_document(uid="uid-1", username="bob", email="bob@example.com")
    )
    monkeypatch.setattr(
        "app.api.user.auth.get_user_by_email",
        lambda email: SimpleNamespace(uid="uid-1"),
    )

    r = client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "pw"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == "uid-1"
    assert "id_token" in data


def test_login_with_username_resolves_email(client, firestore_db, fake_pyrebase_login, monkeypatch):
    firestore_db.collection("users").document("uid-2").set(
        user_document(uid="uid-2", username="carol", email="carol@example.com")
    )
    monkeypatch.setattr(
        "app.api.user.auth.get_user_by_email",
        lambda email: SimpleNamespace(uid="uid-2"),
    )

    r = client.post(
        "/api/auth/login",
        json={"email": "carol", "password": "pw"},
    )
    assert r.status_code == 200


def test_login_unknown_username(client, firestore_db, fake_pyrebase_login):
    r = client.post(
        "/api/auth/login",
        json={"email": "nobody", "password": "pw"},
    )
    assert r.status_code == 400


def test_login_bad_password(client, firestore_db, fake_pyrebase_login):
    firestore_db.collection("users").document("uid-3").set(
        user_document(uid="uid-3", username="dave", email="dave@example.com")
    )

    def bad_sign_in(email, pw):
        raise requests.HTTPError()

    fake_pyrebase_login.auth.return_value.sign_in_with_email_and_password.side_effect = bad_sign_in

    r = client.post(
        "/api/auth/login",
        json={"email": "dave@example.com", "password": "wrong"},
    )
    assert r.status_code == 400


def test_get_me(client, override_user_uid):
    r = client.get("/api/users/me")
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_get_me_not_found(client, firestore_db):
    fastapi_app.dependency_overrides[get_current_user] = lambda: {"uid": "ghost", "email": "g@x.com"}
    try:
        r = client.get("/api/users/me")
        assert r.status_code == 404
    finally:
        fastapi_app.dependency_overrides.clear()


def test_update_profile_no_op(client, override_user_uid):
    r = client.put("/api/users/me/profile", json={})
    assert r.status_code == 200
    assert "No changes" in r.json()["message"]


def test_update_profile_username_conflict(client, override_user_uid, firestore_db):
    firestore_db.collection("users").document("other").set(
        user_document(uid="other", username="takenname", email="o@example.com")
    )
    r = client.put("/api/users/me/profile", json={"username": "takenname"})
    assert r.status_code == 400


def test_change_email(client, override_user_uid, firestore_db, monkeypatch):
    monkeypatch.setattr("app.api.user.auth.update_user", lambda uid, **kw: None)
    r = client.put("/api/users/me/email", json={"new_email": "newmail@example.com"})
    assert r.status_code == 200
    doc = firestore_db.collection("users").document("user-1").get()
    assert doc.to_dict()["email"] == "newmail@example.com"


def test_change_password(client, override_user_uid, monkeypatch):
    monkeypatch.setattr("app.api.user.auth.update_user", lambda uid, **kw: None)
    r = client.put("/api/users/me/password", json={"new_password": "newpw123456"})
    assert r.status_code == 200


def test_logout(client, override_user_uid, monkeypatch):
    monkeypatch.setattr("app.api.user.auth.revoke_refresh_tokens", lambda uid: None)
    r = client.post("/api/auth/logout")
    assert r.status_code == 200


def test_delete_account(client, override_user_uid, firestore_db, monkeypatch):
    monkeypatch.setattr("app.api.user.auth.delete_user", lambda uid: None)
    r = client.delete("/api/users/me")
    assert r.status_code == 200
    assert not firestore_db.collection("users").document("user-1").get().exists


def test_upload_profile_picture(client, override_user_uid, monkeypatch):
    monkeypatch.setattr(
        "app.api.user.cloudinary.uploader.upload",
        lambda *a, **k: {"secure_url": "https://res.cloudinary.com/x/image/upload/v1/a.jpg"},
    )
    files = {"file": ("a.jpg", b"\xff\xd8\xff", "image/jpeg")}
    r = client.post("/api/users/me/profile-picture", files=files)
    assert r.status_code == 200
    assert "cloudinary.com" in r.json()["profile_picture_url"]


def test_upload_profile_picture_rejects_non_image(client, override_user_uid):
    files = {"file": ("x.txt", b"hello", "text/plain")}
    r = client.post("/api/users/me/profile-picture", files=files)
    assert r.status_code == 400


def test_upload_profile_picture_rejects_large_file(client, override_user_uid):
    files = {"file": ("big.jpg", b"x" * (5 * 1024 * 1024 + 1), "image/jpeg")}
    r = client.post("/api/users/me/profile-picture", files=files)
    assert r.status_code == 400


def test_push_token_roundtrip(client, override_user_uid, firestore_db):
    r = client.post(
        "/api/users/me/push-token",
        json={"push_token": "tok", "platform": "ios", "device_id": "d1"},
    )
    assert r.status_code == 200
    g = client.get("/api/users/me/push-token")
    assert g.status_code == 200
    assert g.json()["push_token"] == "tok"
    d = client.delete("/api/users/me/push-token")
    assert d.status_code == 200


def test_admin_list_users(client, override_admin_uid):
    r = client.get("/api/users")
    assert r.status_code == 200
    assert "users" in r.json()


def test_non_admin_cannot_list_users(client, firestore_db):
    firestore_db.collection("users").document("plain").set(user_document(uid="plain", role="user"))
    fastapi_app.dependency_overrides[get_current_user] = lambda: {"uid": "plain", "email": "p@x.com"}
    try:
        r = client.get("/api/users")
        assert r.status_code == 403
    finally:
        fastapi_app.dependency_overrides.clear()

