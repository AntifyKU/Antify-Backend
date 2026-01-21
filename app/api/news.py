"""
News API Routes
Entomology news from RSS feeds
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import datetime

from app.models.news import (
    NewsItemSchema,
    NewsListResponse,
    NewsRefreshResponse,
)
from app.services.news_scraper import news_scraper
from app.dependencies.auth import get_current_user
from firebase_admin import firestore

router = APIRouter()
db = firestore.client()


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


@router.get("/news", response_model=NewsListResponse)
async def get_news(
    limit: int = Query(20, ge=1, le=50, description="Number of articles to return"),
):
    """
    Get latest entomology news articles.
    
    Returns cached news from Firestore, fetched from RSS feeds.
    """
    try:
        articles = await news_scraper.get_news(limit=limit)
        last_update = await news_scraper.get_last_update()
        
        return NewsListResponse(
            items=articles,
            total=len(articles),
            last_updated=last_update,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news/{article_id}", response_model=NewsItemSchema)
async def get_news_article(article_id: str):
    """Get a single news article by ID"""
    try:
        doc = db.collection("news").document(article_id).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Article not found")
        
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/news/refresh", response_model=NewsRefreshResponse)
async def refresh_news(
    current_user: dict = Depends(require_admin),
):
    """
    Refresh news from RSS feeds (Admin only).
    
    Fetches latest articles from configured RSS sources and updates cache.
    """
    try:
        result = await news_scraper.refresh_news()
        
        return NewsRefreshResponse(
            message="News refreshed successfully",
            items_fetched=result["items_fetched"],
            sources_checked=result["sources_checked"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news/sources/list")
async def list_news_sources():
    """List configured news RSS sources"""
    from app.config import NEWS_RSS_SOURCES
    
    return {
        "sources": NEWS_RSS_SOURCES,
        "count": len(NEWS_RSS_SOURCES),
    }
