# Template seed data - 40 premium templates
# Import this in templates router to seed database

PREMIUM_TEMPLATES_DATA = [
    # PRODUCT LAUNCH (5)
    {"name": "🚀 Product Launch", "description": "Announce your new product with impact", "category": "product_launch",
     "content_template": "🎉 Introducing {product_name}!\n\n{description}\n\n✨ Key features:\n• {feature_1}\n• {feature_2}\n• {feature_3}\n\n{cta}",
     "variables": [
         {"name": "product_name", "label": "Product Name", "type": "text",
             "placeholder": "Your Product", "required": True},
         {"name": "description", "label": "Description", "type": "text",
             "placeholder": "Brief description", "required": True},
         {"name": "feature_1", "label": "Feature 1", "type": "text",
             "placeholder": "First feature", "required": True},
         {"name": "feature_2", "label": "Feature 2", "type": "text",
             "placeholder": "Second feature", "required": True},
         {"name": "feature_3", "label": "Feature 3", "type": "text",
             "placeholder": "Third feature", "required": True},
         {"name": "cta", "label": "Call to Action", "type": "text",
             "placeholder": "Learn more", "required": True}
     ],
     "platform_variations": {
         "TWITTER": "🎉 Introducing {product_name}!\n\n{description}\n\n✨ {feature_1}\n✨ {feature_2}\n✨ {feature_3}\n\n{cta}",
         "LINKEDIN": "Excited to announce: {product_name}\n\n{description}\n\nKey capabilities:\n→ {feature_1}\n→ {feature_2}\n→ {feature_3}\n\n{cta}\n\n#ProductLaunch #Innovation"
     },
     "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"],
     "tone": "professional",
     "suggested_hashtags": ["#ProductLaunch", "#NewProduct", "#Innovation"],
     "color_scheme": "#FF6B6B",
     "icon": "rocket"},

    {"name": "⏰ Launch Countdown", "description": "Build anticipation for your launch", "category": "product_launch",
     "content_template": "⏰ {days} DAYS UNTIL LAUNCH!\n\nGet ready for {product_name} 🚀\n\n{teaser}\n\n📅 {launch_date}\n\n{cta}",
     "variables": [
         {"name": "days", "label": "Days", "type": "number",
             "placeholder": "7", "required": True},
         {"name": "product_name", "label": "Product", "type": "text",
             "placeholder": "Product name", "required": True},
         {"name": "teaser", "label": "Teaser", "type": "text",
             "placeholder": "What to expect", "required": True},
         {"name": "launch_date", "label": "Date", "type": "date",
             "placeholder": "MM/DD/YYYY", "required": True},
         {"name": "cta", "label": "CTA", "type": "text",
             "placeholder": "Sign up", "required": True}
     ],
     "platform_variations": {},
     "supported_platforms": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"],
     "tone": "urgent",
     "suggested_hashtags": ["#CountdownToLaunch", "#ComingSoon"],
     "color_scheme": "#FFA500",
     "icon": "clock"},

    # Add more templates here - keeping file concise for now
    # The full 40 templates are in the seed script
]
