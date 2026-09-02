"""Settings from env vars - Modal Secret in the cloud, `op run` locally.

One field per line in .env.tpl. Instantiate Settings() inside functions,
not at import time, so tests can run without secrets.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    notion_api_token: str
    notion_webhook_secret: str = ""  # empty until subscription created
    life_hub_url: str  # life-data hub serving the recurring_specs/cc_keepalive_cards tables
    life_hub_token: str
    notion_tasks_place_tags: str = ""  # comma-separated Tags exempt from the default due date
    dry_run: bool = False

    @property
    def place_tags(self) -> tuple[str, ...]:
        return tuple(t.strip() for t in self.notion_tasks_place_tags.split(",") if t.strip())
