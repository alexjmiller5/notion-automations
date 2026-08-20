"""Run the daily dispatch logic locally, no Modal — for a dry-run sanity
check before deploying. Skips the reconciler's state persistence (no Modal
Dict outside the cloud); logs a fresh window each run.

Usage: DRY_RUN=true op run --env-file=.env.tpl -- uv run scripts/run_local.py
(also wired as `just run-local`)
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from core.asc import developer_id_expiry
from core.config import Settings
from core.dispatcher import check_cert, dispatch
from core.handlers import EVENT_DBS
from core.notion import NotionClient
from core.reconciler import reconcile


def main() -> None:
    s = Settings()
    notion = NotionClient(s.notion_api_token, dry_run=s.dry_run)
    now = datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo("America/New_York")).date()

    for line in dispatch(notion, today):
        print(line)
    print(check_cert(notion, developer_id_expiry(s), today))

    since = (now - timedelta(days=1)).isoformat()
    logs, _mark = reconcile(notion, EVENT_DBS, since, now)
    for line in logs:
        print(line)


if __name__ == "__main__":
    main()
