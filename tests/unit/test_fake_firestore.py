"""Unit tests for tests.fake_firestore (query + ArrayRemove)."""

from __future__ import annotations

from google.cloud.firestore import ArrayRemove
from google.cloud.firestore import Query as FirestoreQuery

from tests.fake_firestore import InMemoryFirestore


def test_array_remove_update():
    """Test that the ArrayRemove update works."""
    db = InMemoryFirestore()
    ref = db.collection("users").document("u1")
    ref.set({"folder_ids": ["a", "b", "a"]})
    ref.update({"folder_ids": ArrayRemove(["a"])})
    assert ref.get().to_dict()["folder_ids"] == ["b"]


def test_where_limit_get():
    """Test that the where limit get works."""
    db = InMemoryFirestore()
    db.collection("users").document("1").set({"username": "bob", "email": "b@e.com"})
    db.collection("users").document("2").set({"username": "ann", "email": "a@e.com"})
    q = db.collection("users").where("username", "==", "bob").limit(1).get()
    assert len(q) == 1
    assert q[0].id == "1"


def test_order_by_descending():
    """Test that the order by descending works."""
    db = InMemoryFirestore()
    db.collection("items").document("a").set({"added_at": 1})
    db.collection("items").document("b").set({"added_at": 3})
    db.collection("items").document("c").set({"added_at": 2})
    snaps = list(
        db.collection("items")
        .order_by("added_at", direction=FirestoreQuery.DESCENDING)
        .stream()
    )
    assert [s.id for s in snaps] == ["b", "c", "a"]
