"""
Feedback API Routes
User feedback, AI improvement suggestions, and species corrections
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import datetime
import uuid

from firebase_admin import firestore
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
from app.dependencies.auth import get_current_user

router = APIRouter()
db = firestore.client()

FEEDBACK_COLLECTION = "feedback"
AI_FEEDBACK_COLLECTION = "ai_feedback"
SPECIES_CORRECTIONS_COLLECTION = "species_corrections"


def require_admin(current_user: dict = Depends(get_current_user)):
    """Dependency to check if user is admin"""
    user_ref = db.collection("users").document(current_user["uid"])
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    user_data = user_doc.to_dict()
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ============== GENERAL FEEDBACK ==============

@router.post("/feedback", response_model=FeedbackSchema)
async def submit_feedback(
    feedback: FeedbackCreateSchema,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """
    Submit general app feedback.
    
    Can be submitted by authenticated users.
    """
    try:
        feedback_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        feedback_data = feedback.model_dump()
        feedback_data["id"] = feedback_id
        feedback_data["user_id"] = current_user.get("uid") if current_user else None
        feedback_data["status"] = FeedbackStatus.PENDING.value
        feedback_data["created_at"] = now
        feedback_data["reviewed_at"] = None
        
        db.collection(FEEDBACK_COLLECTION).document(feedback_id).set(feedback_data)
        
        return feedback_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feedback", response_model=FeedbackListResponse)
async def list_feedback(
    status: Optional[FeedbackStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_admin),
):
    """List all feedback (Admin only)"""
    try:
        query = db.collection(FEEDBACK_COLLECTION)
        
        if status:
            query = query.where("status", "==", status.value)
        
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
        query = query.limit(limit)
        
        docs = query.stream()
        
        items = []
        for doc in docs:
            data = doc.to_dict()
            items.append(data)
        
        return FeedbackListResponse(items=items, total=len(items))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/feedback/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: str,
    status: FeedbackStatus,
    current_user: dict = Depends(require_admin),
):
    """Update feedback status (Admin only)"""
    try:
        doc_ref = db.collection(FEEDBACK_COLLECTION).document(feedback_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Feedback not found")
        
        doc_ref.update({
            "status": status.value,
            "reviewed_at": datetime.utcnow(),
        })
        
        return {"message": f"Feedback status updated to {status.value}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== AI IMPROVEMENT FEEDBACK ==============

@router.post("/feedback/ai", response_model=AIFeedbackSchema)
async def submit_ai_feedback(
    feedback: AIFeedbackCreateSchema,
    current_user: dict = Depends(get_current_user),
):
    """
    Submit AI identification correction feedback.
    
    Used when the AI misidentifies a species and user provides correction.
    """
    try:
        feedback_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        feedback_data = feedback.model_dump()
        
        # Don't store base64 image directly - too large
        # In production, upload to storage and store URL
        if feedback_data.get("image_base64"):
            feedback_data["has_image"] = True
            # Remove base64 to avoid storing large data
            # del feedback_data["image_base64"]
            # For now, keep it but limit size
            if len(feedback_data["image_base64"]) > 100000:  # ~75KB
                feedback_data["image_base64"] = None
                feedback_data["image_too_large"] = True
        
        feedback_data["id"] = feedback_id
        feedback_data["user_id"] = current_user.get("uid")
        feedback_data["status"] = FeedbackStatus.PENDING.value
        feedback_data["created_at"] = now
        
        db.collection(AI_FEEDBACK_COLLECTION).document(feedback_id).set(feedback_data)
        
        return feedback_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feedback/ai")
async def list_ai_feedback(
    status: Optional[FeedbackStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_admin),
):
    """List all AI feedback (Admin only)"""
    try:
        query = db.collection(AI_FEEDBACK_COLLECTION)
        
        if status:
            query = query.where("status", "==", status.value)
        
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
        query = query.limit(limit)
        
        docs = query.stream()
        
        items = []
        for doc in docs:
            data = doc.to_dict()
            # Don't return base64 in list
            if "image_base64" in data:
                data["has_image"] = True
                del data["image_base64"]
            items.append(data)
        
        return {"items": items, "total": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== SPECIES CORRECTIONS ==============

@router.post("/species/{species_id}/corrections", response_model=SpeciesCorrectionSchema)
async def submit_species_correction(
    species_id: str,
    correction: SpeciesCorrectionCreateSchema,
    current_user: dict = Depends(get_current_user),
):
    """
    Submit a correction suggestion for species data.
    
    Users can suggest fixes for incorrect species information.
    """
    try:
        # Verify species exists
        species_doc = db.collection("species").document(species_id).get()
        if not species_doc.exists:
            raise HTTPException(status_code=404, detail="Species not found")
        
        correction_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        correction_data = correction.model_dump()
        correction_data["id"] = correction_id
        correction_data["species_id"] = species_id
        correction_data["user_id"] = current_user.get("uid")
        correction_data["status"] = FeedbackStatus.PENDING.value
        correction_data["created_at"] = now
        
        db.collection(SPECIES_CORRECTIONS_COLLECTION).document(correction_id).set(correction_data)
        
        return correction_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/species/corrections")
async def list_species_corrections(
    species_id: Optional[str] = None,
    status: Optional[FeedbackStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_admin),
):
    """List species corrections (Admin only)"""
    try:
        query = db.collection(SPECIES_CORRECTIONS_COLLECTION)
        
        if species_id:
            query = query.where("species_id", "==", species_id)
        
        if status:
            query = query.where("status", "==", status.value)
        
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
        query = query.limit(limit)
        
        docs = query.stream()
        
        items = []
        for doc in docs:
            data = doc.to_dict()
            items.append(data)
        
        return {"items": items, "total": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/species/corrections/{correction_id}/apply")
async def apply_species_correction(
    correction_id: str,
    current_user: dict = Depends(require_admin),
):
    """
    Apply a species correction (Admin only).
    
    Updates the species data with the suggested correction.
    """
    try:
        # Get correction
        correction_ref = db.collection(SPECIES_CORRECTIONS_COLLECTION).document(correction_id)
        correction_doc = correction_ref.get()
        
        if not correction_doc.exists:
            raise HTTPException(status_code=404, detail="Correction not found")
        
        correction_data = correction_doc.to_dict()
        
        # Apply correction to species
        species_ref = db.collection("species").document(correction_data["species_id"])
        species_doc = species_ref.get()
        
        if not species_doc.exists:
            raise HTTPException(status_code=404, detail="Species not found")
        
        field_name = correction_data["field_name"]
        suggested_value = correction_data["suggested_value"]
        
        # Update species field
        species_ref.update({
            field_name: suggested_value,
            "updated_at": datetime.utcnow(),
        })
        
        # Mark correction as resolved
        correction_ref.update({
            "status": FeedbackStatus.RESOLVED.value,
        })
        
        return {
            "message": f"Correction applied: {field_name} updated",
            "species_id": correction_data["species_id"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
