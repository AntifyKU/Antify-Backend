"""Integration: root, health, OpenAPI (HTTP through ASGI stack)."""

from __future__ import annotations


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert "Antify" in body.get("message", "")
    assert body.get("docs") == "/docs"


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


def test_openapi_docs_available(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec.get("info", {}).get("title") == "Antify API"
