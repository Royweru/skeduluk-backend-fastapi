# app/services/email_service.py
import os
import base64
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

# Scopes needed for sending email
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

class EmailService:
    """
    Production-Ready Email Service using Google Gmail API.
    Used for Traditional Sign-up Verification & Password Resets.
    """
    
    def __init__(self):
        self.service = None
        self.sender_email = os.getenv("GMAIL_SENDER_EMAIL") 
        self.from_name = os.getenv("FROM_NAME", "Skeduluk")
        self._authenticate()
    
    def _authenticate(self):
        """Authenticates with Google (Service Account or User Token)"""
        creds = None
        service_account_path = 'service_account.json'
        token_path = 'token.json'
        
        try:
            if os.path.exists(service_account_path):
                print("🔐 Authenticating via Service Account...")
                creds = service_account.Credentials.from_service_account_file(
                    service_account_path, scopes=SCOPES
                )
            elif os.path.exists(token_path):
                print("🔐 Authenticating via User Token...")
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())

            if creds:
                self.service = build('gmail', 'v1', credentials=creds)
                print("✅ Gmail API Service Ready")
            else:
                print("⚠️  No Google Credentials found. Emails will fail.")
                
        except Exception as e:
            print(f"❌ Gmail Auth Failed: {str(e)}")

    async def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Low-level send function using Gmail API"""
        if not self.service:
            print("❌ Service not initialized")
            return False

        try:
            message = MIMEMultipart('alternative')
            message['to'] = to_email
            message['from'] = f"{self.from_name} <{self.sender_email}>"
            message['subject'] = subject
            message.attach(MIMEText(html_content, 'html'))

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            self.service.users().messages().send(
                userId="me", 
                body={'raw': raw_message}
            ).execute()
            
            print(f"✅ Email sent to {to_email} via Gmail API")
            return True

        except Exception as e:
            print(f"❌ Gmail API Send Error: {e}")
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
            print(f"❌ Verification Logic Error: {e}")
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
            print(f"❌ Reset Logic Error: {e}")
            return False

email_service = EmailService()