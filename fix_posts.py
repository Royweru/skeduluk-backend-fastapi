# Fix existing posts with lowercase platforms
# Run this once in a Python shell or create a migration script

from sqlalchemy import select, update
from app.database import AsyncSessionLocal
from app.models import Post
import json
import asyncio

async def fix_existing_posts():
    async with AsyncSessionLocal() as db:
        # Get all posts
        result = await db.execute(select(Post))
        posts = result.scalars().all()
        
        for post in posts:
            if isinstance(post.platforms, str):
                platforms = json.loads(post.platforms)
                # Normalize to uppercase
                normalized = [p.upper() for p in platforms]
                post.platforms = json.dumps(normalized)
                print(f"Fixed post {post.id}: {platforms} -> {normalized}")
        
        await db.commit()
        print("✅ All posts fixed!")

# Run it
asyncio.run(fix_existing_posts())