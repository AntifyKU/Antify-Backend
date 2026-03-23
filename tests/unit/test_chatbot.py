"""Unit tests for app.services.chatbot.ChatbotService."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.chatbot import ChatbotService, FAQ_SUGGESTIONS


def test_get_faq_suggestions():
    svc = ChatbotService()
    assert svc.get_faq_suggestions() == FAQ_SUGGESTIONS


def test_get_relevant_ant_context_empty_query():
    svc = ChatbotService()
    assert svc._get_relevant_ant_context("a b") == ""


def test_get_relevant_ant_context_matches_species(monkeypatch, firestore_db):
    from tests.conftest import species_document

    monkeypatch.setattr("app.services.chatbot.db", firestore_db)
    sid, data = species_document(doc_id="s1", name="Weaver Ant", scientific_name="Oecophylla smaragdina")
    firestore_db.collection("species").document(sid).set(data)
    svc = ChatbotService()
    ctx = svc._get_relevant_ant_context("Tell me about weaver ants")
    assert "Weaver" in ctx
    assert "Oecophylla" in ctx


@pytest.mark.asyncio
async def test_generate_suggestions_short_history():
    svc = ChatbotService()
    out = await svc.generate_suggestions([{"role": "user", "content": "hi"}])
    assert out == FAQ_SUGGESTIONS


@pytest.mark.asyncio
async def test_generate_suggestions_parses_json():
    with patch("app.services.chatbot.openrouter_client.chat", new_callable=AsyncMock) as chat:
        chat.return_value = '["Q1?", "Q2?", "Q3?"]'
        hist = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "c"},
        ]
        out = await ChatbotService().generate_suggestions(hist)
    assert out == ["Q1?", "Q2?", "Q3?"]


@pytest.mark.asyncio
async def test_generate_suggestions_invalid_json_fallback(monkeypatch):
    with patch("app.services.chatbot.openrouter_client.chat", new_callable=AsyncMock) as chat:
        chat.return_value = "not json"
        hist = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
        out = await ChatbotService().generate_suggestions(hist)
    assert out == FAQ_SUGGESTIONS
