"""
Chatbot Service
Business logic for the ant-focused chatbot
"""
from typing import List, Dict, Any, AsyncGenerator

from app.services.openrouter import openrouter_client


# System prompt for the ant expert chatbot
ANT_EXPERT_SYSTEM_PROMPT = """You are AntBot, an expert AI assistant specialized in myrmecology (the study of ants). You are part of the Antify app, which helps users identify and learn about ant species, particularly those found in Thailand and Southeast Asia.

Your expertise includes:
- Ant species identification and classification
- Ant behavior, ecology, and social structure
- Ant habitats and distribution
- Ant colony dynamics and queen/worker relationships
- Pest control and beneficial uses of ants
- Ant-related research and discoveries

Guidelines:
1. Be friendly, helpful, and educational
2. When identifying ants from descriptions or images, provide your best guess with confidence levels
3. If unsure, say so and suggest what additional information would help
4. Include interesting facts to make learning engaging
5. For pest-related questions, provide safe and practical advice
6. Reference scientific names when discussing species
7. Keep responses concise but informative
8. If asked about non-ant topics, politely redirect to ant-related subjects

When analyzing images:
- Describe what you observe (size, color, body shape, antennae)
- Provide your species identification with confidence level
- Suggest similar species if uncertain
- Note any interesting behaviors visible in the image

Remember: You are an expert but approachable resource for ant enthusiasts of all levels!"""


# FAQ suggestions for quick access
FAQ_SUGGESTIONS = [
    "What ant species are common in Thailand?",
    "How do I identify a fire ant?",
    "Are weaver ants dangerous to humans?",
    "How can I safely remove ants from my home?",
    "What do ants eat?",
    "How long do ant queens live?",
    "Why do ants follow trails?",
    "What's the difference between ants and termites?",
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
        """
        Get streaming response from the chatbot.
        
        Args:
            content: User's message
            conversation_history: Previous messages for context
            
        Yields:
            Response text chunks
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
        """
        Get streaming response for a message with an image.
        
        Args:
            content: User's message/question about the image
            image_base64: Base64 encoded image
            mime_type: Image MIME type
            
        Yields:
            Response text chunks
        """
        # Add context to help with ant identification
        enhanced_prompt = f"""The user has sent an image and asks: "{content}"

Please analyze the image focusing on ant identification. If it shows an ant:
1. Describe the visible characteristics
2. Provide your best species identification
3. Share relevant facts about this species

If the image doesn't clearly show an ant, let the user know and offer guidance on taking a better photo for identification."""
        
        async for chunk in openrouter_client.chat_with_image(
            text=enhanced_prompt,
            image_base64=image_base64,
            mime_type=mime_type,
            system_prompt=self.system_prompt,
            temperature=0.7,
            max_tokens=1024,
        ):
            yield chunk
    
    def get_faq_suggestions(self) -> List[str]:
        """Get FAQ suggestions for quick questions"""
        return FAQ_SUGGESTIONS


# Singleton instance
chatbot_service = ChatbotService()
