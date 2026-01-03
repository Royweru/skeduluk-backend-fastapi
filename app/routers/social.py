# app/routers/social.py
import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import httpx
from .. import models, auth
from ..database import get_async_db
from ..services.oauth_service import OAuthService

router = APIRouter(prefix="/social", tags=["social"])


@router.get("/connections")
async def get_connections(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get user's connected social accounts"""
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.user_id == current_user.id,
            models.SocialConnection.is_active == True
        )
    )
    connections = result.scalars().all()
    
    return {
        "connections": [
            {
                "id": conn.id,
                "platform": conn.platform,
                "platform_user_id": conn.platform_user_id,
                "platform_username": conn.platform_username,
                "username": conn.username,
                "is_active": conn.is_active,
                "last_synced": conn.last_synced.isoformat() if conn.last_synced else None,
                "created_at": conn.created_at.isoformat() if conn.created_at else None
            }
            for conn in connections
        ]
    }


@router.delete("/connections/{connection_id}")
async def disconnect_platform(
    connection_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Disconnect a social platform"""
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.id == connection_id,
            models.SocialConnection.user_id == current_user.id
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Mark as inactive instead of deleting (soft delete)
    connection.is_active = False
    await db.commit()
    
    return {
        "message": f"{connection.platform} disconnected successfully",
        "platform": connection.platform
    }


@router.post("/connections/{connection_id}/refresh")
async def refresh_token(
    connection_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Refresh access token for a connection"""
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.id == connection_id,
            models.SocialConnection.user_id == current_user.id
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    success = await OAuthService.refresh_access_token(db, connection_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to refresh token")
    
    return {"message": "Token refreshed successfully"}

# Routes for facebook pages connection
@router.get("/facebook/pages")
async def get_facebook_pages(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get list of Facebook Pages user can manage"""
    # Get user's Facebook connection
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.user_id == current_user.id,
            models.SocialConnection.platform == "FACEBOOK",
            models.SocialConnection.is_active == True
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(404, "Facebook not connected")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch pages from Facebook
            response = await client.get(
                "https://graph.facebook.com/v20.0/me/accounts",
                params={
                    "access_token": connection.access_token,
                    "fields": "id,name,category,access_token,picture"
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(500, f"Failed to fetch pages: {response.text}")
            
            pages_data = response.json()
            pages = pages_data.get("data", [])
            
            if not pages:
                return {
                    "pages": [],
                    "message": "No Facebook Pages found. You need to create a Facebook Page first.",
                    "create_page_url": "https://www.facebook.com/pages/create"
                }
            
            # Format pages for frontend
            formatted_pages = []
            for page in pages:
                formatted_pages.append({
                    "id": page["id"],
                    "name": page["name"],
                    "category": page.get("category", "Unknown"),
                    "access_token": page["access_token"],
                    "picture_url": page.get("picture", {}).get("data", {}).get("url"),
                    "is_selected": page["id"] == connection.facebook_page_id
                })
            
            return {
                "pages": formatted_pages,
                "selected_page_id": connection.facebook_page_id,
                "total": len(formatted_pages)
            }
            
    except Exception as e:
        print(f"Error fetching Facebook pages: {e}")
        raise HTTPException(500, f"Error fetching pages: {str(e)}")


@router.post("/facebook/pages/select")
async def select_facebook_page(
    page_id: str,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Select which Facebook Page to use for posting"""
    # Get connection
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.user_id == current_user.id,
            models.SocialConnection.platform == "FACEBOOK",
            models.SocialConnection.is_active == True
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(404, "Facebook not connected")
    
    try:
        # Fetch pages to validate selection and get page token
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://graph.facebook.com/v20.0/me/accounts",
                params={
                    "access_token": connection.access_token,
                    "fields": "id,name,category,access_token,picture"
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(500, "Failed to fetch pages")
            
            pages = response.json().get("data", [])
            selected_page = next((p for p in pages if p["id"] == page_id), None)
            
            if not selected_page:
                raise HTTPException(404, "Page not found or not accessible")
            
            # Update connection with selected page info
            connection.facebook_page_id = selected_page["id"]
            connection.facebook_page_name = selected_page["name"]
            connection.facebook_page_access_token = selected_page["access_token"]
            connection.facebook_page_category = selected_page.get("category")
            connection.facebook_page_picture = selected_page.get("picture", {}).get("data", {}).get("url")
            connection.updated_at = datetime.datetime.utcnow()
            
            await db.commit()
            await db.refresh(connection)
            
            return {
                "success": True,
                "message": f"Successfully selected page: {selected_page['name']}",
                "page": {
                    "id": selected_page["id"],
                    "name": selected_page["name"],
                    "category": selected_page.get("category"),
                    "picture_url": selected_page.get("picture", {}).get("data", {}).get("url")
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error selecting Facebook page: {e}")
        raise HTTPException(500, f"Failed to select page: {str(e)}")


@router.get("/facebook/selected-page")
async def get_selected_facebook_page(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get currently selected Facebook Page"""
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.user_id == current_user.id,
            models.SocialConnection.platform == "FACEBOOK",
            models.SocialConnection.is_active == True
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(404, "Facebook not connected")
    
    if not connection.facebook_page_id:
        return {
            "has_selection": False,
            "message": "No Facebook Page selected"
        }
    
    return {
        "has_selection": True,
        "page": {
            "id": connection.facebook_page_id,
            "name": connection.facebook_page_name,
            "category": connection.facebook_page_category,
            "picture_url": connection.facebook_page_picture
        }
    }