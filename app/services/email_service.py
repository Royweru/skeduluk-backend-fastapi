# app/services/email_service.py
import os
from typing import Optional
from jinja2 import Template
from dotenv import load_dotenv
import asyncio
import httpx

load_dotenv()


class EmailService:
    """Email sending service supporting both SMTP and Resend"""
    
    def __init__(self):
        # Check for Resend API key first (preferred)
        self.resend_api_key = os.getenv("RESEND_API_KEY")
        self.use_resend = bool(self.resend_api_key)
        
        # SMTP fallback
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_username or "noreply@skeduluk.com")
        self.from_name = os.getenv("FROM_NAME", "Skeduluk")
        
        if self.use_resend:
            print("✅ Using Resend for email delivery")
        elif self.smtp_username and self.smtp_password:
            print("✅ Using SMTP for email delivery")
        else:
            print("⚠️  WARNING: No email provider configured")
    
    async def _send_via_resend(
        self, 
        to_email: str, 
        subject: str, 
        html_content: str
    ) -> bool:
        """Send email via Resend API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.resend_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "from": f"{self.from_name} <{self.from_email}>",
                        "to": [to_email],
                        "subject": subject,
                        "html": html_content
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Email sent via Resend to {to_email} (ID: {result.get('id')})")
                    return True
                else:
                    print(f"❌ Resend API error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Resend error: {type(e).__name__}: {e}")
            return False
    
    async def _send_via_smtp(
        self, 
        to_email: str, 
        subject: str, 
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send email via SMTP"""
        import smtplib
        import ssl
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        try:
            if not self.smtp_username or not self.smtp_password:
                print("❌ SMTP credentials not configured")
                return False
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            if text_content:
                msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            print(f"📧 Attempting SMTP via {self.smtp_server}:{self.smtp_port}")
            
            # Try SSL first (port 465), then STARTTLS (port 587)
            if self.smtp_port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context, timeout=10) as server:
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
            else:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                    server.starttls(context=context)
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
            
            print(f"✅ Email sent via SMTP to {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ SMTP error: {type(e).__name__}: {e}")
            return False
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send email using available provider"""
        if self.use_resend:
            return await self._send_via_resend(to_email, subject, html_content)
        else:
            return await self._send_via_smtp(to_email, subject, html_content, text_content)
    
    async def send_verification_email(self, email: str, verification_token: str) -> bool:
        """Send email verification email"""
        try:
            verification_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/verify-email?token={verification_token}"
            
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Verify Your Email</title>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                    .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
                    .header h1 { color: white; margin: 0; font-size: 28px; }
                    .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                    .button { display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🎉 Welcome to Skeduluk!</h1>
                    </div>
                    <div class="content">
                        <p>Hi there!</p>
                        <p>Thank you for signing up. Please verify your email by clicking the button below:</p>
                        <div style="text-align: center;">
                            <a href="{{ verification_url }}" class="button">Verify Email Address</a>
                        </div>
                        <p>Or copy this link: {{ verification_url }}</p>
                        <p>This link expires in 24 hours.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            text_template = """
            Welcome to Skeduluk!
            
            Hi there!
            
            Please verify your email by visiting: {{ verification_url }}
            
            This link expires in 24 hours.
            """
            
            html_content = Template(html_template).render(verification_url=verification_url)
            text_content = Template(text_template).render(verification_url=verification_url)
            
            return await self.send_email(
                to_email=email,
                subject="Verify Your Email - Skeduluk",
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            print(f"❌ Failed to send verification email: {e}")
            return False
    
    async def send_password_reset_email(self, email: str, reset_token: str) -> bool:
        """Send password reset email"""
        try:
            reset_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/reset-password?token={reset_token}"
            
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Reset Your Password</title>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                    .header { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
                    .header h1 { color: white; margin: 0; font-size: 28px; }
                    .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                    .button { display: inline-block; background: #f5576c; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔐 Reset Your Password</h1>
                    </div>
                    <div class="content">
                        <p>Click the button below to reset your password:</p>
                        <div style="text-align: center;">
                            <a href="{{ reset_url }}" class="button">Reset Password</a>
                        </div>
                        <p>Or copy this link: {{ reset_url }}</p>
                        <p>This link expires in 1 hour.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            html_content = Template(html_template).render(reset_url=reset_url)
            
            return await self.send_email(
                to_email=email,
                subject="Reset Your Password - Skeduluk",
                html_content=html_content
            )
            
        except Exception as e:
            print(f"❌ Failed to send password reset email: {e}")
            return False


email_service = EmailService()