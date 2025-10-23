# init_db_simple.py
import os
import asyncio
import re
from sqlalchemy import text
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()

async def init_db():
    """Initialize database tables using Neon's approach"""
    print("Initializing database...")
    
    try:
        # Use the exact same approach as Neon's example
        engine = create_async_engine(
            re.sub(r'^postgresql:', 'postgresql+asyncpg:', os.getenv('DATABASE_URL')), 
            echo=True
        )
        
        # Import your models
        from app.models import Base
        
        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            print("✅ Database tables created successfully!")
        
        await engine.dispose()
        return True
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False

async def main():
    """Main function to test connection and initialize database"""
    # First test the connection
    print("Step 1: Testing database connection...")
    engine = create_async_engine(
        re.sub(r'^postgresql:', 'postgresql+asyncpg:', os.getenv('DATABASE_URL')), 
        echo=True
    )
    
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Connected to Neon PostgreSQL: {version}")
        
        await engine.dispose()
        
        # If connection is successful, initialize the database
        print("\nStep 2: Initializing database tables...")
        if await init_db():
            print("\n🎉 Database setup completed successfully!")
        else:
            print("\n❌ Database initialization failed!")
            
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())