"""Modal deployment shim — ALL infrastructure lives here, as code.

Business logic stays in src/core/ (plain Python, no Modal imports) so the
same package runs on the mac mini, in tests, or anywhere else. This file
only maps that logic onto Modal: image, secrets, endpoints, schedules.
"""

import json

import modal
from fastapi import HTTPException, Request

APP_NAME = "notion-automations"  # also the Modal secret name (see justfile sync-secrets)

app = modal.App(APP_NAME)

image = (
    modal.Image.debian_slim(python_version="3.13")
    .uv_sync(extra_options="--no-dev")  # reads pyproject.toml + uv.lock; skip dev group
    # add_local_dir, NOT add_local_python_source: the latter can't resolve
    # packages under src/ layout, and this also carries non-.py data files.
    .add_local_dir("src/core", remote_path="/root/core", ignore=["**/__pycache__"])
)

secrets = [modal.Secret.from_name(APP_NAME)]


# daily() gets wired to src/core/registry.py once the dispatcher lands
# (later task) — the daily cron dispatcher.


@app.function(image=image, secrets=secrets, schedule=modal.Cron("30 9 * * *"))
def daily() -> dict:
    raise NotImplementedError("cron dispatch not yet wired to core.registry")


@app.function(image=image, secrets=secrets, min_containers=0)
@modal.fastapi_endpoint(method="POST")
async def notion_webhook(request: Request):
    from datetime import datetime, timezone

    from core.config import Settings
    from core.handlers import handle_event, verify_signature
    from core.notion import NotionClient

    body = await request.body()
    payload = json.loads(body)
    if "verification_token" in payload:  # one-time subscription handshake: surface it in logs
        print(f"NOTION VERIFICATION TOKEN: {payload['verification_token']}")
        return {"ok": True}
    s = Settings()
    if not verify_signature(
        body, request.headers.get("X-Notion-Signature", ""), s.notion_webhook_secret
    ):
        raise HTTPException(status_code=401)
    notion = NotionClient(s.notion_api_token, dry_run=s.dry_run)
    now = datetime.now(timezone.utc)
    # Notion sends one event per delivery (not a batch under "events" —
    # pinned against the docs 2026-08-20; "batched" in their docs means
    # multiple rapid edits get coalesced into fewer events upstream, not
    # multiple events per HTTP request).
    logs = handle_event(payload, notion, now, notion.me())
    print(logs)
    return {"ok": True, "handled": len(logs)}
