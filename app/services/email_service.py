# app/services/email_service.py
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, Optional
from jinja2 import Template
import ssl
from dotenv import load_dotenv


load_dotenv()  # Load environment variables from .env file
class EmailService:
    """Email sending service using SMTP"""
    
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@socialscheduler.com")
        self.from_name = os.getenv("FROM_NAME", "Skeduluk")
    
    def _create_message(
        self, 
        to_email: str, 
        subject: str, 
        html_content: str, 
        text_content: Optional[str] = None
    ) -> MIMEMultipart:
        """Create email message"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{self.from_name} <{self.from_email}>"
        msg['To'] = to_email
        
        # Add text part
        if text_content:
            text_part = MIMEText(text_content, 'plain')
            msg.attach(text_part)
        
        # Add HTML part
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        return msg
    
    def _send_email(self, msg: MIMEMultipart) -> bool:
        """Send email using SMTP"""
        try:
            context = ssl.create_default_context()
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
                
            return True
            
        except Exception as e:
            print(f"SMTP Error: {e}")
            return False
    
    async def send_verification_email(self, email: str, verification_token: str) -> bool:
        """Send email verification email"""
        try:
            verification_url = f"{os.getenv('FRONTEND_URL')}/verify-email?token={verification_token}"
            
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
                        <p>This link expires in 24 hours.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            text_template = """
            Welcome to Social Scheduler!
            
            Hi there!
            
            Please verify your email by visiting: {{ verification_url }}
            
            This link expires in 24 hours.
            """
            
            html_content = Template(html_template).render(verification_url=verification_url)
            text_content = Template(text_template).render(verification_url=verification_url)
            
            msg = self._create_message(
                to_email=email,
                subject="Verify Your Email - Social Scheduler",
                html_content=html_content,
                text_content=text_content
            )
            
            return self._send_email(msg)
            
        except Exception as e:
            print(f"Failed to send verification email: {e}")
            return False
    
    async def send_password_reset_email(self, email: str, reset_token: str) -> bool:
        """Send password reset email"""
        try:
            reset_url = f"{os.getenv('FRONTEND_URL')}/reset-password?token={reset_token}"
            
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
                        <p>This link expires in 1 hour.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            html_content = Template(html_template).render(reset_url=reset_url)
            
            msg = self._create_message(
                to_email=email,
                subject="Reset Your Password - Social Scheduler",
                html_content=html_content
            )
            
            return self._send_email(msg)
            
        except Exception as e:
            print(f"Failed to send password reset email: {e}")
            return False
        
emaill_service = EmailService()