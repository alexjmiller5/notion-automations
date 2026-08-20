import httpx
import json
from core.notion import NotionClient, task_properties
from datetime import date, datetime, timezone


def make_client(handler, dry_run=False):
    return NotionClient(token="t", dry_run=dry_run, transport=httpx.MockTransport(handler))


def test_query_paginates():
    calls = []

    def handler(req):
        calls.append(json.loads(req.content))
        if len(calls) == 1:
            return httpx.Response(
                200, json={"results": [{"id": "1"}], "has_more": True, "next_cursor": "c"}
            )
        return httpx.Response(200, json={"results": [{"id": "2"}], "has_more": False})

    out = make_client(handler).query("ds")
    assert [r["id"] for r in out] == ["1", "2"]
    assert calls[1]["start_cursor"] == "c"


def test_create_page_dry_run_skips_http():
    def handler(req):
        raise AssertionError("no HTTP in dry run")

    out = make_client(handler, dry_run=True).create_page("ds", {"x": 1})
    assert out["id"] == "dry-run"


def test_task_properties_payload():
    p = task_properties("T", date(2026, 11, 2), ("Chore",), "High", blocked_by="abc")
    assert p["Name"]["title"][0]["text"]["content"] == "T"
    assert p["Due Date"]["date"]["start"] == "2026-11-02"
    assert p["Status"]["status"]["name"] == "To Do"
    assert p["Priority"]["select"]["name"] == "High"
    assert p["Tags"]["multi_select"] == [{"name": "Chore"}]
    assert p["Blocked by"]["relation"] == [{"id": "abc"}]
    assert "Tag & Date History" not in p  # no `now` passed -> bot-created page stays historyless


def test_task_properties_with_now_includes_history_entry():
    # bot-created tasks must be born history-compliant (else the daily reconciler
    # immediately flags them) - passing `now` adds the initial audit-log entry in
    # the exact format rules.py's evaluate() uses for the same rule.
    now = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)  # 08:00 America/New_York (EDT)
    p = task_properties("T", date(2026, 11, 2), ("Chore", "Errand"), "High", now=now)
    entry = p["Tag & Date History"]["rich_text"][0]["text"]["content"]
    assert entry == "[2026-08-20 08:00] --- Tags: [Chore, Errand], Due Date: 2026-11-02"


def test_headers():
    def handler(req):
        assert req.headers["Authorization"] == "Bearer t"
        assert req.headers["Notion-Version"] == "2026-03-11"
        return httpx.Response(200, json={"results": [], "has_more": False})

    make_client(handler).query("ds")
