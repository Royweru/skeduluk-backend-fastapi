# app/routers/analytics.py
"""
Analytics API endpoints.
Provides access to post and user analytics.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app import models, schemas, auth
from app.database import get_async_db
from app.services.analytics.analytics_service import AnalyticsService
from app.crud.analytics_crud import AnalyticsCRUD

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/fetch/{post_id}", response_model=schemas.FetchAnalyticsResponse)
async def fetch_post_analytics(
    post_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Manually fetch/refresh analytics for a specific post.
    Fetches from all platforms where the post was published.
    """
    result = await AnalyticsService.fetch_post_analytics(
        db, post_id, current_user.id
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=404,
            detail=result.get("error", "Failed to fetch analytics")
        )

    return result


@router.get("/post/{post_id}", response_model=List[schemas.PostAnalyticsResponse])
async def get_post_analytics(
    post_id: int,
    platform: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get stored analytics for a specific post.
    Optionally filter by platform.
    """
    analytics = await AnalyticsCRUD.get_post_analytics(db, post_id, platform)

    if not analytics:
        raise HTTPException(
            status_code=404,
            detail="No analytics found for this post"
        )

    return analytics


@router.get("/dashboard", response_model=schemas.DashboardAnalyticsResponse)
async def get_dashboard_analytics(
    days: int = Query(default=30, ge=1, le=365),
    platform: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get comprehensive analytics dashboard for the current user.

    Returns:
    - Summary metrics (total views, engagement, etc.)
    - Top performing posts
    - Analytics trend over time
    """
    dashboard = await AnalyticsService.get_user_dashboard_analytics(
        db, current_user.id, days, platform
    )

    return dashboard


@router.get("/summary", response_model=schemas.AnalyticsSummaryResponse)
async def get_analytics_summary(
    days: int = Query(default=30, ge=1, le=365),
    platform: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get aggregated analytics summary for the user.
    """
    from datetime import datetime, timedelta

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    summary = await AnalyticsCRUD.get_user_analytics_summary(
        db, current_user.id, start_date, end_date, platform
    )

    return summary


@router.get("/top-posts", response_model=List[schemas.TopPerformingPost])
async def get_top_posts(
    limit: int = Query(default=10, ge=1, le=50),
    metric: str = Query(default="engagement_rate",
                        regex="^(engagement_rate|views|likes)$"),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get top performing posts.
    Sort by: engagement_rate, views, or likes
    """
    top_posts = await AnalyticsCRUD.get_top_performing_posts(
        db, current_user.id, limit, metric
    )

    return top_posts


@router.get("/trends", response_model=List[schemas.AnalyticsOverTime])
async def get_analytics_trends(
    days: int = Query(default=30, ge=7, le=365),
    platform: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get analytics trends over time.
    Daily aggregated metrics.
    """
    trends = await AnalyticsCRUD.get_analytics_over_time(
        db, current_user.id, days, platform
    )

    return trends


@router.get("/comparison", response_model=schemas.PlatformComparisonResponse)
async def get_platform_comparison(
    days: int = Query(default=30, ge=1, le=365),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Compare performance across all platforms.
    Shows which platform performs best.
    """
    comparison = await AnalyticsService.get_platform_comparison(
        db, current_user.id, days
    )

    return comparison


@router.post("/suggestions", response_model=schemas.AISuggestionsResponse)
async def get_ai_suggestions(
    request: schemas.AISuggestionRequest = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get AI-powered engagement suggestions based on analytics data.
    Analyzes user's posting patterns and provides actionable tips.
    """
    from datetime import datetime, timedelta
    from app.services.ai_service import ai_service

    days = request.days if request else 30

    # Get user's analytics data
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    summary = await AnalyticsCRUD.get_user_analytics_summary(
        db, current_user.id, start_date, end_date
    )

    # Get top posts for context
    top_posts = await AnalyticsCRUD.get_top_performing_posts(
        db, current_user.id, limit=5, metric='engagement_rate'
    )

    # Get platform comparison
    comparison = await AnalyticsService.get_platform_comparison(
        db, current_user.id, days
    )

    # Build analytics context for AI
    analytics_context = f"""
User Analytics Summary (Last {days} days):
- Total Posts: {summary.get('total_posts', 0)}
- Total Views: {summary.get('total_views', 0):,}
- Total Engagement: {summary.get('total_engagement', 0):,}
- Average Engagement Rate: {summary.get('avg_engagement_rate', 0):.2f}%
- Total Likes: {summary.get('total_likes', 0):,}
- Total Comments: {summary.get('total_comments', 0):,}
- Total Shares: {summary.get('total_shares', 0):,}

Platform Breakdown:
"""

    by_platform = summary.get('by_platform', {})
    for platform, metrics in by_platform.items():
        analytics_context += f"""
- {platform}: {metrics.get('posts', 0)} posts, {metrics.get('views', 0):,} views, {metrics.get('engagement_rate', 0):.2f}% engagement
"""

    best_platform = comparison.get('best_platform', 'Not determined')
    analytics_context += f"\nBest Performing Platform: {best_platform}"

    if top_posts:
        analytics_context += "\n\nTop Performing Posts:"
        for i, post in enumerate(top_posts[:3], 1):
            analytics_context += f"\n{i}. ({post.get('platform')}) {post.get('engagement_rate', 0):.2f}% engagement - \"{post.get('content', '')[:80]}...\""

    # Generate AI suggestions
    suggestions = await _generate_ai_suggestions(ai_service, analytics_context, summary, best_platform)

    return schemas.AISuggestionsResponse(
        suggestions=suggestions,
        analyzed_posts=summary.get('total_posts', 0),
        best_performing_platform=best_platform,
        generated_at=datetime.utcnow().isoformat()
    )


async def _generate_ai_suggestions(ai_service, analytics_context: str, summary: dict, best_platform: str) -> List[schemas.AISuggestion]:
    """Generate AI-powered suggestions based on analytics data"""

    prompt = f"""Based on the following social media analytics data, provide 4-6 specific, actionable suggestions to improve engagement and grow the audience.

{analytics_context}

For each suggestion, provide:
1. A category (timing, content, hashtags, platform, engagement, growth)
2. A short title
3. A detailed description with specific advice
4. Priority level (low, medium, high)
5. 2-3 specific action items

Format your response as JSON array with this structure:
[
  {{
    "category": "content",
    "title": "Suggestion Title",
    "description": "Detailed description...",
    "priority": "high",
    "action_items": ["Action 1", "Action 2"]
  }}
]

Focus on:
- Improving engagement rate
- Best posting times
- Content strategies that work
- Platform-specific optimizations
- Hashtag strategies
- Audience growth tactics

Return ONLY the JSON array, no other text."""

    try:
        # Try to use the AI service
        providers = ai_service._get_available_providers()

        if providers:
            provider = providers[0]

            if provider == "groq":
                response = await ai_service.groq_client.chat.completions.create(
                    model="llama-3.1-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=2000
                )
                result = response.choices[0].message.content
            elif provider == "gemini":
                import asyncio

                def generate():
                    return ai_service.gemini_client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt
                    )
                response = await asyncio.to_thread(generate)
                result = response.text
            elif provider == "openai":
                response = await ai_service.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=2000
                )
                result = response.choices[0].message.content
            elif provider == "anthropic":
                response = await ai_service.anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                result = response.content[0].text
            else:
                # Fallback to default suggestions
                return _get_default_suggestions(summary, best_platform)

            # Parse AI response
            import json
            # Clean up the response (remove markdown code blocks if present)
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1]  # Remove first line
            if result.endswith("```"):
                # Remove last markdown block
                result = result.rsplit("```", 1)[0]
            result = result.strip()

            suggestions_data = json.loads(result)

            return [
                schemas.AISuggestion(
                    category=s.get("category", "general"),
                    title=s.get("title", ""),
                    description=s.get("description", ""),
                    priority=s.get("priority", "medium"),
                    action_items=s.get("action_items", [])
                )
                for s in suggestions_data
            ]

    except Exception as e:
        print(f"AI suggestion generation error: {e}")

    # Fallback to default suggestions
    return _get_default_suggestions(summary, best_platform)


def _get_default_suggestions(summary: dict, best_platform: str) -> List[schemas.AISuggestion]:
    """Generate default suggestions when AI is unavailable"""
    suggestions = []

    total_posts = summary.get('total_posts', 0)
    avg_engagement = summary.get('avg_engagement_rate', 0)

    # Posting frequency suggestion
    if total_posts < 10:
        suggestions.append(schemas.AISuggestion(
            category="growth",
            title="Increase Posting Frequency",
            description="You've posted fewer than 10 times in this period. Consistent posting helps build audience engagement and algorithmic favor.",
            priority="high",
            action_items=[
                "Aim for at least 3-5 posts per week",
                "Use the scheduling feature to plan content ahead",
                "Create a content calendar to stay organized"
            ]
        ))

    # Engagement rate suggestion
    if avg_engagement < 2.0:
        suggestions.append(schemas.AISuggestion(
            category="engagement",
            title="Boost Your Engagement Rate",
            description=f"Your average engagement rate is {avg_engagement:.2f}%. Try these tactics to increase audience interaction.",
            priority="high",
            action_items=[
                "Ask questions in your posts to encourage comments",
                "Respond to comments within the first hour",
                "Use calls-to-action (CTAs) in every post"
            ]
        ))

    # Platform optimization
    if best_platform:
        suggestions.append(schemas.AISuggestion(
            category="platform",
            title=f"Double Down on {best_platform}",
            description=f"{best_platform} is your best performing platform. Consider increasing your focus and content volume there.",
            priority="medium",
            action_items=[
                f"Increase posting frequency on {best_platform}",
                f"Study trending content on {best_platform}",
                "Repurpose top-performing content from other platforms"
            ]
        ))

    # Content timing suggestion
    suggestions.append(schemas.AISuggestion(
        category="timing",
        title="Optimize Your Posting Times",
        description="Posting at optimal times can significantly increase reach and engagement.",
        priority="medium",
        action_items=[
            "Post between 9-11 AM and 7-9 PM in your audience's timezone",
            "Test different posting times and track results",
            "Avoid posting on weekends unless your audience is active then"
        ]
    ))

    # Hashtag strategy
    suggestions.append(schemas.AISuggestion(
        category="hashtags",
        title="Improve Your Hashtag Strategy",
        description="Strategic hashtag use can expand your reach to new audiences.",
        priority="low",
        action_items=[
            "Use 3-5 relevant hashtags per post",
            "Mix popular and niche-specific hashtags",
            "Research trending hashtags in your industry"
        ]
    ))

    return suggestions
