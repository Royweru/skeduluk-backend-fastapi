# app/tasks/scheduled_tasks.py
"""
Celery tasks for scheduled post publishing.
Updated to use refactored platform services.
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any

from app.celery_app import celery_app
from app import models, crud
from app.services.social_service import SocialService
from app.database import create_task_engine, get_async_session_local


async def publish_post_async(post_id: int) -> Dict[str, Any]:
    """
    Async function to publish a post to all selected platforms.
    Uses the refactored SocialService orchestrator.
    """
    # Create task-specific engine
    engine = create_task_engine()
    AsyncSessionLocal = get_async_session_local(engine)
    
    try:
        async with AsyncSessionLocal() as db:
            # Get post
            post = await crud.PostCRUD.get_post_by_id(db, post_id)
            if not post:
                print(f"❌ Post {post_id} not found")
                return {
                    "success": False,
                    "error": "Post not found"
                }
            
            # Parse platforms
            if isinstance(post.platforms, str):
                try:
                    platforms = json.loads(post.platforms)
                except:
                    platforms = [p.strip() for p in post.platforms.split(',')]
            else:
                platforms = post.platforms
            
            print(f"\n{'='*60}")
            print(f"📤 Publishing Post #{post_id}")
            print(f"📝 Content: {post.original_content[:50]}...")
            print(f"🎯 Platforms: {', '.join(platforms)}")
            print(f"{'='*60}\n")
            
            # Update status to posting
            await crud.PostCRUD.update_post_status(db, post_id, "posting")
            await db.commit()
            
            # Get connections for selected platforms
            connections: List[models.SocialConnection] = []
            for platform in platforms:
                conn = await crud.SocialConnectionCRUD.get_connection_by_platform(
                    db, post.user_id, platform.upper()
                )
                if conn:
                    connections.append(conn)
                else:
                    print(f"⚠️  No connection found for {platform}")
            
            if not connections:
                await crud.PostCRUD.update_post_status(
                    db, post_id, "failed",
                    error_messages={"error": "No active connections found"}
                )
                await db.commit()
                return {
                    "success": False,
                    "error": "No active connections"
                }
            
            # Parse enhanced content (platform-specific)
            platform_specific = None
            if post.enhanced_content:
                if isinstance(post.enhanced_content, str):
                    try:
                        platform_specific = json.loads(post.enhanced_content)
                    except:
                        platform_specific = None
                else:
                    platform_specific = post.enhanced_content
            
            # Parse media URLs
            image_urls = []
            video_urls = []
            
            if post.image_urls:
                if isinstance(post.image_urls, str):
                    try:
                        image_urls = json.loads(post.image_urls)
                    except:
                        image_urls = []
                else:
                    image_urls = post.image_urls
            
            if post.video_urls:
                if isinstance(post.video_urls, str):
                    try:
                        video_urls = json.loads(post.video_urls)
                    except:
                        video_urls = []
                else:
                    video_urls = post.video_urls
            
            print(f"🖼️  Images: {len(image_urls)}")
            print(f"🎬 Videos: {len(video_urls)}")
            
            # Publish to all platforms
            result = await SocialService.publish_to_multiple_platforms(
                connections=connections,
                content=post.original_content,
                image_urls=image_urls,
                video_urls=video_urls,
                platform_specific_content=platform_specific,
                db=db
            )
            
            # Save individual results
            for platform_result in result["results"]:
                platform = platform_result["platform"]
                success = platform_result.get("success", False)
                
                await crud.PostResultCRUD.create_result(
                    db=db,
                    post_id=post_id,
                    platform=platform,
                    status="posted" if success else "failed",
                    platform_post_id=platform_result.get("platform_post_id"),
                    platform_post_url=platform_result.get("url"),
                    error_message=platform_result.get("error"),
                    content_used=platform_specific.get(platform.lower()) if platform_specific else post.original_content
                )
            
            # Update post status
            if result["successful"] > 0:
                final_status = "posted" if result["failed"] == 0 else "partial"
            else:
                final_status = "failed"
            
            await crud.PostCRUD.update_post_status(
                db, post_id, final_status
            )
            await db.commit()
            
            print(f"\n{'='*60}")
            print(f"✅ Task completed: {result['successful']}/{result['total_platforms']} platforms succeeded")
            print(f"{'='*60}\n")
            
            return result
            
    except Exception as e:
        print(f"❌ Error publishing post {post_id}: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            async with AsyncSessionLocal() as db:
                await crud.PostCRUD.update_post_status(
                    db, post_id, "failed",
                    error_messages={"error": str(e)}
                )
                await db.commit()
        except:
            pass
        
        return {
            "success": False,
            "error": str(e)
        }
    
    finally:
        # Clean up engine
        await engine.dispose()


@celery_app.task(name="app.tasks.scheduled_tasks.publish_post_task")
def publish_post_task(post_id: int) -> Dict[str, Any]:
    """
    Celery task to publish a post.
    Wrapper around async function.
    """
    print(f"\n🚀 Starting publish task for post {post_id}")
    
    try:
        # Run async function in event loop
        result = asyncio.run(publish_post_async(post_id))
        return result
    except Exception as e:
        print(f"❌ Task error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


@celery_app.task(name="app.tasks.scheduled_tasks.check_scheduled_posts")
def check_scheduled_posts():
    """
    Periodic task to check for scheduled posts that need to be published.
    Runs every minute.
    """
    print("🔍 Checking for scheduled posts...")
    
    async def check_async():
        engine = create_task_engine()
        AsyncSessionLocal = get_async_session_local(engine)
        
        try:
            async with AsyncSessionLocal() as db:
                # Get posts that are scheduled and ready
                posts = await crud.PostCRUD.get_scheduled_posts(db, limit=50)
                
                if not posts:
                    print("✓ No scheduled posts ready for publishing")
                    return
                
                print(f"📋 Found {len(posts)} posts ready for publishing")
                
                # Queue each post for publishing
                for post in posts:
                    print(f"📤 Queueing post {post.id} for publishing")
                    publish_post_task.delay(post.id)
                
        finally:
            await engine.dispose()
    
    try:
        asyncio.run(check_async())
    except Exception as e:
        print(f"❌ Error checking scheduled posts: {e}")
        import traceback
        traceback.print_exc()