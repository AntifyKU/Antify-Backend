"""
News Pydantic Models
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class NewsItemBase(BaseModel):
    """Base news item schema"""
    title: str
    description: str
    link: str
    image: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[datetime] = None


class NewsItemSchema(NewsItemBase):
    """Full news item with ID"""
    id: str

    class Config:
        from_attributes = True


class NewsListResponse(BaseModel):
    """Response for listing news"""
    items: List[NewsItemSchema]
    total: int
    last_updated: Optional[datetime] = None


class NewsRefreshResponse(BaseModel):
    """Response from news refresh"""
    message: str
    items_fetched: int
    sources_checked: int
