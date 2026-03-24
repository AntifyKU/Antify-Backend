"""
Feedback API Routes
User feedback, AI improvement suggestions, and species corrections
"""
from typing import Optional, Annotated
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, HTTPException, Depends, Query
from google.cloud.firestore import Client, Query as FirestoreQuery
from app.firebase import db

from app.models.feedback import (
    FeedbackCreateSchema,
    FeedbackSchema,
    FeedbackStatus,
    AIFeedbackCreateSchema,
    AIFeedbackSchema,
    SpeciesCorrectionCreateSchema,
    SpeciesCorrectionSchema,
    FeedbackListResponse,
)
from app.dependencies.auth import get_current_user, get_optional_user

# Public routes
router = APIRouter()

# Admin-only routes
admin_router = APIRouter()



FEEDBACK_COLLECTION = "feedback"
AI_FEEDBACK_COLLECTION = "ai_feedback"
SPECIES_CORRECTIONS_COLLECTION = "species_corrections"

_IMAGE_SIZE_LIMIT = 100_000  # ~75 KB

_R500 = {
    500: {
        "description": "Internal Server Error",
        "content": {"application/json": {"example": {"detail": "An unexpected error occurred."}}},
    }
}
_R404_500 = {
    404: {
        "description": "Resource not found",
        "content": {"application/json": {"example": {"detail": "<Resource> not found"}}},
    },
    **_R500,
}
_R404_500_FEEDBACK   = {404: {"description": "Feedback not found",   **_R404_500[404]}, **_R500}
_R404_500_SPECIES    = {404: {"description": "Species not found",     **_R404_500[404]}, **_R500}
_R404_500_CORRECTION = {404: {"description": "Correction not found",  **_R404_500[404]}, **_R500}


def _now_utc() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(tz=timezone.utc)


