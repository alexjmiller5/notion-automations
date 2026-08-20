"""All Notion API I/O lives here. Nothing else in core touches HTTP."""

from datetime import date, datetime

import httpx

from core.planner import TaskSnapshot
from core.rules import history_entry

API = "https://api.notion.com"


def task_properties(
    title, due, tags, priority, links="", notes="", blocked_by="", now: datetime | None = None
):
    """Build Tasks-DB page properties. Pass `now` for any bot-created task so
    it's born with an initial Tag & Date History entry - otherwise the daily
    reconciler flags it (and every task like it) the very next sweep."""
    props = {
        "Name": {"title": [{"text": {"content": title}}]},
        "Status": {"status": {"name": "To Do"}},
        "Due Date": {"date": {"start": due.isoformat()}},
        "Priority": {"select": {"name": priority}},
        "Tags": {"multi_select": [{"name": t} for t in tags]},
    }
    if links:
        props["Links"] = {"rich_text": [{"text": {"content": links}}]}
    if notes:
        props["Notes"] = {"rich_text": [{"text": {"content": notes}}]}
    if blocked_by:
        props["Blocked by"] = {"relation": [{"id": blocked_by}]}
    if now is not None:
        entry = history_entry(tags, due.isoformat(), now)
        props["Tag & Date History"] = {"rich_text": [{"text": {"content": entry}}]}
    return props


class NotionClient:
    def __init__(self, token, dry_run=False, transport=None):
        self._c = httpx.Client(
            base_url=API,
            transport=transport,
            timeout=30,
            headers={"Authorization": f"Bearer {token}", "Notion-Version": "2026-03-11"},
        )
        self.dry_run = dry_run
        self._me = None

    def _req(self, method, path, json=None):
        r = self._c.request(method, path, json=json)
        r.raise_for_status()
        return r.json()

    def query(self, data_source_id, filter=None, sorts=None, page_size=100):
        body = {"page_size": page_size}
        if filter:
            body["filter"] = filter
        if sorts:
            body["sorts"] = sorts
        results, cursor = [], None
        while True:
            if cursor:
                body["start_cursor"] = cursor
            out = self._req("POST", f"/v1/data_sources/{data_source_id}/query", body)
            results += out["results"]
            if not out.get("has_more"):
                return results
            cursor = out["next_cursor"]

    def get_page(self, page_id):
        return self._req("GET", f"/v1/pages/{page_id}")

    def create_page(self, data_source_id, properties, icon=None):
        if self.dry_run:
            print(
                f"DRY RUN create in {data_source_id}: {properties.get('Name') or properties.get('Title')}"
            )
            return {"id": "dry-run", "url": ""}
        body = {
            "parent": {"type": "data_source_id", "data_source_id": data_source_id},
            "properties": properties,
        }
        if icon:
            body["icon"] = icon
        return self._req("POST", "/v1/pages", body)

    def update_page(self, page_id, properties):
        if self.dry_run:
            print(f"DRY RUN update {page_id}: {list(properties)}")
            return {"id": "dry-run"}
        return self._req("PATCH", f"/v1/pages/{page_id}", {"properties": properties})

    def me(self):
        if not self._me:
            self._me = self._req("GET", "/v1/users/me")["id"]
        return self._me

    def snapshots(self, data_source_id, titles):
        snaps = []
        for title in titles:
            for p in self.query(
                data_source_id, filter={"property": "Name", "title": {"equals": title}}
            ):
                pr = p["properties"]
                due = (pr["Due Date"]["date"] or {}).get("start")
                comp = (pr["Completed Date"]["date"] or {}).get("start")
                snaps.append(
                    TaskSnapshot(
                        title=title,
                        status=pr["Status"]["status"]["name"],
                        due=date.fromisoformat(due[:10]) if due else None,
                        completed=date.fromisoformat(comp[:10]) if comp else None,
                    )
                )
        return snaps
