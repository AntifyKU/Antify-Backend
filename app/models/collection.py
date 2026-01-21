"""
Collection and Favorites Pydantic Models
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CollectionItemBase(BaseModel):
    """Base schema for collection items"""
    species_id: str = Field(..., description="ID of the species")
    notes: Optional[str] = Field(None, description="User's notes about this specimen")
    location_found: Optional[str] = Field(None, description="Where the user found this ant")
    user_image_url: Optional[str] = Field(None, description="User's own photo of the ant")


class CollectionItemCreate(CollectionItemBase):
    """Schema for adding to collection"""
    pass

    class Config:
        json_schema_extra = {
            "example": {
                "species_id": "2",
                "notes": "Found in my backyard mango tree",
                "location_found": "Bangkok, Thailand",
                "user_image_url": None
            }
        }


class CollectionItemSchema(CollectionItemBase):
    """Full collection item with metadata"""
    id: str
    user_id: str
    added_at: datetime
    # Species details (populated from species collection)
    species_name: Optional[str] = None
    species_scientific_name: Optional[str] = None
    species_image: Optional[str] = None

    class Config:
        from_attributes = True


class CollectionListResponse(BaseModel):
    """Response for listing collection items"""
    items: List[CollectionItemSchema]
    total: int


class FavoriteItemBase(BaseModel):
    """Base schema for favorite items"""
    species_id: str = Field(..., description="ID of the species")


class FavoriteItemCreate(FavoriteItemBase):
    """Schema for adding to favorites"""
    pass

    class Config:
        json_schema_extra = {
            "example": {
                "species_id": "2"
            }
        }


class FavoriteItemSchema(FavoriteItemBase):
    """Full favorite item with metadata"""
    id: str
    user_id: str
    added_at: datetime
    # Species details (populated from species collection)
    species_name: Optional[str] = None
    species_scientific_name: Optional[str] = None
    species_image: Optional[str] = None
    species_about: Optional[str] = None

    class Config:
        from_attributes = True


class FavoriteListResponse(BaseModel):
    """Response for listing favorites"""
    items: List[FavoriteItemSchema]
    total: int
