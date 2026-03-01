import asyncio
import aiohttp
import feedparser
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse
import hashlib
import re

from ...config import settings


class RSSFetcher:
    DEFAULT_FEEDS = [
        "https://feeds.npr.org/1001/rss.xml",
        "https://www.reddit.com/r/stories/.rss",
        "https://www.reddit.com/r/nosleep/.rss",
    ]

    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=30)

    def _clean_html(self, text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _generate_id(self, url: str, title: str) -> str:
        unique_string = f"{url}:{title}"
        return hashlib.md5(unique_string.encode()).hexdigest()[:12]

    async def fetch_feed(
        self,
        feed_url: str,
        limit: int = 20,
        max_age_hours: int = 24,
        keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
        min_content_length: int = 200,
    ) -> List[Dict[str, Any]]:
        entries = []

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(feed_url) as response:
                    if response.status != 200:
                        print(f"Failed to fetch RSS feed {feed_url}: {response.status}")
                        return []

                    content = await response.text()

            feed = feedparser.parse(content)

            for entry in feed.entries[:limit]:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6])
                else:
                    published = datetime.now()

                if max_age_hours:
                    if datetime.now() - published > timedelta(hours=max_age_hours):
                        continue

                title = entry.get("title", "")

                content = ""
                if hasattr(entry, "content") and entry.content:
                    content = entry.content[0].get("value", "")
                elif hasattr(entry, "summary"):
                    content = entry.summary
                elif hasattr(entry, "description"):
                    content = entry.description

                content = self._clean_html(content)

                if len(content) < min_content_length:
                    continue

                if keywords:
                    if not any(
                        kw.lower() in title.lower() or kw.lower() in content.lower()
                        for kw in keywords
                    ):
                        continue

                if exclude_keywords:
                    if any(
                        kw.lower() in title.lower() or kw.lower() in content.lower()
                        for kw in exclude_keywords
                    ):
                        continue

                source_domain = urlparse(feed_url).netloc

                entries.append(
                    {
                        "rss_id": self._generate_id(entry.get("link", ""), title),
                        "title": title,
                        "content": content,
                        "author": entry.get("author", "Unknown"),
                        "source": feed.get("feed", {}).get("title", source_domain),
                        "source_domain": source_domain,
                        "url": entry.get("link", ""),
                        "published_at": published.isoformat(),
                        "source_type": "rss",
                        "score": 0,
                        "num_comments": 0,
                    }
                )

        except Exception as e:
            print(f"Error fetching RSS feed {feed_url}: {e}")

        return entries

    async def fetch_multiple_feeds(
        self,
        feed_urls: List[str],
        limit_per_feed: int = 10,
        max_age_hours: int = 24,
        keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        tasks = [
            self.fetch_feed(
                feed_url=url,
                limit=limit_per_feed,
                max_age_hours=max_age_hours,
                keywords=keywords,
                exclude_keywords=exclude_keywords,
            )
            for url in feed_urls
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_entries = []
        for result in results:
            if isinstance(result, list):
                all_entries.extend(result)

        all_entries.sort(key=lambda x: x.get("published_at", ""), reverse=True)

        return all_entries

    async def fetch_story_feeds(
        self, custom_feeds: Optional[List[str]] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        story_feeds = custom_feeds or [
            "https://www.reddit.com/r/stories/.rss",
            "https://www.reddit.com/r/nosleep/.rss",
            "https://www.reddit.com/r/confessions/.rss",
        ]

        return await self.fetch_multiple_feeds(
            feed_urls=story_feeds,
            limit_per_feed=limit // len(story_feeds) + 1,
            min_content_length=300,
        )

    async def fetch_news_feeds(
        self,
        custom_feeds: Optional[List[str]] = None,
        limit: int = 20,
        keywords: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        news_feeds = custom_feeds or [
            "https://feeds.npr.org/1001/rss.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        ]

        return await self.fetch_multiple_feeds(
            feed_urls=news_feeds,
            limit_per_feed=limit // len(news_feeds) + 1,
            keywords=keywords,
            min_content_length=200,
        )


rss_fetcher = RSSFetcher()
