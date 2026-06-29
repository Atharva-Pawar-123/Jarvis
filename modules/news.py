"""
modules/news.py — JARVIS News Module
====================================
Fetches top news headlines using Google News RSS feeds.
"""

import logging
import feedparser

logger = logging.getLogger(__name__)


def get_news(count: int = 5) -> str:
    """
    Fetch the latest news headlines from Google News.
    
    Args:
        count (int): Number of headlines to retrieve.
        
    Returns:
        str: A formatted string of headlines.
    """
    try:
        # Google News RSS for Top Stories
        rss_url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
        
        logger.info(f"Fetching top {count} headlines from Google News RSS...")
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            return "I couldn't find any news updates at the moment, sir."
            
        headlines = []
        for i, entry in enumerate(feed.entries[:count]):
            # Clean up the title (often includes the source at the end)
            title = entry.title
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
            headlines.append(f"Number {i+1}: {title}.")
            
        report = "Sir, here are the top headlines for today:\n" + "\n".join(headlines)
        return report

    except Exception as exc:
        logger.error(f"News fetch error: {exc}")
        return "I apologize, sir, but I'm having trouble connecting to the news feed."
