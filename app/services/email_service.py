import os
import base64
import json
import tempfile
from typing import Optional
from jinja2 import Template
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Google API Imports
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.oauth2 import service_account

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/gmail.send']


class EmailService:
    def __init__(self):
        self.service = None
        self.sender_email = os.getenv("GMAIL_SENDER_EMAIL")
        self.from_name = os.getenv("FROM_NAME", "Skeduluk management")
        self._authenticate()

    def _authenticate(self):
        """
        Secure Authentication Strategy:
        1. Production: checks GOOGLE_TOKEN_BASE64 env var (Memory)
        2. Local: checks token.json file (Disk)
        """
        creds = None

        # ---  PRODUCTION (Base64 Env Var) ---
        encoded_token = os.getenv("GOOGLE_TOKEN_BASE64")
        if encoded_token:
            print("Authenticating via Base64 Env Var...")
            try:
                # Decode the base64 string back to JSON
                decoded_json = base64.b64decode(encoded_token).decode('utf-8')
                token_info = json.loads(decoded_json)

                # Load credentials directly from the dictionary
                creds = Credentials.from_authorized_user_info(
                    token_info, SCOPES)
            except Exception as e:
                print(f" Failed to decode GOOGLE_TOKEN_BASE64: {e}")

        # --- STRATEGY 2: LOCAL FILE (Fallback) ---
        elif os.path.exists('token.json'):
            print("Authenticating via local token.json...")
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        # --- REFRESH LOGIC ---
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f" Token refresh failed: {e}")
                creds = None

        if creds:
            self.service = build('gmail', 'v1', credentials=creds)
            print(" Gmail API Service Ready")
        else:
            print(" No valid Google Credentials found. Emails will fail.")

    async def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        if not self.service:
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
                userId="me", body={'raw': raw_message}).execute()
            print(f" Email sent to {to_email}")
            return True
        except Exception as e:
            print(f" Gmail Send Error: {e}")
            return False

    async def send_verification_email(self, email: str, verification_token: str) -> bool:
        """Called by Traditional Sign Up Flow"""
        try:
            frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
            verification_url = f"{frontend_url}/verify-email?token={verification_token}"

            html_template = """
            <div style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>Welcome to Skeduluk!</h2>
                <p>Please verify your email to continue.</p>
                <a href="{{ url }}" style="background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Email</a>
                <p>Or click: {{ url }}</p>
            </div>
            """
            html_content = Template(html_template).render(url=verification_url)

            return await self.send_email(email, "Verify Your Account", html_content)
        except Exception as e:
            print(f" Verification Logic Error: {e}")
            return False

    async def send_password_reset_email(self, email: str, reset_token: str) -> bool:
        """Called by Forgot Password Flow"""
        try:
            frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
            reset_url = f"{frontend_url}/reset-password?token={reset_token}"

            html_template = """
            <div style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>Reset Password</h2>
                <a href="{{ url }}" style="background: #f5576c; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a>
            </div>
            """
            html_content = Template(html_template).render(url=reset_url)

            return await self.send_email(email, "Reset Your Password", html_content)
        except Exception as e:
            print(f" Reset Logic Error: {e}")
            return False


email_service = EmailService()
