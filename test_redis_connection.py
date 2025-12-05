import redis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

try:
    # Parse the Redis URL
    from urllib.parse import urlparse
    url = urlparse(REDIS_URL)

    # Connect to Redis
    r = redis.Redis(
        host=url.hostname,
        port=url.port,
        db=int(url.path[1:]) if url.path else 0,
        password=url.password,
        decode_responses=True
    )

    # Try to ping the Redis server
    response = r.ping()
    if response:
        print(f"✅ Successfully connected to Redis at {REDIS_URL}!")
    else:
        print(f"❌ Failed to ping Redis at {REDIS_URL}. Ping returned: {response}")

except redis.exceptions.ConnectionError as e:
    print(f"❌ Could not connect to Redis at {REDIS_URL}. Error: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
