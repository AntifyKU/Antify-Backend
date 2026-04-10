"""Unit tests for helpers in app.api.identification."""

from __future__ import annotations
import io
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.api.identification import (
    _ai_rejected,
    _build_predictions,
    _normalise_timestamps,
    _require_image,
    _to_classification_response,
)


def test_build_predictions_top_predictions():
    """Test that the predictions are built from top predictions."""
    raw = {
        "top_predictions": [
            {"rank": 1, "class_name": "A. a", "confidence": 0.9, "species_id": "s1"},
        ]
    }
    preds = _build_predictions(raw)
    assert len(preds) == 1
    assert preds[0].class_name == "A. a"
    assert preds[0].species_id == "s1"


def test_build_predictions_legacy_top5():
    """Test that the predictions are built from legacy top5 predictions."""
    raw = {
        "top5_predictions": [
            {"species": "B. b", "confidence": 0.5},
        ]
    }
    preds = _build_predictions(raw)
    assert preds[0].class_name == "B. b"


def test_normalise_timestamps():
    """Test that the timestamps are normalised."""

    dt = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    species = {"created_at": dt, "updated_at": dt, "name": "x"}
    out = _normalise_timestamps(species)
    assert out["created_at"].startswith("2024-01-02")
    assert out["name"] == "x"


def test_ai_rejected():
    """Test that the AI rejected response is built."""
    out = _ai_rejected({"message": "custom"})
    assert out["success"] is False
    assert out["message"] == "custom"
    assert not out["predictions"]


def test_to_classification_response():
    """Test that the classification response is built."""
    raw = {
        "top_prediction": "Top",
        "top_confidence": 0.88,
        "top_predictions": [{"class_name": "Top", "confidence": 0.88}],
        "model": "m",
    }
    resp = _to_classification_response(raw)
    assert resp.success is True
    assert resp.top_prediction == "Top"
    assert resp.model_used == "m"


def test_require_image_accepts_image():
    """Test that a image file is accepted."""
    uf = UploadFile(
        filename="a.jpg",
        file=io.BytesIO(b"x"),
        headers={"content-type": "image/jpeg"},
    )
    _require_image(uf)


def test_require_image_rejects_non_image():
    """Test that a non-image file is rejected."""
    uf = UploadFile(
        filename="a.txt",
        file=io.BytesIO(b"x"),
        headers={"content-type": "text/plain"},
    )
    with pytest.raises(HTTPException) as exc:
        _require_image(uf)
    assert exc.value.status_code == 400
