"""
AI Service Client
HTTP client for communicating with the AI microservice (Antify-ai-component)
"""
import base64
from typing import Dict, Any, List
import httpx
from fastapi import UploadFile

from app.config import AI_SERVICE_URL


class AIServiceClient:
    """Client for the AI identification microservice"""

    def __init__(self, base_url: str = AI_SERVICE_URL):
        self.base_url = base_url.rstrip("/")
        self.timeout = 60.0  # 60 seconds timeout for AI inference

    async def health_check(self) -> Dict[str, Any]:
        """Check if AI service is healthy"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as e:
                return {"status": "unavailable", "error": str(e)}
            except httpx.HTTPStatusError as e:
                return {"status": "error", "error": str(e)}

    async def classify_image(
        self,
        file: UploadFile,
        confidence_threshold: float = 0.5,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Classify an ant image to identify species"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Read file content
            content = await file.read()
            await file.seek(0)  # Reset file position

            files = {
                "file": (file.filename, content, file.content_type)
            }
            params = {
                "confidence": confidence_threshold,
                "top_k": top_k,
            }

            response = await client.post(
                f"{self.base_url}/classify",
                files=files,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def detect_ants(
        self,
        file: UploadFile,
        confidence_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ) -> Dict[str, Any]:
        """Detect ants in an image with bounding boxes"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            content = await file.read()
            await file.seek(0)

            files = {
                "file": (file.filename, content, file.content_type)
            }
            params = {
                "confidence": confidence_threshold,
                "iou": iou_threshold,
            }

            response = await client.post(
                f"{self.base_url}/detect",
                files=files,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def classify_base64(
        self,
        image_base64: str,
        mime_type: str = "image/jpeg",
        confidence_threshold: float = 0.5,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Classify an ant image from base64 string"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Decode base64 to bytes
            image_bytes = base64.b64decode(image_base64)

            # Determine filename extension from mime type
            ext = mime_type.split("/")[-1] if "/" in mime_type else "jpg"
            filename = f"image.{ext}"

            files = {
                "file": (filename, image_bytes, mime_type)
            }
            params = {
                "confidence": confidence_threshold,
                "top_k": top_k,
            }

            response = await client.post(
                f"{self.base_url}/classify",
                files=files,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available AI models"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.base_url}/models")
                response.raise_for_status()
                return response.json()
            except (httpx.RequestError, httpx.HTTPStatusError):
                return []

# Singleton instance
ai_client = AIServiceClient()
