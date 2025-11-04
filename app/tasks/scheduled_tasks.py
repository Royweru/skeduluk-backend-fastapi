# app/tasks/scheduled_tasks.py
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from ..celery_app import celery_app
from ..database import get_async_database_url, AsyncSessionLocal
from ..crud import PostCRUD, SocialConnectionCRUD, PostResultCRUD
from ..services.social_service import SocialService

@celery_app.task(bind=True, max_retries=3)
def publish_post_task(self, post_id: int):
    """Publish a post to social platforms"""
    import asyncio
    
    async def _publish_post():
        # Create a new async engine for this task
        engine = create_async_engine(
            get_async_database_url(),
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,   # Recycle connections after 1 hour
        )
        
        async with AsyncSessionLocal(bind=engine) as db:
            try:
                # Get post
                post = await PostCRUD.get_post_by_id(db, post_id, None) 
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
                
                if not relevant_connections:
                    await PostCRUD.update_post_status(
                        db, post_id, "failed", 
                        "No connected platforms found"
                    )
                    return {
                        "success": False, 
                        "error": "No connected platforms found"
                    }
                
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
                            results.append({
                                "platform": connection.platform, 
                                "success": True,
                                "post_id": result.get("platform_post_id")
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
                        
                        # Store error result
                        await PostResultCRUD.create_result(
                            db, post_id, connection.platform,
                            "failed", None, error_msg, content
                        )
                
                # Update post status based on results
                success_count = sum(1 for r in results if r.get("success"))
                total_platforms = len(results)
                
                if success_count == total_platforms:
                    await PostCRUD.update_post_status(db, post_id, "posted")
                elif success_count > 0:
                    await PostCRUD.update_post_status(
                        db, post_id, "partial", 
                        "; ".join(errors)
                    )
                else:
                    await PostCRUD.update_post_status(
                        db, post_id, "failed", 
                        "; ".join(errors)
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
                # Log the full error for debugging
                import traceback
                print(f"Error in publish_post_task: {str(e)}")
                print(traceback.format_exc())
                
                # Try to update post status to failed
                try:
                    await PostCRUD.update_post_status(
                        db, post_id, "failed", 
                        f"Task error: {str(e)}"
                    )
                    await db.commit()
                except:
                    pass
                
                # Retry the task if we haven't exceeded max retries
                raise self.retry(exc=e, countdown=60)  # Retry after 60 seconds
                
            finally:
                await engine.dispose()
    
    # Run the async function
    try:
        return asyncio.run(_publish_post())
    except Exception as e:
        print(f"Fatal error in publish_post_task: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


@celery_app.task
def check_scheduled_posts():
    """Check for posts that need to be published"""
    import asyncio
    
    async def _check_posts():
        # Create a new async engine for this task
        engine = create_async_engine(
            get_async_database_url(),
            pool_pre_ping=True,
        )
        
        async with AsyncSessionLocal(bind=engine) as db:
            try:
                # Get posts scheduled for now or earlier
                posts = await PostCRUD.get_scheduled_posts(db)
                
                print(f"Found {len(posts)} posts to publish")
                
                for post in posts:
                    # Queue each post for publishing
                    publish_post_task.delay(post.id)
                
                return {
                    "checked_posts": len(posts),
                    "queued": len(posts)
                }
                
            finally:
                await engine.dispose()
    
    # Run the async function
    return asyncio.run(_check_posts())