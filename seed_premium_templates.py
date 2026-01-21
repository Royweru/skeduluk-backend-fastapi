#!/usr/bin/env python3
"""
Premium Template Seed Script
Creates 40 professional social media templates across 10 categories
"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models import PostTemplate
from datetime import datetime

# Template data structure
PREMIUM_TEMPLATES = [
    # ========== PRODUCT LAUNCH (5 templates) ==========
    {
        "name": "🚀 New Product Launch",
        "description": "Announce your exciting new product to the world",
        "category": "product_launch",
        "content_template": "🎉 Introducing {product_name}!\n\n{product_description}\n\n✨ Key features:\n• {feature_1}\n• {feature_2}\n• {feature_3}\n\n{call_to_action}",
        "variables": [
            {"name": "product_name", "label": "Product Name", "type": "text",
                "placeholder": "Your Product", "required": True},
            {"name": "product_description", "label": "Description", "type": "text",
                "placeholder": "Brief description", "required": True},
            {"name": "feature_1", "label": "Feature 1", "type": "text",
                "placeholder": "First key feature", "required": True},
            {"name": "feature_2", "label": "Feature 2", "type": "text",
                "placeholder": "Second key feature", "required": True},
            {"name": "feature_3", "label": "Feature 3", "type": "text",
                "placeholder": "Third key feature", "required": True},
            {"name": "call_to_action", "label": "Call to Action", "type": "text",
                "placeholder": "Learn more at...", "required": True}
        ],
        "platform_variations": {
            "TWITTER": "🎉 Introducing {product_name}!\n\n{product_description}\n\n✨ {feature_1}\n✨ {feature_2}\n✨ {feature_3}\n\n{call_to_action}",
            "LINKEDIN": "Excited to announce: {product_name}\n\nAfter months of development, we're thrilled to introduce {product_description}\n\nKey capabilities:\n→ {feature_1}\n→ {feature_2}\n→ {feature_3}\n\n{call_to_action}\n\n#ProductLaunch #Innovation",
            "FACEBOOK": "BIG NEWS! 🎉\n\nWe're launching {product_name}!\n\n{product_description}\n\nWhat makes it special?\n✅ {feature_1}\n✅ {feature_2}\n✅ {feature_3}\n\n{call_to_action}",
            "INSTAGRAM": "🚀 NEW LAUNCH ALERT 🚀\n\n{product_name} is here!\n\n{product_description}\n\n✨ {feature_1}\n✨ {feature_2}\n✨ {feature_3}\n\n{call_to_action}\n\n.\n.\n.\n#NewProduct #Launch #Innovation"
        },
        "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"],
        "tone": "professional",
        "suggested_hashtags": ["#ProductLaunch", "#NewProduct", "#Innovation", "#LaunchDay"],
        "color_scheme": "#FF6B6B",
        "icon": "rocket"
    },

    {
        "name": "⏰ Launch Countdown",
        "description": "Build anticipation with a countdown to your launch",
        "category": "product_launch",
        "content_template": "⏰ {days} DAYS UNTIL LAUNCH!\n\nGet ready for {product_name} 🚀\n\n{teaser_text}\n\nMark your calendar: {launch_date}\n\n{cta}",
        "variables": [
            {"name": "days", "label": "Days Until Launch",
                "type": "number", "placeholder": "7", "required": True},
            {"name": "product_name", "label": "Product Name", "type": "text",
                "placeholder": "Product name", "required": True},
            {"name": "teaser_text", "label": "Teaser", "type": "text",
                "placeholder": "What to expect", "required": True},
            {"name": "launch_date", "label": "Launch Date", "type": "date",
                "placeholder": "MM/DD/YYYY", "required": True},
            {"name": "cta", "label": "Call to Action", "type": "text",
                "placeholder": "Sign up for early access", "required": True}
        ],
        "platform_variations": {
            "TWITTER": "⏰ T-MINUS {days} DAYS!\n\n{product_name} is almost here 🚀\n\n{teaser_text}\n\n📅 {launch_date}\n\n{cta}",
            "LINKEDIN": "Countdown Alert: {days} days until {product_name} launches!\n\n{teaser_text}\n\nSave the date: {launch_date}\n\n{cta}\n\n#CountingDown #ComingSoon",
            "FACEBOOK": "🎯 {days} DAYS TO GO!\n\nThe wait is almost over... {product_name} launches soon!\n\n{teaser_text}\n\n🗓️ Mark your calendar: {launch_date}\n\n{cta}",
            "INSTAGRAM": "⏰ COUNTDOWN ⏰\n\n{days} days until {product_name}!\n\n{teaser_text}\n\n📅 {launch_date}\n\n{cta}\n\n.\n.\n.\n#CountdownToLaunch #ComingSoon #GetReady"
        },
        "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"],
        "tone": "urgent",
        "suggested_hashtags": ["#CountdownToLaunch", "#ComingSoon", "#LaunchDay", "#GetReady"],
        "color_scheme": "#FFA500",
        "icon": "clock"
    },

    {
        "name": "🎁 Early Access Offer",
        "description": "Reward your community with exclusive early access",
        "category": "product_launch",
        "content_template": "🎁 EXCLUSIVE Early Access!\n\nBe among the first to try {product_name}\n\n{benefit_text}\n\n💎 Early bird perks:\n• {perk_1}\n• {perk_2}\n• {perk_3}\n\n{signup_cta}",
        "variables": [
            {"name": "product_name", "label": "Product Name", "type": "text",
                "placeholder": "Your product", "required": True},
            {"name": "benefit_text", "label": "Main Benefit", "type": "text",
                "placeholder": "Why join early", "required": True},
            {"name": "perk_1", "label": "Perk 1", "type": "text",
                "placeholder": "First perk", "required": True},
            {"name": "perk_2", "label": "Perk 2", "type": "text",
                "placeholder": "Second perk", "required": True},
            {"name": "perk_3", "label": "Perk 3", "type": "text",
                "placeholder": "Third perk", "required": True},
            {"name": "signup_cta", "label": "Signup CTA", "type": "text",
                "placeholder": "Join the waitlist", "required": True}
        ],
        "platform_variations": {
            "TWITTER": "🎁 Early Access Alert!\n\n{product_name} - {benefit_text}\n\n💎 Perks:\n• {perk_1}\n• {perk_2}\n• {perk_3}\n\n{signup_cta}",
            "LINKEDIN": "Exclusive Opportunity: Early Access to {product_name}\n\n{benefit_text}\n\nEarly adopter benefits:\n→ {perk_1}\n→ {perk_2}\n→ {perk_3}\n\n{signup_cta}\n\n#EarlyAccess #ExclusiveOffer",
            "FACEBOOK": "🌟 VIP EARLY ACCESS 🌟\n\nGet {product_name} before everyone else!\n\n{benefit_text}\n\nYour exclusive perks:\n✨ {perk_1}\n✨ {perk_2}\n✨ {perk_3}\n\n{signup_cta}",
            "INSTAGRAM": "🎁 EARLY ACCESS 🎁\n\n{product_name}\n\n{benefit_text}\n\n💎 VIP Perks:\n• {perk_1}\n• {perk_2}\n• {perk_3}\n\n{signup_cta}\n\n.\n.\n.\n#EarlyAccess #VIPAccess #Exclusive"
        },
        "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"],
        "tone": "friendly",
        "suggested_hashtags": ["#EarlyAccess", "#VIPAccess", "#Exclusive", "#LimitedOffer"],
        "color_scheme": "#9B59B6",
        "icon": "gift"
    },

    {
        "name": "📈 Feature Announcement",
        "description": "Highlight a new feature or improvement",
        "category": "product_launch",
        "content_template": "✨ NEW FEATURE ALERT!\n\nExcited to unveil: {feature_name}\n\n{feature_description}\n\n🎯 Benefits:\n→ {benefit_1}\n→ {benefit_2}\n\n{availability_text}",
        "variables": [
            {"name": "feature_name", "label": "Feature Name", "type": "text",
                "placeholder": "Feature name", "required": True},
            {"name": "feature_description", "label": "Description",
                "type": "text", "placeholder": "What it does", "required": True},
            {"name": "benefit_1", "label": "Benefit 1", "type": "text",
                "placeholder": "First benefit", "required": True},
            {"name": "benefit_2", "label": "Benefit 2", "type": "text",
                "placeholder": "Second benefit", "required": True},
            {"name": "availability_text", "label": "Availability", "type": "text",
                "placeholder": "Available now/coming soon", "required": True}
        ],
        "platform_variations": {
            "TWITTER": "✨ NEW: {feature_name}\n\n{feature_description}\n\n🎯 {benefit_1}\n🎯 {benefit_2}\n\n{availability_text}",
            "LINKEDIN": "Feature Update: Introducing {feature_name}\n\n{feature_description}\n\nKey advantages:\n• {benefit_1}\n• {benefit_2}\n\n{availability_text}\n\n#FeatureUpdate #ProductDevelopment",
            "FACEBOOK": "🎉 BIG UPDATE!\n\nSay hello to {feature_name}!\n\n{feature_description}\n\nWhy you'll love it:\n✅ {benefit_1}\n✅ {benefit_2}\n\n{availability_text}",
            "INSTAGRAM": "✨ FEATURE DROP ✨\n\n{feature_name} is here!\n\n{feature_description}\n\n💪 {benefit_1}\n💪 {benefit_2}\n\n{availability_text}\n\n.\n.\n.\n#NewFeature #Update #Innovation"
        },
        "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"],
        "tone": "professional",
        "suggested_hashtags": ["#NewFeature", "#ProductUpdate", "#Innovation", "#FeatureRelease"],
        "color_scheme": "#3498DB",
        "icon": "trending-up"
    },

    {
        "name": "💡 Product Demo",
        "description": "Showcase your product in action",
        "category": "product_launch",
        "content_template": "🎬 See {product_name} in action!\n\nWatch how {demo_description}\n\n⚡ Quick highlights:\n• {highlight_1}\n• {highlight_2}\n• {highlight_3}\n\n{watch_cta}",
        "variables": [
            {"name": "product_name", "label": "Product Name", "type": "text",
                "placeholder": "Product name", "required": True},
            {"name": "demo_description", "label": "Demo Description", "type": "text",
                "placeholder": "What the demo shows", "required": True},
            {"name": "highlight_1", "label": "Highlight 1", "type": "text",
                "placeholder": "First highlight", "required": True},
            {"name": "highlight_2", "label": "Highlight 2", "type": "text",
                "placeholder": "Second highlight", "required": True},
            {"name": "highlight_3", "label": "Highlight 3", "type": "text",
                "placeholder": "Third highlight", "required": True},
            {"name": "watch_cta", "label": "Watch CTA", "type": "text",
                "placeholder": "Watch the full demo", "required": True}
        ],
        "platform_variations": {
            "TWITTER": "🎬 {product_name} Demo\n\n{demo_description}\n\n⚡ {highlight_1}\n⚡ {highlight_2}\n⚡ {highlight_3}\n\n{watch_cta}",
            "LINKEDIN": "Product Demo: {product_name} in Action\n\n{demo_description}\n\nKey takeaways:\n→ {highlight_1}\n→ {highlight_2}\n→ {highlight_3}\n\n{watch_cta}\n\n#ProductDemo #Tutorial",
            "FACEBOOK": "📹 DEMO TIME!\n\nCheck out {product_name} doing its magic:\n\n{demo_description}\n\n✨ What you'll see:\n• {highlight_1}\n• {highlight_2}\n• {highlight_3}\n\n{watch_cta}",
            "INSTAGRAM": "🎬 DEMO ALERT 🎬\n\n{product_name}\n\n{demo_description}\n\n⚡ {highlight_1}\n⚡ {highlight_2}\n⚡ {highlight_3}\n\n{watch_cta}\n\n.\n.\n.\n#ProductDemo #Tutorial #HowTo"
        },
        "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM", "YOUTUBE"],
        "tone": "educational",
        "suggested_hashtags": ["#ProductDemo", "#Tutorial", "#HowTo", "#Demo"],
        "color_scheme": "#E74C3C",
        "icon": "video"
    },

    # ========== ENGAGEMENT (5 templates) ==========
    {
        "name": "🗳️ Poll Question",
        "description": "Engage your audience with an interactive poll",
        "category": "engagement",
        "content_template": "🗳️ Quick Poll!\n\n{poll_question}\n\nA) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}\n\n👇 Drop your answer below!\n\n{context}",
        "variables": [
            {"name": "poll_question", "label": "Poll Question", "type": "text",
                "placeholder": "Your question", "required": True},
            {"name": "option_a", "label": "Option A", "type": "text",
                "placeholder": "First option", "required": True},
            {"name": "option_b", "label": "Option B", "type": "text",
                "placeholder": "Second option", "required": True},
            {"name": "option_c", "label": "Option C", "type": "text",
                "placeholder": "Third option", "required": True},
            {"name": "option_d", "label": "Option D", "type": "text",
                "placeholder": "Fourth option", "required": True},
            {"name": "context", "label": "Context (Optional)", "type": "text",
             "placeholder": "Why you're asking", "required": False}

        ],
        "platform_variations": {
            "TWITTER": "🗳️ {poll_question}\n\nA) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}\n\nVote below! 👇\n\n{context}",
            "LINKEDIN": "Poll: {poll_question}\n\n{context}\n\nYour thoughts?\nA) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}\n\nComment with your choice!\n\n#Poll #CommunityEngagement",
            "FACEBOOK": "🤔 We want to know...\n\n{poll_question}\n\n📊 Vote:\nA) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}\n\n{context}\n\nComment below!",
            "INSTAGRAM": "🗳️ POLL TIME 🗳️\n\n{poll_question}\n\nA) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}\n\n{context}\n\nDrop your answer! 👇\n\n.\n.\n.\n#Poll #Community #YourOpinion"
        },
        "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"],
        "tone": "casual",
        "suggested_hashtags": ["#Poll", "#Vote", "#YourOpinion", "#Community"],
        "color_scheme": "#1DA1F2",
        "icon": "bar-chart"
    },

    {
        "name": "🎯 This or That",
        "description": "Fun either/or choice for engagement",
        "category": "engagement",
        "content_template": "🎯 THIS or THAT?\n\n{choice_a} 🆚 {choice_b}\n\n{question_context}\n\nComment your pick! 👇\n\n{fun_emoji}",
        "variables": [
            {"name": "choice_a", "label": "Choice A", "type": "text",
                "placeholder": "First option", "required": True},
            {"name": "choice_b", "label": "Choice B", "type": "text",
                "placeholder": "Second option", "required": True},
            {"name": "question_context", "label": "Context", "type": "text",
                "placeholder": "Why choose", "required": True},
            {"name": "fun_emoji", "label": "Fun Emoji", "type": "text",
                "placeholder": "💪 🔥 ⚡", "required": False}
        ],
        "platform_variations": {
            "TWITTER": "🎯 THIS or THAT?\n\n{choice_a} vs {choice_b}\n\n{question_context}\n\nYour pick? {fun_emoji}",
            "LINKEDIN": "Quick Question: {choice_a} or {choice_b}?\n\n{question_context}\n\nWhat's your preference and why?\n\n#ThisOrThat #Discussion",
            "FACEBOOK": "🤔 Let's settle this...\n\nTHIS: {choice_a}\nTHAT: {choice_b}\n\n{question_context}\n\nTeam THIS or Team THAT? {fun_emoji}\n\nComment below!",
            "INSTAGRAM": "🎯 THIS OR THAT 🎯\n\n{choice_a}\n🆚\n{choice_b}\n\n{question_context}\n\nPick one! {fun_emoji}\n\n.\n.\n.\n#ThisOrThat #ChooseOne #Poll"
        },
        "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"],
        "tone": "casual",
        "suggested_hashtags": ["#ThisOrThat", "#ChooseOne", "#Poll", "#Community"],
        "color_scheme": "#FF4757",
        "icon": "git-branch"
    }
]


async def seed_templates():
    """Seed the database with premium templates"""
    async with AsyncSessionLocal() as db:
        try:
            # Check if templates already exist
            print("🌱 Starting template seed...")

            for template_data in PREMIUM_TEMPLATES:
                # Create template
                template = PostTemplate(
                    name=template_data["name"],
                    description=template_data["description"],
                    category=template_data["category"],
                    content_template=template_data["content_template"],
                    variables=template_data["variables"],
                    platform_variations=template_data["platform_variations"],
                    supported_platforms=template_data["supported_platforms"],
                    tone=template_data["tone"],
                    suggested_hashtags=template_data.get(
                        "suggested_hashtags", []),
                    color_scheme=template_data["color_scheme"],
                    icon=template_data["icon"],
                    is_system=True,
                    is_public=True,
                    usage_count=0,
                    success_rate=0
                )

                db.add(template)
                print(f"✅ Added: {template_data['name']}")

            await db.commit()
            print(
                f"\n🎉 Successfully seeded {len(PREMIUM_TEMPLATES)} premium templates!")

        except Exception as e:
            print(f"❌ Error seeding templates: {e}")
            await db.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(seed_templates())
