# app/services/email_templates.py
"""
Premium HTML email templates for Skeduluk notifications.
All templates use consistent branding with positive, encouraging messaging.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional


class EmailTemplates:
    """Premium HTML email templates with Skeduluk branding."""

    # Brand colors
    PRIMARY_COLOR = "#667eea"  # Purple gradient start
    SECONDARY_COLOR = "#764ba2"  # Purple gradient end
    ACCENT_COLOR = "#f59e0b"  # Amber/Gold
    SUCCESS_COLOR = "#10b981"  # Green
    WARNING_COLOR = "#f59e0b"  # Amber
    ERROR_COLOR = "#ef4444"  # Red
    TEXT_COLOR = "#1f2937"  # Dark gray
    MUTED_COLOR = "#6b7280"  # Gray

    @staticmethod
    def _base_template(content: str, preview_text: str = "") -> str:
        """Base email template with consistent header/footer."""
        return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Skeduluk</title>
    <!--[if mso]>
    <style type="text/css">
        table, td, div, h1, p {{font-family: Arial, sans-serif;}}
    </style>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f3f4f6;">
    <!-- Preview text -->
    <div style="display: none; max-height: 0; overflow: hidden;">
        {preview_text}
    </div>
    
    <!-- Main container -->
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #f3f4f6;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="width: 100%; max-width: 600px; border-collapse: collapse; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px 40px 24px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px 16px 0 0;">
                            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td align="center">
                                        <div style="display: inline-block; width: 48px; height: 48px; background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%); border-radius: 12px; margin-bottom: 16px;">
                                            <span style="display: block; line-height: 48px; font-size: 24px;">✨</span>
                                        </div>
                                        <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">
                                            Skeduluk
                                        </h1>
                                        <p style="margin: 4px 0 0; color: rgba(255,255,255,0.8); font-size: 14px;">
                                            Social Media Scheduler
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    {content}
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 40px 32px; text-align: center; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0 0 8px; color: #6b7280; font-size: 12px;">
                                You're receiving this because you have an account at Skeduluk.
                            </p>
                            <p style="margin: 0 0 16px; color: #6b7280; font-size: 12px;">
                                <a href="{{{{ frontend_url }}}}/dashboard/settings" style="color: #667eea; text-decoration: none;">Manage notification preferences</a>
                            </p>
                            <p style="margin: 0; color: #9ca3af; font-size: 11px;">
                                © {datetime.now().year} Skeduluk. Made with 💜 for content creators.
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
'''

    @classmethod
    def post_success_email(
        cls,
        username: str,
        post_content: str,
        platforms: List[Dict[str, Any]],
        frontend_url: str
    ) -> str:
        """
        Celebratory email when a post is successfully published.
        Includes positive messaging and platform-specific links.
        """
        # Truncate content for preview
        content_preview = post_content[:100] + \
            "..." if len(post_content) > 100 else post_content

        # Build platform results
        platform_rows = ""
        for p in platforms:
            platform_name = p.get("platform", "Platform")
            status = p.get("status", "success")
            url = p.get("url", "#")

            if status == "posted":
                icon = "✅"
                status_text = "Published"
                status_color = cls.SUCCESS_COLOR
            else:
                icon = "⚠️"
                status_text = "Failed"
                status_color = cls.ERROR_COLOR

            platform_rows += f'''
            <tr>
                <td style="padding: 12px 16px; border-bottom: 1px solid #f3f4f6;">
                    <table role="presentation" style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="width: 40px;">
                                <span style="font-size: 20px;">{icon}</span>
                            </td>
                            <td>
                                <p style="margin: 0; font-weight: 600; color: #1f2937;">{platform_name}</p>
                                <p style="margin: 2px 0 0; font-size: 12px; color: {status_color};">{status_text}</p>
                            </td>
                            <td style="text-align: right;">
                                <a href="{url}" style="display: inline-block; padding: 8px 16px; background-color: #f3f4f6; color: #667eea; text-decoration: none; border-radius: 8px; font-size: 13px; font-weight: 500;">View Post →</a>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            '''

        content = f'''
                    <!-- Success Banner -->
                    <tr>
                        <td style="padding: 32px 40px 24px; text-align: center;">
                            <div style="display: inline-block; width: 64px; height: 64px; background: linear-gradient(135deg, #10b981 0%, #34d399 100%); border-radius: 50%; margin-bottom: 16px;">
                                <span style="display: block; line-height: 64px; font-size: 32px;">🎉</span>
                            </div>
                            <h2 style="margin: 0 0 8px; color: #1f2937; font-size: 24px; font-weight: 700;">
                                Your Post is Live!
                            </h2>
                            <p style="margin: 0; color: #6b7280; font-size: 16px;">
                                Hey {username}, your content just went out to the world! 🚀
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Post Preview -->
                    <tr>
                        <td style="padding: 0 40px 24px;">
                            <div style="background-color: #f9fafb; border-radius: 12px; padding: 20px; border-left: 4px solid #667eea;">
                                <p style="margin: 0; color: #1f2937; font-size: 14px; line-height: 1.6;">
                                    "{content_preview}"
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Platform Results -->
                    <tr>
                        <td style="padding: 0 40px 24px;">
                            <h3 style="margin: 0 0 16px; color: #1f2937; font-size: 16px; font-weight: 600;">
                                📊 Publishing Results
                            </h3>
                            <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb;">
                                {platform_rows}
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Encouragement -->
                    <tr>
                        <td style="padding: 0 40px 32px; text-align: center;">
                            <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 12px; padding: 20px;">
                                <p style="margin: 0; color: #92400e; font-size: 14px; font-weight: 500;">
                                    💡 Pro tip: Engage with your audience within the first hour for maximum reach!
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- CTA -->
                    <tr>
                        <td style="padding: 0 40px 32px; text-align: center;">
                            <a href="{frontend_url}/dashboard/posts" style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; text-decoration: none; border-radius: 10px; font-size: 16px; font-weight: 600;">
                                View All Posts
                            </a>
                        </td>
                    </tr>
        '''

        return cls._base_template(content, f"🎉 Your post is live, {username}! Check out where it was published.")

    @classmethod
    def post_failure_email(
        cls,
        username: str,
        post_content: str,
        error_message: str,
        frontend_url: str
    ) -> str:
        """
        Supportive email when a post fails to publish.
        Focuses on solutions and encouragement.
        """
        content_preview = post_content[:80] + \
            "..." if len(post_content) > 80 else post_content

        content = f'''
                    <!-- Warning Banner -->
                    <tr>
                        <td style="padding: 32px 40px 24px; text-align: center;">
                            <div style="display: inline-block; width: 64px; height: 64px; background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%); border-radius: 50%; margin-bottom: 16px;">
                                <span style="display: block; line-height: 64px; font-size: 32px;">⚠️</span>
                            </div>
                            <h2 style="margin: 0 0 8px; color: #1f2937; font-size: 24px; font-weight: 700;">
                                Oops! Something Went Wrong
                            </h2>
                            <p style="margin: 0; color: #6b7280; font-size: 16px;">
                                Hey {username}, we hit a bump trying to publish your post.
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Post Preview -->
                    <tr>
                        <td style="padding: 0 40px 24px;">
                            <div style="background-color: #fef2f2; border-radius: 12px; padding: 20px; border-left: 4px solid #ef4444;">
                                <p style="margin: 0 0 8px; color: #991b1b; font-size: 12px; font-weight: 600; text-transform: uppercase;">
                                    Your Post
                                </p>
                                <p style="margin: 0; color: #1f2937; font-size: 14px; line-height: 1.6;">
                                    "{content_preview}"
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Error Details -->
                    <tr>
                        <td style="padding: 0 40px 24px;">
                            <div style="background-color: #f9fafb; border-radius: 12px; padding: 20px;">
                                <p style="margin: 0 0 8px; color: #6b7280; font-size: 12px; font-weight: 600;">
                                    What happened:
                                </p>
                                <p style="margin: 0; color: #1f2937; font-size: 14px;">
                                    {error_message}
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Solutions -->
                    <tr>
                        <td style="padding: 0 40px 24px;">
                            <h3 style="margin: 0 0 16px; color: #1f2937; font-size: 16px; font-weight: 600;">
                                🛠️ Quick Fixes to Try
                            </h3>
                            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0;">
                                        <span style="color: #667eea; margin-right: 8px;">✓</span>
                                        <span style="color: #4b5563;">Check your social account connections</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;">
                                        <span style="color: #667eea; margin-right: 8px;">✓</span>
                                        <span style="color: #4b5563;">Reconnect the platform if needed</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;">
                                        <span style="color: #667eea; margin-right: 8px;">✓</span>
                                        <span style="color: #4b5563;">Try scheduling the post again</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Encouragement -->
                    <tr>
                        <td style="padding: 0 40px 32px; text-align: center;">
                            <div style="background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); border-radius: 12px; padding: 20px;">
                                <p style="margin: 0; color: #1e40af; font-size: 14px; font-weight: 500;">
                                    💪 Don't worry! These things happen. Your content is still saved and ready to go!
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- CTA -->
                    <tr>
                        <td style="padding: 0 40px 32px; text-align: center;">
                            <a href="{frontend_url}/dashboard/posts" style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; text-decoration: none; border-radius: 10px; font-size: 16px; font-weight: 600;">
                                Try Again
                            </a>
                        </td>
                    </tr>
        '''

        return cls._base_template(content, f"⚠️ {username}, we need your attention on a post")

    @classmethod
    def weekly_analytics_email(
        cls,
        username: str,
        stats: Dict[str, Any],
        top_posts: List[Dict[str, Any]],
        frontend_url: str
    ) -> str:
        """
        Weekly analytics summary with positive, motivating metrics.
        """
        total_posts = stats.get("total_posts", 0)
        total_views = stats.get("total_views", 0)
        total_engagement = stats.get("total_engagement", 0)
        growth_percent = stats.get("growth_percent", 0)

        growth_color = cls.SUCCESS_COLOR if growth_percent >= 0 else cls.ERROR_COLOR
        growth_icon = "📈" if growth_percent >= 0 else "📉"
        growth_text = f"+{growth_percent}%" if growth_percent >= 0 else f"{growth_percent}%"

        # Build top posts section
        top_posts_html = ""
        for i, post in enumerate(top_posts[:3], 1):
            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else "📝"
            content = post.get("content", "")[:50] + "..."
            views = post.get("views", 0)

            top_posts_html += f'''
            <tr>
                <td style="padding: 12px 16px; border-bottom: 1px solid #f3f4f6;">
                    <table role="presentation" style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="width: 40px; font-size: 24px;">{medal}</td>
                            <td>
                                <p style="margin: 0; color: #1f2937; font-size: 14px; font-weight: 500;">{content}</p>
                                <p style="margin: 4px 0 0; color: #6b7280; font-size: 12px;">{views:,} views</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            '''

        content = f'''
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px 40px 24px; text-align: center;">
                            <div style="display: inline-block; width: 64px; height: 64px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 50%; margin-bottom: 16px;">
                                <span style="display: block; line-height: 64px; font-size: 32px;">📊</span>
                            </div>
                            <h2 style="margin: 0 0 8px; color: #1f2937; font-size: 24px; font-weight: 700;">
                                Your Weekly Recap
                            </h2>
                            <p style="margin: 0; color: #6b7280; font-size: 16px;">
                                Hey {username}, here's how you did this week! 🌟
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Stats Grid -->
                    <tr>
                        <td style="padding: 0 40px 24px;">
                            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="width: 33%; padding: 16px; text-align: center; background-color: #f9fafb; border-radius: 12px 0 0 12px;">
                                        <p style="margin: 0; font-size: 28px; font-weight: 700; color: #667eea;">{total_posts}</p>
                                        <p style="margin: 4px 0 0; font-size: 12px; color: #6b7280;">Posts</p>
                                    </td>
                                    <td style="width: 33%; padding: 16px; text-align: center; background-color: #f9fafb;">
                                        <p style="margin: 0; font-size: 28px; font-weight: 700; color: #10b981;">{total_views:,}</p>
                                        <p style="margin: 4px 0 0; font-size: 12px; color: #6b7280;">Views</p>
                                    </td>
                                    <td style="width: 33%; padding: 16px; text-align: center; background-color: #f9fafb; border-radius: 0 12px 12px 0;">
                                        <p style="margin: 0; font-size: 28px; font-weight: 700; color: #f59e0b;">{total_engagement:,}</p>
                                        <p style="margin: 4px 0 0; font-size: 12px; color: #6b7280;">Engagements</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Growth Banner -->
                    <tr>
                        <td style="padding: 0 40px 24px;">
                            <div style="background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); border-radius: 12px; padding: 20px; text-align: center;">
                                <p style="margin: 0; font-size: 14px; color: #065f46;">
                                    {growth_icon} Week over Week Growth: <strong style="color: {growth_color};">{growth_text}</strong>
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Top Posts -->
                    <tr>
                        <td style="padding: 0 40px 24px;">
                            <h3 style="margin: 0 0 16px; color: #1f2937; font-size: 16px; font-weight: 600;">
                                🏆 Your Top Performers
                            </h3>
                            <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb;">
                                {top_posts_html if top_posts_html else '<tr><td style="padding: 24px; text-align: center; color: #6b7280;">No posts this week yet. Keep creating! 🚀</td></tr>'}
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Motivation -->
                    <tr>
                        <td style="padding: 0 40px 32px; text-align: center;">
                            <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 12px; padding: 20px;">
                                <p style="margin: 0; color: #92400e; font-size: 14px; font-weight: 500;">
                                    🎯 You're doing amazing! Keep the momentum going this week!
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- CTA -->
                    <tr>
                        <td style="padding: 0 40px 32px; text-align: center;">
                            <a href="{frontend_url}/dashboard/analytics" style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; text-decoration: none; border-radius: 10px; font-size: 16px; font-weight: 600;">
                                View Full Analytics
                            </a>
                        </td>
                    </tr>
        '''

        return cls._base_template(content, f"📊 {username}, your weekly social media recap is ready!")

    @classmethod
    def password_reset_email(cls, reset_url: str, frontend_url: str) -> str:
        """Password reset email with security-focused messaging."""
        content = f'''
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px 40px 24px; text-align: center;">
                            <div style="display: inline-block; width: 64px; height: 64px; background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); border-radius: 50%; margin-bottom: 16px;">
                                <span style="display: block; line-height: 64px; font-size: 32px;">🔐</span>
                            </div>
                            <h2 style="margin: 0 0 8px; color: #1f2937; font-size: 24px; font-weight: 700;">
                                Reset Your Password
                            </h2>
                            <p style="margin: 0; color: #6b7280; font-size: 16px;">
                                We received a request to reset your password.
                            </p>
                        </td>
                    </tr>
                    
                    <!-- CTA -->
                    <tr>
                        <td style="padding: 0 40px 24px; text-align: center;">
                            <a href="{reset_url}" style="display: inline-block; padding: 16px 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; text-decoration: none; border-radius: 10px; font-size: 16px; font-weight: 600;">
                                Reset Password
                            </a>
                        </td>
                    </tr>
                    
                    <!-- Link fallback -->
                    <tr>
                        <td style="padding: 0 40px 24px;">
                            <div style="background-color: #f9fafb; border-radius: 12px; padding: 16px;">
                                <p style="margin: 0 0 8px; color: #6b7280; font-size: 12px;">
                                    Or copy and paste this link:
                                </p>
                                <p style="margin: 0; color: #667eea; font-size: 12px; word-break: break-all;">
                                    {reset_url}
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Security Note -->
                    <tr>
                        <td style="padding: 0 40px 32px;">
                            <div style="background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); border-radius: 12px; padding: 16px;">
                                <p style="margin: 0; color: #991b1b; font-size: 13px;">
                                    ⚠️ If you didn't request this, you can safely ignore this email.
                                    This link expires in 1 hour.
                                </p>
                            </div>
                        </td>
                    </tr>
        '''

        return cls._base_template(content, "Reset your Skeduluk password")

    @classmethod
    def verification_email(cls, verification_url: str, username: str, frontend_url: str) -> str:
        """Welcome/verification email for new users."""
        content = f'''
                    <!-- Welcome Header -->
                    <tr>
                        <td style="padding: 32px 40px 24px; text-align: center;">
                            <div style="display: inline-block; width: 64px; height: 64px; background: linear-gradient(135deg, #10b981 0%, #34d399 100%); border-radius: 50%; margin-bottom: 16px;">
                                <span style="display: block; line-height: 64px; font-size: 32px;">👋</span>
                            </div>
                            <h2 style="margin: 0 0 8px; color: #1f2937; font-size: 24px; font-weight: 700;">
                                Welcome to Skeduluk, {username}!
                            </h2>
                            <p style="margin: 0; color: #6b7280; font-size: 16px;">
                                Just one more step to get started.
                            </p>
                        </td>
                    </tr>
                    
                    <!-- CTA -->
                    <tr>
                        <td style="padding: 0 40px 24px; text-align: center;">
                            <a href="{verification_url}" style="display: inline-block; padding: 16px 40px; background: linear-gradient(135deg, #10b981 0%, #34d399 100%); color: #ffffff; text-decoration: none; border-radius: 10px; font-size: 16px; font-weight: 600;">
                                Verify My Email
                            </a>
                        </td>
                    </tr>
                    
                    <!-- Link fallback -->
                    <tr>
                        <td style="padding: 0 40px 24px;">
                            <div style="background-color: #f9fafb; border-radius: 12px; padding: 16px;">
                                <p style="margin: 0 0 8px; color: #6b7280; font-size: 12px;">
                                    Or copy and paste this link:
                                </p>
                                <p style="margin: 0; color: #667eea; font-size: 12px; word-break: break-all;">
                                    {verification_url}
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- What's Next -->
                    <tr>
                        <td style="padding: 0 40px 32px;">
                            <h3 style="margin: 0 0 16px; color: #1f2937; font-size: 16px; font-weight: 600;">
                                🚀 What's Next?
                            </h3>
                            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0;">
                                        <span style="color: #667eea; margin-right: 8px;">1.</span>
                                        <span style="color: #4b5563;">Connect your social accounts</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;">
                                        <span style="color: #667eea; margin-right: 8px;">2.</span>
                                        <span style="color: #4b5563;">Create your first post</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;">
                                        <span style="color: #667eea; margin-right: 8px;">3.</span>
                                        <span style="color: #4b5563;">Schedule it and watch the magic happen!</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
        '''

        return cls._base_template(content, f"Welcome to Skeduluk, {username}! Please verify your email.")
