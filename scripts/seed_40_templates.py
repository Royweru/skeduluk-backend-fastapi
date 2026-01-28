#!/usr/bin/env python3
"""
Complete 40 Premium Templates Seed Script
Run this to populate your database with professional social media templates
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import PostTemplate

# Complete template collection - 40 templates across 8 categories
TEMPLATES = [
    # PRODUCT LAUNCH (5)
    {"name": "🚀 Product Launch", "description": "Announce your new product with impact", "category": "product_launch",
     "content_template": "🎉 Introducing {product_name}!\n\n{description}\n\n✨ Key features:\n• {feature_1}\n• {feature_2}\n• {feature_3}\n\n{cta}",
     "variables": [{"name": "product_name", "label": "Product Name", "type": "text", "placeholder": "Your Product", "required": True},
                   {"name": "description", "label": "Description", "type": "text", "placeholder": "Brief description", "required": True},
                   {"name": "feature_1", "label": "Feature 1", "type": "text", "placeholder": "First feature", "required": True},
                   {"name": "feature_2", "label": "Feature 2", "type": "text", "placeholder": "Second feature", "required": True},
                   {"name": "feature_3", "label": "Feature 3", "type": "text", "placeholder": "Third feature", "required": True},
                   {"name": "cta", "label": "Call to Action", "type": "text", "placeholder": "Learn more", "required": True}],
     "platform_variations": {"TWITTER": "🎉 Introducing {product_name}!\n\n{description}\n\n✨ {feature_1}\n✨ {feature_2}\n✨ {feature_3}\n\n{cta}",
                             "LINKEDIN": "Excited to announce: {product_name}\n\n{description}\n\nKey capabilities:\n→ {feature_1}\n→ {feature_2}\n→ {feature_3}\n\n{cta}\n\n#ProductLaunch #Innovation"},
     "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "professional",
     "suggested_hashtags": ["#ProductLaunch", "#NewProduct", "#Innovation"], "color_scheme": "#FF6B6B", "icon": "rocket"},
    
    {"name": "⏰ Launch Countdown", "description": "Build anticipation for your launch", "category": "product_launch",
     "content_template": "⏰ {days} DAYS UNTIL LAUNCH!\n\nGet ready for {product_name} 🚀\n\n{teaser}\n\n📅 {launch_date}\n\n{cta}",
     "variables": [{"name": "days", "label": "Days", "type": "number", "placeholder": "7", "required": True},
                   {"name": "product_name", "label": "Product", "type": "text", "placeholder": "Product name", "required": True},
                   {"name": "teaser", "label": "Teaser", "type": "text", "placeholder": "What to expect", "required": True},
                   {"name": "launch_date", "label": "Date", "type": "date", "placeholder": "MM/DD/YYYY", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Sign up", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "urgent",
     "suggested_hashtags": ["#CountdownToLaunch", "#ComingSoon"], "color_scheme": "#FFA500", "icon": "clock"},
    
    {"name": "🎁 Early Access", "description": "Reward early adopters", "category": "product_launch",
     "content_template": "🎁 EXCLUSIVE Early Access!\n\n{product_name}\n\n{benefit}\n\n💎 Perks:\n• {perk_1}\n• {perk_2}\n• {perk_3}\n\n{cta}",
     "variables": [{"name": "product_name", "label": "Product", "type": "text", "placeholder": "Product", "required": True},
                   {"name": "benefit", "label": "Benefit", "type": "text", "placeholder": "Why join early", "required": True},
                   {"name": "perk_1", "label": "Perk 1", "type": "text", "placeholder": "First perk", "required": True},
                   {"name": "perk_2", "label": "Perk 2", "type": "text", "placeholder": "Second perk", "required": True},
                   {"name": "perk_3", "label": "Perk 3", "type": "text", "placeholder": "Third perk", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Join waitlist", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "friendly",
     "suggested_hashtags": ["#EarlyAccess", "#Exclusive"], "color_scheme": "#9B59B6", "icon": "gift"},
    
    {"name": "📈 Feature Update", "description": "Announce new features", "category": "product_launch",
     "content_template": "✨ NEW FEATURE!\n\n{feature_name}\n\n{description}\n\n🎯 Benefits:\n→ {benefit_1}\n→ {benefit_2}\n\n{availability}",
     "variables": [{"name": "feature_name", "label": "Feature", "type": "text", "placeholder": "Feature name", "required": True},
                   {"name": "description", "label": "Description", "type": "text", "placeholder": "What it does", "required": True},
                   {"name": "benefit_1", "label": "Benefit 1", "type": "text", "placeholder": "First benefit", "required": True},
                   {"name": "benefit_2", "label": "Benefit 2", "type": "text", "placeholder": "Second benefit", "required": True},
                   {"name": "availability", "label": "Availability", "type": "text", "placeholder": "Available now", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "professional",
     "suggested_hashtags": ["#NewFeature", "#Update"], "color_scheme": "#3498DB", "icon": "trending-up"},
    
    {"name": "💡 Product Demo", "description": "Showcase your product", "category": "product_launch",
     "content_template": "🎬 See {product_name} in action!\n\n{demo_description}\n\n⚡ Highlights:\n• {highlight_1}\n• {highlight_2}\n• {highlight_3}\n\n{cta}",
     "variables": [{"name": "product_name", "label": "Product", "type": "text", "placeholder": "Product", "required": True},
                   {"name": "demo_description", "label": "Demo Info", "type": "text", "placeholder": "What demo shows", "required": True},
                   {"name": "highlight_1", "label": "Highlight 1", "type": "text", "placeholder": "First highlight", "required": True},
                   {"name": "highlight_2", "label": "Highlight 2", "type": "text", "placeholder": "Second highlight", "required": True},
                   {"name": "highlight_3", "label": "Highlight 3", "type": "text", "placeholder": "Third highlight", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Watch demo", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM", "YOUTUBE"], "tone": "educational",
     "suggested_hashtags": ["#ProductDemo", "#Tutorial"], "color_scheme": "#E74C3C", "icon": "video"},
    
    # ENGAGEMENT (5)
    {"name": "🗳️ Poll Question", "description": "Engage with interactive polls", "category": "engagement",
     "content_template": "🗳️ Quick Poll!\n\n{question}\n\nA) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}\n\n👇 Vote below!",
     "variables": [{"name": "question", "label": "Question", "type": "text", "placeholder": "Your question", "required": True},
                   {"name": "option_a", "label": "Option A", "type": "text", "placeholder": "First option", "required": True},
                   {"name": "option_b", "label": "Option B", "type": "text", "placeholder": "Second option", "required": True},
                   {"name": "option_c", "label": "Option C", "type": "text", "placeholder": "Third option", "required": True},
                   {"name": "option_d", "label": "Option D", "type": "text", "placeholder": "Fourth option", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "casual",
     "suggested_hashtags": ["#Poll", "#Vote", "#Community"], "color_scheme": "#1DA1F2", "icon": "bar-chart"},
    
    {"name": "🎯 This or That", "description": "Fun choice engagement", "category": "engagement",
     "content_template": "🎯 THIS or THAT?\n\n{choice_a} 🆚 {choice_b}\n\n{context}\n\nComment your pick! 👇",
     "variables": [{"name": "choice_a", "label": "Choice A", "type": "text", "placeholder": "First option", "required": True},
                   {"name": "choice_b", "label": "Choice B", "type": "text", "placeholder": "Second option", "required": True},
                   {"name": "context", "label": "Context", "type": "text", "placeholder": "Why choose", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "casual",
     "suggested_hashtags": ["#ThisOrThat", "#ChooseOne"], "color_scheme": "#FF4757", "icon": "git-branch"},
    
    {"name": "💭 Fill in the Blank", "description": "Interactive completion game", "category": "engagement",
     "content_template": "💭 Fill in the blank!\n\n{statement_before} _____ {statement_after}\n\n{context}\n\nDrop your answer! 👇",
     "variables": [{"name": "statement_before", "label": "Before Blank", "type": "text", "placeholder": "Start of sentence", "required": True},
                   {"name": "statement_after", "label": "After Blank", "type": "text", "placeholder": "End of sentence", "required": True},
                   {"name": "context", "label": "Context", "type": "text", "placeholder": "Optional hint", "required": False}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "casual",
     "suggested_hashtags": ["#FillInTheBlank", "#Engagement"], "color_scheme": "#F39C12", "icon": "message-circle"},
    
    {"name": "📸 Caption This", "description": "Photo caption contest", "category": "engagement",
     "content_template": "📸 CAPTION THIS!\n\n{image_description}\n\n{instructions}\n\nBest caption wins! 👇",
     "variables": [{"name": "image_description", "label": "Image Info", "type": "text", "placeholder": "Describe image", "required": True},
                   {"name": "instructions", "label": "Instructions", "type": "text", "placeholder": "Caption rules", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "FACEBOOK", "INSTAGRAM"], "tone": "casual",
     "suggested_hashtags": ["#CaptionThis", "#Contest"], "color_scheme": "#E91E63", "icon": "image"},
    
    {"name": "🏷️ Tag a Friend", "description": "Viral friend tagging", "category": "engagement",
     "content_template": "🏷️ Tag someone who {description}!\n\n{context}\n\n👇 Tag them below!",
     "variables": [{"name": "description", "label": "Description", "type": "text", "placeholder": "needs to see this", "required": True},
                   {"name": "context", "label": "Context", "type": "text", "placeholder": "Why tag", "required": True}],
     "platform_variations": {}, "supported_platforms": ["FACEBOOK", "INSTAGRAM"], "tone": "casual",
     "suggested_hashtags": ["#TagAFriend", "#ShareThis"], "color_scheme": "#8E44AD", "icon": "users"},
    
    # EDUCATIONAL (5)
    {"name": "📚 How-To Guide", "description": "Step-by-step tutorial", "category": "educational",
     "content_template": "📚 How to {topic}\n\nStep 1: {step_1}\nStep 2: {step_2}\nStep 3: {step_3}\n\n{tip}\n\n{cta}",
     "variables": [{"name": "topic", "label": "Topic", "type": "text", "placeholder": "achieve X", "required": True},
                   {"name": "step_1", "label": "Step 1", "type": "text", "placeholder": "First step", "required": True},
                   {"name": "step_2", "label": "Step 2", "type": "text", "placeholder": "Second step", "required": True},
                   {"name": "step_3", "label": "Step 3", "type": "text", "placeholder": "Third step", "required": True},
                   {"name": "tip", "label": "Pro Tip", "type": "text", "placeholder": "Bonus tip", "required": False},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Learn more", "required": False}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "educational",
     "suggested_hashtags": ["#HowTo", "#Tutorial", "#Tips"], "color_scheme": "#27AE60", "icon": "book-open"},
    
    {"name": "💡 Did You Know", "description": "Share interesting facts", "category": "educational",
     "content_template": "💡 DID YOU KNOW?\n\n{fact}\n\n{explanation}\n\n{cta}",
     "variables": [{"name": "fact", "label": "Fact", "type": "text", "placeholder": "Interesting fact", "required": True},
                   {"name": "explanation", "label": "Explanation", "type": "text", "placeholder": "More details", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Learn more", "required": False}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "educational",
     "suggested_hashtags": ["#DidYouKnow", "#Facts", "#Learning"], "color_scheme": "#3498DB", "icon": "lightbulb"},
    
    {"name": "🎯 Top Tips", "description": "Share expert tips", "category": "educational",
     "content_template": "🎯 Top {number} Tips for {topic}\n\n1️⃣ {tip_1}\n2️⃣ {tip_2}\n3️⃣ {tip_3}\n\n{cta}",
     "variables": [{"name": "number", "label": "Number", "type": "number", "placeholder": "3", "required": True},
                   {"name": "topic", "label": "Topic", "type": "text", "placeholder": "success", "required": True},
                   {"name": "tip_1", "label": "Tip 1", "type": "text", "placeholder": "First tip", "required": True},
                   {"name": "tip_2", "label": "Tip 2", "type": "text", "placeholder": "Second tip", "required": True},
                   {"name": "tip_3", "label": "Tip 3", "type": "text", "placeholder": "Third tip", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Get more tips", "required": False}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "professional",
     "suggested_hashtags": ["#Tips", "#Advice", "#BestPractices"], "color_scheme": "#F39C12", "icon": "target"},
    
    {"name": "❌ Myth Busting", "description": "Debunk common myths", "category": "educational",
     "content_template": "❌ MYTH: {myth}\n\n✅ TRUTH: {truth}\n\n{explanation}\n\n{cta}",
     "variables": [{"name": "myth", "label": "Myth", "type": "text", "placeholder": "Common misconception", "required": True},
                   {"name": "truth", "label": "Truth", "type": "text", "placeholder": "Actual fact", "required": True},
                   {"name": "explanation", "label": "Explanation", "type": "text", "placeholder": "Why it matters", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Learn more", "required": False}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "professional",
     "suggested_hashtags": ["#MythBusting", "#Facts", "#Truth"], "color_scheme": "#E74C3C", "icon": "alert-circle"},
    
    {"name": "📊 Industry Insights", "description": "Share data and trends", "category": "educational",
     "content_template": "📊 Industry Insight\n\n{statistic}\n\n{context}\n\n💡 What this means:\n{implication}\n\n{cta}",
     "variables": [{"name": "statistic", "label": "Statistic", "type": "text", "placeholder": "Key stat", "required": True},
                   {"name": "context", "label": "Context", "type": "text", "placeholder": "Background", "required": True},
                   {"name": "implication", "label": "Implication", "type": "text", "placeholder": "What it means", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Read more", "required": False}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK"], "tone": "professional",
     "suggested_hashtags": ["#Insights", "#Data", "#Trends"], "color_scheme": "#2C3E50", "icon": "trending-up"},
    
    # PROMOTIONAL (5)
    {"name": "⚡ Flash Sale", "description": "Limited time offer", "category": "promotional",
     "content_template": "⚡ FLASH SALE!\n\n{offer}\n\n🎯 {discount}\n⏰ Ends: {deadline}\n\n{cta}",
     "variables": [{"name": "offer", "label": "Offer", "type": "text", "placeholder": "What's on sale", "required": True},
                   {"name": "discount", "label": "Discount", "type": "text", "placeholder": "50% OFF", "required": True},
                   {"name": "deadline", "label": "Deadline", "type": "text", "placeholder": "Tonight at midnight", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Shop now", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "FACEBOOK", "INSTAGRAM"], "tone": "urgent",
     "suggested_hashtags": ["#FlashSale", "#LimitedTime", "#Sale"], "color_scheme": "#E74C3C", "icon": "zap"},
    
    {"name": "🎁 Discount Code", "description": "Share promo codes", "category": "promotional",
     "content_template": "🎁 EXCLUSIVE DISCOUNT!\n\nUse code: {code}\n\n{discount_details}\n\n⏰ Valid until: {expiry}\n\n{cta}",
     "variables": [{"name": "code", "label": "Code", "type": "text", "placeholder": "SAVE20", "required": True},
                   {"name": "discount_details", "label": "Details", "type": "text", "placeholder": "20% off everything", "required": True},
                   {"name": "expiry", "label": "Expiry", "type": "date", "placeholder": "MM/DD/YYYY", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Shop now", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "FACEBOOK", "INSTAGRAM"], "tone": "friendly",
     "suggested_hashtags": ["#DiscountCode", "#Promo", "#Save"], "color_scheme": "#9B59B6", "icon": "tag"},
    
    {"name": "🚚 Free Shipping", "description": "Shipping promotion", "category": "promotional",
     "content_template": "🚚 FREE SHIPPING!\n\n{offer_details}\n\n{minimum_order}\n\n⏰ {duration}\n\n{cta}",
     "variables": [{"name": "offer_details", "label": "Details", "type": "text", "placeholder": "On all orders", "required": True},
                   {"name": "minimum_order", "label": "Minimum", "type": "text", "placeholder": "No minimum", "required": False},
                   {"name": "duration", "label": "Duration", "type": "text", "placeholder": "This weekend only", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Order now", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "FACEBOOK", "INSTAGRAM"], "tone": "friendly",
     "suggested_hashtags": ["#FreeShipping", "#Deal", "#Offer"], "color_scheme": "#27AE60", "icon": "truck"},
    
    {"name": "🎯 Bundle Deal", "description": "Package offers", "category": "promotional",
     "content_template": "🎯 BUNDLE & SAVE!\n\n{bundle_description}\n\n💰 Save {savings}\n\n{what_included}\n\n{cta}",
     "variables": [{"name": "bundle_description", "label": "Bundle", "type": "text", "placeholder": "Complete package", "required": True},
                   {"name": "savings", "label": "Savings", "type": "text", "placeholder": "30%", "required": True},
                   {"name": "what_included", "label": "Includes", "type": "text", "placeholder": "What's in bundle", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Get bundle", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "FACEBOOK", "INSTAGRAM"], "tone": "professional",
     "suggested_hashtags": ["#BundleDeal", "#SaveMore", "#Package"], "color_scheme": "#F39C12", "icon": "package"},
    
    {"name": "🎊 BOGO Offer", "description": "Buy one get one", "category": "promotional",
     "content_template": "🎊 BUY ONE GET ONE!\n\n{offer_details}\n\n{terms}\n\n⏰ {deadline}\n\n{cta}",
     "variables": [{"name": "offer_details", "label": "Offer", "type": "text", "placeholder": "BOGO 50% off", "required": True},
                   {"name": "terms", "label": "Terms", "type": "text", "placeholder": "On select items", "required": False},
                   {"name": "deadline", "label": "Deadline", "type": "text", "placeholder": "Ends Sunday", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Shop BOGO", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "FACEBOOK", "INSTAGRAM"], "tone": "urgent",
     "suggested_hashtags": ["#BOGO", "#BuyOneGetOne", "#Deal"], "color_scheme": "#E91E63", "icon": "shopping-cart"},
    
    # INSPIRATIONAL (5)
    {"name": "✨ Monday Motivation", "description": "Start the week strong", "category": "inspirational",
     "content_template": "✨ MONDAY MOTIVATION\n\n{quote}\n\n{reflection}\n\nLet's make this week amazing! 💪",
     "variables": [{"name": "quote", "label": "Quote", "type": "text", "placeholder": "Inspirational quote", "required": True},
                   {"name": "reflection", "label": "Reflection", "type": "text", "placeholder": "Your thoughts", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "inspirational",
     "suggested_hashtags": ["#MondayMotivation", "#Inspiration", "#Motivation"], "color_scheme": "#FF6B6B", "icon": "sunrise"},
    
    {"name": "🎯 Goal Setting", "description": "Inspire action", "category": "inspirational",
     "content_template": "🎯 SET YOUR GOALS\n\n{goal_prompt}\n\n{action_steps}\n\nWhat's your goal? Share below! 👇",
     "variables": [{"name": "goal_prompt", "label": "Prompt", "type": "text", "placeholder": "What do you want to achieve?", "required": True},
                   {"name": "action_steps", "label": "Steps", "type": "text", "placeholder": "How to start", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "inspirational",
     "suggested_hashtags": ["#Goals", "#Success", "#Achievement"], "color_scheme": "#3498DB", "icon": "target"},
    
    {"name": "💪 Success Story", "description": "Share wins", "category": "inspirational",
     "content_template": "💪 SUCCESS STORY\n\n{achievement}\n\n{journey}\n\n{lesson}\n\nYour turn! 🚀",
     "variables": [{"name": "achievement", "label": "Achievement", "type": "text", "placeholder": "What was accomplished", "required": True},
                   {"name": "journey", "label": "Journey", "type": "text", "placeholder": "How it happened", "required": True},
                   {"name": "lesson", "label": "Lesson", "type": "text", "placeholder": "Key takeaway", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "inspirational",
     "suggested_hashtags": ["#SuccessStory", "#Achievement", "#Inspiration"], "color_scheme": "#27AE60", "icon": "award"},
    
    {"name": "🌟 Thought Leadership", "description": "Share insights", "category": "inspirational",
     "content_template": "🌟 THOUGHT OF THE DAY\n\n{insight}\n\n{elaboration}\n\nWhat do you think? 💭",
     "variables": [{"name": "insight", "label": "Insight", "type": "text", "placeholder": "Your thought", "required": True},
                   {"name": "elaboration", "label": "Elaboration", "type": "text", "placeholder": "Expand on it", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK"], "tone": "professional",
     "suggested_hashtags": ["#ThoughtLeadership", "#Insights", "#Wisdom"], "color_scheme": "#9B59B6", "icon": "brain"},
    
    {"name": "🔥 Overcome Challenges", "description": "Motivate through obstacles", "category": "inspirational",
     "content_template": "🔥 OVERCOMING CHALLENGES\n\n{challenge}\n\n{solution}\n\n{encouragement}\n\nYou've got this! 💪",
     "variables": [{"name": "challenge", "label": "Challenge", "type": "text", "placeholder": "Common obstacle", "required": True},
                   {"name": "solution", "label": "Solution", "type": "text", "placeholder": "How to overcome", "required": True},
                   {"name": "encouragement", "label": "Encouragement", "type": "text", "placeholder": "Motivational message", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "inspirational",
     "suggested_hashtags": ["#Motivation", "#OvercomeChallenges", "#Growth"], "color_scheme": "#E74C3C", "icon": "trending-up"},
    
    # EVENT PROMOTION (5)
    {"name": "📅 Event Announcement", "description": "Announce your event", "category": "event_promotion",
     "content_template": "📅 EVENT ANNOUNCEMENT\n\n{event_name}\n\n📍 {location}\n🗓️ {date}\n⏰ {time}\n\n{description}\n\n{registration_link}",
     "variables": [{"name": "event_name", "label": "Event Name", "type": "text", "placeholder": "Event title", "required": True},
                   {"name": "location", "label": "Location", "type": "text", "placeholder": "Where", "required": True},
                   {"name": "date", "label": "Date", "type": "date", "placeholder": "MM/DD/YYYY", "required": True},
                   {"name": "time", "label": "Time", "type": "text", "placeholder": "6:00 PM", "required": True},
                   {"name": "description", "label": "Description", "type": "text", "placeholder": "Event details", "required": True},
                   {"name": "registration_link", "label": "Link", "type": "url", "placeholder": "Register here", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "professional",
     "suggested_hashtags": ["#Event", "#Register", "#JoinUs"], "color_scheme": "#3498DB", "icon": "calendar"},
    
    {"name": "🎟️ Early Bird", "description": "Early registration offer", "category": "event_promotion",
     "content_template": "🎟️ EARLY BIRD SPECIAL!\n\n{event_name}\n\n💰 Save {discount} - Register by {deadline}\n\n{event_highlights}\n\n{registration_link}",
     "variables": [{"name": "event_name", "label": "Event", "type": "text", "placeholder": "Event name", "required": True},
                   {"name": "discount", "label": "Discount", "type": "text", "placeholder": "30%", "required": True},
                   {"name": "deadline", "label": "Deadline", "type": "date", "placeholder": "MM/DD/YYYY", "required": True},
                   {"name": "event_highlights", "label": "Highlights", "type": "text", "placeholder": "What to expect", "required": True},
                   {"name": "registration_link", "label": "Link", "type": "url", "placeholder": "Register", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "urgent",
     "suggested_hashtags": ["#EarlyBird", "#Register", "#SaveNow"], "color_scheme": "#F39C12", "icon": "ticket"},
    
    {"name": "⏰ Event Countdown", "description": "Build event excitement", "category": "event_promotion",
     "content_template": "⏰ {days} DAYS UNTIL {event_name}!\n\n{excitement_builder}\n\n{what_to_expect}\n\n{registration_status}",
     "variables": [{"name": "days", "label": "Days", "type": "number", "placeholder": "7", "required": True},
                   {"name": "event_name", "label": "Event", "type": "text", "placeholder": "Event name", "required": True},
                   {"name": "excitement_builder", "label": "Excitement", "type": "text", "placeholder": "Get ready for...", "required": True},
                   {"name": "what_to_expect", "label": "Expectations", "type": "text", "placeholder": "What's happening", "required": True},
                   {"name": "registration_status", "label": "Status", "type": "text", "placeholder": "Spots filling fast", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "urgent",
     "suggested_hashtags": ["#Countdown", "#Event", "#ComingSoon"], "color_scheme": "#E74C3C", "icon": "clock"},
    
    {"name": "🎤 Speaker Spotlight", "description": "Highlight event speakers", "category": "event_promotion",
     "content_template": "🎤 SPEAKER SPOTLIGHT\n\n{speaker_name}\n{speaker_title}\n\n{bio}\n\n{topic}\n\n{event_details}",
     "variables": [{"name": "speaker_name", "label": "Name", "type": "text", "placeholder": "Speaker name", "required": True},
                   {"name": "speaker_title", "label": "Title", "type": "text", "placeholder": "Job title", "required": True},
                   {"name": "bio", "label": "Bio", "type": "text", "placeholder": "Brief bio", "required": True},
                   {"name": "topic", "label": "Topic", "type": "text", "placeholder": "Speaking about", "required": True},
                   {"name": "event_details", "label": "Event Info", "type": "text", "placeholder": "Event details", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "professional",
     "suggested_hashtags": ["#Speaker", "#Event", "#Learn"], "color_scheme": "#9B59B6", "icon": "mic"},
    
    {"name": "📸 Event Recap", "description": "Share event highlights", "category": "event_promotion",
     "content_template": "📸 EVENT RECAP\n\n{event_name} was amazing!\n\n{highlights}\n\n{attendee_count}\n\n{next_event}",
     "variables": [{"name": "event_name", "label": "Event", "type": "text", "placeholder": "Event name", "required": True},
                   {"name": "highlights", "label": "Highlights", "type": "text", "placeholder": "Best moments", "required": True},
                   {"name": "attendee_count", "label": "Attendance", "type": "text", "placeholder": "Number of attendees", "required": False},
                   {"name": "next_event", "label": "Next Event", "type": "text", "placeholder": "Coming up next", "required": False}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "friendly",
     "suggested_hashtags": ["#EventRecap", "#Highlights", "#ThankYou"], "color_scheme": "#27AE60", "icon": "camera"},
    
    # ANNOUNCEMENT (5)
    {"name": "📢 Company News", "description": "Share company updates", "category": "announcement",
     "content_template": "📢 COMPANY NEWS\n\n{headline}\n\n{details}\n\n{impact}\n\n{cta}",
     "variables": [{"name": "headline", "label": "Headline", "type": "text", "placeholder": "Main news", "required": True},
                   {"name": "details", "label": "Details", "type": "text", "placeholder": "More information", "required": True},
                   {"name": "impact", "label": "Impact", "type": "text", "placeholder": "What it means", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Learn more", "required": False}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK"], "tone": "professional",
     "suggested_hashtags": ["#CompanyNews", "#Announcement", "#Update"], "color_scheme": "#2C3E50", "icon": "megaphone"},
    
    {"name": "🤝 Partnership", "description": "Announce partnerships", "category": "announcement",
     "content_template": "🤝 PARTNERSHIP ANNOUNCEMENT\n\nExcited to partner with {partner_name}!\n\n{partnership_details}\n\n{benefits}\n\n{cta}",
     "variables": [{"name": "partner_name", "label": "Partner", "type": "text", "placeholder": "Partner name", "required": True},
                   {"name": "partnership_details", "label": "Details", "type": "text", "placeholder": "What partnership entails", "required": True},
                   {"name": "benefits", "label": "Benefits", "type": "text", "placeholder": "What this means", "required": True},
                   {"name": "cta", "label": "CTA", "type": "text", "placeholder": "Learn more", "required": False}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK"], "tone": "professional",
     "suggested_hashtags": ["#Partnership", "#Collaboration", "#Announcement"], "color_scheme": "#3498DB", "icon": "handshake"},
    
    {"name": "🏆 Award Recognition", "description": "Celebrate achievements", "category": "announcement",
     "content_template": "🏆 AWARD ANNOUNCEMENT\n\n{award_name}\n\n{achievement_details}\n\n{gratitude}\n\n{future_plans}",
     "variables": [{"name": "award_name", "label": "Award", "type": "text", "placeholder": "Award received", "required": True},
                   {"name": "achievement_details", "label": "Details", "type": "text", "placeholder": "What was achieved", "required": True},
                   {"name": "gratitude", "label": "Thanks", "type": "text", "placeholder": "Thank you message", "required": True},
                   {"name": "future_plans", "label": "Future", "type": "text", "placeholder": "What's next", "required": False}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "professional",
     "suggested_hashtags": ["#Award", "#Achievement", "#Recognition"], "color_scheme": "#F39C12", "icon": "award"},
    
    {"name": "🎯 Milestone", "description": "Celebrate milestones", "category": "announcement",
     "content_template": "🎯 MILESTONE ACHIEVED!\n\n{milestone}\n\n{journey}\n\n{gratitude}\n\n{next_goal}",
     "variables": [{"name": "milestone", "label": "Milestone", "type": "text", "placeholder": "What was achieved", "required": True},
                   {"name": "journey", "label": "Journey", "type": "text", "placeholder": "How you got here", "required": True},
                   {"name": "gratitude", "label": "Thanks", "type": "text", "placeholder": "Thank supporters", "required": True},
                   {"name": "next_goal", "label": "Next Goal", "type": "text", "placeholder": "What's next", "required": False}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "friendly",
     "suggested_hashtags": ["#Milestone", "#Achievement", "#ThankYou"], "color_scheme": "#27AE60", "icon": "flag"},
    
    {"name": "👥 Team Update", "description": "Introduce team members", "category": "announcement",
     "content_template": "👥 TEAM UPDATE\n\n{update_type} {person_name}!\n\n{role}\n\n{background}\n\n{welcome_message}",
     "variables": [{"name": "update_type", "label": "Type", "type": "text", "placeholder": "Welcome/Congratulations", "required": True},
                   {"name": "person_name", "label": "Name", "type": "text", "placeholder": "Team member name", "required": True},
                   {"name": "role", "label": "Role", "type": "text", "placeholder": "Position", "required": True},
                   {"name": "background", "label": "Background", "type": "text", "placeholder": "Brief bio", "required": True},
                   {"name": "welcome_message", "label": "Message", "type": "text", "placeholder": "Welcome note", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK"], "tone": "friendly",
     "suggested_hashtags": ["#TeamUpdate", "#Welcome", "#Team"], "color_scheme": "#9B59B6", "icon": "users"},
    
    # BEHIND THE SCENES (5)
    {"name": "🎬 BTS Peek", "description": "Show behind the scenes", "category": "behind_scenes",
     "content_template": "🎬 BEHIND THE SCENES\n\n{what_showing}\n\n{interesting_detail}\n\n{context}\n\nWant to see more? 👀",
     "variables": [{"name": "what_showing", "label": "What", "type": "text", "placeholder": "What you're showing", "required": True},
                   {"name": "interesting_detail", "label": "Detail", "type": "text", "placeholder": "Interesting fact", "required": True},
                   {"name": "context", "label": "Context", "type": "text", "placeholder": "Why it matters", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "FACEBOOK", "INSTAGRAM"], "tone": "casual",
     "suggested_hashtags": ["#BehindTheScenes", "#BTS", "#Insider"], "color_scheme": "#E91E63", "icon": "film"},
    
    {"name": "👋 Team Introduction", "description": "Introduce team members", "category": "behind_scenes",
     "content_template": "👋 MEET THE TEAM\n\n{name} - {role}\n\n{fun_fact}\n\n{favorite_thing}\n\nSay hi! 👇",
     "variables": [{"name": "name", "label": "Name", "type": "text", "placeholder": "Team member", "required": True},
                   {"name": "role", "label": "Role", "type": "text", "placeholder": "Position", "required": True},
                   {"name": "fun_fact", "label": "Fun Fact", "type": "text", "placeholder": "Interesting fact", "required": True},
                   {"name": "favorite_thing", "label": "Favorite", "type": "text", "placeholder": "Favorite part of job", "required": True}],
     "platform_variations": {}, "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"], "tone": "casual",
     "suggested_hashtags": ["#MeetTheTeam", "#TeamSpotlight", "#OurTeam"], "color_scheme": "#3498DB", "icon": "user"},
    
    {"name": "🏢 Office Tour", "description": "Show your workspace", "category": "behind_scenes",
     "content_template": "🏢 OFFICE TOUR\n\n{area_description}\n\n{unique_feature}\n\n{team_culture}\n\nWant to join us? 🚀",
     "variables": [{"name": "area_description", "label": "Area", "type": "text", "placeholder": "What area showing", "required": True},
                   {"name": "unique_feature", "label": "Feature", "type": "text", "placeholder": "Cool feature", "required": True},
                   {"name": "team_culture", "label": "Culture", "type": "text", "placeholder": "Team vibe", "required": True}],
     "platform_variations": {}, "supported_platforms": ["FACEBOOK", "INSTAGRAM", "LINKEDIN"], "tone": "casual",
     "suggested_hashtags": ["#OfficeTour", "#Workspace", "#TeamCulture"], "color_scheme": "#27AE60", "icon": "home"},
    
    {"name": "📅 Day in the Life", "description": "Show daily routine", "category": "behind_scenes",
     "content_template": "📅 DAY IN THE LIFE\n\n{role}\n\n{morning_routine}\n{afternoon_activity}\n{evening_wrap}\n\nTypical day! ✨",
     "variables": [{"name": "role", "label": "Role", "type": "text", "placeholder": "Position", "required": True},
                   {"name": "morning_routine", "label": "Morning", "type": "text", "placeholder": "Morning activities", "required": True},
                   {"name": "afternoon_activity", "label": "Afternoon", "type": "text", "placeholder": "Afternoon tasks", "required": True},
                   {"name": "evening_wrap", "label": "Evening", "type": "text", "placeholder": "End of day", "required": True}],
     "platform_variations": {}, "supported_platforms": ["INSTAGRAM", "FACEBOOK", "LINKEDIN"], "tone": "casual",
     "suggested_hashtags": ["#DayInTheLife", "#BehindTheScenes", "#WorkLife"], "color_scheme": "#F39C12", "icon": "clock"},
    
    {"name": "🎨 Creative Process", "description": "Show how you create", "category": "behind_scenes",
     "content_template": "🎨 CREATIVE PROCESS\n\n{what_creating}\n\n{step_1}\n{step_2}\n{step_3}\n\n{final_result}",
     "variables": [{"name": "what_creating", "label": "Creating", "type": "text", "placeholder": "What you're making", "required": True},
                   {"name": "step_1", "label": "Step 1", "type": "text", "placeholder": "First step", "required": True},
                   {"name": "step_2", "label": "Step 2", "type": "text", "placeholder": "Second step", "required": True},
                   {"name": "step_3", "label": "Step 3", "type": "text", "placeholder": "Third step", "required": True},
                   {"name": "final_result", "label": "Result", "type": "text", "placeholder": "End result", "required": True}],
     "platform_variations": {}, "supported_platforms": ["INSTAGRAM", "FACEBOOK", "TWITTER"], "tone": "casual",
     "suggested_hashtags": ["#CreativeProcess", "#BehindTheScenes", "#HowItsMade"], "color_scheme": "#9B59B6", "icon": "palette"},
]


async def seed_templates():
    """Seed database with 40 premium templates"""
    async with AsyncSessionLocal() as db:
        try:
            print("🌱 Starting premium template seed...")
            print(f"📊 Total templates to create: {len(TEMPLATES)}\n")
            
            # Check existing templates
            result = await db.execute(select(PostTemplate).where(PostTemplate.is_system == True))
            existing = result.scalars().all()
            
            if existing:
                print(f"⚠️  Found {len(existing)} existing system templates")
                response = input("Delete existing and reseed? (y/n): ")
                if response.lower() == 'y':
                    for template in existing:
                        await db.delete(template)
                    await db.commit()
                    print("✅ Cleared existing templates\n")
                else:
                    print("❌ Cancelled - keeping existing templates")
                    return
            
            # Create templates
            created_count = 0
            for template_data in TEMPLATES:
                template = PostTemplate(
                    name=template_data["name"],
                    description=template_data["description"],
                    category=template_data["category"],
                    content_template=template_data["content_template"],
                    variables=template_data["variables"],
                    platform_variations=template_data.get("platform_variations", {}),
                    supported_platforms=template_data["supported_platforms"],
                    tone=template_data["tone"],
                    suggested_hashtags=template_data.get("suggested_hashtags", []),
                    color_scheme=template_data["color_scheme"],
                    icon=template_data["icon"],
                    is_system=True,
                    is_public=True,
                    usage_count=0,
                    success_rate=0
                )
                
                db.add(template)
                created_count += 1
                print(f"✅ {created_count}/{len(TEMPLATES)}: {template_data['name']}")
            
            await db.commit()
            print(f"\n🎉 Successfully seeded {created_count} premium templates!")
            print("\n📋 Template breakdown by category:")
            
            # Show category breakdown
            categories = {}
            for t in TEMPLATES:
                cat = t['category']
                categories[cat] = categories.get(cat, 0) + 1
            
            for cat, count in sorted(categories.items()):
                print(f"   • {cat.replace('_', ' ').title()}: {count} templates")
            
        except Exception as e:
            print(f"\n❌ Error seeding templates: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(seed_templates())
