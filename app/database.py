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

engine = create_async_engine(
    get_async_database_url(),
    echo=False,
    pool_pre_ping=True,  # Verify connections are alive before using
    pool_recycle=300,  # Recycle connections after 5 minutes
    pool_size=20,  # ✅ Increased pool size for concurrent requests
    max_overflow=10,  # ✅ Allow extra connections during peak
    pool_timeout=30,  # ✅ Wait up to 30 seconds for a connection
    connect_args={
        "ssl": "require",  # Neon requires SSL
        "timeout": 60,  # ✅ 60 second connection timeout
        "command_timeout": 60,  # ✅ 60 second command timeout
        "server_settings": {
            "application_name": "social_scheduler_fastapi",
            "jit": "off"  # Disable JIT for faster simple queries
        }
    }
)

# Create async session factory for FastAPI
AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()

# ==================== DEPENDENCY FOR FASTAPI ====================

async def get_async_db():
    """
    FastAPI dependency that provides a database session.
    ✅ Improved error handling for connection issues
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            print(f"❌ Database session error: {e}")
            # Let FastAPI's exception handler deal with it
            raise
        finally:
            # Close session cleanly
            try:
                await session.close()
            except Exception as close_error:
                print(f"⚠️ Error closing session: {close_error}")
                # Don't re-raise - session is already problematic

# ==================== ENGINE FACTORY FOR CELERY ====================

def create_task_engine():
    """
    Create a NEW engine instance for Celery tasks.
    Each task gets its own engine bound to its own event loop.
    """
    return create_async_engine(
        get_async_database_url(),
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=10,  # Smaller pool for Celery workers
        max_overflow=5,
        pool_timeout=30,
        connect_args={
            "ssl": "require",
            "timeout": 60,
            "command_timeout": 60,
            "server_settings": {
                "application_name": "social_scheduler_celery",
                "jit": "off"
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