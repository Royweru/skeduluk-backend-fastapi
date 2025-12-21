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
    """Helper to ensure platforms is a list"""
    if isinstance(platforms_raw, str):
        try:
            return json.loads(platforms_raw)
        except json.JSONDecodeError:
            # Fallback: split by comma if it's a plain string
            return [p.strip().upper() for p in platforms_raw.split(',') if p.strip()]
    return platforms_raw or []

# Core task logic (async)
async def _publish_post_async(task_self, post_id: int):
    """Publish a post to social platforms - async implementation"""
    engine = create_task_engine()
    AsyncSessionLocal = get_async_session_local(engine)
    
    async with AsyncSessionLocal() as db:
        logger.info(f"Task {task_self.request.id} starting with engine {id(engine)}")
        try:
            # Get post
            post = await PostCRUD.get_post_by_id(db, post_id, None) 
            if not post:
                try:
                    raise task_self.retry(exc=Exception("Post not found, retrying..."), countdown=10)
                except task_self.MaxRetriesExceededError:
                    return {"success": False, "error": "Post not found after retries"}

            # Update status to posting
            await PostCRUD.update_post_status(db, post_id, "posting")
            
            # Get user connections
            connections = await SocialConnectionCRUD.get_connections_by_user(db, post.user_id)
            
            # Filter relevant connections based on post platforms
            post_platforms = deserialize_platforms(post.platforms)
            relevant_connections = [conn for conn in connections if conn.platform in post_platforms]
            
            if not relevant_connections:
                await PostCRUD.update_post_status(
                    db, post_id, "failed", 
                    {"error": "No connected platforms found"}
                )
                await db.commit()
                return {"success": False, "error": "No connected platforms found"}
            
            results = []
            errors = []
            
            # Publish to each platform
            for connection in relevant_connections:
                content = post.original_content
                if post.enhanced_content and connection.platform.lower() in post.enhanced_content:
                    content = post.enhanced_content[connection.platform.lower()]
                
                try:
                    result = await SocialService.publish_to_platform(
                        connection=connection,
                        content=content,
                        image_urls=post.image_urls or [],
                        video_urls=post.video_urls or []
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
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        errors.append(f"{connection.platform}: {error_msg}")
                        results.append({
                            "platform": connection.platform, 
                            "success": False, 
                            "error": error_msg
                        })
                    
                except Exception as e:
                    error_msg = str(e)
                    errors.append(f"{connection.platform}: {error_msg}")
                    results.append({
                        "platform": connection.platform, 
                        "success": False, 
                        "error": error_msg
                    })
                    await PostResultCRUD.create_result(
                        db, post_id, connection.platform, 
                        "failed", None, error_msg, content
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
            
            return {
                "success": success_count > 0,
                "total_platforms": total_platforms,
                "successful": success_count,
                "failed": total_platforms - success_count,
                "results": results,
                "errors": errors if errors else None
            }
            
        except Exception as e:
            print(f"Error in publish_post_task: {str(e)}")
            print(traceback.format_exc())
            
            try:
                await PostCRUD.update_post_status(
                    db, post_id, "failed", 
                    {"error": f"Task error: {str(e)}"}
                )
                await db.commit()
            except Exception as db_exc:
                print(f"Failed to update post status to failed: {db_exc}")
            
            raise task_self.retry(exc=e, countdown=60)
        finally:
            logger.info(f"Task {task_self.request.id} cleaning up engine {id(engine)}")
            await engine.dispose()

# Public task wrapper (synchronous, for Celery)
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