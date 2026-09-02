"""Run the daily dispatch logic locally, no Modal - for a dry-run sanity
check before deploying. Skips the reconciler's state persistence (no Modal
Dict outside the cloud); logs a fresh window each run.

Usage: PYTHONPATH=src DRY_RUN=true op run --env-file=.env.tpl -- uv run scripts/run_local.py
(also wired as `just run-local`, which sets PYTHONPATH=src automatically -
plain `uv run` doesn't apply pytest's pythonpath config, so `core` isn't
importable without it)
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from core.config import Settings
from core.dispatcher import dispatch
from core.handlers import EVENT_DBS
from core.hub import pull_rows
from core.notion import NotionClient
from core.reconciler import reconcile
from core.registry import CARD_COLUMNS, SPEC_COLUMNS, load_cards, load_recurring


def main() -> None:
    s = Settings()
    notion = NotionClient(s.notion_api_token, dry_run=s.dry_run)
    now = datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo("America/New_York")).date()

    recurring = load_recurring(
        pull_rows(s.life_hub_url, s.life_hub_token, "recurring_specs", SPEC_COLUMNS)
    )
    cards = load_cards(
        pull_rows(s.life_hub_url, s.life_hub_token, "cc_keepalive_cards", CARD_COLUMNS)
    )
    for line in dispatch(notion, today, recurring, cards):
        print(line)

    since = (now - timedelta(days=1)).isoformat()
    logs, _mark = reconcile(notion, EVENT_DBS, since, now)
    for line in logs:
        print(line)


if __name__ == "__main__":
    main()
