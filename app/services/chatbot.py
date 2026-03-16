"""
Chatbot Service
Business logic for the ant-focused chatbot
"""
import json
from typing import List, Dict, Any, AsyncGenerator

from app.services.openrouter import openrouter_client


# System prompt for the ant expert chatbot
ANT_EXPERT_SYSTEM_PROMPT = """
You are AntBot, an ant expert assistant for the Antify app (Thailand/Southeast Asia focus).

STRICT RULES:
1. ONLY answer questions about ants. For non-ant topics, politely say: "I specialize in ants only. Please ask me about ants!"
2. Keep responses SHORT (2-4 sentences max). Be concise and direct.
3. Use simple language. Avoid long explanations.
4. Include scientific names in parentheses when mentioning species.

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
SUGGESTION_SYSTEM_PROMPT = """
Based on the conversation, generate 3 SHORT follow-up questions about the ant species or topic being discussed.

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

    async def get_response_stream(
        self,
        content: str,
        conversation_history: List[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """Get streaming response from the chatbot"""
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

        # Add current user message
        messages.append({"role": "user", "content": content})

        # Stream response
        async for chunk in openrouter_client.chat_stream(
            messages=messages,
            system_prompt=self.system_prompt,
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
        """Get streaming response for a message with an image"""
        # Add context to help with ant identification (kept short)
        enhanced_prompt = f"""User sent an image: "{content}"

Identify the ant briefly:
1. Key features (2-3 words each)
2. Species name (with scientific name)
3. One interesting fact

If not an ant image, say so briefly."""

        async for chunk in openrouter_client.chat_with_image(
            text=enhanced_prompt,
            image_base64=image_base64,
            mime_type=mime_type,
            system_prompt=self.system_prompt,
            temperature=0.7,
            max_tokens=512,
        ):
            yield chunk

    async def generate_suggestions(
        self,
        conversation_history: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate contextual follow-up questions based on conversation"""

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
            print(f"Error decoding JSON for suggestions: {e}")
        except (TypeError, ValueError) as e:
            print(f"Error generating suggestions: {e}")

        return FAQ_SUGGESTIONS

    def get_faq_suggestions(self) -> List[str]:
        """Get FAQ suggestions for quick questions"""
        return FAQ_SUGGESTIONS

# Singleton instance
chatbot_service = ChatbotService()
