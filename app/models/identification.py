"""Identification Model"""
from typing import Optional
from typing import List
from pydantic import BaseModel, ConfigDict


class PredictionResult(BaseModel):
    """Single prediction result"""
    rank: int
    species_id: Optional[str] = None
    class_name: str
    confidence: float


class ClassificationResponse(BaseModel):
    """Response from classification endpoint"""
    success: bool
    top_prediction: str
    top_confidence: float
    top_predictions: List[PredictionResult]
    model_used: Optional[str] = None


class DetectionBox(BaseModel):
    """Detection bounding box"""
    class_id: int
    class_name: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2]


class DetectionResponse(BaseModel):
    """Response from detection endpoint"""
    success: bool
    num_detections: int
    detections: List[DetectionBox]
    image_size: List[int]  # [width, height]


class Base64ImageRequest(BaseModel):
    """Request body for base64 image classification"""
    image_base64: str
    mime_type: str = "image/jpeg"
    confidence_threshold: float = 0.5
    top_k: int = 5

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "image_base64": "/9j/4AAQSkZJRgABAQAAAQABAAD...",
                "mime_type": "image/jpeg",
                "confidence_threshold": 0.5,
                "top_k": 5
            }
        }
    )
