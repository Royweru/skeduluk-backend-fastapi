# app/database.py
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

load_dotenv()

def get_async_database_url():
    """Convert DATABASE_URL to asyncpg format"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Split URL at the '?' to separate base URL from query parameters
    if '?' in database_url:
        base_url = database_url.split('?')[0]
    else:
        base_url = database_url
    
    # Convert to asyncpg format
    if base_url.startswith('postgresql://'):
        async_url = base_url.replace('postgresql://', 'postgresql+asyncpg://')
    elif base_url.startswith('postgres://'):
        async_url = base_url.replace('postgres://', 'postgresql+asyncpg://')
    else:
        async_url = base_url
    
    return async_url

# ==================== GLOBAL ENGINE FOR FASTAPI ====================
# This engine is created once when the application starts and is used
# by all FastAPI requests. It's tied to the main event loop.

# Create async engine for FastAPI
engine = create_async_engine(
    get_async_database_url(),
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Verify connections are alive before using
    pool_recycle=300,  # Recycle connections after 5 minutes
    connect_args={
        "ssl": "require",  # Neon requires SSL
        "server_settings": {
            "application_name": "social_scheduler_fastapi"
        }
    }
)

# Create async session factory for FastAPI (bound to global engine)
AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Base class for SQLAlchemy models
Base = declarative_base()

# ==================== DEPENDENCY FOR FASTAPI ====================
# This is used in your FastAPI endpoints like:
# async def my_endpoint(db: AsyncSession = Depends(get_async_db))
async def get_async_db():
    """
    FastAPI dependency that provides a database session.
    Creates a new session for each request and ensures it's closed after.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# ==================== ENGINE FACTORY FOR CELERY ====================
# Celery tasks run in separate processes with different event loops.
# They need their own engine instances to avoid conflicts.

def create_task_engine():
    """
    Create a NEW engine instance for Celery tasks.
    Each task gets its own engine bound to its own event loop.
    This prevents "Event loop is closed" errors.
    """
    return create_async_engine(
        get_async_database_url(),
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,  # 5 minutes
        connect_args={
            "ssl": "require",
            "server_settings": {
                "application_name": "social_scheduler_celery"
            }
        }
    )

def get_async_session_local(engine):
    """
    Create a session maker bound to a specific engine.
    Used by Celery tasks with their task-local engine.
    """
    return async_sessionmaker(
        engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )