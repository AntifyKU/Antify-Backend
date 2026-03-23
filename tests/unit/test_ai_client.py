"""Unit tests for app.services.ai_client.AIServiceClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from starlette.datastructures import UploadFile

from app.services.ai_client import AIServiceClient


@pytest.mark.asyncio
async def test_health_check_success():
    client = AIServiceClient(base_url="http://ai.test")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "ok"}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as ac:
        inst = ac.return_value.__aenter__.return_value
        inst.get = AsyncMock(return_value=mock_resp)
        out = await client.health_check()
    assert out["status"] == "ok"


@pytest.mark.asyncio
async def test_health_check_request_error():
    client = AIServiceClient(base_url="http://ai.test")
    with patch("httpx.AsyncClient") as ac:
        inst = ac.return_value.__aenter__.return_value
        inst.get = AsyncMock(side_effect=httpx.RequestError("fail", request=MagicMock()))
        out = await client.health_check()
    assert out["status"] == "unavailable"


@pytest.mark.asyncio
async def test_classify_image_posts_multipart():
    client = AIServiceClient(base_url="http://ai.test")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"success": True}
    mock_resp.raise_for_status = MagicMock()

    import io

    uf = UploadFile(filename="a.jpg", file=io.BytesIO(b"bytes"), headers={"content-type": "image/jpeg"})

    with patch("httpx.AsyncClient") as ac:
        inst = ac.return_value.__aenter__.return_value
        inst.post = AsyncMock(return_value=mock_resp)
        out = await client.classify_image(uf, confidence_threshold=0.6, top_k=3)
    assert out["success"] is True
    call_kw = inst.post.call_args
    assert "/classify" in call_kw[0][0]
    assert call_kw[1]["params"] == {"confidence": 0.6, "top_k": 3}


@pytest.mark.asyncio
async def test_get_available_models_empty_on_error():
    client = AIServiceClient(base_url="http://ai.test")
    with patch("httpx.AsyncClient") as ac:
        inst = ac.return_value.__aenter__.return_value
        inst.get = AsyncMock(side_effect=httpx.RequestError("x", request=MagicMock()))
        out = await client.get_available_models()
    assert out == []
