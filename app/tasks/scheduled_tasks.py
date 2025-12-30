# app/tasks/scheduled_tasks.py
import asyncio
from datetime import datetime
import json
import os
import traceback
from dotenv import load_dotenv
from celery import Task
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from ..celery_app import celery_app
from ..crud import PostCRUD, SocialConnectionCRUD, PostResultCRUD
from ..services.social_service import SocialService
import logging

logger = logging.getLogger(__name__)
# Load environment variables
load_dotenv()

def get_async_database_url():
    """Convert DATABASE_URL to asyncpg format"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Remove query parameters for base URL
    if '?' in database_url:
        base_url = database_url.split('?')[0]
    else:
        base_url = database_url
    
    # Convert to asyncpg format
    if base_url.startswith('postgresql://'):
        return base_url.replace('postgresql://', 'postgresql+asyncpg://')
    elif base_url.startswith('postgres://'):
        return base_url.replace('postgres://', 'postgresql+asyncpg://')
    else:
        return base_url

def create_task_engine():
    """Create a new engine instance for each task to avoid event loop conflicts"""
    return create_async_engine(
        get_async_database_url(),
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={
            "ssl": "require",
            "server_settings": {
                "application_name": "social_scheduler"
            }
        }
    )

def get_async_session_local(engine):
    """Create session maker bound to task-specific engine"""
    return async_sessionmaker(
        engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )

def deserialize_platforms(platforms_raw):
    """Helper to ensure platforms is a list - MORE ROBUST VERSION"""
    if platforms_raw is None:
        return []
    
    if isinstance(platforms_raw, list):
        return [p.strip().upper() for p in platforms_raw if p.strip()]
    
    if isinstance(platforms_raw, str):
        # Try JSON first
        try:
            parsed = json.loads(platforms_raw)
            if isinstance(parsed, list):
                return [p.strip().upper() for p in parsed if p.strip()]
            return []
        except json.JSONDecodeError:
            # Fallback: split by comma
            return [p.strip().upper() for p in platforms_raw.split(',') if p.strip()]
    
    return []

# Core task logic (async)
async def _publish_post_async(task_self, post_id: int):
    """Publish a post to social platforms - async implementation"""
    engine = create_task_engine()
    AsyncSessionLocal = get_async_session_local(engine)
    
    async with AsyncSessionLocal() as db:
        logger.info(f"🚀 Task {task_self.request.id} starting for post {post_id}")
        try:
            # Get post
            post = await PostCRUD.get_post_by_id(db, post_id, None) 
            if not post:
                logger.error(f"❌ Post {post_id} not found in database")
                try:
                    raise task_self.retry(exc=Exception("Post not found, retrying..."), countdown=10)
                except task_self.MaxRetriesExceededError:
                    return {"success": False, "error": "Post not found after retries"}

            # Update status to posting
            await PostCRUD.update_post_status(db, post_id, "posting")
            
            # Get user connections
            connections = await SocialConnectionCRUD.get_connections_by_user(db, post.user_id)
            
            # ✅ FIX: Parse platforms properly
            post_platforms = deserialize_platforms(post.platforms)
            logger.info(f"📋 Post platforms: {post_platforms}")
            logger.info(f"🔗 Available connections: {[c.platform for c in connections]}")
            
            # Filter relevant connections
            relevant_connections = [conn for conn in connections if conn.platform in post_platforms]
            
            if not relevant_connections:
                error_msg = f"No connected platforms found. Post platforms: {post_platforms}, Connected: {[c.platform for c in connections]}"
                logger.error(f"❌ {error_msg}")
                await PostCRUD.update_post_status(
                    db, post_id, "failed", 
                    {"error": error_msg}
                )
                await db.commit()
                return {"success": False, "error": error_msg}
            
            results = []
            errors = []
            
            # Publish to each platform
            for connection in relevant_connections:
                # ✅ Get content (with better error handling)
                content = post.original_content
                
                # Check for enhanced content
                if post.enhanced_content:
                    try:
                        enhanced_dict = json.loads(post.enhanced_content) if isinstance(post.enhanced_content, str) else post.enhanced_content
                        platform_key = connection.platform.lower()
                        
                        if enhanced_dict and platform_key in enhanced_dict:
                            content = enhanced_dict[platform_key]
                            logger.info(f"📝 Using enhanced content for {connection.platform}")
                    except Exception as parse_err:
                        logger.warning(f"⚠️ Could not parse enhanced_content: {parse_err}")
                        # Continue with original content
                
                # ✅ Parse media URLs
                image_urls = []
                video_urls = []
                
                try:
                    if post.image_urls:
                        image_urls = json.loads(post.image_urls) if isinstance(post.image_urls, str) else post.image_urls or []
                    
                    if post.video_urls:
                        video_urls = json.loads(post.video_urls) if isinstance(post.video_urls, str) else post.video_urls or []
                    
                    logger.info(f"📸 Media for {connection.platform}: {len(image_urls)} images, {len(video_urls)} videos")
                except Exception as media_err:
                    logger.warning(f"⚠️ Could not parse media URLs: {media_err}")
                    image_urls = []
                    video_urls = []
                
                try:
                    result = await SocialService.publish_to_platform(
                        connection=connection,
                        content=content,
                        image_urls=image_urls,
                        video_urls=video_urls,
                        db=db
                    )
                    
                    await PostResultCRUD.create_result(
                        db, post_id, connection.platform,
                        "posted" if result.get("success") else "failed",
                        result.get("platform_post_id"),
                        result.get("platform_post_url"),
                        result.get("error"),
                        content
                    )
                    
                    if result.get("success"):
                        results.append({
                            "platform": connection.platform, 
                            "success": True, 
                            "post_id": result.get("platform_post_id"),
                            "url": result.get("url")
                        })
                        logger.info(f"✅ Published to {connection.platform}")
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        errors.append(f"{connection.platform}: {error_msg}")
                        results.append({
                            "platform": connection.platform, 
                            "success": False, 
                            "error": error_msg
                        })
                        logger.error(f"❌ Failed to publish to {connection.platform}: {error_msg}")
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"❌ Exception publishing to {connection.platform}: {error_msg}")
                    errors.append(f"{connection.platform}: {error_msg}")
                    results.append({
                        "platform": connection.platform, 
                        "success": False, 
                        "error": error_msg
                    })
                    await PostResultCRUD.create_result(
                        db, post_id, connection.platform, 
                        "failed", None, None, error_msg, content
                    )
            
            success_count = sum(1 for r in results if r.get("success"))
            total_platforms = len(results)
            
            # Determine final status
            final_status = "posted" if success_count == total_platforms else \
                          "partial" if success_count > 0 else "failed"
            
            # Update post status
            await PostCRUD.update_post_status(
                db, post_id, final_status, 
                {"errors": "; ".join(errors)} if errors else None,
                {r["platform"]: r.get("url") for r in results if r.get("url")}
            )
            
            await db.commit()
            
            logger.info(f"✅ Task completed: {success_count}/{total_platforms} platforms succeeded")
            
            return {
                "success": success_count > 0,
                "total_platforms": total_platforms,
                "successful": success_count,
                "failed": total_platforms - success_count,
                "results": results,
                "errors": errors if errors else None
            }
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR in publish_post_task for post {post_id}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {str(e)}")
            logger.error(f"Full traceback:")
            import traceback
            logger.error(traceback.format_exc())
            
            try:
                await PostCRUD.update_post_status(
                    db, post_id, "failed", 
                    {"error": f"Task error: {str(e)}"}
                )
                await db.commit()
            except Exception as db_exc:
                logger.error(f"❌ Failed to update post status: {db_exc}")
            
            # ✅ Don't retry if it's a data parsing error
            if isinstance(e, (json.JSONDecodeError, KeyError, AttributeError, TypeError)):
                logger.error(f"❌ Data error - not retrying: {type(e).__name__}")
                return {
                    "success": False,
                    "error": f"Data error: {str(e)}. Check post data format."
                }
            
            # Retry for other errors (network, API issues, etc.)
            raise task_self.retry(exc=e, countdown=60)
        finally:
            logger.info(f"🧹 Cleaning up engine for task {task_self.request.id}")
            await engine.dispose()
@celery_app.task(bind=True, max_retries=3)
def publish_post_task(self, post_id: int):
    """Publish a post to social platforms"""
    return asyncio.run(_publish_post_async(self, post_id))

# Second task - check scheduled posts
async def _check_scheduled_async():
    """Check for posts that need to be published - async implementation"""
    engine = create_task_engine()
    AsyncSessionLocal = get_async_session_local(engine)
    
    async with AsyncSessionLocal() as db:
        try:
            # Get all scheduled posts ready to be published
            posts = await PostCRUD.get_scheduled_posts(db, limit=50)
            print(f"Found {len(posts)} posts to publish")
            
            # Queue each post for publishing
            for post in posts:
                publish_post_task.delay(post.id)
            
            return {"checked_posts": len(posts), "queued": len(posts)}
        except Exception as e:
            print(f"Error in check_scheduled_posts: {e}")
            return {"success": False, "error": str(e)}
        finally:
            await engine.dispose()

@celery_app.task
def check_scheduled_posts():
    """Check for posts that need to be published"""
    return asyncio.run(_check_scheduled_async())