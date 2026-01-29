# app/services/email_service.py
import os
import base64
import json
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Google API Imports
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from .email_templates import EmailTemplates

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/gmail.send']


class EmailService:
    def __init__(self):
        self.service = None
        self.sender_email = os.getenv("GMAIL_SENDER_EMAIL")
        self.from_name = os.getenv("FROM_NAME", "Skeduluk")
        self.frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        self._authenticate()

    def _authenticate(self):
        """
        Secure Authentication Strategy:
        1. Production: checks GOOGLE_TOKEN_BASE64 env var (Memory)
        2. Local: checks token.json file (Disk)
        """
        creds = None

        # --- PRODUCTION (Base64 Env Var) ---
        encoded_token = os.getenv("GOOGLE_TOKEN_BASE64")
        if encoded_token:
            print("🔐 Authenticating via Base64 Env Var...")
            try:
                decoded_json = base64.b64decode(encoded_token).decode('utf-8')
                token_info = json.loads(decoded_json)
                creds = Credentials.from_authorized_user_info(
                    token_info, SCOPES)
            except Exception as e:
                print(f"❌ Failed to decode GOOGLE_TOKEN_BASE64: {e}")

        # --- LOCAL FILE (Fallback) ---
        elif os.path.exists('token.json'):
            print("🔐 Authenticating via local token.json...")
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        # --- REFRESH LOGIC ---
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"❌ Token refresh failed: {e}")
                creds = None

        if creds:
            self.service = build('gmail', 'v1', credentials=creds)
            print("✅ Gmail API Service Ready")
        else:
            print("⚠️ No valid Google Credentials found. Emails will fail.")

    async def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send an email using Gmail API."""
        if not self.service:
            print("❌ Gmail service not initialized")
            return False
        try:
            message = MIMEMultipart('alternative')
            message['to'] = to_email
            message['from'] = f"{self.from_name} <{self.sender_email}>"
            message['subject'] = subject
            message.attach(MIMEText(html_content, 'html'))
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()).decode('utf-8')
            self.service.users().messages().send(
                userId="me", body={'raw': raw_message}
            ).execute()
            print(f"✅ Email sent to {to_email}")
            return True
        except Exception as e:
            print(f"❌ Gmail Send Error: {e}")
            return False

    # ========================================
    # AUTHENTICATION EMAILS
    # ========================================

    async def send_verification_email(self, email: str, verification_token: str, username: str = "there") -> bool:
        """Send welcome/verification email to new users."""
        try:
            verification_url = f"{self.frontend_url}/verify-email?token={verification_token}"
            html_content = EmailTemplates.verification_email(
                verification_url=verification_url,
                username=username,
                frontend_url=self.frontend_url
            )
            return await self.send_email(email, "🎉 Welcome to Skeduluk - Verify Your Email", html_content)
        except Exception as e:
            print(f"❌ Verification Email Error: {e}")
            return False

    async def send_password_reset_email(self, email: str, reset_token: str) -> bool:
        """Send password reset email."""
        try:
            reset_url = f"{self.frontend_url}/reset-password?token={reset_token}"
            html_content = EmailTemplates.password_reset_email(
                reset_url=reset_url,
                frontend_url=self.frontend_url
            )
            return await self.send_email(email, "🔐 Reset Your Skeduluk Password", html_content)
        except Exception as e:
            print(f"❌ Password Reset Email Error: {e}")
            return False

    # ========================================
    # POST NOTIFICATION EMAILS
    # ========================================

    async def send_post_success_email(
        self,
        email: str,
        username: str,
        post_content: str,
        platform_results: List[Dict[str, Any]]
    ) -> bool:
        """
        Send celebratory email when a post is successfully published.

        Args:
            email: User's email address
            username: User's display name
            post_content: The original post content
            platform_results: List of dicts with platform, status, url keys
        """
        try:
            html_content = EmailTemplates.post_success_email(
                username=username,
                post_content=post_content,
                platforms=platform_results,
                frontend_url=self.frontend_url
            )
            return await self.send_email(
                email,
                "🎉 Your Post is Live!",
                html_content
            )
        except Exception as e:
            print(f"❌ Post Success Email Error: {e}")
            return False

    async def send_post_failure_email(
        self,
        email: str,
        username: str,
        post_content: str,
        error_message: str
    ) -> bool:
        """
        Send supportive email when a post fails to publish.

        Args:
            email: User's email address
            username: User's display name
            post_content: The original post content
            error_message: Description of what went wrong
        """
        try:
            html_content = EmailTemplates.post_failure_email(
                username=username,
                post_content=post_content,
                error_message=error_message,
                frontend_url=self.frontend_url
            )
            return await self.send_email(
                email,
                "⚠️ Action Needed: Post Publishing Issue",
                html_content
            )
        except Exception as e:
            print(f"❌ Post Failure Email Error: {e}")
            return False

    # ========================================
    # ANALYTICS EMAILS
    # ========================================

    async def send_weekly_analytics_email(
        self,
        email: str,
        username: str,
        stats: Dict[str, Any],
        top_posts: List[Dict[str, Any]]
    ) -> bool:
        """
        Send weekly analytics summary email.

        Args:
            email: User's email address
            username: User's display name
            stats: Dict with total_posts, total_views, total_engagement, growth_percent
            top_posts: List of top performing posts with content, views
        """
        try:
            html_content = EmailTemplates.weekly_analytics_email(
                username=username,
                stats=stats,
                top_posts=top_posts,
                frontend_url=self.frontend_url
            )
            return await self.send_email(
                email,
                "📊 Your Weekly Social Media Recap",
                html_content
            )
        except Exception as e:
            print(f"❌ Weekly Analytics Email Error: {e}")
            return False


# Global instance
email_service = EmailService()
