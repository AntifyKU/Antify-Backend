"""
AI Identification API Routes
Proxy to the AI microservice for ant species identification
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from typing import Optional
from pydantic import BaseModel
from typing import List, Dict, Any

from app.services.ai_client import ai_client

router = APIRouter()


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

    class Config:
        json_schema_extra = {
            "example": {
                "image_base64": "/9j/4AAQSkZJRgABAQAAAQABAAD...",
                "mime_type": "image/jpeg",
                "confidence_threshold": 0.5,
                "top_k": 5
            }
        }


@router.get("/identify/health")
async def ai_health_check():
    """Check AI service health status"""
    result = await ai_client.health_check()
    return result


@router.get("/identify/models")
async def list_ai_models():
    """List available AI models"""
    models = await ai_client.get_available_models()
    return {"models": models}


@router.post("/identify", response_model=ClassificationResponse)
async def identify_ant(
    file: UploadFile = File(..., description="Image file to identify"),
    confidence: float = Query(0.5, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    top_k: int = Query(5, ge=1, le=10, description="Number of top predictions"),
):
    """
    Identify ant species from an uploaded image.
    
    Returns top predictions with confidence scores.
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an image file."
        )
    
    try:
        result = await ai_client.classify_image(
            file=file,
            confidence_threshold=confidence,
            top_k=top_k,
        )
        
        # Transform result to match our response model
        predictions = []
        for i, pred in enumerate(result.get("top_predictions", result.get("top5_predictions", [])), 1):
            predictions.append(PredictionResult(
                rank=pred.get("rank", i),
                class_name=pred.get("class_name", pred.get("species", "Unknown")),
                confidence=pred.get("confidence", 0.0),
                species_id=pred.get("species_id"),
            ))
        
        return ClassificationResponse(
            success=True,
            top_prediction=result.get("top_prediction", predictions[0].class_name if predictions else "Unknown"),
            top_confidence=result.get("top_confidence", predictions[0].confidence if predictions else 0.0),
            top_predictions=predictions,
            model_used=result.get("model"),
        )
    except Exception as e:
        # If AI service is unavailable, return a meaningful error
        error_msg = str(e)
        if "ConnectError" in error_msg or "Connection refused" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="AI service is currently unavailable. Please try again later."
            )
        raise HTTPException(status_code=500, detail=f"Identification failed: {error_msg}")


@router.post("/identify/base64", response_model=ClassificationResponse)
async def identify_ant_base64(request: Base64ImageRequest):
    """
    Identify ant species from a base64 encoded image.
    
    Useful for mobile apps that send images as base64 strings.
    """
    try:
        result = await ai_client.classify_base64(
            image_base64=request.image_base64,
            mime_type=request.mime_type,
            confidence_threshold=request.confidence_threshold,
            top_k=request.top_k,
        )
        
        predictions = []
        for i, pred in enumerate(result.get("top_predictions", result.get("top5_predictions", [])), 1):
            predictions.append(PredictionResult(
                rank=pred.get("rank", i),
                class_name=pred.get("class_name", pred.get("species", "Unknown")),
                confidence=pred.get("confidence", 0.0),
                species_id=pred.get("species_id"),
            ))
        
        return ClassificationResponse(
            success=True,
            top_prediction=result.get("top_prediction", predictions[0].class_name if predictions else "Unknown"),
            top_confidence=result.get("top_confidence", predictions[0].confidence if predictions else 0.0),
            top_predictions=predictions,
            model_used=result.get("model"),
        )
    except Exception as e:
        error_msg = str(e)
        if "ConnectError" in error_msg or "Connection refused" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="AI service is currently unavailable. Please try again later."
            )
        raise HTTPException(status_code=500, detail=f"Identification failed: {error_msg}")


@router.post("/identify/detect", response_model=DetectionResponse)
async def detect_ants(
    file: UploadFile = File(..., description="Image file to analyze"),
    confidence: float = Query(0.25, ge=0.0, le=1.0, description="Detection confidence threshold"),
    iou: float = Query(0.45, ge=0.0, le=1.0, description="IoU threshold for NMS"),
):
    """
    Detect ants in an image and return bounding boxes.
    
    Useful for counting ants or highlighting them in the image.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an image file."
        )
    
    try:
        result = await ai_client.detect_ants(
            file=file,
            confidence_threshold=confidence,
            iou_threshold=iou,
        )
        
        detections = []
        for det in result.get("detections", []):
            detections.append(DetectionBox(
                class_id=det.get("class_id", 0),
                class_name=det.get("class_name", "ant"),
                confidence=det.get("confidence", 0.0),
                bbox=det.get("bbox", []),
            ))
        
        return DetectionResponse(
            success=result.get("success", True),
            num_detections=result.get("num_detections", len(detections)),
            detections=detections,
            image_size=result.get("image_size", [0, 0]),
        )
    except Exception as e:
        error_msg = str(e)
        if "ConnectError" in error_msg or "Connection refused" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="AI service is currently unavailable. Please try again later."
            )
        raise HTTPException(status_code=500, detail=f"Detection failed: {error_msg}")
