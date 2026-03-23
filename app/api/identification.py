"""
AI Identification API Routes
"""
import io
import uuid
import logging
from typing import Annotated

import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from firebase_admin import firestore as fs
from firebase_admin.exceptions import FirebaseError

from app.services.ai_client import ai_client
from app.models.identification import (
    PredictionResult,
    ClassificationResponse,
    DetectionBox,
    DetectionResponse,
    Base64ImageRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_ERR_AI_UNAVAILABLE = "AI service is currently unavailable. Please try again later."
_ERR_INVALID_FILE   = "Invalid file type. Please upload an image file."

_RESPONSES_400_503_500 = {
    400: {"description": "Invalid file type"},
    503: {"description": "AI service unavailable"},
    500: {"description": "Internal server error"},
}
_RESPONSES_503_500 = {
    503: {"description": "AI service unavailable"},
    500: {"description": "Internal server error"},
}

_CLOUDINARY_FOLDER = "identified_ants"


def _require_image(file: UploadFile) -> None:
    """Raise HTTP 400 if the upload is not an image."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail=_ERR_INVALID_FILE)


def _raise_from_ai_error(e: Exception, action: str) -> None:
    """Convert AI-client exceptions into appropriate HTTP errors."""
    error_msg = str(e)
    if "ConnectError" in error_msg or "Connection refused" in error_msg:
        raise HTTPException(status_code=503, detail=_ERR_AI_UNAVAILABLE) from e
    raise HTTPException(status_code=500, detail=f"{action} failed: {error_msg}") from e


def _build_predictions(raw: dict) -> list[PredictionResult]:
    raw_preds = raw.get("top_predictions", raw.get("top5_predictions", []))
    return [
        PredictionResult(
            rank=pred.get("rank", i),
            class_name=pred.get("class_name", pred.get("species", "Unknown")),
            confidence=pred.get("confidence", 0.0),
            species_id=pred.get("species_id"),
        )
        for i, pred in enumerate(raw_preds, 1)
    ]


def _build_plain_predictions(result: dict) -> list[dict]:
    raw = result.get("top_predictions", result.get("top5_predictions", []))
    return [
        {
            "rank":       pred.get("rank", i),
            "class_name": pred.get("class_name", pred.get("species", "Unknown")),
            "confidence": pred.get("confidence", 0.0),
            "species_id": pred.get("species_id"),
        }
        for i, pred in enumerate(raw, 1)
    ]


def _to_classification_response(result: dict) -> ClassificationResponse:
    predictions = _build_predictions(result)
    return ClassificationResponse(
        success=True,
        top_prediction=result.get(
            "top_prediction",
            predictions[0].class_name if predictions else "Unknown",
        ),
        top_confidence=result.get(
            "top_confidence",
            predictions[0].confidence if predictions else 0.0,
        ),
        top_predictions=predictions,
        model_used=result.get("model"),
    )


def _normalise_timestamps(species: dict) -> dict:
    """Convert Firestore timestamp fields to ISO strings in-place."""
    for field in ("created_at", "updated_at"):
        value = species.get(field)
        if value is not None:
            try:
                species[field] = value.isoformat()
            except (AttributeError, TypeError):
                pass
    return species


def _lookup_species(scientific_name: str) -> dict | None:
    """Query Firestore for a species by scientific name; returns None on miss or error."""
    try:
        db = fs.client()
        docs = (
            db.collection("species")
            .where("scientific_name", "==", scientific_name)
            .limit(1)
            .stream()
        )
        for doc in docs:
            species = doc.to_dict()
            species["id"] = doc.id
            return _normalise_timestamps(species)
    except FirebaseError as e:
        logger.error("[identify] Firestore species lookup error: %s", e)
    return None


def _ai_rejected(result: dict) -> dict:
    """Return a standardised 'not an ant' response payload."""
    return {
        "success":      False,
        "message":      result.get("message", "Image was not recognized as an ant."),
        "predictions":  [],
        "species_info": None,
    }


def _upload_to_cloudinary(
    content: bytes,
    species_name: str,
    confidence: float,
) -> str | None:
    """
    Upload image bytes to Cloudinary under identified_ants/<species_name>/.
    Tags the asset with the species name and confidence score.
    Returns the secure URL, or None on failure (best-effort).
    """
    try:
        # Sanitise species name for use as a folder path segment
        safe_name = species_name.replace(" ", "_").replace("/", "-")
        public_id = f"{_CLOUDINARY_FOLDER}/{safe_name}/{uuid.uuid4()}"

        result = cloudinary.uploader.upload(
            io.BytesIO(content),
            public_id=public_id,
            resource_type="image",
            overwrite=False,
            context={
                "species":    species_name,
                "confidence": f"{confidence:.4f}",
            },
            tags=[safe_name, "identified_ant"],
        )
        return result["secure_url"]

    except (cloudinary.exceptions.Error, OSError, IOError) as exc:
        logger.warning("[identify] Cloudinary upload failed: %s", exc)
        return None


@router.get("/identify/health")
async def ai_health_check():
    """Check AI service health status."""
    return await ai_client.health_check()


@router.get("/identify/models")
async def list_ai_models():
    """List available AI models."""
    models = await ai_client.get_available_models()
    return {"models": models}


@router.post(
    "/identify",
    response_model=ClassificationResponse,
    responses=_RESPONSES_400_503_500,
)
async def identify_ant(
    file: Annotated[UploadFile, File(description="Image file to identify")],
    confidence: Annotated[float, Query(ge=0.0, le=1.0,
                                       description="Minimum confidence threshold")] = 0.5,
    top_k: Annotated[int, Query(ge=1, le=10, description="Number of top predictions")] = 5,
):
    """
    Identify ant species from an uploaded image.
    Returns top predictions with confidence scores.
    """
    _require_image(file)
    try:
        result = await ai_client.classify_image(
            file=file,
            confidence_threshold=confidence,
            top_k=top_k,
        )
        return _to_classification_response(result)
    except RuntimeError as e:
        _raise_from_ai_error(e, "Identification")


@router.post(
    "/identify/base64",
    response_model=ClassificationResponse,
    responses=_RESPONSES_503_500,
)
async def identify_ant_base64(request: Base64ImageRequest):
    """Identify ant species from a base64-encoded image."""
    try:
        result = await ai_client.classify_base64(
            image_base64=request.image_base64,
            mime_type=request.mime_type,
            confidence_threshold=request.confidence_threshold,
            top_k=request.top_k,
        )
        return _to_classification_response(result)
    except RuntimeError as e:
        _raise_from_ai_error(e, "Identification")


@router.post(
    "/identify/detect",
    response_model=DetectionResponse,
    responses=_RESPONSES_400_503_500,
)
async def detect_ants(
    file: Annotated[UploadFile, File(description="Image file to analyze")],
    confidence: Annotated[float, Query(ge=0.0, le=1.0,
                                       description="Detection confidence threshold")] = 0.25,
    iou: Annotated[float, Query(ge=0.0, le=1.0, description="IoU threshold for NMS")] = 0.45,
):
    """Detect ants in an image and return bounding boxes."""
    _require_image(file)
    try:
        result = await ai_client.detect_ants(
            file=file,
            confidence_threshold=confidence,
            iou_threshold=iou,
        )
        detections = [
            DetectionBox(
                class_id=det.get("class_id", 0),
                class_name=det.get("class_name", "ant"),
                confidence=det.get("confidence", 0.0),
                bbox=det.get("bbox", []),
            )
            for det in result.get("detections", [])
        ]
        return DetectionResponse(
            success=result.get("success", True),
            num_detections=result.get("num_detections", len(detections)),
            detections=detections,
            image_size=result.get("image_size", [0, 0]),
        )
    except RuntimeError as e:
        _raise_from_ai_error(e, "Detection")


@router.post(
    "/identify/species/details",
    responses=_RESPONSES_400_503_500,
)
async def identify_species_details(
    file: Annotated[UploadFile, File(description="Image file to identify")],
    confidence: Annotated[float, Query(ge=0.0, le=1.0,
                                       description="Minimum confidence threshold")] = 0.5,
    top_k: Annotated[int, Query(ge=1, le=10, description="Number of top predictions")] = 5,
):
    """
    Identify ant species AND return full species info from Firestore.

    On success (species identified), the image is uploaded to Cloudinary
    under identified_ants/<species_name>/ with species and confidence metadata.
    Images that cannot be identified are NOT uploaded.
    """
    _require_image(file)

    # Read once, ai_client.classify_image() does its own read+seek internally,
    # so we read here first, seek back, then pass the bytes to Cloudinary after.
    file_content = await file.read()
    await file.seek(0)

    try:
        result = await ai_client.classify_image(
            file=file,
            confidence_threshold=confidence,
            top_k=top_k,
        )
    except RuntimeError as e:
        _raise_from_ai_error(e, "Identification")

    # AI could not identify the image, do not upload
    if not result.get("success", True):
        return _ai_rejected(result)

    predictions         = _build_plain_predictions(result)
    top_scientific_name = result.get(
        "top_prediction",
        predictions[0]["class_name"] if predictions else None,
    )
    top_confidence = result.get(
        "top_confidence",
        predictions[0]["confidence"] if predictions else 0.0,
    )
    species_info = _lookup_species(top_scientific_name) if top_scientific_name else None

    # Upload to Cloudinary (best-effort, never blocks the response)
    image_url: str | None = None
    if top_scientific_name and top_confidence >= 0.80:
        image_url = _upload_to_cloudinary(
            content=file_content,
            species_name=top_scientific_name,
            confidence=top_confidence,
        )

    return {
        "success":        True,
        "top_prediction": top_scientific_name,
        "top_confidence": top_confidence,
        "predictions":    predictions,
        "species_info":   species_info,
        "image_url":      image_url,
        "model":          result.get("model"),
    }
