#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
"""Idempotent, additive-only schema-ensure. Recreates properties the
automations depend on if a human deletes them from the live DB (this
happened to Tasks' "Tag & Date History" on 2026-08-19). Run once before
first deploy, and any time after such a deletion.

ADDITIVE-ONLY: every PATCH body below carries exactly one new property and
nothing else. A data-source PATCH that includes an existing select/
multi_select property wipes that property's options DB-wide if the type
key is sent empty (see the notion-cli skill gotcha) - never widen these
PATCH bodies to "sync" more than the single missing property at a time.
"""

import os

import httpx

TASKS = "77ef5074-aa23-468a-b5fb-2692e78184db"  # core/registry.py TASKS
H = {"Authorization": f"Bearer {os.environ['NOTION_API_TOKEN']}", "Notion-Version": "2026-03-11"}

# (data_source_id, property name, property-type body) - one property per entry, additive-only
REQUIRED_PROPERTIES = [
    (TASKS, "Tag & Date History", {"rich_text": {}}),
]


def ensure(data_source_id, name, body):
    ds = httpx.get(f"https://api.notion.com/v1/data_sources/{data_source_id}", headers=H).json()
    if name in ds["properties"]:
        print(f"present: '{name}' on {data_source_id}")
        return
    r = httpx.patch(
        f"https://api.notion.com/v1/data_sources/{data_source_id}",
        headers=H,
        json={"properties": {name: body}},
    )
    r.raise_for_status()
    print(f"created: '{name}' on {data_source_id}")


if __name__ == "__main__":
    for ds, name, body in REQUIRED_PROPERTIES:
        ensure(ds, name, body)
