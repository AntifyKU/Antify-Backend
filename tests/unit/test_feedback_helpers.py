"""Unit tests for helpers in app.api.feedback."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.api.feedback import _get_or_404, _now_utc, _strip_base64, _stream_collection


def test_now_utc_timezone_aware():
    """Test that the current UTC time is timezone aware."""
    t = _now_utc()
    assert t.tzinfo is not None


def test_strip_base64_marks_has_image():
    """Test that the base64 image is marked as having an image."""
    items = [{"id": "1", "image_base64": "AAAA"}, {"id": "2"}]
    out = _strip_base64(items)
    assert out[0]["has_image"] is True
    assert "image_base64" not in out[0]
    assert "has_image" not in out[1]


def test_get_or_404_found(monkeypatch, firestore_db):
    """Test that the feedback is returned for a found feedback."""
    monkeypatch.setattr("app.api.feedback.db", firestore_db)
    firestore_db.collection("feedback").document("f1").set({"id": "f1", "message": "x"})
    out = _get_or_404("feedback", "f1", "Feedback")
    assert out["id"] == "f1"


def test_get_or_404_missing(monkeypatch, firestore_db):
    """Test that a missing feedback is rejected."""
    monkeypatch.setattr("app.api.feedback.db", firestore_db)
    with pytest.raises(HTTPException) as exc:
        _get_or_404("feedback", "missing", "Feedback")
    assert exc.value.status_code == 404


def test_stream_collection_desc_and_filter(monkeypatch, firestore_db):
    """Test that the feedback is streamed in descending order and filtered by status."""
    monkeypatch.setattr("app.api.feedback.db", firestore_db)
    firestore_db.collection("feedback").document("a").set(
        {"id": "a", "status": "pending", "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc)}
    )
    firestore_db.collection("feedback").document("b").set(
        {"id": "b", "status": "reviewed", "created_at": datetime(2024, 1, 2, tzinfo=timezone.utc)}
    )
    firestore_db.collection("feedback").document("c").set(
        {"id": "c", "status": "pending", "created_at": datetime(2024, 1, 3, tzinfo=timezone.utc)}
    )
    out = _stream_collection("feedback", filters=[("status", "pending")], limit=10)
    assert [x["id"] for x in out] == ["c", "a"]
