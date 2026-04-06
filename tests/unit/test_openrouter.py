"""Unit tests for app.services.openrouter.OpenRouterClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.openrouter import OpenRouterClient


@pytest.mark.asyncio
async def test_chat_stream_yields_chunks():
    """Test that the chat stream yields chunks."""
    chunk = MagicMock()
    chunk.choices = [MagicMock(delta=MagicMock(content="Hi"))]

    async def fake_stream():
        yield chunk

    with patch("app.services.openrouter.AsyncOpenAI") as ctor:
        inst = ctor.return_value
        inst.chat.completions.create = AsyncMock(return_value=fake_stream())
        client = OpenRouterClient(api_key="k", model="m", base_url="http://x")
        parts = []
        async for p in client.chat_stream([{"role": "user", "content": "hello"}]):
            parts.append(p)
    assert parts == ["Hi"]


@pytest.mark.asyncio
async def test_chat_returns_string():
    """Test that the chat returns a string."""
    msg = MagicMock()
    msg.content = "Done"
    choice = MagicMock(message=msg)
    resp = MagicMock(choices=[choice])

    with patch("app.services.openrouter.AsyncOpenAI") as ctor:
        inst = ctor.return_value
        inst.chat.completions.create = AsyncMock(return_value=resp)
        client = OpenRouterClient(api_key="k", model="m", base_url="http://x")
        out = await client.chat([{"role": "user", "content": "q"}])
    assert out == "Done"


@pytest.mark.asyncio
async def test_chat_stream_oserror_yields_error_message():
    """Test that the chat stream yields an error message on OS error."""
    with patch("app.services.openrouter.AsyncOpenAI") as ctor:
        inst = ctor.return_value
        inst.chat.completions.create = AsyncMock(side_effect=OSError("net"))
        client = OpenRouterClient(api_key="k", model="m", base_url="http://x")
        chunks = [c async for c in client.chat_stream([])]
    assert any("Error" in c for c in chunks)
