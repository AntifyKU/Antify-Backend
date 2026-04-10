"""
Chatbot Service
Business logic for the ant-focused chatbot
"""
import json
from typing import List, Dict, Any, AsyncGenerator
import re

from firebase_admin import firestore
from app.services.openrouter import openrouter_client

db = firestore.client()
SPECIES_COLLECTION = "species"


# System prompt for the ant expert chatbot
ANT_EXPERT_SYSTEM_PROMPT = """You are AntBot,
an ant expert assistant for the Antify app (Thailand/Southeast Asia focus).

STRICT RULES:
1. ONLY answer questions about ants. For non-ant topics, politely say: "I specialize in ants only. Please ask me about ants!"
2. Keep responses SHORT (2-4 sentences max). Be concise and direct.
3. Use simple language. Avoid long explanations.
4. Include scientific names in parentheses when mentioning species.
5. IMPORTANT: You MUST answer in the exact same language as the user's prompt (e.g., if asked in Thai, answer in Thai. If asked in English, answer in English).
6. DO NOT use markdown formatting (like **bold** or *italics*). Use plain text ONLY.

Your expertise: ant identification, behavior, ecology, habitats, colonies, pest control.

Response format:
- Answer briefly and directly
- Add 1 interesting fact if relevant
- For images: describe key features → identify species → share 1 fact

Example good response:
"This is a Weaver Ant (Oecophylla smaragdina). They build nests by weaving leaves together using silk from their larvae. Common in Southeast Asian gardens."

Example bad response (too long):
"The Weaver Ant, scientifically known as Oecophylla smaragdina, is a fascinating species... [continues for 10+ sentences]"

Remember: SHORT answers only!"""


# System prompt for generating contextual suggestions
SUGGESTION_SYSTEM_PROMPT = """Based on the conversation,
generate 3 SHORT follow-up questions about the ant species or topic being discussed.

Rules:
1. Questions must be specific to the ant/topic in the conversation
2. Each question should be 5-10 words max
3. Make questions progressively more detailed
4. Return ONLY a JSON array of 3 strings, nothing else

Example output:
["Are Fire Ants dangerous to pets?",
"How to remove Fire Ant nests?", "Where do Fire Ants live in Thailand?"]"""


# Default FAQ suggestions (shown when no context)
FAQ_SUGGESTIONS = [
    "What ants are common in Thailand?",
    "How to identify Fire Ants?",
    "Are Weaver Ants dangerous?",
]


class ChatbotService:
    """Service for handling chatbot conversations"""

    def __init__(self):
        self.system_prompt = ANT_EXPERT_SYSTEM_PROMPT

    def _get_relevant_ant_context(self, query: str) -> str:
        """Fetch ant details from Firebase if query matches ant names/tags."""
        try:
            # Simple keyword extraction: words longer than 3 chars
            words = set(re.findall(r'\b\w{3,}\b', query.lower()))
            if not words:
                return ""

            species_ref = db.collection(SPECIES_COLLECTION)
            docs = species_ref.stream()

            matches = []
            for doc in docs:
                data = doc.to_dict()
                name = data.get("name", "").lower()
                scientific = data.get("scientific_name", "").lower()
                tags = [t.lower() for t in data.get("tags", [])]

                # Check for overlap
                text_to_search = name + " " + scientific + " " + " ".join(tags)
                if any(w in text_to_search for w in words):
                    matches.append(data)

                if len(matches) >= 3:
                    break

            if not matches:
                return ""

            context_parts = ["\n[Database Context about mentioned ants]:"]
            for m in matches:
                context_parts.append(
                    f"- {m.get('name')} ({m.get('scientific_name')}): "
                    f"About: {m.get('about', '')}. "
                    f"Habitat: {', '.join(m.get('habitat', []))}. "
                    f"Behavior: {m.get('behavior', '')}."
                )
            return "\n".join(context_parts)
        except (ValueError, TypeError) as e:
            print(f"Error fetching RAG context: {e}")
            return ""

    def get_relevant_ant_context(self, query: str) -> str:
        """Public wrapper for retrieving species context for a query."""
        return self._get_relevant_ant_context(query)

    async def get_response_stream(
        self,
        content: str,
        conversation_history: List[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Get streaming response from the chatbot.
        """
        # Build messages list
        messages = []

        # Add conversation history (limit to last 10 messages for context)
        if conversation_history:
            for msg in conversation_history[-10:]:
                role = "user" if msg.get("role") == "user" else "assistant"
                messages.append({
                    "role": role,
                    "content": msg.get("content", "")
                })

        # Get context from Firebase based on latest message
        rag_context = self._get_relevant_ant_context(content)
        final_system_prompt = self.system_prompt + rag_context

        # Add current user message
        messages.append({"role": "user", "content": content})

        # Stream response
        async for chunk in openrouter_client.chat_stream(
            messages=messages,
            system_prompt=final_system_prompt,
            temperature=0.7,
            max_tokens=1024,
        ):
            yield chunk

    async def get_response_with_image_stream(
        self,
        content: str,
        image_base64: str,
        mime_type: str = "image/jpeg",
    ) -> AsyncGenerator[str, None]:
        """
        Get streaming response for a message with an image.
        """
        # Add context to help with ant identification (kept short)
        enhanced_prompt = f"""User sent an image: "{content}"

Identify the ant briefly:
1. Key features (2-3 words each)
2. Species name (with scientific name)
3. One interesting fact

If not an ant image, say so briefly."""

        # Get context from Firebase based on current question
        rag_context = self._get_relevant_ant_context(content)
        final_system_prompt = self.system_prompt + rag_context

        async for chunk in openrouter_client.chat_with_image(
            text=enhanced_prompt,
            image_base64=image_base64,
            system_prompt=final_system_prompt,
            options={
                "mime_type": mime_type,
                "temperature": 0.7,
                "max_tokens": 512,
            },
        ):
            yield chunk

    async def generate_suggestions(
        self,
        conversation_history: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Generate contextual follow-up questions based on conversation.
        """
        if not conversation_history or len(conversation_history) < 2:
            return FAQ_SUGGESTIONS

        # Build context from recent messages
        recent_messages = conversation_history[-6:]  # Last 3 exchanges
        context = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in recent_messages
        ])

        try:
            # Get suggestions from LLM
            response = await openrouter_client.chat(
                messages=[{"role": "user", "content": f"Conversation:\n{context}"}],
                system_prompt=SUGGESTION_SYSTEM_PROMPT,
                temperature=0.7,
                max_tokens=150,
            )

            # Parse JSON response
            suggestions = json.loads(response.strip())
            if isinstance(suggestions, list) and len(suggestions) >= 3:
                return suggestions[:3]
        except json.JSONDecodeError as e:
            print(f"Error generating suggestions: {e}")

        return FAQ_SUGGESTIONS

    def get_faq_suggestions(self) -> List[str]:
        """Get FAQ suggestions for quick questions"""
        return FAQ_SUGGESTIONS


# Singleton instance
chatbot_service = ChatbotService()
