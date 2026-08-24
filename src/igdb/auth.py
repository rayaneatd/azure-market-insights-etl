import httpx
from datetime import datetime, timedelta
from src.config import (
    TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET
)

class TwitchAuth:
    def __init__(self):
        self.client_id = TWITCH_CLIENT_ID
        self.client_secret = TWITCH_CLIENT_SECRET
        self.access_token = None
        self.expires_at = None
        self.token_type = None

    def get_access_token(self):
        if self.access_token and self.expires_at and self.expires_at > datetime.now() + timedelta(seconds=60):
            return self.access_token
        self.refresh_access_token()
        return self.access_token

    def refresh_access_token(self):
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        response = httpx.post(url, params=params, timeout=10)
        response.raise_for_status()
        import msgspec
        data = msgspec.json.decode(response.content)
        self.access_token = data["access_token"]
        self.expires_at = datetime.now() + timedelta(seconds=data["expires_in"])
        self.token_type = data["token_type"]