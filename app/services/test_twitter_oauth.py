# test_twitter_oauth.py
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def test_twitter_credentials():
    client_id = os.getenv("TWITTER_CLIENT_ID")
    client_secret = os.getenv("TWITTER_CLIENT_SECRET")
    
    print("=" * 60)
    print("TWITTER OAUTH CONFIGURATION TEST")
    print("=" * 60)
    
    print(f"\n✅ Client ID: {client_id[:15]}..." if client_id else "❌ Client ID: NOT SET")
    print(f"✅ Client Secret: Set" if client_secret else "❌ Client Secret: NOT SET")
    
    print(f"\nClient ID length: {len(client_id) if client_id else 0} characters")
    print(f"Client Secret length: {len(client_secret) if client_secret else 0} characters")
    
    # Twitter OAuth 2.0 Client IDs are typically 20-30 characters
    if client_id and len(client_id) < 15:
        print("\n⚠️  WARNING: Client ID seems too short. Are you sure this is the OAuth 2.0 Client ID?")
        print("   (Not the API Key?)")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_twitter_credentials())