def _get_or_404(collection: str, doc_id: str, label: str) -> dict:
    """Fetch a Firestore document or raise HTTP 404."""
    doc = db.collection(collection).document(doc_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return doc.to_dict()


def _stream_collection(
    collection: str,
    *,
    filters: Optional[list[tuple]] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Stream documents from a Firestore collection with optional equality filters,
    ordered by created_at descending.
    """
    query: FirestoreQuery = db.collection(collection)
    for field, value in (filters or []):
        query = query.where(field, "==", value)
    query = query.order_by("created_at", direction=FirestoreQuery.DESCENDING).limit(limit)
    return [doc.to_dict() for doc in query.stream()]


def _strip_base64(items: list[dict]) -> list[dict]:
    """Remove image_base64 from each item and set has_image flag in-place."""
    for item in items:
        if "image_base64" in item:
            item["has_image"] = True
            del item["image_base64"]
    return items


@router.post("/feedback", response_model=FeedbackSchema, responses=_R500)
async def submit_feedback(
    feedback: FeedbackCreateSchema,
    current_user: Annotated[Optional[dict], Depends(get_optional_user)],
):
    """Submit general app feedback."""
    try:
        feedback_id = str(uuid.uuid4())
        feedback_data = {
            **feedback.model_dump(),
            "id": feedback_id,
            "user_id": current_user.get("uid") if current_user else None,
            "status": FeedbackStatus.PENDING.value,
            "created_at": _now_utc(),
            "reviewed_at": None,
        }
        db.collection(FEEDBACK_COLLECTION).document(feedback_id).set(feedback_data)
        return feedback_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/feedback/ai", response_model=AIFeedbackSchema, responses=_R500)
async def submit_ai_feedback(
    feedback: AIFeedbackCreateSchema,
    current_user: Annotated[Optional[dict], Depends(get_optional_user)],
):
    """
    Submit AI identification correction feedback.
    Used when the AI misidentifies a species and the user provides a correction.
    """
    try:
        feedback_id = str(uuid.uuid4())
        feedback_data = feedback.model_dump()

        image_b64: Optional[str] = feedback_data.get("image_base64")
        if image_b64:
            feedback_data["has_image"] = True
            if len(image_b64) > _IMAGE_SIZE_LIMIT:
                feedback_data["image_base64"] = None
                feedback_data["image_too_large"] = True

        feedback_data.update({
            "id": feedback_id,
            "user_id": current_user.get("uid") if current_user else None,
            "status": FeedbackStatus.PENDING.value,
            "created_at": _now_utc(),
        })
        db.collection(AI_FEEDBACK_COLLECTION).document(feedback_id).set(feedback_data)
        return feedback_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/species/{species_id}/corrections",
    response_model=SpeciesCorrectionSchema,
    responses=_R404_500_SPECIES,
)
async def submit_species_correction(
    species_id: str,
    correction: SpeciesCorrectionCreateSchema,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Submit a correction suggestion for species data."""
    try:
        _get_or_404("species", species_id, "Species")

        correction_id = str(uuid.uuid4())
        correction_data = {
            **correction.model_dump(),
            "id": correction_id,
            "species_id": species_id,
            "user_id": current_user.get("uid"),
            "status": FeedbackStatus.PENDING.value,
            "created_at": _now_utc(),
        }
        db.collection(SPECIES_CORRECTIONS_COLLECTION).document(correction_id).set(correction_data)
        return correction_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@admin_router.get("/feedback", response_model=FeedbackListResponse, responses=_R500)
async def list_feedback(
    status: Annotated[Optional[FeedbackStatus], Query(description="Filter by status")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max items to return")] = 50,
):
    """List all feedback (Admin only)."""
    try:
        filters = [("status", status.value)] if status else None
        items = _stream_collection(FEEDBACK_COLLECTION, filters=filters, limit=limit)
        return FeedbackListResponse(items=items, total=len(items))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@admin_router.put("/feedback/{feedback_id}/status", responses=_R404_500_FEEDBACK)
async def update_feedback_status(
    feedback_id: str,
    status: Annotated[FeedbackStatus, Query(description="New status value")],
):
    """Update feedback status (Admin only)."""
    try:
        doc_ref = db.collection(FEEDBACK_COLLECTION).document(feedback_id)
        if not doc_ref.get().exists:
            raise HTTPException(status_code=404, detail="Feedback not found")
        doc_ref.update({"status": status.value, "reviewed_at": _now_utc()})
        return {"message": f"Feedback status updated to {status.value}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@admin_router.get("/feedback/ai", responses=_R500)
async def list_ai_feedback(
    status: Annotated[Optional[FeedbackStatus], Query(description="Filter by status")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max items to return")] = 50,
):
    """List all AI feedback (Admin only)."""
    try:
        filters = [("status", status.value)] if status else None
        items = _stream_collection(AI_FEEDBACK_COLLECTION, filters=filters, limit=limit)
        return {"items": _strip_base64(items), "total": len(items)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@admin_router.get("/species/corrections", responses=_R500)
async def list_species_corrections(
    species_id: Annotated[Optional[str], Query(description="Filter by species ID")] = None,
    status: Annotated[Optional[FeedbackStatus], Query(description="Filter by status")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max items to return")] = 50,
):
    """List species corrections (Admin only)."""
    try:
        filters = []
        if species_id:
            filters.append(("species_id", species_id))
        if status:
            filters.append(("status", status.value))
        items = _stream_collection(SPECIES_CORRECTIONS_COLLECTION, filters=filters, limit=limit)
        return {"items": items, "total": len(items)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@admin_router.put(
    "/species/corrections/{correction_id}/apply",
    responses=_R404_500_CORRECTION,
)
async def apply_species_correction(correction_id: str):
    """Apply a species correction (Admin only)."""
    try:
        correction_data = _get_or_404(
            SPECIES_CORRECTIONS_COLLECTION, correction_id, "Correction"
        )
        species_id = correction_data["species_id"]
        _get_or_404("species", species_id, "Species")

        db.collection("species").document(species_id).update({
            correction_data["field_name"]: correction_data["suggested_value"],
            "updated_at": _now_utc(),
        })
        db.collection(SPECIES_CORRECTIONS_COLLECTION).document(correction_id).update({
            "status": FeedbackStatus.RESOLVED.value,
        })

        return {
            "message": f"Correction applied: {correction_data['field_name']} updated",
            "species_id": species_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
