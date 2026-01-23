"""
Feedback Pydantic Models
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class FeedbackType(str, Enum):
    """Types of feedback"""
    GENERAL = "general"
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    AI_IMPROVEMENT = "ai_improvement"
    SPECIES_CORRECTION = "species_correction"


class FeedbackStatus(str, Enum):
    """Feedback status"""
    PENDING = "pending"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class FeedbackBase(BaseModel):
    """Base feedback schema"""
    feedback_type: FeedbackType = FeedbackType.GENERAL
    message: str = Field(..., min_length=10, max_length=2000)
    rating: Optional[int] = Field(None, ge=1, le=5, description="App rating 1-5")


class FeedbackCreateSchema(FeedbackBase):
    """Schema for submitting general feedback"""
    pass

    class Config:
        json_schema_extra = {
            "example": {
                "feedback_type": "general",
                "message": "Great app for identifying ants! I learned a lot about local species.",
                "rating": 5
            }
        }


class FeedbackSchema(FeedbackBase):
    """Full feedback with metadata"""
    id: str
    user_id: Optional[str] = None
    status: FeedbackStatus = FeedbackStatus.PENDING
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AIFeedbackBase(BaseModel):
    """Base AI improvement feedback schema"""
    original_prediction: str = Field(..., description="What the AI predicted")
    correct_species_id: str = Field(..., description="ID of the correct species")
    correct_species_name: str = Field(..., description="Name of the correct species")
    confidence_was: Optional[float] = Field(None, description="Original confidence score")
    image_base64: Optional[str] = Field(None, description="Base64 image for reference")
    additional_notes: Optional[str] = None


class AIFeedbackCreateSchema(AIFeedbackBase):
    """Schema for submitting AI correction feedback"""
    pass

    class Config:
        json_schema_extra = {
            "example": {
                "original_prediction": "Weaver Ant",
                "correct_species_id": "3",
                "correct_species_name": "Red Imported Fire Ant",
                "confidence_was": 0.85,
                "additional_notes": "The color was more red than orange"
            }
        }


class AIFeedbackSchema(AIFeedbackBase):
    """Full AI feedback with metadata"""
    id: str
    user_id: Optional[str] = None
    status: FeedbackStatus = FeedbackStatus.PENDING
    created_at: datetime

    class Config:
        from_attributes = True


class SpeciesCorrectionBase(BaseModel):
    """Base species correction schema"""
    field_name: str = Field(..., description="Which field to correct")
    current_value: str = Field(..., description="Current incorrect value")
    suggested_value: str = Field(..., description="Suggested correct value")
    reason: str = Field(..., min_length=10, description="Why this change is needed")
    source: Optional[str] = Field(None, description="Source/reference for correction")


class SpeciesCorrectionCreateSchema(SpeciesCorrectionBase):
    """Schema for submitting species data correction"""
    pass

    class Config:
        json_schema_extra = {
            "example": {
                "field_name": "habitat",
                "current_value": "Tropical Forests",
                "suggested_value": "Tropical Forests, Urban Areas",
                "reason": "This species is commonly found in urban gardens as well",
                "source": "Personal observation + iNaturalist records"
            }
        }


class SpeciesCorrectionSchema(SpeciesCorrectionBase):
    """Full species correction with metadata"""
    id: str
    species_id: str
    user_id: Optional[str] = None
    status: FeedbackStatus = FeedbackStatus.PENDING
    created_at: datetime

    class Config:
        from_attributes = True


class FeedbackListResponse(BaseModel):
    """Response for listing feedback"""
    items: List[FeedbackSchema]
    total: int
