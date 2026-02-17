"""
Socket.IO Server for Real-time Chatbot
Handles WebSocket connections for streaming chat responses
"""
import socketio
from typing import Dict, Any

from app.services.chatbot import chatbot_service


# Create Socket.IO server with CORS enabled
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],
    logger=True,
    engineio_logger=True,
)

# Create ASGI app for Socket.IO
socket_app = socketio.ASGIApp(sio)


@sio.event
async def connect(sid: str, environ: Dict[str, Any]):
    """Handle client connection"""
    print(f"Client connected: {sid}")
    await sio.emit("connected", {"message": "Connected to Antify chatbot"}, to=sid)


@sio.event
async def disconnect(sid: str):
    """Handle client disconnection"""
    print(f"Client disconnected: {sid}")


@sio.event
async def message(sid: str, data: Dict[str, Any]):
    """
    Handle incoming text messages and stream responses.
    
    Expected data format:
    {
        "content": "User's message",
        "conversationHistory": [
            {"content": "...", "role": "user"|"assistant", "timestamp": "..."}
        ]
    }
    """
    try:
        content = data.get("content", "")
        conversation_history = data.get("conversationHistory", [])
        
        if not content.strip():
            await sio.emit("error", {"message": "Empty message"}, to=sid)
            return
        
        # Collect full response for suggestion generation
        full_response = ""
        
        # Stream response chunks
        async for chunk in chatbot_service.get_response_stream(
            content=content,
            conversation_history=conversation_history,
        ):
            full_response += chunk
            await sio.emit("response", chunk, to=sid)
        
        # Signal completion
        await sio.emit("response_complete", to=sid)
        
        # Generate contextual suggestions based on updated conversation
        updated_history = conversation_history + [
            {"role": "user", "content": content},
            {"role": "assistant", "content": full_response},
        ]
        suggestions = await chatbot_service.generate_suggestions(updated_history)
        await sio.emit("suggestions", {"suggestions": suggestions}, to=sid)
        
    except Exception as e:
        print(f"Error handling message: {e}")
        await sio.emit("error", {"message": str(e)}, to=sid)


@sio.event
async def message_with_image(sid: str, data: Dict[str, Any]):
    """
    Handle messages with images for visual analysis.
    
    Expected data format:
    {
        "content": "What species is this?",
        "imageBase64": "base64_encoded_image_data",
        "imageMimeType": "image/jpeg"
    }
    """
    try:
        content = data.get("content", "Identify this ant")
        image_base64 = data.get("imageBase64", "")
        mime_type = data.get("imageMimeType", "image/jpeg")
        
        if not image_base64:
            await sio.emit("error", {"message": "No image provided"}, to=sid)
            return
        
        # Collect full response for suggestion generation
        full_response = ""
        
        # Stream response chunks
        async for chunk in chatbot_service.get_response_with_image_stream(
            content=content,
            image_base64=image_base64,
            mime_type=mime_type,
        ):
            full_response += chunk
            await sio.emit("response", chunk, to=sid)
        
        # Signal completion
        await sio.emit("response_complete", to=sid)
        
        # Generate contextual suggestions based on the image analysis
        updated_history = [
            {"role": "user", "content": f"[Image] {content}"},
            {"role": "assistant", "content": full_response},
        ]
        suggestions = await chatbot_service.generate_suggestions(updated_history)
        await sio.emit("suggestions", {"suggestions": suggestions}, to=sid)
        
    except Exception as e:
        print(f"Error handling image message: {e}")
        await sio.emit("error", {"message": str(e)}, to=sid)


@sio.event
async def get_suggestions(sid: str, data: Dict[str, Any] = None):
    """Get FAQ suggestions for quick questions"""
    suggestions = chatbot_service.get_faq_suggestions()
    await sio.emit("suggestions", {"suggestions": suggestions}, to=sid)
