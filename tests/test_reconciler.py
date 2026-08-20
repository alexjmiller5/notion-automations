"""Compliance reconciler tests. reconcile() only ever flags violations as
remediation tasks in TASKS - it never writes fixes back to the source page
(a human backfills the true event timestamps; the reconciler can't know
them). Calendar's missing-companion-note check is folded in here directly
since evaluate() deliberately excludes it (webhook-only rule elsewhere)."""

from datetime import datetime, timezone

from core import registry as R
from core.reconciler import reconcile

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


class FakeNotion:
    def __init__(self, pages_by_ds, pages_by_id=None):
        self.p, self.created = pages_by_ds, []
        self._by_id = pages_by_id or {}

    def query(self, ds, filter=None, **kw):
        return self.p.get(ds, [])

    def get_page(self, page_id):
        return self._by_id[page_id]

    def create_page(self, ds, props, icon=None):
        self.created.append((ds, props))
        return {"id": "t"}


def bad_book(pid="b1"):
    return {
        "id": pid,
        "url": f"https://notion.so/{pid}",
        "parent": {"data_source_id": R.BOOKS},
        "properties": {
            # "Finished" is the pinned Books status value that sets Date Read
            # (see rules.py TIMESTAMP_RULES / task-6-report.md); the brief's
            # fixture used "Completed", which fires no violation
            "Status": {"status": {"name": "Finished"}},
            "Date Read": {"date": None},
            "Title": {"title": [{"plain_text": "Bad Book"}]},
        },
    }


def cal_page(pid="c1", notes_rel=()):
    return {
        "id": pid,
        "url": f"https://notion.so/{pid}",
        "parent": {"data_source_id": R.CALENDAR},
        "properties": {
            "Title": {"title": [{"plain_text": "Dinner"}]},
            "Notes": {"relation": list(notes_rel)},
        },
    }


def test_violation_creates_remediation_task_not_fix():
    fake = FakeNotion({R.BOOKS: [bad_book()]})
    logs, mark = reconcile(fake, frozenset({R.BOOKS}), "2026-08-19T12:00:00+00:00", NOW)
    assert len(fake.created) == 1
    ds, props = fake.created[0]
    assert ds == R.TASKS
    title = props["Name"]["title"][0]["text"]["content"]
    assert "Bad Book" in title and "books-date-read-set" in title
    assert props["Priority"]["select"]["name"] == "High"
    assert props["Tags"]["multi_select"] == [{"name": "Chore"}]
    assert props["Links"]["rich_text"][0]["text"]["content"] == "https://notion.so/b1"
    assert mark == NOW.isoformat()


def test_compliant_pages_create_nothing():
    good = bad_book()
    good["properties"]["Date Read"] = {"date": {"start": "2026-08-01"}}
    fake = FakeNotion({R.BOOKS: [good]})
    logs, _ = reconcile(fake, frozenset({R.BOOKS}), "2026-08-19T12:00:00+00:00", NOW)
    assert fake.created == []


def test_one_task_per_page_even_with_multiple_violations():
    p = bad_book()
    fake = FakeNotion({R.TASKS: [], R.BOOKS: [p, p]})
    logs, _ = reconcile(fake, frozenset({R.BOOKS}), "2026-08-19T12:00:00+00:00", NOW)
    assert len(fake.created) == 1  # dedupe by page id within a run


def test_calendar_missing_note_flagged():
    fake = FakeNotion({R.CALENDAR: [cal_page()]})
    logs, _ = reconcile(fake, frozenset({R.CALENDAR}), "2026-08-19T12:00:00+00:00", NOW)
    assert len(fake.created) == 1
    ds, props = fake.created[0]
    assert ds == R.TASKS
    title = props["Name"]["title"][0]["text"]["content"]
    assert "Dinner" in title and "calendar-companion-note" in title


def test_calendar_with_note_creates_nothing():
    fake = FakeNotion({R.CALENDAR: [cal_page(notes_rel=[{"id": "n1"}])]})
    logs, _ = reconcile(fake, frozenset({R.CALENDAR}), "2026-08-19T12:00:00+00:00", NOW)
    assert fake.created == []


def trip_page(pid="tr1", title="Japan", notes_rel=()):
    return {
        "id": pid,
        "url": f"https://notion.so/{pid}",
        "parent": {"data_source_id": R.TRIPS},
        "properties": {
            "Name": {"title": [{"plain_text": title}]},
            "Notes": {"relation": list(notes_rel)},
        },
    }


def note_page(pid, title):
    return {
        "id": pid,
        "url": f"https://notion.so/{pid}",
        "parent": {"data_source_id": R.NOTES},
        "properties": {"Title": {"title": [{"plain_text": title}]}},
    }


def test_trips_mismatched_note_title_flagged():
    fake = FakeNotion(
        {R.TRIPS: [trip_page(notes_rel=[{"id": "n1"}])]},
        pages_by_id={"n1": note_page("n1", "Old Title")},
    )
    logs, _ = reconcile(fake, frozenset({R.TRIPS}), "2026-08-19T12:00:00+00:00", NOW)
    assert len(fake.created) == 1
    ds, props = fake.created[0]
    assert ds == R.TASKS
    title = props["Name"]["title"][0]["text"]["content"]
    assert "Japan" in title and "trips-note-title" in title


def test_trips_matching_note_title_creates_nothing():
    fake = FakeNotion(
        {R.TRIPS: [trip_page(notes_rel=[{"id": "n1"}])]},
        pages_by_id={"n1": note_page("n1", "Japan Notes")},
    )
    logs, _ = reconcile(fake, frozenset({R.TRIPS}), "2026-08-19T12:00:00+00:00", NOW)
    assert fake.created == []
