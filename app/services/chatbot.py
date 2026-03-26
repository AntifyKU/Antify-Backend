"""
Chatbot Service
Business logic for the ant-focused chatbot
"""
import json
from typing import List, Dict, Any, AsyncGenerator
import re

from app.firebase import db
from app.services.openrouter import openrouter_client


SPECIES_COLLECTION = "species"


# System prompt for the ant expert chatbot
ANT_EXPERT_SYSTEM_PROMPT = """You are AntBot,
an ant expert assistant for the Antify app (Thailand/Southeast Asia focus).

STRICT RULES:
1. ONLY answer questions about ants. For non-ant topics, politely say: "I specialize in ants only. Please ask me about ants!"
2. Keep responses SHORT (2-4 sentences max). Be concise and direct.
3. Use simple language. Avoid long explanations.
24. Include scientific names in parentheses when mentioning species.
25. BEHAVIOR RULES:
    - If the user asks a general question (e.g., habitat, behavior, lifecycle): Answer with a simple text explanation only.
    - If the user asks about a specific species OR a specific trait (e.g., venom, sting, size, diet): You MUST mention at least one representative species name AND scientific name in your response (e.g., "Fire Ants (Solenopsis) have venom") so the system can display an information card.
26. Even if the user does not ask for a specific species, but asks about a trait (like venom), you should still mention a relevant representative species from the database.
27. IMPORTANT: You MUST answer in the exact same language as the user's prompt (e.g., if asked in Thai, answer in Thai).
28. CRITICAL: NEVER use **bold** or *italics*. Use PLAIN TEXT ONLY. NO MARKDOWN.
29. NO SPECIAL SYMBOLS: Do not end responses with any technical markers or brackets.

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
        self._all_species_cache = []

    def _get_all_species(self) -> List[Dict[str, Any]]:
        """Fetch all species from Firebase for comprehensive name matching."""
        if self._all_species_cache:
            return self._all_species_cache
        
        try:
            docs = db.collection(SPECIES_COLLECTION).stream()
            self._all_species_cache = []
            for doc in docs:
                data = doc.to_dict()
                # Store only essential fields for matching and display
                self._all_species_cache.append({
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "scientific_name": data.get("scientific_name"),
                    "image": data.get("image"),
                    "risk": data.get("risk")
                })
            return self._all_species_cache
        except Exception as e:
            print(f"Error fetching all species: {e}")
            return []

    def find_species_in_text(self, text: str) -> List[Dict[str, Any]]:
        """Scan text for any species name or scientific name from the database."""
        species_list = self._get_all_species()
        text_lower = text.lower()
        
        # We'll categorize matches by "quality"
        full_matches = [] # Full scientific name or full common name
        partial_matches = [] # Genus-only or substring match
        
        # Sort by name length descending to match longest names first
        sorted_species = sorted(species_list, key=lambda x: len(x.get("name", "") or ""), reverse=True)
        
        seen_ids = set()
        for s in sorted_species:
            if s.get("id") in seen_ids:
                continue
                
            name = (s.get("name") or "").lower()
            sci = (s.get("scientific_name") or "").lower()
            
            # 1. Match Full Scientific Name (Highest priority)
            if sci and sci in text_lower:
                full_matches.append(s)
                seen_ids.add(s.get("id"))
                continue

            # 2. Match Full Common Name (High priority)
            if name and len(name) > 3:
                # Use word boundaries for short names
                if len(name) < 7:
                    if re.search(rf'\b{re.escape(name)}\b', text_lower):
                        full_matches.append(s)
                        seen_ids.add(s.get("id"))
                        continue
                elif name in text_lower:
                    full_matches.append(s)
                    seen_ids.add(s.get("id"))
                    continue

            # 3. Match Genus (Lower priority, only if genus is unique or no other match)
            sci_parts = sci.split()
            genus = sci_parts[0] if sci_parts else ""
            if len(genus) > 4 and re.search(rf'\b{re.escape(genus)}\b', text_lower):
                partial_matches.append(s)
                seen_ids.add(s.get("id"))
                
        # Result selection:
        # If we have full name matches, return only those (up to 3)
        if full_matches:
            return full_matches[:3]
            
        # Otherwise, fall back to partial matches (up to 2)
        return partial_matches[:2]

    def _get_relevant_ant_context(self, query: str) -> tuple[str, List[Dict[str, Any]]]:
        """Fetch ant details from Firebase if query matches ant names/tags."""
        try:
            # SIMPLE KEYWORD EXTRACTION: words longer than 3 chars, filtering out common generic words
            GENERIC_WORDS = {"ant", "ants", "what", "which", "where", "tell", "about", "show", "many"}
            words = {w for w in re.findall(r'\b\w{3,}\b', query.lower()) if w not in GENERIC_WORDS}
            if not words:
                return "", []

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
                return "", []

            context_parts = ["\n[Database Context about mentioned ants]:"]
            for m in matches:
                context_parts.append(
                    f"- {m.get('name')} ({m.get('scientific_name')}): "
                    f"About: {m.get('about', '')}. "
                    f"Habitat: {', '.join(m.get('habitat', []))}. "
                    f"Behavior: {m.get('behavior', '')}."
                )
            # Return context string and the list of species objects with essential fields
            species_metadata = []
            for m in matches:
                species_metadata.append({
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "scientific_name": m.get("scientific_name"),
                    "image": m.get("image"),
                    "risk": m.get("risk")
                })
            return "\n".join(context_parts), species_metadata
        except (ValueError, TypeError) as e:
            print(f"Error fetching RAG context: {e}")
            return "", []

    def get_response_stream(
        self,
        content: str,
        conversation_history: List[Dict[str, Any]] = None,
    ) -> tuple[AsyncGenerator[str, None], List[Dict[str, Any]]]:
        """
        Get streaming response from the chatbot.
        Returns a tuple of (streaming_generator, relevant_species_metadata).
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
        rag_context, relevant_species = self._get_relevant_ant_context(content)
        final_system_prompt = self.system_prompt + rag_context

        # Add current user message
        messages.append({"role": "user", "content": content})

        # Define the generator
        async def stream_generator():
            # Stream response
            async for chunk in openrouter_client.chat_stream(
                messages=messages,
                system_prompt=final_system_prompt,
                temperature=0.7,
                max_tokens=1024,
            ):
                # Clean chunk: remove markdown bold/italics
                cleaned_chunk = chunk.replace("**", "").replace("__", "").replace("*", "").replace("_", "")
                # Filter out suspicious markers like [e~[
                if "[e~[" not in cleaned_chunk:
                    yield cleaned_chunk

        return stream_generator(), relevant_species

    def get_response_with_image_stream(
        self,
        content: str,
        image_base64: str,
        mime_type: str = "image/jpeg",
    ) -> tuple[AsyncGenerator[str, None], List[Dict[str, Any]]]:
        """
        Get streaming response for a message with an image.
        Returns a tuple of (streaming_generator, relevant_species_metadata).
        """
        # Add context to help with ant identification (kept short)
        enhanced_prompt = f"""User sent an image: "{content}"

Identify the ant briefly:
1. Key features (2-3 words each)
2. Species name (with scientific name)
3. One interesting fact

If not an ant image, say so briefly."""

        # Get context from Firebase based on current question
        rag_context, relevant_species = self._get_relevant_ant_context(content)
        final_system_prompt = self.system_prompt + rag_context

        async def stream_generator():
            async for chunk in openrouter_client.chat_with_image(
                text=enhanced_prompt,
                image_base64=image_base64,
                mime_type=mime_type,
                system_prompt=final_system_prompt,
                temperature=0.7,
                max_tokens=512,
            ):
                yield chunk

        return stream_generator(), relevant_species

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
