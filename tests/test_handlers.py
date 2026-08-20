"""Webhook handler tests. Event shape is pinned against the real Notion
webhook docs (2026-08-20 read of developers.notion.com/reference/webhooks*),
not the brief's guesses - see task-7-report.md for the full correction list.
Key corrections baked into these fixtures:
  - event.entity has both "id" and "type" (we only act on type == "page")
  - event.data.parent has {"id", "type"} - NEVER a "data_source_id". The
    data_source_id comes only from the fetched Page object's own "parent"
    field (page["parent"]["data_source_id"], per the 2025-09-03+ Pages API),
    so handle_event always fetches the page before routing.
  - event.data.updated_properties carries property IDs (short opaque
    strings), not names - handlers.py resolves names via each property's
    own "id" field on the fetched page.
  - one event per HTTP delivery (no "events" batch wrapper).
"""

import hashlib
import hmac
from datetime import datetime, timezone

from core import registry as R
from core.handlers import handle_event, verify_signature

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def sig(body: bytes, secret="s"):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_signature_roundtrip():
    body = b'{"x":1}'
    assert verify_signature(body, sig(body), "s")
    assert not verify_signature(body, sig(body), "wrong")
    assert not verify_signature(b"tampered", sig(body), "s")


class FakeNotion:
    def __init__(self, pages):
        self.pages, self.updated, self.created = pages, [], []

    def get_page(self, pid):
        return self.pages[pid]

    def update_page(self, pid, props):
        self.updated.append((pid, props))

    def create_page(self, ds, props, icon=None):
        self.created.append((ds, props))
        return {"id": "new-note"}


def event(
    page_id, etype="page.properties_updated", author="other-bot", entity_type="page", updated=()
):
    return {
        "type": etype,
        "entity": {"id": page_id, "type": entity_type},
        "data": {
            "parent": {"id": "irrelevant", "type": "data_source"},
            "updated_properties": list(updated),
        },
        "authors": [{"id": author}],
    }


def test_loop_guard_skips_own_events():
    fake = FakeNotion({})
    out = handle_event(event("p", author="me"), fake, NOW, bot_id="me")
    assert out == ["skipped: self-authored"] and fake.updated == []


def test_non_page_entity_skipped():
    fake = FakeNotion({})
    out = handle_event(event("c", entity_type="comment"), fake, NOW, bot_id="me")
    assert out == ["skipped: non-page entity"]


def test_unwatched_db_skipped():
    fake = FakeNotion(
        {"p": {"id": "p", "url": "u", "parent": {"data_source_id": R.GIFTS}, "properties": {}}}
    )
    out = handle_event(event("p"), fake, NOW, bot_id="me")
    assert out == [f"skipped: unwatched db {R.GIFTS}"]
    assert fake.updated == []


def test_book_completion_gets_fix_applied():
    fake = FakeNotion(
        {
            "p": {
                "id": "p",
                "url": "u",
                "parent": {"data_source_id": R.BOOKS},
                "properties": {
                    "Status": {"status": {"name": "Finished"}},
                    "Date Read": {"date": None},
                    "Title": {"title": [{"plain_text": "B"}]},
                },
            }
        }
    )
    handle_event(event("p"), fake, NOW, bot_id="me")
    assert fake.updated and "Date Read" in fake.updated[0][1]


def test_calendar_page_added_creates_companion_note():
    fake = FakeNotion(
        {
            "p": {
                "id": "p",
                "url": "u",
                "parent": {"data_source_id": R.CALENDAR},
                "properties": {
                    "Title": {"title": [{"plain_text": "Dinner"}]},
                    "Notes": {"relation": []},
                },
            }
        }
    )
    handle_event(event("p", etype="page.created"), fake, NOW, bot_id="me")
    assert fake.created[0][0] == R.NOTES
    assert fake.created[0][1]["Title"]["title"][0]["text"]["content"] == "Dinner Notes"
    assert ("p", {"Notes": {"relation": [{"id": "new-note"}]}}) in fake.updated


def test_trip_edit_syncs_linked_note_title():
    fake = FakeNotion(
        {
            "trip": {
                "id": "trip",
                "url": "u",
                "parent": {"data_source_id": R.TRIPS},
                "properties": {
                    "Name": {"title": [{"plain_text": "Japan"}]},
                    "Notes": {"relation": [{"id": "note1"}]},
                },
            },
            "note1": {
                "id": "note1",
                "url": "u",
                "parent": {"data_source_id": R.NOTES},
                "properties": {"Title": {"title": [{"plain_text": "Old Title"}]}},
            },
        }
    )
    handle_event(event("trip"), fake, NOW, bot_id="me")
    assert ("note1", {"Title": {"title": [{"text": {"content": "Japan Notes"}}]}}) in fake.updated


def test_tasks_edit_appends_history():
    fake = FakeNotion(
        {
            "p": {
                "id": "p",
                "url": "u",
                "parent": {"data_source_id": R.TASKS},
                "properties": {
                    "Status": {"status": {"name": "To Do"}},
                    "Completed Date": {"date": None},
                    "Due Date": {"id": "dueid", "date": {"start": "2026-09-01"}},
                    "Tags": {"id": "tagsid", "multi_select": [{"name": "Chore"}]},
                    "Priority": {"select": {"name": "High"}},
                    "Tag & Date History": {
                        "rich_text": [{"plain_text": "[old] --- Tags: [], Due Date: x"}]
                    },
                    "Name": {"title": [{"plain_text": "T"}]},
                },
            }
        }
    )
    handle_event(event("p", updated=["dueid"]), fake, NOW, bot_id="me")
    ((pid, props),) = [u for u in fake.updated if "Tag & Date History" in u[1]]
    text = props["Tag & Date History"]["rich_text"][0]["text"]["content"]
    assert text.startswith("[old] --- Tags: [], Due Date: x\n[2026-08-20")


def test_tasks_edit_ignores_untracked_property():
    fake = FakeNotion(
        {
            "p": {
                "id": "p",
                "url": "u",
                "parent": {"data_source_id": R.TASKS},
                "properties": {
                    "Status": {"id": "statusid", "status": {"name": "To Do"}},
                    "Completed Date": {"date": None},
                    "Due Date": {"id": "dueid", "date": {"start": "2026-09-01"}},
                    "Tags": {"id": "tagsid", "multi_select": [{"name": "Chore"}]},
                    "Priority": {"select": {"name": "High"}},
                    "Tag & Date History": {
                        "rich_text": [{"plain_text": "[old] --- Tags: [], Due Date: x"}]
                    },
                    "Name": {"title": [{"plain_text": "T"}]},
                },
            }
        }
    )
    handle_event(event("p", updated=["statusid"]), fake, NOW, bot_id="me")
    assert not any("Tag & Date History" in u[1] for u in fake.updated)
