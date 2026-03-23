"""Integration: identification routes with stubbed AI client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import species_document


@pytest.fixture
def stub_ai_client(monkeypatch):
    import app.api.identification as ident

    stub = MagicMock()

    async def classify_image(file, confidence_threshold=0.5, top_k=5):
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


def test_identify_health(client, stub_ai_client):
    r = client.get("/api/identify/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_identify_models(client, stub_ai_client):
    r = client.get("/api/identify/models")
    assert r.status_code == 200
    assert r.json()["models"]


def test_identify_multipart(client, stub_ai_client):
    files = {"file": ("a.jpg", b"\xff\xd8\xff", "image/jpeg")}
    r = client.post("/api/identify", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["top_prediction"] == "Oecophylla smaragdina"


def test_identify_rejects_non_image(client, stub_ai_client):
    files = {"file": ("x.txt", b"hi", "text/plain")}
    r = client.post("/api/identify", files=files)
    assert r.status_code == 400


def test_identify_base64(client, stub_ai_client):
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


def test_detect(client, stub_ai_client):
    files = {"file": ("a.jpg", b"\xff\xd8\xff", "image/jpeg")}
    r = client.post("/api/identify/detect", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["num_detections"] >= 1


def test_identify_species_details(client, stub_ai_client, firestore_db, monkeypatch):
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


def test_identify_species_details_rejected_when_ai_fails(client, monkeypatch, firestore_db):
    import app.api.identification as ident

    async def reject(*a, **kw):
        return {"success": False, "message": "Not an ant"}

    stub = MagicMock()
    stub.classify_image = reject
    monkeypatch.setattr(ident, "ai_client", stub)
    files = {"file": ("a.jpg", b"\xff\xd8\xff", "image/jpeg")}
    r = client.post("/api/identify/species/details", files=files)
    assert r.status_code == 200
    assert r.json()["success"] is False
