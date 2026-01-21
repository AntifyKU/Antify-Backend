#!/usr/bin/env python3
"""
Manually refresh news from RSS feeds
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

import firebase_admin
from firebase_admin import credentials

# Initialize Firebase if not already done
if not firebase_admin._apps:
    cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS"))
    firebase_admin.initialize_app(cred)

from app.services.news_scraper import news_scraper

async def main():
    print("Refreshing news from RSS feeds...")
    result = await news_scraper.refresh_news()
    print(f"Fetched {result['items_fetched']} articles from {result['sources_checked']} sources")
    
    # Get and display articles
    print("\nLatest articles:")
    articles = await news_scraper.get_news(limit=10)
    for i, a in enumerate(articles, 1):
        title = a.get("title", "No title")[:70]
        source = a.get("source", "Unknown")
        print(f"  {i}. [{source}] {title}...")
    
    print(f"\nTotal articles in database: {len(articles)}")

if __name__ == "__main__":
    asyncio.run(main())
