"""Settings from env vars - Modal Secret in the cloud, `op run` locally.

One field per line in .env.tpl. Instantiate Settings() inside functions,
not at import time, so tests can run without secrets.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    notion_api_token: str
    notion_webhook_secret: str = ""  # empty until subscription created
    dry_run: bool = False
