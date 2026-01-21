"""
News RSS Scraper Service
Fetches and parses RSS feeds from entomology news sources
"""
import feedparser
import hashlib
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import httpx

from firebase_admin import firestore
from app.config import NEWS_RSS_SOURCES

db = firestore.client()
NEWS_COLLECTION = "news"
NEWS_META_COLLECTION = "news_meta"


# Keywords to filter for insect/ant-related content
INSECT_KEYWORDS = [
    "ant", "ants", "insect", "insects", "entomology", "myrmecology",
    "formicidae", "colony", "colonies", "pest", "invasive", "arthropod",
    "beetle", "bee", "wasp", "termite", "bug", "invertebrate",
    "species", "larvae", "queen", "worker", "swarm",
]


def extract_image_from_content(content: str) -> Optional[str]:
    """Extract first image URL from HTML content"""
    if not content:
        return None
    
    soup = BeautifulSoup(content, "html.parser")
    
    # Try to find img tag
    img = soup.find("img")
    if img and img.get("src"):
        return img["src"]
    
    # Try to find media:thumbnail or enclosure
    return None


def extract_image_from_entry(entry: Dict[str, Any]) -> Optional[str]:
    """Extract image URL from RSS entry"""
    # Check media_thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")
    
    # Check media_content
    if hasattr(entry, "media_content") and entry.media_content:
        for media in entry.media_content:
            if media.get("type", "").startswith("image/"):
                return media.get("url")
    
    # Check enclosures
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enclosure in entry.enclosures:
            if enclosure.get("type", "").startswith("image/"):
                return enclosure.get("href") or enclosure.get("url")
    
    # Check for image in content
    content = ""
    if hasattr(entry, "content") and entry.content:
        content = entry.content[0].get("value", "")
    elif hasattr(entry, "summary"):
        content = entry.summary or ""
    
    return extract_image_from_content(content)


def clean_html(html_content: str) -> str:
    """Strip HTML tags and clean text"""
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator=" ")
    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_relevant_article(title: str, description: str) -> bool:
    """Check if article is relevant to insects/ants"""
    combined_text = f"{title} {description}".lower()
    return any(keyword in combined_text for keyword in INSECT_KEYWORDS)


def generate_article_id(link: str) -> str:
    """Generate unique ID from article link"""
    return hashlib.md5(link.encode()).hexdigest()[:16]


def parse_date(entry: Dict[str, Any]) -> Optional[datetime]:
    """Parse publication date from entry"""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6])
        except Exception:
            pass
    
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6])
        except Exception:
            pass
    
    return None


async def fetch_rss_feed(url: str) -> List[Dict[str, Any]]:
    """Fetch and parse a single RSS feed"""
    articles = []
    
    try:
        # Use httpx for async fetching
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.text
        
        # Parse RSS feed
        feed = feedparser.parse(content)
        source_name = feed.feed.get("title", url)
        
        for entry in feed.entries:
            title = entry.get("title", "")
            
            # Get description/summary
            description = ""
            if hasattr(entry, "summary"):
                description = clean_html(entry.summary or "")
            elif hasattr(entry, "description"):
                description = clean_html(entry.description or "")
            
            # Skip non-relevant articles (optional - can be removed to get all articles)
            # if not is_relevant_article(title, description):
            #     continue
            
            link = entry.get("link", "")
            if not link:
                continue
            
            article = {
                "id": generate_article_id(link),
                "title": title,
                "description": description[:500] if description else "",  # Limit length
                "link": link,
                "image": extract_image_from_entry(entry),
                "source": source_name,
                "published_at": parse_date(entry),
            }
            articles.append(article)
        
    except Exception as e:
        print(f"Error fetching RSS feed {url}: {e}")
    
    return articles


async def fetch_all_news() -> List[Dict[str, Any]]:
    """Fetch news from all configured RSS sources"""
    all_articles = []
    
    for source_url in NEWS_RSS_SOURCES:
        articles = await fetch_rss_feed(source_url.strip())
        all_articles.extend(articles)
    
    # Sort by published date (newest first)
    all_articles.sort(
        key=lambda x: x.get("published_at") or datetime.min,
        reverse=True
    )
    
    return all_articles


async def save_news_to_firestore(articles: List[Dict[str, Any]]) -> int:
    """Save news articles to Firestore"""
    if not articles:
        return 0
    
    batch = db.batch()
    count = 0
    
    for article in articles[:50]:  # Limit to 50 most recent
        doc_ref = db.collection(NEWS_COLLECTION).document(article["id"])
        
        # Convert datetime for Firestore
        article_data = article.copy()
        if article_data.get("published_at"):
            article_data["published_at"] = article_data["published_at"]
        
        article_data["fetched_at"] = datetime.utcnow()
        
        batch.set(doc_ref, article_data, merge=True)
        count += 1
    
    # Update metadata
    meta_ref = db.collection(NEWS_META_COLLECTION).document("last_update")
    batch.set(meta_ref, {
        "last_updated": datetime.utcnow(),
        "article_count": count,
        "sources_checked": len(NEWS_RSS_SOURCES),
    })
    
    batch.commit()
    return count


async def get_cached_news(limit: int = 20) -> List[Dict[str, Any]]:
    """Get news from Firestore cache"""
    try:
        docs = (
            db.collection(NEWS_COLLECTION)
            .order_by("published_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        
        articles = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            articles.append(data)
        
        return articles
    except Exception as e:
        print(f"Error getting cached news: {e}")
        return []


async def get_last_update_time() -> Optional[datetime]:
    """Get the last time news was refreshed"""
    try:
        doc = db.collection(NEWS_META_COLLECTION).document("last_update").get()
        if doc.exists:
            return doc.to_dict().get("last_updated")
    except Exception:
        pass
    return None


class NewsScraperService:
    """Service for managing news scraping"""
    
    async def refresh_news(self) -> Dict[str, Any]:
        """Fetch fresh news and save to Firestore"""
        articles = await fetch_all_news()
        count = await save_news_to_firestore(articles)
        
        return {
            "items_fetched": count,
            "sources_checked": len(NEWS_RSS_SOURCES),
        }
    
    async def get_news(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get news articles"""
        return await get_cached_news(limit)
    
    async def get_last_update(self) -> Optional[datetime]:
        """Get last update time"""
        return await get_last_update_time()


# Singleton instance
news_scraper = NewsScraperService()
