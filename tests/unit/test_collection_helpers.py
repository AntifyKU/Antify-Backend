"""Unit tests for helpers in app.api.collection."""

from __future__ import annotations

from app.api.collection import _get_species_details, _now_utc

from tests.conftest import species_document


def test_now_utc_timezone_aware():
    """Test that the current UTC time is timezone aware."""
    t = _now_utc()
    assert t.tzinfo is not None


def test_get_species_details_found(monkeypatch, firestore_db):
    """Test that the species details are returned for a found species."""
    monkeypatch.setattr("app.api.collection.db", firestore_db)
    sid, data = species_document(doc_id="sp", name="N", scientific_name="N. n")
    firestore_db.collection("species").document(sid).set(data)
    out = _get_species_details(sid)
    assert out["species_name"] == "N"
    assert out["species_scientific_name"] == "N. n"


def test_get_species_details_missing(monkeypatch, firestore_db):
    """Test that the species details are empty for a missing species."""
    monkeypatch.setattr("app.api.collection.db", firestore_db)
    assert not _get_species_details("missing")
