"""
Collection and Favorites Pydantic Models
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# FOLDER SCHEMAS
class FolderBase(BaseModel):
    """Base schema for folders"""
    name: str = Field(..., min_length=1, max_length=50, description="Folder name")
    color: str = Field("#22A45D", description="Hex color code for the folder")
    icon: str = Field("folder", description="Ionicon name for the folder")


class FolderCreate(FolderBase):
    """Schema for creating a folder"""

    class Config:
        """Example Format"""
        json_schema_extra = {
            "example": {
                "name": "Garden Ants",
                "color": "#22A45D",
                "icon": "leaf"
            }
        }


class FolderUpdate(BaseModel):
    """Schema for updating a folder"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = None
    icon: Optional[str] = None


class FolderSchema(FolderBase):
    """Full folder with metadata"""
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    item_count: int = 0  # Computed: number of items in this folder

    class Config:
        """Example Format"""
        from_attributes = True


class FolderListResponse(BaseModel):
    """Response for listing folders"""
    folders: List[FolderSchema]
    total: int


class AddToFoldersRequest(BaseModel):
    """Request to add an item to folders"""
    folder_ids: List[str] = Field(..., description="List of folder IDs to add the item to")


# COLLECTION SCHEMAS
class CollectionItemBase(BaseModel):
    """Base schema for collection items"""
    species_id: str = Field(..., description="ID of the species")
    notes: Optional[str] = Field(None, description="User's notes about this specimen")
    location_found: Optional[str] = Field(None, description="Where the user found this ant")
    user_image_url: Optional[str] = Field(None, description="User's own photo of the ant")


class CollectionItemCreate(CollectionItemBase):
    """Schema for adding to collection"""
    folder_ids: List[str] = Field(default=[], description="List of folder IDs to add this item to")

    class Config:
        """Example Format"""
        json_schema_extra = {
            "example": {
                "species_id": "2",
                "notes": "Found in my backyard mango tree",
                "location_found": "Bangkok, Thailand",
                "user_image_url": None,
                "folder_ids": []
            }
        }


class CollectionItemSchema(CollectionItemBase):
    """Full collection item with metadata"""
    id: str
    user_id: str
    added_at: datetime
    folder_ids: List[str] = []  # List of folder IDs this item belongs to
    # Species details (populated from species collection)
    species_name: Optional[str] = None
    species_scientific_name: Optional[str] = None
    species_image: Optional[str] = None

    class Config:
        """Example Format"""
        from_attributes = True


class CollectionListResponse(BaseModel):
    """Response for listing collection items"""
    items: List[CollectionItemSchema]
    total: int
