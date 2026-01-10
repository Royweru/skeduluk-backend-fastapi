# scripts/populate_templates.py
"""
Script to populate the database with system templates
Usage: python -m scripts.populate_templates
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import create_async_engine, get_async_session_local
from app import models
from app.crud.template_crud import TemplateCRUD
from app.schemas import TemplateCreate, TemplateVariableDefinition


# ============================================================================
# TEMPLATE DEFINITIONS
# ============================================================================

SYSTEM_TEMPLATES = [
    # PRODUCT LAUNCH TEMPLATES
    {
        "name": "🚀 Product Launch Announcement",
        "description": "Announce your new product with excitement",
        "category": "product_launch",
        "content_template": "🎉 Excited to announce {product_name}! {product_description}\n\n✨ Key features:\n{features}\n\n{cta}\n\n{hashtags}",
        "variables": [
            {
                "name": "product_name",
                "label": "Product Name",
                "type": "text",
                "placeholder": "e.g., Skeduluk Pro",
                "required": True
            },
            {
                "name": "product_description",
                "label": "Brief Description",
                "type": "text",
                "placeholder": "A revolutionary social media scheduler",
                "required": True
            },
            {
                "name": "features",
                "label": "Key Features (separate with line breaks)",
                "type": "text",
                "placeholder": "• AI-powered content\n• Multi-platform\n• Smart scheduling",
                "required": True
            },
            {
                "name": "cta",
                "label": "Call to Action",
                "type": "text",
                "placeholder": "Try it free: www.example.com",
                "required": True
            },
            {
                "name": "hashtags",
                "label": "Hashtags",
                "type": "hashtags",
                "placeholder": "#ProductLaunch #Innovation",
                "required": False,
                "default_value": ""
            }
        ],
        "platform_variations": {
            "TWITTER": "🚀 Launching {product_name}!\n\n{product_description}\n\n{cta} {hashtags}",
            "LINKEDIN": "We're thrilled to introduce {product_name}.\n\n{product_description}\n\nKey highlights:\n{features}\n\n{cta}\n\n{hashtags}"
        },
        "supported_platforms": ["TWITTER", "FACEBOOK", "LINKEDIN", "INSTAGRAM"],
        "tone": "inspirational",
        "suggested_hashtags": ["#ProductLaunch", "#Innovation", "#NewProduct", "#TechNews"],
        "suggested_media_type": "image",
        "color_scheme": "#10B981",
        "icon": "rocket",
        "thumbnail_url": None
    },
    
    # EVENT PROMOTION TEMPLATES
    {
        "name": "📅 Event Invitation",
        "description": "Invite your audience to an upcoming event",
        "category": "event_promotion",
        "content_template": "📅 Save the date! {event_name} is happening {event_date}!\n\n{event_description}\n\n📍 {location}\n🕐 {time}\n\n{registration_link}\n\n{hashtags}",
        "variables": [
            {
                "name": "event_name",
                "label": "Event Name",
                "type": "text",
                "placeholder": "Annual Tech Summit 2024",
                "required": True
            },
            {
                "name": "event_date",
                "label": "Event Date",
                "type": "date",
                "placeholder": "March 15, 2024",
                "required": True
            },
            {
                "name": "event_description",
                "label": "Event Description",
                "type": "text",
                "placeholder": "Join industry leaders for a day of insights",
                "required": True
            },
            {
                "name": "location",
                "label": "Location",
                "type": "text",
                "placeholder": "Virtual / San Francisco, CA",
                "required": True
            },
            {
                "name": "time",
                "label": "Time",
                "type": "text",
                "placeholder": "10:00 AM PST",
                "required": True
            },
            {
                "name": "registration_link",
                "label": "Registration Link",
                "type": "url",
                "placeholder": "Register: www.example.com/register",
                "required": True
            },
            {
                "name": "hashtags",
                "label": "Event Hashtags",
                "type": "hashtags",
                "placeholder": "#TechSummit2024",
                "required": False,
                "default_value": ""
            }
        ],
        "supported_platforms": ["TWITTER", "FACEBOOK", "LINKEDIN", "INSTAGRAM"],
        "tone": "professional",
        "suggested_hashtags": ["#Event", "#Networking", "#Conference"],
        "suggested_media_type": "image",
        "color_scheme": "#8B5CF6",
        "icon": "calendar",
        "thumbnail_url": None
    },
    
    # BLOG POST PROMOTION
    {
        "name": "📝 Blog Post Announcement",
        "description": "Share your latest blog post",
        "category": "blog_post",
        "content_template": "📝 New blog post: {title}\n\n{excerpt}\n\n{key_takeaway}\n\nRead more: {link}\n\n{hashtags}",
        "variables": [
            {
                "name": "title",
                "label": "Blog Post Title",
                "type": "text",
                "placeholder": "10 Tips for Better Social Media Engagement",
                "required": True
            },
            {
                "name": "excerpt",
                "label": "Brief Excerpt",
                "type": "text",
                "placeholder": "Discover proven strategies to boost your engagement",
                "required": True
            },
            {
                "name": "key_takeaway",
                "label": "Key Takeaway",
                "type": "text",
                "placeholder": "💡 Top tip: Consistency is key!",
                "required": False,
                "default_value": ""
            },
            {
                "name": "link",
                "label": "Blog URL",
                "type": "url",
                "placeholder": "https://blog.example.com/post",
                "required": True
            },
            {
                "name": "hashtags",
                "label": "Hashtags",
                "type": "hashtags",
                "placeholder": "#BlogPost #ContentMarketing",
                "required": False,
                "default_value": ""
            }
        ],
        "supported_platforms": ["TWITTER", "FACEBOOK", "LINKEDIN"],
        "tone": "educational",
        "suggested_hashtags": ["#BlogPost", "#ContentMarketing", "#DigitalMarketing"],
        "suggested_media_type": "image",
        "color_scheme": "#3B82F6",
        "icon": "file-text",
        "thumbnail_url": None
    },
    
    # ENGAGEMENT POSTS
    {
        "name": "💬 Question for Engagement",
        "description": "Ask your audience a question to spark conversation",
        "category": "engagement",
        "content_template": "💬 {question}\n\n{context}\n\nDrop your thoughts below! 👇\n\n{hashtags}",
        "variables": [
            {
                "name": "question",
                "label": "Your Question",
                "type": "text",
                "placeholder": "What's your biggest social media challenge?",
                "required": True
            },
            {
                "name": "context",
                "label": "Context (optional)",
                "type": "text",
                "placeholder": "We're curious to hear from our community",
                "required": False,
                "default_value": ""
            },
            {
                "name": "hashtags",
                "label": "Hashtags",
                "type": "hashtags",
                "placeholder": "#Community #Discussion",
                "required": False,
                "default_value": ""
            }
        ],
        "supported_platforms": ["TWITTER", "FACEBOOK", "LINKEDIN", "INSTAGRAM"],
        "tone": "casual",
        "suggested_hashtags": ["#Community", "#Question", "#Discussion"],
        "suggested_media_type": None,
        "color_scheme": "#F59E0B",
        "icon": "message-circle",
        "thumbnail_url": None
    },
    
    # TESTIMONIAL
    {
        "name": "⭐ Customer Testimonial",
        "description": "Share positive feedback from customers",
        "category": "testimonial",
        "content_template": "⭐ {rating}/5 stars from {customer_name}!\n\n\"{testimonial}\"\n\n{context}\n\n{cta}\n\n{hashtags}",
        "variables": [
            {
                "name": "customer_name",
                "label": "Customer Name",
                "type": "text",
                "placeholder": "Sarah J.",
                "required": True
            },
            {
                "name": "rating",
                "label": "Rating",
                "type": "number",
                "placeholder": "5",
                "required": True
            },
            {
                "name": "testimonial",
                "label": "Testimonial Quote",
                "type": "text",
                "placeholder": "This product changed my workflow!",
                "required": True
            },
            {
                "name": "context",
                "label": "Additional Context",
                "type": "text",
                "placeholder": "Sarah has been using our product for 6 months",
                "required": False,
                "default_value": ""
            },
            {
                "name": "cta",
                "label": "Call to Action",
                "type": "text",
                "placeholder": "Want similar results? Try it free!",
                "required": False,
                "default_value": ""
            },
            {
                "name": "hashtags",
                "label": "Hashtags",
                "type": "hashtags",
                "placeholder": "#CustomerSuccess #Testimonial",
                "required": False,
                "default_value": ""
            }
        ],
        "supported_platforms": ["TWITTER", "FACEBOOK", "LINKEDIN", "INSTAGRAM"],
        "tone": "inspirational",
        "suggested_hashtags": ["#CustomerSuccess", "#Testimonial", "#Review"],
        "suggested_media_type": "image",
        "color_scheme": "#EF4444",
        "icon": "star",
        "thumbnail_url": None
    },
    
    # EDUCATIONAL TIP
    {
        "name": "💡 Quick Tip",
        "description": "Share a helpful tip or insight",
        "category": "educational",
        "content_template": "💡 {tip_title}\n\n{tip_description}\n\n{how_to}\n\nTry it out and let us know how it works!\n\n{hashtags}",
        "variables": [
            {
                "name": "tip_title",
                "label": "Tip Title",
                "type": "text",
                "placeholder": "Pro Tip: Schedule posts during peak hours",
                "required": True
            },
            {
                "name": "tip_description",
                "label": "Tip Description",
                "type": "text",
                "placeholder": "Posting when your audience is most active increases engagement by 3x",
                "required": True
            },
            {
                "name": "how_to",
                "label": "How To Apply",
                "type": "text",
                "placeholder": "📊 Check your analytics\n⏰ Find peak times\n🎯 Schedule accordingly",
                "required": True
            },
            {
                "name": "hashtags",
                "label": "Hashtags",
                "type": "hashtags",
                "placeholder": "#ProTip #SocialMediaTips",
                "required": False,
                "default_value": ""
            }
        ],
        "supported_platforms": ["TWITTER", "FACEBOOK", "LINKEDIN", "INSTAGRAM"],
        "tone": "educational",
        "suggested_hashtags": ["#ProTip", "#Marketing101", "#SocialMediaTips"],
        "suggested_media_type": "image",
        "color_scheme": "#14B8A6",
        "icon": "lightbulb",
        "thumbnail_url": None
    },
    
    # PROMOTIONAL OFFER
    {
        "name": "🎁 Limited Time Offer",
        "description": "Promote a special offer or discount",
        "category": "promotional",
        "content_template": "🎁 {offer_title}\n\n{offer_details}\n\n⏰ {deadline}\n💰 {discount_details}\n\n{cta}\n\nUse code: {promo_code}\n\n{hashtags}",
        "variables": [
            {
                "name": "offer_title",
                "label": "Offer Title",
                "type": "text",
                "placeholder": "Flash Sale - 50% Off!",
                "required": True
            },
            {
                "name": "offer_details",
                "label": "Offer Details",
                "type": "text",
                "placeholder": "Get half off all premium plans",
                "required": True
            },
            {
                "name": "deadline",
                "label": "Deadline",
                "type": "text",
                "placeholder": "Ends tonight at midnight!",
                "required": True
            },
            {
                "name": "discount_details",
                "label": "Discount Details",
                "type": "text",
                "placeholder": "Save up to $100",
                "required": True
            },
            {
                "name": "cta",
                "label": "Call to Action",
                "type": "text",
                "placeholder": "Shop now: www.example.com/sale",
                "required": True
            },
            {
                "name": "promo_code",
                "label": "Promo Code",
                "type": "text",
                "placeholder": "SAVE50",
                "required": True
            },
            {
                "name": "hashtags",
                "label": "Hashtags",
                "type": "hashtags",
                "placeholder": "#Sale #LimitedOffer",
                "required": False,
                "default_value": ""
            }
        ],
        "supported_platforms": ["TWITTER", "FACEBOOK", "LINKEDIN", "INSTAGRAM"],
        "tone": "urgent",
        "suggested_hashtags": ["#Sale", "#Discount", "#LimitedOffer"],
        "suggested_media_type": "image",
        "color_scheme": "#DC2626",
        "icon": "tag",
        "thumbnail_url": None
    },
    
    # BEHIND THE SCENES
    {
        "name": "🎬 Behind the Scenes",
        "description": "Give your audience a peek behind the curtain",
        "category": "behind_scenes",
        "content_template": "🎬 Behind the scenes: {subject}\n\n{description}\n\n{fun_fact}\n\n{cta}\n\n{hashtags}",
        "variables": [
            {
                "name": "subject",
                "label": "What are you showing?",
                "type": "text",
                "placeholder": "Our office space / Product development / Team meeting",
                "required": True
            },
            {
                "name": "description",
                "label": "Description",
                "type": "text",
                "placeholder": "Here's how we bring your ideas to life",
                "required": True
            },
            {
                "name": "fun_fact",
                "label": "Fun Fact",
                "type": "text",
                "placeholder": "Did you know? We drink 100 cups of coffee per day! ☕",
                "required": False,
                "default_value": ""
            },
            {
                "name": "cta",
                "label": "Call to Action",
                "type": "text",
                "placeholder": "Want to see more? Follow us!",
                "required": False,
                "default_value": ""
            },
            {
                "name": "hashtags",
                "label": "Hashtags",
                "type": "hashtags",
                "placeholder": "#BTS #BehindTheScenes",
                "required": False,
                "default_value": ""
            }
        ],
        "supported_platforms": ["TWITTER", "FACEBOOK", "LINKEDIN", "INSTAGRAM"],
        "tone": "casual",
        "suggested_hashtags": ["#BehindTheScenes", "#BTS", "#CompanyCulture"],
        "suggested_media_type": "image",
        "color_scheme": "#6366F1",
        "icon": "camera",
        "thumbnail_url": None
    },
    
    # INSPIRATIONAL QUOTE
    {
        "name": "✨ Motivational Quote",
        "description": "Share an inspiring quote",
        "category": "inspirational",
        "content_template": "✨ {quote_intro}\n\n\"{quote}\"\n\n- {author}\n\n{personal_note}\n\n{hashtags}",
        "variables": [
            {
                "name": "quote_intro",
                "label": "Quote Introduction",
                "type": "text",
                "placeholder": "Monday motivation:",
                "required": False,
                "default_value": ""
            },
            {
                "name": "quote",
                "label": "The Quote",
                "type": "text",
                "placeholder": "The only way to do great work is to love what you do",
                "required": True
            },
            {
                "name": "author",
                "label": "Author",
                "type": "text",
                "placeholder": "Steve Jobs",
                "required": True
            },
            {
                "name": "personal_note",
                "label": "Your Thoughts",
                "type": "text",
                "placeholder": "This reminds us why we do what we do every day",
                "required": False,
                "default_value": ""
            },
            {
                "name": "hashtags",
                "label": "Hashtags",
                "type": "hashtags",
                "placeholder": "#MondayMotivation #Inspiration",
                "required": False,
                "default_value": ""
            }
        ],
        "supported_platforms": ["TWITTER", "FACEBOOK", "LINKEDIN", "INSTAGRAM"],
        "tone": "inspirational",
        "suggested_hashtags": ["#Motivation", "#Inspiration", "#QuoteOfTheDay"],
        "suggested_media_type": "image",
        "color_scheme": "#F59E0B",
        "icon": "quote",
        "thumbnail_url": None
    },
    
    # COMPANY MILESTONE
    {
        "name": "🎉 Company Milestone",
        "description": "Celebrate achievements and milestones",
        "category": "announcement",
        "content_template": "🎉 {milestone_title}!\n\n{milestone_details}\n\n{gratitude}\n\n{whats_next}\n\n{hashtags}",
        "variables": [
            {
                "name": "milestone_title",
                "label": "Milestone",
                "type": "text",
                "placeholder": "We just hit 10,000 users",
                "required": True
            },
            {
                "name": "milestone_details",
                "label": "Details",
                "type": "text",
                "placeholder": "From 0 to 10K in just 6 months",
                "required": True
            },
            {
                "name": "gratitude",
                "label": "Thank You Message",
                "type": "text",
                "placeholder": "Thank you to our amazing community for believing in us!",
                "required": True
            },
            {
                "name": "whats_next",
                "label": "What's Next",
                "type": "text",
                "placeholder": "Next stop: 100K! 🚀",
                "required": False,
                "default_value": ""
            },
            {
                "name": "hashtags",
                "label": "Hashtags",
                "type": "hashtags",
                "placeholder": "#Milestone #Growth",
                "required": False,
                "default_value": ""
            }
        ],
        "supported_platforms": ["TWITTER", "FACEBOOK", "LINKEDIN", "INSTAGRAM"],
        "tone": "inspirational",
        "suggested_hashtags": ["#Milestone", "#CompanyGrowth", "#Celebration"],
        "suggested_media_type": "image",
        "color_scheme": "#10B981",
        "icon": "trophy",
        "thumbnail_url": None
    },
    
    # USER GENERATED CONTENT
    {
        "name": "📸 User Generated Content",
        "description": "Share content from your community",
        "category": "user_generated",
        "content_template": "📸 Look what {user_name} created!\n\n{content_description}\n\n{appreciation}\n\n{cta}\n\n📷 Credit: {user_handle}\n\n{hashtags}",
        "variables": [
            {
                "name": "user_name",
                "label": "User Name",
                "type": "text",
                "placeholder": "Sarah",
                "required": True
            },
            {
                "name": "user_handle",
                "label": "User Handle/Tag",
                "type": "text",
                "placeholder": "@sarah_designs",
                "required": True
            },
            {
                "name": "content_description",
                "label": "What they created",
                "type": "text",
                "placeholder": "An amazing design using our product",
                "required": True
            },
            {
                "name": "appreciation",
                "label": "Appreciation Message",
                "type": "text",
                "placeholder": "We love seeing your creativity! 💙",
                "required": True
            },
            {
                "name": "cta",
                "label": "Call to Action",
                "type": "text",
                "placeholder": "Tag us to be featured!",
                "required": False,
                "default_value": ""
            },
            {
                "name": "hashtags",
                "label": "Hashtags",
                "type": "hashtags",
                "placeholder": "#Community #UserGenerated",
                "required": False,
                "default_value": ""
            }
        ],
        "supported_platforms": ["TWITTER", "FACEBOOK", "INSTAGRAM"],
        "tone": "friendly",
        "suggested_hashtags": ["#Community", "#UserGenerated", "#Featured"],
        "suggested_media_type": "image",
        "color_scheme": "#EC4899",
        "icon": "users",
        "thumbnail_url": None
    },
    
    # POLL/SURVEY
    {
        "name": "📊 Quick Poll",
        "description": "Engage with polls and surveys",
        "category": "engagement",
        "content_template": "📊 Quick poll!\n\n{poll_question}\n\n{poll_context}\n\nVote and RT to see results! 👇\n\n{hashtags}",
        "variables": [
            {
                "name": "poll_question",
                "label": "Poll Question",
                "type": "text",
                "placeholder": "What's your preferred posting time?",
                "required": True
            },
            {
                "name": "poll_context",
                "label": "Context/Why you're asking",
                "type": "text",
                "placeholder": "We want to serve you better!",
                "required": False,
                "default_value": ""
            },
            {
                "name": "hashtags",
                "label": "Hashtags",
                "type": "hashtags",
                "placeholder": "#Poll #CommunityInput",
                "required": False,
                "default_value": ""
            }
        ],
        "supported_platforms": ["TWITTER", "FACEBOOK", "LINKEDIN"],
        "tone": "casual",
        "suggested_hashtags": ["#Poll", "#Survey", "#CommunityVote"],
        "suggested_media_type": None,
        "color_scheme": "#8B5CF6",
        "icon": "bar-chart",
        "thumbnail_url": None
    }
]


# ============================================================================
# POPULATION FUNCTION
# ============================================================================

async def populate_templates():
    """Populate database with system templates"""
    
    print("🚀 Starting template population...")
    
    # Create engine and session
    engine = create_async_engine()
    AsyncSessionLocal = get_async_session_local(engine)
    
    try:
        async with AsyncSessionLocal() as db:
            # Check if templates already exist
            from sqlalchemy import select, func
            result = await db.execute(
                select(func.count(models.PostTemplate.id)).where(
                    models.PostTemplate.is_system == True
                )
            )
            existing_count = result.scalar()
            
            if existing_count > 0:
                print(f"⚠️  Found {existing_count} existing system templates")
                response = input("Do you want to delete and recreate them? (yes/no): ")
                
                if response.lower() == 'yes':
                    # Delete existing system templates
                    from sqlalchemy import delete
                    await db.execute(
                        delete(models.PostTemplate).where(
                            models.PostTemplate.is_system == True
                        )
                    )
                    await db.commit()
                    print("🗑️  Deleted existing system templates")
                else:
                    print("❌ Aborting...")
                    return
            
            # Create templates
            created_count = 0
            
            for template_data in SYSTEM_TEMPLATES:
                # Convert variable definitions
                variables = None
                if template_data.get('variables'):
                    variables = [
                        TemplateVariableDefinition(**var)
                        for var in template_data['variables']
                    ]
                
                template_create = TemplateCreate(
                    name=template_data['name'],
                    description=template_data['description'],
                    category=template_data['category'],
                    content_template=template_data['content_template'],
                    variables=variables,
                    platform_variations=template_data.get('platform_variations'),
                    supported_platforms=template_data['supported_platforms'],
                    tone=template_data['tone'],
                    suggested_hashtags=template_data.get('suggested_hashtags'),
                    suggested_media_type=template_data.get('suggested_media_type'),
                    is_public=False,
                    thumbnail_url=template_data.get('thumbnail_url'),
                    color_scheme=template_data['color_scheme'],
                    icon=template_data['icon']
                )
                
                # Create template (user_id=None makes it a system template)
                await TemplateCRUD.create_template(db, template_create, user_id=None)
                created_count += 1
                
                print(f"✅ Created: {template_data['name']}")
            
            print(f"\n🎉 Successfully created {created_count} system templates!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await engine.dispose()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    asyncio.run(populate_templates())