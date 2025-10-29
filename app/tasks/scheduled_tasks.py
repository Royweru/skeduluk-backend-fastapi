# app/tasks/scheduled_tasks.py
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from ..celery_app import celery_app
from ..database import get_async_database_url
from ..database import AsyncSessionLocal
from ..crud import PostCRUD,SocialConnectionCRUD,PostResultCRUD,SubscriptionCRUD
from ..services.social_service import SocialService
@celery_app.task
def publish_post_task(post_id: int):
    """Publish a post to social platforms"""
    import asyncio
    
    async def _publish_post():
        # Create a new async engine for this task
        engine = create_async_engine(get_async_database_url())
        async with AsyncSessionLocal(engine) as db:
            try:
                # Get post
                post = await PostCRUD.get_post_by_id(db, post_id, None)  # No user check for background task
                if not post:
                    return {"success": False, "error": "Post not found"}
                
                # Update status to posting
                await PostCRUD.update_post_status(db, post_id, "posting")
                
                # Get user's social connections
                connections = await SocialConnectionCRUD.get_connections_by_user(
                    db, post.user_id
                )
                
                # Filter connections for the platforms in the post
                relevant_connections = [
                    conn for conn in connections 
                    if conn.platform in post.platforms
                ]
                
                results = []
                errors = []
                
                # Post to each platform
                for connection in relevant_connections:
                    try:
                        # Get content for this platform
                        content = post.original_content
                        if post.enhanced_content and connection.platform.lower() in post.enhanced_content:
                            content = post.enhanced_content[connection.platform.lower()]
                        
                        # Publish to platform
                        result = await SocialService.publish_to_platform(
                            connection=connection,
                            content=content,
                            image_urls=post.image_urls or []
                        )
                        
                        # Store result
                        await PostResultCRUD.create_result(
                            db, post_id, connection.platform,
                            "posted" if result.get("success") else "failed",
                            result.get("platform_post_id"),
                            result.get("error"),
                            content
                        )
                        
                        if result.get("success"):
                            results.append({"platform": connection.platform, "success": True})
                        else:
                            errors.append(f"{connection.platform}: {result.get('error')}")
                            results.append({"platform": connection.platform, "success": False, "error": result.get("error")})
                        
                    except Exception as e:
                        errors.append(f"{connection.platform}: {str(e)}")
                        results.append({"platform": connection.platform, "success": False, "error": str(e)})
                        
                        # Store error result
                        await PostResultCRUD.create_result(
                            db, post_id, connection.platform,
                            "failed", None, str(e), content
                        )
                
                # Update post status
                success_count = sum(1 for r in results if r["success"])
                if success_count == len(results):
                    await PostCRUD.update_post_status(db, post_id, "posted")
                elif success_count > 0:
                    await PostCRUD.update_post_status(db, post_id, "partial", "; ".join(errors))
                else:
                    await PostCRUD.update_post_status(db, post_id, "failed", "; ".join(errors))
                
                return {
                    "success": success_count > 0,
                    "results": results,
                    "errors": errors
                }
                
            finally:
                await engine.dispose()
    
    # Run the async function
    return asyncio.run(_publish_post())

@celery_app.task
def check_scheduled_posts():
    """Check for posts that need to be published"""
    import asyncio
    
    async def _check_posts():
        # Create a new async engine for this task
        engine = create_async_engine(get_async_database_url())
        async with AsyncSessionLocal(engine) as db:
            try:
                # Get posts scheduled for now or earlier
                posts = await PostCRUD.get_scheduled_posts(db)
                
                for post in posts:
                    publish_post_task.delay(post.id)
                
                return {"checked_posts": len(posts)}
                
            finally:
                await engine.dispose()
    
    # Run the async function
    return asyncio.run(_check_posts())