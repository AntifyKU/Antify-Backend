"""Integration: collection and folders (authenticated)."""

from __future__ import annotations

import pytest

from tests.conftest import species_document


def _species(firestore_db, sid: str = "sp-col-1"):
    doc_id, data = species_document(doc_id=sid, name="Col Ant", scientific_name="Colius colius")
    firestore_db.collection("species").document(doc_id).set(data)
    return doc_id


@pytest.mark.usefixtures("override_user_uid")
def test_collection_empty(client):
    """Test that the collection is empty."""
    r = client.get("/api/users/me/collection")
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.usefixtures("override_user_uid")
def test_add_and_list_collection(client, firestore_db):
    """Test that a species can be added to the collection and listed."""
    sp = _species(firestore_db)
    r = client.post(
        "/api/users/me/collection",
        json={
            "species_id": sp,
            "notes": "n",
            "location_found": "here",
            "folder_ids": [],
        },
    )
    assert r.status_code == 200
    item_id = r.json()["id"]
    lst = client.get("/api/users/me/collection")
    assert lst.status_code == 200
    assert lst.json()["total"] == 1
    assert lst.json()["items"][0]["species_id"] == sp

    chk = client.get(f"/api/users/me/collection/{sp}/check")
    assert chk.status_code == 200
    assert chk.json()["in_collection"] is True
    assert chk.json()["collection_id"] == item_id


@pytest.mark.usefixtures("override_user_uid")
def test_add_duplicate_species_rejected(client, firestore_db):
    """Test that a duplicate species is rejected."""
    sp = _species(firestore_db, "sp-dup")
    body = {"species_id": sp, "folder_ids": []}
    assert client.post("/api/users/me/collection", json=body).status_code == 200
    r2 = client.post("/api/users/me/collection", json=body)
    assert r2.status_code == 400


@pytest.mark.usefixtures("override_user_uid")
def test_add_unknown_species_404(client):
    """Test that an unknown species is rejected."""
    r = client.post(
        "/api/users/me/collection",
        json={"species_id": "nope", "folder_ids": []},
    )
    assert r.status_code == 404


@pytest.mark.usefixtures("override_user_uid")
def test_remove_collection_item(client, firestore_db):
    """Test that a collection item can be removed."""
    sp = _species(firestore_db, "sp-rm")
    item = client.post("/api/users/me/collection", json={"species_id": sp, "folder_ids": []}).json()
    r = client.delete(f"/api/users/me/collection/{item['id']}")
    assert r.status_code == 200


@pytest.mark.usefixtures("override_user_uid")
def test_folders_crud(client, firestore_db):
    """Test that folders can be created, duplicated, and linked to collection items."""
    sp = _species(firestore_db, "sp-f")
    f = client.post(
        "/api/users/me/folders",
        json={"name": "F1", "color": "#fff", "icon": "folder"},
    )
    assert f.status_code == 200
    fid = f.json()["id"]

    dup = client.post(
        "/api/users/me/folders",
        json={"name": "F1", "color": "#fff", "icon": "folder"},
    )
    assert dup.status_code == 400

    item = client.post("/api/users/me/collection", json={"species_id": sp, "folder_ids": []}).json()
    add = client.post(
        f"/api/users/me/collection/{item['id']}/folders",
        json={"folder_ids": [fid]},
    )
    assert add.status_code == 200

    lst = client.get("/api/users/me/folders")
    assert lst.status_code == 200
    assert lst.json()["folders"][0]["item_count"] == 1

    rm = client.delete(f"/api/users/me/collection/{item['id']}/folders/{fid}")
    assert rm.status_code == 200

    out = client.delete(f"/api/users/me/folders/{fid}")
    assert out.status_code == 200


@pytest.mark.usefixtures("override_user_uid")
def test_delete_folder_unlinks_items(client, firestore_db):
    """Test that deleting a folder unlinks items from it."""
    sp = _species(firestore_db, "sp-df")
    fid = client.post(
        "/api/users/me/folders",
        json={"name": "Tmp", "color": "#000", "icon": "folder"},
    ).json()["id"]
    item = client.post(
        "/api/users/me/collection",
        json={"species_id": sp, "folder_ids": [fid]},
    ).json()
    assert fid in item["folder_ids"]

    client.delete(f"/api/users/me/folders/{fid}", params={"delete_items": "false"})
    refreshed = client.get("/api/users/me/collection").json()["items"][0]
    assert fid not in refreshed.get("folder_ids", [])


@pytest.mark.usefixtures("override_user_uid")
def test_remove_item_from_folder_not_member(client, firestore_db):
    """Test that removing an item from a folder that it is not a member of is rejected."""
    sp = _species(firestore_db, "sp-nf")
    item = client.post("/api/users/me/collection", json={"species_id": sp, "folder_ids": []}).json()
    r = client.delete(f"/api/users/me/collection/{item['id']}/folders/ghost-folder")
    assert r.status_code == 400


@pytest.mark.usefixtures("override_user_uid")
def test_set_item_folders(client, firestore_db):
    """Test that the folders for a collection item can be set."""
    sp = _species(firestore_db, "sp-sf")
    f1 = client.post(
        "/api/users/me/folders",
        json={"name": "A", "color": "#111", "icon": "folder"},
    ).json()["id"]
    f2 = client.post(
        "/api/users/me/folders",
        json={"name": "B", "color": "#222", "icon": "folder"},
    ).json()["id"]
    item = client.post("/api/users/me/collection",
                       json={"species_id": sp, "folder_ids": [f1]}).json()
    r = client.put(
        f"/api/users/me/collection/{item['id']}/folders",
        json={"folder_ids": [f2]},
    )
    assert r.status_code == 200
    assert set(r.json()["folder_ids"]) == {f2}
