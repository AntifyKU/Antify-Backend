"""Unit tests for Socket.IO event handlers (mocked chatbot)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import socketio_server


@pytest.mark.asyncio
async def test_message_empty_emits_error():
    """Test that an empty message emits an error."""
    mock_sio = MagicMock()
    mock_sio.emit = AsyncMock()

    with patch.object(socketio_server, "sio", mock_sio):
        await socketio_server.message("sid-1", {"content": "   ", "conversationHistory": []})

    mock_sio.emit.assert_called()
    call = [c for c in mock_sio.emit.call_args_list if c[0][0] == "error"]
    assert call
    assert "Empty" in call[0][0][1]["message"]


@pytest.mark.asyncio
async def test_message_with_image_missing_emits_error():
    """Test that a missing image emits an error."""
    mock_sio = MagicMock()
    mock_sio.emit = AsyncMock()

    with patch.object(socketio_server, "sio", mock_sio):
        await socketio_server.message_with_image("sid-1", {"content": "x", "imageBase64": ""})

    err = [c for c in mock_sio.emit.call_args_list if c[0][0] == "error"]
    assert err


@pytest.mark.asyncio
async def test_get_suggestions_emits_faq():
    """Test that the FAQ suggestions are emitted."""
    mock_sio = MagicMock()
    mock_sio.emit = AsyncMock()

    with patch.object(socketio_server, "sio", mock_sio):
        await socketio_server.get_suggestions("sid-1")

    faq = [c for c in mock_sio.emit.call_args_list if c[0][0] == "suggestions"]
    assert faq
