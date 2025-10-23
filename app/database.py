# app/database.py
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

load_dotenv()

def get_async_database_url():
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

# Create async engine
engine = create_async_engine(
    get_async_database_url(),
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={
        "ssl": "require",  # Neon requires SSL
        "server_settings": {
            "application_name": "social_scheduler"
        }
    }
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Create a Base class for our models
Base = declarative_base()

# Dependency to get async DB session
async def get_async_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()