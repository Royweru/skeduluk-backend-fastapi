# test_neon_connection.py
import os
import asyncio
import re
from sqlalchemy import text
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from urllib.parse import urlparse, urlunparse

load_dotenv()

async def test_connection():
    """Test database connection using Neon's recommended approach"""
    print("Testing database connection with Neon's approach...")
    
    try:
        # Get DATABASE_URL
        db_url = os.getenv('DATABASE_URL')
        
        # Parse the URL to remove all query parameters
        parsed = urlparse(db_url)
        # Reconstruct URL without query parameters
        clean_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            '',  # params
            '',  # query - remove this
            ''   # fragment
        ))
        
        # Convert to asyncpg
        async_url = clean_url.replace('postgresql://', 'postgresql+asyncpg://')
        
        print(f"Connecting to: {async_url}")  # Debug print (credentials hidden)
        
        engine = create_async_engine(
            async_url,
            echo=True,
            connect_args={"ssl": "require"}
        )
        
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Connected to Neon PostgreSQL: {version}")
        
        await engine.dispose()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    if await test_connection():
        print("Connection test successful!")
    else:
        print("Connection test failed!")

if __name__ == "__main__":
    asyncio.run(main())