import os
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
print(f"DATABASE_URL: {db_url}")

if not db_url:
    print("❌ DATABASE_URL not found in .env!")
elif "localhost" in db_url:
    print("❌ DATABASE_URL is pointing to localhost!")
    print("   You need a real Neon database URL")
else:
    print("✅ DATABASE_URL looks correct")