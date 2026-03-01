import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import os

from ...config import settings


class RedditFetcher:
    DEFAULT_SUBREDDITS = [
        "stories",
        "nosleep",
        "todayilearned",
        "confessions",
        "askreddit",
        "tifu",
        "relationship_advice",
        "AITA",
        "entitledparents",
        "maliciouscompliance",
    ]

    STORY_SUBREDDITS = ["nosleep", "stories", "confessions", "tifu"]
    DISCUSSION_SUBREDDITS = ["askreddit", "todayilearned", "relationship_advice"]

    def __init__(self):
        self.client_id = settings.REDDIT_CLIENT_ID
        self.client_secret = settings.REDDIT_CLIENT_SECRET
        self.user_agent = settings.REDDIT_USER_AGENT
        self.base_url = "https://www.reddit.com"
        self.oauth_url = "https://oauth.reddit.com"
        self._access_token = None
        self._token_expires = None

    async def _get_access_token(self) -> str:
        if (
            self._access_token
            and self._token_expires
            and datetime.now() < self._token_expires
        ):
            return self._access_token

        if not self.client_id or not self.client_secret:
            print("Reddit API credentials not configured, using anonymous access")
            return None

        auth = aiohttp.BasicAuth(self.client_id, self.client_secret)
        data = {"grant_type": "client_credentials"}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/v1/access_token",
                auth=auth,
                data=data,
                headers={"User-Agent": self.user_agent},
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self._access_token = result["access_token"]
                    self._token_expires = datetime.now() + timedelta(
                        seconds=result["expires_in"] - 60
                    )
                    return self._access_token
                else:
                    print(f"Failed to get Reddit access token: {response.status}")
                    return None

    async def fetch_posts(
        self,
        subreddit: str,
        limit: int = 25,
        timeframe: str = "day",
        min_score: int = 100,
        keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
        max_age_hours: int = 24,
    ) -> List[Dict[str, Any]]:
        access_token = await self._get_access_token()

        headers = {"User-Agent": self.user_agent}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
            url = f"{self.oauth_url}/r/{subreddit}/hot"
        else:
            url = f"{self.base_url}/r/{subreddit}/hot.json"

        params = {"limit": limit, "t": timeframe}

        posts = []

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    print(f"Failed to fetch from r/{subreddit}: {response.status}")
                    return []

                data = await response.json()

                for child in data.get("data", {}).get("children", []):
                    post_data = child.get("data", {})

                    if post_data.get("score", 0) < min_score:
                        continue

                    created_utc = datetime.fromtimestamp(
                        post_data.get("created_utc", 0)
                    )
                    if datetime.now() - created_utc > timedelta(hours=max_age_hours):
                        continue

                    title = post_data.get("title", "")
                    selftext = post_data.get("selftext", "")

                    if keywords:
                        if not any(
                            kw.lower() in title.lower()
                            or kw.lower() in selftext.lower()
                            for kw in keywords
                        ):
                            continue

                    if exclude_keywords:
                        if any(
                            kw.lower() in title.lower()
                            or kw.lower() in selftext.lower()
                            for kw in exclude_keywords
                        ):
                            continue

                    if len(selftext) < 100:
                        continue

                    posts.append(
                        {
                            "reddit_id": post_data.get("id"),
                            "title": title,
                            "content": selftext,
                            "author": post_data.get("author", "[deleted]"),
                            "subreddit": post_data.get("subreddit"),
                            "score": post_data.get("score", 0),
                            "num_comments": post_data.get("num_comments", 0),
                            "url": f"https://reddit.com{post_data.get('permalink', '')}",
                            "created_at": created_utc.isoformat(),
                            "source_type": "reddit",
                        }
                    )

        return posts

    async def fetch_best_stories(
        self,
        subreddits: Optional[List[str]] = None,
        limit_per_subreddit: int = 10,
        min_score: int = 500,
        keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        subreddits = subreddits or self.STORY_SUBREDDITS
        all_posts = []

        tasks = [
            self.fetch_posts(
                subreddit=sr,
                limit=limit_per_subreddit,
                min_score=min_score,
                keywords=keywords,
                exclude_keywords=exclude_keywords,
            )
            for sr in subreddits
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_posts.extend(result)

        all_posts.sort(key=lambda x: x["score"], reverse=True)

        return all_posts

    async def fetch_askreddit_threads(
        self, limit: int = 20, min_score: int = 1000
    ) -> List[Dict[str, Any]]:
        posts = await self.fetch_posts(
            subreddit="AskReddit", limit=limit, min_score=min_score
        )

        for post in posts:
            if "?" in post["title"]:
                post["is_question"] = True

        return posts

    async def search_stories(
        self,
        query: str,
        subreddit: Optional[str] = None,
        limit: int = 25,
        min_score: int = 100,
    ) -> List[Dict[str, Any]]:
        access_token = await self._get_access_token()

        headers = {"User-Agent": self.user_agent}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
            url = f"{self.oauth_url}/search"
        else:
            url = f"{self.base_url}/search.json"

        params = {"q": query, "limit": limit, "sort": "relevance", "type": "link"}

        if subreddit:
            params["subreddit"] = subreddit

        posts = []

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    return []

                data = await response.json()

                for child in data.get("data", {}).get("children", []):
                    post_data = child.get("data", {})

                    if post_data.get("score", 0) < min_score:
                        continue

                    posts.append(
                        {
                            "reddit_id": post_data.get("id"),
                            "title": post_data.get("title"),
                            "content": post_data.get("selftext", ""),
                            "author": post_data.get("author", "[deleted]"),
                            "subreddit": post_data.get("subreddit"),
                            "score": post_data.get("score", 0),
                            "num_comments": post_data.get("num_comments", 0),
                            "url": f"https://reddit.com{post_data.get('permalink', '')}",
                            "source_type": "reddit",
                        }
                    )

        return posts


reddit_fetcher = RedditFetcher()
