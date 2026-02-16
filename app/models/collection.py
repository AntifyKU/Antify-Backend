"""
Collection and Favorites Pydantic Models
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# FOLDER SCHEMAS

class FolderBase(BaseModel):
    """Base schema for folders"""
    name: str = Field(..., min_length=1, max_length=50, description="Folder name")
    color: str = Field("#22A45D", description="Hex color code for the folder")
    icon: str = Field("folder", description="Ionicon name for the folder")


class FolderCreate(FolderBase):
    """Schema for creating a folder"""
    pass

    class Config:
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

# NEWS FAVORITES SCHEMAS

class FavoriteNewsBase(BaseModel):
    """Base schema for favorite news items"""
    news_id: str = Field(..., description="ID of the news item")


class FavoriteNewsCreate(FavoriteNewsBase):
    """Schema for adding news to favorites"""
    pass

    class Config:
        json_schema_extra = {
            "example": {
                "news_id": "news_123456"
            }
        }


class FavoriteNewsSchema(FavoriteNewsBase):
    """Full favorite news item with metadata"""
    id: str
    user_id: str
    added_at: datetime
    # News details (populated from news collection)
    news_title: Optional[str] = None
    news_description: Optional[str] = None
    news_link: Optional[str] = None
    news_image: Optional[str] = None
    news_source: Optional[str] = None
    news_published_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FavoriteNewsListResponse(BaseModel):
    """Response for listing favorite news"""
    items: List[FavoriteNewsSchema]
    total: int


class CheckFavoriteNewsResponse(BaseModel):
    """Response for checking if news is favorited"""
    is_favorite: bool
    favorite_id: Optional[str] = None
