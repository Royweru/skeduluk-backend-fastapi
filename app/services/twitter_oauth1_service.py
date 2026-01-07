import time
import hmac
import base64
import hashlib
import secrets
import urllib.parse
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app import models
from app.config import settings


REQUEST_TOKEN_URL = "https://api.twitter.com/oauth/request_token"
AUTHORIZE_URL = "https://api.twitter.com/oauth/authorize"
ACCESS_TOKEN_URL = "https://api.twitter.com/oauth/access_token"
CALLBACK_URL = f"{settings.BACKEND_URL}/auth/twitter/oauth1/callback"


def _percent_encode(s: str) -> str:
    return urllib.parse.quote(s, safe="")


def _oauth_signature(method, url, params, consumer_secret, token_secret=""):
    sorted_params = "&".join(
        f"{_percent_encode(k)}={_percent_encode(v)}"
        for k, v in sorted(params.items())
    )
    base_string = "&".join([
        method.upper(),
        _percent_encode(url),
        _percent_encode(sorted_params)
    ])
    signing_key = f"{_percent_encode(consumer_secret)}&{_percent_encode(token_secret)}"
    digest = hmac.new(
        signing_key.encode(),
        base_string.encode(),
        hashlib.sha1
    ).digest()
    return base64.b64encode(digest).decode()


class TwitterOAuth1Service:

    @classmethod
    async def initiate(cls, user_id: int):
        oauth_nonce = secrets.token_hex(16)
        oauth_timestamp = str(int(time.time()))

        params = {
            "oauth_callback": CALLBACK_URL,
            "oauth_consumer_key": settings.TWITTER_API_KEY,
            "oauth_nonce": oauth_nonce,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": oauth_timestamp,
            "oauth_version": "1.0",
        }

        signature = _oauth_signature(
            "POST",
            REQUEST_TOKEN_URL,
            params,
            settings.TWITTER_API_SECRET
        )
        params["oauth_signature"] = signature

        auth_header = "OAuth " + ", ".join(
            f'{k}="{_percent_encode(v)}"' for k, v in params.items()
        )

        async with httpx.AsyncClient() as client:
            res = await client.post(
                REQUEST_TOKEN_URL,
                headers={"Authorization": auth_header}
            )

        if res.status_code != 200:
            raise Exception(res.text)

        data = dict(urllib.parse.parse_qsl(res.text))
        return f"{AUTHORIZE_URL}?oauth_token={data['oauth_token']}"

    @classmethod
    async def callback(
        cls,
        oauth_token: str,
        oauth_verifier: str,
        db: AsyncSession,
        user_id: int
    ):
        oauth_nonce = secrets.token_hex(16)
        oauth_timestamp = str(int(time.time()))

        params = {
            "oauth_consumer_key": settings.TWITTER_API_KEY,
            "oauth_token": oauth_token,
            "oauth_verifier": oauth_verifier,
            "oauth_nonce": oauth_nonce,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": oauth_timestamp,
            "oauth_version": "1.0",
        }

        signature = _oauth_signature(
            "POST",
            ACCESS_TOKEN_URL,
            params,
            settings.TWITTER_API_SECRET
        )
        params["oauth_signature"] = signature

        auth_header = "OAuth " + ", ".join(
            f'{k}="{_percent_encode(v)}"' for k, v in params.items()
        )

        async with httpx.AsyncClient() as client:
            res = await client.post(
                ACCESS_TOKEN_URL,
                headers={"Authorization": auth_header}
            )

        if res.status_code != 200:
            raise Exception(res.text)

        data = dict(urllib.parse.parse_qsl(res.text))

        connection = models.SocialConnection(
            user_id=user_id,
            platform="TWITTER",
            platform_user_id=data["user_id"],
            platform_username=data["screen_name"],
            oauth_token=data["oauth_token"],
            oauth_token_secret=data["oauth_token_secret"],
            is_active=True
        )
        db.add(connection)
        await db.commit()
        return connection
