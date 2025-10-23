# app/db_init.py
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

from app.database import Base, get_async_database_url
from app.models import User, SocialConnection, Post, PostResult, Subscription, PostTemplate

load_dotenv()

async def drop_tables():
    """Drop all existing tables (use with caution!)"""
    print("Dropping all tables...")
    
    try:
        engine = create_async_engine(
            get_async_database_url(),
            connect_args={"ssl": "require"}
        )
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        await engine.dispose()
        print("✅ All tables dropped successfully!")
    except Exception as e:
        print(f"❌ Error dropping tables: {e}")
        import traceback
        traceback.print_exc()
        raise

async def init_db():
    """Initialize database tables"""
    print("Initializing database...")
    
    try:
        engine = create_async_engine(
            get_async_database_url(),
            connect_args={"ssl": "require"}
        )
        
        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
        
        await engine.dispose()
        print("✅ Database initialized successfully!")
        print("📋 Tables created:")
        print("  - users")
        print("  - social_connections")
        print("  - posts")
        print("  - post_results")
        print("  - subscriptions")
        print("  - post_templates")
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        raise

async def test_connection():
    """Test database connection"""
    print("Testing database connection...")
    
    try:
        # Get the URL and print it for debugging (hide password)
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            # Hide password for security
            safe_url = db_url
            if '@' in safe_url:
                parts = safe_url.split('@')
                if '://' in parts[0]:
                    user_part = parts[0].split('://')[1]
                    if ':' in user_part:
                        safe_url = safe_url.replace(user_part.split(':')[1], '****')
            print(f"Original URL: {safe_url}")
        
        async_url = get_async_database_url()
        # Hide password in async URL too
        safe_async_url = async_url
        if '@' in safe_async_url:
            parts = safe_async_url.split('@')
            if '://' in parts[0]:
                user_part = parts[0].split('://')[1]
                if ':' in user_part:
                    safe_async_url = safe_async_url.replace(user_part.split(':')[1], '****')
        print(f"Converted URL: {safe_async_url}")
        
        engine = create_async_engine(
            async_url,
            echo=False,
            connect_args={"ssl": "require"}
        )
        
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Connected to Neon PostgreSQL")
            print(f"   Version: {version[:80]}...")
        
        await engine.dispose()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def verify_tables():
    """Verify that all tables were created"""
    print("\nVerifying tables...")
    
    try:
        engine = create_async_engine(
            get_async_database_url(),
            connect_args={"ssl": "require"}
        )
        
        async with engine.connect() as conn:
            # Query to get all table names
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            
            tables = [row[0] for row in result.fetchall()]
            
            if tables:
                print("✅ Tables in database:")
                for table in tables:
                    print(f"   - {table}")
            else:
                print("⚠️  No tables found in database")
        
        await engine.dispose()
    except Exception as e:
        print(f"❌ Error verifying tables: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main function to test connection and initialize database"""
    print("=" * 60)
    print("DATABASE INITIALIZATION")
    print("=" * 60)
    
    # First test the connection
    if await test_connection():
        print()
        # If connection is successful, initialize the database
        await init_db()
        print()
        # Verify tables were created
        await verify_tables()
        print()
        print("=" * 60)
        print("✅ DATABASE SETUP COMPLETE!")
        print("=" * 60)
    else:
        print("=" * 60)
        print("❌ Database initialization aborted due to connection failure.")
        print("=" * 60)

async def reset_db():
    """Drop and recreate all tables (use with caution!)"""
    print("=" * 60)
    print("⚠️  DATABASE RESET - THIS WILL DELETE ALL DATA!")
    print("=" * 60)
    
    if await test_connection():
        await drop_tables()
        print()
        await init_db()
        print()
        await verify_tables()
        print()
        print("=" * 60)
        print("✅ DATABASE RESET COMPLETE!")
        print("=" * 60)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        asyncio.run(reset_db())
    else:
        asyncio.run(main())