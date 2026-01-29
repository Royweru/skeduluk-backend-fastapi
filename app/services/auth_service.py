# app/services/auth_service.py
from app.utils.security import verify_password, get_password_hash
import secrets
import string
import base64
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .. import models
from .email_service import email_service as EmailService


class AuthService:
    @staticmethod
    async def create_user_with_verification(
        db: AsyncSession,
        email: str,
        username: str,
        password: str
    ) -> models.User:
        """
        Creates user and sends verification email via Gmail API.
        """
        # Generate Token
        verification_token = base64.urlsafe_b64encode(
            secrets.token_bytes(32)).decode()
        verification_expires = datetime.utcnow() + timedelta(hours=24)

        # Create User (Not Verified yet)
        user = models.User(
            email=email,
            username=username,
            hashed_password=get_password_hash(password),
            is_email_verified=False,
            email_verification_token=verification_token,
            email_verification_expires=verification_expires,
            plan="trial",
            posts_used=0,
            posts_limit=30
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        # TRIGGER EMAIL (Uses Gmail API from email_service.py)
        try:
            await EmailService.send_verification_email(email, verification_token)
        except Exception as e:
            print(f"Failed to send email: {e}")

        return user

    @staticmethod
    async def get_or_create_google_user(
        db: AsyncSession,
        email: str,
        username_base: str
    ) -> models.User:
        """
        Logs in existing user OR creates new verified user.
        SKIPS email verification.
        Tracks auth_provider and last_login_method.
        """
        # Check if user exists
        result = await db.execute(select(models.User).where(models.User.email == email))
        user = result.scalar_one_or_none()

        if user:
            # Trust Google: Verify them if they weren't already
            if not user.is_email_verified:
                user.is_email_verified = True

            # ✅ Track login method - always update when logging in via Google
            user.last_login_method = "google"
            user.last_login = datetime.utcnow()
            user.updated_at = datetime.utcnow()

            await db.commit()
            return user

        # Create New User (Auto-Verified)
        # Generate random password (they use Google to login)
        alphabet = string.ascii_letters + string.digits + "!@#$%"
        random_password = ''.join(secrets.choice(alphabet) for i in range(20))

        # Unique username
        base_slug = username_base.lower().replace(' ', '')[:10]
        unique_username = f"{base_slug}_{secrets.token_hex(3)}"

        new_user = models.User(
            email=email,
            username=unique_username,
            hashed_password=get_password_hash(random_password),
            is_email_verified=True,  # ✅ Auto-verified by Google
            auth_provider="google",  # ✅ Track original signup method
            last_login_method="google",  # ✅ Track current login method
            last_login=datetime.utcnow(),
            plan="trial",
            posts_limit=10
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    @staticmethod
    async def verify_email(db: AsyncSession, token: str) -> bool:
        """Verify user email with token"""

        result = await db.execute(
            select(models.User).where(
                models.User.email_verification_token == token
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            return False

        if user.email_verification_expires and user.email_verification_expires < datetime.utcnow():
            return False

        user.is_email_verified = True
        user.email_verification_token = None
        user.email_verification_expires = None
        user.updated_at = datetime.utcnow()

        await db.commit()
        return True

    @staticmethod
    async def resend_verification_email(db: AsyncSession, email: str) -> bool:
        """Resend verification email"""

        result = await db.execute(
            select(models.User).where(models.User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            return False

        if user.is_email_verified:
            return False

        verification_token = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode()
        verification_expires = datetime.utcnow() + timedelta(hours=24)

        user.email_verification_token = verification_token
        user.email_verification_expires = verification_expires
        user.updated_at = datetime.utcnow()

        await db.commit()

        try:
            await EmailService.send_verification_email(email, verification_token)
            return True
        except Exception as e:
            print(f"Failed to send verification email: {e}")
            return False

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        username_or_email: str,
        password: str
    ) -> Optional[models.User]:
        """Authenticate user by username or email"""

        # Try username first
        result = await db.execute(
            select(models.User).where(
                models.User.username == username_or_email)
        )
        user = result.scalar_one_or_none()

        # Try email if username not found
        if not user:
            result = await db.execute(
                select(models.User).where(
                    models.User.email == username_or_email)
            )
            user = result.scalar_one_or_none()

        # Verify password
        if not user or not verify_password(password, user.hashed_password):
            return None

        return user

    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> Optional[models.User]:
        """Get user by username"""
        result = await db.execute(
            select(models.User).where(models.User.username == username)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[models.User]:
        """Get user by email"""
        result = await db.execute(
            select(models.User).where(models.User.email == email)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[models.User]:
        """Get user by ID"""
        result = await db.execute(
            select(models.User).where(models.User.id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def initiate_password_reset(db: AsyncSession, email: str) -> bool:
        """Initiate password reset"""

        result = await db.execute(
            select(models.User).where(models.User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            return True  # Don't reveal if user exists

        reset_token = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode()
        reset_expires = datetime.utcnow() + timedelta(hours=1)

        user.password_reset_token = reset_token
        user.password_reset_expires = reset_expires
        user.updated_at = datetime.utcnow()

        await db.commit()

        try:
            await EmailService.send_password_reset_email(email, reset_token)
            return True
        except Exception as e:
            print(f"Failed to send password reset email: {e}")
            return True

    @staticmethod
    async def reset_password(db: AsyncSession, token: str, new_password: str) -> bool:
        """Reset password with token"""

        result = await db.execute(
            select(models.User).where(
                models.User.password_reset_token == token
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            return False

        if user.password_reset_expires and user.password_reset_expires < datetime.utcnow():
            return False

        # Update password using auth.py function
        user.hashed_password = get_password_hash(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        user.updated_at = datetime.utcnow()

        await db.commit()
        return True

    @staticmethod
    async def change_password(
        db: AsyncSession,
        user_id: int,
        old_password: str,
        new_password: str
    ) -> bool:
        """Change user password (requires old password)"""

        user = await AuthService.get_user_by_id(db, user_id)

        if not user:
            return False

        # Verify old password using auth.py function
        if not verify_password(old_password, user.hashed_password):
            return False

        # Update to new password using auth.py function
        user.hashed_password = get_password_hash(new_password)
        user.updated_at = datetime.utcnow()

        await db.commit()
        return True

    @staticmethod
    async def update_user_profile(
        db: AsyncSession,
        user_id: int,
        email: Optional[str] = None,
        username: Optional[str] = None
    ) -> Optional[models.User]:
        """Update user profile information"""

        user = await AuthService.get_user_by_id(db, user_id)

        if not user:
            return None

        # Check if email is already taken
        if email and email != user.email:
            existing_user = await AuthService.get_user_by_email(db, email)
            if existing_user:
                raise ValueError("Email already in use")

            user.email = email
            user.is_email_verified = False

            verification_token = base64.urlsafe_b64encode(
                secrets.token_bytes(32)
            ).decode()
            verification_expires = datetime.utcnow() + timedelta(hours=24)

            user.email_verification_token = verification_token
            user.email_verification_expires = verification_expires

            try:
                await EmailService.send_verification_email(email, verification_token)
            except Exception as e:
                print(f"Failed to send verification email: {e}")

        # Check if username is already taken
        if username and username != user.username:
            existing_user = await AuthService.get_user_by_username(db, username)
            if existing_user:
                raise ValueError("Username already in use")
            user.username = username

        user.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(user)

        return user

    @staticmethod
    async def deactivate_account(db: AsyncSession, user_id: int) -> bool:
        """Deactivate user account"""

        user = await AuthService.get_user_by_id(db, user_id)

        if not user:
            return False

        user.is_active = False
        user.updated_at = datetime.utcnow()

        await db.commit()
        return True

    @staticmethod
    async def reactivate_account(db: AsyncSession, user_id: int) -> bool:
        """Reactivate user account"""

        user = await AuthService.get_user_by_id(db, user_id)

        if not user:
            return False

        user.is_active = True
        user.updated_at = datetime.utcnow()

        await db.commit()
        return True
