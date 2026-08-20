"""Modal deployment shim — ALL infrastructure lives here, as code.

Business logic stays in src/core/ (plain Python, no Modal imports) so the
same package runs on the mac mini, in tests, or anywhere else. This file
only maps that logic onto Modal: image, secrets, endpoints, schedules.
"""

import modal

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


# process()/webhook()/daily() get wired to src/core/registry.py once the
# planner, rules, and notion client land (later tasks) — the Notion webhook
# receiver and the daily cron dispatcher.


@app.function(image=image, secrets=secrets, schedule=modal.Cron("30 9 * * *"))
def daily() -> dict:
    raise NotImplementedError("cron dispatch not yet wired to core.registry")
