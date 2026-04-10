"""Integration: species list/get and admin CRUD."""

from __future__ import annotations

import pytest
from app.dependencies.auth import get_current_user

from tests.conftest import fastapi_app, species_document, user_document


def _seed_two_species(firestore_db):
    """Seed the firestore database with two species."""
    sid1, d1 = species_document(doc_id="s1", name="Weaver Ant",
                                scientific_name="Oecophylla smaragdina")
    sid2, d2 = species_document(doc_id="s2", name="Fire Ant", scientific_name="Solenopsis geminata")
    d2["tags"] = ["stinging"]
    d2["colors"] = ["Red"]
    d2["habitat"] = ["Lawn"]
    d2["distribution"] = ["South"]
    d2["distribution_v2"] = {"provinces": ["Chiang Mai"]}
    firestore_db.collection("species").document(sid1).set(d1)
    firestore_db.collection("species").document(sid2).set(d2)


def test_list_species_empty(client):
    """Test that the species list is empty."""
    r = client.get("/api/species")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["species"] == []


def test_list_species_search_and_filters(client, firestore_db):
    """Test that the species list can be searched and filtered."""
    _seed_two_species(firestore_db)
    r = client.get("/api/species", params={"search": "fire"})
    assert r.status_code == 200
    assert r.json()["total"] == 1

    r2 = client.get("/api/species", params={"tags": "stinging"})
    assert r2.json()["total"] == 1

    r3 = client.get("/api/species", params={"colors": "red"})
    assert r3.json()["total"] == 1

    r4 = client.get("/api/species", params={"habitat": "lawn"})
    assert r4.json()["total"] == 1

    r5 = client.get("/api/species", params={"distribution": "south"})
    assert r5.json()["total"] == 1

    r6 = client.get("/api/species", params={"province": "bangkok"})
    assert r6.json()["total"] == 1


def test_list_species_pagination(client, firestore_db):
    """Test that the species list can be paginated."""
    sid, data = species_document(doc_id="sp1", name="A", scientific_name="A. a")
    firestore_db.collection("species").document(sid).set(data)
    r = client.get("/api/species", params={"page": 1, "limit": 1})
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert len(r.json()["species"]) == 1


def test_get_species(client, firestore_db):
    """Test that a species can be retrieved."""
    sid, data = species_document(doc_id="sx", name="X", scientific_name="X. x")
    firestore_db.collection("species").document(sid).set(data)
    r = client.get(f"/api/species/{sid}")
    assert r.status_code == 200
    assert r.json()["id"] == sid


def test_get_species_not_found(client):
    """Test that a non-existent species is rejected."""
    r = client.get("/api/species/missing")
    assert r.status_code == 404


@pytest.mark.usefixtures("override_admin_uid")
def test_admin_create_species(client):
    """Test that a species can be created."""
    payload = {
        "name": "Test Ant",
        "scientific_name": "Testus antus",
        "classification": {"subfamily": "Myrmicinae", "genus": "Testus"},
        "tags": [],
        "about": "About",
        "characteristics": "Chars",
        "colors": [],
        "habitat": [],
        "distribution": [],
        "behavior": "Behaves",
        "ecological_role": "Role",
        "image": "https://example.com/i.jpg",
    }
    r = client.post("/api/species", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Test Ant"
    assert "id" in body


@pytest.mark.usefixtures("override_admin_uid")
def test_admin_update_species(client, firestore_db):
    """Test that a species can be updated."""
    sid, data = species_document(doc_id="su", name="Old", scientific_name="Oldius oldius")
    firestore_db.collection("species").document(sid).set(data)
    r = client.put(f"/api/species/{sid}", json={"name": "New"})
    assert r.status_code == 200
    assert r.json()["name"] == "New"


@pytest.mark.usefixtures("override_admin_uid")
def test_admin_update_species_allows_extended_fields(client, firestore_db):
    """Test that a species can be updated with extended fields."""
    sid, data = species_document(doc_id="su2", name="Old2", scientific_name="Oldius secondus")
    firestore_db.collection("species").document(sid).set(data)
    payload = {
        "distribution_v2": {"provinces": ["Bangkok"]},
        "accepted_taxon": {"scientific_name": "Oldius secondus", "rank": "species"},
        "risk": {"medical_importance": "low"},
    }
    r = client.put(f"/api/species/{sid}", json=payload)
    assert r.status_code == 200
    assert r.json()["distribution_v2"]["provinces"] == ["Bangkok"]
    assert r.json()["accepted_taxon"]["rank"] == "species"
    assert r.json()["risk"]["medical_importance"] == "low"


@pytest.mark.usefixtures("override_admin_uid")
def test_admin_delete_species(client, firestore_db):
    """Test that a species can be deleted."""
    sid, data = species_document(doc_id="sd", name="D", scientific_name="D. d")
    firestore_db.collection("species").document(sid).set(data)
    r = client.delete(f"/api/species/{sid}")
    assert r.status_code == 200
    assert not firestore_db.collection("species").document(sid).get().exists


def test_non_admin_cannot_create_species(client, firestore_db):
    """Test that a non-admin cannot create a species."""
    firestore_db.collection("users").document("u").set(
        user_document(uid="u", username="u", email="u@e.com", role="user"))
    fastapi_app.dependency_overrides[get_current_user] = lambda: {"uid": "u", "email": "u@e.com"}
    try:
        r = client.post(
            "/api/species",
            json={
                "name": "N",
                "scientific_name": "N. n",
                "classification": {"subfamily": "F", "genus": "N"},
                "about": "a",
                "characteristics": "c",
                "behavior": "b",
                "ecological_role": "r",
                "image": "https://x.com/i.jpg",
            },
        )
        assert r.status_code == 403
    finally:
        fastapi_app.dependency_overrides.clear()
