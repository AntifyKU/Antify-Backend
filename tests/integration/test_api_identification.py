"""Integration: identification routes with stubbed AI client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import species_document
import app.api.identification as ident


@pytest.fixture
def stubbed_ai_client(monkeypatch):
    """Stub the AI client."""
    stub = MagicMock()

    async def classify_image(file, confidence_threshold=0.5, top_k=5):
        _ = (confidence_threshold, top_k)
        await file.read()
        await file.seek(0)
        return {
            "success": True,
            "top_prediction": "Oecophylla smaragdina",
            "top_confidence": 0.91,
            "top_predictions": [
                {
                    "rank": 1,
                    "class_name": "Oecophylla smaragdina",
                    "confidence": 0.91,
                    "species_id": "s1",
                }
            ],
            "model": "stub-model",
        }

    stub.classify_image = classify_image
    stub.classify_base64 = AsyncMock(
        return_value={
            "success": True,
            "top_prediction": "Oecophylla smaragdina",
            "top_confidence": 0.8,
            "top_predictions": [
                {"rank": 1, "class_name": "Oecophylla smaragdina", "confidence": 0.8}
            ],
            "model": "stub",
        }
    )

    async def detect_ants(file, confidence_threshold=0.25, iou_threshold=0.45):
        _ = (confidence_threshold, iou_threshold)
        await file.read()
        await file.seek(0)
        return {
            "success": True,
            "num_detections": 1,
            "detections": [
                {
                    "class_id": 0,
                    "class_name": "ant",
                    "confidence": 0.9,
                    "bbox": [0.1, 0.2, 0.3, 0.4],
                }
            ],
            "image_size": [640, 480],
        }

    stub.detect_ants = detect_ants
    stub.health_check = AsyncMock(return_value={"status": "healthy"})
    stub.get_available_models = AsyncMock(return_value=[{"id": "m1", "name": "stub"}])
    monkeypatch.setattr(ident, "ai_client", stub)
    return stub


@pytest.mark.usefixtures("stubbed_ai_client")
def test_identify_health(client):
    """Test that the identify health endpoint is available."""
    r = client.get("/api/identify/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


@pytest.mark.usefixtures("stubbed_ai_client")
def test_identify_models(client):
    """Test that the identify models endpoint is available."""
    r = client.get("/api/identify/models")
    assert r.status_code == 200
    assert r.json()["models"]


@pytest.mark.usefixtures("stubbed_ai_client")
def test_identify_multipart(client):
    """Test that the identify multipart endpoint is available."""
    files = {"file": ("a.jpg", b"\xff\xd8\xff", "image/jpeg")}
    r = client.post("/api/identify", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["top_prediction"] == "Oecophylla smaragdina"


@pytest.mark.usefixtures("stubbed_ai_client")
def test_identify_rejects_non_image(client):
    """Test that a non-image file is rejected."""
    files = {"file": ("x.txt", b"hi", "text/plain")}
    r = client.post("/api/identify", files=files)
    assert r.status_code == 400


@pytest.mark.usefixtures("stubbed_ai_client")
def test_identify_base64(client):
    """Test that the identify base64 endpoint is available."""
    r = client.post(
        "/api/identify/base64",
        json={
            "image_base64": "ZmFrZQ==",  # "fake" in base64 — stub never decodes meaningfully
            "mime_type": "image/jpeg",
            "confidence_threshold": 0.5,
            "top_k": 5,
        },
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


@pytest.mark.usefixtures("stubbed_ai_client")
def test_detect(client):
    """Test that the identify detect endpoint is available."""
    files = {"file": ("a.jpg", b"\xff\xd8\xff", "image/jpeg")}
    r = client.post("/api/identify/detect", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["num_detections"] >= 1


@pytest.mark.usefixtures("stubbed_ai_client")
def test_identify_species_details(client, firestore_db, monkeypatch):
    """Test that the identify species details endpoint is available."""
    sid, data = species_document(
        doc_id="s-weaver",
        name="Weaver",
        scientific_name="Oecophylla smaragdina",
    )
    firestore_db.collection("species").document(sid).set(data)
    monkeypatch.setattr(
        "app.api.identification.cloudinary.uploader.upload",
        lambda *a, **k: {"secure_url": "https://res.cloudinary.com/demo/upload/v1/x.jpg"},
    )
    files = {"file": ("a.jpg", b"\xff\xd8\xff", "image/jpeg")}
    r = client.post("/api/identify/species/details", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["species_info"] is not None
    assert body["species_info"]["id"] == sid
    assert body.get("image_url")


def test_identify_species_details_rejected_when_ai_fails(client, monkeypatch):
    """Test that the identify species details endpoint is rejected when AI fails."""

    async def reject(*_args, **_kwargs):
        return {"success": False, "message": "Not an ant"}

    stub = MagicMock()
    stub.classify_image = reject
    monkeypatch.setattr(ident, "ai_client", stub)
    files = {"file": ("a.jpg", b"\xff\xd8\xff", "image/jpeg")}
    r = client.post("/api/identify/species/details", files=files)
    assert r.status_code == 200
    assert r.json()["success"] is False
